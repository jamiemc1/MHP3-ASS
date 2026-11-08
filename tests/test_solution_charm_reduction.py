"""Charm reduction and gem consolidation (Solution.cpp:487-658), and CalculateData.

The traces check these stages on shipped data (test_matches_query.py); these
pin the rules shipped data doesn't reach, or reaches too rarely to rely on.
"""

from __future__ import annotations

from functools import partial

import pytest

from mhp3ass.data import GameData
from mhp3ass.model import AbilityPair, Charm, Skill
from mhp3ass.solution import calculate_data, finish
from mhp3ass.solution.bad_skills import fix_bad_skill
from mhp3ass.solution.charm_reduction import (
    LegacyListIndexError,
    num_1slot_decorations,
    potential_spare_slots,
    rearrange_decorations,
    reduce_charm,
    reduce_skills,
    reduce_slots,
    room_for_2_slot,
    room_for_3_slot,
    swap_out,
)
from mhp3ass.solution.fill import calculate_decorations
from mhp3ass.solution.initial import add_initial_armor
from mhp3ass.solution.state import LegacyNullReferenceError, Solution
from solution_builders import make_jewel


@pytest.fixture
def five_pieces(make_armor):
    """Head 3 slots, body 1, arms 2, waist 0, legs 1."""
    pieces = [make_armor(name=f"Piece {slots}", num_slots=slots) for slots in (3, 1, 2, 0, 1)]
    return pieces


def test_potential_spare_slots_counts_groups_less_decorations_of_that_size(
    make_data, five_pieces, attack
):
    charm = Charm(num_slots=2)
    data = make_data([], need={}, abilities={}, charm=charm, weapon_slots_allowed=2)
    data.solution.armors = five_pieces
    data.solution.decorations = [make_jewel("Two", attack, 3, slots=2)]

    # Size 2: arms, the weapon and the charm, less one 2-slot gem.
    assert [potential_spare_slots(data, 2), potential_spare_slots(data, 1)] == [2, 2]


def test_potential_spare_slots_dereferences_an_empty_armour_slot(make_data, five_pieces):
    """Quirk 24: Solution.cpp:510-513 reads every piece's slots."""
    data = make_data([], need={}, abilities={}, charm=Charm(num_slots=1))
    data.solution.armors = [*five_pieces[:4], None]

    with pytest.raises(LegacyNullReferenceError):
        potential_spare_slots(data, 3)


def test_room_for_3_slot_needs_a_free_3_group(make_data, five_pieces, attack):
    data = make_data([], need={}, abilities={}, charm=Charm(num_slots=0))
    data.solution.armors = five_pieces
    data.solution.decorations = [make_jewel("Three", attack, 5, slots=3)]

    # The head's 3-slot group is used; the arms' 2 is still free.
    assert [room_for_3_slot(data), room_for_2_slot(data)] == [False, True]


def test_num_1slot_decorations_counts_body_gems_only_at_multiplier_1(make_data, attack):
    one = make_jewel("One", attack, 1)
    data = make_data([], need={}, abilities={})
    solution = data.solution
    solution.non_body_decorations = [one]
    solution.body_decorations = [one, one]
    solution.torso_multiplier = 1
    plain = num_1slot_decorations(solution, attack)
    solution.torso_multiplier = 2

    assert [plain, num_1slot_decorations(solution, attack)] == [3, 1]


def test_swap_out_uses_raw_amounts_and_leaves_the_body_list(attack, defense):
    """Quirk 22: a body gem counted twice comes off once, and stays listed."""
    one = make_jewel("One", attack, 1, second=defense, second_amount=-1)
    three = make_jewel("Three", attack, 5, slots=3, second=defense, second_amount=-1)
    solution = Solution(armors=[None] * 5, charm=None)
    solution.decorations = [one, one, one]
    solution.body_decorations = [one]
    solution.abilities = {attack: 4, defense: -4}

    swap_out(solution, three)

    assert [solution.decorations, solution.body_decorations, solution.abilities] == [
        [three],
        [one],
        {attack: 6, defense: -2},
    ]


def test_swap_out_past_the_last_gem_indexes_off_the_list(attack):
    """The Assert at Solution.cpp:542 is compiled out, so the loop runs past the end."""
    one = make_jewel("One", attack, 1)
    solution = Solution(armors=[None] * 5, charm=None)
    solution.decorations = [one]
    solution.abilities = {attack: 1}

    with pytest.raises(LegacyListIndexError):
        swap_out(solution, make_jewel("Two", attack, 3, slots=2))


