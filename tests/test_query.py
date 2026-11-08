from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from mhp3ass.data import GameData
from mhp3ass.model import Gender, HunterType
from mhp3ass.query import QueryError, QuerySpec, build_query


def test_every_committed_query_builds(repo_root: Path, teamhgg_game: GameData):
    query_paths = sorted((repo_root / "tests" / "corpus").glob("*.json"))
    query_paths += sorted((repo_root / "tests" / "relevance").glob("*.json"))
    built = {}
    for path in query_paths:
        query = build_query(teamhgg_game, QuerySpec.from_file(path))
        built[path.stem] = [skill.name for skill in query.skills]

    assert len(built) == 33
    assert built["g04-attack-sharp-two-skill"] == ["Attack Up [Med]", "Sharp Sword"]


def test_query_takes_the_spec_fields(
    attack_sharp_query_json: dict[str, Any], teamhgg_game: GameData
):
    attack_sharp_query_json.update(
        hunter_type="gunner",
        gender="female",
        hr=3,
        elder_star=4,
        weapon_slots=2,
        allow_bad=True,
        include_piercings=False,
        allow_event=False,
        allow_low_rank=False,
    )

    query = build_query(teamhgg_game, QuerySpec.from_json(attack_sharp_query_json))

    assert (query.hunter_type, query.gender) == (HunterType.GUNNER, Gender.FEMALE)
    assert (query.hr, query.elder_star, query.weapon_slots_allowed) == (3, 4, 2)
    assert (query.allow_bad, query.include_piercings, query.allow_event, query.allow_low_rank) == (
        True,
        False,
        False,
        False,
    )
    assert query.skills == [teamhgg_game.skills[1], teamhgg_game.skills[12]]
    assert query.rel_armor == [[], [], [], [], []]
    assert query.rel_abilities == []


@pytest.mark.parametrize(
    ("key", "value", "message"),
    [
        ("hr", 0, "hr must be 1-6"),
        ("hr", 7, "hr must be 1-6"),
        ("elder_star", 0, "elder_star must be 1-6"),
        ("elder_star", 7, "elder_star must be 1-6"),
        ("weapon_slots", -1, "weapon_slots must be 0-3"),
        ("weapon_slots", 4, "weapon_slots must be 0-3"),
        ("gender", "both", "gender must be male or female"),
        ("hunter_type", "both", "hunter_type must be blademaster or gunner"),
        ("skill_names", ["Attack Up [Med]"], "same length"),
    ],
)
def test_spec_rejects_what_the_gui_cannot_set(
    attack_sharp_query_json: dict[str, Any], key: str, value: Any, message: str
):
    attack_sharp_query_json[key] = value

    with pytest.raises(QueryError, match=message):
        QuerySpec.from_json(attack_sharp_query_json)


@pytest.mark.parametrize(
    ("skills", "skill_names", "message"),
    [
        (list(range(7)), [""] * 7, "at most 6 skills"),
        ([999], ["Nothing"], "skill index 999 out of range"),
        ([1], ["Sharp Sword"], 'skill 1 is "Attack Up \\[Med\\]", not "Sharp Sword"'),
        ([3], ["Attack Down [Sm]"], "has no positive points"),
        ([1, 2], ["Attack Up [Med]", "Attack Up [Lg]"], "share an ability"),
    ],
)
def test_build_rejects_skill_choices_the_gui_cannot_make(
    attack_sharp_query_json: dict[str, Any],
    teamhgg_game: GameData,
    skills: list[int],
    skill_names: list[str],
    message: str,
):
    attack_sharp_query_json.update(skills=skills, skill_names=skill_names)
    spec = QuerySpec.from_json(attack_sharp_query_json)

    with pytest.raises(QueryError, match=message):
        build_query(teamhgg_game, spec)
