#!/usr/bin/env bash
# shellcheck disable=SC1009,SC1054,SC1073,SC1083,SC1056,SC1072,SC1078,SC1079
# This file contains a chezmoi template directive (curly-percent template)
# below that shellcheck cannot parse. Run `chezmoi apply` first to render the
# template, then run shellcheck on the rendered destination file.
#
# deviate-refactor.sh - Orchestrator for /deviate-refactor (TDD REFACTOR phase)
#
# This script wraps the operational concerns of the TDD REFACTOR phase:
#   - Locate the active TDD task from tasks.md
#   - Extract test_command and lint_command from constitution.md
#   - Emit JSON contract with task context
#   - Stage refactored files and commit
#
# Usage:
#   deviate-refactor.sh pre    # Discover task, emit JSON contract
#   deviate-refactor.sh post   # Stage refactored files and commit
#
# Exit codes:
#   0   Success
#   1   Invalid arguments
#   2   Pre-flight check failed
#   3   Task discovery failed
#   4   Constitution parsing failed
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

# ── Help / usage ─────────────────────────────────────────────────────────
show_help() {
	cat <<EOF
$SCRIPT_NAME - Orchestrator for /deviate-refactor (TDD REFACTOR phase)

SYNOPSIS
	$SCRIPT_NAME <pre|post>

SUBCOMMANDS
	pre     Discover active task, extract test/lint commands, emit JSON contract
	post    Stage refactored files and commit

EXIT CODES
	0   Success
	1   Invalid arguments
	2   Pre-flight check failed
	3   Task discovery failed
	4   Constitution parsing failed

EXAMPLES
	$SCRIPT_NAME pre     # Discover task and emit contract
	$SCRIPT_NAME post    # Stage and commit refactored files
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

# ── Locate active TDD task ──────────────────────────────────────────────
locate_active_task() {
	local tasks_file=""
	local spec_dir=""
	local task_id=""
	local task_title=""
	local task_type=""
	local verification=""
	local files_touched=""
	local task_details=""

	# Find the most recent tasks.md with in-progress or pending tasks
	local candidates
	candidates=$(find "$REPO_ROOT/specs" -name "tasks.md" -type f 2>/dev/null || true)

	if [[ -z "$candidates" ]]; then
		if [[ -f "$REPO_ROOT/tasks.md" ]]; then
			candidates="$REPO_ROOT/tasks.md"
		fi
	fi

	if [[ -z "$candidates" ]]; then
		log_err "No tasks.md found anywhere in repository"
		echo '{"status":"NO_TASKS_REMAINING","reason":"NO_TASKS_MD_FOUND","repo_root":"'"$REPO_ROOT"'"}'
		exit 3
	fi

	# Prefer in-progress [/] over pending [ ]
	while IFS= read -r candidate; do
		local dir
		dir=$(dirname "$candidate")
		local relative_dir
		relative_dir=$(realpath --relative-to="$REPO_ROOT" "$dir" 2>/dev/null || echo "$dir")

		# First look for in-progress tasks (GREEN phase just completed)
		local active_line
		active_line=$(grep -nE '^\s*-\s+\[/\]\s+\[T[0-9]+\]' "$candidate" | head -1 || true)

		# Fallback to pending
		if [[ -z "$active_line" ]]; then
			active_line=$(grep -nE '^\s*-\s+\[ \]\s+\[T[0-9]+\]' "$candidate" | head -1 || true)
		fi

		if [[ -n "$active_line" ]]; then
			tasks_file="$candidate"
			spec_dir="$relative_dir"

			task_id=$(echo "$active_line" | grep -oE '\[T[0-9]+\]' | head -1 | tr -d '[]' || echo "")
			if [[ -z "$task_id" ]]; then
				task_id=$(echo "$active_line" | grep -oE 'TASK-[0-9]+' | head -1 || echo "T001")
			fi

			local line_num
			line_num=$(echo "$active_line" | cut -d: -f1)
			task_title=$(sed -n "${line_num}p" "$candidate" | sed -E 's/^\s*-\s+\[[/ ]\]\s+\[T[0-9]+\]\s+//')

			# Extract task fields from subsequent lines
			local in_task_details=false
			local from_line=$((line_num + 1))
			local to_line
			to_line=$(wc -l <"$candidate")

			for ((i = from_line; i <= to_line; i++)); do
				local line
				line=$(sed -n "${i}p" "$candidate")

				if echo "$line" | grep -qE '^\s*-\s+\[[ \]/]\]'; then
					break
				fi
				if echo "$line" | grep -qE '^##'; then
					break
				fi

				if echo "$line" | grep -qE 'Task_Type'; then
					task_type=$(echo "$line" | sed -E 's/.*Task_Type[^:]*:\s*//' | xargs)
				elif echo "$line" | grep -qE 'Verification'; then
					verification=$(echo "$line" | sed -E 's/.*Verification[^:]*:\s*//' | xargs)
				elif echo "$line" | grep -qE 'Files_Touched'; then
					in_task_details=false
				elif echo "$line" | grep -qE 'Task_Details'; then
					in_task_details=true
				elif $in_task_details && echo "$line" | grep -qE '^\s*-'; then
					local detail
					detail=$(echo "$line" | sed -E 's/^\s*-\s+//')
					if [[ -z "$task_details" ]]; then
						task_details="$detail"
					else
						task_details="$task_details"$'\n'"$detail"
					fi
				elif echo "$line" | grep -qE '^\s+-'; then
					local file
					file=$(echo "$line" | sed -E 's/^\s+-\s+//' | xargs)
					if [[ -n "$file" ]]; then
						if [[ -z "$files_touched" ]]; then
							files_touched="$file"
						else
							files_touched="$files_touched"$'\n'"$file"
						fi
					fi
				fi
			done

			break
		fi
	done <<<"$candidates"

	if [[ -z "$task_id" ]]; then
		log_info "No active tasks found in any tasks.md"
		echo '{"status":"NO_TASKS_REMAINING","reason":"ALL_TASKS_COMPLETE","repo_root":"'"$REPO_ROOT"'"}'
		exit 3
	fi

	TASK_ID="$task_id"
	TASK_TITLE="$task_title"
	TASK_TYPE="$task_type"
	VERIFICATION="$verification"
	# shellcheck disable=SC2034  # Exported for LLM contract
	FILES_TOUCHED="$files_touched"
	# shellcheck disable=SC2034  # Exported for LLM contract
	TASK_DETAILS="$task_details"
	TASKS_FILE="$tasks_file"
	SPEC_DIR="$spec_dir"
}

# ── Extract test_command and lint_command from constitution ──────────────
extract_constitution_commands() {
	local constitution_file="$REPO_ROOT/specs/constitution.md"
	local test_command=""
	local lint_command=""

	if [[ ! -f "$constitution_file" ]]; then
		log_warn "No constitution.md found at $constitution_file — using defaults"
		if [[ -f "$REPO_ROOT/package.json" ]]; then
			test_command="npm test"
			lint_command="npm run lint || true"
		elif [[ -f "$REPO_ROOT/mix.exs" ]]; then
			test_command="mix test"
			lint_command="mix format --check-formatted"
		elif [[ -f "$REPO_ROOT/pyproject.toml" ]] || [[ -f "$REPO_ROOT/setup.py" ]]; then
			test_command="pytest"
			lint_command="ruff check ."
		elif [[ -f "$REPO_ROOT/Cargo.toml" ]]; then
			test_command="cargo test"
			lint_command="cargo fmt --check"
		elif [[ -f "$REPO_ROOT/go.mod" ]]; then
			test_command="go test ./..."
			lint_command="gofmt -l ."
		else
			test_command=""
			lint_command=""
		fi
		TEST_COMMAND="$test_command"
		LINT_COMMAND="$lint_command"
		return 0
	fi

	log_info "Reading constitution from: $constitution_file"

	# Extract test_command and lint_command from constitution.md
	test_command=$(grep -oP 'test_command["'':]+\s*\K[^"''\n]+' "$constitution_file" 2>/dev/null |
		sed 's/^[[:space:]]*//;s/[[:space:]]*$//' |
		head -1 || true)

	lint_command=$(grep -oP 'lint_command["'':]+\s*\K[^"''\n]+' "$constitution_file" 2>/dev/null |
		sed 's/^[[:space:]]*//;s/[[:space:]]*$//' |
		head -1 || true)

	# Fallback to project detection
	if [[ -z "$test_command" ]]; then
		if [[ -f "$REPO_ROOT/package.json" ]]; then
			test_command="npm test"
		elif [[ -f "$REPO_ROOT/mix.exs" ]]; then
			test_command="mix test"
		elif [[ -f "$REPO_ROOT/pyproject.toml" ]] || [[ -f "$REPO_ROOT/setup.py" ]]; then
			test_command="pytest"
		fi
	fi
	if [[ -z "$lint_command" ]]; then
		if [[ -f "$REPO_ROOT/package.json" ]]; then
			lint_command="npm run lint || true"
		elif [[ -f "$REPO_ROOT/mix.exs" ]]; then
			lint_command="mix format --check-formatted"
		elif [[ -f "$REPO_ROOT/pyproject.toml" ]] || [[ -f "$REPO_ROOT/setup.py" ]]; then
			lint_command="ruff check ."
		fi
	fi

	TEST_COMMAND="$test_command"
	LINT_COMMAND="$lint_command"
}

# ── Pre subcommand ───────────────────────────────────────────────────────
cmd_pre() {
	log_info "Deviate-refactor pre-phase starting..."

	validate_repo
	log_ok "Repository validated: $REPO_ROOT"

	locate_active_task
	log_ok "Task discovered: $TASK_ID"

	extract_constitution_commands
	log_ok "Test command: ${TEST_COMMAND:-<none>}"
	log_ok "Lint command: ${LINT_COMMAND:-<none>}"

	GIT_BRANCH=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "unknown")

	# Emit JSON contract
	emit_json_contract \
		"status" "READY" \
		"phase" "refactor" \
		"task_id" "$TASK_ID" \
		"task_title" "$TASK_TITLE" \
		"task_type" "$TASK_TYPE" \
		"verification" "$VERIFICATION" \
		"test_command" "$TEST_COMMAND" \
		"lint_command" "$LINT_COMMAND" \
		"spec_dir" "$SPEC_DIR" \
		"tasks_file" "$TASKS_FILE" \
		"repo_root" "$REPO_ROOT" \
		"git_branch" "$GIT_BRANCH" \
		"skill_dir" "$SKILL_DIR" \
		"timestamp" "$(date -u +%Y-%m-%dT%H:%M:%SZ)"

	log_ok "Pre-phase complete. Contract emitted to stdout."
}

