"""Charm import from a decrypted save: records on synthetic bytes, your save against the
harness's decrypt-save dump (SaveDump.cpp)."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from mhp3ass.charms.my_charms import my_charms_text, save_my_charms
from mhp3ass.charms.naming import charm_name
from mhp3ass.charms.validity import CharmValidity
from mhp3ass.data import GameData
from mhp3ass.model import AbilityPair, Charm
from mhp3ass.savefile.import_charms import (
    ImportedCharacter,
    ImportedCharm,
    NotASaveFileError,
    SaveFileError,
    SaveImport,
    decode_charm_record,
    default_import,
    import_charms,
    load_character,
    read_save,
    select_best,
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


def test_a_legal_charm_the_generator_never_made_is_not_hacked(
    teamhgg_game: GameData, validity: CharmValidity
):
    """Hacked needs both !CharmExists and CharmIsIllegal (ImportCharms.h:409). Poison +6
    with no slots (second ordered ability, nibble 4) is never generated, but a
    generated charm is at least as good, so it's legal."""
    charm = decode_charm_record(bytes.fromhex("016540000200"), teamhgg_game)
    assert (validity.exists(charm), validity.is_illegal(charm)) == (False, False)
    data = _save_with({0: b"A"}, {0: [bytes.fromhex("016540000200")]})

    character = load_character(data, 0, teamhgg_game, validity)

    assert character is not None
    assert [imported.charm.hacked for imported in character.charms] == [False]
    assert character.cheats is False


def _personal_characters(
    save_game_layer: bytes, game: GameData, validity: CharmValidity
) -> list[ImportedCharacter | None]:
    characters = [load_character(save_game_layer, slot, game, validity) for slot in range(3)]
    return characters


def test_select_best_matches_golden_for_every_character(
    save_game_layer: bytes,
    save_golden: Any,
    load_teamhgg_game: Callable[[], GameData],
    validity: CharmValidity,
):
    """On a fresh game: Select Best marks every ability relevant."""
    game = load_teamhgg_game()
    ours = [
        []
        if character is None
        else select_best([imported.charm for imported in character.charms], game)
        for character in _personal_characters(save_game_layer, game, validity)
    ]
    expected = [
        [charm["select_best"] for charm in character["charms"]]
        for character in save_golden["characters"]
    ]

    assert ours == expected


def test_importing_the_default_selection_writes_the_guis_file(
    save_game_layer: bytes,
    save_golden: Any,
    gui_imported_mycharms: list[str],
    load_teamhgg_game: Callable[[], GameData],
    validity: CharmValidity,
):
    """The dialog opens on the first character with charms, with Select Best's ticks."""
    game = load_teamhgg_game()
    characters = _personal_characters(save_game_layer, game, validity)
    default = next(character for character in characters if character and character.charms)
    charms = [imported.charm for imported in default.charms]

    imported = import_charms(charms, select_best(charms, game))
    lines = my_charms_text(imported).split("\r\n")[:-1]

    assert lines == save_golden["mycharms_txt"]
    assert lines == gui_imported_mycharms


def _charm(game: GameData, slots: int, *skills: tuple[int, int], hacked: bool = False) -> Charm:
    """A charm with skills given as (ordered ability index, points)."""
    pairs = [
        AbilityPair(ability=game.ordered_abilities[index], amount=points)
        for index, points in skills
    ]
    charm = Charm(num_slots=slots, abilities=pairs, hacked=hacked)
    return charm


def test_select_best_never_ticks_a_hacked_charm(load_teamhgg_game: Callable[[], GameData]):
    game = load_teamhgg_game()
    charms = [_charm(game, 3, (0, 13), hacked=True), _charm(game, 0, (0, 1))]

    assert select_best(charms, game) == [False, True]


def test_a_hacked_charm_does_not_untick_a_weaker_earlier_one(
    load_teamhgg_game: Callable[[], GameData],
):
    """A hacked charm skips the comparisons too (ImportCharms.h:347-351)."""
    game = load_teamhgg_game()
    charms = [_charm(game, 0, (0, 1)), _charm(game, 3, (0, 13), hacked=True)]

    assert select_best(charms, game) == [True, False]


def test_an_unticked_charm_keeps_unticking_earlier_ones(
    load_teamhgg_game: Callable[[], GameData],
):
    """StrictlyBetterThan isn't transitive: a negative skill the other charm lacks is
    skipped. X beats Z, Z beats Y (Y's only skill is negative), but X doesn't beat Y
    (-4 < -2). Z is unticked by X and still unticks Y (ImportCharms.h:354-364)."""
    game = load_teamhgg_game()
    first, second = 0, 1
    x = _charm(game, 0, (first, 1), (second, -4))
    y = _charm(game, 0, (second, -2))
    z = _charm(game, 0, (first, 1))

    assert select_best([x, y, z], game) == [True, False, False]


