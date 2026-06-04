#!/usr/bin/env bash
# shellcheck disable=SC1009,SC1054,SC1073,SC1083,SC1056,SC1072,SC1078,SC1079
# This file contains a chezmoi template directive (curly-percent template)
# below that shellcheck cannot parse. Run `chezmoi apply` first to render the
# template, then run shellcheck on the rendered destination file.
#
# deviate-execute.sh - Orchestrator for the /deviate-execute (DIRECT task execution)
#
# This script wraps the operational concerns of direct task execution:
#   - Flag parsing (--auto, --dry-run, <TASK_ID>, <MANIFEST_PATH>)
#   - Workflow discovery (spec / tm / plan / unknown) from branch and directory
#   - Task auto-discovery from tasks.md (active -> next -> explicit)
#   - Task detail extraction from tasks.md
#   - Project-type detection -> validation command resolution
#   - Task state transitions in tasks.md ([ ] -> [x])
#   - File staging (tracked + spec files)
#   - Pre-commit hook execution with hash-diff re-staging
#   - .gitignore maintenance for stray untracked files
#   - Conventional commit execution with SHA capture
#
# Usage:
#   deviate-execute.sh pre [--auto] [--dry-run] [<TASK_ID>]
#   deviate-execute.sh post <MANIFEST_PATH> [--dry-run]
#
# The 'pre' subcommand emits a JSON contract on stdout (the LLM parses
# it directly). The 'post' subcommand takes the manifest path as a
# positional argument, re-discovers the workflow from the repo, reads
# the task_id from the manifest, marks the task complete, stages files,
# runs precommit hooks, and commits the work.
#
# Exit codes:
#   0   Success
#   1   Invalid arguments
#   2   Pre-flight check failed (not a repo, missing required scripts)
#   3   Workflow or task discovery failed
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
SKILL_DIR="$(CDPATH="" cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# ── No external script dependencies ──────────────────────────────────────
# This script is fully self-contained. All task discovery, state management,
# and spec context resolution is done inlined from tasks.md directly.

# ── Default flags ────────────────────────────────────────────────────────
CONTINUOUS_MODE=false
DRY_RUN=false
EXPLICIT_TASK=""
MANIFEST_PATH=""

# ── Help / usage ─────────────────────────────────────────────────────────
show_help() {
	cat <<EOF
$SCRIPT_NAME - Orchestrator for the /deviate-execute direct task execution

SYNOPSIS
    $SCRIPT_NAME <pre|post> [OPTIONS]

DESCRIPTION
    Wraps the operational concerns of direct task execution. The 'pre'
    subcommand discovers the workflow, auto-discovers the next task, and
    emits a JSON contract. The 'post' subcommand reads the LLM-written
    execution manifest, marks the task complete, stages files, runs
    precommit hooks, and commits the work.

SUBCOMMANDS
    pre     Discover workflow + task, emit JSON contract
    post    Mark complete, stage, run hooks, commit

OPTIONS (pre only)
    --auto            Continuous mode: after post, loop back to pre
    --dry-run         Preview-only: emit plan and stop (no mutations)
    <TASK_ID>         Execute a specific task (e.g., T001) instead of auto-discovery

OPTIONS (post only)
    <MANIFEST_PATH>   Path to the LLM-written execution manifest JSON
    --dry-run         Preview-only: emit plan and stop (no mutations)

EXIT CODES
    0   Success
    1   Invalid arguments
    2   Pre-flight check failed
    3   Workflow or task discovery failed
    5   Manifest validation failed
    6   Commit execution failed

EXAMPLES
    $SCRIPT_NAME pre                                       # Auto-discover next task
    $SCRIPT_NAME pre T042                                  # Execute a specific task
    $SCRIPT_NAME pre --auto                                # Continuous mode
    $SCRIPT_NAME pre --dry-run T001                        # Preview without mutation
    # After LLM implements the task and writes the manifest:
    $SCRIPT_NAME post /tmp/deviate-execute.XXX/execution-manifest.json
                                                          # Mark complete and commit
    $SCRIPT_NAME post <manifest> --dry-run                 # Preview post-phase
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
		--auto)
			CONTINUOUS_MODE=true
			shift
			;;
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
			# First positional: TASK_ID for pre, MANIFEST_PATH for post
			if [[ "$SUBCOMMAND" == "post" ]]; then
				if [[ -z "$MANIFEST_PATH" ]]; then
					MANIFEST_PATH="$1"
				else
					log_err "Unexpected positional argument: $1"
					exit 1
				fi
			else
				if [[ -z "$EXPLICIT_TASK" ]]; then
					EXPLICIT_TASK="$1"
				else
					log_err "Unexpected positional argument: $1"
					exit 1
				fi
			fi
			shift
			;;
		esac
	done

	# Subcommand-specific required args
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

