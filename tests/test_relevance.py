"""GetRelevantData against the harness's relevance dumps (RelevanceDump.cpp)."""

from __future__ import annotations

from collections.abc import Callable

from golden_shapes import relevance_shape
from goldens import RelevanceGolden, formulate_query_json
from mhp3ass.data import GameData
from mhp3ass.model import Ability, Decoration
from mhp3ass.relevance import _add_decoration
from solution_builders import make_jewel


def _mismatched_relevance(
    goldens: list[RelevanceGolden], load_game: Callable[[], GameData]
) -> list[str]:
    """Queries whose port output differs from the golden.

    Each query runs on a freshly loaded game, as the harness runs each in a new
    process. get_relevant_data rewrites the state it reads, so one shared game
    gives the same result today; the fresh load keeps that an outcome of the
    comparison rather than an assumption of it (about 20 ms per query).
    """
    sections = ("rel_abilities", "relevant_flags", "armor", "decorations")
    mismatched = []
    for golden in goldens:
        game = load_game()
        query = formulate_query_json(game, golden.query)
        ours = relevance_shape(game, query)
        expected = {section: golden.relevance[section] for section in sections}
        if ours != expected:
            mismatched.append(golden.query["id"])
    return mismatched


def test_relevant_data_matches_golden(
    every_relevance_goldens: list[RelevanceGolden], load_teamhgg_game: Callable[[], GameData]
):
    assert _mismatched_relevance(every_relevance_goldens, load_teamhgg_game) == []


def test_a_beaten_decoration_leaves_the_list_but_stays_inferior(attack: Ability):
    """No shipped decoration beats another of its ability outright, so the goldens
    never remove one (LoadedData.cpp:48-51); the rule is pinned here."""
    worse = make_jewel("worse", attack, 1)
    better = make_jewel("better", attack, 3, index=1)
    listed: list[Decoration] = []
    inferior: list[Decoration] = []

    _add_decoration(listed, worse, inferior=inferior)
    _add_decoration(listed, better, inferior=inferior)

    assert listed == [better]
    assert inferior == [worse, better]
