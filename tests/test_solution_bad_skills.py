"""Extra skills and the bad-skill repairs (Solution.cpp:48-206, :726-740)."""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from mhp3ass.data import GameData
from mhp3ass.decorations import NoDecorationsError
from mhp3ass.model import Ability, Skill
from mhp3ass.query import QuerySpec
from mhp3ass.relevance import formulate_query
from mhp3ass.solution.bad_skills import (
    OneSlotGems,
    best_available_decoration,
    check_bad_skills,
    count_1_socket_gems,
    fix_bad_skill,
    get_replacable,
    reorder_gems,
    replace,
)
from mhp3ass.solution.extra_skills import calculate_extra_skills
from mhp3ass.solution.state import LegacyNullReferenceError, Solution, new_calculation_data
from solution_builders import make_jewel

# The bad-skill stages are checked against every trace with the rest of
# MatchesQuery's stages, in test_matches_query.py.


@dataclass(frozen=True)
class UpAndDown:
    """An ability's skills at +10 and -10."""

    up: Skill
    down: Skill


@pytest.fixture
def skilled(attack, defense):
    """Attack and Defense with an up skill at +10 and a down skill at -10, by name."""
    skills = {}
    for ability in (attack, defense):
        up = Skill(name=f"{ability.name} Up", points_required=10, ability=ability)
        down = Skill(name=f"{ability.name} Down", points_required=-10, ability=ability)
        ability.skills = {10: up, -10: down}
        skills[ability.name] = UpAndDown(up=up, down=down)
    return skills


@pytest.fixture
def make_fixable(make_data, skilled, attack, defense):
    """A combination left with Defense Down: Defense at ``defense_points``, the
    given free slots and torso slots, and Attack Up asked for."""

    def make(rel_decorations, defense_points, slots_spare, torso_slots_spare=0, **query_fields):
        data = make_data(
            rel_decorations,
            need={attack: 10},
            abilities={attack: 10, defense: defense_points},
            **query_fields,
        )
        solution = data.solution
        solution.slots_spare = list(slots_spare)
        solution.torso_slots_spare = torso_slots_spare
        solution.torso_multiplier = 1
        solution.total_slots_spare = (
            sum(size * count for size, count in enumerate(slots_spare)) + torso_slots_spare
        )
        data.relevant = {skilled["Attack"].up: 0}
        solution.bad_skills = [skilled["Defense"].down]
        return data

    return make


def test_negative_unasked_skills_are_bad_without_allow_bad(make_fixable, skilled):
    data = make_fixable([], defense_points=-11, slots_spare=[0, 0, 0, 0])

    calculate_extra_skills(data)

    assert (data.solution.bad_skills, data.solution.extra_skills) == ([skilled["Defense"].down], [])


def test_negative_unasked_skills_are_extras_with_allow_bad(make_fixable, skilled):
    data = make_fixable([], defense_points=-11, slots_spare=[0, 0, 0, 0], allow_bad=True)

    calculate_extra_skills(data)

    assert (data.solution.bad_skills, data.solution.extra_skills) == ([], [skilled["Defense"].down])


def test_query_skills_are_neither_extra_nor_bad(make_fixable):
    data = make_fixable([], defense_points=0, slots_spare=[0, 0, 0, 0])

    calculate_extra_skills(data)

    assert (data.solution.bad_skills, data.solution.extra_skills) == ([], [])


def test_fix_bad_skill_fills_the_torso_first_with_its_multiplier(make_fixable, defense, skilled):
    defense.relevant = True
    jewel = make_jewel("Defense[1]", defense, 2)
    data = make_fixable([jewel], defense_points=-12, slots_spare=[0, 1, 0, 0], torso_slots_spare=1)
    data.solution.torso_multiplier = 2

    fixed = fix_bad_skill(data, GameData(), skilled["Defense"].down)

    solution = data.solution
    assert fixed
    assert (solution.body_decorations, solution.non_body_decorations) == ([jewel], [])
    assert (solution.abilities[defense], solution.torso_slots_spare) == (-8, 0)


def test_fix_bad_skill_splits_a_bigger_group_when_its_size_has_none(make_fixable, defense, skilled):
    # A 1-slot jewel with no 1-slot group takes a 2-slot one, leaving a 1 (Solution.cpp:85-89).
    defense.relevant = True
    jewel = make_jewel("Defense[1]", defense, 3)
    data = make_fixable([jewel], defense_points=-12, slots_spare=[0, 0, 1, 0])

    fixed = fix_bad_skill(data, GameData(), skilled["Defense"].down)

    assert fixed
    assert data.solution.slots_spare == [0, 1, 0, 0]


