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
from enum import IntEnum
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
        """Read the corpus schema (``tests/corpus/README.md``); charm fields are ignored.

        Checks run in the harness's order (``QueryFile::FormulateQuery``), so a
        file with several problems reports the same one. Numbers must be JSON
        integers and toggles JSON booleans: the harness's ``Convert`` calls
        would coerce floats and strings, which no committed query relies on.
        """
        weapon_slots = _ranged(spec, key="weapon_slots", minimum=0, maximum=3)
        elder_star = _ranged(spec, key="elder_star", minimum=1, maximum=6)
        hr = _ranged(spec, key="hr", minimum=1, maximum=6)
        genders = {"male": Gender.MALE, "female": Gender.FEMALE}
        if spec["gender"] not in genders:
            raise QueryError(f"gender must be male or female, got {spec['gender']}")
        hunter_types = {"blademaster": HunterType.BLADEMASTER, "gunner": HunterType.GUNNER}
        if spec["hunter_type"] not in hunter_types:
            raise QueryError(
                f"hunter_type must be blademaster or gunner, got {spec['hunter_type']}"
            )
        toggles = {
            key: _boolean(spec, key)
            for key in ("include_piercings", "allow_bad", "allow_event", "allow_low_rank")
        }
        skills = tuple(spec["skills"])
        skill_names = tuple(spec["skill_names"])
        if len(skills) != len(skill_names):
            raise QueryError("skills and skill_names must be the same length")
        if not all(_is_integer(index) for index in skills):
            raise QueryError(f"skills must be integer indices, got {list(skills)}")
        query_spec = cls(
            id=spec["id"],
            language=spec["language"],
            hunter_type=hunter_types[spec["hunter_type"]],
            gender=genders[spec["gender"]],
            hr=hr,
            elder_star=elder_star,
            weapon_slots=weapon_slots,
            skills=skills,
            skill_names=skill_names,
            **toggles,
        )
        return query_spec

    @classmethod
    def from_file(cls, path: Path) -> QuerySpec:
        query_spec = cls.from_json(json.loads(path.read_text(encoding="utf-8")))
        return query_spec


class CharmMode(IntEnum):
    """The Charms drop-down (``cmbCharmSelect``); the value is its selected index."""

    NONE = 0
    MY_CHARMS = 1
    SLOTTED = 2
    ONE_SKILL = 3
    TWO_SKILL = 4

    @classmethod
    def from_name(cls, name: Any) -> CharmMode:
        """A query file's ``charm_mode``, as the harness's ``CharmSelectIndex``
        (``harness/src/Workers.cpp``) reads it."""
        modes: dict[str, CharmMode] = {mode.name.lower(): mode for mode in cls}
        if not isinstance(name, str) or name not in modes:
            raise QueryError(
                "charm_mode must be one of none, my_charms, slotted, one_skill, two_skill; "
                f"got {name}"
            )
        mode = modes[name]
        return mode


@dataclass(frozen=True)
class SearchSpec:
    """A query file's full search: the query, the charm mode and the my-charms lines.

    ``my_charms`` is read in every mode: Auto-Guard looks its charm up there.
    """

    query: QuerySpec
    charm_mode: CharmMode
    # mycharms.txt lines, in the query's language.
    my_charms: tuple[str, ...]

    @classmethod
    def from_json(cls, spec: dict[str, Any]) -> SearchSpec:
        """The corpus schema (``tests/corpus/README.md``).

        Checked in the harness's order (``SearchDump::Run``: my charms, the
        query, then the charm mode), except for what needs the game: the
        my-charms lines are parsed by ``charms.my_charms.load_query_my_charms``
        and the skills checked by ``build_query``, both after this. So a file
        with a bad charm line or skill and a bad charm mode reports the mode.
        """
        my_charms = spec["my_charms"]
        if not isinstance(my_charms, list) or not all(isinstance(line, str) for line in my_charms):
            raise QueryError("my_charms must be a list of mycharms.txt lines")
        query = QuerySpec.from_json(spec)
        charm_mode = CharmMode.from_name(spec["charm_mode"])
        search_spec = cls(query=query, charm_mode=charm_mode, my_charms=tuple(my_charms))
        return search_spec

    @classmethod
    def from_file(cls, path: Path) -> SearchSpec:
        search_spec = cls.from_json(json.loads(path.read_text(encoding="utf-8")))
        return search_spec


def _is_integer(value: Any) -> bool:
    # bool is an int subclass in Python, but true/false is no HR.
    integer = isinstance(value, int) and not isinstance(value, bool)
    return integer


def _ranged(spec: dict[str, Any], key: str, minimum: int, maximum: int) -> int:
    """A NumericUpDown value, in the GUI's range (Form1.h:655-656, :681, :708-709)."""
    value = spec[key]
    if not _is_integer(value) or not minimum <= value <= maximum:
        raise QueryError(f"{key} must be {minimum}-{maximum} as in the GUI, got {value!r}")
    return value


def _boolean(spec: dict[str, Any], key: str) -> bool:
    value = spec[key]
    if not isinstance(value, bool):
        raise QueryError(f"{key} must be true or false, got {value!r}")
    return value


def offered_skills(game: GameData) -> list[int]:
    """Indices of the skills the GUI's drop-downs can offer, in skill-list order.

    ``InitSkills`` (Form1.h:224-247) lists a skill only with positive points;
    its tag filter narrows one drop-down, but filter 0 lists them all. The
    Blademaster and Gunner tabs build the same lists (:253-254).
    """
    offered = [index for index, skill in enumerate(game.skills) if skill.points_required > 0]
    return offered


def rank_locked(hr: int, elder_star: int, query: Query) -> bool:
    """Locked only when both the HR and the village stars it needs are above the
    query's (Armor.cpp:113, Decoration.cpp:112, :129)."""
    locked = hr > query.hr and elder_star > query.elder_star
    return locked


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
