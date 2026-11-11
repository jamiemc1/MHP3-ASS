"""The search box and chips the TUI offers in place of the six skill rows.

A new design over the rows of ``skill_picker`` (``Form1``'s skill drop-downs,
``legacy/Form1.h:210-247``, ``:1478-1556``). Every row is filtered by All,
chip *n* is row *n*, and removing a chip moves the later ones up, so the
chosen skills keep their order and ``query_skills`` reads them as the
original would (``Form1.h:1203-1214``). The tag drop-down and the search
text only narrow the list of skills offered. As in the original, a skill
whose ability is already chosen isn't offered.
"""

from __future__ import annotations

from collections.abc import Sequence

from mhp3ass.data import GameData
from mhp3ass.model import Skill
from mhp3ass.skill_picker import SkillRow, query_skills, skill_choices


def chip_rows(skills: Sequence[Skill], row_count: int = 6) -> tuple[SkillRow, ...]:
    """Rows holding ``skills`` in order, then empty rows, every one filtered by All."""
    if len(skills) > row_count:
        raise ValueError(f"{len(skills)} skills don't fit in {row_count} skill rows")
    filled = [SkillRow(filter_index=0, skill=skill) for skill in skills]
    empty = [SkillRow(filter_index=0, skill=None) for _ in range(row_count - len(skills))]
    rows = (*filled, *empty)
    return rows


def addable_skills(
    game: GameData, rows: Sequence[SkillRow], tag_index: int, text: str
) -> list[Skill]:
    """The skills a chip can be added for: the tag's skills (``skill_choices``)
    without the chosen abilities, whose name contains ``text`` ignoring case."""
    chosen = [skill.ability for skill in query_skills(rows)]
    choices = skill_choices(game, filter_index=tag_index, disallowed=chosen)
    needle = text.strip().casefold()
    matching = [skill for skill in choices if needle in skill.name.casefold()]
    return matching


def add_chip(game: GameData, rows: Sequence[SkillRow], skill: Skill) -> tuple[SkillRow, ...]:
    """Add ``skill`` after the chosen ones. Raises when every row is taken, or
    when the skill isn't offered (its ability is chosen, or it has no points)."""
    chosen = query_skills(rows)
    if len(chosen) == len(rows):
        raise ValueError(f"all {len(rows)} skill rows are taken")
    if skill not in addable_skills(game, rows, tag_index=0, text=""):
        raise ValueError(f"{skill.name} isn't offered with these skills chosen")
    added = chip_rows([*chosen, skill], row_count=len(rows))
    return added


def remove_chip(rows: Sequence[SkillRow], chip: int) -> tuple[SkillRow, ...]:
    """Remove the ``chip``-th chosen skill; the later ones move up."""
    chosen = query_skills(rows)
    if not 0 <= chip < len(chosen):
        raise ValueError(f"chip {chip} isn't one of the {len(chosen)} chosen skills")
    kept = [skill for index, skill in enumerate(chosen) if index != chip]
    removed = chip_rows(kept, row_count=len(rows))
    return removed
