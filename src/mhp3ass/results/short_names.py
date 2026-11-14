"""Shorter armour and charm names for the results table's cells.

Not a port: the original lists every result in full. The table shortens
two of its columns (the inspector keeps the full names):

1. **Armour:** each piece drops the words that name its piece type
   (``Barroth Tasset S`` → ``Barroth S``). The words come from each
   language's own armour names, not a maintained list: a word is a piece
   word for a slot when it is in a good share of that slot's names and
   almost none of the other slots' (``piece_words``). Pieces that would
   shorten alike (``Barroth Helm`` and ``Barroth Cap``) keep their full names.
2. **Charm:** ``+N <short ability>`` for each ability, then the slots in
   brackets (``+4 Atk +3 Shp (1)``). Each ability's short name is the
   shortest prefix of at least 3 characters that no other ability in the
   language starts with (``ability_abbreviations``).

Japanese names have no spaces or hyphens to split at, so their pieces keep
their full names; the table's column fitting cuts them if needed.
"""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from mhp3ass.charms.naming import slot_string
from mhp3ass.data import GameData
from mhp3ass.model import Armor, ArmorType, Charm, HunterType

# Words are split at spaces and hyphens (German names join with hyphens).
_SEPARATORS = re.compile(r"([\s\-]+)")


def _words(name: str) -> list[str]:
    words = [part for part in _SEPARATORS.split(name)[::2] if part]
    return words


def piece_words(
    names_by_slot: Mapping[ArmorType, Sequence[str]],
    min_share: float = 0.05,
    max_elsewhere: float = 0.01,
) -> dict[ArmorType, frozenset[str]]:
    """Each slot's piece words: those in at least ``min_share`` of its names
    and at most ``max_elsewhere`` of the other slots' names. Monster and
    material words (``Barroth``, ``Leather``) are in every slot, so they
    stay; ``S`` and ``U`` too."""
    counts = {
        slot: Counter(word for name in names for word in set(_words(name)))
        for slot, names in names_by_slot.items()
    }
    total = sum(len(names) for names in names_by_slot.values())
    words_by_slot = {}
    for slot, slot_counts in counts.items():
        slot_total = len(names_by_slot[slot])
        others_total = total - slot_total
        chosen = set()
        for word, count in slot_counts.items():
            elsewhere = sum(counts[other][word] for other in counts if other is not slot)
            share_elsewhere = elsewhere / others_total if others_total else 0.0
            if count / slot_total >= min_share and share_elsewhere <= max_elsewhere:
                chosen.add(word)
        words_by_slot[slot] = frozenset(chosen)
    return words_by_slot


def short_armor_name(name: str, words: frozenset[str]) -> str:
    """``name`` without the piece ``words``, keeping the spaces and hyphens
    between the words that stay; the full name if no word would stay."""
    parts = _SEPARATORS.split(name)
    kept: list[str] = []
    separator = ""
    for index, part in enumerate(parts):
        # split with a group alternates words (even) and their separators (odd).
        if index % 2 == 1:
            separator = part
            continue
        if part == "" or part in words:
            continue
        kept.append(separator + part if kept else part)
        separator = ""
    short = "".join(kept)
    return short if short else name


def short_armor_names(armors: Sequence[Armor], words: frozenset[str]) -> dict[str, str]:
    """Each of one slot's ``armors`` by name, shortened (``short_armor_name``),
    except where two pieces one search can return would shorten alike
    (``Barroth Helm`` and ``Barroth Cap``, or a German ``-ArmschienenS`` and
    its low-rank piece): those keep their full names, so no two pieces in a
    results table share a cell. A search is for one hunter type, so a
    blademaster's piece and a gunner's may share a short name."""
    shorts = {armor.name: short_armor_name(armor.name, words) for armor in armors}
    clashing: set[str] = set()
    for hunter_type in (HunterType.BLADEMASTER, HunterType.GUNNER):
        searchable = {
            armor.name
            for armor in armors
            if armor.hunter_type in (hunter_type, HunterType.BOTH_TYPES)
        }
        counts = Counter(shorts[name] for name in searchable)
        clashing.update(name for name in searchable if counts[shorts[name]] > 1)
    distinct = {name: name if name in clashing else short for name, short in shorts.items()}
    return distinct


def ability_abbreviations(names: Sequence[str], minimum: int = 3) -> dict[str, str]:
    """Each name's shortest prefix of at least ``minimum`` characters that no
    other name starts with, ending in a letter or digit (not a space, hyphen,
    dot or apostrophe); a name that is the start of another (or shorter than
    ``minimum``) keeps its full name."""
    distinct = set(names)
    abbreviations = {}
    for name in distinct:
        others = [other for other in distinct if other != name]
        short = name
        for length in range(minimum, len(name)):
            prefix = name[:length]
            if not prefix[-1].isalnum():
                continue
            if not any(other.startswith(prefix) for other in others):
                short = prefix
                break
        abbreviations[name] = short
    return abbreviations


def short_charm_name(charm: Charm, abbreviations: Mapping[str, str]) -> str:
    """``+4 Atk +3 Shp (1)``: each ability's amount, signed, and short name,
    then the slots in brackets when there are any; ``---`` (as ``charm_name``
    writes no slots) for a charm with neither, so it isn't blank like no charm."""
    parts = [
        f"{pair.amount:+d} {abbreviations.get(pair.ability.name, pair.ability.name)}"
        for pair in charm.abilities
    ]
    if charm.num_slots > 0:
        parts.append(f"({charm.num_slots})")
    name = " ".join(parts) if parts else slot_string(0)
    return name


@dataclass(frozen=True)
class ShortNames:
    """The short names for one language's game data."""

    armor_names: Mapping[ArmorType, Mapping[str, str]]
    abbreviations: Mapping[str, str]

    @classmethod
    def from_game(cls, game: GameData) -> ShortNames:
        """From ``game``'s names in its current language; build it again after a switch."""
        names_by_slot = {
            slot: [armor.name for armor in armors] for slot, armors in game.armors.items()
        }
        words_by_slot = piece_words(names_by_slot)
        short_names = cls(
            armor_names={
                slot: short_armor_names(armors, words=words_by_slot[slot])
                for slot, armors in game.armors.items()
            },
            abbreviations=ability_abbreviations([ability.name for ability in game.abilities]),
        )
        return short_names

    def armor(self, name: str, slot: ArmorType) -> str:
        """``name``'s short name in ``slot``; a name the game doesn't have stays whole."""
        short = self.armor_names.get(slot, {}).get(name, name)
        return short

    def charm(self, charm: Charm) -> str:
        return short_charm_name(charm, self.abbreviations)
