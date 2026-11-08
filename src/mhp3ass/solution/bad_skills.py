"""Repairing a combination whose decorations gave it a skill with negative points.

Ported from ``GetBestAvailableDecoration``, ``Solution::FixBadSkill``,
``FixBadSkills``, ``CheckBadSkills``, ``Count1SocketGems``,
``GetReplacable``, ``ReorderGems`` and ``Replace``
(``legacy/Solution.cpp:48-206``).

``MatchesQuery`` tries two repairs when bad skills aren't allowed: spend
free slots on decorations of each bad skill's ability (``FixBadSkills``),
or swap 1-slot gems whose second skill caused it for a bigger gem
(``ReorderGems``). Neither re-checks what its own decorations add, and
``Replace`` ignores the torso multiplier and the body/non-body lists.
These functions take the game for the decoration-by-ability map the
original reads as a static.
"""

from __future__ import annotations

from dataclasses import dataclass

from mhp3ass.data import GameData
from mhp3ass.data.text import as_unsigned
from mhp3ass.decorations import best_decoration_for_query, best_decoration_in_map
from mhp3ass.model import Ability, Decoration, Skill
from mhp3ass.solution.extra_skills import calculate_extra_skills
from mhp3ass.solution.initial import add_decoration, detrimental
from mhp3ass.solution.state import CalculationData, LegacyNullReferenceError, Solution


def best_available_decoration(
    data: CalculationData, game: GameData, ability: Ability, slots_spare: int
) -> Decoration | None:
    """``GetBestAvailableDecoration`` (Solution.cpp:48-53).

    A relevant ability looks in the relevant decorations by size (largest
    first); any other ability uses the query overload, which prefers fewer
    slots and raises ``NoDecorationsError`` for an ability with no
    decorations (quirk 8).
    """
    if ability.relevant:
        decoration = best_decoration_in_map(ability, slots_spare, data.rel_decoration_map)
    else:
        decoration = best_decoration_for_query(game, ability, slots_spare, data.query)
    return decoration


def _require(decoration: Decoration | None, where: str) -> Decoration:
    if decoration is None:
        raise LegacyNullReferenceError(f"null decoration dereferenced at {where}")
    return decoration


def fix_bad_skill(data: CalculationData, game: GameData, skill: Skill) -> bool:
    """``Solution::FixBadSkill`` (Solution.cpp:55-100).

    Adds decorations of the bad skill's ability, first in the body's free
    slots (times the torso multiplier), then in the largest free non-body
    group, splitting a bigger group when the decoration's size has none.
    Returns as soon as the ability is above -10. The decoration is re-picked
    for smaller groups (``:96-97``) without the ``Detrimental`` check made at
    ``:73``, and without a null check: a re-pick that finds nothing raises
    ``LegacyNullReferenceError`` on the next pass (``:78``).
    """
    solution = data.solution
    while solution.torso_slots_spare > 0:
        decoration = best_available_decoration(
            data, game, skill.ability, solution.torso_slots_spare
        )
        if decoration is None or detrimental(decoration, data):
            return False
        solution.torso_slots_spare = as_unsigned(
            solution.torso_slots_spare - decoration.slots_required
        )
        if add_decoration(
            solution, decoration, solution.torso_multiplier, solution.body_decorations
        ):
            return True

    # The original first reads slots_spare here (Solution.cpp:68).
    slots_spare = solution.slots_spare
    if slots_spare is None:
        raise LegacyNullReferenceError("slots_spare is allocated by get_initial_data")
    max_slots = 3
    while max_slots > 0 and not slots_spare[max_slots]:
        max_slots -= 1
    if max_slots == 0:
        return False

    picked = best_available_decoration(data, game, skill.ability, max_slots)
    if picked is None or detrimental(picked, data):
        return False

    while max_slots > 0:
        decoration = _require(picked, "Solution.cpp:78")
        size = decoration.slots_required
        if slots_spare[size] == 0:
            if slots_spare[size + 1] == 0:
                slots_spare[3] = as_unsigned(slots_spare[3] - 1)
                slots_spare[2] = as_unsigned(slots_spare[2] + 1)
            else:
                slots_spare[size + 1] = as_unsigned(slots_spare[size + 1] - 1)
                slots_spare[1] = as_unsigned(slots_spare[1] + 1)
        else:
            slots_spare[size] = as_unsigned(slots_spare[size] - 1)

        if add_decoration(solution, decoration, 1, solution.non_body_decorations):
            return True

        while max_slots > 0 and not slots_spare[max_slots]:
            max_slots -= 1
            picked = best_available_decoration(data, game, skill.ability, max_slots)
    return False


def fix_bad_skills(data: CalculationData, game: GameData) -> bool:
    """``Solution::FixBadSkills`` (Solution.cpp:103-110): fix each bad skill in turn,
    then recompute the extra and bad skills (which a fix can leave non-empty)."""
    for skill in data.solution.bad_skills:
        if not fix_bad_skill(data, game, skill):
            return False
    calculate_extra_skills(data)
    return True


