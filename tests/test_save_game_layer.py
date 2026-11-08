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


@pytest.mark.parametrize(
    ("seed_value", "fallback_value"),
    [
        (0x00000000, 0xDFA3215F),
        (0x12340000, 0x1234215F),
        (0x00005678, 0xDFA35678),
    ],
)
def test_a_zero_seed_half_falls_back_to_its_multiplier(seed_value: int, fallback_value: int):
    """SaveDataEncryption.cpp:104-108: a zero lower half acts as 0x215F and a zero upper
    half as 0xDFA3, so the body decrypts as under a seed with that value."""
    body = bytes(range(32))

    from_zero = decrypt_game_layer(body + _seed_for(seed_value.to_bytes(4, "little")))
    from_fallback = decrypt_game_layer(body + _seed_for(fallback_value.to_bytes(4, "little")))

    assert from_zero[:-4] == from_fallback[:-4]


def test_body_matches_known_answer():
    """Fixed bytes from this port after it matched the harness's hash on a real save,
    so CI checks the generator constants and both substitutions without one."""
    body = bytes((index * 5 + 7) % 256 for index in range(32))

    decrypted = decrypt_game_layer(body + bytes([0x12, 0x34, 0x56, 0x78]))

    assert decrypted.hex() == (
        "07031bfcfedbbee485ceebbc58d5824ce641a0381b79bf2d38a64db2cfeb7b3db9ff4ba8"
    )


def test_a_partial_last_word_overlaps_the_seed():
    """With 10 bytes the second word covers the seed's first two bytes; the seed is
    written back over them afterwards (SaveDataEncryption.cpp:110-121)."""
    seed = bytes([0x00, 0x01, 0x80, 0xFF])

    decrypted = decrypt_game_layer(bytes(6) + seed)

    assert len(decrypted) == 10
    assert decrypted[-4:] == bytes(SUBSTITUTION_TABLE[SUBSTITUTION_TABLE[byte]] for byte in seed)


@pytest.mark.parametrize("length", [0, 3])
def test_rejects_input_without_a_seed(length: int):
    with pytest.raises(ValueError, match="4-byte seed"):
        decrypt_game_layer(bytes(length))
