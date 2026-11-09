"""``run_search``'s worker loop and exception recording, on the trace query whose
search throws (t05: every armour slot empty, Poison charms)."""

from __future__ import annotations

import pytest

from mhp3ass.charms.naming import charm_name
from mhp3ass.decorations import NoDecorationsError
from mhp3ass.query import SearchSpec
from mhp3ass.search import armor_choices, dotnet_exception_type, run_search
from mhp3ass.solution.charm_reduction import LegacyListIndexError
from mhp3ass.solution.fill import UndefinedScoreError
from mhp3ass.solution.state import LegacyNullReferenceError


@pytest.fixture(scope="module")
def empty_armor_spec(repo_root) -> SearchSpec:
    path = repo_root / "tests" / "traces" / "queries" / "t05-empty-armor-my-charms.json"
    return SearchSpec.from_file(path)


@pytest.fixture(scope="module")
def recorded_empty_armor_search(empty_armor_spec, search_data_by_language):
    data = search_data_by_language[empty_armor_spec.query.language]
    return run_search(empty_armor_spec, data=data, record_exceptions=True)


def test_a_throwing_worker_is_recorded_and_stops_the_search(recorded_empty_armor_search):
    result = recorded_empty_armor_search
    exception = result.exception

    assert [
        None if exception is None else [exception.worker, exception.type],
        [
            None if worker.template is None else charm_name(worker.template)
            for worker in result.workers
        ],
        result.worker_count,
    ] == [[1, "NullReferenceException"], [None], 3]


def test_without_recording_the_worker_error_propagates(empty_armor_spec, search_data_by_language):
    data = search_data_by_language[empty_armor_spec.query.language]

    with pytest.raises(LegacyNullReferenceError):
        run_search(empty_armor_spec, data=data)


def test_empty_slots_are_padded_on_a_copy(recorded_empty_armor_search):
    """DoWork pads the shared query's empty lists (Form1.h:1865-1869); the port
    pads a copy per worker, so the query's lists stay as relevance left them."""
    query = recorded_empty_armor_search.query

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
