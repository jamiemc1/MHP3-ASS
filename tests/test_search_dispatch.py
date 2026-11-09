"""``worker_charms`` (StartSearch's dispatch) against every search manifest the
harness wrote, plus the dispatch rules no manifest reaches."""

from __future__ import annotations

from typing import Any

import pytest

from goldens import FuzzGolden, SearchGolden
from mhp3ass.charms.my_charms import load_query_my_charms, my_charms_illegal
from mhp3ass.charms.naming import charm_name
from mhp3ass.model import AbilityPair, Charm
from mhp3ass.query import CharmMode, Query, SearchSpec
from mhp3ass.relevance import formulate_query
from mhp3ass.search import SearchData, worker_charms


def _dispatch_mismatches(
    goldens: list[SearchGolden] | list[FuzzGolden], search_data: dict[str, SearchData]
) -> list[dict[str, Any]]:
    mismatches = []
    for golden in goldens:
        spec = SearchSpec.from_json(golden.query)
        data = search_data[spec.query.language]
        loaded = load_query_my_charms(list(spec.my_charms), game=data.game, validity=data.validity)
        query = formulate_query(data.game, spec.query)
        workers = worker_charms(
            query, charm_mode=spec.charm_mode, my_charms=loaded.charms, tables=data.tables
        )
        ours = {
            "my_charms_loaded": len(loaded.charms),
            "my_charms_illegal": my_charms_illegal(loaded),
            "worker_count": len(workers),
            "charms": [None if charm is None else charm_name(charm) for charm in workers],
        }
        manifest = golden.manifest
        expected = {
            "my_charms_loaded": manifest["my_charms_loaded"],
            "my_charms_illegal": manifest["my_charms_illegal"],
            "worker_count": manifest["worker_count"],
            "charms": [worker["charm"] for worker in manifest["workers"]],
        }
        if ours != expected:
            mismatches.append({"id": manifest["id"], "ours": ours, "expected": expected})
    return mismatches


def test_workers_match_every_corpus_and_fuzz_manifest(
    search_goldens, fuzz_goldens, search_data_by_language
):
    corpus = _dispatch_mismatches(search_goldens, search_data_by_language)
    fuzz = _dispatch_mismatches(fuzz_goldens, search_data_by_language)

    assert [len(search_goldens), len(fuzz_goldens), corpus, fuzz] == [10, 500, [], []]


def test_workers_match_every_personal_manifest(personal_search_goldens, search_data_by_language):
    assert _dispatch_mismatches(personal_search_goldens, search_data_by_language) == []


@pytest.fixture
def teamhgg_search_data(search_data_by_language) -> SearchData:
    return search_data_by_language["English (TeamHGG)"]


@pytest.fixture
def formulate(teamhgg_search_data, attack_sharp_query_json):
    """Formulates the Attack Up [Med] + Sharp Sword query, or the given skills instead."""

    def make(skills: list[int] | None = None) -> Query:
        game = teamhgg_search_data.game
        if skills is not None:
            attack_sharp_query_json.update(
                skills=skills, skill_names=[game.skills[index].name for index in skills]
            )
        spec = SearchSpec.from_json(
            {**attack_sharp_query_json, "charm_mode": "none", "my_charms": []}
        )
        query = formulate_query(game, spec.query)
        return query

    return make


@pytest.fixture
def auto_guard_index(teamhgg_search_data) -> int:
    index = next(
        index
        for index, skill in enumerate(teamhgg_search_data.game.skills)
        if skill.ability.auto_guard and skill.points_required > 0
    )
    return index


def _charm(num_slots: int, *pairs: tuple[Any, int]) -> Charm:
    charm = Charm(
        num_slots=num_slots,
        abilities=[AbilityPair(ability=ability, amount=amount) for ability, amount in pairs],
        custom=True,
    )
    return charm


