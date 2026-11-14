"""One set as Markdown, for copying it and exporting it to a file.

Not a port: the original has no copy or export of a set (its result text
box only takes Select All and the RichTextBox's own copy,
``legacy/Form1.h:1955-1972``). The text holds what the inspector shows
(``results/inspector.py``), from the same ``SolutionDetails``: a table of
the pieces with their notes and the jewels (the chest's apart, or the
version that builds, where the inspector shows one), then the charm, the
spare slots and every skill the set gives (the search's, then the extras).
Above them, a heading naming the set by its pieces' short names and a line
with the search's hunter type, gender, HR and village.
"""

from __future__ import annotations

from collections.abc import Sequence

from mhp3ass.charms.naming import charm_name
from mhp3ass.data.strings import DisplayStrings
from mhp3ass.model import ArmorType
from mhp3ass.query import Query
from mhp3ass.query_form import hunter_summary
from mhp3ass.results.details import SlotsSpare, SolutionDetails
from mhp3ass.results.inspector import InspectorLine, jewel_lines, piece_lines, spare_text
from mhp3ass.results.short_names import ShortNames
from mhp3ass.solution.state import Solution


def set_heading(solution: Solution, short_names: ShortNames) -> str:
    """``## Baggi Cap · Rathian · Chain · Chain · Ranguro``: the pieces'
    short names, head to legs, leaving out an empty slot."""
    names = [
        short_names.armor(armor.name, slot=slot)
        for slot, armor in zip(ArmorType, solution.armors, strict=True)
        if armor is not None
    ]
    heading = f"## {' · '.join(names)}"
    return heading


def _cell(text: str) -> str:
    """``text`` safe inside a Markdown table cell."""
    escaped = text.replace("|", "\\|")
    return escaped


def _with_notes(pieces: Sequence[InspectorLine]) -> list[InspectorLine]:
    """``piece_lines`` with each note in its piece's cell: a table row per piece."""
    rows: list[InspectorLine] = []
    for line in pieces:
        if line.label == "" and rows:
            rows[-1] = InspectorLine(label=rows[-1].label, text=f"{rows[-1].text} {line.text}")
        else:
            rows.append(line)
    return rows


def _table(lines: Sequence[InspectorLine]) -> str:
    rows = ["| | |", "|---|---|"]
    rows.extend(f"| {_cell(line.label)} | {_cell(line.text)} |" for line in lines)
    table = "\n".join(rows)
    return table


def set_markdown(
    solution: Solution,
    details: SolutionDetails,
    query: Query,
    strings: DisplayStrings,
    short_names: ShortNames,
    piece_labels: Sequence[str],
) -> str:
    """``solution`` as Markdown, from its ``details`` for the results' own
    ``query``; ``piece_labels`` name the five armour slots in order. Ends
    with a newline."""
    preamble = hunter_summary(
        hunter_type=query.hunter_type,
        gender=query.gender,
        hr=query.hr,
        elder_star=query.elder_star,
        strings=strings,
    )
    pieces = piece_lines(solution, details, strings, piece_labels=piece_labels)
    table = _table([*_with_notes(pieces), *jewel_lines(details)])
    charm = "no charm" if details.charm is None else charm_name(details.charm)
    # The inspector leaves out no spare slots; a list of sets reads better with it.
    spare = (
        details.slots_spare if details.slots_spare is not None else SlotsSpare(total=0, groups=None)
    )
    skills = ", ".join(skill.name for skill in [*query.skills, *details.extra_skills])
    summary = "\n".join(
        [
            f"- Charm: {charm}",
            f"- Spare: {spare_text(spare, strings)}",
            f"- Skills: {skills}",
        ]
    )
    blocks = [set_heading(solution, short_names), preamble, table, summary]
    text = "\n\n".join(blocks) + "\n"
    return text
