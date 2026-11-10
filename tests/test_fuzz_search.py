"""The differential-fuzz gate: the port's search against the harness on the 500 fuzz queries.

Each query is held to the L3 standard (``search_comparison.compare_search``):
the manifest field for field, including every worker's count and hash and the
recorded exception (none), and the solution lines in order wherever the harness
wrote them. The default run checks a seeded, stratified smoke subset of 25;
``pytest -m fuzz`` checks all 500.
"""

from __future__ import annotations

import random
from math import prod
from typing import Any

import pytest

from goldens import FuzzGolden
from mhp3ass.search import SearchData
from search_comparison import SearchComparison, compare_search, differences


def _evaluations(manifest: dict[str, Any]) -> int:
    """Armour combinations times workers: an empty slot still searches once (as ``None``)."""
    combinations = prod(max(count, 1) for count in manifest["relevant_armor_counts"])
    evaluations = combinations * manifest["worker_count"]
    return evaluations


def smoke_subset(
    goldens: list[FuzzGolden],
    seed: int = 9,
    with_solutions_per_mode: int = 3,
    without_solutions_per_mode: int = 2,
    max_evaluations: int = 20_000,
) -> list[FuzzGolden]:
    """Per charm mode, a seeded sample of queries with and without solutions.

    Only queries that search at least once and cost at most ``max_evaluations``
    are drawn, so the subset exercises the search without slowing the default run.
    """
    by_stratum: dict[tuple[str, bool], list[FuzzGolden]] = {}
    for golden in goldens:
        evaluations = _evaluations(golden.manifest)
        if 0 < evaluations <= max_evaluations:
            stratum = (golden.query["charm_mode"], golden.manifest["solution_count"] > 0)
            by_stratum.setdefault(stratum, []).append(golden)
    rng = random.Random(seed)
    chosen = []
    for (_, has_solutions), members in sorted(by_stratum.items()):
        count = with_solutions_per_mode if has_solutions else without_solutions_per_mode
        chosen.extend(rng.sample(members, count))
    subset = sorted(chosen, key=lambda golden: golden.name)
    return subset


def _compare(
    golden: FuzzGolden, search_data: dict[str, SearchData], max_solution_lines: int = 5000
) -> SearchComparison:
    """``max_solution_lines`` is the limit generate-goldens.ps1 -Fuzz gives the harness."""
    comparison = compare_search(
        query=golden.query,
        manifest=golden.manifest,
        golden_lines=golden.solution_lines,
        golden_candidates=None,
        search_data=search_data,
        max_solution_lines=max_solution_lines,
    )
    return comparison


@pytest.fixture(scope="session")
def fuzz_smoke_goldens(fuzz_goldens) -> list[FuzzGolden]:
    return smoke_subset(fuzz_goldens)


@pytest.fixture(scope="session")
def fuzz_smoke_comparisons(fuzz_smoke_goldens, search_data_by_language) -> list[SearchComparison]:
    comparisons = [_compare(golden, search_data_by_language) for golden in fuzz_smoke_goldens]
    return comparisons


@pytest.fixture(scope="session")
def fuzz_comparisons(fuzz_goldens, search_data_by_language) -> list[SearchComparison]:
    comparisons = [_compare(golden, search_data_by_language) for golden in fuzz_goldens]
    return comparisons


def test_smoke_subset_covers_every_charm_mode(fuzz_smoke_goldens):
    modes = sorted({golden.query["charm_mode"] for golden in fuzz_smoke_goldens})
    per_mode = {
        mode: sum(golden.query["charm_mode"] == mode for golden in fuzz_smoke_goldens)
        for mode in modes
    }
    with_solutions = sum(golden.manifest["solution_count"] > 0 for golden in fuzz_smoke_goldens)
    evaluations = [_evaluations(golden.manifest) for golden in fuzz_smoke_goldens]

    assert [len(fuzz_smoke_goldens), per_mode, with_solutions] == [
        25,
        {"my_charms": 5, "none": 5, "one_skill": 5, "slotted": 5, "two_skill": 5},
        15,
    ]
    assert 0 < min(evaluations) <= max(evaluations) <= 20_000


@pytest.mark.parametrize("part", ["manifest", "solution_lines"])
def test_fuzz_smoke_matches_the_harness(fuzz_smoke_comparisons, part):
    assert [len(fuzz_smoke_comparisons), differences(fuzz_smoke_comparisons, part)] == [25, {}]


@pytest.mark.fuzz
@pytest.mark.parametrize("part", ["manifest", "solution_lines"])
def test_every_fuzz_query_matches_the_harness(fuzz_comparisons, part):
    assert [len(fuzz_comparisons), differences(fuzz_comparisons, part)] == [500, {}]
