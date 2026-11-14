"""The inspector: the selected set's details beside the results table."""

from __future__ import annotations

from rich.cells import cell_len, set_cell_size
from textual.containers import VerticalScroll
from textual.content import Content
from textual.widgets import Static

from mhp3ass.data.strings import DisplayStrings
from mhp3ass.results.details import SolutionDetails
from mhp3ass.results.inspector import inspector_lines
from mhp3ass.solution.state import Solution


class Inspector(VerticalScroll):
    """Shows one set as ``inspector_lines``, labels in a column."""

    DEFAULT_CSS = """
    Inspector {
        width: 45;
        height: 1fr;
        padding: 0 1;
    }
    """

    def __init__(self, strings: DisplayStrings, piece_labels: list[str]) -> None:
        super().__init__(classes="pane")
        self._strings = strings
        self._piece_labels = piece_labels

    def compose(self):
        yield Static(id="inspector_text")

    def show(self, number: int, solution: Solution, details: SolutionDetails) -> None:
        """Set ``number`` (counting from 1 in the table) and its ``details``."""
        lines = inspector_lines(solution, details, self._strings, piece_labels=self._piece_labels)
        label_width = max((cell_len(line.label) for line in lines), default=0)
        text = "\n".join(f"{set_cell_size(line.label, label_width)}  {line.text}" for line in lines)
        self.border_title = Content(f"Set {number:,}")
        self.query_one("#inspector_text", Static).update(Content(text))

    def clear(self) -> None:
        self.border_title = None
        self.query_one("#inspector_text", Static).update("")
