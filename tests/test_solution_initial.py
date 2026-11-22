"""GetInitialData and its helpers against every trace's initial stage, and the
rules the traces don't isolate."""

from __future__ import annotations

import pytest

from mhp3ass.model import AbilityPair, Charm, Skill
from mhp3ass.solution.initial import add_armor_stats, add_decoration, detrimental, get_initial_data
from mhp3ass.solution.state import Place, Solution, new_calculation_data
from solution_builders import make_jewel
from solution_trace import Stage, stage_mismatches


def test_initial_stage_matches_every_trace(every_trace_goldens, scratch_game):
    mismatches = stage_mismatches(
        every_trace_goldens, scratch_game, [Stage(name="initial", run=get_initial_data)]
    )

    assert mismatches == []


@pytest.fixture
def attack_skill(attack):
    return Skill(name="Attack Up [Sm]", points_required=10, ability=attack)


@pytest.fixture
def sharpness(make_ability):
    return make_ability("Sharpness", 2)


def _initial(armors, query, charm=None):
    solution = Solution(armors=armors, charm=charm)
    data = new_calculation_data(solution, query)
    get_initial_data(data)
    return data


def test_body_skills_take_the_multiplier_the_other_pieces_set(
    make_armor, make_query, attack, attack_skill
):
    head = make_armor("Torso-up head", abilities=[(attack, 1)], torso_inc=True)
    legs = make_armor("Torso-up legs", torso_inc=True)
    body = make_armor("Body", abilities=[(attack, 3)])
    query = make_query(skills=[attack_skill])

    data = _initial([head, body, None, None, legs], query)

    assert data.solution.torso_multiplier == 3
    assert data.solution.abilities[attack] == 1 + 3 * 3


def test_abilities_insert_query_skills_then_head_arms_waist_legs_body_charm(
    make_armor, make_query, make_ability, attack, defense, sharpness, attack_skill
):
    expertise = make_ability("Expert", 3)
    guard = make_ability("Guard", 4)
    pieces = [
        make_armor(f"piece {i}", abilities=[(ability, 1)])
        for i, ability in enumerate([defense, sharpness, expertise, guard, attack])
    ]
    charm_ability = make_ability("Charm skill", 5)
    charm = Charm(abilities=[AbilityPair(ability=charm_ability, amount=2)])
    query = make_query(skills=[attack_skill])

    data = _initial(pieces, query, charm=charm)

    # pieces: head defense, body sharpness, arms expertise, waist guard, legs attack.
    order = [ability.name for ability in data.solution.abilities]
    assert order == ["Attack", "Defense", "Expert", "Guard", "Sharpness", "Charm skill"]


def test_body_slots_are_torso_slots_not_a_slot_group(make_armor, make_query):
    body = make_armor("Body", num_slots=3)
    head = make_armor("Head", num_slots=2)
    query = make_query(weapon_slots_allowed=1)

    data = _initial([head, body, None, None, None], query)

    solution = data.solution
    assert (solution.slots_spare, solution.torso_slots_spare, solution.total_slots_spare) == (
        [0, 1, 1, 0],
        3,
        6,
    )


def test_charm_slots_form_a_group_and_charm_abilities_need_nothing(
    make_query, attack, sharpness, attack_skill
):
    charm = Charm(
        num_slots=2,
        abilities=[AbilityPair(ability=attack, amount=4), AbilityPair(ability=sharpness, amount=3)],
    )
    query = make_query(skills=[attack_skill])

    data = _initial([None] * 5, query, charm=charm)

    assert data.need == {attack: 10, sharpness: 0}
    assert data.solution.slots_spare == [0, 0, 1, 0]
    assert data.solution.abilities == {attack: 4, sharpness: 3}


def test_empty_body_leaves_no_torso_slots(make_query):
    data = _initial([None] * 5, make_query(weapon_slots_allowed=3))

    solution = data.solution
    assert (solution.torso_slots_spare, solution.torso_multiplier, solution.slots_spare) == (
        0,
        1,
        [0, 0, 0, 1],
    )


