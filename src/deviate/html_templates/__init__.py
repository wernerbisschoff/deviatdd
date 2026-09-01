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

import re
from pathlib import Path

# Phase identifiers accepted by ``deviate html <phase>``. Each maps to
# one template file in this package.
_PHASES: tuple[str, ...] = ("prd", "plan")

_TEMPLATE_SUFFIX = ".html.tmpl"

# Canonical stylesheet — baked in so the loader has no filesystem
# coupling beyond its own package files. The design system is dark-first,
# ADHD-friendly, and offline-friendly (no external fonts, no JS).
# Legacy CSS variable names (``--bg``, ``--accent`` etc.) are preserved
# so downstream consumers (jump links, search tooling, custom skins) can
# still read them; new layered ink tokens (``--ink-*``, ``--fg-*``,
# ``--accent-*``) drive the visual treatment.
_CSS: str = """\
/* =====================================================================
   DeviaTDD spec stylesheet — "Mission Console"
   Goal: a low-distraction, dark-first reading surface for PRD / plan
   artifacts. ADHD-friendly: sticky
   numbered TOC, progress affordances, mission-stamp tokens, generous
   line-height, no external dependencies.

   Works offline (file://), no JS, no CDN — the page is a static
   inlined CSS + HTML deliverable.
   ===================================================================== */

/* --- 1. Design tokens ------------------------------------------------- */
:root {
    /* Ink layers — deepest first. Not pure black: dark ink reduces
       contrast strain and lets accent colors pop without crushing. */
    --ink-0:  #07090d;     /* deepest; reserved */
    --ink-1:  #0d1117;     /* primary page bg */
    --ink-2:  #161b22;     /* sidebar, callouts, table alt rows */
    --ink-3:  #1f2730;     /* table header, code bg */
    --ink-4:  #2a3441;     /* standard borders */
    --ink-5:  #3a4759;     /* strong borders */

    /* Text — graded legibility. Foreground never below AA on --ink-1. */
    --fg-0:   #f0f6fc;     /* primary text — soft white */
    --fg-1:   #c9d1d9;     /* secondary text */
    --fg-2:   #8b949e;     /* tertiary / muted labels */
    --fg-3:   #586069;     /* subtle / dim — structure only */

    /* Semantic accents — phosphor-console palette.
       Each accent drives a category of tokens, chips, and callouts. */
    --accent-flow:  #58a6ff;   /* sky    — flow tokens, primary CTA     */
    --accent-fr:    #d2a8ff;   /* lavender — FR tokens, requirements   */
    --accent-ac:    #79c0ff;   /* cyan    — AC tokens, contracts         */
    --accent-warn:  #f85149;   /* red     — danger / warn               */
    --accent-go:    #3fb950;   /* green   — ready / done / approved     */
    --accent-amber: #d29922;   /* amber   — pending / draft             */
    --accent-pink:  #db61a2;   /* pink    — accent only                 */

    /* Backwards-compatible legacy tokens — preserved for any
       downstream tooling that read them off generated HTML. */
    --fg:           var(--fg-0);
    --fg-muted:     var(--fg-1);
    --bg:           var(--ink-1);
    --bg-alt:       var(--ink-2);
    --bg-token:     var(--ink-3);
    --border:       var(--ink-4);
    --accent:       var(--accent-flow);
    --code-bg:      var(--ink-3);
    --code-fg:      var(--fg-0);

    /* Typography stacks. System-font only — works offline, picks up the
       host platform's native UI font in the right slot. Subtle feature
       settings enable kerning + ligatures + iStyle variants where the
       underlying font supports them. */
    --font-body:  ui-sans-serif, system-ui, -apple-system,
                  BlinkMacSystemFont, "Segoe UI Variable", "Segoe UI",
                  "Helvetica Neue", Helvetica, Arial, sans-serif;
    --font-mono:  ui-monospace, "SFMono-Regular", "SF Mono", Menlo,
                  Consolas, "Liberation Mono", "DejaVu Sans Mono",
                  monospace;
    --font-serif: ui-serif, "Iowan Old Style", "Apple Garamond", Georgia,
                  Cambria, "Times New Roman", Times, serif;

    /* Layout — split shell with sticky sidebar at >=1080px. */
    --shell-max:  1400px;
    --main-max:   920px;
    --sidebar-w:  280px;
    --gap:        2.5rem;

    /* Type scale (1.25 ratio). Tight on display, normal on body. */
    --fs-xs:   0.78rem;
    --fs-sm:   0.875rem;
    --fs-base: 1rem;
    --fs-md:   1.1rem;
    --fs-lg:   1.35rem;
    --fs-xl:   1.65rem;
    --fs-2xl:  2.1rem;

    /* Motion — short, restrained, with reduced-motion override below. */
    --ease:       cubic-bezier(0.22, 0.61, 0.36, 1);
    --dur-fast:   120ms;
    --dur:        200ms;
    --dur-slow:   400ms;

    color-scheme: dark;
}

/* --- 2. Reset & motion preferences ----------------------------------- */
*, *::before, *::after { box-sizing: border-box; }

:focus { outline: none; }
:focus-visible {
    outline: 2px solid var(--accent-flow);
    outline-offset: 3px;
    border-radius: 3px;
    transition: outline-offset var(--dur-fast) var(--ease);
}

html {
    scroll-behavior: smooth;
    scroll-padding-top: 1.5rem;     /* anchored sections clear the top */
}

@media (prefers-reduced-motion: reduce) {
    html { scroll-behavior: auto; }
    *, *::before, *::after {
        animation-duration: 0.01ms !important;
        animation-iteration-count: 1 !important;
        transition-duration: 0.01ms !important;
        background-attachment: scroll !important;
    }
}

/* --- 3. Page shell ---------------------------------------------------- */
body {
    margin: 0;
    color: var(--fg-0);
    background-color: var(--ink-1);
    /* Subtle dot grid — two layers (one cool, one warm-ish), pinned to
       the viewport. Reads as "instrument backdrop" without being noisy.
       Disabled under prefers-reduced-motion (handled via
       background-attachment above) and falls back to solid color if
       background-image is unsupported. */
    background-image:
        radial-gradient(circle at 12px 12px,
                        rgba(255, 255, 255, 0.018) 1px, transparent 1.5px),
        radial-gradient(circle at calc(100% - 24px) calc(100% - 24px),
                        rgba(88, 166, 255, 0.04) 1px, transparent 1.5px);
    background-size: 56px 56px, 88px 88px;
    background-attachment: fixed;
    background-repeat: repeat;
    background-position: 0 0, 0 0;

    font-family: var(--font-body);
    font-size: var(--fs-base);
    line-height: 1.7;
    -webkit-font-smoothing: antialiased;
    -moz-osx-font-smoothing: grayscale;
    text-rendering: optimizeLegibility;
    font-feature-settings: "kern" 1, "liga" 1, "calt" 1, "ss03" 1;
    font-optical-sizing: auto;
    font-variant-numeric: oldstyle-nums proportional-nums;
}

/* --- 4. Layout (split shell: sticky sidebar + main column) ------------ */
.layout {
    display: grid;
    grid-template-columns: var(--sidebar-w) minmax(0, 1fr);
    gap: var(--gap);
    max-width: var(--shell-max);
    margin: 0 auto;
    padding: 3rem 2rem 6rem;
    align-items: start;
}

.sidebar {
    position: sticky;
    top: 2rem;
    max-height: calc(100vh - 4rem);
    overflow-y: auto;
    padding-right: 0.25rem;
    font-family: var(--font-mono);
    font-size: var(--fs-sm);
    scrollbar-width: thin;
    scrollbar-color: var(--ink-5) transparent;
}

.sidebar::-webkit-scrollbar { width: 6px; }
.sidebar::-webkit-scrollbar-thumb {
    background: var(--ink-5);
    border-radius: 3px;
}

.main {
    min-width: 0;          /* allow grid item to shrink */
    max-width: var(--main-max);
    animation: section-reveal 480ms var(--ease) both;
}

@keyframes section-reveal {
    from { opacity: 0; transform: translateY(8px); }
    to   { opacity: 1; transform: translateY(0); }
}

@media (max-width: 1080px) {
    .layout {
        grid-template-columns: 1fr;
        padding: 1.5rem 1rem 4rem;
    }
    .sidebar {
        position: static;
        max-height: none;
        margin-bottom: 2rem;
    }
}

/* --- 5. Skip-link (a11y) --------------------------------------------- */
.skip-link {
    position: fixed;
    top: -100px;
    left: 1rem;
    padding: 0.65rem 1rem;
    background: var(--accent-flow);
    color: var(--ink-0);
    font-family: var(--font-mono);
    font-size: var(--fs-sm);
    font-weight: 700;
    text-decoration: none;
    border-radius: 6px;
    z-index: 1000;
    transition: top var(--dur) var(--ease);
}
.skip-link:focus,
.skip-link:focus-visible {
    top: 1rem;
    color: var(--ink-0);
    outline: 3px solid var(--ink-0);
    outline-offset: 2px;
}

/* --- 5b. Reading-progress bar (top of viewport) ----------------------- */
/* Pure CSS, scroll-driven. On browsers without animation-timeline the
   bar shows its track only (no fill animation); modern Chrome / Edge /
   Firefox 138+ / Safari 26+ animate the gradient fill as the reader
   scrolls the document. Subtle, accent-driven, respects
   prefers-reduced-motion (keyframes disabled by the global override).  */
.reading-progress {
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    height: 3px;
    z-index: 200;
    background: var(--ink-4);
    pointer-events: none;
}
.reading-progress::after {
    content: "";
    display: block;
    height: 100%;
    width: 100%;
    background: linear-gradient(90deg,
                                var(--accent-flow),
                                var(--accent-ac),
                                var(--accent-fr),
                                var(--accent-go));
    transform-origin: left center;
    transform: scaleX(0);
    box-shadow: 0 0 8px color-mix(in srgb, var(--accent-flow) 50%, transparent);
}
@supports (animation-timeline: scroll(root)) {
    .reading-progress::after {
        animation: reading-progress-grow linear forwards;
        animation-timeline: scroll(root);
    }
    @keyframes reading-progress-grow {
        from { transform: scaleX(0); }
        to   { transform: scaleX(1); }
    }
}

/* --- 6. Headings & section structure ---------------------------------- */
h1, h2, h3, h4, h5, h6 {
    margin: 2.25rem 0 0.85rem;
    line-height: 1.25;
    font-weight: 700;
    letter-spacing: -0.015em;
    color: var(--fg-0);
}

h1 {
    font-size: var(--fs-2xl);
    font-weight: 800;
    letter-spacing: -0.025em;
    line-height: 1.15;
    margin-top: 0;
}
h2 {
    font-size: var(--fs-xl);
    border-bottom: 1px solid var(--ink-4);
    padding-bottom: 0.45rem;
}
h3 { font-size: var(--fs-lg); }
h4 { font-size: var(--fs-md); color: var(--fg-1); font-weight: 600; }
h5 { font-size: var(--fs-base); color: var(--fg-1); font-weight: 600; text-transform: uppercase; letter-spacing: 0.08em; }
h6 { font-size: var(--fs-sm); color: var(--fg-2); font-weight: 600; text-transform: uppercase; letter-spacing: 0.08em; }

p { margin: 0.6rem 0 0.85rem; }

ul, ol { padding-left: 1.5rem; margin: 0.6rem 0 1rem; }
li { margin: 0.25rem 0; }
li > p { margin: 0.25rem 0; }

a {
    color: var(--accent-flow);
    text-decoration: none;
    border-bottom: 1px dotted color-mix(in srgb, var(--accent-flow) 50%, transparent);
    transition: color var(--dur-fast) var(--ease),
                border-color var(--dur-fast) var(--ease);
}
a:hover {
    color: color-mix(in srgb, var(--accent-flow) 80%, white);
    border-bottom-color: var(--accent-flow);
    text-decoration: none;
}

hr {
    border: 0;
    border-top: 1px dashed var(--ink-4);
    margin: 2.5rem 0;
}

blockquote {
    margin: 1.25rem 0;
    padding: 0.75rem 1.25rem;
    border-left: 3px solid var(--accent-flow);
    color: var(--fg-1);
    background: var(--ink-2);
    border-radius: 0 6px 6px 0;
    font-style: italic;
}

strong { font-weight: 700; color: var(--fg-0); }
em { color: var(--fg-1); font-style: italic; }

/* --- 7. Code blocks --------------------------------------------------- */
code {
    font-family: var(--font-mono);
    background: var(--code-bg);
    color: var(--code-fg);
    padding: 0.12em 0.4em;
    border-radius: 4px;
    font-size: 0.88em;
    border: 1px solid var(--ink-4);
    font-feature-settings: "calt" 0, "liga" 0;
}

pre {
    background: var(--code-bg);
    color: var(--code-fg);
    padding: 1rem 1.15rem;
    border-radius: 8px;
    overflow-x: auto;
    line-height: 1.55;
    border: 1px solid var(--ink-4);
    margin: 1rem 0 1.25rem;
    font-size: 0.88em;
}
pre code {
    background: transparent;
    padding: 0;
    border: 0;
    border-radius: 0;
    font-size: 1em;
}

/* --- 8. Tables -------------------------------------------------------- */
table {
    border-collapse: separate;
    border-spacing: 0;
    margin: 1.25rem 0;
    width: 100%;
    font-size: var(--fs-sm);
    border: 1px solid var(--ink-4);
    border-radius: 8px;
    overflow: hidden;
}
thead { background: var(--ink-2); }
th, td {
    padding: 0.65rem 0.9rem;
    text-align: left;
    vertical-align: top;
    border-bottom: 1px solid var(--ink-4);
    font-variant-numeric: tabular-nums;
}
th {
    font-family: var(--font-mono);
    font-size: 0.78em;
    font-weight: 600;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    color: var(--fg-1);
    border-bottom: 2px solid var(--ink-5);
}
tbody tr:last-child td { border-bottom: 0; }
tbody tr:nth-child(even) td { background: var(--ink-2); }

/* Compact audit/source tables keep identifiers narrow and prose readable. */
table.audit-log {
    font-size: 0.82rem;
}
table.audit-log th,
table.audit-log td {
    padding: 0.45rem 0.65rem;
    line-height: 1.45;
}
table.audit-log th:first-child,
table.audit-log td:first-child {
    width: 1%;
    white-space: nowrap;
    font-family: var(--font-mono);
}

/* --- 9. Spec header (top of main column) ----------------------------- */
.spec-meta {
    border-bottom: 1px solid var(--ink-4);
    padding-bottom: 1.25rem;
    margin-bottom: 2.5rem;
    color: var(--fg-1);
    font-size: var(--fs-sm);
}
.spec-meta h1 {
    margin-bottom: 0.5rem;
}
.spec-meta p { margin: 0.3rem 0; }


/* --- 10. Section anchors: numbered, dark dividers, target highlight ---- */
section[id] {
    padding: 1.5rem 0 1.75rem;
    border-bottom: 1px dashed var(--ink-4);
    margin-bottom: 0;
    scroll-margin-top: 1.5rem;
    counter-increment: section;
}

section[id]:target {
    background: rgba(88, 166, 255, 0.04);
    border-radius: 6px;
    outline: 1px dashed color-mix(in srgb, var(--accent-flow) 50%, transparent);
    outline-offset: 4px;
}

section[id] h2 {
    display: flex;
    align-items: baseline;
    flex-wrap: wrap;
    gap: 0.75rem;
    border-bottom: 0;
    padding-bottom: 0;
    margin: 0 0 1.25rem;
}

/* Numeric section stamp — replaces the previously hand-typed "1." prefix.
   Empty counter means the agent may have stripped numbers; CSS supplies
   them so the document reads consistently. */
section[id] h2::before {
    content: counter(section, decimal-leading-zero);
    counter-reset: subsection;
    font-family: var(--font-mono);
    font-size: 0.72em;
    font-weight: 700;
    color: var(--fg-3);
    letter-spacing: 0.06em;
    padding: 0.15em 0.5em;
    border: 1px solid var(--ink-4);
    border-radius: 4px;
    background: var(--ink-2);
    flex-shrink: 0;
}

section[id] h3 {
    display: flex;
    align-items: baseline;
    flex-wrap: wrap;
    gap: 0.5rem;
    counter-increment: subsection;
    counter-reset: subsubsection;
}
section[id] h3::before {
    content: counter(section, decimal-leading-zero) "." counter(subsection);
    font-family: var(--font-mono);
    font-size: 0.7em;
    color: var(--fg-3);
    font-weight: 600;
    letter-spacing: 0.04em;
    padding: 0.1em 0.4em;
    border: 1px solid var(--ink-4);
    border-radius: 4px;
    background: var(--ink-2);
    flex-shrink: 0;
}

/* --- 11. Sidebar TOC -------------------------------------------------- */
.sidebar h2 {
    font-size: 0.7rem;
    text-transform: uppercase;
    letter-spacing: 0.16em;
    color: var(--fg-2);
    font-family: var(--font-mono);
    font-weight: 600;
    margin: 0 0 1rem;
    padding-bottom: 0.6rem;
    border-bottom: 1px solid var(--ink-4);
}

.toc {
    list-style: none;
    padding: 0;
    margin: 0 0 1.5rem;
    counter-reset: toc;
}

.toc li {
    counter-increment: toc;
    margin: 0.15rem 0;
    line-height: 1.35;
}

.toc li a {
    display: block;
    padding: 0.45rem 0.6rem 0.45rem 2.5rem;
    color: var(--fg-1);
    text-decoration: none;
    border-radius: 5px;
    border-left: 2px solid transparent;
    transition: background var(--dur-fast) var(--ease),
                border-color var(--dur-fast) var(--ease),
                color var(--dur-fast) var(--ease);
    position: relative;
}
.toc li a::before {
    content: counter(toc, decimal-leading-zero);
    position: absolute;
    left: 0.7rem;
    top: 0.45rem;
    color: var(--fg-3);
    font-size: 0.72em;
    font-weight: 600;
    letter-spacing: 0.04em;
    transition: color var(--dur-fast) var(--ease);
}
.toc li a:hover {
    background: var(--ink-2);
    border-left-color: var(--accent-flow);
    color: var(--fg-0);
}
.toc li a:hover::before {
    color: var(--accent-flow);
}
.toc li a:focus-visible {
    border-left-color: var(--accent-flow);
}


/* --- 12. Chips (mission-stamp status badges) -------------------------- */
.chip {
    --chip-color: var(--fg-2);
    display: inline-flex;
    align-items: center;
    gap: 0.4em;
    padding: 0.18em 0.55em;
    border-radius: 999px;
    font-family: var(--font-mono);
    font-size: 0.74em;
    font-weight: 500;
    line-height: 1.4;
    letter-spacing: 0.01em;
    color: var(--chip-color);
    background: color-mix(in srgb, var(--chip-color) 10%, transparent);
    border: 1px solid color-mix(in srgb, var(--chip-color) 35%, transparent);
    vertical-align: baseline;
    white-space: nowrap;
    transition: background var(--dur-fast) var(--ease),
                border-color var(--dur-fast) var(--ease);
}
.chip::before {
    content: "";
    width: 0.5em;
    height: 0.5em;
    border-radius: 50%;
    background: var(--chip-color);
    flex-shrink: 0;
    box-shadow: 0 0 6px color-mix(in srgb, var(--chip-color) 60%, transparent);
}
.chip:hover {
    background: color-mix(in srgb, var(--chip-color) 18%, transparent);
    border-color: color-mix(in srgb, var(--chip-color) 55%, transparent);
}

.chip-todo   { --chip-color: var(--accent-amber); }
.chip-draft  { --chip-color: var(--accent-amber); }
.chip-ready  { --chip-color: var(--accent-go); }
.chip-ac     { --chip-color: var(--accent-ac); }
.chip-blocked { --chip-color: var(--accent-warn); }

/* Compact chip used inside headings — slightly tighter */
section[id] h2 .chip,
section[id] h3 .chip {
    font-size: 0.62em;
    transform: translateY(-1px);
}

/* --- 13. Callouts ----------------------------------------------------- */
.callout {
    position: relative;
    padding: 1rem 1.25rem 1rem 1.5rem;
    margin: 1.5rem 0 1.75rem;
    border-radius: 6px;
    background: var(--ink-2);
    border: 1px solid var(--ink-4);
    border-left-width: 3px;
    font-size: 0.95rem;
    line-height: 1.65;
}
.callout p { margin: 0.4rem 0; }
.callout p:first-child { margin-top: 0; }
.callout p:last-child  { margin-bottom: 0; }

.callout-title {
    display: inline-block;
    font-family: var(--font-mono);
    font-size: 0.7rem;
    text-transform: uppercase;
    letter-spacing: 0.13em;
    margin-bottom: 0.5rem;
    color: var(--fg-2);
    font-weight: 600;
}


/*
   Callout variant convention:
   .callout-info  = neutral cross-references;
   .callout-note  = authorial instructions (for example, "shape it like this");
   .callout-warn  = defensive boundaries and exclusions;
   .callout-ready = positive status (no blockers, gate cleared, contract honoured).
*/
.callout-note    { border-left-color: var(--fg-2); }
.callout-ready   { border-left-color: var(--accent-go);  background: color-mix(in srgb, var(--accent-go) 6%, var(--ink-2)); }
.callout-warn    { border-left-color: var(--accent-warn); background: color-mix(in srgb, var(--accent-warn) 6%, var(--ink-2)); }
.callout-info    { border-left-color: var(--accent-flow); background: color-mix(in srgb, var(--accent-flow) 6%, var(--ink-2)); }

.callout-ready .callout-title { color: var(--accent-go); }
.callout-warn  .callout-title { color: var(--accent-warn); }
.callout-info  .callout-title { color: var(--accent-flow); }
.callout-note  .callout-title { color: var(--fg-2); }

/* --- 14. Mission stamps (FR / AC / FLOW tokens) ---------------------- */
code.fr, code.ac, code.flow-ref {
    font-family: var(--font-mono);
    font-size: 0.82em;
    font-weight: 600;
    padding: 0.18em 0.5em;
    border-radius: 4px;
    background: var(--bg-token);
    border: 1px solid color-mix(in srgb, currentColor 35%, transparent);
    letter-spacing: 0.02em;
    box-shadow: 0 0 0 1px color-mix(in srgb, currentColor 8%, transparent),
                0 1px 6px -2px color-mix(in srgb, currentColor 50%, transparent);
}

code.fr       { color: var(--accent-fr); }
code.ac       { color: var(--accent-ac); }
code.flow-ref { color: var(--accent-flow); }

code.fr::before, code.ac::before, code.flow-ref::before { content: ""; }

/* Gherkin keywords — Given/When/Then style */
.gherkin-keyword {
    font-weight: 700;
    letter-spacing: 0.04em;
    text-transform: uppercase;
    font-size: 0.78em;
    color: var(--fg-2);
    margin-right: 0.5em;
    padding: 0.06em 0.45em;
    border-radius: 3px;
    background: var(--ink-3);
    border: 1px solid var(--ink-4);
    font-family: var(--font-mono);
}
.gherkin-keyword.given { color: var(--accent-flow); border-color: color-mix(in srgb, var(--accent-flow) 40%, transparent); background: color-mix(in srgb, var(--accent-flow) 10%, transparent); }
.gherkin-keyword.when  { color: var(--accent-amber); border-color: color-mix(in srgb, var(--accent-amber) 40%, transparent); background: color-mix(in srgb, var(--accent-amber) 10%, transparent); }
.gherkin-keyword.then  { color: var(--accent-go); border-color: color-mix(in srgb, var(--accent-go) 40%, transparent); background: color-mix(in srgb, var(--accent-go) 10%, transparent); }

.gherkin p { margin: 0.35rem 0; display: flex; align-items: baseline; gap: 0.25rem; flex-wrap: wrap; }
.gherkin-keyword + * { flex: 1 1 auto; }

/* --- 15. Component-block (TODO placeholder scaffold) ------------------ */
.component-block {
    border: 1px dashed var(--ink-4);
    border-radius: 6px;
    padding: 1.1rem 1.25rem;
    margin: 1rem 0 1.5rem;
    background: color-mix(in srgb, var(--ink-2) 60%, transparent);
    color: var(--fg-2);
    font-size: 0.93rem;
    position: relative;
}
.component-block p { margin: 0.35rem 0; }
.component-block code { background: var(--ink-0); }

.component-label {
    display: inline-block;
    font-family: var(--font-mono);
    font-size: 0.7rem;
    text-transform: uppercase;
    letter-spacing: 0.13em;
    padding: 0.25em 0.7em;
    background: var(--ink-3);
    border: 1px solid var(--ink-4);
    border-radius: 4px;
    color: var(--accent-amber);
    margin-bottom: 0.75rem;
    font-weight: 600;
}

/* --- 16. Diagram-slot (dot-grid schematic placeholder) --------------- */
.diagram-slot {
    position: relative;
    border: 1px dashed var(--ink-4);
    border-radius: 8px;
    padding: 2.5rem 1.5rem;
    margin: 1.5rem 0;
    color: var(--fg-2);
    font-family: var(--font-mono);
    font-size: 0.88rem;
    text-align: center;
    line-height: 1.7;
    overflow: hidden;
    background-color: var(--ink-2);
    background-image: radial-gradient(circle at 14px 14px,
                                      color-mix(in srgb, var(--accent-flow) 18%, transparent) 1px,
                                      transparent 1.5px);
    background-size: 28px 28px;
    background-position: 0 0;
}
.diagram-slot code {
    background: var(--ink-0);
    border-color: var(--ink-5);
}
.diagram-slot .label {
    display: inline-block;
    padding: 0.3rem 0.75rem;
    border-radius: 4px;
    background: var(--ink-1);
    border: 1px solid var(--ink-5);
    color: var(--fg-1);
    font-size: 0.95em;
    font-weight: 600;
    margin-bottom: 0.75rem;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.4);
}

/* --- 17. Cards (FR, AC, ADR, entity, flow, schema, state-machine) ---- */
.fr-card, .ac-card, .adr, .entity-card, .schema-card, .flow-card, .state-machine {
    background: var(--ink-2);
    border: 1px solid var(--ink-4);
    border-radius: 8px;
    padding: 1.25rem 1.4rem;
    margin: 1.25rem 0;
    position: relative;
}
.fr-card::before, .ac-card::before, .adr::before, .entity-card::before, .schema-card::before {
    content: "";
    position: absolute;
    left: 0;
    top: 1rem;
    bottom: 1rem;
    width: 3px;
    border-radius: 0 3px 3px 0;
    background: var(--chip-color, var(--accent-flow));
}
.fr-card { --chip-color: var(--accent-fr); }
.ac-card { --chip-color: var(--accent-ac); }
.adr     { --chip-color: var(--accent-pink); }
.entity-card { --chip-color: var(--accent-go); }
.schema-card { --chip-color: var(--accent-amber); padding-left: calc(1.4rem + 3px); }
.flow-card {
    border-left: 3px solid var(--accent-flow);
    padding-left: 1.4rem;
}
.state-machine {
    border-left: 3px solid var(--accent-amber);
    padding-left: 1.4rem;
}

.fr-card h3, .ac-card h3, .adr h3, .entity-card h3, .schema-card h3, .flow-card h3, .state-machine h3 {
    margin-top: 0;
    display: flex;
    flex-wrap: wrap;
    align-items: baseline;
    gap: 0.5rem;
}
.fr-card h3 code.fr,
.ac-card .chip-ac,
.schema-card h3 code {
    font-size: 0.85em;
}

/* AC list inside FR cards */
.ac-list {
    list-style: none;
    padding: 0;
    margin: 0.5rem 0 0;
}
.ac-list > li {
    padding: 0.85rem 1rem;
    background: var(--ink-1);
    border-radius: 6px;
    border: 1px solid var(--ink-4);
    margin: 0.6rem 0;
}

/* --- 18. Definition lists (.kv) --------------------------------------- */
.kv {
    display: grid;
    grid-template-columns: max-content 1fr;
    gap: 0.4rem 1.25rem;
    margin: 0.5rem 0;
}
.kv dt {
    font-family: var(--font-mono);
    font-size: 0.78em;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: var(--fg-2);
    padding-top: 0.18rem;
    font-weight: 600;
}
.kv dd {
    margin: 0;
    color: var(--fg-1);
}
.kv dd p { margin: 0.25rem 0; }

@media (max-width: 720px) {
    .kv { grid-template-columns: 1fr; gap: 0.15rem 0; }
    .kv dt { margin-top: 0.5rem; }
}

/* --- 18b. Shared authoring surfaces ------------------------------------ */
/* These patterns are available in every phase starter, not just the file
   that first demonstrated them. */
.component-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
    gap: 0.85rem;
    list-style: none;
    padding: 0;
    margin: 1rem 0 1.25rem;
}
.component-grid > * {
    min-width: 0;
    margin: 0;
    padding: 1rem 1.1rem;
    background: var(--ink-2);
    border: 1px solid var(--ink-4);
    border-radius: 8px;
}

.flow-list {
    display: grid;
    gap: 0.6rem;
    list-style: none;
    padding: 0;
    margin: 1rem 0 1.25rem;
}
.flow-list > li {
    margin: 0;
    padding: 0.7rem 0.9rem 0.7rem 1rem;
    background: var(--ink-2);
    border: 1px solid var(--ink-4);
    border-left: 3px solid var(--accent-flow);
    border-radius: 6px;
}

.principle-list {
    list-style: none;
    padding: 0;
    margin: 1rem 0 1.25rem;
    counter-reset: principle;
}
.principle-list > li {
    counter-increment: principle;
    position: relative;
    margin: 0.55rem 0;
    padding: 0.75rem 1rem 0.75rem 3rem;
    background: var(--ink-2);
    border: 1px solid var(--ink-4);
    border-radius: 6px;
}
.principle-list > li::before {
    content: counter(principle, decimal-leading-zero);
    position: absolute;
    left: 1rem;
    top: 0.75rem;
    color: var(--accent-flow);
    font-family: var(--font-mono);
    font-size: 0.75em;
    font-weight: 700;
    padding: 0.18em 0.45em;
    border: 1px solid var(--ink-4);
    border-radius: 4px;
    background: var(--ink-1);
}

.contract-block {
    margin: 1rem 0 1.5rem;
    padding: 1rem 1.25rem;
    background: color-mix(in srgb, var(--accent-ac) 5%, var(--ink-2));
    border: 1px solid color-mix(in srgb, var(--accent-ac) 30%, var(--ink-4));
    border-left: 3px solid var(--accent-ac);
    border-radius: 6px;
}
.contract-block > :first-child { margin-top: 0; }
.contract-block > :last-child { margin-bottom: 0; }

.op-signature {
    display: block;
    margin: 0.65rem 0;
    padding: 0.65rem 0.8rem;
    overflow-x: auto;
    background: var(--ink-0);
    border: 1px solid var(--ink-4);
    color: var(--accent-ac);
    font-family: var(--font-mono);
    white-space: pre-wrap;
}

.order-steps {
    list-style: none;
    padding: 0;
    margin: 1rem 0 1.25rem;
    counter-reset: order-step;
}
.order-steps > li {
    counter-increment: order-step;
    position: relative;
    margin: 0.5rem 0;
    padding: 0.85rem 1rem 0.85rem 3rem;
    background: var(--ink-2);
    border: 1px solid var(--ink-4);
    border-radius: 6px;
}
.order-steps > li::before {
    content: counter(order-step, decimal-leading-zero);
    position: absolute;
    left: 1rem;
    top: 0.85rem;
    color: var(--accent-ac);
    font-family: var(--font-mono);
    font-size: 0.75em;
    font-weight: 700;
    padding: 0.18em 0.45em;
    border: 1px solid var(--ink-4);
    border-radius: 4px;
    background: var(--ink-1);
}

.component-grid > .component-block {
    margin: 0;
}

.component-grid + .component-grid {
    margin-top: 0.85rem;
}


/* --- 19. State pills -------------------------------------------------- */
.state-pill {
    display: inline-block;
    padding: 0.22em 0.65em;
    border-radius: 3px;
    font-family: var(--font-mono);
    font-size: 0.78em;
    font-weight: 600;
    background: var(--ink-3);
    color: var(--fg-1);
    border: 1px solid var(--ink-4);
    letter-spacing: 0.02em;
}
.state-pill.initial  {
    color: var(--accent-flow);
    border-color: color-mix(in srgb, var(--accent-flow) 45%, transparent);
    background: color-mix(in srgb, var(--accent-flow) 10%, transparent);
}
.state-pill.terminal {
    color: var(--accent-warn);
    border-color: color-mix(in srgb, var(--accent-warn) 45%, transparent);
    background: color-mix(in srgb, var(--accent-warn) 10%, transparent);
}
.state-pill.active   {
    color: var(--accent-go);
    border-color: color-mix(in srgb, var(--accent-go) 45%, transparent);
    background: color-mix(in srgb, var(--accent-go) 10%, transparent);
}

/* --- 20. Readiness checklist ------------------------------------------ */
.readiness-list {
    list-style: none;
    padding: 0;
    margin: 0.5rem 0 1.25rem;
}
.readiness-list li {
    display: flex;
    align-items: baseline;
    gap: 0.65rem;
    padding: 0.45rem 0;
    border-bottom: 1px dashed var(--ink-4);
    color: var(--fg-1);
}
.readiness-list li:last-child { border-bottom: 0; }
.readiness-list input[type="checkbox"] {
    accent-color: var(--accent-go);
    flex-shrink: 0;
    width: 1em;
    height: 1em;
    transform: translateY(2px);
}

/* --- 21. Strategy/workstation/data-flow lists ------------------------ */
.strategy-steps, .workstation-list, .dataflow-steps, .risk-surfaces, .dataflow-trace {
    list-style: none;
    padding: 0;
    margin: 0.5rem 0 1.25rem;
    counter-reset: steps;
}
.strategy-steps > li, .workstation-list > li, .dataflow-steps > li, .risk-surfaces > li, .dataflow-trace > li {
    counter-increment: steps;
    margin: 0.5rem 0;
    padding: 0.85rem 1rem 0.85rem 3rem;
    background: var(--ink-2);
    border: 1px solid var(--ink-4);
    border-radius: 6px;
    position: relative;
}
.strategy-steps > li::before,
.workstation-list > li::before,
.dataflow-steps > li::before,
.dataflow-trace > li::before {
    content: counter(steps, decimal-leading-zero);
    position: absolute;
    left: 1rem;
    top: 0.85rem;
    font-family: var(--font-mono);
    font-size: 0.75em;
    font-weight: 700;
    color: var(--accent-flow);
    padding: 0.18em 0.45em;
    border: 1px solid var(--ink-4);
    border-radius: 4px;
    background: var(--ink-1);
    letter-spacing: 0.04em;
}

.risk-surfaces > li {
    padding: 0.65rem 1rem 0.65rem 1rem;
    list-style: none;
}

/* --- 22. Risk severity (text-only badge classes) --------------------- */
.risk-high, .risk-medium, .risk-low {
    display: inline-block;
    padding: 0.18em 0.55em;
    border-radius: 3px;
    font-family: var(--font-mono);
    font-size: 0.78em;
    font-weight: 600;
    letter-spacing: 0.02em;
    border: 1px solid transparent;
}
.risk-low {
    color: var(--accent-go);
    background: color-mix(in srgb, var(--accent-go) 10%, transparent);
    border-color: color-mix(in srgb, var(--accent-go) 40%, transparent);
}
.risk-medium {
    color: var(--accent-amber);
    background: color-mix(in srgb, var(--accent-amber) 10%, transparent);
    border-color: color-mix(in srgb, var(--accent-amber) 40%, transparent);
}
.risk-high {
    color: var(--accent-warn);
    background: color-mix(in srgb, var(--accent-warn) 10%, transparent);
    border-color: color-mix(in srgb, var(--accent-warn) 40%, transparent);
}

/* --- 23. Flow catalog (grid of cards) -------------------------------- */
.flow-catalog {
    list-style: none;
    padding: 0;
    margin: 1rem 0 1.5rem;
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
    gap: 0.85rem;
}
.flow-catalog > li {
    margin: 0;
}
.flow-catalog > li > a {
    display: block;
    padding: 1rem 1.1rem;
    background: var(--ink-2);
    border: 1px solid var(--ink-4);
    border-radius: 8px;
    color: var(--fg-0);
    text-decoration: none;
    transition: border-color var(--dur-fast) var(--ease),
                background var(--dur-fast) var(--ease),
                transform var(--dur-fast) var(--ease);
    height: 100%;
}
.flow-catalog > li > a:hover {
    border-color: var(--accent-flow);
    background: color-mix(in srgb, var(--accent-flow) 8%, var(--ink-2));
    transform: translateY(-1px);
}
.flow-catalog .flow-id {
    display: block;
    margin-bottom: 0.35rem;
}
.flow-catalog .flow-name {
    display: block;
    font-weight: 600;
    color: var(--fg-0);
    margin-bottom: 0.35rem;
    line-height: 1.35;
}
.flow-catalog .flow-meta {
    display: block;
    font-family: var(--font-mono);
    font-size: 0.74em;
    color: var(--fg-2);
    line-height: 1.5;
}

/* --- 24. Print styles (PDF export friendliness) ---------------------- */
@media print {
    :root {
        --bg: #ffffff;
        --fg: #000000;
        --ink-1: #ffffff;
        --ink-2: #f5f5f5;
        --ink-3: #ececec;
        --ink-4: #d0d0d0;
        --ink-5: #b0b0b0;
        --fg-0: #000000;
        --fg-1: #222222;
        --fg-2: #555555;
        --fg-3: #888888;
        color-scheme: light;
    }
    body { background: #fff !important; background-image: none !important; }
    .sidebar {
        position: static;
        max-height: none;
        page-break-after: avoid;
    }
    .layout {
        display: block;
        max-width: 100%;
        padding: 1rem;
    }
    .main { max-width: 100%; }
    section[id] {
        page-break-inside: avoid;
        border-bottom: 1px solid #999;
    }
    section[id] h2::before,
    section[id] h3::before {
        background: #f5f5f5;
        color: #000;
    }
    .chip, .state-pill {
        border: 1px solid #999 !important;
    }
    .chip::before { display: none; }
    .callout {
        background: #f5f5f5;
        border-color: #999;
    }
    .diagram-slot {
        background: #fafafa !important;
        border-style: solid;
    }
}
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
        "prd": "Product Requirements",
        "plan": "Implementation Plan",
    }[phase]


_SECTION_TAG_RE = re.compile(r'<section\b[^>]*\bid="[^"]+"', re.IGNORECASE)


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
    # placeholders (FR token schemas, ID list items, etc.) that would be
    # interpreted as format placeholders. All substitution slots use
    # unambiguous sentinels and a single replacement pass.
    section_count = len(_SECTION_TAG_RE.findall(template_text))
    if section_count == 0:
        raise ValueError(f"template for {phase!r} contains no section anchors")
    rendered = template_text
    rendered = rendered.replace("<<TITLE>>", _phase_title(phase))
    rendered = rendered.replace("<<PHASE_TITLE>>", _phase_title(phase))
    rendered = rendered.replace("<<SOURCE_MD>>", str(source_md))
    rendered = rendered.replace("<<CSS>>", _CSS)
    return rendered
