"""Pane titles with their region's number, dimmed: ``² Charms``."""

from __future__ import annotations

from textual.content import Content

from mhp3ass.regions import Region, region_hint


def region_title(region: Region, text: str) -> Content:
    title = Content.assemble((f"{region_hint(region)} ", "dim"), text)
    return title
