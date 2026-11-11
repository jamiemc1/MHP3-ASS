"""The skill picker: chips for the chosen skills, a search box, the tag
drop-down and the list of skills offered (``mhp3ass.skill_chips``)."""

from __future__ import annotations

from textual import events
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.content import Content
from textual.message import Message
from textual.widgets import Button, Input, Label, OptionList, Select
from textual.widgets.option_list import Option

from mhp3ass.data import GameData
from mhp3ass.data.strings import DisplayStrings, StringIndex
from mhp3ass.model import Skill
from mhp3ass.skill_chips import add_chip, addable_skills, remove_chip
from mhp3ass.skill_picker import SkillRow, query_skills


class ChipButton(Button):
    """A chosen skill; pressing it removes the skill."""

    def __init__(self, skill: Skill, chip: int) -> None:
        super().__init__(Content(f"{skill.name} ✕"), compact=True)
        self.chip = chip


class SkillSearch(Input):
    """The search box. Backspace in an empty box removes the last chip."""

    class BackspaceWhenEmpty(Message):
        pass

    def action_delete_left(self) -> None:
        if self.value == "":
            self.post_message(self.BackspaceWhenEmpty())
            return
        super().action_delete_left()


class SkillPicker(Vertical):
    """Edits one tab's six skill rows; posts ``RowsChanged`` after each change."""

    DEFAULT_CSS = """
    SkillPicker {
        height: auto;
    }
    SkillPicker Horizontal {
        height: auto;
    }
    SkillPicker #chips ChipButton {
        margin: 1 1 0 0;
    }
    SkillPicker #skill_search {
        width: 40;
    }
    SkillPicker #skill_tag {
        width: 22;
    }
    SkillPicker #skill_options {
        height: auto;
        max-height: 8;
        width: 64;
        margin-left: 2;
    }
    """

    class RowsChanged(Message):
        def __init__(self, rows: tuple[SkillRow, ...]) -> None:
            super().__init__()
            self.rows = rows

    def __init__(self, game: GameData, strings: DisplayStrings, rows: tuple[SkillRow, ...]) -> None:
        super().__init__()
        self._game = game
        self._strings = strings
        self.rows = rows
        self._offered: list[Skill] = []

    def compose(self) -> ComposeResult:
        with Horizontal(id="chips"):
            yield Label(self._strings.static(StringIndex.SKILLS))
        with Horizontal():
            yield SkillSearch(placeholder="add skill", id="skill_search")
            yield Select(
                [(tag.name, index) for index, tag in enumerate(self._game.skill_tags)],
                value=0,
                allow_blank=False,
                id="skill_tag",
            )
        yield OptionList(id="skill_options")

    def on_mount(self) -> None:
        self._refresh()

    def show_rows(self, rows: tuple[SkillRow, ...]) -> None:
        """Show another tab's rows, without posting ``RowsChanged``."""
        self.rows = rows
        self._refresh()

    def on_input_changed(self, event: Input.Changed) -> None:
        event.stop()
        self._refresh_offered()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        event.stop()
        options = self.query_one("#skill_options", OptionList)
        if not self._offered:
            return
        index = options.highlighted if options.highlighted is not None else 0
        self._add(self._offered[index])

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        event.stop()
        self._add(self._offered[event.option_index])

    def on_select_changed(self, event: Select.Changed) -> None:
        if event.select.id != "skill_tag":
            return
        event.stop()
        self._refresh_offered()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if not isinstance(event.button, ChipButton):
            return
        event.stop()
        self._change(remove_chip(self.rows, chip=event.button.chip))

    def on_skill_search_backspace_when_empty(self, event: SkillSearch.BackspaceWhenEmpty) -> None:
        event.stop()
        chosen = query_skills(self.rows)
        if chosen:
            self._change(remove_chip(self.rows, chip=len(chosen) - 1))

    def on_key(self, event: events.Key) -> None:
        # Up and down in the search box move through the offered skills.
        if event.key not in ("up", "down") or not isinstance(self.app.focused, SkillSearch):
            return
        event.stop()
        options = self.query_one("#skill_options", OptionList)
        if event.key == "up":
            options.action_cursor_up()
        else:
            options.action_cursor_down()

    def _add(self, skill: Skill) -> None:
        self.query_one("#skill_search", SkillSearch).value = ""
        self._change(add_chip(self._game, self.rows, skill))

    def _change(self, rows: tuple[SkillRow, ...]) -> None:
        self.rows = rows
        self._refresh()
        self.post_message(self.RowsChanged(rows))

    def _full(self) -> bool:
        full = all(row.skill is not None for row in self.rows)
        return full

    def _refresh(self) -> None:
        chips = self.query_one("#chips", Horizontal)
        chips.remove_children(ChipButton)
        chips.mount_all(
            ChipButton(skill, chip=chip) for chip, skill in enumerate(query_skills(self.rows))
        )
        full = self._full()
        search = self.query_one("#skill_search", SkillSearch)
        search.disabled = full
        search.placeholder = "six skills chosen" if full else "add skill"
        self._refresh_offered()

    def _refresh_offered(self) -> None:
        tag = self.query_one("#skill_tag", Select).value
        text = self.query_one("#skill_search", SkillSearch).value
        full = self._full()
        tag_index = tag if isinstance(tag, int) else 0
        self._offered = (
            [] if full else addable_skills(self._game, self.rows, tag_index=tag_index, text=text)
        )
        options = self.query_one("#skill_options", OptionList)
        options.clear_options()
        options.add_options(
            Option(Content(f"{skill.name:<24} {skill.ability.name} {skill.points_required:+d}"))
            for skill in self._offered
        )
        if self._offered:
            options.highlighted = 0
