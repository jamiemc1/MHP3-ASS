"""The Options modal: the four armour options, the language, the colour
theme, the search's processes and the saved-data folder; and the small
modals it opens.

A new layout over the original's Options and Language menus
(``legacy/Form1.h:911-931``, ``LanguageSelect_Click`` ``:2011``); the
theme, the processes and the folder are the TUI's own (``tui.toml``).
"""

from __future__ import annotations

import subprocess
import sys
from collections.abc import Iterable
from pathlib import Path
from typing import ClassVar

from textual import work
from textual.app import ComposeResult
from textual.binding import Binding, BindingType
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.content import Content
from textual.message import Message
from textual.screen import ModalScreen
from textual.widgets import (
    Button,
    Checkbox,
    DirectoryTree,
    Input,
    Label,
    OptionList,
    Select,
    Static,
    Tree,
)
from textual.widgets.directory_tree import DirEntry
from textual.widgets.option_list import Option

from mhp3ass.data.strings import DisplayStrings, StringIndex
from mhp3ass.query_form import QueryForm


class ThemeList(OptionList):
    """The themes by name. While it has focus, moving the cursor shows each
    theme at once; ⏎, or leaving the list, keeps the highlighted one; Esc
    goes back to the theme it had when it got focus (a second Esc closes
    Options)."""

    BINDINGS: ClassVar[list[BindingType]] = [Binding("escape", "revert", "Revert theme")]

    class Previewed(Message):
        """Show ``theme`` while the cursor is on it, without keeping it."""

        def __init__(self, theme: str) -> None:
            super().__init__()
            self.theme = theme

    class Kept(Message):
        """``theme`` was chosen: keep it and save it."""

        def __init__(self, theme: str) -> None:
            super().__init__()
            self.theme = theme

    def __init__(self, themes: list[str], current: str) -> None:
        super().__init__(*(Option(Content(theme)) for theme in themes), id="theme")
        self._themes = themes
        self._current = current
        # The theme when the list got focus, which Esc goes back to.
        self._original = current
        # Set while Esc moves the cursor back, which shows no preview.
        self._reverting = False

    @property
    def _highlighted_theme(self) -> str:
        if self.highlighted is None:
            raise RuntimeError("the theme list has no highlighted theme")
        theme = self._themes[self.highlighted]
        return theme

    def on_mount(self) -> None:
        self.highlighted = self._themes.index(self._current)

    def on_focus(self) -> None:
        self._original = self._highlighted_theme

    def on_option_list_option_highlighted(self, event: OptionList.OptionHighlighted) -> None:
        event.stop()
        if self._reverting:
            self._reverting = False
            return
        # Highlighting the current theme on mount is no preview.
        if self.has_focus:
            self.post_message(self.Previewed(self._themes[event.option_index]))

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        event.stop()
        self.post_message(self.Kept(self._themes[event.option_index]))

    def on_blur(self) -> None:
        self.post_message(self.Kept(self._highlighted_theme))

    async def action_revert(self) -> None:
        if self._highlighted_theme == self._original:
            await self.run_action("screen.close")
            return
        self._reverting = True
        self.highlighted = self._themes.index(self._original)
        self.post_message(self.Kept(self._original))


