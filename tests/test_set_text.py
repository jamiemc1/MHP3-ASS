"""One set as Markdown, on g13's sets (HR 3, Attack Up + Health, one-skill
charms) and on built ones."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import pytest

from mhp3ass.data import GameData
from mhp3ass.model import ArmorType
from mhp3ass.results.details import (
    ArmorLine,
    ChestJewels,
    CorrectedJewels,
    SolutionDetails,
    solution_details,
)
from mhp3ass.results.placement import place_can_matter
from mhp3ass.results.result_set import SearchResult
from mhp3ass.results.set_text import set_heading, set_markdown
from mhp3ass.results.sorting import SortKey
from mhp3ass.solution.state import Solution


@dataclass(frozen=True)
class SetSearch:
    result: SearchResult
    game: GameData


@dataclass(frozen=True)
class DetailedSet:
    solution: Solution
    details: SolutionDetails


@pytest.fixture(scope="module")
def one_skill_sets(pooled_searches, search_data_by_language) -> SetSearch:
    """g13's search, in English (TeamHGG), with the game its sets are filled in again."""
    search = SetSearch(
        result=pooled_searches["g13"], game=search_data_by_language["English (TeamHGG)"].game
    )
    return search


def _first(
    search: SetSearch,
    chosen: Callable[[Solution], bool],
    shown: Callable[[SolutionDetails], bool],
) -> DetailedSet:
    """The first of the search's ``chosen`` sets whose worked-out details are ``shown``."""
    for solution in search.result.results.all_solutions:
        if not chosen(solution):
            continue
        details = solution_details(
            solution, query=search.result.query, sort_key=SortKey.NONE, refill_game=search.game
        )
        if shown(details):
            return DetailedSet(solution=solution, details=details)
    raise LookupError("no such set in the search")


def _markdown(found: DetailedSet, search: SetSearch, strings, short_names) -> str:
    text = set_markdown(
        found.solution,
        found.details,
        query=search.result.query,
        strings=strings,
        short_names=short_names,
    )
    return text


def test_a_set_without_torso_inc_lists_its_jewels_together(
    one_skill_sets, english_strings, teamhgg_short_names
):
    found = _first(
        one_skill_sets,
        chosen=lambda solution: solution.charm is not None and not place_can_matter(solution),
        shown=lambda details: len(details.extra_skills) == 1,
    )

    text = _markdown(found, one_skill_sets, english_strings, teamhgg_short_names)

    assert text == (
        "## Baggi Cap · Zuwaro Mantle · Chain · Chain Belt · Ranguro\n"
        "\n"
        "Blademaster ♂ · HR 3 · Village Quests 4\n"
        "\n"
        "| Slot | Item |\n"
        "|---|---|\n"
        "| Head | Baggi Cap |\n"
        "| Body | Zuwaro Mantle |\n"
        "| Arms | Chain Vambraces |\n"
        "| Waist | Chain Belt |\n"
        "| Legs | Ranguro Greaves (or anything with Torso Inc) |\n"
        "| Charm | +3 Attack --- |\n"
        "| Jewels | 3x Attack Jewel[1] |\n"
        "\n"
        "- Spare: 0 slots spare\n"
        "- Skills: Attack Up [Sm], Health +20, Health +50\n"
    )


def test_a_torso_inc_set_lists_its_chest_jewels_apart(
    one_skill_sets, english_strings, teamhgg_short_names
):
    found = _first(
        one_skill_sets,
        chosen=lambda solution: solution.charm is not None,
        shown=lambda details: isinstance(details.chest_jewels, ChestJewels),
    )

    text = _markdown(found, one_skill_sets, english_strings, teamhgg_short_names)

    assert text == (
        "## Baggi Cap · Rathian · Chain · Chain Belt · Ranguro\n"
        "\n"
        "Blademaster ♂ · HR 3 · Village Quests 4\n"
        "\n"
        "| Slot | Item |\n"
        "|---|---|\n"
        "| Head | Baggi Cap |\n"
        "| Body | Rathian Mail |\n"
        "| Arms | Chain Vambraces |\n"
        "| Waist | Chain Belt |\n"
        "| Legs | Ranguro Greaves (or anything with Torso Inc) |\n"
        "| Charm | +1 Attack --- |\n"
        "| Chest x2 | 1x Attack Jewel[1] |\n"
        "| Elsewhere | 3x Attack Jewel[1] |\n"
        "\n"
        "- Spare: 0 slots spare\n"
        "- Skills: Attack Up [Sm], Health +20\n"
    )


