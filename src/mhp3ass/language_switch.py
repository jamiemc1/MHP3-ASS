"""Switching the language while the app runs.

Ported from the non-UI part of ``Form1::LanguageSelect_Click``
(``legacy/Form1.h:2011-2130``): ``StringTable::LoadLanguage`` renames the
game's records and loads the display strings, and ``CharmDatabase::SaveCustom``
rewrites ``mycharms.txt`` with the new language's ability names (quirk 30).
"""

from __future__ import annotations

from pathlib import Path

from mhp3ass.charms.my_charms import load_my_charms, my_charms_text
from mhp3ass.charms.validity import CharmValidity
from mhp3ass.data import GameData, apply_language, load_game_data
from mhp3ass.data.strings import DisplayStrings, load_strings
from mhp3ass.model import AbilityPair, Charm
from mhp3ass.saved_data import write_atomically
from mhp3ass.search import language_dir


def switch_language(
    game: GameData,
    validity: CharmValidity,
    data_dir: Path,
    language: str,
    my_charms_path: Path,
) -> DisplayStrings:
    """Rename ``game``'s records into ``language`` (a folder of
    ``data_dir``'s ``Languages``), rewrite ``my_charms_path`` in it, and
    return its display strings.

    The original saves the my-charms list it holds, which a line that failed
    to load at start-up isn't in; here the file is read in the current
    language first, so such a line is dropped the same way.

    Everything that can fail happens before ``game`` is renamed: the strings
    are read, the language is applied to a fresh copy of the game data (so a
    short or broken language file raises here), and the new ``mycharms.txt``
    is written from that copy's names. An error (``FileNotFoundError`` for
    no such language, ``OSError``, ``ValueError``, ``MyCharmsFileError``)
    leaves ``game`` and the files as they were."""
    folder = language_dir(data_dir, language)
    strings = load_strings(folder)
    renamed = load_game_data(data_dir)
    apply_language(renamed, folder)
    loaded = load_my_charms(my_charms_path, game=game, validity=validity)
    charms = [_charm_in(renamed, charm) for charm in loaded.charms]
    write_atomically(my_charms_path, my_charms_text(charms).encode("utf-8"))
    apply_language(game, folder)
    return strings


def _charm_in(game: GameData, charm: Charm) -> Charm:
    """``charm`` with ``game``'s abilities, matched by their place in the list."""
    pairs = [
        AbilityPair(ability=game.abilities[pair.ability.static_index], amount=pair.amount)
        for pair in charm.abilities
    ]
    copy = Charm(num_slots=charm.num_slots, abilities=pairs)
    return copy
