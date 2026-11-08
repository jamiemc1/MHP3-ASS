"""Load the game data files, as the legacy loaders do.

Ported from ``LoadedData::ImportTextFiles`` (``legacy/LoadedData.cpp``),
``Skill::Load`` (``legacy/Skill.cpp``), ``Armor::Load`` (``legacy/Armor.cpp``),
``Decoration::Load`` (``legacy/Decoration.cpp``), ``Material::LoadMaterials``
(``legacy/Common.cpp``) and ``SkillTag::Load`` (``legacy/LoadedData.cpp``),
plus each ``LoadLanguage`` counterpart.

Where the original's ``Assert`` would fire (a no-op in its Release build) or
it would crash on malformed data, these loaders raise instead. On the
shipped data both behave the same.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path

from mhp3ass.data.text import as_unsigned, read_lines, split_fields, to_int32, to_uint32
from mhp3ass.model import (
    Ability,
    AbilityPair,
    Armor,
    ArmorType,
    Decoration,
    Gender,
    HunterType,
    Material,
    MaterialComponent,
    Skill,
    SkillTag,
)


@dataclass
class GameData:
    """The original's static tables, in the order it loads them."""

    skill_tags: list[SkillTag] = field(default_factory=list)
    materials: list[Material] = field(default_factory=list)
    material_map: dict[str, Material] = field(default_factory=dict)
    abilities: list[Ability] = field(default_factory=list)
    ability_map: dict[str, Ability] = field(default_factory=dict)
    ordered_abilities: list[Ability] = field(default_factory=list)
    torso_inc: Ability | None = None
    skills: list[Skill] = field(default_factory=list)
    skill_map: dict[str, Skill] = field(default_factory=dict)
    ordered_skills: list[Skill] = field(default_factory=list)
    armors: dict[ArmorType, list[Armor]] = field(default_factory=dict)
    armor_map: dict[str, Armor] = field(default_factory=dict)
    decorations: list[Decoration] = field(default_factory=list)
    decoration_map: dict[str, Decoration] = field(default_factory=dict)
    # Keyed by each decoration's first ability, in .NET Dictionary insertion order.
    decorations_by_ability: dict[Ability, list[Decoration]] = field(default_factory=dict)


# The armour file for each slot, in the order the original loads and translates them.
_ARMOR_FILES = {
    ArmorType.HEAD: "head.txt",
    ArmorType.BODY: "body.txt",
    ArmorType.ARMS: "arms.txt",
    ArmorType.WAIST: "waist.txt",
    ArmorType.LEGS: "legs.txt",
}


def load_game_data(data_dir: Path) -> GameData:
    """``LoadedData::ImportTextFiles`` (LoadedData.cpp:26-42)."""
    game = GameData(armors={armor_type: [] for armor_type in ArmorType})
    load_materials(game, data_dir / "components.txt")
    load_skill_tags(game, data_dir / "tags.txt")
    load_skills(game, data_dir / "skills.txt")
    for armor_type, file_name in _ARMOR_FILES.items():
        load_armors(game=game, path=data_dir / file_name, armor_type=armor_type)
    load_decorations(game, data_dir / "decorations.txt")
    return game


def load_materials(game: GameData, path: Path) -> None:
    """``Material::LoadMaterials`` (Common.cpp:232-266).

    Blank lines are skipped; ``#`` lines are materials, not comments.
    """
    game.materials.clear()
    for line in read_lines(path):
        if line == "":
            continue
        fields = split_fields(line)
        material = Material(name=fields[0])
        if len(fields) >= 2:
            if fields[1] == "Event":
                material.event_only = True
                material.difficulty = 0
            elif fields[1] != "":
                material.event_only = False
                material.difficulty = to_uint32(fields[1])
        game.materials.append(material)
    game.material_map.clear()
    for material in game.materials:
        _add_unique(game.material_map, key=material.name, value=material)


