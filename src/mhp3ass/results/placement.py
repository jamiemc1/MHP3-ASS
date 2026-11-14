"""Where a Torso Inc set's jewels go: the chest's, whose points count more
than once, and the rest.

``MatchesQuery`` fills the chest's slots with the torso multiplier and the
other slots once (``legacy/Solution.cpp:57-93``, ``:410-484``), keeping the
two apart in ``body_decorations`` and ``non_body_decorations``. The
bad-skill check's ``Replace`` and charm reduction's ``SwapOut`` then change
jewels in ``decorations`` alone, by raw amounts (``Solution.cpp:193-206``,
``:537-558``, quirk 22), so for some sets those lists no longer hold the
jewels shown, and the placement is worked out again from the shown jewels,
the slots and the set's points. A set loaded from ``settings.cfg``, which
keeps none of this, is filled again first (``Solution::MatchesQuery``,
``Solution.cpp:660-724``).

Where no placement of the shown jewels fits (quirk 52), ``correction``
finds a version of the set that builds, with jewels the port picks itself
(``pick_jewels``) if need be. The original shows the listed jewels only.
"""

from __future__ import annotations

import operator
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from itertools import combinations, combinations_with_replacement

from mhp3ass.data import GameData
from mhp3ass.decorations import decoration_skill_at
from mhp3ass.model import Ability, AbilityPair, Armor, Charm, Decoration, Skill
from mhp3ass.query import Query, rank_locked
from mhp3ass.skills import get_skill
from mhp3ass.solution import matches_query
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

    ``solution`` is one the search filled: a set loaded from ``settings.cfg``
    carries neither the multiplier nor the points (its multiplier is 0) and
    goes through ``refilled`` first. ``None`` where a jewel's place can't
    change its points: no Torso Inc (a multiplier of 1 or less), a chest with
    no slots, or no jewels.

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
    if solution.torso_multiplier <= 1 or chest_armor is None or not place_can_matter(solution):
        return None
    multiplier = solution.torso_multiplier
    jewels = solution.decorations
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


def place_can_matter(solution: Solution) -> bool:
    """Whether a jewel's place could change ``solution``'s points, from its
    armour and jewels alone: a Torso Inc piece (the multiplier is one more
    for each, ``Solution.cpp:223``, :246), a chest with slots, and jewels.
    From the armour, so it also answers for sets loaded from
    ``settings.cfg``, whose multiplier isn't kept."""
    chest_armor = solution.armors[1]
    multiplier = 1 + sum(armor.torso_inc for armor in solution.armors if armor is not None)
    can_matter = (
        multiplier > 1
        and chest_armor is not None
        and chest_armor.num_slots > 0
        and bool(solution.decorations)
    )
    return can_matter


def refilled(solution: Solution, query: Query, game: GameData) -> Solution | None:
    """A loaded set as the search fills it, for its ``query``: its armour and
    charm through ``MatchesQuery`` again, giving the multiplier, the points
    and the chest/elsewhere lists the file doesn't keep. The charm is the
    reduced one the file holds, so it is filled as a custom charm, which
    ``ReduceCharm`` leaves alone; reducing it again would change the set.

    The fill reads the abilities' ``relevant`` flags, which the last
    relevance pass, a charm import or a cancelled search may have left set
    for something else, so they are first set to ``query``'s again, as its
    own relevance pass set them (``GetRelevantData``, ``LoadedData.cpp:121-130``).
    Call it only while no search is using ``game``.

    ``None`` when the refill isn't the loaded set: it is rejected, or it
    gives other jewels (where the search had filled the set with the charm
    before reducing it, which the file doesn't keep).
    """
    refill = _filled(solution.armors, charm=solution.charm, custom=True, query=query, game=game)
    if refill is None or Counter(refill.decorations) != Counter(solution.decorations):
        return None
    return refill


@dataclass(frozen=True)
class Correction:
    """A version of a set that builds, where its shown jewels have no valid
    placement (quirk 52): ``charm`` with the jewels so placed. ``charm`` is
    the listed one unless ``charm_changed``."""

    charm: Charm | None
    placement: JewelPlacement
    charm_changed: bool


