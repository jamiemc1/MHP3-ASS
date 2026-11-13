"""Changing and clearing the saved-data folder.

Not a port: the original keeps its files beside its executable. These are
the Options modal's folder choice (move the files there, use what's already
there, or start fresh) and its "clear…", over ``saved_data``'s folders.
"""

from __future__ import annotations

import dataclasses
import shutil
from enum import Enum
from pathlib import Path

from mhp3ass.saved_data import TuiFolders, TuiSettings


class FolderChoice(Enum):
    MOVE = "move"
    USE = "use"
    FRESH = "fresh"


class ClearChoice(Enum):
    """What "clear…" deletes: the saved search and results, my charms, or both."""

    SEARCH = "search"
    MY_CHARMS = "my_charms"
    EVERYTHING = "everything"


def saved_files_in(folder: Path) -> list[Path]:
    """``settings.cfg`` and ``mycharms.txt`` in ``folder``, those that exist."""
    files = [folder / name for name in ("settings.cfg", "mycharms.txt") if (folder / name).exists()]
    return files


def folder_choices(current: Path, new: Path) -> list[FolderChoice]:
    """What can be done on changing the folder from ``current`` to ``new``:
    nothing for the same folder; only use what's there when ``new`` has
    either file (moving would overwrite it, starting fresh would hide it);
    otherwise move the files there or start fresh. A path that is a file
    can't be a folder, so it offers nothing."""
    if new.resolve() == current.resolve() or (new.exists() and not new.is_dir()):
        return []
    if saved_files_in(new):
        return [FolderChoice.USE]
    choices = [FolderChoice.MOVE, FolderChoice.FRESH]
    return choices


def change_folder(current: Path, new: Path, choice: FolderChoice) -> None:
    """Carry out ``choice`` (one of ``folder_choices``): move the files from
    ``current`` into ``new``, or make ``new`` for a fresh start; using what's
    there moves nothing. Raises ``ValueError`` for a choice ``folder_choices``
    doesn't offer, before anything moves. If a move fails, the files already
    moved are moved back before the error is raised, so they stay together."""
    if choice not in folder_choices(current, new):
        raise ValueError(f"can't {choice.value} from {current} to {new}")
    if choice is FolderChoice.USE:
        return
    new.mkdir(parents=True, exist_ok=True)
    if choice is FolderChoice.MOVE:
        moved: list[Path] = []
        try:
            for path in saved_files_in(current):
                shutil.move(path, new / path.name)
                moved.append(path)
        except OSError:
            for path in moved:
                shutil.move(new / path.name, path)
            raise


def with_folder(folders: TuiFolders, new: Path) -> TuiSettings:
    """``tui.toml``'s settings with ``new`` as the saved-data folder: no
    ``data_dir`` when it is the TUI's own folder."""
    data_dir = None if new.resolve() == folders.own.resolve() else new
    settings = dataclasses.replace(folders.settings, data_dir=data_dir)
    return settings


def clear_targets(folder: Path, choice: ClearChoice) -> list[Path]:
    """The files in ``folder`` that clearing ``choice`` would delete."""
    match choice:
        case ClearChoice.SEARCH:
            names = {"settings.cfg"}
        case ClearChoice.MY_CHARMS:
            names = {"mycharms.txt"}
        case ClearChoice.EVERYTHING:
            names = {"settings.cfg", "mycharms.txt"}
    targets = [path for path in saved_files_in(folder) if path.name in names]
    return targets


def clear(folder: Path, choice: ClearChoice) -> list[Path]:
    """Delete ``clear_targets``; returns them. The next start begins from the
    defaults and the shipped charm list, as a fresh install does."""
    targets = clear_targets(folder, choice)
    for path in targets:
        path.unlink()
    return targets
