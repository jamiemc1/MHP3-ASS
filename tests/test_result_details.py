"""What each result shows (Form1.h:1569-1655), on a corpus search and on
synthetic solutions."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

import pytest

from mhp3ass.charms.naming import charm_name
from mhp3ass.data import GameData
from mhp3ass.model import Ability, Armor, ArmorType, Material, MaterialComponent, Skill
from mhp3ass.query import Query, SearchSpec
from mhp3ass.relevance import formulate_query
from mhp3ass.results.details import (
    AbilityLine,
    ArmorLine,
    ArmorNote,
    ChestJewels,
    DecorationCount,
    PlacementPending,
    SlotsSpare,
    SortValue,
    UnknownPlacement,
    armor_details,
    armor_note,
    chest_jewels,
    decoration_details,
    slots_spare,
    solution_details,
    sort_value,
)
from mhp3ass.results.difficulty import hard_materials
from mhp3ass.results.placement import (
    JewelPlacement,
    PlacementUnknownError,
    jewel_placement,
    place_can_matter,
    refilled,
)
from mhp3ass.results.result_set import SearchResult
from mhp3ass.results.sorting import SortKey
from mhp3ass.saved_state import LoadedResults, restore_search
from mhp3ass.savefile.import_charms import select_best
from mhp3ass.search import SearchData, run_search
from mhp3ass.settings_cfg import read_settings_cfg
from mhp3ass.solution import matches_query
from mhp3ass.solution.state import Solution
from solution_builders import make_jewel


@dataclass(frozen=True)
class CorpusSearch:
    spec: SearchSpec
    data: SearchData
    result: SearchResult


def _corpus_search(query_id, search_goldens, search_data_by_language, search_pool):
    golden = next(golden for golden in search_goldens if golden.manifest["id"] == query_id)
    spec = SearchSpec.from_json(golden.query)
    data = search_data_by_language[spec.query.language]
    result = run_search(spec, data=data, pool=search_pool)
    return CorpusSearch(spec=spec, data=data, result=result)


@pytest.fixture(scope="module")
def one_skill_search(search_goldens, search_data_by_language, search_pool) -> CorpusSearch:
    """g13: HR 3, Attack Up + Health, one-skill charms; 4,444 solutions with
    both armour notes and every slots-spare form."""
    search = _corpus_search(
        "g13",
        search_goldens=search_goldens,
        search_data_by_language=search_data_by_language,
        search_pool=search_pool,
    )
    return search


@pytest.fixture
def other_query_spec(search_goldens) -> SearchSpec:
    """1a's query: HR 6, Attack Up [Med] + Sharp Sword, so different relevant abilities."""
    golden = next(golden for golden in search_goldens if golden.manifest["id"] == "1a")
    spec = SearchSpec.from_json(golden.query)
    return spec


def _notes(search: CorpusSearch) -> list[list[ArmorNote | None]]:
    notes = [
        [
            line.note
            for line in solution_details(
                solution,
                query=search.result.query,
                sort_key=SortKey.NONE,
                refill_game=search.data.game,
            ).armors
        ]
        for solution in search.result.results.all_solutions
    ]
    return notes


def _flag_notes(search: CorpusSearch) -> list[list[ArmorNote | None]]:
    """The notes the original reads from the shared armour flags."""
    notes = [
        [
            ArmorNote.ANY_WITH_SLOTS
            if armor.no_skills
            else ArmorNote.ANY_TORSO_INC
            if armor.torso_inc
            else None
            for armor in solution.armors
            if armor is not None
        ]
        for solution in search.result.results.all_solutions
    ]
    return notes


def test_notes_match_the_flags_the_search_relevance_pass_sets(one_skill_search):
    formulate_query(one_skill_search.data.game, one_skill_search.spec.query)

    notes = _notes(one_skill_search)

    assert notes == _flag_notes(one_skill_search)
    assert {note for solution in notes for note in solution} == {
        None,
        ArmorNote.ANY_WITH_SLOTS,
        ArmorNote.ANY_TORSO_INC,
    }


def test_notes_follow_the_search_query_after_another_relevance_pass(
    one_skill_search, other_query_spec
):
    """Quirk 47: the original re-renders from whichever query ran last."""
    formulate_query(one_skill_search.data.game, one_skill_search.spec.query)
    before = _notes(one_skill_search)

    formulate_query(one_skill_search.data.game, other_query_spec.query)

    assert _notes(one_skill_search) == before
    assert _flag_notes(one_skill_search) != before


