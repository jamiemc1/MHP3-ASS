"""The state ``MatchesQuery`` builds up for one armour combination.

Ported from ``Solution`` (``legacy/Solution.h:39-71``), ``CalculationData``
(``legacy/Solution.cpp:9-16``) and the setup at the top of
``Solution::MatchesQuery`` (``Solution.cpp:662-670``).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from mhp3ass.model import Ability, Armor, Charm, Decoration, Skill
from mhp3ass.query import Query


@dataclass(slots=True, eq=False)
class Solution:
    """``Solution``: one armour combination with its charm, and what ``MatchesQuery``
    works out for it.

    ``armors`` holds head, body, arms, waist and legs, with ``None`` for an
    empty slot. ``abilities`` is the original's ``Dictionary``: Python keeps
    its insertion order, which is .NET's while nothing is removed (nothing
    ever is). Fields that are ``unsigned`` in the original (the slot counters,
    ``torso_multiplier``, ``defence``, ``max_defence``, ``rarity``,
    ``difficulty`` and ``slots_spare``'s entries) hold C++ ``unsigned``
    values, so every store to them goes through ``as_unsigned``.
    ``slots_spare`` stays ``None`` until ``GetInitialData`` allocates it.
    """

    armors: list[Armor | None]
    charm: Charm | None
    decorations: list[Decoration] = field(default_factory=list)
    body_decorations: list[Decoration] = field(default_factory=list)
    non_body_decorations: list[Decoration] = field(default_factory=list)
    extra_skills: list[Skill] = field(default_factory=list)
    bad_skills: list[Skill] = field(default_factory=list)
    abilities: dict[Ability, int] = field(default_factory=dict)
    torso_slots_spare: int = 0
    torso_multiplier: int = 0
    total_slots_spare: int = 0
    fire_res: int = 0
    ice_res: int = 0
    water_res: int = 0
    thunder_res: int = 0
    dragon_res: int = 0
    defence: int = 0
    max_defence: int = 0
    rarity: int = 0
    difficulty: int = 0
    slots_spare: list[int] | None = None


@dataclass(slots=True, eq=False)
class CalculationData:
    """``CalculationData``: per-combination scratch state.

    ``need`` maps each query ability (and each charm ability, at 0) to the
    points it needs; ``relevant`` holds the query's skills (the original's
    ``Map_t< Skill^, int >`` is only ever tested for keys).
    ``rel_decoration_map[size]`` lists the query's relevant decorations of
    that slot size, in relevance order.
    """

    query: Query
    solution: Solution
    need: dict[Ability, int] = field(default_factory=dict)
    relevant: dict[Skill, int] = field(default_factory=dict)
    rel_decoration_map: list[list[Decoration]] = field(default_factory=list)


def build_rel_decoration_map(query: Query) -> list[list[Decoration]]:
    """The query's relevant decorations grouped by slot size 0-3 (Solution.cpp:665-670)."""
    rel_decoration_map: list[list[Decoration]] = [[] for _ in range(4)]
    for decoration in query.rel_decorations:
        rel_decoration_map[decoration.slots_required].append(decoration)
    return rel_decoration_map


def new_calculation_data(solution: Solution, query: Query) -> CalculationData:
    """The ``CalculationData`` ``MatchesQuery`` starts from (Solution.cpp:662-670)."""
    data = CalculationData(
        query=query,
        solution=solution,
        rel_decoration_map=build_rel_decoration_map(query),
    )
    return data
