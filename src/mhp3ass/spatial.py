"""Spatial arrows in the query editor: which field an arrow key moves to.

Not a port: the TUI's own keys. The editor's fields sit in rows; ←/→ move
to the field beside the current one on its row, ↑/↓ to the field on the
row above or below whose middle is nearest the current field's. Past the
ends of a row, or above the first row and below the last, the focus stays.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from enum import Enum


class Direction(Enum):
    LEFT = "left"
    RIGHT = "right"
    UP = "up"
    DOWN = "down"


@dataclass(frozen=True)
class FieldBox:
    """A field (``key``, the caller's) at column ``x`` of its row, ``width`` wide."""

    key: int
    x: int
    width: int

    @property
    def middle(self) -> float:
        middle = self.x + self.width / 2
        return middle


def neighbour(rows: Sequence[Sequence[FieldBox]], current: int, direction: Direction) -> int | None:
    """The key of the field ``direction`` moves to from field ``current``,
    with ``rows`` in screen order; ``None`` where the focus stays (or
    ``current`` is in no row). On ↑/↓ a tie for nearest goes to the left."""
    placed = [sorted(row, key=lambda box: box.x) for row in rows if row]
    found = next(
        (
            (row_index, column)
            for row_index, row in enumerate(placed)
            for column, box in enumerate(row)
            if box.key == current
        ),
        None,
    )
    if found is None:
        return None
    row_index, column = found
    row = placed[row_index]
    match direction:
        case Direction.LEFT | Direction.RIGHT:
            step = -1 if direction is Direction.LEFT else 1
            target_column = column + step
            if not 0 <= target_column < len(row):
                return None
            return row[target_column].key
        case Direction.UP | Direction.DOWN:
            target_row = row_index + (-1 if direction is Direction.UP else 1)
            if not 0 <= target_row < len(placed):
                return None
            middle = row[column].middle
            nearest = min(placed[target_row], key=lambda box: (abs(box.middle - middle), box.x))
            return nearest.key
