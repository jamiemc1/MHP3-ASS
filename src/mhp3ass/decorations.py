"""Comparing decorations and choosing them for a query.

Ported from ``Decoration::GetSkillAt``, ``NotWorse``,
``Decoration::IsBetterThan``, ``Decoration::GetBestDecoration( …, Query^ )``
and ``Decoration::MatchesQuery`` (``legacy/Decoration.cpp:82-137``).
"""

from __future__ import annotations

from mhp3ass.data import GameData
from mhp3ass.data.text import as_unsigned
from mhp3ass.model import Ability, Decoration
from mhp3ass.query import Query, rank_locked


class NoDecorationsError(LookupError):
    """Quirk 8: the original's ``KeyNotFoundException`` for an ability with no decorations."""


def decoration_skill_at(decoration: Decoration, ability: Ability) -> int:
    """``Decoration::GetSkillAt``: the decoration's points in ``ability``, or 0."""
    points = next((pair.amount for pair in decoration.abilities if pair.ability is ability), 0)
    return points


def _not_worse(decoration: Decoration, other: Decoration) -> bool:
    """``NotWorse`` (Decoration.cpp:90-93): compares second skills per slot.

    ``amount * slots_required`` is ``int * unsigned``, so C++ compares the
    products as unsigned: a negative product wraps above every positive one.
    """
    if len(other.abilities) != 2:
        return False
    if len(decoration.abilities) == 1:
        return True
    ours = as_unsigned(decoration.abilities[1].amount * other.slots_required)
    theirs = as_unsigned(other.abilities[1].amount * decoration.slots_required)
    not_worse = ours < theirs
    return not_worse


def decoration_is_better_than(decoration: Decoration, other: Decoration) -> bool:
    """``Decoration::IsBetterThan`` (Decoration.cpp:95-102).

    Fewer slots, or a different first ability, counts as better. Otherwise
    the first skill's points per slot decide, then ``_not_worse``. The
    original's ``rel_abilities`` argument is unused, so it is dropped. The
    products here are stored in ``int``, so they compare signed; the shipped
    data keeps them far from overflow.
    """
    if decoration.slots_required < other.slots_required:
        return True
    if decoration.abilities[0].ability is not other.abilities[0].ability:
        return True
    ours = decoration.abilities[0].amount * other.slots_required
    theirs = other.abilities[0].amount * decoration.slots_required
    if ours != theirs:
        return ours > theirs
    better = _not_worse(decoration, other)
    return better


def _available(decoration: Decoration, query: Query) -> bool:
    available = not rank_locked(decoration.hr, decoration.elder_star, query)
    return available


def best_decoration_for_query(
    game: GameData, ability: Ability, max_slots: int, query: Query
) -> Decoration | None:
    """``GetBestDecoration( ability, max_slots, query )`` (Decoration.cpp:104-124).

    The best available decoration fitting ``max_slots`` with positive points in
    ``ability``. ``IsBetterThan`` is strict, so among equals the first in load
    order wins. Only the query's HR and village stars are read.

    Raises ``NoDecorationsError`` for an ability no decoration has first
    (quirk 8): the original indexes its map unchecked, before any filter.
    """
    if ability not in game.decorations_by_ability:
        raise NoDecorationsError(ability.name)
    best = None
    for decoration in game.decorations_by_ability[ability]:
        if not _available(decoration, query) or decoration.slots_required > max_slots:
            continue
        for pair in decoration.abilities:
            gives_points = pair.amount > 0 and pair.ability is ability
            if gives_points and (best is None or decoration_is_better_than(decoration, best)):
                best = decoration
    return best


def decoration_matches_query(decoration: Decoration, query: Query) -> bool:
    """``Decoration::MatchesQuery`` (Decoration.cpp:126-137): available, and its
    first ability is one the query asks for."""
    if not _available(decoration, query) or (decoration.is_event and not query.allow_event):
        return False
    first_ability = decoration.abilities[0].ability
    matches = any(skill.ability is first_ability for skill in query.skills)
    return matches
