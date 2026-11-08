"""Loading rules of the original that the shipped data never exercises.

The golden comparison can't tell these apart from the "obvious" behaviour,
because no shipped file triggers them, so each gets a small synthetic file.
"""

from __future__ import annotations

import pytest

from data_rows import armor_row, decoration_row
from mhp3ass.data import apply_language, load_game_data
from mhp3ass.data.loaders import read_skill_types
from mhp3ass.model import ArmorType


def test_decoration_difficulty_counts_each_material_once(minimal_data_files, write_files):
    # Decoration.cpp:50 adds the material's difficulty, ignoring the amount.
    minimal_data_files["decorations.txt"] = (
        decoration_row("Attack Jewel", materials="Gem,3,,,,,,") + "\n"
    )

    game = load_game_data(write_files(minimal_data_files))

    assert game.decorations[0].difficulty == 7


def test_armor_difficulty_counts_every_unit(minimal_data_files, write_files):
    # Armor.cpp:77 multiplies by the amount.
    minimal_data_files["head.txt"] = armor_row("Cap", materials="Gem,3,,,,,,") + "\n"

    game = load_game_data(write_files(minimal_data_files))

    assert game.armors[ArmorType.HEAD][0].difficulty == 21


def test_armor_loading_stops_at_first_blank_line(minimal_data_files, write_files):
    minimal_data_files["head.txt"] = armor_row("Cap") + "\n\n" + armor_row("Helm") + "\n"

    game = load_game_data(write_files(minimal_data_files))

    assert [armor.name for armor in game.armors[ArmorType.HEAD]] == ["Cap"]


def test_decoration_loading_skips_blank_lines(minimal_data_files, write_files):
    minimal_data_files["decorations.txt"] = (
        decoration_row("Attack Jewel") + "\n\n" + decoration_row("Attack Jewel+") + "\n"
    )

    game = load_game_data(write_files(minimal_data_files))

    assert [decoration.name for decoration in game.decorations] == ["Attack Jewel", "Attack Jewel+"]


def test_skill_loading_stops_at_first_blank_line(minimal_data_files, write_files):
    minimal_data_files["skills.txt"] += "\nAttack Up Big,j,Attack,j,20,0\n"

    game = load_game_data(write_files(minimal_data_files))

    assert [skill.name for skill in game.skills] == ["Attack Up", "Defense Up"]


def test_repeated_armor_name_keeps_the_first_row(minimal_data_files, write_files):
    second_cap = armor_row("Cap").replace(",10,20,", ",99,99,")
    minimal_data_files["head.txt"] = armor_row("Cap") + "\n" + second_cap + "\n"

    game = load_game_data(write_files(minimal_data_files))

    heads = game.armors[ArmorType.HEAD]
    assert [(armor.name, armor.defence) for armor in heads] == [("Cap", 10)]


def test_fields_keep_quotes(minimal_data_files, write_files):
    # SplitString calls RemoveQuotes but discards the result (Common.cpp:30, 36).
    minimal_data_files["components.txt"] = 'Ore,2\nGem,7\n"Quoted Ore",1\n'

    game = load_game_data(write_files(minimal_data_files))

    assert game.materials[2].name == '"Quoted Ore"'


def test_hash_lines_are_materials_not_comments(minimal_data_files, write_files):
    minimal_data_files["components.txt"] = "#Not a comment,3\nOre,2\nGem,7\n"

    game = load_game_data(write_files(minimal_data_files))

    assert [material.name for material in game.materials] == ["#Not a comment", "Ore", "Gem"]


def test_translated_armor_name_taken_by_an_earlier_slot_is_skipped(
    minimal_data_files, minimal_language_files, write_files
):
    # One name map for all five slots (Armor.cpp:202-208): the body file's first
    # line repeats the head's translated name, so the body takes the next line.
    minimal_language_files["body.txt"] = "T Cap\nT Mail\n"
    game = load_game_data(write_files(minimal_data_files))

    apply_language(game, write_files(minimal_language_files, folder_name="Language"))

    assert [game.armors[ArmorType.HEAD][0].name, game.armors[ArmorType.BODY][0].name] == [
        "T Cap",
        "T Mail",
    ]


def test_ordered_skill_file_renames_in_ability_order(
    minimal_data_files, minimal_language_files, write_files
):
    # Load order is torso-up, Defense, Attack; "order" puts Attack before Defense,
    # so the ordered layout and the load-order layout name them differently.
    # Torso-up takes order 0, as in the shipped data: ordered_skills skips that slot.
    minimal_data_files["skills.txt"] = (
        "Torso Up,j,,j,0,0,,\n"
        "Defense Up,j,Defense,j,10,0,,2\n"
        "Attack Up,j,Attack,j,10,0,Offensive,1\n"
    )
    minimal_language_files["skills.txt"] = (
        "#ordered\nT Torso\nT Attack\nT Defense\nT Attack Up\nT Defense Up\n"
    )
    game = load_game_data(write_files(minimal_data_files))

    apply_language(game, write_files(minimal_language_files, folder_name="Language"))

    ability_names = [(ability.order, ability.name) for ability in game.abilities]
    skill_names = [(skill.ability.order, skill.name) for skill in game.skills]
    assert [ability_names, skill_names] == [
        [(0, "T Torso"), (2, "T Defense"), (1, "T Attack")],
        [(2, "T Defense Up"), (1, "T Attack Up")],
    ]


def test_repeated_skill_name_maps_to_the_last_row(minimal_data_files, write_files):
    # Skill.cpp:129 assigns through the indexer, so a later row with the same name wins.
    minimal_data_files["skills.txt"] += "Attack Up,j,Attack,j,15,0\n"

    game = load_game_data(write_files(minimal_data_files))

    assert game.skill_map["Attack Up"].points_required == 15


def test_armor_name_in_two_slots_fails(minimal_data_files, write_files):
    # One armour map for all slots, filled with Dictionary::Add, which throws on a repeat.
    minimal_data_files["body.txt"] = armor_row("Cap") + "\n"

    with pytest.raises(ValueError):
        load_game_data(write_files(minimal_data_files))


def test_skill_types_skip_the_rows_load_skills_skips(minimal_data_files, write_files):
    minimal_data_files["skills.txt"] = (
        "#name,jname,ability,jability,points,type,tag,order\n"
        "Attack Up,j,Attack,j,10,1,Offensive,0\n"
        "Torso Up,j,,j,0,0,,1\n"
        "Defense Up,j,Defense,j,10,2,,2\n"
        "\n"
        "Late Skill,j,Late,j,10,0,,3\n"
    )

    types = read_skill_types(write_files(minimal_data_files) / "skills.txt")

    assert types == [1, 2]
