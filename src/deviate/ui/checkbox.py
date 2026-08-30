"""TTY checkbox multi-select built on Rich (no extra prompt framework)."""

from __future__ import annotations

import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Literal

from rich.console import Console, Group, RenderableType
from rich.text import Text

Action = Literal["continue", "confirm"]


@dataclass
class CheckboxSession:
    """In-memory checkbox list: Space toggles, Enter confirms.

    Default selection is empty (nothing checked). ``picked()`` returns
    names in *options* order so the caller never depends on set iteration.
    Lone ESC is ignored (not confirm) so a missed arrow decode cannot exit.
    """

    options: tuple[str, ...]
    selected: set[str] = field(default_factory=set)
    cursor: int = 0

    def apply(self, key: str) -> Action:
        if not self.options:
            return "confirm"
        if key in {"enter", "\r", "\n"}:
            return "confirm"
        if key in {"space", " "}:
            name = self.options[self.cursor]
            if name in self.selected:
                self.selected.discard(name)
            else:
                self.selected.add(name)
            return "continue"
        if key in {"up", "k", "K"}:
            self.cursor = (self.cursor - 1) % len(self.options)
            return "continue"
        if key in {"down", "j", "J"}:
            self.cursor = (self.cursor + 1) % len(self.options)
            return "continue"
        return "continue"

    def picked(self) -> list[str]:
        return [name for name in self.options if name in self.selected]


def render_checkbox_session(title: str, session: CheckboxSession) -> Group:
    """Build the checklist renderable (one option per row)."""
    lines: list[Text] = [Text(title, style="bold")]
    for index, name in enumerate(session.options):
        mark = "x" if name in session.selected else " "
        prefix = ">" if index == session.cursor else " "
        line = Text(f"{prefix} [{mark}] {name}")
        if index == session.cursor:
            line.stylize("bold cyan")
        lines.append(line)
    lines.append(Text("Space toggles · Enter confirms (default: none)", style="dim"))
    return Group(*lines)


def _arrow_from_sequence(data: str) -> str | None:
    """Map CSI (``[A``/``[B``) or SS3 (``OA``/``OB``) to up/down.

    Accepts a tail after ESC, a leftover ``[A`` chunk, or the full
    three-byte sequence ``\\x1b[A`` / ``\\x1bOA``.
    """
    if not data:
        return None
    seq = data[1:] if data.startswith("\x1b") else data
    if seq in {"[A", "OA"} or seq.endswith("[A") or seq.endswith("OA"):
        return "up"
    if seq in {"[B", "OB"} or seq.endswith("[B") or seq.endswith("OB"):
        return "down"
    return None


def _read_escape_tail(fd: int) -> str:
    """Read the rest of an ESC sequence without a select() race.

    After the first byte is already consumed, VMIN=0 VTIME=1 waits up to
    0.1s per read for the CSI/SS3 tail (``[A`` / ``OA`` / …).
    """
    import termios

    attrs = termios.tcgetattr(fd)
    attrs[6][termios.VMIN] = 0
    attrs[6][termios.VTIME] = 1
    termios.tcsetattr(fd, termios.TCSANOW, attrs)
    parts: list[str] = []
    while True:
        piece = sys.stdin.read(8)
        if not piece:
            break
        parts.append(piece)
        joined = "".join(parts)
        if _arrow_from_sequence(joined) is not None:
            break
        if len(joined) >= 8:
            break
    return "".join(parts)


def _read_key_posix() -> str:
    import termios
    import tty

    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        ch = sys.stdin.read(1)
        if ch == "\x03":
            raise KeyboardInterrupt
        if ch == "\x04":
            raise EOFError
        if ch in {"\r", "\n"}:
            return "enter"
        if ch == " ":
            return "space"
        if ch == "\x1b" or ch in {"[", "O"}:
            tail = _read_escape_tail(fd)
            mapped = _arrow_from_sequence(ch + tail)
            if mapped is not None:
                return mapped
            return "esc" if ch == "\x1b" else ch
        return ch
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)


def _read_key_windows() -> str:
    import msvcrt

    ch = msvcrt.getwch()
    if ch in {"\r", "\n"}:
        return "enter"
    if ch == " ":
        return "space"
    if ch == "\x03":
        raise KeyboardInterrupt
    if ch in {"\x00", "\xe0"}:
        extra = msvcrt.getwch()
        if extra == "H":
            return "up"
        if extra == "P":
            return "down"
        return "esc"
    if ch == "\x1b":
        return "esc"
    return ch


def _read_key() -> str:
    if sys.platform == "win32":
        return _read_key_windows()
    return _read_key_posix()


def checkbox_select(
    options: Sequence[str],
    *,
    title: str = "Select",
    console: Console | None = None,
    read_key: Callable[[], str] | None = None,
) -> list[str]:
    """One option per row. Space toggles; Enter confirms. Default: none.

    ``read_key`` is a no-arg callable used by tests to drive the loop
    without a real TTY. Production leaves it unset and reads stdin.
    """
    if not options:
        return []
    session = CheckboxSession(options=tuple(options))
    key_fn: Callable[[], str] = read_key if read_key is not None else _read_key

    def _run_loop(on_change: Callable[[], None] | None = None) -> list[str]:
        while True:
            if session.apply(key_fn()) == "confirm":
                return session.picked()
            if on_change is not None:
                on_change()

    if read_key is not None:
        return _run_loop()

    from rich.live import Live

    c = console or Console()

    def _frame() -> RenderableType:
        return render_checkbox_session(title, session)

    with Live(_frame(), console=c, auto_refresh=False, transient=True) as live:
        return _run_loop(lambda: live.update(_frame(), refresh=True))
