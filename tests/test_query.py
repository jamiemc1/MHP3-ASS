from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from mhp3ass.data import GameData
from mhp3ass.model import Gender, HunterType
from mhp3ass.query import (
    CharmMode,
    QueryError,
    QuerySpec,
    SearchSpec,
    build_query,
    offered_skills,
)


def test_every_committed_query_builds(repo_root: Path, teamhgg_game: GameData):
    query_paths = sorted((repo_root / "tests" / "corpus").glob("*.json"))
    query_paths += sorted((repo_root / "tests" / "relevance").glob("*.json"))
    built = {}
    for path in query_paths:
        query = build_query(teamhgg_game, QuerySpec.from_file(path))
        built[path.stem] = [skill.name for skill in query.skills]

    assert query_paths
    assert all(built.values())
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
        ("hr", 4.5, "hr must be 1-6"),
        ("hr", "6", "hr must be 1-6"),
        ("hr", True, "hr must be 1-6"),
        ("allow_event", "yes", "allow_event must be true or false"),
        ("skills", [1.0, 12], "skills must be integer indices"),
    ],
)
def test_spec_rejects_what_the_gui_cannot_set(
    attack_sharp_query_json: dict[str, Any], key: str, value: Any, message: str
):
    attack_sharp_query_json[key] = value

    with pytest.raises(QueryError, match=message):
        QuerySpec.from_json(attack_sharp_query_json)


def test_spec_reports_problems_in_the_harness_order(attack_sharp_query_json: dict[str, Any]):
    """QueryFile::FormulateQuery checks ranks before gender and hunter type."""
    attack_sharp_query_json.update(hr=0, gender="both", hunter_type="both")

    with pytest.raises(QueryError, match="hr must be 1-6"):
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


def test_offered_skills_are_exactly_the_ones_build_query_accepts(
    attack_sharp_query_json: dict[str, Any], teamhgg_game: GameData
):
    offered = offered_skills(teamhgg_game)
    accepted = []
    for index, skill in enumerate(teamhgg_game.skills):
        attack_sharp_query_json.update(skills=[index], skill_names=[skill.name])
        try:
            build_query(teamhgg_game, QuerySpec.from_json(attack_sharp_query_json))
        except QueryError:
            continue
        accepted.append(index)

    assert [len(offered), len(teamhgg_game.skills), offered] == [146, 209, accepted]


def test_every_committed_query_reads_as_a_search(repo_root: Path):
    query_paths = sorted((repo_root / "tests" / "corpus").glob("*.json"))
    modes = {path.stem: SearchSpec.from_file(path).charm_mode for path in query_paths}

    assert [modes["1a-attack-sharp-default-charms"], modes["g04-attack-sharp-two-skill"]] == [
        CharmMode.MY_CHARMS,
        CharmMode.TWO_SKILL,
    ]


def test_search_spec_keeps_the_query_and_charm_lines(attack_sharp_query_json: dict[str, Any]):
    attack_sharp_query_json.update(charm_mode="slotted", my_charms=["1,Attack,3,,"])

    search = SearchSpec.from_json(attack_sharp_query_json)

    assert [search.query, search.charm_mode, search.my_charms] == [
        QuerySpec.from_json(attack_sharp_query_json),
        CharmMode.SLOTTED,
        ("1,Attack,3,,",),
    ]


@pytest.mark.parametrize(
    ("name", "mode"),
    [
        ("none", CharmMode.NONE),
        ("my_charms", CharmMode.MY_CHARMS),
        ("slotted", CharmMode.SLOTTED),
        ("one_skill", CharmMode.ONE_SKILL),
        ("two_skill", CharmMode.TWO_SKILL),
    ],
)
def test_charm_modes_are_the_drop_down_indices(name: str, mode: CharmMode):
    assert [CharmMode.from_name(name), int(CharmMode.from_name(name))] == [mode, mode.value]


def test_unknown_charm_mode_gives_the_harness_message(attack_sharp_query_json: dict[str, Any]):
    attack_sharp_query_json.update(charm_mode="three_skill", my_charms=[])

    with pytest.raises(
        QueryError,
        match="charm_mode must be one of none, my_charms, slotted, one_skill, two_skill; "
        "got three_skill",
    ):
        SearchSpec.from_json(attack_sharp_query_json)


@pytest.mark.parametrize("my_charms", ["1,Attack,3,,", [1]])
def test_my_charms_must_be_a_list_of_lines(attack_sharp_query_json: dict[str, Any], my_charms):
    attack_sharp_query_json.update(charm_mode="none", my_charms=my_charms)

    with pytest.raises(QueryError, match="my_charms must be a list"):
        SearchSpec.from_json(attack_sharp_query_json)


def test_query_problems_are_reported_before_the_charm_mode(
    attack_sharp_query_json: dict[str, Any],
):
    attack_sharp_query_json.update(hr=0, charm_mode="three_skill", my_charms=[])

    with pytest.raises(QueryError, match="hr must be 1-6"):
        SearchSpec.from_json(attack_sharp_query_json)
