from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

from mhp3ass.data import GameData
from mhp3ass.data.languages import language_folders
from mhp3ass.settings_cfg import read_settings_cfg
from mhp3ass.skill_picker import (
    SkillRow,
    SkillRowsByHunter,
    SkillSelection,
    query_skills,
    restore_skill_rows,
    row_choices,
    saved_skill_index,
    select_filter,
    select_skill,
    skill_choices,
    starting_rows,
)


@pytest.fixture
def choose_skills(teamhgg_game: GameData) -> Callable[..., tuple[SkillRow, ...]]:
    """Builds rows from the start-up state, choosing skills by name row by row (``None`` skips)."""

    def choose(*names: str | None) -> tuple[SkillRow, ...]:
        rows = starting_rows()
        for row, name in enumerate(names):
            if name is not None:
                rows = select_skill(teamhgg_game, rows, row, teamhgg_game.skill_map[name])
        return rows

    return choose


@pytest.fixture
def start_up_rows() -> SkillRowsByHunter:
    """Both tabs as the GUI starts: every row filtered by All, with no skill."""
    rows = SkillRowsByHunter(blademaster=starting_rows(), gunner=starting_rows())
    return rows


@pytest.fixture
def attack_med_in_row_three(choose_skills) -> SkillRowsByHunter:
    """Blademaster row 3 holds Attack Up [Med]; every other row of both tabs is empty."""
    rows = SkillRowsByHunter(
        blademaster=choose_skills(None, None, None, "Attack Up [Med]"),
        gunner=starting_rows(),
    )
    return rows


@pytest.fixture
def sharp_sword_in_another_game(other_teamhgg_game) -> SkillRowsByHunter:
    """Blademaster row 0 holds Sharp Sword from a separately loaded copy of the game."""
    rows = SkillRowsByHunter(
        blademaster=select_skill(
            other_teamhgg_game, starting_rows(), 0, other_teamhgg_game.skill_map["Sharp Sword"]
        ),
        gunner=starting_rows(),
    )
    return rows


def selection(blademaster_skill=-1, blademaster_filter=0, gunner_skill=-1, gunner_filter=0):
    built = SkillSelection(
        blademaster_filter=blademaster_filter,
        blademaster_skill=blademaster_skill,
        gunner_filter=gunner_filter,
        gunner_skill=gunner_skill,
    )
    return built


def six_rows(*first: SkillSelection) -> list[SkillSelection]:
    """A version 2 file's six rows: ``first``, then empty rows."""
    rows = [*first, *(selection() for _ in range(6 - len(first)))]
    return rows


def skill_index(game: GameData, name: str) -> int:
    index = game.skills.index(game.skill_map[name])
    return index


def names(skills) -> list[str]:
    return [skill.name for skill in skills]


def test_all_offers_every_skill_that_needs_points(teamhgg_game):
    choices = skill_choices(teamhgg_game, filter_index=0, disallowed=[])

    assert choices == [skill for skill in teamhgg_game.skills if skill.points_required > 0]


def test_misc_offers_skills_of_untagged_abilities(teamhgg_game):
    choices = skill_choices(teamhgg_game, filter_index=1, disallowed=[])

    assert [len(choices), any(skill.ability.tags for skill in choices)] == [18, False]


def test_a_tag_filter_offers_skills_with_that_tag(teamhgg_game):
    choices = skill_choices(teamhgg_game, filter_index=2, disallowed=[])

    assert [
        teamhgg_game.skill_tags[2].name,
        len(choices),
        all(any(tag.name == "Offensive" for tag in skill.ability.tags) for skill in choices),
    ] == ["Offensive", 30, True]


def test_no_filter_offers_nothing(teamhgg_game):
    assert skill_choices(teamhgg_game, filter_index=-1, disallowed=[]) == []


def test_a_filter_past_the_last_tag_raises(teamhgg_game):
    with pytest.raises(ValueError, match="filter 8"):
        skill_choices(teamhgg_game, filter_index=8, disallowed=[])


def test_disallowed_abilities_are_left_out(teamhgg_game):
    attack = teamhgg_game.ability_map["Attack"]

    choices = skill_choices(teamhgg_game, filter_index=2, disallowed=[attack])

    assert [len(choices), any(skill.ability is attack for skill in choices)] == [27, False]


