"""My-charms loading and saving against the harness's LoadCustom dump (ModelDump.cpp)."""

from __future__ import annotations

from typing import Any

import pytest

from mhp3ass.charms.my_charms import (
    LineOutcome,
    MyCharmsFileError,
    load_my_charm_lines,
    load_my_charms,
    load_query_my_charms,
    my_charms_illegal,
    my_charms_text,
    save_my_charms,
)
from mhp3ass.charms.naming import charm_name
from mhp3ass.model import AbilityPair, Charm


@pytest.fixture(scope="module")
def my_charms_dir(repo_root):
    return repo_root / "tests" / "models" / "mycharms"


def _loaded_files(models_golden: Any, crashed: bool) -> list[Any]:
    files = [
        entry
        for entry in models_golden["load_custom"]
        if (entry["exception"] is not None) == crashed
    ]
    return files


def test_golden_covers_loading_and_crashing_files(models_golden):
    assert [
        len(_loaded_files(models_golden, crashed=False)),
        len(_loaded_files(models_golden, crashed=True)),
    ] == [2, 3]


def test_loading_matches_golden(models_golden, my_charms_dir, teamhgg_game, validity):
    mismatched = []
    for entry in _loaded_files(models_golden, crashed=False):
        loaded = load_my_charms(my_charms_dir / entry["file"], teamhgg_game, validity)
        ours = {
            "lines": [{"line": line.line, "outcome": line.outcome.value} for line in loaded.lines],
            "charms": [charm_name(charm) for charm in loaded.charms],
            "cheater_message": loaded.cheater_message,
            "saved": my_charms_text(loaded.charms),
        }
        golden = {
            "lines": entry["lines"],
            "charms": [charm["name"] for charm in entry["charms"]],
            "cheater_message": entry["cheater_message"],
            "saved": entry["saved"],
        }
        if ours != golden:
            mismatched.append({"file": entry["file"], "ours": ours, "golden": golden})

    assert mismatched == []


def test_crashing_files_raise_where_the_original_throws(
    models_golden, my_charms_dir, teamhgg_game, validity
):
    # The original's exception per file, and the Python error the port raises in its place.
    # split_fields reports RemoveQuotes' out-of-range read as a ValueError.
    expected_causes = {
        "03-bad-slots.txt": ("FormatException", ValueError),
        "04-four-slots.txt": ("IndexOutOfRangeException", IndexError),
        "05-bad-quotes.txt": ("IndexOutOfRangeException", ValueError),
    }
    ours = {}
    golden = {}
    for entry in _loaded_files(models_golden, crashed=True):
        with pytest.raises(MyCharmsFileError) as error:
            load_my_charms(my_charms_dir / entry["file"], teamhgg_game, validity)
        dotnet_type, python_cause = expected_causes[entry["file"]]
        ours[entry["file"]] = [error.value.line, dotnet_type, type(error.value.cause)]
        golden[entry["file"]] = [
            entry["exception"]["line"],
            entry["exception"]["type"],
            python_cause,
        ]

    assert ours == golden


def test_lines_skip_comments_and_report_each_outcome(teamhgg_game, validity):
    lines = ["#comment", "", "1,Attack,3,,", "1,Attack,3"]
    loaded = load_my_charm_lines(lines, game=teamhgg_game, validity=validity)

    assert [
        [(line.line, line.outcome) for line in loaded.lines],
        [charm_name(charm) for charm in loaded.charms],
    ] == [
        [("1,Attack,3,,", LineOutcome.ACCEPTED), ("1,Attack,3", LineOutcome.WRONG_FIELD_COUNT)],
        ["+3 Attack O--"],
    ]


def test_loaded_charms_are_marked_custom(my_charms_dir, teamhgg_game, validity):
    loaded = load_my_charms(my_charms_dir / "01-valid.txt", teamhgg_game, validity)

    assert [len(loaded.charms) > 0, all(charm.custom for charm in loaded.charms)] == [True, True]


def test_save_writes_utf8_without_bom_and_crlf(tmp_path, teamhgg_game):
    charm = Charm(num_slots=1, abilities=[AbilityPair(ability=teamhgg_game.abilities[0], amount=3)])
    path = tmp_path / "mycharms.txt"
    save_my_charms(path, [charm])

    assert (
        path.read_bytes() == b"#Format: NumSlots,Skill1,Points1,Skill2,Points2\r\n1,Attack,3,,\r\n"
    )


@pytest.mark.parametrize(
    ("line", "cause"),
    [
        ("1,Attack,3", "Incorrect number of commas"),
        ("1,Nothing,3,,", '"Nothing": No such skill'),
        ("1,Attack,three,,", "Could not read skill points"),
    ],
)
def test_query_charm_lines_raise_where_the_gui_shows_a_message(teamhgg_game, validity, line, cause):
    lines = ["1,Attack,3,,", line]

    with pytest.raises(MyCharmsFileError, match=cause) as error:
        load_query_my_charms(lines, game=teamhgg_game, validity=validity)

    assert error.value.line == line


def test_query_charm_lines_skip_and_count_rejected_charms(teamhgg_game, validity):
    lines = ["1,Attack,3,,", "3,Attack,99,,", "0,Attack,1,,"]
    loaded = load_query_my_charms(lines, game=teamhgg_game, validity=validity)

    assert [[charm_name(charm) for charm in loaded.charms], my_charms_illegal(loaded)] == [
        ["+3 Attack O--", "+1 Attack ---"],
        1,
    ]
