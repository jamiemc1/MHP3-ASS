"""Shrinking the charm a combination needs, and consolidating its 1-slot gems.

Ported from ``Num1SlotDecorations``, ``PotentialSpareSlots``,
``RoomFor3Slot``, ``RoomFor2Slot``, ``SwapOut``, ``Solution::ReduceSlots``,
``Solution::ReduceSkills``, ``Solution::RearrangeDecorations`` and
``Solution::ReduceCharm`` (``legacy/Solution.cpp:487-658``).

``MatchesQuery`` runs these after the bad-skill check. A custom charm (my
charms, or the Auto-Guard worker's) only has its gems rearranged; a
generated charm also loses the slots and points the solution doesn't need,
and becomes ``None`` when nothing is left. ``SwapOut`` and ``ReduceCharm``
adjust ``abilities`` by raw amounts: the torso multiplier is ignored and the
body/non-body lists keep the gems they had (quirk candidate L).
"""

from __future__ import annotations

from mhp3ass.data.text import as_unsigned
from mhp3ass.decorations import best_decoration_in_map
from mhp3ass.model import Ability, Charm, Decoration
from mhp3ass.solution.fill import calculate_decorations
from mhp3ass.solution.state import CalculationData, LegacyNullReferenceError, Solution


class LegacyListIndexError(IndexError):
    """A ``List`` indexed past its end (.NET ``ArgumentOutOfRangeException``)."""


def _charm(solution: Solution) -> Charm:
    """The charm these functions dereference unchecked."""
    if solution.charm is None:
        raise LegacyNullReferenceError("the charm is dereferenced unchecked")
    return solution.charm


def num_1slot_decorations(solution: Solution, ability: Ability) -> int:
    """``Num1SlotDecorations`` (Solution.cpp:487-505): the 1-slot gems of ``ability``
    outside the body, plus the body's when the torso multiplier is 1."""
    count = sum(
        1
        for decoration in solution.non_body_decorations
        if decoration.slots_required == 1 and decoration.abilities[0].ability is ability
    )
    if solution.torso_multiplier == 1:
        count += sum(
            1
            for decoration in solution.body_decorations
            if decoration.slots_required == 1 and decoration.abilities[0].ability is ability
        )
    return count


def potential_spare_slots(data: CalculationData, slot_size: int) -> int:
    """``PotentialSpareSlots`` (Solution.cpp:507-521): the slot groups of
    ``slot_size`` the armour, weapon and charm offer, less the decorations of
    that size already used.

    Every armour piece is dereferenced, so an empty slot raises
    ``LegacyNullReferenceError`` here (quirk candidate N).
    """
    solution = data.solution
    count = 0
    for armor in solution.armors:
        if armor is None:
            raise LegacyNullReferenceError("PotentialSpareSlots dereferences an empty armour slot")
        count += armor.num_slots == slot_size
    count += data.query.weapon_slots_allowed == slot_size
    count += _charm(solution).num_slots == slot_size
    count -= sum(1 for decoration in solution.decorations if decoration.slots_required == slot_size)
    return count


def room_for_3_slot(data: CalculationData) -> bool:
    """``RoomFor3Slot`` (Solution.cpp:523-528)."""
    free3 = potential_spare_slots(data, 3)
    room = free3 > 0 and free3 + potential_spare_slots(data, 2) > 0
    return room


def room_for_2_slot(data: CalculationData) -> bool:
    """``RoomFor2Slot`` (Solution.cpp:530-535)."""
    free3 = potential_spare_slots(data, 3)
    room = free3 + potential_spare_slots(data, 2) > 0
    return room


def swap_out(solution: Solution, decoration: Decoration) -> None:
    """``SwapOut`` (Solution.cpp:537-558).

    Removes the first ``slots_required`` 1-slot gems of the decoration's
    first ability (searching ``decorations``, body gems included) and adds
    the decoration in their place. Abilities move by raw amounts; the
    body/non-body lists, ``total_slots_spare`` and ``slots_spare`` are left
    as they were. Running out of gems indexes past the list, as the original
    does with its ``Assert`` compiled out. Plain indexing raises ``KeyError``
    where the original's ``Dictionary`` would throw.
    """
    count = 0
    i = 0
    while count < decoration.slots_required:
        if i >= len(solution.decorations):
            raise LegacyListIndexError(f"SwapOut ran past {len(solution.decorations)} decorations")
        current = solution.decorations[i]
        if (
            current.slots_required == 1
            and current.abilities[0].ability is decoration.abilities[0].ability
        ):
            for pair in current.abilities:
                solution.abilities[pair.ability] -= pair.amount
            del solution.decorations[i]
            count += 1
        else:
            i += 1
    for pair in decoration.abilities:
        solution.abilities[pair.ability] += pair.amount
    solution.decorations.append(decoration)


