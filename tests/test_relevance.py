"""GetRelevantData against the harness's relevance dumps (RelevanceDump.cpp)."""

from __future__ import annotations

from collections.abc import Callable

from golden_shapes import relevance_shape
from goldens import RelevanceGolden
from mhp3ass.data import GameData
from mhp3ass.query import QuerySpec
from mhp3ass.relevance import formulate_query


def _mismatched_relevance(
    goldens: list[RelevanceGolden], load_game: Callable[[], GameData]
) -> list[str]:
    """Queries whose port output differs from the golden, each on a freshly loaded game."""
    sections = ("rel_abilities", "relevant_flags", "armor", "decorations")
    mismatched = []
    for golden in goldens:
        game = load_game()
        query = formulate_query(game, QuerySpec.from_json(golden.query))
        ours = relevance_shape(game, query)
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
