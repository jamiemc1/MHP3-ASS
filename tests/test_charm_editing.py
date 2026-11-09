"""My Charms dialog editing (ManageCharms.h:342-619)."""

from __future__ import annotations

import pytest

from mhp3ass.charms.editing import (
    CharmEntry,
    ability_choices,
    add_new,
    clamp_amount,
    create_charm,
    delete_all,
    delete_selected,
    entry_for_charm,
    move_down,
    move_up,
    replace_selected,
)
from mhp3ass.charms.my_charms import load_my_charms, my_charms_text
from mhp3ass.charms.naming import charm_name
from mhp3ass.model import AbilityPair, Charm


def entry(game, num_slots=0, first=None, first_amount="0", second=None, second_amount="0"):
    """A CharmEntry with abilities given by name."""
    built = CharmEntry(
        num_slots=num_slots,
        first_ability=game.ability_map[first] if first else None,
        first_amount=first_amount,
        second_ability=game.ability_map[second] if second else None,
        second_amount=second_amount,
    )
    return built


def created(charm_entry, validity):
    """The charm ``create_charm`` makes from ``charm_entry``; fails the test if it makes none."""
    charm = create_charm(charm_entry, validity)
    assert charm is not None
    return charm


@pytest.fixture
def loading_attack_entry(teamhgg_game):
    """A charm the game can produce: +3 Loading, +5 Attack, one slot."""
    return entry(teamhgg_game, 1, "Loading", "3", "Attack", "5")


@pytest.fixture
def impossible_entry(teamhgg_game):
    """Three slots with +10 Attack and +13 Expert: no table produces it."""
    return entry(teamhgg_game, 3, "Attack", "10", "Expert", "13")


@pytest.fixture
def unreadable_amount_entry(teamhgg_game):
    return entry(teamhgg_game, 1, "Attack", "five")


@pytest.fixture
def overflowing_amount_entry(teamhgg_game):
    return entry(teamhgg_game, 1, "Attack", "99999999999")


@pytest.fixture
def three_charms():
    """Three distinct (bare) charms, told apart by their slot counts."""
    return [Charm(num_slots=1), Charm(num_slots=2), Charm(num_slots=3)]


@pytest.fixture
def capture_my_charms_files(gui_captures_dir):
    """Every captured GUI search's mycharms.txt (all saved in English (TeamHGG))."""
    paths = sorted(gui_captures_dir.glob("*/mycharms.txt"))
    assert paths, "no mycharms.txt in the GUI captures"
    return paths


def test_creates_the_charm_in_box_order(teamhgg_game, validity, loading_attack_entry):
    charm = created(loading_attack_entry, validity)

    assert [charm_name(charm), charm.custom] == ["+3 Loading, +5 Attack O--", False]


def test_a_charm_the_game_cannot_make_is_refused(validity, impossible_entry):
    assert create_charm(impossible_entry, validity) is None


def test_no_slots_and_no_skills_is_no_charm(teamhgg_game, validity):
    assert create_charm(entry(teamhgg_game, 0, "Attack", "0"), validity) is None


def test_slots_alone_make_a_bare_charm(teamhgg_game, validity):
    assert charm_name(created(entry(teamhgg_game, 3), validity)) == "OOO"


def test_only_the_text_0_skips_a_skill(teamhgg_game, validity):
    """The amount is compared with the string "0", so "00" and "-0" add a 0-point skill."""
    names = [
        charm_name(created(entry(teamhgg_game, 0, "Attack", text, "Expert", "5"), validity))
        for text in ["0", "00", "-0"]
    ]

    assert names == ["+5 Expert ---", "+0 Attack, +5 Expert ---", "+0 Attack, +5 Expert ---"]


def test_a_skill_without_an_ability_is_skipped(teamhgg_game, validity):
    charm = created(entry(teamhgg_game, 1, None, "5", "Attack", "4"), validity)

    assert charm_name(charm) == "+4 Attack O--"


def test_an_unreadable_amount_raises(validity, unreadable_amount_entry):
    with pytest.raises(ValueError, match="not a valid Int32"):
        create_charm(unreadable_amount_entry, validity)


def test_an_overflowing_amount_raises(validity, overflowing_amount_entry):
    with pytest.raises(OverflowError):
        create_charm(overflowing_amount_entry, validity)


@pytest.mark.parametrize("operation", [add_new, replace_selected])
def test_buttons_let_an_overflowing_amount_escape(
    three_charms, validity, overflowing_amount_entry, operation
):
    with pytest.raises(OverflowError):
        operation(three_charms, selected=0, entry=overflowing_amount_entry, validity=validity)


def test_slots_outside_the_spinner_raise(teamhgg_game):
    with pytest.raises(ValueError, match="slots spinner"):
        entry(teamhgg_game, 4)


