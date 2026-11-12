"""The app and its main screen: the query editor above the results table."""

from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path
from threading import Event
from typing import ClassVar

from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding, BindingType
from textual.content import Content
from textual.message import Message
from textual.widgets import Button, Footer, Header, Static
from textual.worker import Worker

from mhp3ass.charms.my_charms import MyCharmsFileError
from mhp3ass.data.strings import DisplayStrings
from mhp3ass.data.text import read_lines
from mhp3ass.model import HunterType
from mhp3ass.query import QueryError
from mhp3ass.query_form import QueryForm
from mhp3ass.results.result_set import SearchResult
from mhp3ass.results.sorting import SortKey
from mhp3ass.results.table import TableRow
from mhp3ass.results.view import ResultsView
from mhp3ass.saved_data import TuiSettings, write_tui_settings
from mhp3ass.saved_state import Startup, settings_for, write_settings_cfg
from mhp3ass.search import (
    SearchCancelled,
    SearchData,
    WorkerPool,
    dotnet_exception_type,
    run_search,
)
from mhp3ass.settings_cfg import SettingsCfg
from mhp3ass.solution.state import LegacyNullReferenceError
from mhp3ass.tui.query_editor import QueryEditor
from mhp3ass.tui.results_pane import ResultsPane, view_rows
from mhp3ass.tui.results_table import ResultsTable
from mhp3ass.tui.search_progress import SearchProgress
from mhp3ass.tui.skill_picker import SkillPicker


