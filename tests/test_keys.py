from __future__ import annotations

from textual.actions import parse

from mhp3ass.keys import app_keys, palette_commands, results_keys
from mhp3ass.tui.app import SearchApp


def test_the_app_keys_are_search_keys_quit_options_and_the_regions():
    shown = {binding.key for binding in app_keys() if binding.show}
    every = {binding.key for binding in app_keys()}

    assert shown == {"ctrl+s", "question_mark", "q", "o"}
    assert every == shown | {"escape", "1", "2", "3", "e", "tab", "shift+tab"}


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


def test_every_key_and_command_names_an_action_the_app_has():
    actions = [
        *(binding.action for binding in app_keys()),
        *(binding.action for binding in results_keys()),
        *(command.action for command in palette_commands()),
    ]

    missing = [action for action in actions if not hasattr(SearchApp, f"action_{parse(action)[1]}")]

    assert missing == []


def test_the_palette_reaches_the_fields_by_name():
    titles = [command.title for command in palette_commands()]

    assert {"Set hunter…", "Set HR…", "Add skill…"} <= set(titles)
    assert len(titles) == len(set(titles))


def test_every_dropped_field_letter_has_a_palette_command():
    actions = {command.action for command in palette_commands()}

    assert {
        "set_field('hunter_type')",
        "set_field('gender')",
        "set_field('hr')",
        "set_field('elder_star')",
        "set_field('weapon_slots')",
        "set_field('charm_mode')",
        "edit_field('skill_search')",
    } <= actions
