from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

import pytest

from corpus_search import CorpusSearch
from mhp3ass.charms.naming import charm_name
from mhp3ass.data import GameData
from mhp3ass.model import Ability, Armor, ArmorType, Charm
from mhp3ass.query import Query, SearchSpec
from mhp3ass.results.details import (
    ChestJewels,
    CorrectedJewels,
    DecorationCount,
    Placement,
    PlacementPending,
    UnbuildableJewels,
    UnknownPlacement,
    chest_jewels,
    solution_details,
)
from mhp3ass.results.placement import (
    Correction,
    JewelPlacement,
    PlacementUnknownError,
    Unbuildable,
    builds,
    correction,
    fits,
    jewel_placement,
    pick_jewels,
    place_can_matter,
    refilled,
)
from mhp3ass.results.sorting import SortKey
from mhp3ass.saved_state import LoadedResults, restore_search
from mhp3ass.savefile.import_charms import select_best
from mhp3ass.search import SearchData, run_search
from mhp3ass.solution import matches_query
from mhp3ass.solution.state import Solution


@pytest.mark.parametrize(
    ("sizes", "groups", "fitted"),
    [
        ([], [], True),
        ([1], [], False),
        ([2, 1], [3], True),
        ([2, 2], [3], False),
        ([1, 1, 1], [1, 2], True),
        ([2], [1, 1], False),
        ([3, 1], [3, 1], True),
        ([1, 3], [1, 3], True),
        ([2, 2, 1, 1], [3, 3], True),
        ([2, 2, 2], [3, 3], False),
    ],
)
def test_jewels_fit_slot_groups_several_to_a_group(sizes, groups, fitted):
    assert fits(sizes, groups=groups) is fitted


def _searched(query_json, search_data_by_language, search_pool) -> CorpusSearch:
    spec = SearchSpec.from_json(query_json)
    data = search_data_by_language[spec.query.language]
    result = run_search(spec, data=data, pool=search_pool)
    return CorpusSearch(spec=spec, data=data, result=result)


@dataclass(frozen=True)
class TorsoIncSets:
    """g13's Torso Inc sets whose chest has slots and that hold jewels, by
    whether their stored chest/elsewhere lists still hold the shown jewels;
    the search's query, its weapon slots, its game and its workers' charms."""

    agreeing: list[Solution]
    disagreeing: list[Solution]
    query: Query
    game: GameData
    weapon_slots: int
    templates: tuple[Charm | None, ...]


def _lists_agree(solution: Solution) -> bool:
    stored = Counter(solution.body_decorations + solution.non_body_decorations)
    agree = stored == Counter(solution.decorations)
    return agree


@pytest.fixture(scope="module")
def torso_inc_sets(one_skill_search) -> TorsoIncSets:
    placeable = [
        solution
        for solution in one_skill_search.result.results.all_solutions
        if solution.torso_multiplier > 1
        and solution.armors[1] is not None
        and solution.armors[1].num_slots > 0
        and solution.decorations
    ]
    query = one_skill_search.result.query
    sets = TorsoIncSets(
        agreeing=[solution for solution in placeable if _lists_agree(solution)],
        disagreeing=[solution for solution in placeable if not _lists_agree(solution)],
        query=query,
        weapon_slots=query.weapon_slots_allowed,
        game=one_skill_search.data.game,
        templates=tuple(worker.template for worker in one_skill_search.result.workers),
    )
    return sets


def _unknown(sets: TorsoIncSets) -> list[Solution]:
    """The disagreeing sets no placement fits."""
    unknown = []
    for solution in sets.disagreeing:
        try:
            jewel_placement(solution, weapon_slots=sets.weapon_slots)
        except PlacementUnknownError:
            unknown.append(solution)
    return unknown


