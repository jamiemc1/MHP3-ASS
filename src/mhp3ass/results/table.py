"""The results table's text: one row per set.

A new layout of what ``Form1::UpdateResultString`` shows for each result
(``legacy/Form1.h:1569-1655``): the five pieces, defence, the spare slots
and the charm, by the original's names. Full names; shortening for narrow
terminals is separate.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

from mhp3ass.charms.naming import charm_name
from mhp3ass.data.text import as_signed
from mhp3ass.results.details import SlotsSpare, slots_spare
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


def table_row(solution: Solution, sort_key: SortKey) -> TableRow:
    """``solution``'s cells; an empty armour slot is blank, as is a charm-free set's charm."""
    names = [armor.name if armor is not None else "" for armor in solution.armors]
    head, body, arms, waist, legs = names
    row = TableRow(
        head=head,
        body=body,
        arms=arms,
        waist=waist,
        legs=legs,
        defence=str(as_signed(solution.defence)),
        spare=spare_text(slots_spare(solution, sort_key)),
        charm=charm_name(solution.charm) if solution.charm is not None else "",
    )
    return row
