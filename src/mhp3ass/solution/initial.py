"""A combination's starting totals, and the helpers decoration filling shares.

Ported from ``Detrimental``, ``AddAbilities``, ``AddDecoration``,
``AddInitialArmor`` and ``GetInitialData`` (``legacy/Solution.cpp:18-46``,
``:208-269``).
"""

from __future__ import annotations

from mhp3ass.data.text import as_unsigned
from mhp3ass.model import Ability, AbilityPair, Armor, Decoration
from mhp3ass.solution.state import CalculationData, LegacyNullReferenceError, Solution


def _add_new[K](mapping: dict[K, int], key: K, value: int) -> None:
    """.NET ``Dictionary::Add``: a key already present throws ``ArgumentException``."""
    if key in mapping:
        raise KeyError(f"{key!r} is already present")
    mapping[key] = value


def detrimental(decoration: Decoration, data: CalculationData) -> bool:
    """``Detrimental`` (Solution.cpp:18-26): whether the decoration's second skill,
    when its ability is relevant, would leave that ability short of what it needs.

    Plain indexing raises ``KeyError`` where the original's ``Dictionary``
    indexer throws: a relevant ability is always in ``need`` and ``abilities``.
    """
    if len(decoration.abilities) < 2 or not decoration.abilities[1].ability.relevant:
        return False
    second = decoration.abilities[1]
    need = data.need[second.ability]
    have = data.solution.abilities[second.ability]
    harmful = have + second.amount < need
    return harmful


def add_abilities(total: dict[Ability, int], pairs: list[AbilityPair], multiplier: int) -> None:
    """``AddAbilities`` (Solution.cpp:28-37): add ``amount * multiplier`` per pair,
    inserting abilities not seen yet at the end of ``total``."""
    for pair in pairs:
        if pair.ability in total:
            total[pair.ability] += pair.amount * multiplier
        else:
            total[pair.ability] = pair.amount * multiplier


def add_decoration(
    solution: Solution, decoration: Decoration, multiplier: int, decoration_list: list[Decoration]
) -> bool:
    """``AddDecoration`` (Solution.cpp:39-46).

    Adds the decoration to ``solution.decorations`` and ``decoration_list``
    (the body or non-body list), adds its skills times ``multiplier`` and
    spends its slots. Returns whether its first ability is now above -10.
    """
    solution.decorations.append(decoration)
    decoration_list.append(decoration)
    add_abilities(solution.abilities, decoration.abilities, multiplier)
    solution.total_slots_spare = as_unsigned(solution.total_slots_spare - decoration.slots_required)
    above = solution.abilities[decoration.abilities[0].ability] > -10
    return above


def add_initial_armor(armor: Armor | None, solution: Solution, multiplier: int) -> None:
    """``AddInitialArmor`` (Solution.cpp:208-226).

    Adds one piece's stats, skills (times ``multiplier``) and slots. The body
    (``armors[1]``) adds no slot group to ``slots_spare``: its slots are
    counted in ``torso_slots_spare`` instead.
    """
    if armor is None:
        return
    slots_spare = solution.slots_spare
    if slots_spare is None:
        raise LegacyNullReferenceError("slots_spare is allocated by get_initial_data first")
    adds_group = armor is not solution.armors[1] and armor.num_slots != 0
    slots_spare[armor.num_slots] = as_unsigned(slots_spare[armor.num_slots] + adds_group)
    solution.defence = as_unsigned(solution.defence + armor.defence)
    solution.max_defence = as_unsigned(solution.max_defence + armor.max_defence)
    solution.ice_res += armor.ice_res
    solution.fire_res += armor.fire_res
    solution.water_res += armor.water_res
    solution.dragon_res += armor.dragon_res
    solution.thunder_res += armor.thunder_res
    solution.rarity = as_unsigned(solution.rarity + armor.rarity)
    solution.difficulty = as_unsigned(solution.difficulty + armor.difficulty)
    add_abilities(solution.abilities, armor.abilities, multiplier)
    solution.torso_multiplier = as_unsigned(solution.torso_multiplier + armor.torso_inc)
    solution.total_slots_spare = as_unsigned(solution.total_slots_spare + armor.num_slots)


def get_initial_data(data: CalculationData) -> None:
    """``GetInitialData`` (Solution.cpp:228-269).

    Seeds ``need``, ``relevant`` and ``abilities`` from the query's skills
    (charm abilities join ``need`` at 0), then adds the weapon slots, the
    torso slots, the armour (head, arms, waist, legs, then the body times the
    torso multiplier those four set) and the charm. The insertion order this
    gives ``abilities`` is the order extra skills come out in.
    """
    solution = data.solution
    query = data.query
    for skill in query.skills:
        _add_new(data.need, skill.ability, skill.points_required)
        _add_new(data.relevant, skill, 0)
        _add_new(solution.abilities, skill.ability, 0)
    if solution.charm is not None:
        for pair in solution.charm.abilities:
            if pair.ability not in data.need:
                data.need[pair.ability] = 0

    solution.total_slots_spare = as_unsigned(query.weapon_slots_allowed)
    solution.torso_multiplier = 1
    slots_spare = [0, 0, 0, 0]
    solution.slots_spare = slots_spare
    weapon_group = query.weapon_slots_allowed != 0
    slots_spare[query.weapon_slots_allowed] = as_unsigned(
        slots_spare[query.weapon_slots_allowed] + weapon_group
    )

    body = solution.armors[1]
    solution.torso_slots_spare = body.num_slots if body is not None else 0

    solution.defence = solution.max_defence = 0
    solution.fire_res = solution.ice_res = solution.water_res = 0
    solution.thunder_res = solution.dragon_res = 0
    solution.rarity = solution.difficulty = 0

    add_initial_armor(solution.armors[0], solution, multiplier=1)
    add_initial_armor(solution.armors[2], solution, multiplier=1)
    add_initial_armor(solution.armors[3], solution, multiplier=1)
    add_initial_armor(solution.armors[4], solution, multiplier=1)
    add_initial_armor(solution.armors[1], solution, multiplier=solution.torso_multiplier)
    if solution.charm is not None:
        charm = solution.charm
        charm_group = charm.num_slots != 0
        slots_spare[charm.num_slots] = as_unsigned(slots_spare[charm.num_slots] + charm_group)
        solution.total_slots_spare = as_unsigned(solution.total_slots_spare + charm.num_slots)
        add_abilities(solution.abilities, charm.abilities, multiplier=1)
