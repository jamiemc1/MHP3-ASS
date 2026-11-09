"""Editing the user's charm list, as the My Charms dialog does.

Ported from ``ManageCharms`` (``legacy/ManageCharms.h:342-619``): ``CreateCharm``,
the Add New, Save, Delete, Delete All, Move Up and Move Down buttons, the skill
lists each skill box offers (``UpdateFilter``) and what selecting a charm puts
in the boxes (``lstCharms_SelectedIndexChanged``).

Each operation takes the list and the selected row and returns a
``CharmListEdit``. The original saves ``mycharms.txt`` (``SaveCustom``) after
every operation that changes something; ``CharmListEdit.saved`` says when, so
the caller passes the new list to ``save_my_charms``.
"""

from __future__ import annotations

from dataclasses import dataclass

from mhp3ass.charms.validity import CharmValidity
from mhp3ass.data import GameData
from mhp3ass.data.text import to_int32
from mhp3ass.model import Ability, AbilityPair, Charm


@dataclass(frozen=True)
class CharmEntry:
    """What the dialog's boxes hold: the slots spinner and two skill/amount pairs.

    An ability is ``None`` when its box shows "(none)". Amounts are the boxes'
    text, which the user can type freely; the drop-downs offer 0 to 10 for the
    first and 0 to 13 for the second.
    """

    num_slots: int
    first_ability: Ability | None
    first_amount: str
    second_ability: Ability | None
    second_amount: str

    def __post_init__(self) -> None:
        # The spinner's range (ManageCharms.h:163); setting it outside throws.
        if not 0 <= self.num_slots <= 3:
            raise ValueError(f"{self.num_slots} slots is outside the slots spinner's 0 to 3")


@dataclass(frozen=True)
class CharmListEdit:
    """The charm list and selected row after an operation.

    ``saved``: the original saved ``mycharms.txt``. ``reselected``: the
    original re-selected the row ``selected``, which refills the boxes from
    that charm (``entry_for_charm``) and drops any unsaved edits in them.
    """

    charms: list[Charm]
    selected: int
    saved: bool
    reselected: bool


def _unchanged(charms: list[Charm], selected: int) -> CharmListEdit:
    unchanged = CharmListEdit(charms=list(charms), selected=selected, saved=False, reselected=False)
    return unchanged


def _refreshed(charms: list[Charm], selected: int) -> CharmListEdit:
    """``RefreshList( selected )`` then ``SaveCustom``: selecting a row refills the boxes."""
    refreshed = CharmListEdit(
        charms=charms, selected=selected, saved=True, reselected=selected >= 0
    )
    return refreshed


def create_charm(entry: CharmEntry, validity: CharmValidity) -> Charm | None:
    """``CreateCharm`` (ManageCharms.h:354-380).

    A skill counts when its box has an ability and its amount text isn't the
    string "0" (so "00" or "-0" adds a skill with 0 points). Amounts are read
    with ``Convert::ToInt32``: unreadable text raises ``ValueError`` (the
    original's ``FormatException``, which the buttons ignore) and text outside
    the ``int`` range raises ``OverflowError`` (an ``OverflowException`` nothing
    catches). Amount ranges are only enforced when a box loses focus
    (``clamp_amount``); the Asserts here are compiled out.

    ``None`` when the charm has neither slots nor skills, or the game can't
    produce it (``CharmExists( ch ) || !CharmIsIllegal( ch )`` fails).
    """
    pairs = []
    for ability, amount_text in (
        (entry.first_ability, entry.first_amount),
        (entry.second_ability, entry.second_amount),
    ):
        if amount_text != "0" and ability is not None:
            pairs.append(AbilityPair(ability=ability, amount=to_int32(amount_text)))
    if entry.num_slots == 0 and not pairs:
        return None
    charm = Charm(num_slots=entry.num_slots, abilities=pairs)
    possible = validity.exists(charm) or not validity.is_illegal(charm)
    created = charm if possible else None
    return created


def clamp_amount(text: str, first: bool) -> str:
    """``cmbAmount_LostFocus`` (ManageCharms.h:586-612): the text a box shows after losing focus.

    The first amount is clamped to 0-10 and the second to -10 to 13;
    unreadable text becomes "0". Text outside the ``int`` range raises
    ``OverflowError``, as the original's uncaught ``OverflowException``.
    """
    try:
        value = to_int32(text)
    except ValueError:
        return "0"
    low, high = (0, 10) if first else (-10, 13)
    if value < low:
        return str(low)
    if value > high:
        return str(high)
    return text


