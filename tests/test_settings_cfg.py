"""settings.cfg reading and writing against the layout SaveConfig writes (Form1.h:342-540)."""

from __future__ import annotations

import dataclasses

import pytest

from mhp3ass.model import ArmorType
from mhp3ass.results.result_set import ResultSet, skill_indices, solution_line
from mhp3ass.results.sorting import SortKey
from mhp3ass.results.view import CharmFilter
from mhp3ass.settings_cfg import (
    SettingsCfgError,
    check_header,
    load_results,
    parse_solution_line,
    read_settings_cfg,
    settings_cfg_text,
    with_solutions,
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


def test_gui_captures_are_in_english_teamhgg(gui_settings_paths, shipped_languages):
    languages = {
        shipped_languages[read_settings_cfg(path).language_index] for path in gui_settings_paths
    }

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
    """Two decorations announced, one given."""
    with pytest.raises(SettingsCfgError, match="list index out of range"):
        parse_solution_line("0 0 0 0 0 0 0 0 0 2 1 ", teamhgg_game)


def test_writing_needs_six_skill_rows(version_1_settings_cfg):
    with pytest.raises(ValueError, match="six skill rows"):
        settings_cfg_text(read_settings_cfg(version_1_settings_cfg))


def test_writes_version_2_with_crlf_and_no_byte_order_mark(version_2_settings_cfg):
    assert settings_cfg_text(read_settings_cfg(version_2_settings_cfg)) == (
        version_2_settings_cfg.read_bytes()
    )


@pytest.fixture
def settings_with_one_line(version_2_settings_cfg):
    settings = dataclasses.replace(
        read_settings_cfg(version_2_settings_cfg), solution_lines=("0 0 0 0 0 0 0 0 0 0 0 ",)
    )
    return settings


def test_writes_the_solution_lines_it_is_given(settings_with_one_line):
    assert settings_cfg_text(settings_with_one_line).endswith(
        b"\r\n1\r\n-1\r\n0 0 0 0 0 0 0 0 0 0 0 \r\n"
    )


@pytest.fixture
def load(teamhgg_game, language_count):
    """``load_results`` in English (TeamHGG), into ``results`` or a new ``ResultSet``."""

    def load_into(settings, results=None):
        view = load_results(
            settings=settings,
            game=teamhgg_game,
            results=ResultSet() if results is None else results,
            language_count=language_count,
        )
        return view

    return load_into


@pytest.fixture
def capture_settings(gui_captures_dir):
    def read(capture):
        settings = read_settings_cfg(gui_captures_dir / capture / "settings.cfg")
        return settings

    return read


@pytest.fixture
def charmed_capture_lines(capture_settings):
    """A capture's lines with a charm: fields left after the extra skills."""

    def charmed(capture):
        lines = []
        for line in capture_settings(capture).solution_lines:
            fields = line.split()
            decorations = int(fields[9])
            skills = int(fields[10 + decorations])
            if 11 + decorations + skills < len(fields):
                lines.append(line)
        return lines

    return charmed


@pytest.fixture
def loadable_settings(version_2_settings_cfg, charmed_line, line_with_difficulty_jewel):
    """The synthetic file with HR 6 (its 7 is out of range), one charmed and one charm-free line."""
    settings = dataclasses.replace(
        read_settings_cfg(version_2_settings_cfg),
        hr=6,
        solution_lines=(charmed_line, line_with_difficulty_jewel),
    )
    return settings


@pytest.fixture
def difficulty_sorted_settings(loadable_settings):
    return dataclasses.replace(loadable_settings, sort_index=8)


@pytest.fixture
def unselected_sort_settings(loadable_settings):
    return dataclasses.replace(loadable_settings, sort_index=-1)


@pytest.fixture
def results_loaded_from_capture_12(load, capture_settings):
    results = ResultSet()
    load(capture_settings("12"), results)
    return results


@pytest.fixture
def results_loaded_from_loadable_settings(load, loadable_settings):
    results = ResultSet()
    load(loadable_settings, results)
    return results


@pytest.mark.parametrize(
    ("capture", "charmed", "charm_free"), [("16", 0, 7241), ("20", 1003, 1223), ("12", 480, 0)]
)
def test_a_load_keeps_charm_free_lines_out_of_all_solutions(
    load, capture_settings, capture, charmed, charm_free
):
    view = load(capture_settings(capture))

    assert [len(view.all_solutions), len(view.no_charm_solutions), len(view.final)] == [
        charmed,
        charm_free,
        charmed,
    ]


@pytest.mark.parametrize("capture", ["16", "20"])
def test_the_save_after_a_load_keeps_only_the_charmed_lines(
    load, capture_settings, charmed_capture_lines, teamhgg_game, capture
):
    settings = capture_settings(capture)

    saved = with_solutions(settings, load(settings).all_solutions, teamhgg_game)

    assert list(saved.solution_lines) == charmed_capture_lines(capture)


def test_loading_the_same_results_again_drops_every_charmed_solution(
    load, capture_settings, results_loaded_from_capture_12
):
    reloaded = load(capture_settings("12"), results_loaded_from_capture_12)

    assert [len(capture_settings("12").solution_lines), len(reloaded.all_solutions)] == [480, 0]


def test_a_load_shows_all_sorted_by_the_saved_sort(load, difficulty_sorted_settings):
    view = load(difficulty_sorted_settings)

    assert [view.charm_filter, view.sort_key] == [CharmFilter.every_solution(), SortKey.DIFFICULTY]
    assert [len(view.all_solutions), len(view.no_charm_solutions)] == [1, 1]


def test_a_saved_sort_of_minus_one_sorts_nothing(load, unselected_sort_settings):
    assert load(unselected_sort_settings).sort_key is SortKey.NONE


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("language_index", 7, "language 7"),
        ("sort_index", 11, "sort 11"),
        ("sort_index", -2, "sort -2"),
        ("charm_select_index", 5, "charm select 5"),
        ("charm_select_index", -2, "charm select -2"),
        ("hr", 0, "HR 0"),
        ("hr", 7, "HR 7"),
        ("elder_star", 7, "village 7"),
        ("weapon_slots", 4, "weapon slots 4"),
        ("weapon_slots", -1, "weapon slots -1"),
    ],
)
def test_a_header_value_load_config_cannot_apply_is_rejected(
    loadable_settings, language_count, field, value, message
):
    settings = dataclasses.replace(loadable_settings, **{field: value})

    with pytest.raises(SettingsCfgError, match=message):
        check_header(settings, language_count=language_count)


@pytest.mark.parametrize(
    "changes",
    [
        {"language_index": 6, "sort_index": 10, "charm_select_index": 4, "hr": 6},
        {"language_index": 0, "sort_index": -1, "charm_select_index": -1, "hr": 1},
        {"elder_star": 1, "weapon_slots": 0},
        {"elder_star": 6, "weapon_slots": 3},
    ],
)
def test_header_values_at_their_limits_load(load, loadable_settings, changes):
    settings = dataclasses.replace(loadable_settings, **changes)

    assert len(load(settings).all_solutions) == 1


def test_a_rejected_header_leaves_the_results_alone(
    load, loadable_settings, results_loaded_from_loadable_settings
):
    kept = results_loaded_from_loadable_settings.all_solutions

    with pytest.raises(SettingsCfgError):
        load(dataclasses.replace(loadable_settings, hr=7), results_loaded_from_loadable_settings)

    assert [results_loaded_from_loadable_settings.all_solutions is kept, len(kept)] == [True, 1]
