"""A ``Solution`` as plain indices, to pass between processes and rebuild against a game.

Not a port of an original module: the original searches in threads that share
one ``LoadedData``. Every field of ``Solution`` (``legacy/Solution.h:39-71``)
is kept, with game records replaced by their position in the game's tables,
so rebuilding a record against the same game gives back the same records,
the same ``abilities`` order and the same charm.
"""

from __future__ import annotations

from dataclasses import dataclass

from mhp3ass.data import GameData
from mhp3ass.model import Ability, AbilityPair, Armor, ArmorType, Charm, Decoration, Skill
from mhp3ass.solution.state import Solution


@dataclass(frozen=True, slots=True)
class CharmRecord:
    """A ``Charm``: its pairs as ``(ability static index, amount)`` in order."""

    num_slots: int
    abilities: tuple[tuple[int, int], ...]
    custom: bool
    hacked: bool


@dataclass(frozen=True, slots=True)
class SolutionRecord:
    """A ``Solution`` by index: armour per slot (-1 for empty), decorations,
    skills and abilities by their position in the game's tables."""

    armors: tuple[int, ...]
    charm: CharmRecord | None
    decorations: tuple[int, ...]
    body_decorations: tuple[int, ...]
    non_body_decorations: tuple[int, ...]
    extra_skills: tuple[int, ...]
    bad_skills: tuple[int, ...]
    abilities: tuple[tuple[int, int], ...]
    torso_slots_spare: int
    torso_multiplier: int
    total_slots_spare: int
    fire_res: int
    ice_res: int
    water_res: int
    thunder_res: int
    dragon_res: int
    defence: int
    max_defence: int
    rarity: int
    difficulty: int
    slots_spare: tuple[int, ...] | None


@dataclass(frozen=True, eq=False)
class RecordIndex:
    """A game and the position of each of its skills, which ``Skill`` doesn't carry."""

    game: GameData
    skill_positions: dict[Skill, int]

    @classmethod
    def for_game(cls, game: GameData) -> RecordIndex:
        index = cls(
            game=game,
            skill_positions={skill: position for position, skill in enumerate(game.skills)},
        )
        return index


def _armor_index(armor: Armor | None, armor_type: ArmorType, game: GameData) -> int:
    if armor is None:
        return -1
    pieces = game.armors[armor_type]
    if not 0 <= armor.index < len(pieces) or pieces[armor.index] is not armor:
        raise ValueError(f"{armor.name} is not {armor_type.name} armour {armor.index} of this game")
    return armor.index


def _decoration_indices(decorations: list[Decoration], game: GameData) -> tuple[int, ...]:
    indices = []
    for decoration in decorations:
        index = decoration.index
        if not 0 <= index < len(game.decorations) or game.decorations[index] is not decoration:
            raise ValueError(f"{decoration.name} is not decoration {index} of this game")
        indices.append(index)
    return tuple(indices)


def _ability_index(ability: Ability, game: GameData) -> int:
    index = ability.static_index
    if not 0 <= index < len(game.abilities) or game.abilities[index] is not ability:
        raise ValueError(f"{ability.name} is not ability {index} of this game")
    return index


def _skill_indices(skills: list[Skill], index: RecordIndex) -> tuple[int, ...]:
    positions = []
    for skill in skills:
        position = index.skill_positions.get(skill)
        if position is None:
            raise ValueError(f"{skill.name} is not a skill of this game")
        positions.append(position)
    return tuple(positions)


def _charm_record(charm: Charm | None, game: GameData) -> CharmRecord | None:
    if charm is None:
        return None
    record = CharmRecord(
        num_slots=charm.num_slots,
        abilities=tuple(
            (_ability_index(pair.ability, game), pair.amount) for pair in charm.abilities
        ),
        custom=charm.custom,
        hacked=charm.hacked,
    )
    return record


