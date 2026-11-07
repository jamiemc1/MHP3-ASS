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


def read_gui_capture_solutions(capture_dir: Path) -> list[str]:
    """Solution lines from a GUI capture's settings.cfg.

    settings.cfg version 2: 14 option lines and 24 skill lines, then one
    solution per line.
    """
    lines = (capture_dir / "settings.cfg").read_text(encoding="utf-8").splitlines()
    if lines[0] != "2":
        raise ValueError(f"unsupported settings.cfg version {lines[0]!r} in {capture_dir}")
    solution_lines = lines[38:]
    return solution_lines
