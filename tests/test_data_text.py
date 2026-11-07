"""Text handling against the .NET behaviour it reproduces."""

from __future__ import annotations

import pytest

from mhp3ass.data.text import (
    as_unsigned,
    dotnet_trim,
    read_lines,
    split_fields,
    to_int32,
    to_uint32,
)


def test_read_lines_breaks_only_on_cr_and_lf(tmp_path):
    path = tmp_path / "lines.txt"
    path.write_bytes(b"a\x0cb\r\nc\rd\ne\xe2\x80\xa8f")

    # \x0c and U+2028 are line breaks for str.splitlines but not for StreamReader.ReadLine.
    assert read_lines(path) == ["a\x0cb", "c", "d", "e\u2028f"]


def test_read_lines_final_line_break_adds_no_line(tmp_path):
    path = tmp_path / "lines.txt"
    path.write_bytes(b"a\n\nb\n")

    assert read_lines(path) == ["a", "", "b"]


def test_read_lines_strips_utf8_bom(tmp_path):
    path = tmp_path / "lines.txt"
    path.write_bytes(b"\xef\xbb\xbfa,b\n")

    assert read_lines(path) == ["a,b"]


def test_read_lines_decodes_utf16_with_bom(tmp_path):
    path = tmp_path / "lines.txt"
    path.write_bytes("﻿Jäger\n".encode("utf-16-le"))

    assert read_lines(path) == ["Jäger"]


def test_trim_keeps_separators_python_treats_as_space():
    # \x1c-\x1f count as space for str.strip but not for String.Trim.
    assert dotnet_trim("\x1c a b 　") == "\x1c a b"


def test_split_fields_trims_the_line_but_not_fields():
    assert split_fields('  "a", b ,c  ') == ['"a"', " b ", "c"]


@pytest.mark.parametrize("text", ["1_0", "\u0661", "", "1.0", "0x10"])
def test_to_int32_rejects_what_convert_rejects(text):
    with pytest.raises(ValueError):
        to_int32(text)


def test_to_int32_accepts_sign_and_surrounding_space():
    assert [to_int32(" -5 "), to_int32("+7")] == [-5, 7]


def test_to_int32_range():
    with pytest.raises(OverflowError):
        to_int32("2147483648")


def test_to_uint32_rejects_negative():
    with pytest.raises(OverflowError):
        to_uint32("-1")


def test_as_unsigned_wraps_like_cpp():
    assert [as_unsigned(-1), as_unsigned(2**32 + 5)] == [2**32 - 1, 5]
