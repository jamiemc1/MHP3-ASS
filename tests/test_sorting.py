"""SortResults and the comparison functions (Form1.h:20-80, :2149-2172)."""

from __future__ import annotations

import pytest

from mhp3ass.results.sorting import SortKey, solution_comparison, sort_results
from mhp3ass.solution.state import Solution


def solution(**stats):
    return Solution(armors=[None] * 5, charm=None, **stats)


@pytest.fixture
def solutions_with_one_stat_each():
    """Three solutions per stat, out of order: the middle value first."""

    def make(field):
        return [solution(**{field: 2}), solution(**{field: 1}), solution(**{field: 3})]

    return make


@pytest.fixture
def defence_and_fire_ties():
    """Four solutions where fire res ties in pairs and defence breaks them the other way."""
    solutions = [
        solution(defence=10, fire_res=1),
        solution(defence=30, fire_res=2),
        solution(defence=20, fire_res=1),
        solution(defence=40, fire_res=2),
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
def test_keys_sort_highest_first(solutions_with_one_stat_each, key, field):
    solutions = solutions_with_one_stat_each(field)

    sort_results(solutions, key)

    assert [getattr(item, field) for item in solutions] == [3, 2, 1]


def test_difficulty_sorts_lowest_first(solutions_with_one_stat_each):
    solutions = solutions_with_one_stat_each("difficulty")

    sort_results(solutions, SortKey.DIFFICULTY)

    assert [item.difficulty for item in solutions] == [1, 2, 3]


def test_none_leaves_the_order_alone(solutions_with_one_stat_each):
    solutions = solutions_with_one_stat_each("defence")
    before = list(solutions)

    sort_results(solutions, SortKey.NONE)

    assert [solution_comparison(SortKey.NONE), solutions] == [None, before]


def test_ties_keep_the_previous_sort(defence_and_fire_ties):
    """Sorting by fire after defence leaves each fire tie in defence order."""
    solutions = list(defence_and_fire_ties)

    sort_results(solutions, SortKey.DEFENCE)
    sort_results(solutions, SortKey.FIRE_RES)

    assert [item.defence for item in solutions] == [40, 30, 20, 10]


def test_unsigned_stats_compare_as_int():
    """The comparisons take ``int``: a difficulty of 2**31 or more is negative and sorts first."""
    solutions = [solution(difficulty=0), solution(difficulty=2**31)]

    sort_results(solutions, SortKey.DIFFICULTY)

    assert [item.difficulty for item in solutions] == [2**31, 0]
