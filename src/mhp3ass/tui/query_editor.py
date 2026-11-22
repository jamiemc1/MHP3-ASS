"""The query editor: the search form's controls, labelled in the game's language.

A new layout over ``Form1``'s controls (``legacy/Form1.h``), with their text
as ``UpdateLanguage`` sets it (``:2065-2089``, ``StaticString``).
"""

from __future__ import annotations

from dataclasses import fields, replace
from typing import Any

from rich.cells import cell_len
from textual import events
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widget import Widget
from textual.widgets import Button, Label, Select, Static

from mhp3ass.data import GameData
from mhp3ass.data.strings import DisplayStrings, StringIndex
from mhp3ass.editor_rows import group_spacing, select_width
from mhp3ass.model import Gender, HunterType
from mhp3ass.query import CharmMode
from mhp3ass.query_form import QueryForm, charm_mode_label
from mhp3ass.regions import Region
from mhp3ass.spatial import Direction, FieldBox, neighbour
from mhp3ass.tui.skill_picker import SkillPicker
from mhp3ass.tui.titles import region_title


class QueryEditor(Vertical):
    """The form's drop-downs and skill picker. ``form`` follows every change.

    The fields sit on an even grid: each row's first cell (the hunter
    drop-down, the weapon slots' label, the skills' label) takes the same
    width, so the fields after them line up; a label is a cell from its
    field, and a field two from the next label. Each drop-down is as wide
    as its longest choice (``select_width``).

    Compact, above the results, the weapon slots, the charm mode and the
    Search button share the second row. Spread, with the screen to itself,
    the fields form four groups: the hunter's setup, the charm mode, the
    skills, and Search on a row of its own under them. The gaps between
    the groups grow with the height, up to two rows each, and the block is
    centred in the rest (``group_spacing``); with no rows to spare they
    close up."""

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
        padding: 0 1 0 0;
    }
    QueryEditor Select {
        margin-right: 2;
    }
    QueryEditor #slots_cell {
        width: auto;
    }
    /* The charm mode gives way, so the Search button beside it is never cut. */
    QueryEditor #charm_mode {
        width: 1fr;
        min-width: 12;
    }
    QueryEditor #search {
        min-width: 10;
    }
    /* Their heights are set by _space_groups. */
    QueryEditor .group-space, QueryEditor #search_row {
        display: none;
    }
    QueryEditor.-spread .group-space, QueryEditor.-spread #search_row {
        display: block;
    }
    QueryEditor.-spread #search {
        display: none;
    }
    /* Spread, the setup's second row and the charm mode are stacked. */
    QueryEditor.-spread #mid_row {
        layout: vertical;
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
        hunters = [
            (strings.static(StringIndex.BLADEMASTER), HunterType.BLADEMASTER),
            (strings.static(StringIndex.GUNNER), HunterType.GUNNER),
        ]
        genders = [
            (strings.static(StringIndex.MALE), Gender.MALE),
            (strings.static(StringIndex.FEMALE), Gender.FEMALE),
        ]
        charm_modes = [(strings.static(charm_mode_label(mode)), mode) for mode in CharmMode]
        slots_label = strings.static(StringIndex.MAX_WEAPON_SLOTS)
        charms_label = strings.static(StringIndex.CHARMS)
        # Each row's first cell, with the gap after it.
        lead = max(
            select_width(label for label, _ in hunters) + 2,
            cell_len(slots_label) + 1,
            cell_len(strings.static(StringIndex.SKILLS)) + 1,
        )
        self._lead = lead
        # Spread, the Charms label takes the lead column, or more if it is longer.
        self._charms_width = max(lead, cell_len(charms_label) + 1)
        yield Static(id="space_above", classes="group-space")
        with Horizontal(id="setup_row"):
            hunter = Select(
                hunters,
                value=self.form.hunter_type,
                allow_blank=False,
                compact=True,
                id="hunter_type",
            )
            hunter.styles.width = lead - 2
            yield hunter
            gender = Select(
                genders,
                value=self.form.gender,
                allow_blank=False,
                compact=True,
                id="gender",
            )
            gender.styles.width = select_width(label for label, _ in genders)
            yield gender
            yield Label(strings.static(StringIndex.HR))
            yield _number_select(1, 6, value=self.form.hr, select_id="hr")
            yield Label(strings.static(StringIndex.VILLAGE_QUESTS))
            yield _number_select(1, 6, value=self.form.elder_star, select_id="elder_star")
        search_label = strings.basic(StringIndex.SEARCH)
        # Room in the skill box for the longest skill name; Search, spread, is as wide.
        search_width = 26
        # Weapon slots start the second row, so the first fits in 80 columns.
        with Horizontal(id="mid_row"):
            with Horizontal(id="slots_cell"):
                slots = Label(slots_label)
                slots.styles.width = lead
                yield slots
                yield _number_select(0, 3, value=self.form.weapon_slots, select_id="weapon_slots")
            yield Static(classes="group-space group-gap")
            with Horizontal(id="charm_cell"):
                yield Label(charms_label, id="charms_label")
                charm_mode = Select(
                    charm_modes,
                    value=self.form.charm_mode,
                    allow_blank=False,
                    compact=True,
                    id="charm_mode",
                )
                charm_mode.styles.max_width = select_width(label for label, _ in charm_modes)
                yield charm_mode
                # The app handles the press: searching needs its data and pool.
                yield Button(
                    search_label, variant="primary", compact=True, id="search", classes="search"
                )
        yield Static(classes="group-space group-gap")
        yield SkillPicker(
            self._game,
            strings=strings,
            rows=self.form.current_rows(),
            hunter_type=self.form.hunter_type,
            lead=lead,
            search_width=search_width,
        )
        yield Static(classes="group-space group-gap")
        # Spread, Search is the last step, on its own row in the fields' column.
        with Horizontal(id="search_row"):
            search_last = Button(
                search_label, variant="primary", compact=True, id="search_last", classes="search"
            )
            search_last.styles.margin = (0, 0, 0, lead)
            search_last.styles.width = search_width
            yield search_last

    def fit_height(self, screen_height: int, spread: bool) -> None:
        """Take at most about 40 % of a ``screen_height``-row screen, and
        never less than 8 rows of it, so the results stay in view; or, with
        the screen to itself (``spread``), the room left, its fields in
        groups spread over it, past which it scrolls."""
        self.styles.height = "1fr" if spread else "auto"
        self.styles.max_height = None if spread else max(8, screen_height * 40 // 100)
        if spread == self.has_class("-spread"):
            return
        self.set_class(spread, "-spread")
        # Spread, the charm mode starts its own row, in the fields' column.
        self.query_one("#charms_label", Label).styles.width = self._charms_width if spread else None
        # Only one of the two Search buttons shows: the focus moves to it,
        # unless the editor is collapsing, which gives the focus to the table.
        shown = self.query_one("#search_last" if spread else "#search", Button)
        hidden = self.query_one("#search" if spread else "#search_last", Button)
        if self.display and self.app.focused is hidden:
            shown.focus()
        # Measured once the -spread class has laid the rows out.
        self.call_after_refresh(self._space_groups)

    def on_resize(self, event: events.Resize) -> None:
        self.call_after_refresh(self._space_groups)

    def on_skill_picker_height_changed(self, event: SkillPicker.HeightChanged) -> None:
        event.stop()
        self.call_after_refresh(self._space_groups)

    def _space_groups(self) -> None:
        """Spread, share the rows the groups leave between them
        (``group_spacing``); the offered skills, while open, take the rows
        below the block before any above it, so the block stays put."""
        if not self.has_class("-spread"):
            return
        picker = self.query_one(SkillPicker)
        rows = [
            *(
                self.query_one(f"#{row_id}")
                for row_id in ("setup_row", "slots_cell", "charm_cell", "search_row")
            ),
            picker,
        ]
        opened = picker.offered_rows
        content = sum(row.outer_size.height for row in rows) - opened
        gaps = list(self.query(".group-gap"))
        spacing = group_spacing(
            room=self.size.height, content=content, gaps=len(gaps), opened=opened
        )
        self.query_one("#space_above", Static).styles.height = spacing.above
        for gap, height in zip(gaps, spacing.between, strict=True):
            gap.styles.height = height

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

    def on_skill_picker_left_upwards(self, event: SkillPicker.LeftUpwards) -> None:
        event.stop()
        self.move_focus(Direction.UP)

    def focus_fields(self) -> list[Widget]:
        """The editor's widgets that take focus, in Tab order; none while a
        modal is over the editor's screen, so nothing under it moves."""
        focus_chain = self.app.screen.focus_chain
        focusable = [widget for widget in focus_chain if self in widget.ancestors]
        return focusable

    def move_focus(self, direction: Direction) -> None:
        """Focus the field beside the focused one, or on the row above or
        below (``spatial.neighbour``). Each of the editor's horizontal
        containers is a row; a field outside one is a row of its own. With
        no field that way, or the focus on none, nothing moves."""
        focusable = self.focus_fields()
        current = self._focused_field(focusable)
        if current is None:
            return
        rows: dict[Widget, list[FieldBox]] = {}
        for key, widget in enumerate(focusable):
            row = self._row_of(widget)
            rows.setdefault(row, []).append(
                FieldBox(key, x=self._x_of(widget), width=widget.virtual_region.width)
            )
        target = neighbour(list(rows.values()), current=current, direction=direction)
        if target is not None:
            focusable[target].focus()

    def step_focus(self, step: int) -> bool:
        """Focus the next (``step`` 1) or previous (-1) field after the
        focused one. ``False``, moving nothing, when the focus is on no field
        or the step would leave the editor past either end."""
        focusable = self.focus_fields()
        current = self._focused_field(focusable)
        if current is None or not 0 <= current + step < len(focusable):
            return False
        focusable[current + step].focus()
        return True

    def focus_end(self, step: int) -> None:
        """Entering the editor: focus its first field going forwards
        (``step`` 1), its last going back."""
        focusable = self.focus_fields()
        if focusable:
            focusable[0 if step > 0 else -1].focus()

    def _focused_field(self, focusable: list[Widget]) -> int | None:
        """The index of the focused widget in ``focusable``, or ``None``."""
        focused = self.app.focused
        index = next((index for index, field in enumerate(focusable) if field is focused), None)
        return index

    def _row_of(self, widget: Widget) -> Widget:
        """The row ``widget`` is on: the outermost of the containers around
        it laid out side by side, as the CSS has them at the time (the
        spread editor stacks some), or ``widget`` alone outside any."""
        row = widget
        for ancestor in widget.ancestors:
            if ancestor is self or not isinstance(ancestor, Widget):
                break
            layout = ancestor.styles.layout
            if layout is not None and layout.name == "horizontal":
                row = ancestor
            elif row is not widget:
                break
        return row

    def _x_of(self, widget: Widget) -> int:
        """``widget``'s column in the editor's own frame, whatever the
        containers between them (each ``virtual_region`` is its container's)."""
        x = widget.virtual_region.x
        for ancestor in widget.ancestors:
            if ancestor is self:
                break
            if isinstance(ancestor, Widget):
                x += ancestor.virtual_region.x
        return x


def _number_select(minimum: int, maximum: int, value: int, select_id: str) -> Select[int]:
    numbers = range(minimum, maximum + 1)
    select = Select(
        [(str(number), number) for number in numbers],
        value=value,
        allow_blank=False,
        compact=True,
        id=select_id,
    )
    select.styles.width = select_width(str(number) for number in numbers)
    return select
