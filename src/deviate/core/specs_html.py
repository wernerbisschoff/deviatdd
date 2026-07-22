"""Render DeviaTDD markdown specs (PRD, plan, flows) into standalone HTML.

The CLI calls :func:`render_html` from post-commit hooks for plan/prd and from
the ``deviate render`` command for flow files. Output is byte-stable so that
CSS-only edits to ``specs.css`` produce no spurious commit churn.

The renderer is intentionally minimal: CommonMark + tables + fenced code,
FR/AC/flow-ref token highlighting via a tiny post-processor, and the bundled
``specs.css`` embedded inline so files work offline (``file://`` open).
"""

from __future__ import annotations

import importlib.resources
import re
from html import escape
from pathlib import Path
from typing import Iterable

import markdown
from markdown.extensions.codehilite import CodeHiliteExtension

# ---------------------------------------------------------------------------
# Token highlighting — runs after markdown→HTML conversion
# ---------------------------------------------------------------------------

# FR-NNN-ID, AC-NNN-ID-NN, FLOW-NN (case-sensitive, must have digits).
_TOKEN_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("fr", re.compile(r"\bFR-\d{2,}-[A-Z][A-Z0-9_]+\b")),
    ("ac", re.compile(r"\bAC-\d{2,}-[A-Z][A-Z0-9_]+-\d{2,}\b")),
    ("flow-ref", re.compile(r"\bFLOW-\d{2,}\b")),
)

# Gherkin keywords get a <span class="gherkin-keyword"> for visual anchoring.
_GHERKIN_RE = re.compile(r"\b(Given|When|Then|And|But)\b(?!:)")

# Match <code>...</code> regions — both inline (single tag pair) and fenced
# (rendered as <pre><code>...</code></pre>). We strip these out before
# tokenizing so we don't wrap tokens that already live inside code.
_CODE_BLOCK_RE = re.compile(r"<code\b[^>]*>.*?</code>", re.DOTALL)


def _mask_code_regions(html: str) -> tuple[str, list[str]]:
    """Replace <code>...</code> regions with placeholders.

    Returns (masked_html, original_blocks) where ``original_blocks[i]`` is the
    i-th matched <code>...</code> region (in source order). The caller
    reinserts them after token highlighting.
    """
    blocks: list[str] = []

    def stash(match: re.Match[str]) -> str:
        blocks.append(match.group(0))
        return f"\x00CODE_BLOCK_{len(blocks) - 1}\x00"

    return _CODE_BLOCK_RE.sub(stash, html), blocks


def _restore_code_regions(html: str, blocks: list[str]) -> str:
    """Inverse of :func:`_mask_code_regions`."""
    for i, block in enumerate(blocks):
        html = html.replace(f"\x00CODE_BLOCK_{i}\x00", block)
    return html


def _highlight_tokens(html: str) -> str:
    """Wrap recognized spec tokens in <code class="..."> for CSS styling.

    Tokens inside existing <code>...</code> regions (inline or fenced) are
    left alone — those regions are stashed out, the highlighter runs on the
    remaining HTML, and the originals are spliced back in.
    """
    masked, blocks = _mask_code_regions(html)

    def apply(text: str) -> str:
        for cls, pattern in _TOKEN_PATTERNS:
            text = pattern.sub(
                lambda m: f'<code class="{cls}">{m.group(0)}</code>',
                text,
            )
        return text

    # Split on HTML tags so replacement only touches text nodes outside tags.
    parts = re.split(r"(<[^>]+>)", masked)
    masked = "".join(
        apply(part) if not part.startswith("<") else part for part in parts
    )
    return _restore_code_regions(masked, blocks)


def _highlight_gherkin(html: str) -> str:
    """Highlight Given/When/Then/And/But keywords in plain text nodes.

    Same code-mask discipline as :func:`_highlight_tokens` — code regions are
    preserved verbatim so we don't break inline code that happens to contain
    ``Given`` etc.
    """
    masked, blocks = _mask_code_regions(html)

    def apply(text: str) -> str:
        return _GHERKIN_RE.sub(
            r'<span class="gherkin-keyword">\1</span>',
            text,
        )

    parts = re.split(r"(<[^>]+>)", masked)
    masked = "".join(
        apply(part) if not part.startswith("<") else part for part in parts
    )
    return _restore_code_regions(masked, blocks)


# ---------------------------------------------------------------------------
# CSS asset loading
# ---------------------------------------------------------------------------

_CSS_PACKAGE = "deviate.assets"


def _load_css() -> str:
    """Load the bundled ``specs.css`` from package resources."""
    return (
        importlib.resources.files(_CSS_PACKAGE)
        .joinpath("specs.css")
        .read_text(encoding="utf-8")
    )


def _html_escape_attr(value: str) -> str:
    return escape(value, quote=True)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

_FRONTMATTER_RE = re.compile(r"^---\s*\n.*?\n---\s*\n", re.DOTALL)


