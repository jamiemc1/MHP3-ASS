"""The app and its main screen: the query editor above the results table."""

from __future__ import annotations

from pathlib import Path
from threading import Event
from typing import ClassVar

from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding, BindingType
from textual.message import Message
from textual.widgets import Button, Footer, Header, Static
from textual.worker import Worker

from mhp3ass.charms.my_charms import MyCharmsFileError
from mhp3ass.data.strings import DisplayStrings
from mhp3ass.data.text import read_lines
from mhp3ass.query import QueryError
from mhp3ass.query_form import QueryForm
from mhp3ass.results.result_set import SearchResult
from mhp3ass.results.sorting import SortKey
from mhp3ass.results.table import TableRow
from mhp3ass.results.view import ResultsView
from mhp3ass.search import (
    SearchCancelled,
    SearchData,
    WorkerPool,
    dotnet_exception_type,
    run_search,
)
from mhp3ass.solution.state import LegacyNullReferenceError
from mhp3ass.tui.query_editor import QueryEditor
from mhp3ass.tui.results_pane import ResultsPane, view_rows
from mhp3ass.tui.search_progress import SearchProgress
from mhp3ass.tui.skill_picker import SkillPicker


class Progressed(Message):
    """A search's combinations checked so far, posted from its thread."""

    def __init__(self, number: int, done: int, total: int) -> None:
        super().__init__()
        self.number = number
        self.done = done
        self.total = total