def test_every_shown_spare_group_breakdown_adds_up_to_its_total(one_skill_search):
    shown = [
        slots_spare(solution, SortKey.NONE)
        for solution in one_skill_search.result.results.all_solutions
    ]

    breakdowns = [
        (spare.total, spare.groups)
        for spare in shown
        if spare is not None and spare.groups is not None
    ]
    assert all(sum(groups) == total and len(groups) > 1 for total, groups in breakdowns)
    assert [len(breakdowns), shown.count(None)] == [1714, 814]


@pytest.fixture
def health() -> Ability:
    return Ability(name="Health", static_index=2)


@pytest.mark.parametrize(
    ("piece", "note"),
    [
        ({"abilities": "relevant", "amount": 2}, None),
        ({"abilities": "relevant", "amount": -2}, ArmorNote.ANY_WITH_SLOTS),
        ({"abilities": "other", "amount": 2}, ArmorNote.ANY_WITH_SLOTS),
        ({"abilities": "relevant", "amount": 2, "torso_inc": True}, ArmorNote.ANY_TORSO_INC),
    ],
)
def test_a_piece_is_noted_by_its_points_in_the_search_skills(
    piece, note, make_armor, make_query, attack, health
):
    ability = attack if piece["abilities"] == "relevant" else health
    armor = make_armor(
        abilities=[(ability, piece["amount"])], torso_inc=piece.get("torso_inc", False)
    )

    assert armor_note(armor, make_query(rel_abilities=[attack])) is note


@pytest.mark.parametrize(
    ("total", "groups", "sort_key", "shown"),
    [
        (0, [0, 0, 0, 0], SortKey.NONE, None),
        (0, [0, 0, 0, 0], SortKey.SLOTS_SPARE, SlotsSpare(total=0, groups=None)),
        (1, [0, 1, 0, 0], SortKey.NONE, SlotsSpare(total=1, groups=None)),
        (2, [0, 0, 1, 0], SortKey.NONE, SlotsSpare(total=2, groups=None)),
        (3, [0, 0, 0, 1], SortKey.NONE, SlotsSpare(total=3, groups=None)),
        (2, None, SortKey.NONE, SlotsSpare(total=2, groups=None)),
        (2, [0, 2, 0, 0], SortKey.NONE, SlotsSpare(total=2, groups=(1, 1))),
        (3, [0, 1, 1, 0], SortKey.NONE, SlotsSpare(total=3, groups=(1, 2))),
        (4, [0, 0, 2, 0], SortKey.NONE, SlotsSpare(total=4, groups=(2, 2))),
        (4, [0, 1, 0, 1], SortKey.NONE, SlotsSpare(total=4, groups=(1, 3))),
    ],
)
def test_slots_spare_shows_a_breakdown_only_when_the_total_isnt_one_group(
    total, groups, sort_key, shown
):
    solution = Solution(armors=[], charm=None, total_slots_spare=total, slots_spare=groups)

    assert slots_spare(solution, sort_key) == shown


@pytest.fixture
def stat_solution() -> Solution:
    """A solution with a different value in every sortable stat."""
    solution = Solution(
        armors=[],
        charm=None,
        dragon_res=1,
        fire_res=2,
        ice_res=3,
        thunder_res=4,
        water_res=5,
        defence=6,
        max_defence=7,
        difficulty=8,
        rarity=9,
    )
    return solution


@pytest.mark.parametrize(
    ("key", "value"),
    [
        (SortKey.NONE, None),
        (SortKey.DRAGON_RES, 1),
        (SortKey.FIRE_RES, 2),
        (SortKey.ICE_RES, 3),
        (SortKey.THUNDER_RES, 4),
        (SortKey.WATER_RES, 5),
        (SortKey.DEFENCE, 6),
        (SortKey.MAX_DEFENCE, 7),
        (SortKey.DIFFICULTY, 8),
        (SortKey.RARITY, 9),
        (SortKey.SLOTS_SPARE, None),
    ],
)
def test_the_sort_value_is_the_sorted_stat(key, value, stat_solution):
    shown = None if value is None else SortValue(key=key, value=value)

    assert sort_value(stat_solution, key) == shown


@pytest.fixture
def decorated_solution(make_armor, attack, health) -> Solution:
    """Head and legs only, no charm, jewels A, B, A, and extra skills one of
    which the search asked for."""
    jewel_a = make_jewel("A", first=attack, amount=1)
    jewel_b = make_jewel("B", first=health, amount=1)
    solution = Solution(
        armors=[make_armor("Head", abilities=[(attack, 1)]), None, None, None, make_armor("Legs")],
        charm=None,
        decorations=[jewel_a, jewel_b, jewel_a],
        extra_skills=[
            Skill(name="Attack Up [S]", points_required=10, ability=attack),
            Skill(name="Health +20", points_required=10, ability=health),
        ],
    )
    return solution


