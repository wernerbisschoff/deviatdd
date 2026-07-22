"""Tests for ``deviate.core.specs_html`` — the spec markdown→HTML renderer.

Covers the render contract end-to-end:
- Token highlighting (FR/AC/flow-ref) on rendered HTML.
- Table rendering via the ``tables`` extension.
- Fenced-code-block rendering via the ``fenced_code`` + CodeHilite extensions.
- CSS is embedded inline (works offline via ``file://``).
- ``find_flow_files()`` discovery over the canonical flows layout.
- Byte-identical round-trip (deterministic; CSS-only edits don't churn).
- ``render_and_stage_if_changed`` change-detection gate.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from deviate.core.commit import _git_env
from deviate.core.specs_html import (
    find_flow_files,
    render_and_stage_if_changed,
    render_html,
    render_spec_set,
)


# ---------------------------------------------------------------------------
# Token highlighting
# ---------------------------------------------------------------------------


def test_fr_ac_flow_tokens_are_highlighted(tmp_path: Path) -> None:
    md = tmp_path / "plan.md"
    md.write_text(
        "# Plan\n\nImplements FR-001-AUTH and AC-001-AUTH-01; referenced by FLOW-04.\n",
        encoding="utf-8",
    )
    html = render_html(md, md.with_suffix(".html"))
    body = html.read_text(encoding="utf-8")
    assert '<code class="fr">FR-001-AUTH</code>' in body
    assert '<code class="ac">AC-001-AUTH-01</code>' in body
    assert '<code class="flow-ref">FLOW-04</code>' in body


def test_lowercase_tokens_are_not_highlighted(tmp_path: Path) -> None:
    """Lowercase variants (flow-04, fr-001-foo) must NOT match the regex."""
    md = tmp_path / "x.md"
    md.write_text(
        "# X\n\n"
        "FLOW-04 uppercase token. flow-04 fr-001-foo flow_ref-04 are lowercase.\n",
        encoding="utf-8",
    )
    html = render_html(md, md.with_suffix(".html"))
    body = html.read_text(encoding="utf-8")
    # Uppercase token IS wrapped.
    assert '<code class="flow-ref">FLOW-04</code>' in body
    # No FR-class wrapper anywhere (lowercase fr-001-foo doesn't match).
    assert '<code class="fr">' not in body
    # Lowercase tokens remain as plain text.
    assert "flow-04" in body
    assert "fr-001-foo" in body


def test_tokens_inside_code_blocks_are_not_double_wrapped(tmp_path: Path) -> None:
    """Tokens inside fenced code blocks are already inside <code> — skip."""
    md = tmp_path / "x.md"
    md.write_text(
        "# X\n\n"
        "Inline FR-001-AUTH mentions it.\n\n"
        "```\n"
        "FR-001-AUTH literal in code\n"
        "```\n",
        encoding="utf-8",
    )
    html = render_html(md, md.with_suffix(".html"))
    body = html.read_text(encoding="utf-8")
    # Exactly ONE wrapped token — the inline one.
    assert body.count('<code class="fr">FR-001-AUTH</code>') == 1
    # The literal-in-code one stays as plain code text.
    assert "FR-001-AUTH literal in code" in body


# ---------------------------------------------------------------------------
# Markdown extensions
# ---------------------------------------------------------------------------


def test_tables_render_correctly(tmp_path: Path) -> None:
    md = tmp_path / "prd.md"
    md.write_text(
        "# PRD\n\n"
        "| FR ID | Status |\n"
        "| ----- | ------ |\n"
        "| FR-001-AUTH | OPEN |\n"
        "| FR-002-API | DONE |\n",
        encoding="utf-8",
    )
    html = render_html(md, md.with_suffix(".html"))
    body = html.read_text(encoding="utf-8")
    assert "<table>" in body
    assert "<th>FR ID</th>" in body
    assert '<td><code class="fr">FR-001-AUTH</code></td>' in body


def test_fenced_code_blocks_render(tmp_path: Path) -> None:
    md = tmp_path / "design.md"
    md.write_text(
        "# Design\n\n```python\ndef hello() -> str:\n    return 'world'\n```\n",
        encoding="utf-8",
    )
    html = render_html(md, md.with_suffix(".html"))
    body = html.read_text(encoding="utf-8")
    # CodeHiliteExtension splits tokens into spans; the rendered string
    # contains the source as a span soup rather than raw text. Assert on
    # structural markers and on guaranteed-literal span classes.
    assert "<pre>" in body
    assert '<span class="k">def</span>' in body
    assert '<span class="nf">hello</span>' in body
    assert "world" in body


def test_yaml_frontmatter_is_stripped_from_body(tmp_path: Path) -> None:
    md = tmp_path / "x.md"
    md.write_text(
        "---\nflow_refs: [FLOW-04]\n---\n# Visible Heading\n\nBody content here.\n",
        encoding="utf-8",
    )
    html = render_html(md, md.with_suffix(".html"))
    body = html.read_text(encoding="utf-8")
    assert "Visible Heading" in body
    # The frontmatter literal text should not appear inside the body.
    assert "flow_refs: [FLOW-04]" not in body


# ---------------------------------------------------------------------------
# CSS embedded + offline
# ---------------------------------------------------------------------------


def test_css_is_embedded_inline(tmp_path: Path) -> None:
    md = tmp_path / "x.md"
    md.write_text("# Title\n", encoding="utf-8")
    html = render_html(md, md.with_suffix(".html"))
    body = html.read_text(encoding="utf-8")
    # CSS lives inside <style>...</style>, not as an external link.
    assert "<style>" in body
    assert "</style>" in body
    # No external CSS reference — must work offline.
    assert '<link rel="stylesheet"' not in body
    # Spot-check a known token class from the bundled sheet.
    assert ".fr" in body
    assert ".ac" in body
    assert ".flow-ref" in body


def test_title_inference_from_first_h1(tmp_path: Path) -> None:
    md = tmp_path / "x.md"
    md.write_text("# My Custom PRD Title\n\nbody\n", encoding="utf-8")
    html = render_html(md, md.with_suffix(".html"))
    body = html.read_text(encoding="utf-8")
    assert "<title>My Custom PRD Title</title>" in body
    assert 'name="source-md" content="x.md"' in body


def test_title_falls_back_to_filename(tmp_path: Path) -> None:
    md = tmp_path / "fallback-plan.md"
    md.write_text("body without heading\n", encoding="utf-8")
    html = render_html(md, md.with_suffix(".html"))
    body = html.read_text(encoding="utf-8")
    # Filename stem → "Fallback Plan".
    assert "Fallback Plan" in body


# ---------------------------------------------------------------------------
# render_spec_set
# ---------------------------------------------------------------------------


def test_render_spec_set_writes_sibling_html(tmp_path: Path) -> None:
    md_a = tmp_path / "a.md"
    md_b = tmp_path / "b.md"
    md_a.write_text("# A\n", encoding="utf-8")
    md_b.write_text("# B\n", encoding="utf-8")
    written = render_spec_set([md_a, md_b])
    assert len(written) == 2
    assert all(p.exists() for p in written)
    assert (tmp_path / "a.html").exists()
    assert (tmp_path / "b.html").exists()


def test_render_spec_set_with_explicit_dir(tmp_path: Path) -> None:
    md = tmp_path / "src" / "x.md"
    md.parent.mkdir(parents=True, exist_ok=True)
    md.write_text("# X\n", encoding="utf-8")
    out_dir = tmp_path / "out"
    written = render_spec_set([md], html_dir=out_dir)
    assert written == [out_dir / "x.html"]
    assert (out_dir / "x.html").exists()


# ---------------------------------------------------------------------------
# Flow discovery
# ---------------------------------------------------------------------------


def test_find_flow_files_returns_index_and_domain(tmp_path: Path) -> None:
    flows_dir = tmp_path / "_product" / "flows"
    flows_dir.mkdir(parents=True, exist_ok=True)
    (flows_dir / "index.md").write_text("# Index\n", encoding="utf-8")
    (flows_dir / "flows-product.md").write_text("# Product\n", encoding="utf-8")
    (flows_dir / "flows-streaming.md").write_text("# Streaming\n", encoding="utf-8")
    result = find_flow_files(tmp_path)
    names = sorted(p.name for p in result)
    assert "index.md" in names
    assert "flows-product.md" in names
    assert "flows-streaming.md" in names


def test_find_flow_files_excludes_hidden_and_non_md(tmp_path: Path) -> None:
    flows_dir = tmp_path / "_product" / "flows"
    flows_dir.mkdir(parents=True, exist_ok=True)
    (flows_dir / "index.md").write_text("# Index\n", encoding="utf-8")
    (flows_dir / ".hidden-flow.md").write_text("secret\n", encoding="utf-8")
    (flows_dir / "README.txt").write_text("not markdown\n", encoding="utf-8")
    result = find_flow_files(tmp_path)
    names = [p.name for p in result]
    assert names == ["index.md"]


def test_find_flow_files_returns_empty_when_dir_absent(tmp_path: Path) -> None:
    assert find_flow_files(tmp_path) == []


# ---------------------------------------------------------------------------
# Determinism — byte-identical round-trip
# ---------------------------------------------------------------------------


def test_render_html_is_byte_deterministic(tmp_path: Path) -> None:
    md = tmp_path / "x.md"
    md.write_text(
        "# Determinism\n\n"
        "FR-001-X AC-001-X-01 FLOW-04 — all paths covered.\n"
        "\n"
        "| Col A | Col B |\n"
        "| ----- | ----- |\n"
        "| 1     | 2     |\n",
        encoding="utf-8",
    )
    out_a = tmp_path / "a.html"
    out_b = tmp_path / "b.html"
    render_html(md, out_a)
    render_html(md, out_b)
    assert out_a.read_bytes() == out_b.read_bytes()


def test_render_html_path_must_exist(tmp_path: Path) -> None:
    md = tmp_path / "missing.md"
    with pytest.raises(FileNotFoundError):
        render_html(md, md.with_suffix(".html"))


# ---------------------------------------------------------------------------
# render_and_stage_if_changed — the post-hook gate
# ---------------------------------------------------------------------------


def _init_repo(path: Path) -> None:
    subprocess.run(["git", "init"], cwd=path, env=_git_env(), check=True)
    subprocess.run(
        ["git", "config", "user.email", "r@t.local"],
        cwd=path,
        env=_git_env(),
        check=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "R"],
        cwd=path,
        env=_git_env(),
        check=True,
    )


def test_render_and_stage_skips_when_no_md_changes(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    md = tmp_path / "plan.md"
    md.write_text("# Plan\n", encoding="utf-8")
    subprocess.run(["git", "add", "plan.md"], cwd=tmp_path, env=_git_env(), check=True)
    subprocess.run(
        ["git", "commit", "-m", "init"], cwd=tmp_path, env=_git_env(), check=True
    )
    # md is now committed — no pending changes.
    result = render_and_stage_if_changed(md, repo=tmp_path)
    assert result is None
    # No HTML should have been written either.
    assert not (tmp_path / "plan.html").exists()


def test_render_and_stage_writes_html_when_md_changed(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    md = tmp_path / "plan.md"
    md.write_text("# Plan v1\n", encoding="utf-8")
    subprocess.run(["git", "add", "plan.md"], cwd=tmp_path, env=_git_env(), check=True)
    subprocess.run(
        ["git", "commit", "-m", "init"], cwd=tmp_path, env=_git_env(), check=True
    )
    # Now edit — this is the "pending change" that should trigger HTML render.
    md.write_text("# Plan v2\n\nNew FR-001-AUTH section.\n", encoding="utf-8")
    result = render_and_stage_if_changed(md, repo=tmp_path)
    assert result == md.with_suffix(".html")
    assert result.exists()
    body = result.read_text(encoding="utf-8")
    assert '<code class="fr">FR-001-AUTH</code>' in body
