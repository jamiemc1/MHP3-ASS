"""Synthetic checks for individual branches of Armor.cpp:105-175, including
ones the shipped data never reaches (danger skills)."""

from __future__ import annotations

from collections.abc import Callable

import pytest

from mhp3ass.armor import armor_is_better_than, armor_matches_query, armor_skill_at
from mhp3ass.model import Ability, Armor, Gender, HunterType
from mhp3ass.query import Query


def test_skill_at_reads_points_or_zero(
    make_armor: Callable[..., Armor], attack: Ability, defense: Ability
):
    piece = make_armor(abilities=[(attack, 3)])

    assert armor_skill_at(piece, attack) == 3
    assert armor_skill_at(piece, defense) == 0


@pytest.mark.parametrize(
    ("piece_fields", "query_fields"),
    [
        ({"is_piercing": True}, {"include_piercings": False}),
        ({"is_event": True}, {"allow_event": False}),
        ({"hr": 3, "elder_star": 1}, {"allow_low_rank": False}),
        ({"hunter_type": HunterType.GUNNER}, {"hunter_type": HunterType.BLADEMASTER}),
        ({"gender": Gender.FEMALE}, {"gender": Gender.MALE}),
        ({"hr": 6, "elder_star": 6}, {"hr": 5, "elder_star": 5}),
    ],
)
def test_requirements_exclude_a_piece_with_skills(
    make_armor: Callable[..., Armor],
    make_query: Callable[..., Query],
    attack: Ability,
    piece_fields: dict,
    query_fields: dict,
):
    piece = make_armor(abilities=[(attack, 2)], **piece_fields)
    query = make_query(rel_abilities=[attack], **query_fields)

    assert not armor_matches_query(piece, query, danger_skills=[], max_slots=0)


@pytest.mark.parametrize(("hr", "elder_star"), [(6, 1), (1, 6)])
def test_either_rank_unlocks_a_piece(
    make_armor: Callable[..., Armor],
    make_query: Callable[..., Query],
    attack: Ability,
    hr: int,
    elder_star: int,
):
    piece = make_armor(abilities=[(attack, 2)], hr=6, elder_star=6)
    query = make_query(rel_abilities=[attack], hr=hr, elder_star=elder_star)

    assert armor_matches_query(piece, query, danger_skills=[], max_slots=0)


def test_relevant_points_match_at_any_slot_count(
    make_armor: Callable[..., Armor], make_query: Callable[..., Query], attack: Ability
):
    piece = make_armor(abilities=[(attack, 2)], num_slots=0)
    piece.no_skills = True

    assert armor_matches_query(
        piece, make_query(rel_abilities=[attack]), danger_skills=[], max_slots=3
    )
    assert piece.no_skills is False


@pytest.mark.parametrize(("num_slots", "matches"), [(1, False), (2, True), (3, True)])
def test_skill_less_piece_needs_the_most_slots_so_far(
    make_armor: Callable[..., Armor],
    make_query: Callable[..., Query],
    attack: Ability,
    defense: Ability,
    num_slots: int,
    matches: bool,
):
    piece = make_armor(abilities=[(defense, 4)], num_slots=num_slots)

    assert (
        armor_matches_query(
            piece, make_query(rel_abilities=[attack]), danger_skills=[], max_slots=2
        )
        is matches
    )
    assert piece.no_skills is True


@pytest.mark.parametrize(("num_slots", "matches"), [(1, False), (2, True), (3, True)])
def test_negative_relevant_points_count_as_skill_less(
    make_armor: Callable[..., Armor],
    make_query: Callable[..., Query],
    attack: Ability,
    num_slots: int,
    matches: bool,
):
    """Quirk 6: bad_skills is never set, so the equal-slots piece is kept (Armor.cpp:140-143)."""
    piece = make_armor(abilities=[(attack, -3)], num_slots=num_slots)

    assert (
        armor_matches_query(
            piece, make_query(rel_abilities=[attack]), danger_skills=[], max_slots=2
        )
        is matches
    )
    assert piece.no_skills is True


@pytest.mark.parametrize("num_slots", [2, 3])
def test_danger_skill_excludes_a_skill_less_piece(
    make_armor: Callable[..., Armor],
    make_query: Callable[..., Query],
    attack: Ability,
    defense: Ability,
    num_slots: int,
):
    """The original's danger list is always empty (LoadedData.cpp:141-158), so this path is
    unreachable from a search; the rule is pinned here."""
    piece = make_armor(abilities=[(defense, -2)], num_slots=num_slots)

    assert not armor_matches_query(
        piece, make_query(rel_abilities=[attack]), danger_skills=[defense], max_slots=2
    )
    assert piece.danger is defense


