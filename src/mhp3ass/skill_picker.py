"""The six skill rows a search is built from, per hunter type.

Ported from ``Form1``'s skill drop-downs (``legacy/Form1.h``): ``InitSkills``
and ``ResetSkill`` (``:210-247``), the filter and skill handlers
``cmbSkillFilter_SelectedIndexChanged`` and ``cmbSkill_SelectedIndexChanged``
(``:1478-1556``), ``SearchIndexMap`` (``:548-556``) and the skill-row part of
``LoadConfig`` (``:414-426``).

Each row has a filter (an index into ``game.skill_tags``: 0 All, 1 Misc, then
the tags) and at most one skill. A row offers the skills its filter allows,
leaving out every ability another row has chosen. The original keeps that
true after every change: picking a skill rebuilds every other row's list, and
a row's own choice survives a rebuild whenever it is still offered. So the
state here is just the rows, and each row's list is computed from the others.

Rows hold the game's own ``Skill`` records and abilities are compared by
identity, so rows must come from the ``GameData`` they are used with.
"""

from __future__ import annotations

from collections.abc import Collection, Sequence
from dataclasses import dataclass

from mhp3ass.data import GameData
from mhp3ass.model import Ability, Skill
from mhp3ass.settings_cfg import SkillSelection


@dataclass(frozen=True)
class SkillRow:
    """One row: the filter drop-down's index (-1 when it has none) and the chosen skill."""

    filter_index: int
    skill: Skill | None


@dataclass(frozen=True)
class SkillRowsByHunter:
    """The Blademaster and Gunner tabs' rows, which the original keeps separately."""

    blademaster: tuple[SkillRow, ...]
    gunner: tuple[SkillRow, ...]


def starting_rows() -> tuple[SkillRow, ...]:
    """Six rows filtered by All with no skill, as ``InitFilters`` leaves them (``:199-208``)."""
    rows = tuple(SkillRow(filter_index=0, skill=None) for _ in range(6))
    return rows


def skill_choices(
    game: GameData, filter_index: int, disallowed: Collection[Ability]
) -> list[Skill]:
    """``InitSkills( box, map, filter, disallowed )``: the skills a row lists after "(none)".

    Skills come in load order (``Skill::static_skills``), leaving out those
    with no points required (the negative skills) and those of a
    ``disallowed`` ability. Filter 0 (All) keeps the rest, 1 (Misc) those whose
    ability has no tags, and any other index those whose ability has a tag
    with that filter's name. A row with no filter (-1) lists nothing, not
    even "(none)".
    """
    _check_filter(game, filter_index)
    if filter_index == -1:
        return []
    tag_name = game.skill_tags[filter_index].name
    choices = []
    for skill in game.skills:
        ability = skill.ability
        if skill.points_required <= 0 or ability in disallowed:
            continue
        if filter_index == 0:
            choices.append(skill)
        elif filter_index == 1:
            if not ability.tags:
                choices.append(skill)
        elif any(tag.name == tag_name for tag in ability.tags):
            choices.append(skill)
    return choices


def row_choices(game: GameData, rows: Sequence[SkillRow], row: int) -> list[Skill]:
    """The skills row ``row`` lists: its filter's, without the other rows' abilities."""
    _check_row(rows, row)
    chosen_elsewhere = [
        other.skill.ability
        for index, other in enumerate(rows)
        if index != row and other.skill is not None
    ]
    choices = skill_choices(game, filter_index=rows[row].filter_index, disallowed=chosen_elsewhere)
    return choices


def select_filter(
    game: GameData, rows: Sequence[SkillRow], row: int, filter_index: int
) -> tuple[SkillRow, ...]:
    """``cmbSkillFilter_SelectedIndexChanged``: change a row's filter.

    The row keeps its skill only if the new filter offers it.
    ``filter_index`` must be one of the filter drop-down's items, or -1:
    setting anything else throws ``ArgumentOutOfRangeException`` in the
    original, which this raises as ``ValueError``.
    """
    _check_row(rows, row)
    _check_filter(game, filter_index)
    cleared = _replaced(rows, row, SkillRow(filter_index=filter_index, skill=None))
    kept = rows[row].skill
    still_offered = kept is not None and kept in row_choices(game, cleared, row)
    filtered = _replaced(
        rows, row, SkillRow(filter_index=filter_index, skill=kept if still_offered else None)
    )
    return filtered


