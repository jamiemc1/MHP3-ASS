"""The TUI's form, sort and results to and from settings.cfg (SaveConfig and LoadConfig,
Form1.h:380-541)."""

from __future__ import annotations

import dataclasses

import pytest

from mhp3ass.model import Gender, HunterType
from mhp3ass.query import CharmMode
from mhp3ass.query_form import QueryForm
from mhp3ass.results.sorting import SortKey
from mhp3ass.saved_state import (
    SavedSearch,
    Startup,
    StartupSettings,
    form_from_settings,
    read_startup_settings,
    restore_search,
    settings_for,
    startup,
    write_settings_cfg,
)
from mhp3ass.settings_cfg import (
    SettingsCfg,
    SettingsCfgError,
    read_settings_cfg,
    settings_cfg_text,
)
from mhp3ass.skill_chips import chip_rows
from mhp3ass.skill_picker import SkillRowsByHunter, SkillSelection


@pytest.fixture
def skill_index(scratch_game):
    def index(name):
        return scratch_game.skills.index(scratch_game.skill_map[name])

    return index


@pytest.fixture
def two_tab_form(scratch_game):
    """Gunner shown, female, every option off; two skills on each tab."""
    skill_map = scratch_game.skill_map
    form = QueryForm(
        hunter_type=HunterType.GUNNER,
        gender=Gender.FEMALE,
        hr=4,
        elder_star=5,
        weapon_slots=2,
        charm_mode=CharmMode.TWO_SKILL,
        allow_bad=True,
        allow_piercings=False,
        allow_event=False,
        allow_low_rank=False,
        skill_rows=SkillRowsByHunter(
            blademaster=chip_rows([skill_map["Attack Up [Med]"], skill_map["Sharp Sword"]]),
            gunner=chip_rows([skill_map["Load Up"], skill_map["Accuracy+1"]]),
        ),
    )
    return form


@pytest.fixture
def two_tab_settings(two_tab_form, scratch_game):
    settings = settings_for(
        two_tab_form,
        game=scratch_game,
        language_index=0,
        last_search_gunner=True,
        sort_key=SortKey.DIFFICULTY,
        solutions=[],
    )
    return settings


def test_the_header_follows_the_form(two_tab_settings):
    assert [
        two_tab_settings.language_index,
        two_tab_settings.last_search_gunner,
        two_tab_settings.hunter_tab,
        two_tab_settings.male,
        two_tab_settings.allow_bad,
        two_tab_settings.allow_piercings,
        two_tab_settings.allow_event,
        two_tab_settings.allow_low_rank,
        two_tab_settings.sort_index,
        two_tab_settings.charm_select_index,
        two_tab_settings.hr,
        two_tab_settings.elder_star,
        two_tab_settings.weapon_slots,
    ] == [0, True, 1, False, True, False, False, False, 8, 4, 4, 5, 2]


def test_every_row_is_written_with_the_all_filter(two_tab_settings, skill_index):
    rows = two_tab_settings.skill_selections

    assert rows[:3] == (
        SkillSelection(
            blademaster_filter=0,
            blademaster_skill=skill_index("Attack Up [Med]"),
            gunner_filter=0,
            gunner_skill=skill_index("Load Up"),
        ),
        SkillSelection(
            blademaster_filter=0,
            blademaster_skill=skill_index("Sharp Sword"),
            gunner_filter=0,
            gunner_skill=skill_index("Accuracy+1"),
        ),
        SkillSelection(
            blademaster_filter=0, blademaster_skill=-1, gunner_filter=0, gunner_skill=-1
        ),
    )
    assert len(rows) == 6


def test_the_form_comes_back_from_the_file(two_tab_settings, two_tab_form, scratch_game, tmp_path):
    path = tmp_path / "settings.cfg"
    path.write_bytes(settings_cfg_text(two_tab_settings))

    assert form_from_settings(read_settings_cfg(path), scratch_game) == two_tab_form


@pytest.fixture
def settings_with_gaps(two_tab_settings, skill_index):
    """Blademaster's skills in rows 2 and 5, filtered by Misc and All; Gunner's in row 6."""
    empty = SkillSelection(
        blademaster_filter=0, blademaster_skill=-1, gunner_filter=0, gunner_skill=-1
    )
    rows = [empty] * 6
    rows[1] = dataclasses.replace(empty, blademaster_skill=skill_index("Sharp Sword"))
    rows[4] = dataclasses.replace(empty, blademaster_skill=skill_index("Attack Up [Med]"))
    rows[5] = dataclasses.replace(empty, gunner_skill=skill_index("Load Up"))
    settings = dataclasses.replace(two_tab_settings, skill_selections=tuple(rows))
    return settings


