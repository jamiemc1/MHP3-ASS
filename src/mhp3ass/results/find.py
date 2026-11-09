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

    def __post_init__(self) -> None:
        if self.start < 0 or self.length < 0:
            raise ValueError(f"a selection can't start or extend negatively: {self}")


def find_next(text: str, needle: str, selection: TextSelection) -> TextSelection:
    """The results box's selection after Find Next for ``needle``.

    The search starts at the end of the current selection, or at 0 when that
    is the end of the text, and covers the whole text (the "Solutions
    found" header included). A match selects ``len(needle)`` characters. No
    match moves the caret to the end, so the next press starts again from
    the top; a match that ends at the end of the text does the same
    straight away. An empty needle changes nothing.

    ``text`` is the text as the results box holds it: a RichTextBox stores
    line breaks as ``"\\n"``, so offsets differ from a ``"\\r\\n"`` string.
    A selection reaching past the text raises ``ValueError``, where
    ``String.IndexOf`` throws ``ArgumentOutOfRangeException``.

    The original's ``String.IndexOf( String, Int32 )`` compares with the
    current culture's rules; this compares ordinally until the harness's
    culture fixture says where they differ on the shipped data.
    """
    if needle == "":
        return selection
    start = selection.start + selection.length
    if start > len(text):
        raise ValueError(f"selection {selection} reaches past the {len(text)}-character text")
    if start == len(text):
        start = 0
    index = text.find(needle, start)
    if index == -1:
        not_found = TextSelection(start=len(text), length=0)
        return not_found
    found = TextSelection(start=index, length=len(needle))
    return found
