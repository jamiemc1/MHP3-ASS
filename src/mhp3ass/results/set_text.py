"""One set as Markdown, for copying it and exporting it to a file.

Not a port: the original has no copy or export of a set (its result text
box only takes Select All and the RichTextBox's own copy,
``legacy/Form1.h:1955-1972``). The text holds what the inspector shows
(``results/inspector.py``), from the same ``SolutionDetails``: a table of
the pieces with their notes, the charm and the jewels (the chest's apart,
or the version that builds, where the inspector shows one), then the
spare slots and every skill the set gives (the search's, then the extras).
Above them, a heading naming the set by its pieces' short names and a line
with the search's hunter type, gender, HR and village.
"""

from __future__ import annotations

from collections.abc import Sequence

from mhp3ass.data.strings import DisplayStrings
from mhp3ass.model import ArmorType
from mhp3ass.query import Query
from mhp3ass.query_form import hunter_summary
from mhp3ass.results.details import SolutionDetails, spare_slots
from mhp3ass.results.inspector import (
    InspectorLine,
    charm_text,
    jewel_lines,
    piece_lines,
    spare_text,
)
from mhp3ass.results.short_names import ShortNames
from mhp3ass.solution.state import Solution


def set_heading(solution: Solution, short_names: ShortNames) -> str:
    """``## Baggi Cap · Rathian · Chain · Chain Belt · Ranguro``: the
    pieces' short names, head to legs, leaving out an empty slot."""
    names = [
        short_names.armor(armor.name, slot=slot)
        for slot, armor in zip(ArmorType, solution.armors, strict=True)
        if armor is not None
    ]
    heading = f"## {' · '.join(names)}"
    return heading


def _cell(text: str) -> str:
    """``text`` safe inside a Markdown table cell."""
    escaped = text.replace("\\", "\\\\").replace("|", "\\|")
    return escaped


def _table(lines: Sequence[InspectorLine]) -> str:
    # Markdown tables need a header row; empty cells would render as a blank row.
    rows = ["| Slot | Item |", "|---|---|"]
    rows.extend(f"| {_cell(line.label)} | {_cell(line.text)} |" for line in lines)
    table = "\n".join(rows)
    return table


def set_markdown(
    solution: Solution,
    details: SolutionDetails,
    query: Query,
    strings: DisplayStrings,
    short_names: ShortNames,
) -> str:
    """``solution`` as Markdown, from its ``details`` for the results' own
    ``query``. Ends with a newline.

    The jewels are as ``details`` gives them, so a caller wanting the
    worked-out placement passes details from ``solution_details`` with a
    game to fill the set in, not the inspector's while it works one out."""
    preamble = hunter_summary(
        hunter_type=query.hunter_type,
        gender=query.gender,
        hr=query.hr,
        elder_star=query.elder_star,
        strings=strings,
    )
    pieces = [
        InspectorLine(
            label=piece.label,
            text=piece.name if piece.note is None else f"{piece.name} {piece.note}",
        )
        for piece in piece_lines(details, strings)
    ]
    charm = InspectorLine(label="Charm", text=charm_text(details.charm))
    table = _table([*pieces, charm, *jewel_lines(details)])
    spare = spare_slots(solution)
    skills = ", ".join(skill.name for skill in [*query.skills, *details.extra_skills])
    summary = f"- Spare: {spare_text(spare, strings)}\n- Skills: {skills}"
    blocks = [set_heading(solution, short_names), preamble, table, summary]
    text = "\n\n".join(blocks) + "\n"
    return text