def load_skill_tags(game: GameData, path: Path) -> None:
    """``SkillTag::Load`` (LoadedData.cpp:169-181): "All" and "Misc", then every non-blank line."""
    game.skill_tags.clear()
    game.skill_tags.append(SkillTag("All"))
    game.skill_tags.append(SkillTag("Misc"))
    for line in read_lines(path):
        if line != "":
            game.skill_tags.append(SkillTag(line))


def _find_tag(game: GameData, name: str) -> SkillTag | None:
    """``SkillTag::FindTag``: the first tag with this name."""
    for tag in game.skill_tags:
        if tag.name == name:
            return tag
    return None


def load_skills(game: GameData, path: Path) -> None:
    """``Skill::Load`` (Skill.cpp:64-157). Stops at the first blank line."""
    game.abilities.clear()
    game.ability_map.clear()
    game.skills.clear()
    game.skill_map.clear()
    game.ordered_skills.clear()

    for line in read_lines(path):
        if line == "":
            break
        if line[0] == "#":
            continue
        fields = split_fields(line)
        if fields[2] == "":
            # The torso-up row names an ability with no skill of its own.
            torso_inc = Ability(name=fields[0], static_index=len(game.abilities))
            game.torso_inc = torso_inc
            game.abilities.append(torso_inc)
            game.ability_map[torso_inc.name] = torso_inc
            continue
        points_required = to_int32(fields[4])
        ability = game.ability_map.get(fields[2])
        if ability is None:
            ability = Ability(name=fields[2], static_index=len(game.abilities))
            ability.auto_guard = ability.name == "Auto-Guard"
            game.abilities.append(ability)
            game.ability_map[ability.name] = ability
            if len(fields) != 8:
                raise ValueError(f"Ability {ability.name} has not enough data")
            if fields[6] != "":
                tag = _find_tag(game, fields[6])
                if tag is None:
                    raise ValueError(f"Skill Tag '{fields[6]}' does not exist")
                ability.tags.append(tag)
            if fields[7] == "":
                raise ValueError(f"Ability {ability.name} is missing order number")
            ability.order = to_uint32(fields[7])
        skill = Skill(name=fields[0], points_required=points_required, ability=ability)
        ability.skills[points_required] = skill
        game.skills.append(skill)
        game.skill_map[skill.name] = skill

    ordered: list[Ability | None] = [None] * len(game.abilities)
    for ability in game.abilities:
        ordered[ability.order] = ability
    if any(ability is None for ability in ordered):
        raise ValueError("Bad ordering of abilities")
    game.ordered_abilities = [ability for ability in ordered if ability is not None]

    # Skill.cpp:148-157: positive thresholds first, then negative, per ability in order.
    for ability in game.ordered_abilities[1:]:
        for points in (10, 15, 20, -10, -15, -20):
            if points in ability.skills:
                game.ordered_skills.append(ability.skills[points])


def read_skill_types(path: Path) -> list[int]:
    """The ``Type`` column of ``skills.txt`` per skill (0 both, 1 Blademaster, 2 Gunner).

    ``Skill::Load`` never reads this column (it uses fields 0, 2, 4, 6 and 7),
    and the GUI has no hunter-type skill filter. Lines are skipped as
    ``load_skills`` skips them, so the list lines up with ``GameData.skills``.
    """
    types = []
    for line in read_lines(path):
        if line == "":
            break
        if line[0] == "#":
            continue
        fields = split_fields(line)
        if fields[2] == "":
            continue
        types.append(to_int32(fields[5]))
    return types


def other_hunter_types_skill(skill_type: int, hunter_type: HunterType) -> bool:
    """The type column (``read_skill_types``) assigns the skill to the other hunter type."""
    mismatched = (skill_type == 1 and hunter_type is HunterType.GUNNER) or (
        skill_type == 2 and hunter_type is HunterType.BLADEMASTER
    )
    return mismatched


def _find_ability(game: GameData, name: str) -> Ability:
    ability = game.ability_map.get(name)
    if ability is None:
        raise ValueError(f"No such ability found: {name!r}")
    return ability


def _find_material(game: GameData, name: str) -> Material:
    material = game.material_map.get(name)
    if material is None:
        raise ValueError(f"No such material found: {name!r}")
    return material


