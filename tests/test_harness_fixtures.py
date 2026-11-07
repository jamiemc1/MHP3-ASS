"""Checks that the harness fixtures agree with independent references.

The golden fixtures are only a contract if the harness reproduces the
original application faithfully. These tests compare harness output with
output captured from the GUI itself, and check the fixtures are internally
consistent.
"""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass
from typing import Any

from goldens import SearchGolden


def test_save_import_matches_gui_output(save_golden: Any, gui_imported_mycharms: list[str]):
    assert save_golden["mycharms_txt"] == gui_imported_mycharms


def test_every_language_is_dumped(language_names: dict[str, Any], legacy_data_dir):
    languages_dir = legacy_data_dir / "Languages"
    language_dirs = sorted(path.name for path in languages_dir.iterdir() if path.is_dir())

    assert sorted(language_names) == language_dirs


def test_every_record_is_named_in_every_language(language_names: dict[str, Any]):
    unnamed = []
    for language, names in language_names.items():
        tables = {key: value for key, value in names.items() if key != "armors"}
        tables.update({f"armors.{slot}": armors for slot, armors in names["armors"].items()})
        for table, table_names in tables.items():
            unnamed += [
                (language, table, index)
                for index, name in enumerate(table_names)
                if not isinstance(name, str) or not name.strip()
            ]

    assert unnamed == []


def test_record_indices_match_list_positions(game_data: Any):
    records = {f"armors.{slot}": armors for slot, armors in game_data["armors"].items()}
    records["decorations"] = game_data["decorations"]

    misplaced = [
        (table, position, record["index"])
        for table, table_records in records.items()
        for position, record in enumerate(table_records)
        if record["index"] != position
    ]

    assert misplaced == []


@dataclass(frozen=True)
class CountMismatch:
    harness_count: int
    gui_count: int


def _count_mismatches(goldens: list[SearchGolden]) -> dict[str, CountMismatch]:
    mismatches = {}
    for golden in goldens:
        gui_count = golden.query.get("gui_solution_count")
        harness_count = golden.manifest["solution_count"]
        if gui_count is not None and harness_count != gui_count:
            mismatches[golden.query["id"]] = CountMismatch(
                harness_count=harness_count, gui_count=gui_count
            )
    return mismatches


def _stale_goldens(goldens: list[SearchGolden]) -> list[str]:
    """Queries whose corpus file changed after their golden was generated."""
    stale = [
        golden.query["id"]
        for golden in goldens
        if json.loads(golden.manifest["query_json"]) != golden.query
    ]
    return stale


def test_search_goldens_are_current(search_goldens: list[SearchGolden]):
    assert _stale_goldens(search_goldens) == []


def test_personal_search_goldens_are_current(personal_search_goldens: list[SearchGolden]):
    assert _stale_goldens(personal_search_goldens) == []


def test_search_counts_match_gui(search_goldens: list[SearchGolden]):
    assert _count_mismatches(search_goldens) == {}


def test_personal_search_counts_match_gui(personal_search_goldens: list[SearchGolden]):
    assert _count_mismatches(personal_search_goldens) == {}


def test_search_manifests_are_consistent(search_goldens: list[SearchGolden]):
    inconsistent = [
        golden.query["id"]
        for golden in search_goldens
        if not (
            golden.manifest["solution_count"]
            == len(golden.solution_lines)
            == sum(worker["added"] for worker in golden.manifest["workers"])
        )
    ]

    assert inconsistent == []


def test_query_1b_matches_gui_solutions(
    personal_search_goldens: list[SearchGolden], gui_query_1b_solution_lines: list[str]
):
    goldens_by_id = {golden.query["id"]: golden for golden in personal_search_goldens}
    assert "1b" in goldens_by_id, (
        "settings.cfg for query 1b exists but tests/savefile/corpus has no query 1b"
    )

    # Same solutions; order differs because the GUI's search threads interleave their batches.
    assert Counter(goldens_by_id["1b"].solution_lines) == Counter(gui_query_1b_solution_lines)
