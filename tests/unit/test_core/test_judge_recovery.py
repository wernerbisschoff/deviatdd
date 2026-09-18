import pytest

from deviate.core.judge_contradiction import detect_judge_requirement_contradiction
from deviate.core.commands import install_command
from deviate.prompts.assembly import load_template


@pytest.mark.behavioral
def test_repeated_database_diagnostics_are_not_conflicting_requirements():
    diagnostic = (
        "mise integration still fails in tests/integration/test_crypto_withdrawal_admission.py "
        "with HTTP 400 and event-loop database errors."
    )
    repair = (
        "The next RED attempt must:\n"
        "- Requirement: AC-PLAN-002 and AC-PLAN-011 require real authenticated HTTP admission, read, and replay behavior.\n"
        "- Evidence: mise integration still fails with HTTP 400 and event-loop database errors before the assertions.\n"
        "- Correction: Repair the integration fixture and application lifecycle setup in tests/integration/test_crypto_withdrawal_admission.py.\n"
        "- Verification: Run mise integration; expect behavioral failures from missing transport behavior, not setup or event-loop errors.\n"
        "- Boundary: Change tests only. Keep the work in tests/integration and preserve legacy routes."
    )
    assert detect_judge_requirement_contradiction([repair, diagnostic], repair) is None


@pytest.mark.behavioral
def test_alternating_independent_repairs_do_not_require_a_spec_decision():
    first = "Requirement: Validate withdrawal amounts.\nCorrection: Reject negative amounts."
    second = "Requirement: Close database sessions.\nCorrection: Dispose the async engine after fixture teardown."
    assert detect_judge_requirement_contradiction([first, second], first) is None


@pytest.mark.behavioral
@pytest.mark.parametrize("mode", ["auto", "manual"])
def test_judge_can_repair_tasks_and_environment_without_weakening_tests(mode, tmp_path):
    if mode == "auto":
        prompt = load_template("judge")
    else:
        install_command("deviate-judge", tmp_path)
        prompt = (tmp_path / "deviate-judge.md").read_text()
    assert "entire active issue's `tasks.md`" in prompt
    assert "mise setup, doctor, reset, and verification commands" in prompt
    assert "Preserve completed-task regression tests" in prompt
    assert "does not `git reset` or edit `tasks.md`" not in prompt


@pytest.mark.behavioral
def test_tasks_template_declares_acceptance_scope_and_red_preserves_prior_tests():
    tasks = load_template("tasks")
    assert "**Acceptance Criteria**:" in tasks
    assert "Do not list excluded suite paths" in tasks
    assert "Preserve completed-task regression tests" in load_template("red")


@pytest.mark.behavioral
def test_judge_repairs_survive_rejection_without_preserving_green(tmp_git_repo):
    import subprocess
    from deviate.core._shared import git_env
    from deviate.core.judge_repairs import (
        snapshot_repairs,
        commit_repairs,
        repair_commits,
        replay_repairs,
    )

    root = tmp_git_repo

    def git(*args):
        return subprocess.run(
            ["git", *args],
            cwd=root,
            env=git_env(),
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()

    tasks = root / "specs/issue/tasks.md"
    tasks.parent.mkdir(parents=True)
    tasks.write_text("- TSK-001-01: admission\n")
    (root / "mise.toml").write_text('[tasks.integration]\nrun = "broken"\n')
    git("add", ".")
    git("commit", "-m", "test: baseline")
    boundary = git("rev-parse", "HEAD")
    (root / "implementation.py").write_text("wrong = True\n")
    git("add", ".")
    git("commit", "-m", "feat: rejected implementation")
    before = snapshot_repairs(root)
    tasks.write_text("- TSK-001-01: repaired admission\n- TSK-001-02: concurrency\n")
    (root / "mise.toml").write_text(
        '[tasks.integration]\nrun = "pytest -m integration"\n'
    )
    script = root / "scripts/setup-local"
    script.parent.mkdir()
    script.write_text("#!/bin/sh\nexit 0\n")
    script.chmod(0o755)
    assert commit_repairs(root, before)
    commits = repair_commits(root, boundary)
    assert len(commits) == 1
    git("reset", "--hard", boundary)
    replay_repairs(root, commits)
    assert "repaired admission" in tasks.read_text()
    assert "TSK-001-02" in tasks.read_text()
    assert "pytest" in (root / "mise.toml").read_text()
    assert script.stat().st_mode & 0o111
    assert not (root / "implementation.py").exists()
    assert not git("status", "--porcelain")


@pytest.mark.behavioral
@pytest.mark.parametrize("mode", ["auto", "manual"])
def test_judge_repairs_survive_the_real_cycle(tmp_git_repo, monkeypatch, mode):
    from dataclasses import replace
    from tests.helpers.cycle_driver import (
        CycleTask,
        seed_cycle_repo,
        reject_then_pass_steps,
        run_scripted_cycle,
    )

    task = CycleTask("TSK-160-01", "Repair local readiness", ac="AC-PLAN-001")
    seeded = seed_cycle_repo(tmp_git_repo, tasks=[task])
    tasks_path = seeded.ledger_path.with_name("tasks.md")
    steps = reject_then_pass_steps(task.task_id, ac=task.ac)
    steps[2] = replace(
        steps[2],
        files={
            str(tasks_path.relative_to(tmp_git_repo)): tasks_path.read_text()
            + "\n## Local readiness\nRun mise setup before integration.\n",
            "scripts/setup-local": "#!/bin/sh\nexit 0\n",
        },
    )
    result = run_scripted_cycle(seeded, steps, monkeypatch, mode=mode)
    assert result.error is None, result.output
    assert result.statuses_for(task.task_id)[-1] == "COMPLETED"
    assert "Run mise setup before integration." in tasks_path.read_text()
    assert (tmp_git_repo / "scripts/setup-local").exists()