def _gender(code: str) -> Gender:
    if code == "1":
        return Gender.MALE
    if code == "2":
        return Gender.FEMALE
    return Gender.BOTH_GENDERS


def _hunter_type(code: str) -> HunterType:
    if code == "1":
        return HunterType.BLADEMASTER
    if code == "2":
        return HunterType.GUNNER
    return HunterType.BOTH_TYPES


def load_armors(game: GameData, path: Path, armor_type: ArmorType) -> None:
    """``Armor::Load`` (Armor.cpp:18-103). Stops at the first blank line; skips repeated names."""
    armors = game.armors[armor_type]
    armors.clear()
    for line in read_lines(path):
        if line == "":
            break
        if line[0] == "#":
            continue
        fields = split_fields(line)
        if any(existing.name == fields[0] for existing in armors):
            continue
        # name, jname, gender, type, rarity, slots, hr, village, defence, max defence,
        # fire, water, ice, thunder, dragon, 5 x (skill, points), 4 x (material, amount)
        armor = Armor(
            name=fields[0],
            index=len(armors),
            gender=_gender(fields[2]),
            hunter_type=_hunter_type(fields[3]),
            rarity=as_unsigned(to_int32(fields[4])),
            num_slots=to_uint32(fields[5]),
            hr=to_uint32(fields[6]),
            elder_star=to_uint32(fields[7]),
            defence=to_uint32(fields[8]),
            max_defence=to_uint32(fields[9]),
            fire_res=to_int32(fields[10]),
            water_res=to_int32(fields[11]),
            ice_res=to_int32(fields[12]),
            thunder_res=to_int32(fields[13]),
            dragon_res=to_int32(fields[14]),
            is_piercing="Piercing" in fields[0],
        )
        for i in range(1, 5):
            if fields[i * 2 + 23] != "":
                material = _find_material(game, fields[i * 2 + 23])
                component = MaterialComponent(
                    material=material, amount=as_unsigned(to_int32(fields[i * 2 + 24]))
                )
                armor.components.append(component)
                armor.is_event = armor.is_event or material.event_only
                armor.difficulty = as_unsigned(
                    armor.difficulty + material.difficulty * component.amount
                )
        for i in range(5):
            index = 15 + i * 2
            if fields[index] != "":
                amount = to_int32(fields[index + 1]) if fields[index + 1] != "" else 0
                pair = AbilityPair(ability=_find_ability(game, fields[index]), amount=amount)
                armor.abilities.append(pair)
                if pair.ability is game.torso_inc:
                    armor.torso_inc = True
        armors.append(armor)
        _add_unique(game.armor_map, key=armor.name, value=armor)


def load_decorations(game: GameData, path: Path) -> None:
    """``Decoration::Load`` (Decoration.cpp:8-80). Blank and ``#`` lines are skipped."""
    game.decoration_map.clear()
    game.decorations_by_ability.clear()
    game.decorations.clear()
    for line in read_lines(path):
        if line == "" or line[0] == "#":
            continue
        fields = split_fields(line)
        # name, jname, rarity, slots, hr, village, 2 x (skill, points),
        # 4 x (material, amount), 4 x (alternative material, amount)
        decoration = Decoration(
            name=fields[0],
            index=len(game.decorations),
            rarity=to_uint32(fields[2]),
            slots_required=to_uint32(fields[3]),
            hr=to_uint32(fields[4]),
            elder_star=to_uint32(fields[5]),
        )
        for i in range(2):
            if fields[6 + i * 2] == "":
                continue
            pair = AbilityPair(
                ability=_find_ability(game, fields[6 + i * 2]), amount=to_int32(fields[7 + i * 2])
            )
            decoration.abilities.append(pair)
        for i in range(4):
            if fields[10 + i * 2] != "":
                material = _find_material(game, fields[10 + i * 2])
                component = MaterialComponent(
                    material=material, amount=to_uint32(fields[11 + i * 2])
                )
                decoration.components.append(component)
                decoration.is_event = decoration.is_event or material.event_only
                # Unlike armour, the original adds the material's difficulty once, not per unit.
                decoration.difficulty = as_unsigned(decoration.difficulty + material.difficulty)
            if fields[18 + i * 2] != "":
                material = _find_material(game, fields[18 + i * 2])
                component = MaterialComponent(
                    material=material, amount=to_uint32(fields[19 + i * 2])
                )
                decoration.components2.append(component)
        game.decorations.append(decoration)
        game.decorations_by_ability.setdefault(decoration.abilities[0].ability, []).append(
            decoration
        )
        _add_unique(game.decoration_map, key=decoration.name, value=decoration)


