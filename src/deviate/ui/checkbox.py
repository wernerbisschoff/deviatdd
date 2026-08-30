"""TTY checkbox multi-select built on Rich (no extra prompt framework)."""

from __future__ import annotations

import select
import sys
from dataclasses import dataclass, field
from collections.abc import Callable, Sequence
from typing import Literal

from rich.console import Console, Group, RenderableType
from rich.text import Text

Action = Literal["continue", "confirm"]


@dataclass
class CheckboxSession:
    """In-memory checkbox list: Space toggles, Enter confirms.

    Default selection is empty (nothing checked). ``picked()`` returns
    names in *options* order so the caller never depends on set iteration.
    """

    options: tuple[str, ...]
    selected: set[str] = field(default_factory=set)
    cursor: int = 0

    def apply(self, key: str) -> Action:
        if not self.options:
            return "confirm"
        if key in {"enter", "\r", "\n", "esc"}:
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
        if ch == "\x1b":
            if select.select([sys.stdin], [], [], 0.05)[0]:
                rest = sys.stdin.read(2)
                if rest == "[A":
                    return "up"
                if rest == "[B":
                    return "down"
            return "esc"
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