class OptionsScreen(ModalScreen[None]):
    """Posts a message for each change; the app applies and saves it."""

    DEFAULT_CSS = """
    OptionsScreen {
        align: center middle;
    }
    OptionsScreen #options {
        width: 60;
        height: auto;
        max-height: 100%;
        border: round $accent;
        padding: 0 1;
    }
    OptionsScreen Horizontal {
        height: auto;
    }
    OptionsScreen Label {
        padding: 1 1 0 0;
        width: 16;
    }
    OptionsScreen #language {
        width: 36;
    }
    OptionsScreen #theme {
        width: 36;
        height: 6;
    }
    OptionsScreen #jobs {
        width: 12;
    }
    OptionsScreen #saved_folder {
        width: 1fr;
    }
    OptionsScreen #folder_buttons {
        padding: 0 0 0 16;
    }
    OptionsScreen #folder_buttons Button {
        margin: 0 2 0 0;
    }
    OptionsScreen #folder_note {
        width: auto;
        padding: 0 2 0 0;
        color: $text-muted;
    }
    OptionsScreen #keys {
        color: $text-muted;
        width: 1fr;
        text-align: right;
        padding: 1 0 0 0;
    }
    """
    BINDINGS: ClassVar[list[BindingType]] = [Binding("escape", "close", "Close")]

    class OptionChanged(Message):
        """An armour option, by its ``QueryForm`` field."""

        def __init__(self, field: str, value: bool) -> None:
            super().__init__()
            self.field = field
            self.value = value

    class LanguageChosen(Message):
        def __init__(self, language: str) -> None:
            super().__init__()
            self.language = language

    class JobsChosen(Message):
        def __init__(self, jobs: int) -> None:
            super().__init__()
            self.jobs = jobs

    class FolderChosen(Message):
        """A saved-data folder typed (⏎) or picked with Browse…."""

        def __init__(self, folder: Path) -> None:
            super().__init__()
            self.folder = folder

    class ClearRequested(Message):
        pass

    def __init__(
        self,
        form: QueryForm,
        strings: DisplayStrings,
        languages: list[str],
        language: str,
        jobs: int,
        max_jobs: int,
        saved_folder: Path,
        folder_locked: bool,
        themes: list[str],
        theme: str,
    ) -> None:
        """``folder_locked``: ``MHP3ASS_HOME`` chooses the folder, so it can't
        be changed here. ``themes``: every theme's name, ``theme`` the one in use."""
        super().__init__()
        self._themes = themes
        self._theme = theme
        self._form = form
        self._strings = strings
        self._languages = languages
        self._language = language
        self._jobs = jobs
        self._max_jobs = max_jobs
        self._saved_folder = saved_folder
        self._folder_locked = folder_locked

    def compose(self) -> ComposeResult:
        strings = self._strings
        # Scrolls when the terminal is too short for every option.
        options = VerticalScroll(id="options", can_focus=False)
        options.border_title = strings.basic(StringIndex.OPTIONS)
        with options:
            for option in self._form.armour_options():
                yield Checkbox(strings.basic(option.label), value=option.on, id=option.field)
            with Horizontal():
                yield Label(strings.basic(StringIndex.LANGUAGE))
                yield Select(
                    [(language, language) for language in self._languages],
                    value=self._language,
                    allow_blank=False,
                    id="language",
                )
            with Horizontal():
                yield Label("Theme")
                yield ThemeList(self._themes, current=self._theme)
            with Horizontal():
                yield Label("Search jobs")
                yield Select(
                    [(str(jobs), jobs) for jobs in range(1, self._max_jobs + 1)],
                    value=self._jobs,
                    allow_blank=False,
                    id="jobs",
                )
            with Horizontal():
                yield Label("Saved data")
                yield Input(
                    str(self._saved_folder), disabled=self._folder_locked, id="saved_folder"
                )
            with Horizontal(id="folder_buttons"):
                if self._folder_locked:
                    yield Label("set by MHP3ASS_HOME", id="folder_note")
                else:
                    yield Button("Browse…", compact=True, id="browse")
                yield Button("clear…", compact=True, id="clear")
            yield Label("Space toggle · ⏎ use folder · Esc close", id="keys")

    def on_checkbox_changed(self, event: Checkbox.Changed) -> None:
        event.stop()
        field = event.checkbox.id
        if field is not None:
            self.post_message(self.OptionChanged(field, value=event.value))

    def on_select_changed(self, event: Select.Changed) -> None:
        event.stop()
        value = event.value
        if event.select.id == "language" and isinstance(value, str) and value != self._language:
            self._language = value
            self.post_message(self.LanguageChosen(value))
        elif event.select.id == "jobs" and isinstance(value, int) and value != self._jobs:
            self._jobs = value
            self.post_message(self.JobsChosen(value))

    def on_input_submitted(self, event: Input.Submitted) -> None:
        event.stop()
        text = event.value.strip()
        if text != "":
            # Resolved here, as tui.toml would read a relative folder as under its own.
            self.post_message(self.FolderChosen(Path(text).expanduser().resolve()))

    def on_button_pressed(self, event: Button.Pressed) -> None:
        event.stop()
        if event.button.id == "clear":
            self.post_message(self.ClearRequested())
        elif event.button.id == "browse":
            self._browse()

    def _browse(self) -> None:
        """The macOS folder dialog, else a folder tree in the terminal."""
        if sys.platform == "darwin":
            self._choose_folder_on_macos()
        else:
            self.app.push_screen(FolderPicker(), self._picked)

    @work(thread=True, group="browse", exclusive=True)
    def _choose_folder_on_macos(self) -> None:
        try:
            completed = subprocess.run(
                ["osascript", "-e", "POSIX path of (choose folder)"],
                capture_output=True,
                text=True,
                check=False,
            )
        except OSError as error:
            # No osascript to run.
            self.app.call_from_thread(self.notify, f"Can't open the folder dialog: {error}")
            return
        # A cancelled dialog exits non-zero with nothing on stdout.
        chosen = completed.stdout.strip()
        if completed.returncode == 0 and chosen != "":
            self.app.call_from_thread(self._picked, Path(chosen))

    def _picked(self, folder: Path | None) -> None:
        # The macOS dialog can answer after this modal has been closed.
        if folder is None or not self.is_attached:
            return
        self.query_one("#saved_folder", Input).value = str(folder)
        self.post_message(self.FolderChosen(folder))

    def action_close(self) -> None:
        self.dismiss()


