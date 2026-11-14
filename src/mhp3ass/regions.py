"""The main screen's regions: the query, the charm sidebar and the sets table.

Not a port: the TUI's own layout. Each region has a number, which
``region_hint`` writes as a superscript (``¹``, ``²``, ``³``) for the
region's title.
"""

from __future__ import annotations

from enum import IntEnum


class Region(IntEnum):
    """The regions, numbered in screen order."""

    QUERY = 1
    CHARMS = 2
    SETS = 3


def region_hint(region: Region) -> str:
    """``region``'s number as superscript digits."""
    superscripts = str.maketrans("0123456789", "⁰¹²³⁴⁵⁶⁷⁸⁹")
    hint = str(int(region)).translate(superscripts)
    return hint


def next_region(current: Region | None, step: int, editor_open: bool, charms_shown: bool) -> Region:
    """The region Tab (``step`` 1) or Shift+Tab (-1) moves to from
    ``current``, round in screen order. The query is a stop only while its
    editor is open (``1`` opens it), and the charms only while they show
    (``charms_shown``); with focus in no region, Tab goes to the first and
    Shift+Tab to the last."""
    stops = [
        region
        for region in Region
        if (editor_open or region is not Region.QUERY)
        and (charms_shown or region is not Region.CHARMS)
    ]
    if current is None or current not in stops:
        start = -1 if step > 0 else len(stops)
    else:
        start = stops.index(current)
    region = stops[(start + step) % len(stops)]
    return region
