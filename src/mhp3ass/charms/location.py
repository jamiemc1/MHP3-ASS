"""Which charm tables can produce a charm, and the charm tooltip's name parser.

Ported from ``FindCharm2`` (``legacy/CharmDatabase.cpp:1006-1099``) and the
parsing half of ``Utility::UpdateContextMenu( strip, String^ charm )``
(``legacy/Common.cpp:157-193``). The menu itself and the location cache
stay with the UI.

``FindCharm2`` counts, for every table and charm type, the entries of
``table_hashes[ table ][ type ][ num_slots ]`` that are at least as good as
the request. Those lists hold one entry per RNG seed, so a charm several
seeds produce counts several times. ``CharmLocationIndex`` groups the
entries by the abilities they hold, so a lookup only visits entries that can
match. The counts don't depend on visiting order, and the example is set
only when exactly one entry matched, so the result is the same as the
original's full scan.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from mhp3ass.charms.generation import CharmTables
from mhp3ass.charms.validity import DecodedCharm, decode_charm_hash
from mhp3ass.data import GameData
from mhp3ass.data.text import as_unsigned, to_uint32
from mhp3ass.model import Ability, AbilityPair, Charm


class CharmNameError(ValueError):
    """The tooltip's parser failed where .NET throws (``Substring``, ``ToUInt32``).

    ``dotnet_type`` names the exception the original throws there.
    """

    def __init__(self, message: str, dotnet_type: str):
        super().__init__(message)
        self.dotnet_type = dotnet_type


@dataclass(frozen=True)
class CharmLocationQuery:
    """``FindCharm2``'s arguments: ``points1`` is unsigned, ``points2`` signed."""

    ability1: Ability | None
    points1: int
    ability2: Ability | None
    points2: int
    num_slots: int


@dataclass
class CharmLocation:
    """``CharmLocationData`` (CharmDatabase.h:10-14)."""

    # counts[ table ][ type ]: type 0 mystery, 1 shining, 2 timeworn.
    counts: list[list[int]]
    example: Charm | None


@dataclass(frozen=True)
class _Entry:
    table: int
    charm_type: int
    hashed: int
    decoded: DecodedCharm


@dataclass
class _SlotEntries:
    """One slot count's table entries, by every ability index they hold."""

    by_ability: dict[int, list[_Entry]] = field(default_factory=dict)
    # Entries per (table, type): the no-ability lookup's counts.
    list_lengths: list[list[int]] = field(default_factory=list)


def _signed(value: int) -> int:
    """An ``unsigned`` read as ``int``: ``(int)points1``."""
    as_int = value - 2**32 if value >= 2**31 else value
    return as_int


@dataclass
class CharmLocationIndex:
    """``table_hashes`` grouped for ``FindCharm2``, built once per set of tables."""

    abilities: list[Ability]
    table_count: int
    type_count: int
    slots: list[_SlotEntries]

    @classmethod
    def build(cls, tables: CharmTables, abilities: list[Ability]) -> CharmLocationIndex:
        table_count = len(tables.table_hashes)
        type_count = len(tables.table_hashes[0])
        slot_count = len(tables.table_hashes[0][0])
        slots = [
            _SlotEntries(list_lengths=[[0] * type_count for _ in range(table_count)])
            for _ in range(slot_count)
        ]
        for table, by_type in enumerate(tables.table_hashes):
            for charm_type, by_slots in enumerate(by_type):
                for num_slots, hashes in enumerate(by_slots):
                    entries = slots[num_slots]
                    entries.list_lengths[table][charm_type] = len(hashes)
                    for hashed in hashes:
                        decoded = decode_charm_hash(hashed)
                        entry = _Entry(
                            table=table, charm_type=charm_type, hashed=hashed, decoded=decoded
                        )
                        held = {decoded.ability1_index, decoded.ability2_index}
                        for ability_index in held:
                            entries.by_ability.setdefault(ability_index, []).append(entry)
        index = cls(
            abilities=abilities, table_count=table_count, type_count=type_count, slots=slots
        )
        return index


def _matches_one_skill(decoded: DecodedCharm, ability1: int, points1: int) -> bool:
    """CharmDatabase.cpp:1055-1056: first skill (unsigned compare) or second (int compare)."""
    as_first = decoded.ability1_index == ability1 and decoded.points1 >= points1
    as_second = decoded.ability2_index == ability1 and decoded.points2 >= _signed(points1)
    return as_first or as_second


def _matches_two_skills(
    decoded: DecodedCharm, ability1: int, points1: int, ability2: int, points2: int
) -> bool:
    """CharmDatabase.cpp:1031-1032: the pair in either order, each at least as good."""
    same_order = (
        decoded.ability1_index == ability1
        and decoded.points1 >= points1
        and decoded.ability2_index == ability2
        and decoded.points2 >= points2
    )
    swapped = (
        decoded.ability1_index == ability2
        and decoded.points1 >= points2
        and decoded.ability2_index == ability1
        and decoded.points2 >= _signed(points1)
    )
    return same_order or swapped