# ── Workflow discovery ───────────────────────────────────────────────────
discover_workflow() {
	local workflow=""
	local spec_dir=""

	# Priority 1: Spec mode (worktree with specs/)
	if [[ -d "$REPO_ROOT/specs" ]]; then
		# Resolve spec dir from branch name or directory search
		local branch_name safe_branch_name
		branch_name=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "unknown")
		safe_branch_name=$(basename "$branch_name")

		# Parse feat/{EPIC}/{FEATURE} pattern
		if [[ "$branch_name" =~ ^feat/([^/]+)/(.+)$ ]]; then
			spec_dir="specs/${BASH_REMATCH[1]}/${BASH_REMATCH[2]}"
		else
			# Search for nested structure: specs/*/<branch_name>/
			cd "$REPO_ROOT"
			for feature_dir in specs/*/; do
				if [[ -d "${feature_dir}${safe_branch_name}" ]]; then
					spec_dir="${feature_dir}${safe_branch_name}"
					break
				fi
			done
			# Fallback to legacy flat structure: specs/<branch_name>/
			if [[ -z "$spec_dir" ]] && [[ -d "specs/$safe_branch_name" ]]; then
				spec_dir="specs/$safe_branch_name"
			fi
		fi

		if [[ -n "$spec_dir" ]] && [[ -f "$REPO_ROOT/$spec_dir/tasks.md" ]]; then
			workflow="spec"
		fi
	fi

	# Priority 2: TM mode
	if [[ -z "$workflow" ]] && [[ -d "$REPO_ROOT/.task-master" ]]; then
		workflow="tm"
	fi

	# Priority 3: Plan mode
	if [[ -z "$workflow" ]] && [[ -d "$REPO_ROOT/thoughts/plans" ]]; then
		workflow="plan"
	fi

	# Fallback
	if [[ -z "$workflow" ]]; then
		workflow="unknown"
	fi

	WORKFLOW="$workflow"
	SPEC_DIR="$spec_dir"
}

# ── Task discovery (spec mode) ───────────────────────────────────────────
discover_task_spec() {
	local source=""
	local tasks_file="$REPO_ROOT/$SPEC_DIR/tasks.md"

	if [[ ! -f "$tasks_file" ]]; then
		log_err "tasks.md not found at $tasks_file"
		return 1
	fi

	if [[ -n "$EXPLICIT_TASK" ]]; then
		TASK_ID="$EXPLICIT_TASK"
		source="explicit"
	else
		# First check for in-progress task [/]
		local match
		match=$(grep -E "^- \[/\] \[T[0-9]{3}\]" "$tasks_file" | head -n 1)
		if [[ -n "$match" ]]; then
			TASK_ID=$(echo "$match" | sed -E 's/.*\[(T[0-9]{3})\].*/\1/')
			source="in_progress"
		else
			# Get next available unchecked task [ ]
			match=$(grep -E "^- \[ \] \[T[0-9]{3}\]" "$tasks_file" | head -n 1)
			if [[ -n "$match" ]]; then
				TASK_ID=$(echo "$match" | sed -E 's/.*\[(T[0-9]{3})\].*/\1/')
				source="next"
			else
				TASK_ID=""
				return 1
			fi
		fi
	fi

	if [[ -z "$TASK_ID" ]]; then
		return 1
	fi

	TASK_SOURCE="$source"
	return 0
}