@dataclass(frozen=True)
class AppFiles:
    """The files the app reads and saves: ``settings.cfg`` (and the index of
    the language it is in), ``mycharms.txt`` and ``tui.toml`` with its
    settings."""

    settings_cfg: Path
    language_index: int
    my_charms: Path
    tui_toml: Path
    tui_settings: TuiSettings


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
    #query_summary {
        display: none;
        height: auto;
        padding: 0 2;
        background: $panel;
    }
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
        Binding("h", "edit_field('hunter_type')", "Hunter", show=False),
        Binding("g", "edit_field('gender')", "Gender", show=False),
        Binding("r", "edit_field('hr')", "HR", show=False),
        Binding("v", "edit_field('elder_star')", "Village", show=False),
        Binding("w", "edit_field('weapon_slots')", "Weapon slots", show=False),
        Binding("m", "edit_field('charm_mode')", "Charm mode", show=False),
        Binding("k", "edit_field('skill_search')", "Skills", show=False),
        Binding("s", "focus('sort_key')", "Sort"),
        Binding("S", "reverse_sort", "Reverse"),
        Binding("slash", "find", "Find"),
        Binding("e", "edit_query", "Edit query"),
        Binding("n", "find_next(1)", "Next", show=False),
        Binding("N", "find_next(-1)", "Previous", show=False),
    ]

    def __init__(
        self,
        language: str,
        data: SearchData,
        strings: DisplayStrings,
        pool: WorkerPool | None,
        files: AppFiles,
        startup: Startup,
    ) -> None:
        super().__init__()
        self.sub_title = language
        self._language = language
        self._data = data
        self._pool = pool
        self._files = files
        self._strings = strings
        self._startup = startup
        self._last_search_gunner = startup.search.last_search_gunner
        # The editor owns the form; read it as ``self.editor.form``.
        self.editor = QueryEditor(startup.search.form, game=data.game, strings=strings)
        self.result: SearchResult | None = None
        self._search_number = 0
        self._cancel: Event | None = None
        self._worker: Worker[None] | None = None
        self._search_waiting = False
        # The form the running search started from, and the one the shown results came from.
        self._running_form: QueryForm | None = None
        self._searched_form: QueryForm | None = None

    def compose(self) -> ComposeResult:
        yield Header()
        yield Static(id="query_summary")
        yield self.editor
        yield SearchProgress()
        yield Static("Choose up to six skills, then Search.", id="hint")
        yield ResultsPane(
            self._strings,
            sort_key=self._startup.search.sort_key,
            reverse=self._files.tui_settings.reverse,
        )
        yield Footer()

    def on_mount(self) -> None:
        """Show the loaded results, if any, then save, as every load ends
        with ``SaveConfig`` (``Form1.h:456``)."""
        results = self._startup.search.results
        if results is not None:
            self._searched_form = results.form
            view = results.view
            self.query_one(ResultsPane).show(view, rows=view_rows(view), query=results.query)
            self._collapse_editor()
            count = len(view.all_solutions) + results.charm_free_only_under_none
            self.query_one("#hint", Static).update(f"{count:,} sets from last time.")
        if self._startup.notice is not None:
            self.notify(self._startup.notice, timeout=15)
        self._save()

    def _settings(self) -> SettingsCfg:
        """What ``SaveConfig`` writes: the form as edited, the sort and the
        shown results' ``all_solutions``."""
        pane = self.query_one(ResultsPane)
        view = pane.view
        settings = settings_for(
            self.editor.form,
            game=self._data.game,
            language_index=self._files.language_index,
            last_search_gunner=self._last_search_gunner,
            sort_key=pane.sort_key,
            solutions=view.all_solutions if view is not None else [],
        )
        return settings

    def _save(self) -> None:
        try:
            write_settings_cfg(self._files.settings_cfg, self._settings())
        except OSError as error:
            self.notify(f"Can't save {self._files.settings_cfg}: {error}", severity="error")

    def on_results_pane_sort_changed(self, event: ResultsPane.SortChanged) -> None:
        event.stop()
        self._save()

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
        self._running_form = form
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
        """Stop the search and keep the view as it was before it started; with
        no search running, close the reopened editor over the results."""
        if self._cancel is None:
            if self._searched_form is not None and self.editor.display:
                self._collapse_editor()
            return
        self._cancel.set()
        self._finish_search()

    def action_edit_query(self) -> None:
        """Reopen the editor over the results, unchanged."""
        self.action_edit_field("skill_search")

    def action_edit_field(self, widget_id: str) -> None:
        """Focus one of the editor's fields, reopening the editor if it's collapsed."""
        self.editor.display = True
        self.query_one("#query_summary", Static).display = False
        self.set_focus(self.query_one(f"#{widget_id}"))

    def _collapse_editor(self) -> None:
        """Show the summary of the form the results came from, not the form
        as edited since."""
        if self._searched_form is None:
            return
        summary = self.query_one("#query_summary", Static)
        summary.update(Content(f"{self._searched_form.summary(self._strings)}   e edit"))
        summary.display = True
        self.editor.display = False
        self.set_focus(self.query_one(ResultsTable))

    async def action_quit(self) -> None:
        """Save, as closing the original's window does (``Form1.h:564``), then exit."""
        # The search thread can't be killed; cancelling lets it return.
        if self._cancel is not None:
            self._cancel.set()
        try:
            write_settings_cfg(self._files.settings_cfg, self._settings())
        except OSError as error:
            self.exit(return_code=1, message=f"Can't save {self._files.settings_cfg}: {error}")
            return
        self.exit()

    def action_reverse_sort(self) -> None:
        pane = self.query_one(ResultsPane)
        pane.reverse_sort()
        tui_settings = replace(self._files.tui_settings, reverse=pane.reverse)
        try:
            write_tui_settings(self._files.tui_toml, tui_settings)
        except OSError as error:
            self.notify(f"Can't save {self._files.tui_toml}: {error}", severity="error")
            return
        self._files = replace(self._files, tui_settings=tui_settings)

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
                my_charms=tuple(read_lines(self._files.my_charms)),
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
        self._searched_form = self._running_form
        self._last_search_gunner = result.query.hunter_type is HunterType.GUNNER
        self.query_one(ResultsPane).show(view, rows=rows, query=result.query)
        self._collapse_editor()
        # SaveConfig once the last worker returns (Form1.h:1830).
        self._save()
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
