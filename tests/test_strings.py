"""Display strings (StringTable::LoadLanguage, Common.cpp:290-311) and the Common.h macros."""

from __future__ import annotations

import pytest

from mhp3ass.data.languages import language_folders
from mhp3ass.data.strings import DisplayStrings, StringIndex, load_strings, strip_ampersands


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
def ampersand_strings():
    text = tuple(["E&xit", *([""] * (len(StringIndex) - 1))])
    return DisplayStrings(text=text)


def test_every_shipped_language_has_all_strings(legacy_data_dir):
    languages_dir = legacy_data_dir / "Languages"

    counts = {
        folder: len(load_strings(languages_dir / folder).text)
        for folder in language_folders(languages_dir)
    }

    assert counts == dict.fromkeys(language_folders(languages_dir), 87)


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

    with pytest.raises(ValueError, match="86 of 87"):
        load_strings(folder)


def test_strip_ampersands_removes_every_ampersand():
    assert strip_ampersands("&Save && E&xit") == "Save  Exit"


def test_macros_add_spaces_and_colons(ampersand_strings):
    index = StringIndex.FILE

    assert [
        ampersand_strings.static(index),
        ampersand_strings.add(index),
        ampersand_strings.run(index),
        ampersand_strings.start(index),
        ampersand_strings.basic(index),
        ampersand_strings.colon(index),
    ] == ["E&xit", " E&xit", " E&xit ", "E&xit ", "Exit", "E&xit: "]
