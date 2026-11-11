"""What each result shows, as data; the TUI lays it out.

Ported from ``Form1::UpdateResultString`` (``legacy/Form1.h:1569-1655``).
Armour notes and extra skills come from the search's own query, not the
latest relevance pass (quirk 47).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from mhp3ass.model import Armor, Charm, Decoration, Skill
from mhp3ass.query import Query
from mhp3ass.results.sorting import SortKey
from mhp3ass.solution.state import Solution


class ArmorNote(Enum):
    """The alternative a result offers for a piece (Form1.h:1577-1585)."""

    ANY_WITH_SLOTS = "any_with_slots"
    ANY_TORSO_INC = "any_torso_inc"


@dataclass(frozen=True)
class ArmorLine:
    armor: Armor
    note: ArmorNote | None


@dataclass(frozen=True)
class DecorationCount:
    decoration: Decoration
    count: int


@dataclass(frozen=True)
class SlotsSpare:
    """``groups``: each spare group's size, smallest first; ``None`` when only the total shows."""

    total: int
    groups: tuple[int, ...] | None


@dataclass(frozen=True)
class SortValue:
    key: SortKey
    value: int


@dataclass(frozen=True)
class SolutionDetails:
    armors: tuple[ArmorLine, ...]
    charm: Charm | None
    decorations: tuple[DecorationCount, ...]
    slots_spare: SlotsSpare | None
    sort_value: SortValue | None
    extra_skills: tuple[Skill, ...]


def armor_note(armor: Armor, query: Query) -> ArmorNote | None:
    """``no_skills`` as ``Armor::MatchesQuery`` sets it for ``query`` (Armor.cpp:115-139).

    Torso-up pieces return before ``no_skills`` is written, so they only ever
    get the Torso Inc note.
    """
    if armor.torso_inc:
        return ArmorNote.ANY_TORSO_INC
    has_skills = any(
        pair.amount > 0 and pair.ability in query.rel_abilities for pair in armor.abilities
    )
    note = None if has_skills else ArmorNote.ANY_WITH_SLOTS
    return note


def decoration_counts(solution: Solution) -> tuple[DecorationCount, ...]:
    """Each distinct decoration and how many, in first-placed order (Form1.h:1597-1606)."""
    counts: dict[Decoration, int] = {}
    for decoration in solution.decorations:
        counts[decoration] = counts.get(decoration, 0) + 1
    decorations = tuple(
        DecorationCount(decoration=decoration, count=count) for decoration, count in counts.items()
    )
    return decorations


def slots_spare(solution: Solution, sort_key: SortKey) -> SlotsSpare | None:
    """Form1.h:1608-1632: shown when any slot is spare or when sorting by slots spare."""
    total = solution.total_slots_spare
    if total == 0 and sort_key is not SortKey.SLOTS_SPARE:
        return None
    spare = solution.slots_spare
    if total <= 1 or spare is None or (total <= 3 and spare[total] == 1):
        return SlotsSpare(total=total, groups=None)
    groups = tuple(size for size in (1, 2, 3) for _ in range(spare[size]))
    shown = SlotsSpare(total=total, groups=groups)
    return shown


def sort_value(solution: Solution, sort_key: SortKey) -> SortValue | None:
    """The sorted stat (Form1.h:1633-1645); none for None and slots spare."""
    stats = {
        SortKey.DRAGON_RES: solution.dragon_res,
        SortKey.FIRE_RES: solution.fire_res,
        SortKey.ICE_RES: solution.ice_res,
        SortKey.THUNDER_RES: solution.thunder_res,
        SortKey.WATER_RES: solution.water_res,
        SortKey.DEFENCE: solution.defence,
        SortKey.MAX_DEFENCE: solution.max_defence,
        SortKey.DIFFICULTY: solution.difficulty,
        SortKey.RARITY: solution.rarity,
    }
    if sort_key not in stats:
        return None
    value = SortValue(key=sort_key, value=stats[sort_key])
    return value


def solution_details(solution: Solution, query: Query, sort_key: SortKey) -> SolutionDetails:
    """One result's details, for the search ``query`` that found it."""
    armors = tuple(
        ArmorLine(armor=armor, note=armor_note(armor, query))
        for armor in solution.armors
        if armor is not None
    )
    extra_skills = tuple(skill for skill in solution.extra_skills if skill not in query.skills)
    details = SolutionDetails(
        armors=armors,
        charm=solution.charm,
        decorations=decoration_counts(solution),
        slots_spare=slots_spare(solution, sort_key),
        sort_value=sort_value(solution, sort_key),
        extra_skills=extra_skills,
    )
    return details
