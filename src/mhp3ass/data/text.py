"""Text handling that matches the .NET calls the legacy loaders make.

Python's defaults differ from .NET's in small ways that change parsing:
``str.splitlines`` breaks on more characters than ``StreamReader.ReadLine``,
``str.strip`` removes more than ``String.Trim``, and ``int()`` accepts
underscores and Unicode digits that ``Convert.ToInt32`` rejects.
"""

from __future__ import annotations

import codecs
import re
import unicodedata
from pathlib import Path

# NumberStyles.Integer: optional white space (U+0009-U+000D, U+0020) around an
# optional sign and ASCII digits.
_INTEGER = re.compile(r"[\t\n\v\f\r ]*([+-]?)([0-9]+)[\t\n\v\f\r ]*")


def read_lines(path: Path) -> list[str]:
    """Lines as ``StreamReader.ReadLine`` returns them until ``EndOfStream``.

    The encoding comes from a byte order mark (UTF-8, UTF-16 or UTF-32),
    defaulting to UTF-8. Lines end at ``\\r\\n``, ``\\r`` or ``\\n``; a final
    line break does not start another line.
    """
    data = path.read_bytes()
    boms = [
        (codecs.BOM_UTF32_LE, "utf-32-le"),
        (codecs.BOM_UTF32_BE, "utf-32-be"),
        (codecs.BOM_UTF8, "utf-8"),
        (codecs.BOM_UTF16_LE, "utf-16-le"),
        (codecs.BOM_UTF16_BE, "utf-16-be"),
    ]
    encoding = "utf-8"
    for bom, bom_encoding in boms:
        if data.startswith(bom):
            data = data[len(bom) :]
            encoding = bom_encoding
            break
    text = data.decode(encoding, errors="replace")
    if not text:
        return []
    lines = re.split(r"\r\n|\r|\n", text)
    if text.endswith(("\n", "\r")):
        lines.pop()
    return lines


def _is_dotnet_white_space(char: str) -> bool:
    """``Char.IsWhiteSpace``: Unicode space separators plus \\t-\\r and U+0085."""
    return char in "\t\n\v\f\r\x85" or unicodedata.category(char) in ("Zs", "Zl", "Zp")


def dotnet_trim(text: str) -> str:
    """``String.Trim()``."""
    start = 0
    end = len(text)
    while start < end and _is_dotnet_white_space(text[start]):
        start += 1
    while end > start and _is_dotnet_white_space(text[end - 1]):
        end -= 1
    trimmed = text[start:end]
    return trimmed


def split_fields(line: str, separator: str = ",") -> list[str]:
    """``Utility::SplitString`` (Common.cpp:21-38).

    Trims the whole line, then splits on ``separator``. The original calls
    ``RemoveQuotes`` on each field but discards the result, so quotes and
    per-field white space are kept.
    """
    fields = dotnet_trim(line).split(separator)
    return fields


def _parse_integer(text: str, minimum: int, maximum: int, type_name: str) -> int:
    match = _INTEGER.fullmatch(text)
    if match is None:
        raise ValueError(f"{text!r} is not a valid {type_name}")
    sign, digits = match.groups()
    value = -int(digits) if sign == "-" else int(digits)
    if not minimum <= value <= maximum:
        raise OverflowError(f"{text!r} is outside the {type_name} range")
    return value


def to_int32(text: str) -> int:
    """``Convert::ToInt32( String^ )``."""
    value = _parse_integer(text, minimum=-(2**31), maximum=2**31 - 1, type_name="Int32")
    return value


def to_uint32(text: str) -> int:
    """``Convert::ToUInt32( String^ )``."""
    value = _parse_integer(text, minimum=0, maximum=2**32 - 1, type_name="UInt32")
    return value


def as_unsigned(value: int) -> int:
    """Store ``value`` in a C++ ``unsigned`` (32-bit, wraps on overflow and underflow)."""
    wrapped = value & 0xFFFFFFFF
    return wrapped
