"""Whether a user's charm is one the game can produce.

Ported from ``CharmExists`` and ``CharmIsIllegal``
(``legacy/CharmDatabase.cpp:1001-1004``, ``:1101-1164``), with the hash
decoding of its ``UnhashCharm`` macro (``:1012-1017``).

``CharmIsIllegal`` scans every generated hash for the charm's slot count
until one matches. Only whether a match exists matters, so this indexes the
distinct decoded hashes once per slot count and applies the same match
conditions to the index.
"""

from __future__ import annotations

import bisect
from dataclasses import dataclass, field

from mhp3ass.charms.generation import CharmTables
from mhp3ass.charms.naming import charm_hash
from mhp3ass.data import GameData
from mhp3ass.data.text import as_unsigned
from mhp3ass.model import AbilityPair, Charm


@dataclass(frozen=True)
class DecodedCharm:
    """``UnhashCharm``'s fields, plus the slot count in the hash's low bits
    (``Charm::HashFunction`` adds it unshifted), which ``UnhashCharm`` doesn't read."""

    ability1_index: int
    ability2_index: int
    points1: int
    points2: int
    num_slots: int


def decode_charm_hash(hashed: int) -> DecodedCharm:
    decoded = DecodedCharm(
        ability1_index=(hashed >> 11) & 0x7F,
        ability2_index=(hashed >> 18) & 0x7F,
        points1=(hashed >> 2) & 0xF,
        points2=((hashed >> 6) & 0x1F) - 12,
        num_slots=hashed & 3,
    )
    return decoded


def generated_charm(hashed: int, game: GameData) -> Charm:
    """The charm a generated hash stands for, with ``game``'s abilities.

    An ability index equal to the ability count means no ability
    (``Charm::HashFunction``). A second ability is kept with whatever points
    the hash holds, zero or negative included, so the charm hashes back to
    ``hashed``.
    """
    decoded = decode_charm_hash(hashed)
    ability_count = len(game.abilities)
    pairs = []
    if decoded.ability1_index != ability_count:
        pairs.append(
            AbilityPair(ability=game.abilities[decoded.ability1_index], amount=decoded.points1)
        )
    if decoded.ability2_index != ability_count:
        pairs.append(
            AbilityPair(ability=game.abilities[decoded.ability2_index], amount=decoded.points2)
        )
    charm = Charm(num_slots=decoded.num_slots, abilities=pairs)
    return charm


@dataclass
class _SlotIndex:
    """The generated charms for one slot count, by the abilities they hold."""

    # (ability 1, ability 2) -> every distinct (points 1, points 2) seen.
    points_by_pair: dict[tuple[int, int], set[tuple[int, int]]] = field(default_factory=dict)
    # Highest first-skill points per first ability, and second-skill points per second ability.
    best_first: dict[int, int] = field(default_factory=dict)
    best_second: dict[int, int] = field(default_factory=dict)
    has_charms: bool = False


@dataclass
class CharmValidity:
    """``CharmExists`` and ``CharmIsIllegal`` over one set of generated tables."""

    charm_hashes: list[int]
    ability_count: int
    slots: list[_SlotIndex]

    def exists(self, charm: Charm) -> bool:
        """``CharmExists``: its exact hash was generated (binary search, as the original)."""
        hashed = charm_hash(charm, self.ability_count)
        position = bisect.bisect_left(self.charm_hashes, hashed)
        found = position < len(self.charm_hashes) and self.charm_hashes[position] == hashed
        return found

    def is_illegal(self, charm: Charm) -> bool:
        """``CharmIsIllegal``: no generated charm with the same slot count is at least as good.

        The first skill's points are held as ``unsigned``, so a negative
        amount wraps: it can't match as a first skill, but compares as
        itself (cast back to ``int``) against a second skill. A charm with
        more than two abilities is checked on its first alone. Four or more
        slots raise ``IndexError``, as the original indexes past its tables.
        """
        if not 0 <= charm.num_slots < len(self.slots):
            raise IndexError(f"no charm table for {charm.num_slots} slots")
        index = self.slots[charm.num_slots]
        if not charm.abilities:
            return not index.has_charms
        first = charm.abilities[0]
        ability1 = first.ability.static_index
        points1_unsigned = as_unsigned(first.amount)
        points1_signed = first.amount
        if len(charm.abilities) == 2:
            second = charm.abilities[1]
            ability2 = second.ability.static_index
            points2 = second.amount
            same_order = index.points_by_pair.get((ability1, ability2), set())
            swapped = index.points_by_pair.get((ability2, ability1), set())
            legal = any(p1 >= points1_unsigned and p2 >= points2 for p1, p2 in same_order) or any(
                p1 >= points2 and p2 >= points1_signed for p1, p2 in swapped
            )
            return not legal
        as_first = index.best_first.get(ability1)
        as_second = index.best_second.get(ability1)
        legal = (as_first is not None and as_first >= points1_unsigned) or (
            as_second is not None and as_second >= points1_signed
        )
        return not legal


def build_charm_validity(tables: CharmTables, ability_count: int) -> CharmValidity:
    """Index ``table_hashes`` per slot count, across every table and charm type."""
    slots = []
    for slot_count in range(4):
        index = _SlotIndex()
        distinct = {
            hashed
            for per_table in tables.table_hashes
            for per_type in per_table
            for hashed in per_type[slot_count]
        }
        index.has_charms = bool(distinct)
        for hashed in distinct:
            decoded = decode_charm_hash(hashed)
            pair = (decoded.ability1_index, decoded.ability2_index)
            index.points_by_pair.setdefault(pair, set()).add((decoded.points1, decoded.points2))
            best_first = index.best_first.get(decoded.ability1_index)
            if best_first is None or decoded.points1 > best_first:
                index.best_first[decoded.ability1_index] = decoded.points1
            best_second = index.best_second.get(decoded.ability2_index)
            if best_second is None or decoded.points2 > best_second:
                index.best_second[decoded.ability2_index] = decoded.points2
        slots.append(index)
    validity = CharmValidity(
        charm_hashes=tables.charm_hashes, ability_count=ability_count, slots=slots
    )
    return validity