# ── Extract task fields directly from tasks.md ───────────────────────────
# Find the line number of the task matching TASK_ID in tasks.md
find_task_line_num() {
	local tasks_file="$1"
	local task_id="$2"
	grep -n "^- \[.\] \[$task_id\]" "$tasks_file" 2>/dev/null | head -n 1 | cut -d: -f1 || echo ""
}

# Extract a single-line field (e.g., Task_Type, Description) from tasks.md
parse_task_field() {
	local field_name="$1"
	local value=""
	value=$(grep -E "  - \[${field_name}\]: " "$TASKS_FILE" 2>/dev/null |
		sed -E "s/.*\[${field_name}\]:[[:space:]]*//" | head -n 1)
	printf '%s' "$value"
}

# Extract a multi-line field (e.g., Files_Touched, Task_Details) from tasks.md
parse_task_multiline_field() {
	local field_name="$1"
	local value=""
	local in_block=false
	while IFS= read -r line; do
		if [[ "$line" == "  - [${field_name}]:" ]]; then
			in_block=true
		elif [[ "$in_block" == "true" ]]; then
			if [[ "$line" == "    - "* ]]; then
				trimmed="${line#    - }"
				[[ -n "$value" ]] && value+=$'\n'
				value+="- ${trimmed}"
			elif [[ "$line" == "  - ["* ]] || [[ "$line" == "- ["* ]] || [[ -z "$line" ]]; then
				in_block=false
			fi
		fi
	done <"$TASKS_FILE"
	printf '%s' "$value"
}

# ── Project-type detection → validation command ─────────────────────────
resolve_validation_command() {
	if [[ -f "$REPO_ROOT/package.json" ]]; then
		VALIDATION_COMMAND="npm run lint"
		VALIDATION_TYPE="lint"
	elif [[ -f "$REPO_ROOT/mix.exs" ]]; then
		VALIDATION_COMMAND="mix format --check-formatted"
		VALIDATION_TYPE="format"
	elif [[ -f "$REPO_ROOT/pyproject.toml" ]] || [[ -f "$REPO_ROOT/setup.py" ]]; then
		VALIDATION_COMMAND="ruff check ."
		VALIDATION_TYPE="lint"
	elif [[ -f "$REPO_ROOT/Cargo.toml" ]]; then
		VALIDATION_COMMAND="cargo fmt --check"
		VALIDATION_TYPE="format"
	elif [[ -f "$REPO_ROOT/go.mod" ]]; then
		VALIDATION_COMMAND="gofmt -l ."
		VALIDATION_TYPE="format"
	else
		VALIDATION_COMMAND=""
		VALIDATION_TYPE="none"
	fi
}

