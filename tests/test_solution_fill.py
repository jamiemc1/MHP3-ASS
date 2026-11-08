"""Decoration scoring and the two decoration loops (Solution.cpp:271-404)."""

from __future__ import annotations

from typing import Any

import pytest

from mhp3ass.model import AbilityPair, Charm, Decoration
from mhp3ass.solution.fill import (
    PossibleDecoration,
    UndefinedScoreError,
    add_decorations1,
    add_decorations23,
    best_possible_decoration,
    calculate_decorations,
    get_score,
    is_charm_ability,
    point_score,
)
from mhp3ass.solution.initial import get_initial_data
from mhp3ass.solution.state import Solution, new_calculation_data
from solution_trace import stage_mismatches


def _dense_ranks(values: list[int]) -> list[int]:
    ordered = sorted(set(values))
    ranks = [ordered.index(value) for value in values]
    return ranks


def test_point_score_orders_like_the_harness(solution_probes_golden: Any):
    scores = [point_score(index) for index in range(23)]

    assert scores[:6] == solution_probes_golden["point_score_in_bounds"]
    assert _dense_ranks(scores) == solution_probes_golden["point_score_rank"]


def test_point_score_beyond_the_probed_range_raises():
    with pytest.raises(UndefinedScoreError):
        point_score(23)


def _jewel(name, first, amount, slots=1, second=None, second_amount=0):
    decoration = Decoration(name=name, index=0, rarity=1, slots_required=slots, hr=1, elder_star=1)
    decoration.abilities = [AbilityPair(ability=first, amount=amount)]
    if second is not None:
        decoration.abilities.append(AbilityPair(ability=second, amount=second_amount))
    return decoration


@pytest.fixture
def make_data(make_query):
    """CalculationData over ``rel_decorations`` with the given needs and totals."""

    def make(rel_decorations, need, abilities, charm=None):
        solution = Solution(armors=[None] * 5, charm=charm)
        solution.abilities = dict(abilities)
        data = new_calculation_data(solution, make_query(rel_decorations=rel_decorations))
        data.need = dict(need)
        return data

    return make


def test_negative_points_given_reads_as_unsigned_and_raises(make_data, attack):
    data = make_data([], need={}, abilities={})

    with pytest.raises(UndefinedScoreError):
        get_score(_jewel("Attack", attack, 1), data, -1)


def test_equal_scores_go_to_the_last_candidate_whatever_bad_says(make_data, attack, defense):
    # The first candidate's second skill (Defense) has the higher total; the
    # "less bad" tie-break never applies because >= already took the last.
    data = make_data([], need={}, abilities={attack: 0, defense: 5})
    first = PossibleDecoration(_jewel("first", attack, 1, second=defense, second_amount=-1), 2)
    last = PossibleDecoration(_jewel("last", attack, 1), 2)

    best = best_possible_decoration([first, last], data)

    assert best is last


def test_an_out_of_bounds_score_outranks_every_in_bounds_one(make_data, attack):
    data = make_data([], need={}, abilities={})
    six = PossibleDecoration(_jewel("six", attack, 3), 6)
    four = PossibleDecoration(_jewel("four", attack, 4), 4)

    best = best_possible_decoration([six, four], data)

    assert best is six


def test_add_decorations23_fills_each_slot_group(make_data, attack):
    jewel = _jewel("Attack[2]", attack, 3, slots=2)
    data = make_data([jewel], need={attack: 10}, abilities={attack: 0})

    remaining = add_decorations23(
        data, 2, 2, 1, data.solution.non_body_decorations, allow_bad=True, allow_detrimental=True
    )

    assert remaining == 0
    assert data.solution.non_body_decorations == [jewel, jewel]
    assert data.solution.abilities[attack] == 6


def test_add_decorations23_stops_short_of_overshooting_by_more_than_one(make_data, attack):
    jewel = _jewel("Attack[2]", attack, 3, slots=2)
    data = make_data([jewel], need={attack: 10}, abilities={attack: 7})

    remaining = add_decorations23(
        data, 2, 2, 1, data.solution.non_body_decorations, allow_bad=True, allow_detrimental=True
    )

    assert remaining == 1
    assert data.solution.abilities[attack] == 10


def test_charm_ability_scores_its_full_amount(make_data, attack, defense):
    # Both would fill 2 points of need; the charm's ability scores all 3 of its
    # points, so it beats the later candidate that would otherwise win the tie.
    charm = Charm(abilities=[AbilityPair(ability=defense, amount=1)])
    defense_jewel = _jewel("Defense[2]", defense, 3, slots=2)
    attack_jewel = _jewel("Attack[2]", attack, 3, slots=2)
    data = make_data(
        [defense_jewel, attack_jewel],
        need={attack: 10, defense: 10},
        abilities={attack: 8, defense: 8},
        charm=charm,
    )

    add_decorations23(
        data, 2, 1, 1, data.solution.non_body_decorations, allow_bad=True, allow_detrimental=True
    )

    assert data.solution.decorations == [defense_jewel]


