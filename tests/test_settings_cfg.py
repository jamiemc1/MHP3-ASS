"""settings.cfg reading and writing against the layout SaveConfig writes (Form1.h:342-540)."""

from __future__ import annotations

import dataclasses

import pytest

from mhp3ass.data.languages import language_folders
from mhp3ass.model import ArmorType
from mhp3ass.results.result_set import skill_indices, solution_line
from mhp3ass.settings_cfg import (
    SettingsCfgError,
    parse_solution_line,
    read_settings_cfg,
    settings_cfg_text,
)
from mhp3ass.skill_picker import SkillSelection


@pytest.fixture
def option_lines():
    """Lines 2-14, as SaveConfig writes them."""
    lines = [
        "2",  # language index
        "True",  # last search gunner
        "0",  # hunter tab showing
        "False",  # male
        "True",  # allow bad
        "False",  # piercings
        "True",  # event
        "False",  # low rank
        "3",  # sort
        "4",  # charm select
        "7",  # HR
        "6",  # elder star
        "2",  # weapon slots
    ]
    return lines


@pytest.fixture
def solution_lines():
    return ("1 2 3 4 5 0 0 0 0 0 0 ", "6 7 8 9 10 1 1 0 0 0 0 1 2 1 4 12 ")


@pytest.fixture
def write_settings_cfg(tmp_path, option_lines):
    """Write a settings.cfg as SaveConfig does (CRLF), with ``skill_rows`` drop-down rows."""

    def write(version: str, skill_rows: int, solutions: tuple[str, ...]):
        rows = []
        for row in range(skill_rows):
            rows += ["0", str(row * 10), "1", "-1"]
        path = tmp_path / "settings.cfg"
        lines = [version, *option_lines, *rows, *solutions]
        path.write_text("\r\n".join(lines) + "\r\n", encoding="utf-8")
        return path

    return write


@pytest.fixture
def version_2_settings_cfg(write_settings_cfg, solution_lines):
    return write_settings_cfg(version="2", skill_rows=6, solutions=solution_lines)


@pytest.fixture
def version_1_settings_cfg(write_settings_cfg, solution_lines):
    return write_settings_cfg(version="1", skill_rows=5, solutions=solution_lines)


@pytest.fixture
def version_2_settings_cfg_missing_a_skill_row(write_settings_cfg):
    return write_settings_cfg(version="2", skill_rows=5, solutions=())


@pytest.fixture
def settings_cfg_with_blank_solution_line(write_settings_cfg, solution_lines):
    return write_settings_cfg(version="2", skill_rows=6, solutions=(solution_lines[0], ""))


def test_reads_options_in_save_order(version_2_settings_cfg):
    settings = read_settings_cfg(version_2_settings_cfg)

    assert [
        settings.language_index,
        settings.last_search_gunner,
        settings.hunter_tab,
        settings.male,
        settings.allow_bad,
        settings.allow_piercings,
        settings.allow_event,
        settings.allow_low_rank,
        settings.sort_index,
        settings.charm_select_index,
        settings.hr,
        settings.elder_star,
        settings.weapon_slots,
    ] == [2, True, 0, False, True, False, True, False, 3, 4, 7, 6, 2]


def test_reads_six_skill_rows_from_version_2(version_2_settings_cfg):
    settings = read_settings_cfg(version_2_settings_cfg)

    assert len(settings.skill_selections) == 6
    assert settings.skill_selections[5] == SkillSelection(
        blademaster_filter=0, blademaster_skill=50, gunner_filter=1, gunner_skill=-1
    )


def test_solutions_follow_the_header(version_2_settings_cfg, solution_lines):
    assert read_settings_cfg(version_2_settings_cfg).solution_lines == solution_lines


def test_version_1_has_five_skill_rows(version_1_settings_cfg, solution_lines):
    settings = read_settings_cfg(version_1_settings_cfg)

    assert [len(settings.skill_selections), settings.solution_lines] == [5, solution_lines]


def test_rejects_versions_load_config_ignores(tmp_path):
    path = tmp_path / "settings.cfg"
    path.write_text("3\n", encoding="utf-8")

    with pytest.raises(ValueError, match="unsupported"):
        read_settings_cfg(path)


def test_rejects_a_file_ending_inside_the_header(version_2_settings_cfg_missing_a_skill_row):
    with pytest.raises(ValueError, match="ends inside its header"):
        read_settings_cfg(version_2_settings_cfg_missing_a_skill_row)


def test_rejects_a_blank_solution_line(settings_cfg_with_blank_solution_line):
    with pytest.raises(ValueError, match="blank solution line"):
        read_settings_cfg(settings_cfg_with_blank_solution_line)


@pytest.fixture(scope="module")
def gui_settings_paths(gui_captures_dir):
    paths = sorted(gui_captures_dir.glob("*/settings.cfg"))
    return paths


@pytest.fixture
def difficulty_jewel(teamhgg_game):
    jewel = next(decoration for decoration in teamhgg_game.decorations if decoration.difficulty > 0)
    return jewel


