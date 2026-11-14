"""The app and its main screen: the query editor above the results table."""

from __future__ import annotations

import asyncio
import signal
import sys
from collections.abc import Iterable
from dataclasses import dataclass, replace
from functools import partial
from pathlib import Path
from threading import Event, Lock
from typing import Any, ClassVar

from textual import events, work
from textual.actions import parse
from textual.app import App, ComposeResult, SystemCommand
from textual.binding import BindingType
from textual.containers import Horizontal
from textual.css.query import NoMatches
from textual.geometry import Size
from textual.message import Message
from textual.screen import Screen
from textual.theme import Theme
from textual.widget import Widget
from textual.widgets import Button, Footer, Label, OptionList, Select, Static
from textual.worker import Worker

from mhp3ass.charms.my_charms import MyCharmsFileError
from mhp3ass.data.strings import DisplayStrings, StringIndex
from mhp3ass.data.text import read_lines
from mhp3ass.escape import EscapeState, EscapeStep, escape_step
from mhp3ass.key_help import KeyEntry, help_sections
from mhp3ass.keys import app_keys, palette_commands
from mhp3ass.language_switch import switch_language
from mhp3ass.layout import (
    InspectorPlace,
    Layout,
    height_breakpoints,
    layout_for,
    width_breakpoints,
)
from mhp3ass.model import HunterType
from mhp3ass.parallel import SearchPool, usable_cpus
from mhp3ass.query import QueryError
from mhp3ass.query_form import QueryForm
from mhp3ass.regions import Region, next_region
from mhp3ass.results.result_set import SearchResult
from mhp3ass.results.short_names import ShortNames
from mhp3ass.results.sorting import SortKey
from mhp3ass.results.table import TableRow
from mhp3ass.results.view import ResultsView
from mhp3ass.saved_data import TuiFolders, TuiSettings, write_tui_settings
from mhp3ass.saved_folder import (
    ClearChoice,
    FolderChoice,
    change_folder,
    clear,
    clear_targets,
    folder_choices,
    with_folder,
)
from mhp3ass.saved_state import Startup, settings_for, write_settings_cfg
from mhp3ass.search import (
    SearchCancelled,
    SearchData,
    dotnet_exception_type,
    run_search,
)
from mhp3ass.settings_cfg import SettingsCfg
from mhp3ass.solution.state import LegacyNullReferenceError
from mhp3ass.spatial import Direction, FieldBox, neighbour
from mhp3ass.themes import starting_theme
from mhp3ass.tui.help_screen import HelpScreen
from mhp3ass.tui.inspector import Inspector
from mhp3ass.tui.options import ChoiceScreen, OptionsScreen, ThemeList
from mhp3ass.tui.query_editor import QueryEditor
from mhp3ass.tui.results_pane import ResultsPane, view_rows
from mhp3ass.tui.results_table import ResultsTable
from mhp3ass.tui.search_progress import SearchProgress
from mhp3ass.tui.skill_picker import SkillPicker
from mhp3ass.tui.sort_picker import SortPicker
from mhp3ass.tui.titles import region_title


@dataclass(frozen=True)
class AppFiles:
    """The files the app reads and saves: ``settings.cfg`` (and the index of
    the language it is in), ``mycharms.txt``, and the folders with
    ``tui.toml``'s settings."""

    settings_cfg: Path
    language_index: int
    my_charms: Path
    folders: TuiFolders


class Progressed(Message):
    """A search's combinations checked so far, posted from its thread."""

    def __init__(self, number: int, done: int, total: int) -> None:
        super().__init__()
        self.number = number
        self.done = done
        self.total = total


