"""Scripted TDD-cycle driver — replay a wild handover without an LLM.

Two invocation styles, same payloads:

* **Auto** — ``_run_tdd_cycle`` / ``_run_*_phase``. Patch the agent-invoke
  seam (``_invoke_agent``), not ``_run_*_phase``. ``_apply_judge_verdict``
  stays real. Auto does **not** call ``deviate <phase> pre|post``.
  Test-command / format / pytest subprocesses are stubbed so the host
  suite is never re-entered.
* **Manual** — ``deviate red|green|judge|refactor pre`` → write scripted
  files → ``deviate <phase> post``. The handover YAML is parsed the same
  way production parses agent stdout (``AgentBackend.parse_output``).

Do not stub ``_run_red_phase`` / ``_run_green_phase`` / ``_run_judge_phase``
/ ``_run_refactor_phase``. Cycle regressions belong in fixtures here, not
new ``_coerce_judge_action`` branches only.

No network, no live LLM, no real consumer pytest.
"""

from __future__ import annotations

import io
import json
import subprocess
from collections.abc import Mapping, Sequence
from contextlib import chdir
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from rich.console import Console
from typer.testing import CliRunner

from deviate.cli import cli
from deviate.cli.micro import (
    PhaseFailedError,
    _AgentInvokeResult,
    _run_tdd_cycle,
)
from deviate.core.agent import AgentBackend, HandoverManifest
from deviate.state.config import SessionState
from deviate.state.ledger import TaskRecord
from tests.conftest import _git_env

CycleMode = Literal["auto", "manual"]

_ISSUE_ID = "ISS-160-001"
_FEATURE = "160-cycle-driver"
_ISSUE_SLUG = "001-scripted-cycle"


def _task_slug(task_id: str) -> str:
    return task_id.replace("-", "_").lower()


def _test_rel(task_id: str) -> str:
    return f"tests/test_{_task_slug(task_id)}.py"


def _impl_rel(task_id: str) -> str:
    return f"src/{_task_slug(task_id)}.py"


def _test_quote(task_id: str) -> str:
    return f'assert cycle_feature() == "{task_id}"'


def _impl_quote(task_id: str) -> str:
    return f'return "{task_id}"'


def _test_body(task_id: str) -> str:
    return (
        f"from {_task_slug(task_id)} import cycle_feature\n\n"
        "def test_cycle_feature() -> None:\n"
        f"    {_test_quote(task_id)}\n"
    )


def _impl_body(task_id: str) -> str:
    return f"def cycle_feature() -> str:\n    {_impl_quote(task_id)}\n"


_REFACTOR_NOTE = (
    "REFACTOR NOTE: The root layout is implemented as a function "
    "component rather than a separate template file."
)
_STALE_EVIDENCE = [
    {
        "ac": "AC-PLAN-099",
        "test_path": "test/stale_route_test.exs",
        "test_quote": 'assert live(conn, ~p"/")',
        "impl_path": "lib/stale.ex",
        "impl_quote": "use Phoenix.LiveView, layout: {Layouts, :app}",
    }
]

_runner = CliRunner()


@dataclass(frozen=True, slots=True)
class CycleTask:
    """One PENDING (or later) task seeded into the cycle repo."""

    task_id: str
    description: str
    ac: str = ""
    status: str = "PENDING"


@dataclass(frozen=True, slots=True)
class CycleStep:
    """One scripted phase: handover plus optional files to write."""

    phase: str
    handover: str | HandoverManifest | None = None
    files: Mapping[str, str] | None = None
    test_returncode: int | None = None


