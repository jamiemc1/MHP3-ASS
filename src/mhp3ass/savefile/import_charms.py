"""Reading charms from a decrypted save, as the import dialog does.

Ported from ``ImportCharms::LoadCharms( data, char_num )``,
``SelectDefault`` and ``AddCharms`` (``legacy/ImportCharms.h:278-436``).
The dialog's list view and radio buttons become plain data; the TUI shows
them.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from mhp3ass.charms.comparison import strictly_better_than
from mhp3ass.charms.naming import charms_equal
from mhp3ass.charms.validity import CharmValidity
from mhp3ass.data import GameData
from mhp3ass.model import AbilityPair, Charm
from mhp3ass.savefile.game_layer import decrypt_game_layer
from mhp3ass.savefile.system_layer import decrypt_system_layer


class SaveFileError(ValueError):
    """A save the original's import would fail on."""


@dataclass(eq=False)
class ImportedCharm:
    """A charm and the six record bytes it was decoded from."""

    charm: Charm
    raw: bytes


@dataclass(eq=False)
class ImportedCharacter:
    """One of the save's three character slots that holds a character."""

    slot: int
    # The radio button's text: the character's name, or None if it has no charms
    # (the dialog shows "No charms found" and disables the button).
    name: str | None
    charms: list[ImportedCharm] = field(default_factory=list)
    # Some charm is neither generated nor legal: the dialog warns once per import.
    cheats: bool = False


def _charm_offset(slot: int) -> int:
    """Where a character's data starts in the decrypted save (ImportCharms.h:372)."""
    offset = 0x800 + slot * 0x60000
    return offset


def decode_charm_record(raw: bytes, game: GameData) -> Charm:
    """A charm from the first six bytes of an equipment record (ImportCharms.h:398-408).

    Skill indices are 1-based into ``ordered_abilities``, 0 for none. The
    first skill's points are stored minus 2 in a nibble, so 14 and 15 decode
    to 0 and 1. The second's are a 4-bit value with a sign flag (clear for
    negative, subtracting 16), plus 2. A charm with no first skill and a
    second one keeps that skill first, with its possibly negative points.
    """
    amount1 = ((raw[2] >> 4) + 2) % 16
    amount2 = ((raw[3] & 0x3C) >> 2) - (0 if raw[3] & 0x80 else 16) + 2
    ability1 = raw[4] & 0x7F
    ability2 = (1 if raw[4] & 0x80 else 0) + ((raw[5] & 0x3F) << 1)
    charm = Charm(num_slots=raw[5] >> 6)
    for ability_index, amount in ((ability1, amount1), (ability2, amount2)):
        if not ability_index:
            continue
        if ability_index > len(game.ordered_abilities):
            raise SaveFileError(
                f"charm record {raw.hex()} names skill {ability_index}, "
                f"past the {len(game.ordered_abilities)} the game has"
            )
        ability = game.ordered_abilities[ability_index - 1]
        charm.abilities.append(AbilityPair(ability=ability, amount=amount))
    return charm


def _name_end(data: bytes, offset: int) -> int:
    """The first zero byte from ``offset`` (ImportCharms.h:378-380), scanned byte by byte
    even though the name is UTF-16."""
    if 0 not in data[offset:]:
        raise SaveFileError(f"the character name at {offset:#x} has no terminating zero byte")
    name_end = data.index(0, offset)
    return name_end


def load_character(
    data: bytes, slot: int, game: GameData, validity: CharmValidity
) -> ImportedCharacter | None:
    """``LoadCharms( data, char_num )`` on the decrypted save: the slot's charms in
    record order, or None for an empty slot.

    Each of the 1,000 equipment records is a charm if it starts ``01 65``. A
    charm the generator can't make and the cheat check rejects is ``hacked``.
    """
    offset = _charm_offset(slot)
    if not data[offset]:
        return None
    name_end = _name_end(data, offset)
    character = ImportedCharacter(slot=slot, name=None)
    for record in range(1000):
        start = offset + 0x168 + record * 12
        raw = bytes(data[start : start + 6])
        if raw[0] != 1 or raw[1] != 0x65:
            continue
        charm = decode_charm_record(raw, game)
        if not validity.exists(charm) and validity.is_illegal(charm):
            charm.hacked = True
            character.cheats = True
        character.charms.append(ImportedCharm(charm=charm, raw=raw))
    if character.charms:
        # Encoding::GetString on the scanned bytes (ImportCharms.h:425-426): a trailing
        # odd byte decodes to U+FFFD.
        character.name = data[offset:name_end].decode("utf-16-le", errors="replace")
    return character


