"""``QueryEditor``'s field navigation, driven headless in a bare app."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable

import pytest
from textual.app import App, ComposeResult
from textual.pilot import Pilot
from textual.screen import ModalScreen
from textual.widgets import Label

from mhp3ass.data import GameData
from mhp3ass.data.strings import DisplayStrings
from mhp3ass.query_form import QueryForm
from mhp3ass.spatial import Direction
from mhp3ass.tui.query_editor import QueryEditor
from mhp3ass.tui.skill_picker import SkillPicker


class EditorApp(App[None]):
    """The starting form's editor on a screen of its own, compact (never spread)."""

    def __init__(self, game: GameData, strings: DisplayStrings) -> None:
        super().__init__()
        self._game = game
        self._strings = strings

    def compose(self) -> ComposeResult:
        yield QueryEditor(QueryForm.starting(), game=self._game, strings=self._strings)


class Covering(ModalScreen[None]):
    def compose(self) -> ComposeResult:
        yield Label("over the editor")


type Steps = Callable[[EditorApp, Pilot[None]], Awaitable[object]]


@pytest.fixture
def in_editor(teamhgg_game, english_strings) -> Callable[[Steps], object]:
    """Run ``steps`` in an ``EditorApp`` 80 columns by 24 rows; their result."""

    def run(steps: Steps) -> object:
        async def main() -> object:
            app = EditorApp(teamhgg_game, strings=english_strings)
            async with app.run_test(size=(80, 24)) as pilot:
                await pilot.pause()
                result = await steps(app, pilot)
            return result

        outcome = asyncio.run(main())
        return outcome

    return run


def _id(widget) -> str | None:
    return widget.id if widget is not None else None


def test_the_fields_are_the_editors_focusable_widgets_in_tab_order(in_editor):
    async def steps(app, pilot):
        ids = [field.id for field in app.query_one(QueryEditor).focus_fields()]
        return ids

    assert in_editor(steps) == [
        "hunter_type",
        "gender",
        "hr",
        "elder_star",
        "weapon_slots",
        "charm_mode",
        "search",
        "skill_search",
        "skill_tag",
    ]


def test_a_modal_over_the_editor_leaves_it_no_fields(in_editor):
    async def steps(app, pilot):
        await app.push_screen(Covering())
        await pilot.pause()
        fields = app.query_one(QueryEditor).focus_fields()
        return fields

    assert in_editor(steps) == []


@pytest.mark.parametrize(
    ("start", "direction", "expected"),
    [
        ("hunter_type", Direction.RIGHT, "gender"),
        ("hunter_type", Direction.DOWN, "weapon_slots"),
        # The weapon slots' drop-down sits under the gender one, past the long label.
        ("weapon_slots", Direction.UP, "gender"),
        ("charm_mode", Direction.LEFT, "weapon_slots"),
        # No field that way: the focus stays.
        ("hunter_type", Direction.LEFT, "hunter_type"),
        ("hunter_type", Direction.UP, "hunter_type"),
    ],
)
def test_an_arrow_moves_to_the_field_that_way(in_editor, start, direction, expected):
    async def steps(app, pilot):
        editor = app.query_one(QueryEditor)
        app.query_one(f"#{start}").focus()
        await pilot.pause()
        editor.move_focus(direction)
        await pilot.pause()
        return _id(app.focused)

    assert in_editor(steps) == expected


def test_an_arrow_with_the_focus_off_the_fields_moves_nothing(in_editor):
    async def steps(app, pilot):
        app.set_focus(None)
        await pilot.pause()
        app.query_one(QueryEditor).move_focus(Direction.DOWN)
        await pilot.pause()
        return app.focused

    assert in_editor(steps) is None


@pytest.mark.parametrize(
    ("start", "step", "expected"),
    [
        ("hunter_type", 1, [True, "gender"]),
        ("gender", -1, [True, "hunter_type"]),
        # Past either end the editor gives the step back, focus unmoved.
        ("skill_tag", 1, [False, "skill_tag"]),
        ("hunter_type", -1, [False, "hunter_type"]),
    ],
)
def test_tab_steps_to_the_next_field_until_either_end(in_editor, start, step, expected):
    async def steps(app, pilot):
        app.query_one(f"#{start}").focus()
        await pilot.pause()
        moved = app.query_one(QueryEditor).step_focus(step)
        await pilot.pause()
        return [moved, _id(app.focused)]

    assert in_editor(steps) == expected


def test_tab_with_the_focus_off_the_fields_moves_nothing(in_editor):
    async def steps(app, pilot):
        app.set_focus(None)
        await pilot.pause()
        moved = app.query_one(QueryEditor).step_focus(1)
        return [moved, app.focused]

    assert in_editor(steps) == [False, None]


@pytest.mark.parametrize(("step", "expected"), [(1, "hunter_type"), (-1, "skill_tag")])
def test_entering_the_editor_focuses_its_first_or_last_field(in_editor, step, expected):
    async def steps(app, pilot):
        app.set_focus(None)
        await pilot.pause()
        app.query_one(QueryEditor).focus_end(step)
        await pilot.pause()
        return _id(app.focused)

    assert in_editor(steps) == expected


def test_up_out_of_the_skill_search_moves_to_the_row_above(in_editor):
    """The picker's ``LeftUpwards`` is the editor's up arrow, and stops there."""

    async def steps(app, pilot):
        editor = app.query_one(QueryEditor)
        app.query_one("#skill_search").focus()
        await pilot.pause()
        editor.move_focus(Direction.UP)
        await pilot.pause()
        by_arrow = _id(app.focused)
        app.query_one("#skill_search").focus()
        await pilot.pause()
        app.query_one(SkillPicker).post_message(SkillPicker.LeftUpwards())
        await pilot.pause()
        return [by_arrow, _id(app.focused)]

    by_arrow, by_message = in_editor(steps)

    assert [by_message, by_arrow != "skill_search"] == [by_arrow, True]
