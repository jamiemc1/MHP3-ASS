"""The results table: every set reachable, only the visible lines drawn.

Textual's ``DataTable`` builds every row up front, which takes seconds for a
50,000-set search; this draws each line from the row list when it is shown,
so filling, sorting and filtering cost the same at any size. The pinned
columns stay at the left and the rest scroll a whole column at a time
(``column_window``).
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

from mhp3ass.column_window import column_window, scrolled_columns, spare_cells
from mhp3ass.keys import results_keys
from mhp3ass.results.table import TableRow, fit_widths, truncate


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
        row.fire,
        row.water,
        row.thunder,
        row.ice,
        row.dragon,
        row.extra,
    )
    return cells


class ResultsTable(ScrollView, can_focus=True):
    """A header line, then one line per row; ▲▼ PgUp PgDn Home End move the
    cursor, ◀▶ scroll a column and Shift+◀▶ to either end. The wide
    columns show only while ``show_wide`` is set."""

    COMPONENT_CLASSES: ClassVar[set[str]] = {
        "results-table--header",
        "results-table--cursor",
        "results-table--empty",
    }
    DEFAULT_CSS = """
    ResultsTable {
        height: 1fr;
        overflow-x: hidden;
    }
    ResultsTable > .results-table--header {
        text-style: bold;
        background: $panel;
    }
    ResultsTable > .results-table--cursor {
        background: $block-cursor-background;
        color: $block-cursor-foreground;
    }
    ResultsTable > .results-table--empty {
        color: $text-muted;
    }
    """
    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("up", "move(-1)", "Up", show=False),
        Binding("down", "move(1)", "Down", show=False),
        Binding("pageup", "page(-1)", "Page up", show=False),
        Binding("pagedown", "page(1)", "Page down", show=False),
        Binding("home", "jump(0)", "First", show=False),
        Binding("end", "jump(-1)", "Last", show=False),
        Binding("left", "column_step(-1)", "Column left", show=False),
        Binding("right", "column_step(1)", "Column right", show=False),
        Binding("shift+left", "column_end(-1)", "First column", show=False),
        Binding("shift+right", "column_end(1)", "Last column", show=False),
        *results_keys(),
    ]

    cursor = reactive(0)

    class Highlighted(Message):
        """The cursor moved to ``row`` (an index into the rows)."""

        def __init__(self, row: int) -> None:
            super().__init__()
            self.row = row

    def __init__(
        self,
        headers: Sequence[str],
        right_aligned: frozenset[int],
        must_fit: frozenset[int],
        pinned: frozenset[int],
        wide: frozenset[int],
        id: str | None = None,
    ) -> None:
        """The ``right_aligned`` columns are numbers and never cut; the
        ``must_fit`` columns are cut, if need be, to fit the table's width,
        and the others are reached by scrolling. The ``pinned`` columns
        show first, whatever the scroll; the ``wide`` ones are hidden until
        ``show_wide``."""
        super().__init__(id=id)
        self._headers = tuple(headers)
        self._right_aligned = right_aligned
        self._must_fit = must_fit
        self._pinned = pinned
        self._wide = wide
        self._show_wide = False
        self._rows: Sequence[TableRow] = ()
        # Each column's widest cell, and the widths the table's width leaves them.
        self._widths = [cell_len(header) for header in self._headers]
        self._fitted = list(self._widths)
        # The columns in view, and the width they were worked out for.
        self._window = column_window(self._fitted, pinned=pinned, hidden=wide, first=0, width=0)
        self._layout_width = 0
        # Shown on the first line while there are no rows.
        self.empty_text = ""
        self._update_size(first=0)

    @property
    def row_count(self) -> int:
        return len(self._rows)

    def row_at(self, index: int) -> tuple[str, ...]:
        cells = row_cells(index + 1, self._rows[index])
        return cells

    def set_rows(self, rows: Sequence[TableRow]) -> None:
        """Show ``rows``, with the cursor on the first and the columns scrolled to the start."""
        self._take_rows(rows)
        self._update_size(first=0)
        self.scroll_to(0, 0, animate=False)
        self.refresh()
        # Moving the cursor posts Highlighted; a cursor already at the top needs it posted here.
        if self.cursor == 0:
            if rows:
                self.post_message(self.Highlighted(0))
        else:
            self.cursor = 0

    def replace_rows(self, rows: Sequence[TableRow]) -> None:
        """Show ``rows`` in place of the same number of rows, the same sets
        named differently, keeping the cursor and the scroll."""
        if len(rows) != len(self._rows):
            raise ValueError(f"{len(rows)} rows can't replace {len(self._rows)}")
        self._take_rows(rows)
        self._update_size(first=self._window.first)
        self.refresh()

    def _take_rows(self, rows: Sequence[TableRow]) -> None:
        """Keep ``rows`` and each column's widest cell."""
        self._rows = rows
        widths = [cell_len(header) for header in self._headers]
        widths[0] = max(widths[0], len(str(len(rows))))
        for row in rows:
            for column, cell in enumerate(row_cells(0, row)[1:], start=1):
                width = cell_len(cell)
                if width > widths[column]:
                    widths[column] = width
        self._widths = widths

    def on_resize(self, event: events.Resize) -> None:
        self._update_size(first=self._window.first)
        self.refresh()

    def _update_size(self, first: int) -> None:
        """Fit the ``must_fit`` columns to the table's width (``fit_widths``),
        then work out which columns show from ``first`` (``column_window``)
        and size the scroll area."""
        width = self.scrollable_content_region.width
        scrolled_must_fit = len(self._must_fit - self._pinned)
        available = width - spare_cells(len(self._pinned), scrolled=scrolled_must_fit)
        self._fitted = (
            fit_widths(
                self._widths,
                available=available,
                must_fit=self._must_fit,
                fixed=self._right_aligned,
            )
            if width > 0
            else list(self._widths)
        )
        self._window = column_window(
            self._fitted, pinned=self._pinned, hidden=self._hidden(), first=first, width=width
        )
        self._layout_width = width
        # The window scrolls the columns, so the scroll area has no width of its own.
        self.virtual_size = Size(0, len(self._rows) + 1)

    def _hidden(self) -> frozenset[int]:
        hidden = frozenset() if self._show_wide else self._wide
        return hidden

    @property
    def show_wide(self) -> bool:
        return self._show_wide

    def set_show_wide(self, shown: bool) -> None:
        """Show the wide columns, or hide them, keeping the cursor; shown,
        the first of them scrolls to the start of the window."""
        self._show_wide = shown
        columns = scrolled_columns(len(self._widths), self._pinned, hidden=self._hidden())
        first = columns.index(min(self._wide)) if shown else self._window.first
        self._update_size(first=first)
        self.refresh()

    def _cell(self, column: int, full: str, width: int) -> str:
        cell = truncate(full, width)
        padding = " " * (width - cell_len(cell))
        text = padding + cell if column in self._right_aligned else cell + padding
        return text

    def _line_text(self, cells: Sequence[str], markers: bool) -> str:
        """A line of ``cells`` laid out as ``column_window`` says, with the
        ``<`` and ``>`` markers if ``markers`` (the header line)."""
        window = self._window
        width = self._layout_width
        pinned = "  ".join(
            self._cell(column, cells[column], self._fitted[column]) for column in window.pinned
        )
        left = "<" if markers and window.more_left else " "
        prefix = f" {pinned} {left} "
        # A lone scrolled column wider than the room left is cut to it.
        room = width - cell_len(prefix) - 2
        scrolled = "  ".join(
            self._cell(
                column,
                cells[column],
                self._fitted[column]
                if len(window.scrolled) > 1
                else max(min(self._fitted[column], room), 0),
            )
            for column in window.scrolled
        )
        right = ">" if markers and window.more_right else " "
        text = set_cell_size(prefix + scrolled, max(width - 1, 0)) + right
        return text

    def render_line(self, y: int) -> Strip:
        # The vertical scrollbar comes and goes with the rows without a resize.
        if self.scrollable_content_region.width != self._layout_width:
            self._update_size(first=self._window.first)
        scroll_y = int(self.scroll_offset.y)
        width = self._layout_width
        if y == 0:
            text = self._line_text(self._headers, markers=True)
            style = self.get_component_rich_style("results-table--header")
        else:
            index = scroll_y + y - 1
            if not self._rows and y == 1:
                empty_style = self.get_component_rich_style("results-table--empty")
                empty = set_cell_size(f" {self.empty_text}", width)
                return Strip([Segment(empty, empty_style)])
            if index >= len(self._rows):
                return Strip.blank(width, self.rich_style)
            text = self._line_text(row_cells(index + 1, self._rows[index]), markers=False)
            style = (
                self.get_component_rich_style("results-table--cursor")
                if index == self.cursor
                else self.rich_style
            )
        line = set_cell_size(text, width)
        strip = Strip([Segment(line, style)])
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

    def action_column_step(self, step: int) -> None:
        """Scroll the unpinned columns by ``step`` whole columns."""
        self._update_size(first=self._window.first + step)
        self.refresh()

    def action_column_end(self, direction: int) -> None:
        """Scroll to the first unpinned column (``direction`` -1) or the last
        (1; ``column_window`` stops at the furthest it need go)."""
        self._update_size(first=0 if direction < 0 else len(self._widths))
        self.refresh()

    def on_click(self, event: events.Click) -> None:
        row = int(self.scroll_offset.y) + event.y - 1
        # The header line, and the blank lines below the last row, aren't rows.
        if event.y >= 1 and row < len(self._rows):
            self.cursor = row