def check_bad_skills(data: CalculationData, game: GameData) -> bool:
    """``Solution::CheckBadSkills`` (Solution.cpp:112-115): no bad skills, or free
    slots that fix them, or a gem reorder that does."""
    solution = data.solution
    fine = (
        len(solution.bad_skills) == 0
        or (solution.total_slots_spare > 0 and fix_bad_skills(data, game))
        or reorder_gems(data, game)
    )
    return fine


@dataclass(frozen=True)
class OneSlotGems:
    """``Count1SocketGems``' result: the 1-slot gem used most, and how often."""

    decoration: Decoration
    count: int


def count_1_socket_gems(solution: Solution, ability: Ability) -> OneSlotGems | None:
    """``Solution::Count1SocketGems`` (Solution.cpp:117-147).

    Among the 1-slot gems whose second skill is ``ability``, the one used
    most often. A strict ``>`` keeps the first gem to reach the top count.
    ``None`` where the original returns a null gem with a count of 0.
    """
    count = 0
    best = None
    decoration_count: dict[Decoration, int] = {}
    for decoration in solution.decorations:
        if (
            decoration.slots_required == 1
            and len(decoration.abilities) == 2
            and decoration.abilities[1].ability is ability
        ):
            if decoration in decoration_count:
                decoration_count[decoration] += 1
                times = decoration_count[decoration]
                if times > count:
                    count = times
                    best = decoration
            else:
                decoration_count[decoration] = 1
                if count == 0:
                    count = 1
                    best = decoration
    gems = OneSlotGems(decoration=best, count=count) if best is not None else None
    return gems


def get_replacable(solution: Solution, ability: Ability, slots: int) -> int:
    """``Solution::GetReplacable`` (Solution.cpp:149-155): the first decoration of
    ``slots`` slots with a second skill other than ``ability``, or -1."""
    for index, decoration in enumerate(solution.decorations):
        if (
            decoration.slots_required == slots
            and len(decoration.abilities) > 1
            and decoration.abilities[1].ability is not ability
        ):
            return index
    return -1


def replace(solution: Solution, index: int, decoration: Decoration) -> None:
    """``Solution::Replace`` (Solution.cpp:193-206).

    Swaps one decoration for another and adjusts ``abilities`` by their raw
    amounts: the torso multiplier is ignored and the body/non-body lists keep
    the old decoration.
    """
    for pair in solution.decorations[index].abilities:
        solution.abilities[pair.ability] -= pair.amount
    solution.decorations[index] = decoration
    for pair in decoration.abilities:
        if pair.ability in solution.abilities:
            solution.abilities[pair.ability] += pair.amount
        else:
            solution.abilities[pair.ability] = pair.amount


def reorder_gems(data: CalculationData, game: GameData) -> bool:
    """``Solution::ReorderGems`` (Solution.cpp:157-191).

    For each bad skill at -10 or below: if enough 1-slot gems with that
    second skill are used, swap a bigger gem of a different second skill for
    a big gem of their ability, then that many of them for the other gem's
    ability's first decoration in file order (unchecked for rank, events or
    relevance). Gives up when any step can't be done.
    """
    solution = data.solution
    for skill in solution.bad_skills:
        if solution.abilities[skill.ability] >= -9:
            continue
        gems = count_1_socket_gems(solution, skill.ability)
        if gems is None:
            return False
        one_slot = gems.decoration
        bigger_slotted = _require(
            best_available_decoration(data, game, one_slot.abilities[0].ability, 3),
            "Solution.cpp:169",
        )
        num_required = bigger_slotted.abilities[0].amount
        if gems.count < num_required:
            return False

        other = get_replacable(solution, skill.ability, bigger_slotted.slots_required)
        if other == -1:
            return False
        other_decoration = solution.decorations[other]
        if not (
            gems.count >= other_decoration.abilities[0].amount
            and solution.abilities[other_decoration.abilities[1].ability] > -8
        ):
            return False
        other_one_slot = game.decorations_by_ability[other_decoration.abilities[0].ability][0]
        replace(solution, other, bigger_slotted)
        # Read after the replace, so this is bigger_slotted's amount (Solution.cpp:179).
        replaced_amount = solution.decorations[other].abilities[0].amount
        num_to_replace = replaced_amount if replaced_amount > num_required else num_required
        num_replaced = 0
        for index in range(len(solution.decorations)):
            if solution.decorations[index] is one_slot:
                # num_replaced++ < num_to_replace: compares, then counts.
                replacing = num_replaced < num_to_replace
                num_replaced += 1
                if replacing:
                    replace(solution, index, other_one_slot)
        if solution.abilities[skill.ability] < -9:
            return False
    calculate_extra_skills(data)
    return True
