"""Micro phase pending-task discovery helpers (split of the god-file package)."""

from __future__ import annotations

from pathlib import Path

from deviate.core.tasks_ledger import parse_test_strategy, resolve_execution_mode


def _find_all_pending_tasks(
    root: Path, issue_id: str | None = None
) -> list[tuple[dict, Path]]:
    from deviate.cli.micro.surface import (
        _MODE_LINE_RE,
        _TASK_LINE_RE,
        _TERMINAL_STATUSES,
        _TEST_STRATEGY_LINE_RE,
        _TYPE_LINE_RE,
        _collect_latest_task_records,
        _find_tasks_md_for_issue,
        _log,
        _resolve_md_issue_id,
    )

    _log(f"find_all_pending_tasks: issue_id={issue_id}, root={root}")

    latest_by_issue: dict[tuple[str, str], dict] = {}
    ledger_of_by_issue: dict[tuple[str, str], Path] = {}
    for rec, ledger_file in _collect_latest_task_records(root):
        tid = rec["id"]
        rec_issue = rec.get("issue_id", "")
        if not rec_issue:
            continue
        if issue_id is not None and rec_issue != issue_id:
            _log(f"  skipping {tid} from issue {rec_issue} (expected {issue_id})")
            continue
        key = (rec_issue, tid)
        latest_by_issue[key] = rec
        ledger_of_by_issue[key] = ledger_file
        _log(
            f"  ledger record: {tid} ({rec_issue})"
            f" → {rec.get('status')} ({ledger_file.name})"
        )

    seen: set[str] = set()
    results: list[tuple[dict, Path]] = []

    def _process_one_tasks_md(md_path: Path, md_issue_id: str) -> None:
        fallback = md_path.parent / "tasks.jsonl"
        content_lines = md_path.read_text(encoding="utf-8").splitlines()
        for i, line in enumerate(content_lines):
            m = _TASK_LINE_RE.match(line)
            if m is None:
                continue
            tid = m.group(2)
            checkbox = m.group(1)
            _log(f"  tasks.md task: {tid} (issue={md_issue_id})")
            seen.add(tid)
            key = (md_issue_id, tid)
            rec = latest_by_issue.get(key)
            if rec is not None:
                if rec.get("status") in _TERMINAL_STATUSES:
                    _log(f"    → terminal ({rec.get('status')}), skipping")
                    continue
                _log(f"    → status={rec.get('status')}, including")
                results.append((rec, ledger_of_by_issue.get(key, fallback)))
                continue
            if checkbox and checkbox.lower() == "x":
                _log("    → checked [x] in tasks.md, skipping")
                continue
            mode = "TDD"
            task_type: str | None = None
            test_strategy: str | None = None
            for j in range(i + 1, min(i + 12, len(content_lines))):
                type_m = _TYPE_LINE_RE.match(content_lines[j])
                if type_m:
                    task_type = type_m.group(1)
                    continue
                mode_m = _MODE_LINE_RE.match(content_lines[j])
                if mode_m:
                    mode = mode_m.group(1)
                    continue
                strategy_m = _TEST_STRATEGY_LINE_RE.match(content_lines[j])
                if strategy_m:
                    test_strategy = parse_test_strategy(strategy_m.group(1))
            mode = resolve_execution_mode(task_type, mode)
            _log(f"    → no ledger entry, mode={mode}")
            pending: dict[str, str] = {
                "id": tid,
                "issue_id": md_issue_id,
                "description": m.group(3).strip(),
                "status": "PENDING",
                "execution_mode": mode,
            }
            if task_type:
                pending["task_type"] = task_type
            if test_strategy:
                pending["test_strategy"] = test_strategy
            results.append(
                (
                    pending,
                    fallback,
                )
            )

    if issue_id is not None:
        tasks_md = _find_tasks_md_for_issue(root, issue_id)
        _log(f"  tasks_md: {tasks_md}")
        if tasks_md is not None:
            _process_one_tasks_md(tasks_md, issue_id)
        else:
            for fallback_md in sorted(root.glob("specs/**/tasks.md")):
                md_issue_id = _resolve_md_issue_id(fallback_md)
                if md_issue_id and md_issue_id != issue_id:
                    continue
                _process_one_tasks_md(fallback_md, issue_id)
    else:
        for tasks_md in sorted(root.glob("specs/**/tasks.md")):
            md_issue_id = _resolve_md_issue_id(tasks_md)
            _log(f"  tasks_md: {tasks_md} → issue_id={md_issue_id}")
            _process_one_tasks_md(tasks_md, md_issue_id)

    for (rec_issue, tid), rec in latest_by_issue.items():
        if tid in seen:
            continue
        if issue_id is not None and rec_issue != issue_id:
            continue
        if rec.get("status") not in _TERMINAL_STATUSES:
            _log(
                f"  orphan ledger task: {tid} ({rec_issue}"
                f", {rec.get('status')}), including"
            )
            results.append((rec, ledger_of_by_issue[(rec_issue, tid)]))
        else:
            _log(
                f"  orphan ledger task: {tid} ({rec_issue}"
                f", {rec.get('status')}), skipping"
            )

    _log(f"  total pending: {len(results)}")
    return results
