from __future__ import annotations

import pytest

from mhp3ass.model import Ability, AbilityPair, ArmorType, Charm
from mhp3ass.results.short_names import (
    ShortNames,
    ability_abbreviations,
    piece_words,
    short_armor_name,
    short_charm_name,
)


@pytest.fixture
def names_by_slot():
    """Three slots' names: each slot has its piece words, and the monster and
    material words (Rathian, Leather) and the S suffix are in every slot."""
    names = {
        ArmorType.HEAD: ["Rathian Helm", "Leather Helm S", "Rathian Cap", "Leather Cap"],
        ArmorType.BODY: ["Rathian Mail", "Leather Mail S", "Rathian Vest S", "Leather Vest"],
        ArmorType.ARMS: [
            "Rathian Vambraces S",
            "Leather Guards",
            "Rathian Guards",
            "Leather Vambraces",
        ],
    }
    return names


def test_piece_words_are_common_in_their_slot_and_absent_from_the_others(names_by_slot):
    words = piece_words(names_by_slot)

    assert words == {
        ArmorType.HEAD: frozenset({"Helm", "Cap"}),
        ArmorType.BODY: frozenset({"Mail", "Vest"}),
        ArmorType.ARMS: frozenset({"Vambraces", "Guards"}),
    }


def test_a_word_in_another_slots_names_is_not_a_piece_word(names_by_slot):
    names = {**names_by_slot, ArmorType.BODY: [*names_by_slot[ArmorType.BODY], "Helm Plate"]}

    words = piece_words(names, max_elsewhere=0.0)

    assert "Helm" not in words[ArmorType.HEAD]
    assert "Cap" in words[ArmorType.HEAD]


def test_a_word_in_too_few_of_its_slots_names_is_not_a_piece_word(names_by_slot):
    words = piece_words(names_by_slot, min_share=0.6)

    assert words[ArmorType.HEAD] == frozenset()


@pytest.mark.parametrize(
    ("name", "short"),
    [
        ("Barroth Tasset S", "Barroth S"),
        ("Jinouga Helm", "Jinouga"),
        ("Golden Moon Tasset", "Golden Moon"),
        ("Casco Tigrex U", "Tigrex U"),
        ("Ahorn-Helm", "Ahorn"),
        ("Hapulbokka-Helm S", "Hapulbokka S"),
        ("Yukumo Sash", "Yukumo Sash"),
        ("Helm", "Helm"),
    ],
)
def test_a_short_armour_name_drops_the_piece_words(name, short):
    words = frozenset({"Helm", "Tasset", "Casco"})

    assert short_armor_name(name, words) == short


def test_a_name_with_no_spaces_or_hyphens_is_kept_whole():
    assert short_armor_name("ハプルＳヘルム", frozenset({"ヘルム"})) == "ハプルＳヘルム"


def test_each_ability_gets_its_shortest_unique_prefix_of_three_or_more():
    names = ["Attack", "Sharpness", "Sharp Sword", "Guard", "Guard Up", "Ice Res", "Ice Atk", "Hi"]

    abbreviations = ability_abbreviations(names)

    assert abbreviations == {
        "Attack": "Att",
        "Sharpness": "Sharpn",
        "Sharp Sword": "Sharp S",
        "Guard": "Guard",
        "Guard Up": "Guard U",
        "Ice Res": "Ice R",
        "Ice Atk": "Ice A",
        "Hi": "Hi",
    }


def test_a_charm_reads_as_signed_amounts_short_abilities_and_its_slots():
    attack = Ability(name="Attack", static_index=0)
    sharpness = Ability(name="Sharpness", static_index=1)
    charm = Charm(
        num_slots=1,
        abilities=[
            AbilityPair(ability=attack, amount=4),
            AbilityPair(ability=sharpness, amount=-2),
        ],
    )

    name = short_charm_name(charm, {"Attack": "Att", "Sharpness": "Shp"})

    assert name == "+4 Att -2 Shp (1)"


def test_a_slotless_charm_has_no_brackets_and_an_ability_with_no_short_name_stays_whole():
    guard = Ability(name="Guard", static_index=0)
    charm = Charm(num_slots=0, abilities=[AbilityPair(ability=guard, amount=3)])

    assert short_charm_name(charm, {}) == "+3 Guard"


def test_the_english_game_drops_its_piece_words(teamhgg_short_names):
    pieces = [
        ("Jinouga Helm", ArmorType.HEAD),
        ("Agnaktor Mail", ArmorType.BODY),
        ("Jinouga Vambraces", ArmorType.ARMS),
        ("Barroth Tasset S", ArmorType.WAIST),
        ("Baggi Greaves S", ArmorType.LEGS),
    ]

    shorts = [teamhgg_short_names.armor(name, slot) for name, slot in pieces]

    assert shorts == ["Jinouga", "Agnaktor", "Jinouga", "Barroth S", "Baggi S"]


def test_every_language_shortens_some_pieces_except_japanese(games_by_language):
    shortened = {}
    for language, game in games_by_language.items():
        names = ShortNames.from_game(game)
        shortened[language] = sum(
            names.armor(armor.name, slot) != armor.name
            for slot, armors in game.armors.items()
            for armor in armors
        )

    assert shortened["Japanese"] == 0
    assert all(count > 200 for language, count in shortened.items() if language != "Japanese")


def test_every_languages_short_ability_names_are_unique(games_by_language):
    clashes = {}
    for language, game in games_by_language.items():
        abbreviations = ShortNames.from_game(game).abbreviations
        shorts = list(abbreviations.values())
        clashes[language] = len(shorts) - len(set(shorts))

    assert set(clashes.values()) == {0}
