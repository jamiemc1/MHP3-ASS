"""Builders for synthetic records in Solution-stage tests."""

from __future__ import annotations

from mhp3ass.model import Ability, AbilityPair, Decoration


def make_jewel(
    name: str,
    first: Ability,
    amount: int,
    slots: int = 1,
    second: Ability | None = None,
    second_amount: int = 0,
) -> Decoration:
    """A decoration of ``slots`` slots, HR 1 / village 1, with one or two skills."""
    decoration = Decoration(name=name, index=0, rarity=1, slots_required=slots, hr=1, elder_star=1)
    decoration.abilities = [AbilityPair(ability=first, amount=amount)]
    if second is not None:
        decoration.abilities.append(AbilityPair(ability=second, amount=second_amount))
    return decoration