def _placed_points(solution: Solution, placement: JewelPlacement) -> dict[Ability, int]:
    """The points a placement gives: the chest's jewels count ``multiplier``
    times and the chest piece the multiplier less its own Torso Inc (it is
    added before that counts), the other pieces, the charm and the other
    jewels once. Zero totals left out, as ``abilities`` may hold them."""
    totals: Counter[Ability] = Counter()
    weighted = [
        (armor.abilities, placement.multiplier - armor.torso_inc if slot == 1 else 1)
        for slot, armor in enumerate(solution.armors)
        if armor is not None
    ]
    if solution.charm is not None:
        weighted.append((solution.charm.abilities, 1))
    weighted += [(jewel.abilities, placement.multiplier) for jewel in placement.chest]
    weighted += [(jewel.abilities, 1) for jewel in placement.elsewhere]
    for pairs, weight in weighted:
        for pair in pairs:
            totals[pair.ability] += pair.amount * weight
    points = {ability: amount for ability, amount in totals.items() if amount != 0}
    return points


def _stored_points(solution: Solution) -> dict[Ability, int]:
    points = {ability: amount for ability, amount in solution.abilities.items() if amount != 0}
    return points


def test_agreeing_lists_are_the_placement(torso_inc_sets):
    """g13: the stored lists hold the shown jewels in 1,242 of these sets."""
    sets = torso_inc_sets.agreeing

    placements = [
        jewel_placement(solution, weapon_slots=torso_inc_sets.weapon_slots) for solution in sets
    ]

    differ = [
        solution
        for solution, placement in zip(sets, placements, strict=True)
        if placement is None
        or placement.chest != tuple(solution.body_decorations)
        or placement.elsewhere != tuple(solution.non_body_decorations)
        or _placed_points(solution, placement) != _stored_points(solution)
    ]
    assert [len(sets), differ] == [1242, []]


def test_disagreeing_lists_are_placed_from_the_shown_jewels(torso_inc_sets):
    """g13: of the 58 of these sets whose stored lists don't hold the shown
    jewels, 25 have a placement that fits the slots and gives the stored
    points. Each places every shown jewel once."""
    placed = []
    for solution in torso_inc_sets.disagreeing:
        try:
            placement = jewel_placement(solution, weapon_slots=torso_inc_sets.weapon_slots)
        except PlacementUnknownError:
            continue
        placed.append((solution, placement))

    wrong = [
        solution
        for solution, placement in placed
        if placement is None
        or Counter(placement.chest + placement.elsewhere) != Counter(solution.decorations)
        or _placed_points(solution, placement) != _stored_points(solution)
    ]
    assert [len(torso_inc_sets.disagreeing), len(placed), wrong] == [58, 25, []]


def test_jewels_no_placement_fits_raise(torso_inc_sets):
    """The other 33 (quirk 52)."""
    assert len(_unknown(torso_inc_sets)) == 33


def test_a_torso_inc_set_with_nothing_for_the_chest_has_no_split(one_skill_search):
    """g13's Torso Inc sets whose chest has no slots or that hold no jewels:
    every jewel is elsewhere, which gives the stored points."""
    weapon_slots = one_skill_search.result.query.weapon_slots_allowed
    nothing_for_the_chest = [
        solution
        for solution in one_skill_search.result.results.all_solutions
        if solution.torso_multiplier > 1
        and (
            solution.armors[1] is None
            or solution.armors[1].num_slots == 0
            or not solution.decorations
        )
    ]

    placements = [
        jewel_placement(solution, weapon_slots=weapon_slots) for solution in nothing_for_the_chest
    ]

    all_elsewhere_wrong = [
        solution
        for solution in nothing_for_the_chest
        if _placed_points(
            solution,
            JewelPlacement(
                multiplier=solution.torso_multiplier,
                chest=(),
                elsewhere=tuple(solution.decorations),
            ),
        )
        != _stored_points(solution)
    ]
    assert [len(placements), set(placements), all_elsewhere_wrong] == [336, {None}, []]


def _correction(solution: Solution, sets: TorsoIncSets) -> Correction | Unbuildable:
    found = correction(solution, query=sets.query, game=sets.game, charm_templates=sets.templates)
    return found


