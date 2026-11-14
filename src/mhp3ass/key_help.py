"""The `?` help: the keys that work where the focus is, from the bindings.

Not a port: the TUI's own help. It is built from the bindings active at
the moment, so it can't drift from them: the focused region's own keys
first, then the app's, each key once. A key with no description is left
out, and keys that run the same action under the same name share a line
(``i, ⏎  Inspect``).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass


@dataclass(frozen=True)
class KeyEntry:
    """One active binding: its ``key`` as shown (``^s``), the ``action`` it
    runs and its ``description``; ``everywhere``: the app's, not the
    focused region's."""

    key: str
    action: str
    description: str
    everywhere: bool


@dataclass(frozen=True)
class HelpRow:
    """A line of the help: the ``keys`` that do ``description``."""

    keys: tuple[str, ...]
    description: str


@dataclass(frozen=True)
class HelpSection:
    title: str
    rows: tuple[HelpRow, ...]


def help_sections(entries: Sequence[KeyEntry], region: str) -> list[HelpSection]:
    """``entries`` as the help shows them: a section titled ``region`` for
    the focused region's keys, then "Everywhere" for the app's, in the
    order given, leaving out empty sections."""
    sections = []
    for title, everywhere in ((region, False), ("Everywhere", True)):
        rows: dict[tuple[str, str], list[str]] = {}
        for entry in entries:
            if entry.everywhere != everywhere or entry.description == "":
                continue
            keys = rows.setdefault((entry.action, entry.description), [])
            if entry.key not in keys:
                keys.append(entry.key)
        if rows:
            sections.append(
                HelpSection(
                    title=title,
                    rows=tuple(
                        HelpRow(keys=tuple(keys), description=description)
                        for (_, description), keys in rows.items()
                    ),
                )
            )
    return sections
