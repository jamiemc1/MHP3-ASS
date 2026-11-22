"""The "Sort Results By" keys, their names and the stat each one sorts by.

Ported from the comparison functions (``legacy/Form1.h:20-80``),
``Form1::SortResults``' choice of one per key (``legacy/Form1.h:2149-2172``)
and ``cmbSort``'s item text (``legacy/Form1.h:2090-2100``): ``stat_key``
gives each key's stat, negated for the keys that put the highest first, and
``sort_label`` its name. The results are sorted by
``results.view.sorted_positions``.

Each key's stat and direction are the original's. The order of solutions
with equal values is presentation, not part of the port's contract:
``sorted_positions`` puts ties in a fixed order. The original's
``List<T>.Sort`` is an unstable introsort whose tie order depends on the
previous sort and the list's capacity (quirk 27).
"""

from __future__ import annotations

from collections.abc import Callable
from enum import IntEnum

from mhp3ass.data.strings import StringIndex
from mhp3ass.data.text import as_signed
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


def sort_label(key: SortKey) -> StringIndex:
    """``cmbSort``'s item text for ``key`` (``Form1.h:2090-2100``)."""
    match key:
        case SortKey.NONE:
            return StringIndex.NONE
        case SortKey.DRAGON_RES:
            return StringIndex.DRAGON_RES
        case SortKey.FIRE_RES:
            return StringIndex.FIRE_RES
        case SortKey.ICE_RES:
            return StringIndex.ICE_RES
        case SortKey.THUNDER_RES:
            return StringIndex.THUNDER_RES
        case SortKey.WATER_RES:
            return StringIndex.WATER_RES
        case SortKey.DEFENCE:
            return StringIndex.BASE_DEFENCE
        case SortKey.MAX_DEFENCE:
            return StringIndex.MAX_DEFENCE
        case SortKey.DIFFICULTY:
            return StringIndex.DIFFICULTY
        case SortKey.RARITY:
            return StringIndex.RARITY
        case SortKey.SLOTS_SPARE:
            return StringIndex.SORT_SLOTS_SPARE


def stat_key(key: SortKey) -> Callable[[Solution], int] | None:
    """The sort key ``SortResults``' comparison for ``key`` amounts to: the
    solution's stat, negated where the comparison is ``ReverseCompare`` (every
    key but Difficulty), so an ascending sort by it puts solutions in the
    comparison's order. ``None`` for None.

    The comparison functions take ``const int``: the unsigned stats arrive as
    ``(int)`` conversions, hence ``as_signed``.
    """
    stats: dict[SortKey, Callable[[Solution], int]] = {
        SortKey.DRAGON_RES: lambda solution: solution.dragon_res,
        SortKey.FIRE_RES: lambda solution: solution.fire_res,
        SortKey.ICE_RES: lambda solution: solution.ice_res,
        SortKey.THUNDER_RES: lambda solution: solution.thunder_res,
        SortKey.WATER_RES: lambda solution: solution.water_res,
        SortKey.DEFENCE: lambda solution: as_signed(solution.defence),
        SortKey.MAX_DEFENCE: lambda solution: as_signed(solution.max_defence),
        SortKey.DIFFICULTY: lambda solution: as_signed(solution.difficulty),
        SortKey.RARITY: lambda solution: as_signed(solution.rarity),
        SortKey.SLOTS_SPARE: lambda solution: as_signed(solution.total_slots_spare),
    }
    if key == SortKey.NONE:
        return None
    stat = stats[key]
    if sorts_ascending(key):
        return stat

    def highest_first(solution: Solution) -> int:
        negated = -stat(solution)
        return negated

    return highest_first


def sorts_ascending(key: SortKey) -> bool | None:
    """Whether ``key``'s comparison puts the lowest value first (only
    Difficulty, the one ``Compare`` rather than ``ReverseCompare``); ``None``
    for None, which keeps the arrival order."""
    if key == SortKey.NONE:
        return None
    ascending = key == SortKey.DIFFICULTY
    return ascending
