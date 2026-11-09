"""Find Next (frmFind.h:135-144, Form1.h:1938-1953)."""

from __future__ import annotations

import pytest

from mhp3ass.results.find import TextSelection, find_next


@pytest.fixture
def results_text():
    """Two solutions under the header, as the results box holds them (``\\n`` line breaks)."""
    return "Solutions found: 2\n\nJinouga Helm\nAttack Jewel\n\nJinouga Helm\nRazor Jewel\n"


def test_finds_from_the_end_of_the_selection(results_text):
    first = results_text.index("Jinouga")
    second = results_text.index("Jinouga", first + 1)

    found = find_next(results_text, "Jinouga", TextSelection(start=first, length=7))

    assert found == TextSelection(start=second, length=7)


def test_no_further_match_moves_the_caret_to_the_end(results_text):
    last = results_text.rindex("Jinouga")

    found = find_next(results_text, "Jinouga", TextSelection(start=last, length=7))

    assert found == TextSelection(start=len(results_text), length=0)


def test_from_the_end_the_search_starts_again_at_the_top(results_text):
    found = find_next(results_text, "Jinouga", TextSelection(start=len(results_text), length=0))

    assert found == TextSelection(start=results_text.index("Jinouga"), length=7)


def test_the_header_is_searched_too(results_text):
    found = find_next(results_text, "found", TextSelection(start=0, length=0))

    assert found == TextSelection(start=10, length=5)


def test_matching_is_case_sensitive(results_text):
    found = find_next(results_text, "jinouga", TextSelection(start=0, length=0))

    assert found == TextSelection(start=len(results_text), length=0)


def test_an_empty_needle_changes_nothing(results_text):
    selection = TextSelection(start=3, length=2)

    assert find_next(results_text, "", selection) == selection