def to_record(solution: Solution, index: RecordIndex) -> SolutionRecord:
    """``solution`` by index into ``index.game``; raises ``ValueError`` on a record
    that isn't that game's, or on a number of armour slots other than five."""
    game = index.game
    record = SolutionRecord(
        armors=tuple(
            _armor_index(armor, armor_type, game)
            for armor, armor_type in zip(solution.armors, ArmorType, strict=True)
        ),
        charm=_charm_record(solution.charm, game),
        decorations=_decoration_indices(solution.decorations, game),
        body_decorations=_decoration_indices(solution.body_decorations, game),
        non_body_decorations=_decoration_indices(solution.non_body_decorations, game),
        extra_skills=_skill_indices(solution.extra_skills, index),
        bad_skills=_skill_indices(solution.bad_skills, index),
        abilities=tuple(
            (_ability_index(ability, game), points)
            for ability, points in solution.abilities.items()
        ),
        torso_slots_spare=solution.torso_slots_spare,
        torso_multiplier=solution.torso_multiplier,
        total_slots_spare=solution.total_slots_spare,
        fire_res=solution.fire_res,
        ice_res=solution.ice_res,
        water_res=solution.water_res,
        thunder_res=solution.thunder_res,
        dragon_res=solution.dragon_res,
        defence=solution.defence,
        max_defence=solution.max_defence,
        rarity=solution.rarity,
        difficulty=solution.difficulty,
        slots_spare=tuple(solution.slots_spare) if solution.slots_spare is not None else None,
    )
    return record


def _entry[T](table: list[T], position: int, what: str) -> T:
    """``table[position]``, raising on a position outside it (Python would wrap a negative one)."""
    if not 0 <= position < len(table):
        raise ValueError(f"{what} {position} is not in this game (0-{len(table) - 1})")
    return table[position]


def _charm(record: CharmRecord | None, game: GameData) -> Charm | None:
    if record is None:
        return None
    charm = Charm(
        num_slots=record.num_slots,
        abilities=[
            AbilityPair(ability=_entry(game.abilities, position, "ability"), amount=amount)
            for position, amount in record.abilities
        ],
        custom=record.custom,
        hacked=record.hacked,
    )
    return charm


def _abilities(pairs: tuple[tuple[int, int], ...], game: GameData) -> dict[Ability, int]:
    """The ability totals in record order; a position given twice raises."""
    abilities: dict[Ability, int] = {}
    for position, points in pairs:
        ability = _entry(game.abilities, position, "ability")
        if ability in abilities:
            raise ValueError(f"ability {position} appears twice in the record")
        abilities[ability] = points
    return abilities


def from_record(record: SolutionRecord, game: GameData) -> Solution:
    """The ``Solution`` ``record`` describes, built from ``game``'s records; raises
    ``ValueError`` on an index outside the game's tables, an ability given twice
    or a number of armour slots other than five."""
    armors: list[Armor | None] = [
        None
        if position == -1
        else _entry(game.armors[armor_type], position, f"{armor_type.name} armour")
        for position, armor_type in zip(record.armors, ArmorType, strict=True)
    ]
    solution = Solution(
        armors=armors,
        charm=_charm(record.charm, game),
        decorations=[
            _entry(game.decorations, position, "decoration") for position in record.decorations
        ],
        body_decorations=[
            _entry(game.decorations, position, "decoration") for position in record.body_decorations
        ],
        non_body_decorations=[
            _entry(game.decorations, position, "decoration")
            for position in record.non_body_decorations
        ],
        extra_skills=[_entry(game.skills, position, "skill") for position in record.extra_skills],
        bad_skills=[_entry(game.skills, position, "skill") for position in record.bad_skills],
        abilities=_abilities(record.abilities, game),
        torso_slots_spare=record.torso_slots_spare,
        torso_multiplier=record.torso_multiplier,
        total_slots_spare=record.total_slots_spare,
        fire_res=record.fire_res,
        ice_res=record.ice_res,
        water_res=record.water_res,
        thunder_res=record.thunder_res,
        dragon_res=record.dragon_res,
        defence=record.defence,
        max_defence=record.max_defence,
        rarity=record.rarity,
        difficulty=record.difficulty,
        slots_spare=list(record.slots_spare) if record.slots_spare is not None else None,
    )
    return solution
