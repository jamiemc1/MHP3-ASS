from __future__ import annotations

import pytest

from mhp3ass.layout import (
    InspectorPlace,
    Layout,
    WidthClass,
    breakpoint_class,
    layout_for,
    width_breakpoints,
)


@pytest.mark.parametrize(
    ("width", "expected"),
    [
        (60, WidthClass.NARROW),
        (80, WidthClass.NARROW),
        (109, WidthClass.NARROW),
        (110, WidthClass.MEDIUM),
        (130, WidthClass.MEDIUM),
        (149, WidthClass.MEDIUM),
        (150, WidthClass.WIDE),
        (219, WidthClass.WIDE),
        (220, WidthClass.HUGE),
        (400, WidthClass.HUGE),
    ],
)
def test_each_width_takes_the_class_of_the_widest_breakpoint_it_reaches(width, expected):
    assert layout_for(width).width is expected


def test_the_breakpoints_name_every_class_once():
    names = [name for _, name in width_breakpoints()]

    assert sorted(names) == sorted(width_class.value for width_class in WidthClass)


def test_breakpoint_class_does_not_depend_on_the_order_given():
    breakpoints = [(150, "-wide"), (0, "-narrow"), (110, "-medium")]

    assert breakpoint_class(120, breakpoints) == "-medium"


def test_breakpoint_class_below_every_breakpoint_raises():
    with pytest.raises(ValueError, match="no breakpoint covers 5"):
        breakpoint_class(5, [(10, "-small")])


@pytest.mark.parametrize(
    ("width_class", "sidebar"),
    [
        (WidthClass.NARROW, False),
        (WidthClass.MEDIUM, False),
        (WidthClass.WIDE, True),
        (WidthClass.HUGE, True),
    ],
)
def test_the_sidebar_shows_from_wide_and_the_drop_down_below(width_class, sidebar):
    assert Layout(width=width_class).sidebar is sidebar


@pytest.mark.parametrize(
    ("width_class", "place"),
    [
        (WidthClass.NARROW, InspectorPlace.OVER),
        (WidthClass.MEDIUM, InspectorPlace.BESIDE),
        (WidthClass.WIDE, InspectorPlace.BESIDE),
        (WidthClass.HUGE, InspectorPlace.BESIDE),
    ],
)
def test_only_narrow_puts_the_inspector_over_the_table(width_class, place):
    assert Layout(width=width_class).inspector is place


@pytest.mark.parametrize(
    ("width_class", "full"),
    [
        (WidthClass.NARROW, False),
        (WidthClass.MEDIUM, False),
        (WidthClass.WIDE, False),
        (WidthClass.HUGE, True),
    ],
)
def test_only_huge_names_the_pieces_in_full(width_class, full):
    assert Layout(width=width_class).full_names is full
