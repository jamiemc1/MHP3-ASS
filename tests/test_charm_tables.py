"""The extracted OmaSkill tables against the game data they index."""

from __future__ import annotations

import subprocess
import sys

from mhp3ass.charms.tables import SKILL_TABLES, SLOT_THRESHOLDS


def test_committed_tables_match_the_legacy_source(repo_root):
    script = repo_root / "scripts" / "extract_charm_tables.py"
    result = subprocess.run(
        [sys.executable, str(script), "--check"], capture_output=True, text=True, check=False
    )

    assert [result.returncode, result.stderr] == [0, ""]


def test_skill_rows_name_ordered_abilities_with_valid_ranges(teamhgg_game):
    ability_count = len(teamhgg_game.ordered_abilities)
    invalid = [
        (table, row)
        for table, rows in enumerate(SKILL_TABLES)
        for row, (ability_index, minimum, maximum) in enumerate(rows)
        if not (0 <= ability_index < ability_count and minimum <= maximum and maximum > 0)
    ]

    assert [[len(rows) for rows in SKILL_TABLES], invalid] == [[43, 61, 55, 54, 52], []]


def test_slot_thresholds_rise_to_99():
    misordered = [
        (kind, rank)
        for kind, ranks in enumerate(SLOT_THRESHOLDS)
        for rank, thresholds in enumerate(ranks)
        if list(thresholds) != sorted(thresholds) or thresholds[-1] != 99
    ]

    assert [[len(ranks) for ranks in SLOT_THRESHOLDS], misordered] == [[21, 21, 11], []]
