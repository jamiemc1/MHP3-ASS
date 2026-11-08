"""Filling a combination's free slots with decorations.

Ported from ``AddDecorations1``, ``PossibleDecoration``, ``GetScore``,
``GetBestDecoration( List_t< PossibleDecoration^ >% )``, ``IsCharmAbility``,
``AddDecorations23`` and ``CalculateDecorations``
(``legacy/Solution.cpp:271-485``).

The original's ``template< bool, bool >`` parameters are keyword booleans
here. Its slot counters are ``unsigned`` and passed by reference; these
functions return the remaining count for the caller to store.
"""

from __future__ import annotations

from dataclasses import dataclass

from mhp3ass.data.text import as_unsigned
from mhp3ass.model import Ability, Charm, Decoration
from mhp3ass.solution.initial import add_decoration, detrimental
from mhp3ass.solution.state import CalculationData


class UndefinedScoreError(IndexError):
    """``point_score`` read beyond what this port reproduces (see ``point_score``)."""


def point_score(actual_good: int) -> int:
    """``point_score[ actual_good ]`` in ``GetScore`` (Solution.cpp:326-328).

    The array has 6 elements, and ``MatchesQuery`` reads past it: up to index
    20 on shipped data. In the harness build the words after it are method
    thunk addresses patched in at load, so their values change from run to
    run, but each is above every in-bounds score and they rise with the index
    (``tests/golden/data/solution-probes.json.gz``). Scores are only ever
    compared, so these stand-ins, with the same order, choose the same
    decorations. Beyond index 22 nothing is pinned, so this raises.
    """
    in_bounds = (0, 1, 2, 3, 4, 3)
    if actual_good < len(in_bounds):
        return in_bounds[actual_good]
    if actual_good <= 22:
        out_of_bounds = actual_good - 1
        return out_of_bounds
    raise UndefinedScoreError(f"point_score[{actual_good}] is undefined")


@dataclass(slots=True, eq=False)
class PossibleDecoration:
    """``PossibleDecoration`` (Solution.cpp:311-315)."""

    decoration: Decoration
    points_given: int


@dataclass(frozen=True, slots=True)
class Score:
    """``GetScore``'s ``pair( good, bad )``."""

    good: int
    bad: int


def get_score(decoration: Decoration, data: CalculationData, actual_good: int) -> Score:
    """``GetScore`` (Solution.cpp:324-329): ``point_score[ actual_good ]``, and the
    points the solution already has in the decoration's last ability (0 for a
    one-ability decoration). ``actual_good`` is ``unsigned`` in the original."""
    bad = 0
    if len(decoration.abilities) != 1:
        bad = data.solution.abilities.get(decoration.abilities[-1].ability, 0)
    score = Score(good=point_score(as_unsigned(actual_good)), bad=bad)
    return score


def best_possible_decoration(
    decorations: list[PossibleDecoration], data: CalculationData
) -> PossibleDecoration:
    """``GetBestDecoration( List_t< PossibleDecoration^ >% )`` (Solution.cpp:331-345).

    The highest score, and among equal scores the last: the comparison is
    ``>=``. Its second clause (an equal score with a higher ``bad``) is
    implied by the first, so ``bad`` never decides anything.
    """
    best = 0
    score = get_score(decorations[best].decoration, data, decorations[best].points_given)
    for i in range(1, len(decorations)):
        current = get_score(decorations[i].decoration, data, decorations[i].points_given)
        if current.good >= score.good or (current.good == score.good and current.bad > score.bad):
            score = current
            best = i
    chosen = decorations[best]
    return chosen


def is_charm_ability(charm: Charm | None, ability: Ability) -> bool:
    """``IsCharmAbility`` (Solution.cpp:347-350): the charm's first ability is ``ability``."""
    first = charm is not None and len(charm.abilities) > 0 and charm.abilities[0].ability is ability
    return first


