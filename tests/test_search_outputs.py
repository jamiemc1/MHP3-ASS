"""The search writers against the harness's own files: what ``mhp3ass search
--out`` writes for a corpus query is what the harness wrote for it."""

from __future__ import annotations

import gzip
import json
from pathlib import Path

import pytest

from mhp3ass.query import SearchSpec
from mhp3ass.results.result_set import (
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
    manifest = search_manifest(spec_json, result=result, game=data.game, **manifest_options)
    prefix = out_dir / query_name
    write_search_outputs(
        prefix,
        manifest=manifest,
        lines=solution_lines(result, game=data.game),
        candidates=candidate_lines(result, game=data.game),
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
