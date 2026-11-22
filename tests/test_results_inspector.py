from __future__ import annotations

from dataclasses import dataclass

import pytest

from mhp3ass.charms.naming import charm_name
from mhp3ass.data.strings import StringIndex
from mhp3ass.model import AbilityPair, ArmorType, Charm, Decoration
from mhp3ass.results.details import (
    ArmorLine,
    ArmorNote,
    CorrectedJewels,
    DecorationCount,
    Placement,
    PlacementPending,
    SlotsSpare,
    SolutionDetails,
    UnbuildableJewels,
    UnknownPlacement,
)
from mhp3ass.results.inspector import (
    InspectorLine,
    PieceLine,
    charm_text,
    inspector_lines,
    jewel_lines,
    note_text,
    piece_lines,
    slot_label,
    spare_text,
)
from mhp3ass.results.placement import JewelPlacement, ShortSkill, Unbuildable
from mhp3ass.solution.state import Solution


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
    one_slot = next(armor for armor in teamhgg_game.armors[ArmorType.HEAD] if armor.num_slots == 1)

    note = note_text(
        ArmorLine(slot=ArmorType.HEAD, armor=one_slot, note=ArmorNote.ANY_WITH_SLOTS),
        english_strings,
    )

    assert note == "(or anything with 1 slot)"


def test_a_piece_with_two_slots_and_no_skills_says_slots(teamhgg_game, english_strings):
    two_slots = next(armor for armor in teamhgg_game.armors[ArmorType.HEAD] if armor.num_slots == 2)

    note = note_text(
        ArmorLine(slot=ArmorType.HEAD, armor=two_slots, note=ArmorNote.ANY_WITH_SLOTS),
        english_strings,
    )

    assert note == "(or anything with 2 slots)"


def test_a_torso_up_piece_says_torso_inc(teamhgg_game, english_strings):
    piece = teamhgg_game.armors[ArmorType.HEAD][0]

    note = note_text(
        ArmorLine(slot=ArmorType.HEAD, armor=piece, note=ArmorNote.ANY_TORSO_INC), english_strings
    )

    assert note == "(or anything with Torso Inc)"


def test_a_piece_with_skills_has_no_note(teamhgg_game, english_strings):
    piece = teamhgg_game.armors[ArmorType.HEAD][0]

    assert (
        note_text(ArmorLine(slot=ArmorType.HEAD, armor=piece, note=None), english_strings) is None
    )


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
            ArmorLine(slot=ArmorType.HEAD, armor=head, note=None),
            ArmorLine(slot=ArmorType.BODY, armor=body, note=None),
            ArmorLine(slot=ArmorType.WAIST, armor=waist, note=ArmorNote.ANY_WITH_SLOTS),
            ArmorLine(slot=ArmorType.LEGS, armor=legs, note=None),
        ),
        charm=charm,
        decorations=(
            DecorationCount(decoration=attack_jewel, count=3),
            DecorationCount(decoration=razor_jewel, count=2),
        ),
        chest_jewels=None,
        slots_spare=SlotsSpare(total=2, groups=(1, 1)),
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

    lines = inspector_lines(solution, details=details, strings=english_strings)

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


def test_the_piece_lines_skip_the_empty_slot_and_carry_each_note(
    teamhgg_game, english_strings, set_with_an_empty_arms_slot
):
    waist = teamhgg_game.armor_map["Barroth Tasset S"]

    lines = piece_lines(set_with_an_empty_arms_slot.details, english_strings)

    assert lines == [
        PieceLine(label="Head", name="Jinouga Helm", note=None),
        PieceLine(label="Body", name="Agnaktor Mail", note=None),
        PieceLine(
            label="Waist",
            name="Barroth Tasset S",
            note=f"(or anything with {waist.num_slots} slots)",
        ),
        PieceLine(label="Legs", name="Baggi Greaves S", note=None),
    ]


def test_a_charm_is_named_and_no_charm_says_so(teamhgg_game):
    charm = Charm(
        num_slots=1,
        abilities=[AbilityPair(ability=teamhgg_game.ability_map["Attack"], amount=4)],
    )

    assert [charm_text(charm), charm_text(None)] == ["+4 Attack O--", "no charm"]


