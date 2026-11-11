"""Advanced search lists and ticks (frmAdvanced.h, Form1.h:1420-1459)."""

from __future__ import annotations

import pytest

from golden_shapes import relevance_shape
from goldens import formulate_query_json
from mhp3ass.advanced import (
    ArmorOption,
    RememberedTicks,
    advanced_choices,
    apply_selection,
    check_result,
    clear_box,
    default_box,
)
from mhp3ass.model import ArmorType, HunterType


def _default_selection_mismatches(goldens, load_game):
    """Queries whose rel lists change when rebuilt from the dialog's default ticks."""
    sections = ("armor", "decorations")
    mismatched = []
    for golden in goldens:
        game = load_game()
        query = formulate_query_json(game, golden.query)
        apply_selection(query, advanced_choices(query).default_ticks())
        shaped = relevance_shape(game, query)
        ours = {section: shaped[section] for section in sections}
        if ours != {section: golden.relevance[section] for section in sections}:
            mismatched.append(golden.query["id"])
    return mismatched


@pytest.fixture
def head_extra_before_a_default(attack_sharp_query):
    """Positions in the head list of the first piece the quick search leaves out and of a
    piece it uses that comes later."""
    defaults = [listed.default for listed in advanced_choices(attack_sharp_query).armor[0]]
    extra = defaults.index(False)
    later_default = defaults.index(True, extra)
    return {"extra": extra, "later_default": later_default}


@pytest.fixture
def three_box_ticks():
    return [[True, False], [False, True, True], [True]]


@pytest.fixture
def remembered_on_both_pages():
    remembered = RememberedTicks()
    remembered.dialog_closed(HunterType.BLADEMASTER, [[True]])
    remembered.dialog_closed(HunterType.GUNNER, [[False]])
    return remembered


def test_default_ticks_rebuild_the_quick_search_lists(relevance_goldens, load_teamhgg_game):
    assert _default_selection_mismatches(relevance_goldens, load_teamhgg_game) == []


def test_personal_default_ticks_rebuild_the_quick_search_lists(
    personal_relevance_goldens, load_teamhgg_game
):
    assert _default_selection_mismatches(personal_relevance_goldens, load_teamhgg_game) == []


def test_the_dialog_lists_pieces_the_quick_search_leaves_out(attack_sharp_query):
    choices = advanced_choices(attack_sharp_query)

    slots_with_extras = [any(not listed.default for listed in slot) for slot in choices.armor]

    assert slots_with_extras == [True] * len(ArmorType)


def test_a_ticked_inferior_piece_takes_its_inferior_list_position(
    attack_sharp_query, head_extra_before_a_default
):
    """The rebuilt list follows inf order, so an extra piece can land before a default one."""
    choices = advanced_choices(attack_sharp_query)
    ticks = choices.default_ticks()
    ticks[ArmorType.HEAD.value][head_extra_before_a_default["extra"]] = True

    apply_selection(attack_sharp_query, ticks)

    rebuilt = attack_sharp_query.rel_armor[ArmorType.HEAD.value]
    extra_piece = choices.armor[0][head_extra_before_a_default["extra"]].item
    default_piece = choices.armor[0][head_extra_before_a_default["later_default"]].item
    assert rebuilt.index(extra_piece) < rebuilt.index(default_piece)


def test_unticking_a_slot_empties_it(attack_sharp_query):
    choices = advanced_choices(attack_sharp_query)
    ticks = clear_box(choices.default_ticks(), box=ArmorType.LEGS.value)

    apply_selection(attack_sharp_query, ticks)

    assert [
        attack_sharp_query.rel_armor[ArmorType.LEGS.value],
        len(attack_sharp_query.rel_armor[ArmorType.HEAD.value]) > 0,
    ] == [[], True]


def test_unticking_decorations_empties_them(attack_sharp_query):
    choices = advanced_choices(attack_sharp_query)
    ticks = clear_box(choices.default_ticks(), box=len(ArmorType))

    apply_selection(attack_sharp_query, ticks)

    assert attack_sharp_query.rel_decorations == []


def test_ticks_of_the_wrong_length_raise(attack_sharp_query):
    ticks = advanced_choices(attack_sharp_query).default_ticks()
    ticks[ArmorType.ARMS.value].append(True)

    with pytest.raises(ValueError, match="longer"):
        apply_selection(attack_sharp_query, ticks)


def test_no_remembered_ticks_open_with_the_defaults(three_box_ticks):
    assert check_result(three_box_ticks, remembered=None) == three_box_ticks


def test_remembered_ticks_replace_the_defaults_by_position(three_box_ticks):
    remembered = [[False], [True, False, False], []]

    assert check_result(three_box_ticks, remembered) == [
        [False, False],
        [True, False, False],
        [True],
    ]


def test_remembered_ticks_past_a_box_raise(three_box_ticks):
    with pytest.raises(IndexError, match="past the 1 items of box 2"):
        check_result(three_box_ticks, [[], [], [True, True]])


def test_default_button_restores_one_box(three_box_ticks):
    ticks = [[False, True], [True, False, False], [False]]

    assert default_box(ticks, defaults=three_box_ticks, box=1) == [
        [False, True],
        [False, True, True],
        [False],
    ]


def test_none_button_clears_one_box(three_box_ticks):
    assert clear_box(three_box_ticks, box=1) == [[True, False], [False, False, False], [True]]


def test_a_closed_dialog_records_its_ticks_for_its_page():
    remembered = RememberedTicks()

    remembered.dialog_closed(HunterType.GUNNER, [[True], [False]])

    assert [
        remembered.ticks_for(HunterType.GUNNER),
        remembered.ticks_for(HunterType.BLADEMASTER),
    ] == [[[True], [False]], None]


def test_closing_the_window_forgets_the_ticks(remembered_on_both_pages):
    remembered_on_both_pages.dialog_closed(HunterType.GUNNER, None)

    assert [
        remembered_on_both_pages.ticks_for(HunterType.BLADEMASTER),
        remembered_on_both_pages.ticks_for(HunterType.GUNNER),
    ] == [[[True]], None]


def test_a_skill_change_forgets_only_the_page_showing(remembered_on_both_pages):
    remembered_on_both_pages.skill_or_filter_changed(HunterType.BLADEMASTER)

    assert [
        remembered_on_both_pages.ticks_for(HunterType.BLADEMASTER),
        remembered_on_both_pages.ticks_for(HunterType.GUNNER),
    ] == [None, [[False]]]


def test_rank_or_gender_changes_forget_both_pages(remembered_on_both_pages):
    remembered_on_both_pages.rank_or_gender_changed()

    assert [
        remembered_on_both_pages.ticks_for(HunterType.BLADEMASTER),
        remembered_on_both_pages.ticks_for(HunterType.GUNNER),
    ] == [None, None]


@pytest.mark.parametrize(
    ("option", "kept"),
    [
        (ArmorOption.ALLOW_BAD_SKILLS, [[True]]),
        (ArmorOption.ALLOW_PIERCINGS, None),
        (ArmorOption.ALLOW_EVENT_ARMOR, None),
        (ArmorOption.ALLOW_LOW_RANK_ARMOR, None),
    ],
)
def test_option_toggles_forget_except_allow_bad_skills(remembered_on_both_pages, option, kept):
    remembered_on_both_pages.option_toggled(option)

    assert remembered_on_both_pages.ticks_for(HunterType.BLADEMASTER) == kept


def test_both_types_is_not_a_page():
    with pytest.raises(ValueError, match="Blademaster and Gunner"):
        RememberedTicks().ticks_for(HunterType.BOTH_TYPES)