def test_rows_with_gaps_close_up_in_order(settings_with_gaps, scratch_game):
    skill_map = scratch_game.skill_map

    form = form_from_settings(settings_with_gaps, scratch_game)

    assert form.skill_rows == SkillRowsByHunter(
        blademaster=chip_rows([skill_map["Sharp Sword"], skill_map["Attack Up [Med]"]]),
        gunner=chip_rows([skill_map["Load Up"]]),
    )


@pytest.fixture
def settings_with_a_skill_its_filter_hides(two_tab_settings, skill_index, scratch_game):
    """Row 1's Blademaster skill under a filter that doesn't list it."""
    sharp_sword = scratch_game.skill_map["Sharp Sword"]
    hiding = next(
        index
        for index, tag in enumerate(scratch_game.skill_tags)
        if index > 1 and tag not in sharp_sword.ability.tags
    )
    rows = list(two_tab_settings.skill_selections)
    rows[1] = dataclasses.replace(rows[1], blademaster_filter=hiding)
    settings = dataclasses.replace(two_tab_settings, skill_selections=tuple(rows))
    return settings


def test_a_skill_its_row_filter_hides_is_dropped(
    settings_with_a_skill_its_filter_hides, scratch_game
):
    form = form_from_settings(settings_with_a_skill_its_filter_hides, scratch_game)

    assert form.skill_rows.blademaster == chip_rows([scratch_game.skill_map["Attack Up [Med]"]])


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"hunter_tab": 2}, "hunter tab 2"),
        ({"hunter_tab": -1}, "hunter tab -1"),
        ({"charm_select_index": -1}, "no charm mode"),
    ],
)
def test_values_the_tui_cannot_show_raise(two_tab_settings, scratch_game, changes, message):
    with pytest.raises(SettingsCfgError, match=message):
        form_from_settings(dataclasses.replace(two_tab_settings, **changes), scratch_game)


@pytest.fixture
def settings_with_an_unknown_filter(two_tab_settings, scratch_game):
    rows = list(two_tab_settings.skill_selections)
    rows[0] = dataclasses.replace(rows[0], gunner_filter=len(scratch_game.skill_tags))
    settings = dataclasses.replace(two_tab_settings, skill_selections=tuple(rows))
    return settings


def test_an_unknown_filter_raises(settings_with_an_unknown_filter, scratch_game):
    with pytest.raises(SettingsCfgError, match="can't restore the skill rows"):
        form_from_settings(settings_with_an_unknown_filter, scratch_game)


@pytest.fixture
def restore(scratch_game, language_count):
    def restore_settings(settings: SettingsCfg) -> SavedSearch:
        search = restore_search(
            settings,
            game=scratch_game,
            language="English (TeamHGG)",
            language_count=language_count,
        )
        return search

    return restore_settings


def test_a_file_without_lines_restores_no_results(restore, two_tab_settings, two_tab_form):
    search = restore(two_tab_settings)

    assert search == SavedSearch(
        form=two_tab_form, sort_key=SortKey.DIFFICULTY, last_search_gunner=True, results=None
    )


@pytest.mark.parametrize(
    ("field", "value", "message"), [("hr", 7, "HR 7"), ("language_index", 7, "language 7")]
)
def test_a_header_out_of_range_raises_without_lines(
    restore, two_tab_settings, field, value, message
):
    with pytest.raises(SettingsCfgError, match=message):
        restore(dataclasses.replace(two_tab_settings, **{field: value}))


@pytest.fixture
def capture_settings(gui_captures_dir):
    def read(capture):
        settings = read_settings_cfg(gui_captures_dir / capture / "settings.cfg")
        return settings

    return read


@pytest.fixture
def capture_names(gui_captures_dir):
    names = sorted(path.parent.name for path in gui_captures_dir.glob("*/settings.cfg"))
    return names


def _header(settings: SettingsCfg) -> SettingsCfg:
    header = dataclasses.replace(settings, skill_selections=(), solution_lines=())
    return header


def _saved_skills(settings: SettingsCfg) -> list[list[int]]:
    rows = settings.skill_selections
    skills = [
        [row.blademaster_skill for row in rows if row.blademaster_skill != -1],
        [row.gunner_skill for row in rows if row.gunner_skill != -1],
    ]
    return skills


def test_every_capture_is_saved_back_with_its_header_and_skills(
    capture_settings, capture_names, scratch_game
):
    changed = []
    for name in capture_names:
        settings = capture_settings(name)
        saved = settings_for(
            form_from_settings(settings, scratch_game),
            game=scratch_game,
            language_index=settings.language_index,
            last_search_gunner=settings.last_search_gunner,
            sort_key=SortKey(settings.sort_index),
            solutions=[],
        )
        if [_header(saved), _saved_skills(saved)] != [_header(settings), _saved_skills(settings)]:
            changed.append(name)

    assert [len(capture_names), changed] == [21, []]