def test_details_list_pieces_jewel_counts_and_the_unsearched_extra_skills(
    decorated_solution, make_query, attack, teamhgg_game
):
    asked = decorated_solution.extra_skills[0]
    query = make_query(rel_abilities=[attack], skills=[asked])

    details = solution_details(
        decorated_solution, query=query, sort_key=SortKey.DEFENCE, refill_game=teamhgg_game
    )

    head, legs = decorated_solution.armors[0], decorated_solution.armors[4]
    jewel_a, jewel_b = decorated_solution.decorations[:2]
    assert details.armors == (
        ArmorLine(armor=head, note=None),
        ArmorLine(armor=legs, note=ArmorNote.ANY_WITH_SLOTS),
    )
    assert details.decorations == (
        DecorationCount(decoration=jewel_a, count=2),
        DecorationCount(decoration=jewel_b, count=1),
    )
    assert details.extra_skills == (decorated_solution.extra_skills[1],)
    assert [details.charm, details.slots_spare, details.sort_value] == [
        None,
        None,
        SortValue(key=SortKey.DEFENCE, value=0),
    ]


@pytest.fixture
def torso_inc_pieces(teamhgg_game) -> list[Armor]:
    pieces = [
        armor for armors in teamhgg_game.armors.values() for armor in armors if armor.torso_inc
    ]
    return pieces


def test_torso_inc_pieces_list_torso_inc_by_name_alone(torso_inc_pieces, teamhgg_game):
    torso_inc_line = AbilityLine(ability=teamhgg_game.torso_inc, amount=None)

    lines = [armor_details(armor, teamhgg_game).abilities for armor in torso_inc_pieces]

    assert len(torso_inc_pieces) > 0
    assert all(torso_inc_line in piece_lines for piece_lines in lines)


@pytest.fixture
def two_recipe_jewel(attack, health):
    """A jewel with +2 Attack, 0 Health and a second recipe."""
    jewel = make_jewel("Jewel", first=attack, amount=2, second=health, second_amount=0)
    jewel.components = [MaterialComponent(material=Material(name="Ore"), amount=3)]
    jewel.components2 = [MaterialComponent(material=Material(name="Bone"), amount=1)]
    return jewel


def test_a_jewel_lists_points_and_both_recipes(two_recipe_jewel, teamhgg_game, attack, health):
    details = decoration_details(two_recipe_jewel, teamhgg_game)

    assert details.abilities == (
        AbilityLine(ability=attack, amount=2),
        AbilityLine(ability=health, amount=None),
    )
    assert [details.components, details.alternative_components] == [
        tuple(two_recipe_jewel.components),
        tuple(two_recipe_jewel.components2),
    ]


@pytest.fixture
def attack_torso_inc_piece(make_armor, teamhgg_game, attack):
    """A piece with +3 Attack and +1 Torso Inc, no recipe."""
    armor = make_armor(abilities=[(attack, 3), (teamhgg_game.torso_inc, 1)])
    return armor


def test_a_piece_lists_its_points_and_recipe(attack_torso_inc_piece, teamhgg_game, attack):
    details = armor_details(attack_torso_inc_piece, teamhgg_game)

    assert details.abilities == (
        AbilityLine(ability=attack, amount=3),
        AbilityLine(ability=teamhgg_game.torso_inc, amount=None),
    )
    assert [details.armor, details.components] == [attack_torso_inc_piece, ()]


def test_the_hard_materials_add_up_to_every_found_sets_difficulty(one_skill_search):
    """g13: HR 3, Attack Up + Health, one-skill charms."""
    mismatched = [
        solution
        for solution in one_skill_search.result.results.all_solutions
        if sum(part.count * part.material.difficulty for part in hard_materials(solution))
        != solution.difficulty
    ]

    assert mismatched == []


@dataclass(frozen=True)
class TorsoIncSets:
    """g13's Torso Inc sets whose chest has slots and that hold jewels, by
    whether their stored chest/elsewhere lists still hold the shown jewels;
    the search's query, its weapon slots and its game."""

    agreeing: list[Solution]
    disagreeing: list[Solution]
    query: Query
    game: GameData
    weapon_slots: int


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


def test_a_set_no_placement_fits_keeps_one_list(torso_inc_sets):
    unknown = _unknown(torso_inc_sets)[0]

    details = solution_details(
        unknown, query=torso_inc_sets.query, sort_key=SortKey.NONE, refill_game=torso_inc_sets.game
    )

    assert details.chest_jewels == UnknownPlacement()