def _corrected_with(sets: TorsoIncSets, charm_changed: bool) -> list[Solution]:
    corrected = []
    for solution in _unknown(sets):
        found = _correction(solution, sets)
        if isinstance(found, Correction) and found.charm_changed is charm_changed:
            corrected.append(solution)
    return corrected


def _builds_with(solution: Solution, found: Correction, sets: TorsoIncSets) -> bool:
    built = builds(
        solution.armors,
        charm=found.charm,
        placement=found.placement,
        query=sets.query,
        weapon_slots=sets.weapon_slots,
    )
    return built


def test_every_unplaceable_g13_set_gets_a_version_that_builds(torso_inc_sets):
    """g13's 33 (quirk 52): 28 build with the listed charm filled again,
    5 only with the charm before reduction; each correction builds."""
    found = [
        (solution, _correction(solution, torso_inc_sets)) for solution in _unknown(torso_inc_sets)
    ]

    kinds = Counter(
        fix.charm_changed if isinstance(fix, Correction) else "unbuildable" for _, fix in found
    )
    not_building = [
        solution
        for solution, fix in found
        if isinstance(fix, Correction) and not _builds_with(solution, fix, torso_inc_sets)
    ]
    assert [kinds, not_building] == [Counter({False: 28, True: 5}), []]


@pytest.fixture(scope="module")
def refill_corrected(torso_inc_sets) -> list[Solution]:
    """g13's unplaceable sets the listed charm, filled again, builds (step 1)."""
    sets = _corrected_with(torso_inc_sets, charm_changed=False)
    return sets


def test_a_set_the_listed_charm_refills_gets_the_refills_jewels(torso_inc_sets, refill_corrected):
    """Step 1: the jewels are the refill's, which differ from the shown ones."""
    corrections = [_correction(solution, torso_inc_sets) for solution in refill_corrected]
    refills = [
        _plain_fill(solution, query=torso_inc_sets.query, game=torso_inc_sets.game)
        for solution in refill_corrected
    ]

    differ = [
        solution
        for solution, fix, refill in zip(refill_corrected, corrections, refills, strict=True)
        if not isinstance(fix, Correction)
        or refill is None
        or Counter(fix.placement.chest + fix.placement.elsewhere) != Counter(refill.decorations)
        or Counter(refill.decorations) == Counter(solution.decorations)
    ]
    assert [len(refill_corrected), differ] == [28, []]


@pytest.fixture(scope="module")
def charm_corrected(torso_inc_sets) -> list[Solution]:
    """g13's unplaceable sets only the charm before reduction builds (step 3)."""
    sets = _corrected_with(torso_inc_sets, charm_changed=True)
    return sets


def test_a_set_only_its_unreduced_charm_builds_gets_that_charm(torso_inc_sets, charm_corrected):
    """The charm is one of the search's workers' and carries more than the
    listed one; no jewel list builds the listed charm (step 2 fails)."""
    corrections = [_correction(solution, torso_inc_sets) for solution in charm_corrected]
    picks = [
        pick_jewels(
            solution.armors,
            charm=solution.charm,
            query=torso_inc_sets.query,
            game=torso_inc_sets.game,
            weapon_slots=torso_inc_sets.weapon_slots,
        )
        for solution in charm_corrected
    ]

    wrong = [
        solution
        for solution, fix, pick in zip(charm_corrected, corrections, picks, strict=True)
        if not isinstance(fix, Correction)
        or not any(fix.charm is template for template in torso_inc_sets.templates)
        or fix.charm == solution.charm
        or not isinstance(pick, Unbuildable)
    ]
    assert [len(charm_corrected), wrong] == [5, []]


@dataclass(frozen=True)
class StatusSet:
    """f112's Skull Mask S set: its search, and the set."""

    search: CorpusSearch
    solution: Solution