@pytest.mark.parametrize(
    "charm_mode", [CharmMode.SLOTTED, CharmMode.ONE_SKILL, CharmMode.TWO_SKILL]
)
def test_auto_guard_takes_the_first_single_auto_guard_charm(
    formulate, auto_guard_index, teamhgg_search_data, charm_mode
):
    query = formulate(skills=[1, auto_guard_index])
    attack, auto_guard = (skill.ability for skill in query.skills)
    my_charms = [
        _charm(3, (attack, 4)),
        _charm(0, (auto_guard, 10), (attack, 1)),
        _charm(0, (auto_guard, -2)),
        _charm(2, (auto_guard, 10)),
    ]

    workers = worker_charms(
        query, charm_mode=charm_mode, my_charms=my_charms, tables=teamhgg_search_data.tables
    )

    assert [len(workers), workers[0] is my_charms[2]] == [1, True]


def test_auto_guard_without_its_charm_starts_no_worker(
    formulate, auto_guard_index, teamhgg_search_data
):
    query = formulate(skills=[1, auto_guard_index])
    attack, auto_guard = (skill.ability for skill in query.skills)
    my_charms = [_charm(0, (auto_guard, 10), (attack, 1))]

    workers = worker_charms(
        query,
        charm_mode=CharmMode.ONE_SKILL,
        my_charms=my_charms,
        tables=teamhgg_search_data.tables,
    )

    assert workers == []


@pytest.mark.parametrize(
    ("charm_mode", "expected"),
    [(CharmMode.NONE, [None]), (CharmMode.MY_CHARMS, [None, 0])],
)
def test_auto_guard_is_not_special_in_none_and_my_charms_modes(
    formulate, auto_guard_index, teamhgg_search_data, charm_mode, expected
):
    query = formulate(skills=[1, auto_guard_index])
    auto_guard = query.skills[1].ability
    my_charms = [_charm(0, (auto_guard, 10))]

    workers = worker_charms(
        query, charm_mode=charm_mode, my_charms=my_charms, tables=teamhgg_search_data.tables
    )

    assert workers == [None if position is None else my_charms[position] for position in expected]


@pytest.mark.parametrize("charm_mode", list(CharmMode))
def test_no_skills_starts_no_worker(formulate, teamhgg_search_data, charm_mode):
    query = formulate(skills=[])
    my_charms = [_charm(3, (teamhgg_search_data.game.abilities[0], 4))]

    workers = worker_charms(
        query, charm_mode=charm_mode, my_charms=my_charms, tables=teamhgg_search_data.tables
    )

    assert workers == []


def test_slotted_mode_searches_one_bare_three_slot_charm(formulate, teamhgg_search_data):
    query = formulate()

    workers = worker_charms(
        query, charm_mode=CharmMode.SLOTTED, my_charms=[], tables=teamhgg_search_data.tables
    )

    assert [
        [(charm.num_slots, charm.abilities, charm.custom) for charm in workers if charm is not None]
    ] == [[(3, [], False)]]


def test_my_charms_drop_a_trade_off_with_the_same_relevant_skills(formulate, teamhgg_search_data):
    """Quirk 1: BasicallyTheSameAs ignores amounts, so the second charm is
    dropped although neither is strictly better."""
    query = formulate()
    attack, sharpness = (skill.ability for skill in query.skills)
    first = _charm(0, (attack, 5), (sharpness, 1))
    trade_off = _charm(0, (attack, 3), (sharpness, 2))

    workers = worker_charms(
        query,
        charm_mode=CharmMode.MY_CHARMS,
        my_charms=[first, trade_off],
        tables=teamhgg_search_data.tables,
    )

    assert workers == [None, first]


def test_my_charms_compare_with_the_last_formulated_query(formulate, teamhgg_search_data):
    """The comparisons read the game's relevance flags, not the query's skills."""
    query = formulate()
    attack, sharpness = (skill.ability for skill in query.skills)
    first = _charm(0, (attack, 5), (sharpness, 1))
    more_sharpness = _charm(0, (attack, 3), (sharpness, 2))
    formulate(skills=[12])

    workers = worker_charms(
        query,
        charm_mode=CharmMode.MY_CHARMS,
        my_charms=[first, more_sharpness],
        tables=teamhgg_search_data.tables,
    )

    assert workers == [None, more_sharpness]
