"""Comparing decorations.

Ported from ``Decoration::GetSkillAt``, ``NotWorse`` and
``Decoration::IsBetterThan`` (``legacy/Decoration.cpp:82-102``).
"""

from __future__ import annotations

from mhp3ass.data.text import as_unsigned
from mhp3ass.model import Ability, Decoration


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
