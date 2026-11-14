"""Which colour theme the TUI starts with.

Not a port: the original has no themes. ``tui.toml`` keeps the theme
picked in Options or the command palette; ``dracula`` is the default.
"""

from __future__ import annotations

from collections.abc import Collection
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