def test_a_row_leaves_out_abilities_chosen_in_other_rows(teamhgg_game, choose_skills):
    rows = choose_skills("Attack Up [Med]")

    offered = names(row_choices(teamhgg_game, rows, 1))

    assert [name for name in offered if name.startswith("Attack Up")] == []


def test_a_row_still_offers_other_levels_of_its_own_ability(teamhgg_game, choose_skills):
    rows = choose_skills("Attack Up [Med]")

    offered = names(row_choices(teamhgg_game, rows, 0))

    assert [name for name in offered if name.startswith("Attack Up")] == [
        "Attack Up [Sm]",
        "Attack Up [Med]",
        "Attack Up [Lg]",
    ]


def test_a_row_outside_the_six_raises(teamhgg_game, choose_skills):
    with pytest.raises(ValueError, match="row -1"):
        row_choices(teamhgg_game, choose_skills(), -1)


def test_choosing_a_skill_another_row_rules_out_raises(teamhgg_game, choose_skills):
    rows = choose_skills("Attack Up [Med]")

    with pytest.raises(ValueError, match="Attack Up \\[Lg\\]"):
        select_skill(teamhgg_game, rows, 1, teamhgg_game.skill_map["Attack Up [Lg]"])


def test_choosing_none_clears_the_row(teamhgg_game, choose_skills):
    rows = choose_skills("Attack Up [Med]", "Sharp Sword")

    cleared = select_skill(teamhgg_game, rows, 0, None)

    assert names(query_skills(cleared)) == ["Sharp Sword"]


def test_clearing_a_row_outside_the_six_raises(teamhgg_game, choose_skills):
    with pytest.raises(ValueError, match="row 6"):
        select_skill(teamhgg_game, choose_skills(), 6, None)


def test_a_filter_that_offers_the_skill_keeps_it(teamhgg_game, choose_skills):
    rows = choose_skills("Attack Up [Med]")

    filtered = select_filter(teamhgg_game, rows, 0, filter_index=2)

    assert filtered[0] == SkillRow(filter_index=2, skill=teamhgg_game.skill_map["Attack Up [Med]"])


def test_a_filter_that_doesnt_offer_the_skill_clears_it(teamhgg_game, choose_skills):
    rows = choose_skills("Attack Up [Med]")

    filtered = select_filter(teamhgg_game, rows, 0, filter_index=1)

    assert filtered[0] == SkillRow(filter_index=1, skill=None)


def test_changing_a_filter_leaves_other_rows_alone(teamhgg_game, choose_skills):
    rows = choose_skills("Attack Up [Med]", "Sharp Sword")

    filtered = select_filter(teamhgg_game, rows, 0, filter_index=1)

    assert filtered[1:] == rows[1:]


def test_setting_a_filter_past_the_last_tag_raises(teamhgg_game, choose_skills):
    with pytest.raises(ValueError, match="filter -2"):
        select_filter(teamhgg_game, choose_skills(), 0, filter_index=-2)


def test_the_query_takes_skills_in_row_order(choose_skills):
    rows = choose_skills(None, "Sharp Sword", None, None, "Attack Up [Med]")

    assert names(query_skills(rows)) == ["Sharp Sword", "Attack Up [Med]"]


def test_an_empty_row_is_saved_as_minus_one(teamhgg_game):
    assert saved_skill_index(teamhgg_game, SkillRow(filter_index=0, skill=None)) == -1


def test_a_chosen_row_is_saved_as_its_static_index(teamhgg_game, choose_skills):
    rows = choose_skills("Sharp Sword")

    assert saved_skill_index(teamhgg_game, rows[0]) == skill_index(teamhgg_game, "Sharp Sword")


def test_restoring_from_start_up_gives_the_saved_rows(teamhgg_game, start_up_rows):
    selections = six_rows(
        selection(skill_index(teamhgg_game, "Attack Up [Med]"), blademaster_filter=2),
        selection(gunner_skill=skill_index(teamhgg_game, "Sharp Sword")),
    )

    restored = restore_skill_rows(teamhgg_game, start_up_rows, selections)

    assert [names(query_skills(restored.blademaster)), names(query_skills(restored.gunner))] == [
        ["Attack Up [Med]"],
        ["Sharp Sword"],
    ]