# ── Pre subcommand ───────────────────────────────────────────────────────
cmd_pre() {
	log_info "Deviate-execute pre-phase starting..."
	log_info "  continuous_mode: $CONTINUOUS_MODE"
	log_info "  dry_run: $DRY_RUN"
	log_info "  explicit_task: ${EXPLICIT_TASK:-<none>}"

	validate_repo
	log_ok "Repository validated: $REPO_ROOT"

	discover_workflow
	log_info "Workflow: $WORKFLOW"

	if [[ "$WORKFLOW" == "unknown" ]]; then
		log_warn "No workflow detected (no specs/, .task-master/, or thoughts/plans/)"
		emit_json_contract \
			"status" "NO_WORKFLOW" \
			"phase" "execute" \
			"workflow" "$WORKFLOW" \
			"skill_dir" "$SKILL_DIR" \
			"timestamp" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
			"message" "Ask user to specify: spec, tm, or plan"
		exit 0
	fi

	# Task discovery (spec mode only for now)
	if [[ "$WORKFLOW" == "spec" ]]; then
		if ! discover_task_spec; then
			log_info "No tasks remaining in $SPEC_DIR/tasks.md"
			emit_json_contract \
				"status" "NO_TASKS_REMAINING" \
				"phase" "execute" \
				"workflow" "$WORKFLOW" \
				"spec_dir" "$SPEC_DIR" \
				"skill_dir" "$SKILL_DIR" \
				"timestamp" "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
			exit 0
		fi
		log_ok "Task discovered: $TASK_ID (source: $TASK_SOURCE)"

		# Set TASKS_FILE for field extraction functions
		TASKS_FILE="$REPO_ROOT/$SPEC_DIR/tasks.md"

		# Extract task fields directly from tasks.md
		TASK_TITLE=$(grep -E "^- \[.\] \[$TASK_ID\]" "$TASKS_FILE" | head -n 1 | sed -E "s/^- \[.\] \[$TASK_ID\] //")
		TASK_TYPE=$(parse_task_field "Task_Type")
		TEST_STRATEGY=$(parse_task_field "Test_Strategy")
		VERIFICATION=$(parse_task_field "Verification")
		ESTIMATED_TIME=$(parse_task_field "Estimated_Time")
		DEPENDENCY=$(parse_task_field "Dependency")
		FILES_TOUCHED=$(parse_task_multiline_field "Files_Touched")
		TASK_DETAILS=$(parse_task_multiline_field "Task_Details")
	else
		# TM/Plan mode: placeholders (exported for downstream consumers)
		export TASK_ID="${EXPLICIT_TASK:-unknown}"
		TASK_TITLE=""
		export TASK_TYPE=""
		TEST_STRATEGY=""
		VERIFICATION=""
		ESTIMATED_TIME=""
		DEPENDENCY=""
		# shellcheck disable=SC2034  # exported for LLM contract consumption
		export FILES_TOUCHED=""
		# shellcheck disable=SC2034  # exported for LLM contract consumption
		export TASK_DETAILS=""
		if [[ -n "$EXPLICIT_TASK" ]]; then
			TASK_SOURCE="explicit"
		else
			TASK_SOURCE="unknown"
		fi
	fi

	resolve_validation_command
	log_ok "Validation command: ${VALIDATION_COMMAND:-<none>}"

	# Branch info
	GIT_BRANCH=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "unknown")

	# Create temp dir for plan_target (manifest handoff to post)
	TEMP_DIR=$(create_temp_dir "deviate-execute") || {
		log_err "Cannot create temp directory"
		emit_json_contract \
			"status" "FAILURE" \
			"phase" "execute" \
			"reason" "TEMP_DIR_CREATION_FAILED" \
			"skill_dir" "$SKILL_DIR"
		exit 2
	}
	PLAN_TARGET="$TEMP_DIR/execution-manifest.json"

	# Build JSON contract
	CONTRACT=$(emit_json_contract \
		"status" "READY" \
		"phase" "execute" \
		"workflow" "$WORKFLOW" \
		"spec_dir" "$SPEC_DIR" \
		"repo_root" "$REPO_ROOT" \
		"git_branch" "$GIT_BRANCH" \
		"task_id" "$TASK_ID" \
		"task_title" "$TASK_TITLE" \
		"task_type" "$TASK_TYPE" \
		"test_strategy" "$TEST_STRATEGY" \
		"verification" "$VERIFICATION" \
		"estimated_time" "$ESTIMATED_TIME" \
		"dependency" "$DEPENDENCY" \
		"task_source" "$TASK_SOURCE" \
		"auto_mode" "$CONTINUOUS_MODE" \
		"dry_run" "$DRY_RUN" \
		"validation_command" "$VALIDATION_COMMAND" \
		"validation_type" "$VALIDATION_TYPE" \
		"plan_target" "$PLAN_TARGET" \
		"skill_dir" "$SKILL_DIR" \
		"timestamp" "$(date -u +%Y-%m-%dT%H:%M:%SZ)")

	# Emit on stdout (what the LLM parses)
	printf '%s\n' "$CONTRACT"

	log_ok "Pre-phase complete. Plan target: $PLAN_TARGET"
}

