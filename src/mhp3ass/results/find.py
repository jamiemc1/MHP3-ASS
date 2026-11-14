"""Find Next in the results text, and find over the results table's rows.

The counterpart of ``frmFind::btnFind_Click`` (``legacy/frmFind.h:135-144``)
and the main form's ``FindDialogFoundText`` (``legacy/Form1.h:1938-1953``).
How find behaves is presentation, not part of the port's contract, so this
is the port's own rule: case-insensitive, wrapping around to the top. The
original matches with the current culture's rules and only wraps on the
press after the last match (quirk 33). The TUI shows a table, so it finds
rows (``find_row``) by the names in each set (``row_text``).
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass

from mhp3ass.charms.naming import charm_name
from mhp3ass.model import ArmorType
from mhp3ass.query import Query
from mhp3ass.results.short_names import ShortNames
from mhp3ass.solution.state import Solution


@dataclass(frozen=True)
class TextSelection:
    """A selection in the results text: its start offset and length."""

    start: int
    length: int

    def __post_init__(self) -> None:
        if self.start < 0 or self.length < 0:
            raise ValueError(f"a selection can't start or extend negatively: {self}")


def find_next(text: str, needle: str, selection: TextSelection) -> TextSelection | None:
    """The next match of ``needle`` after ``selection``, wrapping to the top; None if none.

    Matching ignores case. The search starts at the end of the current
    selection and, finding nothing after it, continues from the top, so the
    current match is found again when it is the only one. An empty needle
    finds nothing. A selection reaching past the text raises ``ValueError``.

    Case-insensitive matching uses ``re.IGNORECASE`` rather than comparing
    ``casefold()`` strings, because case folding can change a string's length
    (``"ß"`` folds to ``"ss"``) and the returned offsets must index ``text``.
    """
    start = selection.start + selection.length
    if start > len(text):
        raise ValueError(f"selection {selection} reaches past the {len(text)}-character text")
    if needle == "":
        return None
    pattern = re.compile(re.escape(needle), flags=re.IGNORECASE)
    match = pattern.search(text, start)
    if match is None:
        match = pattern.search(text, 0)
    if match is None:
        return None
    found = TextSelection(start=match.start(), length=match.end() - match.start())
    return found


def row_text(solution: Solution, query: Query, short_names: ShortNames | None = None) -> str:
    """What find matches in a set: its pieces, jewels, charm and extra skills,
    by name, one per line (so a match can't run from one name into the next).
    The extra skills are those the inspector lists: not the results' own
    ``query``'s skills (``solution_details``). With ``short_names``, the
    pieces' and charm's short names (as the table shows them) are matched too."""
    names = [armor.name for armor in solution.armors if armor is not None]
    names.extend(decoration.name for decoration in solution.decorations)
    if solution.charm is not None:
        names.append(charm_name(solution.charm))
    names.extend(skill.name for skill in solution.extra_skills if skill not in query.skills)
    if short_names is not None:
        names.extend(
            short_names.armor(armor.name, slot)
            for armor, slot in zip(solution.armors, ArmorType, strict=True)
            if armor is not None
        )
        if solution.charm is not None:
            names.append(short_names.charm(solution.charm))
    text = "\n".join(names)
    return text


def find_row(texts: Sequence[str], needle: str, start: int, step: int = 1) -> int | None:
    """The next row after ``start`` (``step`` 1) or before it (``step`` -1) whose
    text contains ``needle``, ignoring case, wrapping round, with ``start``
    itself checked last; None if no row matches or the needle is empty."""
    if step not in (1, -1):
        raise ValueError(f"find steps 1 or -1 rows, not {step}")
    if not 0 <= start < len(texts):
        raise ValueError(f"row {start} isn't one of the {len(texts)} rows")
    if needle == "":
        return None
    folded = needle.casefold()
    for offset in range(1, len(texts) + 1):
        row = (start + step * offset) % len(texts)
        if folded in texts[row].casefold():
            return row
    return None