def add_new(
    charms: list[Charm], selected: int, entry: CharmEntry, validity: CharmValidity
) -> CharmListEdit:
    """``btnAddNew_Click``: append the entry's charm, marked custom, and select it."""
    try:
        charm = create_charm(entry, validity)
    except ValueError:
        charm = None
    if charm is None:
        return _unchanged(charms, selected)
    charm.custom = True
    added = [*charms, charm]
    edit = _refreshed(added, selected=len(added) - 1)
    return edit


def replace_selected(
    charms: list[Charm], selected: int, entry: CharmEntry, validity: CharmValidity
) -> CharmListEdit:
    """``btnSave_Click``: replace the selected charm with the entry's.

    Unlike Add New, the new charm isn't marked custom, so until the list is
    next loaded it is searched like a generated charm. Only the list row's
    text changes, so the boxes keep what they hold.
    """
    if selected <= -1:
        return _unchanged(charms, selected)
    try:
        charm = create_charm(entry, validity)
    except ValueError:
        charm = None
    if charm is None:
        return _unchanged(charms, selected)
    replaced = list(charms)
    replaced[selected] = charm
    edit = CharmListEdit(charms=replaced, selected=selected, saved=True, reselected=False)
    return edit


def delete_selected(charms: list[Charm], selected: int) -> CharmListEdit:
    """``btnDelete_Click``: remove the selected charm; its row (or the new last) stays selected."""
    if selected <= -1:
        return _unchanged(charms, selected)
    remaining = list(charms)
    del remaining[selected]
    new_selected = selected if selected < len(remaining) else len(remaining) - 1
    edit = _refreshed(remaining, selected=new_selected)
    return edit


def delete_all() -> CharmListEdit:
    """``btnDeleteAll_Click``: empty the list, without asking, and save it."""
    edit = _refreshed([], selected=-1)
    return edit


def move_up(charms: list[Charm], selected: int) -> CharmListEdit:
    """``btnMoveUp_Click``: swap the selected charm with the one above."""
    if selected <= 0:
        return _unchanged(charms, selected)
    moved = list(charms)
    moved[selected - 1], moved[selected] = moved[selected], moved[selected - 1]
    edit = _refreshed(moved, selected=selected - 1)
    return edit


def move_down(charms: list[Charm], selected: int) -> CharmListEdit:
    """``btnMoveDown_Click``: swap the selected charm with the one below."""
    if not -1 < selected < len(charms) - 1:
        return _unchanged(charms, selected)
    moved = list(charms)
    moved[selected], moved[selected + 1] = moved[selected + 1], moved[selected]
    edit = _refreshed(moved, selected=selected + 1)
    return edit


def ability_choices(game: GameData, filter_index: int, banned: Ability | None) -> list[Ability]:
    """``UpdateFilter`` (ManageCharms.h:464-518): the abilities a skill box lists after "(none)".

    ``filter_index`` indexes the filter box, which lists ``game.skill_tags``:
    0 (All) offers every ability but Torso Inc, 1 (Misc) those without tags,
    any other index those with a tag of that name. ``banned``, the other box's
    ability, is never offered. Abilities come in load order.
    """
    abilities = [ability for ability in game.abilities if ability is not banned]
    if filter_index == 0:
        choices = [ability for ability in abilities if ability is not game.torso_inc]
    elif filter_index == 1:
        choices = [
            ability for ability in abilities if not ability.tags and ability is not game.torso_inc
        ]
    else:
        tag_name = game.skill_tags[filter_index].name
        choices = [
            ability for ability in abilities if any(tag.name == tag_name for tag in ability.tags)
        ]
    return choices


def entry_for_charm(game: GameData, charm: Charm, previous: CharmEntry) -> CharmEntry:
    """``lstCharms_SelectedIndexChanged``: the boxes after selecting ``charm`` in the list.

    Both filters go back to All. Each skill box selects the charm's ability if
    its All list offers it (every ability but Torso Inc, and for the second
    box not the first box's ability), else shows "(none)". An amount box takes
    the charm's amount when the charm has that skill, whether or not its
    ability was found; otherwise it keeps its previous text.
    """
    first_ability = None
    first_amount = previous.first_amount
    second_ability = None
    second_amount = previous.second_amount
    if charm.abilities:
        first = charm.abilities[0]
        if first.ability is not game.torso_inc:
            first_ability = first.ability
        first_amount = str(first.amount)
        if len(charm.abilities) > 1:
            second = charm.abilities[1]
            if second.ability is not game.torso_inc and second.ability is not first_ability:
                second_ability = second.ability
            second_amount = str(second.amount)
    entry = CharmEntry(
        num_slots=charm.num_slots,
        first_ability=first_ability,
        first_amount=first_amount,
        second_ability=second_ability,
        second_amount=second_amount,
    )
    return entry
