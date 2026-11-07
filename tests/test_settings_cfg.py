"""settings.cfg reading against the layout SaveConfig writes (Form1.h:464-540)."""

from __future__ import annotations

import pytest

from mhp3ass.settings_cfg import SkillSelection, read_settings_cfg


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
