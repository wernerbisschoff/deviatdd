#!/usr/bin/env bash
#
# deviate-shard.sh - Orchestrator for the /deviate-shard skill
#
# This script wraps operational concerns of vertical shard generation:
#   - Repository discovery (walk-up to .git)
#   - Epic slug discovery (most recently modified NNN-* under specs/)
#   - PRD path resolution and validation
#   - Shard file validation (file existence, section completeness)
#   - Issue ledger registration (inline, no external script)
#   - Atomic git commit
#
# Usage:
#   deviate-shard.sh pre
#   deviate-shard.sh post <MANIFEST_PATH> [--dry-run]
#
# The 'pre' subcommand discovers the epic slug, resolves the PRD path,
# and emits a JSON contract. The 'post' subcommand reads the LLM-written
# execution manifest, validates shard files, registers issues in the
# ledger, stages files, and commits.
#
# Exit codes:
#   0   Success
#   1   Invalid arguments
#   2   Pre-flight check failed (not a repo, no epic found)
#   5   Manifest validation failed
#   6   Commit execution failed
#
set -euo pipefail

# ── Shared library (colors, logging, helpers) ────────────────────────────
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


SCRIPT_NAME="$(basename "$0")"

# ── Default flags ────────────────────────────────────────────────────────
DRY_RUN=false
MANIFEST_PATH=""

# ── Help / usage ─────────────────────────────────────────────────────────
show_help() {
	cat <<EOF
$SCRIPT_NAME - Orchestrator for the /deviate-shard skill

SYNOPSIS
	$SCRIPT_NAME <pre|post> [OPTIONS]

DESCRIPTION
	Wraps operational concerns of vertical shard generation from a PRD.
	The 'pre' subcommand discovers the epic slug, resolves the PRD path,
	and emits a JSON contract. The 'post' subcommand reads the LLM-written
	execution manifest, validates shard files, registers issues in the
	ledger, stages files, and commits.

SUBCOMMANDS
	pre     Discover epic slug, resolve PRD path, emit JSON contract
	post    Validate shards, register issues, stage, commit

OPTIONS (pre only)
	--dry-run         Preview-only: emit plan and stop (no mutations)

OPTIONS (post only)
	<MANIFEST_PATH>   Path to the LLM-written execution manifest JSON
	--dry-run         Preview-only: emit preview and stop (no mutations)

EXIT CODES
	0   Success
	1   Invalid arguments
	2   Pre-flight check failed
	5   Manifest validation failed
	6   Commit execution failed

EXAMPLES
	$SCRIPT_NAME pre
	$SCRIPT_NAME pre --dry-run
	$SCRIPT_NAME post /tmp/deviate-shard.XXX/execution-manifest.json
EOF
}

# ── Argument parsing ─────────────────────────────────────────────────────
parse_args() {
	if [[ $# -lt 1 ]]; then
		log_err "Missing subcommand (expected: pre, post)"
		show_help >&2
		exit 1
	fi

	SUBCOMMAND="$1"
	shift

	if [[ "$SUBCOMMAND" == "-h" || "$SUBCOMMAND" == "--help" || "$SUBCOMMAND" == "help" ]]; then
		show_help
		exit 0
	fi

	if [[ "$SUBCOMMAND" != "pre" && "$SUBCOMMAND" != "post" ]]; then
		log_err "Unknown subcommand: $SUBCOMMAND (expected: pre, post)"
		exit 1
	fi

	while [[ $# -gt 0 ]]; do
		case "$1" in
		--dry-run)
			DRY_RUN=true
			shift
			;;
		-h | --help | help)
			show_help
			exit 0
			;;
		-*)
			log_err "Unknown option: $1"
			exit 1
			;;
		*)
			if [[ "$SUBCOMMAND" == "post" ]]; then
				if [[ -z "$MANIFEST_PATH" ]]; then
					MANIFEST_PATH="$1"
				else
					log_err "Unexpected positional argument: $1"
					exit 1
				fi
			else
				log_err "Unexpected positional argument: $1"
				exit 1
			fi
			shift
			;;
		esac
	done

	if [[ "$SUBCOMMAND" == "post" ]] && [[ -z "$MANIFEST_PATH" ]]; then
		log_err "Missing required argument: <MANIFEST_PATH>"
		show_help >&2
		exit 1
	fi
}

