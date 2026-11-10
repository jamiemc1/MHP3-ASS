"""``paused_gc`` around a search: collection off inside, previous state restored after."""

from __future__ import annotations

import gc

import pytest

from mhp3ass.query import QuerySpec, SearchSpec
from mhp3ass.relevance import formulate_query
from mhp3ass.search import paused_gc, run_search, run_worker
from mhp3ass.solution.state import LegacyNullReferenceError
from solution_trace import template_charm


@pytest.fixture
def gc_enabled():
    """Cyclic GC on for the test; the state from before the test restored afterwards."""
    was_enabled = gc.isenabled()
    gc.enable()
    yield
    if not was_enabled:
        gc.disable()


@pytest.fixture
def gc_disabled():
    """Cyclic GC off for the test; the state from before the test restored afterwards."""
    was_enabled = gc.isenabled()
    gc.disable()
    yield
    if was_enabled:
        gc.enable()


@pytest.fixture
def trace_worker(trace_goldens, scratch_game):
    """A traced query and one of its workers' charm templates, by query id and worker number."""

    def make(query_id, worker):
        golden = next(golden for golden in trace_goldens if golden.query["id"] == query_id)
        query = formulate_query(scratch_game, QuerySpec.from_json(golden.query))
        template = template_charm(golden.header["workers"][worker]["template"], scratch_game)
        return query, template

    return make


def test_collection_is_off_inside_and_back_on_after(gc_enabled):
    with paused_gc():
        inside = gc.isenabled()
    assert inside is False
    assert gc.isenabled() is True


def test_collection_stays_off_when_it_was_off_before(gc_disabled):
    with paused_gc():
        pass
    assert gc.isenabled() is False


def test_collection_is_back_on_after_a_worker_raises(gc_enabled, trace_worker, scratch_game):
    # t05 worker 1 (+5 Poison O--, every armour slot empty) throws in PotentialSpareSlots.
    query, template = trace_worker("t05", 1)
    with pytest.raises(LegacyNullReferenceError), paused_gc():
        run_worker(query, template, scratch_game)
    assert gc.isenabled() is True


@pytest.mark.parametrize(
    ("query_id", "worker"),
    [("1a", 1), ("g16", 0)],
    ids=["charm-template", "no-charm"],
)
def test_search_leaves_no_cyclic_garbage(gc_enabled, trace_worker, scratch_game, query_id, worker):
    query, template = trace_worker(query_id, worker)
    gc.collect()
    with paused_gc():
        solutions = run_worker(query, template, scratch_game)
    charmed_count = sum(solution.charm is not None for solution in solutions)
    solution_count = len(solutions)
    del solutions
    unreachable = gc.collect()
    assert solution_count > 0
    assert (charmed_count > 0) == (template is not None)
    assert unreachable == 0


@pytest.fixture(params=["serial", "pool"])
def pool(request, search_pool):
    """No pool (the workers run in turn), then the session's pool."""
    chosen = search_pool if request.param == "pool" else None
    return chosen


def test_run_search_pauses_collection_and_restores_it_when_a_worker_raises(
    gc_enabled, repo_root, search_data_by_language, pool
):
    """t05's worker 1 throws; ``on_worker_done`` sees collection off for worker 0."""
    spec = SearchSpec.from_file(
        repo_root / "tests" / "traces" / "queries" / "t05-empty-armor-my-charms.json"
    )
    seen = []

    with pytest.raises(LegacyNullReferenceError):
        run_search(
            spec,
            data=search_data_by_language[spec.query.language],
            on_worker_done=lambda progress: seen.append(gc.isenabled()),
            pool=pool,
        )

    assert [seen, gc.isenabled()] == [[False], True]
