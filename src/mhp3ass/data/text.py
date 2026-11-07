"""Text handling that matches the .NET calls the legacy loaders make.

The reference is .NET Framework 4.8, which the GUI and harness builds
target. Python's defaults differ from it in small ways that change parsing:
``str.splitlines`` breaks on more characters than ``StreamReader.ReadLine``,
``str.strip`` removes more than ``String.Trim``, and ``int()`` accepts
underscores and Unicode digits that ``Convert.ToInt32`` rejects.
"""

from __future__ import annotations

import codecs
import re
from pathlib import Path

# String.Trim's characters on .NET Framework 4.8, found by probing every BMP
# character on that runtime. Fixed here so Python's Unicode tables can't drift.
_TRIM_CHARS = "".join(
    chr(code_point)
    for code_point in [
        *range(0x0009, 0x000D + 1),
        0x0020,
        0x0085,
        0x00A0,
        0x1680,
        *range(0x2000, 0x200A + 1),
        0x2028,
        0x2029,
        0x202F,
        0x205F,
        0x3000,
    ]
)
# NumberStyles.Integer: optional white space (U+0009-U+000D, U+0020) around an
# optional sign and ASCII digits. .NET also ignores NULs after the trailing white space.
_INTEGER = re.compile(r"[\t\n\v\f\r ]*([+-]?)([0-9]+)[\t\n\v\f\r ]*\x00*")


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


def dotnet_trim(text: str) -> str:
    """``String.Trim()``."""
    trimmed = text.strip(_TRIM_CHARS)
    return trimmed


def _check_remove_quotes(field: str) -> None:
    """Raise where ``Utility::RemoveQuotes`` (Common.cpp:12-19) would throw.

    It trims the field, then reads its first character and, after dropping
    a leading quote, its last character, without checking the length: a
    field that trims to nothing or to a lone quote throws
    IndexOutOfRangeException.
    """
    if field == "":
        return
    trimmed = dotnet_trim(field)
    if trimmed == "" or trimmed == '"':
        raise ValueError(f"field {field!r} makes the original's RemoveQuotes fail")


def split_fields(line: str, separator: str = ",") -> list[str]:
    """``Utility::SplitString`` (Common.cpp:21-38).

    Trims the whole line, then splits on ``separator``. The original calls
    ``RemoveQuotes`` on each field but discards the result, so quotes and
    per-field white space are kept; the call still fails on some fields.
    """
    fields = dotnet_trim(line).split(separator)
    for field in fields:
        _check_remove_quotes(field)
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


def to_boolean(text: str) -> bool:
    """``Convert::ToBoolean( String^ )``, which is ``Boolean.Parse``.

    "True" or "False" in any ASCII case, after trimming white space and NULs.
    Non-ASCII case variants are rejected; whether .NET accepts any is unprobed.
    """
    trimmed = text.strip(_TRIM_CHARS + "\x00")
    lowered = trimmed.lower() if trimmed.isascii() else trimmed
    if lowered not in ("true", "false"):
        raise ValueError(f"{text!r} is not a valid Boolean")
    value = lowered == "true"
    return value


def as_unsigned(value: int) -> int:
    """Store ``value`` in a C++ ``unsigned`` (32-bit, wraps on overflow and underflow)."""
    wrapped = value & 0xFFFFFFFF
    return wrapped