@pytest.fixture(scope="module")
def status_set(fuzz_goldens, search_data_by_language, search_pool) -> StatusSet:
    """f112: Anti-Theft 10, Defense 15, Status 15, bad skills off. Its Skull
    Mask S / Bnahabra Suit set (Torso Inc x3) shows jewels no placement fits;
    the bad-skill repair swapped them by raw amounts."""
    golden = next(golden for golden in fuzz_goldens if golden.name == "f112")
    search = _searched(golden.query, search_data_by_language, search_pool)
    pieces = ["Skull Mask S", "Bnahabra Suit", "Barroth Vambraces U", "Vangis Coil"]
    solution = next(
        solution
        for solution in search.result.results.all_solutions
        if [armor.name if armor is not None else None for armor in solution.armors[:4]] == pieces
        and solution.torso_multiplier == 3
    )
    return StatusSet(search=search, solution=solution)


def test_a_set_only_other_jewels_build_gets_them_from_the_picker(status_set):
    """Step 2: the listed charm refilled gives the shown jewels again, which
    don't place; the picker's list with the same charm does."""
    query = status_set.search.result.query
    game = status_set.search.data.game
    solution = status_set.solution

    found = correction(
        solution,
        query=query,
        game=game,
        charm_templates=tuple(worker.template for worker in status_set.search.result.workers),
    )

    refill = _plain_fill(solution, query=query, game=game)
    assert refill is not None
    assert Counter(refill.decorations) == Counter(solution.decorations)
    assert isinstance(found, Correction)
    assert [
        found.charm is solution.charm,
        found.charm_changed,
        [jewel.name for jewel in found.placement.chest],
        sorted(jewel.name for jewel in found.placement.elsewhere),
    ] == [
        True,
        False,
        ["Disabler Jewel 1"],
        [
            "Alarm Jewel 1",
            "Defense Jewel 1",
            "Defense Jewel 1",
            "Defense Jewel 2",
            "Disabler Jewel 2",
        ],
    ]
    assert builds(
        solution.armors,
        charm=solution.charm,
        placement=found.placement,
        query=query,
        weapon_slots=query.weapon_slots_allowed,
    )


def test_the_fill_time_lists_with_a_bad_skill_dont_build(status_set):
    """The same set's lists from before the repair keep Attack at -11, so
    Attack Down (S) shows with bad skills off."""
    query = status_set.search.result.query
    solution = status_set.solution
    before_the_repair = JewelPlacement(
        multiplier=3,
        chest=tuple(solution.body_decorations),
        elsewhere=tuple(solution.non_body_decorations),
    )

    built = builds(
        solution.armors,
        charm=solution.charm,
        placement=before_the_repair,
        query=query,
        weapon_slots=query.weapon_slots_allowed,
    )

    assert built is False


def _full_chest_set(sets: TorsoIncSets) -> Solution:
    """g13's first agreeing set whose chest is full, with a chest jewel that
    takes points from nothing."""
    for solution in sets.agreeing:
        chest = solution.body_decorations
        chest_armor = solution.armors[1]
        if chest_armor is None:
            continue
        full = sum(jewel.slots_required for jewel in chest) == chest_armor.num_slots
        if full and any(all(pair.amount > 0 for pair in jewel.abilities) for jewel in chest):
            return solution
    raise LookupError("g13 has no agreeing set with a full chest")


def test_one_jewel_past_the_chest_slots_doesnt_build(torso_inc_sets):
    """The same jewels build; one more copy of a chest jewel with no negative
    points only adds points, so the slots are the only reason it doesn't."""
    solution = _full_chest_set(torso_inc_sets)
    chest = tuple(solution.body_decorations)
    extra = next(jewel for jewel in chest if all(pair.amount > 0 for pair in jewel.abilities))
    stored = JewelPlacement(
        multiplier=solution.torso_multiplier,
        chest=chest,
        elsewhere=tuple(solution.non_body_decorations),
    )
    overfull = JewelPlacement(
        multiplier=stored.multiplier, chest=(*chest, extra), elsewhere=stored.elsewhere
    )

    results = [
        builds(
            solution.armors,
            charm=solution.charm,
            placement=placement,
            query=torso_inc_sets.query,
            weapon_slots=torso_inc_sets.weapon_slots,
        )
        for placement in (stored, overfull)
    ]

    assert results == [True, False]