@dataclass
class CycleResult:
    """Recorded auto/manual cycle outcome for assertions."""

    mode: CycleMode
    phases: list[str] = field(default_factory=list)
    decisions: list[dict[str, object]] = field(default_factory=list)
    prompts: dict[str, list[str]] = field(default_factory=dict)
    output: str = ""
    error: BaseException | None = None
    session: SessionState | None = None
    ledger_path: Path | None = None
    cycle_ends: list[dict[str, object]] = field(default_factory=list)
    loop_events: list[dict[str, object]] = field(default_factory=list)

    @property
    def ledger_statuses(self) -> list[str]:
        if self.ledger_path is None or not self.ledger_path.exists():
            return []
        return ledger_statuses(self.ledger_path)

    def statuses_for(self, task_id: str) -> list[str]:
        if self.ledger_path is None or not self.ledger_path.exists():
            return []
        return ledger_statuses(self.ledger_path, task_id=task_id)


@dataclass
class SeededCycle:
    """Seeded tmp repo ready for ``run_scripted_cycle``."""

    root: Path
    ledger_path: Path
    tasks: list[dict[str, str]]
    issue_id: str

    def task(self, task_id: str | None = None) -> dict[str, str]:
        if task_id is None:
            return self.tasks[0]
        for item in self.tasks:
            if item["id"] == task_id:
                return item
        raise KeyError(task_id)


def ledger_statuses(path: Path, *, task_id: str | None = None) -> list[str]:
    """Return append-only status tokens from a tasks.jsonl ledger."""
    statuses: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if task_id is not None and row.get("id") != task_id:
            continue
        statuses.append(str(row.get("status", "")))
    return statuses


def load_session(root: Path) -> SessionState:
    return SessionState.load(root / ".deviate" / "session.json")


def red_files(task_id: str) -> dict[str, str]:
    return {_test_rel(task_id): _test_body(task_id)}


def green_files(task_id: str) -> dict[str, str]:
    return {_impl_rel(task_id): _impl_body(task_id)}


def _handover_yaml(
    *,
    phase: str,
    task_id: str,
    status: str = "PASS",
    extra: str = "",
) -> str:
    body = f"phase: {phase}\nstatus: {status}\ntask_id: {task_id}\n"
    if extra:
        body += extra if extra.endswith("\n") else extra + "\n"
    return body


def red_handover_yaml(task_id: str) -> str:
    return _handover_yaml(
        phase="RED",
        task_id=task_id,
        extra=f"test_file: {_test_rel(task_id)}\n",
    )


def green_handover_yaml(task_id: str) -> str:
    return _handover_yaml(phase="GREEN", task_id=task_id)


def refactor_handover_yaml(task_id: str) -> str:
    return _handover_yaml(phase="REFACTOR", task_id=task_id)


def judge_pass_yaml(
    task_id: str,
    *,
    ac: str,
    next_action: str | None = None,
    train_feedback: str = "COMPLIANCE_PASS: No correctness issues.\n",
    verdict: str = "COMPLIANCE_PASS",
) -> str:
    """JUDGE handover YAML parsed through ``AgentBackend.parse_output``."""
    action_line = f"next_action: {next_action}\n" if next_action is not None else ""
    feedback = (
        train_feedback if train_feedback.endswith("\n") else train_feedback + "\n"
    )
    return (
        "phase: JUDGE\n"
        "status: PASS\n"
        f"task_id: {task_id}\n"
        f'verdict: "{verdict}"\n'
        f"{action_line}"
        "train_feedback: |\n"
        + "".join(f"  {line}\n" for line in feedback.splitlines())
        + "evidence:\n"
        f"  - ac: {ac}\n"
        f"    test_path: {_test_rel(task_id)}\n"
        f"    test_quote: {_test_quote(task_id)!r}\n"
        f"    impl_path: {_impl_rel(task_id)}\n"
        f"    impl_quote: {_impl_quote(task_id)!r}\n"
    )


def verdicts_path(root: Path, issue_id: str, task_id: str) -> Path:
    """Per-task JUDGE postmortem file (not the transcript ``.log``)."""
    return root / ".deviate" / "logs" / issue_id / f"{task_id}.verdicts.jsonl"


