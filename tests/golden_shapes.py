"""Python game data in the harness's golden fixture layout.

Mirrors ``harness/src/DataDump.cpp`` so loaded data can be compared with
``tests/golden/data/`` table by table.
"""

from __future__ import annotations

from typing import Any

from mhp3ass.data import GameData
from mhp3ass.model import Ability, AbilityPair, ArmorType, Gender, HunterType, MaterialComponent


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


def _ability_ref(ability: Ability | None) -> int | None:
    reference = None if ability is None else ability.static_index
    return reference


def _ability_pairs(pairs: list[AbilityPair]) -> list[dict[str, Any]]:
    shaped = [{"ability": _ability_ref(pair.ability), "amount": pair.amount} for pair in pairs]
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
        "ordered_abilities": [_ability_ref(ability) for ability in game.ordered_abilities],
        "skills": [
            {
                "index": index,
                "name": skill.name,
                "points_required": skill.points_required,
                "ability": _ability_ref(skill.ability),
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
                    "danger": _ability_ref(armor.danger),
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
