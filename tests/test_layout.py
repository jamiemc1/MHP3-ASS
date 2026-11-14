from __future__ import annotations

import pytest

from mhp3ass.layout import (
    HeightClass,
    InspectorPlace,
    Layout,
    WidthClass,
    breakpoint_class,
    height_breakpoints,
    layout_for,
    width_breakpoints,
)


def _layout(width_class, height_class=HeightClass.NORMAL, small=False):
    """A layout of ``width_class`` at a normal height, not small."""
    layout = Layout(width=width_class, height=height_class, small=small)
    return layout


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
    assert layout_for(width, height=40).width is expected


@pytest.mark.parametrize(
    ("height", "expected"),
    [
        (16, HeightClass.SHORT),
        (24, HeightClass.SHORT),
        (29, HeightClass.SHORT),
        (30, HeightClass.NORMAL),
        (45, HeightClass.NORMAL),
        (46, HeightClass.TALL),
        (70, HeightClass.TALL),
    ],
)
def test_each_height_takes_the_class_of_the_tallest_breakpoint_it_reaches(height, expected):
    assert layout_for(160, height=height).height is expected


@pytest.mark.parametrize(
    ("width", "height", "small"),
    [(61, 17, False), (60, 50, True), (200, 16, True), (60, 16, True), (80, 24, False)],
)
def test_a_screen_is_small_at_60_columns_or_16_rows_and_below(width, height, small):
    assert layout_for(width, height=height).small is small


def test_the_width_breakpoints_name_every_width_class_once():
    names = [name for _, name in width_breakpoints()]

    assert sorted(names) == sorted(width_class.value for width_class in WidthClass)


def test_the_height_breakpoints_name_every_height_class_once():
    names = [name for _, name in height_breakpoints()]

    assert sorted(names) == sorted(height_class.value for height_class in HeightClass)


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
    assert _layout(width_class).sidebar is sidebar


def test_a_small_screen_has_no_sidebar_however_wide():
    assert not _layout(WidthClass.HUGE, height_class=HeightClass.SHORT, small=True).sidebar


@pytest.mark.parametrize(
    ("width_class", "place"),
    [
        (WidthClass.NARROW, InspectorPlace.OVER),
        (WidthClass.MEDIUM, InspectorPlace.BESIDE),
        (WidthClass.WIDE, InspectorPlace.BESIDE),
        (WidthClass.HUGE, InspectorPlace.BESIDE),
    ],
)
def test_at_a_normal_height_only_narrow_puts_the_inspector_over_the_table(width_class, place):
    assert _layout(width_class).inspector is place


@pytest.mark.parametrize(
    ("width_class", "place"),
    [
        (WidthClass.NARROW, InspectorPlace.BELOW),
        (WidthClass.MEDIUM, InspectorPlace.BESIDE),
        (WidthClass.WIDE, InspectorPlace.BESIDE),
    ],
)
def test_a_narrow_tall_screen_puts_the_inspector_below_the_table(width_class, place):
    assert _layout(width_class, height_class=HeightClass.TALL).inspector is place


def test_a_narrow_short_screen_puts_the_inspector_over_the_table():
    layout = _layout(WidthClass.NARROW, height_class=HeightClass.SHORT)

    assert layout.inspector is InspectorPlace.OVER


@pytest.mark.parametrize(
    ("width_class", "height_class"),
    [(WidthClass.NARROW, HeightClass.TALL), (WidthClass.WIDE, HeightClass.SHORT)],
)
def test_a_small_screen_puts_the_inspector_over_the_table(width_class, height_class):
    layout = _layout(width_class, height_class=height_class, small=True)

    assert layout.inspector is InspectorPlace.OVER


@pytest.mark.parametrize(
    ("height_class", "covers"),
    [(HeightClass.SHORT, True), (HeightClass.NORMAL, False), (HeightClass.TALL, False)],
)
def test_only_a_short_screen_opens_the_editor_in_the_results_place(height_class, covers):
    layout = _layout(WidthClass.WIDE, height_class=height_class)

    assert layout.editor_covers_results(editor_open=True, has_results=True) is covers


@pytest.mark.parametrize(("editor_open", "has_results"), [(False, True), (True, False)])
def test_a_closed_editor_or_no_results_leaves_the_results_in_place(editor_open, has_results):
    layout = _layout(WidthClass.WIDE, height_class=HeightClass.SHORT)

    assert not layout.editor_covers_results(editor_open=editor_open, has_results=has_results)


@pytest.mark.parametrize(
    ("editor_open", "has_results", "small", "shown"),
    [
        (False, True, False, True),
        (True, True, False, False),
        (False, False, False, False),
        (False, True, True, False),
    ],
)
def test_the_query_line_shows_for_results_with_the_editor_closed_unless_small(
    editor_open, has_results, small, shown
):
    layout = _layout(WidthClass.NARROW, small=small)

    assert layout.shows_query_line(editor_open=editor_open, has_results=has_results) is shown


@pytest.mark.parametrize(
    ("height_class", "palette"),
    [(HeightClass.SHORT, False), (HeightClass.NORMAL, True), (HeightClass.TALL, True)],
)
def test_a_short_screens_footer_drops_the_palette_hint(height_class, palette):
    assert _layout(WidthClass.WIDE, height_class=height_class).footer_palette is palette


@pytest.mark.parametrize(("small", "shown"), [(False, True), (True, False)])
def test_a_small_screen_shows_no_charms(small, shown):
    assert _layout(WidthClass.NARROW, small=small).charms_shown is shown


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
    assert _layout(width_class).full_names is full