@pytest.mark.parametrize(
    ("text", "first", "shown"),
    [
        ("-3", True, "0"),
        ("11", True, "10"),
        ("+5", True, "+5"),
        ("-11", False, "-10"),
        ("14", False, "13"),
        ("-7", False, "-7"),
        ("x", False, "0"),
    ],
)
def test_amounts_are_clamped_when_a_box_loses_focus(text, first, shown):
    assert clamp_amount(text, first=first) == shown


def test_clamping_an_overflowing_amount_raises():
    with pytest.raises(OverflowError):
        clamp_amount("99999999999", first=True)


def test_add_new_appends_a_custom_charm_and_selects_it(
    three_charms, validity, loading_attack_entry
):
    edit = add_new(three_charms, selected=0, entry=loading_attack_entry, validity=validity)

    assert [
        [charm_name(charm) for charm in edit.charms],
        edit.charms[-1].custom,
        edit.selected,
        edit.saved,
        edit.reselected,
    ] == [["O--", "OO-", "OOO", "+3 Loading, +5 Attack O--"], True, 3, True, True]


@pytest.mark.parametrize("entry_fixture", ["impossible_entry", "unreadable_amount_entry"])
def test_add_new_without_a_charm_changes_nothing(three_charms, validity, request, entry_fixture):
    edit = add_new(
        three_charms, selected=1, entry=request.getfixturevalue(entry_fixture), validity=validity
    )

    assert [edit.charms, edit.selected, edit.saved, edit.reselected] == [
        three_charms,
        1,
        False,
        False,
    ]


def test_save_replaces_the_selected_charm_without_marking_it_custom(
    three_charms, validity, loading_attack_entry
):
    edit = replace_selected(three_charms, selected=1, entry=loading_attack_entry, validity=validity)

    assert [
        [charm_name(charm) for charm in edit.charms],
        edit.charms[1].custom,
        edit.selected,
        edit.saved,
        edit.reselected,
    ] == [["O--", "+3 Loading, +5 Attack O--", "OOO"], False, 1, True, False]


def test_save_with_nothing_selected_changes_nothing(three_charms, validity, loading_attack_entry):
    edit = replace_selected(
        three_charms, selected=-1, entry=loading_attack_entry, validity=validity
    )

    assert [edit.charms, edit.selected, edit.saved] == [three_charms, -1, False]


@pytest.mark.parametrize(
    ("selected", "remaining_slots", "new_selected"),
    [(0, [2, 3], 0), (1, [1, 3], 1), (2, [1, 2], 1)],
)
def test_delete_keeps_the_row_or_selects_the_new_last(
    three_charms, selected, remaining_slots, new_selected
):
    edit = delete_selected(three_charms, selected=selected)

    assert [
        [charm.num_slots for charm in edit.charms],
        edit.selected,
        edit.saved,
        edit.reselected,
    ] == [remaining_slots, new_selected, True, True]


def test_deleting_the_only_charm_selects_nothing():
    edit = delete_selected([Charm(num_slots=1)], selected=0)

    assert [edit.charms, edit.selected, edit.saved, edit.reselected] == [[], -1, True, False]


def test_delete_with_nothing_selected_changes_nothing(three_charms):
    edit = delete_selected(three_charms, selected=-1)

    assert [edit.charms, edit.selected, edit.saved] == [three_charms, -1, False]


def test_delete_all_empties_and_saves():
    edit = delete_all()

    assert [edit.charms, edit.selected, edit.saved, edit.reselected] == [[], -1, True, False]


@pytest.mark.parametrize(
    ("move", "selected", "order", "new_selected", "changed"),
    [
        (move_up, 2, [1, 3, 2], 1, True),
        (move_up, 0, [1, 2, 3], 0, False),
        (move_up, -1, [1, 2, 3], -1, False),
        (move_down, 0, [2, 1, 3], 1, True),
        (move_down, 2, [1, 2, 3], 2, False),
        (move_down, -1, [1, 2, 3], -1, False),
    ],
)
def test_moves_swap_neighbours_within_the_list(
    three_charms, move, selected, order, new_selected, changed
):
    edit = move(three_charms, selected=selected)

    assert [
        [charm.num_slots for charm in edit.charms],
        edit.selected,
        edit.saved,
        edit.reselected,
    ] == [order, new_selected, changed, changed]


def test_all_filter_offers_every_ability_but_torso_inc_and_the_other_box(teamhgg_game):
    attack = teamhgg_game.ability_map["Attack"]

    choices = ability_choices(teamhgg_game, filter_index=0, banned=attack)

    assert choices == [
        ability
        for ability in teamhgg_game.abilities
        if ability is not teamhgg_game.torso_inc and ability is not attack
    ]


