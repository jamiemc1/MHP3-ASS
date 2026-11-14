"""Exporting sets: appending each to a Markdown file.

Not a port: the original has no export of a set. ``Y`` appends the
highlighted set's text (``results/set_text.py``) to ``mhp3-ass-sets.md``,
so several sets exported one after another collect in one document. Each
export starts with a horizontal rule. A new file starts with a title, so
its first line isn't the rule, which Markdown tools would take for the
start of front matter.
"""

from __future__ import annotations

import os
from pathlib import Path


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
    ending in ``file_tail`` (its last two bytes; empty for a new or empty
    file): a title for a new file, a blank line after what is there, then
    the rule and ``text``."""
    if file_tail == b"":
        lead = "# MHP3 Armor Set Search: sets\n\n"
    elif file_tail.endswith(b"\n\n"):
        lead = ""
    elif file_tail.endswith(b"\n"):
        lead = "\n"
    else:
        lead = "\n\n"
    entry = f"{lead}---\n\n{text}"
    return entry


def _tail(path: Path) -> bytes:
    """``path``'s last two bytes; empty when it doesn't exist."""
    if not path.exists():
        return b""
    with path.open("rb") as file:
        size = file.seek(0, os.SEEK_END)
        file.seek(max(size - 2, 0))
        tail = file.read()
    return tail


def append_set(path: Path, text: str) -> None:
    """Append ``text`` to ``path`` as ``export_entry`` lays it out, creating
    the file if it is missing (but not its folder). A missing or unwritable
    folder or file raises ``OSError`` before anything is written."""
    entry = export_entry(text, file_tail=_tail(path))
    with path.open("ab") as file:
        file.write(entry.encode("utf-8"))
