"""The L3 gate: every corpus query's full search against the harness's goldens.

For each query, one ``run_search`` (run once per session) must give the
harness's manifest field for field (workers, counts, every hash), its
solution lines in order, and, for the ``gui_order_dependent`` queries, every
worker's solutions before duplicate removal. Personal queries (built from a
save) are checked the same way when ``tests/savefile/`` holds them.

The default run searches in the session's process pool; ``pytest -m fuzz``
also runs every query with the workers in turn, the reference path.
"""

from __future__ import annotations

import pytest

from goldens import SearchGolden
from mhp3ass.search import SearchData, WorkerPool
from search_comparison import SearchComparison, compare_search, differences


def _compare(
    golden: SearchGolden, search_data: dict[str, SearchData], pool: WorkerPool | None
) -> SearchComparison:
    comparison = compare_search(
        query=golden.query,
        manifest=golden.manifest,
        golden_lines=golden.solution_lines,
        golden_candidates=golden.candidates,
        search_data=search_data,
        max_solution_lines=-1,
        pool=pool,
    )
    return comparison


@pytest.fixture(scope="session")
def public_comparisons(
    search_goldens, search_data_by_language, search_pool
) -> list[SearchComparison]:
    comparisons = [
        _compare(golden, search_data_by_language, pool=search_pool) for golden in search_goldens
    ]
    return comparisons


@pytest.fixture(scope="session")
def personal_comparisons(
    personal_search_goldens, search_data_by_language, search_pool
) -> list[SearchComparison]:
    comparisons = [
        _compare(golden, search_data_by_language, pool=search_pool)
        for golden in personal_search_goldens
    ]
    return comparisons


@pytest.fixture(scope="session")
def serial_comparisons(
    search_goldens, personal_search_goldens, search_data_by_language
) -> list[SearchComparison]:
    comparisons = [
        _compare(golden, search_data_by_language, pool=None)
        for golden in [*search_goldens, *personal_search_goldens]
    ]
    return comparisons


@pytest.mark.parametrize("part", ["manifest", "solution_lines", "candidates"])
def test_search_matches_the_harness(public_comparisons, part):
    assert [len(public_comparisons), differences(public_comparisons, part)] == [10, {}]


def test_every_order_dependent_query_compares_candidates(search_goldens):
    with_candidates = [golden.manifest["id"] for golden in search_goldens if golden.candidates]

    assert with_candidates == ["g03", "g04", "g13"]


@pytest.mark.parametrize("part", ["manifest", "solution_lines", "candidates"])
def test_personal_search_matches_the_harness(personal_comparisons, part):
    assert [len(personal_comparisons), differences(personal_comparisons, part)] == [12, {}]


@pytest.mark.fuzz
@pytest.mark.parametrize("part", ["manifest", "solution_lines", "candidates"])
def test_search_with_the_workers_in_turn_matches_the_harness(serial_comparisons, part):
    assert [len(serial_comparisons), differences(serial_comparisons, part)] == [22, {}]
