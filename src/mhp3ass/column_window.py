"""Which of the sets table's columns show: the pinned ones, then a window
onto the rest.

Not a port: the TUI's own table. The pinned columns (``#`` and Def) stay at
the left, and the others scroll by whole columns, so a cell is never shown
cut by the table's edge. A line is laid out as::

     #  Def < Head  Body  ...  Charm >

one space at the left, two between columns, `` < `` between the pinned
columns and the scrolled ones, and `` >`` at the right edge; the markers
show while there are columns off-screen that way, and are spaces otherwise.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass


@dataclass(frozen=True)
class ColumnWindow:
    """The columns a line shows, by index, left to right: the ``pinned``
    ones, then the ``scrolled`` ones in view, from ``first`` (an index
    into ``scrolled_columns``). ``more_left`` and ``more_right``: columns
    are off-screen that way."""

    pinned: tuple[int, ...]
    scrolled: tuple[int, ...]
    first: int
    more_left: bool
    more_right: bool


def spare_cells(pinned: int, scrolled: int) -> int:
    """The cells a line spends outside its columns, with ``pinned`` and
    ``scrolled`` columns showing: the spaces, the gaps and both markers."""
    pinned_gaps = 2 * max(pinned - 1, 0)
    scrolled_gaps = 2 * max(scrolled - 1, 0)
    # One space at the left, " < " after the pinned columns, " >" at the right.
    cells = 1 + pinned_gaps + 3 + scrolled_gaps + 2
    return cells


def scrolled_columns(count: int, pinned: frozenset[int]) -> list[int]:
    """The indexes of ``count`` columns that aren't ``pinned``, in order."""
    columns = [column for column in range(count) if column not in pinned]
    return columns


def _room(widths: Sequence[int], pinned: frozenset[int], width: int) -> int:
    """The cells a line ``width`` wide leaves the scrolled columns and the
    gaps between them."""
    pinned_widths = sum(widths[column] for column in pinned)
    room = width - pinned_widths - spare_cells(len(pinned), scrolled=1)
    return room


def _fits(widths: Sequence[int], room: int) -> bool:
    """``widths`` side by side, two cells apart, fit in ``room``."""
    fits = sum(widths) + 2 * max(len(widths) - 1, 0) <= room
    return fits


def last_first(widths: Sequence[int], pinned: frozenset[int], width: int) -> int:
    """The furthest the window need scroll: the first scrolled column (an
    index into ``scrolled_columns``) from which every one to the end fits,
    or the last column when it doesn't fit even on its own."""
    columns = scrolled_columns(len(widths), pinned)
    room = _room(widths, pinned, width)
    first = max(len(columns) - 1, 0)
    while first > 0 and _fits([widths[column] for column in columns[first - 1 :]], room):
        first -= 1
    return first


def column_window(
    widths: Sequence[int], pinned: frozenset[int], first: int, width: int
) -> ColumnWindow:
    """The columns a line ``width`` wide shows, for columns ``widths``
    wide, with the scrolled columns starting at ``first`` (an index into
    ``scrolled_columns``, held between 0 and ``last_first``). As many whole
    columns as fit show; the first always does, cut if need be."""
    columns = scrolled_columns(len(widths), pinned)
    start = min(max(first, 0), last_first(widths, pinned=pinned, width=width))
    room = _room(widths, pinned, width)
    end = min(start + 1, len(columns))
    while end < len(columns) and _fits(
        [widths[column] for column in columns[start : end + 1]], room
    ):
        end += 1
    window = ColumnWindow(
        pinned=tuple(column for column in range(len(widths)) if column in pinned),
        scrolled=tuple(columns[start:end]),
        first=start,
        more_left=start > 0,
        more_right=end < len(columns),
    )
    return window
