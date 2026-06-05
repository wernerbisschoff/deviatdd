#!/usr/bin/env bash
#
# deviate-specify.sh - Orchestrator for the /deviate-specify skill
#
# This script wraps operational concerns of the functional specification
# contract phase:
#   - Repository discovery (walk-up to .git)
#   - Issue resolution (by ID, next unblocked, or shard file)
#   - Worktree creation and branch checkout
#   - Ledger claim and push-to-claim
#   - PRD path resolution and traceability pre-validation
#   - spec.md content validation (required sections, Gherkin syntax)
#   - Atomic git commit
#
# Usage:
#   deviate-specify.sh pre
#   deviate-specify.sh post
#   deviate-specify.sh post --force
#
# The 'pre' subcommand resolves the target issue, creates a worktree,
# claims the issue in the ledger, pre-validates PRD traceability, and
# emits a JSON contract on stdout. The 'post' subcommand validates the
# written spec.md, commits, and updates the ledger.
#
# Exit codes:
#   0   Success
#   1   Invalid arguments
#   2   Pre-flight check failed (not a repo, missing required scripts)
#   3   Issue resolution failed
#   4   Worktree creation or claim failed
#   5   spec.md validation failed
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
	                    ($status_map[.] // "UNKNOWN") == "COMPLETED"
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

# ── No external scripts required (fully self-contained) ──────────────────
# This script uses common.sh.tmpl functions directly.

# ── Default flags ────────────────────────────────────────────────────────
FORCE_MODE=false
DRY_RUN=false

# ── Help / usage ─────────────────────────────────────────────────────────
show_help() {
	cat <<EOF
$SCRIPT_NAME - Orchestrator for the /deviate-specify skill

SYNOPSIS
	$SCRIPT_NAME <pre|post> [OPTIONS]

DESCRIPTION
	Wraps operational concerns of the functional specification contract
	phase. The 'pre' subcommand resolves the target issue, creates a
	worktree, claims the issue in the ledger, pre-validates PRD
	traceability, and emits a JSON contract. The 'post' subcommand
	validates the written spec.md, commits, and updates the ledger.

SUBCOMMANDS
	pre     Resolve issue, create worktree, claim, validate, emit contract
	post    Validate spec.md, commit, update ledger

OPTIONS
	--force   (post only) Bypass validation errors and commit anyway
	--dry-run (pre only)  Resolve issue and emit contract without creating
	                      worktree or claiming the issue

EXIT CODES
	0   Success
	1   Invalid arguments
	2   Pre-flight check failed
	3   Issue resolution failed
	4   Worktree creation or claim failed
	5   spec.md validation failed
	6   Commit execution failed

EXAMPLES
	$SCRIPT_NAME pre
	$SCRIPT_NAME pre --dry-run
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
	if ! command -v git >/dev/null 2>&1; then
		missing+=("git")
	fi
	if ! command -v gh >/dev/null 2>&1; then
		log_warn "gh (GitHub CLI) not found — push-to-claim will be skipped"
	fi

	if [[ ${#missing[@]} -gt 0 ]]; then
		log_err "Required tools missing: ${missing[*]}"
		echo "{\"status\":\"FAILURE\",\"reason\":\"MISSING_REQUIRED_TOOLS\",\"missing\":$(printf '%s\n' "${missing[@]}" | jq -R . | jq -s .)}"
		exit 2
	fi
}

# ── Specs directory discovery ────────────────────────────────────────────
discover_specs_dir() {
	SPECS_DIR="$REPO_ROOT/specs"

	if [[ ! -d "$SPECS_DIR" ]]; then
		log_err "No specs/ directory found at $SPECS_DIR"
		return 1
	fi

	export SPECS_DIR
	return 0
}

# ── Epic discovery (most recently modified NNN-* under specs/) ───────────
discover_epic() {
	local latest
	# shellcheck disable=SC2012  # ls with glob pattern is safe for NNN-* format
	latest=$(ls -1dt "$SPECS_DIR"/[0-9][0-9][0-9]-* 2>/dev/null | head -1 || true)

	if [[ -z "$latest" ]]; then
		# shellcheck disable=SC2012  # ls with glob pattern is safe for NNN-* format
		latest=$(ls -1d "$SPECS_DIR"/[0-9][0-9][0-9]-* 2>/dev/null | head -1 || true)
	fi

	if [[ -z "$latest" ]]; then
		log_err "No feature epic directories (NNN-*) found in specs/"
		return 1
	fi

	EPIC_DIR="$latest"
	EPIC_SLUG=$(basename "$latest")
	EPIC_ID=$(echo "$EPIC_SLUG" | grep -oE '^[0-9]{3}' || echo "$EPIC_SLUG")
	export EPIC_DIR EPIC_SLUG EPIC_ID
	return 0
}

# ── Issue resolution from the JSONL ledger ───────────────────────────────
resolve_issue() {
	local issues_file="$SPECS_DIR/issues.jsonl"
	local issue_id="${ISSUE_ID:-}"

	if [[ ! -f "$issues_file" ]]; then
		log_err "Issues ledger not found at $issues_file"
		return 1
	fi

	# If no specific issue ID, pick the oldest unblocked BACKLOG feature issue
	if [[ -z "$issue_id" ]]; then
		log_info "No explicit issue ID — selecting oldest unblocked BACKLOG issue"

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
	                        ($status_map[.] // "UNKNOWN") == "COMPLETED"
	                    )
	                ))]
	        | sort_by(.timestamp // "1970-01-01")
	        | .[0] // empty
	    ')

		if [[ -z "$selected" ]] || [[ "$selected" == "null" ]]; then
			log_err "No unblocked BACKLOG issues available"
			return 1
		fi

		issue_id=$(echo "$selected" | jq -r '.issue_id // empty')
	fi

	if [[ -z "$issue_id" ]]; then
		log_err "Could not resolve issue ID"
		return 1
	fi

	# Get the latest state of the issue from the ledger
	local issue_json
	issue_json=$(jq -R 'fromjson' "$issues_file" 2>/dev/null |
		jq -s --arg id "$issue_id" '
	    ([.[] | select(.type == "feature")]
	        | group_by(.issue_id) | map(last)) as $features
	    | [$features[] | select(.issue_id == $id)]
	    | .[0] // empty
	')

	if [[ -z "$issue_json" ]] || [[ "$issue_json" == "null" ]]; then
		log_err "Issue $issue_id not found in ledger"
		return 1
	fi

	ISSUE_ID="$issue_id"
	ISSUE_JSON="$issue_json"
	ISSUE_TITLE=$(echo "$issue_json" | jq -r '.title // "Untitled Issue"')
	ISSUE_SOURCE_FILE=$(echo "$issue_json" | jq -r '.source_file // ""')
	ISSUE_STATUS=$(echo "$issue_json" | jq -r '.status // "BACKLOG"')

	# Check event log for completed status — the feature entry may still say
	# BACKLOG even if the issue was completed in a prior session.
	local latest_event
	latest_event=$(jq -R 'fromjson' "$issues_file" 2>/dev/null |
		jq -s --arg id "$issue_id" '
	    [.[] | select(.issue_id == $id and (.type | not) and .status == "COMPLETED")]
	    | last
	')

	if [[ -n "$latest_event" && "$latest_event" != "null" ]]; then
		log_warn "Issue $issue_id is already COMPLETED (event log) — cannot claim"
		return 1
	fi

	export ISSUE_ID ISSUE_JSON ISSUE_TITLE ISSUE_SOURCE_FILE ISSUE_STATUS
	return 0
}

# ── Issue body reading ───────────────────────────────────────────────────
# shellcheck disable=SC2120,SC2329  # Invoked indirectly via parse_issue_source
read_issue_body() {
	if [[ -z "$ISSUE_SOURCE_FILE" ]]; then
		log_warn "No source_file in issue — issue body will be empty"
		ISSUE_BODY=""
		return 0
	fi

	local full_path="$REPO_ROOT/$ISSUE_SOURCE_FILE"
	if [[ ! -f "$full_path" ]]; then
		log_warn "Issue body file not found at $full_path — body will be empty"
		ISSUE_BODY=""
		return 0
	fi

	ISSUE_BODY=$(cat "$full_path")
	export ISSUE_BODY
	return 0
}

# ── Parse source_file for slug and number ────────────────────────────────
parse_issue_source() {
	if [[ -z "$ISSUE_SOURCE_FILE" ]]; then
		# Derive from epic and issue title
		local slug
		slug=$(echo "$ISSUE_TITLE" | tr '[:upper:]' '[:lower:]' | sed 's/[^a-z0-9]/-/g' | sed 's/--*/-/g' | sed 's/^-//;s/-$//')
		ISSUE_SLUG="$(printf '%03d' "${ISSUE_NUMBER:-1}")-$slug"
		export ISSUE_SLUG
		return 0
	fi

	if [[ "$ISSUE_SOURCE_FILE" =~ ^specs/([^/]+)/issues/([0-9]+)-(.+)\.md$ ]]; then
		ISSUE_EPIC="${BASH_REMATCH[1]}"
		ISSUE_NUMBER="${BASH_REMATCH[2]}"
		ISSUE_SLUG="${ISSUE_NUMBER}-${BASH_REMATCH[3]}"
		ISSUE_NUMBER_INT=$((10#${ISSUE_NUMBER}))
		export ISSUE_EPIC ISSUE_NUMBER ISSUE_SLUG ISSUE_NUMBER_INT
	else
		log_warn "Source file does not match expected pattern: $ISSUE_SOURCE_FILE"
		local slug
		slug=$(echo "$ISSUE_TITLE" | tr '[:upper:]' '[:lower:]' | sed 's/[^a-z0-9]/-/g' | sed 's/--*/-/g' | sed 's/^-//;s/-$//')
		ISSUE_SLUG="001-$slug"
		export ISSUE_SLUG
	fi
}

# ── PRD path resolution ──────────────────────────────────────────────────
resolve_prd_path() {
	local prd_path="$EPIC_DIR/prd.md"
	if [[ ! -f "$prd_path" ]]; then
		log_warn "PRD not found at $prd_path"
		PRD_PATH=""
		export PRD_PATH
		return 0
	fi

	PRD_PATH="$prd_path"
	export PRD_PATH
	return 0
}

# ── PRD traceability validation ──────────────────────────────────────────
validate_prd_traceability() {
	if [[ -z "$PRD_PATH" ]]; then
		TRACEABILITY_STATUS="FAIL"
		TRACEABILITY_DETAILS="PRD not found — traceability cannot be validated"
		log_warn "PRD traceability: FAIL (no PRD)"
		export TRACEABILITY_STATUS TRACEABILITY_DETAILS
		return 1
	fi

	if ! command -v jq >/dev/null 2>&1; then
		TRACEABILITY_STATUS="FAIL"
		TRACEABILITY_DETAILS="jq not available for PRD traceability"
		log_warn "PRD traceability: FAIL (jq missing)"
		export TRACEABILITY_STATUS TRACEABILITY_DETAILS
		return 1
	fi

	# Extract FR IDs from the PRD
	local prd_frs
	prd_frs=$(grep -oE 'FR-[0-9]+[-_]?[0-9]*' "$PRD_PATH" | sort -u || true)

	# Extract FR IDs from the issue body
	local issue_frs
	issue_frs=$(echo "$ISSUE_BODY" | grep -oE 'FR-[0-9]+[-_]?[0-9]*' | sort -u || true)

	if [[ -z "$issue_frs" ]]; then
		TRACEABILITY_STATUS="WARN"
		TRACEABILITY_DETAILS="No FR references found in issue body"
		log_warn "PRD traceability: WARN (no FRs in issue body)"
		export TRACEABILITY_STATUS TRACEABILITY_DETAILS
		return 0
	fi

	# Check all issue FRs exist in the PRD
	local missing=()
	while IFS= read -r fr; do
		[[ -z "$fr" ]] && continue
		if ! echo "$prd_frs" | grep -qx "$fr"; then
			missing+=("$fr")
		fi
	done <<<"$issue_frs"

	if [[ ${#missing[@]} -eq 0 ]]; then
		TRACEABILITY_STATUS="PASS"
		TRACEABILITY_DETAILS="All FRs present in PRD"
		log_ok "PRD traceability: PASS"
	else
		TRACEABILITY_STATUS="FAIL"
		TRACEABILITY_DETAILS="Missing in PRD: ${missing[*]}"
		log_warn "PRD traceability: FAIL (missing: ${missing[*]})"
	fi

	export TRACEABILITY_STATUS TRACEABILITY_DETAILS
	[[ ${#missing[@]} -eq 0 ]]
}

# ── Worktree creation ────────────────────────────────────────────────────
create_worktree() {
	local branch_name="feat/${EPIC_SLUG}/${ISSUE_SLUG}"

	# Check if worktree already exists for this branch
	local existing_worktree
	existing_worktree=$(git worktree list | grep "$branch_name" | awk '{print $1}' | head -1 || true)

	if [[ -n "$existing_worktree" ]]; then
		log_info "Worktree already exists for branch $branch_name at $existing_worktree"
		WORKTREE_PATH="$existing_worktree"
		BRANCH_NAME="$branch_name"
		export WORKTREE_PATH BRANCH_NAME
		# Trust mise config in the existing worktree (idempotent)
		if command -v mise >/dev/null 2>&1; then
			(cd "$WORKTREE_PATH" && mise trust 2>/dev/null || true)
		fi
		return 0
	fi

	# Check if branch exists on remote — this is a strong signal the issue
	# was already claimed and a worktree exists elsewhere.
	if git fetch origin "$branch_name" 2>/dev/null; then
		log_err "Branch $branch_name already exists on remote (origin/$branch_name) — issue likely already claimed"
		return 1
	fi

	# Check if branch already exists locally
	if git rev-parse --verify "$branch_name" >/dev/null 2>&1; then
		log_info "Branch $branch_name already exists locally"
		BRANCH_NAME="$branch_name"
	else
		# Create branch from the latest main
		log_info "Creating branch $branch_name from origin/main"
		git fetch origin main 2>/dev/null || true
		if git rev-parse --verify origin/main >/dev/null 2>&1; then
			git branch "$branch_name" origin/main
		else
			git branch "$branch_name" main 2>/dev/null || git branch "$branch_name" HEAD
		fi
		BRANCH_NAME="$branch_name"
	fi

	# Create the worktree
	local worktree_dir="${REPO_ROOT}/.worktrees/${branch_name}"
	mkdir -p "$(dirname "$worktree_dir")" 2>/dev/null || true

	if ! git worktree add "$worktree_dir" "$BRANCH_NAME" 2>/dev/null; then
		log_err "Failed to create worktree at $worktree_dir"
		return 1
	fi

	WORKTREE_PATH="$worktree_dir"
	export WORKTREE_PATH BRANCH_NAME
	log_ok "Worktree created at $WORKTREE_PATH on branch $BRANCH_NAME"

	# Trust mise config in the new worktree
	if command -v mise >/dev/null 2>&1; then
		(cd "$WORKTREE_PATH" && mise trust 2>/dev/null || true)
	fi

	return 0
}

# ── Issue ledger claim ───────────────────────────────────────────────────
claim_issue() {
	if [[ -z "$WORKTREE_PATH" ]]; then
		log_err "No worktree path available for claim"
		return 1
	fi

	# Double-check the issue hasn't been completed since resolve_issue ran.
	# This catches race conditions or stale ledger state.
	local issues_file="$SPECS_DIR/issues.jsonl"
	local already_done
	already_done=$(jq -R 'fromjson' "$issues_file" 2>/dev/null |
		jq -s --arg id "$ISSUE_ID" '
	    [.[] | select(.issue_id == $id and (.type | not) and .status == "COMPLETED")]
	    | last
	')
	if [[ -n "$already_done" && "$already_done" != "null" ]]; then
		log_err "Issue $ISSUE_ID was already COMPLETED — refusing to claim"
		return 1
	fi

	# Record the claim using the standard event-log convention:
	# {"issue_id": "...", "status": "CLAIMED", "worker_id": "...", "timestamp": "..."}
	local timestamp
	timestamp=$(date -u +%Y-%m-%dT%H:%M:%SZ)
	local claim_entry
	claim_entry=$(jq -n \
		--arg issue_id "$ISSUE_ID" \
		--arg status "CLAIMED" \
		--arg worker_id "${USER:-unknown}@$(hostname)" \
		--arg timestamp "$timestamp" \
		'{
	    issue_id: $issue_id,
	    status: $status,
	    worker_id: $worker_id,
	    timestamp: $timestamp
	}')

	# Append claim to ledger (appended to existing JSONL in the worktree source)
	echo "$claim_entry" >>"$issues_file" 2>/dev/null || {
		log_err "Failed to write claim to ledger"
		return 1
	}

	log_ok "Issue $ISSUE_ID claimed on branch $BRANCH_NAME"
	return 0
}

# ── Constitution path resolution ─────────────────────────────────────────
resolve_constitution() {
	CONSTITUTION_PATH="$SPECS_DIR/constitution.md"
	if [[ ! -f "$CONSTITUTION_PATH" ]]; then
		log_warn "Constitution not found at $CONSTITUTION_PATH"
		CONSTITUTION_PATH=""
	fi
	export CONSTITUTION_PATH
}

# ── Spec target path ─────────────────────────────────────────────────────
resolve_spec_target() {
	local spec_dir="$WORKTREE_PATH/specs/$EPIC_SLUG"
	SPEC_TARGET="$spec_dir/$ISSUE_SLUG/spec.md"
	if [[ "$DRY_RUN" != "true" ]]; then
		mkdir -p "$(dirname "$SPEC_TARGET")" 2>/dev/null || true
	fi

	# Relative from worktree root
	SPEC_TARGET_RELATIVE="specs/$EPIC_SLUG/$ISSUE_SLUG/spec.md"
	export SPEC_TARGET SPEC_TARGET_RELATIVE
}

# ── Pre subcommand ───────────────────────────────────────────────────────
cmd_pre() {
	log_info "Deviate-specify pre-phase starting..."

	validate_required_tools
	validate_repo
	log_ok "Repository validated: $REPO_ROOT"

	discover_specs_dir || {
		log_err "Specs directory not found"
		emit_json_contract \
			"status" "FAILURE" \
			"phase" "specify" \
			"reason" "NO_SPECS_DIR" \
		exit 2
	}
	log_ok "Specs directory: $SPECS_DIR"

	discover_epic || {
		log_err "No epic directory found in specs/"
		emit_json_contract \
			"status" "FAILURE" \
			"phase" "specify" \
			"reason" "NO_EPIC" \
		exit 3
	}
	log_ok "Epic: $EPIC_SLUG"

	resolve_issue || {
		log_err "Issue resolution failed"
		emit_json_contract \
			"status" "FAILURE" \
			"phase" "specify" \
			"reason" "ISSUE_RESOLUTION_FAILED" \
		exit 3
	}
	log_ok "Issue: $ISSUE_ID ($ISSUE_TITLE)"

	# shellcheck disable=SC2119  # Uses global ISSUE_SOURCE_FILE, not positional params
	read_issue_body
	parse_issue_source
	log_ok "Issue slug: $ISSUE_SLUG"

	resolve_prd_path
	resolve_constitution

	validate_prd_traceability || true # Non-fatal — surface in contract

	if [[ "$DRY_RUN" == "true" ]]; then
		log_info "Dry-run mode — skipping worktree creation and ledger claim"
		WORKTREE_PATH="$REPO_ROOT"
		BRANCH_NAME="feat/${EPIC_SLUG}/${ISSUE_SLUG}"
	else
		create_worktree || {
			log_err "Worktree creation failed"
			emit_json_contract \
				"status" "FAILURE" \
				"phase" "specify" \
				"reason" "WORKTREE_CREATION_FAILED" \
			exit 4
		}
		log_ok "Worktree path: $WORKTREE_PATH"

		if claim_issue; then
			log_ok "Issue claimed on branch $BRANCH_NAME"

			# Commit the claim and push to remote so other sessions
			# detect the branch and refuse to claim the same issue.
			(cd "$WORKTREE_PATH" &&
				git add "specs/issues.jsonl" 2>/dev/null &&
				git commit --no-verify -m "chore: claim $ISSUE_ID" 2>/dev/null) ||
				log_warn "Failed to commit claim to ledger — continuing locally"

			if command -v gh >/dev/null 2>&1; then
				(cd "$WORKTREE_PATH" &&
					git push origin "$BRANCH_NAME" 2>/dev/null) ||
					log_warn "Failed to push claim branch to remote — continuing locally"
			fi
		else
			log_warn "Ledger claim failed — continuing (non-fatal)"
		fi
	fi

	resolve_spec_target
	log_ok "Spec target: $SPEC_TARGET"
	log_ok "Spec target (relative): $SPEC_TARGET_RELATIVE"

	# Extract PRD requirements as JSON array
	local prd_requirements="[]"
	if [[ -n "$PRD_PATH" ]] && command -v jq >/dev/null 2>&1; then
		prd_requirements=$(grep -oE 'FR-[0-9]+[-_]?[0-9]*' "$PRD_PATH" |
			sort -u |
			jq -R -s 'split("\n") | map(select(length > 0))')
	fi

	# Constitution test and lint commands
	local constitution_test_command=""
	local constitution_lint_command=""
	if [[ -f "$CONSTITUTION_PATH" ]]; then
		constitution_test_command=$(grep -E '^\s*\*\*Test\*\*|^\[Test\]' "$CONSTITUTION_PATH" | head -1 | sed 's/^\s*\*\*Test\*\*\s*:\s*//' | sed 's/^\[Test\]\s*:\s*//' || true)
		constitution_lint_command=$(grep -E '^\s*\*\*Lint\*\*|^\[Lint\]' "$CONSTITUTION_PATH" | head -1 | sed 's/^\s*\*\*Lint\*\*\s*:\s*//' | sed 's/^\[Lint\]\s*:\s*//' || true)
	fi

	local git_branch
	git_branch=$(cd "$WORKTREE_PATH" && git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "$BRANCH_NAME")

	local git_state
	git_state=$(cd "$WORKTREE_PATH" && gather_git_state 2>/dev/null || echo '{}')

	# Build JSON contract
	local contract_json
	contract_json=$(jq -n \
		--arg status "READY" \
		--arg phase "specify" \
		--arg issue_id "$ISSUE_ID" \
		--arg issue_title "$ISSUE_TITLE" \
		--arg issue_body "$ISSUE_BODY" \
		--arg epic_slug "$EPIC_SLUG" \
		--arg epic_id "$EPIC_ID" \
		--arg issue_slug "$ISSUE_SLUG" \
		--arg branch_name "$BRANCH_NAME" \
		--arg worktree_full "$WORKTREE_PATH" \
		--arg spec_target "$SPEC_TARGET_RELATIVE" \
		--arg spec_target_abs "$SPEC_TARGET" \
		--arg prd_requirements "$prd_requirements" \
		--arg traceability_status "$TRACEABILITY_STATUS" \
		--arg traceability_details "$TRACEABILITY_DETAILS" \
		--arg constitution_path "$CONSTITUTION_PATH" \
		--arg constitution_test_command "$constitution_test_command" \
		--arg constitution_lint_command "$constitution_lint_command" \
		--arg repo_root "$REPO_ROOT" \
		--arg git_branch "$git_branch" \
		--argjson git_state "$git_state" \
		--arg timestamp "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
		'{
	    status: $status,
	    phase: $phase,
	    issue_id: $issue_id,
	    issue_title: $issue_title,
	    issue_body: $issue_body,
	    epic_slug: $epic_slug,
	    epic_id: $epic_id,
	    issue_slug: $issue_slug,
	    branch_name: $branch_name,
	    worktree_full: $worktree_full,
	    spec_target: $spec_target,
	    spec_target_abs: $spec_target_abs,
	    prd_requirements: $prd_requirements,
	    traceability_status: $traceability_status,
	    traceability_details: $traceability_details,
	    constitution_path: $constitution_path,
	    constitution_test_command: $constitution_test_command,
	    constitution_lint_command: $constitution_lint_command,
	    repo_root: $repo_root,
	    git_branch: $git_branch,
	    git_state: $git_state,
	    timestamp: $timestamp
	}')

	printf '%s\n' "$contract_json"
	log_ok "Pre-phase complete. Worktree: $WORKTREE_PATH"
}

# ── Validate spec.md content ─────────────────────────────────────────────
validate_spec_content() {
	local spec_file="$1"

	if [[ ! -f "$spec_file" ]]; then
		log_err "spec.md not found at $spec_file"
		return 1
	fi

	# Check required section headers
	extract_spec_sections "$spec_file" \
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
	log_ok "All required sections present"

	# Check Gherkin syntax
	local content
	content=$(cat "$spec_file")
	local gherkin_valid=true
	if ! validate_gherkin_syntax "$content"; then
		gherkin_valid=false
	fi

	if [[ $GHERKIN_SCENARIO_COUNT -eq 0 ]]; then
		log_err "No Gherkin Given/When/Then blocks found in spec.md"
		return 1
	else
		log_ok "Found $GHERKIN_SCENARIO_COUNT Gherkin scenarios"
	fi

	if [[ "$gherkin_valid" != "true" ]]; then
		log_err "Malformed Gherkin blocks detected:"
		while IFS= read -r line; do
			[[ -z "$line" ]] && continue
			log_err "  $line"
		done <<<"$GHERKIN_MISSING_CLAUSES"
		return 1
	fi

	# Check FR traceability in spec
	local spec_frs
	spec_frs=$(grep -oE 'FR-[0-9]+[-_]?[0-9]*' "$spec_file" | sort -u || true)

	if [[ -z "$spec_frs" ]]; then
		log_warn "No FR references found in spec.md"
	else
		log_ok "FR references in spec: $(echo "$spec_frs" | tr '\n' ' ')"
	fi

	return 0
}

# ── Update ledger after commit ───────────────────────────────────────────
update_ledger() {
	local issues_file="$SPECS_DIR/issues.jsonl"
	local entry
	entry=$(jq -c -n \
		--arg operation "specify_complete" \
		--arg issue_id "$ISSUE_ID" \
		--arg spec_path "$SPEC_TARGET_RELATIVE" \
		--arg completed_at "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
		--arg next_phase "tasks" \
		'{
	    operation: $operation,
	    issue_id: $issue_id,
	    spec_path: $spec_path,
	    completed_at: $completed_at,
	    next_phase: $next_phase
	}')

	echo "$entry" >>"$issues_file" 2>/dev/null || {
		log_warn "Failed to update ledger (non-fatal)"
		return 1
	}
	log_ok "Ledger updated: specify_complete for $ISSUE_ID"
	return 0
}

# ── Post subcommand ──────────────────────────────────────────────────────
cmd_post() {
	log_info "Deviate-specify post-phase starting..."
	log_info "  force_mode: $FORCE_MODE"

	validate_required_tools
	validate_repo
	log_ok "Repository validated: $REPO_ROOT"

	discover_specs_dir || true
	discover_epic || true

	# REPO_ROOT from find_repo_root already resolves to the correct
	# worktree root (it detects [ -f "$dir/.git" ] which exists in worktrees).
	# Do NOT use git worktree list | head -1 — that always picks the main repo.
	WORKTREE_PATH="$REPO_ROOT"

	log_info "Using worktree path: $WORKTREE_PATH"

	# Derive spec_target from worktree state
	# If we can locate spec.md in the worktree, use it
	local potential_specs
	potential_specs=$(find "$WORKTREE_PATH/specs/$EPIC_SLUG" -maxdepth 3 -name "spec.md" 2>/dev/null || true)
	if [[ -z "$potential_specs" ]]; then
		log_err "No spec.md found in worktree"
		echo '{"status":"FAILURE","reason":"SPEC_NOT_FOUND"}'
		exit 5
	fi

	local spec_file
	spec_file=$(echo "$potential_specs" | head -1)
	SPEC_TARGET="$spec_file"
	SPEC_TARGET_RELATIVE="${spec_file#"$WORKTREE_PATH"/}"
	log_ok "spec.md found: $SPEC_TARGET"

	# Validate spec content
	if ! validate_spec_content "$SPEC_TARGET"; then
		if [[ "$FORCE_MODE" == "true" ]]; then
			log_warn "Validation failed but --force is set — proceeding with commit"
		else
			log_err "spec.md validation failed. Use --force to bypass."
			echo '{"status":"FAILURE","reason":"SPEC_VALIDATION_FAILED","spec_path":"'"$SPEC_TARGET"'"}'
			exit 5
		fi
	fi

	# Extract issue_id from spec if not already set
	if [[ -z "${ISSUE_ID:-}" ]]; then
		ISSUE_ID=$(grep -E "^\|.*ISSUE_ID.*\|" "$SPEC_TARGET" | head -1 | awk -F'|' '{print $3}' | tr -d ' ' || echo "unknown")
	fi

	# Extract numeric issue number for commit scope (ISS-005 → 005)
	ISSUE_NUM=$(echo "$ISSUE_ID" | grep -oE '[0-9]+$' || echo "$ISSUE_ID")

	cd "$WORKTREE_PATH"

	# Stage the spec file
	log_info "Staging spec.md..."
	git add "$SPEC_TARGET_RELATIVE" 2>/dev/null || {
		log_err "Failed to stage spec.md"
		echo '{"status":"FAILURE","reason":"STAGE_FAILED"}'
		exit 6
	}

	# Also stage the worktree specs/ directory and ledger
	git add "specs/" 2>/dev/null || true

	# Run pre-commit hooks if present
	if [[ -f "$WORKTREE_PATH/.pre-commit-config.yaml" ]] && command -v pre-commit >/dev/null 2>&1; then
		log_info "Running pre-commit hooks..."
		git diff --staged --name-only | xargs pre-commit run --files 2>/dev/null || true
		git add "$SPEC_TARGET_RELATIVE" 2>/dev/null || true
		git add "specs/" 2>/dev/null || true
	fi

	# Commit
	local commit_subject="docs(${EPIC_ID}-${ISSUE_NUM}): add spec for ${ISSUE_ID:-unknown}"
	log_info "Committing with: $commit_subject"
	if git commit --no-verify -m "$commit_subject" 2>/dev/null; then
		local commit_sha
		commit_sha=$(git rev-parse --short HEAD)
		log_ok "Committed: $commit_sha"

		# Update ledger
		update_ledger || true

		emit_json_contract \
			"status" "SUCCESS" \
			"phase" "specify" \
			"issue_id" "$ISSUE_ID" \
			"commit_sha" "$commit_sha" \
			"spec_path" "$SPEC_TARGET_RELATIVE" \
			"next_action" "Run /deviate-tasks to create task decomposition" \
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