def correction(
    solution: Solution,
    query: Query,
    game: GameData,
    charm_templates: Sequence[Charm | None] | None,
) -> Correction | Unbuildable:
    """A version of ``solution``, a filled set ``jewel_placement`` can't
    place, that builds (``builds``), tried in turn:

    1. the listed charm filled again (as ``refilled`` fills it), with the
       jewels that fill gives, placed as ``jewel_placement`` tries them;
    2. the listed charm with ``pick_jewels``' jewels;
    3. the charm before reduction with the jewels the search's fill placed
       in ``body_decorations`` and ``non_body_decorations``, which the
       bad-skill repair and charm reduction leave as they were (quirk 22).
       The charm is the first of the search's ``charm_templates`` whose fill
       gives the set again.

    ``Unbuildable`` (step 2's reason) when none builds. Raises
    ``PlacementUnknownError`` when steps 1 and 2 don't build and
    ``charm_templates`` is ``None`` (not known, as for loaded results).
    Fills read the abilities' ``relevant`` flags: call it only while no
    search is using ``game``.
    """
    weapon_slots = query.weapon_slots_allowed
    multiplier = solution.torso_multiplier
    refill = _filled(solution.armors, charm=solution.charm, custom=True, query=query, game=game)
    if refill is not None:
        placed = _buildable_split(
            refill,
            charm=solution.charm,
            jewels=refill.decorations,
            multiplier=multiplier,
            query=query,
        )
        if placed is not None:
            return Correction(charm=solution.charm, placement=placed, charm_changed=False)
    picked = pick_jewels(
        solution.armors, charm=solution.charm, query=query, game=game, weapon_slots=weapon_slots
    )
    if isinstance(picked, JewelPlacement):
        return Correction(charm=solution.charm, placement=picked, charm_changed=False)
    if charm_templates is None:
        raise PlacementUnknownError("the search's charms aren't known, so neither is a build")
    for template in charm_templates:
        filled = _filled(solution.armors, charm=template, custom=False, query=query, game=game)
        if filled is None or not _same_set(filled, solution):
            continue
        fill_time_jewels = [*filled.body_decorations, *filled.non_body_decorations]
        placed = _buildable_split(
            filled,
            charm=template,
            jewels=fill_time_jewels,
            multiplier=multiplier,
            query=query,
        )
        if placed is None:
            break
        rebuilt = Correction(charm=template, placement=placed, charm_changed=True)
        return rebuilt
    return picked


def _filled(
    armors: Sequence[Armor | None], charm: Charm | None, custom: bool, query: Query, game: GameData
) -> Solution | None:
    """``armors`` and a copy of ``charm`` through ``MatchesQuery`` for
    ``query``, the charm marked ``custom`` if asked; ``None`` if rejected.
    The abilities' ``relevant`` flags are first set to ``query``'s."""
    relevant = set(query.rel_abilities)
    for ability in game.abilities:
        ability.relevant = ability in relevant
    copied = charm.copy() if charm is not None else None
    if copied is not None and custom:
        copied.custom = True
    filled = Solution(armors=list(armors), charm=copied)
    if not matches_query(filled, query, game):
        return None
    return filled


def _same_set(filled: Solution, solution: Solution) -> bool:
    """The same charm as shown, and the same jewels."""
    same = _charm_key(filled.charm) == _charm_key(solution.charm) and Counter(
        filled.decorations
    ) == Counter(solution.decorations)
    return same


def _charm_key(charm: Charm | None) -> tuple[int, tuple[tuple[Ability, int], ...]] | None:
    if charm is None:
        return None
    key = (charm.num_slots, tuple((pair.ability, pair.amount) for pair in charm.abilities))
    return key


def _buildable_split(
    filled: Solution,
    charm: Charm | None,
    jewels: Sequence[Decoration],
    multiplier: int,
    query: Query,
) -> JewelPlacement | None:
    """The first split of ``jewels`` that ``builds`` ``filled``'s armour with
    ``charm``: ``filled``'s own chest and other lists when they hold exactly
    ``jewels``, then the splits in ``jewel_placement``'s order."""
    weapon_slots = query.weapon_slots_allowed
    stored = JewelPlacement(
        multiplier=multiplier,
        chest=tuple(filled.body_decorations),
        elsewhere=tuple(filled.non_body_decorations),
    )
    holds_them = Counter(stored.chest + stored.elsewhere) == Counter(jewels)
    if holds_them and builds(filled.armors, charm, stored, query=query, weapon_slots=weapon_slots):
        return stored
    chest_armor = filled.armors[1]
    chest_slots = chest_armor.num_slots if chest_armor is not None else 0
    for count in range(min(chest_slots, len(jewels)) + 1):
        for chosen in combinations(range(len(jewels)), count):
            placement = JewelPlacement(
                multiplier=multiplier,
                chest=tuple(jewels[i] for i in chosen),
                elsewhere=tuple(jewel for i, jewel in enumerate(jewels) if i not in chosen),
            )
            if builds(filled.armors, charm, placement, query=query, weapon_slots=weapon_slots):
                return placement
    return None