def test_a_set_whose_listed_jewels_dont_fit_lists_the_jewels_that_build_it(
    one_skill_sets, english_strings, teamhgg_short_names
):
    """Quirk 52: the set's own jewels (2x Health Jewel[1], Attack Jewel[1],
    Attack Jewel[2]) have no placement, so the text has the inspector's."""
    found = _first(
        one_skill_sets,
        chosen=lambda solution: solution.charm is not None,
        shown=lambda details: (
            isinstance(details.chest_jewels, CorrectedJewels)
            and not details.chest_jewels.charm_changed
        ),
    )

    text = _markdown(found, one_skill_sets, english_strings, teamhgg_short_names)

    assert sorted(decoration.name for decoration in found.solution.decorations) == [
        "Attack Jewel[1]",
        "Attack Jewel[2]",
        "Health Jewel[1]",
        "Health Jewel[1]",
    ]
    assert text == (
        "## Baggi Cap · Yamato Plate · Chain · Chain Belt · Ranguro\n"
        "\n"
        "Blademaster ♂ · HR 3 · Village Quests 4\n"
        "\n"
        "| Slot | Item |\n"
        "|---|---|\n"
        "| Head | Baggi Cap |\n"
        "| Body | Yamato Plate (or anything with 2 slots) |\n"
        "| Arms | Chain Vambraces |\n"
        "| Waist | Chain Belt |\n"
        "| Legs | Ranguro Greaves (or anything with Torso Inc) |\n"
        "| Charm | +1 Attack --- |\n"
        "| Jewels | (the listed jewels don't fit; these build it) |\n"
        "| Chest x2 | 1x Attack Jewel[2] |\n"
        "| Elsewhere | 3x Health Jewel[1] |\n"
        "\n"
        "- Spare: 0 slots spare\n"
        "- Skills: Attack Up [Sm], Health +20\n"
    )


def test_a_set_only_another_charm_builds_names_that_charm_under_its_own(
    one_skill_sets, english_strings, teamhgg_short_names
):
    found = _first(
        one_skill_sets,
        chosen=lambda solution: solution.charm is not None,
        shown=lambda details: (
            isinstance(details.chest_jewels, CorrectedJewels) and details.chest_jewels.charm_changed
        ),
    )

    text = _markdown(found, one_skill_sets, english_strings, teamhgg_short_names)

    assert (
        "| Charm | +1 Attack --- |\n"
        "| Jewels | (the listed charm and jewels don't fit; these build it) |\n"
        "| Builds with | +3 Attack O-- |\n"
        "| Chest x3 | 1x Attack Jewel[1] |\n"
        "|  | 1x Health Jewel[1] |\n"
        "| Elsewhere | 2x Attack Jewel[1] |\n"
        "\n"
    ) in text


def test_a_charmless_set_says_it_has_no_charm(one_skill_sets, english_strings, teamhgg_short_names):
    found = _first(
        one_skill_sets,
        chosen=lambda solution: solution.charm is None,
        shown=lambda details: details.chest_jewels is None,
    )

    text = _markdown(found, one_skill_sets, english_strings, teamhgg_short_names)

    assert text == (
        "## Baggi Cap · Baggi · Chain · Chain Belt · Barroth\n"
        "\n"
        "Blademaster ♂ · HR 3 · Village Quests 4\n"
        "\n"
        "| Slot | Item |\n"
        "|---|---|\n"
        "| Head | Baggi Cap |\n"
        "| Body | Baggi Mail |\n"
        "| Arms | Chain Vambraces |\n"
        "| Waist | Chain Belt |\n"
        "| Legs | Barroth Greaves |\n"
        "| Charm | no charm |\n"
        "| Jewels | 3x Health Jewel[1] |\n"
        "|  | 1x Attack Jewel[1] |\n"
        "\n"
        "- Spare: 2 slots spare\n"
        "- Skills: Attack Up [Sm], Health +20\n"
    )


def test_the_heading_leaves_out_an_empty_slot(teamhgg_game, teamhgg_short_names):
    armor_map = teamhgg_game.armor_map
    solution = Solution(
        armors=[armor_map["Jinouga Helm"], armor_map["Agnaktor Mail"], None, None, None],
        charm=None,
    )

    heading = set_heading(solution, teamhgg_short_names)

    assert heading == (
        f"## {teamhgg_short_names.armor('Jinouga Helm', slot=ArmorType.HEAD)}"
        f" · {teamhgg_short_names.armor('Agnaktor Mail', slot=ArmorType.BODY)}"
    )
    assert heading.count(" · ") == 1


@pytest.mark.parametrize(
    ("name", "cell"),
    [("Odd|Helm", "Odd\\|Helm"), ("Odd\\", "Odd\\\\"), ("Odd\\|Helm", "Odd\\\\\\|Helm")],
)
def test_a_bar_or_backslash_in_a_name_stays_in_its_cell(
    make_armor, make_query, english_strings, teamhgg_short_names, name, cell
):
    piece = make_armor(name=name)
    details = SolutionDetails(
        armors=(ArmorLine(slot=ArmorType.HEAD, armor=piece, note=None),),
        charm=None,
        decorations=(),
        chest_jewels=None,
        slots_spare=None,
        extra_skills=(),
    )

    text = set_markdown(
        Solution(armors=[piece, None, None, None, None], charm=None),
        details,
        query=make_query(),
        strings=english_strings,
        short_names=teamhgg_short_names,
    )

    assert f"| Head | {cell} |\n" in text
    assert f"| Head | {name} |" not in text