class SearchApp(App[None]):
    """The main screen: a header naming the language, the query editor, the
    search's progress, the results table and the footer of keys.

    One search runs at a time, in a thread. Each search has a number, and the
    progress and results of any search but the latest are dropped, so a
    cancelled search can't overwrite the view."""

    TITLE = "MHP3 Armor Set Search"
    CSS = """
    #hint {
        height: auto;
        padding: 1 2;
        color: $text-muted;
    }
    #results {
        height: 1fr;
    }
    """
    BINDINGS: ClassVar[list[BindingType]] = [
        ("q", "quit", "Quit"),
        Binding("ctrl+s", "search", "Search"),
        Binding("escape", "cancel_search", "Cancel", show=False),
        Binding("h", "focus('hunter_type')", "Hunter", show=False),
        Binding("g", "focus('gender')", "Gender", show=False),
        Binding("r", "focus('hr')", "HR", show=False),
        Binding("v", "focus('elder_star')", "Village", show=False),
        Binding("w", "focus('weapon_slots')", "Weapon slots", show=False),
        Binding("m", "focus('charm_mode')", "Charm mode", show=False),
        Binding("k", "focus('skill_search')", "Skills", show=False),
        Binding("s", "focus('sort_key')", "Sort"),
        Binding("S", "reverse_sort", "Reverse"),
        Binding("slash", "find", "Find"),
        Binding("n", "find_next(1)", "Next", show=False),
        Binding("N", "find_next(-1)", "Previous", show=False),
    ]

    def __init__(
        self,
        language: str,
        data: SearchData,
        strings: DisplayStrings,
        form: QueryForm,
        pool: WorkerPool | None,
        my_charms_path: Path,
    ) -> None:
        super().__init__()
        self.sub_title = language
        self._language = language
        self._data = data
        self._pool = pool
        self._my_charms_path = my_charms_path
        self._strings = strings
        # The editor owns the form; read it as ``self.editor.form``.
        self.editor = QueryEditor(form, game=data.game, strings=strings)
        self.result: SearchResult | None = None
        self._search_number = 0
        self._cancel: Event | None = None
        self._worker: Worker[None] | None = None
        self._search_waiting = False

    def compose(self) -> ComposeResult:
        yield Header()
        yield self.editor
        yield SearchProgress()
        yield Static("Choose up to six skills, then Search.", id="hint")
        yield ResultsPane(self._strings)
        yield Footer()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "search":
            event.stop()
            self.action_search()

    def on_skill_picker_search_requested(self, event: SkillPicker.SearchRequested) -> None:
        event.stop()
        self.action_search()

    def action_search(self) -> None:
        if self._cancel is not None:
            return
        # A cancelled search's thread may still be stopping, and the pool runs
        # one search at a time: this one starts when that thread returns.
        if self._worker is not None and not self._worker.is_finished:
            self._search_waiting = True
            return
        self._search_waiting = False
        form = self.editor.form
        if not any(row.skill is not None for row in form.current_rows()):
            self.notify("Choose at least one skill first.")
            return
        self._search_number += 1
        self._cancel = Event()
        self.query_one(SearchProgress).start()
        pane = self.query_one(ResultsPane)
        self._worker = self._run_search(
            form,
            number=self._search_number,
            cancel=self._cancel,
            sort_key=pane.sort_key,
            reverse=pane.reverse,
        )

    def action_cancel_search(self) -> None:
        """Stop the search and keep the view as it was before it started."""
        if self._cancel is None:
            return
        self._cancel.set()
        self._finish_search()

    async def action_quit(self) -> None:
        # The search thread can't be killed; cancelling lets it return.
        if self._cancel is not None:
            self._cancel.set()
        self.exit()

    def action_reverse_sort(self) -> None:
        self.query_one(ResultsPane).reverse_sort()

    def action_find(self) -> None:
        self.query_one(ResultsPane).open_find()

    def action_find_next(self, step: int) -> None:
        self.query_one(ResultsPane).find(step=step)

    def on_worker_state_changed(self, event: Worker.StateChanged) -> None:
        if event.worker is self._worker and event.worker.is_finished and self._search_waiting:
            self.action_search()

    def on_progressed(self, event: Progressed) -> None:
        if event.number == self._search_number and self._cancel is not None:
            self.query_one(SearchProgress).advance(event.done, event.total)

    @work(thread=True, group="search")
    def _run_search(
        self, form: QueryForm, number: int, cancel: Event, sort_key: SortKey, reverse: bool
    ) -> None:
        """The search, then its view sorted as the pane shows results (reading
        every solution back from the pool's records, so off the UI thread)."""

        def report(done: int, total: int) -> None:
            # post_message doesn't wait for the UI, so the search doesn't either.
            self.post_message(Progressed(number=number, done=done, total=total))

        try:
            spec = form.search_spec(
                self._data.game,
                language=self._language,
                my_charms=tuple(read_lines(self._my_charms_path)),
            )
            result = run_search(
                spec,
                data=self._data,
                record_exceptions=True,
                pool=self._pool,
                on_progress=report,
                cancel=cancel,
            )
        except SearchCancelled:
            return
        except (
            OSError,
            UnicodeDecodeError,
            QueryError,
            MyCharmsFileError,
            LegacyNullReferenceError,
            LookupError,
        ) as error:
            # mycharms.txt missing or not UTF-8, a skill or my-charms line the
            # original would refuse, or a throw the original's GUI reports
            # outside the workers (quirk 35).
            self.call_from_thread(self._search_failed, number, error)
            return
        if cancel.is_set():
            return
        view = ResultsView.from_search(result.results, sort_key=sort_key, reverse=reverse)
        rows = view_rows(view)
        self.call_from_thread(self._search_finished, number, result, view, rows)

    def _search_finished(
        self, number: int, result: SearchResult, view: ResultsView, rows: list[TableRow]
    ) -> None:
        if number != self._search_number or self._cancel is None:
            return
        self._finish_search()
        self.result = result
        self.query_one(ResultsPane).show(view, rows=rows, query=result.query)
        count = len(result.results.all_solutions)
        summary = f"{count:,} sets."
        if result.exception is not None:
            summary += (
                f" Worker {result.exception.worker + 1} of {result.worker_count} stopped with "
                f"{result.exception.type}, as the original's would; its sets and later "
                "workers' are missing."
            )
        self.query_one("#hint", Static).update(summary)

    def _search_failed(self, number: int, error: Exception) -> None:
        if number != self._search_number or self._cancel is None:
            return
        self._finish_search()
        exception_type = dotnet_exception_type(error)
        message = str(error) if exception_type is None else f"The original throws {exception_type}"
        self.notify(message, title="Search failed", severity="error")

    def _finish_search(self) -> None:
        self._cancel = None
        self.query_one(SearchProgress).stop()
