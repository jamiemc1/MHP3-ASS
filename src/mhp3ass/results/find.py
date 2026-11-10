"""Find Next in the results text.

The counterpart of ``frmFind::btnFind_Click`` (``legacy/frmFind.h:135-144``)
and the main form's ``FindDialogFoundText`` (``legacy/Form1.h:1938-1953``).
How find behaves is presentation, not part of the port's contract, so this
is the port's own rule: case-insensitive, wrapping around to the top. The
original matches with the current culture's rules and only wraps on the
press after the last match (quirk 33).
"""

from __future__ import annotations

import re
from dataclasses import dataclass


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
