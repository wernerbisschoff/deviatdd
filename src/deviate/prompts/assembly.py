from __future__ import annotations

import importlib.resources as resources
import logging
import re
from pathlib import Path

logger = logging.getLogger(__name__)


_LAYER_MAP: dict[str, str | None] = {
    "explore": "macro",
    "research": "macro",
    "prd": "macro",
    "shard": "macro",
    "plan": "meso",
    "tasks": "meso",
    "red": "micro",
    "green": "micro",
    "refactor": "micro",
    "judge": "micro",
    "execute": "micro",
}


_CORE_DIR = "deviate.prompts.core"
_AUTO_DIR = "deviate.prompts.auto"

# Injected only when ``[log].agent_reasons = true``. Default prompts must
# not mention logging, ``deviate log``, or writing a reason file.
AGENT_REASONS_BLOCK = (
    "## Agent rationale\n"
    "Emit a one-line handover `rationale` for the route you chose.\n"
    "For JUDGE, say why `revert_red` (the test is wrong; discard RED and "
    "GREEN) versus `revert_green` (the test is honest; discard GREEN only).\n"
    "Use the existing `rationale` / `train_feedback` handover fields.\n"
)


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

        specs/constitution.md       — project governance (from *constitution_path*)
        core/core.md                — universal invariants (shared by ALL phases)
        core/{layer}-shared.md      — layer-specific disciplines (shared auto/manual)
        core/lifecycle-auto.md      — orchestrator lifecycle block (auto mode)
        auto/{template}.md          — phase-specific instructions

    Constitution is optional — if it doesn't exist the remaining tiers are used standalone.
    Manual slash-command composition goes through ``deviate.core.commands.compose_command_body``.
    """
    parts: list[str] = []

    # 0.
    if constitution_path is not None:
        try:
            constitution_content = constitution_path.read_text(encoding="utf-8")
            parts.append(constitution_content)
        except OSError as exc:
            logger.warning("CONSTITUTION_MISSING: %s: %s", constitution_path, exc)

    # 1.
    core = _read_resource(_CORE_DIR, "core.md")
    if core:
        parts.append(core)

    # 2.
    layer = _LAYER_MAP.get(template_name)
    if layer:
        layer_content = _read_resource(_CORE_DIR, f"{layer}-shared.md")
        if layer_content:
            parts.append(layer_content)

    # 3.
    lifecycle = _read_resource(_CORE_DIR, "lifecycle-auto.md")
    if lifecycle:
        parts.append(lifecycle)

    # 4.
    style = _read_resource(_CORE_DIR, "style-ste.md")
    if style:
        parts.append(style)

    # 5.
    if template_name == "plan":
        from deviate.prompts.handover import format_handover_checklist

        parts.append(format_handover_checklist())

    # 6.
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
    from deviate.state.config import resolve_agent_reasons

    root = constitution_path.parent.parent
    if resolve_agent_reasons(root):
        prompt = prompt.rstrip() + "\n\n" + AGENT_REASONS_BLOCK
    return prompt