# ── Post subcommand ──────────────────────────────────────────────────────
cmd_post() {
	log_info "Deviate-refactor post-phase starting..."

	validate_repo
	log_ok "Repository validated: $REPO_ROOT"

	cd "$REPO_ROOT"

	# Stage all tracked changes (refactored files written by LLM)
	git add -u

	# Stage spec directories
	if [[ -d "$REPO_ROOT/specs" ]]; then
		git add "$REPO_ROOT/specs/" 2>/dev/null || true
	fi

	# Check for staged changes
	if git diff --cached --quiet; then
		log_warn "No staged changes to commit."
		emit_json_contract \
			"status" "SUCCESS" \
			"phase" "refactor" \
			"action" "no_changes" \
			"timestamp" "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
		exit 0
	fi

	# Run pre-commit hooks if available
	if [[ -f "$REPO_ROOT/.pre-commit-config.yaml" ]] && command -v pre-commit >/dev/null 2>&1; then
		log_info "Running pre-commit hooks..."
		git diff --staged --name-only | xargs pre-commit run --files 2>/dev/null || true
		# Re-stage any hook modifications
		git add -u
		if [[ -d "$REPO_ROOT/specs" ]]; then
			git add "$REPO_ROOT/specs/" 2>/dev/null || true
		fi
	fi

	# Commit with conventional message
	local commit_subject="refactor($TASK_ID): improve code structure"
	if ! git commit -m "$commit_subject" -m "Phase: REFACTOR"; then
		log_err "Commit failed"
		echo '{"status":"FAILURE","reason":"COMMIT_FAILED"}'
		exit 6
	fi

	local commit_sha
	commit_sha=$(git rev-parse --short HEAD)
	log_ok "Committed: $commit_sha"

	emit_json_contract \
		"status" "SUCCESS" \
		"phase" "refactor" \
		"task_id" "$TASK_ID" \
		"commit_sha" "$commit_sha" \
		"timestamp" "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
}

# ── Dispatch ─────────────────────────────────────────────────────────────
parse_args "$@"
case "$SUBCOMMAND" in
pre) cmd_pre ;;
post) cmd_post ;;
esac
