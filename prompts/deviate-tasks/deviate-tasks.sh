#!/usr/bin/env bash
#
# deviate-tasks.sh - Orchestrator for the /deviate-tasks skill
#
# This script wraps operational concerns of the task decomposition phase:
#   - Repository discovery (walk-up to .git)
#   - Worktree detection and branch validation
#   - spec.md path resolution and required-section validation
#   - Optional research artifact discovery (design.md, data-model.md)
#   - tasks.md content validation (section headers, T{NNN} format, checkboxes)
#   - Atomic git commit and ledger update
#
# Usage:
#   deviate-tasks.sh pre
#   deviate-tasks.sh post
#   deviate-tasks.sh post --force
#
# The 'pre' subcommand detects the worktree, locates spec.md, validates
# its required sections, and emits a JSON contract. The 'post' subcommand
# validates the written tasks.md, commits, and updates the ledger.
#
# Exit codes:
#   0   Success
#   1   Invalid arguments
#   2   Pre-flight check failed (not a repo, no spec found)
#   3   Worktree detection or branch validation failed
#   5   tasks.md validation failed
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
SKILL_DIR="$(CDPATH="" cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# ── No external scripts required (fully self-contained) ──────────────────
# This script uses common.sh.tmpl functions directly.

# ── Default flags ────────────────────────────────────────────────────────
FORCE_MODE=false
DRY_RUN=false

# ── Help / usage ─────────────────────────────────────────────────────────
show_help() {
	cat <<EOF
$SCRIPT_NAME - Orchestrator for the /deviate-tasks skill

SYNOPSIS
	$SCRIPT_NAME <pre|post> [OPTIONS]

DESCRIPTION
	Wraps operational concerns of the task decomposition phase. The 'pre'
	subcommand detects the worktree, locates spec.md, validates its
	required sections, and emits a JSON contract. The 'post' subcommand
	validates the written tasks.md, commits, and updates the ledger.

SUBCOMMANDS
	pre     Detect worktree, validate spec.md, emit JSON contract
	post    Validate tasks.md, commit, update ledger

OPTIONS (post only)
	--force   Bypass validation errors and commit anyway

EXIT CODES
	0   Success
	1   Invalid arguments
	2   Pre-flight check failed
	3   Worktree detection or branch validation failed
	5   tasks.md validation failed
	6   Commit execution failed

EXAMPLES
	$SCRIPT_NAME pre
	$SCRIPT_NAME post
	$SCRIPT_NAME post --force
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
		--force)
			FORCE_MODE=true
			shift
			;;
		--dry-run)
			# shellcheck disable=SC2034  # Exported for LLM contract
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
			log_err "Unexpected positional argument: $1"
			exit 1
			;;
		esac
	done
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