@pytest.fixture
def line_with_difficulty_jewel(difficulty_jewel):
    """Head 1, body 2, arms 3, waist 4, legs 5; one spare 2-slot; the jewel; no charm."""
    return f"1 2 3 4 5 2 0 1 0 1 {difficulty_jewel.index} 0 "


@pytest.fixture
def charmed_line():
    """No decorations, one extra skill (12), a 2-slot charm: +4 of ability 7, -2 of ability 3."""
    return "0 0 0 0 0 0 0 0 0 0 1 12 2 2 4 7 -2 3 "


def test_every_gui_capture_is_written_back_byte_for_byte(gui_settings_paths):
    rewritten = [
        path.parent.name
        for path in gui_settings_paths
        if settings_cfg_text(read_settings_cfg(path)) != path.read_bytes()
    ]

    assert [len(gui_settings_paths), rewritten] == [21, []]


def test_gui_captures_are_in_english_teamhgg(gui_settings_paths, legacy_data_dir):
    folders = language_folders(legacy_data_dir / "Languages")
    languages = {folders[read_settings_cfg(path).language_index] for path in gui_settings_paths}

    assert languages == {"English (TeamHGG)"}


def test_every_gui_capture_line_loads_and_saves_unchanged(gui_settings_paths, teamhgg_game):
    skill_index = skill_indices(teamhgg_game)
    changed = [
        line
        for path in gui_settings_paths
        for line in read_settings_cfg(path).solution_lines
        if solution_line(parse_solution_line(line, teamhgg_game), skill_index) != line
    ]

    assert changed == []


def test_a_line_names_its_armour_decorations_and_skills(line_with_difficulty_jewel, teamhgg_game):
    solution = parse_solution_line(line_with_difficulty_jewel, teamhgg_game)

    assert [armor.index if armor else None for armor in solution.armors] == [1, 2, 3, 4, 5]
    assert [armor.name for armor in solution.armors if armor] == [
        teamhgg_game.armors[armor_type][index].name
        for armor_type, index in zip(ArmorType, [1, 2, 3, 4, 5], strict=True)
    ]
    assert [solution.charm, solution.extra_skills] == [None, []]


def test_spare_slots_come_from_the_line(line_with_difficulty_jewel, teamhgg_game):
    solution = parse_solution_line(line_with_difficulty_jewel, teamhgg_game)

    assert [solution.total_slots_spare, solution.slots_spare] == [2, [0, 0, 1, 0]]


def test_difficulty_counts_the_armour_but_not_the_decorations(
    line_with_difficulty_jewel, teamhgg_game
):
    solution = parse_solution_line(line_with_difficulty_jewel, teamhgg_game)
    armor_difficulty = sum(armor.difficulty for armor in solution.armors if armor)

    assert solution.difficulty == armor_difficulty
    assert solution.decorations[0].difficulty > 0


def test_a_charm_keeps_its_pairs_in_line_order(charmed_line, teamhgg_game):
    solution = parse_solution_line(charmed_line, teamhgg_game)
    charm = solution.charm

    assert charm is not None
    assert [
        charm.num_slots,
        [(pair.ability.static_index, pair.amount) for pair in charm.abilities],
    ] == [
        2,
        [(7, 4), (3, -2)],
    ]
    assert solution.extra_skills == [teamhgg_game.skills[12]]


def test_an_empty_slot_cannot_be_loaded(teamhgg_game):
    with pytest.raises(SettingsCfgError, match=r"'-1 2 3 4 5 0 0 0 0 0 0 '"):
        parse_solution_line("-1 2 3 4 5 0 0 0 0 0 0 ", teamhgg_game)


def test_an_armour_index_past_the_table_cannot_be_loaded(teamhgg_game):
    head_count = len(teamhgg_game.armors[ArmorType.HEAD])

    with pytest.raises(SettingsCfgError, match="HEAD armour"):
        parse_solution_line(f"{head_count} 0 0 0 0 0 0 0 0 0 0 ", teamhgg_game)


def test_a_line_that_ends_early_cannot_be_loaded(teamhgg_game):
    with pytest.raises(SettingsCfgError, match="can't load"):
        parse_solution_line("0 0 0 0 0 0 0 0 0 2 1 ", teamhgg_game)


def test_writing_needs_six_skill_rows(version_1_settings_cfg):
    with pytest.raises(ValueError, match="six skill rows"):
        settings_cfg_text(read_settings_cfg(version_1_settings_cfg))


def test_writes_version_2_with_crlf_and_no_byte_order_mark(version_2_settings_cfg):
    assert settings_cfg_text(read_settings_cfg(version_2_settings_cfg)) == (
        version_2_settings_cfg.read_bytes()
    )


def test_writes_the_solution_lines_it_is_given(version_2_settings_cfg):
    settings = dataclasses.replace(
        read_settings_cfg(version_2_settings_cfg), solution_lines=("0 0 0 0 0 0 0 0 0 0 0 ",)
    )

    assert settings_cfg_text(settings).endswith(b"\r\n1\r\n-1\r\n0 0 0 0 0 0 0 0 0 0 0 \r\n")
