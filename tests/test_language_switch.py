"""Switching language at run time (LanguageSelect_Click, Form1.h:2011-2130)."""

from __future__ import annotations

import shutil

import pytest

from mhp3ass.charms.my_charms import MyCharmsFileError, load_my_charms, my_charms_text
from mhp3ass.data.strings import load_strings
from mhp3ass.language_switch import switch_language
from mhp3ass.model import ArmorType
from mhp3ass.search import SearchData


@pytest.fixture
def switch_data(legacy_data_dir):
    """Search data in English (TeamHGG) that the test renames."""
    data = SearchData.load(legacy_data_dir, language="English (TeamHGG)")
    return data


@pytest.fixture
def my_charms_copy(tmp_path, legacy_data_dir):
    path = tmp_path / "mycharms.txt"
    shutil.copyfile(legacy_data_dir / "mycharms.txt", path)
    return path


@pytest.fixture
def switch(switch_data, legacy_data_dir, my_charms_copy):
    def switch_to(language):
        strings = switch_language(
            switch_data.game,
            validity=switch_data.validity,
            data_dir=legacy_data_dir,
            language=language,
            my_charms_path=my_charms_copy,
        )
        return strings

    return switch_to


def test_the_game_and_strings_are_in_the_new_language(switch, switch_data, legacy_data_dir):
    strings = switch("Deutsch (Vuze)")

    assert "Attack" not in switch_data.game.ability_map
    assert strings == load_strings(legacy_data_dir / "Languages" / "Deutsch (Vuze)")


def test_my_charms_are_rewritten_in_the_new_language(
    switch, switch_data, my_charms_copy, legacy_data_dir
):
    switch("Japanese")
    rewritten = load_my_charms(my_charms_copy, game=switch_data.game, validity=switch_data.validity)

    assert my_charms_copy.read_bytes() == my_charms_text(rewritten.charms).encode("utf-8")
    assert len(rewritten.charms) > 0
    assert "Cold Res" not in my_charms_copy.read_text(encoding="utf-8")


@pytest.fixture
def my_charms_with_an_unknown_skill(my_charms_copy):
    with my_charms_copy.open("a", encoding="utf-8") as file:
        file.write("0,No Such Skill,5,,\r\n")
    return my_charms_copy


def test_a_line_that_failed_to_load_is_dropped(switch, my_charms_with_an_unknown_skill):
    switch("English (TMO)")

    assert "No Such Skill" not in my_charms_with_an_unknown_skill.read_text(encoding="utf-8")


def test_switching_there_and_back_keeps_the_list(switch, my_charms_copy, switch_data):
    original = load_my_charms(my_charms_copy, game=switch_data.game, validity=switch_data.validity)

    switch("Deutsch (Vuze)")
    switch("English (TeamHGG)")

    assert my_charms_copy.read_bytes() == my_charms_text(original.charms).encode("utf-8")


@pytest.fixture
def my_charms_the_original_cannot_load(my_charms_copy):
    """A slot count that isn't a number: LoadCustom throws (quirk 9)."""
    my_charms_copy.write_text("x,Attack,4,,\r\n", encoding="utf-8")
    return my_charms_copy


def test_a_list_that_cannot_load_changes_nothing(
    switch, switch_data, my_charms_the_original_cannot_load
):
    with pytest.raises(MyCharmsFileError):
        switch("Japanese")

    assert [
        "Attack" in switch_data.game.ability_map,
        my_charms_the_original_cannot_load.read_bytes(),
    ] == [True, b"x,Attack,4,,\r\n"]


@pytest.fixture
def data_with_a_short_skills_file(tmp_path, legacy_data_dir):
    """A copy of the game data whose German skills.txt stops half-way."""
    data_dir = tmp_path / "Data"
    shutil.copytree(legacy_data_dir, data_dir)
    skills = data_dir / "Languages" / "Deutsch (Vuze)" / "skills.txt"
    lines = skills.read_bytes().splitlines(keepends=True)
    skills.write_bytes(b"".join(lines[: len(lines) // 2]))
    return data_dir


def test_a_broken_language_changes_nothing(
    switch_data, my_charms_copy, data_with_a_short_skills_file
):
    """The armour files come before skills.txt, so a rename in place would have renamed them."""
    head = switch_data.game.armors[ArmorType.HEAD][1]
    head_name = head.name
    before = my_charms_copy.read_bytes()

    with pytest.raises(ValueError, match="Unexpected end of file"):
        switch_language(
            switch_data.game,
            validity=switch_data.validity,
            data_dir=data_with_a_short_skills_file,
            language="Deutsch (Vuze)",
            my_charms_path=my_charms_copy,
        )

    assert [head.name, my_charms_copy.read_bytes()] == [head_name, before]


def test_an_unknown_language_raises(switch):
    with pytest.raises(FileNotFoundError, match="no language folder"):
        switch("Klingon")


@pytest.fixture
def my_charms_in_a_locked_folder(my_charms_copy):
    """mycharms.txt can be read, but its folder can't be written."""
    my_charms_copy.parent.chmod(0o500)
    yield my_charms_copy
    my_charms_copy.parent.chmod(0o700)


def test_a_list_that_cannot_be_written_changes_nothing(
    switch, switch_data, my_charms_in_a_locked_folder
):
    before = my_charms_in_a_locked_folder.read_bytes()

    with pytest.raises(OSError):
        switch("Deutsch (Vuze)")

    assert [
        "Attack" in switch_data.game.ability_map,
        my_charms_in_a_locked_folder.read_bytes(),
    ] == [True, before]
