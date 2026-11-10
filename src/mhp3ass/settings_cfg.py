"""The GUI's saved state: ``settings.cfg`` (and File > Save's ``.ass``, the same format).

Ported from ``Form1::LoadConfig``, ``Form1::SaveConfig`` and
``Form1::AddSolution( String^ )`` (``legacy/Form1.h:342-540``): the options,
the skill drop-down rows, then one line per solution.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from mhp3ass.data import GameData
from mhp3ass.data.text import read_lines, split_fields, to_boolean, to_int32, to_uint32
from mhp3ass.model import AbilityPair, Armor, ArmorType, Charm
from mhp3ass.skill_picker import SkillSelection
from mhp3ass.solution import calculate_data
from mhp3ass.solution.state import Solution


class SettingsCfgError(ValueError):
    """A ``settings.cfg`` the original can't load."""


@dataclass(frozen=True)
class SettingsCfg:
    version: str
    language_index: int
    last_search_gunner: bool
    hunter_tab: int
    male: bool
    allow_bad: bool
    allow_piercings: bool
    allow_event: bool
    allow_low_rank: bool
    sort_index: int
    charm_select_index: int
    hr: int
    elder_star: int
    weapon_slots: int
    skill_selections: tuple[SkillSelection, ...]
    solution_lines: tuple[str, ...]


def read_settings_cfg(path: Path) -> SettingsCfg:
    """Read ``settings.cfg`` field by field, in ``LoadConfig``'s order.

    Version 1 files hold five skill rows and version 2 six. The original
    silently ignores any other version; this raises instead, as does a file
    that ends before the skill rows do. Every line after the skill rows is a
    solution, as ``LoadConfig`` reads them until ``EndOfStream``; a blank one
    raises, as ``AddSolution`` fails converting its empty first field
    (``Form1.h:342-348``).
    """
    lines = read_lines(path)
    if not lines or lines[0] not in ("1", "2"):
        raise SettingsCfgError(f"unsupported settings.cfg version in {path}")
    version = lines[0]
    skill_rows = 6 if version == "2" else 5
    header_length = 14 + 4 * skill_rows
    if len(lines) < header_length:
        raise SettingsCfgError(f"{path} ends inside its header ({len(lines)} lines)")

    solution_lines = tuple(lines[header_length:])
    if "" in solution_lines:
        raise SettingsCfgError(f"{path} has a blank solution line")

    rows = lines[14:header_length]
    skill_selections = tuple(
        SkillSelection(
            blademaster_filter=to_int32(rows[row * 4]),
            blademaster_skill=to_int32(rows[row * 4 + 1]),
            gunner_filter=to_int32(rows[row * 4 + 2]),
            gunner_skill=to_int32(rows[row * 4 + 3]),
        )
        for row in range(skill_rows)
    )
    settings = SettingsCfg(
        version=version,
        language_index=to_uint32(lines[1]),
        last_search_gunner=to_boolean(lines[2]),
        hunter_tab=to_int32(lines[3]),
        male=to_boolean(lines[4]),
        allow_bad=to_boolean(lines[5]),
        allow_piercings=to_boolean(lines[6]),
        allow_event=to_boolean(lines[7]),
        allow_low_rank=to_boolean(lines[8]),
        sort_index=to_int32(lines[9]),
        charm_select_index=to_int32(lines[10]),
        hr=to_int32(lines[11]),
        elder_star=to_int32(lines[12]),
        weapon_slots=to_int32(lines[13]),
        skill_selections=skill_selections,
        solution_lines=solution_lines,
    )
    return settings


def settings_cfg_text(settings: SettingsCfg) -> bytes:
    """``SaveConfig``'s file for ``settings``: version 2, six skill rows, UTF-8
    without a byte order mark, CRLF after every line."""
    if len(settings.skill_selections) != 6:
        raise ValueError(f"SaveConfig writes six skill rows, not {len(settings.skill_selections)}")
    header: list[object] = [
        "2",
        settings.language_index,
        settings.last_search_gunner,
        settings.hunter_tab,
        settings.male,
        settings.allow_bad,
        settings.allow_piercings,
        settings.allow_event,
        settings.allow_low_rank,
        settings.sort_index,
        settings.charm_select_index,
        settings.hr,
        settings.elder_star,
        settings.weapon_slots,
    ]
    for row in settings.skill_selections:
        header += [
            row.blademaster_filter,
            row.blademaster_skill,
            row.gunner_filter,
            row.gunner_skill,
        ]
    lines = [str(value) for value in header] + list(settings.solution_lines)
    text = "".join(f"{line}\r\n" for line in lines)
    data = text.encode("utf-8")
    return data


def parse_solution_line(line: str, game: GameData) -> Solution:
    """``AddSolution( String^ )`` up to its filing (Form1.h:342-375): the
    solution a saved line describes, its stats from ``calculate_data`` and its
    spare slots from the line. Raises ``SettingsCfgError`` naming the line
    where the original throws, as on an empty slot's ``-1`` (quirk 43).
    Difficulty is the armour's only (quirk 44)."""
    try:
        solution = _parse_solution_fields(split_fields(line, separator=" "), game)
    except (ValueError, OverflowError, IndexError) as error:
        raise SettingsCfgError(f"can't load the solution line {line!r}: {error}") from error
    return solution


def _parse_solution_fields(fields: list[str], game: GameData) -> Solution:
    armors: list[Armor | None] = [
        _entry(game.armors[armor_type], to_uint32(fields[slot]), f"{armor_type.name} armour")
        for slot, armor_type in enumerate(ArmorType)
    ]
    decoration_count = to_uint32(fields[9])
    decorations = [
        _entry(game.decorations, to_uint32(fields[10 + i]), "decoration")
        for i in range(decoration_count)
    ]
    skill_count = to_uint32(fields[10 + decoration_count])
    extra_skills = [
        _entry(game.skills, to_uint32(fields[11 + decoration_count + i]), "skill")
        for i in range(skill_count)
    ]
    charm = None
    charm_start = 11 + decoration_count + skill_count
    if charm_start < len(fields):
        charm = Charm(num_slots=to_uint32(fields[charm_start]))
        ability_count = to_uint32(fields[charm_start + 1])
        for i in range(ability_count):
            # The ability index is converted before the amount (Form1.h:365-366).
            ability = _entry(game.abilities, to_uint32(fields[charm_start + 3 + i * 2]), "ability")
            amount = to_int32(fields[charm_start + 2 + i * 2])
            charm.abilities.append(AbilityPair(ability=ability, amount=amount))
    solution = Solution(
        armors=armors, charm=charm, decorations=decorations, extra_skills=extra_skills
    )
    calculate_data(solution)
    solution.total_slots_spare = to_uint32(fields[5])
    solution.slots_spare = [0, *(to_uint32(fields[5 + size]) for size in (1, 2, 3))]
    return solution


def _entry[T](table: list[T], position: int, what: str) -> T:
    """``table[position]`` as a .NET ``List`` indexer: out of range throws."""
    if position >= len(table):
        raise IndexError(f"{what} {position} is not in this game (0-{len(table) - 1})")
    return table[position]