def test_danger_is_cleared_when_no_danger_skill_applies(
    make_armor: Callable[..., Armor],
    make_query: Callable[..., Query],
    attack: Ability,
    defense: Ability,
):
    piece = make_armor(abilities=[(defense, 2)], num_slots=2)
    piece.danger = defense

    assert armor_matches_query(
        piece, make_query(rel_abilities=[attack]), danger_skills=[defense], max_slots=2
    )
    assert piece.danger is None


def test_torso_up_piece_matches_without_writing_its_flags(
    make_armor: Callable[..., Armor],
    make_query: Callable[..., Query],
    attack: Ability,
    defense: Ability,
):
    piece = make_armor(torso_inc=True, num_slots=0)
    piece.danger = defense

    assert armor_matches_query(
        piece, make_query(rel_abilities=[attack]), danger_skills=[], max_slots=3
    )
    assert piece.danger is defense
    assert piece.no_skills is False


def test_more_slots_and_more_points_are_each_better(
    make_armor: Callable[..., Armor], attack: Ability
):
    slotted = make_armor(num_slots=2, no_skills=True)
    skilled = make_armor(abilities=[(attack, 5)], num_slots=1)

    assert armor_is_better_than(slotted, skilled, rel_abilities=[attack])
    assert armor_is_better_than(skilled, slotted, rel_abilities=[attack])


def test_fewer_slots_and_no_more_points_is_not_better(
    make_armor: Callable[..., Armor], attack: Ability
):
    slotted = make_armor(abilities=[(attack, 5)], num_slots=2)
    skilled = make_armor(abilities=[(attack, 5)], num_slots=1)

    assert not armor_is_better_than(skilled, slotted, rel_abilities=[attack])


@pytest.mark.parametrize(
    ("ours", "theirs", "better", "worse"),
    [
        ({"defence": 12, "rarity": 1}, {"defence": 10, "rarity": 5}, True, False),
        ({"defence": 10, "rarity": 5}, {"defence": 10, "rarity": 1}, True, False),
        ({"defence": 10, "rarity": 1}, {"defence": 10, "rarity": 1}, False, False),
    ],
)
def test_skill_less_pieces_compare_defence_then_rarity(
    make_armor: Callable[..., Armor], ours: dict, theirs: dict, better: bool, worse: bool
):
    piece = make_armor(no_skills=True, **ours)
    other = make_armor(no_skills=True, **theirs)

    assert armor_is_better_than(piece, other, rel_abilities=[]) is better
    assert armor_is_better_than(other, piece, rel_abilities=[]) is worse


@pytest.mark.parametrize(
    ("ours", "theirs", "better", "worse"),
    [
        ({"rarity": 5, "defence": 1}, {"rarity": 3, "defence": 9}, True, False),
        ({"rarity": 3, "defence": 9}, {"rarity": 3, "defence": 1}, True, False),
        ({"rarity": 3, "defence": 9}, {"rarity": 3, "defence": 9}, False, False),
    ],
)
def test_torso_up_pieces_compare_rarity_then_defence(
    make_armor: Callable[..., Armor], ours: dict, theirs: dict, better: bool, worse: bool
):
    piece = make_armor(torso_inc=True, **ours)
    other = make_armor(torso_inc=True, **theirs)

    assert armor_is_better_than(piece, other, rel_abilities=[]) is better
    assert armor_is_better_than(other, piece, rel_abilities=[]) is worse


def test_torso_up_and_skilled_piece_are_each_better(
    make_armor: Callable[..., Armor], attack: Ability
):
    torso_up = make_armor(torso_inc=True)
    skilled = make_armor(abilities=[(attack, 5)])

    assert armor_is_better_than(torso_up, skilled, rel_abilities=[attack])
    assert armor_is_better_than(skilled, torso_up, rel_abilities=[attack])


def test_more_points_in_any_relevant_ability_is_better(
    make_armor: Callable[..., Armor], attack: Ability, defense: Ability
):
    attack_piece = make_armor(abilities=[(attack, 3), (defense, 1)])
    defense_piece = make_armor(abilities=[(attack, 1), (defense, 3)])
    copy = make_armor(abilities=[(attack, 3), (defense, 1)])

    assert armor_is_better_than(attack_piece, defense_piece, rel_abilities=[attack, defense])
    assert armor_is_better_than(defense_piece, attack_piece, rel_abilities=[attack, defense])
    assert not armor_is_better_than(attack_piece, copy, rel_abilities=[attack, defense])
    assert not armor_is_better_than(defense_piece, attack_piece, rel_abilities=[attack])
