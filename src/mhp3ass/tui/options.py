"""The Options modal: the four armour options, the language and the search's processes.

A new layout over the original's Options and Language menus
(``legacy/Form1.h:911-931``, ``LanguageSelect_Click`` ``:2011``); the
processes are the TUI's own (``tui.toml``'s ``jobs``).
"""

from __future__ import annotations

from typing import ClassVar

from textual.app import ComposeResult
from textual.binding import Binding, BindingType
from textual.containers import Horizontal, Vertical
from textual.message import Message
from textual.screen import ModalScreen
from textual.widgets import Checkbox, Label, Select

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

    def __init__(
        self,
        form: QueryForm,
        strings: DisplayStrings,
        languages: list[str],
        language: str,
        jobs: int,
        max_jobs: int,
    ) -> None:
        super().__init__()
        self._form = form
        self._strings = strings
        self._languages = languages
        self._language = language
        self._jobs = jobs
        self._max_jobs = max_jobs

    def compose(self) -> ComposeResult:
        strings = self._strings
        form = self._form
        options = Vertical(id="options")
        options.border_title = strings.basic(StringIndex.OPTIONS)
        with options:
            for field, label, value in (
                ("allow_piercings", StringIndex.ALLOW_PIERCINGS, form.allow_piercings),
                ("allow_event", StringIndex.ALLOW_EVENT_ARMOR, form.allow_event),
                ("allow_low_rank", StringIndex.ALLOW_LOW_RANK_ARMOR, form.allow_low_rank),
                ("allow_bad", StringIndex.ALLOW_BAD_SKILLS, form.allow_bad),
            ):
                yield Checkbox(strings.basic(label), value=value, id=field)
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
            yield Label("Space toggle · Esc close", id="keys")

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

    def action_close(self) -> None:
        self.dismiss()
