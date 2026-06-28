from __future__ import annotations

import importlib.resources as resources
import logging
import re
from pathlib import Path

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Layer routing
# ---------------------------------------------------------------------------

_LAYER_MAP: dict[str, str | None] = {
    # Macro layer — auto prefix (CLI orchestrates pre/post)
    "explore": "macro-auto",
    "research": "macro-auto",
    "prd": "macro-auto",
    "shard": "macro-auto",
    "specify": "macro-auto",
    # Meso layer — auto prefix
    "plan": "meso-auto",
    "tasks": "meso-auto",
    # Micro layer — auto prefix
    "red": "micro-auto",
    "green": "micro-auto",
    "refactor": "micro-auto",
    "yellow": "micro-auto",
    "judge": "micro-auto",
    "execute": "micro-auto",
}

# Slash commands live as package resources under `src/deviate/prompts/commands/<name>.md`
# and are installed to `<workdir>/.<agent>/commands/<name>.md` by `deviate setup`.
# No `.sh` wrappers in `prompts/` — every template is loaded with `importlib.resources.files()`.

_CORE_DIR = "deviate.prompts.core"
_AUTO_DIR = "deviate.prompts.auto"


def _read_resource(package: str, filename: str) -> str | None:
    path = resources.files(package) / filename
    if path.is_file():
        return path.read_text(encoding="utf-8")
    return None


def load_template(
    template_name: str,
    constitution_path: Path | None = None,
) -> str:
    """Load and compose a prompt template from its constituent parts.

    Assembly order::

        specs/constitution.md  — project governance (from *constitution_path*)
        core/core.md           — universal invariants (shared by ALL phases)
        core/{layer}.md        — layer-specific preamble (macro / meso / micro)
        auto/{template}.md     — phase-specific instructions

    Constitution and layer files are optional — if they don't exist the
    remaining tiers are used standalone.
    """
    parts: list[str] = []

    # 0. Constitution (project governance) — optional
    if constitution_path is not None:
        try:
            constitution_content = constitution_path.read_text(encoding="utf-8")
            parts.append(constitution_content)
        except OSError as exc:
            logger.warning("CONSTITUTION_MISSING: %s: %s", constitution_path, exc)

    # 1. Universal core
    core = _read_resource(_CORE_DIR, "core.md")
    if core:
        parts.append(core)

    # 2. Layer-specific preamble
    layer = _LAYER_MAP.get(template_name)
    if layer:
        layer_content = _read_resource(_CORE_DIR, f"{layer}.md")
        if layer_content:
            parts.append(layer_content)

    # 3. Phase-specific template
    phase = _read_resource(_AUTO_DIR, f"{template_name}.md")
    if not phase:
        raise FileNotFoundError(f"Template '{template_name}' not found in {_AUTO_DIR}")
    parts.append(phase)

    return "\n\n".join(parts)


def inject_constitution(
    prompt: str,
    constitution_path: Path,
) -> str:
    try:
        constitution_content = constitution_path.read_text(encoding="utf-8")
    except OSError as exc:
        logger.warning("CONSTITUTION_MISSING: %s: %s", constitution_path, exc)
        return prompt

    return f"{constitution_content}\n\n{prompt}"


_PLACEHOLDER_RE = re.compile(r"\$\{(.+?)\}|\$(\w+)|{(.+?)}")


def _replace_placeholder(match: re.Match[str], context: dict[str, str]) -> str:
    key = match.group(1) or match.group(2) or match.group(3)
    return context.get(key, match.group(0))


def assemble_prompt(
    template_name: str,
    context: dict[str, str],
    constitution_path: Path,
) -> str:
    prompt = load_template(template_name, constitution_path=constitution_path)
    prompt = _PLACEHOLDER_RE.sub(lambda m: _replace_placeholder(m, context), prompt)
    return prompt
