from __future__ import annotations

import inspect

import pytest
from textual.actions import parse

from mhp3ass.keys import app_keys, palette_commands, results_keys
from mhp3ass.tui.app import SearchApp


def test_the_app_keys_are_search_keys_quit_options_and_the_regions():
    shown = {binding.key for binding in app_keys() if binding.show}
    every = {binding.key for binding in app_keys()}

    assert shown == {"ctrl+s", "question_mark", "q", "o"}
    regions = {"1", "2", "3", "e", "tab", "shift+tab"}
    assert every == shown | regions | {"escape", "left", "right", "up", "down"}


def test_the_form_fields_have_no_letter_of_their_own():
    every = {binding.key for binding in app_keys()} | {binding.key for binding in results_keys()}

    assert every.isdisjoint({"h", "g", "r", "v", "w", "m", "k"})


def test_the_results_keys_are_sort_reverse_and_find():
    keys = [binding.key for binding in results_keys()]

    assert keys == ["s", "S", "slash", "n", "N"]


def test_no_results_key_is_also_an_app_key():
    app = {binding.key for binding in app_keys()}

    assert app.isdisjoint(binding.key for binding in results_keys())


def test_the_results_keys_run_the_apps_actions():
    namespaces = {parse(binding.action)[0] for binding in results_keys()}

    assert namespaces == {"app"}


def test_every_key_and_command_calls_an_app_action_with_arguments_it_takes():
    actions = [
        *(binding.action for binding in app_keys()),
        *(binding.action for binding in results_keys()),
        *(command.action for command in palette_commands(has_results=True, searching=True)),
    ]

    unfit = []
    for action in actions:
        _, name, arguments = parse(action)
        method = getattr(SearchApp, f"action_{name}", None)
        if method is None:
            unfit.append(action)
            continue
        try:
            inspect.signature(method).bind(None, *arguments)
        except TypeError:
            unfit.append(action)

    assert unfit == []


def test_the_palette_reaches_the_fields_by_name():
    titles = [command.title for command in palette_commands(has_results=True, searching=True)]

    assert {"Set hunter…", "Set HR…", "Add skill…"} <= set(titles)
    assert len(titles) == len(set(titles))


def test_every_dropped_field_letter_has_a_palette_command():
    actions = {command.action for command in palette_commands(has_results=False, searching=False)}

    assert {
        "set_field('hunter_type')",
        "set_field('gender')",
        "set_field('hr')",
        "set_field('elder_star')",
        "set_field('weapon_slots')",
        "set_field('charm_mode')",
        "edit_field('skill_search')",
    } <= actions


@pytest.mark.parametrize(
    ("has_results", "searching", "expected"),
    [
        (False, False, set()),
        (True, False, {"Find…", "Find next", "Find previous"}),
        (False, True, {"Cancel search"}),
        (True, True, {"Find…", "Find next", "Find previous", "Cancel search"}),
    ],
)
def test_find_needs_results_and_cancel_a_running_search(has_results, searching, expected):
    state_dependent = {"Find…", "Find next", "Find previous", "Cancel search"}

    titles = {command.title for command in palette_commands(has_results, searching=searching)}

    assert titles & state_dependent == expected
    assert {"Search", "Sort…", "Options"} <= titles
