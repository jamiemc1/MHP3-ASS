"""The language list (Form1::LoadLanguages) and the default language (Form1::LoadConfig)."""

from __future__ import annotations

import pytest

from mhp3ass.data.languages import default_language, language_folders


@pytest.fixture
def languages_dir_with_a_file(tmp_path):
    """Folders whose plain and case-insensitive orders differ, plus a stray file."""
    for name in ["b", "A", "English (TMO)", "English (TeamHGG)"]:
        (tmp_path / name).mkdir()
    (tmp_path / "readme.txt").write_text("not a language", encoding="utf-8")
    return tmp_path


def test_shipped_languages_in_gui_order(legacy_data_dir):
    assert language_folders(legacy_data_dir / "Languages") == [
        "Deutsch (Vuze)",
        "English (Athena)",
        "English (TeamHGG)",
        "English (TMO)",
        "Español (Team Hunters 404)",
        "Français (Team MHP2)",
        "Japanese",
    ]


def test_folders_sort_case_insensitively_and_files_are_ignored(languages_dir_with_a_file):
    assert language_folders(languages_dir_with_a_file) == [
        "A",
        "b",
        "English (TeamHGG)",
        "English (TMO)",
    ]


def test_default_is_the_first_teamhgg_folder():
    assert default_language(["Deutsch", "English (TeamHGG)", "TeamHGG copy"]) == (
        "English (TeamHGG)"
    )


def test_default_falls_back_to_the_first_folder():
    assert default_language(["Deutsch", "Japanese"]) == "Deutsch"


def test_no_folders_gives_no_default():
    assert default_language([]) is None
