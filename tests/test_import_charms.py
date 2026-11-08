"""Charm import from a decrypted save: records on synthetic bytes, your save against the
harness's decrypt-save dump (SaveDump.cpp)."""

from __future__ import annotations

from typing import Any

import pytest

from mhp3ass.charms.naming import charm_name
from mhp3ass.charms.validity import CharmValidity
from mhp3ass.data import GameData
from mhp3ass.model import Charm
from mhp3ass.savefile.import_charms import (
    ImportedCharacter,
    SaveFileError,
    decode_charm_record,
    load_character,
)


def _charm_fields(charm: Charm) -> dict[str, Any]:
    """``Fixtures::WriteCharmFields`` (harness/src/Fixtures.h:44-50)."""
    fields = {
        "name": charm_name(charm),
        "num_slots": charm.num_slots,
        "abilities": [
            {"ability": pair.ability.static_index, "amount": pair.amount}
            for pair in charm.abilities
        ],
    }
    return fields


def _pairs(charm: Charm, game: GameData) -> list[tuple[int, int]]:
    """Each skill as (index in ordered_abilities, points)."""
    pairs = [(game.ordered_abilities.index(pair.ability), pair.amount) for pair in charm.abilities]
    return pairs


def _character_shape(character: ImportedCharacter | None, slot: int) -> dict[str, Any]:
    """The golden's per-character fields, without the Select Best ticks."""
    charms = [] if character is None else character.charms
    shaped = {
        "slot": slot,
        "present": character is not None,
        "name": None if character is None else character.name,
        "charms": [
            {
                "raw": imported.raw.hex(),
                **_charm_fields(imported.charm),
                "hacked": imported.charm.hacked,
            }
            for imported in charms
        ],
    }
    return shaped


def test_every_character_matches_golden(
    save_game_layer: bytes, save_golden: Any, teamhgg_game: GameData, validity: CharmValidity
):
    ours = [
        _character_shape(load_character(save_game_layer, slot, teamhgg_game, validity), slot)
        for slot in range(3)
    ]
    expected = [
        {
            "slot": character["slot"],
            "present": character["present"],
            "name": character["name"],
            "charms": [
                {key: value for key, value in charm.items() if key != "select_best"}
                for charm in character["charms"]
            ],
        }
        for character in save_golden["characters"]
    ]

    assert ours == expected


@pytest.mark.parametrize(
    ("raw", "slots", "pairs"),
    [
        # Skill 1 (first ordered ability) nibble 3 -> +5; skill 2 = 2 (bit 7 of byte 4
        # clear, low 6 bits of byte 5 = 1), sign flag set, value 4 -> +6; 2 slots.
        ("016530900181", 2, [(0, 5), (1, 6)]),
        # No first skill; skill 2 = 3 (bit 7 of byte 4 set, byte 5 low bits 1), sign
        # flag clear, value 1 -> 1 - 16 + 2 = -13. It becomes the charm's only skill.
        ("016500048001", 0, [(2, -13)]),
        # Nibbles 14 and 15 wrap: (14 + 2) % 16 = 0 and (15 + 2) % 16 = 1 points.
        ("0165e0000500", 0, [(4, 0)]),
        ("0165f00005c0", 3, [(4, 1)]),
        # No skills at all: a bare slotted charm.
        ("016500000040", 1, []),
    ],
)
def test_decode_charm_record(raw: str, slots: int, pairs: list, teamhgg_game: GameData):
    charm = decode_charm_record(bytes.fromhex(raw), teamhgg_game)

    assert (charm.num_slots, _pairs(charm, teamhgg_game)) == (slots, pairs)


def test_a_skill_past_the_ordered_list_is_rejected(teamhgg_game: GameData):
    """The original's ordered_abilities[ 126 ] throws (ImportCharms.h:406)."""
    with pytest.raises(SaveFileError, match="names skill 127,"):
        decode_charm_record(bytes.fromhex("016500007f00"), teamhgg_game)


def _save_with(slot_bytes: dict[int, bytes], records: dict[int, list[bytes]]) -> bytes:
    """A decrypted-save-sized buffer with name bytes and equipment records per slot."""
    data = bytearray(0x121000)
    for slot, name in slot_bytes.items():
        offset = 0x800 + slot * 0x60000
        data[offset : offset + len(name)] = name
        for index, record in enumerate(records.get(slot, [])):
            start = offset + 0x168 + index * 12
            data[start : start + len(record)] = record
    return bytes(data)


def test_empty_slot_has_no_character(teamhgg_game: GameData, validity: CharmValidity):
    data = _save_with({}, {})

    assert load_character(data, 0, teamhgg_game, validity) is None


def test_character_without_charms_has_no_name(teamhgg_game: GameData, validity: CharmValidity):
    data = _save_with({1: "Ann".encode("utf-16-le")}, {})

    character = load_character(data, 1, teamhgg_game, validity)

    assert character is not None
    assert (character.name, character.charms, character.cheats) == (None, [], False)


def test_charms_are_read_in_record_order_skipping_other_equipment(
    teamhgg_game: GameData, validity: CharmValidity
):
    """The name is scanned to the first zero byte, so "Ann" in UTF-16LE (41 00 ...)
    stops after one byte and decodes to U+FFFD, as in the original."""
    records = [
        bytes.fromhex("016500000040"),
        bytes.fromhex("026500000040"),
        bytes.fromhex("0165e0000500"),
    ]
    data = _save_with({2: "Ann".encode("utf-16-le")}, {2: records})

    character = load_character(data, 2, teamhgg_game, validity)

    assert character is not None
    assert character.name == "�"
    assert [imported.raw.hex() for imported in character.charms] == ["016500000040", "0165e0000500"]


def test_a_charm_the_game_cannot_make_is_hacked(teamhgg_game: GameData, validity: CharmValidity):
    # First ordered ability +13 (nibble 11) with 3 slots: beyond any generated charm.
    data = _save_with({0: b"A"}, {0: [bytes.fromhex("0165b00001c0")]})

    character = load_character(data, 0, teamhgg_game, validity)

    assert character is not None
    assert [imported.charm.hacked for imported in character.charms] == [True]
    assert character.cheats is True
