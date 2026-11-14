"""The sort picker: ``cmbSort``'s items (``legacy/Form1.h:2090-2100``) as a
short list over the results, opened with ``s``."""

from __future__ import annotations

from typing import ClassVar

from textual.app import ComposeResult
from textual.binding import Binding, BindingType
from textual.content import Content
from textual.screen import ModalScreen
from textual.widgets import OptionList
from textual.widgets.option_list import Option

from mhp3ass.results.sorting import SortKey


class SortPicker(ModalScreen[SortKey | None]):
    """⏎ (or a click) picks the highlighted key; Esc keeps the sort as it was."""

    DEFAULT_CSS = """
    SortPicker {
        align: center middle;
    }
    SortPicker OptionList {
        width: 34;
        height: auto;
        max-height: 80%;
        border: round $accent;
    }
    """
    BINDINGS: ClassVar[list[BindingType]] = [Binding("escape", "cancel", "Cancel")]

    def __init__(self, names: list[tuple[SortKey, str]], current: SortKey, title: str) -> None:
        """``names``: each key with its name in the game's language, in drop-down order."""
        super().__init__()
        self._keys = [key for key, _ in names]
        self._names = [name for _, name in names]
        self._current = current
        self._title = title

    def compose(self) -> ComposeResult:
        options = OptionList(*(Option(Content(name)) for name in self._names))
        options.border_title = Content(self._title)
        options.highlighted = self._keys.index(self._current)
        yield options

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        event.stop()
        self.dismiss(self._keys[event.option_index])

    def action_cancel(self) -> None:
        self.dismiss(None)
