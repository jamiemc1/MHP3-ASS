"""What Esc does on the main screen: it backs out one level at a time.

Not a port: the TUI's own key. The order, first match wins:

1. close the open drop-down or popup;
2. clear the find text;
3. close the modal (the inspector shown over a narrow table counts as
   one), restore a maximised region, or collapse the editor (leave it,
   when there are no results for it to collapse over);
4. cancel the running search.

A modal closes on its own Esc, since closing one has its own steps (Options
keeps the theme on show, a picker answers ``None``), and a drop-down open in
it takes Esc first; the ``?`` help is a modal too. So ``escape_step``
decides the main screen's levels. Esc never quits; ``q`` does.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto


class EscapeStep(Enum):
    """The level Esc backs out of on the main screen."""

    CLOSE_POPUP = auto()
    CLEAR_FIND = auto()
    CLOSE_INSPECTOR = auto()
    RESTORE_REGION = auto()
    COLLAPSE_EDITOR = auto()
    LEAVE_EDITOR = auto()
    CANCEL_SEARCH = auto()
    NOTHING = auto()


@dataclass(frozen=True)
class EscapeState:
    """What is open on the main screen when Esc is pressed.

    ``inspector_open``: the inspector shows over the table, as it does on
    request on a narrow screen; ``maximised``: a region fills the screen
    (``z``); ``editor_open``: the query editor shows;
    ``can_collapse``: there are results for it to collapse over (before the
    first search there are none); ``editor_focused``: the focus is in it."""

    popup_open: bool
    find_open: bool
    inspector_open: bool
    maximised: bool
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
    if state.inspector_open:
        return EscapeStep.CLOSE_INSPECTOR
    if state.maximised:
        return EscapeStep.RESTORE_REGION
    if state.editor_open and state.can_collapse:
        return EscapeStep.COLLAPSE_EDITOR
    if state.editor_open and state.editor_focused:
        return EscapeStep.LEAVE_EDITOR
    if state.searching:
        return EscapeStep.CANCEL_SEARCH
    return EscapeStep.NOTHING
