from __future__ import annotations

import pytest

from mhp3ass.data import GameData
from mhp3ass.skill_chips import add_chip, addable_skills, chip_rows, remove_chip
from mhp3ass.skill_picker import SkillRow, query_skills, skill_choices


@pytest.fixture
def attack_and_sharp_sword_rows(teamhgg_game: GameData) -> tuple[SkillRow, ...]:
    """Rows with Attack Up [Med] then Sharp Sword chosen."""
    rows = chip_rows(
        [teamhgg_game.skill_map["Attack Up [Med]"], teamhgg_game.skill_map["Sharp Sword"]]
    )
    return rows


@pytest.fixture
def six_skill_rows(teamhgg_game: GameData) -> tuple[SkillRow, ...]:
    """Rows with six skills of six different abilities, in skill-list order."""
    skills = []
    for skill in skill_choices(teamhgg_game, filter_index=0, disallowed=[]):
        if all(skill.ability is not chosen.ability for chosen in skills):
            skills.append(skill)
        if len(skills) == 6:
            break
    rows = chip_rows(skills)
    return rows


def test_chip_rows_fill_in_order_then_pad_with_empty_rows(teamhgg_game):
    attack = teamhgg_game.skill_map["Attack Up [Med]"]

    rows = chip_rows([attack])

    assert rows == (
        SkillRow(filter_index=0, skill=attack),
        *(SkillRow(filter_index=0, skill=None) for _ in range(5)),
    )


def test_more_skills_than_rows_raise(teamhgg_game):
    attack = teamhgg_game.skill_map["Attack Up [Med]"]

    with pytest.raises(ValueError, match="2 skills don't fit in 1 skill rows"):
        chip_rows([attack, attack], row_count=1)


def test_no_chosen_skills_and_no_text_offer_what_a_row_filtered_by_all_offers(teamhgg_game):
    skills = addable_skills(teamhgg_game, chip_rows([]), tag_index=0, text="")

    assert skills == skill_choices(teamhgg_game, filter_index=0, disallowed=[])


def test_a_chosen_ability_isnt_offered_again(teamhgg_game, attack_and_sharp_sword_rows):
    skills = addable_skills(teamhgg_game, attack_and_sharp_sword_rows, tag_index=0, text="")

    assert teamhgg_game.skill_map["Attack Up [Sm]"] not in skills
    assert teamhgg_game.skill_map["Attack Up [Lg]"] not in skills
    assert teamhgg_game.skill_map["Sharp Sword"] not in skills


def test_the_text_matches_inside_names_ignoring_case(teamhgg_game):
    skills = addable_skills(teamhgg_game, chip_rows([]), tag_index=0, text="  attack up ")

    assert [skill.name for skill in skills] == [
        "Attack Up [Sm]",
        "Attack Up [Med]",
        "Attack Up [Lg]",
    ]


def test_text_no_name_contains_offers_nothing(teamhgg_game):
    skills = addable_skills(teamhgg_game, chip_rows([]), tag_index=0, text="no such skill")

    assert skills == []


def test_the_tag_narrows_as_a_rows_filter_does(teamhgg_game, attack_and_sharp_sword_rows):
    offensive = 2
    chosen = [skill.ability for skill in query_skills(attack_and_sharp_sword_rows)]

    skills = addable_skills(teamhgg_game, attack_and_sharp_sword_rows, tag_index=offensive, text="")

    assert skills == skill_choices(teamhgg_game, filter_index=offensive, disallowed=chosen)
    every_tag = addable_skills(teamhgg_game, attack_and_sharp_sword_rows, tag_index=0, text="")
    assert len(skills) < len(every_tag)


def test_a_chip_goes_after_the_chosen_skills(teamhgg_game, attack_and_sharp_sword_rows):
    guard = teamhgg_game.skill_map["Guard +1"]

    rows = add_chip(teamhgg_game, attack_and_sharp_sword_rows, guard)

    assert [skill.name for skill in query_skills(rows)] == [
        "Attack Up [Med]",
        "Sharp Sword",
        "Guard +1",
    ]
    assert len(rows) == 6


def test_a_skill_of_a_chosen_ability_cant_be_added(teamhgg_game, attack_and_sharp_sword_rows):
    with pytest.raises(ValueError, match=r"Attack Up \[Lg\] isn't offered"):
        add_chip(
            teamhgg_game, attack_and_sharp_sword_rows, teamhgg_game.skill_map["Attack Up [Lg]"]
        )


def test_a_seventh_skill_cant_be_added(teamhgg_game, six_skill_rows):
    chosen = [skill.ability for skill in query_skills(six_skill_rows)]
    unchosen = skill_choices(teamhgg_game, filter_index=0, disallowed=chosen)[0]

    with pytest.raises(ValueError, match="all 6 skill rows are taken"):
        add_chip(teamhgg_game, six_skill_rows, unchosen)


def test_removing_a_chip_moves_the_later_ones_up(teamhgg_game, attack_and_sharp_sword_rows):
    rows = remove_chip(attack_and_sharp_sword_rows, chip=0)

    assert rows == chip_rows([teamhgg_game.skill_map["Sharp Sword"]])


def test_removing_the_last_chip_leaves_the_others(teamhgg_game, attack_and_sharp_sword_rows):
    rows = remove_chip(attack_and_sharp_sword_rows, chip=1)

    assert rows == chip_rows([teamhgg_game.skill_map["Attack Up [Med]"]])


@pytest.mark.parametrize("chip", [-1, 2])
def test_removing_a_chip_that_isnt_there_raises(attack_and_sharp_sword_rows, chip):
    with pytest.raises(ValueError, match=f"chip {chip} isn't one of the 2 chosen skills"):
        remove_chip(attack_and_sharp_sword_rows, chip=chip)
