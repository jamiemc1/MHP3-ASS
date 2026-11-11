"""The results table: every set reachable, only the visible lines drawn.

Textual's ``DataTable`` builds every row up front, which takes seconds for a
50,000-set search; this draws each line from the row list when it is shown,
so filling, sorting and filtering cost the same at any size.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import ClassVar

from rich.cells import cell_len, set_cell_size
from rich.segment import Segment
from textual import events
from textual.binding import Binding, BindingType
from textual.geometry import Size
from textual.message import Message
from textual.reactive import reactive
from textual.scroll_view import ScrollView
from textual.strip import Strip

from mhp3ass.results.table import TableRow


def row_cells(number: int, row: TableRow) -> tuple[str, ...]:
    cells = (
        str(number),
        row.head,
        row.body,
        row.arms,
        row.waist,
        row.legs,
        row.defence,
        row.spare,
        row.charm,
    )
    return cells


class ResultsTable(ScrollView, can_focus=True):
    """A header line, then one line per row; ▲▼ PgUp PgDn Home End move the cursor."""

    COMPONENT_CLASSES: ClassVar[set[str]] = {"results-table--header", "results-table--cursor"}
    DEFAULT_CSS = """
    ResultsTable {
        height: 1fr;
    }
    ResultsTable > .results-table--header {
        text-style: bold;
        background: $panel;
    }
    ResultsTable > .results-table--cursor {
        background: $block-cursor-background;
        color: $block-cursor-foreground;
    }
    """
    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("up", "move(-1)", "Up", show=False),
        Binding("down", "move(1)", "Down", show=False),
        Binding("pageup", "page(-1)", "Page up", show=False),
        Binding("pagedown", "page(1)", "Page down", show=False),
        Binding("home", "jump(0)", "First", show=False),
        Binding("end", "jump(-1)", "Last", show=False),
    ]

    cursor = reactive(0)

    class Highlighted(Message):
        """The cursor moved to ``row`` (an index into the rows)."""

        def __init__(self, row: int) -> None:
            super().__init__()
            self.row = row

    def __init__(
        self, headers: Sequence[str], right_aligned: frozenset[int], id: str | None = None
    ) -> None:
        super().__init__(id=id)
        self._headers = tuple(headers)
        self._right_aligned = right_aligned
        self._rows: Sequence[TableRow] = ()
        self._widths = [cell_len(header) for header in self._headers]
        self._update_size()

    @property
    def row_count(self) -> int:
        return len(self._rows)

    def row_at(self, index: int) -> tuple[str, ...]:
        cells = row_cells(index + 1, self._rows[index])
        return cells

    def set_rows(self, rows: Sequence[TableRow]) -> None:
        """Show ``rows``, with the cursor on the first."""
        self._rows = rows
        widths = [cell_len(header) for header in self._headers]
        widths[0] = max(widths[0], len(str(len(rows))))
        for row in rows:
            for column, cell in enumerate(row_cells(0, row)[1:], start=1):
                width = cell_len(cell)
                if width > widths[column]:
                    widths[column] = width
        self._widths = widths
        self._update_size()
        self.scroll_to(0, 0, animate=False)
        self.refresh()
        # Moving the cursor posts Highlighted; a cursor already at the top needs it posted here.
        if self.cursor == 0:
            if rows:
                self.post_message(self.Highlighted(0))
        else:
            self.cursor = 0

    def _update_size(self) -> None:
        line_width = sum(self._widths) + 2 * len(self._widths)
        self.virtual_size = Size(line_width, len(self._rows) + 1)

    def _line_text(self, cells: Sequence[str]) -> str:
        parts = []
        for column, (cell, width) in enumerate(zip(cells, self._widths, strict=True)):
            padding = " " * (width - cell_len(cell))
            parts.append(padding + cell if column in self._right_aligned else cell + padding)
        text = " " + "  ".join(parts) + " "
        return text

    def render_line(self, y: int) -> Strip:
        scroll_x, scroll_y = self.scroll_offset
        width = self.size.width
        if y == 0:
            text = self._line_text(self._headers)
            style = self.get_component_rich_style("results-table--header")
        else:
            index = scroll_y + y - 1
            if index >= len(self._rows):
                return Strip.blank(width, self.rich_style)
            text = self._line_text(row_cells(index + 1, self._rows[index]))
            style = (
                self.get_component_rich_style("results-table--cursor")
                if index == self.cursor
                else self.rich_style
            )
        line = set_cell_size(text, max(cell_len(text), scroll_x + width))
        strip = Strip([Segment(line, style)]).crop(scroll_x, scroll_x + width)
        return strip

    def _visible_rows(self) -> int:
        rows = max(self.size.height - 1, 1)
        return rows

    def watch_cursor(self, old: int, new: int) -> None:
        top = int(self.scroll_offset.y)
        if new < top:
            self.scroll_to(y=new, animate=False)
        elif new >= top + self._visible_rows():
            self.scroll_to(y=new - self._visible_rows() + 1, animate=False)
        self.refresh()
        if self._rows:
            self.post_message(self.Highlighted(new))

    def _clamped(self, row: int) -> int:
        clamped = min(max(row, 0), max(len(self._rows) - 1, 0))
        return clamped

    def action_move(self, step: int) -> None:
        self.cursor = self._clamped(self.cursor + step)

    def action_page(self, direction: int) -> None:
        self.cursor = self._clamped(self.cursor + direction * self._visible_rows())

    def action_jump(self, row: int) -> None:
        self.cursor = self._clamped(row if row >= 0 else len(self._rows) - 1)

    def on_click(self, event: events.Click) -> None:
        row = int(self.scroll_offset.y) + event.y - 1
        # The header line, and the blank lines below the last row, aren't rows.
        if event.y >= 1 and row < len(self._rows):
            self.cursor = row