# ── Check required tools ─────────────────────────────────────────────────
validate_required_tools() {
	local missing=()

	if ! command -v jq >/dev/null 2>&1; then
		missing+=("jq")
	fi

	if [[ ${#missing[@]} -gt 0 ]]; then
		log_err "Required tools missing: ${missing[*]}"
		echo '{"status":"FAILURE","reason":"MISSING_REQUIRED_TOOLS"}'
		exit 2
	fi
}

# ── Worktree detection ───────────────────────────────────────────────────
# REPO_ROOT from find_repo_root already resolves to the correct worktree
# root (it detects [ -f "$dir/.git" ] which exists in worktrees).
# Do NOT parse git worktree list — head -1 always picks the main repo.
detect_worktree() {
	WORKTREE_PATH="$REPO_ROOT"
	export WORKTREE_PATH
	log_info "Worktree path: $WORKTREE_PATH"
	return 0
}

# ── Branch validation ────────────────────────────────────────────────────
validate_branch() {
	local branch
	branch=$(cd "$WORKTREE_PATH" && git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "unknown")

	if [[ -z "$branch" || "$branch" == "HEAD" || "$branch" == "unknown" ]]; then
		log_warn "Detached HEAD or unknown branch"
		BRANCH_NAME="$branch"
		export BRANCH_NAME
		return 1
	fi

	BRANCH_NAME="$branch"
	export BRANCH_NAME

	if validate_worktree_branch "$BRANCH_NAME"; then
		log_ok "Branch: $BRANCH_NAME"
		return 0
	else
		log_warn "Branch $BRANCH_NAME is a base branch — tasks should run on feature branches"
		return 1
	fi
}

# ── spec.md discovery ────────────────────────────────────────────────────
discover_spec_md() {
	# Look for spec.md in the usual location
	local found_specs
	found_specs=$(find "$WORKTREE_PATH/specs" -maxdepth 3 -name "spec.md" 2>/dev/null || true)

	if [[ -z "$found_specs" ]]; then
		log_err "No spec.md found in specs/ directories"
		return 1
	fi

	# Pick the most recently modified spec.md
	local latest_spec
	latest_spec=$(echo "$found_specs" | while read -r f; do
		echo "$(date -r "$f" +%s) $f"
	done | sort -rn | head -1 | awk '{print $2}' || true)

	if [[ -z "$latest_spec" ]]; then
		# Fallback to first found
		latest_spec=$(echo "$found_specs" | head -1)
	fi

	SPEC_PATH="$latest_spec"
	SPEC_PATH_RELATIVE="${SPEC_PATH#"$WORKTREE_PATH"/}"
	export SPEC_PATH SPEC_PATH_RELATIVE

	log_ok "spec.md found: $SPEC_PATH"
	return 0
}

# ── Validate spec.md required sections ───────────────────────────────────
validate_spec_sections() {
	extract_spec_sections "$SPEC_PATH" \
		"FEATURE_SPECIFICATION:" \
		"SYSTEM_TOPOLOGY_MAPPING" \
		"THE_PROBLEM_CONTRACT" \
		"SCOPE_BOUNDARIES" \
		"ATDD_ACCEPTANCE_CRITERIA_LEDGER" \
		"SYSTEM_STATUS_SUMMARY"

	# shellcheck disable=SC2178,SC2128  # SPEC_SECTIONS_MISSING is a comma-separated string
	local missing="$SPEC_SECTIONS_MISSING"
	if [[ -n "$missing" ]]; then
		log_err "spec.md is missing required sections: $missing"
		return 1
	fi

	log_ok "spec.md all required sections present"
	return 0
}

# ── Research artifact discovery (design.md, data-model.md) ───────────────
discover_research_artifacts() {
	DESIGN_PATH=""
	DATA_MODEL_PATH=""

	# design.md may be alongside spec.md or in the parent issue directory
	local spec_dir
	spec_dir=$(dirname "$SPEC_PATH")
	local issue_dir
	issue_dir=$(dirname "$spec_dir")

	local potential_design="$issue_dir/design.md"
	if [[ -f "$potential_design" ]]; then
		DESIGN_PATH="$potential_design"
		log_ok "Research artifact found: design.md"
	fi

	local potential_data_model="$issue_dir/data-model.md"
	if [[ -f "$potential_data_model" ]]; then
		DATA_MODEL_PATH="$potential_data_model"
		log_ok "Research artifact found: data-model.md"
	fi

	export DESIGN_PATH DATA_MODEL_PATH
}

# ── Tasks target path ────────────────────────────────────────────────────
resolve_tasks_target() {
	# tasks.md goes alongside spec.md
	local spec_dir
	spec_dir=$(dirname "$SPEC_PATH")
	TASKS_TARGET="$spec_dir/tasks.md"
	TASKS_TARGET_RELATIVE="${TASKS_TARGET#"$WORKTREE_PATH"/}"
	export TASKS_TARGET TASKS_TARGET_RELATIVE
	log_ok "Tasks target: $TASKS_TARGET"
}

# ── Extract epic/issue slugs from spec path ──────────────────────────────
extract_slugs_from_path() {
	# Path example: specs/001-epic/001-issue-slug/spec.md
	if [[ "$SPEC_PATH_RELATIVE" =~ ^specs/([^/]+)/([0-9]+)-(.+)/spec\.md$ ]]; then
		EPIC_SLUG="${BASH_REMATCH[1]}"
		ISSUE_NUMBER="${BASH_REMATCH[2]}"
		ISSUE_SLUG="${ISSUE_NUMBER}-${BASH_REMATCH[3]}"
		# Path: specs/{epic}/{issue_slug}/spec.md
		ISSUE_ID="${ISSUE_NUMBER}"
		# Try to get actual issue_id from file naming or content
		local potential_id
		potential_id=$(grep -oE '\bISS-[0-9]+\b' "$SPEC_PATH" | head -1 || true)
		if [[ -n "$potential_id" ]]; then
			ISSUE_ID="$potential_id"
		fi
		export EPIC_SLUG ISSUE_SLUG ISSUE_ID
		return 0
	fi

	# Fallback: try to extract from spec content
	EPIC_SLUG=$(grep -E "^\|.*EPIC_SLUG.*\|" "$SPEC_PATH" | head -1 | awk -F'|' '{print $3}' | tr -d ' ' || echo "unknown")
	ISSUE_ID=$(grep -E "^\|.*ISSUE_ID.*\|" "$SPEC_PATH" | head -1 | awk -F'|' '{print $3}' | tr -d ' ' || echo "unknown")
	ISSUE_SLUG=$(grep -E "^\|.*BRANCH_NAME.*\|" "$SPEC_PATH" | head -1 | awk -F'|' '{print $3}' | tr -d ' ' | sed 's|.*/||' || echo "unknown")
	export EPIC_SLUG ISSUE_ID ISSUE_SLUG
	return 0
}

# ── Pre subcommand ───────────────────────────────────────────────────────
cmd_pre() {
	log_info "Deviate-tasks pre-phase starting..."

	validate_required_tools
	validate_repo
	log_ok "Repository validated: $REPO_ROOT"

	detect_worktree
	log_ok "Worktree path: $WORKTREE_PATH"

	validate_branch || {
		log_warn "Branch validation issued warning — continuing"
	}

	discover_spec_md || {
		log_err "No spec.md found in worktree"
		emit_json_contract \
			"status" "SPEC_NOT_FOUND" \
			"phase" "tasks" \
			"reason" "No spec.md found in worktree issues directories" \
			"worktree_full" "$WORKTREE_PATH" \
			"repo_root" "$REPO_ROOT" \
			"skill_dir" "$SKILL_DIR" \
			"timestamp" "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
		exit 3
	}

	validate_spec_sections || {
		log_err "spec.md validation failed — /deviate-specify must complete first"
		emit_json_contract \
			"status" "SPEC_INVALID" \
			"phase" "tasks" \
			"reason" "spec.md missing required sections" \
			"spec_path" "$SPEC_PATH_RELATIVE" \
			"worktree_full" "$WORKTREE_PATH" \
			"skill_dir" "$SKILL_DIR" \
			"timestamp" "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
		exit 3
	}

	discover_research_artifacts
	resolve_tasks_target
	extract_slugs_from_path

	# Reuse from specify — true because the pre-script detects that
	# this session ran /deviate-specify first (the spec.md is committed
	# and the worktree exists with the correct branch).
	local reuse_from_specify="true"

	local git_state
	git_state=$(cd "$WORKTREE_PATH" && gather_git_state 2>/dev/null || echo '{}')

	# Build JSON contract
	local contract_json
	contract_json=$(jq -n \
		--arg status "READY" \
		--arg phase "tasks" \
		--arg branch_name "$BRANCH_NAME" \
		--arg worktree_full "$WORKTREE_PATH" \
		--arg spec_path "$SPEC_PATH" \
		--arg spec_path_relative "$SPEC_PATH_RELATIVE" \
		--arg tasks_target "$TASKS_TARGET" \
		--arg tasks_target_relative "$TASKS_TARGET_RELATIVE" \
		--arg design_path "${DESIGN_PATH:-}" \
		--arg data_model_path "${DATA_MODEL_PATH:-}" \
		--arg reuse_from_specify "$reuse_from_specify" \
		--arg epic_slug "${EPIC_SLUG:-}" \
		--arg issue_id "${ISSUE_ID:-}" \
		--arg issue_slug "${ISSUE_SLUG:-}" \
		--arg repo_root "$REPO_ROOT" \
		--arg skill_dir "$SKILL_DIR" \
		--argjson git_state "$git_state" \
		--arg timestamp "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
		'{
	    status: $status,
	    phase: $phase,
	    branch_name: $branch_name,
	    worktree_full: $worktree_full,
	    spec_path: $spec_path,
	    spec_path_relative: $spec_path_relative,
	    tasks_target: $tasks_target,
	    tasks_target_relative: $tasks_target_relative,
	    design_path: $design_path,
	    data_model_path: $data_model_path,
	    reuse_from_specify: $reuse_from_specify,
	    epic_slug: $epic_slug,
	    issue_id: $issue_id,
	    issue_slug: $issue_slug,
	    repo_root: $repo_root,
	    skill_dir: $skill_dir,
	    git_state: $git_state,
	    timestamp: $timestamp
	}')

	printf '%s\n' "$contract_json"
	log_ok "Pre-phase complete. Tasks target: $TASKS_TARGET"
}

# ── Validate tasks.md content ────────────────────────────────────────────
validate_tasks_content() {
	local tasks_file="$1"

	if [[ ! -f "$tasks_file" ]]; then
		log_err "tasks.md not found at $tasks_file"
		return 1
	fi

	# Check required section headers
	extract_spec_sections "$tasks_file" \
		"Implementation Tasks:" \
		"PHASE_1"

	# shellcheck disable=SC2178,SC2128  # SPEC_SECTIONS_MISSING is a comma-separated string
	local missing="$SPEC_SECTIONS_MISSING"
	if [[ -n "$missing" ]]; then
		log_err "tasks.md is missing required sections: $missing"
		return 1
	fi
	log_ok "Required sections present"

	# Check task ID format (T{NNN})
	local invalid_ids
	invalid_ids=$(grep -oP '\[T\d+\]' "$tasks_file" | grep -vP '\[T\d{3}\]' || true)
	if [[ -n "$invalid_ids" ]]; then
		log_err "Invalid task ID format found: $(echo "$invalid_ids" | tr '\n' ' ')"
		return 1
	fi
	log_ok "Task ID format validated (T{NNN})"

	# Check for completed checkboxes (must NOT have [x])
	local completed_tasks
	completed_tasks=$(grep -cP '-\s+\[x\]' "$tasks_file" || true)
	if [[ $completed_tasks -gt 0 ]]; then
		log_warn "Found $completed_tasks completed task(s) — tasks should start with empty [ ]"
		if [[ "$FORCE_MODE" != "true" ]]; then
			log_err "Tasks must start with empty [ ] checkboxes. Use --force to bypass."
			return 1
		fi
	fi

	# Check for Verification commands
	local tasks_without_verification
	tasks_without_verification=$(grep -cP '\[T\d{3}\]' "$tasks_file" || true)
	local verifications
	verifications=$(grep -cP 'Verification' "$tasks_file" || true)
	if [[ $tasks_without_verification -gt "$verifications" ]]; then
		log_warn "Some tasks may be missing Verification commands"
	fi

	# Count tasks
	local task_count
	task_count=$(grep -cP '\[T\d{3}\]' "$tasks_file" || true)
	log_ok "Found $task_count task(s)"

	return 0
}

# ── Post subcommand ──────────────────────────────────────────────────────
cmd_post() {
	log_info "Deviate-tasks post-phase starting..."
	log_info "  force_mode: $FORCE_MODE"

	validate_required_tools
	validate_repo
	log_ok "Repository validated: $REPO_ROOT"

	detect_worktree
	log_ok "Worktree path: $WORKTREE_PATH"

	discover_spec_md || {
		log_err "No spec.md found"
		echo '{"status":"FAILURE","reason":"SPEC_NOT_FOUND"}'
		exit 5
	}

	resolve_tasks_target
	extract_slugs_from_path

	# Extract epic number from slug (001-cli-command-tree → 001)
	EPIC_NUM=$(echo "$EPIC_SLUG" | grep -oE '^[0-9]{3}' || echo "$EPIC_SLUG")

	# Check if tasks.md was written by the LLM
	if [[ ! -f "$TASKS_TARGET" ]]; then
		log_err "tasks.md not found at $TASKS_TARGET — LLM must write it before post"
		echo '{"status":"FAILURE","reason":"TASKS_NOT_FOUND","path":"'"$TASKS_TARGET"'"}'
		exit 5
	fi

	log_ok "tasks.md found: $TASKS_TARGET"

	# Validate tasks content
	if ! validate_tasks_content "$TASKS_TARGET"; then
		if [[ "$FORCE_MODE" == "true" ]]; then
			log_warn "Validation failed but --force is set — proceeding with commit"
		else
			log_err "tasks.md validation failed. Use --force to bypass."
			echo '{"status":"FAILURE","reason":"TASKS_VALIDATION_FAILED","path":"'"$TASKS_TARGET"'"}'
			exit 5
		fi
	fi

	cd "$WORKTREE_PATH"

	# Stage the tasks file
	log_info "Staging tasks.md..."
	git add "$TASKS_TARGET_RELATIVE" 2>/dev/null || {
		log_err "Failed to stage tasks.md"
		echo '{"status":"FAILURE","reason":"STAGE_FAILED"}'
		exit 6
	}

	# Also stage related spec and ledger files
	git add "$SPEC_PATH_RELATIVE" 2>/dev/null || true
	git add "specs/" 2>/dev/null || true

	# Run pre-commit hooks if present
	if [[ -f "$WORKTREE_PATH/.pre-commit-config.yaml" ]] && command -v pre-commit >/dev/null 2>&1; then
		log_info "Running pre-commit hooks..."
		git diff --staged --name-only | xargs pre-commit run --files 2>/dev/null || true
		git add "$TASKS_TARGET_RELATIVE" 2>/dev/null || true
		git add "specs/" 2>/dev/null || true
	fi

	# Commit
	local commit_subject="docs(${EPIC_NUM}-${ISSUE_NUMBER}): add task decomposition for ${ISSUE_ID:-unknown}"
	log_info "Committing with: $commit_subject"
	if git commit --no-verify -m "$commit_subject" 2>/dev/null; then
		local commit_sha
		commit_sha=$(git rev-parse --short HEAD)
		log_ok "Committed: $commit_sha"

		emit_json_contract \
			"status" "SUCCESS" \
			"phase" "tasks" \
			"issue_id" "${ISSUE_ID:-unknown}" \
			"commit_sha" "$commit_sha" \
			"tasks_path" "$TASKS_TARGET_RELATIVE" \
			"next_action" "Run /deviate-execute to start executing tasks" \
			"timestamp" "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
	else
		log_err "Commit failed (possibly nothing to commit)"
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
