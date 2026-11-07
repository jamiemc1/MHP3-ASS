"""Decoration comparisons against the harness's IsBetterThan dump (ModelDump.cpp)."""

from __future__ import annotations

import pytest

from mhp3ass.decorations import decoration_is_better_than, decoration_skill_at
from mhp3ass.model import Ability, AbilityPair, Decoration


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
def attack():
    return Ability(name="Attack", static_index=0)


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
