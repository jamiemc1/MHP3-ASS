from __future__ import annotations

import stat
from pathlib import Path

import pytest

from mhp3ass.set_export import append_set, export_entry, export_file


def test_sets_go_to_the_folder_the_tui_was_started_from():
    path = export_file(export_dir=None, launch_dir=Path("/work"))

    assert path == Path("/work/mhp3-ass-sets.md")


def test_an_export_folder_replaces_it():
    path = export_file(export_dir=Path("/sets"), launch_dir=Path("/work"))

    assert path == Path("/sets/mhp3-ass-sets.md")


def test_a_relative_export_folder_is_under_the_start_folder():
    path = export_file(export_dir=Path("notes"), launch_dir=Path("/work"))

    assert path == Path("/work/notes/mhp3-ass-sets.md")


def test_a_tilde_in_the_export_folder_is_the_home_folder():
    path = export_file(export_dir=Path("~/sets"), launch_dir=Path("/work"))

    assert path == Path.home() / "sets" / "mhp3-ass-sets.md"


@pytest.mark.parametrize(
    ("tail", "entry"),
    [
        (b"", "# MHP3 Armor Set Search: sets\n\n---\n\n## Set\n"),
        (b"e\n", "\n---\n\n## Set\n"),
        (b"\n\n", "---\n\n## Set\n"),
        (b"xe", "\n\n---\n\n## Set\n"),
    ],
)
def test_each_entry_starts_with_a_rule_a_blank_line_after_what_is_there(tail, entry):
    assert export_entry("## Set\n", file_tail=tail) == entry


def test_two_exports_make_two_blocks_under_one_title(tmp_path):
    path = tmp_path / "mhp3-ass-sets.md"

    append_set(path, "## First\n\nBlademaster ♂\n")
    append_set(path, "## Second\n\nGunner ♀\n")

    assert path.read_text(encoding="utf-8") == (
        "# MHP3 Armor Set Search: sets\n"
        "\n"
        "---\n"
        "\n"
        "## First\n"
        "\n"
        "Blademaster ♂\n"
        "\n"
        "---\n"
        "\n"
        "## Second\n"
        "\n"
        "Gunner ♀\n"
    )


def test_a_file_edited_without_a_last_newline_gets_its_blank_line(tmp_path):
    path = tmp_path / "mhp3-ass-sets.md"
    path.write_bytes(b"my notes")

    append_set(path, "## Set\n")

    assert path.read_bytes() == b"my notes\n\n---\n\n## Set\n"


def test_a_missing_folder_raises_and_is_not_made(tmp_path):
    path = tmp_path / "gone" / "mhp3-ass-sets.md"

    with pytest.raises(FileNotFoundError):
        append_set(path, "## Set\n")

    assert not path.parent.exists()


@pytest.fixture
def read_only_folder(tmp_path):
    folder = tmp_path / "locked"
    folder.mkdir()
    folder.chmod(stat.S_IRUSR | stat.S_IXUSR)
    yield folder
    folder.chmod(stat.S_IRWXU)


def test_an_unwritable_folder_raises_and_gets_no_file(read_only_folder):
    path = read_only_folder / "mhp3-ass-sets.md"

    with pytest.raises(PermissionError):
        append_set(path, "## Set\n")

    assert list(read_only_folder.iterdir()) == []
