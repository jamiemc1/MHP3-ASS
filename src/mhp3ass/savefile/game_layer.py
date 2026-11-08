"""The save file's inner, game-specific encryption.

Ported from ``DecryptSaveData`` and its helpers in
``legacy/SaveDataEncryption.cpp:47-122``.

The last 4 bytes are a seed. Every 4-byte word before it is substituted
byte by byte, XORed with the output of two 16-bit multiplicative
generators seeded from the seed, and substituted again.
"""

from __future__ import annotations

from mhp3ass.savefile.tables import SUBSTITUTION_TABLE


def _substitute(data: bytearray, start: int) -> None:
    """``set_table_data`` (SaveDataEncryption.cpp:78-84): four bytes through the table."""
    for index in range(start, start + 4):
        data[index] = SUBSTITUTION_TABLE[data[index]]


def decrypt_game_layer(data: bytes) -> bytes:
    """``DecryptSaveData`` (SaveDataEncryption.cpp:91-122).

    The original reads each word as a signed 32-bit ``long``, so a word with
    bit 31 set is negative. That never shows: the generator offsets are masked
    to 16 bits and only the low 32 bits of each XOR are written back, so
    reading unsigned gives the same bytes. The seed is written back
    substituted twice.
    """
    if len(data) < 4 or len(data) % 4:
        raise ValueError(f"the game layer works on whole 4-byte words, got {len(data)} bytes")
    lower_multiplier, upper_multiplier = 0x215F, 0xDFA3
    lower_modulus, upper_modulus = 0xFF8F, 0xFFEF
    decrypted = bytearray(data)
    length = len(decrypted) - 4
    seed = bytearray(decrypted[length:])
    _substitute(seed, 0)
    _substitute(seed, 0)
    seed_value = int.from_bytes(seed, "little")
    lower = seed_value & 0xFFFF
    upper = (seed_value >> 16) & 0xFFFF
    # A zero half falls back to its multiplier (SaveDataEncryption.cpp:104-108).
    if lower == 0:
        lower = lower_multiplier
    if upper == 0:
        upper = upper_multiplier
    for offset in range(0, length, 4):
        _substitute(decrypted, offset)
        word = int.from_bytes(decrypted[offset : offset + 4], "little")
        lower = (lower * lower_multiplier) % lower_modulus
        upper = (upper * upper_multiplier) % upper_modulus
        mask = lower + (upper << 16)
        decrypted[offset : offset + 4] = ((word ^ mask) & 0xFFFFFFFF).to_bytes(4, "little")
        _substitute(decrypted, offset)
    decrypted[length:] = seed
    return bytes(decrypted)