def test_no_jewels_leave_the_query_skills_short(status_set):
    query = status_set.search.result.query
    solution = status_set.solution

    built = builds(
        solution.armors,
        charm=solution.charm,
        placement=JewelPlacement(multiplier=3, chest=(), elsewhere=()),
        query=query,
        weapon_slots=query.weapon_slots_allowed,
    )

    assert built is False


@pytest.fixture(scope="module")
def protection_search(fuzz_goldens, search_data_by_language, search_pool) -> CorpusSearch:
    """f318: bad skills off; 10 of its sets no jewel list builds with either charm."""
    golden = next(golden for golden in fuzz_goldens if golden.name == "f318")
    search = _searched(golden.query, search_data_by_language, search_pool)
    return search


def test_a_set_no_jewels_build_says_which_bad_skill_stays(protection_search):
    """Every usable decoration is tried, with the listed charm and the one
    before reduction: Demonic Protection stays active in each of the 10."""
    query = protection_search.result.query
    templates = tuple(worker.template for worker in protection_search.result.workers)
    placements = []
    for solution in protection_search.result.results.all_solutions:
        if solution.torso_multiplier <= 1:
            continue
        try:
            jewel_placement(solution, weapon_slots=query.weapon_slots_allowed)
        except PlacementUnknownError:
            placements.append(
                chest_jewels(
                    solution,
                    query=query,
                    refill_game=protection_search.data.game,
                    charm_templates=templates,
                )
            )

    reasons = Counter(
        tuple(skill.name for skill in placement.reason.bad_skills)
        for placement in placements
        if isinstance(placement, UnbuildableJewels)
    )

    assert reasons == Counter({("Demonic Protection",): 10})


def test_without_the_search_charms_a_set_needing_one_has_no_placement(
    torso_inc_sets, charm_corrected
):
    details = solution_details(
        charm_corrected[0],
        query=torso_inc_sets.query,
        sort_key=SortKey.NONE,
        refill_game=torso_inc_sets.game,
        charm_templates=None,
    )

    assert details.chest_jewels == UnknownPlacement()


def test_a_set_whose_listed_jewels_fit_gets_no_correction(torso_inc_sets):
    """g13's 1,267 Torso Inc sets a placement of the shown jewels fits: each
    gets that split, with the search's charms there to correct it."""
    unknown = {id(solution) for solution in _unknown(torso_inc_sets)}
    placeable = [
        solution
        for solution in torso_inc_sets.agreeing + torso_inc_sets.disagreeing
        if id(solution) not in unknown
    ]

    kinds = Counter(
        type(
            chest_jewels(
                solution,
                query=torso_inc_sets.query,
                refill_game=torso_inc_sets.game,
                charm_templates=torso_inc_sets.templates,
            )
        ).__name__
        for solution in placeable
    )

    assert kinds == Counter({"ChestJewels": 1267})


def test_a_torso_inc_set_lists_its_chest_jewels_apart(torso_inc_sets):
    """g13's first Torso Inc set with a Baggi Mail chest: one Health Jewel in
    the chest, one elsewhere."""
    solution = next(
        solution
        for solution in torso_inc_sets.agreeing
        if solution.armors[1] is not None and solution.armors[1].name == "Baggi Mail"
    )
    health_jewel = solution.decorations[0]

    jewels = chest_jewels(
        solution,
        query=torso_inc_sets.query,
        refill_game=torso_inc_sets.game,
        charm_templates=torso_inc_sets.templates,
    )

    assert health_jewel.name == "Health Jewel[1]"
    assert jewels == ChestJewels(
        multiplier=2,
        chest=(DecorationCount(decoration=health_jewel, count=1),),
        elsewhere=(DecorationCount(decoration=health_jewel, count=1),),
    )