def _strip_frontmatter(md: str) -> tuple[str, str]:
    """Strip a YAML frontmatter block, returning (body, frontmatter).

    Many specs (plan.md, issue files) carry ``flow_refs`` etc. in frontmatter;
    we drop it from the HTML body but still respect it for title inference.
    """
    match = _FRONTMATTER_RE.match(md)
    if not match:
        return md, ""
    return md[match.end() :], match.group(0)


def _infer_title(md_path: Path, body: str) -> str:
    """Use the first H1 in the body, falling back to the filename stem."""
    for line in body.splitlines():
        stripped = line.strip()
        if stripped.startswith("# "):
            return stripped[2:].strip()
    return md_path.stem.replace("-", " ").replace("_", " ").title()


_MD_EXTENSIONS = [
    "tables",
    "fenced_code",
    CodeHiliteExtension(guess_lang=False, css_class="highlight"),
]


def render_html(
    md_path: Path,
    html_path: Path,
    *,
    title: str | None = None,
) -> Path:
    """Render a single markdown file to a sibling HTML file.

    The renderer is deterministic — calling ``render_html`` twice on the same
    input produces byte-identical output, so a CSS-only update is detectable
    via ``git status`` without producing spurious commit churn from the
    markdown-side hooks.
    """
    md_path = Path(md_path)
    html_path = Path(html_path)
    raw = md_path.read_text(encoding="utf-8")
    body, _frontmatter = _strip_frontmatter(raw)

    resolved_title = title or _infer_title(md_path, body)

    body_html = markdown.markdown(
        body,
        extensions=_MD_EXTENSIONS,
        output_format="html5",
    )
    body_html = _highlight_tokens(body_html)
    body_html = _highlight_gherkin(body_html)

    css = _load_css()
    rel_md = _html_escape_attr(md_path.name)
    document = _HTML_TEMPLATE.format(
        title=_html_escape_attr(resolved_title),
        source_md=rel_md,
        css=css,
        body=body_html,
    )

    html_path.parent.mkdir(parents=True, exist_ok=True)
    html_path.write_text(document, encoding="utf-8")
    return html_path


def render_spec_set(
    md_paths: Iterable[Path],
    html_dir: Path | None = None,
) -> list[Path]:
    """Render a collection of markdown files to sibling HTML files.

    When ``html_dir`` is omitted, each ``.md`` is rendered next to itself
    (``foo.md`` → ``foo.html`` in the same directory). Returns the list of
    HTML paths written.
    """
    written: list[Path] = []
    for md_path in md_paths:
        md_path = Path(md_path)
        if html_dir is not None:
            html_path = Path(html_dir) / f"{md_path.stem}.html"
        else:
            html_path = md_path.with_suffix(".html")
        render_html(md_path, html_path)
        written.append(html_path)
    return written


def render_and_stage_if_changed(
    md_path: Path,
    repo: Path,
) -> Path | None:
    """Render ``md_path`` to ``md_path.with_suffix('.html')`` if it has pending changes.

    Wraps :func:`deviate.core.commit._has_changes_to_stage` so callers can
    gate HTML emission on real markdown diffs — a CSS-only update to
    ``specs.css`` returns ``None`` here and the caller skips the HTML entry
    in its staged ``files=[...]`` list, preventing spurious commits.

    Used by the post-commit hooks (``_plan_post``, ``prd_post``). Returns
    the rendered HTML path when the markdown changed, else ``None``.
    """
    from deviate.core.commit import _has_changes_to_stage

    md_path = Path(md_path)
    if not _has_changes_to_stage([md_path], Path(repo)):
        return None
    html_path = md_path.with_suffix(".html")
    render_html(md_path, html_path)
    return html_path


# ---------------------------------------------------------------------------
# Flow discovery
# ---------------------------------------------------------------------------


def find_flow_files(specs_root: Path) -> list[Path]:
    """Return all flow markdown files under ``<specs_root>/_product/flows``.

    Includes the canonical ``index.md`` and every ``flows-<domain>.md`` (or
    plain ``flows-<x>.md``) sibling. Excludes non-markdown files. Returns an
    empty list when the directory does not exist.
    """
    flows_dir = Path(specs_root) / "_product" / "flows"
    if not flows_dir.is_dir():
        return []
    out: list[Path] = []
    for path in sorted(flows_dir.glob("*.md")):
        # Skip anything inside a hidden subdir or with a leading dot.
        if path.name.startswith("."):
            continue
        out.append(path)
    return out


# ---------------------------------------------------------------------------
# HTML template
# ---------------------------------------------------------------------------

_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>{title}</title>
<meta name="generator" content="deviate specs_html">
<meta name="source-md" content="{source_md}">
<style>
{css}
</style>
</head>
<body>
<header class="spec-meta">
<p><strong>Source</strong>: <code>{source_md}</code></p>
</header>
{body}
</body>
</html>
"""
