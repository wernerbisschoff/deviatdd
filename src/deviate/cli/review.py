from __future__ import annotations

import json
import logging
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import typer

from deviate.cli._common import console
from deviate.core._shared import git_env as _git_env

logger = logging.getLogger(__name__)

_SOURCE_EXTENSIONS: frozenset[str] = frozenset(
    {
        ".py",
        ".scm",
        ".js",
        ".mjs",
        ".cjs",
        ".ts",
        ".mts",
        ".cts",
        ".tsx",
        ".rs",
        ".go",
        ".cpp",
        ".cc",
        ".cxx",
        ".hpp",
        ".h",
        ".ex",
        ".exs",
        ".cs",
        ".sh",
        ".bash",
        ".zsh",
        ".kt",
        ".kts",
        ".swift",
    }
)


def _is_source_file(filepath: str) -> bool:
    """Check if a filepath corresponds to source code with a meaningful AST."""
    stem, _, ext = filepath.rpartition(".")
    return ("." + ext) in _SOURCE_EXTENSIONS if ext else False


review_app = typer.Typer(no_args_is_help=True)


@review_app.command()
def pre(
    base: str = typer.Option(
        "main", "--base", help="Base branch for merge-base computation"
    ),
    branch: str | None = typer.Option(
        None, "--branch", help="Target branch for self-contained review"
    ),
) -> None:
    """Gather git state and governance context for review."""
    repo = Path.cwd()

    target = branch or "HEAD"
    branch_name = branch or _get_current_branch(repo)

    diff = _compute_diff(repo, base, target)
    entries = _compute_structured_diff(repo, base, target)
    structured_diff_markdown = _format_structured_diff_markdown(entries)
    constitution_path = _resolve_constitution_path(repo)
    prd_path, prd_warning = _resolve_prd(branch_name, repo)
    report_exists = _check_existing_reports(repo)

    contract = {
        "status": "READY",
        "diff": diff,
        "structured_diff": entries,
        "structured_diff_markdown": structured_diff_markdown,
        "constitution_path": constitution_path,
        "constitution_warning": constitution_path is None,
        "prd_path": prd_path,
        "prd_warning": prd_warning,
        "base_branch": base,
        "report_exists": report_exists,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    print(json.dumps(contract, indent=2))


def _get_current_branch(repo: Path) -> str | None:
    """Get current git branch name."""
    try:
        return subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=repo,
            env=_git_env(),
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


def _compute_merge_base(commit_a: str, commit_b: str, repo: Path) -> str:
    """Compute merge base between two commits."""
    try:
        return subprocess.run(
            ["git", "merge-base", commit_a, commit_b],
            cwd=repo,
            env=_git_env(),
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return ""


def _gather_diff(base: str, head: str, repo: Path) -> str:
    """Gather unified diff between base and head commits."""
    try:
        return subprocess.run(
            ["git", "diff", f"{base}..{head}"],
            cwd=repo,
            env=_git_env(),
            capture_output=True,
            text=True,
            check=True,
        ).stdout
    except (subprocess.CalledProcessError, FileNotFoundError):
        return ""


def _compute_diff(repo: Path, base: str = "main", target_branch: str = "HEAD") -> str:
    """Compute unified diff against merge-base with given base branch."""
    merge_base = _compute_merge_base(base, target_branch, repo)
    if not merge_base:
        return ""
    return _gather_diff(merge_base, target_branch, repo)


def _resolve_constitution_path(repo: Path) -> str | None:
    """Resolve specs/constitution.md path if it exists."""
    path = repo / "specs" / "constitution.md"
    if path.exists():
        return str(path.resolve())
    return None


def _resolve_prd(branch_name: str | None, repo: Path) -> tuple[str | None, bool]:
    """Resolve PRD path with epic priority over adhoc fallback."""
    epic_slug = None
    if branch_name:
        parts = branch_name.split("/")
        if len(parts) > 1:
            epic_slug = parts[1]

    if epic_slug:
        epic_prd = repo / "specs" / epic_slug / "prd.md"
        if epic_prd.exists():
            return str(epic_prd.resolve()), False

    adhoc_prd = repo / "specs" / "adhoc" / "prd.md"
    if adhoc_prd.exists():
        return str(adhoc_prd.resolve()), False

    return None, True


def _reports_dir(repo: Path) -> Path:
    """Resolve the .deviate/review/reports/ directory path."""
    return repo / ".deviate" / "review" / "reports"


def _check_existing_reports(repo: Path) -> bool:
    """Check if review reports already exist under .deviate/review/reports/."""
    reports_dir = _reports_dir(repo)
    if not reports_dir.is_dir():
        return False
    return any(reports_dir.iterdir())


def _parse_diff_filepaths(diff_text: str) -> list[str]:
    paths: list[str] = []
    for line in diff_text.splitlines():
        if line.startswith("diff --git"):
            parts = line.split()
            if len(parts) >= 4:
                b_path = parts[-1].lstrip("b/")
                paths.append(b_path)
    return paths


def _compute_file_stats(diff_text: str, target_filepath: str) -> dict:
    """Compute file-level stats: net_lines_changed, chunks_changed, chunks."""
    added = 0
    removed = 0
    chunks = 0
    in_target = False
    for line in diff_text.splitlines():
        if line.startswith("diff --git"):
            parts = line.split()
            b_path = parts[-1].lstrip("b/") if len(parts) >= 4 else ""
            in_target = b_path == target_filepath
            continue
        if not in_target:
            continue
        if line.startswith("@@"):
            chunks += 1
            continue
        if (
            line.startswith("--- ")
            or line.startswith("+++ ")
            or line.startswith("index ")
        ):
            continue
        if line.startswith("new file"):
            continue
        if line.startswith("deleted file"):
            continue
        if line.startswith("+"):
            added += 1
        elif line.startswith("-"):
            removed += 1
    net_str = f"+{added}/-{removed}"
    return {
        "net_lines_changed": net_str,
        "lines_added": added,
        "lines_removed": removed,
        "chunks_changed": chunks,
    }


def _parse_diff_imports(
    diff_text: str, target_filepath: str, extract_imports_fn
) -> dict:
    """Parse added/removed import lines from diff for target filepath."""
    added: list[str] = []
    removed: list[str] = []
    in_target = False
    for line in diff_text.splitlines():
        if line.startswith("diff --git"):
            parts = line.split()
            b_path = parts[-1].lstrip("b/") if len(parts) >= 4 else ""
            in_target = b_path == target_filepath
            continue
        if not in_target:
            continue
        if (
            line.startswith("--- ")
            or line.startswith("+++ ")
            or line.startswith("index ")
        ):
            continue
        if line.startswith("@@"):
            continue
        content = line[1:] if len(line) > 1 else ""
        stripped = content.strip()
        if not stripped:
            continue
        if line.startswith("+"):
            if extract_imports_fn(stripped):
                added.append(stripped)
        elif line.startswith("-"):
            if extract_imports_fn(stripped):
                removed.append(stripped)
    return {"imports_added": added, "imports_removed": removed}


def _is_import_line(line: str) -> bool:
    """Heuristic check if a line looks like an import/include/using directive."""
    lower = line.lower().strip()
    if lower.startswith(
        (
            "import ",
            "from ",
            "using ",
            "include ",
            "#include",
            "use ",
            "extern crate",
            "require(",
            "const ",
        )
    ):
        return True
    if lower.startswith("#") and "include" in lower:
        return True
    return False


def _build_file_entry(
    filepath: str, language: str, symbols_raw, diff_text: str
) -> dict:
    """Build a file entry dict for the structured diff contract."""
    stats = _compute_file_stats(diff_text, filepath)
    entry: dict = {
        "file": filepath,
        "language": language,
        "net_lines_changed": stats["net_lines_changed"],
        "lines_added": stats["lines_added"],
        "lines_removed": stats["lines_removed"],
        "chunks_changed": stats["chunks_changed"],
    }
    symbols_list: list[dict] = []
    for sc in symbols_raw:
        sym: dict[str, str | int] = {
            "k": sc.kind,
            "n": sc.name,
            "c": sc.change,
        }
        if sc.start_line or sc.end_line:
            sym["L"] = f"{sc.start_line}-{sc.end_line}"
        if sc.old_start_line or sc.old_end_line:
            sym["LO"] = f"{sc.old_start_line}-{sc.old_end_line}"
        if sc.old_signature:
            sym["SO"] = sc.old_signature[:80]
        if sc.new_signature:
            sym["SN"] = sc.new_signature[:80]
        if sc.old_line_count or sc.new_line_count:
            sym["S"] = f"{sc.old_line_count}→{sc.new_line_count}"
        symbols_list.append(sym)
    entry["symbols"] = symbols_list
    imports = _parse_diff_imports(diff_text, filepath, _is_import_line)
    if imports["imports_added"] or imports["imports_removed"]:
        entry["+I"] = imports["imports_added"]
        entry["-I"] = imports["imports_removed"]
    return entry


def _format_structured_diff_markdown(entries: list[dict]) -> str:
    """Render structured diff as a compact markdown table — token-efficient for LLM."""
    sections: list[str] = []
    for ent in entries:
        fp = ent["file"]
        lang = ent["language"]
        net = ent["net_lines_changed"]
        lines = [f"### {fp} ({lang}, {net})"]
        syms = ent.get("symbols", [])
        if syms:
            lines.append("| k | n | c | L | LO | S | SO | SN |")
            lines.append("|---|---|---|---|---|---|---|---|")
            for s in syms:
                lines.append(
                    f"| {s.get('k', '-')} "
                    f"| {s.get('n', '-')} "
                    f"| {s.get('c', '-')} "
                    f"| {s.get('L', '-')} "
                    f"| {s.get('LO', '-')} "
                    f"| {s.get('S', '-')} "
                    f"| {s.get('SO', '-')[:40]} "
                    f"| {s.get('SN', '-')[:40]} |"
                )
        added = ent.get("+I", [])
        removed = ent.get("-I", [])
        if added or removed:
            lines.append("")
            if added:
                for imp in added:
                    lines.append(f"+ `{imp}`")
            if removed:
                for imp in removed:
                    lines.append(f"- `{imp}`")
        sections.append("\n".join(lines))
    return "\n\n".join(sections) if sections else "(no source changes)"


def _compute_structured_diff(repo: Path, base: str, target: str) -> list[dict]:
    """Compute structured AST diff entries for ALL changed files.

    Source files get full symbol-level AST diff breakdown.
    Non-source files get empty symbols and ``unknown`` language.
    Returns empty list when no diff or tree-sitter unavailable.
    """
    merge_base = _compute_merge_base(base, target, repo)
    if not merge_base:
        return []

    diff_text = _gather_diff(merge_base, target, repo)
    if not diff_text.strip():
        return []

    try:
        from deviate.core.treesitter import extract_changed_symbols, get_language_id
    except ImportError:
        logger.warning("tree-sitter not available — skipping structured diff")
        return []

    filepaths = _parse_diff_filepaths(diff_text)
    entries: list[dict] = []

    for filepath in filepaths:
        try:
            if _is_source_file(filepath):
                symbols = extract_changed_symbols(diff_text, filepath)
                language = (
                    symbols[0].language
                    if symbols
                    else get_language_id(filepath) or "unknown"
                )
            else:
                symbols = []
                language = "unknown"
            entries.append(_build_file_entry(filepath, language, symbols, diff_text))
        except (LookupError, TypeError, ValueError):
            logger.warning("Failed to compute structured diff for: %s", filepath)

    return entries


@review_app.command()
def post(
    content: str | None = typer.Argument(
        None, help="Report markdown content. If not provided, reads from stdin."
    ),
) -> None:
    """Persist review report and mark review complete."""
    if not content:
        if not sys.stdin.isatty():
            content = sys.stdin.read()

    if not content:
        console.print("[yellow]SKIP[/] no report content provided")
        raise typer.Exit(code=0)

    repo = Path.cwd()
    reports_dir = _reports_dir(repo)
    reports_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    report_file = reports_dir / f"review-report-{timestamp}.md"
    report_file.write_text(content, encoding="utf-8")
    console.print(f"[green]OK[/] report written to {report_file}")