def load_verdicts(root: Path, issue_id: str, task_id: str) -> list[dict[str, object]]:
    """Parse ``.verdicts.jsonl`` as one JSON object per non-empty line."""
    path = verdicts_path(root, issue_id, task_id)
    if not path.exists():
        return []
    records: list[dict[str, object]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        records.append(json.loads(line))
    return records


def judge_fail_yaml(
    task_id: str,
    *,
    next_action: str = "revert_green",
    verdict: str = "COMPLIANCE_FAIL",
    train_feedback: str = (
        "COMPLIANCE_FAIL: spec gap. The next GREEN attempt must: "
        "implement the missing error path.\n"
    ),
) -> str:
    """JUDGE reject handover (COMPLIANCE_FAIL / revert_green by default)."""
    action_line = f"next_action: {next_action}\n"
    feedback = (
        train_feedback if train_feedback.endswith("\n") else train_feedback + "\n"
    )
    return (
        "phase: JUDGE\n"
        "status: FAIL\n"
        f"task_id: {task_id}\n"
        f'verdict: "{verdict}"\n'
        f"{action_line}"
        "train_feedback: |\n" + "".join(f"  {line}\n" for line in feedback.splitlines())
    )


def judge_revert_green_yaml(
    task_id: str,
    *,
    feedback: str = "implementation misses the RED contract",
) -> str:
    """JUDGE ``COMPLIANCE_VIOLATION`` + ``revert_green`` (TRAIN GREEN)."""
    body = feedback if feedback.endswith("\n") else feedback + "\n"
    return (
        "phase: JUDGE\n"
        "status: SUCCESS\n"
        f"task_id: {task_id}\n"
        'verdict: "COMPLIANCE_VIOLATION"\n'
        "next_action: revert_green\n"
        "train_feedback: |\n" + "".join(f"  {line}\n" for line in body.splitlines())
    )


def judge_pass_plus_note_yaml(
    task_id: str,
    *,
    ac: str,
    next_action: str = "revert_red",
) -> str:
    """GH-158 payload: clean pass + REFACTOR NOTE + leftover revert."""
    feedback = f"COMPLIANCE_PASS: No correctness issues.\n\n{_REFACTOR_NOTE}\n"
    return judge_pass_yaml(
        task_id,
        ac=ac,
        next_action=next_action,
        train_feedback=feedback,
    )


def happy_path_steps(task_id: str, *, ac: str) -> list[CycleStep]:
    """RED fail + GREEN pass + JUDGE COMPLIANCE_PASS (no note) + REFACTOR."""
    return [
        CycleStep(
            phase="RED", handover=red_handover_yaml(task_id), files=red_files(task_id)
        ),
        CycleStep(
            phase="GREEN",
            handover=green_handover_yaml(task_id),
            files=green_files(task_id),
        ),
        CycleStep(
            phase="JUDGE",
            handover=judge_pass_yaml(task_id, ac=ac),
        ),
        CycleStep(phase="REFACTOR", handover=refactor_handover_yaml(task_id)),
    ]


def gh158_steps(
    task_id: str,
    *,
    ac: str,
    next_action: str = "revert_red",
) -> list[CycleStep]:
    """Full cycle whose JUDGE payload is the GH-158 pass+note revert."""
    return [
        CycleStep(
            phase="RED", handover=red_handover_yaml(task_id), files=red_files(task_id)
        ),
        CycleStep(
            phase="GREEN",
            handover=green_handover_yaml(task_id),
            files=green_files(task_id),
        ),
        CycleStep(
            phase="JUDGE",
            handover=judge_pass_plus_note_yaml(task_id, ac=ac, next_action=next_action),
        ),
        CycleStep(phase="REFACTOR", handover=refactor_handover_yaml(task_id)),
    ]


def reject_then_pass_steps(task_id: str, *, ac: str) -> list[CycleStep]:
    """RED + GREEN + JUDGE reject (revert_green) + GREEN train + pass + REFACTOR."""
    return [
        CycleStep(
            phase="RED", handover=red_handover_yaml(task_id), files=red_files(task_id)
        ),
        CycleStep(
            phase="GREEN",
            handover=green_handover_yaml(task_id),
            files=green_files(task_id),
        ),
        CycleStep(phase="JUDGE", handover=judge_fail_yaml(task_id)),
        CycleStep(
            phase="GREEN",
            handover=green_handover_yaml(task_id),
            files=green_files(task_id),
        ),
        CycleStep(
            phase="JUDGE",
            handover=judge_pass_yaml(task_id, ac=ac, next_action="continue_refactor"),
        ),
        CycleStep(phase="REFACTOR", handover=refactor_handover_yaml(task_id)),
    ]


def two_revert_green_then_pass_steps(task_id: str, *, ac: str) -> list[CycleStep]:
    """Two consecutive ``revert_green`` JUDGE rejects, then pass + REFACTOR."""
    return [
        CycleStep(
            phase="RED", handover=red_handover_yaml(task_id), files=red_files(task_id)
        ),
        CycleStep(
            phase="GREEN",
            handover=green_handover_yaml(task_id),
            files=green_files(task_id),
        ),
        CycleStep(phase="JUDGE", handover=judge_fail_yaml(task_id)),
        CycleStep(
            phase="GREEN",
            handover=green_handover_yaml(task_id),
            files=green_files(task_id),
        ),
        CycleStep(phase="JUDGE", handover=judge_fail_yaml(task_id)),
        CycleStep(
            phase="GREEN",
            handover=green_handover_yaml(task_id),
            files=green_files(task_id),
        ),
        CycleStep(
            phase="JUDGE",
            handover=judge_pass_yaml(task_id, ac=ac, next_action="continue_refactor"),
        ),
        CycleStep(phase="REFACTOR", handover=refactor_handover_yaml(task_id)),
    ]


def skip_refactor_steps(task_id: str, *, ac: str) -> list[CycleStep]:
    """Complete a task via JUDGE ``skip_refactor`` (no REFACTOR phase)."""
    return [
        CycleStep(
            phase="RED", handover=red_handover_yaml(task_id), files=red_files(task_id)
        ),
        CycleStep(
            phase="GREEN",
            handover=green_handover_yaml(task_id),
            files=green_files(task_id),
        ),
        CycleStep(
            phase="JUDGE",
            handover=judge_pass_yaml(task_id, ac=ac, next_action="skip_refactor"),
        ),
    ]


def _write_files(root: Path, files: Mapping[str, str] | None) -> None:
    if not files:
        return
    for rel, body in files.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body, encoding="utf-8")


