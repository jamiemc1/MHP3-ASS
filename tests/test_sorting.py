"""SortResults and the comparison functions (Form1.h:20-80, :2149-2172), sorted stably."""

from __future__ import annotations

import random

import pytest

from mhp3ass.results.sorting import SortKey, solution_comparison, sort_results
from mhp3ass.solution.state import Solution


def solution(**stats):
    return Solution(armors=[None] * 5, charm=None, **stats)


@pytest.fixture
def shuffled_values():
    """0-19 in a fixed shuffled order."""
    values = list(range(20))
    random.Random(7).shuffle(values)
    return values


@pytest.fixture
def seventeen_fire_ties():
    """17 solutions with equal fire res, told apart by defence 0-16 in arrival order."""
    solutions = [solution(fire_res=5, defence=index) for index in range(17)]
    return solutions


@pytest.fixture
def defence_pairs_with_shuffled_fire():
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

    sort_results(solutions, key)

    assert [getattr(item, field) for item in solutions] == list(range(19, -1, -1))


def test_difficulty_sorts_lowest_first(shuffled_values):
    solutions = [solution(difficulty=value) for value in shuffled_values]

    sort_results(solutions, SortKey.DIFFICULTY)

    assert [item.difficulty for item in solutions] == list(range(20))


def test_none_leaves_the_order_alone(shuffled_values):
    solutions = [solution(defence=value) for value in shuffled_values]
    before = list(solutions)

    sort_results(solutions, SortKey.NONE)

    assert [solution_comparison(SortKey.NONE), solutions] == [None, before]


def test_ties_keep_their_arrival_order(seventeen_fire_ties):
    solutions = list(seventeen_fire_ties)

    sort_results(solutions, SortKey.FIRE_RES)

    assert [item.defence for item in solutions] == list(range(17))


def test_ties_keep_the_order_the_previous_sort_left(defence_pairs_with_shuffled_fire):
    """Defence after fire res: highest defence first, each defence tie in fire res order."""
    solutions = list(defence_pairs_with_shuffled_fire)
    expected = sorted(solutions, key=lambda item: (-item.defence, -item.fire_res))

    sort_results(solutions, SortKey.FIRE_RES)
    sort_results(solutions, SortKey.DEFENCE)

    assert [id(item) for item in solutions] == [id(item) for item in expected]


def test_unsigned_stats_compare_as_int():
    """The comparisons take ``int``: a difficulty of 2**31 or more is negative and sorts first."""
    solutions = [solution(difficulty=0), solution(difficulty=2**31)]

    sort_results(solutions, SortKey.DIFFICULTY)

    assert [item.difficulty for item in solutions] == [2**31, 0]
