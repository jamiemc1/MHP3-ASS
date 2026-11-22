"""How the query editor packs its fields: each drop-down's width,
whether the chosen skills share a row with the skill box, and the gaps
between its groups when it has the screen to itself.

Not a port: the TUI's own layout over ``Form1``'s controls. A compact
drop-down shows its text, a space and its arrow, with a cell of padding on
the right; its list adds a border and padding either side of each option.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

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


def chips_share_row(chips: Iterable[int], fields: int, room: int) -> bool:
    """The chosen skills (``chips``, each this many cells, a cell apart)
    fit before the skill box and tag drop-down (``fields`` cells), on a
    row ``room`` cells wide."""
    shared = chips_cells(chips) + fields <= room
    return shared


@dataclass(frozen=True)
class GroupSpacing:
    """The blank rows of an editor spread over the height: ``above`` the
    first group, and ``between`` each group and the next, in order."""

    above: int
    between: tuple[int, ...]


def group_spacing(
    room: int, content: int, gaps: int, most: int = 2, opened: int = 0
) -> GroupSpacing:
    """Spread groups ``content`` rows high over ``room`` rows. The
    ``gaps`` between them grow evenly with the rows to spare, each up to
    ``most``, the first ones a row ahead when the rows don't share out
    evenly; the block is centred in what the gaps leave. With no rows to
    spare there are no gaps, and the editor scrolls.

    A list ``opened`` rows high before the last gap (the offered skills)
    doesn't count in ``content``, so opening it moves nothing above it while
    it fits: it takes the rows below the block first, then the last gap,
    and only then the rows above the block and the other gaps, last first."""
    if gaps < 1:
        raise ValueError(f"groups need at least one gap between them, not {gaps}")
    spare = max(0, room - content)
    each = min(most, spare // gaps)
    ahead = spare - each * gaps if each < most else 0
    between = [each + 1 if index < ahead else each for index in range(gaps)]
    above = (spare - sum(between)) // 2
    below = spare - above - sum(between)
    needed = max(0, opened - below)
    taken = min(needed, between[-1])
    between[-1] -= taken
    needed -= taken
    taken = min(needed, above)
    above -= taken
    needed -= taken
    for index in reversed(range(gaps - 1)):
        taken = min(needed, between[index])
        between[index] -= taken
        needed -= taken
    spacing = GroupSpacing(above=above, between=tuple(between))
    return spacing


def chip_label(name: str) -> str:
    """A chosen skill's chip: its name and ✕, which removes it."""
    label = f"{name} ✕"
    return label


def chip_width(name: str) -> int:
    """The cells a chosen skill's chip takes: its label (``chip_label``),
    with a cell of padding either side."""
    width = cell_len(chip_label(name)) + 2
    return width
