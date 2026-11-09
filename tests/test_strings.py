"""Display strings (StringTable::LoadLanguage, Common.cpp:290-311) and the Common.h macros."""

from __future__ import annotations

import pytest

from mhp3ass.data.languages import language_folders
from mhp3ass.data.strings import DisplayStrings, StringIndex, load_strings, strip_ampersands
from mhp3ass.data.text import read_lines


@pytest.fixture
def strings_with_comments_and_blanks():
    """Every string named after its index, with a comment and a blank line before the first
    and two extra lines after the last."""
    lines = ["# header", "", *(f"s{index}" for index in range(len(StringIndex))), "extra", "more"]
    return "\n".join(lines) + "\n"


@pytest.fixture
def short_strings():
    return "\n".join(f"s{index}" for index in range(len(StringIndex) - 1)) + "\n"


@pytest.fixture
def strings_with_ampersand_at_exit():
    text = ["" for _ in StringIndex]
    text[StringIndex.EXIT] = "E&xit"
    return DisplayStrings(text=tuple(text))


def test_string_index_has_one_member_per_shipped_line(legacy_data_dir):
    lines = read_lines(legacy_data_dir / "Languages" / "English (TeamHGG)" / "strings.txt")

    assert [len(StringIndex), len(lines)] == [87, 87]


def test_every_shipped_language_ends_on_its_last_line(legacy_data_dir):
    """The last string is each file's last line, so no shipped line is skipped or left over."""
    languages_dir = legacy_data_dir / "Languages"
    folders = language_folders(languages_dir)

    last_strings = {
        folder: load_strings(languages_dir / folder).static(StringIndex.RESULTS)
        for folder in folders
    }

    assert last_strings == {
        folder: read_lines(languages_dir / folder / "strings.txt")[-1] for folder in folders
    }


def test_indices_line_up_with_the_shipped_file(legacy_data_dir):
    strings = load_strings(legacy_data_dir / "Languages" / "English (TeamHGG)")

    assert [
        strings.static(StringIndex.FILE),
        strings.static(StringIndex.SORT_SLOTS_SPARE),
        strings.static(StringIndex.NONE_BRACKETS),
        strings.static(StringIndex.SOLUTIONS_FOUND),
        strings.static(StringIndex.RESULTS),
    ] == ["&File", "Slots Spare", "(none)", "Solutions found:", "Results"]


def test_skips_blank_and_comment_lines_and_ignores_extra_lines(
    write_files, strings_with_comments_and_blanks
):
    folder = write_files({"strings.txt": strings_with_comments_and_blanks})

    strings = load_strings(folder)

    assert strings.text == tuple(f"s{index}" for index in range(len(StringIndex)))


def test_a_short_file_raises(write_files, short_strings):
    folder = write_files({"strings.txt": short_strings})

    with pytest.raises(ValueError, match=r"Unexpected end of file.*strings\.txt"):
        load_strings(folder)


def test_a_table_of_the_wrong_length_raises():
    with pytest.raises(ValueError, match="86 display strings, expected 87"):
        DisplayStrings(text=("",) * 86)


def test_strip_ampersands_removes_every_ampersand():
    assert strip_ampersands("&Save && E&xit") == "Save  Exit"


def test_macros_add_spaces_and_colons(strings_with_ampersand_at_exit):
    index = StringIndex.EXIT

    assert [
        strings_with_ampersand_at_exit.static(index),
        strings_with_ampersand_at_exit.add(index),
        strings_with_ampersand_at_exit.run(index),
        strings_with_ampersand_at_exit.start(index),
        strings_with_ampersand_at_exit.basic(index),
        strings_with_ampersand_at_exit.colon(index),
    ] == ["E&xit", " E&xit", " E&xit ", "E&xit ", "Exit", "E&xit: "]
