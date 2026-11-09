"""Advanced search lists and ticks (frmAdvanced.h, Form1.h:1420-1459)."""

from __future__ import annotations

import pytest

from golden_shapes import relevance_shape
from mhp3ass.advanced import (
    ArmorOption,
    DialogOutcome,
    HunterTab,
    RememberedTicks,
    advanced_choices,
    apply_selection,
    check_result,
    clear_box,
    default_box,
)
from mhp3ass.model import ArmorType
from mhp3ass.query import QuerySpec
from mhp3ass.relevance import formulate_query


def _default_selection_mismatches(goldens, load_game):
    """Queries whose rel lists change when rebuilt from the dialog's default ticks, and the
    number of slots that list pieces beyond the quick search's."""
    mismatched = []
    slots_with_extras = 0
    for golden in goldens:
        game = load_game()
        query = formulate_query(game, QuerySpec.from_json(golden.query))
        choices = advanced_choices(query)
        slots_with_extras += sum(
            any(not listed.default for listed in slot) for slot in choices.armor
        )
        apply_selection(query, choices.default_ticks())
        shaped = relevance_shape(game, query)
        sections = ("armor", "decorations")
        if {section: shaped[section] for section in sections} != {
            section: golden.relevance[section] for section in sections
        }:
            mismatched.append(golden.query["id"])
    return [mismatched, slots_with_extras > 0]


@pytest.fixture
def attack_sharp_query(scratch_game, attack_sharp_query_json):
    """Attack Up [Med] + Sharp Sword at HR 6, formulated on the scratch game."""
    return formulate_query(scratch_game, QuerySpec.from_json(attack_sharp_query_json))


@pytest.fixture
def three_box_ticks():
    return [[True, False], [False, True, True], [True]]


@pytest.fixture
def remembered_on_both_tabs():
    remembered = RememberedTicks()
    remembered.dialog_closed(HunterTab.BLADEMASTER, DialogOutcome.SEARCH, [[True]])
    remembered.dialog_closed(HunterTab.GUNNER, DialogOutcome.SEARCH, [[False]])
    return remembered


def test_default_ticks_rebuild_the_quick_search_lists(relevance_goldens, load_teamhgg_game):
    assert _default_selection_mismatches(relevance_goldens, load_teamhgg_game) == [[], True]


def test_personal_default_ticks_rebuild_the_quick_search_lists(
    personal_relevance_goldens, load_teamhgg_game
):
    assert _default_selection_mismatches(personal_relevance_goldens, load_teamhgg_game) == [
        [],
        True,
    ]


def test_a_ticked_inferior_piece_takes_its_inferior_list_position(attack_sharp_query):
    """The rebuilt list follows inf order, so an extra piece can land before a default one."""
    choices = advanced_choices(attack_sharp_query)
    slot = ArmorType.HEAD.value
    defaults = [listed.default for listed in choices.armor[slot]]
    extra = defaults.index(False)
    later_default = defaults.index(True, extra)
    ticks = choices.default_ticks()
    ticks[slot][extra] = True

    apply_selection(attack_sharp_query, ticks)

    rebuilt = attack_sharp_query.rel_armor[slot]
    extra_piece = choices.armor[slot][extra].item
    default_piece = choices.armor[slot][later_default].item
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


@pytest.mark.parametrize(
    ("outcome", "remembered"), [(DialogOutcome.SEARCH, [[True]]), (DialogOutcome.CANCEL, [[True]])]
)
def test_search_and_cancel_both_remember_the_ticks(outcome, remembered):
    ticks = RememberedTicks()

    ticks.dialog_closed(HunterTab.GUNNER, outcome, [[True]])

    assert [ticks.ticks_for(HunterTab.GUNNER), ticks.ticks_for(HunterTab.BLADEMASTER)] == [
        remembered,
        None,
    ]


def test_closing_the_window_forgets_the_ticks(remembered_on_both_tabs):
    remembered_on_both_tabs.dialog_closed(HunterTab.GUNNER, DialogOutcome.CLOSED, [[True]])

    assert [
        remembered_on_both_tabs.ticks_for(HunterTab.BLADEMASTER),
        remembered_on_both_tabs.ticks_for(HunterTab.GUNNER),
    ] == [[[True]], None]


def test_a_skill_change_forgets_only_the_page_showing(remembered_on_both_tabs):
    remembered_on_both_tabs.skill_or_filter_changed(HunterTab.BLADEMASTER)

    assert [
        remembered_on_both_tabs.ticks_for(HunterTab.BLADEMASTER),
        remembered_on_both_tabs.ticks_for(HunterTab.GUNNER),
    ] == [None, [[False]]]


def test_rank_or_gender_changes_forget_both_pages(remembered_on_both_tabs):
    remembered_on_both_tabs.rank_or_gender_changed()

    assert [
        remembered_on_both_tabs.ticks_for(HunterTab.BLADEMASTER),
        remembered_on_both_tabs.ticks_for(HunterTab.GUNNER),
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
def test_option_toggles_forget_except_allow_bad_skills(remembered_on_both_tabs, option, kept):
    remembered_on_both_tabs.option_toggled(option)

    assert remembered_on_both_tabs.ticks_for(HunterTab.BLADEMASTER) == kept
