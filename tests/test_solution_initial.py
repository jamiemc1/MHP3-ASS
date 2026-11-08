"""GetInitialData and its helpers against every trace's initial stage, and the
rules the traces don't isolate."""

from __future__ import annotations

import pytest

from mhp3ass.model import Ability, AbilityPair, Charm, Decoration, Skill
from mhp3ass.solution.initial import add_decoration, detrimental, get_initial_data
from mhp3ass.solution.state import Solution, new_calculation_data
from solution_trace import Stage, stage_mismatches


def test_initial_stage_matches_every_trace(trace_goldens, scratch_game):
    assert (
        stage_mismatches(trace_goldens, scratch_game, [Stage(name="initial", run=get_initial_data)])
        == []
    )


def test_personal_initial_stage_matches_every_trace(personal_trace_goldens, scratch_game):
    mismatches = stage_mismatches(
        personal_trace_goldens, scratch_game, [Stage(name="initial", run=get_initial_data)]
    )

    assert mismatches == []


@pytest.fixture
def attack_skill(attack):
    return Skill(name="Attack Up [Sm]", points_required=10, ability=attack)


@pytest.fixture
def sharpness():
    return Ability(name="Sharpness", static_index=2)


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
    make_armor, make_query, attack, defense, sharpness, attack_skill
):
    expertise = Ability(name="Expert", static_index=3)
    guard = Ability(name="Guard", static_index=4)
    pieces = [
        make_armor(f"piece {i}", abilities=[(ability, 1)])
        for i, ability in enumerate([defense, sharpness, expertise, guard, attack])
    ]
    charm_ability = Ability(name="Charm skill", static_index=5)
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


def test_two_skills_with_one_ability_raise_as_dictionary_add(make_query, attack, attack_skill):
    larger = Skill(name="Attack Up [Med]", points_required=15, ability=attack)

    with pytest.raises(KeyError):
        _initial([None] * 5, make_query(skills=[attack_skill, larger]))


def _jewel(first, amount, second=None, second_amount=0, slots=1):
    decoration = Decoration(
        name="Jewel", index=0, rarity=1, slots_required=slots, hr=1, elder_star=1
    )
    decoration.abilities = [AbilityPair(ability=first, amount=amount)]
    if second is not None:
        decoration.abilities.append(AbilityPair(ability=second, amount=second_amount))
    return decoration


def test_add_decoration_spends_slots_unsigned(attack):
    solution = Solution(armors=[None] * 5, charm=None)
    solution.abilities = {attack: 0}
    deck = []

    above = add_decoration(solution, _jewel(attack, 2, slots=3), multiplier=2, decoration_list=deck)

    assert above
    assert solution.abilities == {attack: 4}
    assert solution.total_slots_spare == 2**32 - 3
    assert (len(solution.decorations), len(deck)) == (1, 1)


def test_add_decoration_reports_the_first_ability_at_minus_ten(attack):
    solution = Solution(armors=[None] * 5, charm=None)
    solution.abilities = {attack: -11}

    above = add_decoration(solution, _jewel(attack, 1), multiplier=1, decoration_list=[])

    assert not above
    assert solution.abilities[attack] == -10


def test_detrimental_only_for_a_relevant_second_skill_falling_short(make_query, attack, defense):
    solution = Solution(armors=[None] * 5, charm=None)
    solution.abilities = {attack: 0, defense: 3}
    data = new_calculation_data(solution, make_query())
    data.need = {attack: 10, defense: 3}
    jewel = _jewel(attack, 1, second=defense, second_amount=-1)

    defense.relevant = False
    irrelevant = detrimental(jewel, data)
    defense.relevant = True
    short = detrimental(jewel, data)
    data.solution.abilities[defense] = 4
    enough = detrimental(jewel, data)

    assert (irrelevant, short, enough) == (False, True, False)
