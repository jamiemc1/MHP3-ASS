from __future__ import annotations

import pytest

from mhp3ass.pane_titles import sets_title, sort_arrow
from mhp3ass.results.sorting import SortKey


@pytest.mark.parametrize(
    ("key", "reverse", "arrow"),
    [
        (SortKey.DEFENCE, False, "▼"),
        (SortKey.DEFENCE, True, "▲"),
        (SortKey.DIFFICULTY, False, "▲"),
        (SortKey.DIFFICULTY, True, "▼"),
        (SortKey.NONE, False, ""),
        (SortKey.NONE, True, "reversed"),
    ],
)
def test_the_arrow_points_the_way_the_values_run(key, reverse, arrow):
    assert sort_arrow(key, reverse=reverse) == arrow


def test_the_title_has_the_count_and_the_sort():
    title = sets_title(52812, SortKey.DEFENCE, sort_name="Defence", reverse=False)

    assert title == "Sets 52,812 · Sort: Defence ▼"


def test_a_title_before_any_search_has_no_count():
    title = sets_title(None, SortKey.NONE, sort_name="None", reverse=False)

    assert title == "Sets · Sort: None"


def test_an_empty_result_counts_zero():
    title = sets_title(0, SortKey.NONE, sort_name="None", reverse=True)

    assert title == "Sets 0 · Sort: None reversed"
