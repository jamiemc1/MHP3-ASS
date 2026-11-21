"""``Solution::MatchesQuery`` and the stages it runs for one armour combination.

Ported from ``Solution::MatchesQuery`` and ``Solution::CalculateData``
(``legacy/Solution.cpp:660-724``, ``:742-757``); the stages live in this
package's modules.
"""

from __future__ import annotations

from enum import Enum

from mhp3ass.data import GameData
from mhp3ass.data.text import as_unsigned
from mhp3ass.query import Query
from mhp3ass.solution.bad_skills import check_bad_skills
from mhp3ass.solution.charm_reduction import (
    rearrange_decorations,
    reduce_charm,
    reduce_skills,
    reduce_slots,
)
from mhp3ass.solution.extra_skills import calculate_extra_skills
from mhp3ass.solution.fill import calculate_decorations
from mhp3ass.solution.initial import add_armor_stats, get_initial_data
from mhp3ass.solution.state import (
    CalculationData,
    LegacyNullReferenceError,
    Solution,
    allocated_slots,
    new_calculation_data,
)


def has_enough_points(data: CalculationData) -> bool:
    """MatchesQuery's points check (Solution.cpp:674-680): every query skill reached."""
    abilities = data.solution.abilities
    enough = all(
        abilities[skill.ability] >= data.need[skill.ability] for skill in data.query.skills
    )
    return enough


def finish(data: CalculationData) -> None:
    """MatchesQuery's last steps (Solution.cpp:717-722): the leftover body slots
    become one more spare group, and the decorations' difficulty is added."""
    solution = data.solution
    slots_spare = allocated_slots(solution)
    # An index past the 4-element array raises IndexError, as .NET's array does.
    slots_spare[solution.torso_slots_spare] = as_unsigned(
        slots_spare[solution.torso_slots_spare] + 1
    )
    for decoration in solution.decorations:
        solution.difficulty = as_unsigned(solution.difficulty + decoration.difficulty)


class Outcome(Enum):
    """How ``MatchesQuery`` ended: accepted, or which of its two checks returned false."""

    ACCEPTED = "accepted"
    REJECTED_POINTS = "rejected_points"  # Solution.cpp:679
    REJECTED_BAD_SKILLS = "rejected_bad_skills"  # Solution.cpp:684


def match(data: CalculationData, game: GameData) -> Outcome:
    """``Solution::MatchesQuery``'s body (Solution.cpp:672-723) on ``data``, which
    ``new_calculation_data`` set up; ``matches_query`` is the usual entry point."""
    solution = data.solution
    get_initial_data(data)
    calculate_decorations(data, allow_bad=True, allow_detrimental=True)
    if not has_enough_points(data):
        return Outcome.REJECTED_POINTS
    calculate_extra_skills(data)
    if not data.query.allow_bad and not check_bad_skills(data, game):
        return Outcome.REJECTED_BAD_SKILLS

    if solution.charm is not None:
        if solution.charm.custom:
            rearrange_decorations(data)
        else:
            reduce_slots(data)
            reduce_skills(data)
            rearrange_decorations(data)
            reduce_charm(data)
            calculate_extra_skills(data)
    finish(data)
    return Outcome.ACCEPTED


def matches_query(solution: Solution, query: Query, game: GameData) -> bool:
    """``Solution::MatchesQuery`` (Solution.cpp:660-724).

    Fills ``solution`` (armour and a per-combination copy of the worker's
    charm template) for ``query`` and says whether it gives every query
    skill. The filling pass allows bad skills and detrimental gems whatever
    the query says; the query's ``allow_bad`` only decides whether bad skills
    must then be repaired. A rejected solution keeps the state it reached.
    Reads ``game`` for the decorations the bad-skill repairs may use, and
    ``query.relevant_abilities``, which building the query set.
    """
    data = new_calculation_data(solution, query)
    accepted = match(data, game) is Outcome.ACCEPTED
    return accepted


def calculate_data(solution: Solution) -> None:
    """``Solution::CalculateData`` (Solution.cpp:742-757): the armour's stats summed
    again, as loading saved results does. Every piece is dereferenced, so an
    empty slot raises ``LegacyNullReferenceError``."""
    solution.fire_res = solution.ice_res = solution.thunder_res = 0
    solution.water_res = solution.dragon_res = 0
    solution.defence = solution.rarity = solution.difficulty = solution.max_defence = 0
    for armor in solution.armors:
        if armor is None:
            raise LegacyNullReferenceError("CalculateData dereferences an empty armour slot")
        add_armor_stats(solution, armor)
