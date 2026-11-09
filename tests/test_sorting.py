"""SortResults and the comparison functions (Form1.h:20-80, :2149-2172)."""

from __future__ import annotations

import random

import pytest

from mhp3ass.results.sorting import SortKey, solution_comparison, sort_results
from mhp3ass.solution.state import Solution


def solution(**stats):
    return Solution(armors=[None] * 5, charm=None, **stats)


@pytest.fixture
def shuffled_values():
    """0-19 in a fixed shuffled order: more than 16, so the sort partitions."""
    values = list(range(20))
    random.Random(7).shuffle(values)
    return values


@pytest.fixture
def seventeen_fire_ties():
    """17 solutions with equal fire res, told apart by defence 0-16."""
    solutions = [solution(fire_res=5, defence=index) for index in range(17)]
    return solutions


@pytest.fixture
def seventeen_defence_pairs_with_fire_order():
    """17 solutions: defence ties in pairs, fire res 0-16 in a shuffled order."""
    fire_values = list(range(17))
    random.Random(3).shuffle(fire_values)
    solutions = [
        solution(defence=index // 2, fire_res=fire) for index, fire in enumerate(fire_values)
    ]
    return solutions


@pytest.mark.parametrize(
    ("key", "field"),
    [
        (SortKey.DRAGON_RES, "dragon_res"),
        (SortKey.FIRE_RES, "fire_res"),
        (SortKey.ICE_RES, "ice_res"),
        (SortKey.THUNDER_RES, "thunder_res"),
        (SortKey.WATER_RES, "water_res"),
        (SortKey.DEFENCE, "defence"),
        (SortKey.MAX_DEFENCE, "max_defence"),
        (SortKey.RARITY, "rarity"),
        (SortKey.SLOTS_SPARE, "total_slots_spare"),
    ],
)
def test_keys_sort_highest_first(shuffled_values, key, field):
    solutions = [solution(**{field: value}) for value in shuffled_values]

    sort_results(solutions, key, array_length=len(solutions))

    assert [getattr(item, field) for item in solutions] == list(range(19, -1, -1))


def test_difficulty_sorts_lowest_first(shuffled_values):
    solutions = [solution(difficulty=value) for value in shuffled_values]

    sort_results(solutions, SortKey.DIFFICULTY, array_length=len(solutions))

    assert [item.difficulty for item in solutions] == list(range(20))


def test_none_leaves_the_order_alone(shuffled_values):
    solutions = [solution(defence=value) for value in shuffled_values]
    before = list(solutions)

    sort_results(solutions, SortKey.NONE, array_length=len(solutions))

    assert [solution_comparison(SortKey.NONE), solutions] == [None, before]


def test_ties_are_reordered_by_partitioning(seventeen_fire_ties):
    """17 equal keys go through one partition, which moves them (hand-traced)."""
    solutions = list(seventeen_fire_ties)

    sort_results(solutions, SortKey.FIRE_RES, array_length=len(solutions))

    assert [item.defence for item in solutions] == [
        0, 14, 13, 12, 11, 10, 9, 15, 8, 6, 5, 4, 3, 2, 1, 7, 16
    ]  # fmt: skip


def test_ties_keep_the_previous_sort(seventeen_defence_pairs_with_fire_order):
    """Sorting by defence after fire res gives a different tie order than defence alone."""
    after_fire = list(seventeen_defence_pairs_with_fire_order)
    alone = list(seventeen_defence_pairs_with_fire_order)

    sort_results(after_fire, SortKey.FIRE_RES, array_length=17)
    sort_results(after_fire, SortKey.DEFENCE, array_length=17)
    sort_results(alone, SortKey.DEFENCE, array_length=17)

    assert [item.defence for item in after_fire] == [item.defence for item in alone]
    assert [item.fire_res for item in after_fire] != [item.fire_res for item in alone]


def test_unsigned_stats_compare_as_int():
    """The comparisons take ``int``: a difficulty of 2**31 or more is negative and sorts first."""
    solutions = [solution(difficulty=0), solution(difficulty=2**31)]

    sort_results(solutions, SortKey.DIFFICULTY, array_length=4)

    assert [item.difficulty for item in solutions] == [2**31, 0]
