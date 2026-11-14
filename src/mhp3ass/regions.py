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
