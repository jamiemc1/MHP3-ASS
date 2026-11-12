from __future__ import annotations

from dataclasses import dataclass

import pytest

from mhp3ass.data.strings import DisplayStrings, StringIndex, load_strings
from mhp3ass.model import AbilityPair, Charm
from mhp3ass.results.details import (
    ArmorLine,
    ArmorNote,
    DecorationCount,
    SlotsSpare,
    SolutionDetails,
)
from mhp3ass.results.inspector import InspectorLine, inspector_lines, note_text, spare_text
from mhp3ass.solution.state import Solution


@pytest.fixture(scope="module")
def english_strings(legacy_data_dir) -> DisplayStrings:
    strings = load_strings(legacy_data_dir / "Languages" / "English (TeamHGG)")
    return strings


@pytest.mark.parametrize(
    ("spare", "text"),
    [
        (SlotsSpare(total=0, groups=None), "0 slots spare"),
        (SlotsSpare(total=1, groups=None), "1 slot spare"),
        (SlotsSpare(total=3, groups=None), "3 slots spare"),
        (SlotsSpare(total=4, groups=(1, 1, 2)), "4 slots spare (1+1+2)"),
    ],
)
def test_spare_slots_read_as_the_original_writes_them(english_strings, spare, text):
    assert spare_text(spare, english_strings) == text


def test_a_piece_with_one_slot_and_no_skills_says_one_slot(teamhgg_game, english_strings):
    one_slot = next(armor for armor in teamhgg_game.armor_map.values() if armor.num_slots == 1)

    note = note_text(ArmorLine(armor=one_slot, note=ArmorNote.ANY_WITH_SLOTS), english_strings)

    assert note == "(or anything with 1 slot)"


def test_a_piece_with_two_slots_and_no_skills_says_slots(teamhgg_game, english_strings):
    two_slots = next(armor for armor in teamhgg_game.armor_map.values() if armor.num_slots == 2)

    note = note_text(ArmorLine(armor=two_slots, note=ArmorNote.ANY_WITH_SLOTS), english_strings)

    assert note == "(or anything with 2 slots)"


def test_a_torso_up_piece_says_torso_inc(teamhgg_game, english_strings):
    piece = next(iter(teamhgg_game.armor_map.values()))

    note = note_text(ArmorLine(armor=piece, note=ArmorNote.ANY_TORSO_INC), english_strings)

    assert note == "(or anything with Torso Inc)"


def test_a_piece_with_skills_has_no_note(teamhgg_game, english_strings):
    piece = next(iter(teamhgg_game.armor_map.values()))

    assert note_text(ArmorLine(armor=piece, note=None), english_strings) is None


@dataclass(frozen=True)
class InspectedSet:
    solution: Solution
    details: SolutionDetails


@pytest.fixture
def set_with_an_empty_arms_slot(teamhgg_game) -> InspectedSet:
    """Four pieces (no arms), a charm, two kinds of jewel, two slots spare, one extra skill."""
    armor_map = teamhgg_game.armor_map
    head = armor_map["Jinouga Helm"]
    body = armor_map["Agnaktor Mail"]
    waist = armor_map["Barroth Tasset S"]
    legs = armor_map["Baggi Greaves S"]
    attack_jewel, razor_jewel = teamhgg_game.decorations[0], teamhgg_game.decorations[1]
    charm = Charm(
        num_slots=1,
        abilities=[AbilityPair(ability=teamhgg_game.ability_map["Attack"], amount=4)],
    )
    solution = Solution(
        armors=[head, body, None, waist, legs],
        charm=charm,
        defence=412,
        max_defence=520,
        fire_res=2,
        water_res=-1,
        thunder_res=6,
        ice_res=0,
        dragon_res=-3,
        rarity=30,
        difficulty=7,
    )
    details = SolutionDetails(
        armors=(
            ArmorLine(armor=head, note=None),
            ArmorLine(armor=body, note=None),
            ArmorLine(armor=waist, note=ArmorNote.ANY_WITH_SLOTS),
            ArmorLine(armor=legs, note=None),
        ),
        charm=charm,
        decorations=(
            DecorationCount(decoration=attack_jewel, count=3),
            DecorationCount(decoration=razor_jewel, count=2),
        ),
        slots_spare=SlotsSpare(total=2, groups=(1, 1)),
        sort_value=None,
        extra_skills=(teamhgg_game.skill_map["Guard +1"],),
    )
    inspected = InspectedSet(solution=solution, details=details)
    return inspected


def test_the_lines_list_pieces_charm_jewels_spare_extra_skills_and_stats(
    teamhgg_game, english_strings, set_with_an_empty_arms_slot
):
    solution = set_with_an_empty_arms_slot.solution
    details = set_with_an_empty_arms_slot.details
    waist = teamhgg_game.armor_map["Barroth Tasset S"]
    attack_jewel, razor_jewel = teamhgg_game.decorations[0], teamhgg_game.decorations[1]

    lines = inspector_lines(
        solution, details, english_strings, piece_labels=["Head", "Body", "Arms", "Waist", "Legs"]
    )

    assert lines == [
        InspectorLine("Head", "Jinouga Helm"),
        InspectorLine("Body", "Agnaktor Mail"),
        InspectorLine("Waist", "Barroth Tasset S"),
        InspectorLine("", f"(or anything with {waist.num_slots} slots)"),
        InspectorLine("Legs", "Baggi Greaves S"),
        InspectorLine("Charm", "+4 Attack O--"),
        InspectorLine("Jewels", f"3x {attack_jewel.name}"),
        InspectorLine("", f"2x {razor_jewel.name}"),
        InspectorLine("Spare", "2 slots spare (1+1)"),
        InspectorLine("Extra", "Guard +1"),
        InspectorLine("Base Defence", "412"),
        InspectorLine("Max Defence", "520"),
        InspectorLine("Fire res", "2"),
        InspectorLine(english_strings.static(StringIndex.WATER_RES), "-1"),
        InspectorLine(english_strings.static(StringIndex.THUNDER_RES), "6"),
        InspectorLine(english_strings.static(StringIndex.ICE_RES), "0"),
        InspectorLine(english_strings.static(StringIndex.DRAGON_RES), "-3"),
        InspectorLine("Rarity", "30"),
        InspectorLine("Difficulty", "7"),
    ]