def select_skill(
    game: GameData, rows: Sequence[SkillRow], row: int, skill: Skill | None
) -> tuple[SkillRow, ...]:
    """``cmbSkill_SelectedIndexChanged``: choose one of the row's offered skills.

    ``None``, the "(none)" item, clears the row. A skill the row doesn't offer
    can't be chosen in the drop-down, so it raises ``ValueError``.
    """
    _check_row(rows, row)
    if skill is not None and skill not in row_choices(game, rows, row):
        raise ValueError(f"row {row} doesn't offer {skill.name}")
    selected = _replaced(rows, row, SkillRow(filter_index=rows[row].filter_index, skill=skill))
    return selected


def restore_skill_rows(
    game: GameData, current: SkillRowsByHunter, selections: Sequence[SkillSelection]
) -> SkillRowsByHunter:
    """The skill rows ``LoadConfig`` restores from ``settings.cfg`` (``Form1.h:414-426``).

    Row by row, each tab's filter is set, then its skill is looked up by its
    ``Skill::static_skills`` index among the skills the row now offers
    (``SearchIndexMap``). A skill the row doesn't offer, or -1, leaves the
    row empty. Rows not yet restored still hold ``current``'s choices, so a
    saved skill whose ability one of them has chosen is dropped (quirk 41).
    A version 1 file has five rows; the sixth keeps ``current``'s.
    """
    for rows in (current.blademaster, current.gunner):
        if len(rows) != 6:
            raise ValueError(f"each tab has six skill rows, not {len(rows)}")
        for row in rows:
            if row.skill is not None:
                saved_skill_index(game, row)
    if len(selections) not in (5, 6):
        raise ValueError(f"settings.cfg holds five or six skill rows, not {len(selections)}")
    blademaster = current.blademaster
    gunner = current.gunner
    for row, selection in enumerate(selections):
        blademaster = _restore_row(
            game,
            rows=blademaster,
            row=row,
            filter_index=selection.blademaster_filter,
            skill_index=selection.blademaster_skill,
        )
        gunner = _restore_row(
            game,
            rows=gunner,
            row=row,
            filter_index=selection.gunner_filter,
            skill_index=selection.gunner_skill,
        )
    restored = SkillRowsByHunter(blademaster=blademaster, gunner=gunner)
    return restored


def query_skills(rows: Sequence[SkillRow]) -> list[Skill]:
    """The skills ``FormulateQuery`` searches for (``Form1.h:1203-1214``), in row order."""
    skills = [row.skill for row in rows if row.skill is not None]
    return skills


def saved_skill_index(game: GameData, row: SkillRow) -> int:
    """``SaveConfig``'s value for a row's skill (``Form1.h:486-492``): its static index, or -1."""
    if row.skill is None:
        return -1
    try:
        index = game.skills.index(row.skill)
    except ValueError:
        raise ValueError(f"{row.skill.name} isn't one of this game's skills") from None
    return index


def _restore_row(
    game: GameData, rows: tuple[SkillRow, ...], row: int, filter_index: int, skill_index: int
) -> tuple[SkillRow, ...]:
    """Set the row's filter, then pick its saved skill from what the row offers."""
    _check_filter(game, filter_index)
    cleared = _replaced(rows, row, SkillRow(filter_index=filter_index, skill=None))
    saved = game.skills[skill_index] if 0 <= skill_index < len(game.skills) else None
    found = saved if saved is not None and saved in row_choices(game, cleared, row) else None
    restored = _replaced(rows, row, SkillRow(filter_index=filter_index, skill=found))
    return restored


def _check_filter(game: GameData, filter_index: int) -> None:
    if not -1 <= filter_index < len(game.skill_tags):
        raise ValueError(
            f"filter {filter_index} isn't one of the {len(game.skill_tags)} filter items"
        )


def _check_row(rows: Sequence[SkillRow], row: int) -> None:
    if not 0 <= row < len(rows):
        raise ValueError(f"row {row} isn't one of the {len(rows)} skill rows")


def _replaced(rows: Sequence[SkillRow], row: int, new_row: SkillRow) -> tuple[SkillRow, ...]:
    replaced = tuple(new_row if index == row else old for index, old in enumerate(rows))
    return replaced
