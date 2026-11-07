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


@dataclass(frozen=True)
class SearchGolden:
    """Harness output for one corpus query."""

    query: dict[str, Any]
    manifest: dict[str, Any]
    solution_lines: list[str]


def read_search_goldens(corpus_dir: Path, golden_dir: Path) -> list[SearchGolden]:
    """Pair each corpus query with the harness output generated from it."""
    goldens = []
    for query_path in sorted(corpus_dir.glob("*.json")):
        prefix = golden_dir / query_path.stem
        with gzip.open(f"{prefix}.solutions.txt.gz", "rt", encoding="utf-8") as handle:
            solution_lines = handle.read().splitlines()
        golden = SearchGolden(
            query=read_golden(query_path),
            manifest=read_golden(Path(f"{prefix}.manifest.json")),
            solution_lines=solution_lines,
        )
        goldens.append(golden)
    return goldens
