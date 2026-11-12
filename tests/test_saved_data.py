from __future__ import annotations

from pathlib import Path

import pytest

from mhp3ass.saved_data import (
    TuiFolders,
    TuiSettings,
    config_dir,
    my_charms_file,
    read_tui_settings,
    saved_data_dir,
    tui_settings_text,
    write_tui_settings,
)


def test_the_folder_is_under_dot_config_on_macos_and_linux():
    folder = config_dir(env={}, platform="darwin", home=Path("/home/hunter"))

    assert folder == Path("/home/hunter/.config/mhp3-ass")


def test_xdg_config_home_moves_the_folder():
    folder = config_dir(
        env={"XDG_CONFIG_HOME": "/xdg"}, platform="linux", home=Path("/home/hunter")
    )

    assert folder == Path("/xdg/mhp3-ass")


def test_an_empty_xdg_config_home_is_ignored():
    folder = config_dir(env={"XDG_CONFIG_HOME": ""}, platform="linux", home=Path("/home/hunter"))

    assert folder == Path("/home/hunter/.config/mhp3-ass")


def test_the_folder_is_under_app_data_on_windows():
    folder = config_dir(env={"APPDATA": "/appdata"}, platform="win32", home=Path("/home/hunter"))

    assert folder == Path("/appdata/mhp3-ass")


def test_windows_without_app_data_raises():
    with pytest.raises(KeyError, match="APPDATA"):
        config_dir(env={}, platform="win32", home=Path("/home/hunter"))


def test_no_tui_toml_gives_the_defaults(tmp_path):
    assert read_tui_settings(tmp_path / "tui.toml") == TuiSettings()


def test_settings_survive_a_write_and_read(tmp_path):
    path = tmp_path / "config" / "tui.toml"
    settings = TuiSettings(data_dir=Path('/Volumes/Shared/MHP3 "Run"'), jobs=4, reverse=True)

    write_tui_settings(path, settings)

    assert read_tui_settings(path) == settings


def test_defaults_write_an_empty_file():
    assert tui_settings_text(TuiSettings()) == ""


@pytest.mark.parametrize(
    ("text", "message"),
    [
        ("colour = 'blue'\n", "unknown settings"),
        ("data_dir = 3\n", "data_dir must be a string"),
        ("jobs = 'eight'\n", "jobs must be a whole number"),
        ("jobs = true\n", "jobs must be a whole number"),
        ("reverse = 'yes'\n", "reverse must be true or false"),
        ("jobs = 0\n", "jobs must be at least 1"),
    ],
)
def test_settings_the_tui_cant_use_raise(tmp_path, text, message):
    path = tmp_path / "tui.toml"
    path.write_text(text, encoding="utf-8")

    with pytest.raises(ValueError, match=message):
        read_tui_settings(path)


def test_mhp3ass_home_comes_first(tmp_path):
    settings = TuiSettings(data_dir=tmp_path / "chosen")

    folder = saved_data_dir({"MHP3ASS_HOME": str(tmp_path / "home")}, settings, own_dir=tmp_path)

    assert folder == tmp_path / "home"


def test_the_chosen_folder_comes_next(tmp_path):
    settings = TuiSettings(data_dir=tmp_path / "chosen")

    assert saved_data_dir({}, settings, own_dir=tmp_path / "own") == tmp_path / "chosen"


def test_without_either_it_is_the_tuis_own_folder(tmp_path):
    assert saved_data_dir({"MHP3ASS_HOME": ""}, TuiSettings(), own_dir=tmp_path) == tmp_path


@pytest.fixture
def shipped_list(tmp_path) -> Path:
    path = tmp_path / "shipped" / "mycharms.txt"
    path.parent.mkdir()
    path.write_bytes(b"0,Attack,4,,\r\n")
    return path


def test_the_first_run_copies_the_shipped_list(tmp_path, shipped_list):
    path = my_charms_file(tmp_path / "saved", shipped=shipped_list)

    assert (path, path.read_bytes()) == (tmp_path / "saved" / "mycharms.txt", b"0,Attack,4,,\r\n")


def test_an_existing_list_is_left_alone(tmp_path, shipped_list):
    own = tmp_path / "saved" / "mycharms.txt"
    own.parent.mkdir()
    own.write_bytes(b"0,Guard,10,,\r\n")

    path = my_charms_file(tmp_path / "saved", shipped=shipped_list)

    assert path.read_bytes() == b"0,Guard,10,,\r\n"


def test_a_folder_name_beyond_the_basic_plane_survives_a_write_and_read(tmp_path):
    path = tmp_path / "tui.toml"
    settings = TuiSettings(data_dir=Path("/Volumes/MHP3 \U0001f600 ハンター"))

    write_tui_settings(path, settings)

    assert read_tui_settings(path) == settings


def test_broken_toml_names_the_file(tmp_path):
    path = tmp_path / "tui.toml"
    path.write_text("jobs = = 4\n", encoding="utf-8")

    with pytest.raises(ValueError, match=r"tui\.toml: "):
        read_tui_settings(path)


def test_a_tilde_in_mhp3ass_home_is_the_home_folder(tmp_path):
    folder = saved_data_dir({"MHP3ASS_HOME": "~/mhp3"}, TuiSettings(), own_dir=tmp_path)

    assert folder == Path.home() / "mhp3"


def test_a_tilde_in_the_chosen_folder_is_the_home_folder(tmp_path):
    settings = TuiSettings(data_dir=Path("~/mhp3"))

    assert saved_data_dir({}, settings, own_dir=tmp_path) == Path.home() / "mhp3"


def test_a_relative_chosen_folder_is_under_the_tuis_own_folder(tmp_path):
    settings = TuiSettings(data_dir=Path("saves"))

    assert saved_data_dir({}, settings, own_dir=tmp_path) == tmp_path / "saves"


def test_the_folders_read_tui_toml_from_the_tuis_own_folder(tmp_path):
    own = tmp_path / "xdg" / "mhp3-ass"
    write_tui_settings(own / "tui.toml", TuiSettings(data_dir=tmp_path / "saves", jobs=2))

    folders = TuiFolders.find({"XDG_CONFIG_HOME": str(tmp_path / "xdg")}, "linux", home=tmp_path)

    assert (folders.settings_file, folders.saved, folders.settings.jobs) == (
        own / "tui.toml",
        tmp_path / "saves",
        2,
    )


def test_mhp3ass_home_overrides_the_folders_saved_data(tmp_path):
    env = {"XDG_CONFIG_HOME": str(tmp_path / "xdg"), "MHP3ASS_HOME": str(tmp_path / "home")}

    folders = TuiFolders.find(env, "linux", home=tmp_path)

    assert folders.saved == tmp_path / "home"