@dataclass(frozen=True)
class ShortSkill:
    """A query skill no jewel list brings to its points: the most it reaches."""

    skill: Skill
    most: int


@dataclass(frozen=True)
class Unbuildable:
    """Why no jewel list builds a set: the bad skills that stay active
    with the fewest of them, or else the query skills short of their points."""

    bad_skills: tuple[Skill, ...]
    short: tuple[ShortSkill, ...]


def pick_jewels(
    armors: Sequence[Armor | None],
    charm: Charm | None,
    query: Query,
    game: GameData,
    weapon_slots: int,
) -> JewelPlacement | Unbuildable:
    """A jewel list that builds ``armors`` with ``charm`` for ``query``, from
    every decoration the query can use (its rank, and event ones only when
    allowed, as ``Decoration::MatchesQuery`` filters, ``Decoration.cpp:126-137``),
    or why none does.

    It builds when the chest's jewels fit the chest's slots, the rest fit
    the other slot groups (each other piece's, the weapon's, the charm's),
    every query skill reaches its points with the chest's jewels and the
    chest piece counted as ``jewel_placement`` counts them, and, without bad
    skills allowed, no ability outside the query's has negative points that
    give a skill (``CalculateExtraSkills``, ``Solution.cpp:726-740``).

    Only decorations adding to a query ability, or to one with a negative
    skill that the set can take points from, are tried, less any another
    beats (``_useful_decorations``): any other is never better than an empty
    slot. The search is over the points each group can add (``_Search``), so
    it is exhaustive. Of the lists that build, the first found is taken
    (largest groups first, depth first, each group's most points first,
    then fewer and smaller decorations). Without one, ``Unbuildable`` names the bad skills
    that stay with the fewest of them, or, when the query skills can't all
    be reached, those short of their points (none when each can be reached
    alone but not together).
    """
    multiplier = 1 + sum(armor.torso_inc for armor in armors if armor is not None)
    base = _armor_and_charm_points(armors, charm, multiplier=multiplier)
    useful = _useful_decorations(base, query=query, game=game)
    abilities = sorted(useful.watched, key=lambda ability: ability.name)
    chest_armor = armors[1]
    chest_slots = chest_armor.num_slots if chest_armor is not None else 0
    groups = [_Group(size=chest_slots, weight=multiplier, chest=True)]
    groups += [
        _Group(size=size, weight=1, chest=False)
        for size in _slot_groups(armors, charm, weapon_slots)
    ]
    # The largest groups first leaves the small ones last, where the caps and
    # floors are tight and merge or drop the most states.
    groups.sort(key=lambda group: group.size * group.weight, reverse=True)
    decorations = useful.decorations
    # An ability that ends on target whatever the groups add needn't be
    # followed; dropping one can leave decorations beaten, so repeat.
    while True:
        search = _search(base, groups, decorations=decorations, abilities=abilities, query=query)
        contested = [
            ability
            for index, ability in enumerate(abilities)
            if search.least(index) < search.targets[index]
        ]
        if contested == abilities:
            break
        abilities = contested
        followed = set(contested)
        adding = [
            decoration
            for decoration in decorations
            if any(pair.amount > 0 and pair.ability in followed for pair in decoration.abilities)
        ]
        decorations = _unbeaten(adding, watched=followed)
    found = search.first_build()
    if found is not None:
        picked = JewelPlacement(multiplier=multiplier, chest=found.chest, elsewhere=found.elsewhere)
        return picked
    reaching = search.reaching()
    if reaching:
        bad_skills = min((_bad(points, abilities, query) for points in reaching), key=len)
        return Unbuildable(bad_skills=bad_skills, short=())
    short = tuple(
        ShortSkill(skill=skill, most=most)
        for skill in query.skills
        if skill.ability in abilities
        and (most := search.most(abilities.index(skill.ability))) < skill.points_required
    )
    unbuildable = Unbuildable(bad_skills=(), short=short)
    return unbuildable