# ── Pre-flight: repository ───────────────────────────────────────────────
validate_repo() {
	if ! REPO_ROOT=$(find_repo_root "$(pwd)"); then
		log_err "Not inside a git repository"
		echo '{"status":"FAILURE","reason":"NOT_A_GIT_REPOSITORY"}'
		exit 2
	fi
	export REPO_ROOT
}

# ── Issue ledger registration (inline, no external script) ──────────────
# Appends a new issue entry to specs/issues.jsonl (append-only JSON Lines).
# Assigns a deterministic ISS-NNN identifier based on existing entries.
# Supports additional fields: source_file, blocked_by, coordinates_with.
#
# Usage:
#   register_issue_in_ledger "Issue title" [--source-file <path>] [--blocked-by <json>] [--coordinates-with <json>]
register_issue_in_ledger() {
	local title=""
	local source_file=""
	local blocked_by="[]"
	local coordinates_with="[]"
	local issue_type="feature"

	while [[ $# -gt 0 ]]; do
		case "$1" in
		--source-file)
			source_file="$2"
			shift 2
			;;
		--blocked-by)
			blocked_by="$2"
			shift 2
			;;
		--coordinates-with)
			coordinates_with="$2"
			shift 2
			;;
		--type)
			issue_type="$2"
			shift 2
			;;
		*)
			if [[ -z "$title" ]]; then
				title="$1"
			fi
			shift
			;;
		esac
	done

	if [[ -z "$title" ]]; then
		log_err "register_issue_in_ledger requires a title"
		return 1
	fi

	local issues_file="$REPO_ROOT/specs/issues.jsonl"
	mkdir -p "$(dirname "$issues_file")"

	# Find highest existing issue number
	local highest_num=0
	if [[ -f "$issues_file" ]]; then
		while IFS= read -r line; do
			local id
			id=$(echo "$line" | grep -oE '"issue_id": "ISS-[0-9]+"' | grep -oE '[0-9]+' || true)
			if [[ -n "$id" ]]; then
				local num
				num=$((10#$id))
				[[ $num -gt $highest_num ]] && highest_num=$num
			fi
		done <"$issues_file"
	fi

	local next_num=$((highest_num + 1))
	local issue_id
	issue_id=$(printf "ISS-%03d" "$next_num")
	local timestamp
	timestamp=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

	# Build JSON entry
	local entry
	entry=$(jq -n \
		--arg issue_id "$issue_id" \
		--arg type "$issue_type" \
		--arg title "$title" \
		--arg status "BACKLOG" \
		--arg timestamp "$timestamp" \
		--arg source_file "$source_file" \
		--argjson blocked_by "$blocked_by" \
		--argjson coordinates_with "$coordinates_with" \
		'{
	    issue_id: $issue_id,
	    type: $type,
	    title: $title,
	    status: $status,
	    timestamp: $timestamp,
	    source_file: $source_file,
	    blocked_by: $blocked_by,
	    coordinates_with: $coordinates_with
	}')

	echo "$entry" >>"$issues_file"
	log_ok "Registered issue $issue_id: $title"
}

# ── Epic slug discovery ──────────────────────────────────────────────────
# Find the most recently modified NNN-* directory under specs/.
# Falls back to the first NNN-* directory if dates are identical.
discover_epic_slug() {
	local specs_dir="$REPO_ROOT/specs"

	if [[ ! -d "$specs_dir" ]]; then
		log_err "No specs/ directory found"
		return 1
	fi

	local latest
	# shellcheck disable=SC2012  # ls with glob pattern is safe for NNN-* format
	latest=$(ls -1dt "$specs_dir"/[0-9][0-9][0-9]-* 2>/dev/null | head -1 || true)

	if [[ -z "$latest" ]]; then
		# Fall back to any NNN-* directory
		# shellcheck disable=SC2012  # ls with glob pattern is safe for NNN-* format
		latest=$(ls -1d "$specs_dir"/[0-9][0-9][0-9]-* 2>/dev/null | head -1 || true)
	fi

	if [[ -z "$latest" ]]; then
		log_err "No feature epic directories (NNN-*) found in specs/"
		return 1
	fi

	EPIC_DIR="$latest"
	EPIC_SLUG=$(basename "$latest")
	export EPIC_DIR EPIC_SLUG
	return 0
}

# ── PRD path resolution ──────────────────────────────────────────────────
resolve_prd_path() {
	FEATURE_DIR="${EPIC_DIR#"${REPO_ROOT}"/}"
	PRD_PATH="$EPIC_DIR/prd.md"
	ISSUES_DIR="$FEATURE_DIR/issues"
	ISSUES_ABS_DIR="$EPIC_DIR/issues"
	CONSTITUTION_PATH="$REPO_ROOT/specs/constitution.md"
	ISSUES_LEDGER="$REPO_ROOT/specs/issues.jsonl"

	if [[ ! -f "$PRD_PATH" ]]; then
		log_err "PRD not found at $PRD_PATH"
		return 1
	fi
	log_ok "PRD found: $PRD_PATH"

	# Create issues directory if it doesn't exist
	mkdir -p "$ISSUES_ABS_DIR"

	export FEATURE_DIR PRD_PATH ISSUES_DIR ISSUES_ABS_DIR CONSTITUTION_PATH ISSUES_LEDGER
	return 0
}

# ── Pre subcommand ───────────────────────────────────────────────────────
cmd_pre() {
	log_info "Deviate-shard pre-phase starting..."
	log_info "  dry_run: $DRY_RUN"

	validate_repo
	log_ok "Repository validated: $REPO_ROOT"

	if ! discover_epic_slug; then
		log_err "Could not resolve epic slug"
		emit_json_contract \
			"status" "NO_EPIC" \
			"phase" "shard" \
			"skill_dir" "$SKILL_DIR" \
			"timestamp" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
			"reason" "No NNN-* feature directory found in specs/"
		exit 2
	fi
	log_ok "Epic slug: $EPIC_SLUG"

	if ! resolve_prd_path; then
		log_err "Could not resolve PRD path"
		emit_json_contract \
			"status" "NO_PRD" \
			"phase" "shard" \
			"epic_slug" "$EPIC_SLUG" \
			"skill_dir" "$SKILL_DIR" \
			"timestamp" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
			"reason" "No prd.md found in $FEATURE_DIR"
		exit 2
	fi
	log_ok "Feature dir: $FEATURE_DIR"
	log_ok "PRD path: $PRD_PATH"
	log_ok "Issues dir: $ISSUES_DIR"

	local git_branch
	git_branch=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "unknown")

	local git_state
	git_state=$(gather_git_state 2>/dev/null || echo '{}')

	# Derive epic_id from slug (first 3 digits)
	local epic_id
	epic_id=$(echo "$EPIC_SLUG" | grep -oE '^[0-9]{3}' || echo "$EPIC_SLUG")

	# Create temp dir for plan_target (manifest handoff to post)
	local temp_dir
	temp_dir=$(create_temp_dir "deviate-shard") || {
		log_err "Cannot create temp directory"
		echo '{"status":"FAILURE","reason":"TEMP_DIR_CREATION_FAILED"}'
		exit 2
	}
	local plan_target="$temp_dir/execution-manifest.json"

	# Build JSON contract
	local contract_json
	contract_json=$(jq -n \
		--arg status "READY" \
		--arg phase "shard" \
		--arg repo_root "$REPO_ROOT" \
		--arg git_branch "$git_branch" \
		--arg epic_slug "$EPIC_SLUG" \
		--arg epic_id "$epic_id" \
		--arg feature_dir "$FEATURE_DIR" \
		--arg prd_path "$PRD_PATH" \
		--arg constitution_path "$CONSTITUTION_PATH" \
		--arg issues_dir "$ISSUES_DIR" \
		--arg issues_abs_dir "$ISSUES_ABS_DIR" \
		--arg issues_ledger "$ISSUES_LEDGER" \
		--arg plan_target "$plan_target" \
		--arg skill_dir "$SKILL_DIR" \
		--argjson dry_run "$DRY_RUN" \
		--arg git_state "$git_state" \
		--arg timestamp "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
		'{
	    status: $status,
	    phase: $phase,
	    repo_root: $repo_root,
	    git_branch: $git_branch,
	    epic_slug: $epic_slug,
	    epic_id: $epic_id,
	    feature_dir: $feature_dir,
	    prd_path: $prd_path,
	    constitution_path: $constitution_path,
	    issues_dir: $issues_dir,
	    issues_abs_dir: $issues_abs_dir,
	    issues_ledger: $issues_ledger,
	    plan_target: $plan_target,
	    skill_dir: $skill_dir,
	    dry_run: $dry_run,
	    git_state: $git_state,
	    timestamp: $timestamp
	}')

	printf '%s\n' "$contract_json"

	log_ok "Pre-phase complete. Plan target: $plan_target"
}

