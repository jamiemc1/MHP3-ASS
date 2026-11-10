"""Comparing a port search with the harness's output for the same query.

Shared by the L3 gate (``test_search.py``) and the differential-fuzz gate
(``test_fuzz_search.py``), so both hold the port to the same standard.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from goldens import Candidate
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


def compare_search(
    *,
    query: dict[str, Any],
    manifest: dict[str, Any],
    golden_lines: list[str] | None,
    golden_candidates: list[Candidate] | None,
    search_data: dict[str, SearchData],
    max_solution_lines: int,
) -> SearchComparison:
    """Run ``query`` and compare it with the harness's manifest, and with its
    solution lines and candidates where the harness wrote them.
    ``max_solution_lines`` is the limit the harness ran with (below 0: none).

    Without solution lines (a fuzz query over 5,000 solutions) the manifest
    still pins every worker's count and hash and both set hashes.
    """
    spec = SearchSpec.from_json(query)
    data = search_data[spec.query.language]
    record_exceptions = "exception" in manifest
    result = run_search(spec, data=data, record_exceptions=record_exceptions)
    our_manifest = search_manifest(
        query, result=result, game=data.game, max_solution_lines=max_solution_lines
    )
    lines_difference = None
    if golden_lines is not None:
        lines_difference = _lines_difference(solution_lines(result, game=data.game), golden_lines)
    candidates_difference = None
    if golden_candidates is not None:
        ours = [
            (candidate.worker, candidate.charm_name, candidate.solution_line)
            for candidate in candidate_lines(result, game=data.game)
        ]
        expected = [
            (candidate.worker, candidate.charm_name, candidate.solution_line)
            for candidate in golden_candidates
        ]
        candidates_difference = _rows_difference(ours, expected)
    comparison = SearchComparison(
        query_id=manifest["id"],
        manifest=_manifest_difference(our_manifest, manifest),
        solution_lines=lines_difference,
        candidates=candidates_difference,
    )
    return comparison


def differences(comparisons: list[SearchComparison], part: str) -> dict[str, str]:
    """Each query's difference in ``part`` (a ``SearchComparison`` field), by query id."""
    found = {
        comparison.query_id: getattr(comparison, part)
        for comparison in comparisons
        if getattr(comparison, part) is not None
    }
    return found
