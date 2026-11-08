"""CharmDatabase::GetCharms against the harness's relevance dumps (RelevanceDump.cpp)."""

from __future__ import annotations

from typing import Any

from golden_shapes import charm_shape
from goldens import RelevanceGolden
from mhp3ass.charms.for_query import get_charms
from mhp3ass.charms.generation import CharmTables
from mhp3ass.data import GameData
from mhp3ass.query import QuerySpec, build_query


def _charms_section(
    golden: RelevanceGolden, game: GameData, tables: CharmTables, use_two_skill_charms: bool
) -> dict[str, Any]:
    query = build_query(game, QuerySpec.from_json(golden.query))
    charms = get_charms(query, tables=tables, use_two_skill_charms=use_two_skill_charms)
    section = {"exception": None, "charms": [charm_shape(charm) for charm in charms]}
    return section


def _mismatched_charms(
    goldens: list[RelevanceGolden], game: GameData, tables: CharmTables
) -> list[tuple[str, str]]:
    mismatched = []
    for golden in goldens:
        for key, use_two_skill_charms in (("charms_one_skill", False), ("charms_two_skill", True)):
            ours = _charms_section(golden, game, tables, use_two_skill_charms=use_two_skill_charms)
            if ours != golden.relevance[key]:
                mismatched.append((golden.query["id"], key))
    return mismatched


def test_charms_match_golden(
    relevance_goldens: list[RelevanceGolden], teamhgg_game: GameData, charm_tables: CharmTables
):
    assert _mismatched_charms(relevance_goldens, teamhgg_game, charm_tables) == []


def test_personal_charms_match_golden(
    personal_relevance_goldens: list[RelevanceGolden],
    teamhgg_game: GameData,
    charm_tables: CharmTables,
):
    assert _mismatched_charms(personal_relevance_goldens, teamhgg_game, charm_tables) == []


def test_two_skill_charms_are_the_tables_own_objects(
    repo_root, teamhgg_game: GameData, charm_tables: CharmTables
):
    spec = QuerySpec.from_file(repo_root / "tests" / "relevance" / "r23-large-two-skill-pair.json")
    query = build_query(teamhgg_game, spec)
    eating, attack = (skill.ability for skill in query.skills)

    charms = get_charms(query, tables=charm_tables, use_two_skill_charms=True)

    table_charms = charm_tables.two_skill[attack][eating]
    *from_table, bare = charms
    assert len(table_charms) == 7
    assert all(ours is theirs for ours, theirs in zip(from_table, table_charms, strict=True))
    assert (bare.num_slots, bare.abilities) == (3, [])