def _parse_handover(
    handover: str | HandoverManifest | None, phase: str
) -> HandoverManifest:
    if handover is None:
        raise AssertionError(f"scripted {phase} step has no handover")
    if isinstance(handover, HandoverManifest):
        return handover
    return AgentBackend.parse_output(handover, "cli")


def _write_ledger(path: Path, *records: TaskRecord) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        for record in records:
            handle.write(record.model_dump_json() + "\n")


def seed_cycle_repo(
    root: Path,
    *,
    tasks: Sequence[CycleTask] | None = None,
    issue_id: str = _ISSUE_ID,
) -> SeededCycle:
    """Seed a tmp git repo + PENDING task(s) + session.json."""
    specs = [
        CycleTask(task_id="TSK-160-01", description="Cycle slice", ac="AC-PLAN-001")
    ]
    if tasks is not None:
        specs = list(tasks)

    source = f"specs/{_FEATURE}/issues/{_ISSUE_SLUG}.md"
    issue_md = root / source
    issue_md.parent.mkdir(parents=True, exist_ok=True)
    issue_md.write_text("# Scripted TDD cycle driver\n", encoding="utf-8")

    workspace = root / "specs" / _FEATURE / _ISSUE_SLUG
    workspace.mkdir(parents=True, exist_ok=True)
    cards = ["# Tasks\n"]
    for spec in specs:
        cards.append(f"- [ ] {spec.task_id}: {spec.description}\n")
        if spec.ac:
            cards.append(f"  - **Acceptance Criteria**: {spec.ac}\n")
        cards.append("  - **Verification**: pytest\n")
    (workspace / "tasks.md").write_text("".join(cards), encoding="utf-8")
    (workspace / "plan.md").write_text(
        "## Acceptance Contract\n\nNo extra plan tokens beyond the task cards.\n",
        encoding="utf-8",
    )
    (root / "specs" / "issues.jsonl").write_text(
        json.dumps({"issue_id": issue_id, "source_file": source}) + "\n",
        encoding="utf-8",
    )
    (root / "specs" / "constitution.md").write_text(
        "# constitution\n", encoding="utf-8"
    )
    (root / ".gitignore").write_text(".deviate/\n", encoding="utf-8")
    (root / "pyproject.toml").write_text(
        '[project]\nname = "cycle-driver-seed"\nversion = "0.0.0"\n',
        encoding="utf-8",
    )
    (root / "src").mkdir(parents=True, exist_ok=True)
    (root / "src" / "__init__.py").write_text("", encoding="utf-8")

    ledger_path = workspace / "tasks.jsonl"
    task_dicts: list[dict[str, str]] = []
    records: list[TaskRecord] = []
    for spec in specs:
        records.append(
            TaskRecord(
                id=spec.task_id,
                issue_id=issue_id,
                description=spec.description,
                status=spec.status,  # type: ignore[arg-type]
                execution_mode="TDD",
            )
        )
        task_dicts.append(
            {
                "id": spec.task_id,
                "issue_id": issue_id,
                "description": spec.description,
                "status": spec.status,
                "execution_mode": "TDD",
            }
        )
    _write_ledger(ledger_path, *records)

    # Parent ~/.gitconfig may set core.hooksPath or commit.gpgsign; a
    # hook or gpg wait would blow the <30s budget. Keep commits real.
    for key, value in (
        ("core.hooksPath", "/dev/null"),
        ("commit.gpgsign", "false"),
        ("tag.gpgsign", "false"),
    ):
        subprocess.run(
            ["git", "config", key, value],
            cwd=root,
            env=_git_env(),
            check=True,
        )
    subprocess.run(["git", "add", "."], cwd=root, env=_git_env(), check=True)
    subprocess.run(
        ["git", "commit", "-m", "chore: seed cycle-driver meso artifacts"],
        cwd=root,
        env=_git_env(),
        check=True,
    )

    session_path = root / ".deviate" / "session.json"
    session_path.parent.mkdir(parents=True, exist_ok=True)
    SessionState(current_phase="IDLE", active_issue_id=issue_id).save(session_path)
    return SeededCycle(
        root=root,
        ledger_path=ledger_path,
        tasks=task_dicts,
        issue_id=issue_id,
    )


