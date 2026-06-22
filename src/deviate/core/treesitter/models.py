from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class SymbolChange:
    language: str
    kind: str
    name: str
    change: str
    old_name: str = ""
    start_line: int = 0
    end_line: int = 0
    old_start_line: int = 0
    old_end_line: int = 0
    old_signature: str = ""
    new_signature: str = ""
    old_line_count: int = 0
    new_line_count: int = 0


@dataclass
class DuplicateBlock:
    lines: int
    locations: list[str]
    similarity: float


@dataclass
class FileStructure:
    filepath: str
    language: str
    symbols: list[dict[str, str | int]] = field(default_factory=list)
    imports: list[str] = field(default_factory=list)