class SearchApp(App[bool]):
    """The main screen: the query editor (or, once there are results, a
    line summing up their query), the search's progress, the results and
    the footer of keys.

    The app's result is whether to start again: after the saved-data folder
    changes or is cleared, it exits with ``True`` so that start-up reads the
    folder afresh.

    One search runs at a time, in a thread. Each search has a number, and the
    progress and results of any search but the latest are dropped, so a
    cancelled search can't overwrite the view."""

    TITLE = "MHP3 Armor Set Search"
    CSS = """
    #query_line {
        display: none;
        height: 1;
        padding: 0 1;
        background: $panel;
    }
    #query_summary {
        width: 1fr;
        text-wrap: nowrap;
        text-overflow: ellipsis;
    }
    #query_keys {
        width: auto;
        padding: 0 0 0 2;
        color: $text-muted;
    }
    .pane {
        border: round $foreground 25%;
        border-title-color: $foreground;
    }
    .pane:focus, .pane:focus-within {
        border: round $accent;
    }
    QueryEditor.pane {
        border: none;
        border-top: round $foreground 25%;
    }
    QueryEditor.pane:focus-within {
        border: none;
        border-top: round $accent;
    }
    #small_note {
        display: none;
        dock: bottom;
        height: 1;
        padding: 0 1;
        background: $panel;
        color: $text-muted;
    }
    /* The width classes (``layout``); the results pane's own CSS is scoped to it. */
    Screen.-huge ResultsPane Inspector {
        width: 56;
    }
    Screen.-medium ResultsPane #charm_filter, Screen.-narrow ResultsPane #charm_filter {
        display: none;
    }
    Screen.-medium ResultsPane #charms_bar, Screen.-narrow ResultsPane #charms_bar {
        display: block;
    }
    /* The classes ``_fit_layout`` sets from the layout as a whole. */
    Screen.-inspector-over ResultsPane Inspector {
        display: none;
    }
    Screen.-inspector-over ResultsPane.-inspecting Inspector {
        display: block;
        width: 1fr;
    }
    Screen.-inspector-over ResultsPane.-inspecting #sets {
        display: none;
    }
    Screen.-portrait ResultsPane {
        layout: vertical;
    }
    Screen.-portrait ResultsPane #sets {
        height: 3fr;
    }
    Screen.-portrait ResultsPane Inspector {
        width: 1fr;
        height: 2fr;
    }
    Screen.-editor-over ResultsPane {
        display: none;
    }
    Screen.-small ResultsPane #charm_filter, Screen.-small ResultsPane #charms_bar {
        display: none;
    }
    Screen.-small Footer {
        display: none;
    }
    Screen.-small #small_note {
        display: block;
    }
    """
    BINDINGS: ClassVar[list[BindingType]] = [*app_keys()]
    # Esc restores a maximised region in its turn (``escape_step``), not first.
    ESCAPE_TO_MINIMIZE = False
    # The screen's width and height classes (``layout``), for the CSS's ``Screen.-narrow …``.
    HORIZONTAL_BREAKPOINTS = width_breakpoints()
    VERTICAL_BREAKPOINTS = height_breakpoints()

    def __init__(
        self,
        languages: list[str],
        language: str,
        data: SearchData,
        strings: DisplayStrings,
        pool: SearchPool | None,
        jobs: int,
        files: AppFiles,
        startup: Startup,
    ) -> None:
        """``pool`` searches in ``jobs`` processes (``None`` with one job,
        which searches in this process). Options can replace the pool, so
        whoever runs the app closes ``app.pool`` afterwards."""
        super().__init__()
        self._languages = languages
        self._language = language
        self._data = data
        self.pool = pool
        self.jobs = jobs
        self._files = files
        self._strings = strings
        self._startup = startup
        # Held by a search and by the inspector's placements: both set the abilities' relevance.
        self._game_lock = Lock()
        # The table's short piece and charm names, in the game's current language.
        self._short_names = ShortNames.from_game(data.game)
        self._last_search_gunner = startup.search.last_search_gunner
        # How the results pane shows them, kept to rebuild it in another language.
        self._sort_key = startup.search.sort_key
        self._reverse = files.folders.settings.reverse
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
        # Set once the app has asked to exit, so a late signal doesn't save over what it left.
        self._exiting = False
        theme = starting_theme(files.folders.settings.theme, available=self.available_themes)
        self.theme = theme.name
        self._theme_unavailable = theme.unavailable
        # While Options' theme list shows a theme under its cursor, that theme isn't kept.
        self._theme_previewing = False

    def compose(self) -> ComposeResult:
        with Horizontal(id="query_line"):
            yield Static(id="query_summary")
            yield Label("1 edit", id="query_keys")
        yield self.editor
        yield SearchProgress()
        yield ResultsPane(
            self._strings,
            sort_key=self._sort_key,
            reverse=self._reverse,
            is_searching=self._searching,
            game_lock=self._game_lock,
            short_names=self._short_names,
            full_names=self._layout().full_names,
        )
        yield Static("terminal small: ? for keys", id="small_note")
        yield Footer(compact=True)

    def on_mount(self) -> None:
        """Show the loaded results, if any, then save, as every load ends
        with ``SaveConfig`` (``Form1.h:456``)."""
        results = self._startup.search.results
        if results is not None:
            self._searched_form = results.form
            view = results.view
            pane = self.query_one(ResultsPane)
            # Reversed before the rows are built, so show needn't build them again.
            view.select_reverse(pane.reverse)
            # The file doesn't keep which charms the search ran with.
            pane.show(
                view,
                rows=view_rows(view, names=pane.table_names, query=results.query),
                query=results.query,
                game=self._data.game,
                charm_templates=None,
            )
            self._collapse_editor()
        if self._startup.notice is not None:
            self.notify(self._startup.notice, timeout=15)
        if self._theme_unavailable is not None:
            self.notify(
                f"{self._files.folders.settings_file} names the theme "
                f"{self._theme_unavailable!r}, which isn't available; using {self.theme}.",
                markup=False,
            )
        # The command palette's Theme command changes the theme too.
        self.theme_changed_signal.subscribe(self, self._theme_changed)
        self._save()
        self._save_on_close_signals()

    def on_resize(self, event: events.Resize) -> None:
        # The event's size: the app's own can still be the old one here.
        self._fit_layout(event.size)

    def _layout(self) -> Layout:
        """The main screen's layout at the terminal's size."""
        layout = layout_for(self.size.width, height=self.size.height)
        return layout

    def _fit_layout(self, size: Size) -> None:
        """Lay the main screen out for a terminal of ``size`` and what is
        open: the classes its CSS reads beyond the breakpoints' own, the
        editor's height, the table's names and the footer."""
        main = self.screen_stack[0]
        try:
            # The main screen's, though a modal may be the one showing.
            pane = main.query_one(ResultsPane)
            footer = main.query_one(Footer)
            sidebar = main.query_one("#charm_filter", OptionList)
            choice = main.query_one("#charm_choice", Select)
        except NoMatches:
            # The screen is being composed again (a language switch).
            return
        layout = layout_for(size.width, height=size.height)
        has_results = self._searched_form is not None
        over_results = layout.editor_covers_results(
            editor_open=self.editor.display, has_results=has_results
        )
        main.set_class(layout.inspector is InspectorPlace.OVER, "-inspector-over")
        portrait = layout.inspector is InspectorPlace.BELOW
        if portrait != main.has_class("-portrait"):
            main.set_class(portrait, "-portrait")
            # Its text keeps the height it had at its old width until laid out again.
            self.call_after_refresh(pane.query_one(Inspector).relayout)
        main.set_class(over_results, "-editor-over")
        main.set_class(layout.small, "-small")
        main.query_one("#query_line", Horizontal).display = layout.shows_query_line(
            editor_open=self.editor.display, has_results=has_results
        )
        self.editor.fit_height(size.height, over_results=over_results)
        pane.name_in_full(layout.full_names)
        # The inspector has a place of its own again.
        if layout.inspector is not InspectorPlace.OVER and pane.inspecting:
            pane.show_inspector(False)
            self._focus_region(Region.SETS)
        # The focus leaves what the layout hides: the charms move between the
        # sidebar and the drop-down once the screen's new class has shown the
        # other; with no charms shown, or the editor over the results, it goes
        # to the sets or the editor.
        focused = main.focused
        within = focused.ancestors_with_self if focused is not None else []
        hidden = (
            [sidebar, choice]
            if not layout.charms_shown
            else [choice if layout.sidebar else sidebar]
        )
        if over_results and pane in within:
            self._focus_editor_end(1)
        elif any(widget in within for widget in hidden):
            region = Region.CHARMS if layout.charms_shown else Region.SETS
            self.call_after_refresh(self._focus_region, region)
        footer.show_command_palette = layout.footer_palette
        # Whether ``i`` shows in the footer depends on the layout.
        self.refresh_bindings()

    def _save_on_close_signals(self) -> None:
        """Closing the terminal sends SIGHUP and a shutdown sends SIGTERM; Textual
        handles neither, so either would kill the app without the save that
        closing the original's window makes. Windows has no SIGHUP, and its event
        loop can't take signal handlers."""
        if sys.platform == "win32":
            return
        loop = asyncio.get_running_loop()
        for number in (signal.SIGHUP, signal.SIGTERM):
            loop.add_signal_handler(number, self._save_and_exit)

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

    def _write_settings(self) -> str | None:
        """Write ``settings.cfg``; why it couldn't be written, or ``None``."""
        try:
            write_settings_cfg(self._files.settings_cfg, self._settings())
        except OSError as error:
            failure = f"Can't save {self._files.settings_cfg}: {error}"
            return failure
        return None

    def _save(self) -> None:
        failure = self._write_settings()
        if failure is not None:
            self.notify(failure, severity="error", markup=False)

    def on_results_pane_sort_changed(self, event: ResultsPane.SortChanged) -> None:
        event.stop()
        self._save()

    def action_options(self) -> None:
        self.push_screen(
            OptionsScreen(
                self.editor.form,
                strings=self._strings,
                languages=self._languages,
                language=self._language,
                jobs=self.jobs,
                max_jobs=max(usable_cpus(), self.jobs),
                saved_folder=self._files.folders.saved,
                folder_locked=self._files.folders.saved_set_by_env,
                themes=sorted(self.available_themes),
                theme=self.theme,
            ),
            # Closing Options while a theme is shown keeps it.
            lambda _: self._keep_theme(self.theme) if self._theme_previewing else None,
        )

    def on_theme_list_previewed(self, event: ThemeList.Previewed) -> None:
        event.stop()
        self._theme_previewing = True
        self.theme = event.theme

    def on_theme_list_kept(self, event: ThemeList.Kept) -> None:
        event.stop()
        self._keep_theme(event.theme)

    def _theme_changed(self, theme: Theme) -> None:
        if not self._theme_previewing:
            self._keep_theme(self.theme)

    def _keep_theme(self, name: str) -> None:
        """Use theme ``name`` and save it in ``tui.toml``, unless it already holds it."""
        self._theme_previewing = False
        self.theme = name
        if self._files.folders.settings.theme == name:
            return
        self._save_tui_settings(replace(self._files.folders.settings, theme=name))

    def on_options_screen_folder_chosen(self, event: OptionsScreen.FolderChosen) -> None:
        """Ask what to do with the files, as ``folder_choices`` allows."""
        event.stop()
        current = self._files.folders.saved
        choices = folder_choices(current, event.folder)
        if not choices:
            self.notify(f"{event.folder} is the folder in use, or isn't a folder.", markup=False)
            return
        labels = {
            FolderChoice.MOVE: f"Move settings.cfg and mycharms.txt from {current} there",
            FolderChoice.FRESH: "Start fresh there (the files here stay where they are)",
            FolderChoice.USE: "Use the files already there",
        }
        self.push_screen(
            ChoiceScreen(
                title="Saved data",
                text=f"Keep saved data in {event.folder}?",
                answers=[(labels[choice], choice) for choice in choices],
            ),
            lambda choice: self._change_folder(event.folder, choice),
        )

    def _change_folder(self, folder: Path, choice: FolderChoice | None) -> None:
        """Save, carry out ``choice``, record the folder in ``tui.toml``, then
        start again from it."""
        if choice is None:
            return
        if self._searching():
            self.notify("The folder can change once the search has finished.")
            return
        self._save()
        current = self._files.folders.saved
        try:
            change_folder(current, folder, choice)
        except OSError as error:
            self.notify(f"Can't use {folder}: {error}", severity="error", markup=False)
            return
        if self._save_tui_settings(with_folder(self._files.folders, folder)):
            self._start_again()

    def on_options_screen_clear_requested(self, event: OptionsScreen.ClearRequested) -> None:
        event.stop()
        folder = self._files.folders.saved
        answers = []
        for label, choice in (
            ("The saved search and results", ClearChoice.SEARCH),
            ("My charms (back to the shipped list)", ClearChoice.MY_CHARMS),
            ("Everything", ClearChoice.EVERYTHING),
        ):
            targets = clear_targets(folder, choice)
            if not targets:
                continue
            names = ", ".join(path.name for path in targets)
            if choice is ClearChoice.SEARCH:
                # The language lives in settings.cfg too; it stays, so my charms still load.
                answers.append((f"{label}: resets {names}, keeping the language", choice))
            else:
                answers.append((f"{label}: deletes {names}", choice))
        if not answers:
            self.notify(f"{folder} has nothing to clear.", markup=False)
            return
        self.push_screen(
            ChoiceScreen(title="Clear", text=f"Clear in {folder}:", answers=answers),
            self._clear,
        )

    def _clear(self, choice: ClearChoice | None) -> None:
        """Clear the chosen files, then start again without them. Clearing the
        search writes the starting form in the current language rather than
        deleting the file, so a ``mycharms.txt`` written in that language
        (quirk 30) still loads."""
        if choice is None:
            return
        if self._searching():
            self.notify("Saved data can be cleared once the search has finished.")
            return
        try:
            if choice is ClearChoice.SEARCH:
                starting = settings_for(
                    QueryForm.starting(),
                    game=self._data.game,
                    language_index=self._files.language_index,
                    last_search_gunner=False,
                    sort_key=SortKey.NONE,
                    solutions=[],
                )
                write_settings_cfg(self._files.settings_cfg, starting)
            else:
                clear(self._files.folders.saved, choice)
        except OSError as error:
            self.notify(f"Can't clear: {error}", severity="error", markup=False)
            return
        self._start_again()

    def on_options_screen_option_changed(self, event: OptionsScreen.OptionChanged) -> None:
        """A toggle applies to the next search and saves, as ``OptionsChanged``
        does (``Form1.h:1218-1223``)."""
        event.stop()
        changes: dict[str, Any] = {event.field: event.value}
        self.editor.form = replace(self.editor.form, **changes)
        self._save()

    def _searching(self) -> bool:
        """A search, or a cancelled one's thread, is still running."""
        running = self._cancel is not None or (
            self._worker is not None and not self._worker.is_finished
        )
        return running

    async def on_options_screen_language_chosen(self, event: OptionsScreen.LanguageChosen) -> None:
        """``LanguageSelect_Click``: rename everything, rewrite my charms in the
        new language, then show every widget again in it and save."""
        event.stop()
        # The modal is opened again on every path, so it shows what is in use.
        await self.pop_screen()
        if self._searching():
            self.notify("The language can change once the search has finished.")
            self.action_options()
            return
        self.query_one(ResultsPane).stop_placements()
        try:
            # Waits for a placement already being worked out, which reads the game's records.
            with self._game_lock:
                strings = switch_language(
                    self._data.game,
                    validity=self._data.validity,
                    data_dir=self._data.data_dir,
                    language=event.language,
                    my_charms_path=self._files.my_charms,
                )
        except (OSError, ValueError, MyCharmsFileError) as error:
            # No such language folder or a broken file in it, an unreadable or
            # unwritable mycharms.txt, or one the original couldn't load.
            self.notify(f"Can't switch to {event.language}: {error}", severity="error")
            self.action_options()
            return
        self._language = event.language
        self._strings = strings
        self._short_names = ShortNames.from_game(self._data.game)
        self._files = replace(self._files, language_index=self._languages.index(event.language))
        await self._rebuild()
        self._save()
        self.action_options()

    async def _rebuild(self) -> None:
        """Compose the screen again in the current language, keeping the form,
        the sort and its direction, the results with the charm chosen and the
        cursor's set, and whether the editor is collapsed."""
        pane = self.query_one(ResultsPane)
        view = pane.view
        query = pane.results_query
        charm_templates = pane.charm_templates
        note = pane.note
        cursor = self.query_one(ResultsTable).cursor
        show_wide = self.query_one(ResultsTable).show_wide
        column_start = self.query_one(ResultsTable).column_start
        collapsed = not self.editor.display
        self._sort_key = pane.sort_key
        self._reverse = pane.reverse
        self.editor = QueryEditor(self.editor.form, game=self._data.game, strings=self._strings)
        await self.recompose()
        if view is not None and query is not None:
            view.relanguage()
            pane = self.query_one(ResultsPane)
            pane.show(
                view,
                rows=view_rows(view, names=pane.table_names, query=query),
                query=query,
                game=self._data.game,
                charm_templates=charm_templates,
                note=note,
            )
            self.query_one(ResultsTable).cursor = cursor
        self.query_one(ResultsTable).set_show_wide(show_wide, first=column_start)
        if collapsed:
            self._collapse_editor()
        else:
            self._fit_layout(self.size)

    def on_options_screen_jobs_chosen(self, event: OptionsScreen.JobsChosen) -> None:
        """Start a pool of the new size at once, close the old one in the
        background, and keep the choice in ``tui.toml``."""
        event.stop()
        if self._searching():
            self.pop_screen()
            self.notify("The search's processes can change once the search has finished.")
            self.action_options()
            return
        old_pool = self.pool
        self.pool = SearchPool(jobs=event.jobs) if event.jobs > 1 else None
        if self.pool is not None:
            self.pool.start()
        self.jobs = event.jobs
        if old_pool is not None:
            self._close_pool(old_pool)
        self._save_tui_settings(replace(self._files.folders.settings, jobs=event.jobs))

    @work(thread=True, group="pool")
    def _close_pool(self, pool: SearchPool) -> None:
        pool.close()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "search":
            event.stop()
            self.action_search()

    def on_skill_picker_search_requested(self, event: SkillPicker.SearchRequested) -> None:
        event.stop()
        self.action_search()

    def on_skill_picker_left_upwards(self, event: SkillPicker.LeftUpwards) -> None:
        event.stop()
        self.action_spatial(Direction.UP.value)

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
        pane.show_searching(True)
        self._worker = self._run_search(
            form,
            number=self._search_number,
            cancel=self._cancel,
            sort_key=pane.sort_key,
            reverse=pane.reverse,
            names=pane.table_names,
        )

    def action_cancel_search(self) -> None:
        """Stop the search and keep the view as it was before it started."""
        if self._cancel is None:
            return
        self._cancel.set()
        self._finish_search()

    def action_back_out(self) -> None:
        """Esc on the main screen: back out of one level, the one
        ``escape_step`` picks. A modal closes on its own Esc."""
        if len(self.screen_stack) > 1:
            return
        try:
            pane = self.query_one(ResultsPane)
            skill_picker = self.editor.query_one(SkillPicker)
        except NoMatches:
            # The screen is being composed again (a language switch).
            return
        focused = self.focused
        state = EscapeState(
            popup_open=skill_picker.options_open,
            find_open=pane.find_open,
            inspector_open=pane.inspecting,
            maximised=self.screen.maximized is not None,
            editor_open=self.editor.display,
            can_collapse=self._searched_form is not None,
            editor_focused=focused is not None and self.editor in focused.ancestors_with_self,
            searching=self._cancel is not None,
        )
        match escape_step(state):
            case EscapeStep.CLOSE_POPUP:
                skill_picker.dismiss_options()
            case EscapeStep.CLEAR_FIND:
                pane.clear_find()
            case EscapeStep.RESTORE_REGION:
                self.screen.minimize()
            case EscapeStep.CLOSE_INSPECTOR:
                pane.show_inspector(False)
                self._focus_region(Region.SETS)
            case EscapeStep.COLLAPSE_EDITOR:
                self._collapse_editor()
            case EscapeStep.LEAVE_EDITOR:
                self._focus_region(Region.SETS)
            case EscapeStep.CANCEL_SEARCH:
                self.action_cancel_search()
            case EscapeStep.NOTHING:
                pass

    def action_edit_query(self) -> None:
        """Reopen the editor over the results, unchanged."""
        self.action_edit_field("skill_search")

    def action_region(self, number: int) -> None:
        """``1`` opens the editor at the skills (as ``e`` does), ``2`` and ``3``
        focus the charm sidebar and the sets."""
        region = Region(number)
        self._close_inspector()
        if region is Region.QUERY:
            self.action_edit_query()
        else:
            self._focus_region(region)

    def check_action(self, action: str, parameters: tuple[object, ...]) -> bool | None:
        # Regions are the main screen's: over a modal or the palette, Tab and z are theirs.
        if action in {"cycle", "maximise"} and len(self.screen_stack) > 1:
            return False
        # Text boxes and lists keep their own arrows, and an open drop-down its ▲▼.
        if action == "spatial" and not self._on_spatial_field():
            return False
        # Beside the table the inspector already shows.
        if action == "inspect" and (
            len(self.screen_stack) > 1
            or self._layout().inspector is not InspectorPlace.OVER
            or self.screen_stack[0].has_class("-editor-over")
        ):
            return False
        return super().check_action(action, parameters)

    def _on_spatial_field(self) -> bool:
        """The focus is on one of the main screen's editor's drop-downs or buttons."""
        focused = self.focused
        on_field = (
            len(self.screen_stack) == 1
            and isinstance(focused, Select | Button)
            and self.editor in focused.ancestors
        )
        return on_field

    def action_spatial(self, direction: str) -> None:
        """An arrow on an editor field: the field beside it, or on the row
        above or below (``spatial.neighbour``). Each of the editor's
        horizontal containers is a row; a field outside one is a row of its own.
        An arrow with no field that way does nothing (⏎ or space opens a drop-down)."""
        fields = self._editor_fields()
        current = self._focused_field(fields)
        if current is None:
            return
        rows: dict[Widget, list[FieldBox]] = {}
        for key, widget in enumerate(fields):
            row = next(
                (ancestor for ancestor in widget.ancestors if isinstance(ancestor, Horizontal)),
                widget,
            )
            rows.setdefault(row, []).append(
                FieldBox(key, x=self._editor_x(widget), width=widget.virtual_region.width)
            )
        target = neighbour(list(rows.values()), current=current, direction=Direction(direction))
        if target is not None:
            fields[target].focus()

    def _focused_field(self, fields: list[Widget]) -> int | None:
        """The index of the focused widget in ``fields``, or ``None``."""
        focused = self.focused
        index = next((index for index, field in enumerate(fields) if field is focused), None)
        return index

    def _editor_x(self, widget: Widget) -> int:
        """``widget``'s column in the editor's own frame, whatever the
        containers between them (each ``virtual_region`` is its container's)."""
        x = widget.virtual_region.x
        for ancestor in widget.ancestors:
            if ancestor is self.editor:
                break
            if isinstance(ancestor, Widget):
                x += ancestor.virtual_region.x
        return x

    def action_cycle(self, step: int) -> None:
        """Tab (``step`` 1) and Shift+Tab (-1): inside the open editor, the
        next or previous field, leaving it past either end; elsewhere, the
        next or previous region (``next_region``)."""
        try:
            region = self._focused_region()
            pane = self.query_one(ResultsPane)
        except NoMatches:
            # The screen is being composed again (a language switch).
            return
        # The inspector over the table gives way, so the regions can be seen.
        if pane.inspecting:
            pane.show_inspector(False)
            region = Region.SETS
        editor_open = self.editor.display
        if region is Region.QUERY and editor_open:
            fields = self._editor_fields()
            current = self._focused_field(fields)
            if current is not None and 0 <= current + step < len(fields):
                fields[current + step].focus()
                return
        target = next_region(
            region,
            step=step,
            editor_open=editor_open,
            charms_shown=self._layout().charms_shown,
        )
        if target is Region.QUERY:
            self._focus_editor_end(step)
        else:
            self._focus_region(target)

    def _focused_region(self) -> Region | None:
        focused = self.focused
        if focused is None:
            return None
        ancestors = focused.ancestors_with_self
        if self.editor in ancestors:
            return Region.QUERY
        if self.query_one("#charm_filter", OptionList) in ancestors:
            return Region.CHARMS
        # The charm drop-down, in the sets pane, stands in for the sidebar.
        if self.query_one("#charm_choice", Select) in ancestors:
            return Region.CHARMS
        if self.query_one("#sets") in ancestors:
            return Region.SETS
        return None

    def _editor_fields(self) -> list[Widget]:
        """The open editor's widgets that take focus, in Tab order."""
        fields = [widget for widget in self.screen.focus_chain if self.editor in widget.ancestors]
        return fields

    def _focus_editor_end(self, step: int) -> None:
        """Entering the open editor: its first field going forwards (``step``
        1), its last going back."""
        fields = self._editor_fields()
        if fields:
            self._restore_unless_within(self.editor)
            fields[0 if step > 0 else -1].focus()

    def _restore_unless_within(self, widget: Widget) -> None:
        """Restore a maximised region, unless ``widget`` is in it: the
        focus is moving to ``widget``."""
        maximised = self.screen_stack[0].maximized
        if maximised is not None and maximised not in widget.ancestors_with_self:
            self.screen_stack[0].minimize()

    def _focus_region(self, region: Region) -> None:
        """Focus the charm sidebar (the charm drop-down where the sidebar
        doesn't show), or the sets: the find box while it is open, else the
        table."""
        if region is Region.QUERY:
            raise ValueError("the query is entered through its fields, not as a whole")
        # The editor over the results gives them back.
        if self.screen_stack[0].has_class("-editor-over"):
            self._collapse_editor()
        layout = self._layout()
        if region is Region.CHARMS:
            # A small screen shows neither the sidebar nor the drop-down.
            if not layout.charms_shown:
                return
            charms = (
                self.query_one("#charm_filter", OptionList)
                if layout.sidebar
                else self.query_one("#charm_choice", Select)
            )
            self._restore_unless_within(charms)
            charms.focus()
            return
        find_box = self.query_one("#find_box")
        target = find_box if find_box.display else self.query_one(ResultsTable)
        self._restore_unless_within(target)
        target.focus()

    def action_edit_field(self, widget_id: str) -> None:
        """Focus one of the editor's fields, reopening the editor if it's collapsed."""
        self._close_inspector()
        self._restore_unless_within(self.editor)
        self.editor.display = True
        self.set_focus(self.query_one(f"#{widget_id}"))
        # With the focus in the editor, covering the results moves nothing.
        self._fit_layout(self.size)

    def action_set_field(self, widget_id: str) -> None:
        """Focus one of the editor's drop-downs and open it."""
        self.action_edit_field(widget_id)
        # A collapsed editor has just been shown: open the drop-down once it is laid out.
        self.call_after_refresh(self.query_one(f"#{widget_id}", Select).action_show_overlay)

    def action_help(self) -> None:
        """``?``: the keys that work where the focus is (``help_sections``),
        from the screen's active bindings, over the screen. The app's and
        the main screen's work everywhere, but for the arrows between the
        editor's fields, which only work on them; a modal's are its own."""
        screen = self.screen
        main = self.screen_stack[0]
        entries = [
            KeyEntry(
                key=self.get_key_display(active.binding),
                action=active.binding.action,
                description=active.binding.description,
                everywhere=(active.node is self or active.node is main)
                and parse(active.binding.action)[1] != "spatial",
            )
            for active in screen.active_bindings.values()
            if active.enabled
        ]
        region = self._help_region() if screen is self.screen_stack[0] else "Here"
        self.push_screen(HelpScreen(help_sections(entries, region=region), title=f"Keys: {region}"))

    def _help_region(self) -> str:
        """The name of the region the focus is in, for the help's title."""
        focused = self.focused
        if focused is not None and any(
            isinstance(node, Inspector) for node in focused.ancestors_with_self
        ):
            return "Inspector"
        region = self._focused_region()
        name = region.name.title() if region is not None else "Here"
        return name

    def get_system_commands(self, screen: Screen[Any]) -> Iterable[SystemCommand]:
        """Textual's commands, but ``?``'s help in place of its keys panel
        (not over the help itself) and, on the main screen, ``z`` in place
        of its maximise; then the main screen's by name (``palette_commands``).
        Over a modal only Textual's and the help, as the main screen's
        fields aren't there."""
        main = screen is self.screen_stack[0]
        replaced = {"Keys", "Maximize", "Minimize"} if main else {"Keys"}
        yield from (
            command
            for command in super().get_system_commands(screen)
            if command.title not in replaced
        )
        if not isinstance(screen, HelpScreen):
            yield SystemCommand(
                "Keys", "The keys that work where the focus is (?)", self.action_help
            )
        if not main:
            return
        commands = palette_commands(
            has_results=self.query_one(ResultsPane).view is not None,
            searching=self._cancel is not None,
            inspector_over=self._layout().inspector is InspectorPlace.OVER,
        )
        for command in commands:
            yield SystemCommand(
                command.title, command.help, partial(self.run_action, command.action)
            )

    def _collapse_editor(self) -> None:
        """Show the summary of the form the results came from, not the form
        as edited since."""
        if self._searched_form is None:
            return
        self._restore_unless_within(self.query_one(ResultsTable))
        summary = self.query_one("#query_summary", Static)
        summary.update(region_title(Region.QUERY, self._searched_form.summary(self._strings)))
        self.editor.display = False
        self._fit_layout(self.size)
        # The inspector over the table keeps the focus while it shows.
        if not self.query_one(ResultsPane).inspecting:
            self.set_focus(self.query_one(ResultsTable))

    async def action_quit(self) -> None:
        self._save_and_exit()

    def _save_and_exit(self) -> None:
        """Save, as closing the original's window does (``Form1.h:564``), then
        exit; a failed save is printed after the exit, where it can be seen.
        Once the app is on its way out, a second call (a SIGTERM after a
        SIGHUP, or a signal after a clear or a folder change has asked to
        start again) changes nothing. The exit happens even if saving raises:
        as a signal handler, an error would otherwise only be logged, leaving
        an app that ignores the signal."""
        if self._exiting:
            return
        self._exiting = True
        # The search thread can't be killed; cancelling lets it return.
        if self._cancel is not None:
            self._cancel.set()
        failure = None
        saved = False
        try:
            # Quitting from Options' theme list keeps the theme on show.
            if self._theme_previewing:
                self._keep_theme(self.theme)
            failure = self._write_settings()
            saved = failure is None
        finally:
            self.exit(return_code=0 if saved else 1, message=failure)

    def _start_again(self) -> None:
        """Exit and have the CLI run the app again, reading the saved data afresh."""
        self._exiting = True
        self.exit(result=True)

    def action_sort(self) -> None:
        pane = self.query_one(ResultsPane)
        self.push_screen(
            SortPicker(
                pane.sort_names(),
                current=pane.sort_key,
                title=self._strings.static(StringIndex.SORT_RESULTS_BY),
            ),
            pane.choose_sort,
        )

    def action_reverse_sort(self) -> None:
        pane = self.query_one(ResultsPane)
        pane.reverse_sort()
        self._save_tui_settings(replace(self._files.folders.settings, reverse=pane.reverse))

    def _save_tui_settings(self, settings: TuiSettings) -> bool:
        """Write ``tui.toml`` and keep its settings; a failure is reported.
        Returns whether it was written."""
        path = self._files.folders.settings_file
        try:
            write_tui_settings(path, settings)
        except OSError as error:
            self.notify(f"Can't save {path}: {error}", severity="error", markup=False)
            return False
        self._files = replace(self._files, folders=replace(self._files.folders, settings=settings))
        return True

    def action_find(self) -> None:
        self._close_inspector()
        self.query_one(ResultsPane).open_find()

    def _close_inspector(self) -> None:
        """Show the table again in place of the inspector over it, if it
        shows, for the caller to focus what it opens."""
        pane = self.query_one(ResultsPane)
        if pane.inspecting:
            pane.show_inspector(False)

    def action_maximise(self) -> None:
        """``z``: fill the screen with the focused region (the editor, the
        charm sidebar or the sets), or restore the one that fills it."""
        main = self.screen_stack[0]
        if main.maximized is not None:
            main.minimize()
            return
        focused = self.focused
        if focused is None:
            return
        regions = [self.editor, self.query_one("#charm_filter"), self.query_one("#sets")]
        region = next((widget for widget in regions if widget in focused.ancestors_with_self), None)
        if region is not None:
            main.maximized = region

    def action_wide_columns(self) -> None:
        """``w``: show or hide the table's wide columns, the resistances and extra skills."""
        table = self.query_one(ResultsTable)
        shown = not table.show_wide
        table.set_show_wide(shown, first=table.wide_start if shown else table.column_start)

    def action_inspect(self) -> None:
        """Show the inspector over the table, or the table again (a narrow screen's)."""
        pane = self.query_one(ResultsPane)
        # The inspector is beside the sets, so a maximised region gives way to it.
        self.screen_stack[0].minimize()
        pane.show_inspector(not pane.inspecting)
        if not pane.inspecting:
            self._focus_region(Region.SETS)

    def action_find_next(self, step: int) -> None:
        self.query_one(ResultsPane).find(step=step)

    def on_worker_state_changed(self, event: Worker.StateChanged) -> None:
        if event.worker is not self._worker or not event.worker.is_finished:
            return
        if self._search_waiting:
            self.action_search()
        elif not self._searching():
            self.query_one(ResultsPane).redraw_inspector()

    def on_progressed(self, event: Progressed) -> None:
        if event.number == self._search_number and self._cancel is not None:
            self.query_one(SearchProgress).advance(event.done, event.total)

    @work(thread=True, group="search")
    def _run_search(
        self,
        form: QueryForm,
        number: int,
        cancel: Event,
        sort_key: SortKey,
        reverse: bool,
        names: ShortNames,
    ) -> None:
        """The search, then its view sorted as the pane shows results and its
        rows named by ``names`` (reading every solution back from the pool's
        records, so off the UI thread)."""

        def report(done: int, total: int) -> None:
            # post_message doesn't wait for the UI, so the search doesn't either.
            self.post_message(Progressed(number=number, done=done, total=total))

        try:
            spec = form.search_spec(
                self._data.game,
                language=self._language,
                my_charms=tuple(read_lines(self._files.my_charms)),
            )
            # The inspector works out placements in the same game in a thread.
            with self._game_lock:
                result = run_search(
                    spec,
                    data=self._data,
                    record_exceptions=True,
                    pool=self.pool,
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
        rows = view_rows(view, names=names, query=result.query)
        self.call_from_thread(self._search_finished, number, result, view, rows, names)

    def _search_finished(
        self,
        number: int,
        result: SearchResult,
        view: ResultsView,
        rows: list[TableRow],
        names: ShortNames,
    ) -> None:
        if number != self._search_number or self._cancel is None:
            return
        self._finish_search()
        self.result = result
        self._searched_form = self._running_form
        self._last_search_gunner = result.query.hunter_type is HunterType.GUNNER
        note = None
        if result.exception is not None:
            stopped = (
                f"Worker {result.exception.worker + 1} of {result.worker_count} stopped with "
                f"{result.exception.type}"
            )
            note = f"Incomplete: {stopped}"
            self.notify(
                f"{stopped}, as the original's would; its sets and later workers' are missing.",
                severity="warning",
                timeout=30,
                markup=False,
            )
        pane = self.query_one(ResultsPane)
        # The screen's width class may have changed while the search ran.
        if names != pane.table_names:
            rows = view_rows(view, names=pane.table_names, query=result.query)
        pane.show(
            view,
            rows=rows,
            query=result.query,
            game=self._data.game,
            charm_templates=tuple(worker.template for worker in result.workers),
            note=note,
        )
        self._collapse_editor()
        # SaveConfig once the last worker returns (Form1.h:1830).
        self._save()

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
        self.query_one(ResultsPane).show_searching(False)
        # Its thread may still be running; if so, its end redraws instead.
        if not self._searching():
            self.query_one(ResultsPane).redraw_inspector()