def test_a_set_without_torso_inc_has_no_split(one_skill_search):
    """g13's sets without Torso Inc whose chest holds jewels: the place would
    matter but for the multiplier."""
    unmultiplied = [
        solution
        for solution in one_skill_search.result.results.all_solutions
        if solution.torso_multiplier == 1 and solution.body_decorations
    ]

    weapon_slots = one_skill_search.result.query.weapon_slots_allowed

    placements = [jewel_placement(solution, weapon_slots=weapon_slots) for solution in unmultiplied]

    assert [len(placements), set(placements)] == [2071, {None}]


@dataclass(frozen=True)
class LoadedCapture:
    """A GUI capture's settings.cfg loaded into its own game data."""

    data: SearchData
    results: LoadedResults


def _load_capture(settings, legacy_data_dir, language, shipped_languages) -> LoadedCapture:
    data = SearchData.load(legacy_data_dir, language=language)
    search = restore_search(
        settings,
        game=data.game,
        language=language,
        language_count=len(shipped_languages),
    )
    if search.results is None:
        raise ValueError("the capture holds no results")
    capture = LoadedCapture(data=data, results=search.results)
    return capture


@pytest.fixture(scope="module")
def loaded_capture_13(capture_settings, legacy_data_dir, shipped_languages, one_skill_search):
    """GUI capture 13: g13's query searched in the original, saved to settings.cfg."""
    capture = _load_capture(
        capture_settings["13"],
        legacy_data_dir=legacy_data_dir,
        language=one_skill_search.spec.query.language,
        shipped_languages=shipped_languages,
    )
    return capture


@dataclass(frozen=True)
class SetKey:
    """A set by its pieces', charm's and jewels' names, to match it across games."""

    armour: tuple[str | None, ...]
    charm: str | None
    jewels: tuple[str, ...]


def _set_key(solution: Solution) -> SetKey:
    key = SetKey(
        armour=tuple(armor.name if armor is not None else None for armor in solution.armors),
        charm=charm_name(solution.charm) if solution.charm is not None else None,
        jewels=tuple(sorted(decoration.name for decoration in solution.decorations)),
    )
    return key


@dataclass(frozen=True)
class NamedSplit:
    """A split by jewel names and counts, to compare it across games; in name
    order, as a refill's stored lists and a search's split list jewels in
    different orders."""

    multiplier: int
    chest: tuple[tuple[str, int], ...]
    elsewhere: tuple[tuple[str, int], ...]


@dataclass(frozen=True)
class NamedCorrection:
    """A correction by charm name and named split, to compare it across games."""

    charm: str | None
    charm_changed: bool
    jewels: NamedSplit


def _named(split: Placement) -> NamedSplit | NamedCorrection | Placement:
    if isinstance(split, CorrectedJewels):
        named_correction = NamedCorrection(
            charm=None if split.charm is None else charm_name(split.charm),
            charm_changed=split.charm_changed,
            jewels=_named_split(split.jewels),
        )
        return named_correction
    if not isinstance(split, ChestJewels):
        return split
    named = _named_split(split)
    return named


def _named_split(split: ChestJewels) -> NamedSplit:
    named = NamedSplit(
        multiplier=split.multiplier,
        chest=tuple(sorted((count.decoration.name, count.count) for count in split.chest)),
        elsewhere=tuple(sorted((count.decoration.name, count.count) for count in split.elsewhere)),
    )
    return named


def _loaded_sets(capture: LoadedCapture) -> list[Solution]:
    view = capture.results.view
    solutions = list(view.all_solutions) + list(view.no_charm_solutions)
    return solutions


