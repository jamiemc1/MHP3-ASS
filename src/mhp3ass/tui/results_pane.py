"""The results: the charm sidebar with counts, the sort line and the table.

A new layout over ``ResultsView``: the sidebar is ``cmbCharms`` (All, None,
then each charm), the sort drop-down is ``cmbSort`` with its items' text as
``UpdateLanguage`` sets it (``legacy/Form1.h:2068-2100``), and the table
shows ``ResultsView.final`` one row per set.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, replace
from threading import Lock
from typing import ClassVar

from rich.cells import cell_len, set_cell_size
from textual import work
from textual.app import ComposeResult
from textual.binding import Binding, BindingType
from textual.containers import Horizontal, Vertical
from textual.content import Content
from textual.message import Message
from textual.widgets import Input, OptionList
from textual.widgets.option_list import Option
from textual.worker import get_current_worker

from mhp3ass.data import GameData
from mhp3ass.data.strings import DisplayStrings, StringIndex
from mhp3ass.model import Charm
from mhp3ass.pane_titles import sets_title
from mhp3ass.query import Query
from mhp3ass.results.details import PlacementPending, SolutionDetails, solution_details
from mhp3ass.results.find import find_row, row_text
from mhp3ass.results.sorting import SortKey
from mhp3ass.results.table import TableRow, table_row
from mhp3ass.results.view import CharmFilter, ResultsView
from mhp3ass.solution.state import Solution
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


@dataclass(frozen=True)
class JewelJob:
    """A placement to work out: highlight ``inspection``'s set ``number``,
    and what ``solution_details`` needs for it."""

    inspection: int
    number: int
    solution: Solution
    query: Query
    sort_key: SortKey
    game: GameData
    charm_templates: tuple[Charm | None, ...] | None


class ResultsPane(Horizontal):
    """Shows one ``ResultsView``; the sidebar and the sort line change it."""

    class SortChanged(Message):
        """The sort drop-down was changed from the keyboard or mouse."""

    DEFAULT_CSS = """
    ResultsPane {
        height: 1fr;
    }
    ResultsPane #charm_filter {
        width: 34;
        height: 1fr;
    }
    ResultsPane #results {
        height: 1fr;
        border: round $panel-lighten-2;
        border-title-color: $text;
    }
    ResultsPane #find_box {
        display: none;
    }
    """

    def __init__(
        self,
        strings: DisplayStrings,
        sort_key: SortKey,
        reverse: bool,
        is_searching: Callable[[], bool],
        game_lock: Lock,
    ) -> None:
        """``is_searching`` says whether a search is using the game, when sets
        can't be filled again for their placements; ``game_lock`` is held
        while a search or a placement uses it."""
        super().__init__()
        self._strings = strings
        self._is_searching = is_searching
        self._game_lock = game_lock
        # Counts highlights, so a placement worked out for an earlier one is dropped.
        self._inspection = 0
        self.view: ResultsView | None = None
        self._sort_key = sort_key
        # Kept here so the next search's view is shown the same way round.
        self.reverse = reverse
        self._filters: list[CharmFilter] = []
        self._options: list[Option] = []
        self._query: Query | None = None
        self._game: GameData | None = None
        self._charm_templates: tuple[Charm | None, ...] | None = None
        self._needle = ""
        # Find texts by id(solution); the view keeps every solution alive.
        self._text_by_set: dict[int, str] = {}

    def compose(self) -> ComposeResult:
        yield OptionList(id="charm_filter")
        with Vertical():
            table = ResultsTable(
                ["#", "Head", "Body", "Arms", "Waist", "Legs", "Def", "Spare", "Charm"],
                right_aligned=frozenset({0, 6}),
                id="results",
            )
            table.empty_text = "Choose up to six skills, then Search."
            table.border_title = Content(self._title())
            yield table
            yield FindBox(placeholder="find: piece, jewel, charm or skill", id="find_box")
        yield Inspector(self._strings, piece_labels=["Head", "Body", "Arms", "Waist", "Legs"])

    @property
    def results_query(self) -> Query | None:
        """The shown results' own query, as ``show`` was given it."""
        return self._query

    @property
    def charm_templates(self) -> tuple[Charm | None, ...] | None:
        """The shown results' charm templates, as ``show`` was given them."""
        return self._charm_templates

    @property
    def sort_key(self) -> SortKey:
        return self._sort_key

    def sort_names(self) -> list[tuple[SortKey, str]]:
        """Each sort key with its name in the game's language, in drop-down order."""
        names = [(key, self._strings.basic(sort_label(key))) for key in SortKey]
        return names

    def show(
        self,
        view: ResultsView,
        rows: Sequence[TableRow],
        query: Query,
        game: GameData,
        charm_templates: tuple[Charm | None, ...] | None,
    ) -> None:
        """Show a new search's view and the rows of its ``final`` (``view_rows``);
        ``query`` is the results' own, for the inspector's notes and extra skills,
        ``game`` the one they were found in, for its jewel placements, and
        ``charm_templates`` the search's workers' charms (``None`` for loaded
        results), for a set that can't be built as listed (quirk 52).
        The view was built with the sort and reverse of the search's start; if
        they changed while it ran, it is sorted again here."""
        self.view = view
        self._query = query
        self._game = game
        self._charm_templates = charm_templates
        self._text_by_set = {}
        self._fill_filters()
        if view.sort_key is not self.sort_key or view.reverse != self.reverse:
            view.select_sort(self.sort_key)
            view.select_reverse(self.reverse)
            rows = view_rows(view)
        self._set_rows(rows)

    def on_results_table_highlighted(self, event: ResultsTable.Highlighted) -> None:
        event.stop()
        self._inspect(event.row)

    def redraw_inspector(self) -> None:
        """Show the highlighted set again: once a search stops using the game,
        a placement pending until then can be worked out."""
        self._inspect(self.query_one(ResultsTable).cursor)

    def stop_placements(self) -> None:
        """Cancel the placement being worked out; a result already on its way
        is dropped as stale."""
        self._inspection += 1
        self.workers.cancel_group(self, "jewels")

    def _inspect(self, row: int) -> None:
        """Show set ``row`` at once; a placement that needs the set filled
        again (a loaded set, or one whose shown jewels don't fit, quirk 52)
        shows as being worked out, and is worked out in a thread."""
        self.stop_placements()
        view = self.view
        inspector = self.query_one(Inspector)
        # A highlight posted before the rows were replaced can be past the new end.
        if view is None or self._query is None or self._game is None or row >= len(view.final):
            inspector.clear()
            return
        solution = view.final[row]
        details = solution_details(
            solution,
            query=self._query,
            sort_key=view.sort_key,
            refill_game=None,
            charm_templates=self._charm_templates,
        )
        if not isinstance(details.chest_jewels, PlacementPending) or self._is_searching():
            inspector.show(row + 1, solution, details)
            return
        working = replace(details, chest_jewels=PlacementPending(while_searching=False))
        inspector.show(row + 1, solution, working)
        self._work_out_jewels(
            JewelJob(
                inspection=self._inspection,
                number=row + 1,
                solution=solution,
                query=self._query,
                sort_key=view.sort_key,
                game=self._game,
                charm_templates=self._charm_templates,
            )
        )

    @work(thread=True, exclusive=True, group="jewels")
    def _work_out_jewels(self, job: JewelJob) -> None:
        """The set's details with its placement, under the game lock a search
        also takes (both fill sets and set the abilities' relevance)."""
        with self._game_lock:
            # A later highlight cancelled this one while it waited: skip the work.
            if get_current_worker().is_cancelled:
                return
            details = solution_details(
                job.solution,
                query=job.query,
                sort_key=job.sort_key,
                refill_game=job.game,
                charm_templates=job.charm_templates,
            )
        try:
            self.app.call_from_thread(self._jewels_worked_out, job, details)
        except RuntimeError:
            # The app stopped running while the placement was worked out.
            return

    def _jewels_worked_out(self, job: JewelJob, details: SolutionDetails) -> None:
        # Moving on since the job started, or a rebuild that removed this pane, makes it stale.
        if job.inspection != self._inspection or not self.is_attached:
            return
        self.query_one(Inspector).show(job.number, job.solution, details)

    def choose_sort(self, key: SortKey | None) -> None:
        """Sort by ``key``, as choosing it in ``cmbSort`` does; ``None`` (the
        picker closed) or the key already in use changes nothing."""
        if key is None or key is self._sort_key:
            return
        self._sort_key = key
        if self.view is not None:
            self.view.select_sort(key)
            self._fill_table()
        else:
            self._update_title()
        self.post_message(self.SortChanged())

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
        self._close_find()
        self.find(step=1, from_cursor=True)

    def on_find_box_closed(self, event: FindBox.Closed) -> None:
        event.stop()
        self._close_find()

    def _close_find(self) -> None:
        self.query_one("#find_box", FindBox).display = False
        self.query_one("#results", ResultsTable).focus()

    def find(self, step: int, from_cursor: bool = False) -> None:
        """Move the cursor to the next (``step`` 1) or previous (-1) set
        matching the find text; with ``from_cursor`` (a new find text) the
        set under the cursor counts too. A notice when none matches."""
        table = self.query_one("#results", ResultsTable)
        view = self.view
        query = self._query
        if view is None or query is None or table.row_count == 0 or self._needle == "":
            return
        texts = []
        for solution in view.final:
            # Each set's text is built once per search, whatever the sort or filter.
            key = id(solution)
            if key not in self._text_by_set:
                self._text_by_set[key] = row_text(solution, query=query)
            texts.append(self._text_by_set[key])
        start = (table.cursor - step) % len(texts) if from_cursor else table.cursor
        row = find_row(texts, needle=self._needle, start=start, step=step)
        if row is None:
            self.notify(f"No set has {self._needle!r}.")
            return
        table.cursor = row

    def reverse_sort(self) -> None:
        self.reverse = not self.reverse
        if self.view is not None:
            self.view.select_reverse(self.reverse)
            self._fill_table()
        else:
            self._update_title()

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
        # The view's own filter: All after a search, the charm it kept after a language switch.
        chosen = view.charm_filter
        options.highlighted = self._filters.index(chosen) if chosen in self._filters else 0

    def _title(self) -> str:
        shown = len(self.view.final) if self.view is not None else None
        name = self._strings.basic(sort_label(self._sort_key))
        title = sets_title(shown, self._sort_key, sort_name=name, reverse=self.reverse)
        return title

    def _update_title(self) -> None:
        self.query_one("#results", ResultsTable).border_title = Content(self._title())

    def _set_rows(self, rows: Sequence[TableRow]) -> None:
        table = self.query_one("#results", ResultsTable)
        table.empty_text = "No sets."
        table.set_rows(rows)
        self._update_title()
        # With no rows the table moves no cursor, so nothing else clears the inspector.
        if not rows:
            self.query_one(Inspector).clear()

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