def test_swap_out_into_an_ability_not_yet_in_the_totals_raises(attack, defense):
    """Solution.cpp:555 reads before it writes, so a new ability throws."""
    one = make_jewel("One", attack, 1)
    solution = Solution(armors=[None] * 5, charm=None)
    solution.decorations = [one, one]
    solution.abilities = {attack: 2}

    with pytest.raises(KeyError):
        swap_out(solution, make_jewel("Two", attack, 3, slots=2, second=defense, second_amount=-1))


def test_reduce_slots_frees_the_smallest_group_that_fits(make_data, attack):
    charm = Charm(num_slots=1, abilities=[AbilityPair(ability=attack, amount=3)])
    data = make_data([], need={}, abilities={}, charm=charm)
    data.solution.slots_spare = [0, 0, 1, 1]
    data.solution.total_slots_spare = 5

    reduce_slots(data)

    assert [data.solution.slots_spare, data.solution.total_slots_spare, charm.num_slots] == [
        [0, 1, 0, 1],
        4,
        0,
    ]


def test_reduce_slots_moves_an_exact_fit_to_slots_spare_0(make_data):
    charm = Charm(num_slots=2)
    data = make_data([], need={}, abilities={}, charm=charm)
    data.solution.slots_spare = [0, 0, 1, 0]
    data.solution.total_slots_spare = 2

    reduce_slots(data)

    assert [data.solution.slots_spare, data.solution.total_slots_spare] == [[1, 0, 0, 0], 0]


def test_reduce_slots_does_nothing_without_free_slots(make_data):
    charm = Charm(num_slots=2)
    data = make_data([], need={}, abilities={}, charm=charm)
    data.solution.slots_spare = [0, 0, 1, 0]
    data.solution.total_slots_spare = 0

    reduce_slots(data)

    assert [data.solution.slots_spare, charm.num_slots] == [[0, 0, 1, 0], 2]


def test_reduce_skills_fills_for_the_charm_points_then_restores_need(make_data, attack):
    one = make_jewel("One", attack, 1)
    charm = Charm(num_slots=0, abilities=[AbilityPair(ability=attack, amount=2)])
    data = make_data([one], need={attack: 10}, abilities={attack: 10}, charm=charm)
    solution = data.solution
    solution.slots_spare = [0, 2, 0, 0]
    solution.total_slots_spare = 2
    solution.torso_multiplier = 1

    reduce_skills(data)

    assert [data.need, solution.abilities, solution.decorations] == [
        {attack: 10},
        {attack: 12},
        [one, one],
    ]


def test_reduce_charm_takes_off_only_what_isnt_needed(make_data, attack, defense):
    charm = Charm(
        num_slots=0,
        abilities=[AbilityPair(ability=attack, amount=5), AbilityPair(ability=defense, amount=3)],
    )
    data = make_data(
        [], need={attack: 15, defense: 0}, abilities={attack: 17, defense: 3}, charm=charm
    )

    reduce_charm(data)

    # Defense isn't needed (need 0), so it keeps its points.
    assert [[(pair.ability, pair.amount) for pair in charm.abilities], data.solution.abilities] == [
        [(attack, 3), (defense, 3)],
        {attack: 15, defense: 3},
    ]


def test_reduce_charm_short_of_the_need_adds_points(make_data, attack):
    """Quirk 25: with extra < 0 (Assert compiled out), take_off is negative."""
    charm = Charm(num_slots=0, abilities=[AbilityPair(ability=attack, amount=4)])
    data = make_data([], need={attack: 15}, abilities={attack: 12}, charm=charm)

    reduce_charm(data)

    assert [charm.abilities[0].amount, data.solution.abilities[attack]] == [7, 15]


def test_reduce_charm_nulls_a_charm_with_nothing_left(make_data, attack):
    charm = Charm(num_slots=0, abilities=[AbilityPair(ability=attack, amount=2)])
    data = make_data([], need={attack: 10}, abilities={attack: 12}, charm=charm)

    reduce_charm(data)

    assert data.solution.charm is None


