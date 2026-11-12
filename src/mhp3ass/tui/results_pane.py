"""The results: the charm sidebar with counts, the sort line and the table.

A new layout over ``ResultsView``: the sidebar is ``cmbCharms`` (All, None,
then each charm), the sort drop-down is ``cmbSort`` with its items' text as
``UpdateLanguage`` sets it (``legacy/Form1.h:2068-2100``), and the table
shows ``ResultsView.final`` one row per set.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import ClassVar

from rich.cells import cell_len, set_cell_size
from textual.app import ComposeResult
from textual.binding import Binding, BindingType
from textual.containers import Horizontal, Vertical
from textual.content import Content
from textual.message import Message
from textual.widgets import Input, Label, OptionList, Select
from textual.widgets.option_list import Option

from mhp3ass.data.strings import DisplayStrings, StringIndex
from mhp3ass.query import Query
from mhp3ass.results.find import find_row, row_text
from mhp3ass.results.sorting import SortKey
from mhp3ass.results.table import TableRow, table_row
from mhp3ass.results.view import CharmFilter, ResultsView
from mhp3ass.tui.inspector import Inspector
from mhp3ass.tui.results_table import ResultsTable


def sort_label(key: SortKey) -> StringIndex:
    """``cmbSort``'s item text (``Form1.h:2090-2100``)."""
    match key:
        case SortKey.NONE:
            return StringIndex.NONE
        case SortKey.DRAGON_RES:
            return StringIndex.DRAGON_RES
        case SortKey.FIRE_RES:
            return StringIndex.FIRE_RES
        case SortKey.ICE_RES:
            return StringIndex.ICE_RES
        case SortKey.THUNDER_RES:
            return StringIndex.THUNDER_RES
        case SortKey.WATER_RES:
            return StringIndex.WATER_RES
        case SortKey.DEFENCE:
            return StringIndex.BASE_DEFENCE
        case SortKey.MAX_DEFENCE:
            return StringIndex.MAX_DEFENCE
        case SortKey.DIFFICULTY:
            return StringIndex.DIFFICULTY
        case SortKey.RARITY:
            return StringIndex.RARITY
        case SortKey.SLOTS_SPARE:
            return StringIndex.SORT_SLOTS_SPARE


class FindBox(Input):
    """The find text; Esc closes it."""

    BINDINGS: ClassVar[list[BindingType]] = [Binding("escape", "close", "Close", show=False)]

    class Closed(Message):
        pass

    def action_close(self) -> None:
        self.post_message(self.Closed())


