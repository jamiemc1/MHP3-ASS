"""Find Next in the results text: case-insensitive, wrapping to the top."""

from __future__ import annotations

import pytest

from mhp3ass.results.find import TextSelection, find_next


@pytest.fixture
def results_text():
    """Two solutions that share a helm."""
    return "Jinouga Helm\nAttack Jewel\n\nJinouga Helm\nRazor Jewel\n"


def test_finds_from_the_end_of_the_selection(results_text):
    first = results_text.index("Jinouga")
    second = results_text.index("Jinouga", first + 1)

    found = find_next(results_text, "Jinouga", TextSelection(start=first, length=7))

    assert found == TextSelection(start=second, length=7)


def test_after_the_last_match_it_wraps_to_the_first(results_text):
    last = results_text.rindex("Jinouga")

    found = find_next(results_text, "Jinouga", TextSelection(start=last, length=7))

    assert found == TextSelection(start=results_text.index("Jinouga"), length=7)


def test_a_single_match_is_found_again(results_text):
    razor = results_text.index("Razor")

    found = find_next(results_text, "Razor", TextSelection(start=razor, length=5))

    assert found == TextSelection(start=razor, length=5)


def test_matching_ignores_case(results_text):
    found = find_next(results_text, "rAzOr jEwEl", TextSelection(start=0, length=0))

    assert found == TextSelection(start=results_text.index("Razor Jewel"), length=11)


def test_offsets_index_the_original_text_when_case_folding_changes_length():
    """``"ß".casefold()`` is ``"ss"``; the match must still point into the unfolded text."""
    text = "Straße\nStrasse"

    found = find_next(text, "STRASSE", TextSelection(start=0, length=0))

    assert found == TextSelection(start=text.index("Strasse"), length=7)


def test_no_match_anywhere_finds_nothing(results_text):
    assert find_next(results_text, "Rathalos", TextSelection(start=0, length=0)) is None


def test_an_empty_needle_finds_nothing(results_text):
    assert find_next(results_text, "", TextSelection(start=3, length=2)) is None


def test_empty_text_finds_nothing():
    assert find_next("", "Jinouga", TextSelection(start=0, length=0)) is None


def test_a_selection_past_the_text_raises(results_text):
    with pytest.raises(ValueError, match="reaches past"):
        find_next(results_text, "Jinouga", TextSelection(start=len(results_text), length=1))


def test_a_negative_selection_raises():
    with pytest.raises(ValueError, match="negatively"):
        TextSelection(start=-5, length=0)
