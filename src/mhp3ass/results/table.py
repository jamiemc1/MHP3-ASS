"""The results table's text: one row per set.

A new layout of what ``Form1::UpdateResultString`` shows for each result
(``legacy/Form1.h:1569-1655``): the five pieces, defence, the spare slots
and the charm. The pieces and the charm are shortened (``short_names``);
the pieces are cut with ``…`` where the number, the five pieces and the
defence would not fit otherwise (``fit_widths``, ``truncate``), never below
6 characters; the columns after them are reached by scrolling, so the table
scrolls rather than squeezes.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass

from rich.cells import cell_len, set_cell_size

from mhp3ass.data.text import as_signed
from mhp3ass.model import ArmorType
from mhp3ass.results.details import SlotsSpare, slots_spare
from mhp3ass.results.short_names import ShortNames
from mhp3ass.results.sorting import SortKey
from mhp3ass.solution.state import Solution


@dataclass(frozen=True)
class TableRow:
    """One set's cells, in column order after its number."""

    head: str
    body: str
    arms: str
    waist: str
    legs: str
    defence: str
    spare: str
    charm: str


def spare_text(spare: SlotsSpare | None) -> str:
    """Blank with nothing spare; the total when the groups don't show; else
    each group size with its count, smallest first, as ``2x1 1x3``."""
    if spare is None:
        return ""
    if spare.groups is None:
        return str(spare.total)
    counts = Counter(spare.groups)
    text = " ".join(f"{count}x{size}" for size, count in sorted(counts.items()))
    return text


def table_row(solution: Solution, sort_key: SortKey, names: ShortNames) -> TableRow:
    """``solution``'s cells with the pieces and charm shortened by ``names``;
    an empty armour slot is blank, as is a charm-free set's charm."""
    pieces = [
        names.armor(armor.name, slot) if armor is not None else ""
        for armor, slot in zip(solution.armors, ArmorType, strict=True)
    ]
    head, body, arms, waist, legs = pieces
    row = TableRow(
        head=head,
        body=body,
        arms=arms,
        waist=waist,
        legs=legs,
        defence=str(as_signed(solution.defence)),
        spare=spare_text(slots_spare(solution, sort_key)),
        charm=names.charm(solution.charm) if solution.charm is not None else "",
    )
    return row


def truncate(text: str, width: int) -> str:
    """``text`` cut to ``width`` terminal cells (wide characters count
    twice), ending in ``…`` when cut; unchanged when it fits."""
    if cell_len(text) <= width:
        return text
    cut = set_cell_size(text, max(width - 1, 0)).rstrip() + "…"
    return cut


def fit_widths(
    widths: Sequence[int],
    available: int,
    must_fit: frozenset[int],
    fixed: frozenset[int],
    minimum: int = 6,
) -> list[int]:
    """Column widths that fit the ``must_fit`` columns in ``available``
    cells, cutting the widest of them first to a common cap. The ``fixed``
    columns, those already at most ``minimum`` wide and those not in
    ``must_fit`` (reached by scrolling) keep their widths. No column is cut
    below ``minimum``, so the ``must_fit`` columns can still need more than
    ``available``."""
    fitted = list(widths)
    if sum(fitted[index] for index in must_fit) <= available:
        return fitted
    cuttable = [index for index in must_fit if index not in fixed]
    budget = available - sum(fitted[index] for index in must_fit if index in fixed)
    cap = max((fitted[index] for index in cuttable), default=minimum)
    # The largest cap, no lower than minimum, whose capped columns fit the budget.
    while cap > minimum and sum(min(fitted[index], cap) for index in cuttable) > budget:
        cap -= 1
    for index in cuttable:
        fitted[index] = min(fitted[index], cap)
    return fitted