def test_fix_bad_skill_dereferences_a_failed_repick(make_fixable, defense, skilled):
    """Solution.cpp:96-97 re-picks for a smaller group without a null check; :78
    then dereferences it. Only a 2-slot Defense jewel exists, and 1-slot groups remain."""
    defense.relevant = True
    jewel = make_jewel("Defense[2]", defense, 1, slots=2)
    data = make_fixable([jewel], defense_points=-20, slots_spare=[0, 1, 1, 0])

    with pytest.raises(LegacyNullReferenceError):
        fix_bad_skill(data, GameData(), skilled["Defense"].down)


def test_fix_bad_skill_does_not_recheck_detrimental_after_a_repick(
    make_fixable, attack, defense, skilled
):
    """Quirk candidate I: the first pick is checked (:73), the re-pick (:97) isn't."""
    defense.relevant = True
    attack.relevant = True
    big = make_jewel("Defense[2]", defense, 1, slots=2)
    small = make_jewel("Defense[1]", defense, 1, second=attack, second_amount=-5)
    data = make_fixable([small, big], defense_points=-11, slots_spare=[0, 1, 1, 0])
    data.solution.abilities[attack] = 10

    fixed = fix_bad_skill(data, GameData(), skilled["Defense"].down)

    # The small jewel takes Attack below its need of 10: Detrimental, yet added.
    assert fixed
    assert data.solution.non_body_decorations == [big, small]
    assert data.solution.abilities[attack] == 5


def test_fix_bad_skill_rejects_a_detrimental_first_pick(make_fixable, attack, defense, skilled):
    defense.relevant = True
    attack.relevant = True
    small = make_jewel("Defense[1]", defense, 1, second=attack, second_amount=-5)
    data = make_fixable([small], defense_points=-11, slots_spare=[0, 1, 0, 0])

    fixed = fix_bad_skill(data, GameData(), skilled["Defense"].down)

    assert not fixed
    assert data.solution.decorations == []


def test_irrelevant_ability_without_decorations_raises_quirk_8(make_fixable, skilled):
    """An irrelevant ability goes to the query overload, whose unchecked map lookup
    throws for an ability no decoration has (quirk 8)."""
    data = make_fixable([], defense_points=-12, slots_spare=[0, 0, 0, 0], torso_slots_spare=1)

    with pytest.raises(NoDecorationsError):
        fix_bad_skill(data, GameData(), skilled["Defense"].down)


def test_fixing_ignores_allow_event_for_irrelevant_abilities(make_fixable, defense):
    """Quirk candidate J: the query overload has no is_event test (Decoration.cpp:112)."""
    event_jewel = make_jewel("Defense[1]", defense, 2)
    event_jewel.is_event = True
    game = GameData()
    game.decorations_by_ability = {defense: [event_jewel]}
    data = make_fixable([], defense_points=-12, slots_spare=[0, 1, 0, 0], allow_event=False)

    picked = best_available_decoration(data, game, defense, 1)

    assert picked is event_jewel


def test_fix_bad_skills_accepts_a_new_bad_skill_its_fix_creates(
    make_fixable, attack, defense, skilled
):
    """Quirk candidate K: FixBadSkills recomputes the bad skills but returns true
    (Solution.cpp:108-109), so a fix's own second skill can leave a new one."""
    fix = make_jewel("Defense[1]", defense, 3, second=attack, second_amount=-25)
    game = GameData()
    game.decorations_by_ability = {defense: [fix]}
    data = make_fixable([], defense_points=-12, slots_spare=[0, 1, 0, 0])
    data.relevant = {}

    fine = check_bad_skills(data, game)

    assert fine
    assert data.solution.bad_skills == [skilled["Attack"].down]


def test_check_bad_skills_without_free_slots_goes_straight_to_reordering(make_fixable, defense):
    # No free slots: FixBadSkills isn't called, ReorderGems finds no 1-slot gems.
    data = make_fixable([], defense_points=-12, slots_spare=[0, 0, 0, 0])

    fine = check_bad_skills(data, GameData())

    assert not fine
    assert data.solution.decorations == []


def test_count_1_socket_gems_keeps_the_first_to_reach_the_top_count(attack, defense):
    a = make_jewel("A", attack, 1, second=defense, second_amount=-1)
    b = make_jewel("B", attack, 1, second=defense, second_amount=-1)
    solution = Solution(armors=[None] * 5, charm=None, decorations=[a, b, b, a])

    gems = count_1_socket_gems(solution, defense)

    # A and B both end on 2; B got there first.
    assert gems == OneSlotGems(decoration=b, count=2)


def test_count_1_socket_gems_single_uses_keep_the_first(attack, defense):
    a = make_jewel("A", attack, 1, second=defense, second_amount=-1)
    b = make_jewel("B", attack, 1, second=defense, second_amount=-1)
    solution = Solution(armors=[None] * 5, charm=None, decorations=[a, b])

    gems = count_1_socket_gems(solution, defense)

    assert gems == OneSlotGems(decoration=a, count=1)


