"""The search writers against the harness's own files: what ``mhp3-ass search
--out`` writes for a corpus query is what the harness wrote for it."""

from __future__ import annotations

import gzip
import json
from dataclasses import replace
from pathlib import Path

import pytest

from mhp3ass.query import SearchSpec
from mhp3ass.results.result_set import (
    SearchResult,
    WorkerResult,
    added_lines,
    candidate_lines,
    gzip_lines,
    manifest_text,
    search_manifest,
    solution_lines,
    write_search_outputs,
)
from mhp3ass.search import run_search


def _write(query_name: str, repo_root: Path, search_data, out_dir: Path, **manifest_options):
    spec_json = json.loads(
        (repo_root / "tests" / "corpus" / f"{query_name}.json").read_text(encoding="utf-8")
    )
    spec = SearchSpec.from_json(spec_json)
    data = search_data[spec.query.language]
    result = run_search(spec, data=data)
    manifest = search_manifest(
        spec_json,
        result=result,
        worker_lines=added_lines(result),
        **manifest_options,
    )
    prefix = out_dir / query_name
    write_search_outputs(
        prefix,
        manifest=manifest,
        lines=solution_lines(result),
        candidates=candidate_lines(result),
    )
    return prefix


def _lines(path: Path) -> list[str]:
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        lines = handle.read().splitlines()
    return lines


@pytest.mark.parametrize(
    "query_name", ["g13-hr3-attack-health-one-skill", "g16-attack-sharp-no-charms"]
)
def test_written_files_hold_what_the_harness_wrote(
    query_name, repo_root, search_data_by_language, tmp_path
):
    prefix = _write(query_name, repo_root, search_data_by_language, tmp_path)
    golden = repo_root / "tests" / "golden" / "search" / query_name
    golden_candidates = Path(f"{golden}.candidates.txt.gz")

    assert [
        Path(f"{prefix}.manifest.json").read_bytes(),
        _lines(Path(f"{prefix}.solutions.txt.gz")),
    ] == [
        Path(f"{golden}.manifest.json").read_bytes(),
        _lines(Path(f"{golden}.solutions.txt.gz")),
    ]
    if golden_candidates.is_file():
        assert _lines(Path(f"{prefix}.candidates.txt.gz")) == _lines(golden_candidates)


def test_added_lines_are_each_workers_kept_lines_joining_to_the_kept_list(one_skill_search):
    result = one_skill_search.result

    worker_lines = added_lines(result)

    assert [
        [len(kept) for kept in worker_lines],
        [line for kept in worker_lines for line in kept],
    ] == [[len(worker.added) for worker in result.workers], solution_lines(result)]
    assert sum(1 for kept in worker_lines if kept) > 1


@pytest.fixture
def one_skill_result_with_a_worker_keeping_nothing(one_skill_search) -> SearchResult:
    """g13's result with a fifth, charm-free worker that found and kept nothing."""
    result = one_skill_search.result
    idle = WorkerResult(template=None, found=[], added=[])
    with_idle = replace(result, workers=[*result.workers, idle])
    return with_idle


def test_a_worker_that_kept_nothing_has_no_lines_in_its_place(
    one_skill_result_with_a_worker_keeping_nothing,
):
    worker_lines = added_lines(one_skill_result_with_a_worker_keeping_nothing)

    assert [len(worker_lines), worker_lines[-1]] == [5, []]


def test_a_result_with_no_finished_workers_has_no_lines(one_skill_search):
    result = replace(one_skill_search.result, workers=[])

    assert added_lines(result) == []


@pytest.mark.parametrize(
    "lines_for",
    [lambda lines: lines[:-1], lambda lines: [lines[1], lines[0], *lines[2:]]],
    ids=["a-worker-missing", "workers-swapped"],
)
def test_a_manifest_needs_each_finished_workers_own_lines(one_skill_search, lines_for):
    result = one_skill_search.result
    worker_lines = added_lines(result)

    with pytest.raises(ValueError, match="for the finished workers' added"):
        search_manifest({"id": "g13"}, result=result, worker_lines=lines_for(worker_lines))


def test_too_many_lines_removes_the_solutions_file(repo_root, search_data_by_language, tmp_path):
    stale = tmp_path / "g16-attack-sharp-no-charms.solutions.txt.gz"
    stale.write_bytes(gzip_lines(["stale"]))

    prefix = _write(
        "g16-attack-sharp-no-charms",
        repo_root,
        search_data_by_language,
        tmp_path,
        max_solution_lines=1,
    )
    manifest = json.loads(Path(f"{prefix}.manifest.json").read_text(encoding="utf-8"))

    assert [manifest["solutions_file"], stale.exists()] == [False, False]


def test_no_lines_give_the_empty_gzip_member():
    empty = gzip_lines([])

    assert [len(empty), gzip.decompress(empty)] == [20, b""]


def test_manifest_strings_are_escaped_as_the_harness_escapes_them():
    text = manifest_text({"name": 'a"\\\n\r\t\x01\x7fé😀', "empty": [], "none": None})

    assert text == (
        "{\n"
        '  "name": "a\\"\\\\\\n\\r\\t\\u0001\\u007f\\u00e9\\ud83d\\ude00",\n'
        '  "empty": [],\n'
        '  "none": null\n'
        "}\n"
    )


def test_manifest_nesting_is_laid_out_as_the_harness_lays_it_out():
    text = manifest_text({"workers": [{"worker": 0, "charm": None, "ok": True}], "map": {}})

    assert text == (
        "{\n"
        '  "workers": [\n'
        "    {\n"
        '      "worker": 0,\n'
        '      "charm": null,\n'
        '      "ok": true\n'
        "    }\n"
        "  ],\n"
        '  "map": {}\n'
        "}\n"
    )


@pytest.mark.parametrize("character", ["\b", "\f"], ids=["backspace", "form-feed"])
@pytest.mark.parametrize(
    "where",
    [
        lambda c: {"name": f"a{c}b"},
        lambda c: {f"key{c}": 1},
        lambda c: {"workers": [{"charm": c}]},
        lambda c: {"lines": [["x", c]]},
    ],
    ids=["value", "key", "nested-dict", "nested-list"],
)
def test_a_backspace_or_form_feed_in_a_manifest_string_raises(character, where):
    with pytest.raises(ValueError, match="backspace or form feed"):
        manifest_text(where(character))


@pytest.mark.parametrize(
    "manifest",
    [{"id": 1.5}, {"lines": ("x\b",)}, {"map": {1: "one"}}, {"set": {"a"}}],
    ids=["float", "tuple", "int-key", "set"],
)
def test_a_value_the_harness_has_no_form_for_raises(manifest):
    with pytest.raises(TypeError, match="no JSON form"):
        manifest_text(manifest)


def test_a_manifest_that_cannot_be_written_leaves_the_files_as_they_were(tmp_path):
    prefix = tmp_path / "query"
    files = {
        suffix: Path(f"{prefix}.{suffix}")
        for suffix in ("solutions.txt.gz", "candidates.txt.gz", "manifest.json")
    }
    for path in files.values():
        path.write_bytes(b"before")

    with pytest.raises(ValueError, match="backspace or form feed"):
        write_search_outputs(
            prefix,
            manifest={"solutions_file": True, "message": "a\bb"},
            lines=["new"],
            candidates=[],
        )

    assert [path.read_bytes() for path in files.values()] == [b"before"] * 3
