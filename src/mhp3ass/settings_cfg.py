"""The GUI's saved state: ``settings.cfg``.

Ported from ``Form1::LoadConfig`` and ``Form1::SaveConfig``
(``legacy/Form1.h:381-540``). The GUI rewrites the file after every search
and whenever an Options toggle changes: the options, the six skill
drop-downs, then one line per solution found by the last search.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from mhp3ass.data.text import read_lines, to_boolean, to_int32, to_uint32
from mhp3ass.skill_picker import SkillSelection


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
        raise ValueError(f"unsupported settings.cfg version in {path}")
    version = lines[0]
    skill_rows = 6 if version == "2" else 5
    header_length = 14 + 4 * skill_rows
    if len(lines) < header_length:
        raise ValueError(f"{path} ends inside its header ({len(lines)} lines)")

    solution_lines = tuple(lines[header_length:])
    if "" in solution_lines:
        raise ValueError(f"{path} has a blank solution line")

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
