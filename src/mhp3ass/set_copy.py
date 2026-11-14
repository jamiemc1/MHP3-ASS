"""Copying a set: when its text is ready, and the system's copy command.

Not a port: the original has no copy of a set (``legacy/Form1.h:1955-1972``
only selects and copies its result text box). The TUI copies through the
terminal (OSC 52, ``App.copy_to_clipboard``), which macOS Terminal doesn't
support, so on macOS it also runs ``pbcopy``.
"""

from __future__ import annotations

from mhp3ass.results.details import PlacementPending, SolutionDetails


def system_copy_command(platform: str) -> list[str] | None:
    """The command that copies its standard input on ``platform``
    (``sys.platform``), where the terminal may not: ``pbcopy`` on macOS;
    ``None`` elsewhere, where OSC 52 is left to do it."""
    command = ["pbcopy"] if platform == "darwin" else None
    return command


def copied_notice(number: int, details: SolutionDetails) -> str:
    """The notice once set ``number`` is copied; during a search, a set
    whose placement waits for it says its jewels aren't placed yet."""
    jewels = details.chest_jewels
    if isinstance(jewels, PlacementPending) and jewels.while_searching:
        notice = (
            f"Copied set {number:,}, without its jewels' places:"
            " copy it again after the search for them."
        )
        return notice
    notice = f"Copied set {number:,}."
    return notice


def jewels_being_worked_out(details: SolutionDetails) -> bool:
    """Whether the inspector is still working out ``details``' placement
    in a thread, so its text would say so rather than give the jewels. A
    placement waiting for a search to finish isn't: it stays as it is
    until then."""
    jewels = details.chest_jewels
    working = isinstance(jewels, PlacementPending) and not jewels.while_searching
    return working
