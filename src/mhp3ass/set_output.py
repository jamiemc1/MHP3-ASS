"""Copying and exporting a set: when its text is ready, the system's copy
command, and appending sets to a Markdown file.

Not a port: the original has no copy or export of a set
(``legacy/Form1.h:1955-1972`` only selects and copies its result text box).

``y`` copies the highlighted set's text (``results/set_text.py``) through
the terminal (OSC 52, ``App.copy_to_clipboard``), which macOS Terminal
doesn't support, so on macOS it also runs ``pbcopy``.

``Y`` appends it to ``mhp3-ass-sets.md``, so several sets exported one after
another collect in one document. Each export starts with a horizontal rule.
A new file starts with a title, so its first line isn't the rule, which
Markdown tools would take for the start of front matter.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Literal

from mhp3ass.results.details import PlacementPending, SolutionDetails


def jewels_wait(details: SolutionDetails, action: Literal["copy", "export"]) -> str | None:
    """Why a set with ``details`` can't be copied or exported (``action``)
    yet, or ``None`` when it can. Both wait while the inspector is working
    out its jewels in a thread. During a search, a copy goes ahead
    without the jewels' places (``copied_notice`` says so), but an export
    waits, since a file keeps what it is given."""
    jewels = details.chest_jewels
    if not isinstance(jewels, PlacementPending):
        return None
    if not jewels.while_searching:
        return f"Still working out the set's jewels: {action} it again in a moment."
    if action == "export":
        return "The set's jewels are placed once the search finishes: export it then."
    return None


def system_copy_command(platform: str) -> list[str] | None:
    """The command that copies its standard input on ``platform``
    (``sys.platform``), where the terminal may not: ``pbcopy`` on macOS;
    ``None`` elsewhere, where OSC 52 is left to do it."""
    command = ["pbcopy"] if platform == "darwin" else None
    return command


def copied_notice(number: int, details: SolutionDetails) -> str:
    """The notice once set ``number`` is copied; during a search, a set
    whose placement waits for it says its jewels aren't placed yet."""
    jewels = details.chest_jewels
    if isinstance(jewels, PlacementPending) and jewels.while_searching:
        notice = (
            f"Copied set {number:,}, without its jewels' places:"
            " copy it again after the search for them."
        )
        return notice
    notice = f"Copied set {number:,}."
    return notice


def export_file(export_dir: Path | None, launch_dir: Path) -> Path:
    """The file sets are appended to: ``mhp3-ass-sets.md`` in ``export_dir``
    (``tui.toml``'s), else in ``launch_dir``, the folder the TUI was started
    from. A leading ``~`` is the home folder; a relative ``export_dir`` is
    under ``launch_dir``."""
    if export_dir is None:
        folder = launch_dir
    else:
        chosen = export_dir.expanduser()
        folder = chosen if chosen.is_absolute() else launch_dir / chosen
    path = folder / "mhp3-ass-sets.md"
    return path


def export_entry(text: str, file_tail: bytes) -> str:
    """What appending ``text`` (a set's Markdown) writes after a file
    ending in ``file_tail`` (its last four bytes; empty for a new or empty
    file): a title for a new file, a blank line after what is there (its
    lines may end in CRLF, as a Windows editor saves them), then the rule
    and ``text``."""
    if file_tail == b"":
        lead = "# MHP3 Armor Set Search: sets\n\n"
    elif file_tail.endswith((b"\n\n", b"\n\r\n")):
        lead = ""
    elif file_tail.endswith(b"\n"):
        lead = "\n"
    else:
        lead = "\n\n"
    entry = f"{lead}---\n\n{text}"
    return entry


def _tail(path: Path) -> bytes:
    """``path``'s last four bytes; empty when it doesn't exist."""
    if not path.exists():
        return b""
    with path.open("rb") as file:
        size = file.seek(0, os.SEEK_END)
        file.seek(max(size - 4, 0))
        tail = file.read()
    return tail


def append_set(path: Path, text: str) -> None:
    """Append ``text`` to ``path`` as ``export_entry`` lays it out, in one
    write, creating the file if it is missing (but not its folder). A
    missing or unwritable folder or file raises ``OSError`` when it is
    opened, before anything is written; a write that fails part-way (a full
    disk) can leave part of the entry."""
    entry = export_entry(text, file_tail=_tail(path))
    with path.open("ab") as file:
        file.write(entry.encode("utf-8"))
