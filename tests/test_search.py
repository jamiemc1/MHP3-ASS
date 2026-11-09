"""The L3 gate: every corpus query's full search against the harness's goldens.

For each query, one ``run_search`` (run once per session) must give the
harness's manifest field for field (workers, counts, every hash), its
solution lines in order, and, for the ``gui_order_dependent`` queries, every
worker's solutions before duplicate removal. Personal queries (built from a
save) are checked the same way when ``tests/savefile/`` holds them.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

import pytest

from goldens import SearchGolden
from mhp3ass.query import SearchSpec
from mhp3ass.results.result_set import candidate_lines, search_manifest, solution_lines
from mhp3ass.search import SearchData, run_search


@dataclass(frozen=True)
class SearchComparison:
    """How one query's port search differs from its golden; empty when equal."""

    query_id: str
    manifest: str | None
    solution_lines: str | None
    candidates: str | None


def _comparable(manifest: dict[str, Any]) -> dict[str, Any]:
    # query_json is compared parsed: the harness's serialiser escapes differently.
    comparable = {**manifest, "query_json": json.loads(manifest["query_json"])}
    return comparable


def _manifest_difference(ours: dict[str, Any], golden: dict[str, Any]) -> str | None:
    ours = _comparable(ours)
    golden = _comparable(golden)
    if ours == golden:
        return None
    fields = sorted(key for key in ours.keys() | golden.keys() if ours.get(key) != golden.get(key))
    first_worker = None
    for number, golden_worker in enumerate(golden["workers"]):
        our_worker = ours["workers"][number] if number < len(ours["workers"]) else None
        if our_worker != golden_worker:
            first_worker = number
            break
    order_only = (
        ours["solutions_sha256"] != golden["solutions_sha256"]
        and ours["solution_set_sha256"] == golden["solution_set_sha256"]
    )
    difference = f"fields {fields}, first differing worker {first_worker}, order only {order_only}"
    return difference


def _lines_difference(ours: list[str], golden: list[str]) -> str | None:
    if ours == golden:
        return None
    our_set = set(ours)
    golden_set = set(golden)
    missing = [line for line in golden if line not in our_set][:10]
    extra = [line for line in ours if line not in golden_set][:10]
    difference = f"{len(ours)} lines vs {len(golden)}; missing {missing}; extra {extra}"
    return difference


def _rows_difference(
    ours: list[tuple[int, str, str]], expected: list[tuple[int, str, str]]
) -> str | None:
    """The first candidate row that differs, as (worker, charm name, line)."""
    if ours == expected:
        return None
    first = min(len(ours), len(expected))
    for index, (our_row, expected_row) in enumerate(zip(ours, expected, strict=False)):
        if our_row != expected_row:
            first = index
            break
    our_row = ours[first] if first < len(ours) else None
    expected_row = expected[first] if first < len(expected) else None
    difference = (
        f"{len(ours)} rows vs {len(expected)}; row {first}: ours {our_row}, harness {expected_row}"
    )
    return difference


def _compare(golden: SearchGolden, search_data: dict[str, SearchData]) -> SearchComparison:
    spec = SearchSpec.from_json(golden.query)
    data = search_data[spec.query.language]
    record_exceptions = "exception" in golden.manifest
    result = run_search(spec, data=data, record_exceptions=record_exceptions)
    manifest = search_manifest(golden.query, result=result, game=data.game)
    candidates_difference = None
    if golden.candidates is not None:
        ours = [
            (candidate.worker, candidate.charm_name, candidate.solution_line)
            for candidate in candidate_lines(result, game=data.game)
        ]
        expected = [
            (candidate.worker, candidate.charm_name, candidate.solution_line)
            for candidate in golden.candidates
        ]
        candidates_difference = _rows_difference(ours, expected)
    comparison = SearchComparison(
        query_id=golden.manifest["id"],
        manifest=_manifest_difference(manifest, golden.manifest),
        solution_lines=_lines_difference(
            solution_lines(result, game=data.game), golden.solution_lines
        ),
        candidates=candidates_difference,
    )
    return comparison


def _differences(comparisons: list[SearchComparison], part: str) -> dict[str, str]:
    differences = {
        comparison.query_id: getattr(comparison, part)
        for comparison in comparisons
        if getattr(comparison, part) is not None
    }
    return differences


@pytest.fixture(scope="session")
def public_comparisons(search_goldens, search_data_by_language) -> list[SearchComparison]:
    comparisons = [_compare(golden, search_data_by_language) for golden in search_goldens]
    return comparisons


@pytest.fixture(scope="session")
def personal_comparisons(
    personal_search_goldens, search_data_by_language
) -> list[SearchComparison]:
    comparisons = [_compare(golden, search_data_by_language) for golden in personal_search_goldens]
    return comparisons


@pytest.mark.parametrize("part", ["manifest", "solution_lines", "candidates"])
def test_search_matches_the_harness(public_comparisons, part):
    assert [len(public_comparisons), _differences(public_comparisons, part)] == [10, {}]


def test_every_order_dependent_query_compares_candidates(search_goldens):
    with_candidates = [golden.manifest["id"] for golden in search_goldens if golden.candidates]

    assert with_candidates == ["g03", "g04", "g13"]


@pytest.mark.parametrize("part", ["manifest", "solution_lines", "candidates"])
def test_personal_search_matches_the_harness(personal_comparisons, part):
    assert [len(personal_comparisons), _differences(personal_comparisons, part)] == [12, {}]