def test_the_1b_capture_loads_the_guis_count(restore, capture_settings):
    """1b: Blademaster Attack Up [Med] + Sharp Sword with the imported charms (GUI: 34,153)."""
    results = restore(capture_settings("1b")).results

    assert results is not None
    assert len(results.view.all_solutions) + results.charm_free_only_under_none == 34_153


def test_results_belong_to_the_last_searchs_hunter_type(restore, capture_settings, capture_names):
    """A capture searched as Gunner, loaded with the Blademaster tab shown:
    its results' form and query are still Gunner's."""
    gunner_capture = next(
        name for name in capture_names if capture_settings(name).last_search_gunner
    )
    settings = dataclasses.replace(capture_settings(gunner_capture), hunter_tab=0)

    search = restore(settings)

    assert search.results is not None
    assert [
        search.form.hunter_type,
        search.results.form.hunter_type,
        search.results.query.hunter_type,
    ] == [HunterType.BLADEMASTER, HunterType.GUNNER, HunterType.GUNNER]


def test_the_starting_state_is_the_starting_form():
    assert SavedSearch.starting() == SavedSearch(
        form=QueryForm.starting(), sort_key=SortKey.NONE, last_search_gunner=False, results=None
    )


@pytest.fixture
def settings_path(tmp_path):
    return tmp_path / "settings.cfg"


@pytest.fixture
def unknown_version_file(settings_path):
    settings_path.write_bytes(b"3\r\n")
    return settings_path


@pytest.fixture
def file_with_language_7(settings_path, two_tab_settings):
    settings_path.write_bytes(
        settings_cfg_text(dataclasses.replace(two_tab_settings, language_index=7))
    )
    return settings_path


def test_a_missing_file_gives_no_settings_and_no_notice(settings_path, language_count):
    assert read_startup_settings(settings_path, language_count=language_count) == StartupSettings(
        settings=None, notice=None
    )


@pytest.mark.parametrize(
    ("file", "message"),
    [("unknown_version_file", "unsupported"), ("file_with_language_7", "language 7")],
)
def test_a_file_that_cant_be_read_is_set_aside(request, language_count, file, message):
    path = request.getfixturevalue(file)

    read = read_startup_settings(path, language_count=language_count)

    assert read.settings is None
    assert read.notice is not None
    assert message in read.notice
    assert "kept as settings.cfg.unreadable" in read.notice
    assert path.with_name("settings.cfg.unreadable").read_bytes() == path.read_bytes()


@pytest.fixture
def start(settings_path, scratch_game, language_count):
    def start_from(settings):
        started = startup(
            settings_path,
            settings=settings,
            game=scratch_game,
            language="English (TeamHGG)",
            language_count=language_count,
        )
        return started

    return start_from


def test_no_settings_start_from_the_defaults(start):
    assert start(None) == Startup(search=SavedSearch.starting(), notice=None)


@pytest.fixture
def file_with_no_charm_mode(settings_path, two_tab_settings):
    settings = dataclasses.replace(two_tab_settings, charm_select_index=-1)
    settings_path.write_bytes(settings_cfg_text(settings))
    return settings


def test_settings_that_cant_be_restored_start_from_the_defaults(
    start, settings_path, file_with_no_charm_mode
):
    started = start(file_with_no_charm_mode)

    assert started.search == SavedSearch.starting()
    assert started.notice is not None
    assert "no charm mode" in started.notice
    assert settings_path.with_name("settings.cfg.unreadable").exists()


def test_charm_free_sets_shown_only_under_none_get_a_notice(start, capture_settings):
    """Capture 20: Gunner Load Up + Accuracy+1, slotted charms, piercings and event armour off."""
    started = start(capture_settings("20"))

    assert started.notice == (
        "1,223 charm-free sets from last time show only under None, as in the original."
    )


def test_a_load_with_only_charmed_sets_has_no_notice(start, capture_settings):
    """Capture 12: 480 sets, every one with a charm."""
    started = start(capture_settings("12"))

    assert started.search.results is not None
    assert [len(started.search.results.view.all_solutions), started.notice] == [480, None]


@pytest.fixture
def old_settings_file(settings_path):
    settings_path.write_bytes(b"old")
    return settings_path


def test_writing_replaces_the_file_and_leaves_no_temporary_file(
    old_settings_file, two_tab_settings
):
    write_settings_cfg(old_settings_file, two_tab_settings)

    assert [path.name for path in old_settings_file.parent.iterdir()] == ["settings.cfg"]
    assert old_settings_file.read_bytes() == settings_cfg_text(two_tab_settings)
