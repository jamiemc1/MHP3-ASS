"""The comparison functions (Form1.h:20-80) and which way each key sorts."""

from __future__ import annotations

import functools
import random

import pytest

from mhp3ass.results.sorting import SortKey, solution_comparison, sorts_ascending
from mhp3ass.solution.state import Solution


def solution(**stats):
    return Solution(armors=[None] * 5, charm=None, **stats)


def sorted_by(solutions, key):
    comparison = solution_comparison(key)
    if comparison is None:
        raise ValueError(f"{key.name} has no comparison")
    ordered = sorted(solutions, key=functools.cmp_to_key(comparison))
    return ordered


@pytest.fixture
def shuffled_values():
    """0-19 in a fixed shuffled order."""
    values = list(range(20))
    random.Random(7).shuffle(values)
    return values


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

    ordered = sorted_by(solutions, key)

    assert [getattr(item, field) for item in ordered] == list(range(19, -1, -1))


def test_difficulty_sorts_lowest_first(shuffled_values):
    solutions = [solution(difficulty=value) for value in shuffled_values]

    ordered = sorted_by(solutions, SortKey.DIFFICULTY)

    assert [item.difficulty for item in ordered] == list(range(20))


def test_sorts_ascending_says_which_way_every_key_sorts(shuffled_values):
    """Every key but None, so a new key without a direction fails here."""
    fields = {
        SortKey.DRAGON_RES: "dragon_res",
        SortKey.FIRE_RES: "fire_res",
        SortKey.ICE_RES: "ice_res",
        SortKey.THUNDER_RES: "thunder_res",
        SortKey.WATER_RES: "water_res",
        SortKey.DEFENCE: "defence",
        SortKey.MAX_DEFENCE: "max_defence",
        SortKey.DIFFICULTY: "difficulty",
        SortKey.RARITY: "rarity",
        SortKey.SLOTS_SPARE: "total_slots_spare",
    }
    directions = {}
    for key in SortKey:
        if key is SortKey.NONE:
            continue
        field = fields[key]
        ordered = sorted_by([solution(**{field: value}) for value in shuffled_values], key)
        first_is_lowest = getattr(ordered[0], field) < getattr(ordered[-1], field)
        directions[key] = (sorts_ascending(key), first_is_lowest)

    assert all(said is found for said, found in directions.values())
    assert [key for key, (said, _) in directions.items() if said] == [SortKey.DIFFICULTY]


def test_none_sorts_neither_way():
    assert sorts_ascending(SortKey.NONE) is None


def test_none_has_no_comparison():
    assert solution_comparison(SortKey.NONE) is None


def test_unsigned_stats_compare_as_int():
    """The comparisons take ``int``: a difficulty of 2**31 or more is negative and sorts first."""
    solutions = [solution(difficulty=0), solution(difficulty=2**31)]

    ordered = sorted_by(solutions, SortKey.DIFFICULTY)

    assert [item.difficulty for item in ordered] == [2**31, 0]
