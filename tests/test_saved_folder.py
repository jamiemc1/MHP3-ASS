from __future__ import annotations

import shutil

import pytest

from mhp3ass.saved_data import TuiFolders, TuiSettings
from mhp3ass.saved_folder import (
    ClearChoice,
    FolderChoice,
    change_folder,
    clear,
    clear_targets,
    folder_choices,
    saved_files_in,
    with_folder,
)


@pytest.fixture
def current(tmp_path):
    """The folder in use, with both files."""
    folder = tmp_path / "current"
    folder.mkdir()
    (folder / "settings.cfg").write_bytes(b"settings")
    (folder / "mycharms.txt").write_bytes(b"charms")
    return folder


@pytest.fixture
def empty_folder(tmp_path):
    folder = tmp_path / "empty"
    folder.mkdir()
    return folder


@pytest.fixture
def folder_with_my_charms(tmp_path):
    """A folder holding only a mycharms.txt, as a copied Windows install might."""
    folder = tmp_path / "windows"
    folder.mkdir()
    (folder / "mycharms.txt").write_bytes(b"other charms")
    return folder


@pytest.fixture
def a_file(tmp_path):
    path = tmp_path / "file"
    path.write_bytes(b"")
    return path


def test_an_empty_or_missing_folder_offers_move_or_fresh(current, empty_folder, tmp_path):
    assert [
        folder_choices(current, empty_folder),
        folder_choices(current, tmp_path / "not yet"),
    ] == [[FolderChoice.MOVE, FolderChoice.FRESH]] * 2


def test_a_folder_with_either_file_offers_only_use(current, folder_with_my_charms):
    assert folder_choices(current, folder_with_my_charms) == [FolderChoice.USE]


def test_the_same_folder_or_a_file_offers_nothing(current, a_file):
    assert [folder_choices(current, current / "."), folder_choices(current, a_file)] == [[], []]


def test_moving_takes_both_files(current, tmp_path):
    new = tmp_path / "a" / "new"

    change_folder(current, new, FolderChoice.MOVE)

    assert [saved_files_in(current), (new / "settings.cfg").read_bytes()] == [[], b"settings"]
    assert (new / "mycharms.txt").read_bytes() == b"charms"


def test_a_fresh_start_makes_the_folder_and_moves_nothing(current, tmp_path):
    new = tmp_path / "fresh"

    change_folder(current, new, FolderChoice.FRESH)

    assert [new.is_dir(), saved_files_in(new), len(saved_files_in(current))] == [True, [], 2]


def test_using_what_is_there_changes_no_file(current, folder_with_my_charms):
    change_folder(current, folder_with_my_charms, FolderChoice.USE)

    assert [len(saved_files_in(current)), saved_files_in(folder_with_my_charms)] == [
        2,
        [folder_with_my_charms / "mycharms.txt"],
    ]


def test_a_choice_not_offered_raises_before_moving(current, folder_with_my_charms):
    with pytest.raises(ValueError, match="can't move"):
        change_folder(current, folder_with_my_charms, FolderChoice.MOVE)

    assert (folder_with_my_charms / "mycharms.txt").read_bytes() == b"other charms"
    assert len(saved_files_in(current)) == 2


@pytest.fixture
def folders(tmp_path):
    own = tmp_path / "own"
    folders = TuiFolders(own=own, settings=TuiSettings(jobs=3, reverse=True), env={})
    return folders


def test_another_folder_is_kept_as_data_dir(folders, empty_folder):
    assert with_folder(folders, empty_folder) == TuiSettings(
        data_dir=empty_folder, jobs=3, reverse=True
    )


def test_the_tuis_own_folder_needs_no_data_dir(folders):
    assert with_folder(folders, folders.own) == TuiSettings(data_dir=None, jobs=3, reverse=True)


@pytest.mark.parametrize(
    ("choice", "names"),
    [
        (ClearChoice.SEARCH, ["settings.cfg"]),
        (ClearChoice.MY_CHARMS, ["mycharms.txt"]),
        (ClearChoice.EVERYTHING, ["settings.cfg", "mycharms.txt"]),
    ],
)
def test_clearing_deletes_what_it_names(current, choice, names):
    targets = clear_targets(current, choice)

    deleted = clear(current, choice)

    assert [[path.name for path in targets], deleted] == [names, targets]
    assert not any(path.exists() for path in targets)


def test_clearing_a_folder_without_the_files_deletes_nothing(empty_folder):
    assert clear(empty_folder, ClearChoice.EVERYTHING) == []


@pytest.fixture
def second_move_fails(monkeypatch):
    """shutil.move works once, then raises, as a full disk part-way would."""
    real_move = shutil.move
    calls = []

    def move(source, destination):
        calls.append(source)
        if len(calls) == 2:
            raise OSError("no space left")
        return real_move(source, destination)

    monkeypatch.setattr("shutil.move", move)


def test_a_failed_move_puts_the_moved_files_back(current, tmp_path, second_move_fails):
    new = tmp_path / "new"

    with pytest.raises(OSError, match="no space left"):
        change_folder(current, new, FolderChoice.MOVE)

    assert [[path.name for path in saved_files_in(current)], saved_files_in(new)] == [
        ["settings.cfg", "mycharms.txt"],
        [],
    ]