def test_misc_filter_offers_abilities_without_tags(teamhgg_game):
    choices = ability_choices(teamhgg_game, filter_index=1, banned=None)

    assert [len(choices), any(ability.tags for ability in choices)] == [12, False]


def test_misc_filter_leaves_out_the_other_box(teamhgg_game):
    untagged = ability_choices(teamhgg_game, filter_index=1, banned=None)[0]

    choices = ability_choices(teamhgg_game, filter_index=1, banned=untagged)

    assert [len(choices), untagged in choices] == [11, False]


def test_tag_filters_offer_abilities_with_that_tag(teamhgg_game):
    choices = ability_choices(teamhgg_game, filter_index=2, banned=None)

    assert [
        teamhgg_game.skill_tags[2].name,
        [ability.name for ability in choices[:5]],
        all(any(tag.name == "Offensive" for tag in ability.tags) for ability in choices),
    ] == ["Offensive", ["Attack", "Expert", "FastCharge", "Debilitate", "Gunnery"], True]


def test_tag_filters_leave_out_the_other_box(teamhgg_game):
    choices = ability_choices(
        teamhgg_game, filter_index=2, banned=teamhgg_game.ability_map["Attack"]
    )

    assert [ability.name for ability in choices[:2]] == ["Expert", "FastCharge"]


def test_selecting_a_one_skill_charm_keeps_the_second_amount(teamhgg_game, validity):
    previous = entry(teamhgg_game, 0, "Expert", "2", "Attack", "7")
    charm = created(entry(teamhgg_game, 2, "Attack", "4"), validity)

    selected = entry_for_charm(teamhgg_game, charm, previous)

    assert selected == entry(teamhgg_game, 2, "Attack", "4", None, "7")


def test_selecting_a_two_skill_charm_fills_both_boxes(teamhgg_game, loading_attack_entry):
    charm = Charm(
        num_slots=1,
        abilities=[
            AbilityPair(ability=teamhgg_game.ability_map["Loading"], amount=3),
            AbilityPair(ability=teamhgg_game.ability_map["Attack"], amount=-2),
        ],
    )

    selected = entry_for_charm(teamhgg_game, charm, entry(teamhgg_game))

    assert selected == entry(teamhgg_game, 1, "Loading", "3", "Attack", "-2")


def test_selecting_a_charm_with_both_skills_the_same_leaves_the_second_box_empty(teamhgg_game):
    """The second box's list leaves out the first box's ability, so it can't be selected."""
    attack = teamhgg_game.ability_map["Attack"]
    charm = Charm(
        num_slots=0,
        abilities=[AbilityPair(ability=attack, amount=3), AbilityPair(ability=attack, amount=2)],
    )

    selected = entry_for_charm(teamhgg_game, charm, entry(teamhgg_game))

    assert selected == entry(teamhgg_game, 0, "Attack", "3", None, "2")


def test_selecting_a_torso_inc_charm_shows_none_but_copies_the_amount(teamhgg_game):
    charm = Charm(
        num_slots=0,
        abilities=[
            AbilityPair(ability=teamhgg_game.torso_inc, amount=1),
            AbilityPair(ability=teamhgg_game.ability_map["Attack"], amount=4),
        ],
    )

    selected = entry_for_charm(teamhgg_game, charm, entry(teamhgg_game))

    assert selected == entry(teamhgg_game, 0, None, "1", "Attack", "4")


def test_selecting_a_bare_charm_keeps_both_amounts(teamhgg_game):
    previous = entry(teamhgg_game, 0, "Expert", "2", "Attack", "7")

    selected = entry_for_charm(teamhgg_game, Charm(num_slots=3), previous)

    assert selected == entry(teamhgg_game, 3, None, "2", None, "7")


def test_captured_charms_round_trip_through_the_editor(
    capture_my_charms_files, teamhgg_game, validity
):
    """Selecting each captured charm and creating it again gives the same charm."""
    mismatched = []
    previous = entry(teamhgg_game)
    for path in capture_my_charms_files:
        for charm in load_my_charms(path, teamhgg_game, validity).charms:
            recreated = create_charm(entry_for_charm(teamhgg_game, charm, previous), validity)
            if recreated is None or charm_name(recreated) != charm_name(charm):
                mismatched.append(f"{path.parent.name}: {charm_name(charm)}")

    assert mismatched == []


def test_captured_files_save_back_unchanged_after_moving_a_charm_and_back(
    capture_my_charms_files, teamhgg_game, validity
):
    changed = []
    for path in capture_my_charms_files:
        charms = load_my_charms(path, teamhgg_game, validity).charms
        moved = move_up(charms, selected=1)
        restored = move_down(moved.charms, selected=moved.selected)
        same_bytes = my_charms_text(restored.charms).encode("utf-8") == path.read_bytes()
        if not (moved.saved and restored.saved and same_bytes):
            changed.append(path.parent.name)

    assert changed == []
