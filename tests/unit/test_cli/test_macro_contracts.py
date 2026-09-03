from __future__ import annotations

import json
import os
import subprocess
from contextlib import chdir
from pathlib import Path

from typer.testing import CliRunner

from deviate.cli import cli
from tests.prd_fixture import MINIMAL_VALID_PRD

runner = CliRunner()


def _git_env() -> dict[str, str]:
    return {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}


class TestMacroContracts:
    EXPLORE_REQUIRED_FIELDS = frozenset(
        {
            "repo_root",
            "git_branch",
            "constitution_path",
            "test_cmd",
            "lint_cmd",
            "type_check_cmd",
            "epic_id",
            "is_greenfield",
            "timestamp",
            "status",
            "phase",
            "issue_id",
            "feature_bucket",
            "feature_dir",
            "explore_path",
        }
    )

    RESEARCH_REQUIRED_FIELDS = frozenset(
        {
            "repo_root",
            "git_branch",
            "constitution_path",
            "test_cmd",
            "lint_cmd",
            "type_check_cmd",
            "is_greenfield",
            "timestamp",
            "status",
            "phase",
            "issue_id",
            "feature_bucket",
            "explore_path",
            "design_target",
            "data_model_target",
        }
    )

    PRD_REQUIRED_FIELDS = frozenset(
        {
            "repo_root",
            "git_branch",
            "constitution_path",
            "test_cmd",
            "lint_cmd",
            "type_check_cmd",
            "timestamp",
            "status",
            "phase",
            "issue_id",
            "feature_bucket",
            "design_path",
            "data_model_path",
            "explore_md_path",
            "plan_target",
        }
    )

    SHARD_REQUIRED_FIELDS = frozenset(
        {
            "repo_root",
            "git_branch",
            "constitution_path",
            "issues_dir",
            "plan_target",
            "dry_run",
            "timestamp",
            "status",
            "phase",
            "issue_id",
            "prd_path",
            "shard_count",
        }
    )

    @staticmethod
    def _setup_git_repo(path: Path) -> None:
        subprocess.run(
            ["git", "init"], cwd=path, env=_git_env(), check=True, capture_output=True
        )
        subprocess.run(
            ["git", "config", "user.email", "runner@test.local"],
            cwd=path,
            env=_git_env(),
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Test Runner"],
            cwd=path,
            env=_git_env(),
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "commit", "--allow-empty", "-m", "initial"],
            cwd=path,
            env=_git_env(),
            check=True,
            capture_output=True,
        )

    @staticmethod
    def _setup_minimal_env(
        path: Path, session_phase: str = "IDLE", *, with_constitution: bool = True
    ) -> None:
        dot_dir = path / ".deviate"
        dot_dir.mkdir(parents=True, exist_ok=True)
        session_data = {"current_phase": session_phase}
        (dot_dir / "session.json").write_text(json.dumps(session_data))
        if not with_constitution:
            return

        specs_dir = path / "specs"
        specs_dir.mkdir(parents=True, exist_ok=True)
        constitution = (
            "# Project Constitution\n\n"
            "## [TESTING_PROTOCOLS]\n"
            "- `TEST_COMMAND`: pytest\n"
            "- `LINT_COMMAND`: ruff check .\n"
            "- `TYPE_CHECK_COMMAND`: (none)\n"
        )
        (specs_dir / "constitution.md").write_text(constitution)

    @staticmethod
    def _extract_contract(output: str) -> dict:
        start = output.index("{")
        end = output.rindex("}") + 1
        return json.loads(output[start:end])

    def test_explore_pre_contract_has_all_fields(self, tmp_path: Path) -> None:
        with chdir(tmp_path):
            self._setup_git_repo(tmp_path)
            self._setup_minimal_env(tmp_path, session_phase="IDLE")

            result = runner.invoke(
                cli, ["explore", "pre", "test problem", "--slug", "test-feature"]
            )
            assert result.exit_code == 0, result.output

            contract = self._extract_contract(result.output)

            for field in sorted(self.EXPLORE_REQUIRED_FIELDS):
                assert field in contract, (
                    f"Missing field in explore pre contract: {field!r}"
                )

    def test_research_pre_contract_has_all_fields(self, tmp_path: Path) -> None:
        with chdir(tmp_path):
            self._setup_git_repo(tmp_path)
            self._setup_minimal_env(tmp_path, session_phase="EXPLORE")

            explore_dir = tmp_path / "specs" / "explore"
            explore_dir.mkdir(parents=True, exist_ok=True)
            (explore_dir / "test-feature.md").write_text(
                "# Explore\n\nDiscovered facts.\n"
            )

            result = runner.invoke(cli, ["research", "pre", "--slug", "test-feature"])
            assert result.exit_code == 0, result.output

            contract = self._extract_contract(result.output)

            for field in sorted(self.RESEARCH_REQUIRED_FIELDS):
                assert field in contract, (
                    f"Missing field in research pre contract: {field!r}"
                )

    def test_prd_pre_contract_has_all_fields(self, tmp_path: Path) -> None:
        with chdir(tmp_path):
            self._setup_git_repo(tmp_path)
            self._setup_minimal_env(tmp_path, session_phase="RESEARCH")

            epic_dir = tmp_path / "specs" / "test-epic"
            epic_dir.mkdir(parents=True, exist_ok=True)
            (epic_dir / "explore.md").write_text("# Explore\n\nFacts.\n")
            (epic_dir / "design.md").write_text("# Design\n\nDesign details.\n")
            (epic_dir / "data-model.md").write_text("# Data Model\n\nSchema details.\n")

            result = runner.invoke(cli, ["prd", "pre"])
            assert result.exit_code == 0, result.output

            contract = self._extract_contract(result.output)

            for field in sorted(self.PRD_REQUIRED_FIELDS):
                assert field in contract, (
                    f"Missing field in prd pre contract: {field!r}"
                )

    def test_shard_pre_contract_has_all_fields(self, tmp_path: Path) -> None:
        with chdir(tmp_path):
            self._setup_git_repo(tmp_path)
            self._setup_minimal_env(tmp_path, session_phase="PRD")

            epic_dir = tmp_path / "specs" / "test-epic"
            epic_dir.mkdir(parents=True, exist_ok=True)
            (epic_dir / "explore.md").write_text("# Explore\n\nFacts.\n")
            (epic_dir / "design.md").write_text("# Design\n\nDesign details.\n")
            (epic_dir / "data-model.md").write_text("# Data Model\n\nSchema details.\n")
            (epic_dir / "prd.md").write_text(MINIMAL_VALID_PRD)

            result = runner.invoke(cli, ["shard", "pre"])
            assert result.exit_code == 0, result.output

            contract = self._extract_contract(result.output)

            for field in sorted(self.SHARD_REQUIRED_FIELDS):
                assert field in contract, (
                    f"Missing field in shard pre contract: {field!r}"
                )

    def test_shard_pre_emits_per_epic_next_issue_id(self, tmp_path: Path) -> None:
        """``shard pre``: ``next_issue_id`` in the contract is per-epic
        format (``002-001``) when the active epic has a numeric prefix.
        Commit 2's RED pin — wires the caller at
        ``cli/macro.py:828`` to pass ``epic_slug`` into
        ``_compute_next_issue_id``. Today the caller passes nothing, so
        the function falls back to the legacy ``ISS-001`` global
        counter; after the GREEN this test pins ``002-001``."""
        with chdir(tmp_path):
            self._setup_git_repo(tmp_path)
            self._setup_minimal_env(tmp_path, session_phase="PRD")

            # Seed a numbered epic bucket with all the artifacts ``shard pre``
            # expects, and an empty issues ledger so the next id is the
            # epic's first ordinal.
            bucket = "002-embedder-vector-search"
            epic_dir = tmp_path / "specs" / bucket
            epic_dir.mkdir(parents=True, exist_ok=True)
            (epic_dir / "explore.md").write_text("# Explore\n\nFacts.\n")
            (epic_dir / "design.md").write_text("# Design\n\nDesign details.\n")
            (epic_dir / "data-model.md").write_text("# Data Model\n\nSchema details.\n")
            (epic_dir / "prd.md").write_text(MINIMAL_VALID_PRD)
            ledger_path = tmp_path / "specs" / "issues.jsonl"
            ledger_path.parent.mkdir(parents=True, exist_ok=True)
            ledger_path.write_text("")

            result = runner.invoke(cli, ["shard", "pre"])
            assert result.exit_code == 0, result.output

            contract = self._extract_contract(result.output)
            assert contract["next_issue_id"] == "002-001"

    def test_prd_pre_dry_run_does_not_create_artifacts(self, tmp_path: Path) -> None:
        with chdir(tmp_path):
            self._setup_git_repo(tmp_path)
            self._setup_minimal_env(tmp_path, session_phase="RESEARCH")

            epic_dir = tmp_path / "specs" / "test-epic"
            epic_dir.mkdir(parents=True, exist_ok=True)
            (epic_dir / "explore.md").write_text("# Explore\n\nFacts.\n")
            (epic_dir / "design.md").write_text("# Design\n\nDesign details.\n")
            (epic_dir / "data-model.md").write_text("# Data Model\n\nSchema details.\n")

            session_path = tmp_path / ".deviate" / "session.json"
            before = json.loads(session_path.read_text())
            assert before["current_phase"] == "RESEARCH"

            result = runner.invoke(cli, ["prd", "pre", "--dry-run"])

            assert result.exit_code == 0, result.output

            session_after = json.loads(session_path.read_text())
            assert session_after["current_phase"] == "RESEARCH"

    def test_shard_pre_dry_run_does_not_create_issues(self, tmp_path: Path) -> None:
        with chdir(tmp_path):
            self._setup_git_repo(tmp_path)
            self._setup_minimal_env(tmp_path, session_phase="PRD")

            epic_dir = tmp_path / "specs" / "test-epic"
            epic_dir.mkdir(parents=True, exist_ok=True)
            (epic_dir / "explore.md").write_text("# Explore\n\nFacts.\n")
            (epic_dir / "design.md").write_text("# Design\n\nDesign details.\n")
            (epic_dir / "data-model.md").write_text("# Data Model\n\nSchema details.\n")
            (epic_dir / "prd.md").write_text(MINIMAL_VALID_PRD)

            ledger_path = tmp_path / "specs" / "issues.jsonl"
            (tmp_path / "specs").mkdir(parents=True, exist_ok=True)
            ledger_path.write_text("")

            result = runner.invoke(cli, ["shard", "pre", "--dry-run"])

            assert result.exit_code == 0, result.output

            assert ledger_path.read_text() == ""

    def test_explore_pre_reports_greenfield_when_constitution_missing(
        self, tmp_path: Path
    ) -> None:
        """explore pre derives is_greenfield from constitution presence.

        A fresh repo (no specs/constitution.md) reports ``is_greenfield=True``.
        explore does NOT bootstrap the constitution — that's research pre's job.
        """
        with chdir(tmp_path):
            self._setup_git_repo(tmp_path)
            self._setup_minimal_env(
                tmp_path, session_phase="IDLE", with_constitution=False
            )

            result = runner.invoke(
                cli, ["explore", "pre", "test problem", "--slug", "test-feature"]
            )
            assert result.exit_code == 0, result.output

            contract = self._extract_contract(result.output)
            assert contract["is_greenfield"] is True
            assert contract["constitution_path"] == ""

            # Constitution is still absent — explore must not bootstrap it.
            assert not (tmp_path / "specs" / "constitution.md").exists()

    def test_research_pre_bootstraps_constitution_when_missing(
        self, tmp_path: Path
    ) -> None:
        """research pre scaffolds specs/constitution.md when absent.

        The contract is emitted AFTER the bootstrap, so the scaffolded
        path is visible in ``constitution_path`` and ``is_greenfield``
        reflects the post-bootstrap state (False).
        """
        with chdir(tmp_path):
            self._setup_git_repo(tmp_path)
            self._setup_minimal_env(
                tmp_path, session_phase="EXPLORE", with_constitution=False
            )

            explore_dir = tmp_path / "specs" / "explore"
            explore_dir.mkdir(parents=True, exist_ok=True)
            (explore_dir / "test-feature.md").write_text(
                "# Explore\n\nDiscovered facts.\n"
            )

            result = runner.invoke(cli, ["research", "pre", "--slug", "test-feature"])
            assert result.exit_code == 0, result.output

            # Bootstrap fired.
            const_path = tmp_path / "specs" / "constitution.md"
            assert const_path.exists()

            contract = self._extract_contract(result.output)
            assert contract["is_greenfield"] is False
            assert contract["constitution_path"].endswith("specs/constitution.md")

    # ------------------------------------------------------------------
    # Per-epic issue-id labels (Commit 1 — RED).
    #
    # _compute_next_issue_id(epic_slug) now emits a per-epic compound label
    # (``002-001``, ``adhoc-001``) when the epic slug has a numeric prefix;
    # otherwise it falls back to the legacy ``ISS-NNN`` global counter so
    # adhoc and bootstrap callers keep working. Legacy ``ISS-NNN`` rows in
    # ``specs/issues.jsonl`` resolve through ``resolve_issue_record`` as
    # before — the resolve layer is grandfathered.
    # ------------------------------------------------------------------

    @staticmethod
    def _seed_issue_ledger(
        repo: Path,
        rows: list[dict],
    ) -> Path:
        ledger = repo / "specs" / "issues.jsonl"
        ledger.parent.mkdir(parents=True, exist_ok=True)
        with ledger.open("w", encoding="utf-8") as f:
            for r in rows:
                f.write(json.dumps(r) + "\n")
        return ledger

    @staticmethod
    def _ledger_row(
        issue_id: str,
        bucket: str,
        slug: str,
        status: str = "SPECIFIED",
    ) -> dict:
        return {
            "issue_id": issue_id,
            "type": "feature",
            "title": f"test {issue_id}",
            "status": status,
            "source_file": f"specs/{bucket}/issues/{slug}.md",
            "blocked_by": [],
            "coordinates_with": [],
            "timestamp": "2026-07-30T00:00:00Z",
            "created_at": "2026-07-30T00:00:00Z",
        }

    def test_compute_next_issue_id_emits_per_epic_label_for_empty_ledger(
        self, tmp_path: Path
    ) -> None:
        """``_compute_next_issue_id``: numeric epic, empty ledger → ``002-001``."""
        from deviate.cli.macro import _compute_next_issue_id

        ledger = tmp_path / "specs" / "issues.jsonl"
        ledger.parent.mkdir(parents=True, exist_ok=True)
        ledger.write_text("")

        next_id = _compute_next_issue_id(ledger, epic_slug="002-embedder-vector-search")
        assert next_id == "002-001"

    def test_compute_next_issue_id_monotonicity_within_epic(
        self, tmp_path: Path
    ) -> None:
        """``_compute_next_issue_id``: per-epic ordinal monotonicity across
        format boundaries.

        Two seeded rows in epic 002 and one in epic 001:
        - ``ISS-001`` (epic 001) — must NOT influence epic 002's ordinal.
        - ``002-001`` (epic 002, new format) — counts toward ordinal.
        - ``ISS-019`` (epic 002, legacy format, same bucket) — counts
          toward ordinal under interpretation #2. Next id is ``002-020``,
          not ``002-002`` — legacy ``ISS-NNN`` rows from the same epic
          contribute their numeric value to the per-epic ordinal.
        """
        from deviate.cli.macro import _compute_next_issue_id

        ledger = self._seed_issue_ledger(
            tmp_path,
            [
                # Legacy row from a *different* epic — must NOT influence
                # epic 002's per-epic ordinal.
                self._ledger_row(
                    "ISS-001", bucket="001-gloss-v1-mvp", slug="001-cargo-init"
                ),
                # Already-sharded issue in the target epic (new format).
                self._ledger_row(
                    "002-001",
                    bucket="002-embedder-vector-search",
                    slug="001-embedder-registry",
                ),
                # Legacy row from the *same* epic — DOES count under
                # interpretation #2. Next ordinal must be 19+1 = 20.
                self._ledger_row(
                    "ISS-019",
                    bucket="002-embedder-vector-search",
                    slug="019-legacy-embedder-something",
                ),
            ],
        )

        next_id = _compute_next_issue_id(ledger, epic_slug="002-embedder-vector-search")
        assert next_id == "002-020"

    def test_compute_next_issue_id_falls_back_to_legacy_for_adhoc(
        self, tmp_path: Path
    ) -> None:
        """``_compute_next_issue_id``: adhoc bucket (no numeric prefix) →
        legacy ``ISS-NNN`` global counter. Adhoc issue generation is
        unchanged from the pre-per-epic behavior."""
        from deviate.cli.macro import _compute_next_issue_id

        ledger = self._seed_issue_ledger(
            tmp_path,
            [
                self._ledger_row(
                    "ISS-018", bucket="001-gloss-v1-mvp", slug="018-anything"
                ),
            ],
        )

        next_id = _compute_next_issue_id(ledger, epic_slug="adhoc")
        assert next_id == "ISS-019"

    def test_compute_next_issue_id_falls_back_for_empty_epic_slug(
        self, tmp_path: Path
    ) -> None:
        """``_compute_next_issue_id``: empty ``epic_slug`` (e.g. fresh repo
        with no numbered epic and no adhoc bucket yet) → legacy
        ``ISS-001``. Defensive fallback so callers never see a malformed id
        like ``0-001``."""
        from deviate.cli.macro import _compute_next_issue_id

        ledger = self._seed_issue_ledger(tmp_path, [])

        next_id = _compute_next_issue_id(ledger, epic_slug="")
        assert next_id == "ISS-001"

    def test_resolve_issue_record_grandfathers_legacy_iss_ids(
        self, tmp_path: Path
    ) -> None:
        """``resolve_issue_record``: legacy ``ISS-019`` row continues to
        resolve after the per-epic label change. Cross-function grandfather
        pin — the resolve layer must continue to find old ids even after
        ``_compute_next_issue_id`` starts emitting ``002-001``-style
        labels for new issues."""
        from deviate.state.ledger import resolve_issue_record

        legacy_row = self._ledger_row(
            "ISS-019",
            bucket="002-embedder-vector-search",
            slug="001-embedder-registry",
            status="COMPLETED",
        )
        new_row = self._ledger_row(
            "002-001",
            bucket="002-embedder-vector-search",
            slug="002-project-config-extensions",
        )
        ledger = self._seed_issue_ledger(tmp_path, [legacy_row, new_row])

        resolved = resolve_issue_record("ISS-019", ledger)
        assert resolved is not None
        assert resolved.issue_id == "ISS-019"
        assert resolved.source_file == legacy_row["source_file"]
        assert resolved.status == "COMPLETED"


