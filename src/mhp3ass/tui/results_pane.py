"""The results: the charm sidebar with counts, the sort line and the table.

A new layout over ``ResultsView``: the sidebar is ``cmbCharms`` (All, None,
then each charm), the sort drop-down is ``cmbSort`` with its items' text as
``UpdateLanguage`` sets it (``legacy/Form1.h:2068-2100``), and the table
shows ``ResultsView.final`` one row per set.

How it is laid out follows the screen's width class (``layout``): below
wide, a charm drop-down at the top of the sets takes the sidebar's place,
and on a narrow screen the inspector shows over the table on request.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, replace
from threading import Lock

from rich.cells import set_cell_size
from textual import work
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.content import Content
from textual.message import Message
from textual.widgets import Input, Label, OptionList, Select
from textual.widgets.option_list import Option
from textual.worker import get_current_worker

from mhp3ass.data import GameData
from mhp3ass.data.strings import DisplayStrings, StringIndex
from mhp3ass.model import Charm
from mhp3ass.pane_titles import sets_title
from mhp3ass.query import Query
from mhp3ass.regions import Region
from mhp3ass.results.details import PlacementPending, SolutionDetails, solution_details
from mhp3ass.results.find import find_row, row_text
from mhp3ass.results.short_names import ShortNames
from mhp3ass.results.sorting import SortKey
from mhp3ass.results.table import TableRow, table_row, truncate
from mhp3ass.results.view import CharmFilter, ResultsView
from mhp3ass.solution.state import Solution
from mhp3ass.tui.inspector import Inspector
from mhp3ass.tui.results_table import ResultsTable
from mhp3ass.tui.titles import region_title

# The empty table's line before any results, shown again when a first search is cancelled.
_BEFORE_SEARCH = "Choose up to six skills, then Search."


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
    """Shows one ``ResultsView``; the sidebar and the sort picker change it."""

    class SortChanged(Message):
        """A sort was chosen in the sort picker."""

    DEFAULT_CSS = """
    ResultsPane {
        height: 1fr;
    }
    ResultsPane #charm_filter {
        width: 24;
        height: 1fr;
    }
    ResultsPane #results {
        height: 1fr;
    }
    ResultsPane #find_box {
        display: none;
    }
    ResultsPane #charms_bar {
        height: 1;
        display: none;
    }
    ResultsPane #charm_label {
        padding: 0 1 0 0;
    }
    ResultsPane #charm_choice {
        width: 42;
    }
    ResultsPane Inspector {
        width: 42;
    }
    """

    def __init__(
        self,
        strings: DisplayStrings,
        sort_key: SortKey,
        reverse: bool,
        is_searching: Callable[[], bool],
        game_lock: Lock,
        short_names: ShortNames,
        full_names: bool,
    ) -> None:
        """``is_searching`` says whether a search is using the game, when sets
        can't be filled again for their placements; ``game_lock`` is held
        while a search or a placement uses it; ``short_names`` shorten the
        table's cells, unless ``full_names`` (a huge screen) names them in
        full. Find matches both either way."""
        super().__init__()
        self._strings = strings
        self._short_names = short_names
        self._full_names = full_names
        # No names to shorten to, so every piece and charm keeps its own.
        self._names_in_full = ShortNames(armor_names={}, abbreviations={})
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
        self.note: str | None = None
        # Find texts by id(solution); the view keeps every solution alive.
        self._text_by_set: dict[int, str] = {}

    def compose(self) -> ComposeResult:
        charm_filter = OptionList(id="charm_filter", classes="pane")
        charm_filter.border_title = region_title(
            Region.CHARMS, self._strings.static(StringIndex.CHARMS)
        )
        yield charm_filter
        # The table and the find box under it are one region, bordered together.
        sets = Vertical(id="sets", classes="pane")
        sets.border_title = region_title(Region.SETS, self._title())
        with sets:
            # Below wide, the charm sidebar's place (the screen's CSS shows one or the other).
            with Horizontal(id="charms_bar"):
                yield Label(
                    region_title(Region.CHARMS, self._strings.static(StringIndex.CHARMS)),
                    id="charm_label",
                )
                yield Select(
                    [(Content(self._strings.static(StringIndex.ALL)), 0)],
                    allow_blank=False,
                    compact=True,
                    id="charm_choice",
                )
            table = ResultsTable(
                [
                    "#",
                    "Head",
                    "Body",
                    "Arms",
                    "Waist",
                    "Legs",
                    "Def",
                    "Spare",
                    "Charm",
                    "Fire",
                    "Water",
                    "Thunder",
                    "Ice",
                    "Dragon",
                    "Extra skills",
                ],
                right_aligned=frozenset({0, 6, 9, 10, 11, 12, 13}),
                # The number, the five pieces and the defence; the spare slots and charm scroll.
                must_fit=frozenset(range(7)),
                # The number and the defence stay in view while the rest scroll.
                pinned=frozenset({0, 6}),
                # The resistances and extra skills, shown with ``w``.
                wide=frozenset(range(9, 15)),
                id="results",
            )
            table.empty_text = _BEFORE_SEARCH
            yield table
            yield Input(placeholder="find: piece, jewel, charm or skill", id="find_box")
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

    @property
    def table_names(self) -> ShortNames:
        """The names the table's cells use: short, or in full."""
        names = self._names_in_full if self._full_names else self._short_names
        return names

    def name_in_full(self, full: bool) -> None:
        """Name the table's pieces and charm in full (``full``) or shortened,
        keeping the cursor's set."""
        if full == self._full_names:
            return
        self._full_names = full
        if self.view is not None and self._query is not None:
            self.query_one("#results", ResultsTable).replace_rows(
                view_rows(self.view, names=self.table_names, query=self._query)
            )

    @property
    def inspecting(self) -> bool:
        """The inspector shows over the table (a narrow screen's, on request)."""
        return self.has_class("-inspecting")

    def show_inspector(self, shown: bool) -> None:
        """Show the inspector over the table, or the table again. The hidden
        table can't keep the focus, so the inspector takes it meanwhile;
        once it is hidden again, the caller puts the focus where it goes."""
        self.set_class(shown, "-inspecting")
        inspector = self.query_one(Inspector)
        inspector.can_focus = shown
        if shown:
            inspector.focus()

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
        note: str | None = None,
    ) -> None:
        """Show a new search's view and the rows of its ``final``
        (``view_rows``, named by ``table_names``); ``query`` is the results'
        own, for the inspector's notes and extra skills,
        ``game`` the one they were found in, for its jewel placements, and
        ``charm_templates`` the search's workers' charms (``None`` for loaded
        results), for a set that can't be built as listed (quirk 52).
        ``note``, shown in the sets' bottom border until the next results,
        says what is wrong with them (a worker that stopped).
        The view was built with the sort and reverse of the search's start; if
        they changed while it ran, it is sorted again here."""
        self.view = view
        self.note = note
        table = self.query_one("#results", ResultsTable)
        table.empty_text = "No sets."
        sets = self.query_one("#sets", Vertical)
        sets.border_subtitle = Content(note) if note is not None else None
        self._query = query
        self._game = game
        self._charm_templates = charm_templates
        self._text_by_set = {}
        self._fill_filters()
        if view.sort_key is not self.sort_key or view.reverse != self.reverse:
            view.select_sort(self.sort_key)
            view.select_reverse(self.reverse)
            rows = view_rows(view, names=self.table_names, query=query)
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

    def show_searching(self, running: bool) -> None:
        """Before the first results, the empty table says whether a search is running."""
        if self.view is not None:
            return
        table = self.query_one("#results", ResultsTable)
        table.empty_text = "Searching…" if running else _BEFORE_SEARCH
        table.refresh()

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
            self.query_one("#charm_choice", Select).value = index
            self._fill_table()

    def on_select_changed(self, event: Select.Changed) -> None:
        """A charm chosen in the drop-down; setting it to match the sidebar changes nothing."""
        if event.select.id != "charm_choice":
            return
        event.stop()
        index = event.value
        if self.view is None or not isinstance(index, int) or index >= len(self._filters):
            return
        chosen = self._filters[index]
        if chosen == self.view.charm_filter:
            return
        self.view.select_filter(chosen)
        self.query_one("#charm_filter", OptionList).highlighted = index
        self._fill_table()

    @property
    def find_open(self) -> bool:
        return self.query_one("#find_box", Input).display

    def open_find(self) -> None:
        box = self.query_one("#find_box", Input)
        box.display = True
        box.focus()

    def clear_find(self) -> None:
        """Close the find box with its text cleared, as Esc does; the last
        find text submitted stays for ``n`` and ``N``."""
        self.query_one("#find_box", Input).value = ""
        self._close_find()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id != "find_box":
            return
        event.stop()
        self._needle = event.value
        self._close_find()
        self.find(step=1, from_cursor=True)

    def _close_find(self) -> None:
        self.query_one("#find_box", Input).display = False
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
                self._text_by_set[key] = row_text(
                    solution, query=query, short_names=self._short_names
                )
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
            Option(Content(f"{_fit(label, 12)} {count:>7,}"))
            for label, count in zip(labels, counts, strict=True)
        ]
        options = self.query_one("#charm_filter", OptionList)
        options.clear_options()
        options.add_options(self._options)
        # The view's own filter: All after a search, the charm it kept after a language switch.
        chosen = view.charm_filter
        index = self._filters.index(chosen) if chosen in self._filters else 0
        options.highlighted = index
        # The drop-down opens over the table, so it has room for longer names.
        choice = self.query_one("#charm_choice", Select)
        choice.set_options(
            (Content(f"{_fit(label, 30)} {count:>7,}"), number)
            for number, (label, count) in enumerate(zip(labels, counts, strict=True))
        )
        choice.value = index
        # Its value can be unchanged while its text isn't (new counts): show the new text.
        choice.mutate_reactive(Select.value)

    def _title(self) -> str:
        shown = len(self.view.final) if self.view is not None else None
        name = self._strings.basic(sort_label(self._sort_key))
        title = sets_title(shown, self._sort_key, sort_name=name, reverse=self.reverse)
        return title

    def _update_title(self) -> None:
        self.query_one("#sets", Vertical).border_title = region_title(Region.SETS, self._title())

    def _set_rows(self, rows: Sequence[TableRow]) -> None:
        self.query_one("#results", ResultsTable).set_rows(rows)
        self._update_title()
        # With no rows the table moves no cursor, so nothing else clears the inspector.
        if not rows:
            self.query_one(Inspector).clear()

    def _fill_table(self) -> None:
        if self.view is not None and self._query is not None:
            self._set_rows(view_rows(self.view, names=self.table_names, query=self._query))


def _fit(label: str, width: int) -> str:
    """``label`` padded or cut (``truncate``) to ``width`` terminal cells."""
    fitted = set_cell_size(truncate(label, width), width)
    return fitted


def view_rows(view: ResultsView, names: ShortNames, query: Query) -> list[TableRow]:
    """The table's rows for what ``view`` shows, shortened by ``names``,
    with the extra skills beyond ``query``'s (the results' own)."""
    rows = [
        table_row(solution, view.sort_key, names=names, query_skills=query.skills)
        for solution in view.final
    ]
    return rows
