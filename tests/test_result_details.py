"""What each result shows (Form1.h:1569-1655), on a corpus search and on
synthetic solutions."""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from mhp3ass.model import Ability, Armor, Material, MaterialComponent, Skill
from mhp3ass.query import SearchSpec
from mhp3ass.relevance import formulate_query
from mhp3ass.results.details import (
    AbilityLine,
    ArmorLine,
    ArmorNote,
    DecorationCount,
    SlotsSpare,
    SortValue,
    armor_details,
    armor_note,
    decoration_details,
    slots_spare,
    solution_details,
    sort_value,
)
from mhp3ass.results.result_set import SearchResult
from mhp3ass.results.sorting import SortKey
from mhp3ass.search import SearchData, run_search
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
                solution, query=search.result.query, sort_key=SortKey.NONE
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
    decorated_solution, make_query, attack
):
    asked = decorated_solution.extra_skills[0]
    query = make_query(rel_abilities=[attack], skills=[asked])

    details = solution_details(decorated_solution, query=query, sort_key=SortKey.DEFENCE)

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
