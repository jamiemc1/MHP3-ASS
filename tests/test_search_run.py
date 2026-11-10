"""``run_search``'s worker loop, exception recording and progress, with the
workers run in turn and in the session's process pool, on the trace query whose
search throws (t05: every armour slot empty, Poison charms) and on g13."""

from __future__ import annotations

import json
from math import prod

import pytest

from mhp3ass.charms.naming import charm_name
from mhp3ass.decorations import NoDecorationsError
from mhp3ass.parallel import SearchPool
from mhp3ass.query import SearchSpec
from mhp3ass.results.result_set import candidate_lines, search_manifest, solution_lines
from mhp3ass.search import armor_choices, dotnet_exception_type, run_search
from mhp3ass.solution.charm_reduction import LegacyListIndexError
from mhp3ass.solution.fill import UndefinedScoreError
from mhp3ass.solution.state import LegacyNullReferenceError


@pytest.fixture(params=["serial", "pool"])
def pool(request, search_pool) -> SearchPool | None:
    """No pool (the workers run in turn), then the session's pool."""
    chosen = search_pool if request.param == "pool" else None
    return chosen


@pytest.fixture(scope="module")
def empty_armor_spec(repo_root) -> SearchSpec:
    path = repo_root / "tests" / "traces" / "queries" / "t05-empty-armor-my-charms.json"
    return SearchSpec.from_file(path)


@pytest.fixture(scope="module")
def one_skill_spec(repo_root) -> SearchSpec:
    """g13: four one-skill workers."""
    path = repo_root / "tests" / "corpus" / "g13-hr3-attack-health-one-skill.json"
    return SearchSpec.from_file(path)


def test_a_throwing_worker_is_recorded_and_stops_the_search(
    empty_armor_spec, search_data_by_language, pool
):
    data = search_data_by_language[empty_armor_spec.query.language]

    result = run_search(empty_armor_spec, data=data, record_exceptions=True, pool=pool)

    exception = result.exception
    assert [
        None if exception is None else [exception.worker, exception.type],
        [
            None if worker.template is None else charm_name(worker.template)
            for worker in result.workers
        ],
        result.worker_count,
    ] == [[1, "NullReferenceException"], [None], 3]


def test_without_recording_the_worker_error_propagates(
    empty_armor_spec, search_data_by_language, pool
):
    data = search_data_by_language[empty_armor_spec.query.language]

    with pytest.raises(LegacyNullReferenceError):
        run_search(empty_armor_spec, data=data, pool=pool)


def test_empty_slots_are_padded_on_a_copy(empty_armor_spec, search_data_by_language):
    """DoWork pads the shared query's empty lists (Form1.h:1865-1869); the port
    pads a copy per worker, so the query's lists stay as relevance left them."""
    data = search_data_by_language[empty_armor_spec.query.language]
    query = run_search(empty_armor_spec, data=data, record_exceptions=True).query

    assert [query.rel_armor, armor_choices(query)] == [[[]] * 5, [[None]] * 5]


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (LegacyNullReferenceError("null"), "NullReferenceException"),
        (LegacyListIndexError("index"), "ArgumentOutOfRangeException"),
        (NoDecorationsError("none"), "KeyNotFoundException"),
        (KeyError("key"), "KeyNotFoundException"),
        (IndexError("index"), "IndexOutOfRangeException"),
        (UndefinedScoreError("score"), None),
        (ValueError("value"), None),
    ],
)
def test_port_errors_map_to_the_dotnet_exceptions_they_stand_for(error, expected):
    assert dotnet_exception_type(error) == expected


def test_each_finished_worker_is_reported_in_order(one_skill_spec, search_data_by_language, pool):
    reports = []

    result = run_search(
        one_skill_spec,
        data=search_data_by_language[one_skill_spec.query.language],
        on_worker_done=reports.append,
        pool=pool,
    )

    assert [
        [(report.number, report.worker_count) for report in reports],
        [report.worker for report in reports] == result.workers,
    ] == [[(0, 4), (1, 4), (2, 4), (3, 4)], True]


def test_progress_counts_every_combination_of_every_worker(
    one_skill_spec, search_data_by_language, pool
):
    reports: list[tuple[int, int]] = []

    result = run_search(
        one_skill_spec,
        data=search_data_by_language[one_skill_spec.query.language],
        pool=pool,
        on_progress=lambda done, total: reports.append((done, total)),
    )

    combinations = result.worker_count * prod(
        len(choices) for choices in armor_choices(result.query)
    )
    done = [report[0] for report in reports]
    assert [result.worker_count, {report[1] for report in reports}] == [4, {combinations}]
    assert done == sorted(done)
    assert reports[-1] == (combinations, combinations)


def test_progress_stops_short_when_a_worker_throws(empty_armor_spec, search_data_by_language, pool):
    reports: list[tuple[int, int]] = []

    run_search(
        empty_armor_spec,
        data=search_data_by_language[empty_armor_spec.query.language],
        record_exceptions=True,
        pool=pool,
        on_progress=lambda done, total: reports.append((done, total)),
    )

    assert reports[-1][0] < reports[-1][1] == 3


def test_the_pool_gives_the_serial_result(
    repo_root, one_skill_spec, search_data_by_language, search_pool
):
    """g13's workers repeat each other's sets, so the pool's duplicate removal
    on records must keep the serial search's solutions, worker by worker."""
    spec_json = json.loads(
        (repo_root / "tests" / "corpus" / "g13-hr3-attack-health-one-skill.json").read_text(
            encoding="utf-8-sig"
        )
    )
    data = search_data_by_language[one_skill_spec.query.language]
    manifests = []
    outputs = []

    for pool in (None, search_pool):
        result = run_search(one_skill_spec, data=data, record_exceptions=True, pool=pool)
        manifests.append(search_manifest(spec_json, result=result, game=data.game))
        outputs.append(
            [solution_lines(result, game=data.game), candidate_lines(result, game=data.game)]
        )

    removed = sum(worker["found"] - worker["added"] for worker in manifests[0]["workers"])
    assert removed > 0
    assert [manifests[1], outputs[1]] == [manifests[0], outputs[0]]
