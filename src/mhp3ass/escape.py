"""What Esc does on the main screen: it backs out one level at a time.

Not a port: the TUI's own key. The order, first match wins:

1. close the open drop-down or popup;
2. clear the find text;
3. close the modal, or collapse the editor (leave it, when there are no
   results for it to collapse over);
4. cancel the running search.

Esc never quits; ``q`` does.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto


class EscapeStep(Enum):
    """The level Esc backs out of."""

    CLOSE_POPUP = auto()
    CLEAR_FIND = auto()
    CLOSE_MODAL = auto()
    COLLAPSE_EDITOR = auto()
    LEAVE_EDITOR = auto()
    CANCEL_SEARCH = auto()
    NOTHING = auto()


@dataclass(frozen=True)
class EscapeState:
    """What is open when Esc is pressed.

    ``editor_open``: the query editor shows; ``can_collapse``: there are
    results for it to collapse over (before the first search there are
    none); ``editor_focused``: the focus is in it."""

    popup_open: bool
    find_open: bool
    modal_open: bool
    editor_open: bool
    can_collapse: bool
    editor_focused: bool
    searching: bool


def escape_step(state: EscapeState) -> EscapeStep:
    """The level Esc backs out of in ``state``."""
    if state.popup_open:
        return EscapeStep.CLOSE_POPUP
    if state.find_open:
        return EscapeStep.CLEAR_FIND
    if state.modal_open:
        return EscapeStep.CLOSE_MODAL
    if state.editor_open and state.can_collapse:
        return EscapeStep.COLLAPSE_EDITOR
    if state.editor_open and state.editor_focused:
        return EscapeStep.LEAVE_EDITOR
    if state.searching:
        return EscapeStep.CANCEL_SEARCH
    return EscapeStep.NOTHING