def _example(hashed: int, abilities: list[Ability]) -> Charm:
    """CharmDatabase.cpp:1066-1074: the one match, with its second ability even at <= 0 points."""
    decoded = decode_charm_hash(hashed)
    example = Charm(num_slots=hashed & 0x3)
    if decoded.ability1_index != len(abilities):
        example.abilities.append(
            AbilityPair(ability=abilities[decoded.ability1_index], amount=decoded.points1)
        )
    if decoded.ability2_index != len(abilities):
        example.abilities.append(
            AbilityPair(ability=abilities[decoded.ability2_index], amount=decoded.points2)
        )
    return example


def find_charm_location(index: CharmLocationIndex, query: CharmLocationQuery) -> CharmLocation:
    """``FindCharm2``: per table and charm type, how many entries are at least this good."""
    entries = index.slots[query.num_slots]
    if query.ability1 is None:
        counts = [list(row) for row in entries.list_lengths]
        location = CharmLocation(counts=counts, example=None)
        return location

    counts = [[0] * index.type_count for _ in range(index.table_count)]
    points1 = as_unsigned(query.points1)
    ability1 = query.ability1.static_index
    # CharmDatabase.cpp:1044-1045: written for an unnamed Auto-Guard ability.
    if (
        query.ability2 is None
        and query.num_slots == 0
        and query.ability1.name == ""
        and points1 == 10
    ):
        location = CharmLocation(counts=counts, example=None)
        return location

    matched = []
    for entry in entries.by_ability.get(ability1, []):
        if query.ability2 is None:
            is_match = _matches_one_skill(entry.decoded, ability1=ability1, points1=points1)
        else:
            is_match = _matches_two_skills(
                entry.decoded,
                ability1=ability1,
                points1=points1,
                ability2=query.ability2.static_index,
                points2=query.points2,
            )
        if is_match:
            counts[entry.table][entry.charm_type] += 1
            matched.append(entry)
    example = _example(matched[0].hashed, index.abilities) if len(matched) == 1 else None
    location = CharmLocation(counts=counts, example=example)
    return location


def _substring(text: str, start: int, length: int) -> str:
    """``String::Substring( start, length )``, which throws where a slice would clip."""
    if start < 0 or length < 0 or start + length > len(text):
        raise CharmNameError(
            f"Substring({start}, {length}) is out of range for {text!r}",
            dotnet_type="ArgumentOutOfRangeException",
        )
    part = text[start : start + length]
    return part


def _parse_points(text: str) -> int:
    try:
        points = to_uint32(text)
    except OverflowError as error:
        raise CharmNameError(str(error), dotnet_type="OverflowException") from error
    except ValueError as error:
        raise CharmNameError(str(error), dotnet_type="FormatException") from error
    return points


def parse_charm_name(name: str, game: GameData) -> CharmLocationQuery:
    """What ``UpdateContextMenu`` (Common.cpp:164-189) passes ``FindCharm2`` for a charm name.

    Quirk 7: for a two-skill name the first amount is parsed into a shadowing
    local (``:182``), so ``points1`` stays 0. The second amount skips its sign
    (``Substring( comma + 3, … )``), so ``-3`` reads as 3.
    """
    num_slots = _substring(name, len(name) - 3, 3).count("O")
    points1 = 0
    points2 = 0
    ability1 = None
    ability2 = None
    if _substring(name, 0, 1) != "O":
        comma = name.find(",")
        if comma == -1:
            space = name.find(" ")
            points1 = _parse_points(_substring(name, 1, space - 1))
            ability1 = game.ability_map.get(_substring(name, space + 1, len(name) - space - 5))
        else:
            space1 = name.find(" ")
            # Parsed, so it can still throw, but never used (quirk 7).
            _parse_points(_substring(name, 1, space1 - 1))
            ability1 = game.ability_map.get(_substring(name, space1 + 1, comma - space1 - 1))
            if comma + 2 > len(name):
                raise CharmNameError(
                    f"IndexOf start {comma + 2} is past the end of {name!r}",
                    dotnet_type="ArgumentOutOfRangeException",
                )
            space2 = name.find(" ", comma + 2)
            points2 = _parse_points(_substring(name, comma + 3, space2 - comma - 3))
            ability2 = game.ability_map.get(_substring(name, space2 + 1, len(name) - space2 - 5))
    query = CharmLocationQuery(
        ability1=ability1,
        points1=points1,
        ability2=ability2,
        points2=points2,
        num_slots=num_slots,
    )
    return query
