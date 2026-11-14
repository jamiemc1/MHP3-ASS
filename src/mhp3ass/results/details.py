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
    JewelPlacement,
    PlacementUnknownError,
    Unbuildable,
    correction,
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
    """A Torso Inc set whose jewels no placement fits (``jewel_placement``),
    or a loaded one the search's fill doesn't reproduce (``refilled``)."""


@dataclass(frozen=True)
class PlacementPending:
    """A Torso Inc set whose placement needs filling it again in the game:
    waiting for a search to stop using it (``while_searching``), or being
    worked out."""

    while_searching: bool = True


@dataclass(frozen=True)
class CorrectedJewels:
    """A Torso Inc set whose shown jewels no placement fits (quirk 52), and
    a version that builds (``correction``): ``charm``, the listed one unless
    ``charm_changed``, with ``jewels``."""

    charm: Charm | None
    charm_changed: bool
    jewels: ChestJewels


@dataclass(frozen=True)
class UnbuildableJewels:
    """A Torso Inc set no jewel list builds (quirk 52), and why."""

    reason: Unbuildable


type Placement = (
    ChestJewels | CorrectedJewels | UnbuildableJewels | UnknownPlacement | PlacementPending | None
)


@dataclass(frozen=True)
class SolutionDetails:
    """``chest_jewels``: the jewels by place, for a set where that changes
    their points; ``None`` where it doesn't."""

    armors: tuple[ArmorLine, ...]
    charm: Charm | None
    decorations: tuple[DecorationCount, ...]
    chest_jewels: Placement
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
    solution: Solution,
    query: Query,
    refill_game: GameData | None,
    charm_templates: Sequence[Charm | None] | None,
) -> Placement:
    """``jewel_placement`` as counts, for the results' own ``query``: ``None``
    where a jewel's place can't change its points.

    Where no placement fits the set's slots and points (quirk 52), the
    ``correction`` that builds, ``UnbuildableJewels`` where none does, or
    ``UnknownPlacement`` where that can't be told without the search's
    ``charm_templates`` (``None`` for loaded results). Working it out fills
    sets in ``refill_game``; with ``None`` (a search is using the game, or
    the caller works it out later in a thread) it is ``PlacementPending``,
    which the caller says the reason for (``while_searching``).

    A set loaded from ``settings.cfg`` is recognised by its multiplier of 0
    (the search sets it to 1 or more for every set it fills, and the file
    doesn't keep it). It is ``refilled`` in ``refill_game`` first, and is
    ``UnknownPlacement`` when the refill isn't the loaded set."""
    searched = solution
    if solution.torso_multiplier == 0:
        if not place_can_matter(solution):
            return None
        if refill_game is None:
            return PlacementPending()
        refill = refilled(solution, query=query, game=refill_game)
        if refill is None:
            return UnknownPlacement()
        searched = refill
    try:
        placement = jewel_placement(searched, weapon_slots=query.weapon_slots_allowed)
    except PlacementUnknownError:
        corrected = _corrected(
            searched, query=query, game=refill_game, charm_templates=charm_templates
        )
        return corrected
    if placement is None:
        return None
    jewels = _counted(placement)
    return jewels


def _corrected(
    searched: Solution,
    query: Query,
    game: GameData | None,
    charm_templates: Sequence[Charm | None] | None,
) -> CorrectedJewels | UnbuildableJewels | UnknownPlacement | PlacementPending:
    if game is None:
        return PlacementPending()
    try:
        found = correction(searched, query=query, game=game, charm_templates=charm_templates)
    except PlacementUnknownError:
        return UnknownPlacement()
    if isinstance(found, Unbuildable):
        return UnbuildableJewels(reason=found)
    corrected = CorrectedJewels(
        charm=found.charm, charm_changed=found.charm_changed, jewels=_counted(found.placement)
    )
    return corrected


def _counted(placement: JewelPlacement) -> ChestJewels:
    jewels = ChestJewels(
        multiplier=placement.multiplier,
        chest=decoration_counts(placement.chest),
        elsewhere=decoration_counts(placement.elsewhere),
    )
    return jewels


def extra_skills(solution: Solution, query_skills: Sequence[Skill]) -> tuple[Skill, ...]:
    """The skills ``solution`` has beyond ``query_skills`` (its search's),
    in its own order, as the original lists them under the set
    (``Form1.h:1646-1653``)."""
    extras = tuple(skill for skill in solution.extra_skills if skill not in query_skills)
    return extras


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
    solution: Solution,
    query: Query,
    sort_key: SortKey,
    refill_game: GameData | None,
    charm_templates: Sequence[Charm | None] | None,
) -> SolutionDetails:
    """One result's details, for the results' own ``query``; ``refill_game``
    and ``charm_templates`` as ``chest_jewels`` takes them."""
    armors = tuple(
        ArmorLine(armor=armor, note=armor_note(armor, query))
        for armor in solution.armors
        if armor is not None
    )
    extras = extra_skills(solution, query_skills=query.skills)
    details = SolutionDetails(
        armors=armors,
        charm=solution.charm,
        decorations=decoration_counts(solution.decorations),
        chest_jewels=chest_jewels(
            solution, query=query, refill_game=refill_game, charm_templates=charm_templates
        ),
        slots_spare=slots_spare(solution, sort_key),
        sort_value=sort_value(solution, sort_key),
        extra_skills=extras,
    )
    return details
