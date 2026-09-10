from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from pydantic import ValidationError

from deviate.state.ledger import CriterionLink, TaskRecord


_TASK_LINE_PATTERN = re.compile(r"^\s*-\s+(?:\[(?:x| )\]\s+)?(TSK-\d{3}-\d{2}):\s*(.+)")
_MODE_PATTERN = re.compile(r"\*\*Mode\*\*:\s*(\S+)")
_TYPE_PATTERN = re.compile(r"\*\*Type\*\*:\s*(\S+)")
_STRATEGY_PATTERN = re.compile(r"\*\*Test Strategy\*\*:\s*`?(\S+)`?")
_CRITERIA_LINE_PATTERN = re.compile(r"^\s*-\s*\*\*Acceptance Criteria\*\*:\s*(.+)")
_LINK_PATTERN = re.compile(r"^(AC-PLAN-\d{3})\s*\(([^)]*)\)$")
_CRITERIA_ENTRY_SPLIT: re.Pattern[str] = re.compile(r",\s*(?=AC-PLAN-\d{3}\s*\()")

TEST_STRATEGIES = frozenset({"unit", "integration", "e2e"})

# Modes that are not a Red-Green-Refactor cycle. Closing [VERIFY] / [E2E]
# Verification_Batch cards are IMMEDIATE and may name the full ladder.
_NON_TDD_MODES = frozenset({"IMMEDIATE", "EXECUTE", "DIRECT"})
_LAYER_TOKEN_RE = re.compile(r"\b(unit|integration|integ|e2e)\b", re.IGNORECASE)
_MISE_LAYER_RE = re.compile(
    r"\bmise\s+(?:exec\s+--\s+)?(unit|integration|integ|e2e)\b",
    re.IGNORECASE,
)
_FIELD_RE = re.compile(r"^\s*-\s+\*\*([^*]+)\*\*:\s*(.*)$")
_FILE_ITEM_RE = re.compile(r"^\s+-\s+`?([^`]+?)`?\s*$")
_COMMAND_SPLIT_RE = re.compile(r"\s*(?:&&|\|\||;)\s*")
_E2E_PATH_PREFIXES = ("tests/e2e", "test/e2e", "e2e")
_INTEG_PATH_PREFIXES = (
    "tests/integration",
    "tests/integ",
    "test/integration",
    "test/integ",
)
_UNIT_PATH_PREFIXES = ("tests/unit",)
_ELIXIR_UNIT_PREFIX = "test"


class MixedTestLayerError(ValueError):
    """A TDD card names more than one of ``unit`` / ``integration`` / ``e2e``."""

    def __init__(self, task_id: str, layers: set[str]) -> None:
        ordered = [name for name in ("unit", "integration", "e2e") if name in layers]
        if len(ordered) == 2:
            named = f"both {ordered[0]} and {ordered[1]}"
        else:
            named = ", ".join(ordered[:-1]) + f", and {ordered[-1]}"
        super().__init__(
            f"MIXED_TEST_LAYER: {task_id} names {named}. "
            "Split into two TDD tasks (one Test Strategy, one write dir, "
            "one verification command)."
        )
        self.task_id = task_id
        self.layers = frozenset(layers)


def parse_test_strategy(value: str | None) -> str | None:
    """Return ``unit``, ``integration``, or ``e2e``; drop retired runner values.

    ``Sociable_Unit`` / ``Solitary_Unit`` are not verification buckets.
    """
    if not value or not isinstance(value, str):
        return None
    normalized = value.strip().strip("`").strip("*").rstrip(".").lower()
    if normalized in TEST_STRATEGIES:
        return normalized
    return None


# Hard type→mode lock. Verification_Batch is not a Red-Green-Refactor cycle
# (api.md / architecture.md: EXECUTE / IMMEDIATE). Other types keep the
# planner-declared Mode so adhoc/plan can still pick TDD vs IMMEDIATE.
IMMEDIATE_TASK_TYPES = frozenset({"Verification_Batch"})


def resolve_execution_mode(
    task_type: str | None,
    declared_mode: str = "TDD",
) -> str:
    """Return the execution mode for a task type.

    ``Verification_Batch`` is always ``IMMEDIATE``. Every other type (or a
    missing type) keeps *declared_mode*.
    """
    if task_type in IMMEDIATE_TASK_TYPES:
        return "IMMEDIATE"
    return declared_mode


