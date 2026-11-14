"""The main screen's regions: the query, the charm sidebar and the sets table.

Not a port: the TUI's own layout. Each region has a number, shown as a
superscript in its title (``¹ Query``, ``² Charms``, ``³ Sets``).
"""

from __future__ import annotations

from enum import IntEnum


class Region(IntEnum):
    """The regions, numbered in screen order."""

    QUERY = 1
    CHARMS = 2
    SETS = 3


def region_hint(region: Region) -> str:
    """``region``'s number as a superscript digit."""
    superscripts = {Region.QUERY: "¹", Region.CHARMS: "²", Region.SETS: "³"}
    hint = superscripts[region]
    return hint