def test_add_decorations23_without_bad_skips_a_second_skill_reaching_minus_ten(
    make_data, attack, defense
):
    jewel = _jewel("Attack[2]", attack, 3, slots=2, second=defense, second_amount=-1)
    data = make_data([jewel], need={attack: 10}, abilities={attack: 0, defense: -9})

    remaining = add_decorations23(data, 2, 1, 1, [], allow_bad=False, allow_detrimental=True)

    assert remaining == 1
    assert data.solution.decorations == []


def test_add_decorations1_repeats_a_decoration_while_it_qualifies(make_data, attack):
    jewel = _jewel("Attack[1]", attack, 1)
    data = make_data([jewel], need={attack: 3}, abilities={attack: 0})

    remaining = add_decorations1(data, 5, 1, [], allow_bad=True, allow_overkill=True)

    assert remaining == 2
    assert data.solution.decorations == [jewel, jewel, jewel]


def test_add_decorations1_without_overkill_keeps_within_amount_minus_one(make_data, attack):
    # On the body at multiplier 2: 9 + 2 * 2 = 13 > 10 + 2 - 1, too far past the need.
    jewel = _jewel("Attack[1]", attack, 2)
    data = make_data([jewel], need={attack: 10}, abilities={attack: 9})

    without_overkill = add_decorations1(data, 1, 2, [], allow_bad=True, allow_overkill=False)
    with_overkill = add_decorations1(data, 1, 2, [], allow_bad=True, allow_overkill=True)

    assert (without_overkill, with_overkill) == (1, 0)


def test_add_decorations1_makes_one_pass(make_data, attack, defense):
    # The Attack jewel is skipped while its Defense -1 would leave Defense short
    # of its need; the Defense jewel later fixes that, but the pass is over.
    defense.relevant = True
    attack_jewel = _jewel("Attack[1]", attack, 1, second=defense, second_amount=-1)
    defense_jewel = _jewel("Defense[1]", defense, 2)
    data = make_data(
        [attack_jewel, defense_jewel],
        need={attack: 2, defense: 2},
        abilities={attack: 0, defense: 1},
    )

    remaining = add_decorations1(data, 3, 1, [], allow_bad=True, allow_overkill=True)

    assert remaining == 2
    assert data.solution.decorations == [defense_jewel]


def test_add_decorations1_applies_detrimental_whatever_the_flags(make_data, attack, defense):
    defense.relevant = True
    jewel = _jewel("Attack[1]", attack, 1, second=defense, second_amount=-1)
    data = make_data([jewel], need={attack: 2, defense: 1}, abilities={attack: 0, defense: 1})

    remaining = add_decorations1(data, 1, 1, [], allow_bad=True, allow_overkill=True)

    assert remaining == 1
    assert data.solution.decorations == []


def test_body_decorations_count_the_multiplier(make_data, attack):
    jewel = _jewel("Attack[1]", attack, 1)
    data = make_data([jewel], need={attack: 3}, abilities={attack: 0})

    add_decorations1(
        data, 2, 2, data.solution.body_decorations, allow_bad=True, allow_overkill=True
    )

    assert data.solution.abilities[attack] == 4
    assert data.solution.body_decorations == [jewel, jewel]


def test_charm_ability_is_the_first_charm_ability_only(attack, defense):
    charm = Charm(
        abilities=[AbilityPair(ability=attack, amount=3), AbilityPair(ability=defense, amount=2)]
    )

    checks = (
        is_charm_ability(charm, attack),
        is_charm_ability(charm, defense),
        is_charm_ability(Charm(num_slots=3), attack),
        is_charm_ability(None, attack),
    )

    assert checks == (True, False, False, False)


def _fill_as_matches_query(data):
    """MatchesQuery's filling pass (Solution.cpp:673): both flags set, whatever the query."""
    calculate_decorations(data, allow_bad=True, allow_detrimental=True)


def test_decorated_stage_matches_every_trace(trace_goldens, scratch_game):
    stages = [("initial", get_initial_data), ("decorated", _fill_as_matches_query)]

    assert stage_mismatches(trace_goldens, scratch_game, stages) == []


def test_personal_decorated_stage_matches_every_trace(personal_trace_goldens, scratch_game):
    stages = [("initial", get_initial_data), ("decorated", _fill_as_matches_query)]

    assert stage_mismatches(personal_trace_goldens, scratch_game, stages) == []


