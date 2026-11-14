from __future__ import annotations

import pytest

from mhp3ass.spatial import Direction, FieldBox, neighbour


@pytest.fixture
def editor_rows():
    """The editor's shape: hunter, gender, HR, village (1-4); weapon slots,
    charm mode, Search (5-7); two chips (8-9); the skill box and its tag
    (10-11); the offered skills (12). One row is listed out of order."""
    rows = [
        [FieldBox(1, x=0, width=16), FieldBox(2, x=17, width=10), FieldBox(3, x=31, width=6),
         FieldBox(4, x=53, width=6)],
        [FieldBox(7, x=64, width=10), FieldBox(5, x=18, width=6), FieldBox(6, x=32, width=30)],
        [FieldBox(8, x=8, width=20), FieldBox(9, x=30, width=14)],
        [FieldBox(10, x=0, width=40), FieldBox(11, x=42, width=22)],
        [FieldBox(12, x=2, width=64)],
    ]  # fmt: skip
    return rows


@pytest.mark.parametrize(
    ("current", "direction", "expected"),
    [
        (2, Direction.LEFT, 1),
        (2, Direction.RIGHT, 3),
        (5, Direction.RIGHT, 6),
        (6, Direction.RIGHT, 7),
        (7, Direction.LEFT, 6),
    ],
)
def test_left_and_right_move_along_the_row_in_screen_order(
    editor_rows, current, direction, expected
):
    assert neighbour(editor_rows, current=current, direction=direction) == expected


@pytest.mark.parametrize(
    ("current", "direction"),
    [(1, Direction.LEFT), (4, Direction.RIGHT), (12, Direction.LEFT), (12, Direction.RIGHT)],
)
def test_past_either_end_of_a_row_the_focus_stays(editor_rows, current, direction):
    assert neighbour(editor_rows, current=current, direction=direction) is None


@pytest.mark.parametrize(
    ("current", "direction", "expected"),
    [
        (1, Direction.DOWN, 5),
        (4, Direction.DOWN, 6),
        (7, Direction.UP, 4),
        (6, Direction.DOWN, 9),
        (10, Direction.DOWN, 12),
        (12, Direction.UP, 10),
        (11, Direction.UP, 9),
    ],
)
def test_up_and_down_go_to_the_nearest_field_on_the_next_row(
    editor_rows, current, direction, expected
):
    assert neighbour(editor_rows, current=current, direction=direction) == expected


def test_above_the_first_row_and_below_the_last_the_focus_stays(editor_rows):
    assert neighbour(editor_rows, current=3, direction=Direction.UP) is None
    assert neighbour(editor_rows, current=12, direction=Direction.DOWN) is None


def test_a_tie_for_nearest_goes_to_the_left():
    rows = [
        [FieldBox(1, x=10, width=10)],
        [FieldBox(2, x=0, width=10), FieldBox(3, x=20, width=10)],
    ]

    assert neighbour(rows, current=1, direction=Direction.DOWN) == 2


def test_empty_rows_are_passed_over():
    rows = [[FieldBox(1, x=0, width=10)], [], [FieldBox(2, x=0, width=10)]]

    assert neighbour(rows, current=1, direction=Direction.DOWN) == 2


def test_a_field_in_no_row_has_no_neighbour(editor_rows):
    assert neighbour(editor_rows, current=99, direction=Direction.RIGHT) is None
