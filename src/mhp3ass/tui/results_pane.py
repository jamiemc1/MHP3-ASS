"""The results: the charm sidebar with counts, the sort line and the table.

A new layout over ``ResultsView``: the sidebar is ``cmbCharms`` (All, None,
then each charm), the sort drop-down is ``cmbSort`` with its items' text as
``UpdateLanguage`` sets it (``legacy/Form1.h:2068-2100``), and the table
shows ``ResultsView.final`` one row per set.
"""

from __future__ import annotations

from collections.abc import Sequence

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.content import Content
from textual.widgets import Label, OptionList, Select
from textual.widgets.option_list import Option

from mhp3ass.data.strings import DisplayStrings, StringIndex
from mhp3ass.results.sorting import SortKey
from mhp3ass.results.table import TableRow, table_row
from mhp3ass.results.view import CharmFilter, ResultsView
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
    """

    def __init__(self, strings: DisplayStrings) -> None:
        super().__init__()
        self._strings = strings
        self.view: ResultsView | None = None
        # Kept here so the next search's view is shown the same way round.
        self.reverse = False
        self._filters: list[CharmFilter] = []

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

    @property
    def sort_key(self) -> SortKey:
        value = self.query_one("#sort_key", Select).value
        key = value if isinstance(value, SortKey) else SortKey.NONE
        return key

    def show(self, view: ResultsView, rows: Sequence[TableRow]) -> None:
        """Show a new search's view, built with this pane's ``sort_key`` and
        ``reverse``, and the rows of its ``final`` (``view_rows``)."""
        self.view = view
        self._fill_filters()
        self.query_one("#results", ResultsTable).set_rows(rows)

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
        # A selection posted for a list since refilled can point past its end.
        if self.view is not None and event.option_index < len(self._filters):
            self.view.select_filter(self._filters[event.option_index])
            self._fill_table()

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
        options = self.query_one("#charm_filter", OptionList)
        options.clear_options()
        options.add_options(
            Option(Content(f"{_fit(label, 21):<21} {count:>7,}"))
            for label, count in zip(labels, counts, strict=True)
        )
        options.highlighted = 0

    def _fill_table(self) -> None:
        if self.view is not None:
            self.query_one("#results", ResultsTable).set_rows(view_rows(self.view))


def _fit(label: str, width: int) -> str:
    """``label`` cut to ``width`` characters, ending in ``…`` when cut."""
    fitted = label if len(label) <= width else label[: width - 1] + "…"
    return fitted


def view_rows(view: ResultsView) -> list[TableRow]:
    """The table's rows for what ``view`` shows."""
    rows = [table_row(solution, view.sort_key) for solution in view.final]
    return rows
