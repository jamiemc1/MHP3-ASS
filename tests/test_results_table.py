from __future__ import annotations

import pytest

from mhp3ass.model import AbilityPair, Charm
from mhp3ass.results.details import SlotsSpare
from mhp3ass.results.sorting import SortKey
from mhp3ass.results.table import TableRow, spare_text, table_row
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
    )
    return solution


def test_a_row_has_the_pieces_defence_spare_slots_and_charm(first_1a_set):
    row = table_row(first_1a_set, sort_key=SortKey.DEFENCE)

    assert row == TableRow(
        head="Jinouga Helm",
        body="Agnaktor Mail",
        arms="Jinouga Vambraces",
        waist="Barroth Tasset S",
        legs="Baggi Greaves S",
        defence="412",
        spare="2x1",
        charm="+4 Attack, +3 Sharpness O--",
    )


def test_an_empty_slot_and_no_charm_are_blank():
    solution = Solution(armors=[None] * 5, charm=None, defence=0)

    row = table_row(solution, sort_key=SortKey.NONE)

    assert (row.head, row.legs, row.charm, row.spare) == ("", "", "", "")