# ── Post subcommand ──────────────────────────────────────────────────────
cmd_post() {
	log_info "Deviate-execute post-phase starting..."
	log_info "  manifest_path: $MANIFEST_PATH"
	log_info "  dry_run: $DRY_RUN"

	validate_repo
	log_ok "Repository validated: $REPO_ROOT"

	# Read the LLM-written execution manifest (path passed as positional arg)
	if [[ ! -f "$MANIFEST_PATH" ]]; then
		log_err "Execution manifest not found at: $MANIFEST_PATH"
		log_err "The LLM must write the execution manifest before running post"
		echo '{"status":"FAILURE","reason":"MANIFEST_NOT_FOUND","path":"'"$MANIFEST_PATH"'"}'
		exit 5
	fi

	log_info "Reading execution manifest from: $MANIFEST_PATH"
	local manifest
	manifest=$(cat "$MANIFEST_PATH")

	# Validate manifest has required fields
	local task_id commit_subject files_count
	task_id=$(printf '%s' "$manifest" | jq -r '.task_id // empty')
	commit_subject=$(printf '%s' "$manifest" | jq -r '.commit_subject // empty')
	files_count=$(printf '%s' "$manifest" | jq -r '.files_modified | length // 0')

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

	# Re-discover workflow + spec_dir from the repo (the pre contract
	# isn't persisted, so post must recover this state from disk)
	discover_workflow
	log_info "Workflow: $WORKFLOW"

	# Dry-run: emit preview and stop
	if [[ "$DRY_RUN" == "true" ]]; then
		log_info "Dry run — no mutations will be made"
		printf '%s' "$manifest" | jq -n --argjson m "$manifest" \
			--arg task_id "$task_id" \
			--arg workflow "$WORKFLOW" \
			--arg spec_dir "$SPEC_DIR" \
			'{status:"DRY_RUN",task_id:$task_id,workflow:$workflow,spec_dir:$spec_dir,manifest:$m}'
		exit 0
	fi

	cd "$REPO_ROOT"

	# Step 1: Mark task complete (spec mode only)
	if [[ "$WORKFLOW" == "spec" ]] && [[ -n "$SPEC_DIR" ]]; then
		local tasks_file="$REPO_ROOT/$SPEC_DIR/tasks.md"
		if [[ -f "$tasks_file" ]]; then
			log_info "Marking $task_id as complete in $tasks_file"
			# Change [/] or [ ] to [x] for the task (self-contained, no external scripts)
			perl -i -pe "s/^- \[[ \/]\] \[$task_id\]/- [x] [$task_id]/" "$tasks_file"
			log_ok "Task $task_id marked complete"
		fi
	fi

	# Step 2: Stage files (tracked + spec + manifest target)
	log_info "Staging tracked changes..."
	git add -u

	# Always stage spec and task files
	if [[ -n "$SPEC_DIR" ]]; then
		git add "$SPEC_DIR"/*.md specs/ 2>/dev/null || true
	fi

	# Step 3: Run pre-commit hooks with hash-diff verification
	if [[ -f "$REPO_ROOT/.pre-commit-config.yaml" ]] || [[ -f "$REPO_ROOT/.git/hooks/pre-commit" ]]; then
		local staged_before staged_after
		staged_before=$(git diff --staged --name-only | sort | sha256sum | cut -d' ' -f1)

		if [[ -f "$REPO_ROOT/.pre-commit-config.yaml" ]] && command -v pre-commit >/dev/null 2>&1; then
			log_info "Running pre-commit hooks..."
			git diff --staged --name-only | xargs pre-commit run --files 2>/dev/null || true
		fi
		if [[ -x "$REPO_ROOT/.git/hooks/pre-commit" ]]; then
			"$REPO_ROOT/.git/hooks/pre-commit" 2>/dev/null || true
		fi

		staged_after=$(git diff --staged --name-only | sort | sha256sum | cut -d' ' -f1)
		if [[ "$staged_before" != "$staged_after" ]]; then
			log_info "Hooks modified staged files — re-staging"
			git add -u
			[[ -n "$SPEC_DIR" ]] && git add "$SPEC_DIR"/*.md specs/ 2>/dev/null || true
		fi
	fi

	# Step 4: Update .gitignore for stray untracked files
	local new_gitignore_entries=()
	while IFS= read -r line; do
		local file
		file=$(echo "$line" | awk '{print $2}')
		if [[ "$file" == *.log || "$file" == *.tmp || "$file" == node_modules/* ]]; then
			# Check if already ignored
			if ! grep -qxF "$file" "$REPO_ROOT/.gitignore" 2>/dev/null; then
				new_gitignore_entries+=("$file")
			fi
		fi
	done < <(git status --porcelain | grep "^??" || true)

	if [[ ${#new_gitignore_entries[@]} -gt 0 ]]; then
		log_info "Adding ${#new_gitignore_entries[@]} entries to .gitignore"
		{
			echo ""
			echo "# Auto-added by deviate-execute on $(date -u +%Y-%m-%d)"
			printf '%s\n' "${new_gitignore_entries[@]}"
		} >>"$REPO_ROOT/.gitignore"
		git add "$REPO_ROOT/.gitignore"
	fi

	# Step 5: Commit with conventional format
	log_info "Committing with conventional message..."

	# Check for staged changes before attempting commit
	if git diff --cached --quiet; then
		log_err "No staged changes to commit. Run $(git status) and $(git diff) for diagnostics."
		echo '{"status":"FAILURE","reason":"COMMIT_FAILED","detail":"No staged changes to commit"}'
		exit 6
	fi

	local commit_body
	commit_body=$(printf '%s' "$manifest" | jq -r '.commit_body // ""')
	local validation_summary
	validation_summary=$(printf '%s' "$manifest" | jq -r '.validation.summary // "see manifest"')

	local commit_args=(-m "$commit_subject")
	if [[ -n "$commit_body" ]]; then
		commit_args+=(-m "$commit_body")
	fi
	commit_args+=(-m "Mode: DIRECT")
	commit_args+=(-m "Validation: $validation_summary")
	if [[ -n "$SPEC_DIR" ]]; then
		commit_args+=(-m "spec_dir: $SPEC_DIR")
	fi

	if ! git commit "${commit_args[@]}"; then
		local status_output diff_output
		status_output=$(git status --short 2>&1)
		diff_output=$(git diff --cached 2>&1)
		log_err "Commit failed. Git status:"
		log_err "$status_output"
		log_err "Staged diff:"
		log_err "$diff_output"
		echo '{"status":"FAILURE","reason":"COMMIT_FAILED"}'
		exit 6
	fi

	# Step 6: Capture commit SHA
	local commit_sha
	commit_sha=$(git rev-parse --short HEAD)
	log_ok "Committed: $commit_sha"

	# Step 7: Emit success status
	local log_output
	log_output=$(git --no-pager log --oneline --decorate -3 2>/dev/null || true)

	emit_json_contract \
		"status" "SUCCESS" \
		"phase" "execute" \
		"task_id" "$task_id" \
		"workflow" "$WORKFLOW" \
		"commit_sha" "$commit_sha" \
		"files_modified" "$files_count" \
		"auto_mode" "$CONTINUOUS_MODE" \
		"next_action" "$([[ "$CONTINUOUS_MODE" == "true" ]] && echo "Run pre again for next task" || echo "Task complete")" \
		"recent_commits" "$log_output" \
		"timestamp" "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
}

# ── Dispatch ─────────────────────────────────────────────────────────────
parse_args "$@"
case "$SUBCOMMAND" in
pre) cmd_pre ;;
post) cmd_post ;;
esac