def test_reduce_charm_keeps_a_slotted_charm_without_skills(make_data, attack):
    charm = Charm(num_slots=1, abilities=[AbilityPair(ability=attack, amount=2)])
    data = make_data([], need={attack: 10}, abilities={attack: 12}, charm=charm)

    reduce_charm(data)

    assert [data.solution.charm is charm, charm.abilities] == [True, []]


def test_rearrange_swaps_three_one_slot_gems_for_a_three_slot_gem(make_data, five_pieces, attack):
    one = make_jewel("One", attack, 1)
    three = make_jewel("Three", attack, 4, slots=3)
    charm = Charm(num_slots=0, abilities=[AbilityPair(ability=attack, amount=2)], custom=True)
    data = make_data([one, three], need={attack: 5}, abilities={attack: 5}, charm=charm)
    solution = data.solution
    solution.armors = five_pieces
    solution.torso_multiplier = 1
    solution.decorations = [one, one, one]
    solution.non_body_decorations = [one, one, one]

    rearrange_decorations(data)

    assert [solution.decorations, solution.abilities] == [[three], {attack: 6}]


def test_rearrange_counts_one_slot_gems_once(make_data, five_pieces, attack):
    """num1 is counted before the loop: after a 3-for-1 swap of four gems, one gem
    remains but num1 is 1, so no 2-slot swap follows."""
    one = make_jewel("One", attack, 1)
    two = make_jewel("Two", attack, 3, slots=2)
    three = make_jewel("Three", attack, 4, slots=3)
    charm = Charm(num_slots=0, abilities=[AbilityPair(ability=attack, amount=2)], custom=True)
    data = make_data([one, two, three], need={attack: 6}, abilities={attack: 6}, charm=charm)
    solution = data.solution
    solution.armors = five_pieces
    solution.torso_multiplier = 1
    solution.decorations = [one, one, one, one]
    solution.non_body_decorations = [one, one, one, one]

    rearrange_decorations(data)

    assert solution.decorations == [one, three]


def test_calculate_data_sums_the_armour(make_armor):
    pieces = [make_armor(defence=10 + i, rarity=1, fire_res=i) for i in range(5)]
    solution = Solution(armors=pieces, charm=None)
    solution.defence = 999

    calculate_data(solution)

    assert [solution.defence, solution.rarity, solution.fire_res] == [60, 5, 10]


def test_calculate_data_dereferences_an_empty_slot(make_armor):
    solution = Solution(armors=[make_armor(), None, None, None, None], charm=None)

    with pytest.raises(LegacyNullReferenceError):
        calculate_data(solution)


@pytest.mark.parametrize(
    "stage",
    ["finish", "calculate_decorations", "add_initial_armor", "fix_bad_skill", "reduce_slots"],
)
def test_stages_before_get_initial_data_dereference_null_slots(
    stage, make_data, make_armor, attack
):
    """slots_spare is allocated by GetInitialData (Solution.cpp:247): a stage that
    reads it before then dereferences a null array, as the original would."""
    data = make_data([], need={}, abilities={}, charm=Charm(num_slots=1))
    data.solution.total_slots_spare = 1
    down = Skill(name="Attack Down", points_required=-10, ability=attack)
    calls = {
        "finish": partial(finish, data),
        "calculate_decorations": partial(
            calculate_decorations, data, allow_bad=True, allow_detrimental=True
        ),
        "add_initial_armor": partial(add_initial_armor, make_armor(), data.solution, multiplier=1),
        "fix_bad_skill": partial(fix_bad_skill, data, GameData(), down),
        "reduce_slots": partial(reduce_slots, data),
    }

    with pytest.raises(LegacyNullReferenceError):
        calls[stage]()


def test_charm_stages_dereference_a_missing_charm(make_data):
    data = make_data([], need={}, abilities={})

    with pytest.raises(LegacyNullReferenceError):
        rearrange_decorations(data)


def test_reduce_slots_wraps_an_undercount_like_unsigned(make_data):
    """total_slots_spare is unsigned. It always includes the charm's own
    slots on real data, so this only pins the wrap a smaller count would give."""
    charm = Charm(num_slots=2)
    data = make_data([], need={}, abilities={}, charm=charm)
    data.solution.slots_spare = [0, 0, 1, 0]
    data.solution.total_slots_spare = 1

    reduce_slots(data)

    assert data.solution.total_slots_spare == 2**32 - 1
