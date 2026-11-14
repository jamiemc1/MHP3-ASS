from __future__ import annotations

from mhp3ass.themes import ThemeChoice, starting_theme


def test_with_no_theme_saved_it_starts_with_dracula():
    choice = starting_theme(None, available={"dracula", "nord"})

    assert choice == ThemeChoice(name="dracula", unavailable=None)


def test_a_saved_theme_that_is_available_is_used():
    choice = starting_theme("nord", available={"dracula", "nord"})

    assert choice == ThemeChoice(name="nord", unavailable=None)


def test_a_saved_theme_that_isnt_available_falls_back_and_is_named():
    choice = starting_theme("solarized-dusk", available={"dracula", "nord"})

    assert choice == ThemeChoice(name="dracula", unavailable="solarized-dusk")