def test_get_replacable_skips_gems_of_the_bad_skill(attack, defense):
    bad = make_jewel("Bad[3]", attack, 5, slots=3, second=defense, second_amount=-1)
    other = make_jewel("Other[3]", defense, 4, slots=3, second=attack, second_amount=-2)
    solution = Solution(armors=[None] * 5, charm=None, decorations=[bad, other])

    found = (get_replacable(solution, defense, 3), get_replacable(solution, defense, 2))

    assert found == (1, -1)


def test_replace_indexes_abilities_plainly(attack, defense):
    """Solution.cpp:197 subtracts with the Dictionary indexer, which throws for a
    missing key; the port's plain indexing raises KeyError there too."""
    old = make_jewel("Old", attack, 1, second=defense, second_amount=-1)
    solution = Solution(armors=[None] * 5, charm=None, decorations=[old])
    solution.abilities = {attack: 1}

    with pytest.raises(KeyError):
        replace(solution, 0, make_jewel("New", attack, 2))


def test_replace_ignores_the_torso_multiplier_and_the_body_list(attack, defense):
    """Quirk candidate L: raw amounts, and body_decorations keeps the old gem."""
    old = make_jewel("Old", attack, 1, second=defense, second_amount=-1)
    new = make_jewel("New", defense, 2)
    solution = Solution(armors=[None] * 5, charm=None, decorations=[old], body_decorations=[old])
    solution.torso_multiplier = 2
    solution.abilities = {attack: 2, defense: -2}

    replace(solution, 0, new)

    assert solution.abilities == {attack: 1, defense: 1}
    assert (solution.decorations, solution.body_decorations) == ([new], [old])


@pytest.fixture
def attack_sharp_data(scratch_game, attack_sharp_query_json):
    """CalculationData for the Attack Up [Med] + Sharp Sword query on shipped data,
    with no armour and no decorations yet."""
    query = formulate_query(scratch_game, QuerySpec.from_json(attack_sharp_query_json))
    data = new_calculation_data(Solution(armors=[None] * 5, charm=None), query)
    return data


def test_reorder_gems_swaps_one_slot_gems_for_a_bigger_one(attack_sharp_data, scratch_game):
    """ReorderGems' success path, which no traced query reaches: six Attack
    Jewel[1] (Defense -1 each) and a Razor Jewel[3] leave Defense Down. The
    Razor Jewel[3] becomes an Attack Jewel[3], and five Attack Jewel[1] become
    the first Sharpness decoration in file order, a Razor Jewel[1] (quirk M)."""
    game = scratch_game
    data = attack_sharp_data
    attack_1 = game.decoration_map["Attack Jewel[1]"]
    attack_3 = game.decoration_map["Attack Jewel[3]"]
    razor_1 = game.decoration_map["Razor Jewel[1]"]
    razor_3 = game.decoration_map["Razor Jewel[3]"]
    attack, defense = game.ability_map["Attack"], game.ability_map["Defense"]
    sharpness, artisan = game.ability_map["Sharpness"], game.ability_map["Artisan"]
    solution = data.solution
    solution.decorations = [attack_1] * 6 + [razor_3]
    solution.abilities = {attack: 6, sharpness: 4, defense: -12, artisan: -2}
    solution.bad_skills = [game.skill_map["Def Down (S)"]]
    data.relevant = {skill: 0 for skill in data.query.skills}

    reordered = reorder_gems(data, game)

    assert reordered
    assert game.decorations_by_ability[sharpness][0] is razor_1
    assert solution.decorations == [razor_1] * 5 + [attack_1, attack_3]
    assert solution.abilities == {attack: 6, sharpness: 5, defense: -8, artisan: -5}
    assert solution.bad_skills == []


def test_check_bad_skills_fixes_only_with_free_slots_counted(make_fixable, defense):
    """Solution.cpp:114 tries FixBadSkills only when total_slots_spare > 0: with the
    counter at 0, a free group in slots_spare isn't used."""
    defense.relevant = True
    jewel = make_jewel("Defense[1]", defense, 5)
    data = make_fixable([jewel], defense_points=-12, slots_spare=[0, 1, 0, 0])
    data.solution.total_slots_spare = 0

    fine = check_bad_skills(data, GameData())

    assert not fine
    assert data.solution.decorations == []