def _second_skill_allowed(
    decoration: Decoration, data: CalculationData, multiplier: int, allow_bad: bool
) -> bool:
    """The bad-skill guard both loops share (Solution.cpp:286-287, :369-370): the
    decoration's second skill mustn't take its ability to -10 or below."""
    if allow_bad or len(decoration.abilities) < 2:
        return True
    second = decoration.abilities[1]
    abilities = data.solution.abilities
    if second.ability not in abilities:
        return True
    allowed = abilities[second.ability] + second.amount * multiplier > -10
    return allowed


def add_decorations23(
    data: CalculationData,
    size: int,
    num_slots: int,
    multiplier: int,
    decoration_list: list[Decoration],
    *,
    allow_bad: bool,
    allow_detrimental: bool,
) -> int:
    """``AddDecorations23< allow_bad, allow_detrimental >`` (Solution.cpp:352-404).

    Collects every relevant ``size``-slot decoration that would help without
    overshooting its ability's need by more than 1, adds the best one, and
    repeats while slot groups remain. Returns the slot groups left.
    """
    rel_decorations = data.rel_decoration_map[size]
    if num_slots == 0 or len(rel_decorations) == 0:
        return num_slots
    solution = data.solution
    possible_decorations: list[PossibleDecoration] = []
    for decoration in rel_decorations:
        if not (allow_detrimental or not detrimental(decoration, data)):
            continue
        first = decoration.abilities[0]
        if not _second_skill_allowed(decoration, data, multiplier, allow_bad):
            continue
        current_amount = solution.abilities[first.ability]
        decoration_amount = first.amount * multiplier
        needed_amount = data.need[first.ability]
        if (
            decoration_amount > 0
            and current_amount < needed_amount
            and current_amount + decoration_amount <= needed_amount + 1
        ):
            if is_charm_ability(solution.charm, first.ability):
                points_given = decoration_amount
            else:
                points_given = min(decoration_amount, needed_amount - current_amount)
            possible_decorations.append(
                PossibleDecoration(decoration=decoration, points_given=points_given)
            )
    if len(possible_decorations) == 0:
        return num_slots
    best = best_possible_decoration(possible_decorations, data)
    add_decoration(solution, best.decoration, multiplier, decoration_list)
    num_slots = as_unsigned(num_slots - 1)
    if num_slots > 0:
        num_slots = add_decorations23(
            data,
            size,
            num_slots,
            multiplier,
            decoration_list,
            allow_bad=allow_bad,
            allow_detrimental=allow_detrimental,
        )
    return num_slots


def add_decorations1(
    data: CalculationData,
    num_slots: int,
    multiplier: int,
    decoration_list: list[Decoration],
    *,
    allow_bad: bool,
    allow_overkill: bool,
) -> int:
    """``AddDecorations1< allow_bad, allow_overkill >`` (Solution.cpp:271-309).

    One pass over the relevant 1-slot decorations, adding each one again for
    as long as it still qualifies. A decoration skipped earlier in the pass is
    not reconsidered after later ones change the totals: the original's
    ``loop = true`` is always reset at the end of the pass. ``Detrimental``
    applies whatever the flags. Without ``allow_overkill``, a decoration may
    not take its ability more than its own amount minus 1 past the need.
    Returns the slots left.
    """
    rel_decorations = data.rel_decoration_map[1]
    if num_slots == 0 or len(rel_decorations) == 0:
        return num_slots
    solution = data.solution
    i = 0
    while i < len(rel_decorations):
        decoration = rel_decorations[i]
        added = False
        if not detrimental(decoration, data) and _second_skill_allowed(
            decoration, data, multiplier, allow_bad
        ):
            first = decoration.abilities[0]
            current_amount = solution.abilities[first.ability]
            decoration_amount = first.amount * multiplier
            needed_amount = data.need[first.ability]
            if allow_overkill:
                within_need = current_amount < needed_amount
            else:
                within_need = current_amount + decoration_amount <= needed_amount + first.amount - 1
            if decoration_amount > 0 and current_amount < needed_amount and within_need:
                add_decoration(solution, decoration, multiplier, decoration_list)
                num_slots = as_unsigned(num_slots - 1)
                if num_slots == 0:
                    return num_slots
                added = True
        if not added:
            i += 1
    return num_slots