@pytest.fixture
def make_slotted_data(make_data):
    """CalculationData after a GetInitialData-like setup: slot groups by size,
    torso slots, and the total."""

    def make(rel_decorations, need, abilities, slots_spare, torso_slots_spare=0, multiplier=1):
        data = make_data(rel_decorations, need=need, abilities=abilities)
        solution = data.solution
        solution.slots_spare = list(slots_spare)
        solution.torso_slots_spare = torso_slots_spare
        solution.torso_multiplier = multiplier
        solution.total_slots_spare = (
            slots_spare[1] + 2 * slots_spare[2] + 3 * slots_spare[3] + torso_slots_spare
        )
        return data

    return make


def _calculate(data):
    calculate_decorations(data, allow_bad=True, allow_detrimental=True)
    groups = data.solution.slots_spare
    return groups


def test_two_slot_decorations_beyond_two_slot_groups_take_three_slot_groups(
    make_slotted_data, attack
):
    # Two Attack[2] in one 2-slot group and one 3-slot group: the 3 is used
    # as a 2 and leaves a 1 (Solution.cpp:437-443).
    jewel = _jewel("Attack[2]", attack, 3, slots=2)
    data = make_slotted_data([jewel], {attack: 6}, {attack: 0}, slots_spare=[0, 0, 1, 1])

    groups = _calculate(data)

    assert data.solution.decorations == [jewel, jewel]
    assert groups == [0, 1, 0, 0]


def test_one_slot_decorations_spill_into_a_three_through_the_unsigned_wrap(
    make_slotted_data, attack
):
    # Four 1-slot jewels in groups 0/1/1 leave one slot free. On the way,
    # extra = 4 converts one 3 (extra 1, num_2_slots 1), and slots_spare[1]
    # loses 1 - 2 * 1 = -1 (Solution.cpp:478): right only modulo 2**32.
    jewel = _jewel("Attack[1]", attack, 1)
    data = make_slotted_data([jewel], {attack: 4}, {attack: 0}, slots_spare=[0, 0, 1, 1])

    groups = _calculate(data)

    assert len(data.solution.decorations) == 4
    assert groups == [0, 1, 0, 0]


def test_one_slot_decorations_filling_a_three_exactly_leave_the_two(make_slotted_data, attack):
    # Three 1-slot jewels in groups 0/1/1: extra 3 converts one 3 exactly (:470-474).
    jewel = _jewel("Attack[1]", attack, 1)
    data = make_slotted_data([jewel], {attack: 3}, {attack: 0}, slots_spare=[0, 0, 1, 1])

    groups = _calculate(data)

    assert len(data.solution.decorations) == 3
    assert groups == [0, 0, 1, 0]


def test_one_slot_decorations_part_filling_a_three_return_the_rest(make_slotted_data, attack):
    # Two 1-slot jewels in one 3-slot group: the third slot comes back as a
    # 1-slot group (:462-468).
    jewel = _jewel("Attack[1]", attack, 1)
    data = make_slotted_data([jewel], {attack: 2}, {attack: 0}, slots_spare=[0, 0, 0, 1])

    groups = _calculate(data)

    assert len(data.solution.decorations) == 2
    assert groups == [0, 1, 0, 0]


def test_one_slot_decorations_within_one_slot_groups_just_use_them(make_slotted_data, attack):
    jewel = _jewel("Attack[1]", attack, 1)
    data = make_slotted_data([jewel], {attack: 1}, {attack: 0}, slots_spare=[0, 2, 0, 0])

    groups = _calculate(data)

    assert groups == [0, 1, 0, 0]


def test_body_three_slots_take_smaller_decorations_with_the_multiplier(make_slotted_data, attack):
    # A 3-slot body at multiplier 2: one Attack[2] (6 points) then one
    # Attack[1] (2 points) on the body; nothing is left in the torso.
    two = _jewel("Attack[2]", attack, 3, slots=2)
    one = _jewel("Attack[1]", attack, 1)
    data = make_slotted_data(
        [one, two],
        {attack: 8},
        {attack: 0},
        slots_spare=[0, 0, 0, 0],
        torso_slots_spare=3,
        multiplier=2,
    )

    _calculate(data)

    solution = data.solution
    assert solution.body_decorations == [two, one]
    assert (solution.abilities[attack], solution.torso_slots_spare) == (8, 0)


def test_body_one_slot_pass_retries_with_overkill(make_slotted_data, attack):
    # At multiplier 2 a 2-point jewel overshoots 9 -> 13 against need 10, so
    # the no-overkill pass skips it and the overkill pass adds it (:449, :481-482).
    jewel = _jewel("Attack[1]", attack, 2)
    data = make_slotted_data(
        [jewel],
        {attack: 10},
        {attack: 9},
        slots_spare=[0, 0, 0, 0],
        torso_slots_spare=1,
        multiplier=2,
    )

    _calculate(data)

    assert data.solution.body_decorations == [jewel]
    assert data.solution.torso_slots_spare == 0
