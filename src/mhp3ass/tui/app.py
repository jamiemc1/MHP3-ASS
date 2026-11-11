"""The app and its main screen: the query editor above the results table."""

from __future__ import annotations

from typing import ClassVar

from textual.app import App, ComposeResult
from textual.binding import Binding, BindingType
from textual.widgets import DataTable, Footer, Header, Static

from mhp3ass.data.strings import DisplayStrings
from mhp3ass.query_form import QueryForm
from mhp3ass.tui.query_editor import QueryEditor


class SearchApp(App[None]):
    """The main screen: a header naming the language, the query editor, the
    results table and the footer of keys."""

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
        Binding("h", "focus('hunter_type')", "Hunter", show=False),
        Binding("g", "focus('gender')", "Gender", show=False),
        Binding("r", "focus('hr')", "HR", show=False),
        Binding("v", "focus('elder_star')", "Village", show=False),
        Binding("w", "focus('weapon_slots')", "Weapon slots", show=False),
        Binding("m", "focus('charm_mode')", "Charm mode", show=False),
    ]

    def __init__(self, language: str, strings: DisplayStrings, form: QueryForm) -> None:
        super().__init__()
        self.sub_title = language
        # The editor owns the form; read it as ``self.editor.form``.
        self.editor = QueryEditor(form, strings=strings)

    def compose(self) -> ComposeResult:
        yield Header()
        yield self.editor
        yield Static("Choose up to six skills, then Search.", id="hint")
        yield DataTable(id="results", cursor_type="row", zebra_stripes=True)
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#results", DataTable)
        table.add_columns("#", "Head", "Body", "Arms", "Waist", "Legs", "Def", "Spare", "Charm")