@dataclass
class _TaskBlock:
    task_id: str
    description: str
    execution_mode: str = "TDD"
    task_type: str | None = None
    test_strategy: str | None = None
    criteria_entries: list[str] = field(default_factory=list)


def generate_jsonl_from_md(tasks_md: Path, issue_id: str) -> list[TaskRecord]:
    content = tasks_md.read_text(encoding="utf-8")
    blocks: list[_TaskBlock] = []
    current: _TaskBlock | None = None

    for line in content.splitlines():
        task_match = _TASK_LINE_PATTERN.match(line)
        if task_match:
            if current is not None:
                blocks.append(current)
            current = _TaskBlock(
                task_id=task_match.group(1),
                description=task_match.group(2).strip(),
            )
        elif current is not None:
            type_match = _TYPE_PATTERN.search(line)
            if type_match:
                current.task_type = type_match.group(1)
            mode_match = _MODE_PATTERN.search(line)
            if mode_match:
                current.execution_mode = mode_match.group(1)
            strategy_match = _STRATEGY_PATTERN.search(line)
            if strategy_match:
                current.test_strategy = parse_test_strategy(strategy_match.group(1))
            criteria_match = _CRITERIA_LINE_PATTERN.search(line)
            if criteria_match:
                current.criteria_entries = _parse_criteria_entries(
                    criteria_match.group(1)
                )
    if current is not None:
        blocks.append(current)

    return [
        _build_task_record(
            task_id=block.task_id,
            issue_id=issue_id,
            description=block.description,
            execution_mode=resolve_execution_mode(
                block.task_type, block.execution_mode
            ),
            test_strategy=block.test_strategy,
            criteria_entries=block.criteria_entries,
        )
        for block in blocks
    ]


def _parse_criteria_entries(text: str) -> list[str]:
    return [
        entry.strip() for entry in _CRITERIA_ENTRY_SPLIT.split(text) if entry.strip()
    ]


def _build_task_record(
    task_id: str,
    issue_id: str,
    description: str | None,
    execution_mode: str,
    criteria_entries: list[str] | None = None,
    test_strategy: str | None = None,
) -> TaskRecord:
    links: list[CriterionLink] | None = None
    if criteria_entries:
        links = [_parse_criterion_link(task_id, entry) for entry in criteria_entries]
    return TaskRecord(
        id=task_id,
        issue_id=issue_id,
        description=description or "",
        status="PENDING",
        execution_mode=execution_mode,
        test_strategy=test_strategy,  # type: ignore[arg-type]
        acceptance_criteria=links,
    )


def _parse_criterion_link(task_id: str, entry: str) -> CriterionLink:
    match = _LINK_PATTERN.match(entry)
    if match is None:
        raise ValueError(
            f"Unparseable acceptance criteria entry for task {task_id}: {entry}"
        )
    inner = match.group(2)
    if not inner or not inner.strip():
        raise ValueError(
            f"Unparseable acceptance criteria entry for task {task_id}: {entry}"
        )
    parts = [p.strip() for p in inner.split(",")]
    if len(parts) > 2 or not parts[0]:
        raise ValueError(
            f"Malformed acceptance criteria entry for task {task_id}: {entry}"
        )
    verification_mode = parts[0]
    test_ref = parts[1] if len(parts) > 1 and parts[1] else None
    return CriterionLink(
        criterion_id=match.group(1),
        verification_mode=verification_mode,
        test_ref=test_ref,
    )


def validate_tdd_task_layers(tasks_md: Path) -> None:
    """Reject TDD cards that name more than one verification layer.

    Called from ``deviate tasks post`` when Tasks writes ``tasks.md``.
    ``generate_jsonl_from_md`` does **not** call this — historical mixed
    cards (e.g. wallet-service TSK-001-02) must still parse.

    A card is mixed when **Test Strategy**, **Files**, or **Verification**
    together name more than one of ``unit`` / ``integration`` / ``e2e``.
    Details / Rationale are not scanned (unit cards say "forbid
    ``tests/integration``"). ``Verification_Batch`` and IMMEDIATE /
    EXECUTE / DIRECT cards are exempt so issue-end ``[VERIFY]`` / ``[E2E]``
    sweeps may still run the ladder. Flat ``tests/test_foo.py`` and
    ``mise test`` are not layers.
    """
    content = tasks_md.read_text(encoding="utf-8")
    for task_id, card in _iter_task_cards(content):
        fields = _card_fields(card)
        if not _is_tdd_card(fields):
            continue
        layers: set[str] = set()
        for value in fields.get("test strategy", []):
            layers.update(_layers_from_strategy_value(value))
        for value in fields.get("files", []):
            layer = _layer_from_relpath(value)
            if layer is not None:
                layers.add(layer)
        for value in fields.get("verification", []):
            layers.update(_layers_from_command(value))
        if len(layers) > 1:
            raise MixedTestLayerError(task_id, layers)


