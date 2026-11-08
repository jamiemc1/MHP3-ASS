"""The save's system layer: the harness's hash on your save, and fixed answers and the
original's size behaviour on synthetic data."""

from __future__ import annotations

import hashlib
from typing import Any

import pytest

from mhp3ass.savefile.system_layer import SystemLayerError, decrypt_system_layer


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


def test_keystream_matches_known_answer():
    """A zero body decrypts to the bare keystream. These bytes come from this port after
    it matched the harness's hash on a real save, so CI checks the key derivation,
    counter and chaining without one."""
    decrypted = decrypt_system_layer(_pattern(16, step=3) + bytes(0x820))

    assert len(decrypted) == 0x820
    assert decrypted[:32].hex() == (
        "c32d5a4c46957bf3d105363ccb41a4c9ddaaa3f49b85b8c3f277035b4e30d0cb"
    )
    assert decrypted[-16:].hex() == "470a76d227b649333ea9da2e5c6d3938"
    assert hashlib.sha256(decrypted).hexdigest() == (
        "d175269c48b04e718240e18131eec3dfbb4c2798ef45d06349ffbfbae056449d"
    )


def test_bodies_under_one_header_differ_by_their_xor():
    header = _pattern(16, step=3)
    first = _pattern(0x820, step=5)
    second = _pattern(0x820, step=11)

    decrypted_first = decrypt_system_layer(header + first)
    decrypted_second = decrypt_system_layer(header + second)

    assert bytes(a ^ b for a, b in zip(decrypted_first, decrypted_second, strict=True)) == bytes(
        a ^ b for a, b in zip(first, second, strict=True)
    )


def test_input_is_zero_padded_to_whole_blocks():
    data = _pattern(16 + 0x810 + 4, step=3)

    assert decrypt_system_layer(data) == decrypt_system_layer(data + bytes(12))


@pytest.mark.parametrize("length", [1, 15, 16])
def test_a_header_alone_gives_an_empty_body(length: int):
    """PSPCryptoEngine.cpp:541-554: one aligned block leaves nothing to decrypt."""
    assert decrypt_system_layer(bytes(length)) == b""


@pytest.mark.parametrize(
    ("length", "message"),
    [
        (0, "empty file"),
        (17, "16-byte body"),
        (0x810, "2048-byte body"),
    ],
)
def test_inputs_the_original_throws_on_are_rejected(length: int, message: str):
    """An empty input, and a body of 16-0x800 bytes (hleSdRemoveValue reads past its
    buffer, PSPCryptoEngine.cpp:302)."""
    with pytest.raises(SystemLayerError, match=message):
        decrypt_system_layer(bytes(length))


def test_the_shortest_body_the_original_decrypts():
    assert len(decrypt_system_layer(bytes(0x820))) == 0x810
