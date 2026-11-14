"""The query editor: the search form's controls, labelled in the game's language.

A new layout over ``Form1``'s controls (``legacy/Form1.h``), with their text
as ``UpdateLanguage`` sets it (``:2065-2089``, ``StaticString``).
"""

from __future__ import annotations

from dataclasses import fields, replace
from typing import Any

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Button, Label, Select

from mhp3ass.data import GameData
from mhp3ass.data.strings import DisplayStrings, StringIndex
from mhp3ass.model import Gender, HunterType
from mhp3ass.query import CharmMode
from mhp3ass.query_form import QueryForm, charm_mode_label
from mhp3ass.regions import Region
from mhp3ass.tui.skill_picker import SkillPicker
from mhp3ass.tui.titles import region_title


class QueryEditor(Vertical):
    """The form's drop-downs and skill picker. ``form`` follows every change."""

    # Its max-height is set by fit_height; past it the editor scrolls.
    DEFAULT_CSS = """
    QueryEditor {
        height: auto;
        overflow-y: auto;
        padding: 0 1;
    }
    QueryEditor Horizontal {
        height: auto;
    }
    QueryEditor Label {
        padding: 0 1 0 2;
    }
    QueryEditor Select {
        margin-right: 1;
    }
    QueryEditor #hunter_type {
        width: 16;
        margin-left: 2;
    }
    QueryEditor #gender {
        width: 12;
    }
    QueryEditor #hr, QueryEditor #elder_star, QueryEditor #weapon_slots {
        width: 7;
    }
    QueryEditor #charm_mode {
        width: 30;
    }
    QueryEditor #search {
        min-width: 10;
    }
    """

    def __init__(self, form: QueryForm, game: GameData, strings: DisplayStrings) -> None:
        super().__init__(id="query", classes="pane")
        self.border_title = region_title(Region.QUERY, "Query")
        self.form = form
        self._game = game
        self._strings = strings

    def compose(self) -> ComposeResult:
        strings = self._strings
        with Horizontal():
            yield Select(
                [
                    (strings.static(StringIndex.BLADEMASTER), HunterType.BLADEMASTER),
                    (strings.static(StringIndex.GUNNER), HunterType.GUNNER),
                ],
                value=self.form.hunter_type,
                allow_blank=False,
                compact=True,
                id="hunter_type",
            )
            yield Select(
                [
                    (strings.static(StringIndex.MALE), Gender.MALE),
                    (strings.static(StringIndex.FEMALE), Gender.FEMALE),
                ],
                value=self.form.gender,
                allow_blank=False,
                compact=True,
                id="gender",
            )
            yield Label(strings.static(StringIndex.HR))
            yield _number_select(1, 6, value=self.form.hr, select_id="hr")
            yield Label(strings.static(StringIndex.VILLAGE_QUESTS))
            yield _number_select(1, 6, value=self.form.elder_star, select_id="elder_star")
        # Weapon slots start the second row, so the first fits in 80 columns.
        with Horizontal():
            yield Label(strings.static(StringIndex.MAX_WEAPON_SLOTS))
            yield _number_select(0, 3, value=self.form.weapon_slots, select_id="weapon_slots")
            yield Label(strings.static(StringIndex.CHARMS))
            yield Select(
                [(strings.static(charm_mode_label(mode)), mode) for mode in CharmMode],
                value=self.form.charm_mode,
                allow_blank=False,
                compact=True,
                id="charm_mode",
            )
            # The app handles the press: searching needs its data and pool.
            yield Button(
                strings.basic(StringIndex.SEARCH), variant="primary", compact=True, id="search"
            )
        yield SkillPicker(
            self._game,
            strings=strings,
            rows=self.form.current_rows(),
            hunter_type=self.form.hunter_type,
        )

    def on_mount(self) -> None:
        self.fit_height(self.app.size.height, over_results=False)

    def fit_height(self, screen_height: int, over_results: bool) -> None:
        """Take at most about 40 % of a ``screen_height``-row screen, and
        never less than 8 rows of it, so the results stay in view; or, open
        in the results' place (``over_results``), all the room it needs."""
        self.styles.max_height = None if over_results else max(8, screen_height * 40 // 100)

    def on_select_changed(self, event: Select.Changed) -> None:
        # The form's selects are those whose id is the QueryForm field they set.
        field = event.select.id
        if field not in {form_field.name for form_field in fields(QueryForm)}:
            return
        event.stop()
        changes: dict[str, Any] = {field: event.value}
        self.form = replace(self.form, **changes)
        if field == "hunter_type":
            self.query_one(SkillPicker).show_rows(
                self.form.current_rows(), hunter_type=self.form.hunter_type
            )

    def on_skill_picker_rows_changed(self, event: SkillPicker.RowsChanged) -> None:
        event.stop()
        self.form = self.form.with_rows(event.hunter_type, rows=event.rows)


def _number_select(minimum: int, maximum: int, value: int, select_id: str) -> Select[int]:
    select = Select(
        [(str(number), number) for number in range(minimum, maximum + 1)],
        value=value,
        allow_blank=False,
        compact=True,
        id=select_id,
    )
    return select
