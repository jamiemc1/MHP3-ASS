"""Where a Torso Inc set's jewels go: the chest's, whose points count more
than once, and the rest.

``MatchesQuery`` fills the chest's slots with the torso multiplier and the
other slots once (``legacy/Solution.cpp:57-93``, ``:410-484``), keeping the
two apart in ``body_decorations`` and ``non_body_decorations``. Charm
reduction's ``SwapOut`` then merges 1-slot jewels in ``decorations`` alone
(``Solution.cpp:537-558``, quirk 22), so for some sets those lists no longer
hold the jewels shown, and the placement is worked out again from the shown
jewels, the slots and the set's points.
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

    When the stored lists hold exactly the shown jewels, they are the
    placement. Otherwise every split of the shown jewels between the chest
    and the rest is tried. A split is valid when the chest's jewels fit the
    chest's slots, the rest fit the other slot groups the search counts (each
    other piece's, the weapon's and the charm's; ``Solution.cpp:212``,
    ``:249``, ``:265``), and the points it gives (the chest piece and its
    jewels times the multiplier, everything else once; ``:262``) are the
    set's ``abilities``. Of several valid splits, the first is taken: the
    fewest jewels in the chest, then the earliest in the shown order. Raises
    ``PlacementUnknownError`` when no split is valid (quirk 52).
    """
    chest_armor = solution.armors[1]
    multiplier = solution.torso_multiplier
    if multiplier <= 1 or chest_armor is None or chest_armor.num_slots == 0:
        return None
    jewels = solution.decorations
    if not jewels:
        return None
    if Counter(jewels) == Counter(solution.body_decorations + solution.non_body_decorations):
        stored = JewelPlacement(
            multiplier=multiplier,
            chest=tuple(solution.body_decorations),
            elsewhere=tuple(solution.non_body_decorations),
        )
        return stored
    groups = _other_slot_groups(solution, weapon_slots=weapon_slots)
    target = _nonzero(solution.abilities)
    for count in range(min(chest_armor.num_slots, len(jewels)) + 1):
        for chosen in combinations(range(len(jewels)), count):
            chest = tuple(jewels[i] for i in chosen)
            elsewhere = tuple(jewel for i, jewel in enumerate(jewels) if i not in chosen)
            if sum(jewel.slots_required for jewel in chest) > chest_armor.num_slots:
                continue
            if not fits([jewel.slots_required for jewel in elsewhere], groups=groups):
                continue
            if _nonzero(_points(solution, chest=chest, elsewhere=elsewhere)) != target:
                continue
            placement = JewelPlacement(multiplier=multiplier, chest=chest, elsewhere=elsewhere)
            return placement
    names = ", ".join(jewel.name for jewel in jewels)
    raise PlacementUnknownError(
        f"no placement of {names} fits the set's slots and gives its points"
    )


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


def _points(
    solution: Solution, chest: Sequence[Decoration], elsewhere: Sequence[Decoration]
) -> Counter[Ability]:
    """The points the armour, the charm and the jewels so placed give."""
    multiplier = solution.torso_multiplier
    totals: Counter[Ability] = Counter()
    for slot, armor in enumerate(solution.armors):
        if armor is not None:
            _add(totals, armor.abilities, weight=multiplier if slot == 1 else 1)
    if solution.charm is not None:
        _add(totals, solution.charm.abilities, weight=1)
    for jewel in chest:
        _add(totals, jewel.abilities, weight=multiplier)
    for jewel in elsewhere:
        _add(totals, jewel.abilities, weight=1)
    return totals


def _add(totals: Counter[Ability], pairs: Sequence[AbilityPair], weight: int) -> None:
    for pair in pairs:
        totals[pair.ability] += pair.amount * weight


def _nonzero(points: dict[Ability, int]) -> dict[Ability, int]:
    nonzero = {ability: amount for ability, amount in points.items() if amount != 0}
    return nonzero
