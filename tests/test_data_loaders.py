"""The Python loaders against the harness's L1 data fixtures.

Each table is compared whole with what the original holds in memory after
loading, including list and dictionary order.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from golden_shapes import game_data_shape, names_shape
from mhp3ass.data import GameData, load_game_data
from mhp3ass.model import Skill


@pytest.fixture(scope="module")
def loaded_shape(legacy_data_dir: Path) -> dict[str, Any]:
    game = load_game_data(legacy_data_dir)
    shape = game_data_shape(game)
    return shape


@pytest.mark.parametrize(
    "table",
    [
        "abilities",
        "ordered_abilities",
        "skills",
        "ordered_skills",
        "armors",
        "decorations",
        "decorations_by_ability",
        "materials",
        "skill_tags",
    ],
)
def test_table_matches_original(loaded_shape: dict[str, Any], game_data: Any, table: str):
    assert loaded_shape[table] == game_data[table]


def test_shape_covers_every_golden_table(loaded_shape: dict[str, Any], game_data: Any):
    assert sorted(loaded_shape) == sorted(game_data)


def _inconsistent_maps(game: GameData) -> list[str]:
    """Name maps that don't map exactly every record's current name to that record."""
    expected = {
        "material_map": {material.name: material for material in game.materials},
        "ability_map": {ability.name: ability for ability in game.abilities},
        "skill_map": {skill.name: skill for skill in game.skills},
        "armor_map": {armor.name: armor for armors in game.armors.values() for armor in armors},
        "decoration_map": {decoration.name: decoration for decoration in game.decorations},
    }
    inconsistent = [name for name, mapping in expected.items() if getattr(game, name) != mapping]
    return inconsistent


def test_name_maps_cover_every_record(legacy_data_dir: Path):
    game = load_game_data(legacy_data_dir)

    assert _inconsistent_maps(game) == []


def test_name_maps_cover_every_record_in_every_language(games_by_language: dict[str, GameData]):
    inconsistent = {
        language: maps
        for language, game in games_by_language.items()
        if (maps := _inconsistent_maps(game))
    }

    assert [len(games_by_language), inconsistent] == [7, {}]


def test_every_language_matches_original(
    games_by_language: dict[str, GameData], language_names: dict[str, Any]
):
    mismatched = {}
    for language, game in games_by_language.items():
        names = names_shape(game)
        expected = language_names[language]
        differing_tables = sorted(table for table in expected if names[table] != expected[table])
        if differing_tables:
            mismatched[language] = differing_tables

    assert [sorted(games_by_language), mismatched] == [sorted(language_names), {}]


def test_every_skill_knows_its_place_in_the_skill_list(teamhgg_game):
    misplaced = [
        skill.name
        for position, skill in enumerate(teamhgg_game.skills)
        if skill.static_index != position or teamhgg_game.skill_index(skill) != position
    ]

    assert [len(teamhgg_game.skills) > 0, misplaced] == [True, []]


def test_another_games_skill_has_no_index_here(teamhgg_game, other_teamhgg_game):
    with pytest.raises(ValueError, match="isn't one of this game's skills"):
        teamhgg_game.skill_index(other_teamhgg_game.skills[0])


@pytest.mark.parametrize("static_index", [-1, 100_000], ids=["negative", "past-the-end"])
def test_a_skill_index_outside_the_list_raises(teamhgg_game, static_index):
    skill = teamhgg_game.skills[0]
    stray = Skill(
        name=skill.name,
        points_required=skill.points_required,
        ability=skill.ability,
        static_index=static_index,
    )

    with pytest.raises(ValueError, match="isn't one of this game's skills"):
        teamhgg_game.skill_index(stray)
