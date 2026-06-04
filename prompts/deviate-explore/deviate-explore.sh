#!/usr/bin/env bash
#
# explore.sh - Orchestrator for the /deviate-explore (PHASE_EXPLORE) macro layer
#
# This script wraps operational concerns of the explore workflow:
#   - Repository discovery (walk-up to .git)
#   - Constitutional validation gate
#   - Feature bucket allocation (next NNN index in specs/)
#   - Feature slug derivation
#   - Active-feature marker write
#   - Issue ledger scratch entry
#   - Pre-flight validation of explore.md (required sections, evidence rows)
#   - Atomic git commit
#
# Usage:
#   explore.sh pre "<problem-statement>"
#   explore.sh post
#
# The 'pre' subcommand emits a JSON contract to stdout. The contract carries
# the absolute paths the orchestrator must use and the metadata for the
# downstream 'research' skill. The 'post' subcommand reads the LLM-written
# artifact, validates it, commits it, and returns STATUS: SUCCESS.
#
# Exit codes:
#   0   Success
#   1   Invalid arguments
#   2   Pre-flight check failed (not a repo, constitution missing)
#   3   Feature bucket allocation failed
#   5   Content validation failed
#   6   Commit / ledger update failed
#
set -euo pipefail

SCRIPT_NAME="$(basename "$0")"

# Shared library: colors, logging, find_repo_root, create_temp_dir, etc.
# shellcheck disable=SC1054,SC1009,SC1083,SC1073,SC1056,SC1072  # chezmoi template directive, not real bash
# shellcheck disable=SC2148
#
# common.sh.tmpl — Shared Library for Orchestrator Scripts
#
# This chezmoi template is expanded inline at render time into every
# orchestrator script that includes it via the chezmoi template directive
# (curly-percent template "scripts/lib/common.sh.tmpl" percent-curly).
#
# Provided exports:
#   Color constants:     RED, GREEN, YELLOW, BLUE, NC
#   Logging:             log_info(), log_ok(), log_warn(), log_err()
#   Skill directory:     resolve_skill_dir() — optional; sets SKILL_DIR
#   Repository:          find_repo_root()
#   Temp dir:            create_temp_dir()
#   Git state:           gather_git_state() — staged/unstaged/untracked as JSON
#   JSON helpers:        emit_json_contract(), build_json_contract()
#
# Spec workflow functions (used by deviate-specify, deviate-tasks, and related scripts):
#   Branch validation:   validate_worktree_branch()
#   Ledger checks:       check_ledger_dirty()
#   Issue resolution:    get_issue_by_id(), select_next_unblocked_issue(),
#                        read_issue_body(), parse_source_file()
#   PRD traceability:    extract_prd_requirements(), validate_traceability()
#   Section validation:  extract_spec_sections(), extract_section_body()
#   Gherkin validation:  validate_gherkin_syntax()
#   Artifact commits:    commit_phase_artifact(), commit_phase_files()
#
# All logging functions write exclusively to stderr (>&2).
#

# ── Color Constants ──────────────────────────────────────────────────────

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# ── Optional Skill Directory Resolution ─────────────────────────────────

# Resolve SKILL_DIR to the directory containing the orchestrator script.
# Uses BASH_SOURCE[0] which correctly resolves because the library is
# expanded inline at render time (not sourced at runtime).
#
# Only sets SKILL_DIR if not already exported by the environment or script.
# Scripts can skip this entirely if they manage SKILL_DIR independently.
#
# Usage (optional — only if the script needs $SKILL_DIR):
#   resolve_skill_dir
resolve_skill_dir() {
	if [ -z "${SKILL_DIR:-}" ]; then
	SKILL_DIR="$(CDPATH="" cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
	export SKILL_DIR
	fi
}

# ── Logging Functions (stderr only) ──────────────────────────────────────

log_info() { echo -e "${BLUE}[INFO]${NC}  $*" >&2; }
log_ok()   { echo -e "${GREEN}[OK]${NC}    $*" >&2; }
log_warn() { echo -e "${YELLOW}[WARN]${NC}  $*" >&2; }
log_err()  { echo -e "${RED}[ERROR]${NC} $*" >&2; }

# Aliases for backward compatibility with scripts using different naming
log_success() { log_ok "$@"; }
log_error()   { log_err "$@"; }

# ── Repository Discovery ─────────────────────────────────────────────────

# Walk up from the given directory to locate a .git directory or file.
# Returns the repo root path on success (exit 0), empty string on failure
# (exit 1).
find_repo_root() {
	local dir="${1:-$(pwd)}"
	if [ -d "$dir/.git" ] || [ -f "$dir/.git" ]; then
	echo "$dir"
	return 0
	fi
	while [ "$dir" != "/" ]; do
	dir="$(dirname "$dir")"
	if [ -d "$dir/.git" ] || [ -f "$dir/.git" ]; then
	    echo "$dir"
	    return 0
	fi
	done
	return 1
}

# ── XDG-Compliant Temp Directory Creation ────────────────────────────────

