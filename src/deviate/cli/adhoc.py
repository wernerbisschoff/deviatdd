from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import typer

from deviate.cli._common import console
from deviate.core.complexity import ClassificationResult, ComplexityGate
from deviate.core.treesitter import extract_file_structure
from deviate.state.ledger import AdhocRecord

adhoc_app = typer.Typer(no_args_is_help=True)

_DEFAULT_SCAN_DIR = "src"
_CODEBASE_STRUCTURE_FILE = "specs/adhoc/codebase_structure.md"


def _adhoc_ledger_path() -> Path:
    return Path.cwd() / "specs" / "adhoc.jsonl"


def _read_adhoc_ledger(path: Path) -> dict[str, dict]:
    if not path.exists():
        return {}
    records: dict[str, dict] = {}
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
                if isinstance(rec, dict):
                    issue_id = rec.get("issue_id")
                    if issue_id:
                        records[issue_id] = rec
            except json.JSONDecodeError:
                continue
    return records


def _emit_contract(status: str, **fields: object) -> None:
    contract: dict[str, object] = {"status": status, **fields}
    print(json.dumps(contract, indent=2))


def _scan_directory_for_python_files(scan_dir: Path) -> list[Path]:
    if not scan_dir.is_dir():
        console.print(
            f"[yellow]CODEBASE_STRUCTURE_SKIP[/] Scan directory not found: {scan_dir}"
        )
        return []
    return sorted(scan_dir.rglob("*.py"))


def _format_function_signature(name: str, info: dict[str, object]) -> str:
    params = ", ".join(info.get("params", []))
    ret = info.get("return_type")
    sig = f"{name}({params})"
    if ret:
        sig += f" -> {ret}"
    return sig


def _format_structure_lines(structure: dict[str, object]) -> list[str]:
    lines: list[str] = []
    imports = structure.get("imports", [])
    if imports:
        lines.append("Imports:\n")
        if isinstance(imports, list):
            for imp in imports:
                lines.append(f"- `{imp}`\n")
    functions = structure.get("functions", {})
    if functions and isinstance(functions, dict):
        lines.append("Functions:\n")
        for name, info in functions.items():
            lines.append(f"- `{_format_function_signature(name, info)}`\n")
    classes = structure.get("classes", {})
    if classes and isinstance(classes, dict):
        lines.append("Classes:\n")
        for name, info in classes.items():
            methods = info.get("methods", {})
            if methods and isinstance(methods, dict):
                lines.append(f"- `{name}`:\n")
                for mname, minfo in methods.items():
                    lines.append(f"  - `{_format_function_signature(mname, minfo)}`\n")
            else:
                lines.append(f"- `{name}`\n")
    return lines


def _build_codebase_structure_artifact(
    scan_dir: Path, output_path: Path
) -> Path | None:
    py_files = _scan_directory_for_python_files(scan_dir)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if not py_files:
        output_path.write_text("## Codebase Structure\n\n", encoding="utf-8")
        return output_path

    lines: list[str] = ["## Codebase Structure\n"]
    for filepath in py_files:
        try:
            content = filepath.read_text(encoding="utf-8")
            structure = extract_file_structure(content)
        except Exception:
            console.print(
                f"[yellow]CODEBASE_STRUCTURE_SKIP[/] Could not parse: {filepath}"
            )
            continue
        rel_path = filepath.relative_to(Path.cwd())
        lines.append(f"### {rel_path}\n")
        lines.extend(_format_structure_lines(structure))
        lines.append("\n")

    output_path.write_text("".join(lines), encoding="utf-8")
    return output_path


@adhoc_app.command()
def pre(
    description: str = typer.Argument(..., help="Task description to classify"),
    skip_gates: bool = typer.Option(
        False,
        "--skip-gates",
        help="Skip complexity gate rejection for HIGH complexity tasks",
    ),
    scan_dir: str = typer.Option(
        _DEFAULT_SCAN_DIR,
        "--scan-dir",
        help="Directory to scan for Python file structure",
    ),
) -> None:
    """Classify an ad-hoc task description and record it for execution."""
    result: ClassificationResult = ComplexityGate.classify(description)

    if result.level == "HIGH" and not skip_gates:
        console.print(
            "[red]COMPLEXITY_GATE_REJECTION[/] HIGH complexity tasks require "
            "--skip-gates to proceed"
        )
        raise typer.Exit(code=1)

    artifact_path = _build_codebase_structure_artifact(
        Path.cwd() / scan_dir, Path.cwd() / _CODEBASE_STRUCTURE_FILE
    )

    record = AdhocRecord(
        issue_id=f"adhoc-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}",
        description=description,
        execution_mode=result.execution_mode,
        status="PENDING",
    )

    ledger_path = _adhoc_ledger_path()
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    with ledger_path.open("a", encoding="utf-8") as f:
        f.write(record.model_dump_json() + "\n")

    contract_fields: dict[str, object] = {
        "execution_mode": result.execution_mode,
        "description": description,
        "issue_id": record.issue_id,
    }
    if artifact_path is not None:
        contract_fields["codebase_structure_path"] = str(artifact_path)
    console.print(
        f"[green]{result.execution_mode}[/] execution_mode={result.execution_mode}"
    )
    _emit_contract(status="READY", **contract_fields)


@adhoc_app.command()
def post(
    issue_id: str = typer.Argument(..., help="Issue/manifest ID to mark complete"),
) -> None:
    """Mark an ad-hoc record as completed."""
    ledger_path = _adhoc_ledger_path()
    records = _read_adhoc_ledger(ledger_path)

    found = records.get(issue_id)

    if found is None:
        console.print(
            f"[red]MANIFEST_NOT_FOUND[/] No record found with issue_id={issue_id}"
        )
        raise typer.Exit(code=1)

    completed = found.copy()
    completed["status"] = "COMPLETED"
    completed["timestamp"] = datetime.now(timezone.utc).isoformat()

    with ledger_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(completed) + "\n")

    console.print(f"[green]COMPLETED[/] {issue_id}")
    _emit_contract(status="COMPLETED", issue_id=issue_id)
