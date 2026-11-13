"""Where a Torso Inc set's jewels go: the chest's, whose points count more
than once, and the rest.

``MatchesQuery`` fills the chest's slots with the torso multiplier and the
other slots once (``legacy/Solution.cpp:57-93``, ``:410-484``), keeping the
two apart in ``body_decorations`` and ``non_body_decorations``. The
bad-skill check's ``Replace`` and charm reduction's ``SwapOut`` then change
jewels in ``decorations`` alone, by raw amounts (``Solution.cpp:193-206``,
``:537-558``, quirk 22), so for some sets those lists no longer hold the
jewels shown, and the placement is worked out again from the shown jewels,
the slots and the set's points.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from itertools import combinations

from mhp3ass.model import Ability, AbilityPair, Decoration
from mhp3ass.solution.state import Solution


class PlacementUnknownError(ValueError):
    """No way of socketing a set's shown jewels fits its slots and gives its points."""


@dataclass(frozen=True)
class JewelPlacement:
    """The jewels in the chest, whose points count ``multiplier`` times, and the rest."""

    multiplier: int
    chest: tuple[Decoration, ...]
    elsewhere: tuple[Decoration, ...]


def jewel_placement(solution: Solution, weapon_slots: int) -> JewelPlacement | None:
    """Where ``solution``'s shown jewels go, for a search with ``weapon_slots``.

    ``None`` where a jewel's place can't change its points: no Torso Inc
    (a multiplier of 1), a chest with no slots, or no jewels. Sets loaded
    from ``settings.cfg`` carry neither the multiplier nor the points (their
    multiplier is 0), so they get ``None`` too.

    A placement is valid when the chest's jewels fit the chest's slots, the
    rest fit the other slot groups the search counts (each other piece's, the
    weapon's and the charm's; ``Solution.cpp:212``, ``:249``, ``:265``), and
    the points it gives are the set's ``abilities``: the chest's jewels count
    the final multiplier times, the chest piece the multiplier before its own
    Torso Inc (``GetInitialData`` adds it last, ``:258-262``), everything
    else once.

    The stored lists are the placement when they hold exactly the shown
    jewels and are valid. Otherwise every split of the shown jewels between
    the chest and the rest is tried, and of the valid ones the first is
    taken: the fewest jewels in the chest, then the earliest in the shown
    order. Raises ``PlacementUnknownError`` when no split is valid (quirk 52).
    """
    chest_armor = solution.armors[1]
    multiplier = solution.torso_multiplier
    if multiplier <= 1 or chest_armor is None or chest_armor.num_slots == 0:
        return None
    jewels = solution.decorations
    if not jewels:
        return None
    check = _PlacementCheck(
        solution=solution,
        chest_slots=chest_armor.num_slots,
        other_groups=_other_slot_groups(solution, weapon_slots=weapon_slots),
        points=_nonzero(solution.abilities),
    )
    stored = JewelPlacement(
        multiplier=multiplier,
        chest=tuple(solution.body_decorations),
        elsewhere=tuple(solution.non_body_decorations),
    )
    holds_the_shown = Counter(jewels) == Counter(stored.chest + stored.elsewhere)
    if holds_the_shown and check.valid(stored):
        return stored
    for count in range(min(chest_armor.num_slots, len(jewels)) + 1):
        for chosen in combinations(range(len(jewels)), count):
            placement = JewelPlacement(
                multiplier=multiplier,
                chest=tuple(jewels[i] for i in chosen),
                elsewhere=tuple(jewel for i, jewel in enumerate(jewels) if i not in chosen),
            )
            if check.valid(placement):
                return placement
    names = ", ".join(jewel.name for jewel in jewels)
    raise PlacementUnknownError(
        f"no placement of {names} fits the set's slots and gives its points"
    )


@dataclass(frozen=True)
class _PlacementCheck:
    """What a placement of ``solution``'s jewels must meet: the chest's slots,
    the other slot groups, and the set's non-zero points."""

    solution: Solution
    chest_slots: int
    other_groups: list[int]
    points: dict[Ability, int]

    def valid(self, placement: JewelPlacement) -> bool:
        if sum(jewel.slots_required for jewel in placement.chest) > self.chest_slots:
            return False
        if not fits(
            [jewel.slots_required for jewel in placement.elsewhere], groups=self.other_groups
        ):
            return False
        given = _nonzero(_points(self.solution, placement))
        valid = given == self.points
        return valid


def fits(sizes: Sequence[int], groups: Sequence[int]) -> bool:
    """Whether jewels needing ``sizes`` slots go into slot groups of ``groups``
    slots, several to a group while they fit."""
    free = list(groups)
    placed = _place(sorted(sizes, reverse=True), free=free)
    return placed


def _place(sizes: list[int], free: list[int]) -> bool:
    """Depth-first: the largest jewel left into each group with room for it."""
    if not sizes:
        return True
    size, rest = sizes[0], sizes[1:]
    tried = set()
    for group, room in enumerate(free):
        # Two groups with the same room left lead to the same placements.
        if room < size or room in tried:
            continue
        tried.add(room)
        free[group] -= size
        placed = _place(rest, free=free)
        free[group] += size
        if placed:
            return True
    return False


def _other_slot_groups(solution: Solution, weapon_slots: int) -> list[int]:
    """The slot groups outside the chest: each other piece's, the weapon's
    and the charm's, as ``GetInitialData`` counts them into ``slots_spare``."""
    groups = [
        armor.num_slots
        for slot, armor in enumerate(solution.armors)
        if slot != 1 and armor is not None and armor.num_slots > 0
    ]
    if weapon_slots > 0:
        groups.append(weapon_slots)
    if solution.charm is not None and solution.charm.num_slots > 0:
        groups.append(solution.charm.num_slots)
    return groups


def _points(solution: Solution, placement: JewelPlacement) -> Counter[Ability]:
    """The points the armour, the charm and the jewels so placed give."""
    totals: Counter[Ability] = Counter()
    for slot, armor in enumerate(solution.armors):
        if armor is None:
            continue
        # The chest piece is added before its own Torso Inc counts (Solution.cpp:262).
        weight = placement.multiplier - armor.torso_inc if slot == 1 else 1
        _add(totals, armor.abilities, weight=weight)
    if solution.charm is not None:
        _add(totals, solution.charm.abilities, weight=1)
    for jewel in placement.chest:
        _add(totals, jewel.abilities, weight=placement.multiplier)
    for jewel in placement.elsewhere:
        _add(totals, jewel.abilities, weight=1)
    return totals


def _add(totals: Counter[Ability], pairs: Sequence[AbilityPair], weight: int) -> None:
    for pair in pairs:
        totals[pair.ability] += pair.amount * weight


def _nonzero(points: dict[Ability, int]) -> dict[Ability, int]:
    nonzero = {ability: amount for ability, amount in points.items() if amount != 0}
    return nonzero
