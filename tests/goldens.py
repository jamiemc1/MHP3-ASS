"""Readers for the harness's golden fixtures."""

from __future__ import annotations

import gzip
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


def read_golden(path: Path) -> Any:
    """Load a harness fixture; files ending in .gz are gzip-compressed JSON."""
    if path.suffix == ".gz":
        with gzip.open(path, "rt", encoding="utf-8") as handle:
            return json.load(handle)
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def _read_gzip_lines(path: Path) -> list[str]:
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        lines = handle.read().splitlines()
    return lines


@dataclass(frozen=True)
class Candidate:
    """A solution one worker found, before duplicate removal."""

    worker: int
    charm_name: str
    solution_line: str


@dataclass(frozen=True)
class SearchGolden:
    """Harness output for one corpus query."""

    query: dict[str, Any]
    manifest: dict[str, Any]
    solution_lines: list[str]
    # Only for queries marked gui_order_dependent.
    candidates: list[Candidate] | None


@dataclass(frozen=True)
class RelevanceGolden:
    """Harness relevance output for one query."""

    query: dict[str, Any]
    relevance: dict[str, Any]


def read_relevance_goldens(query_dirs: list[Path], golden_dir: Path) -> list[RelevanceGolden]:
    """Pair each query in ``query_dirs`` with ``<golden_dir>/<name>.json.gz``."""
    goldens = [
        RelevanceGolden(
            query=read_golden(query_path),
            relevance=read_golden(golden_dir / f"{query_path.stem}.json.gz"),
        )
        for query_dir in query_dirs
        for query_path in sorted(query_dir.glob("*.json"))
    ]
    return goldens


@dataclass(frozen=True)
class TraceGolden:
    """Harness traces output for one spec: a header line, then one line per sample."""

    name: str
    spec_path: Path
    spec: dict[str, Any]
    query_path: Path
    query: dict[str, Any]
    header: dict[str, Any]
    samples: list[dict[str, Any]]


def read_trace_goldens(spec_dir: Path, golden_dir: Path) -> list[TraceGolden]:
    """Pair each spec in ``spec_dir`` with ``<golden_dir>/<name>.jsonl.gz`` and its query."""
    goldens = []
    for spec_path in sorted(spec_dir.glob("*.json")):
        spec = read_golden(spec_path)
        query_path = (spec_path.parent / spec["query"]).resolve()
        rows = [
            json.loads(line) for line in _read_gzip_lines(golden_dir / f"{spec_path.stem}.jsonl.gz")
        ]
        golden = TraceGolden(
            name=spec_path.stem,
            spec_path=spec_path,
            spec=spec,
            query_path=query_path,
            query=read_golden(query_path),
            header=rows[0],
            samples=rows[1:],
        )
        goldens.append(golden)
    return goldens


def read_search_goldens(corpus_dir: Path, golden_dir: Path) -> list[SearchGolden]:
    """Pair each corpus query with the harness output generated from it."""
    goldens = []
    for query_path in sorted(corpus_dir.glob("*.json")):
        prefix = golden_dir / query_path.stem
        candidates_path = Path(f"{prefix}.candidates.txt.gz")
        candidates = None
        if candidates_path.is_file():
            rows = [row.split("\t") for row in _read_gzip_lines(candidates_path)]
            candidates = [
                Candidate(worker=int(worker), charm_name=charm, solution_line=line)
                for worker, charm, line in rows
            ]
        golden = SearchGolden(
            query=read_golden(query_path),
            manifest=read_golden(Path(f"{prefix}.manifest.json")),
            solution_lines=_read_gzip_lines(Path(f"{prefix}.solutions.txt.gz")),
            candidates=candidates,
        )
        goldens.append(golden)
    return goldens


@dataclass(frozen=True)
class FuzzGolden:
    """Harness search output for one fuzz query: always a manifest; solution
    lines only when the harness wrote them (at most 5,000 lines)."""

    name: str
    query: dict[str, Any]
    manifest: dict[str, Any]
    solution_lines: list[str] | None


def read_fuzz_goldens(fuzz_dir: Path, golden_dir: Path) -> list[FuzzGolden]:
    """Pair each fuzz query with its manifest and, where one exists, its solutions file."""
    goldens = []
    for query_path in sorted(fuzz_dir.glob("f*.json")):
        prefix = golden_dir / query_path.stem
        solutions_path = Path(f"{prefix}.solutions.txt.gz")
        solution_lines = _read_gzip_lines(solutions_path) if solutions_path.is_file() else None
        golden = FuzzGolden(
            name=query_path.stem,
            query=read_golden(query_path),
            manifest=read_golden(Path(f"{prefix}.manifest.json")),
            solution_lines=solution_lines,
        )
        goldens.append(golden)
    return goldens