def test_select_best_keeps_the_first_of_value_equal_charms(
    load_teamhgg_game: Callable[[], GameData],
):
    """Neither charm is strictly better (each has more of one skill), but operator==
    ignores amounts (quirk 1), so the second counts as a duplicate of the first."""
    game = load_teamhgg_game()
    charms = [_charm(game, 1, (0, 4), (1, 1)), _charm(game, 1, (0, 2), (1, 3))]

    assert select_best(charms, game) == [True, False]
    assert select_best(list(reversed(charms)), game) == [True, False]


def test_a_later_strictly_better_charm_unticks_an_earlier_one(
    load_teamhgg_game: Callable[[], GameData],
):
    game = load_teamhgg_game()
    charms = [_charm(game, 0, (0, 4)), _charm(game, 1, (0, 4))]

    assert select_best(charms, game) == [False, True]


def test_select_best_marks_every_ability_relevant(load_teamhgg_game: Callable[[], GameData]):
    game = load_teamhgg_game()

    select_best([], game)

    assert all(ability.relevant for ability in game.abilities)


def test_import_skips_hacked_and_unticked_charms_and_marks_the_rest_custom(
    load_teamhgg_game: Callable[[], GameData],
):
    """AddCharms checks hacked itself: the dialog lets a hacked charm be ticked (quirk
    candidate: listView1_ItemChecked is never wired up)."""
    game = load_teamhgg_game()
    kept = _charm(game, 1, (0, 4))
    unticked = _charm(game, 0, (1, 3))
    hacked = _charm(game, 3, (0, 13), hacked=True)

    imported = import_charms([kept, unticked, hacked], [True, False, True])

    assert imported == [kept]
    assert (kept.custom, unticked.custom, hacked.custom) == (True, False, False)


def test_importing_your_save_writes_the_guis_file(
    save_bytes: bytes,
    save_golden: Any,
    gui_imported_mycharms: list[str],
    load_teamhgg_game: Callable[[], GameData],
    validity: CharmValidity,
    tmp_path: Path,
):
    """Save file in, mycharms.txt out, as pressing Import straight away does."""
    game = load_teamhgg_game()
    save_import = read_save(save_bytes, game, validity)
    output = tmp_path / "mycharms.txt"

    save_my_charms(output, default_import(save_import, game))

    expected_default = next(
        character["slot"]
        for character in save_golden["characters"]
        if character["default_selection"]
    )
    expected_cheats = any(
        charm["hacked"] for character in save_golden["characters"] for charm in character["charms"]
    )
    default_character = save_import.default_character
    assert default_character is not None
    assert (default_character.slot, save_import.cheats) == (expected_default, expected_cheats)
    # Bytes, not read_text: the file must use the original's CRLF line endings.
    assert output.read_bytes().decode("utf-8").split("\r\n")[:-1] == gui_imported_mycharms


@pytest.mark.parametrize("length", [0, 0x121000, 0x121011])
def test_a_file_of_any_other_size_is_not_a_save(
    length: int, teamhgg_game: GameData, validity: CharmValidity
):
    with pytest.raises(NotASaveFileError, match="1,183,760 bytes"):
        read_save(bytes(length), teamhgg_game, validity)


def test_a_save_without_charms_imports_nothing(load_teamhgg_game: Callable[[], GameData]):
    game = load_teamhgg_game()
    save_import = SaveImport(characters=[None, ImportedCharacter(slot=1, name=None), None])

    assert save_import.default_character is None
    assert default_import(save_import, game) == []


def test_the_default_character_is_the_first_with_charms(load_teamhgg_game: Callable[[], GameData]):
    """An empty slot and a character without charms are both passed over
    (ImportCharms.h:417-424, :448-455); cheats comes from any slot."""
    game = load_teamhgg_game()
    without_charms = ImportedCharacter(slot=1, name=None, cheats=False)
    with_charms = ImportedCharacter(
        slot=2,
        name="B",
        charms=[ImportedCharm(charm=_charm(game, 0, (0, 1)), raw=bytes(6))],
        cheats=True,
    )
    save_import = SaveImport(characters=[None, without_charms, with_charms])

    assert save_import.default_character is with_charms
    assert save_import.cheats is True