def poison_stale_skip_refactor(
    root: Path,
    *,
    prior_task_id: str,
    pending: str = "skip_refactor",
    evidence: list[dict[str, object]] | None = None,
) -> None:
    """Leave a previous task's forward route in session.json (GH-148)."""
    session_path = root / ".deviate" / "session.json"
    session = SessionState.load(session_path)
    session.pending_judge_action = pending
    session.last_judge_verdict = "COMPLIANCE_PASS"
    session.validated_evidence = list(
        evidence if evidence is not None else _STALE_EVIDENCE
    )
    session.judge_task_id = prior_task_id
    session.judge_red_commit_sha = session.red_commit_sha
    session.current_phase = "IDLE"
    session.save(session_path)


def _install_common_patches(
    monkeypatch: object,
    *,
    remaining: list[CycleStep],
    current_phase: dict[str, str],
    decisions: list[dict[str, object]],
    cycle_ends: list[dict[str, object]] | None = None,
    loop_events: list[dict[str, object]] | None = None,
) -> None:
    import deviate.cli.micro as micro

    real_log = micro._log_run

    def capturing_log(event: str, **kwargs: object) -> None:
        if event == "PHASE_DECISION":
            decisions.append({"event": event, **kwargs})
        if event == "CYCLE_END" and cycle_ends is not None:
            cycle_ends.append({"event": event, **kwargs})
        if event == "LOOP_DETECTED" and loop_events is not None:
            loop_events.append({"event": event, **kwargs})
        real_log(event, **kwargs)

    def fake_test_cmd(
        *_args: object, **_kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        step_code = None
        phase = current_phase.get("name", "")
        for step in remaining:
            if step.phase.upper() == phase.upper() and step.test_returncode is not None:
                step_code = step.test_returncode
                break
        if step_code is None:
            step_code = 1 if phase.upper() == "RED" else 0
        stdout = "1 failed" if step_code else "1 passed"
        return subprocess.CompletedProcess(
            args=[], returncode=step_code, stdout=stdout, stderr=""
        )

    monkeypatch.setattr("deviate.cli.micro._log_run", capturing_log)
    monkeypatch.setattr("deviate.cli.micro._run_test_cmd", fake_test_cmd)
    monkeypatch.setattr(
        "deviate.cli.micro._run_pytest",
        lambda *_a, **_k: subprocess.CompletedProcess(
            args=[], returncode=0, stdout="1 passed", stderr=""
        ),
    )
    monkeypatch.setattr(
        "deviate.cli.micro._run_format_cmd",
        lambda *_a, **_k: subprocess.CompletedProcess(
            args=[], returncode=0, stdout="", stderr=""
        ),
    )
    monkeypatch.setattr(
        "deviate.cli.micro._verify_worktree_branch", lambda *_a, **_k: None
    )
    real_commit = micro._commit_phase

    def commit_without_hooks(
        message: str,
        root: Path,
        no_verify: bool = False,
        phase: str | None = None,
        *,
        task_id: str | None = None,
    ) -> bool:
        del no_verify
        return real_commit(message, root, no_verify=True, phase=phase, task_id=task_id)

    monkeypatch.setattr("deviate.cli.micro._commit_phase", commit_without_hooks)


def _take_step(remaining: list[CycleStep], phase: str) -> CycleStep:
    needle = phase.upper()
    for index, step in enumerate(remaining):
        if step.phase.upper() == needle:
            return remaining.pop(index)
    raise AssertionError(
        f"cycle driver: no scripted step for phase {phase!r}; leftover={remaining!r}"
    )


def run_auto_cycle(
    seeded: SeededCycle,
    steps: Sequence[CycleStep],
    monkeypatch: object,
    *,
    task_id: str | None = None,
    start_phase: str | None = None,
    no_refactor: bool = False,
) -> CycleResult:
    """Drive ``_run_tdd_cycle`` with a scripted ``_invoke_agent`` seam."""
    remaining = list(steps)
    current_phase = {"name": start_phase or "RED"}
    decisions: list[dict[str, object]] = []
    cycle_ends: list[dict[str, object]] = []
    loop_events: list[dict[str, object]] = []
    phases: list[str] = []
    prompts: dict[str, list[str]] = {}
    _install_common_patches(
        monkeypatch,
        remaining=remaining,
        current_phase=current_phase,
        decisions=decisions,
        cycle_ends=cycle_ends,
        loop_events=loop_events,
    )

    def fake_invoke(
        prompt: str,
        _console: object,
        backend_name: str = "pi",
        task_id: str = "",
        phase: str = "",
        output_callback: object = None,
        model: str | None = None,
        stall_timeout: int | None = None,
    ) -> _AgentInvokeResult:
        del backend_name, task_id, output_callback, model, stall_timeout
        label = (phase or "").upper() or "UNKNOWN"
        current_phase["name"] = label
        phases.append(label)
        prompts.setdefault(label, []).append(prompt)
        step = _take_step(remaining, label)
        _write_files(seeded.root, step.files)
        manifest = _parse_handover(step.handover, label)
        return _AgentInvokeResult(manifest, "")

    monkeypatch.setattr("deviate.cli.micro._invoke_agent", fake_invoke)

    buf = io.StringIO()
    console = Console(file=buf, force_terminal=False, width=200)
    error: BaseException | None = None
    task = seeded.task(task_id)
    with chdir(seeded.root):
        try:
            _run_tdd_cycle(
                task,
                seeded.ledger_path,
                console,
                start_phase=start_phase,
                no_refactor=no_refactor,
            )
        except PhaseFailedError as exc:
            error = exc
            buf.write(f"\n{exc}\n")
    return CycleResult(
        mode="auto",
        phases=phases,
        decisions=decisions,
        prompts=prompts,
        output=buf.getvalue(),
        error=error,
        session=load_session(seeded.root),
        ledger_path=seeded.ledger_path,
        cycle_ends=cycle_ends,
        loop_events=loop_events,
    )


def run_manual_cycle(
    seeded: SeededCycle,
    steps: Sequence[CycleStep],
    monkeypatch: object,
    *,
    task_id: str | None = None,
) -> CycleResult:
    """Drive real ``deviate <phase> pre|post`` with scripted files on disk."""
    remaining = list(steps)
    current_phase = {"name": ""}
    decisions: list[dict[str, object]] = []
    cycle_ends: list[dict[str, object]] = []
    loop_events: list[dict[str, object]] = []
    phases: list[str] = []
    prompts: dict[str, list[str]] = {}
    _install_common_patches(
        monkeypatch,
        remaining=remaining,
        current_phase=current_phase,
        decisions=decisions,
        cycle_ends=cycle_ends,
        loop_events=loop_events,
    )

    task = seeded.task(task_id)
    tid = task["id"]
    chunks: list[str] = []
    error: BaseException | None = None

    with chdir(seeded.root):
        for step in steps:
            label = step.phase.upper()
            current_phase["name"] = label
            phases.append(label)
            pre_args = [label.lower(), "pre"]
            if label in {"RED", "GREEN", "REFACTOR"}:
                pre_args.extend(["--task", tid])
            pre = _runner.invoke(cli, pre_args)
            chunks.append(pre.output)
            if pre.exit_code not in {0, None} and pre.exception:
                error = pre.exception
                break
            if pre.exit_code != 0:
                error = PhaseFailedError(
                    f"manual {label} pre failed ({pre.exit_code}): {pre.output}"
                )
                break
            _write_files(seeded.root, step.files)
            if label == "JUDGE":
                if not isinstance(step.handover, str):
                    raise AssertionError(
                        "manual JUDGE steps must supply handover YAML so "
                        "judge post parses it the same way production does"
                    )
                manifest_path = seeded.root.parent / f"judge-{tid}.yaml"
                manifest_path.write_text(step.handover, encoding="utf-8")
                post = _runner.invoke(
                    cli, ["judge", "post", str(manifest_path), "--yes"]
                )
            elif label == "RED":
                post = _runner.invoke(cli, ["red", "post", "--task-id", tid])
            else:
                post = _runner.invoke(cli, [label.lower(), "post"])
            chunks.append(post.output)
            if post.exception and post.exit_code not in {0, None}:
                error = post.exception
                break
            if post.exit_code != 0:
                error = PhaseFailedError(
                    f"manual {label} post failed ({post.exit_code}): {post.output}"
                )
                break

    return CycleResult(
        mode="manual",
        phases=phases,
        decisions=decisions,
        prompts=prompts,
        output="".join(chunks),
        error=error,
        session=load_session(seeded.root),
        ledger_path=seeded.ledger_path,
        cycle_ends=cycle_ends,
        loop_events=loop_events,
    )


def run_scripted_cycle(
    seeded: SeededCycle,
    steps: Sequence[CycleStep],
    monkeypatch: object,
    *,
    mode: CycleMode,
    task_id: str | None = None,
    start_phase: str | None = None,
    no_refactor: bool = False,
) -> CycleResult:
    """Run the same script on auto or manual. ``no_refactor`` is auto-only."""
    if mode == "auto":
        return run_auto_cycle(
            seeded,
            steps,
            monkeypatch,
            task_id=task_id,
            start_phase=start_phase,
            no_refactor=no_refactor,
        )
    if start_phase or no_refactor:
        raise AssertionError("manual cycle does not accept start_phase/no_refactor")
    return run_manual_cycle(seeded, steps, monkeypatch, task_id=task_id)
