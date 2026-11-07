"""Charm comparisons against the harness's dump under each relevant-flag set (ModelDump.cpp)."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest

from mhp3ass.charms.comparison import (
    add_charm_to_optimal_list,
    basically_the_same_as,
    strictly_better_than,
)
from mhp3ass.charms.naming import charm_name, charms_equal
from mhp3ass.model import AbilityPair, Charm


@pytest.fixture(scope="module")
def flag_game(load_teamhgg_game):
    """A game of its own: these tests set the abilities' relevant flags."""
    return load_teamhgg_game()


@pytest.fixture
def set_relevant(flag_game):
    """Sets exactly the given abilities relevant; restores the loaded flags afterwards."""
    loaded_flags = [ability.relevant for ability in flag_game.abilities]

    def apply(indices: list[int]) -> None:
        for ability in flag_game.abilities:
            ability.relevant = False
        for index in indices:
            flag_game.abilities[index].relevant = True

    yield apply
    for ability, flag in zip(flag_game.abilities, loaded_flags, strict=True):
        ability.relevant = flag


@pytest.fixture(scope="module")
def comparisons(models_golden):
    return models_golden["charm_comparisons"]


@pytest.fixture(scope="module")
def sample_charms(comparisons, flag_game):
    charms = [
        Charm(
            num_slots=entry["num_slots"],
            abilities=[
                AbilityPair(ability=flag_game.abilities[pair["ability"]], amount=pair["amount"])
                for pair in entry["abilities"]
            ],
        )
        for entry in comparisons["charms"]
    ]
    return charms


def _matrix(charms: list[Charm], compare: Callable[[Charm, Charm], bool]) -> list[str]:
    rows: list[str] = ["".join("1" if compare(a, b) else "0" for b in charms) for a in charms]
    return rows


def _optimal_indices(charms: list[Charm], order: list[Charm]) -> list[int]:
    optimal: list[Charm] = []
    for charm in order:
        add_charm_to_optimal_list(optimal, charm)
    indices = [next(i for i, sample in enumerate(charms) if sample is charm) for charm in optimal]
    return indices


def test_sample_names_match_golden(comparisons, sample_charms):
    assert [charm_name(charm) for charm in sample_charms] == [
        entry["name"] for entry in comparisons["charms"]
    ]


def test_value_equality_matches_golden(comparisons, sample_charms):
    assert _matrix(sample_charms, charms_equal) == comparisons["equal"]


def test_comparisons_match_golden_for_each_relevant_set(comparisons, sample_charms, set_relevant):
    mismatched: list[Any] = []
    for relevant_set in comparisons["relevant_sets"]:
        set_relevant(relevant_set["relevant"])
        ours = {
            "strictly_better_than": _matrix(sample_charms, strictly_better_than),
            "basically_the_same_as": _matrix(sample_charms, basically_the_same_as),
            "optimal_forward": _optimal_indices(sample_charms, sample_charms),
            "optimal_reverse": _optimal_indices(sample_charms, sample_charms[::-1]),
        }
        golden = {key: relevant_set[key] for key in ours}
        if ours != golden:
            mismatched.append(
                {"relevant": relevant_set["relevant"], "ours": ours, "golden": golden}
            )

    assert [len(comparisons["relevant_sets"]), mismatched] == [5, []]


def test_optimal_list_keeps_the_first_of_two_basically_same_charms(flag_game, set_relevant):
    # Only Attack is relevant, so the charms differ only in an ability the search ignores.
    set_relevant([0])
    attack, expert = flag_game.abilities[0], flag_game.abilities[1]
    first = Charm(
        num_slots=1,
        abilities=[AbilityPair(ability=attack, amount=3), AbilityPair(ability=expert, amount=1)],
    )
    more_irrelevant_points = Charm(
        num_slots=1,
        abilities=[AbilityPair(ability=attack, amount=3), AbilityPair(ability=expert, amount=4)],
    )
    optimal: list[Charm] = []
    for charm in (first, more_irrelevant_points):
        add_charm_to_optimal_list(optimal, charm)

    assert [len(optimal), optimal[0] is first] == [1, True]