# ── Post subcommand ──────────────────────────────────────────────────────
cmd_post() {
	log_info "Deviate-shard post-phase starting..."
	log_info "  manifest_path: $MANIFEST_PATH"
	log_info "  dry_run: $DRY_RUN"

	validate_repo

	# Read the LLM-written execution manifest
	if [[ ! -f "$MANIFEST_PATH" ]]; then
		log_err "Execution manifest not found at: $MANIFEST_PATH"
		echo '{"status":"FAILURE","reason":"MANIFEST_NOT_FOUND","path":"'"$MANIFEST_PATH"'"}'
		exit 5
	fi

	log_info "Reading execution manifest from: $MANIFEST_PATH"
	local manifest
	manifest=$(cat "$MANIFEST_PATH")

	# Validate manifest has required fields
	local task_id commit_subject
	task_id=$(printf '%s' "$manifest" | jq -r '.task_id // empty')
	commit_subject=$(printf '%s' "$manifest" | jq -r '.commit_subject // empty')

	local missing=()
	[[ -n "$task_id" ]] || missing+=("task_id")
	[[ -n "$commit_subject" ]] || missing+=("commit_subject")
	if [[ ${#missing[@]} -gt 0 ]]; then
		local missing_json
		missing_json=$(printf '"%s",' "${missing[@]}" | sed 's/,$//')
		log_err "Execution manifest missing required fields: ${missing[*]}"
		echo "{\"status\":\"FAILURE\",\"reason\":\"INVALID_MANIFEST\",\"missing\":[${missing_json}]}"
		exit 5
	fi

	# Re-discover epic slug and resolve paths from the repo
	if ! discover_epic_slug; then
		log_err "Could not resolve epic slug from repo state"
		echo '{"status":"FAILURE","reason":"NO_EPIC_FOUND"}'
		exit 5
	fi
	resolve_prd_path || true # Non-fatal — we only need the paths for staging

	# Dry-run: emit preview and stop
	if [[ "$DRY_RUN" == "true" ]]; then
		log_info "Dry run — no mutations will be made"
		printf '%s' "$manifest" | jq -n --argjson m "$manifest" \
			--arg issues_dir "$ISSUES_DIR" \
			'{status:"DRY_RUN",issues_dir:$issues_dir,manifest:$m}'
		exit 0
	fi

	cd "$REPO_ROOT"

	# Step 1: Validate that shard files were created
	local shard_files
	shard_files=$(ls "$ISSUES_ABS_DIR"/[0-9][0-9][0-9]-*.md 2>/dev/null || true)

	if [[ -z "$shard_files" ]]; then
		log_err "No shard files found in $ISSUES_ABS_DIR"
		echo '{"status":"FAILURE","reason":"SHARD_FILES_NOT_FOUND","path":"'"$ISSUES_ABS_DIR"'"}'
		exit 5
	fi

	local shard_count
	shard_count=$(echo "$shard_files" | wc -l | tr -d ' ')
	log_ok "Found $shard_count shard file(s) in $ISSUES_DIR"

	# Step 2: Validate each shard has required frontmatter
	local failed=false
	local shard_file
	for shard_file in $shard_files; do
		local basename
		basename=$(basename "$shard_file")
		if ! grep -q "^---" "$shard_file" 2>/dev/null; then
			log_warn "Shard $basename missing YAML frontmatter"
		fi
		if ! grep -q "^title:" "$shard_file" 2>/dev/null; then
			log_warn "Shard $basename missing title in frontmatter"
			failed=true
		fi
		if ! grep -q "blocked_by:" "$shard_file" 2>/dev/null; then
			log_warn "Shard $basename missing blocked_by in frontmatter"
		fi
	done

	if [[ "$failed" == "true" ]]; then
		log_err "Some shard files are missing required frontmatter fields"
		echo '{"status":"FAILURE","reason":"SHARD_VALIDATION_FAILED"}'
		exit 5
	fi

	# Step 3: Register shards in the issues ledger (inline, no external script)
	log_info "Registering shard issues in the ledger..."
	local shard_file
	for shard_file in $shard_files; do
		local basename
		basename=$(basename "$shard_file")
		local title
		title=$(grep "^title:" "$shard_file" | sed 's/^title: "\(.*\)"$/\1/' | sed 's/^title: //')

		# Extract frontmatter fields for the ledger entry
		local source_path="$ISSUES_DIR/$basename"

		# Parse blocked_by array from YAML frontmatter
		local blocked_by_json="[]"
		local blocked_by_line
		blocked_by_line=$(grep "^blocked_by:" "$shard_file" | head -1 | sed 's/^blocked_by: *//' || true)
		if [[ -n "$blocked_by_line" ]] && [[ "$blocked_by_line" != "[]" ]]; then
			blocked_by_json="$blocked_by_line"
		fi

		# Parse coordinates_with array from YAML frontmatter
		local coordinates_with_json="[]"
		local coordinates_line
		coordinates_line=$(grep "^coordinates_with:" "$shard_file" | head -1 | sed 's/^coordinates_with: *//' || true)
		if [[ -n "$coordinates_line" ]] && [[ "$coordinates_line" != "[]" ]]; then
			coordinates_with_json="$coordinates_line"
		fi

		if [[ -n "$title" ]]; then
			log_info "Registering: $basename — $title"
			register_issue_in_ledger \
				"$title" \
				--type feature \
				--source-file "$source_path" \
				--blocked-by "$blocked_by_json" \
				--coordinates-with "$coordinates_with_json" ||
				log_warn "Failed to register $basename (non-fatal)"
		fi
	done

	# Step 4: Stage files
	log_info "Staging shard files and ledger..."
	git add "$ISSUES_DIR/" 2>/dev/null || true
	git add "$REPO_ROOT/specs/issues.jsonl" 2>/dev/null || true

	# Step 5: Run pre-commit hooks if present
	if [[ -f "$REPO_ROOT/.pre-commit-config.yaml" ]] && command -v pre-commit >/dev/null 2>&1; then
		log_info "Running pre-commit hooks..."
		git diff --staged --name-only | xargs pre-commit run --files 2>/dev/null || true
		git add "$ISSUES_DIR/" 2>/dev/null || true
	fi

	# Step 6: Commit
	log_info "Committing with conventional message..."
	if git commit --no-verify -m "$commit_subject" 2>/dev/null; then
		local commit_sha
		commit_sha=$(git rev-parse --short HEAD)
		log_ok "Committed: $commit_sha"
		emit_json_contract \
			"status" "SUCCESS" \
			"phase" "shard" \
			"task_id" "$task_id" \
			"commit_sha" "$commit_sha" \
			"shard_count" "$shard_count" \
			"issues_dir" "$ISSUES_DIR" \
			"next_action" "Shard generation complete — issues are ready for claiming" \
			"timestamp" "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
	else
		log_err "Commit failed"
		echo '{"status":"FAILURE","reason":"COMMIT_FAILED"}'
		exit 6
	fi
}

# ── Dispatch ─────────────────────────────────────────────────────────────
parse_args "$@"
case "$SUBCOMMAND" in
pre) cmd_pre ;;
post) cmd_post ;;
esac