def test_loaded_torso_inc_sets_get_the_split_they_get_after_the_search(
    loaded_capture_13, one_skill_search
):
    """Capture 13 has 1,300 Torso Inc sets with jewels and a chest with slots:
    1,154 refill to the loaded jewels, and each of the 1,149 that g13's
    search finds too gets the split it gets straight after the search. The
    other 5 are duplicates (same charm name and armour) where the original
    kept another copy than the port's ordered search does (quirk 5)."""
    fresh: dict[SetKey, set[NamedSplit | NamedCorrection | Placement]] = {}
    for solution in one_skill_search.result.results.all_solutions:
        # Without the charms, as for loaded results, so both sides know the same.
        split = chest_jewels(
            solution,
            query=one_skill_search.result.query,
            refill_game=one_skill_search.data.game,
            charm_templates=None,
        )
        fresh.setdefault(_set_key(solution), set()).add(_named(split))
    results = loaded_capture_13.results
    game = loaded_capture_13.data.game
    loaded = [
        solution for solution in _loaded_sets(loaded_capture_13) if place_can_matter(solution)
    ]

    refilling = [
        solution
        for solution in loaded
        if refilled(solution, query=results.query, game=game) is not None
    ]

    in_both = [solution for solution in refilling if _set_key(solution) in fresh]
    different = [
        solution
        for solution in in_both
        if _named(
            chest_jewels(solution, query=results.query, refill_game=game, charm_templates=None)
        )
        not in fresh[_set_key(solution)]
    ]
    assert [len(loaded), len(refilling), len(in_both), different] == [1300, 1154, 1149, []]


def test_a_loaded_set_the_refill_cant_reproduce_has_no_placement(loaded_capture_13):
    """Capture 13's other 146: the search filled them with the charm before
    reducing it, which settings.cfg doesn't keep."""
    results = loaded_capture_13.results
    game = loaded_capture_13.data.game
    unreproduced = [
        solution
        for solution in _loaded_sets(loaded_capture_13)
        if place_can_matter(solution) and refilled(solution, query=results.query, game=game) is None
    ]

    splits = {
        _named(chest_jewels(solution, query=results.query, refill_game=game, charm_templates=None))
        for solution in unreproduced
    }

    assert [len(unreproduced), splits] == [146, {UnknownPlacement()}]


def _plain_fill(solution: Solution, query: Query, game: GameData) -> Solution | None:
    """``solution``'s armour and charm (as custom) through MatchesQuery with
    whatever relevance the game holds; ``None`` if rejected."""
    charm = solution.charm.copy() if solution.charm is not None else None
    if charm is not None:
        charm.custom = True
    job = Solution(armors=list(solution.armors), charm=charm)
    if not matches_query(job, query, game):
        return None
    return job


@dataclass(frozen=True)
class RefillingSet:
    """A loaded set and its refill."""

    solution: Solution
    refill: Solution


@pytest.fixture(scope="module")
def refilling_loaded_set(loaded_capture_13) -> RefillingSet:
    """Capture 13's first loaded Torso Inc set that refills."""
    results = loaded_capture_13.results
    game = loaded_capture_13.data.game
    for solution in _loaded_sets(loaded_capture_13):
        if not place_can_matter(solution):
            continue
        refill = refilled(solution, query=results.query, game=game)
        if refill is not None:
            return RefillingSet(solution=solution, refill=refill)
    raise LookupError("capture 13 has no loaded set that refills")


def test_a_loaded_set_refills_the_same_after_a_charm_import(
    loaded_capture_13, refilling_loaded_set
):
    """A charm import's select_best leaves every ability relevant, under which
    the search's fill fails on this set (a relevant ability it has no need
    for); the refill sets the loaded query's relevance again."""
    game = loaded_capture_13.data.game
    query = loaded_capture_13.results.query
    select_best([], game=game)
    with pytest.raises(KeyError):
        _plain_fill(refilling_loaded_set.solution, query=query, game=game)

    after = refilled(
        refilling_loaded_set.solution, query=loaded_capture_13.results.query, game=game
    )

    before = refilling_loaded_set.refill
    assert after is not None
    assert [after.torso_multiplier, after.body_decorations, after.non_body_decorations] == [
        before.torso_multiplier,
        before.body_decorations,
        before.non_body_decorations,
    ]


def test_a_loaded_set_waits_while_a_search_runs(loaded_capture_13, refilling_loaded_set):
    split = chest_jewels(
        refilling_loaded_set.solution,
        query=loaded_capture_13.results.query,
        refill_game=None,
        charm_templates=None,
    )

    assert split == PlacementPending()


