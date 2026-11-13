"""What makes a set hard to build: the materials behind its difficulty.

A new view of the difficulty the original sums (``legacy/LoadedData.cpp``
for each piece's and jewel's difficulty, ``Solution.cpp:719-722``,
``:754`` for the set's): each material that carries a difficulty, with how
many the set's pieces and jewels count for. As the loaders sum it, a piece
counts every unit of a material and a jewel each material once, so
``sum(count * material.difficulty)`` is the set's difficulty as a search
finds it.
"""

from __future__ import annotations

from dataclasses import dataclass

from mhp3ass.model import Material
from mhp3ass.solution.state import Solution


@dataclass(frozen=True)
class MaterialCount:
    material: Material
    count: int


def hard_materials(solution: Solution) -> list[MaterialCount]:
    """The materials with a difficulty that ``solution``'s pieces and jewels
    need, in the order they first appear (pieces in slot order, then the
    jewels), each with its count. Event materials have no difficulty, so
    they aren't listed."""
    # Materials compare by identity, and a dict keeps first-appearance order.
    counts: dict[Material, int] = {}
    needs = [
        (component.material, component.amount)
        for armor in solution.armors
        if armor is not None
        for component in armor.components
    ]
    needs += [
        (component.material, 1)
        for decoration in solution.decorations
        for component in decoration.components
    ]
    for material, count in needs:
        if material.difficulty > 0:
            counts[material] = counts.get(material, 0) + count
    hard = [MaterialCount(material=material, count=count) for material, count in counts.items()]
    return hard