class FolderTree(DirectoryTree):
    """A ``DirectoryTree`` of folders only, so whatever is highlighted can be chosen."""

    def filter_paths(self, paths: Iterable[Path]) -> Iterable[Path]:
        # DirectoryTree's own check, which treats an unreadable entry as not a folder.
        folders = [path for path in paths if self._safe_is_dir(path)]
        return folders

    @property
    def chosen(self) -> Path:
        """The highlighted folder, or the tree's root when nothing is highlighted
        (the cursor is cleared when a collapse hides it)."""
        node = self.cursor_node
        entry = node.data if node is not None else self.root.data
        if entry is None:
            raise ValueError("The folder tree has no root folder")
        folder = entry.path.resolve()
        return folder


class FolderPicker(ModalScreen[Path | None]):
    """A folder tree from the home folder. A click or ⏎ opens or closes a
    folder; Choose (or ``c``) picks the highlighted one; Esc cancels."""

    DEFAULT_CSS = """
    FolderPicker {
        align: center middle;
    }
    FolderPicker #picker {
        width: 70;
        height: auto;
        border: round $accent;
    }
    FolderPicker FolderTree {
        height: 22;
    }
    FolderPicker #highlighted {
        color: $text-muted;
        padding: 0 1;
    }
    FolderPicker #picker_buttons {
        height: auto;
        align-horizontal: right;
    }
    FolderPicker #picker_buttons Button {
        margin: 0 0 0 2;
    }
    """
    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("escape", "cancel", "Cancel"),
        Binding("c", "choose", "Choose"),
    ]

    def compose(self) -> ComposeResult:
        home = Path.home()
        with Vertical(id="picker"):
            yield FolderTree(home)
            yield Static(Content(str(home)), id="highlighted")
            with Horizontal(id="picker_buttons"):
                yield Button("Cancel", id="cancel")
                yield Button("Choose", id="choose", variant="primary")

    def on_mount(self) -> None:
        picker = self.query_one("#picker", Vertical)
        picker.border_title = "Choose a folder: ⏎ opens, c chooses, Esc cancels"
        # The tree starts with no cursor; start it on the home folder that Choose would pick.
        self.query_one(FolderTree).cursor_line = 0

    def on_tree_node_highlighted(self, event: Tree.NodeHighlighted[DirEntry]) -> None:
        event.stop()
        self._show_chosen()

    def on_tree_node_collapsed(self, event: Tree.NodeCollapsed[DirEntry]) -> None:
        # A collapse can clear the cursor without a highlight message.
        event.stop()
        self._show_chosen()

    def _show_chosen(self) -> None:
        chosen = self.query_one(FolderTree).chosen
        self.query_one("#highlighted", Static).update(Content(str(chosen)))

    def on_button_pressed(self, event: Button.Pressed) -> None:
        event.stop()
        if event.button.id == "choose":
            self.action_choose()
        elif event.button.id == "cancel":
            self.action_cancel()

    def action_choose(self) -> None:
        self.dismiss(self.query_one(FolderTree).chosen)

    def action_cancel(self) -> None:
        self.dismiss(None)


class ChoiceScreen[T](ModalScreen[T | None]):
    """A question with one button per answer; Esc answers ``None``."""

    DEFAULT_CSS = """
    ChoiceScreen {
        align: center middle;
    }
    ChoiceScreen #choice {
        width: 72;
        height: auto;
        border: round $accent;
        padding: 0 1;
    }
    ChoiceScreen Button {
        width: 1fr;
        margin: 1 0 0 0;
    }
    """
    BINDINGS: ClassVar[list[BindingType]] = [Binding("escape", "cancel", "Cancel")]

    def __init__(self, title: str, text: str, answers: list[tuple[str, T]]) -> None:
        super().__init__()
        self._title = title
        self._text = text
        self._answers = answers

    def compose(self) -> ComposeResult:
        box = Vertical(id="choice")
        box.border_title = self._title
        with box:
            yield Static(Content(self._text))
            for number, (label, _) in enumerate(self._answers):
                yield Button(Content(label), id=f"answer_{number}")
            yield Button("Cancel", variant="default", id="cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        event.stop()
        button_id = event.button.id
        if button_id is not None and button_id.startswith("answer_"):
            self.dismiss(self._answers[int(button_id.removeprefix("answer_"))][1])
        else:
            self.dismiss(None)

    def action_cancel(self) -> None:
        self.dismiss(None)
