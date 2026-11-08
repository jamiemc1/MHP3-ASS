"""FindCharm2 and the charm tooltip's name parser against the harness."""

from __future__ import annotations

from typing import Any

import pytest

from mhp3ass.charms.location import (
    CharmLocation,
    CharmLocationIndex,
    CharmLocationQuery,
    CharmNameError,
    find_charm_location,
    parse_charm_name,
)
from mhp3ass.charms.naming import charm_name
from mhp3ass.data import GameData
from mhp3ass.model import Ability, AbilityPair, Charm


def _ability(game: GameData, index: int | None) -> Ability | None:
    ability = None if index is None else game.abilities[index]
    return ability


def _example_shape(example: Charm | None) -> Any:
    """The example as the harness writes it, without its name."""
    if example is None:
        return None
    shape = {
        "num_slots": example.num_slots,
        "abilities": [
            {"ability": pair.ability.static_index, "amount": pair.amount}
            for pair in example.abilities
        ],
    }
    return shape


def _golden_example_shape(example: dict[str, Any] | None) -> Any:
    if example is None:
        return None
    shape = {"num_slots": example["num_slots"], "abilities": example["abilities"]}
    return shape


def _differs(location: CharmLocation, record: dict[str, Any]) -> bool:
    differs = location.counts != record["table"] or _example_shape(
        location.example
    ) != _golden_example_shape(record["example"])
    return differs


def _find_charm2_mismatches(
    golden: Any, index: CharmLocationIndex, game: GameData
) -> list[dict[str, Any]]:
    mismatches = []
    for record in golden["find_charm2"]:
        query = CharmLocationQuery(
            ability1=_ability(game, record["ability1"]),
            points1=record["points1"],
            ability2=_ability(game, record["ability2"]),
            points2=record["points2"],
            num_slots=record["num_slots"],
        )
        location = find_charm_location(index, query)
        names_differ = (
            location.example is not None
            and charm_name(location.example) != record["example"]["name"]
        )
        if _differs(location, record) or names_differ:
            mismatches.append(record)
    return mismatches


def test_find_charm_location_matches_every_harness_call(
    charm_location_golden: Any, charm_location_index: CharmLocationIndex, teamhgg_game: GameData
):
    assert _find_charm2_mismatches(charm_location_golden, charm_location_index, teamhgg_game) == []


def test_harness_calls_cover_examples_and_every_branch(charm_location_golden: Any):
    """The fixture reaches one- and two-skill examples, the no-ability branch and wrapped points."""
    records = charm_location_golden["find_charm2"]
    one_skill_examples = [r for r in records if r["ability2"] is None and r["example"]]
    two_skill_examples = [r for r in records if r["ability2"] is not None and r["example"]]
    no_ability = [r for r in records if r["ability1"] is None]
    wrapped = [r for r in records if r["points1"] >= 2**31]

    assert one_skill_examples
    assert two_skill_examples
    assert len(no_ability) == 4
    assert wrapped


def _in_language(example: Charm, game: GameData) -> Charm:
    """The same charm with ``game``'s abilities, so its name is in ``game``'s language."""
    renamed = Charm(
        num_slots=example.num_slots,
        abilities=[
            AbilityPair(ability=game.abilities[pair.ability.static_index], amount=pair.amount)
            for pair in example.abilities
        ],
    )
    return renamed


def _parse_mismatches(
    golden: Any, index: CharmLocationIndex, games_by_language: dict[str, GameData]
) -> list[dict[str, Any]]:
    mismatches = []
    for record in golden["parse_and_find"]:
        game = games_by_language[record["language"]]
        try:
            query = parse_charm_name(record["name"], game)
        except CharmNameError as error:
            if error.dotnet_type != record["exception"]:
                mismatches.append(record)
            continue
        location = find_charm_location(index, query)
        if location.example is None:
            header = record["name"]
        else:
            header = charm_name(_in_language(location.example, game))
        if (
            record["exception"] is not None
            or _differs(location, record)
            or header != record["header"]
        ):
            mismatches.append(record)
    return mismatches


def test_parser_matches_harness_in_every_language(
    charm_location_golden: Any,
    charm_location_index: CharmLocationIndex,
    games_by_language: dict[str, GameData],
):
    assert _parse_mismatches(charm_location_golden, charm_location_index, games_by_language) == []


def test_parser_records_cover_every_language_and_exception(
    charm_location_golden: Any, games_by_language: dict[str, GameData]
):
    records = charm_location_golden["parse_and_find"]
    languages = {record["language"] for record in records}
    exceptions = {record["exception"] for record in records} - {None}

    assert languages == set(games_by_language)
    assert exceptions == {"FormatException", "OverflowException"}


def test_two_skill_name_drops_first_points_and_second_sign(teamhgg_game: GameData):
    """Quirk 7 (Common.cpp:182): points1 stays 0; the second amount loses its sign (:187)."""
    query = parse_charm_name("+4 Attack, -3 Sharpness ---", teamhgg_game)

    assert query == CharmLocationQuery(
        ability1=teamhgg_game.ability_map["Attack"],
        points1=0,
        ability2=teamhgg_game.ability_map["Sharpness"],
        points2=3,
        num_slots=0,
    )


def test_zero_second_skill_name_fails_to_parse(teamhgg_game: GameData):
    """GetName writes ", 0 Sharpness" with no sign, so the amount text is empty."""
    with pytest.raises(CharmNameError) as raised:
        parse_charm_name("+4 Attack, 0 Sharpness O--", teamhgg_game)

    assert raised.value.dotnet_type == "FormatException"


def test_negative_first_skill_name_overflows(teamhgg_game: GameData):
    with pytest.raises(CharmNameError) as raised:
        parse_charm_name("+-3 Attack ---", teamhgg_game)

    assert raised.value.dotnet_type == "OverflowException"


def test_slotted_charm_name_skips_parsing(teamhgg_game: GameData):
    query = parse_charm_name("OO-", teamhgg_game)

    assert query == CharmLocationQuery(
        ability1=None, points1=0, ability2=None, points2=0, num_slots=2
    )


def test_short_name_fails_like_substring(teamhgg_game: GameData):
    with pytest.raises(CharmNameError) as raised:
        parse_charm_name("O-", teamhgg_game)

    assert raised.value.dotnet_type == "ArgumentOutOfRangeException"


def test_unnamed_ability_at_ten_points_counts_nothing(
    charm_location_index: CharmLocationIndex, teamhgg_game: GameData
):
    """CharmDatabase.cpp:1044-1045, dead on shipped data (no ability has an empty name):
    an unnamed ability at +10 with no slots matches nothing, even where entries exist."""
    anti_theft = teamhgg_game.ability_map["Anti-Theft"]
    unnamed = Ability(name="", static_index=anti_theft.static_index)
    named_query = CharmLocationQuery(
        ability1=anti_theft, points1=10, ability2=None, points2=0, num_slots=0
    )
    unnamed_query = CharmLocationQuery(
        ability1=unnamed, points1=10, ability2=None, points2=0, num_slots=0
    )

    named = find_charm_location(charm_location_index, named_query)
    unnamed_location = find_charm_location(charm_location_index, unnamed_query)

    assert any(any(row) for row in named.counts)
    assert unnamed_location == CharmLocation(counts=[[0, 0, 0] for _ in range(12)], example=None)
