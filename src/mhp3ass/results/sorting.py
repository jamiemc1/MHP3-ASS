"""Sorting results by the "Sort Results By" drop-down.

Ported from the comparison functions (``legacy/Form1.h:20-80``) and
``Form1::SortResults`` (``legacy/Form1.h:2149-2172``).

The sort is in place and unstable (``results.dotnet_sort``), so ties keep
whatever order the previous sort left, and "None" leaves the list as it is.
"""

from __future__ import annotations

from collections.abc import Callable
from enum import IntEnum

from mhp3ass.data.text import as_signed
from mhp3ass.results.dotnet_sort import introsort
from mhp3ass.solution.state import Solution


class SortKey(IntEnum):
    """The ``cmbSort`` items, in drop-down order."""

    NONE = 0
    DRAGON_RES = 1
    FIRE_RES = 2
    ICE_RES = 3
    THUNDER_RES = 4
    WATER_RES = 5
    DEFENCE = 6
    MAX_DEFENCE = 7
    DIFFICULTY = 8
    RARITY = 9
    SLOTS_SPARE = 10


def compare(x: int, y: int) -> int:
    """``Compare``: ascending."""
    result = -1 if x < y else 1 if y < x else 0
    return result


def reverse_compare(x: int, y: int) -> int:
    """``ReverseCompare``: descending."""
    result = 1 if x < y else -1 if y < x else 0
    return result


# The comparison functions take ``const int``: the unsigned stats arrive as
# ``(int)`` conversions, hence ``as_signed``.


def compare_by_defence(s1: Solution, s2: Solution) -> int:
    result = reverse_compare(as_signed(s1.defence), as_signed(s2.defence))
    return result


def compare_by_max_defence(s1: Solution, s2: Solution) -> int:
    result = reverse_compare(as_signed(s1.max_defence), as_signed(s2.max_defence))
    return result


def compare_by_fire_res(s1: Solution, s2: Solution) -> int:
    return reverse_compare(s1.fire_res, s2.fire_res)


def compare_by_ice_res(s1: Solution, s2: Solution) -> int:
    return reverse_compare(s1.ice_res, s2.ice_res)


def compare_by_water_res(s1: Solution, s2: Solution) -> int:
    return reverse_compare(s1.water_res, s2.water_res)


def compare_by_thunder_res(s1: Solution, s2: Solution) -> int:
    return reverse_compare(s1.thunder_res, s2.thunder_res)


def compare_by_dragon_res(s1: Solution, s2: Solution) -> int:
    return reverse_compare(s1.dragon_res, s2.dragon_res)


def compare_by_rarity(s1: Solution, s2: Solution) -> int:
    result = reverse_compare(as_signed(s1.rarity), as_signed(s2.rarity))
    return result


def compare_by_difficulty(s1: Solution, s2: Solution) -> int:
    """The one ascending key: least difficult first."""
    result = compare(as_signed(s1.difficulty), as_signed(s2.difficulty))
    return result


def compare_by_slots_spare(s1: Solution, s2: Solution) -> int:
    result = reverse_compare(as_signed(s1.total_slots_spare), as_signed(s2.total_slots_spare))
    return result


def solution_comparison(key: SortKey) -> Callable[[Solution, Solution], int] | None:
    """The comparison ``SortResults`` passes to ``List::Sort`` for ``key``; ``None`` for None."""
    comparisons = {
        SortKey.DRAGON_RES: compare_by_dragon_res,
        SortKey.FIRE_RES: compare_by_fire_res,
        SortKey.ICE_RES: compare_by_ice_res,
        SortKey.THUNDER_RES: compare_by_thunder_res,
        SortKey.WATER_RES: compare_by_water_res,
        SortKey.DEFENCE: compare_by_defence,
        SortKey.MAX_DEFENCE: compare_by_max_defence,
        SortKey.DIFFICULTY: compare_by_difficulty,
        SortKey.RARITY: compare_by_rarity,
        SortKey.SLOTS_SPARE: compare_by_slots_spare,
    }
    comparison = comparisons.get(key)
    return comparison


def sort_results(solutions: list[Solution], key: SortKey, array_length: int | None = None) -> None:
    """``SortResults``: sort ``solutions`` in place by ``key``; None leaves them as they are.

    ``array_length`` is the capacity of the ``List`` being sorted
    (``final_solutions``), which sets the introsort's depth limit; it
    defaults to ``len(solutions)``. ``sort_off`` is never set in the
    original, so it isn't modelled.
    """
    comparison = solution_comparison(key)
    if comparison is None:
        return
    introsort(solutions, compare=comparison, array_length=array_length)
