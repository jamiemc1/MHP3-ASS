"""Builders for single lines of the legacy data files, for synthetic test data."""

from __future__ import annotations


def armor_row(name: str, materials: str = ",,,,,,,") -> str:
    """An armour line: male, blademaster, rarity 1, 1 slot, HR 1, village 1,
    defence 10-20, no resistances, Attack +2, then the given 8 material fields."""
    row = f"{name},jname,1,1,1,1,1,1,10,20,0,0,0,0,0,Attack,2,,,,,,,,,{materials}"
    return row


def decoration_row(name: str, materials: str = "Ore,1,,,,,,") -> str:
    """A 1-slot decoration line: Attack +1, Defense -1, the given 8 material
    fields, no alternative recipe."""
    row = f"{name},jname,1,1,1,1,Attack,1,Defense,-1,{materials},,,,,,,,"
    return row
