from __future__ import annotations

import pytest

from mhp3ass.editor_rows import (
    GroupSpacing,
    chip_label,
    chip_width,
    chips_cells,
    chips_share_row,
    group_spacing,
    select_width,
)


def test_a_drop_down_is_its_longest_label_and_four_cells():
    width = select_width(["Blademaster", "Gunner"])

    assert width == 15


def test_a_drop_down_counts_wide_characters_as_two_cells():
    width = select_width(["剣士", "ガンナー"])

    assert width == 12


def test_a_drop_down_with_no_labels_has_room_for_its_arrow_alone():
    width = select_width([])

    assert width == 4


def test_the_chips_share_the_row_when_they_fit_exactly():
    shared = chips_share_row(chips=[10, 12], fields=40, room=11 + 13 + 40)

    assert shared


def test_the_chips_move_to_a_row_of_their_own_one_cell_past_the_room():
    shared = chips_share_row(chips=[10, 12], fields=40, room=11 + 13 + 40 - 1)

    assert not shared


def test_no_chips_share_the_row_whenever_the_fields_fit():
    shared = chips_share_row(chips=[], fields=40, room=40)

    assert shared


def test_a_chip_is_its_name_the_cross_and_a_cell_either_side():
    assert chip_width("Attack Up [Med]") == 19


def test_a_chip_counts_wide_characters_as_two_cells():
    assert chip_width("攻撃力") == 10


def test_a_chip_reads_as_the_skill_and_a_cross():
    assert chip_label("Sharp Sword") == "Sharp Sword ✕"


def test_the_chips_take_their_widths_and_a_cell_after_each():
    assert chips_cells([10, 12]) == 24


def test_no_chips_take_no_cells():
    assert chips_cells([]) == 0


def test_groups_with_no_rows_to_spare_have_no_gaps():
    spacing = group_spacing(room=10, content=10, gaps=3)

    assert spacing == GroupSpacing(above=0, between=(0, 0, 0))


def test_groups_taller_than_the_room_have_no_gaps():
    spacing = group_spacing(room=7, content=12, gaps=3)

    assert spacing == GroupSpacing(above=0, between=(0, 0, 0))


def test_rows_that_dont_share_out_evenly_go_to_the_first_gaps():
    spacing = group_spacing(room=15, content=10, gaps=3)

    assert spacing == GroupSpacing(above=0, between=(2, 2, 1))


def test_a_single_spare_row_opens_the_first_gap():
    spacing = group_spacing(room=11, content=10, gaps=3)

    assert spacing == GroupSpacing(above=0, between=(1, 0, 0))


def test_the_gaps_stop_growing_at_their_most_and_the_block_is_centred():
    spacing = group_spacing(room=30, content=10, gaps=3, most=2)

    assert spacing == GroupSpacing(above=7, between=(2, 2, 2))


def test_the_gaps_reach_their_most_exactly_with_nothing_left_to_centre():
    spacing = group_spacing(room=16, content=10, gaps=3, most=2)

    assert spacing == GroupSpacing(above=0, between=(2, 2, 2))


def test_an_odd_row_left_over_goes_below_the_block():
    spacing = group_spacing(room=17, content=10, gaps=3, most=2)

    assert spacing == GroupSpacing(above=0, between=(2, 2, 2))


def test_groups_need_a_gap_between_them():
    with pytest.raises(ValueError, match="at least one gap"):
        group_spacing(room=10, content=5, gaps=0)


def test_a_list_that_fits_below_the_block_moves_nothing():
    spacing = group_spacing(room=30, content=10, gaps=3, opened=6)

    assert spacing == GroupSpacing(above=7, between=(2, 2, 2))


def test_a_list_past_the_rows_below_takes_the_last_gap_next():
    # Spare 14: gaps 2, 2, 2, then 4 above and 4 below.
    spacing = group_spacing(room=24, content=10, gaps=3, opened=5)

    assert spacing == GroupSpacing(above=4, between=(2, 2, 1))


def test_a_list_past_the_last_gap_takes_the_rows_above_the_block():
    spacing = group_spacing(room=24, content=10, gaps=3, opened=8)

    assert spacing == GroupSpacing(above=2, between=(2, 2, 0))


def test_a_list_past_the_rows_above_closes_the_other_gaps_last_first():
    spacing = group_spacing(room=24, content=10, gaps=3, opened=13)

    assert spacing == GroupSpacing(above=0, between=(1, 0, 0))


def test_a_list_taller_than_every_spare_row_leaves_no_gaps():
    spacing = group_spacing(room=24, content=10, gaps=3, opened=20)

    assert spacing == GroupSpacing(above=0, between=(0, 0, 0))