# Create a temporary directory using XDG-compliant path resolution.
# Fallback chain:
#   ${TMPDIR} → ${XDG_STATE_HOME} → ${HOME}/.local/state → /tmp → /dev/shm
#
# Usage:
#   local temp_dir
#   temp_dir=$(create_temp_dir "my-prefix") || exit 1
#
# On failure, prints a diagnostic to stderr and returns exit code 1.
create_temp_dir() {
	local prefix="${1:-tmp}"
	local base=""

	# Resolve base directory — prefer proper temp locations first
	if [ -n "${TMPDIR:-}" ]; then
	base="$TMPDIR"
	else
	base="/tmp"
	fi

	# Attempt creation in resolved base
	if [ -n "$base" ]; then
	mkdir -p "$base" 2>/dev/null
	local temp_dir
	temp_dir=$(mktemp -d "$base/${prefix}.XXXXXX" 2>/dev/null) && {
	    echo "$temp_dir"
	    return 0
	}
	fi

	# Fallback to /dev/shm
	if [ -d "/dev/shm" ]; then
	temp_dir=$(mktemp -d "/dev/shm/${prefix}.XXXXXX" 2>/dev/null) && {
	    echo "$temp_dir"
	    return 0
	}
	fi

	# Fallback to XDG state home
	if [ -n "${XDG_STATE_HOME:-}" ]; then
	mkdir -p "$XDG_STATE_HOME" 2>/dev/null
	temp_dir=$(mktemp -d "$XDG_STATE_HOME/${prefix}.XXXXXX" 2>/dev/null) && {
	    echo "$temp_dir"
	    return 0
	}
	fi

	# Fallback to home local state
	if [ -n "${HOME:-}" ]; then
	mkdir -p "${HOME}/.local/state" 2>/dev/null
	temp_dir=$(mktemp -d "${HOME}/.local/state/${prefix}.XXXXXX" 2>/dev/null) && {
	    echo "$temp_dir"
	    return 0
	}
	fi

	# All fallbacks exhausted
	log_err "Cannot create temp directory (all locations unwritable)"
	return 1
}

# ── Git State Gathering ───────────────────────────────────────────────────

# Gather staged, unstaged, and untracked file information as JSON.
# Outputs a JSON object to stdout with file lists and counts.
# Returns 0 on success, 1 if not in a git repository.
#
# Usage:
#   git_state=$(gather_git_state) || exit 1
#   # => {"staged_files":"file1 file2","staged_count":2,"unstaged_files":"file3",...}
gather_git_state() {
	# Validate we're in a git repository
	if ! git rev-parse --show-toplevel >/dev/null 2>&1; then
	log_err "Not a git repository"
	return 1
	fi

	# Validate jq availability (required for JSON contract emission)
	if ! command -v jq >/dev/null 2>&1; then
	log_err "gather_git_state requires jq for JSON contract emission"
	return 1
	fi

	# Gather file lists
	local staged_files unstaged_files untracked_files
	staged_files=$(git diff --cached --name-only 2>/dev/null | tr '\n' ' ' | sed 's/ $//')
	unstaged_files=$(git diff --name-only 2>/dev/null | tr '\n' ' ' | sed 's/ $//')
	untracked_files=$(git ls-files --others --exclude-standard 2>/dev/null | tr '\n' ' ' | sed 's/ $//')

	# Count files
	local staged_count=0 unstaged_count=0 untracked_count=0
	[[ -n "$staged_files" ]] && staged_count=$(echo "$staged_files" | wc -w | tr -d ' ')
	[[ -n "$unstaged_files" ]] && unstaged_count=$(echo "$unstaged_files" | wc -w | tr -d ' ')
	[[ -n "$untracked_files" ]] && untracked_count=$(echo "$untracked_files" | wc -w | tr -d ' ')

	# Build JSON arrays for file lists
	# SC2086: Word splitting on space-separated git output is intentional
	local staged_json="[]" unstaged_json="[]" untracked_json="[]"
	if [[ -n "$staged_files" ]]; then
	# shellcheck disable=SC2086
	staged_json=$(printf '%s\n' $staged_files | jq -R -s 'split("\n") | map(select(length > 0))')
	fi
	if [[ -n "$unstaged_files" ]]; then
	# shellcheck disable=SC2086
	unstaged_json=$(printf '%s\n' $unstaged_files | jq -R -s 'split("\n") | map(select(length > 0))')
	fi
	if [[ -n "$untracked_files" ]]; then
	# shellcheck disable=SC2086
	untracked_json=$(printf '%s\n' $untracked_files | jq -R -s 'split("\n") | map(select(length > 0))')
	fi

	# Emit JSON object
	jq -n \
	--arg staged_files "$staged_files" \
	--arg unstaged_files "$unstaged_files" \
	--arg untracked_files "$untracked_files" \
	--argjson staged_count "$staged_count" \
	--argjson unstaged_count "$unstaged_count" \
	--argjson untracked_count "$untracked_count" \
	--argjson staged_json "$staged_json" \
	--argjson unstaged_json "$unstaged_json" \
	--argjson untracked_json "$untracked_json" \
	'{
	    staged_files: $staged_files,
	    unstaged_files: $unstaged_files,
	    untracked_files: $untracked_files,
	    staged_count: $staged_count,
	    unstaged_count: $unstaged_count,
	    untracked_count: $untracked_count,
	    staged_json: $staged_json,
	    unstaged_json: $unstaged_json,
	    untracked_json: $untracked_json
	}'
}

