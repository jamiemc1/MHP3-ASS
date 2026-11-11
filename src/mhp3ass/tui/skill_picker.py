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
from mhp3ass.model import HunterType, Skill
from mhp3ass.skill_chips import add_chip, addable_skills, remove_chip, rows_full
from mhp3ass.skill_picker import SkillRow, query_skills


class ChipButton(Button):
    """A chosen skill; pressing it removes the skill."""

    def __init__(self, skill: Skill) -> None:
        super().__init__(Content(f"{skill.name} ✕"), compact=True)
        self.skill = skill


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

    class SearchRequested(Message):
        """Enter in the empty search box: search with the chosen skills."""

    class RowsChanged(Message):
        """New rows for ``hunter_type``'s tab (the tab shown when they changed)."""

        def __init__(self, rows: tuple[SkillRow, ...], hunter_type: HunterType) -> None:
            super().__init__()
            self.rows = rows
            self.hunter_type = hunter_type

    def __init__(
        self,
        game: GameData,
        strings: DisplayStrings,
        rows: tuple[SkillRow, ...],
        hunter_type: HunterType,
    ) -> None:
        super().__init__()
        self._game = game
        self._strings = strings
        self.rows = rows
        self.hunter_type = hunter_type
        self._offered: list[Skill] = []
        self._browsed = False

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

    def show_rows(self, rows: tuple[SkillRow, ...], hunter_type: HunterType) -> None:
        """Show another tab's rows, without posting ``RowsChanged``."""
        self.rows = rows
        self.hunter_type = hunter_type
        self._refresh()

    def on_input_changed(self, event: Input.Changed) -> None:
        event.stop()
        self._refresh_offered()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        event.stop()
        # An empty box searches, unless ▲▼ has picked a skill from the list.
        if event.value.strip() == "" and not self._browsed:
            self.post_message(self.SearchRequested())
            return
        options = self.query_one("#skill_options", OptionList)
        if not self._offered:
            return
        index = options.highlighted if options.highlighted is not None else 0
        self._add(self._offered[index])

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        event.stop()
        # The list may have been rebuilt since the selection was posted.
        if event.option_index < len(self._offered):
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
        # A press posted before the chips were rebuilt may name a removed skill.
        chosen = query_skills(self.rows)
        if event.button.skill in chosen:
            self._change(remove_chip(self.rows, chip=chosen.index(event.button.skill)))

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
        self._browsed = True
        options = self.query_one("#skill_options", OptionList)
        if event.key == "up":
            options.action_cursor_up()
        else:
            options.action_cursor_down()

    def on_descendant_focus(self, event: events.DescendantFocus) -> None:
        self._show_options()

    def on_descendant_blur(self, event: events.DescendantBlur) -> None:
        self._show_options()

    def _show_options(self) -> None:
        """The offered skills show while the search box or the list has focus."""
        options = self.query_one("#skill_options", OptionList)
        focused = self.app.focused
        in_use = isinstance(focused, SkillSearch) or focused is options
        options.display = bool(self._offered) and in_use

    def _add(self, skill: Skill) -> None:
        if rows_full(self.rows) or skill not in self._offered:
            return
        self.query_one("#skill_search", SkillSearch).value = ""
        self._change(add_chip(self._game, self.rows, skill))

    def _change(self, rows: tuple[SkillRow, ...]) -> None:
        self.rows = rows
        self._refresh()
        self.post_message(self.RowsChanged(rows, hunter_type=self.hunter_type))

    def _refresh(self) -> None:
        chips = self.query_one("#chips", Horizontal)
        chips.remove_children(ChipButton)
        chips.mount_all(ChipButton(skill) for skill in query_skills(self.rows))
        full = rows_full(self.rows)
        search = self.query_one("#skill_search", SkillSearch)
        search.placeholder = "six skills chosen" if full else "add skill"
        self._refresh_offered()

    def _refresh_offered(self) -> None:
        # A rebuilt list starts at its top, so nothing has been picked from it yet.
        self._browsed = False
        tag = self.query_one("#skill_tag", Select).value
        text = self.query_one("#skill_search", SkillSearch).value
        full = rows_full(self.rows)
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
        self._show_options()
        if self._offered:
            options.highlighted = 0