def test_a_saved_skill_its_filter_doesnt_offer_leaves_the_row_empty(teamhgg_game, start_up_rows):
    misc_attack = selection(skill_index(teamhgg_game, "Attack Up [Med]"), blademaster_filter=1)

    restored = restore_skill_rows(teamhgg_game, start_up_rows, six_rows(misc_attack))

    assert restored.blademaster[0] == SkillRow(filter_index=1, skill=None)


def test_a_saved_index_past_the_last_skill_leaves_the_row_empty(teamhgg_game, start_up_rows):
    past_the_end = selection(len(teamhgg_game.skills))

    restored = restore_skill_rows(teamhgg_game, start_up_rows, six_rows(past_the_end))

    assert restored.blademaster[0] == SkillRow(filter_index=0, skill=None)


def test_restoring_drops_a_skill_a_row_not_yet_restored_rules_out(
    teamhgg_game, attack_med_in_row_three
):
    attack_lg_first = six_rows(selection(skill_index(teamhgg_game, "Attack Up [Lg]")))

    restored = restore_skill_rows(teamhgg_game, attack_med_in_row_three, attack_lg_first)

    assert query_skills(restored.blademaster) == []


def test_restoring_keeps_a_skill_once_the_row_ruling_it_out_is_cleared(
    teamhgg_game, attack_med_in_row_three
):
    attack_lg_fifth = six_rows(
        *(selection() for _ in range(4)), selection(skill_index(teamhgg_game, "Attack Up [Lg]"))
    )

    restored = restore_skill_rows(teamhgg_game, attack_med_in_row_three, attack_lg_fifth)

    assert names(query_skills(restored.blademaster)) == ["Attack Up [Lg]"]


def test_a_version_1_file_leaves_the_sixth_row_alone(teamhgg_game, choose_skills):
    start = SkillRowsByHunter(
        blademaster=choose_skills(None, None, None, None, None, "Sharp Sword"),
        gunner=starting_rows(),
    )
    five_rows = [selection() for _ in range(5)]

    restored = restore_skill_rows(teamhgg_game, start, five_rows)

    assert names(query_skills(restored.blademaster)) == ["Sharp Sword"]


def test_restoring_raises_on_a_filter_past_the_last_tag(teamhgg_game, start_up_rows):
    with pytest.raises(ValueError, match="filter 9"):
        restore_skill_rows(teamhgg_game, start_up_rows, six_rows(selection(blademaster_filter=9)))


def test_restoring_raises_on_seven_saved_rows(teamhgg_game, start_up_rows):
    with pytest.raises(ValueError, match="not 7"):
        restore_skill_rows(teamhgg_game, start_up_rows, [selection() for _ in range(7)])


def test_restoring_raises_on_rows_from_another_game(teamhgg_game, sharp_sword_in_another_game):
    with pytest.raises(ValueError, match="Sharp Sword isn't one of this game's skills"):
        restore_skill_rows(teamhgg_game, sharp_sword_in_another_game, six_rows())


def _capture_mismatches(
    gui_captures_dir: Path, legacy_data_dir: Path, games_by_language: dict[str, GameData]
) -> list[str]:
    languages = language_folders(legacy_data_dir / "Languages")
    mismatched = []
    for capture in sorted(gui_captures_dir.iterdir()):
        settings = read_settings_cfg(capture / "settings.cfg")
        game = games_by_language[languages[settings.language_index]]
        start = SkillRowsByHunter(blademaster=starting_rows(), gunner=starting_rows())
        restored = restore_skill_rows(game, start, settings.skill_selections)
        resaved = tuple(
            SkillSelection(
                blademaster_filter=blademaster.filter_index,
                blademaster_skill=saved_skill_index(game, blademaster),
                gunner_filter=gunner.filter_index,
                gunner_skill=saved_skill_index(game, gunner),
            )
            for blademaster, gunner in zip(restored.blademaster, restored.gunner, strict=True)
        )
        if resaved != settings.skill_selections:
            mismatched.append(capture.name)
    return mismatched


def test_every_gui_capture_restores_its_saved_rows(
    gui_captures_dir, legacy_data_dir, games_by_language
):
    assert _capture_mismatches(gui_captures_dir, legacy_data_dir, games_by_language) == []