def _add_unique[T](mapping: dict[str, T], key: str, value: T) -> None:
    """``Dictionary::Add``, which throws on a duplicate key."""
    if key in mapping:
        raise ValueError(f"Duplicate name {key!r}")
    mapping[key] = value


class _LanguageFile:
    """Reads a language file line by line, skipping blank and ``#`` lines."""

    def __init__(self, path: Path, lines: list[str] | None = None) -> None:
        self.path = path
        self.lines: Iterator[str] = iter(read_lines(path) if lines is None else lines)

    def next_name(self) -> str:
        for line in self.lines:
            if line == "" or line[0] == "#":
                continue
            return line
        raise ValueError(f"Unexpected end of file: not enough lines of text in {self.path.name}")


def apply_language(game: GameData, language_dir: Path) -> None:
    """The record renaming in ``StringTable::LoadLanguage`` (Common.cpp:290-326).

    Display strings (``strings.txt``) belong to the user interface and are
    not loaded here.
    """
    tags = _LanguageFile(language_dir / "tags.txt")
    for tag in game.skill_tags:
        tag.name = tags.next_name()

    materials = _LanguageFile(language_dir / "components.txt")
    game.material_map.clear()
    for material in game.materials:
        material.name = materials.next_name()
        _add_unique(game.material_map, key=material.name, value=material)

    # One map shared by all five slots: a name already taken by an earlier
    # armour (in any slot) is skipped and the next line is used instead.
    game.armor_map.clear()
    for armor_type, file_name in _ARMOR_FILES.items():
        names = _LanguageFile(language_dir / file_name)
        for armor in game.armors[armor_type]:
            name = names.next_name()
            while name in game.armor_map:
                name = names.next_name()
            armor.name = name
            game.armor_map[name] = armor

    decorations = _LanguageFile(language_dir / "decorations.txt")
    game.decoration_map.clear()
    for decoration in game.decorations:
        decoration.name = decorations.next_name()
        _add_unique(game.decoration_map, key=decoration.name, value=decoration)

    _apply_skill_language(game, language_dir / "skills.txt")


def _apply_skill_language(game: GameData, path: Path) -> None:
    """``Skill::LoadLanguage`` (Skill.cpp:270-318).

    A file starting with ``#ordered`` lists abilities and skills in
    ``ordered_abilities`` / ``ordered_skills`` order instead of load order.
    """
    lines = read_lines(path)
    ordered = False
    if lines and lines[0].startswith("#"):
        # The original consumes the first line whenever it is a comment.
        ordered = lines[0] == "#ordered"
        lines = lines[1:]
    names = _LanguageFile(path, lines=lines)

    abilities = game.ordered_abilities if ordered else game.abilities
    skills = game.ordered_skills if ordered else game.skills

    # Renames static_abilities.Count entries, then static_skills.Count entries,
    # of whichever list applies. An ordered list that is shorter fails partway,
    # after the earlier renames, as the original's indexing does.
    game.ability_map.clear()
    for i in range(len(game.abilities)):
        ability = _entry(abilities, index=i, path=path)
        ability.name = names.next_name()
        _add_unique(game.ability_map, key=ability.name, value=ability)

    game.skill_map.clear()
    for i in range(len(game.skills)):
        skill = _entry(skills, index=i, path=path)
        skill.name = names.next_name()
        _add_unique(game.skill_map, key=skill.name, value=skill)


def _entry[T](records: list[T], index: int, path: Path) -> T:
    if index >= len(records):
        raise ValueError(f"{path.name}: the ordered list has only {len(records)} entries")
    return records[index]