def _search(
    base: Counter[Ability],
    groups: list[_Group],
    decorations: Sequence[Decoration],
    abilities: list[Ability],
    query: Query,
) -> _Search:
    """The search over ``groups`` with ``decorations``, following ``abilities``."""
    by_shape = {
        (size, weight): _group_options(
            size, weight=weight, decorations=decorations, abilities=abilities
        )
        for size, weight in {(group.size, group.weight) for group in groups}
    }
    asked = {skill.ability for skill in query.skills}
    search = _Search(
        start=tuple(base[ability] for ability in abilities),
        groups=groups,
        options=[by_shape[group.size, group.weight] for group in groups],
        targets=_targets(abilities, query),
        asked=tuple(ability in asked for ability in abilities),
    )
    return search


@dataclass(frozen=True)
class _Group:
    """A slot group: the chest's, whose jewels count ``weight`` times, or another."""

    size: int
    weight: int
    chest: bool


@dataclass(frozen=True)
class _Jewels:
    chest: tuple[Decoration, ...]
    elsewhere: tuple[Decoration, ...]

    def with_group(self, chosen: tuple[Decoration, ...], chest: bool) -> _Jewels:
        if chest:
            return _Jewels(chest=self.chest + chosen, elsewhere=self.elsewhere)
        return _Jewels(chest=self.chest, elsewhere=self.elsewhere + chosen)


@dataclass(frozen=True)
class _Bounds:
    caps: tuple[int, ...]
    floors: tuple[int, ...]


@dataclass(frozen=True)
class _Search:
    """``pick_jewels``' search over the points each slot group adds, from
    ``start`` (the armour's and the charm's), ability by ability as
    ``targets`` and ``asked`` give them (``_targets``)."""

    start: tuple[int, ...]
    groups: list[_Group]
    options: list[_GroupOptions]
    targets: tuple[int, ...]
    asked: tuple[bool, ...]

    def first_build(self) -> _Jewels | None:
        """The first jewels found that bring every ability to its target,
        each group's gains tried most points first, depth first; ``None``
        when none do. Points past what the groups left could take off again
        are held at that cap, so states that end alike are tried once, and a
        state the groups left can't bring to its targets is dropped."""
        bounds = [self._bounds(index, keep_bad=False) for index in range(len(self.groups))]
        ordered = [
            sorted(options.gains.items(), key=lambda entry: sum(entry[0]), reverse=True)
            for options in self.options
        ]
        # States after each group that lead to no build, so each is tried once.
        failed: list[set[tuple[int, ...]]] = [set() for _ in self.groups]

        def visit(index: int, points: tuple[int, ...], jewels: _Jewels) -> _Jewels | None:
            if index == len(self.groups):
                return jewels
            bound = bounds[index]
            group = self.groups[index]
            for gain, chosen in ordered[index]:
                # map over operator functions: this loop is the search's cost.
                after = tuple(
                    map(min, map(operator.add, points, gain, strict=True), bound.caps, strict=True)
                )
                if after in failed[index] or any(
                    map(operator.lt, after, bound.floors, strict=True)
                ):
                    continue
                found = visit(index + 1, after, jewels.with_group(chosen, chest=group.chest))
                if found is not None:
                    return found
                failed[index].add(after)
            return None

        first = visit(0, self.start, _Jewels(chest=(), elsewhere=()))
        return first

    def reaching(self) -> dict[tuple[int, ...], _Jewels]:
        """The end points, each with the first jewels found giving it, that
        bring every query ability to its target, whatever the others end at;
        capped and dropped as ``first_build`` does."""
        states = {self.start: _Jewels(chest=(), elsewhere=())}
        for index, group in enumerate(self.groups):
            bound = self._bounds(index, keep_bad=True)
            grown: dict[tuple[int, ...], _Jewels] = {}
            for points, jewels in states.items():
                for gain, chosen in self.options[index].gains.items():
                    after = tuple(
                        map(
                            min,
                            map(operator.add, points, gain, strict=True),
                            bound.caps,
                            strict=True,
                        )
                    )
                    if after in grown or any(map(operator.lt, after, bound.floors, strict=True)):
                        continue
                    grown[after] = jewels.with_group(chosen, chest=group.chest)
            states = grown
        return states

    def _bounds(self, index: int, keep_bad: bool) -> _Bounds:
        """After group ``index``: per ability, the cap past which more can't
        matter once the groups left take off the most they can, and the floor
        below which they can't bring it to its target (none for an ability
        other than a query's when ``keep_bad``)."""
        later = self.options[index + 1 :]
        caps = tuple(
            target - sum(min(gain[ability] for gain in options.gains) for options in later)
            for ability, target in enumerate(self.targets)
        )
        # Below any points a set reaches: no floor.
        no_floor = -(2**63)
        floors = tuple(
            target - sum(max(gain[ability] for gain in options.gains) for options in later)
            if is_asked or not keep_bad
            else no_floor
            for ability, (target, is_asked) in enumerate(zip(self.targets, self.asked, strict=True))
        )
        bounds = _Bounds(caps=caps, floors=floors)
        return bounds

    def most(self, ability: int) -> int:
        """The most points ``ability`` reaches, every group adding its most."""
        most = self.start[ability] + sum(
            max(gain[ability] for gain in options.gains) for options in self.options
        )
        return most

    def least(self, ability: int) -> int:
        """The fewest points ``ability`` ends at, every group adding its least."""
        least = self.start[ability] + sum(options.least[ability] for options in self.options)
        return least


