"""The `?` help: the keys that work where the focus was, over the screen."""

from __future__ import annotations

from collections.abc import Sequence
from typing import ClassVar

from rich.cells import cell_len, set_cell_size
from textual.app import ComposeResult
from textual.binding import Binding, BindingType
from textual.containers import VerticalScroll
from textual.content import Content
from textual.screen import ModalScreen
from textual.widgets import Static

from mhp3ass.key_help import HelpSection


class HelpScreen(ModalScreen[None]):
    """``help_sections``' keys, a section to a heading; Esc, ``?`` or ``q``
    closes it."""

    DEFAULT_CSS = """
    HelpScreen {
        align: center middle;
    }
    HelpScreen VerticalScroll {
        width: auto;
        max-width: 90%;
        height: auto;
        max-height: 90%;
        border: round $accent;
        padding: 0 1;
    }
    HelpScreen Static {
        width: auto;
    }
    """
    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("escape", "close", "Close"),
        Binding("question_mark", "close", "Close", show=False),
        Binding("q", "close", "Close", show=False),
    ]

    def __init__(self, sections: Sequence[HelpSection], title: str) -> None:
        super().__init__()
        self._sections = sections
        self._title = title

    def compose(self) -> ComposeResult:
        rows = [row for section in self._sections for row in section.rows]
        key_width = max((cell_len(", ".join(row.keys)) for row in rows), default=0)
        lines: list[Content] = []
        for number, section in enumerate(self._sections):
            if number > 0:
                lines.append(Content(""))
            lines.append(Content.styled(section.title, "bold"))
            lines.extend(
                Content.assemble(
                    (set_cell_size(", ".join(row.keys), key_width), "$accent"),
                    "  ",
                    row.description,
                )
                for row in section.rows
            )
        with VerticalScroll() as scroll:
            scroll.border_title = Content(self._title)
            yield Static(Content("\n").join(lines))

    def action_close(self) -> None:
        self.dismiss(None)
