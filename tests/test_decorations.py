"""Decoration comparisons and choices against the harness's dumps
(ModelDump.cpp's IsBetterThan, RelevanceDump.cpp's best-decorations)."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest

from mhp3ass.data import GameData
from mhp3ass.decorations import (
    NoDecorationsError,
    best_decoration_for_query,
    decoration_is_better_than,
    decoration_matches_query,
    decoration_skill_at,
)
from mhp3ass.model import Ability, AbilityPair, Decoration, Skill
from mhp3ass.query import Query


def test_is_better_than_matches_golden_for_every_pair(models_golden, teamhgg_game):
    decorations = teamhgg_game.decorations
    ours = [
        "".join("1" if decoration_is_better_than(a, b) else "0" for b in decorations)
        for a in decorations
    ]

    mismatched = [
        decorations[index].name
        for index, (row, golden_row) in enumerate(
            zip(ours, models_golden["decoration_is_better_than"], strict=True)
        )
        if row != golden_row
    ]

    assert mismatched == []


@pytest.fixture
def sharpness():
    return Ability(name="Sharpness", static_index=1)


def _decoration(name, slots, pairs):
    decoration = Decoration(name=name, index=0, rarity=1, slots_required=slots, hr=1, elder_star=1)
    decoration.abilities = [
        AbilityPair(ability=ability, amount=amount) for ability, amount in pairs
    ]
    return decoration


def test_second_skill_comparison_is_unsigned(attack, sharpness):
    # Same first skill per slot; second skills +1 against -1. Signed, +1 < -1 is false;
    # as C++ unsigned, 1 < 0xFFFFFFFF is true.
    positive = _decoration("positive", slots=1, pairs=[(attack, 2), (sharpness, 1)])
    negative = _decoration("negative", slots=1, pairs=[(attack, 2), (sharpness, -1)])

    assert decoration_is_better_than(positive, negative)


def test_skill_at_is_zero_for_other_abilities(attack, sharpness):
    decoration = _decoration("one skill", slots=1, pairs=[(attack, 2)])

    assert [
        decoration_skill_at(decoration, attack),
        decoration_skill_at(decoration, sharpness),
    ] == [2, 0]


def _best_decoration_cell(game: GameData, ability: Ability, max_slots: int, query: Query) -> int:
    """The golden's encoding: a decoration index, -1 for none, -2 where the call raises."""
    try:
        best = best_decoration_for_query(game, ability, max_slots=max_slots, query=query)
    except NoDecorationsError:
        return -2
    cell = best.index if best is not None else -1
    return cell


def test_best_decoration_matches_golden_for_every_rank_and_slot_count(
    best_decorations_golden: Any, teamhgg_game: GameData, make_query: Callable[..., Query]
):
    minimum = best_decorations_golden["min_rank"]
    ranks = range(minimum, best_decorations_golden["max_rank"] + 1)
    slot_counts = range(best_decorations_golden["max_slots"] + 1)
    mismatched = []
    for entry in best_decorations_golden["abilities"]:
        ability = teamhgg_game.abilities[entry["ability"]]
        for hr in ranks:
            for elder_star in ranks:
                query = make_query(hr=hr, elder_star=elder_star)
                ours = [
                    _best_decoration_cell(teamhgg_game, ability, max_slots=slots, query=query)
                    for slots in slot_counts
                ]
                if ours != entry["best"][hr - minimum][elder_star - minimum]:
                    mismatched.append((ability.name, hr, elder_star))

    assert mismatched == []


def test_best_decoration_raises_for_an_ability_without_decorations(
    teamhgg_game: GameData, make_query: Callable[..., Query]
):
    """Quirk 8 (Decoration.cpp:110): Auto-Guard has no decorations."""
    auto_guard = next(ability for ability in teamhgg_game.abilities if ability.auto_guard)

    with pytest.raises(NoDecorationsError, match="Auto-Guard"):
        best_decoration_for_query(teamhgg_game, auto_guard, max_slots=3, query=make_query())


def test_best_decoration_keeps_the_first_of_equals(
    attack: Ability, make_query: Callable[..., Query]
):
    first = _decoration("first", slots=1, pairs=[(attack, 1)])
    second = _decoration("second", slots=1, pairs=[(attack, 1)])
    game = GameData(decorations_by_ability={attack: [first, second]})

    best = best_decoration_for_query(game, attack, max_slots=3, query=make_query())

    assert best is first


def test_best_decoration_skips_negative_points(attack: Ability, make_query: Callable[..., Query]):
    negative = _decoration("negative", slots=1, pairs=[(attack, -1)])
    game = GameData(decorations_by_ability={attack: [negative]})

    assert best_decoration_for_query(game, attack, max_slots=3, query=make_query()) is None


@pytest.mark.parametrize(
    ("decoration_fields", "query_fields", "matches"),
    [
        ({}, {}, True),
        ({"is_event": True}, {"allow_event": False}, False),
        ({"is_event": True}, {"allow_event": True}, True),
        ({"hr": 6, "elder_star": 6}, {"hr": 5, "elder_star": 5}, False),
        ({"hr": 6, "elder_star": 6}, {"hr": 6, "elder_star": 1}, True),
        ({"hr": 6, "elder_star": 6}, {"hr": 1, "elder_star": 6}, True),
    ],
)
def test_decoration_matches_when_available(
    attack: Ability,
    make_query: Callable[..., Query],
    decoration_fields: dict,
    query_fields: dict,
    matches: bool,
):
    decoration = _decoration("jewel", slots=1, pairs=[(attack, 1)])
    for key, value in decoration_fields.items():
        setattr(decoration, key, value)
    query = make_query(
        skills=[Skill(name="Attack Up", points_required=10, ability=attack)], **query_fields
    )

    assert decoration_matches_query(decoration, query) is matches


def test_decoration_matches_only_on_its_first_ability(
    attack: Ability, sharpness: Ability, make_query: Callable[..., Query]
):
    decoration = _decoration("jewel", slots=1, pairs=[(sharpness, 1), (attack, 1)])
    query = make_query(skills=[Skill(name="Attack Up", points_required=10, ability=attack)])

    assert not decoration_matches_query(decoration, query)
