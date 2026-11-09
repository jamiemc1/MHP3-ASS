"""``paused_gc`` around a search: collection off inside, previous state restored after."""

from __future__ import annotations

import gc

import pytest

from mhp3ass.query import QuerySpec
from mhp3ass.relevance import formulate_query
from mhp3ass.search import paused_gc, run_worker
from mhp3ass.solution.state import LegacyNullReferenceError
from solution_trace import template_charm


@pytest.fixture
def gc_enabled():
    """Cyclic GC on at the start of the test, and on again afterwards whatever the test did."""
    gc.enable()
    yield
    gc.enable()


@pytest.fixture
def gc_disabled():
    """Cyclic GC off at the start of the test, and on again afterwards."""
    gc.disable()
    yield
    gc.enable()


@pytest.fixture
def t05_throwing_worker(trace_goldens, scratch_game):
    """t05's query (every armour slot empty) and worker 1's charm template
    (``+5 Poison O--``), whose search raises in ``PotentialSpareSlots``."""
    golden = next(golden for golden in trace_goldens if golden.query["id"] == "t05")
    query = formulate_query(scratch_game, QuerySpec.from_json(golden.query))
    template = template_charm(golden.header["workers"][1]["template"], scratch_game)
    return query, template


def test_collection_is_off_inside_and_back_on_after(gc_enabled):
    with paused_gc():
        inside = gc.isenabled()
    assert inside is False
    assert gc.isenabled() is True


def test_collection_stays_off_when_it_was_off_before(gc_disabled):
    with paused_gc():
        pass
    assert gc.isenabled() is False


def test_collection_is_back_on_after_a_worker_raises(gc_enabled, t05_throwing_worker, scratch_game):
    query, template = t05_throwing_worker
    with pytest.raises(LegacyNullReferenceError), paused_gc():
        run_worker(query, template, scratch_game)
    assert gc.isenabled() is True


def test_search_leaves_no_cyclic_garbage(gc_enabled, attack_sharp_query_json, scratch_game):
    query = formulate_query(scratch_game, QuerySpec.from_json(attack_sharp_query_json))
    gc.collect()
    with paused_gc():
        solutions = run_worker(query, None, scratch_game)
    solution_count = len(solutions)
    del solutions
    unreachable = gc.collect()
    assert solution_count > 0
    assert unreachable == 0