def _targets(abilities: Sequence[Ability], query: Query) -> tuple[int, ...]:
    """Per ability, the points it must end at or above: a query skill's
    points, and for another one more than its nearest negative skill, the
    least points that give no bad skill (``get_skill``)."""
    required = {skill.ability: skill.points_required for skill in query.skills}
    targets = tuple(
        required[ability] if ability in required else _nearest_bad(ability) + 1
        for ability in abilities
    )
    return targets


def _nearest_bad(ability: Ability) -> int:
    """The negative skill threshold nearest 0; ``ValueError`` if it has none."""
    nearest = max(threshold for threshold in ability.skills if threshold < 0)
    return nearest


def _can_go_bad(ability: Ability) -> bool:
    can = any(threshold < 0 for threshold in ability.skills)
    return can


def builds(
    armors: Sequence[Armor | None],
    charm: Charm | None,
    placement: JewelPlacement,
    query: Query,
    weapon_slots: int,
) -> bool:
    """Whether ``placement``'s jewels build ``armors`` with ``charm`` for
    ``query``, by ``pick_jewels``' rules: they fit, every query skill reaches
    its points, and no bad skill shows unless the query allows them."""
    chest_armor = armors[1]
    chest_slots = chest_armor.num_slots if chest_armor is not None else 0
    if sum(jewel.slots_required for jewel in placement.chest) > chest_slots:
        return False
    sizes = [jewel.slots_required for jewel in placement.elsewhere]
    if not fits(sizes, groups=_slot_groups(armors, charm, weapon_slots)):
        return False
    totals = _armor_and_charm_points(armors, charm, multiplier=placement.multiplier)
    for jewel in placement.chest:
        _add(totals, jewel.abilities, weight=placement.multiplier)
    for jewel in placement.elsewhere:
        _add(totals, jewel.abilities, weight=1)
    abilities = sorted(
        set(totals) | {skill.ability for skill in query.skills}, key=lambda a: a.name
    )
    points = tuple(totals[ability] for ability in abilities)
    built = not _short(points, abilities, query) and not _bad(points, abilities, query)
    return built


def _armor_and_charm_points(
    armors: Sequence[Armor | None], charm: Charm | None, multiplier: int
) -> Counter[Ability]:
    totals: Counter[Ability] = Counter()
    for slot, armor in enumerate(armors):
        if armor is None:
            continue
        # The chest piece is added before its own Torso Inc counts (Solution.cpp:262).
        _add(totals, armor.abilities, weight=multiplier - armor.torso_inc if slot == 1 else 1)
    if charm is not None:
        _add(totals, charm.abilities, weight=1)
    return totals


@dataclass(frozen=True)
class _Useful:
    """The decorations worth trying, and the abilities whose points matter."""

    decorations: list[Decoration]
    watched: set[Ability]


def _useful_decorations(base: Counter[Ability], query: Query, game: GameData) -> _Useful:
    """The query's usable decorations that add to a watched ability, less
    any another beats (as few slots or fewer, and at least its points in
    every watched ability), and the watched abilities: the query's, and,
    without bad skills allowed, every one that has a negative skill and that
    the armour, the charm or a useful decoration takes points from."""
    usable = [
        decoration
        for decoration in game.decorations
        if not rank_locked(decoration.hr, decoration.elder_star, query)
        and (query.allow_event or not decoration.is_event)
    ]
    watched = {skill.ability for skill in query.skills}
    if not query.allow_bad:
        watched |= {
            ability for ability, amount in base.items() if amount < 0 and _can_go_bad(ability)
        }
    while True:
        adding = [
            decoration
            for decoration in usable
            if any(pair.amount > 0 and pair.ability in watched for pair in decoration.abilities)
        ]
        taken = {
            pair.ability
            for decoration in adding
            for pair in decoration.abilities
            if pair.amount < 0 and not query.allow_bad and _can_go_bad(pair.ability)
        }
        if taken <= watched:
            break
        watched |= taken
    useful = _Useful(decorations=_unbeaten(adding, watched=watched), watched=watched)
    return useful


