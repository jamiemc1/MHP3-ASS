from __future__ import annotations

from mhp3ass.editor_rows import chip_label, chip_width, chips_cells, chips_share_row, select_width


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
    shared = chips_share_row(label=7, chips=[10, 12], fields=40, room=7 + 11 + 13 + 40)

    assert shared


def test_the_chips_move_to_a_row_of_their_own_one_cell_past_the_room():
    shared = chips_share_row(label=7, chips=[10, 12], fields=40, room=7 + 11 + 13 + 40 - 1)

    assert not shared


def test_no_chips_share_the_row_whenever_the_label_and_fields_fit():
    shared = chips_share_row(label=7, chips=[], fields=40, room=47)

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
