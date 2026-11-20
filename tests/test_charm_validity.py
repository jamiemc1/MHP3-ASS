"""Charm validity against the harness's CharmExists / CharmIsIllegal dump (ModelDump.cpp)."""

from __future__ import annotations

from typing import Any

import pytest

from mhp3ass.charms.generation import CharmTables
from mhp3ass.charms.naming import charm_hash
from mhp3ass.charms.validity import build_charm_validity, decode_charm_hash, generated_charm
from mhp3ass.data import GameData
from mhp3ass.model import AbilityPair, Charm


def _golden_charm(case: dict[str, Any], game: GameData) -> Charm:
    pairs = [
        AbilityPair(ability=game.abilities[pair["ability"]], amount=pair["amount"])
        for pair in case["abilities"]
    ]
    charm = Charm(num_slots=case["num_slots"], abilities=pairs)
    return charm


def test_validity_matches_golden_for_every_case(models_golden, teamhgg_game, validity):
    ability_count = len(teamhgg_game.abilities)
    mismatched = []
    for number, case in enumerate(models_golden["charm_validity"]):
        charm = _golden_charm(case, teamhgg_game)
        ours = {
            "hash": charm_hash(charm, ability_count),
            "exists": validity.exists(charm),
            "illegal": validity.is_illegal(charm),
        }
        golden = {key: case[key] for key in ours}
        if ours != golden:
            mismatched.append({"case": number, "ours": ours, "golden": golden})

    assert [len(models_golden["charm_validity"]) > 1000, mismatched[:5]] == [True, []]


def test_golden_covers_each_validity_outcome(models_golden):
    outcomes = {(case["exists"], case["illegal"]) for case in models_golden["charm_validity"]}

    assert outcomes == {(True, False), (False, True), (False, False), (True, True)}


@pytest.fixture
def tables_with_one_attack_charm(teamhgg_game):
    """Generated tables holding a single 0-slot charm: +5 Attack, with no second skill."""
    attack = teamhgg_game.abilities[0]
    ability_count = len(teamhgg_game.abilities)
    hashed = charm_hash(
        Charm(num_slots=0, abilities=[AbilityPair(ability=attack, amount=5)]), ability_count
    )
    table_hashes = [[[[] for _ in range(4)] for _ in range(3)] for _ in range(12)]
    table_hashes[0][0][0].append(hashed)
    tables = CharmTables(
        max_points=[[{} for _ in range(4)] for _ in range(3)],
        two_skill={},
        charm_hashes=[hashed],
        table_hashes=table_hashes,
    )
    return tables


def test_negative_first_skill_compares_unsigned(tables_with_one_attack_charm, teamhgg_game):
    # Signed, -1 <= 5 would make -1 Attack legal; the original holds -1 as 0xFFFFFFFF.
    validity = build_charm_validity(
        tables_with_one_attack_charm, ability_count=len(teamhgg_game.abilities)
    )
    attack = teamhgg_game.abilities[0]
    negative = Charm(num_slots=0, abilities=[AbilityPair(ability=attack, amount=-1)])
    positive = Charm(num_slots=0, abilities=[AbilityPair(ability=attack, amount=4)])

    assert [validity.is_illegal(negative), validity.is_illegal(positive)] == [True, False]


def test_four_slots_raise_like_the_original(validity):
    with pytest.raises(IndexError):
        validity.is_illegal(Charm(num_slots=4))


def test_possible_charms_follow_each_golden_outcome(models_golden, teamhgg_game, validity):
    # A known hash is possible even when CharmIsIllegal says otherwise: (True, True).
    possible_by_outcome: dict[tuple[bool, bool], set[bool]] = {}
    for case in models_golden["charm_validity"]:
        charm = _golden_charm(case, teamhgg_game)
        outcome = (case["exists"], case["illegal"])
        possible_by_outcome.setdefault(outcome, set()).add(validity.is_possible(charm))

    assert possible_by_outcome == {
        (True, False): {True},
        (True, True): {True},
        (False, False): {True},
        (False, True): {False},
    }


def test_slot_only_charms_are_possible_where_a_charm_has_their_slots(
    tables_with_one_attack_charm, teamhgg_game
):
    validity = build_charm_validity(
        tables_with_one_attack_charm, ability_count=len(teamhgg_game.abilities)
    )

    assert [validity.is_possible(Charm(num_slots=0)), validity.is_possible(Charm(num_slots=1))] == [
        True,
        False,
    ]


def test_possible_raises_for_an_unknown_charm_with_four_slots(validity):
    with pytest.raises(IndexError):
        validity.is_possible(Charm(num_slots=4))


def test_possible_skips_the_illegal_check_for_a_known_hash(teamhgg_game):
    # A four-slot charm would raise in is_illegal; a known hash must not get that far.
    ability_count = len(teamhgg_game.abilities)
    four_slots = Charm(num_slots=4)
    tables = CharmTables(
        max_points=[[{} for _ in range(4)] for _ in range(3)],
        two_skill={},
        charm_hashes=[charm_hash(four_slots, ability_count)],
        table_hashes=[[[[] for _ in range(4)] for _ in range(3)] for _ in range(12)],
    )
    validity = build_charm_validity(tables, ability_count=ability_count)

    assert validity.is_possible(four_slots) is True


def test_decode_reverses_hash_fields(teamhgg_game):
    attack, expert = teamhgg_game.abilities[0], teamhgg_game.abilities[1]
    charm = Charm(
        num_slots=2,
        abilities=[AbilityPair(ability=attack, amount=7), AbilityPair(ability=expert, amount=-3)],
    )
    decoded = decode_charm_hash(charm_hash(charm, len(teamhgg_game.abilities)))

    assert [decoded.ability1_index, decoded.ability2_index, decoded.points1, decoded.points2] == [
        attack.static_index,
        expert.static_index,
        7,
        -3,
    ]


def test_every_generated_hash_rebuilds_a_charm_that_exists(charm_tables, teamhgg_game, validity):
    ability_count = len(teamhgg_game.abilities)
    rebuilt = [generated_charm(hashed, teamhgg_game) for hashed in charm_tables.charm_hashes]
    not_round_tripped = [
        hashed
        for hashed, charm in zip(charm_tables.charm_hashes, rebuilt, strict=True)
        if charm_hash(charm, ability_count) != hashed or not validity.exists(charm)
    ]
    shapes = {(charm.num_slots, len(charm.abilities)) for charm in rebuilt}

    assert not_round_tripped == []
    assert shapes == {(slots, count) for slots in range(4) for count in (1, 2)}


def test_decode_reads_the_slot_bits(teamhgg_game):
    attack = teamhgg_game.abilities[0]
    charm = Charm(num_slots=3, abilities=[AbilityPair(ability=attack, amount=2)])
    decoded = decode_charm_hash(charm_hash(charm, len(teamhgg_game.abilities)))

    assert [decoded.num_slots, decoded.ability2_index, decoded.points2] == [
        3,
        len(teamhgg_game.abilities),
        0,
    ]
