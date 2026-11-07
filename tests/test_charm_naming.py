"""Charm copies, names, value equality and hashes (Armor.cpp:216-341)."""

from __future__ import annotations

from typing import Any

import pytest

from mhp3ass.charms.naming import charm_hash, charm_name, charms_equal, hash_function
from mhp3ass.data import GameData
from mhp3ass.model import Ability, AbilityPair, Charm


@pytest.fixture
def attack():
    return Ability(name="Attack", static_index=0)


@pytest.fixture
def sharpness():
    return Ability(name="Sharpness", static_index=5)


@pytest.fixture
def two_skill_charm(attack, sharpness):
    charm = Charm(
        num_slots=2,
        abilities=[
            AbilityPair(ability=attack, amount=4),
            AbilityPair(ability=sharpness, amount=-2),
        ],
        custom=True,
        hacked=True,
    )
    return charm


def test_copy_is_deep_and_drops_hacked(two_skill_charm):
    copied = two_skill_charm.copy()
    copied.abilities[0].amount = 9

    assert [two_skill_charm.abilities[0].amount, copied.custom, copied.hacked] == [4, True, False]


@pytest.mark.parametrize(
    ("amounts", "slots", "expected"),
    [
        ([], 3, "OOO"),
        ([3], 1, "+3 Attack O--"),
        ([4, 2], 2, "+4 Attack, +2 Sharpness OO-"),
        ([4, -2], 0, "+4 Attack, -2 Sharpness ---"),
        ([-1], 0, "+-1 Attack ---"),
    ],
)
def test_charm_name_matches_get_name(attack, sharpness, amounts, slots, expected):
    pairs = [
        AbilityPair(ability=ability, amount=amount)
        for ability, amount in zip([attack, sharpness], amounts, strict=False)
    ]

    assert charm_name(Charm(num_slots=slots, abilities=pairs)) == expected


def test_charms_equal_ignores_amounts(two_skill_charm):
    other = two_skill_charm.copy()
    other.abilities[1].amount = 7

    assert charms_equal(two_skill_charm, other)


def test_charms_equal_needs_same_abilities_in_order(two_skill_charm):
    swapped = two_skill_charm.copy()
    swapped.abilities.reverse()

    assert not charms_equal(two_skill_charm, swapped)


def test_hash_packs_fields_into_bit_ranges(attack, sharpness):
    hashed = hash_function(
        num_slots=2, ability1=sharpness, points1=3, ability2=attack, points2=4, ability_count=100
    )

    assert hashed == 2 + (3 << 2) + ((4 + 12) << 6) + (5 << 11) + (0 << 18)


def test_hash_without_abilities_uses_ability_count():
    hashed = hash_function(
        num_slots=1, ability1=None, points1=7, ability2=None, points2=7, ability_count=100
    )

    assert hashed == 1 + (12 << 6) + (100 << 11) + (100 << 18)


def test_hash_wraps_negative_points_like_unsigned(attack):
    hashed = hash_function(
        num_slots=0, ability1=attack, points1=-1, ability2=None, points2=0, ability_count=100
    )

    assert hashed == (-4 + (12 << 6) + (100 << 18)) % 2**32


def _golden_two_skill_charms(golden: Any, game: GameData) -> list[tuple[str, Charm]]:
    named = []
    for entry in golden["two_skill_charms"]:
        for charm in entry["charms"]:
            pairs = [
                AbilityPair(ability=game.abilities[pair["ability"]], amount=pair["amount"])
                for pair in charm["abilities"]
            ]
            named.append((charm["name"], Charm(num_slots=charm["num_slots"], abilities=pairs)))
    return named


def test_names_match_golden_two_skill_charms(charm_database_golden, teamhgg_game):
    named = _golden_two_skill_charms(charm_database_golden, teamhgg_game)
    misnamed = [name for name, charm in named if charm_name(charm) != name]

    assert [len(named) > 0, misnamed] == [True, []]


def test_golden_two_skill_charms_hash_into_charm_hashes(charm_database_golden, teamhgg_game):
    known = set(charm_database_golden["charm_hashes"])
    ability_count = len(teamhgg_game.abilities)
    unknown = [
        name
        for name, charm in _golden_two_skill_charms(charm_database_golden, teamhgg_game)
        if charm_hash(charm, ability_count) not in known
    ]

    assert unknown == []


def test_auto_guard_hash_is_in_charm_hashes(charm_database_golden, teamhgg_game):
    auto_guard = next(ability for ability in teamhgg_game.abilities if ability.auto_guard)
    hashed = hash_function(
        num_slots=0,
        ability1=auto_guard,
        points1=10,
        ability2=None,
        points2=0,
        ability_count=len(teamhgg_game.abilities),
    )

    assert hashed in charm_database_golden["charm_hashes"]
