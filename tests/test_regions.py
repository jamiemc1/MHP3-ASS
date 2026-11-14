from __future__ import annotations

import pytest

from mhp3ass.regions import Region, next_region, region_hint


def test_the_regions_are_numbered_in_screen_order():
    assert [(region.name, int(region)) for region in Region] == [
        ("QUERY", 1),
        ("CHARMS", 2),
        ("SETS", 3),
    ]


def test_each_hint_is_its_regions_number_as_a_superscript():
    assert [region_hint(region) for region in Region] == ["¹", "²", "³"]


@pytest.mark.parametrize(
    ("current", "step", "expected"),
    [
        (Region.QUERY, 1, Region.CHARMS),
        (Region.CHARMS, 1, Region.SETS),
        (Region.SETS, 1, Region.QUERY),
        (Region.QUERY, -1, Region.SETS),
        (Region.CHARMS, -1, Region.QUERY),
        (Region.SETS, -1, Region.CHARMS),
    ],
)
def test_with_the_editor_open_tab_goes_round_all_three(current, step, expected):
    assert next_region(current, step=step, editor_open=True) is expected


@pytest.mark.parametrize(
    ("current", "step", "expected"),
    [
        (Region.CHARMS, 1, Region.SETS),
        (Region.SETS, 1, Region.CHARMS),
        (Region.CHARMS, -1, Region.SETS),
        (Region.SETS, -1, Region.CHARMS),
    ],
)
def test_with_the_editor_collapsed_tab_skips_the_query(current, step, expected):
    assert next_region(current, step=step, editor_open=False) is expected


@pytest.mark.parametrize(
    ("step", "editor_open", "expected"),
    [
        (1, True, Region.QUERY),
        (-1, True, Region.SETS),
        (1, False, Region.CHARMS),
        (-1, False, Region.SETS),
    ],
)
def test_from_no_region_tab_goes_to_the_first_and_shift_tab_to_the_last(
    step, editor_open, expected
):
    assert next_region(None, step=step, editor_open=editor_open) is expected
