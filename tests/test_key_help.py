from __future__ import annotations

import pytest

from mhp3ass.key_help import HelpRow, HelpSection, KeyEntry, help_sections
from mhp3ass.keys import app_keys, results_keys


@pytest.fixture
def table_entries():
    """The sets table's keys and some of the app's, as the active bindings give them."""
    entries = [
        KeyEntry(key="s", action="app.sort", description="Sort", everywhere=False),
        KeyEntry(key="i", action="app.inspect", description="Inspect", everywhere=False),
        KeyEntry(key="⏎", action="app.inspect", description="Inspect", everywhere=False),
        KeyEntry(key="^s", action="search", description="Search", everywhere=True),
        KeyEntry(key="q", action="quit", description="Quit", everywhere=True),
    ]
    return entries


def test_the_regions_keys_come_before_the_apps(table_entries):
    sections = help_sections(table_entries, region="Sets")

    assert [section.title for section in sections] == ["Sets", "Everywhere"]
    assert sections[1] == HelpSection(
        title="Everywhere",
        rows=(
            HelpRow(keys=("^s",), description="Search"),
            HelpRow(keys=("q",), description="Quit"),
        ),
    )


def test_keys_for_the_same_action_share_a_line(table_entries):
    sections = help_sections(table_entries, region="Sets")

    assert sections[0].rows == (
        HelpRow(keys=("s",), description="Sort"),
        HelpRow(keys=("i", "⏎"), description="Inspect"),
    )


def test_a_key_without_a_description_is_left_out():
    entries = [
        KeyEntry(key="x", action="hidden", description="", everywhere=False),
        KeyEntry(key="q", action="quit", description="Quit", everywhere=True),
    ]

    sections = help_sections(entries, region="Sets")

    assert sections == [HelpSection(title="Everywhere", rows=(HelpRow(("q",), "Quit"),))]


def test_the_same_action_under_another_name_keeps_its_own_line():
    entries = [
        KeyEntry(key="n", action="app.find_next(1)", description="Next", everywhere=False),
        KeyEntry(key="N", action="app.find_next(-1)", description="Previous", everywhere=False),
    ]

    sections = help_sections(entries, region="Sets")

    assert [row.keys for row in sections[0].rows] == [("n",), ("N",)]


def test_a_key_given_twice_is_listed_once():
    entries = [KeyEntry(key="q", action="quit", description="Quit", everywhere=True)] * 2

    sections = help_sections(entries, region="Sets")

    assert sections[0].rows == (HelpRow(keys=("q",), description="Quit"),)


def test_no_keys_gives_no_sections():
    assert help_sections([], region="Sets") == []


def test_every_app_and_results_key_has_a_description_for_the_help():
    bindings = [*app_keys(), *results_keys()]

    assert [binding.key for binding in bindings if binding.description == ""] == []


def test_each_description_starts_with_a_capital():
    entries = [KeyEntry(key="^p", action="command_palette", description="palette", everywhere=True)]

    sections = help_sections(entries, region="Sets")

    assert sections[0].rows == (HelpRow(keys=("^p",), description="Palette"),)
