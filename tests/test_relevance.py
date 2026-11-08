"""GetRelevantData against the harness's relevance dumps (RelevanceDump.cpp)."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from goldens import RelevanceGolden
from mhp3ass.data import GameData
from mhp3ass.model import Ability, Armor, ArmorType, Decoration
from mhp3ass.query import Query, QuerySpec
from mhp3ass.relevance import formulate_query


def _ability_ref(ability: Ability | None) -> int | None:
    reference = ability.static_index if ability is not None else None
    return reference


def _armor_entries(armors: list[Armor]) -> list[dict[str, Any]]:
    entries = [
        {"index": armor.index, "no_skills": armor.no_skills, "danger": _ability_ref(armor.danger)}
        for armor in armors
    ]
    return entries


def _decoration_indices(decorations: list[Decoration]) -> list[int]:
    indices = [decoration.index for decoration in decorations]
    return indices


def _relevance_dump(game: GameData, query: Query) -> dict[str, Any]:
    """The query in the harness's relevance layout, without its charm sections."""
    armor = {
        armor_type.name.lower(): {
            "relevant": _armor_entries(query.rel_armor[armor_type.value]),
            "inferior": _armor_entries(query.inf_armor[armor_type.value]),
        }
        for armor_type in ArmorType
    }
    dump = {
        "rel_abilities": [ability.static_index for ability in query.rel_abilities],
        "relevant_flags": [ability.static_index for ability in game.abilities if ability.relevant],
        "armor": armor,
        "decorations": {
            "relevant": _decoration_indices(query.rel_decorations),
            "inferior": _decoration_indices(query.inf_decorations),
        },
    }
    return dump


def _mismatched_relevance(
    goldens: list[RelevanceGolden], load_game: Callable[[], GameData]
) -> list[str]:
    """Queries whose port output differs from the golden, each on a freshly loaded game."""
    sections = ("rel_abilities", "relevant_flags", "armor", "decorations")
    mismatched = []
    for golden in goldens:
        game = load_game()
        query = formulate_query(game, QuerySpec.from_json(golden.query))
        ours = _relevance_dump(game, query)
        expected = {section: golden.relevance[section] for section in sections}
        if ours != expected:
            mismatched.append(golden.query["id"])
    return mismatched


def test_relevant_data_matches_golden(
    relevance_goldens: list[RelevanceGolden], load_teamhgg_game: Callable[[], GameData]
):
    assert _mismatched_relevance(relevance_goldens, load_teamhgg_game) == []


def test_personal_relevant_data_matches_golden(
    personal_relevance_goldens: list[RelevanceGolden], load_teamhgg_game: Callable[[], GameData]
):
    assert _mismatched_relevance(personal_relevance_goldens, load_teamhgg_game) == []