def _seed_origin_feat_ref(repo: Path, feat_suffix: str) -> None:
    """Point an already-fetched origin feat ref at HEAD (no network)."""
    subprocess.run(
        [
            "git",
            "update-ref",
            f"refs/remotes/origin/feat/{feat_suffix}",
            "HEAD",
        ],
        cwd=repo,
        env=_git_env(),
        check=True,
        capture_output=True,
    )


def _adhoc_ordinal(issue_id: str) -> int:
    """Last numeric segment of ``ISS-018`` or ``ISS-ADH-018``."""
    assert issue_id.startswith("ISS-")
    return int(issue_id.rsplit("-", 1)[-1])


def _next_adhoc_id(ledger: Path, repo: Path) -> str:
    from deviate.cli.macro import _compute_next_issue_id

    with chdir(repo):
        return _compute_next_issue_id(ledger, epic_slug="adhoc")


class TestComputeNextIssueIdRemoteAware:
    """AC-PLAN-001 / AC-PLAN-004: adhoc next-id is remote-aware, one series."""

    def test_remote_feat_adhoc_017_allocates_018_when_local_ledger_has_no_017(
        self, tmp_git_repo: Path
    ) -> None:
        _seed_origin_feat_ref(tmp_git_repo, "adhoc/017-two-counter-tdd-retry")
        _seed_origin_feat_ref(tmp_git_repo, "adhoc/017-optional-push-as-lock")
        ledger = TestMacroContracts._seed_issue_ledger(tmp_git_repo, [])

        next_id = _next_adhoc_id(ledger, tmp_git_repo)

        assert _adhoc_ordinal(next_id) == 18

    def test_iss_adh_017_and_iss_017_share_one_adhoc_series(
        self, tmp_git_repo: Path
    ) -> None:
        ledger = TestMacroContracts._seed_issue_ledger(
            tmp_git_repo,
            [
                TestMacroContracts._ledger_row(
                    "ISS-ADH-017",
                    bucket="adhoc",
                    slug="017-two-counter-tdd-retry",
                ),
            ],
        )

        next_id = _next_adhoc_id(ledger, tmp_git_repo)

        assert _adhoc_ordinal(next_id) == 18

    def test_origin_main_ledger_ordinal_counts_when_working_copy_ledger_is_empty(
        self, tmp_git_repo: Path
    ) -> None:
        ledger = TestMacroContracts._seed_issue_ledger(
            tmp_git_repo,
            [
                TestMacroContracts._ledger_row(
                    "ISS-ADH-017",
                    bucket="adhoc",
                    slug="017-origin-ledger-row",
                ),
            ],
        )
        subprocess.run(
            ["git", "add", "specs/issues.jsonl"],
            cwd=tmp_git_repo,
            env=_git_env(),
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "commit", "-m", "origin ledger"],
            cwd=tmp_git_repo,
            env=_git_env(),
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "update-ref", "refs/remotes/origin/main", "HEAD"],
            cwd=tmp_git_repo,
            env=_git_env(),
            check=True,
            capture_output=True,
        )
        ledger.write_text("")

        next_id = _next_adhoc_id(ledger, tmp_git_repo)

        assert _adhoc_ordinal(next_id) == 18

    def test_local_only_feat_adhoc_019_does_not_reserve_019(
        self, tmp_git_repo: Path
    ) -> None:
        _seed_origin_feat_ref(tmp_git_repo, "adhoc/018-claimed-on-origin")
        subprocess.run(
            ["git", "branch", "feat/adhoc/019-local-only"],
            cwd=tmp_git_repo,
            env=_git_env(),
            check=True,
            capture_output=True,
        )
        ledger = TestMacroContracts._seed_issue_ledger(tmp_git_repo, [])

        next_id = _next_adhoc_id(ledger, tmp_git_repo)

        assert _adhoc_ordinal(next_id) == 19
