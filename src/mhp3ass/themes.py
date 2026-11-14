"""Which colour theme the TUI starts with.

Not a port: the original has no themes. ``tui.toml`` keeps the theme
picked in Options or the command palette; ``dracula`` is the default.
"""

from __future__ import annotations

from collections.abc import Collection, Iterable
from dataclasses import dataclass


@dataclass(frozen=True)
class ThemeChoice:
    """The theme to start with, and the saved name that couldn't be used
    (``None`` when the saved one, or none, was asked for)."""

    name: str
    unavailable: str | None


def starting_theme(
    saved: str | None, available: Collection[str], default: str = "dracula"
) -> ThemeChoice:
    """``saved`` when it is one of ``available``, else ``default``."""
    if saved is None:
        return ThemeChoice(name=default, unavailable=None)
    if saved not in available:
        return ThemeChoice(name=default, unavailable=saved)
    choice = ThemeChoice(name=saved, unavailable=None)
    return choice


class ThemePreview:
    """A theme picker that shows each theme its cursor reaches: the theme
    it opened on (``original``), and the one on show (``shown``)."""

    def __init__(self, original: str) -> None:
        self.original = original
        self.shown = original

    def show(self, name: str | None, available: Collection[str]) -> str | None:
        """Show ``name``, an entry under the cursor, when it is one of
        ``available``; the theme now on show, or ``None`` for an entry that
        isn't a theme."""
        if name is None or name not in available:
            return None
        self.shown = name
        return name

    def close(self, chosen: bool) -> str:
        """The theme to keep once the picker closes: the one on show if a
        theme was ``chosen``, else the one it opened on."""
        kept = self.shown if chosen else self.original
        return kept


def themes_from(current: str, themes: Iterable[str]) -> list[str]:
    """``themes`` in order of name, starting at ``current`` and wrapping
    round, so that a picker whose cursor starts on its first entry opens on
    the theme in use. In name order alone when ``current`` isn't one of them."""
    ordered = sorted(themes)
    if current not in ordered:
        return ordered
    start = ordered.index(current)
    rotated = ordered[start:] + ordered[:start]
    return rotated