def test_a_set_without_armour_has_no_piece_lines(english_strings):
    details = SolutionDetails(
        armors=(),
        charm=None,
        decorations=(),
        chest_jewels=None,
        slots_spare=None,
        extra_skills=(),
    )

    lines = piece_lines(details, english_strings)

    assert lines == []


@pytest.mark.parametrize(
    ("slot", "label"),
    [
        (ArmorType.HEAD, "Head"),
        (ArmorType.BODY, "Body"),
        (ArmorType.ARMS, "Arms"),
        (ArmorType.WAIST, "Waist"),
        (ArmorType.LEGS, "Legs"),
    ],
)
def test_each_slot_is_labelled_in_english(slot, label):
    assert slot_label(slot) == label


@pytest.fixture
def jewel_counts(teamhgg_game) -> list[DecorationCount]:
    attack_jewel, razor_jewel = teamhgg_game.decorations[0], teamhgg_game.decorations[1]
    counts = [
        DecorationCount(decoration=attack_jewel, count=2),
        DecorationCount(decoration=razor_jewel, count=1),
    ]
    return counts


def _each(*counts: DecorationCount) -> tuple[Decoration, ...]:
    """Each counted jewel as many times as it is counted, in order."""
    jewels = tuple(count.decoration for count in counts for _ in range(count.count))
    return jewels


def _jewel_details(
    counts: list[DecorationCount],
    chest_jewels: Placement,
) -> SolutionDetails:
    details = SolutionDetails(
        armors=(),
        charm=None,
        decorations=tuple(counts),
        chest_jewels=chest_jewels,
        slots_spare=None,
        extra_skills=(),
    )
    return details


def test_torso_inc_jewels_are_listed_by_place(jewel_counts):
    attack, razor = jewel_counts
    split = JewelPlacement(multiplier=3, chest=_each(attack), elsewhere=_each(razor))

    lines = jewel_lines(_jewel_details(jewel_counts, chest_jewels=split))

    assert lines == [
        InspectorLine("Chest x3", f"2x {attack.decoration.name}"),
        InspectorLine("Elsewhere", f"1x {razor.decoration.name}"),
    ]


def test_a_jewel_placed_twice_apart_is_counted_once_in_first_placed_order(jewel_counts):
    attack, razor = jewel_counts
    interleaved = (attack.decoration, razor.decoration, attack.decoration)
    split = JewelPlacement(multiplier=2, chest=interleaved, elsewhere=())

    lines = jewel_lines(_jewel_details(jewel_counts, chest_jewels=split))

    assert lines[:2] == [
        InspectorLine("Chest x2", f"2x {attack.decoration.name}"),
        InspectorLine("", f"1x {razor.decoration.name}"),
    ]


def test_an_empty_chest_says_none(jewel_counts):
    split = JewelPlacement(multiplier=2, chest=(), elsewhere=_each(*jewel_counts))

    lines = jewel_lines(_jewel_details(jewel_counts, chest_jewels=split))

    assert lines[0] == InspectorLine("Chest x2", "none")
    assert [line.label for line in lines[1:]] == ["Elsewhere", ""]


def test_an_unknown_placement_keeps_one_list_and_says_so(jewel_counts):
    attack, razor = jewel_counts

    lines = jewel_lines(_jewel_details(jewel_counts, chest_jewels=UnknownPlacement()))

    assert lines == [
        InspectorLine("Jewels", f"2x {attack.decoration.name}"),
        InspectorLine("", f"1x {razor.decoration.name}"),
        InspectorLine("", "(placement not known)"),
    ]


def test_a_pending_placement_keeps_one_list_and_says_it_waits(jewel_counts):
    lines = jewel_lines(_jewel_details(jewel_counts, chest_jewels=PlacementPending()))

    assert lines[-1] == InspectorLine("", "(placement after the search)")
    assert [line.label for line in lines] == ["Jewels", "", ""]


def test_a_placement_being_worked_out_says_so(jewel_counts):
    pending = PlacementPending(while_searching=False)

    lines = jewel_lines(_jewel_details(jewel_counts, chest_jewels=pending))

    assert lines[-1] == InspectorLine("", "(working out jewels…)")
    assert [line.label for line in lines] == ["Jewels", "", ""]


def test_a_set_without_a_split_has_no_note(jewel_counts):
    lines = jewel_lines(_jewel_details(jewel_counts, chest_jewels=None))

    assert [line.label for line in lines] == ["Jewels", ""]