def test_a_torso_inc_set_lists_its_chest_jewels_apart(torso_inc_sets):
    """g13's first Torso Inc set with a Baggi Mail chest: one Health Jewel in
    the chest, one elsewhere."""
    solution = next(
        solution
        for solution in torso_inc_sets.agreeing
        if solution.armors[1] is not None and solution.armors[1].name == "Baggi Mail"
    )
    health_jewel = solution.decorations[0]

    jewels = chest_jewels(solution, query=torso_inc_sets.query, refill_game=torso_inc_sets.game)

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


@pytest.fixture
def hard_parts_solution(make_armor, attack):
    """Head: 3 Ruby (2) and 1 Bone (0); legs: 1 Plate (5) and 2 Ruby;
    two jewels each needing 4 Ruby and an event Ticket (0)."""
    ruby = Material(name="Ruby", difficulty=2)
    plate = Material(name="Plate", difficulty=5)
    bone = Material(name="Bone")
    ticket = Material(name="Ticket", event_only=True)
    head = make_armor(
        "Head",
        components=[
            MaterialComponent(material=ruby, amount=3),
            MaterialComponent(material=bone, amount=1),
        ],
    )
    legs = make_armor(
        "Legs",
        components=[
            MaterialComponent(material=plate, amount=1),
            MaterialComponent(material=ruby, amount=2),
        ],
    )
    jewel = make_jewel("Jewel", first=attack, amount=1)
    jewel.components = [
        MaterialComponent(material=ruby, amount=4),
        MaterialComponent(material=ticket, amount=1),
    ]
    solution = Solution(
        armors=[head, None, None, None, legs], charm=None, decorations=[jewel, jewel]
    )
    return solution


def test_pieces_count_each_unit_and_jewels_each_material_once(hard_parts_solution):
    parts = hard_materials(hard_parts_solution)

    assert [(part.material.name, part.count) for part in parts] == [("Ruby", 7), ("Plate", 1)]


def test_a_set_without_hard_materials_lists_none(make_armor):
    solution = Solution(armors=[make_armor(), None, None, None, None], charm=None)

    assert hard_materials(solution) == []


@dataclass(frozen=True)
class LoadedCapture:
    """A GUI capture's settings.cfg loaded into its own game data."""

    data: SearchData
    results: LoadedResults


def _load_capture(path, legacy_data_dir, language, shipped_languages) -> LoadedCapture:
    data = SearchData.load(legacy_data_dir, language=language)
    search = restore_search(
        read_settings_cfg(path),
        game=data.game,
        language=language,
        language_count=len(shipped_languages),
    )
    if search.results is None:
        raise ValueError(f"{path} holds no results")
    capture = LoadedCapture(data=data, results=search.results)
    return capture


@pytest.fixture(scope="module")
def loaded_capture_13(gui_captures_dir, legacy_data_dir, shipped_languages, one_skill_search):
    """GUI capture 13: g13's query searched in the original, saved to settings.cfg."""
    capture = _load_capture(
        gui_captures_dir / "13" / "settings.cfg",
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


def _named(
    split: ChestJewels | UnknownPlacement | PlacementPending | None,
) -> NamedSplit | UnknownPlacement | PlacementPending | None:
    if not isinstance(split, ChestJewels):
        return split
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
    fresh: dict[SetKey, set[NamedSplit | UnknownPlacement | PlacementPending | None]] = {}
    for solution in one_skill_search.result.results.all_solutions:
        split = chest_jewels(
            solution,
            query=one_skill_search.result.query,
            refill_game=one_skill_search.data.game,
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
        if _named(chest_jewels(solution, query=results.query, refill_game=game))
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
        _named(chest_jewels(solution, query=results.query, refill_game=game))
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


def test_a_jewel_place_can_matter_with_torso_inc_a_slotted_chest_and_jewels(
    teamhgg_game, torso_inc_head, slotted_chest
):
    solution = Solution(
        armors=[torso_inc_head, slotted_chest, None, None, None],
        charm=None,
        decorations=[teamhgg_game.decorations[0]],
    )

    assert place_can_matter(solution) is True


def test_a_jewel_place_cant_matter_without_torso_inc(teamhgg_game, slotted_chest):
    solution = Solution(
        armors=[None, slotted_chest, None, None, None],
        charm=None,
        decorations=[teamhgg_game.decorations[0]],
    )

    assert place_can_matter(solution) is False


def test_a_jewel_place_cant_matter_with_a_slotless_chest(
    teamhgg_game, torso_inc_head, slotless_chest
):
    solution = Solution(
        armors=[torso_inc_head, slotless_chest, None, None, None],
        charm=None,
        decorations=[teamhgg_game.decorations[0]],
    )

    assert place_can_matter(solution) is False


def test_a_jewel_place_cant_matter_without_jewels(torso_inc_head, slotted_chest):
    solution = Solution(armors=[torso_inc_head, slotted_chest, None, None, None], charm=None)

    assert place_can_matter(solution) is False
