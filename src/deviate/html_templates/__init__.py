"""Per-phase HTML starter scaffolds for the ``deviate html`` command.

The renderer is intentionally minimal: it bakes the canonical stylesheet
into a placeholder template and writes a sibling ``.html`` file. The agent
running the phase is responsible for authoring the body — there is no
markdown→HTML translation. That contract is what lets HTML express
diagrams, interactive components, and custom layouts that CommonMark
cannot.

Templates are stored as ``<phase>.html.tmpl`` files alongside this
module. The CSS is inlined as a module constant so the loader is
self-contained — no package data, no ``importlib.resources`` lookup,
no path-on-disk coupling for the stylesheet.
"""

from __future__ import annotations

from pathlib import Path

# Phase identifiers accepted by ``deviate html <phase>``. Each maps to
# one template file in this package.
_PHASES: tuple[str, ...] = ("architecture", "prd", "plan", "flows", "domain-model")

_TEMPLATE_SUFFIX = ".html.tmpl"

# Canonical stylesheet — baked in so the loader has no filesystem
# coupling beyond its own package files. Kept in sync with the
# rendering target (PRD/plan/flows/etc.) and updated as the design
# system evolves.
_CSS: str = """\
/* DeviaTDD spec stylesheet — bundled into rendered spec HTML.
   Goal: dense, scannable, monospace-friendly reading for PRD/plan/flows.
   No external fonts, no JS — must work offline via file://. */

:root {
    --fg: #1d1f21;
    --fg-muted: #6a737d;
    --bg: #ffffff;
    --bg-alt: #f7f7f8;
    --bg-token: #eef2ff;
    --border: #e1e4e8;
    --accent: #2563eb;
    --accent-fr: #7c3aed;
    --accent-ac: #0891b2;
    --code-bg: #f6f8fa;
    --code-fg: #24292e;
}

* { box-sizing: border-box; }

body {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
    color: var(--fg);
    background: var(--bg);
    line-height: 1.55;
    max-width: 920px;
    margin: 2rem auto;
    padding: 0 1.5rem;
}

header.spec-meta {
    border-bottom: 1px solid var(--border);
    padding-bottom: 1rem;
    margin-bottom: 2rem;
    color: var(--fg-muted);
    font-size: 0.9rem;
}

header.spec-meta h1 { margin-top: 0; color: var(--fg); }

h1, h2, h3, h4 {
    line-height: 1.25;
    margin-top: 2rem;
    margin-bottom: 0.75rem;
    font-weight: 600;
}
h1 { font-size: 1.9rem; border-bottom: 1px solid var(--border); padding-bottom: 0.3rem; }
h2 { font-size: 1.4rem; border-bottom: 1px solid var(--border); padding-bottom: 0.25rem; }
h3 { font-size: 1.15rem; }
h4 { font-size: 1rem; color: var(--fg-muted); }

a { color: var(--accent); text-decoration: none; }
a:hover { text-decoration: underline; }

code {
    font-family: "SF Mono", Menlo, Consolas, "Liberation Mono", monospace;
    background: var(--code-bg);
    color: var(--code-fg);
    padding: 0.15em 0.35em;
    border-radius: 3px;
    font-size: 0.92em;
}

pre {
    background: var(--code-bg);
    color: var(--code-fg);
    padding: 1rem;
    border-radius: 6px;
    overflow-x: auto;
    line-height: 1.45;
    border: 1px solid var(--border);
}
pre code {
    background: transparent;
    padding: 0;
    font-size: 0.88em;
}

table {
    border-collapse: collapse;
    margin: 1rem 0;
    width: 100%;
    font-size: 0.92rem;
}
th, td {
    border: 1px solid var(--border);
    padding: 0.5rem 0.75rem;
    text-align: left;
    vertical-align: top;
}
th { background: var(--bg-alt); font-weight: 600; }
tbody tr:nth-child(even) { background: var(--bg-alt); }

blockquote {
    margin: 1rem 0;
    padding: 0.25rem 1rem;
    border-left: 4px solid var(--accent);
    color: var(--fg-muted);
    background: var(--bg-alt);
}

ul, ol { padding-left: 1.5rem; }
li { margin: 0.25rem 0; }

hr { border: 0; border-top: 1px solid var(--border); margin: 2rem 0; }

/* FR-/AC-token highlighting — anchors the spec contract semantically */
code.fr, code.ac, code.flow-ref {
    background: var(--bg-token);
    font-weight: 600;
    padding: 0.1em 0.4em;
    border-radius: 3px;
}
code.fr   { color: var(--accent-fr); }
code.ac   { color: var(--accent-ac); }
code.flow-ref { color: var(--accent); }

/* Gherkin keywords (Given/When/Then) get subtle emphasis */
.gherkin-keyword { font-weight: 600; color: var(--accent); }
"""


def supported_phases() -> tuple[str, ...]:
    """Return the ordered list of phase identifiers the command accepts."""
    return _PHASES


def is_supported_phase(phase: str) -> bool:
    """Whether ``phase`` is a registered starter-template identifier."""
    return phase in _PHASES


def _phase_title(phase: str) -> str:
    """Human-readable title for the ``<h1>`` in the starter scaffold."""
    return {
        "architecture": "Architecture",
        "prd": "Product Requirements",
        "plan": "Implementation Plan",
        "flows": "Flow Catalog",
        "domain-model": "Domain Model",
    }[phase]


def render_starter(phase: str, source_md: Path) -> str:
    """Render the starter HTML scaffold for ``phase``.

    ``source_md`` is the path to the markdown file the agent will read
    when authoring the body. It is recorded in the ``<meta name="source-md">``
    tag and the visible header so reviewers know where the source of truth
    lives. The body itself is empty placeholder content &mdash; the agent
    fills it in.
    """
    if not is_supported_phase(phase):
        raise ValueError(f"unknown phase: {phase!r}; supported: {', '.join(_PHASES)}")
    from importlib.resources import files

    template_text = (
        files("deviate.html_templates")
        .joinpath(f"{phase}{_TEMPLATE_SUFFIX}")
        .read_text(encoding="utf-8")
    )
    # Use sentinel substitution exclusively. ``str.format()`` is unsafe
    # here because template bodies contain literal ``{NNN}`` / ``{ID}``
    # placeholders (FR token schemas, ID list items, etc.) that would
    # be interpreted as format placeholders. All four substitution slots
    # use unambiguous sentinels (``<<NAME>>``) and a single ``.replace``
    # pass each, in CSS-last order to keep the stylesheet out of the
    # format machinery entirely.
    rendered = template_text
    rendered = rendered.replace("<<TITLE>>", _phase_title(phase))
    rendered = rendered.replace("<<PHASE_TITLE>>", _phase_title(phase))
    rendered = rendered.replace("<<SOURCE_MD>>", str(source_md))
    rendered = rendered.replace("<<CSS>>", _CSS)
    return rendered
