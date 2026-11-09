"""The display strings of a language folder (``strings.txt``).

Ported from ``StringTable`` and the string macros (``legacy/Common.h:90-194``),
the strings part of ``StringTable::LoadLanguage`` (``legacy/Common.cpp:290-311``)
and ``StripAmpersands`` (``legacy/Common.cpp:328-337``).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum
from pathlib import Path

from mhp3ass.data.text import read_lines


class StringIndex(IntEnum):
    """``StringTable::StringIndex``: the line of each display string, in file order."""

    FILE = 0
    OPTIONS = 1
    LANGUAGE = 2
    HELP = 3
    LOAD = 4
    SAVE = 5
    EXIT = 6
    CLEAR_SETTINGS = 7
    ALLOW_BAD_SKILLS = 8
    ALLOW_PIERCINGS = 9
    ALLOW_EVENT_ARMOR = 10
    ALLOW_LOW_RANK_ARMOR = 11
    CHECK_FOR_UPDATES = 12
    ABOUT = 13
    MY_CHARMS = 14
    IMPORT = 15
    QUICK_SEARCH = 16
    ADVANCED_SEARCH = 17
    CANCEL = 18
    DEFAULT = 19
    NONE = 20
    SEARCH = 21
    SELECT_NONE = 22
    SELECT_BEST = 23
    ADD_NEW = 24
    DELETE = 25
    DELETE_ALL = 26
    MOVE_UP = 27
    MOVE_DOWN = 28
    CLOSE = 29
    FIND_NEXT = 30
    HR = 31
    VILLAGE_QUESTS = 32
    MAX_WEAPON_SLOTS = 33
    MALE = 34
    FEMALE = 35
    FILTER_RESULTS_BY_CHARM = 36
    SORT_RESULTS_BY = 37
    ALL = 38
    DRAGON_RES = 39
    FIRE_RES = 40
    ICE_RES = 41
    THUNDER_RES = 42
    WATER_RES = 43
    BASE_DEFENCE = 44
    MAX_DEFENCE = 45
    DIFFICULTY = 46
    RARITY = 47
    SORT_SLOTS_SPARE = 48
    CHARMS = 49
    USE_NO_CHARMS = 50
    USE_ONLY_MY_CHARMS = 51
    USE_ONLY_SLOTTED_CHARMS = 52
    USE_UP_TO_ONE_SKILL_CHARMS = 53
    USE_ONLY_TWO_SKILL_CHARMS = 54
    SKILLS = 55
    SKILL_FILTERS = 56
    BLADEMASTER = 57
    GUNNER = 58
    SELECT_ARMOR = 59
    IMPORT_CHARMS_FROM_SAVE_DATA = 60
    CHARACTERS = 61
    DELETE_EXISTING_CHARMS = 62
    NO_CHARACTER_DATA_FOUND = 63
    NO_CHARMS_FOUND = 64
    SLOTS = 65
    NONE_BRACKETS = 66
    SLOT_SPARE = 67
    SLOTS_SPARE = 68
    OR_ANYTHING_WITH_SINGULAR = 69
    SLOT_BRACKET = 70
    OR_ANYTHING_WITH_PLURAL = 71
    SLOTS_BRACKET = 72
    OR_ANYTHING_WITH_TORSO_INC = 73
    SOLUTIONS_FOUND = 74
    SHOWING_FIRST = 75
    SOLUTIONS_ONLY = 76
    MHP3RD_SAVE_DATA = 77
    NOT_A_VALID_MHP3RD_SAVE_FILE = 78
    VERSION = 79
    FIND = 80
    CHEATER = 81
    ERROR = 82
    TO = 83
    DEFENCE = 84
    TABLE = 85
    RESULTS = 86


def strip_ampersands(text: str) -> str:
    """``StripAmpersands``: drops every ``&`` (the menu accelerator markers)."""
    stripped = text.replace("&", "")
    return stripped


@dataclass(frozen=True)
class DisplayStrings:
    """``StringTable::text`` for one language, with the ``Common.h`` string macros."""

    text: tuple[str, ...]

    def static(self, index: StringIndex) -> str:
        """``StaticString( X )``."""
        return self.text[index]

    def add(self, index: StringIndex) -> str:
        """``AddString( X )``: a leading space."""
        added = " " + self.text[index]
        return added

    def run(self, index: StringIndex) -> str:
        """``RunString( X )``: a space either side."""
        run = " " + self.text[index] + " "
        return run

    def start(self, index: StringIndex) -> str:
        """``StartString( X )``: a trailing space."""
        started = self.text[index] + " "
        return started

    def basic(self, index: StringIndex) -> str:
        """``BasicString( X )``: without ``&``."""
        basic = strip_ampersands(self.text[index])
        return basic

    def colon(self, index: StringIndex) -> str:
        """``ColonString( X )``: followed by ``": "``."""
        colon = self.text[index] + ": "
        return colon


def load_strings(language_dir: Path) -> DisplayStrings:
    """The strings part of ``StringTable::LoadLanguage`` (Common.cpp:290-311).

    Reads one string per line, skipping blank and ``#`` lines, until every
    ``StringIndex`` has one; later lines are ignored. Where the original
    shows "Unexpected end of file" and carries on with the missing strings
    unset, this raises.
    """
    path = language_dir / "strings.txt"
    text = [line for line in read_lines(path) if line != "" and line[0] != "#"]
    if len(text) < len(StringIndex):
        raise ValueError(
            f"Unexpected end of file: not enough lines of text in {path.name} "
            f"({len(text)} of {len(StringIndex)})"
        )
    strings = DisplayStrings(text=tuple(text[: len(StringIndex)]))
    return strings