def test_reorder_gems_counts_replacements_after_the_swap(make_data, skilled, attack, defense):
    """Solution.cpp:179 reads decorations[ other ] after Replace put the bigger gem
    there, so the other gem's own amount (here 6, more than the bigger gem's 5)
    never sets how many 1-slot gems are swapped: five of six are."""
    sharpness = Ability(name="Sharpness", static_index=2)
    artisan = Ability(name="Artisan", static_index=3)
    attack.relevant = True
    one_slot = make_jewel("Attack[1]", attack, 1, second=defense, second_amount=-1)
    bigger = make_jewel("Attack[3]", attack, 5, slots=3, second=defense, second_amount=-1)
    other = make_jewel("Sharp[3]", sharpness, 6, slots=3, second=artisan, second_amount=-2)
    sharp_one_slot = make_jewel("Sharp[1]", sharpness, 1, second=artisan, second_amount=-1)
    game = GameData()
    game.decorations_by_ability = {sharpness: [sharp_one_slot, other]}
    data = make_data(
        [one_slot, bigger],
        need={attack: 10},
        abilities={attack: 6, sharpness: 6, defense: -12, artisan: -2},
    )
    data.solution.decorations = [one_slot] * 6 + [other]
    data.solution.bad_skills = [skilled["Defense"].down]

    reordered = reorder_gems(data, game)

    assert reordered
    assert data.solution.decorations == [sharp_one_slot] * 5 + [one_slot, bigger]


def test_count_1_socket_gems_without_a_match_is_none(attack, defense):
    gem = make_jewel("A", attack, 1, second=attack, second_amount=-1)
    solution = Solution(armors=[None] * 5, charm=None, decorations=[gem])

    assert count_1_socket_gems(solution, defense) is None


def test_fix_bad_skill_gives_up_when_the_torso_has_no_decoration(make_fixable, defense, skilled):
    """Solution.cpp:60-61: torso slots free, but no decoration of the ability fits."""
    defense.relevant = True
    data = make_fixable([], defense_points=-12, slots_spare=[0, 1, 0, 0], torso_slots_spare=1)

    fixed = fix_bad_skill(data, GameData(), skilled["Defense"].down)

    assert not fixed
    assert data.solution.decorations == []


def test_replace_adds_an_ability_the_totals_lack(attack, defense):
    """Solution.cpp:202-204: the new decoration's abilities are added when missing."""
    old = make_jewel("Old", attack, 1)
    new = make_jewel("New", attack, 1, second=defense, second_amount=-1)
    solution = Solution(armors=[None] * 5, charm=None)
    solution.decorations = [old]
    solution.abilities = {attack: 1}

    replace(solution, 0, new)

    assert solution.abilities == {attack: 1, defense: -1}


def _reorder_setup(data, game, defense_points: int, artisan_points: int):
    """Six Attack Jewel[1] and a Razor Jewel[3], leaving Defense Down."""
    attack_1 = game.decoration_map["Attack Jewel[1]"]
    razor_3 = game.decoration_map["Razor Jewel[3]"]
    abilities = game.ability_map
    solution = data.solution
    solution.decorations = [attack_1] * 6 + [razor_3]
    solution.abilities = {
        abilities["Attack"]: 6,
        abilities["Sharpness"]: 4,
        abilities["Defense"]: defense_points,
        abilities["Artisan"]: artisan_points,
    }
    solution.bad_skills = [game.skill_map["Def Down (S)"]]
    data.relevant = {skill: 0 for skill in data.query.skills}


def test_reorder_gems_gives_up_when_the_other_gems_second_skill_is_low(
    attack_sharp_data, scratch_game
):
    """Solution.cpp:174: the bigger gem to swap out mustn't have its second
    ability at -8 or below; here Artisan is at -9."""
    _reorder_setup(attack_sharp_data, scratch_game, defense_points=-12, artisan_points=-9)
    before = list(attack_sharp_data.solution.decorations)

    reordered = reorder_gems(attack_sharp_data, scratch_game)

    assert not reordered
    assert attack_sharp_data.solution.decorations == before


def test_reorder_gems_gives_up_when_the_swap_leaves_the_skill_bad(attack_sharp_data, scratch_game):
    """Solution.cpp:183-184: the swaps are kept, but Defense ends at -16, still bad."""
    _reorder_setup(attack_sharp_data, scratch_game, defense_points=-20, artisan_points=-2)
    defense = scratch_game.ability_map["Defense"]

    reordered = reorder_gems(attack_sharp_data, scratch_game)

    assert not reordered
    assert attack_sharp_data.solution.abilities[defense] == -16


def test_reorder_gems_skips_a_bad_skill_no_longer_at_minus_10(attack_sharp_data, scratch_game):
    """Solution.cpp:162 only reorders for a skill still at -10 or below. Bad
    skills come from points at -10 or below, so only a stale list reaches
    this: then nothing is swapped and the skills are recomputed."""
    _reorder_setup(attack_sharp_data, scratch_game, defense_points=-5, artisan_points=-2)
    before = list(attack_sharp_data.solution.decorations)

    reordered = reorder_gems(attack_sharp_data, scratch_game)

    assert reordered
    assert [attack_sharp_data.solution.decorations, attack_sharp_data.solution.bad_skills] == [
        before,
        [],
    ]