def _iter_task_cards(content: str) -> list[tuple[str, str]]:
    lines = content.splitlines()
    starts: list[tuple[int, str]] = []
    for index, line in enumerate(lines):
        match = _TASK_LINE_PATTERN.match(line)
        if match:
            starts.append((index, match.group(1)))
    cards: list[tuple[str, str]] = []
    for idx, (start, task_id) in enumerate(starts):
        end = len(lines)
        if idx + 1 < len(starts):
            end = starts[idx + 1][0]
        else:
            for cursor in range(start + 1, len(lines)):
                if lines[cursor].startswith("## ") or lines[cursor].startswith("---"):
                    end = cursor
                    break
        cards.append((task_id, "\n".join(lines[start:end])))
    return cards


def _card_fields(card: str) -> dict[str, list[str]]:
    """Top-level ``**Field**`` values. Nested Details bullets are ignored."""
    values: dict[str, list[str]] = {}
    current: str | None = None
    collect_items = False
    for line in card.splitlines():
        field = _FIELD_RE.match(line)
        if field:
            name = field.group(1).strip().lower()
            rest = field.group(2).strip()
            current = name
            collect_items = name in {"files", "verification", "test strategy"}
            values.setdefault(name, [])
            if rest:
                if name == "files":
                    values[name].extend(
                        part.strip().strip("`")
                        for part in rest.split(",")
                        if part.strip().strip("`")
                    )
                else:
                    values[name].append(rest)
            continue
        if collect_items and current is not None:
            item = _FILE_ITEM_RE.match(line)
            if item:
                values[current].append(item.group(1).strip())
    return values


def _first_field(fields: dict[str, list[str]], name: str) -> str | None:
    values = fields.get(name)
    if not values:
        return None
    return values[0].strip().strip("`").split()[0] if values[0].strip() else None


def _is_tdd_card(fields: dict[str, list[str]]) -> bool:
    task_type = _first_field(fields, "type")
    declared = _first_field(fields, "mode") or "TDD"
    if declared.upper() in _NON_TDD_MODES:
        return False
    return resolve_execution_mode(task_type, declared) != "IMMEDIATE"


def _normalize_layer_token(token: str) -> str:
    lowered = token.lower()
    return "integration" if lowered == "integ" else lowered


def _layers_from_strategy_value(value: str) -> set[str]:
    return {
        _normalize_layer_token(match.group(1))
        for match in _LAYER_TOKEN_RE.finditer(value)
    }


def _path_has_prefix(path: str, prefix: str) -> bool:
    return path == prefix or path.startswith(prefix + "/")


def _layer_from_relpath(raw: str) -> str | None:
    path = raw.strip().strip("`").strip().replace("\\", "/").lstrip("./")
    if not path:
        return None
    for prefix in _E2E_PATH_PREFIXES:
        if _path_has_prefix(path, prefix):
            return "e2e"
    for prefix in _INTEG_PATH_PREFIXES:
        if _path_has_prefix(path, prefix):
            return "integration"
    for prefix in _UNIT_PATH_PREFIXES:
        if _path_has_prefix(path, prefix):
            return "unit"
    if _path_has_prefix(path, _ELIXIR_UNIT_PREFIX):
        return "unit"
    return None


def _layers_from_command(command: str) -> set[str]:
    layers: set[str] = set()
    for part in _COMMAND_SPLIT_RE.split(command):
        stripped = part.split("#", 1)[0]
        for match in _MISE_LAYER_RE.finditer(stripped):
            layers.add(_normalize_layer_token(match.group(1)))
        for token in re.findall(r"[^\s`]+", stripped):
            layer = _layer_from_relpath(token)
            if layer is not None:
                layers.add(layer)
    return layers


def validate_tasks_jsonl(records: list[dict]) -> list[str]:
    errors: list[str] = []
    for i, record in enumerate(records):
        try:
            TaskRecord.model_validate(record)
        except ValidationError as e:
            for err in e.errors():
                loc = ".".join(str(part) for part in err["loc"])
                errors.append(f"Record {i}: {loc}: {err['msg']}")
    return errors
