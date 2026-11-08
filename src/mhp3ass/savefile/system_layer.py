"""The save file's outer, system-level encryption.

Ported from ``PSPCryptoEngine::DecryptSaveData`` and the parts of
``hleSdCreateList`` (generator mode 2), ``hleSdSetMember`` and ``Kirk`` it
reaches (``legacy/PSPCryptoEngine.cpp:177-224``, ``:311-436``, ``:532-561``).

The first 16 bytes are a header; the rest is XORed with a keystream made by
AES-decrypting numbered counter blocks under a key derived from the header.

``hleSdRemoveValue`` (:261-309) only feeds an integrity hash nothing reads
(the check is commented out at :556-558), so its computation is left out.
Its one observable effect is kept: for a body of 16 to 0x800 bytes it copies
16 bytes from ``blockSize + 4`` (:302), past the end of its buffer, and throws.
"""

from __future__ import annotations

from mhp3ass.savefile.aes import cbc_decrypt_zero_iv
from mhp3ass.savefile.tables import AES_KEY_0X12, AES_KEY_0X64, GAME_KEY, SD_KEY_6, SD_KEY_7


class SystemLayerError(ValueError):
    """An input the original's system-layer decryption throws on."""


def _xor(first: bytes, second: bytes) -> bytes:
    if len(first) != len(second):
        raise ValueError(f"XOR of {len(first)} and {len(second)} bytes")
    combined = (int.from_bytes(first, "big") ^ int.from_bytes(second, "big")).to_bytes(
        len(first), "big"
    )
    return combined


def _key_block(header: bytes) -> bytes:
    """``hleSdCreateList`` mode 2 then the key half of ``hleSdSetMember``
    (PSPCryptoEngine.cpp:367-379, :393-408): the header XORed with the game key,
    then SD key 7, one AES block under seed 0x12, then SD key 6."""
    hashed = _xor(header, GAME_KEY)
    decrypted = cbc_decrypt_zero_iv(AES_KEY_0X12, _xor(hashed, SD_KEY_7))
    key_block = _xor(decrypted, SD_KEY_6)
    return key_block


def _counter_blocks(key_block: bytes, length: int) -> bytes:
    """The numbered list ``hleSdSetMember`` builds (PSPCryptoEngine.cpp:419-427): the
    key block's first 12 bytes and a little-endian counter from 1, per 16 bytes."""
    prefix = key_block[:12]
    blocks = b"".join(
        prefix + number.to_bytes(4, "little") for number in range(1, length // 16 + 1)
    )
    return blocks


def decrypt_system_layer(data: bytes) -> bytes:
    """``PSPCryptoEngine::DecryptSaveData``: the decrypted body, without the header.

    The input is zero-padded to whole 16-byte blocks first, as the original
    copies it into an aligned buffer (PSPCryptoEngine.cpp:541-546). Like the
    original, an input of 1-16 bytes gives an empty body, and an empty input
    or a body of 16-0x800 bytes raises (``SystemLayerError``).
    """
    if not data:
        # The output buffer would be 16 bytes shorter than nothing (:542).
        raise SystemLayerError("an empty file has no header")
    aligned_size = (len(data) + 0xF) >> 4 << 4
    padded = data + bytes(aligned_size - len(data))
    header = padded[:0x10]
    body = padded[0x10:]
    if 0 < len(body) <= 0x800:
        raise SystemLayerError(
            f"a {len(body)}-byte body is too short for hleSdRemoveValue (needs over 0x800)"
        )
    keystream = cbc_decrypt_zero_iv(AES_KEY_0X64, _counter_blocks(_key_block(header), len(body)))
    decrypted = _xor(body, keystream)
    return decrypted