def test_a_corrected_set_shows_the_jewels_that_build_it(jewel_counts):
    attack, razor = jewel_counts
    corrected = CorrectedJewels(
        charm=None,
        charm_changed=False,
        jewels=JewelPlacement(multiplier=2, chest=_each(razor), elsewhere=_each(attack)),
    )

    lines = jewel_lines(_jewel_details(jewel_counts, chest_jewels=corrected))

    assert lines == [
        InspectorLine("Jewels", "(the listed jewels don't fit; these build it)"),
        InspectorLine("Chest x2", f"1x {razor.decoration.name}"),
        InspectorLine("Elsewhere", f"2x {attack.decoration.name}"),
    ]


def test_a_set_needing_its_unreduced_charm_names_the_charm(jewel_counts, teamhgg_game):
    attack, razor = jewel_counts
    attack_ability = attack.decoration.abilities[0].ability
    charm = Charm(num_slots=2, abilities=[AbilityPair(ability=attack_ability, amount=5)])
    corrected = CorrectedJewels(
        charm=charm,
        charm_changed=True,
        jewels=JewelPlacement(multiplier=3, chest=(), elsewhere=_each(attack, razor)),
    )

    lines = jewel_lines(_jewel_details(jewel_counts, chest_jewels=corrected))

    assert lines[:3] == [
        InspectorLine("Jewels", "(the listed charm and jewels don't fit; these build it)"),
        InspectorLine("Builds with", charm_name(charm)),
        InspectorLine("Chest x3", "none"),
    ]


def test_an_unbuildable_set_keeps_its_jewels_and_names_the_bad_skill(jewel_counts, teamhgg_game):
    attack_down = next(skill for skill in teamhgg_game.skills if skill.points_required < 0)
    unbuildable = UnbuildableJewels(reason=Unbuildable(bad_skills=(attack_down,), short=()))

    lines = jewel_lines(_jewel_details(jewel_counts, chest_jewels=unbuildable))

    assert [line.label for line in lines] == ["Jewels", "", ""]
    assert lines[-1] == InspectorLine(
        "", f"(can't be built as listed: {attack_down.name} stays active)"
    )


def test_an_unbuildable_set_names_the_skill_short_of_its_points(jewel_counts, teamhgg_game):
    skill = next(skill for skill in teamhgg_game.skills if skill.points_required == 10)
    unbuildable = UnbuildableJewels(
        reason=Unbuildable(bad_skills=(), short=(ShortSkill(skill=skill, most=7),))
    )

    lines = jewel_lines(_jewel_details(jewel_counts, chest_jewels=unbuildable))

    assert lines[-1] == InspectorLine(
        "", f"(can't be built as listed: {skill.ability.name} reaches 7 of 10)"
    )


def test_an_unbuildable_set_whose_skills_only_reach_apart_says_so(jewel_counts):
    unbuildable = UnbuildableJewels(reason=Unbuildable(bad_skills=(), short=()))

    lines = jewel_lines(_jewel_details(jewel_counts, chest_jewels=unbuildable))

    assert lines[-1] == InspectorLine(
        "", "(can't be built as listed: the skills can't all reach their points together)"
    )


@pytest.fixture
def hard_piece(teamhgg_game):
    """The first head piece whose recipe has a material with a difficulty."""
    piece = next(
        armor
        for armor in teamhgg_game.armors[ArmorType.HEAD]
        if any(component.material.difficulty > 0 for component in armor.components)
    )
    return piece


def test_the_hard_materials_follow_the_difficulty(english_strings, hard_piece):
    solution = Solution(armors=[hard_piece, None, None, None, None], charm=None, difficulty=3)
    details = SolutionDetails(
        armors=(ArmorLine(slot=ArmorType.HEAD, armor=hard_piece, note=None),),
        charm=None,
        decorations=(),
        chest_jewels=None,
        slots_spare=None,
        extra_skills=(),
    )
    expected = [
        InspectorLine("", f"{component.amount}x {component.material.name}")
        for component in hard_piece.components
        if component.material.difficulty > 0
    ]

    lines = inspector_lines(solution, details=details, strings=english_strings)

    difficulty_line = lines.index(InspectorLine("Difficulty", "3"))
    assert lines[difficulty_line + 1 :] == expected
    assert expected != []
