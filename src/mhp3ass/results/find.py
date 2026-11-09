"""Find Next in the results text.

Ported from ``frmFind::btnFind_Click`` (``legacy/frmFind.h:135-144``) and the
main form's ``FindDialogFoundText`` (``legacy/Form1.h:1938-1953``), which
applies the result to the results box's selection.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TextSelection:
    """A selection in the results text: its start offset and length."""

    start: int
    length: int


def find_next(text: str, needle: str, selection: TextSelection) -> TextSelection:
    """The results box's selection after Find Next for ``needle``.

    The search starts at the end of the current selection, or at 0 when that
    is the end of the text, and covers the whole text (the "Solutions
    found" header included). A match selects ``len(needle)`` characters; no
    match moves the caret to the end, so only the next press starts again
    from the top. An empty needle changes nothing.

    ``text`` is the text as the results box holds it: a RichTextBox stores
    line breaks as ``"\\n"``, so offsets differ from a ``"\\r\\n"`` string.

    The original's ``String.IndexOf( String, Int32 )`` compares with the
    current culture's rules; this compares ordinally until the harness's
    culture fixture says where they differ on the shipped data.
    """
    if needle == "":
        return selection
    start = selection.start + selection.length
    if start == len(text):
        start = 0
    index = text.find(needle, start)
    if index == -1:
        not_found = TextSelection(start=len(text), length=0)
        return not_found
    found = TextSelection(start=index, length=len(needle))
    return found
