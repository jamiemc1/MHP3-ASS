from __future__ import annotations

from dataclasses import fields, replace
from itertools import product

import pytest

from mhp3ass.escape import EscapeState, EscapeStep, escape_step


@pytest.fixture
def nothing_open():
    state = EscapeState(
        popup_open=False,
        find_open=False,
        inspector_open=False,
        editor_open=False,
        can_collapse=False,
        editor_focused=False,
        searching=False,
    )
    return state


@pytest.fixture
def everything_open(nothing_open):
    state = replace(
        nothing_open,
        popup_open=True,
        find_open=True,
        inspector_open=True,
        editor_open=True,
        can_collapse=True,
        editor_focused=True,
        searching=True,
    )
    return state


def test_with_nothing_open_esc_does_nothing(nothing_open):
    assert escape_step(nothing_open) is EscapeStep.NOTHING


def test_esc_does_nothing_only_when_there_is_nothing_to_back_out_of():
    names = [field.name for field in fields(EscapeState)]
    idle = []
    for values in product([False, True], repeat=len(names)):
        state = EscapeState(**dict(zip(names, values, strict=True)))
        if escape_step(state) is EscapeStep.NOTHING:
            idle.append(state)

    # Nothing to close, collapse, leave or cancel: a collapsed editor, or an open one
    # with no results to collapse over and the focus elsewhere.
    assert all(
        not (state.popup_open or state.find_open or state.inspector_open or state.searching)
        and not (state.editor_open and (state.can_collapse or state.editor_focused))
        for state in idle
    )
    assert len(idle) == 5


def test_backing_out_one_level_at_a_time_ends_with_the_search(everything_open):
    state = everything_open
    steps = []
    closed_by = {
        EscapeStep.CLOSE_POPUP: {"popup_open": False},
        EscapeStep.CLEAR_FIND: {"find_open": False},
        EscapeStep.CLOSE_INSPECTOR: {"inspector_open": False},
        EscapeStep.COLLAPSE_EDITOR: {"editor_open": False, "editor_focused": False},
        EscapeStep.CANCEL_SEARCH: {"searching": False},
    }
    while (step := escape_step(state)) is not EscapeStep.NOTHING:
        steps.append(step)
        state = replace(state, **closed_by[step])

    assert steps == [
        EscapeStep.CLOSE_POPUP,
        EscapeStep.CLEAR_FIND,
        EscapeStep.CLOSE_INSPECTOR,
        EscapeStep.COLLAPSE_EDITOR,
        EscapeStep.CANCEL_SEARCH,
    ]


def test_a_search_is_cancelled_only_once_the_editor_is_collapsed(nothing_open):
    state = replace(nothing_open, editor_open=True, can_collapse=True, searching=True)

    assert escape_step(state) is EscapeStep.COLLAPSE_EDITOR


def test_with_no_results_esc_leaves_the_editor_it_cannot_collapse(nothing_open):
    state = replace(nothing_open, editor_open=True, editor_focused=True)

    assert escape_step(state) is EscapeStep.LEAVE_EDITOR


def test_with_no_results_and_the_focus_elsewhere_esc_cancels_the_search(nothing_open):
    state = replace(nothing_open, editor_open=True, searching=True)

    assert escape_step(state) is EscapeStep.CANCEL_SEARCH


def test_with_no_results_and_no_search_esc_outside_the_editor_does_nothing(nothing_open):
    state = replace(nothing_open, editor_open=True)

    assert escape_step(state) is EscapeStep.NOTHING


def test_a_collapsed_editor_is_not_collapsed_again(nothing_open):
    state = replace(nothing_open, can_collapse=True, searching=True)

    assert escape_step(state) is EscapeStep.CANCEL_SEARCH


def test_the_find_text_is_cleared_before_the_editor_collapses(nothing_open):
    state = replace(nothing_open, find_open=True, editor_open=True, can_collapse=True)

    assert escape_step(state) is EscapeStep.CLEAR_FIND


def test_the_inspector_over_the_table_closes_before_the_editor_collapses(nothing_open):
    state = replace(nothing_open, inspector_open=True, editor_open=True, can_collapse=True)

    assert escape_step(state) is EscapeStep.CLOSE_INSPECTOR


def test_the_inspector_over_the_table_closes_before_a_search_is_cancelled(nothing_open):
    state = replace(nothing_open, inspector_open=True, searching=True)

    assert escape_step(state) is EscapeStep.CLOSE_INSPECTOR
