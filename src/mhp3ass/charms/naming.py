"""Charm names, value equality and hashes.

Ported from ``Charm::GetName``, ``EqualAbilities``, ``Charm::operator==``,
``Charm::GetHash`` and ``Charm::HashFunction`` (``legacy/Armor.cpp:216-341``)
and ``Utility::SlotString`` (``legacy/Common.cpp:62-67``).
"""

from __future__ import annotations

from mhp3ass.data.text import as_unsigned
from mhp3ass.model import Ability, AbilityPair, Charm


def slot_string(slots: int) -> str:
    """``Utility::SlotString``: ``---``, ``O--``, ``OO-``, and ``OOO`` for 3 or more."""
    slot_strings = {0: "---", 1: "O--", 2: "OO-"}
    slot_text = slot_strings.get(slots, "OOO")
    return slot_text


def charm_name(charm: Charm) -> str:
    """``Charm::GetName``, e.g. ``+4 Attack, -2 Sharpness OO-``.

    The first amount always gets a ``+``, even when negative. Duplicate
    removal in a search keys solutions on this name (quirk 4).
    """
    parts = []
    if charm.abilities:
        first = charm.abilities[0]
        parts.append(f"+{first.amount} {first.ability.name}")
        if len(charm.abilities) > 1:
            second = charm.abilities[1]
            separator = ", +" if second.amount > 0 else ", "
            parts.append(f"{separator}{second.amount} {second.ability.name} ")
        else:
            parts.append(" ")
    parts.append(slot_string(charm.num_slots))
    name = "".join(parts)
    return name


def equal_abilities(first: list[AbilityPair], second: list[AbilityPair]) -> bool:
    """``EqualAbilities`` (Armor.cpp:290-298).

    Compares ``l2[i]->amount != l2[i]->amount``, always false, so amounts are
    ignored (quirk 1). Only the abilities, in order, must match.
    """
    same = all(a.ability is b.ability for a, b in zip(first, second, strict=True))
    return same


def charms_equal(charm: Charm, other: Charm) -> bool:
    """``Charm::operator==`` (Armor.cpp:300-305): slots and abilities, not amounts (quirk 1)."""
    equal = (
        charm.num_slots == other.num_slots
        and len(charm.abilities) == len(other.abilities)
        and equal_abilities(charm.abilities, other.abilities)
    )
    return equal


def hash_function(
    num_slots: int,
    ability1: Ability | None,
    points1: int,
    ability2: Ability | None,
    points2: int,
    ability_count: int,
) -> int:
    """``Charm::HashFunction`` (Armor.cpp:331-341), as a C++ ``unsigned``.

    A missing ability takes index ``ability_count``
    (``Ability::static_abilities.Count``). Negative points wrap, as the
    original's ``unsigned`` arithmetic does.
    """
    index1 = ability1.static_index if ability1 is not None else ability_count
    index2 = ability2.static_index if ability2 is not None else ability_count
    points1_bits = points1 << 2 if ability1 is not None else 0
    points2_bits = (points2 + 12 if ability2 is not None else 12) << 6
    hashed = as_unsigned(num_slots + points1_bits + points2_bits + (index1 << 11) + (index2 << 18))
    return hashed


def charm_hash(charm: Charm, ability_count: int) -> int:
    """``Charm::GetHash`` (Armor.cpp:321-329): only the first two abilities count."""
    pairs = charm.abilities[:2]
    first = pairs[0] if pairs else None
    second = pairs[1] if len(pairs) > 1 else None
    hashed = hash_function(
        num_slots=charm.num_slots,
        ability1=first.ability if first is not None else None,
        points1=first.amount if first is not None else 0,
        ability2=second.ability if second is not None else None,
        points2=second.amount if second is not None else 0,
        ability_count=ability_count,
    )
    return hashed
