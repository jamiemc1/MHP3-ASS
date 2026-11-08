"""Write ``src/mhp3ass/savefile/tables.py`` from the save decryption constants in ``legacy/``.

Takes the game layer's substitution table (``GetDecryptionTable``,
``legacy/SaveDataEncryption.cpp``) and the system layer's game key, SD keys
6 and 7 and the AES keys for seeds 0x12 and 0x64 (``legacy/PSPCryptoEngine.cpp``),
the only ones decryption reaches. The output is already ruff-formatted;
``--check`` compares it with the committed module instead of writing it (a
test runs this).

Usage:
    uv run python scripts/extract_save_tables.py [--check]
"""

from __future__ import annotations

import argparse
import re
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ByteTable:
    values: bytes
    first_line: int
    last_line: int


def _braced_bytes(lines: list[str], start: int) -> ByteTable:
    """The hex bytes of the first ``gcnew array< Byte >{ ... }`` at or after line ``start``."""
    gcnew_line = next(i for i in range(start, len(lines)) if "gcnew" in lines[i])
    text = "\n".join(lines[gcnew_line:])
    opening = text.index("{")
    closing = text.index("}", opening)
    hex_bytes = re.findall(r"0x([0-9A-Fa-f]{2})\b", text[opening:closing])
    table = ByteTable(
        values=bytes(int(token, 16) for token in hex_bytes),
        first_line=gcnew_line + text[:opening].count("\n") + 1,
        last_line=gcnew_line + text[:closing].count("\n") + 1,
    )
    return table


def _find(lines: list[str], pattern: str) -> int:
    index = next(i for i, line in enumerate(lines) if re.search(pattern, line))
    return index


def _hex_literal(values: bytes, per_line: int = 16) -> str:
    rows = [values[offset : offset + per_line] for offset in range(0, len(values), per_line)]
    if len(rows) == 1:
        return f'bytes.fromhex("{rows[0].hex(" ")}")'
    body = "\n".join(f'    "{row.hex(" ")} "' for row in rows)
    return f"bytes.fromhex(\n{body}\n)"


def render_module(tables: dict[str, ByteTable], sources: dict[str, str]) -> str:
    def entry(name: str, comment: str) -> str:
        table = tables[name]
        lines = (
            f"{table.first_line}"
            if table.first_line == table.last_line
            else f"{table.first_line}-{table.last_line}"
        )
        return f"# {comment}\n# ({sources[name]}:{lines}).\n{name} = {_hex_literal(table.values)}\n"

    module = f'''"""Constants for decrypting a save file.

Extracted from ``legacy/SaveDataEncryption.cpp`` and ``legacy/PSPCryptoEngine.cpp``
by ``scripts/extract_save_tables.py``; do not edit by hand. Only the keys
decryption reaches are kept.
"""

from __future__ import annotations

{entry("SUBSTITUTION_TABLE", "Game layer: GetDecryptionTable, applied to every byte")}
{entry("GAME_KEY", "System layer: PSPCryptoEngine::mhp3_gamekey, XORed into the header")}
{entry("SD_KEY_6", "System layer: GetSDKey( 6 )")}
{entry("SD_KEY_7", "System layer: GetSDKey( 7 )")}
{entry("AES_KEY_0X12", "System layer: getAESKeyFromSeed( 0x12 ), decrypts the key block")}
{entry("AES_KEY_0X64", "System layer: getAESKeyFromSeed( 0x64 ), decrypts the counter stream")}'''
    return module.rstrip("\n") + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--check", action="store_true", help="fail if the committed module differs")
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parent.parent
    game_layer = "SaveDataEncryption.cpp"
    system_layer = "PSPCryptoEngine.cpp"
    game_lines = (repo_root / "legacy" / game_layer).read_text(encoding="utf-8").splitlines()
    system_lines = (repo_root / "legacy" / system_layer).read_text(encoding="utf-8").splitlines()
    tables = {
        "SUBSTITUTION_TABLE": _braced_bytes(
            game_lines, _find(game_lines, r"GetDecryptionTable\(\)")
        ),
        "GAME_KEY": _braced_bytes(system_lines, _find(system_lines, r"mhp3_gamekey\s*=")),
        "SD_KEY_6": _braced_bytes(system_lines, _find(system_lines, r"case 6:")),
        "SD_KEY_7": _braced_bytes(system_lines, _find(system_lines, r"case 7:")),
        "AES_KEY_0X12": _braced_bytes(system_lines, _find(system_lines, r"case 0x12:")),
        "AES_KEY_0X64": _braced_bytes(system_lines, _find(system_lines, r"case 0x64:")),
    }
    sizes = {name: len(table.values) for name, table in tables.items()}
    expected = {name: 256 if name == "SUBSTITUTION_TABLE" else 16 for name in tables}
    if sizes != expected:
        raise SystemExit(f"unexpected table sizes {sizes}")
    sources = {
        name: game_layer if name == "SUBSTITUTION_TABLE" else system_layer for name in tables
    }
    module = render_module(tables, sources)
    output = repo_root / "src" / "mhp3ass" / "savefile" / "tables.py"
    if args.check:
        if output.read_text(encoding="utf-8") != module:
            raise SystemExit(f"{output.relative_to(repo_root)} differs from legacy/")
        print(f"{output.relative_to(repo_root)} matches legacy/")
        return
    output.write_text(module, encoding="utf-8")
    print(f"wrote {output.relative_to(repo_root)}")


if __name__ == "__main__":
    main()
