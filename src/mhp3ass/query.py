"""Search queries.

Ported from ``Query`` (``legacy/Solution.h:15-27``) and the query-building
half of ``Form1::FormulateQuery`` (``legacy/Form1.h:1184-1214``), with the
form's controls replaced by a corpus query file. The checks follow the
harness (``harness/src/QueryFile.cpp``): only queries the GUI could build
are accepted.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from mhp3ass.data import GameData
from mhp3ass.model import Ability, Armor, ArmorType, Decoration, Gender, HunterType, Skill


class QueryError(ValueError):
    """A query the GUI could not have built."""


@dataclass(frozen=True)
class QuerySpec:
    """A query file's search inputs: the values of the GUI's controls."""

    id: str
    language: str
    hunter_type: HunterType
    gender: Gender
    hr: int
    elder_star: int
    weapon_slots: int
    allow_bad: bool
    include_piercings: bool
    allow_event: bool
    allow_low_rank: bool
    # Indices into the skill list (Skill::static_skills), as the GUI saves them.
    skills: tuple[int, ...]
    # The same skills by name in ``language``, so typos in a query file are caught.
    skill_names: tuple[str, ...]

    @classmethod
    def from_json(cls, spec: dict[str, Any]) -> QuerySpec:
        """Read the corpus schema (``tests/corpus/README.md``); charm fields are ignored."""
        hunter_types = {"blademaster": HunterType.BLADEMASTER, "gunner": HunterType.GUNNER}
        genders = {"male": Gender.MALE, "female": Gender.FEMALE}
        if spec["hunter_type"] not in hunter_types:
            raise QueryError(
                f"hunter_type must be blademaster or gunner, got {spec['hunter_type']}"
            )
        if spec["gender"] not in genders:
            raise QueryError(f"gender must be male or female, got {spec['gender']}")
        skills = tuple(spec["skills"])
        skill_names = tuple(spec["skill_names"])
        if len(skills) != len(skill_names):
            raise QueryError("skills and skill_names must be the same length")
        query_spec = cls(
            id=spec["id"],
            language=spec["language"],
            hunter_type=hunter_types[spec["hunter_type"]],
            gender=genders[spec["gender"]],
            hr=_ranged(spec, key="hr", minimum=1, maximum=6),
            elder_star=_ranged(spec, key="elder_star", minimum=1, maximum=6),
            weapon_slots=_ranged(spec, key="weapon_slots", minimum=0, maximum=3),
            allow_bad=spec["allow_bad"],
            include_piercings=spec["include_piercings"],
            allow_event=spec["allow_event"],
            allow_low_rank=spec["allow_low_rank"],
            skills=skills,
            skill_names=skill_names,
        )
        return query_spec

    @classmethod
    def from_file(cls, path: Path) -> QuerySpec:
        query_spec = cls.from_json(json.loads(path.read_text(encoding="utf-8")))
        return query_spec


def _ranged(spec: dict[str, Any], key: str, minimum: int, maximum: int) -> int:
    """A NumericUpDown value, in the GUI's range (Form1.h:655-656, :681, :708-709)."""
    value = spec[key]
    if not minimum <= value <= maximum:
        raise QueryError(f"{key} must be {minimum}-{maximum} as in the GUI, got {value}")
    return value


@dataclass(eq=False)
class Query:
    """``Query``: the search inputs plus what ``GetRelevantData`` fills in."""

    skills: list[Skill]
    hunter_type: HunterType
    gender: Gender
    hr: int
    elder_star: int
    weapon_slots_allowed: int
    include_piercings: bool
    allow_bad: bool
    allow_event: bool
    allow_low_rank: bool
    # One list per ArmorType, in ArmorType order.
    rel_armor: list[list[Armor]] = field(default_factory=lambda: [[] for _ in ArmorType])
    inf_armor: list[list[Armor]] = field(default_factory=lambda: [[] for _ in ArmorType])
    rel_abilities: list[Ability] = field(default_factory=list)
    rel_decorations: list[Decoration] = field(default_factory=list)
    inf_decorations: list[Decoration] = field(default_factory=list)


def build_query(game: GameData, spec: QuerySpec) -> Query:
    """``FormulateQuery`` up to its ``GetRelevantData`` call (Form1.h:1186-1214).

    ``game`` must have ``spec.language`` applied, for the skill-name check.
    The GUI offers at most six skill drop-downs (Form1.h:95), each listing
    skills with positive points (``InitSkills``, :224-247) and leaving out
    abilities already chosen (:1527-1537).
    """
    if len(spec.skills) > 6:
        raise QueryError("The GUI allows at most 6 skills")
    skills: list[Skill] = []
    for index, expected_name in zip(spec.skills, spec.skill_names, strict=True):
        if not 0 <= index < len(game.skills):
            raise QueryError(f"skill index {index} out of range")
        skill = game.skills[index]
        if skill.name != expected_name:
            raise QueryError(f'skill {index} is "{skill.name}", not "{expected_name}"')
        if skill.points_required <= 0:
            raise QueryError(
                f'skill "{skill.name}" has no positive points; the GUI does not offer it'
            )
        chosen = next((other for other in skills if other.ability is skill.ability), None)
        if chosen is not None:
            raise QueryError(
                f'skills "{chosen.name}" and "{skill.name}" share an ability; '
                "the GUI allows one per ability"
            )
        skills.append(skill)
    query = Query(
        skills=skills,
        hunter_type=spec.hunter_type,
        gender=spec.gender,
        hr=spec.hr,
        elder_star=spec.elder_star,
        weapon_slots_allowed=spec.weapon_slots,
        include_piercings=spec.include_piercings,
        allow_bad=spec.allow_bad,
        allow_event=spec.allow_event,
        allow_low_rank=spec.allow_low_rank,
    )
    return query