# ── JSON Contract Emission ───────────────────────────────────────────────

# Emit a JSON object to stdout constructed from alternating key/value
# arguments. Uses jq --arg for proper escaping of all values.
#
# Usage:
#   emit_json_contract "name" "test" "version" "1.0"
#   # => {"name":"test","version":"1.0"}
#
# With an odd number of arguments, emits an empty JSON object to stdout
# and a warning to stderr.
emit_json_contract() {
	local json="{}"

	while [ $# -gt 1 ]; do
	json=$(echo "$json" | jq --arg k "$1" --arg v "$2" '. + {($k): $v}')
	shift 2
	done

	if [ $# -eq 1 ]; then
	log_warn "emit_json_contract called with odd argument count"
	echo "{}"
	return 0
	fi

	echo "$json"
}

# ── Spec Workflow Functions ──────────────────────────────────────────────────

# Validate that a branch name is valid for worktree operations.
# Returns 0 if branch is valid (not main/master/HEAD/detached), 1 otherwise.
#
# Usage:
#   if validate_worktree_branch "feat/my-feature"; then ...
validate_worktree_branch() {
	local branch="$1"
	case "$branch" in
	main|master|HEAD|unknown|"") return 1 ;;
	*) return 0 ;;
	esac
}

# Check if the issues ledger has uncommitted changes.
# Returns 0 if ledger is clean (no uncommitted changes), 1 if dirty.
# Path to ledger file: REPO_ROOT/specs/issues.jsonl
#
# Usage:
#   if check_ledger_dirty "$repo_root"; then ...
check_ledger_dirty() {
	local repo_root="$1"
	if [[ -z "$repo_root" ]]; then
	log_err "check_ledger_dirty requires repo_root"
	return 1
	fi
	local dirty
	dirty=$(cd "$repo_root" && git status --porcelain specs/issues.jsonl 2>/dev/null || true)
	[[ -n "$dirty" ]]
}

# Read the latest state of a single issue by ID from the JSONL ledger.
# Outputs a JSON object with the issue's current fields on stdout.
# Returns non-zero if issue not found.
#
# Usage:
#   issue_json=$(get_issue_by_id "$repo_root" "ISS-001")
get_issue_by_id() {
	local repo_root="$1"
	local issue_id="$2"
	local issues_file="$repo_root/specs/issues.jsonl"

	if [[ ! -f "$issues_file" ]]; then
	log_err "issues ledger not found: $issues_file"
	return 1
	fi

	if ! grep -q "\"issue_id\": \"$issue_id\"" "$issues_file"; then
	log_err "issue $issue_id not found in ledger"
	return 1
	fi

	if ! command -v jq >/dev/null 2>&1; then
	log_err "jq required for issue resolution"
	return 1
	fi

	# Reduce to latest state per issue_id, then filter to the requested one
	jq -R 'fromjson' "$issues_file" 2>/dev/null \
	| jq -s --arg id "$issue_id" '
	    group_by(.issue_id) | map(last) | .[]
	    | select(.issue_id == $id)
	'
}

