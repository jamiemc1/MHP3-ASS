"""The query editor: the search form's controls, labelled in the game's language."""

from __future__ import annotations

from dataclasses import replace
from typing import Any

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Label, Select

from mhp3ass.data.strings import DisplayStrings, StringIndex
from mhp3ass.model import Gender, HunterType
from mhp3ass.query import CharmMode
from mhp3ass.query_form import QueryForm


class QueryEditor(Vertical):
    """The form's drop-downs. ``form`` follows every change."""

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

    def __init__(self, form: QueryForm, strings: DisplayStrings) -> None:
        super().__init__(id="query")
        self.form = form
        self._strings = strings

    def compose(self) -> ComposeResult:
        strings = self._strings
        with Horizontal():
            yield Select(
                [
                    (strings.basic(StringIndex.BLADEMASTER), HunterType.BLADEMASTER),
                    (strings.basic(StringIndex.GUNNER), HunterType.GUNNER),
                ],
                value=self.form.hunter_type,
                allow_blank=False,
                id="hunter_type",
            )
            yield Select(
                [
                    (strings.basic(StringIndex.MALE), Gender.MALE),
                    (strings.basic(StringIndex.FEMALE), Gender.FEMALE),
                ],
                value=self.form.gender,
                allow_blank=False,
                id="gender",
            )
            yield Label(strings.basic(StringIndex.HR))
            yield _number_select(1, 6, value=self.form.hr, select_id="hr")
            yield Label(strings.basic(StringIndex.VILLAGE_QUESTS))
            yield _number_select(1, 6, value=self.form.elder_star, select_id="elder_star")
            yield Label(strings.basic(StringIndex.MAX_WEAPON_SLOTS))
            yield _number_select(0, 3, value=self.form.weapon_slots, select_id="weapon_slots")
        with Horizontal():
            yield Label(strings.basic(StringIndex.CHARMS))
            yield Select(
                [(strings.basic(_charm_mode_label(mode)), mode) for mode in CharmMode],
                value=self.form.charm_mode,
                allow_blank=False,
                id="charm_mode",
            )

    def on_select_changed(self, event: Select.Changed) -> None:
        # Each select's id is the QueryForm field it sets.
        field = event.select.id
        if field is None:
            raise ValueError("a query editor select has no id")
        changes: dict[str, Any] = {field: event.value}
        self.form = replace(self.form, **changes)


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
    labels = {
        CharmMode.NONE: StringIndex.USE_NO_CHARMS,
        CharmMode.MY_CHARMS: StringIndex.USE_ONLY_MY_CHARMS,
        CharmMode.SLOTTED: StringIndex.USE_ONLY_SLOTTED_CHARMS,
        CharmMode.ONE_SKILL: StringIndex.USE_UP_TO_ONE_SKILL_CHARMS,
        CharmMode.TWO_SKILL: StringIndex.USE_ONLY_TWO_SKILL_CHARMS,
    }
    label = labels[mode]
    return label
