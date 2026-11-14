from __future__ import annotations

from mhp3ass.themes import ThemeChoice, ThemePreview, starting_theme, themes_from


def test_with_no_theme_saved_it_starts_with_dracula():
    choice = starting_theme(None, available={"dracula", "nord"})

    assert choice == ThemeChoice(name="dracula", unavailable=None)


def test_a_saved_theme_that_is_available_is_used():
    choice = starting_theme("nord", available={"dracula", "nord"})

    assert choice == ThemeChoice(name="nord", unavailable=None)


def test_a_saved_theme_that_isnt_available_falls_back_and_is_named():
    choice = starting_theme("solarized-dusk", available={"dracula", "nord"})

    assert choice == ThemeChoice(name="dracula", unavailable="solarized-dusk")


def test_a_preview_shows_the_theme_under_the_cursor():
    preview = ThemePreview("dracula")

    shown = preview.show("nord", available={"dracula", "nord"})

    assert shown == "nord"
    assert preview.shown == "nord"


def test_a_preview_ignores_an_entry_that_isnt_a_theme():
    preview = ThemePreview("dracula")
    preview.show("nord", available={"dracula", "nord"})

    shown = preview.show("Quit the application", available={"dracula", "nord"})

    assert shown is None
    assert preview.shown == "nord"


def test_a_preview_ignores_an_entry_with_no_text():
    preview = ThemePreview("dracula")

    shown = preview.show(None, available={"dracula", "nord"})

    assert shown is None
    assert preview.shown == "dracula"


def test_closing_with_a_choice_keeps_the_theme_on_show():
    preview = ThemePreview("dracula")
    preview.show("nord", available={"dracula", "nord"})

    kept = preview.close(chosen=True)

    assert kept == "nord"


def test_closing_without_a_choice_goes_back_to_the_theme_it_opened_on():
    preview = ThemePreview("dracula")
    preview.show("nord", available={"dracula", "nord"})

    kept = preview.close(chosen=False)

    assert kept == "dracula"


def test_the_themes_start_at_the_current_one_and_wrap_round():
    themes = themes_from("nord", ["dracula", "nord", "ansi-dark", "solarized"])

    assert themes == ["nord", "solarized", "ansi-dark", "dracula"]


def test_the_themes_are_in_name_order_from_the_first_when_it_is_current():
    themes = themes_from("ansi-dark", ["nord", "ansi-dark", "dracula"])

    assert themes == ["ansi-dark", "dracula", "nord"]


def test_the_themes_are_in_name_order_when_the_current_one_isnt_among_them():
    themes = themes_from("textual-dark", ["nord", "ansi-dark", "dracula"])

    assert themes == ["ansi-dark", "dracula", "nord"]