def test_query_skills_seed_need_relevant_and_abilities_in_order(
    make_query, attack, sharpness, attack_skill
):
    sharp_skill = Skill(name="Sharpness +1", points_required=10, ability=sharpness)

    data = _initial([None] * 5, make_query(skills=[sharp_skill, attack_skill]))

    assert list(data.need.items()) == [(sharpness, 10), (attack, 10)]
    assert data.relevant == {sharp_skill, attack_skill}
    assert list(data.solution.abilities.items()) == [(sharpness, 0), (attack, 0)]


def test_two_skills_with_one_ability_raise_as_dictionary_add(make_query, attack, attack_skill):
    larger = Skill(name="Attack Up [Med]", points_required=15, ability=attack)
    data = new_calculation_data(
        Solution(armors=[None] * 5, charm=None), make_query(skills=[attack_skill, larger])
    )

    with pytest.raises(KeyError):
        get_initial_data(data)
    assert (data.need, data.relevant, data.solution.abilities) == ({}, set(), {})


def test_add_decoration_spends_slots_unsigned(attack):
    solution = Solution(armors=[None] * 5, charm=None)
    solution.abilities = {attack: 0}
    deck = []

    above = add_decoration(
        solution, make_jewel("Jewel", attack, 2, slots=3), multiplier=2, decoration_list=deck
    )

    assert above
    assert solution.abilities == {attack: 4}
    assert solution.total_slots_spare == 2**32 - 3
    assert (len(solution.decorations), len(deck)) == (1, 1)


def test_add_decoration_reports_the_first_ability_at_minus_ten(attack):
    solution = Solution(armors=[None] * 5, charm=None)
    solution.abilities = {attack: -11}

    above = add_decoration(
        solution, make_jewel("Jewel", attack, 1), multiplier=1, decoration_list=[]
    )

    assert not above
    assert solution.abilities[attack] == -10


def test_add_decoration_places_a_gem_by_its_list(attack):
    jewel = make_jewel("Jewel", attack, 1)
    solution = Solution(armors=[None] * 5, charm=None)

    add_decoration(solution, jewel, multiplier=1, decoration_list=solution.non_body_decorations)
    add_decoration(solution, jewel, multiplier=2, decoration_list=solution.body_decorations)

    assert solution.places == [Place.ELSEWHERE, Place.CHEST]


def test_detrimental_only_for_a_relevant_second_skill_falling_short(make_query, attack, defense):
    solution = Solution(armors=[None] * 5, charm=None)
    solution.abilities = {attack: 0, defense: 3}
    data = new_calculation_data(solution, make_query())
    data.need = {attack: 10, defense: 3}
    jewel = make_jewel("Jewel", attack, 1, second=defense, second_amount=-1)

    data.query.relevant_abilities = frozenset()
    irrelevant = detrimental(jewel, data)
    data.query.relevant_abilities = frozenset({defense})
    short = detrimental(jewel, data)
    data.solution.abilities[defense] = 4
    enough = detrimental(jewel, data)

    assert (irrelevant, short, enough) == (False, True, False)


def test_add_armor_stats_adds_each_stat(make_armor):
    solution = Solution(armors=[None] * 5, charm=None)
    piece = make_armor(
        defence=10,
        max_defence=20,
        fire_res=1,
        water_res=2,
        ice_res=3,
        thunder_res=4,
        dragon_res=5,
        rarity=6,
        difficulty=7,
    )

    add_armor_stats(solution, piece)
    add_armor_stats(solution, piece)

    stats = [
        solution.defence,
        solution.max_defence,
        solution.fire_res,
        solution.water_res,
        solution.ice_res,
        solution.thunder_res,
        solution.dragon_res,
        solution.rarity,
        solution.difficulty,
    ]
    assert stats == [20, 40, 2, 4, 6, 8, 10, 12, 14]


def test_add_armor_stats_wraps_the_unsigned_stats_but_not_resistances(make_armor):
    solution = Solution(armors=[None] * 5, charm=None)
    piece = make_armor(defence=-1, max_defence=-2, rarity=-3, difficulty=-4, fire_res=-5)

    add_armor_stats(solution, piece)

    stats = [
        solution.defence,
        solution.max_defence,
        solution.rarity,
        solution.difficulty,
        solution.fire_res,
    ]
    assert stats == [2**32 - 1, 2**32 - 2, 2**32 - 3, 2**32 - 4, -5]