class ResultsPane(Horizontal):
    """Shows one ``ResultsView``; the sidebar and the sort line change it."""

    DEFAULT_CSS = """
    ResultsPane {
        height: 1fr;
    }
    ResultsPane #charm_filter {
        width: 34;
        height: 1fr;
    }
    ResultsPane #sort_line {
        height: auto;
    }
    ResultsPane #sort_line Label {
        padding: 1 1 0 2;
    }
    ResultsPane #sort_key {
        width: 30;
    }
    ResultsPane #results {
        height: 1fr;
    }
    ResultsPane #find_box {
        display: none;
    }
    """

    def __init__(self, strings: DisplayStrings) -> None:
        super().__init__()
        self._strings = strings
        self.view: ResultsView | None = None
        # Kept here so the next search's view is shown the same way round.
        self.reverse = False
        self._filters: list[CharmFilter] = []
        self._options: list[Option] = []
        self._query: Query | None = None
        self._needle = ""
        self._row_texts: list[str] | None = None

    def compose(self) -> ComposeResult:
        strings = self._strings
        yield OptionList(id="charm_filter")
        with Vertical():
            with Horizontal(id="sort_line"):
                yield Label(strings.static(StringIndex.SORT_RESULTS_BY))
                yield Select(
                    [(strings.basic(sort_label(key)), key) for key in SortKey],
                    value=SortKey.NONE,
                    allow_blank=False,
                    id="sort_key",
                )
                yield Label("", id="reversed")
            yield ResultsTable(
                ["#", "Head", "Body", "Arms", "Waist", "Legs", "Def", "Spare", "Charm"],
                right_aligned=frozenset({0, 6}),
                id="results",
            )
            yield FindBox(placeholder="find: piece, jewel, charm or skill", id="find_box")
        yield Inspector(self._strings, piece_labels=["Head", "Body", "Arms", "Waist", "Legs"])

    @property
    def sort_key(self) -> SortKey:
        value = self.query_one("#sort_key", Select).value
        if not isinstance(value, SortKey):
            raise TypeError(f"the sort drop-down holds {value!r}, not a SortKey")
        return value

    def show(self, view: ResultsView, rows: Sequence[TableRow], query: Query) -> None:
        """Show a new search's view and the rows of its ``final`` (``view_rows``);
        ``query`` is the results' own, for the inspector's notes and extra skills.
        The view was built with the sort and reverse of the search's start; if
        they changed while it ran, it is sorted again here."""
        self.view = view
        self._query = query
        self._fill_filters()
        if view.sort_key is not self.sort_key or view.reverse != self.reverse:
            view.select_sort(self.sort_key)
            view.select_reverse(self.reverse)
            rows = view_rows(view)
        self._set_rows(rows)

    def on_results_table_highlighted(self, event: ResultsTable.Highlighted) -> None:
        event.stop()
        view = self.view
        inspector = self.query_one(Inspector)
        # A highlight posted before the rows were replaced can be past the new end.
        if view is None or self._query is None or event.row >= len(view.final):
            inspector.clear()
            return
        inspector.show(
            event.row + 1, view.final[event.row], query=self._query, sort_key=view.sort_key
        )

    def on_select_changed(self, event: Select.Changed) -> None:
        if event.select.id != "sort_key":
            return
        event.stop()
        if self.view is not None:
            self.view.select_sort(self.sort_key)
            self._fill_table()

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        if event.option_list.id != "charm_filter":
            return
        event.stop()
        # A selection posted before the list was refilled names an old option.
        index = event.option_index
        current = index < len(self._options) and event.option is self._options[index]
        if self.view is not None and current:
            self.view.select_filter(self._filters[index])
            self._fill_table()

    def open_find(self) -> None:
        box = self.query_one("#find_box", FindBox)
        box.display = True
        box.focus()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id != "find_box":
            return
        event.stop()
        self._needle = event.value
        self.find(step=1)
        self.query_one("#results", ResultsTable).focus()

    def on_find_box_closed(self, event: FindBox.Closed) -> None:
        event.stop()
        self.query_one("#find_box", FindBox).display = False
        self.query_one("#results", ResultsTable).focus()

    def find(self, step: int) -> None:
        """Move the cursor to the next (``step`` 1) or previous (-1) set
        matching the find text; a notice when none does."""
        table = self.query_one("#results", ResultsTable)
        if self.view is None or table.row_count == 0 or self._needle == "":
            return
        if self._row_texts is None:
            self._row_texts = [row_text(solution) for solution in self.view.final]
        row = find_row(self._row_texts, needle=self._needle, start=table.cursor, step=step)
        if row is None:
            self.notify(f"No set has {self._needle!r}.")
            return
        table.cursor = row

    def reverse_sort(self) -> None:
        self.reverse = not self.reverse
        self.query_one("#reversed", Label).update("reversed" if self.reverse else "")
        if self.view is not None:
            self.view.select_reverse(self.reverse)
            self._fill_table()

    def _fill_filters(self) -> None:
        view = self.view
        if view is None:
            return
        strings = self._strings
        names = view.charm_filter_names()
        self._filters = [
            CharmFilter.every_solution(),
            CharmFilter.charm_free(),
            *(CharmFilter.charm(name) for name in names),
        ]
        counts = [
            len(view.all_solutions),
            len(view.no_charm_solutions),
            *(len(view.by_charm[name]) for name in names),
        ]
        labels = [
            strings.static(StringIndex.ALL),
            strings.basic(StringIndex.NONE),
            *names,
        ]
        self._options = [
            Option(Content(f"{_fit(label, 21)} {count:>7,}"))
            for label, count in zip(labels, counts, strict=True)
        ]
        options = self.query_one("#charm_filter", OptionList)
        options.clear_options()
        options.add_options(self._options)
        options.highlighted = 0

    def _set_rows(self, rows: Sequence[TableRow]) -> None:
        # Find's texts follow the rows shown; they're rebuilt at the next find.
        self._row_texts = None
        self.query_one("#results", ResultsTable).set_rows(rows)

    def _fill_table(self) -> None:
        if self.view is not None:
            self._set_rows(view_rows(self.view))


def _fit(label: str, width: int) -> str:
    """``label`` padded or cut to ``width`` terminal cells (wide characters
    count twice), ending in ``…`` when cut."""
    if cell_len(label) <= width:
        return set_cell_size(label, width)
    fitted = set_cell_size(label, width - 1) + "…"
    return fitted


def view_rows(view: ResultsView) -> list[TableRow]:
    """The table's rows for what ``view`` shows."""
    rows = [table_row(solution, view.sort_key) for solution in view.final]
    return rows
