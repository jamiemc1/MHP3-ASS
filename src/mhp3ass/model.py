"""Game records, mirroring the legacy reference types.

Ported from ``legacy/Skill.h``, ``legacy/Armor.h`` (including ``Charm``),
``legacy/Decoration.h`` and ``legacy/Common.h``. The original's records are .NET reference types:
dictionaries key them by identity and loaders mutate them in place (a
language load renames them). These dataclasses keep that: ``eq=False`` gives
identity equality and hashing, and fields are mutable.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class Gender(Enum):
    """``Gender`` in Common.h; values match the original's."""

    MALE = 4
    FEMALE = 5
    BOTH_GENDERS = 6


class HunterType(Enum):
    """``HunterType`` in Common.h; values match the original's."""

    BLADEMASTER = 1
    GUNNER = 2
    BOTH_TYPES = 3


class ArmorType(Enum):
    """``Armor::ArmorType``: the five armour slots, in search order."""

    HEAD = 0
    BODY = 1
    ARMS = 2
    WAIST = 3
    LEGS = 4


@dataclass(eq=False)
class SkillTag:
    name: str


@dataclass(eq=False)
class Ability:
    """A skill tree: points from armour and decorations accumulate per ability."""

    name: str
    static_index: int
    tags: list[SkillTag] = field(default_factory=list)
    relevant: bool = False
    auto_guard: bool = False
    order: int = 0
    # Points threshold -> skill, in .NET Dictionary insertion order; GetSkill walks it.
    skills: dict[int, Skill] = field(default_factory=dict)


@dataclass(eq=False)
class Skill:
    name: str
    points_required: int
    ability: Ability


@dataclass(eq=False)
class AbilityPair:
    ability: Ability
    amount: int


@dataclass(eq=False)
class Material:
    name: str
    event_only: bool = False
    difficulty: int = 0


@dataclass(eq=False)
class MaterialComponent:
    material: Material
    amount: int


@dataclass(eq=False)
class Armor:
    name: str
    index: int
    gender: Gender
    hunter_type: HunterType
    rarity: int
    num_slots: int
    hr: int
    elder_star: int
    defence: int
    max_defence: int
    fire_res: int
    water_res: int
    ice_res: int
    thunder_res: int
    dragon_res: int
    is_piercing: bool
    is_event: bool = False
    torso_inc: bool = False
    # Set by MatchesQuery during a search, not by loading.
    no_skills: bool = False
    danger: Ability | None = None
    difficulty: int = 0
    abilities: list[AbilityPair] = field(default_factory=list)
    components: list[MaterialComponent] = field(default_factory=list)


@dataclass(eq=False)
class Decoration:
    name: str
    index: int
    rarity: int
    slots_required: int
    hr: int
    elder_star: int
    is_event: bool = False
    difficulty: int = 0
    abilities: list[AbilityPair] = field(default_factory=list)
    components: list[MaterialComponent] = field(default_factory=list)
    # The alternative recipe: it adds neither difficulty nor the event flag.
    components2: list[MaterialComponent] = field(default_factory=list)


@dataclass(eq=False)
class Charm:
    """``Charm`` (Armor.h:32-50).

    Equality is identity; ``charms.naming.charms_equal`` is the original's ``==``.
    """

    num_slots: int = 0
    abilities: list[AbilityPair] = field(default_factory=list)
    # Entered by the user (my charms) rather than generated.
    custom: bool = False
    hacked: bool = False

    def copy(self) -> Charm:
        """``Charm( Charm^ other )`` (Armor.cpp:231-237): new pairs; ``hacked`` is reset."""
        copied = Charm(
            num_slots=self.num_slots,
            abilities=[
                AbilityPair(ability=pair.ability, amount=pair.amount) for pair in self.abilities
            ],
            custom=self.custom,
            hacked=False,
        )
        return copied
