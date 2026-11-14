from __future__ import annotations

import pytest

from mhp3ass.column_window import (
    ColumnWindow,
    column_window,
    last_first,
    scrolled_columns,
    spare_cells,
)


@pytest.fixture
def table_widths():
    """The sets table's columns: #, five pieces, Def, Spare and Charm."""
    widths = [5, 10, 10, 10, 10, 10, 3, 5, 20]
    return widths


@pytest.fixture
def pinned():
    """# and Def."""
    columns = frozenset({0, 6})
    return columns


def _line_cells(widths, window):
    """The cells a line showing ``window`` takes."""
    shown = [*window.pinned, *window.scrolled]
    cells = sum(widths[column] for column in shown) + spare_cells(
        len(window.pinned), scrolled=len(window.scrolled)
    )
    return cells


def test_spare_cells_counts_the_spaces_gaps_and_markers():
    # " " + "#" + "  " + "Def" + " < " + 3 columns two apart + " >".
    assert spare_cells(2, scrolled=3) == 1 + 2 + 3 + 4 + 2


def test_spare_cells_with_one_column_each_side_has_no_gaps():
    assert spare_cells(1, scrolled=1) == 1 + 3 + 2


def test_scrolled_columns_skip_the_pinned_ones_in_order(pinned):
    assert scrolled_columns(9, pinned, hidden=frozenset()) == [1, 2, 3, 4, 5, 7, 8]


def test_a_wide_enough_line_shows_every_column(table_widths, pinned):
    window = column_window(table_widths, pinned=pinned, hidden=frozenset(), first=0, width=200)

    assert window == ColumnWindow(
        pinned=(0, 6),
        scrolled=(1, 2, 3, 4, 5, 7, 8),
        first=0,
        more_left=False,
        more_right=False,
    )


def test_a_narrow_line_shows_whole_columns_and_marks_the_rest(table_widths, pinned):
    # Pinned 8 + spare 8 leave 46: four 10-wide columns two apart take 46.
    window = column_window(table_widths, pinned=pinned, hidden=frozenset(), first=0, width=62)

    assert window.scrolled == (1, 2, 3, 4)
    assert window.more_right
    assert not window.more_left
    assert _line_cells(table_widths, window) <= 62


def test_one_cell_narrower_drops_a_whole_column(table_widths, pinned):
    window = column_window(table_widths, pinned=pinned, hidden=frozenset(), first=0, width=61)

    assert window.scrolled == (1, 2, 3)


def test_scrolling_starts_the_window_further_right(table_widths, pinned):
    window = column_window(table_widths, pinned=pinned, hidden=frozenset(), first=2, width=62)

    assert window.scrolled == (3, 4, 5, 7)
    assert window.more_left
    assert window.more_right


def test_last_first_is_where_the_last_column_comes_into_view(table_widths, pinned):
    first = last_first(table_widths, pinned=pinned, hidden=frozenset(), width=62)
    window = column_window(table_widths, pinned=pinned, hidden=frozenset(), first=first, width=62)

    # 10 + 5 + 20 and two gaps fit 46; one more 10-wide column doesn't.
    assert first == 4
    assert window.scrolled == (5, 7, 8)
    assert not window.more_right


def test_scrolling_past_the_end_stops_at_last_first(table_widths, pinned):
    window = column_window(table_widths, pinned=pinned, hidden=frozenset(), first=99, width=62)

    assert window.scrolled == (5, 7, 8)
    assert window.first == 4


def test_scrolling_before_the_start_stops_at_the_first_column(table_widths, pinned):
    window = column_window(table_widths, pinned=pinned, hidden=frozenset(), first=-3, width=62)

    assert window.scrolled[0] == 1
    assert window.first == 0
    assert not window.more_left


def test_last_first_is_zero_when_everything_fits(table_widths, pinned):
    assert last_first(table_widths, pinned=pinned, hidden=frozenset(), width=200) == 0


def test_a_column_wider_than_the_room_still_shows_alone(pinned):
    widths = [5, 10, 10, 10, 10, 10, 3, 5, 80]

    window = column_window(widths, pinned=pinned, hidden=frozenset(), first=99, width=62)

    assert window.scrolled == (8,)
    assert window.more_left
    assert not window.more_right


def test_last_first_with_a_too_wide_last_column_is_that_column(pinned):
    widths = [5, 10, 10, 10, 10, 10, 3, 5, 80]

    assert last_first(widths, pinned=pinned, hidden=frozenset(), width=62) == 6


def test_scrolled_columns_skip_the_hidden_ones(pinned):
    assert scrolled_columns(9, pinned, hidden=frozenset({7, 8})) == [1, 2, 3, 4, 5]


def test_hidden_columns_neither_show_nor_count_as_off_screen(table_widths, pinned):
    window = column_window(
        table_widths, pinned=pinned, hidden=frozenset({7, 8}), first=0, width=200
    )

    assert window.scrolled == (1, 2, 3, 4, 5)
    assert not window.more_right


def test_the_furthest_scroll_ignores_hidden_columns(table_widths, pinned):
    first = last_first(table_widths, pinned=pinned, hidden=frozenset({8}), width=62)
    window = column_window(
        table_widths, pinned=pinned, hidden=frozenset({8}), first=first, width=62
    )

    # 10 + 10 + 10 + 5 and three gaps fit 46; the charm, hidden, isn't reached for.
    assert window.scrolled == (3, 4, 5, 7)
    assert not window.more_right
