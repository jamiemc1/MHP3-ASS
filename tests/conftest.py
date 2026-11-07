from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from data_rows import armor_row, decoration_row
from goldens import SearchGolden, read_golden, read_search_goldens
from mhp3ass.charms.generation import CharmTables, generate_charm_tables
from mhp3ass.data import GameData, apply_language, load_game_data


@pytest.fixture(scope="session")
def repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


@pytest.fixture
def minimal_data_files() -> dict[str, str]:
    """A tiny but complete data set: two abilities, two materials, one armour per slot,
    one decoration. Tests replace single files to isolate one loading rule."""
    files = {
        "components.txt": "Ore,2\nGem,7\n",
        "tags.txt": "Offensive\n",
        "skills.txt": (
            "#name,jname,ability,jability,points,type,tag,order\n"
            "Attack Up,j,Attack,j,10,0,Offensive,0\n"
            "Defense Up,j,Defense,j,10,0,,1\n"
        ),
        "head.txt": armor_row("Cap") + "\n",
        "body.txt": armor_row("Mail") + "\n",
        "arms.txt": armor_row("Vambraces") + "\n",
        "waist.txt": armor_row("Tasset") + "\n",
        "legs.txt": armor_row("Greaves") + "\n",
        "decorations.txt": decoration_row("Attack Jewel") + "\n",
    }
    return files


@pytest.fixture
def minimal_language_files() -> dict[str, str]:
    """A translation of ``minimal_data_files``: every record renamed with a "T " prefix."""
    files = {
        "tags.txt": "T All\nT Misc\nT Offensive\n",
        "components.txt": "T Ore\nT Gem\n",
        "head.txt": "T Cap\n",
        "body.txt": "T Mail\n",
        "arms.txt": "T Vambraces\n",
        "waist.txt": "T Tasset\n",
        "legs.txt": "T Greaves\n",
        "decorations.txt": "T Attack Jewel\n",
        "skills.txt": "T Attack\nT Defense\nT Attack Up\nT Defense Up\n",
    }
    return files


@pytest.fixture
def write_files(tmp_path: Path):
    """Write a {file name: content} dict into a fresh folder and return the folder."""

    def write(files: dict[str, str], folder_name: str = "Data") -> Path:
        folder = tmp_path / folder_name
        folder.mkdir()
        for name, content in files.items():
            (folder / name).write_text(content, encoding="utf-8")
        return folder

    return write


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
def charm_database_golden(golden_data_dir: Path) -> Any:
    """Harness dump of CharmDatabase::GenerateCharmTable, names in English (TeamHGG)."""
    return read_golden(golden_data_dir / "charm-database.json.gz")


@pytest.fixture(scope="session")
def models_golden(golden_data_dir: Path) -> Any:
    """Harness dump-models output (ModelDump.cpp), names in English (TeamHGG)."""
    return read_golden(golden_data_dir / "models.json.gz")


@pytest.fixture(scope="session")
def teamhgg_game(legacy_data_dir: Path) -> GameData:
    """Game data in English (TeamHGG), the GUI's default language and the charm golden's.

    Shared across the session: tests must not mutate it.
    """
    game = load_game_data(legacy_data_dir)
    apply_language(game, legacy_data_dir / "Languages" / "English (TeamHGG)")
    return game


@pytest.fixture(scope="session")
def charm_tables(teamhgg_game: GameData) -> CharmTables:
    """Generated charm tables for ``teamhgg_game`` (about a second). Tests must not mutate them."""
    return generate_charm_tables(teamhgg_game)


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
def gui_captures_dir(savefile_dir: Path) -> Path:
    """Searches captured from the original GUI (scripts/windows/capture-gui-searches.ps1)."""
    captures_dir = savefile_dir / "gui-captures"
    if not captures_dir.is_dir():
        pytest.skip("no GUI captures in tests/savefile/gui-captures")
    return captures_dir
