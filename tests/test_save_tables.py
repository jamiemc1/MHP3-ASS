"""The extracted save decryption constants against the legacy source."""

from __future__ import annotations

import subprocess
import sys

from mhp3ass.savefile.tables import (
    AES_KEY_0X12,
    AES_KEY_0X64,
    GAME_KEY,
    SD_KEY_6,
    SD_KEY_7,
    SUBSTITUTION_TABLE,
)


def test_committed_tables_match_the_legacy_source(repo_root):
    script = repo_root / "scripts" / "extract_save_tables.py"
    result = subprocess.run(
        [sys.executable, str(script), "--check"], capture_output=True, text=True, check=False
    )

    assert [result.returncode, result.stderr] == [0, ""]


def test_substitution_table_is_a_permutation_of_every_byte():
    """Decryption substitutes every byte twice, so the table must lose nothing."""
    assert sorted(SUBSTITUTION_TABLE) == list(range(256))


def test_keys_are_aes_128_blocks():
    keys = [GAME_KEY, SD_KEY_6, SD_KEY_7, AES_KEY_0X12, AES_KEY_0X64]

    assert [len(key) for key in keys] == [16] * 5
