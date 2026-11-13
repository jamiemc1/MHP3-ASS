"""The Options modal: the four armour options, the language, the search's
processes and the saved-data folder; and the small modals it opens.

A new layout over the original's Options and Language menus
(``legacy/Form1.h:911-931``, ``LanguageSelect_Click`` ``:2011``); the
processes and the folder are the TUI's own (``tui.toml``).
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import ClassVar

from textual import work
from textual.app import ComposeResult
from textual.binding import Binding, BindingType
from textual.containers import Horizontal, Vertical
from textual.content import Content
from textual.message import Message
from textual.screen import ModalScreen
from textual.widgets import Button, Checkbox, DirectoryTree, Input, Label, Select, Static

from mhp3ass.data.strings import DisplayStrings, StringIndex
from mhp3ass.query_form import QueryForm


class OptionsScreen(ModalScreen[None]):
    """Posts a message for each change; the app applies and saves it."""

    DEFAULT_CSS = """
    OptionsScreen {
        align: center middle;
    }
    OptionsScreen #options {
        width: 60;
        height: auto;
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
    ) -> None:
        """``folder_locked``: ``MHP3ASS_HOME`` chooses the folder, so it can't be changed here."""
        super().__init__()
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
        options = Vertical(id="options")
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


class FolderPicker(ModalScreen[Path | None]):
    """A folder tree from the home folder; ⏎ on a folder chooses it, Esc cancels."""

    DEFAULT_CSS = """
    FolderPicker {
        align: center middle;
    }
    FolderPicker DirectoryTree {
        width: 70;
        height: 24;
        border: round $accent;
    }
    """
    BINDINGS: ClassVar[list[BindingType]] = [Binding("escape", "cancel", "Cancel")]

    def compose(self) -> ComposeResult:
        tree = DirectoryTree(Path.home())
        tree.border_title = "Choose a folder (⏎)"
        yield tree

    def on_directory_tree_directory_selected(self, event: DirectoryTree.DirectorySelected) -> None:
        event.stop()
        self.dismiss(event.path)

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