def select_best(charms: list[Charm], game: GameData) -> list[bool]:
    """``SelectDefault`` (ImportCharms.h:337-367): which charms the dialog ticks.

    Marks every ability relevant first and leaves them so, as the original
    does (the next search resets them). Each charm that isn't hacked is
    ticked, then compared with every earlier ticked one: it unticks one it
    is strictly better than, and is unticked by one strictly better than it
    or value-equal to it (``operator==``, quirks 1 and 2). An unticked charm
    keeps comparing, so the result depends on order.
    """
    for ability in game.abilities:
        ability.relevant = True
    ticked = [False] * len(charms)
    for index, charm in enumerate(charms):
        if charm.hacked:
            continue
        ticked[index] = True
        for earlier in range(index):
            if not ticked[earlier]:
                continue
            if strictly_better_than(charm, charms[earlier]):
                ticked[earlier] = False
            elif strictly_better_than(charms[earlier], charm) or charms_equal(
                charm, charms[earlier]
            ):
                ticked[index] = False
    return ticked


def import_charms(charms: list[Charm], ticked: list[bool]) -> list[Charm]:
    """``AddCharms`` for the selected character (ImportCharms.h:278-292): the ticked
    charms that aren't hacked, marked ``custom``, in order.

    They replace the my-charms list rather than adding to it (quirk 3).
    """
    if len(ticked) != len(charms):
        raise ValueError(f"{len(ticked)} ticks for {len(charms)} charms")
    imported = []
    for charm, is_ticked in zip(charms, ticked, strict=True):
        if is_ticked and not charm.hacked:
            charm.custom = True
            imported.append(charm)
    return imported


class NotASaveFileError(SaveFileError):
    """A file of the wrong size: the import button refuses it (Form1.h:2326-2332)."""


@dataclass(eq=False)
class SaveImport:
    """What the import dialog opens with: the three character slots."""

    characters: list[ImportedCharacter | None]
    # The slot the dialog selects first: the first with charms (ImportCharms.h:448-455).
    default_slot: int | None
    # The dialog shows its "cheater" message box (ImportCharms.h:445-446).
    cheats: bool


def read_save(data: bytes, game: GameData, validity: CharmValidity) -> SaveImport:
    """The import button and ``LoadCharms( data )`` (Form1.h:2326-2335,
    ImportCharms.h:438-456): check the size, decrypt both layers, load every slot."""
    if len(data) != 0x121010:
        raise NotASaveFileError(
            f"an MHP3rd save file is {0x121010:,} bytes, this one is {len(data):,}"
        )
    decrypted = decrypt_game_layer(decrypt_system_layer(data))
    characters = [load_character(decrypted, slot, game, validity) for slot in range(3)]
    default_slot = next(
        (slot for slot, character in enumerate(characters) if character and character.charms),
        None,
    )
    cheats = any(character.cheats for character in characters if character is not None)
    save_import = SaveImport(characters=characters, default_slot=default_slot, cheats=cheats)
    return save_import


def default_import(save_import: SaveImport, game: GameData) -> list[Charm]:
    """The charms pressing Import straight away adds: the default character's, as
    Select Best ticks them. Empty when no character has charms."""
    if save_import.default_slot is None:
        return []
    character = save_import.characters[save_import.default_slot]
    if character is None:
        raise ValueError(f"default slot {save_import.default_slot} has no character")
    charms = [imported.charm for imported in character.charms]
    imported = import_charms(charms, select_best(charms, game))
    return imported
