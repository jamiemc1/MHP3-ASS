"""GetRelevantData against the harness's relevance dumps (RelevanceDump.cpp)."""

from __future__ import annotations

from collections.abc import Callable

from golden_shapes import relevance_shape
from goldens import RelevanceGolden
from mhp3ass.data import GameData
from mhp3ass.model import Ability, AbilityPair, Armor, Decoration
from mhp3ass.query import QuerySpec
from mhp3ass.relevance import _add_armor, _add_decoration, formulate_query


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


def test_a_beaten_decoration_leaves_the_list_but_stays_inferior(attack: Ability):
    """No shipped decoration beats another of its ability outright, so the goldens
    never remove one (LoadedData.cpp:48-51); the rule is pinned here."""
    worse = Decoration(name="worse", index=0, rarity=1, slots_required=1, hr=1, elder_star=1)
    worse.abilities = [AbilityPair(ability=attack, amount=1)]
    better = Decoration(name="better", index=1, rarity=1, slots_required=1, hr=1, elder_star=1)
    better.abilities = [AbilityPair(ability=attack, amount=3)]
    listed: list[Decoration] = []
    inferior: list[Decoration] = []

    _add_decoration(listed, worse, inferior=inferior)
    _add_decoration(listed, better, inferior=inferior)

    assert listed == [better]
    assert inferior == [worse, better]


def test_a_danger_piece_does_not_displace_one_without_it(
    make_armor: Callable[..., Armor], attack: Ability, defense: Ability
):
    """The original's danger list is always empty (LoadedData.cpp:141-158), so only a
    synthetic piece reaches the danger check on displacing (:66)."""
    plain = make_armor("plain", abilities=[(attack, 1)], num_slots=0)
    dangerous = make_armor("dangerous", abilities=[(attack, 2), (defense, -2)], num_slots=1)
    dangerous.danger = defense
    listed: list[Armor] = []
    inferior: list[Armor] = []

    _add_armor(listed, plain, rel_abilities=[attack], inferior=inferior)
    _add_armor(listed, dangerous, rel_abilities=[attack], inferior=inferior)

    assert listed == [plain, dangerous]
    assert inferior == [plain, dangerous]


def test_a_listed_danger_piece_does_not_turn_away_one_without_it(
    make_armor: Callable[..., Armor], attack: Ability, defense: Ability
):
    """The danger check on being displaced (LoadedData.cpp:73): a listed piece with a
    danger skill only turns away a new piece with the same one."""
    dangerous = make_armor("dangerous", abilities=[(attack, 2), (defense, -2)], num_slots=1)
    dangerous.danger = defense
    plain = make_armor("plain", abilities=[(attack, 1)], num_slots=0)
    listed: list[Armor] = []
    inferior: list[Armor] = []

    _add_armor(listed, dangerous, rel_abilities=[attack], inferior=inferior)
    _add_armor(listed, plain, rel_abilities=[attack], inferior=inferior)

    assert listed == [dangerous, plain]
    assert inferior == [dangerous, plain]
