from __future__ import annotations

from dataclasses import replace

import pytest

from mhp3ass.model import AbilityPair, Charm
from mhp3ass.results.details import SlotsSpare
from mhp3ass.results.sorting import SortKey
from mhp3ass.results.table import TableRow, fit_widths, spare_text, table_row, truncate
from mhp3ass.solution.state import Solution


@pytest.mark.parametrize(
    ("spare", "text"),
    [
        (None, ""),
        (SlotsSpare(total=1, groups=None), "1"),
        (SlotsSpare(total=3, groups=None), "3"),
        (SlotsSpare(total=4, groups=(1, 1, 2)), "2x1 1x2"),
        (SlotsSpare(total=5, groups=(2, 3)), "1x2 1x3"),
    ],
)
def test_spare_slots_read_as_counts_of_each_size(spare, text):
    assert spare_text(spare) == text


@pytest.fixture
def first_1a_set(teamhgg_game) -> Solution:
    """The pieces of 1b's first listed set, with a two-skill charm and two
    one-slot holes spare."""
    pieces = [
        "Jinouga Helm",
        "Agnaktor Mail",
        "Jinouga Vambraces",
        "Barroth Tasset S",
        "Baggi Greaves S",
    ]
    ability_map = teamhgg_game.ability_map
    solution = Solution(
        armors=[teamhgg_game.armor_map[name] for name in pieces],
        charm=Charm(
            num_slots=1,
            abilities=[
                AbilityPair(ability=ability_map["Attack"], amount=4),
                AbilityPair(ability=ability_map["Sharpness"], amount=3),
            ],
        ),
        defence=412,
        total_slots_spare=2,
        slots_spare=[0, 2, 0, 0],
        fire_res=2,
        water_res=-13,
        thunder_res=7,
        ice_res=-9,
        dragon_res=-3,
    )
    return solution


def test_a_row_has_the_short_pieces_defence_spare_slots_short_charm_and_resistances(
    first_1a_set, teamhgg_short_names
):
    row = table_row(
        first_1a_set, sort_key=SortKey.DEFENCE, names=teamhgg_short_names, query_skills=()
    )

    assert row == TableRow(
        head="Jinouga Helm",
        body="Agnaktor",
        arms="Jinouga",
        waist="Barroth S",
        legs="Baggi S",
        defence="412",
        spare="2x1",
        charm="+4 Att +3 Sharpn (1)",
        fire="2",
        water="-13",
        thunder="7",
        ice="-9",
        dragon="-3",
        extra="",
    )


def test_the_extra_skills_are_those_beyond_the_query_joined_by_commas(
    first_1a_set, teamhgg_game, teamhgg_short_names
):
    skills = teamhgg_game.skill_map
    attack, sharp, guard = skills["Attack Up [Med]"], skills["Sharp Sword"], skills["Guard +1"]
    solution = replace(first_1a_set, extra_skills=[attack, guard, sharp])

    row = table_row(
        solution, sort_key=SortKey.NONE, names=teamhgg_short_names, query_skills=[attack]
    )

    assert row.extra == "Guard +1, Sharp Sword"


def test_an_empty_slot_and_no_charm_are_blank(teamhgg_short_names):
    solution = Solution(armors=[None] * 5, charm=None, defence=0)

    row = table_row(solution, sort_key=SortKey.NONE, names=teamhgg_short_names, query_skills=())

    assert (row.head, row.legs, row.charm, row.spare, row.extra) == ("", "", "", "", "")


@pytest.mark.parametrize(
    ("text", "width", "cut"),
    [
        ("Barroth S", 9, "Barroth S"),
        ("Barroth S", 20, "Barroth S"),
        ("Barroth S", 6, "Barro…"),
        ("ハプルＳヘルム", 6, "ハプ…"),
        ("ハプルＳヘルム", 7, "ハプル…"),
    ],
)
def test_truncate_cuts_to_the_width_in_cells_with_an_ellipsis(text, width, cut):
    assert truncate(text, width) == cut


def test_truncate_drops_a_space_before_the_ellipsis():
    assert truncate("Golden Moon", 8) == "Golden…"


def test_widths_that_fit_are_kept():
    fitted = fit_widths(
        [3, 10, 12, 40], available=25, must_fit=frozenset({0, 1, 2}), fixed=frozenset({0})
    )

    assert fitted == [3, 10, 12, 40]


def test_the_widest_must_fit_columns_are_cut_first_to_a_common_cap():
    fitted = fit_widths(
        [3, 20, 8, 14, 30], available=33, must_fit=frozenset({0, 1, 2, 3}), fixed=frozenset({0})
    )

    assert fitted == [3, 11, 8, 11, 30]


def test_fixed_and_narrow_columns_keep_their_width():
    fitted = fit_widths(
        [5, 4, 20, 3], available=20, must_fit=frozenset({0, 1, 2, 3}), fixed=frozenset({0})
    )

    assert fitted == [5, 4, 8, 3]


def test_no_column_is_cut_below_six_so_the_must_fit_columns_can_stay_too_wide():
    fitted = fit_widths(
        [3, 20, 20, 20], available=20, must_fit=frozenset({0, 1, 2, 3}), fixed=frozenset({0})
    )

    assert fitted == [3, 6, 6, 6]
    assert sum(fitted) > 20
