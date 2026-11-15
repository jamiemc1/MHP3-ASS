"""The inspector: the selected set's details beside the results table."""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from rich.cells import cell_len, set_cell_size
from textual.binding import Binding, BindingType
from textual.containers import VerticalScroll
from textual.content import Content
from textual.widgets import Static

from mhp3ass.data.strings import DisplayStrings
from mhp3ass.query import Query
from mhp3ass.results.details import SolutionDetails
from mhp3ass.results.inspector import inspector_lines
from mhp3ass.solution.state import Solution


@dataclass(frozen=True)
class ShownSet:
    """A set the inspector shows: its ``number`` in the table (counting from
    1), the ``solution``, and its ``details`` for ``query``, the results' own.
    Kept together so a copy of it doesn't pair a set with the next results'
    query."""

    number: int
    solution: Solution
    details: SolutionDetails
    query: Query


class Inspector(VerticalScroll, can_focus=False):
    """Shows one set as ``inspector_lines``, labels in a column. It follows
    the table's cursor, so it isn't a Tab stop; the mouse wheel scrolls it.
    Shown over a narrow screen's table it takes the focus, ▲▼ scroll it,
    ``y`` copies the set, ``Y`` exports it, and ``i`` (or Esc) goes back
    to the table."""

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("i", "app.inspect", "Back to sets"),
        Binding("y", "app.copy_set", "Copy set"),
        Binding("Y", "app.export_set", "Export set"),
    ]

    DEFAULT_CSS = """
    Inspector {
        height: 1fr;
        padding: 0 1;
    }
    """

    def __init__(self, strings: DisplayStrings, piece_labels: list[str]) -> None:
        super().__init__(classes="pane")
        self._strings = strings
        self._piece_labels = piece_labels
        self.shown: ShownSet | None = None

    def compose(self):
        yield Static(id="inspector_text")

    def show(self, shown: ShownSet) -> None:
        self.shown = shown
        lines = inspector_lines(
            shown.solution, shown.details, self._strings, piece_labels=self._piece_labels
        )
        label_width = max((cell_len(line.label) for line in lines), default=0)
        text = "\n".join(f"{set_cell_size(line.label, label_width)}  {line.text}" for line in lines)
        self.border_title = Content(f"Set {shown.number:,}")
        self.query_one("#inspector_text", Static).update(Content(text))

    def relayout(self) -> None:
        """Lay the text out again, after the inspector moves to a new width."""
        self.query_one("#inspector_text", Static).refresh(layout=True)

    def clear(self) -> None:
        self.shown = None
        self.border_title = None
        self.query_one("#inspector_text", Static).update("")
