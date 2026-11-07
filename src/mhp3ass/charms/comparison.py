"""Comparing charms on the abilities a search cares about.

Ported from ``Charm::StrictlyBetterThan`` and ``Charm::BasicallyTheSameAs``
(``legacy/Armor.cpp:241-319``) and ``Form1::AddCharmToOptimalList``
(``legacy/Form1.h:1237-1249``). All three read each ability's ``relevant``
flag, which a search sets for the abilities its query asks for.
"""

from __future__ import annotations

from mhp3ass.charms.naming import equal_abilities
from mhp3ass.model import Charm


def strictly_better_than(charm: Charm, other: Charm) -> bool:
    """``Charm::StrictlyBetterThan`` (Armor.cpp:241-288).

    At least as many slots and at least the other's points in every relevant
    ability it has, and better somewhere: more points, a relevant ability the
    other lacks, or more slots.
    """
    if charm.num_slots < other.num_slots:
        return False
    better = False
    for theirs in other.abilities:
        if not theirs.ability.relevant:
            continue
        ours = next((pair for pair in charm.abilities if pair.ability is theirs.ability), None)
        if ours is None:
            if theirs.amount > 0:
                return False
            continue
        if ours.amount < theirs.amount:
            return False
        if ours.amount > theirs.amount:
            better = True
    if better:
        return True
    # So far equal: a relevant ability only this charm has makes it better.
    other_abilities = [pair.ability for pair in other.abilities]
    for ours in charm.abilities:
        if ours.ability.relevant and not any(
            ours.ability is ability for ability in other_abilities
        ):
            return True
    more_slots = charm.num_slots > other.num_slots
    return more_slots


def basically_the_same_as(charm: Charm, other: Charm) -> bool:
    """``Charm::BasicallyTheSameAs`` (Armor.cpp:307-319).

    Same slots and the same relevant abilities in order. Amounts are ignored
    (quirk 1), so charms differing only in points count as the same.
    """
    if charm.num_slots != other.num_slots:
        return False
    ours = [pair for pair in charm.abilities if pair.ability.relevant]
    theirs = [pair for pair in other.abilities if pair.ability.relevant]
    same = len(ours) == len(theirs) and equal_abilities(ours, theirs)
    return same


def add_charm_to_optimal_list(charms: list[Charm], new_charm: Charm) -> None:
    """``Form1::AddCharmToOptimalList`` (Form1.h:1237-1249), in place.

    Drops listed charms the new one strictly beats; skips the new one if a
    listed charm beats it or is basically the same, so the first of two
    "same" charms stays, whatever its points.
    """
    index = 0
    while index < len(charms):
        current = charms[index]
        if strictly_better_than(new_charm, current):
            del charms[index]
            continue
        if strictly_better_than(current, new_charm) or basically_the_same_as(current, new_charm):
            return
        index += 1
    charms.append(new_charm)