def reduce_slots(data: CalculationData) -> None:
    """``Solution::ReduceSlots`` (Solution.cpp:560-575).

    With slots free, finds the smallest free group at least the charm's size,
    moves its remainder to the group size left over and drops the charm's
    slots. The remainder lands in ``slots_spare[0]`` when the sizes match.
    """
    solution = data.solution
    if solution.total_slots_spare == 0:
        return
    charm = _charm(solution)
    slots_spare = solution.slots_spare
    if slots_spare is None:
        raise LegacyNullReferenceError("slots_spare is allocated by get_initial_data")
    i = charm.num_slots
    while i <= 3 and not slots_spare[i]:
        i += 1
    if i <= 3:
        slots_spare[i - charm.num_slots] = as_unsigned(slots_spare[i - charm.num_slots] + 1)
        slots_spare[i] = as_unsigned(slots_spare[i] - 1)
        solution.total_slots_spare = as_unsigned(solution.total_slots_spare - charm.num_slots)
        charm.num_slots = 0


def reduce_skills(data: CalculationData) -> None:
    """``Solution::ReduceSkills`` (Solution.cpp:577-591).

    With slots free, raises ``need`` by the charm's points, fills again with
    neither bad skills nor detrimental gems allowed, then lowers ``need``
    back, so the free slots try to cover what the charm gives.
    """
    solution = data.solution
    if solution.total_slots_spare == 0:
        return
    charm = _charm(solution)
    for pair in charm.abilities:
        data.need[pair.ability] += pair.amount
    calculate_decorations(data, allow_bad=False, allow_detrimental=False)
    for pair in charm.abilities:
        data.need[pair.ability] -= pair.amount


def rearrange_decorations(data: CalculationData) -> None:
    """``Solution::RearrangeDecorations`` (Solution.cpp:593-631).

    For each charm ability, swaps three of its 1-slot gems for its best
    3-slot gem, or two for its best 2-slot gem, while there's room
    (``PotentialSpareSlots``) and enough 1-slot gems. ``num1`` counts the
    gems once, up front, so later swaps don't recount them.
    """
    solution = data.solution
    charm = _charm(solution)
    for pair in charm.abilities:
        num1 = num_1slot_decorations(solution, pair.ability)
        best3 = best_decoration_in_map(pair.ability, 3, data.rel_decoration_map)
        best2 = best_decoration_in_map(pair.ability, 2, data.rel_decoration_map)
        replaced = True
        while replaced:
            replaced = False
            if num1 >= 3:
                if best3 is not None and best3.slots_required == 3 and room_for_3_slot(data):
                    replaced = True
                    swap_out(solution, best3)
                    num1 -= 3
                elif best2 is not None and best2.slots_required == 2 and room_for_2_slot(data):
                    replaced = True
                    swap_out(solution, best2)
                    num1 -= 2
            elif (
                num1 == 2
                and best2 is not None
                and best2.slots_required == 2
                and room_for_2_slot(data)
            ):
                replaced = True
                swap_out(solution, best2)
                num1 -= 2


def reduce_charm(data: CalculationData) -> None:
    """``Solution::ReduceCharm`` (Solution.cpp:633-658).

    For each charm ability the query needs, takes off the points the
    solution has beyond the need (all of them at most), then drops skills
    left at 0 and the charm itself when it has neither slots nor skills.
    An ability short of its need (``extra < 0``, with the ``Assert`` compiled
    out) gets points added instead (quirk candidate O).
    """
    solution = data.solution
    charm = _charm(solution)
    for pair in charm.abilities:
        need = data.need[pair.ability]
        if need > 0:
            have = solution.abilities[pair.ability]
            extra = have - need
            take_off = pair.amount if extra >= pair.amount else extra
            pair.amount -= take_off
            solution.abilities[pair.ability] -= take_off
    charm.abilities[:] = [pair for pair in charm.abilities if pair.amount != 0]
    if charm.num_slots == 0 and len(charm.abilities) == 0:
        solution.charm = None
