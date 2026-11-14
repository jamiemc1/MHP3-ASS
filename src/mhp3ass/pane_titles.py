"""The TUI's pane titles: the text in each pane's top border.

Not a port: the TUI's own layout, which puts the results' count and sort in
the table's title rather than in lines of their own.
"""

from __future__ import annotations

from mhp3ass.results.sorting import SortKey, sorts_ascending


def sort_arrow(key: SortKey, reverse: bool) -> str:
    """``▼`` when the highest value is shown first, ``▲`` when the lowest
    is; for None, which keeps the arrival order, ``reversed`` or nothing."""
    ascending = sorts_ascending(key)
    if ascending is None:
        return "reversed" if reverse else ""
    lowest_first = ascending != reverse
    arrow = "▲" if lowest_first else "▼"
    return arrow


def sets_title(shown: int | None, key: SortKey, sort_name: str, reverse: bool) -> str:
    """The results table's title: ``Sets 52,812 · Sort: Defence ▼``, with
    ``shown`` the sets the table lists (``None`` before any search) and
    ``sort_name`` the key's name in the game's language."""
    count = f" {shown:,}" if shown is not None else ""
    arrow = sort_arrow(key, reverse=reverse)
    sort = f"Sort: {sort_name} {arrow}" if arrow != "" else f"Sort: {sort_name}"
    title = f"Sets{count} · {sort}"
    return title
