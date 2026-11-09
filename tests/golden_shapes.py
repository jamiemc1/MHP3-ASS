"""Python game data in the harness's golden fixture layout.

Mirrors ``harness/src/DataDump.cpp``, ``Fixtures.h`` and ``RelevanceDump.cpp``
so port output can be compared with ``tests/golden/`` section by section.
"""

from __future__ import annotations

from typing import Any

from mhp3ass.charms.naming import charm_name
from mhp3ass.data import GameData
from mhp3ass.model import (
    Ability,
    AbilityPair,
    Armor,
    ArmorType,
    Charm,
    Decoration,
    Gender,
    HunterType,
    MaterialComponent,
)
from mhp3ass.query import Query


def _gender_name(gender: Gender) -> str:
    names = {Gender.MALE: "male", Gender.FEMALE: "female", Gender.BOTH_GENDERS: "both"}
    return names[gender]


def _hunter_type_name(hunter_type: HunterType) -> str:
    names = {
        HunterType.BLADEMASTER: "blademaster",
        HunterType.GUNNER: "gunner",
        HunterType.BOTH_TYPES: "both",
    }
    return names[hunter_type]


def ability_ref(ability: Ability | None) -> int | None:
    reference = None if ability is None else ability.static_index
    return reference


def _ability_pairs(pairs: list[AbilityPair]) -> list[dict[str, Any]]:
    shaped = [{"ability": ability_ref(pair.ability), "amount": pair.amount} for pair in pairs]
    return shaped


def _components(components: list[MaterialComponent]) -> list[dict[str, Any]]:
    shaped = [
        {"material": component.material.name, "amount": component.amount}
        for component in components
    ]
    return shaped


def game_data_shape(game: GameData) -> dict[str, Any]:
    """The layout of ``game-data.json.gz`` (``DataDump::WriteGameData``)."""
    skill_positions = {id(skill): position for position, skill in enumerate(game.skills)}
    shape = {
        "abilities": [
            {
                "static_index": ability.static_index,
                "name": ability.name,
                "order": ability.order,
                "auto_guard": ability.auto_guard,
                "is_torso_inc": ability is game.torso_inc,
                "tags": [tag.name for tag in ability.tags],
                "skills": [
                    {"points": points, "skill": skill.name}
                    for points, skill in ability.skills.items()
                ],
            }
            for ability in game.abilities
        ],
        "ordered_abilities": [ability_ref(ability) for ability in game.ordered_abilities],
        "skills": [
            {
                "index": index,
                "name": skill.name,
                "points_required": skill.points_required,
                "ability": ability_ref(skill.ability),
            }
            for index, skill in enumerate(game.skills)
        ],
        "ordered_skills": [skill_positions[id(skill)] for skill in game.ordered_skills],
        "armors": {
            armor_type.name.lower(): [
                {
                    "index": armor.index,
                    "name": armor.name,
                    "hr": armor.hr,
                    "elder_star": armor.elder_star,
                    "num_slots": armor.num_slots,
                    "defence": armor.defence,
                    "max_defence": armor.max_defence,
                    "rarity": armor.rarity,
                    "difficulty": armor.difficulty,
                    "fire_res": armor.fire_res,
                    "water_res": armor.water_res,
                    "thunder_res": armor.thunder_res,
                    "ice_res": armor.ice_res,
                    "dragon_res": armor.dragon_res,
                    "gender": _gender_name(armor.gender),
                    "hunter_type": _hunter_type_name(armor.hunter_type),
                    "torso_inc": armor.torso_inc,
                    "no_skills": armor.no_skills,
                    "is_piercing": armor.is_piercing,
                    "is_event": armor.is_event,
                    "danger": ability_ref(armor.danger),
                    "abilities": _ability_pairs(armor.abilities),
                    "components": _components(armor.components),
                }
                for armor in game.armors[armor_type]
            ]
            for armor_type in ArmorType
        },
        "decorations": [
            {
                "index": decoration.index,
                "name": decoration.name,
                "hr": decoration.hr,
                "elder_star": decoration.elder_star,
                "slots_required": decoration.slots_required,
                "rarity": decoration.rarity,
                "difficulty": decoration.difficulty,
                "is_event": decoration.is_event,
                "abilities": _ability_pairs(decoration.abilities),
                "components": _components(decoration.components),
                "components2": _components(decoration.components2),
            }
            for decoration in game.decorations
        ],
        "decorations_by_ability": [
            {
                "ability": ability.static_index,
                "decorations": [decoration.index for decoration in decorations],
            }
            for ability, decorations in game.decorations_by_ability.items()
        ],
        "materials": [
            {
                "name": material.name,
                "event_only": material.event_only,
                "difficulty": material.difficulty,
            }
            for material in game.materials
        ],
        "skill_tags": [tag.name for tag in game.skill_tags],
    }
    return shape


def names_shape(game: GameData) -> dict[str, Any]:
    """The layout of ``names/<language>.json.gz`` (``DataDump::WriteNames``)."""
    shape = {
        "abilities": [ability.name for ability in game.abilities],
        "skills": [skill.name for skill in game.skills],
        "armors": {
            armor_type.name.lower(): [armor.name for armor in game.armors[armor_type]]
            for armor_type in ArmorType
        },
        "decorations": [decoration.name for decoration in game.decorations],
        "materials": [material.name for material in game.materials],
        "skill_tags": [tag.name for tag in game.skill_tags],
    }
    return shape


def charm_shape(charm: Charm) -> dict[str, Any]:
    """``Fixtures::WriteCharmFields`` (Fixtures.h:44-50)."""
    shaped = {
        "name": charm_name(charm),
        "num_slots": charm.num_slots,
        "abilities": _ability_pairs(charm.abilities),
    }
    return shaped


def _armor_entries(armors: list[Armor]) -> list[dict[str, Any]]:
    entries = [
        {"index": armor.index, "no_skills": armor.no_skills, "danger": ability_ref(armor.danger)}
        for armor in armors
    ]
    return entries


def _decoration_indices(decorations: list[Decoration]) -> list[int]:
    indices = [decoration.index for decoration in decorations]
    return indices


def relevance_shape(game: GameData, query: Query) -> dict[str, Any]:
    """``RelevanceDump::Run``'s GetRelevantData sections (RelevanceDump.cpp)."""
    armor = {
        armor_type.name.lower(): {
            "relevant": _armor_entries(query.rel_armor[armor_type.value]),
            "inferior": _armor_entries(query.inf_armor[armor_type.value]),
        }
        for armor_type in ArmorType
    }
    shaped = {
        "rel_abilities": [ability.static_index for ability in query.rel_abilities],
        "relevant_flags": [ability.static_index for ability in game.abilities if ability.relevant],
        "armor": armor,
        "decorations": {
            "relevant": _decoration_indices(query.rel_decorations),
            "inferior": _decoration_indices(query.inf_decorations),
        },
    }
    return shaped
