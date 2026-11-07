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
from pathlib import Path
from typing import Any

from goldens import Candidate, SearchGolden
from mhp3ass.settings_cfg import read_settings_cfg


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


def _armor_hash(solution_line: str) -> int:
    """Form1::HashArmor (Form1.h:1691-1699): sum(index << (slot * 3)) over the armour indices."""
    indices = [int(token) for token in solution_line.split()[:5]]
    hashed = sum(index << (slot * 3) for slot, index in enumerate(indices))
    return hashed


def _remove_duplicates(candidates: list[Candidate]) -> list[str]:
    """Form1::AddSolutions (Form1.h:1701-1746) applied to candidates in the given order."""
    seen: set[tuple[str, int]] = set()
    kept = []
    for candidate in candidates:
        if candidate.charm_name:
            key = (candidate.charm_name, _armor_hash(candidate.solution_line))
            if key in seen:
                continue
            seen.add(key)
        kept.append(candidate.solution_line)
    return kept


def _survivor_choice_differs_only(candidates: list[Candidate], gui_lines: tuple[str, ...]) -> bool:
    """Whether the GUI's result is the candidates with some choice of duplicates kept.

    True when every GUI line is a candidate, charm-free solutions (never
    de-duplicated) match exactly, and the GUI keeps exactly one solution per
    (charm name, armour hash) key, covering the same keys as the candidates.
    """
    charm_of = {candidate.solution_line: candidate.charm_name for candidate in candidates}
    if any(line not in charm_of for line in gui_lines):
        return False
    charm_free_gui = Counter(line for line in gui_lines if charm_of[line] == "")
    charm_free_candidates = Counter(c.solution_line for c in candidates if c.charm_name == "")
    gui_keys = Counter((charm_of[line], _armor_hash(line)) for line in gui_lines if charm_of[line])
    candidate_keys = {
        (c.charm_name, _armor_hash(c.solution_line)) for c in candidates if c.charm_name
    }
    matches = (
        charm_free_gui == charm_free_candidates
        and all(count == 1 for count in gui_keys.values())
        and set(gui_keys) == candidate_keys
    )
    return matches


def _gui_mismatches(goldens: list[SearchGolden], captures_dir: Path) -> list[str]:
    mismatched = []
    for golden in goldens:
        capture = golden.query.get("gui_capture")
        if capture is None:
            continue
        if not (captures_dir / capture).is_dir():
            mismatched.append(f"{golden.query['id']} (no capture {capture})")
            continue
        gui_lines = read_settings_cfg(captures_dir / capture / "settings.cfg").solution_lines
        if golden.query.get("gui_order_dependent"):
            if golden.candidates is None or not _survivor_choice_differs_only(
                golden.candidates, gui_lines
            ):
                mismatched.append(golden.query["id"])
        # Same solutions; order differs because the GUI's search threads interleave their batches.
        elif Counter(golden.solution_lines) != Counter(gui_lines):
            mismatched.append(golden.query["id"])
    return mismatched


def test_searches_match_gui_captures(search_goldens: list[SearchGolden], gui_captures_dir: Path):
    assert _gui_mismatches(search_goldens, gui_captures_dir) == []


def test_personal_searches_match_gui_captures(
    personal_search_goldens: list[SearchGolden], gui_captures_dir: Path
):
    assert _gui_mismatches(personal_search_goldens, gui_captures_dir) == []


def _missing_candidates(goldens: list[SearchGolden]) -> list[str]:
    missing = [
        golden.query["id"]
        for golden in goldens
        if golden.query.get("gui_order_dependent") and golden.candidates is None
    ]
    return missing


def _candidates_disagreeing_with_solutions(goldens: list[SearchGolden]) -> list[str]:
    # Workers run in start order, each in loop order: the order the harness adds them in.
    differing = [
        golden.query["id"]
        for golden in goldens
        if golden.candidates is not None
        and _remove_duplicates(golden.candidates) != golden.solution_lines
    ]
    return differing


def test_order_dependent_queries_have_candidates(search_goldens: list[SearchGolden]):
    assert _missing_candidates(search_goldens) == []


def test_personal_order_dependent_queries_have_candidates(
    personal_search_goldens: list[SearchGolden],
):
    assert _missing_candidates(personal_search_goldens) == []


def test_duplicate_removal_over_candidates_reproduces_solutions(search_goldens: list[SearchGolden]):
    assert _candidates_disagreeing_with_solutions(search_goldens) == []


def test_personal_duplicate_removal_over_candidates_reproduces_solutions(
    personal_search_goldens: list[SearchGolden],
):
    assert _candidates_disagreeing_with_solutions(personal_search_goldens) == []
