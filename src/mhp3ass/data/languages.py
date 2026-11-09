"""The language list and the default language.

Ported from ``Form1::LoadLanguages`` (``legacy/Form1.h:331-340``) and the
no-``settings.cfg`` branch of ``Form1::LoadConfig`` (``legacy/Form1.h:441-454``).
"""

from __future__ import annotations

from pathlib import Path


def language_folders(languages_dir: Path) -> list[str]:
    """Language folders in the order the GUI lists them (NTFS name order).

    ``Directory::GetDirectories`` returns NTFS order, which compares names
    case-insensitively, so "English (TeamHGG)" sorts before "English (TMO)".
    ``settings.cfg`` stores a language as an index into this list.

    ``str.upper`` approximates NTFS's upcase table: they differ for names with
    characters whose upper case is several characters (``ß``) or that lie
    outside the BMP, which no shipped folder has.
    """
    folders = sorted(
        (path.name for path in languages_dir.iterdir() if path.is_dir()), key=str.upper
    )
    return folders


def default_language(folders: list[str]) -> str | None:
    """The language chosen when there is no ``settings.cfg``.

    The first folder whose name contains "TeamHGG", else the first folder;
    ``None`` when there are no folders (the original then selects none).
    The original's ``IndexOf`` is culture-sensitive; this ordinal ``in``
    agrees with it on the shipped folder names.
    """
    for folder in folders:
        if "TeamHGG" in folder:
            return folder
    first = folders[0] if folders else None
    return first
