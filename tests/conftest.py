from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from goldens import SearchGolden, read_golden, read_search_goldens


@pytest.fixture(scope="session")
def repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


@pytest.fixture(scope="session")
def legacy_data_dir(repo_root: Path) -> Path:
    """Game data shipped with the original application: the input both implementations read."""
    return repo_root / "legacy" / "Run" / "Data"


@pytest.fixture(scope="session")
def golden_data_dir(repo_root: Path) -> Path:
    return repo_root / "tests" / "golden" / "data"


@pytest.fixture(scope="session")
def game_data(golden_data_dir: Path) -> Any:
    """Harness dump of every loaded table, before any language is applied."""
    return read_golden(golden_data_dir / "game-data.json.gz")


@pytest.fixture(scope="session")
def language_names(golden_data_dir: Path) -> dict[str, Any]:
    """Harness name dumps keyed by language folder name."""
    names_dir = golden_data_dir / "names"
    names_by_language = {
        path.name.removesuffix(".json.gz"): read_golden(path)
        for path in sorted(names_dir.glob("*.json.gz"))
    }
    return names_by_language


@pytest.fixture(scope="session")
def search_goldens(repo_root: Path) -> list[SearchGolden]:
    """Committed corpus queries and their harness results."""
    return read_search_goldens(
        corpus_dir=repo_root / "tests" / "corpus",
        golden_dir=repo_root / "tests" / "golden" / "search",
    )


@pytest.fixture(scope="session")
def savefile_dir(repo_root: Path) -> Path:
    """Gitignored folder holding the user's own save and reference outputs."""
    return repo_root / "tests" / "savefile"


@pytest.fixture(scope="session")
def personal_search_goldens(savefile_dir: Path) -> list[SearchGolden]:
    """Corpus queries built from a personal charm list, kept out of git with their results."""
    corpus_dir = savefile_dir / "corpus"
    if not corpus_dir.is_dir():
        pytest.skip("no personal corpus in tests/savefile/corpus")
    return read_search_goldens(corpus_dir=corpus_dir, golden_dir=savefile_dir / "golden" / "search")


@pytest.fixture(scope="session")
def save_golden(savefile_dir: Path) -> Any:
    path = savefile_dir / "golden" / "save.json"
    if not path.is_file():
        pytest.skip("no save-derived golden; run scripts/windows/generate-goldens.ps1 with a save")
    return read_golden(path)


@pytest.fixture(scope="session")
def gui_imported_mycharms(savefile_dir: Path) -> list[str]:
    """mycharms.txt as the original GUI wrote it after importing the save."""
    path = savefile_dir / "mycharms.imported.txt"
    if not path.is_file():
        pytest.skip("no mycharms.imported.txt captured from the GUI")
    return path.read_text(encoding="utf-8").splitlines()


@pytest.fixture(scope="session")
def gui_query_1b_solution_lines(savefile_dir: Path) -> list[str]:
    """Solution lines the original GUI saved in settings.cfg after running query 1b."""
    path = savefile_dir / "gui-query-1b.settings.cfg"
    if not path.is_file():
        pytest.skip("no settings.cfg captured from the GUI for query 1b")
    # settings.cfg version 2: 14 option lines and 24 skill lines, then one solution per line.
    solution_lines = path.read_text(encoding="utf-8").splitlines()[38:]
    return solution_lines
