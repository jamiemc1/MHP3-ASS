"""The query editor: the search form's controls, labelled in the game's language.

A new layout over ``Form1``'s controls (``legacy/Form1.h``), with their text
as ``UpdateLanguage`` sets it (``:2065-2089``, ``StaticString``).
"""

from __future__ import annotations

from dataclasses import fields, replace
from typing import Any

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Label, Select

from mhp3ass.data import GameData
from mhp3ass.data.strings import DisplayStrings, StringIndex
from mhp3ass.model import Gender, HunterType
from mhp3ass.query import CharmMode
from mhp3ass.query_form import QueryForm
from mhp3ass.tui.skill_picker import SkillPicker


class QueryEditor(Vertical):
    """The form's drop-downs and skill picker. ``form`` follows every change."""

    DEFAULT_CSS = """
    QueryEditor {
        height: auto;
        padding: 0 1;
    }
    QueryEditor Horizontal {
        height: auto;
    }
    QueryEditor Label {
        padding: 1 1 0 2;
    }
    QueryEditor #hunter_type {
        width: 22;
    }
    QueryEditor #gender {
        width: 14;
    }
    QueryEditor #hr, QueryEditor #elder_star, QueryEditor #weapon_slots {
        width: 9;
    }
    QueryEditor #charm_mode {
        width: 38;
    }
    """

    def __init__(self, form: QueryForm, game: GameData, strings: DisplayStrings) -> None:
        super().__init__(id="query")
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
                id="hunter_type",
            )
            yield Select(
                [
                    (strings.static(StringIndex.MALE), Gender.MALE),
                    (strings.static(StringIndex.FEMALE), Gender.FEMALE),
                ],
                value=self.form.gender,
                allow_blank=False,
                id="gender",
            )
            yield Label(strings.static(StringIndex.HR))
            yield _number_select(1, 6, value=self.form.hr, select_id="hr")
            yield Label(strings.static(StringIndex.VILLAGE_QUESTS))
            yield _number_select(1, 6, value=self.form.elder_star, select_id="elder_star")
            yield Label(strings.static(StringIndex.MAX_WEAPON_SLOTS))
            yield _number_select(0, 3, value=self.form.weapon_slots, select_id="weapon_slots")
        with Horizontal():
            yield Label(strings.static(StringIndex.CHARMS))
            yield Select(
                [(strings.static(_charm_mode_label(mode)), mode) for mode in CharmMode],
                value=self.form.charm_mode,
                allow_blank=False,
                id="charm_mode",
            )
        yield SkillPicker(self._game, strings=strings, rows=self.form.current_rows())

    def on_select_changed(self, event: Select.Changed) -> None:
        # The form's selects are those whose id is the QueryForm field they set.
        field = event.select.id
        if field not in {form_field.name for form_field in fields(QueryForm)}:
            return
        event.stop()
        changes: dict[str, Any] = {field: event.value}
        self.form = replace(self.form, **changes)
        if field == "hunter_type":
            self.query_one(SkillPicker).show_rows(self.form.current_rows())

    def on_skill_picker_rows_changed(self, event: SkillPicker.RowsChanged) -> None:
        event.stop()
        self.form = self.form.with_current_rows(event.rows)


def _number_select(minimum: int, maximum: int, value: int, select_id: str) -> Select[int]:
    select = Select(
        [(str(number), number) for number in range(minimum, maximum + 1)],
        value=value,
        allow_blank=False,
        id=select_id,
    )
    return select


def _charm_mode_label(mode: CharmMode) -> StringIndex:
    """``cmbCharmSelect``'s item text (``Form1.h:2085-2089``)."""
    match mode:
        case CharmMode.NONE:
            return StringIndex.USE_NO_CHARMS
        case CharmMode.MY_CHARMS:
            return StringIndex.USE_ONLY_MY_CHARMS
        case CharmMode.SLOTTED:
            return StringIndex.USE_ONLY_SLOTTED_CHARMS
        case CharmMode.ONE_SKILL:
            return StringIndex.USE_UP_TO_ONE_SKILL_CHARMS
        case CharmMode.TWO_SKILL:
            return StringIndex.USE_ONLY_TWO_SKILL_CHARMS
