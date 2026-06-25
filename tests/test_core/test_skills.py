from __future__ import annotations

from pathlib import Path

from deviate.core.skills import discover_skills, install_skill, resolve_skill


class TestDiscoverSkills:
    def test_discover_skills_lists_directories(self, tmp_path: Path):
        skills_root = tmp_path / "skills"
        (skills_root / "deviate-specify").mkdir(parents=True)
        (skills_root / "deviate-specify" / "SKILL.md").touch()
        (skills_root / "deviate-red").mkdir(parents=True)
        (skills_root / "deviate-red" / "SKILL.md").touch()
        result = discover_skills(skills_root=skills_root)
        assert "deviate-specify" in result
        assert "deviate-red" in result

    def test_discover_skills_skips_dirs_without_skill_md(self, tmp_path: Path):
        skills_root = tmp_path / "skills"
        (skills_root / "with-skill").mkdir(parents=True)
        (skills_root / "with-skill" / "SKILL.md").touch()
        (skills_root / "without-skill").mkdir(parents=True)
        result = discover_skills(skills_root=skills_root)
        assert "with-skill" in result
        assert "without-skill" not in result


class TestInstallSkillGraphiteRouting:
    """Conditional `## Graphite Routing` section in deviate-pr based on config."""

    @staticmethod
    def _seed_graphite_config(workdir: Path, value: bool | None) -> None:
        dot_dir = workdir / ".deviate"
        dot_dir.mkdir(parents=True, exist_ok=True)
        config_path = dot_dir / "config.toml"
        if value is None:
            config_path.write_text('profile = "default"\n', encoding="utf-8")
        else:
            config_path.write_text(
                f'profile = "default"\ngraphite = {"true" if value else "false"}\n',
                encoding="utf-8",
            )

    def test_install_deviate_pr_appends_graphite_when_configured(self, tmp_path: Path):
        """graphite = true in config → installed skill contains routing section."""
        workdir = tmp_path / "repo"
        workdir.mkdir()
        self._seed_graphite_config(workdir, True)
        target = tmp_path / "agent" / "skills"

        assert install_skill("deviate-pr", target, workdir=workdir) is True
        installed = target / "deviate-pr" / "SKILL.md"
        assert installed.exists()
        content = installed.read_text(encoding="utf-8")
        assert "<graphite_routing>" in content
        assert "gt submit --stack" in content

    def test_install_deviate_pr_omits_graphite_when_unset(self, tmp_path: Path):
        """graphite key absent from config → no routing section emitted."""
        workdir = tmp_path / "repo"
        workdir.mkdir()
        self._seed_graphite_config(workdir, None)
        target = tmp_path / "agent" / "skills"

        install_skill("deviate-pr", target, workdir=workdir)
        installed = target / "deviate-pr" / "SKILL.md"
        assert installed.exists()
        content = installed.read_text(encoding="utf-8")
        assert "<graphite_routing>" not in content

    def test_install_deviate_pr_omits_graphite_when_false(self, tmp_path: Path):
        """graphite = false in config → no routing section emitted."""
        workdir = tmp_path / "repo"
        workdir.mkdir()
        self._seed_graphite_config(workdir, False)
        target = tmp_path / "agent" / "skills"

        install_skill("deviate-pr", target, workdir=workdir)
        content = (target / "deviate-pr" / "SKILL.md").read_text(encoding="utf-8")
        assert "<graphite_routing>" not in content

    def test_install_deviate_pr_graphite_idempotent_on_repeat(self, tmp_path: Path):
        """Second install with same config → no duplicate section, file unchanged."""
        workdir = tmp_path / "repo"
        workdir.mkdir()
        self._seed_graphite_config(workdir, True)
        target = tmp_path / "agent" / "skills"

        install_skill("deviate-pr", target, workdir=workdir)
        first = (target / "deviate-pr" / "SKILL.md").read_text(encoding="utf-8")

        assert install_skill("deviate-pr", target, workdir=workdir) is False
        second = (target / "deviate-pr" / "SKILL.md").read_text(encoding="utf-8")
        assert first == second
        assert second.count("<graphite_routing>") == 1

    def test_install_deviate_pr_removes_graphite_when_disabled_after_enable(
        self, tmp_path: Path
    ):
        """Toggle graphite false → re-install removes the routing section."""
        workdir = tmp_path / "repo"
        workdir.mkdir()
        self._seed_graphite_config(workdir, True)
        target = tmp_path / "agent" / "skills"

        install_skill("deviate-pr", target, workdir=workdir)
        assert "<graphite_routing>" in (target / "deviate-pr" / "SKILL.md").read_text(
            encoding="utf-8"
        )

        self._seed_graphite_config(workdir, False)
        assert install_skill("deviate-pr", target, workdir=workdir) is True
        content = (target / "deviate-pr" / "SKILL.md").read_text(encoding="utf-8")
        assert "<graphite_routing>" not in content

    def test_install_deviate_pr_without_workdir_skips_graphite_check(
        self, tmp_path: Path
    ):
        """No workdir passed → no graphite injection (callers must opt in)."""
        target = tmp_path / "agent" / "skills"
        install_skill("deviate-pr", target)
        content = (target / "deviate-pr" / "SKILL.md").read_text(encoding="utf-8")
        assert "<graphite_routing>" not in content

    def test_install_other_skills_unaffected_by_graphite(self, tmp_path: Path):
        """graphite = true must not inject the section into non-deviate-pr skills."""
        workdir = tmp_path / "repo"
        workdir.mkdir()
        self._seed_graphite_config(workdir, True)
        target = tmp_path / "agent" / "skills"

        install_skill("deviate-red", target, workdir=workdir)
        content = (target / "deviate-red" / "SKILL.md").read_text(encoding="utf-8")
        assert "<graphite_routing>" not in content


class TestShardSkillIssueIdFormat:
    """deviate-shard SKILL.md must use the flat ``ISS-<NNN>`` format.

    The ``next_issue_id`` returned by ``deviate shard pre`` is the flat global
    counter (``ISS-001``, ``ISS-002``, ...). The skill must instruct the LLM
    to consume ``next_issue_id`` directly and increment per shard — it must
    NEVER concatenate the epic identifier, which would produce duplicate
    ``ISS-<epic>-<NNN>`` IDs across epics.
    """

    @staticmethod
    def _skill_text() -> str:
        return resolve_skill("deviate-shard").read_text(encoding="utf-8")

    def test_instruction_uses_flat_format_not_epic_prefixed(self):
        """Issue ID assignment rule must show flat ``ISS-<NNN>`` examples."""
        text = self._skill_text()
        assert "ISS-001-004" not in text
        assert "ISS-001-005" not in text

    def test_blocked_by_and_coordinates_with_examples_use_flat_format(self):
        """blocked_by / coordinates_with examples must reference flat IDs."""
        text = self._skill_text()
        assert 'blocked_by: ["ISS-001-004"]' not in text

    def test_manifest_schema_uses_flat_format(self):
        """Manifest schema must declare ``ISS-<NNN>``, not ``ISS-<epic>-<NNN>``."""
        text = self._skill_text()
        assert "ISS-<epic>-<NNN>" not in text

    def test_manifest_example_uses_flat_format(self):
        """Manifest example must show flat IDs (e.g. ``ISS-003``, not ``ISS-003-001``)."""
        text = self._skill_text()
        assert "ISS-003-001" not in text
        assert "ISS-003-002" not in text

    def test_instruction_references_flat_counter_format(self):
        """The rule must explicitly show the flat counter pattern."""
        text = self._skill_text()
        assert "ISS-003" in text or "ISS-004" in text
