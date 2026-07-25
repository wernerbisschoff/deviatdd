"""Tests for ``deviate html`` — per-phase HTML starter scaffold writer.

The CLI does NOT render markdown to HTML. It writes an empty HTML5
skeleton with section anchors and ``TODO`` placeholders; the agent
running the phase fills in the body from the corresponding ``.md``
file. These tests pin that contract: the scaffold is created, the
existing-html guard works, and overwrites require ``--force``.
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest
from typer.testing import CliRunner

from deviate.cli import cli
from deviate.html_templates import (
    is_supported_phase,
    render_starter,
    supported_phases,
)

runner = CliRunner()


def _git_env() -> dict[str, str]:
    """Strip inherited GIT_* / GH_* env vars from the parent repo."""
    return {k: v for k, v in os.environ.items() if not k.startswith(("GIT_", "GH_"))}


def _init_repo(path: Path) -> None:
    subprocess.run(["git", "init"], cwd=path, env=_git_env(), check=True)
    subprocess.run(
        ["git", "config", "user.email", "test@test"],
        cwd=path,
        env=_git_env(),
        check=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test"],
        cwd=path,
        env=_git_env(),
        check=True,
    )
    (path / "README.md").write_text("init")
    subprocess.run(["git", "add", "README.md"], cwd=path, env=_git_env(), check=True)
    subprocess.run(
        ["git", "commit", "-m", "init"],
        cwd=path,
        env=_git_env(),
        check=True,
    )


def _seed_product_md(tmp_path: Path) -> Path:
    """Create the product-layer markdown files the html command consumes."""
    product = tmp_path / "specs" / "_product"
    flows = product / "flows"
    flows.mkdir(parents=True)
    (product / "architecture.md").write_text("# Architecture\n")
    (product / "domain-model.md").write_text("# Domain Model\n")
    (flows / "index.md").write_text("# Flows\n")
    return product


def _seed_issue(
    specs: Path,
    *,
    issue_id: str,
    source_file: str,
    title: str = "Demo",
    status: str = "BACKLOG",
) -> None:
    """Write one valid ``IssueRecord`` line into ``specs/issues.jsonl``."""
    (specs / "issues.jsonl").write_text(
        json.dumps(
            {
                "issue_id": issue_id,
                "type": "feature",
                "title": title,
                "status": status,
                "source_file": source_file,
                "timestamp": "2026-01-01T00:00:00Z",
            }
        )
        + "\n"
    )


# ---------------------------------------------------------------------------
# Library surface
# ---------------------------------------------------------------------------


def test_supported_phases_returns_expected_list() -> None:
    """The five phases map to the five human-review artifacts."""
    assert supported_phases() == (
        "architecture",
        "prd",
        "plan",
        "flows",
        "domain-model",
    )


def test_is_supported_phase_accepts_known_phases() -> None:
    assert is_supported_phase("architecture")
    assert is_supported_phase("prd")
    assert is_supported_phase("plan")
    assert is_supported_phase("flows")
    assert is_supported_phase("domain-model")


def test_is_supported_phase_rejects_unknown_phases() -> None:
    assert not is_supported_phase("explore")
    assert not is_supported_phase("research")
    assert not is_supported_phase("")


def test_render_starter_rejects_unknown_phase() -> None:
    with pytest.raises(ValueError, match="unknown phase"):
        render_starter("research", Path("x.md"))


def test_render_starter_substitutes_all_sentinels(tmp_path: Path) -> None:
    """Sentinels are replaced; nothing leaks back into the output."""
    out = render_starter(
        "architecture", tmp_path / "specs" / "_product" / "architecture.md"
    )
    assert "<<TITLE>>" not in out
    assert "<<PHASE_TITLE>>" not in out
    assert "<<SOURCE_MD>>" not in out
    assert "<<CSS>>" not in out
    # The source path appears in the header / <meta> tag.
    assert "architecture.md" in out
    # CSS content is present (variable declarations).
    assert "--bg:" in out


def test_render_starter_does_not_translate_markdown_body(tmp_path: Path) -> None:
    """The starter body is empty placeholders — no markdown → HTML leak."""
    md = tmp_path / "prd.md"
    md.write_text("# H1\n\n**bold** text\n```python\ncode\n```\n")
    out = render_starter("prd", md)
    # Fenced code blocks render as <pre><code> under CommonMark; the
    # sentinel scaffold contains no fenced-code rendering.
    assert "<pre><code>" not in out
    # Auto-id headings (``<h2 id="user-stories">``) are a markdown
    # extension artefact; the scaffold emits plain ``<h2>``.
    assert "<h2 id=" not in out


# ---------------------------------------------------------------------------
# CLI: per-phase commands
# ---------------------------------------------------------------------------


def test_html_architecture_writes_scaffold(tmp_path: Path, monkeypatch) -> None:
    _seed_product_md(tmp_path)
    monkeypatch.chdir(tmp_path)
    r = runner.invoke(cli, ["html", "architecture"])
    assert r.exit_code == 0, r.output
    out = tmp_path / "specs" / "_product" / "architecture.html"
    assert out.exists()
    body = out.read_text()
    assert "<!DOCTYPE html>" in body
    assert "Architecture" in body
    assert "architecture.md" in body
    # Section anchors present, no markdown → HTML conversion.
    assert 'id="recommended-architecture"' in body
    assert "<pre><code>" not in body
    assert "<h1 id=" not in body


def test_html_prd_refuses_when_no_prd_exists(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "specs").mkdir()
    r = runner.invoke(cli, ["html", "prd"])
    assert r.exit_code != 0
    assert "HTML_NO_PRD" in r.output or "HTML_NO_PRD" in (r.stderr or "")


def test_html_prd_refuses_with_multiple_prds(tmp_path: Path, monkeypatch) -> None:
    """Ambiguity guard — refuses when more than one epic has prd.md."""
    _seed_product_md(tmp_path)
    (tmp_path / "specs" / "001-foo").mkdir(parents=True)
    (tmp_path / "specs" / "001-foo" / "prd.md").write_text("# Foo\n")
    (tmp_path / "specs" / "002-bar").mkdir(parents=True)
    (tmp_path / "specs" / "002-bar" / "prd.md").write_text("# Bar\n")
    monkeypatch.chdir(tmp_path)
    r = runner.invoke(cli, ["html", "prd"])
    assert r.exit_code != 0
    assert "HTML_AMBIGUOUS_PRD" in r.output or "HTML_AMBIGUOUS_PRD" in (r.stderr or "")


def test_html_prd_writes_scaffold_for_single_epic(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / "specs" / "001-foo").mkdir(parents=True)
    (tmp_path / "specs" / "001-foo" / "prd.md").write_text("# Foo\n")
    monkeypatch.chdir(tmp_path)
    r = runner.invoke(cli, ["html", "prd"])
    assert r.exit_code == 0, r.output
    assert (tmp_path / "specs" / "001-foo" / "prd.html").exists()


def test_html_prd_excludes_adhoc_and_unnumbered_buckets(
    tmp_path: Path, monkeypatch
) -> None:
    """``adhoc`` / ``_product`` / ``explore`` must not appear as candidates."""
    (tmp_path / "specs" / "adhoc").mkdir(parents=True)
    (tmp_path / "specs" / "adhoc" / "prd.md").write_text("# Adhoc\n")
    (tmp_path / "specs" / "explore").mkdir(parents=True)
    (tmp_path / "specs" / "explore" / "prd.md").write_text("# Explore\n")
    _seed_product_md(tmp_path)
    monkeypatch.chdir(tmp_path)
    r = runner.invoke(cli, ["html", "prd"])
    # All non-epic candidates excluded → HTML_NO_PRD, not AMBIGUOUS.
    assert r.exit_code != 0
    assert "HTML_NO_PRD" in r.output or "HTML_NO_PRD" in (r.stderr or "")
    # No html written into the non-epic dirs.
    assert not (tmp_path / "specs" / "adhoc" / "prd.html").exists()
    assert not (tmp_path / "specs" / "explore" / "prd.html").exists()


def test_html_flows_writes_index_scaffold(tmp_path: Path, monkeypatch) -> None:
    _seed_product_md(tmp_path)
    monkeypatch.chdir(tmp_path)
    r = runner.invoke(cli, ["html", "flows"])
    assert r.exit_code == 0, r.output
    out = tmp_path / "specs" / "_product" / "flows" / "index.html"
    assert out.exists()


def test_html_flows_fails_when_index_missing(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / "specs" / "_product" / "flows").mkdir(parents=True)
    monkeypatch.chdir(tmp_path)
    r = runner.invoke(cli, ["html", "flows"])
    assert r.exit_code != 0


def test_html_domain_model_writes_scaffold(tmp_path: Path, monkeypatch) -> None:
    _seed_product_md(tmp_path)
    monkeypatch.chdir(tmp_path)
    r = runner.invoke(cli, ["html", "domain-model"])
    assert r.exit_code == 0, r.output
    assert (tmp_path / "specs" / "_product" / "domain-model.html").exists()


# ---------------------------------------------------------------------------
# CLI: overwrite guard
# ---------------------------------------------------------------------------


def test_html_refuses_to_overwrite_without_force(tmp_path: Path, monkeypatch) -> None:
    _seed_product_md(tmp_path)
    monkeypatch.chdir(tmp_path)
    first = runner.invoke(cli, ["html", "architecture"])
    assert first.exit_code == 0, first.output
    second = runner.invoke(cli, ["html", "architecture"])
    assert second.exit_code != 0
    assert "HTML_EXISTS" in second.output or "HTML_EXISTS" in (second.stderr or "")


def test_html_force_overwrites(tmp_path: Path, monkeypatch) -> None:
    _seed_product_md(tmp_path)
    monkeypatch.chdir(tmp_path)
    runner.invoke(cli, ["html", "architecture"])
    r = runner.invoke(cli, ["html", "architecture", "--force"])
    assert r.exit_code == 0, r.output


# ---------------------------------------------------------------------------
# CLI: plan resolution + branch autodetect
# ---------------------------------------------------------------------------


def test_html_plan_without_issue_or_branch_fails_gracefully(
    tmp_path: Path, monkeypatch
) -> None:
    """No ``--issue``, not on a feat/* branch, no session → HTML_NO_ISSUE."""
    (tmp_path / "specs").mkdir()
    _init_repo(tmp_path)
    monkeypatch.chdir(tmp_path)
    r = runner.invoke(cli, ["html", "plan"])
    assert r.exit_code != 0
    assert "HTML_NO_ISSUE" in r.output or "HTML_NO_ISSUE" in (r.stderr or "")


def test_html_plan_with_explicit_issue_writes_scaffold(
    tmp_path: Path, monkeypatch
) -> None:
    """``--issue ISS-NNN-NN`` resolves through the ledger to ``plan.md``.

    Real layout: ``specs/<bucket>/<slug>/plan.md`` lives under the
    per-issue subdirectory, not at the bucket root.
    """
    _init_repo(tmp_path)
    specs = tmp_path / "specs"
    (specs / "001-feat" / "issues").mkdir(parents=True)
    (specs / "001-feat" / "issues" / "demo.md").write_text(
        "# Demo\n\n## User Stories Ledger\n- US1\n"
    )
    plan_dir = specs / "001-feat" / "demo"
    plan_dir.mkdir(parents=True)
    (plan_dir / "plan.md").write_text("# Plan\n")
    _seed_issue(
        specs,
        issue_id="ISS-001-01",
        source_file="specs/001-feat/issues/demo.md",
    )
    monkeypatch.chdir(tmp_path)
    r = runner.invoke(cli, ["html", "plan", "--issue", "ISS-001-01"])
    assert r.exit_code == 0, r.output
    assert (plan_dir / "plan.html").exists()


def test_html_plan_autodetects_from_branch(tmp_path: Path, monkeypatch) -> None:
    """``feat/<bucket>/<slug>`` branch → ledger lookup → plan.md path."""
    _init_repo(tmp_path)
    specs = tmp_path / "specs"
    (specs / "001-feat" / "issues").mkdir(parents=True)
    (specs / "001-feat" / "issues" / "demo.md").write_text("# Demo\n")
    plan_dir = specs / "001-feat" / "demo"
    plan_dir.mkdir(parents=True)
    (plan_dir / "plan.md").write_text("# Plan\n")
    _seed_issue(
        specs,
        issue_id="ISS-001-01",
        source_file="specs/001-feat/issues/demo.md",
    )
    subprocess.run(
        ["git", "checkout", "-b", "feat/001-feat/demo"],
        cwd=tmp_path,
        env=_git_env(),
        check=True,
    )
    monkeypatch.chdir(tmp_path)
    r = runner.invoke(cli, ["html", "plan"])
    assert r.exit_code == 0, r.output
    assert (plan_dir / "plan.html").exists()


# ---------------------------------------------------------------------------
# CLI: `all`
# ---------------------------------------------------------------------------


def test_html_all_writes_every_phase_scaffold(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / "specs" / "001-foo").mkdir(parents=True)
    (tmp_path / "specs" / "001-foo" / "prd.md").write_text("# Foo\n")
    _seed_product_md(tmp_path)
    monkeypatch.chdir(tmp_path)
    r = runner.invoke(cli, ["html", "all", "--force"])
    # plan is best-effort; without a branch/session, it's silently skipped.
    assert r.exit_code == 0
    assert (tmp_path / "specs" / "_product" / "architecture.html").exists()
    assert (tmp_path / "specs" / "_product" / "domain-model.html").exists()
    assert (tmp_path / "specs" / "_product" / "flows" / "index.html").exists()
    assert (tmp_path / "specs" / "001-foo" / "prd.html").exists()


def test_html_all_skips_existing(tmp_path: Path, monkeypatch) -> None:
    """Without ``--force``, existing HTML is reported as skipped."""
    _seed_product_md(tmp_path)
    monkeypatch.chdir(tmp_path)
    runner.invoke(cli, ["html", "architecture"])
    r = runner.invoke(cli, ["html", "all"])
    assert "HTML_SKIPPED" in r.output or "HTML_SKIPPED" in (r.stderr or "")
