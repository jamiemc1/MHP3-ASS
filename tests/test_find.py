"""Find over the results table's rows: case-insensitive, wrapping round."""

from __future__ import annotations

import pytest

from mhp3ass.model import AbilityPair, Charm
from mhp3ass.results.find import find_row, row_text
from mhp3ass.solution.state import Solution


@pytest.fixture
def row_texts() -> list[str]:
    """Four rows: Jinouga in rows 0 and 2, Rathalos in row 1, nothing shared in row 3."""
    texts = [
        "Jinouga Helm\nAttack Jewel[2]",
        "Rathalos Helm\nRazor Jewel[1]",
        "Kirin Helm\nJinouga Vambraces",
        "Barroth Helm",
    ]
    return texts


def test_find_moves_to_the_next_matching_row(row_texts):
    assert find_row(row_texts, needle="jinouga", start=0) == 2


def test_find_wraps_to_the_first_matching_row(row_texts):
    assert find_row(row_texts, needle="jinouga", start=2) == 0


def test_find_backwards_moves_to_the_previous_matching_row(row_texts):
    assert find_row(row_texts, needle="JINOUGA", start=0, step=-1) == 2


def test_the_only_matching_row_is_found_again(row_texts):
    assert find_row(row_texts, needle="razor", start=1) == 1


def test_no_matching_row_finds_nothing(row_texts):
    assert find_row(row_texts, needle="Ukanlos", start=0) is None


def test_an_empty_needle_finds_no_row(row_texts):
    assert find_row(row_texts, needle="", start=0) is None


def test_a_match_does_not_run_across_two_names(row_texts):
    assert find_row(row_texts, needle="HelmAttack", start=1) is None


@pytest.mark.parametrize(("start", "step"), [(4, 1), (-1, 1), (0, 2)])
def test_a_start_off_the_rows_or_a_bad_step_raises(row_texts, start, step):
    with pytest.raises(ValueError, match=r"isn't one of the 4 rows|steps 1 or -1"):
        find_row(row_texts, needle="Helm", start=start, step=step)


def test_a_rows_text_has_its_pieces_jewels_charm_and_extra_skills(teamhgg_game, make_query):
    solution = Solution(
        armors=[teamhgg_game.armor_map["Jinouga Helm"], None, None, None, None],
        charm=Charm(
            num_slots=0,
            abilities=[AbilityPair(ability=teamhgg_game.ability_map["Attack"], amount=4)],
        ),
    )
    solution.decorations = [teamhgg_game.decorations[0]]
    solution.extra_skills = [teamhgg_game.skill_map["Guard +1"]]

    text = row_text(solution, query=make_query())

    assert text.split("\n") == [
        "Jinouga Helm",
        teamhgg_game.decorations[0].name,
        "+4 Attack ---",
        "Guard +1",
    ]


def test_a_rows_text_leaves_out_extra_skills_the_query_asked_for(teamhgg_game, make_query):
    guard = teamhgg_game.skill_map["Guard +1"]
    solution = Solution(
        armors=[teamhgg_game.armor_map["Jinouga Helm"], None, None, None, None], charm=None
    )
    solution.extra_skills = [guard]

    text = row_text(solution, query=make_query(skills=[guard]))

    assert text == "Jinouga Helm"


def test_with_short_names_a_rows_text_has_the_cells_the_table_shows(
    teamhgg_game, teamhgg_short_names, make_query
):
    solution = Solution(
        armors=[None, None, None, teamhgg_game.armor_map["Barroth Tasset S"], None],
        charm=Charm(
            num_slots=1,
            abilities=[AbilityPair(ability=teamhgg_game.ability_map["Attack"], amount=4)],
        ),
    )

    text = row_text(solution, query=make_query(), short_names=teamhgg_short_names)

    assert text.split("\n") == ["Barroth Tasset S", "+4 Attack O--", "Barroth S", "+4 Att (1)"]
    assert find_row([text], needle="barroth s", start=0) == 0
