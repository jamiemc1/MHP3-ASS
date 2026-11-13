"""What each result shows, as data; the TUI lays it out.

Ported from ``Form1::UpdateResultString`` (``legacy/Form1.h:1569-1655``) and
the armour and decoration ``UpdateContextMenu`` (``legacy/Common.cpp:77-122``).
Armour notes and extra skills come from the results' own query (the search's,
or the one loaded with them from ``settings.cfg``), not the latest relevance
pass (quirk 47).
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from enum import Enum

from mhp3ass.data import GameData
from mhp3ass.model import (
    Ability,
    AbilityPair,
    Armor,
    Charm,
    Decoration,
    MaterialComponent,
    Skill,
)
from mhp3ass.query import Query
from mhp3ass.results.placement import (
    PlacementUnknownError,
    jewel_placement,
    place_can_matter,
    refilled,
)
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
class ChestJewels:
    """The chest's jewels, whose points count ``multiplier`` times, and the rest."""

    multiplier: int
    chest: tuple[DecorationCount, ...]
    elsewhere: tuple[DecorationCount, ...]


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
class UnknownPlacement:
    """A Torso Inc set whose jewels no placement fits (``jewel_placement``)."""


@dataclass(frozen=True)
class SolutionDetails:
    """``chest_jewels``: the jewels by place, for a set where that changes
    their points; ``None`` where it doesn't."""

    armors: tuple[ArmorLine, ...]
    charm: Charm | None
    decorations: tuple[DecorationCount, ...]
    chest_jewels: ChestJewels | UnknownPlacement | None
    slots_spare: SlotsSpare | None
    sort_value: SortValue | None
    extra_skills: tuple[Skill, ...]


@dataclass(frozen=True)
class AbilityLine:
    """``amount`` is ``None`` where the menu shows the name alone: no points, or Torso Inc."""

    ability: Ability
    amount: int | None


@dataclass(frozen=True)
class ArmorDetails:
    """The piece's menu: its name, slots, defence range and resistances, then these."""

    armor: Armor
    abilities: tuple[AbilityLine, ...]
    components: tuple[MaterialComponent, ...]


@dataclass(frozen=True)
class DecorationDetails:
    """The jewel's menu: its name and slots, then these. ``alternative_components``
    is empty for a jewel with one recipe."""

    decoration: Decoration
    abilities: tuple[AbilityLine, ...]
    components: tuple[MaterialComponent, ...]
    alternative_components: tuple[MaterialComponent, ...]


def ability_lines(pairs: list[AbilityPair], game: GameData) -> tuple[AbilityLine, ...]:
    """Common.cpp:77-86."""
    lines = tuple(
        AbilityLine(
            ability=pair.ability,
            amount=pair.amount if pair.amount != 0 and pair.ability is not game.torso_inc else None,
        )
        for pair in pairs
    )
    return lines


def armor_details(armor: Armor, game: GameData) -> ArmorDetails:
    """Common.cpp:107-122."""
    details = ArmorDetails(
        armor=armor,
        abilities=ability_lines(armor.abilities, game),
        components=tuple(armor.components),
    )
    return details


def decoration_details(decoration: Decoration, game: GameData) -> DecorationDetails:
    """Common.cpp:95-105."""
    details = DecorationDetails(
        decoration=decoration,
        abilities=ability_lines(decoration.abilities, game),
        components=tuple(decoration.components),
        alternative_components=tuple(decoration.components2),
    )
    return details


def armor_note(armor: Armor, query: Query) -> ArmorNote | None:
    """``no_skills`` as ``Armor::MatchesQuery`` sets it for ``query`` (Armor.cpp:115-139).

    Torso-up pieces return before ``no_skills`` is written, so they only ever
    get the Torso Inc note. Worked out for any piece, including one the
    query's requirement checks would skip (the original keeps a stale flag).
    """
    if armor.torso_inc:
        return ArmorNote.ANY_TORSO_INC
    has_skills = any(
        pair.amount > 0 and pair.ability in query.rel_abilities for pair in armor.abilities
    )
    note = None if has_skills else ArmorNote.ANY_WITH_SLOTS
    return note


def decoration_counts(decorations: Sequence[Decoration]) -> tuple[DecorationCount, ...]:
    """Each distinct decoration and how many, in first-placed order (Form1.h:1597-1606)."""
    counts = Counter(decorations)
    decoration_count = tuple(
        DecorationCount(decoration=decoration, count=count) for decoration, count in counts.items()
    )
    return decoration_count


def chest_jewels(
    solution: Solution, query: Query, game: GameData
) -> ChestJewels | UnknownPlacement | None:
    """``jewel_placement`` as counts, for the results' own ``query``: ``None``
    where a jewel's place can't change its points, ``UnknownPlacement`` where
    no placement fits the set's slots and points. A set loaded from
    ``settings.cfg`` (multiplier 0: the search never filled it here) is
    ``refilled`` first, and is ``UnknownPlacement`` when the refill isn't the
    loaded set."""
    searched = solution
    if solution.torso_multiplier == 0:
        if not place_can_matter(solution):
            return None
        refill = refilled(solution, query=query, game=game)
        if refill is None:
            return UnknownPlacement()
        searched = refill
    try:
        placement = jewel_placement(searched, weapon_slots=query.weapon_slots_allowed)
    except PlacementUnknownError:
        return UnknownPlacement()
    if placement is None:
        return None
    jewels = ChestJewels(
        multiplier=placement.multiplier,
        chest=decoration_counts(placement.chest),
        elsewhere=decoration_counts(placement.elsewhere),
    )
    return jewels


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


def solution_details(
    solution: Solution, query: Query, sort_key: SortKey, game: GameData
) -> SolutionDetails:
    """One result's details, for the results' own ``query`` in ``game``."""
    armors = tuple(
        ArmorLine(armor=armor, note=armor_note(armor, query))
        for armor in solution.armors
        if armor is not None
    )
    extra_skills = tuple(skill for skill in solution.extra_skills if skill not in query.skills)
    details = SolutionDetails(
        armors=armors,
        charm=solution.charm,
        decorations=decoration_counts(solution.decorations),
        chest_jewels=chest_jewels(solution, query=query, game=game),
        slots_spare=slots_spare(solution, sort_key),
        sort_value=sort_value(solution, sort_key),
        extra_skills=extra_skills,
    )
    return details
