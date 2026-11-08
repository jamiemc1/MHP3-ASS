"""AES-128-CBC decryption against published known-answer vectors."""

from __future__ import annotations

import pytest

from mhp3ass.savefile.aes import cbc_decrypt_zero_iv


def test_single_block_matches_fips_197():
    """FIPS-197 appendix C.1: one block, so CBC with a zero IV is plain AES."""
    key = bytes.fromhex("000102030405060708090a0b0c0d0e0f")
    ciphertext = bytes.fromhex("69c4e0d86a7b0430d8cdb78070b4c55a")

    assert cbc_decrypt_zero_iv(key, ciphertext).hex() == "00112233445566778899aabbccddeeff"


def test_chaining_matches_sp_800_38a():
    """NIST SP 800-38A F.2.2 (CBC-AES128.Decrypt). The vector's IV isn't zero, so
    only the first block differs, by exactly that IV."""
    key = bytes.fromhex("2b7e151628aed2a6abf7158809cf4f3c")
    iv = bytes.fromhex("000102030405060708090a0b0c0d0e0f")
    ciphertext = bytes.fromhex(
        "7649abac8119b246cee98e9b12e9197d"
        "5086cb9b507219ee95db113a917678b2"
        "73bed6b8e3c1743b7116e69e22229516"
        "3ff1caa1681fac09120eca307586e1a7"
    )
    expected = bytes.fromhex(
        "6bc1bee22e409f96e93d7e117393172a"
        "ae2d8a571e03ac9c9eb76fac45af8e51"
        "30c81c46a35ce411e5fbc1191a0a52ef"
        "f69f2445df4f9b17ad2b417be66c3710"
    )

    plaintext = cbc_decrypt_zero_iv(key, ciphertext)
    first_block = bytes(byte ^ iv_byte for byte, iv_byte in zip(plaintext[:16], iv, strict=True))

    assert first_block + plaintext[16:] == expected


@pytest.mark.parametrize(
    ("key", "data", "message"),
    [(bytes(15), bytes(16), "16-byte key"), (bytes(16), bytes(17), "whole 16-byte blocks")],
)
def test_rejects_sizes_aes_128_cbc_cannot_take(key: bytes, data: bytes, message: str):
    with pytest.raises(ValueError, match=message):
        cbc_decrypt_zero_iv(key, data)
