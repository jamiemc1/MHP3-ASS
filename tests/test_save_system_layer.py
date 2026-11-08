"""The save's system layer: structure on synthetic data, the harness's hash on your save."""

from __future__ import annotations

import hashlib
from typing import Any

import pytest

from mhp3ass.savefile.system_layer import decrypt_system_layer


def _pattern(length: int, step: int) -> bytes:
    pattern = bytes((index * step + 7) % 256 for index in range(length))
    return pattern


def test_save_golden_is_for_this_save(save_bytes: bytes, save_golden: Any):
    """A different save makes every save golden stale: regenerate save.json on Windows
    (scripts/windows/generate-goldens.ps1)."""
    assert [len(save_bytes), hashlib.sha256(save_bytes).hexdigest()] == [
        save_golden["input_length"],
        save_golden["input_sha256"],
    ]


def test_system_layer_matches_golden(save_system_layer: bytes, save_golden: Any):
    assert [len(save_system_layer), hashlib.sha256(save_system_layer).hexdigest()] == [
        save_golden["system_layer_length"],
        save_golden["system_layer_sha256"],
    ]


def test_header_is_dropped_and_the_body_is_xored_with_a_header_keystream():
    """Round trips prove nothing for an XOR stream; this checks that structure instead.
    Bodies under the same header differ by exactly their XOR."""
    header = _pattern(16, step=3)
    first = _pattern(64, step=5)
    second = _pattern(64, step=11)

    decrypted_first = decrypt_system_layer(header + first)
    decrypted_second = decrypt_system_layer(header + second)

    assert len(decrypted_first) == 64
    assert bytes(a ^ b for a, b in zip(decrypted_first, decrypted_second, strict=True)) == bytes(
        a ^ b for a, b in zip(first, second, strict=True)
    )


def test_the_keystream_depends_on_the_header():
    body = bytes(32)

    assert decrypt_system_layer(_pattern(16, step=3) + body) != decrypt_system_layer(
        _pattern(16, step=5) + body
    )


def test_input_is_zero_padded_to_whole_blocks():
    data = _pattern(16 + 20, step=3)

    assert decrypt_system_layer(data) == decrypt_system_layer(data + bytes(12))


def test_input_shorter_than_the_header_is_rejected():
    with pytest.raises(ValueError, match="16-byte header"):
        decrypt_system_layer(bytes(15))
