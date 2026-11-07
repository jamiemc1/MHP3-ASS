"""Guards on the shared game data that the port and the harness both read."""

from __future__ import annotations

from pathlib import Path

import pytest

GAME_DATA_FILES = [
    "arms.txt",
    "body.txt",
    "components.txt",
    "decorations.txt",
    "head.txt",
    "legs.txt",
    "skills.txt",
    "tags.txt",
    "waist.txt",
]


def test_base_data_set_is_complete(legacy_data_dir: Path):
    missing = [name for name in GAME_DATA_FILES if not (legacy_data_dir / name).is_file()]

    assert missing == []


@pytest.mark.parametrize(
    "language",
    [
        "Deutsch (Vuze)",
        "English (Athena)",
        "English (TMO)",
        "English (TeamHGG)",
        "Español (Team Hunters 404)",
        "Français (Team MHP2)",
        "Japanese",
    ],
)
def test_language_data_set_is_complete(legacy_data_dir: Path, language: str):
    language_dir = legacy_data_dir / "Languages" / language
    expected = [*GAME_DATA_FILES, "strings.txt"]

    missing = [name for name in expected if not (language_dir / name).is_file()]

    assert missing == []