def _unbeaten(decorations: list[Decoration], watched: set[Ability]) -> list[Decoration]:
    """``decorations`` less any another beats; of equals, the first is kept.
    More points never make a set worse (a query skill gets closer to its
    points, another ability further from a bad skill), so a beaten one never
    builds where its better can't."""

    order = sorted(watched, key=lambda ability: ability.name)
    profiles = [
        (
            decoration.slots_required,
            tuple(decoration_skill_at(decoration, ability) for ability in order),
        )
        for decoration in decorations
    ]
    kept: list[Decoration] = []
    seen: set[tuple[int, tuple[int, ...]]] = set()
    for decoration, (slots, ours) in zip(decorations, profiles, strict=True):
        strictly_beaten = any(
            their_slots <= slots
            and all(theirs >= mine for theirs, mine in zip(their_points, ours, strict=True))
            and (their_slots, their_points) != (slots, ours)
            for their_slots, their_points in profiles
        )
        if strictly_beaten or (slots, ours) in seen:
            continue
        seen.add((slots, ours))
        kept.append(decoration)
    return kept


def _slot_groups(
    armors: Sequence[Armor | None], charm: Charm | None, weapon_slots: int
) -> list[int]:
    groups = [
        armor.num_slots
        for slot, armor in enumerate(armors)
        if slot != 1 and armor is not None and armor.num_slots > 0
    ]
    if weapon_slots > 0:
        groups.append(weapon_slots)
    if charm is not None and charm.num_slots > 0:
        groups.append(charm.num_slots)
    return groups


def _group_options(
    size: int,
    weight: int,
    decorations: Sequence[Decoration],
    abilities: Sequence[Ability],
) -> _GroupOptions:
    """Each gain one group of ``size`` slots can add that no other gain
    matches or beats on every ability, with the first (fewest, then
    earliest) decorations giving it. More points never make a set worse (a
    query skill gets closer to its points, another ability further from a
    bad skill), so a beaten gain never builds where its better can't."""
    position = {ability: index for index, ability in enumerate(abilities)}
    smallest_first = sorted(decorations, key=lambda decoration: decoration.slots_required)
    found: dict[tuple[int, ...], tuple[Decoration, ...]] = {tuple(0 for _ in abilities): ()}
    for count in range(1, size + 1):
        for chosen in combinations_with_replacement(smallest_first, count):
            if sum(decoration.slots_required for decoration in chosen) > size:
                continue
            gain = [0] * len(abilities)
            for decoration in chosen:
                for pair in decoration.abilities:
                    if pair.ability in position:
                        gain[position[pair.ability]] += pair.amount * weight
            found.setdefault(tuple(gain), chosen)
    # Highest totals first: a gain can only be beaten by one with a higher total.
    front: list[tuple[int, ...]] = []
    for gain in sorted(found, key=sum, reverse=True):
        if not any(all(map(operator.ge, other, gain, strict=True)) for other in front):
            front.append(gain)
    kept = set(front)
    unbeaten = {gain: chosen for gain, chosen in found.items() if gain in kept}
    options = _GroupOptions(
        gains=unbeaten,
        least=tuple(min(gain[index] for gain in found) for index in range(len(abilities))),
    )
    return options


@dataclass(frozen=True)
class _GroupOptions:
    """A group's unbeaten ``gains`` with their decorations, and per ability
    the ``least`` any decorations fitting it add, beaten or not."""

    gains: dict[tuple[int, ...], tuple[Decoration, ...]]
    least: tuple[int, ...]


def _short(points: tuple[int, ...], abilities: Sequence[Ability], query: Query) -> bool:
    position = {ability: index for index, ability in enumerate(abilities)}
    short = any(points[position[skill.ability]] < skill.points_required for skill in query.skills)
    return short


def _bad(points: tuple[int, ...], abilities: Sequence[Ability], query: Query) -> tuple[Skill, ...]:
    """The skills negative points give outside the query's, unless bad skills are allowed."""
    if query.allow_bad:
        return ()
    asked = {skill.ability for skill in query.skills}
    bad = tuple(
        skill
        for ability, amount in zip(abilities, points, strict=True)
        if ability not in asked and amount < 0 and (skill := get_skill(ability, amount)) is not None
    )
    return bad


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