# Select the oldest unblocked BACKLOG feature issue (auto-pick) from the JSONL ledger.
# Uses self-contained jq logic — no external scripts required.
# Determines "unblocked" by checking that all blocked_by issue IDs have a COMPLETED
# status in the ledger (or the blocked_by list is empty).
#
# Outputs a JSON object for the selected issue on stdout.
# Returns non-zero if no unblocked issues are available.
#
# Usage:
#   issue_json=$(select_next_unblocked_issue "$repo_root")
select_next_unblocked_issue() {
	local repo_root="$1"
	local issues_file="$repo_root/specs/issues.jsonl"

	if [[ ! -f "$issues_file" ]]; then
	log_err "issues ledger not found: $issues_file"
	return 1
	fi

	if ! command -v jq >/dev/null 2>&1; then
	log_err "jq required for issue resolution"
	return 1
	fi

	local selected
	selected=$(jq -R 'fromjson' "$issues_file" 2>/dev/null |
		jq -s '
	    ([.[] | select(.type == "feature")]
	        | group_by(.issue_id) | map(last)) as $features
	    | ([.[] | select((.type | not) and .status == "COMPLETED")]
	        | map(.issue_id) | unique) as $completed
	    | ($features
	        | map({key: .issue_id, value: .status})
	        | from_entries) as $status_map
	    | [$features[]
	        | select(.status == "BACKLOG"
	            and (
	                (.blocked_by // [] | length == 0)
	                or all(.blocked_by[];
	                    IN($completed[])
	                    or ($status_map[.] // "UNKNOWN") == "COMPLETED"
	                )
	            ))]
	    | sort_by(.created_at // .timestamp // "1970-01-01")
	    | .[0] // empty
	')

	if [[ -z "$selected" ]] || [[ "$selected" == "null" ]]; then
	log_err "no unblocked BACKLOG feature issues available"
	return 1
	fi

	echo "$selected"
}

# Read the issue body markdown file referenced by source_file.
# Outputs the file contents on stdout.
#
# Usage:
#   issue_body=$(read_issue_body "$repo_root" "specs/001/issues/001-feature.md")
# shellcheck disable=SC2120,SC2329  # Only used by scripts with their own override
read_issue_body() {
	local repo_root="$1"
	local source_file="$2"
	local full_path="$repo_root/$source_file"

	if [[ ! -f "$full_path" ]]; then
	log_err "issue body file not found: $source_file"
	return 1
	fi

	cat "$full_path"
}

# Parse a source_file path of the form specs/{epic}/issues/{number}-{slug}.md
# Sets globals: ISSUE_EPIC, ISSUE_NUMBER, ISSUE_SLUG, ISSUE_NUMBER_INT
# Returns non-zero if path doesn't match expected pattern.
#
# Usage:
#   if parse_source_file "specs/001/issues/001-feature.md"; then
#     echo "Epic: $ISSUE_EPIC, Number: $ISSUE_NUMBER_INT"
#   fi
parse_source_file() {
	local source_file="$1"
	if [[ ! "$source_file" =~ ^specs/([^/]+)/issues/([0-9]+)-(.+)\.md$ ]]; then
	log_err "source_file does not match expected pattern: $source_file"
	return 1
	fi
	# shellcheck disable=SC2034  # Set for caller
	ISSUE_EPIC="${BASH_REMATCH[1]}"
	# shellcheck disable=SC2034
	ISSUE_NUMBER="${BASH_REMATCH[2]}"
	# ISSUE_SLUG includes the number prefix (e.g., "002-cli-command-tree")
	# so spec directories and worktree paths remain aligned with the source file naming.
	# shellcheck disable=SC2034
	ISSUE_SLUG="${ISSUE_NUMBER}-${BASH_REMATCH[3]}"
	# Strip leading zeros for integer
	# shellcheck disable=SC2034
	ISSUE_NUMBER_INT=$((10#$ISSUE_NUMBER))
}

# Extract functional requirements (FR-NNN) from a PRD markdown file.
# Outputs a JSON array of {id, text} objects on stdout.
# Returns non-zero if PRD not found.
#
# Usage:
#   requirements=$(extract_prd_requirements "specs/001/prd.md")
extract_prd_requirements() {
	local prd_path="$1"

	if [[ ! -f "$prd_path" ]]; then
	log_err "PRD not found: $prd_path"
	return 1
	fi

	if ! command -v jq >/dev/null 2>&1; then
	log_err "jq required"
	return 1
	fi

	# Match patterns like:
	#   - **FR-001**: text
	#   - [FR-001] text
	#   - FR-001: text
	#   - [FR_001]: text
	# Use grep + sed to extract, then jq to build the array
	# Avoid character-class ranges in awk to keep portability
	grep -oE 'FR-[0-9]+([_-][0-9]+)?[^a-zA-Z0-9][^"\n]*' "$prd_path" 2>/dev/null \
	| sed -E 's/^(FR-[0-9]+([_-][0-9]+)?)[^a-zA-Z0-9]+(.*)$/\1\n\3/' \
	| awk 'NR%2==1 { id=$0; next } { gsub(/^[[:space:]]+|[[:space:]]+$/, ""); if (length($0) > 0) printf "{\"id\":\"%s\",\"text\":\"%s\"}\n", id, $0 }' \
	| jq -s '. // []' 2>/dev/null \
	|| echo "[]"
}

# Validate that FR tokens mentioned in the issue body are present in the PRD.
# Sets globals: TRACEABILITY_STATUS ("PASS" or "FAIL"), TRACEABILITY_DETAILS (JSON array of mismatches)
#
# Usage:
#   if validate_traceability "$issue_body" "$prd_path"; then ...
validate_traceability() {
	local issue_body="$1"
	local prd_path="$2"

	if [[ ! -f "$prd_path" ]]; then
	# shellcheck disable=SC2034  # Set for caller
	TRACEABILITY_STATUS="FAIL"
	# shellcheck disable=SC2034
	TRACEABILITY_DETAILS='[{"reason":"PRD not found","path":"'"$prd_path"'"}]'
	return 1
	fi

	if ! command -v jq >/dev/null 2>&1; then
	# shellcheck disable=SC2034
	TRACEABILITY_STATUS="FAIL"
	# shellcheck disable=SC2034
	TRACEABILITY_DETAILS='[{"reason":"jq not available"}]'
	return 1
	fi

	# Extract FR IDs from issue body
	local issue_frs
	issue_frs=$(echo "$issue_body" | grep -oE 'FR-[0-9]+[-_]?[0-9]*' | sort -u || true)

	# Extract FR IDs from PRD
	local prd_frs_raw
	prd_frs_raw=$(extract_prd_requirements "$prd_path" 2>/dev/null || echo "[]")
	local prd_frs
	prd_frs=$(echo "$prd_frs_raw" | jq -r '.[].id' | sort -u)

	# Find missing
	local missing=()
	while IFS= read -r fr; do
	[[ -z "$fr" ]] && continue
	if ! echo "$prd_frs" | grep -qx "$fr"; then
	    missing+=("$fr")
	fi
	done <<< "$issue_frs"

	if [[ ${#missing[@]} -eq 0 ]]; then
	# shellcheck disable=SC2034
	TRACEABILITY_STATUS="PASS"
	# shellcheck disable=SC2034
	TRACEABILITY_DETAILS="[]"
	return 0
	else
	# shellcheck disable=SC2034
	TRACEABILITY_STATUS="FAIL"
	local missing_json
	missing_json=$(printf '"%s",' "${missing[@]}")
	missing_json="[${missing_json%,}]"
	# shellcheck disable=SC2034
	TRACEABILITY_DETAILS="{\"missing_in_prd\":$missing_json}"
	return 1
	fi
}

# Check whether a markdown file contains all required section headers.
# Sets SPEC_SECTIONS_MISSING to a comma-separated list (empty if all present).
#
# Usage:
#   if extract_spec_sections "spec.md" "INTRODUCTION" "METHODS" "RESULTS"; then ...
extract_spec_sections() {
	local file_path="$1"
	shift
	local missing=()
	for header in "$@"; do
	if ! grep -qE "^##? ${header}" "$file_path" 2>/dev/null; then
	    missing+=("$header")
	fi
	done
	# shellcheck disable=SC2034  # Set for caller
	SPEC_SECTIONS_MISSING=$(IFS=,; echo "${missing[*]}")
	[[ ${#missing[@]} -eq 0 ]]
}

# Extract a section block from a markdown file (from header to next ## or EOF).
#
# Usage:
#   section_body=$(extract_section_body "spec.md" "INTRODUCTION")
extract_section_body() {
	local file_path="$1"
	local header="$2"
	awk -v h="$header" '
	$0 ~ "^##? " h { in_section = 1; next }
	/^##? / && in_section { in_section = 0 }
	in_section { print }
	' "$file_path"
}

# Count Gherkin Given/When/Then blocks in a content string.
# Splits content into US story blocks and verifies each block contains all
# three Gherkin clauses (**Given**, **When**, **Then**).
# Sets GHERKIN_SCENARIO_COUNT to the count of US stories with Gherkin clauses.
# Sets GHERKIN_MISSING_CLAUSES to a newline-separated list of
# "STORY: missing CLAUSE[, CLAUSE]" diagnostics (empty if all valid).
# Returns 0 if all stories have all three clauses, 1 otherwise.
#
# Supported per-story formats (both are valid per the specify output template):
#   Numbered:
#     ### US-001-Foo: Title
#     1. **Given** <state>
#     2. **When** <action>
#     3. **Then** <expected>
#   Bold-keyword (multi-scenario supported):
#     ### US-001-Foo: Title
#     **Scenario: <name>**
#     **Given** <state>
#     **When** <action>
#     **Then** <expected>
#
# Usage:
#   if validate_gherkin_syntax "$content"; then
#     echo "All $GHERKIN_SCENARIO_COUNT stories valid"
#   else
#     echo "Malformed:$GHERKIN_MISSING_CLAUSES"
#   fi
validate_gherkin_syntax() {
	local content="$1"
	# shellcheck disable=SC2034
	GHERKIN_SCENARIO_COUNT=0
	GHERKIN_MISSING_CLAUSES=""

	# Extract each US story block: from "### US-" header to next "### " or EOF.
	# Use ASCII Record Separator (0x1E) as the block delimiter so multi-line
	# blocks survive the bash `read` loop intact. Newlines split blocks
	# incorrectly because bash reads line-by-line.
	local RS
	RS=$'\x1e'
	local story_blocks
	story_blocks=$(printf '%s' "$content" \
	    | awk -v sep="$RS" '
	        /^### US-/ {
	            if (block != "") printf "%s%c", block, 30
	            block = $0
	            next
	        }
	        /^### / && block != "" { printf "%s%c", block, 30; block = ""; next }
	        block != "" { block = block ORS $0 }
	        END { if (block != "") printf "%s", block }
	    ')

	if [[ -z "$story_blocks" ]]; then
		return 1
	fi

	local has_error=false
	local missing_report=""
	local block

	# Read blocks separated by ASCII Record Separator (0x1E).
	# `read -d $'\x1e'` reads until the separator, preserving multi-line blocks.
	while IFS= read -r -d "$RS" block; do
		[[ -z "$block" ]] && continue

		# shellcheck disable=SC2034
		GHERKIN_SCENARIO_COUNT=$((GHERKIN_SCENARIO_COUNT + 1))

		# Extract the story title (first line)
		local story_title
		story_title=$(echo "$block" | head -1)

		# Check for each clause
		local missing=""
		echo "$block" | grep -qE '\*\*Given\*\*' || missing="${missing}Given"
		echo "$block" | grep -qE '\*\*When\*\*'  || missing="${missing:+$missing, }When"
		echo "$block" | grep -qE '\*\*Then\*\*'  || missing="${missing:+$missing, }Then"

		if [[ -n "$missing" ]]; then
			has_error=true
			missing_report="${missing_report}${story_title}: missing ${missing}"$'\n'
		fi
	done < <(printf '%s%c' "$story_blocks" "$RS")

	GHERKIN_MISSING_CLAUSES="$missing_report"
	! $has_error
}

# Commit an existing file (already written by the LLM) in a worktree.
#
# Usage:
#   commit_phase_artifact "/path/to/worktree" "spec.md" "docs: add spec" "Optional body"
commit_phase_artifact() {
	local worktree_dir="$1"
	local file_path="$2"
	local commit_subject="$3"
	local commit_body="${4:-}"

	if [[ ! -d "$worktree_dir" ]]; then
	log_err "worktree directory not found: $worktree_dir"
	return 1
	fi

	local full_path="$worktree_dir/$file_path"
	if [[ ! -f "$full_path" ]]; then
	log_err "artifact not found at $full_path"
	return 1
	fi

	cd "$worktree_dir"
	git add "$file_path"

	if [[ -n "$commit_body" ]]; then
	git commit --no-verify -m "$commit_subject" -m "$commit_body" >/dev/null
	else
	git commit --no-verify -m "$commit_subject" >/dev/null
	fi
}

# Commit one or more files (already on disk) in a worktree as a single commit.
# Enforces the claim-then-commit invariant: ledger state changes must be staged
# and committed together with the artifact they describe, so the transition is
# durable in git history even if a later step fails.
#
# Usage:
#   commit_phase_files "/path/to/worktree" "docs: update spec" "Body" "spec.md" "tasks.md"
commit_phase_files() {
	local worktree_dir="$1"
	local commit_subject="$2"
	local commit_body="${3:-}"
	shift 3

	if [[ ! -d "$worktree_dir" ]]; then
	log_err "worktree directory not found: $worktree_dir"
	return 1
	fi

	if [[ $# -lt 1 ]]; then
	log_err "commit_phase_files requires at least one file path"
	return 1
	fi

	local files=("$@")
	local missing=()
	for f in "${files[@]}"; do
	if [[ ! -f "$worktree_dir/$f" ]]; then
	    missing+=("$f")
	fi
	done
	if [[ ${#missing[@]} -gt 0 ]]; then
	log_err "files not found in worktree: ${missing[*]}"
	return 1
	fi

	cd "$worktree_dir"
	git add "${files[@]}"

	if [[ -n "$commit_body" ]]; then
	git commit --no-verify -m "$commit_subject" -m "$commit_body" >/dev/null
	else
	git commit --no-verify -m "$commit_subject" >/dev/null
	fi
}

# Build a JSON contract from key=value pairs provided as arguments.
# Values containing special chars are JSON-escaped.
#
# Usage:
#   build_json_contract "name=test" "version=1.0"
#   # => {"name":"test","version":"1.0"}
build_json_contract() {
	if ! command -v jq >/dev/null 2>&1; then
	log_err "jq required for JSON contract emission"
	return 1
	fi

	local first=true
	printf '{'
	for kv in "$@"; do
	local key="${kv%%=*}"
	local value="${kv#*=}"
	if [[ "$first" == "true" ]]; then
	    first=false
	else
	    printf ','
	fi
	# Use jq to safely encode both key and value
	printf '%s' "$key" | jq -R '.'
	printf ':'
	printf '%s' "$value" | jq -R '.'
	done
	printf '}'
}

resolve_skill_dir

#------------------------------------------------------------------------------
# Helpers
#------------------------------------------------------------------------------

# Derive kebab-case slug from a freeform problem statement.
# Strips non-alphanumeric characters, squeezes whitespace to single hyphens,
# lowercases, and trims leading/trailing hyphens. Caps length to 60 chars.
derive_feature_slug() {
	local input="$1"
	printf '%s' "$input" |
		tr '[:upper:]' '[:lower:]' |
		sed -E 's/[^a-z0-9]+/-/g' |
		sed -E 's/^-+|-+$//g' |
		cut -c1-60 |
		sed -E 's/-+$//g'
}

# Read all top-level numeric prefixes in specs/ and return the max N.
highest_spec_index() {
	local specs_dir="$1"
	local highest=0
	[ -d "$specs_dir" ] || {
		echo "$highest"
		return
	}
	for d in "$specs_dir"/*; do
		[ -d "$d" ] || continue
		local base
		base=$(basename "$d")
		if echo "$base" | grep -qE '^[0-9]{3}-'; then
			local num
			num=$(echo "$base" | grep -oE '^[0-9]{3}' | sed 's/^0*//')
			num=$((10#${num:-0}))
			[ "$num" -gt "$highest" ] && highest=$num
		fi
	done
	echo "$highest"
}

# Append a BACKLOG line to the global issues ledger if it exists.
# Note: the entry records the EPIC for the feature bucket, not a sub-issue.
# At this phase no issue exists yet — commits must reference the epic id.
append_issue_ledger() {
	local ledger="$1"
	local epic_id="$2"
	local feature_slug="$3"
	local title="$4"
	[ -f "$ledger" ] || return 0
	local ts
	ts=$(date -u +%Y-%m-%dT%H:%M:%SZ)
	local line
	line=$(jq -nc \
		--arg epic_id "$epic_id" \
		--arg feature_slug "$feature_slug" \
		--arg title "$title" \
		--arg ts "$ts" \
		'{epic_id:$epic_id,type:"epic",feature_slug:$feature_slug,title:$title,status:"BACKLOG",timestamp:$ts}')
	printf '%s\n' "$line" >>"$ledger"
}

#------------------------------------------------------------------------------
# pre
#------------------------------------------------------------------------------

cmd_pre() {
	if [ $# -lt 1 ]; then
		log_err "Missing problem statement"
		log_err "Usage: $SCRIPT_NAME pre \"<problem-statement>\""
		exit 1
	fi
	local problem="$1"

	local repo_root
	repo_root=$(find_repo_root "$(pwd)") || {
		echo '{"status":"FAILURE","reason":"Not a git repository"}'
		exit 2
	}
	cd "$repo_root"

	# Constitutional validation gate
	local constitution_path=""
	for candidate in \
		"$repo_root/specs/constitution.md" \
		"$repo_root/.deviate/constitution.md" \
		"$repo_root/CONSTITUTION.md"; do
		if [ -f "$candidate" ] && [ -s "$candidate" ]; then
			constitution_path="$candidate"
			break
		fi
	done
	if [ -z "$constitution_path" ]; then
		echo '{"status":"FAILURE","reason":"MALFORMED_CONSTITUTION: specs/constitution.md is missing or empty"}'
		exit 2
	fi

	# Optional: extract light-touch hints from constitution (no parsing, just exposure).
	local constitution_test_command=""
	local constitution_lint_command=""
	local type_check_command=""
	if command -v rg >/dev/null 2>&1; then
		constitution_test_command=$(rg -m1 -o '\[Test\]:\s*[^[:space:]].*' "$constitution_path" 2>/dev/null |
			sed -E 's/^\[Test\]:\s*//' || true)
		constitution_lint_command=$(rg -m1 -o '\[Lint\]:\s*[^[:space:]].*' "$constitution_path" 2>/dev/null |
			sed -E 's/^\[Lint\]:\s*//' || true)
		type_check_command=$(rg -m1 -o '\[TypeCheck\]:\s*[^[:space:]].*' "$constitution_path" 2>/dev/null |
			sed -E 's/^\[TypeCheck\]:\s*//' || true)
	fi
	# Short-name aliases for the v2.0.0 contract. Legacy long names are kept
	# for downstream spec/specify/plan templates that haven't migrated yet.
	local test_command="$constitution_test_command"
	local lint_command="$constitution_lint_command"

	# Resolve the active git branch (used for commit scoping and contract).
	local git_branch
	git_branch=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "")

	# Feature bucket allocation
	local specs_directory="specs"
	local specs_dir="$repo_root/$specs_directory"
	mkdir -p "$specs_dir"
	local highest
	highest=$(highest_spec_index "$specs_dir")
	local next_num=$((highest + 1))
	local next_index
	next_index=$(printf "%03d" "$next_num")

	# Derive slug from problem statement; guarantee non-empty
	local slug
	slug=$(derive_feature_slug "$problem")
	[ -z "$slug" ] && slug="feature"

	local feature_dir="${specs_directory}/${next_index}-${slug}"
	local feature_abs="$repo_root/$feature_dir"
	mkdir -p "$feature_abs"
	log_ok "Allocated feature bucket: $feature_dir"

	local spec_target_abs="$feature_abs/explore.md"
	local spec_target_rel="$feature_dir/explore.md"

	# Issue ledger scratch entry (optional — create the file if missing).
	# The epic id IS the feature bucket number (e.g., "001"); no ISS- prefix.
	# Commit messages and ledger entries reference the epic, not a phantom issue.
	local issues_ledger="$specs_dir/issues.jsonl"
	local epic_id="$next_index"
	append_issue_ledger "$issues_ledger" "$epic_id" "${next_index}-${slug}" "$problem" || true

	# Stash the contract for the post-script (env-var + temp file fallback)
	local contract_json
	contract_json=$(jq -n \
		--arg status "READY" \
		--arg phase "explore" \
		--arg repo_root "$repo_root" \
		--arg git_branch "$git_branch" \
		--arg feature_slug "${next_index}-${slug}" \
		--arg feature_dir "$feature_dir" \
		--arg specs_directory "$specs_directory" \
		--arg spec_target "$spec_target_rel" \
		--arg spec_target_abs "$spec_target_abs" \
		--arg constitution_path "$constitution_path" \
		--arg test_cmd "$test_command" \
		--arg lint_cmd "$lint_command" \
		--arg type_check_cmd "$type_check_command" \
		--arg constitution_test_cmd "$constitution_test_command" \
		--arg constitution_lint_cmd "$constitution_lint_command" \
		--arg epic_id "$epic_id" \
		--arg issues_ledger "$issues_ledger" \
		--arg skill_dir "$SKILL_DIR" \
		--arg timestamp "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
		'{
            status: $status,
            phase: $phase,
            repo_root: $repo_root,
            git_branch: $git_branch,
            feature_slug: $feature_slug,
            feature_dir: $feature_dir,
            specs_directory: $specs_directory,
            spec_target: $spec_target,
            spec_target_abs: $spec_target_abs,
            constitution_path: $constitution_path,
            test_command: $test_cmd,
            lint_command: $lint_cmd,
            type_check_command: $type_check_cmd,
            constitution_test_command: $constitution_test_cmd,
            constitution_lint_command: $constitution_lint_cmd,
            epic_id: $epic_id,
            issues_ledger: $issues_ledger,
            skill_dir: $skill_dir,
            timestamp: $timestamp
        }')

	# Persist for the post-script (mirrors the contract for handoff)
	local contract_path="${DEVIATE_EXPLORE_CONTRACT_PATH:-}"
	if [ -z "$contract_path" ]; then
		contract_path=$(mktemp "$(create_temp_dir "deviate-explore-phase")/contract-XXXXXX.json")
	fi
	printf '%s\n' "$contract_json" >"$contract_path"

	# Emit on stdout (what the orchestrator parses)
	printf '%s\n' "$contract_json"

	# Side-channel env var for convenience
	log_info "Contract written to: $contract_path"
	log_info "Run 'DEVIATE_EXPLORE_CONTRACT_PATH=$contract_path $SCRIPT_NAME post' after writing the artifact."
}

#------------------------------------------------------------------------------
# post
#------------------------------------------------------------------------------

cmd_post() {
	local contract_path="${DEVIATE_EXPLORE_CONTRACT_PATH:-}"

	# Fall back to a fresh search of the canonical temp dir
	if [ -z "$contract_path" ] || [ ! -f "$contract_path" ]; then
		local temp_base="${TMPDIR:-${XDG_STATE_HOME:-${HOME}/.local/state}}"
		contract_path=$(ls -t "$temp_base"/deviate-explore-phase.*/contract-*.json \
			"$HOME/.tmp"/deviate-explore-phase.*/contract-*.json \
			/tmp/deviate-explore-phase.*/contract-*.json 2>/dev/null | head -1 || true)
	fi

	if [ -z "$contract_path" ] || [ ! -f "$contract_path" ]; then
		log_err "Explore contract not found."
		log_err "Run: $SCRIPT_NAME pre \"<problem-statement>\" first."
		exit 5
	fi

	local contract
	contract=$(cat "$contract_path")
	local spec_target_abs
	spec_target_abs=$(printf '%s' "$contract" | jq -r '.spec_target_abs // empty')
	local feature_dir
	feature_dir=$(printf '%s' "$contract" | jq -r '.feature_dir // empty')
	local epic_id
	epic_id=$(printf '%s' "$contract" | jq -r '.epic_id // empty')
	[ -z "$epic_id" ] && epic_id="explore"
	local repo_root
	repo_root=$(printf '%s' "$contract" | jq -r '.repo_root // empty')

	if [ -z "$spec_target_abs" ] || [ ! -f "$spec_target_abs" ]; then
		log_err "Explore artifact not found at $spec_target_abs"
		exit 5
	fi

	cd "$repo_root"

	# Content validation — required section headers (v2.0.0 schema)
	local missing=()
	local required=(
		"## \[PROBLEM_DEFINITION\]"
		"## \[DISCOVERY_AUDIT_RESULTS\]"
		"## \[CONSTITUTION_QUOTES\]"
		"## \[FILE_REGISTRY\]"
		"## \[STATUS_SUMMARY\]"
	)
	local header
	for header in "${required[@]}"; do
		if ! grep -Eq "^${header}$" "$spec_target_abs"; then
			missing+=("$header")
		fi
	done

	if [ "${#missing[@]}" -gt 0 ]; then
		log_err "Content validation failed — missing required headers:"
		for h in "${missing[@]}"; do
			log_err "  - $h"
		done
		exit 5
	fi

	log_ok "Content validation passed"

	# Atomic commit — reference the EPIC (the feature bucket number),
	# not a phantom issue. At this phase no issue exists yet.
	local rel_path="${spec_target_abs#${repo_root}/}"
	local commit_msg="docs(${epic_id}): scaffold explore.md"
	git add "$rel_path" >/dev/null 2>&1 || {
		log_err "Failed to stage $rel_path"
		exit 6
	}
	if git commit --no-verify -m "$commit_msg" >/dev/null 2>&1; then
		log_ok "Committed: $commit_msg"
	else
		log_err "Commit failed for $rel_path"
		exit 6
	fi

	jq -n \
		--arg status "SUCCESS" \
		--arg spec_target "$rel_path" \
		--arg feature_dir "$feature_dir" \
		--arg epic_id "$epic_id" \
		--arg next_action "Run the research skill" \
		'{
            status: $status,
            spec_target: $spec_target,
            feature_dir: $feature_dir,
            epic_id: $epic_id,
            next_action: $next_action
        }'
}

#------------------------------------------------------------------------------
# Dispatch
#------------------------------------------------------------------------------

if [ $# -lt 1 ]; then
	cat <<EOF >&2
Usage: $SCRIPT_NAME <pre|post> [args]

Subcommands:
  pre "<problem-statement>"   Allocate the feature bucket and emit a JSON contract.
  post                       Validate the LLM-written explore.md, commit it, update the ledger.

Environment:
  DEVIATE_EXPLORE_CONTRACT_PATH       Override the temp file used to hand the contract from pre to post.
EOF
	exit 1
fi

SUBCOMMAND="$1"
shift

case "$SUBCOMMAND" in
pre) cmd_pre "$@" ;;
post) cmd_post "$@" ;;
-h | --help | help)
	cat <<EOF
$SCRIPT_NAME - Orchestrator for the /deviate-explore macro layer (PHASE_EXPLORE)

  $SCRIPT_NAME pre "<problem-statement>"
  $SCRIPT_NAME post
EOF
	exit 0
	;;
*)
	log_err "Unknown subcommand: $SUBCOMMAND"
	exit 1
	;;
esac
