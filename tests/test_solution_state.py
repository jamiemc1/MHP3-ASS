"""MatchesQuery's per-combination setup and the rel_deco_map decoration lookup."""

from __future__ import annotations

import pytest

from mhp3ass.decorations import best_decoration_in_map
from mhp3ass.solution.state import (
    LegacyNullReferenceError,
    Solution,
    allocated_slots,
    build_rel_decoration_map,
    new_calculation_data,
)
from solution_builders import make_jewel


@pytest.fixture
def attack_jewels(attack):
    """Attack jewels in relevance order: two 1-slot, then a 3-slot, then a 2-slot."""
    jewels = [
        make_jewel("Attack[1] first", attack, 1),
        make_jewel("Attack[3]", attack, 5, slots=3),
        make_jewel("Attack[1] second", attack, 1),
        make_jewel("Attack[2]", attack, 3, slots=2),
    ]
    return jewels


def test_rel_decoration_map_groups_by_size_in_relevance_order(make_query, attack_jewels):
    query = make_query(rel_decorations=attack_jewels)

    rel_decoration_map = build_rel_decoration_map(query)

    names = [[decoration.name for decoration in size] for size in rel_decoration_map]
    assert names == [[], ["Attack[1] first", "Attack[1] second"], ["Attack[2]"], ["Attack[3]"]]


def test_new_calculation_data_starts_empty(make_query, attack_jewels):
    query = make_query(rel_decorations=attack_jewels)
    solution = Solution(armors=[None] * 5, charm=None)

    data = new_calculation_data(solution, query)

    assert (data.query, data.solution, data.need, data.relevant) == (query, solution, {}, set())
    assert [len(size) for size in data.rel_decoration_map] == [0, 2, 1, 1]


def test_new_solution_has_no_slots_spare_until_initial_data():
    solution = Solution(armors=[None] * 5, charm=None)

    assert solution.slots_spare is None


def test_allocated_slots_raises_before_initial_data():
    solution = Solution(armors=[None] * 5, charm=None)

    with pytest.raises(LegacyNullReferenceError):
        allocated_slots(solution)


def test_allocated_slots_is_the_solution_s_own_list():
    slots_spare = [0, 1, 0, 2]
    solution = Solution(armors=[None] * 5, charm=None, slots_spare=slots_spare)

    allocated = allocated_slots(solution)

    assert allocated is slots_spare


def test_map_lookup_prefers_the_largest_size_that_fits(make_query, attack_jewels, attack):
    rel_decoration_map = build_rel_decoration_map(make_query(rel_decorations=attack_jewels))

    best = best_decoration_in_map(attack, 2, rel_decoration_map)

    assert best is not None
    assert best.name == "Attack[2]"


def test_map_lookup_takes_the_first_in_relevance_order_within_a_size(
    make_query, attack_jewels, attack
):
    rel_decoration_map = build_rel_decoration_map(make_query(rel_decorations=attack_jewels))

    best = best_decoration_in_map(attack, 1, rel_decoration_map)

    assert best is not None
    assert best.name == "Attack[1] first"


def test_map_lookup_matches_only_the_first_ability(make_query, attack, defense):
    # Defense is this decoration's second skill, which the lookup never reads.
    decoration = make_jewel("Attack, Defense", attack, 1, second=defense, second_amount=-1)
    rel_decoration_map = build_rel_decoration_map(make_query(rel_decorations=[decoration]))

    best = best_decoration_in_map(defense, 3, rel_decoration_map)

    assert best is None


def test_map_lookup_with_zero_slots_reads_only_size_zero(make_query, attack_jewels, attack):
    rel_decoration_map = build_rel_decoration_map(make_query(rel_decorations=attack_jewels))

    best = best_decoration_in_map(attack, 0, rel_decoration_map)

    assert best is None


def test_map_lookup_for_an_ability_without_decorations_is_none(
    make_query, make_ability, attack_jewels
):
    rel_decoration_map = build_rel_decoration_map(make_query(rel_decorations=attack_jewels))

    best = best_decoration_in_map(make_ability("Auto-Guard", 2), 3, rel_decoration_map)

    assert best is None
