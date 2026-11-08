"""Constants for decrypting a save file.

Extracted from ``legacy/SaveDataEncryption.cpp`` and ``legacy/PSPCryptoEngine.cpp``
by ``scripts/extract_save_tables.py``; do not edit by hand. Only the keys
decryption reaches are kept.
"""

from __future__ import annotations

# Game layer: GetDecryptionTable, applied to every byte
# (SaveDataEncryption.cpp:11-44).
SUBSTITUTION_TABLE = bytes.fromhex(
    "a6 21 22 f9 3d fb f5 06 87 54 76 75 ed 16 33 2e "
    "5a 17 50 1c de af 73 39 b5 28 d9 f1 cd 98 5f 2d "
    "78 62 29 c9 fd ea 32 cc 31 70 34 61 ae 4d fe c2 "
    "45 24 f8 fc d7 2f d8 26 59 a0 bd a5 01 18 a1 95 "
    "ee 4b 1a 7a 5b db f0 27 e6 f4 b2 ad 4a 14 9a 20 "
    "b9 36 4f 3b ca e4 41 85 3a 46 5c cb 3c ec 63 84 "
    "66 c4 eb 25 aa 7e c3 47 9b 74 8b 5d 23 8f 72 81 "
    "8c 56 c6 d4 40 60 a2 6d e5 b0 15 58 52 0f 7d 67 "
    "ef d2 0b cf 0d d6 2b 0a 9f 80 5e 3f 71 68 05 86 "
    "bb 38 ce 7f f3 83 03 48 d3 fa 35 df 44 7c 82 93 "
    "53 a3 09 6a 77 13 55 dd be 00 9c b4 e3 9e bc 96 "
    "a7 e2 42 4e 37 0e f6 9d 1b 2a 79 bf dc a9 88 4c "
    "d0 ab c5 69 d1 e1 ac e9 c1 b6 7b 57 90 07 30 92 "
    "b7 1e da 49 0c b8 a4 ff b3 f2 64 8a c7 02 6c 08 "
    "6f f7 89 c0 10 a8 8d ba 91 43 6b 3e d5 65 e0 6e "
    "12 2c 94 99 e8 1f c8 11 8e b1 e7 51 1d 97 04 19 "
)

# System layer: PSPCryptoEngine::mhp3_gamekey, XORed into the header
# (PSPCryptoEngine.cpp:65-70).
GAME_KEY = bytes.fromhex("e3 05 ce fa eb 46 b0 31 85 9a 27 5b df 32 d8 63")

# System layer: GetSDKey( 6 )
# (PSPCryptoEngine.cpp:80).
SD_KEY_6 = bytes.fromhex("70 44 a3 ae ef 5d a5 f2 85 7f f2 d6 94 f5 36 3b")

# System layer: GetSDKey( 7 )
# (PSPCryptoEngine.cpp:81).
SD_KEY_7 = bytes.fromhex("ec 6d 29 59 26 35 a5 7f 97 2a 0d bc a3 26 33 00")

# System layer: getAESKeyFromSeed( 0x12 ), decrypts the key block
# (PSPCryptoEngine.cpp:100).
AES_KEY_0X12 = bytes.fromhex("5d c7 11 39 d0 19 38 bc 02 7f dd dc b0 83 7d 9d")

# System layer: getAESKeyFromSeed( 0x64 ), decrypts the counter stream
# (PSPCryptoEngine.cpp:109).
AES_KEY_0X64 = bytes.fromhex("03 b3 02 e8 5f f3 81 b1 3b 8d aa 2a 90 ff 5e 61")
