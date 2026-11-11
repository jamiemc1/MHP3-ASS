"""The app and its main screen: the query area above the results table."""

from __future__ import annotations

from typing import ClassVar

from textual.app import App, ComposeResult
from textual.binding import BindingType
from textual.widgets import DataTable, Footer, Header, Static


class SearchApp(App[None]):
    """The main screen: a header naming the language, the query area, the
    results table and the footer of keys."""

    TITLE = "MHP3 Armor Set Search"
    CSS = """
    #query {
        height: auto;
        padding: 1 2;
        color: $text-muted;
    }
    #results {
        height: 1fr;
    }
    """
    BINDINGS: ClassVar[list[BindingType]] = [("q", "quit", "Quit")]

    def __init__(self, language: str | None) -> None:
        super().__init__()
        self.sub_title = language if language is not None else ""

    def compose(self) -> ComposeResult:
        yield Header()
        yield Static("Choose up to six skills, then Search.", id="query")
        yield DataTable(id="results", cursor_type="row", zebra_stripes=True)
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#results", DataTable)
        table.add_columns("#", "Head", "Body", "Arms", "Waist", "Legs", "Def", "Spare", "Charm")
