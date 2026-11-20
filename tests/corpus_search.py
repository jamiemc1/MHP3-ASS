"""A corpus query's search, as the result-details, placement and difficulty tests read it."""

from __future__ import annotations

from dataclasses import dataclass

from mhp3ass.query import SearchSpec
from mhp3ass.results.result_set import SearchResult
from mhp3ass.search import SearchData


@dataclass(frozen=True)
class CorpusSearch:
    spec: SearchSpec
    data: SearchData
    result: SearchResult