def test_a_refill_leaves_the_loaded_charm_as_it_was(loaded_capture_13, refilling_loaded_set):
    charm = refilling_loaded_set.solution.charm
    if charm is None:
        raise LookupError("the flag-dependent set has no charm")
    before = (charm.num_slots, charm.custom, [(p.ability, p.amount) for p in charm.abilities])

    refilled(
        refilling_loaded_set.solution,
        query=loaded_capture_13.results.query,
        game=loaded_capture_13.data.game,
    )

    after = (charm.num_slots, charm.custom, [(p.ability, p.amount) for p in charm.abilities])
    assert after == before


@pytest.fixture(scope="module")
def rejected_loaded_set(loaded_capture_13) -> Solution:
    """Capture 13's first loaded Torso Inc set whose armour and charm
    MatchesQuery rejects when filled again under its own relevance."""
    results = loaded_capture_13.results
    game = loaded_capture_13.data.game
    for solution in _loaded_sets(loaded_capture_13):
        if not place_can_matter(solution):
            continue
        # Sets the loaded query's relevance, for the plain fill after it.
        if refilled(solution, query=results.query, game=game) is not None:
            continue
        if _plain_fill(solution, query=results.query, game=game) is None:
            return solution
    raise LookupError("capture 13 has no loaded set the refill rejects")


def test_a_loaded_set_the_search_rejects_isnt_refilled(loaded_capture_13, rejected_loaded_set):
    refill = refilled(
        rejected_loaded_set, query=loaded_capture_13.results.query, game=loaded_capture_13.data.game
    )

    assert refill is None


def test_a_charm_free_loaded_set_refills_without_a_charm(loaded_capture_13):
    """Capture 13's charm-free Torso Inc sets that refill: the refill keeps
    no charm and finds the multiplier."""
    results = loaded_capture_13.results
    game = loaded_capture_13.data.game
    charm_free = [
        solution for solution in results.view.no_charm_solutions if place_can_matter(solution)
    ]

    refills = [refilled(solution, query=results.query, game=game) for solution in charm_free]

    reproduced = [refill for refill in refills if refill is not None]
    assert reproduced != []
    assert {refill.charm for refill in reproduced} == {None}
    assert all(refill.torso_multiplier > 1 for refill in reproduced)


@pytest.fixture
def torso_inc_head(teamhgg_game) -> Armor:
    head = next(armor for armor in teamhgg_game.armors[ArmorType.HEAD] if armor.torso_inc)
    return head


@pytest.fixture
def slotted_chest(teamhgg_game) -> Armor:
    chest = next(
        armor
        for armor in teamhgg_game.armors[ArmorType.BODY]
        if armor.num_slots > 0 and not armor.torso_inc
    )
    return chest


@pytest.fixture
def slotless_chest(teamhgg_game) -> Armor:
    chest = next(
        armor
        for armor in teamhgg_game.armors[ArmorType.BODY]
        if armor.num_slots == 0 and not armor.torso_inc
    )
    return chest


@pytest.mark.parametrize(
    ("head", "chest", "jewel_count", "can_matter"),
    [
        pytest.param(
            "torso_inc_head", "slotted_chest", 1, True, id="torso-inc-slotted-chest-jewel"
        ),
        pytest.param(None, "slotted_chest", 1, False, id="no-torso-inc"),
        pytest.param("torso_inc_head", "slotless_chest", 1, False, id="slotless-chest"),
        pytest.param("torso_inc_head", "slotted_chest", 0, False, id="no-jewels"),
    ],
)
def test_a_jewel_place_matters_only_with_torso_inc_a_slotted_chest_and_jewels(
    request, teamhgg_game, head, chest, jewel_count, can_matter
):
    head_piece = request.getfixturevalue(head) if head is not None else None
    solution = Solution(
        armors=[head_piece, request.getfixturevalue(chest), None, None, None],
        charm=None,
        decorations=teamhgg_game.decorations[:jewel_count],
    )

    assert place_can_matter(solution) is can_matter
