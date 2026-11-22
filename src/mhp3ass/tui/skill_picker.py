"""The skill picker: chips for the chosen skills, a search box, the tag
drop-down and the list of skills offered (``mhp3ass.skill_chips``)."""

from __future__ import annotations

from textual import events
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.content import Content
from textual.message import Message
from textual.widgets import Button, Input, OptionList, Select
from textual.widgets.option_list import Option

from mhp3ass.data import GameData
from mhp3ass.editor_rows import (
    chip_label,
    chip_width,
    chips_cells,
    chips_share_row,
    select_width,
)
from mhp3ass.model import HunterType, Skill
from mhp3ass.skill_chips import add_chip, addable_skills, remove_chip, rows_full
from mhp3ass.skill_picker import SkillRow, query_skills


class ChipButton(Button):
    """A chosen skill; pressing it removes the skill."""

    def __init__(self, skill: Skill) -> None:
        super().__init__(Content(chip_label(skill.name)), compact=True)
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
    """Edits one tab's six skill rows; posts ``RowsChanged`` after each change.

    The chosen skills' chips are on the search box's row where they fit
    before it (``chips_share_row``), else on a row of their own above it.
    The skills' label is the editor's, in the column before the picker, and
    the offered skills open under the search box."""

    DEFAULT_CSS = """
    SkillPicker {
        height: auto;
    }
    SkillPicker Horizontal {
        height: auto;
    }
    /* A row even with no chips on it, beside the skills' label. */
    SkillPicker #chips {
        height: 1;
    }
    SkillPicker ChipButton {
        min-width: 0;
        margin: 0 1 0 0;
    }
    SkillPicker #skill_search {
        margin: 0 1 0 0;
    }
    SkillPicker #skill_tag {
        margin: 0;
    }
    SkillPicker #skill_options {
        height: auto;
        max-height: 6;
        width: 1fr;
        max-width: 64;
    }
    """

    class SearchRequested(Message):
        """Enter in the empty search box: search with the chosen skills."""

    class LeftUpwards(Message):
        """Up in the search box at the top of the offered skills: the field
        above should take the focus."""

    class HeightChanged(Message):
        """The picker takes more or fewer rows: the offered skills opened or
        closed, or the chips moved between rows."""

    class RowsChanged(Message):
        """New rows for ``hunter_type``'s tab (the tab shown when they changed)."""

        def __init__(self, rows: tuple[SkillRow, ...], hunter_type: HunterType) -> None:
            super().__init__()
            self.rows = rows
            self.hunter_type = hunter_type

    def __init__(
        self,
        game: GameData,
        rows: tuple[SkillRow, ...],
        hunter_type: HunterType,
        search_width: int,
    ) -> None:
        """``search_width``: the search box's, room for the longest skill name."""
        super().__init__()
        self._game = game
        self.rows = rows
        self.hunter_type = hunter_type
        self._search_width = search_width
        self._tag_width = select_width(tag.name for tag in game.skill_tags)
        # Whether the chips are on the search box's row, once there is a width to decide by.
        self._chips_shared: bool | None = None
        # Its height as last laid out, to post HeightChanged when it changes.
        self._height = 0
        self._offered: list[Skill] = []
        self._browsed = False
        # Esc hides the offered skills until the list is rebuilt, ▲▼ browses it or ⏎ asks for it.
        self._dismissed = False

    def compose(self) -> ComposeResult:
        yield Horizontal(id="chips")
        with Horizontal(id="skill_row"):
            search = SkillSearch(placeholder="add skill", compact=True, id="skill_search")
            search.styles.width = self._search_width
            yield search
            tags = Select(
                [(tag.name, index) for index, tag in enumerate(self._game.skill_tags)],
                value=0,
                allow_blank=False,
                compact=True,
                id="skill_tag",
            )
            tags.styles.width = self._tag_width
            yield tags
        yield OptionList(compact=True, id="skill_options")

    def on_mount(self) -> None:
        self._refresh()

    def on_resize(self, event: events.Resize) -> None:
        if event.size.height != self._height:
            self._height = event.size.height
            self.post_message(self.HeightChanged())
        widths = [chip_width(skill.name) for skill in query_skills(self.rows)]
        if self._shares_row(widths, room=event.size.width) != self._chips_shared:
            self._place_chips()

    def _shares_row(self, chip_widths: list[int], room: int) -> bool:
        """Chips ``chip_widths`` wide fit on the search box's row, ``room`` cells wide."""
        shared = chips_share_row(
            chips=chip_widths,
            fields=self._search_width + 1 + self._tag_width,
            room=room,
        )
        return shared

    def _place_chips(self) -> None:
        """Show a chip for each chosen skill, on the search box's row if
        they fit there, else on their own row above it, keeping the focus on
        the chip that had it. Before the picker has a width, the first
        resize places them."""
        if self.size.width == 0:
            return
        skills = query_skills(self.rows)
        widths = [chip_width(skill.name) for skill in skills]
        shared = self._shares_row(widths, room=self.size.width)
        self._chips_shared = shared
        focused = self.app.focused
        focused_skill = (
            focused.skill
            if isinstance(focused, ChipButton) and focused in self.query(ChipButton)
            else None
        )
        self.query(ChipButton).remove()
        chips = [ChipButton(skill) for skill in skills]
        if shared:
            row = self.query_one("#skill_row", Horizontal)
            row.mount_all(chips, before=self.query_one("#skill_search", SkillSearch))
        else:
            self.query_one("#chips", Horizontal).mount_all(chips)
        self.query_one("#chips", Horizontal).display = not shared
        # The offered skills open under the search box, after the chips beside it.
        offset = chips_cells(widths) if shared else 0
        self.query_one("#skill_options", OptionList).styles.margin = (0, 0, 0, offset)
        for chip in chips:
            if chip.skill == focused_skill:
                self.call_after_refresh(chip.focus)

    def show_rows(self, rows: tuple[SkillRow, ...], hunter_type: HunterType) -> None:
        """Show another tab's rows, without posting ``RowsChanged``."""
        self.rows = rows
        self.hunter_type = hunter_type
        self._refresh()

    @property
    def offered_rows(self) -> int:
        """The rows the offered skills take under the search box while they show."""
        options = self.query_one("#skill_options", OptionList)
        rows = options.outer_size.height if options.display else 0
        return rows

    @property
    def options_open(self) -> bool:
        """The offered skills show under the search box."""
        return self.query_one("#skill_options", OptionList).display

    def dismiss_options(self) -> None:
        """Hide the offered skills, as Esc does; focus in the list goes back
        to the search box, so it doesn't stay on a hidden widget."""
        options = self.query_one("#skill_options", OptionList)
        if self.app.focused is options:
            self.query_one("#skill_search", SkillSearch).focus()
        self._dismissed = True
        self._show_options()

    def on_input_changed(self, event: Input.Changed) -> None:
        event.stop()
        self._refresh_offered()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        event.stop()
        # An empty box searches, unless ▲▼ has picked a skill from the list.
        if event.value.strip() == "" and not self._browsed:
            self.post_message(self.SearchRequested())
            return
        # Hidden with Esc: ⏎ shows the skills again rather than adding one unseen.
        if self._dismissed:
            self._dismissed = False
            self._show_options()
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
        options = self.query_one("#skill_options", OptionList)
        if event.key == "up":
            # Up from the first offered skill, or with none offered, goes to the row
            # above; a list Esc hid comes back first, at the skill it was on.
            if not self._offered or (options.display and options.highlighted in (None, 0)):
                self.post_message(self.LeftUpwards())
                return
            if not options.display:
                self._dismissed = False
                self._show_options()
                return
        self._browsed = True
        self._dismissed = False
        self._show_options()
        if event.key == "up":
            options.action_cursor_up()
        else:
            options.action_cursor_down()

    def on_descendant_focus(self, event: events.DescendantFocus) -> None:
        self._show_options()

    def on_descendant_blur(self, event: events.DescendantBlur) -> None:
        self._show_options()

    def _show_options(self) -> None:
        """The offered skills show while the search box or the list has
        focus, unless Esc has hidden them."""
        options = self.query_one("#skill_options", OptionList)
        focused = self.app.focused
        in_use = isinstance(focused, SkillSearch) or focused is options
        options.display = bool(self._offered) and in_use and not self._dismissed
        if options.display:
            # The editor scrolls on a short screen: bring the whole list into view, with
            # the search box above it, so the list's own scrolling keeps its cursor seen.
            self.call_after_refresh(options.scroll_visible, animate=False)

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
        self._place_chips()
        full = rows_full(self.rows)
        search = self.query_one("#skill_search", SkillSearch)
        search.placeholder = "six skills chosen" if full else "add skill"
        self._refresh_offered()

    def _refresh_offered(self) -> None:
        # A rebuilt list starts at its top, so nothing has been picked from it yet,
        # and shows again if Esc hid the old one.
        self._browsed = False
        self._dismissed = False
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
