"""The differential-fuzz goldens: current with their queries and internally consistent.

Phase 9b compares the Python search with these; here they're only checked
against their own queries and solution files.
"""

from __future__ import annotations

import json
from pathlib import Path

from goldens import FuzzGolden
from mhp3ass.results import lines_sha256


def test_fuzz_goldens_are_current(fuzz_goldens: list[FuzzGolden]):
    stale = [
        golden.name
        for golden in fuzz_goldens
        if json.loads(golden.manifest["query_json"]) != golden.query
    ]

    assert stale == []


def test_every_fuzz_golden_has_a_query(repo_root: Path):
    tests_dir = repo_root / "tests"
    query_names = {path.stem for path in (tests_dir / "fuzz").glob("f*.json")}
    golden_names = {path.name.split(".")[0] for path in (tests_dir / "golden" / "fuzz").iterdir()}

    assert golden_names == query_names


def _inconsistent(golden: FuzzGolden, max_solution_lines: int) -> bool:
    """A manifest that disagrees with itself or with its solutions file."""
    manifest = golden.manifest
    workers = manifest["workers"]
    counts_agree = manifest["solution_count"] == sum(worker["added"] for worker in workers)
    # Workers after a recorded exception don't run.
    workers_complete = manifest["exception"] is not None or manifest["worker_count"] == len(workers)
    file_rule = manifest["solutions_file"] == (manifest["solution_count"] <= max_solution_lines)
    file_present = (golden.solution_lines is not None) == manifest["solutions_file"]
    hashes_agree = True
    if golden.solution_lines is not None:
        lines = golden.solution_lines
        start = 0
        for worker in workers:
            added = lines[start : start + worker["added"]]
            hashes_agree = hashes_agree and worker["added_sha256"] == lines_sha256(added)
            start += worker["added"]
        hashes_agree = (
            hashes_agree
            and len(lines) == manifest["solution_count"]
            and manifest["solutions_sha256"] == lines_sha256(lines)
            and manifest["solution_set_sha256"] == lines_sha256(sorted(lines))
        )
    consistent = counts_agree and workers_complete and file_rule and file_present and hashes_agree
    return not consistent


def test_fuzz_manifests_are_consistent(fuzz_goldens: list[FuzzGolden]):
    """generate-goldens.ps1 -Fuzz writes solution files for at most 5,000 lines."""
    inconsistent = [golden.name for golden in fuzz_goldens if _inconsistent(golden, 5000)]

    assert inconsistent == []


def test_ten_fuzz_queries_skip_illegal_charms(fuzz_goldens: list[FuzzGolden]):
    """The corpus puts illegal my-charms lines in exactly ten queries (tests/fuzz/README.md)."""
    with_illegal = [golden.name for golden in fuzz_goldens if golden.manifest["my_charms_illegal"]]

    assert len(with_illegal) == 10


def test_no_fuzz_query_throws(fuzz_goldens: list[FuzzGolden]):
    """A worker exception on a GUI-reachable query is a finding to raise, not a golden to keep."""
    exceptions = {
        golden.name: golden.manifest["exception"]
        for golden in fuzz_goldens
        if golden.manifest["exception"] is not None
    }

    assert exceptions == {}
