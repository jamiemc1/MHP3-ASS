"""Switching the language while the app runs.

Ported from the non-UI part of ``Form1::LanguageSelect_Click``
(``legacy/Form1.h:2011-2130``): ``StringTable::LoadLanguage`` renames the
game's records and loads the display strings, and ``CharmDatabase::SaveCustom``
rewrites ``mycharms.txt`` with the new language's ability names (quirk 30).
"""

from __future__ import annotations

from pathlib import Path

from mhp3ass.charms.my_charms import load_my_charms, save_my_charms
from mhp3ass.charms.validity import CharmValidity
from mhp3ass.data import GameData, apply_language
from mhp3ass.data.strings import DisplayStrings, load_strings


def switch_language(
    game: GameData, validity: CharmValidity, language_dir: Path, my_charms_path: Path
) -> DisplayStrings:
    """Rename ``game``'s records into the language of ``language_dir``,
    rewrite ``my_charms_path`` in it, and return its display strings.

    The original saves the my-charms list it holds, which a line that failed
    to load at start-up isn't in; here the file is read in the current
    language first, so such a line is dropped the same way. The strings and
    the charms are read before anything is renamed, so a strings file that
    is too short (``ValueError``), an unreadable my-charms file (``OSError``)
    or one the original couldn't load (``MyCharmsFileError``) changes
    nothing."""
    strings = load_strings(language_dir)
    loaded = load_my_charms(my_charms_path, game=game, validity=validity)
    apply_language(game, language_dir)
    save_my_charms(my_charms_path, loaded.charms)
    return strings
