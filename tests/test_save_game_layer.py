"""The save's game layer: its seed rules on synthetic data, the harness's hash on your save."""

from __future__ import annotations

import hashlib
from typing import Any

import pytest

from mhp3ass.savefile.game_layer import decrypt_game_layer
from mhp3ass.savefile.tables import SUBSTITUTION_TABLE


def _seed_for(substituted_twice: bytes) -> bytes:
    """The seed bytes that come out of the table twice as ``substituted_twice``."""
    inverse = [0] * 256
    for byte, substituted in enumerate(SUBSTITUTION_TABLE):
        inverse[substituted] = byte
    seed = bytes(inverse[inverse[byte]] for byte in substituted_twice)
    return seed


def test_game_layer_matches_golden(save_game_layer: bytes, save_golden: Any):
    assert hashlib.sha256(save_game_layer).hexdigest() == save_golden["game_layer_sha256"]


def test_seed_is_written_back_substituted_twice():
    seed = bytes([0x00, 0x01, 0x80, 0xFF])

    decrypted = decrypt_game_layer(bytes(8) + seed)

    assert decrypted[-4:] == bytes(SUBSTITUTION_TABLE[SUBSTITUTION_TABLE[byte]] for byte in seed)


def test_zero_seed_halves_fall_back_to_the_multipliers():
    """SaveDataEncryption.cpp:104-108: a zero half acts as 0x215F (lower) or 0xDFA3
    (upper), so the bodies decrypt alike under either seed."""
    body = bytes(range(32))
    zero_seed = _seed_for(bytes(4))
    fallback_seed = _seed_for((0xDFA3215F).to_bytes(4, "little"))

    from_zero = decrypt_game_layer(body + zero_seed)
    from_fallback = decrypt_game_layer(body + fallback_seed)

    assert from_zero[:-4] == from_fallback[:-4]
    assert from_zero[:-4] != decrypt_game_layer(body + _seed_for(bytes([1, 0, 0, 0])))[:-4]


@pytest.mark.parametrize("length", [0, 3, 10])
def test_rejects_partial_words(length: int):
    with pytest.raises(ValueError, match="whole 4-byte words"):
        decrypt_game_layer(bytes(length))
