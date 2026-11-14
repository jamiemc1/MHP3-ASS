"""How the query editor packs its fields: each drop-down's width, and
whether the chosen skills share a row with the skill box.

Not a port: the TUI's own layout over ``Form1``'s controls. A compact
drop-down shows its text, a space and its arrow, with a cell of padding on
the right; its list adds a border and padding either side of each option.
"""

from __future__ import annotations

from collections.abc import Iterable

from rich.cells import cell_len


def select_width(labels: Iterable[str]) -> int:
    """The cells a compact drop-down needs for the longest of ``labels``,
    so neither it nor its open list cuts one."""
    longest = max((cell_len(label) for label in labels), default=0)
    # The open list's border and padding: one cell either side of each.
    width = longest + 4
    return width


def chips_cells(chips: Iterable[int]) -> int:
    """The cells the chosen skills' chips take on a row, each ``chips``
    cells wide with a cell after it."""
    chip_widths = list(chips)
    cells = sum(chip_widths) + len(chip_widths)
    return cells


def chips_share_row(label: int, chips: Iterable[int], fields: int, room: int) -> bool:
    """The chosen skills (``chips``, each this many cells, a cell apart)
    fit after their ``label`` and before the skill box and tag drop-down
    (``fields`` cells), on a row ``room`` cells wide."""
    shared = label + chips_cells(chips) + fields <= room
    return shared


def chip_label(name: str) -> str:
    """A chosen skill's chip: its name and ✕, which removes it."""
    label = f"{name} ✕"
    return label


def chip_width(name: str) -> int:
    """The cells a chosen skill's chip takes: its label (``chip_label``),
    with a cell of padding either side."""
    width = cell_len(chip_label(name)) + 2
    return width
