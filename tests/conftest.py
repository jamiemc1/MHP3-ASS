from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from data_rows import armor_row, decoration_row
from goldens import (
    RelevanceGolden,
    SearchGolden,
    TraceGolden,
    read_golden,
    read_relevance_goldens,
    read_search_goldens,
    read_trace_goldens,
)
from mhp3ass.charms.generation import CharmTables, generate_charm_tables
from mhp3ass.charms.location import CharmLocationIndex
from mhp3ass.charms.validity import CharmValidity, build_charm_validity
from mhp3ass.data import GameData, apply_language, load_game_data
from mhp3ass.model import Ability, AbilityPair, Armor, Gender, HunterType
from mhp3ass.query import Query
from mhp3ass.savefile.game_layer import decrypt_game_layer
from mhp3ass.savefile.system_layer import decrypt_system_layer


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
def load_teamhgg_game(legacy_data_dir: Path) -> Callable[[], GameData]:
    """Loads a fresh copy of the game data in English (TeamHGG), for tests that mutate it."""

    def load() -> GameData:
        game = load_game_data(legacy_data_dir)
        apply_language(game, legacy_data_dir / "Languages" / "English (TeamHGG)")
        return game

    return load


@pytest.fixture(scope="session")
def teamhgg_game(load_teamhgg_game: Callable[[], GameData]) -> GameData:
    """Game data in English (TeamHGG), the GUI's default language and the charm golden's.

    Shared across the session: tests must not mutate it.
    """
    return load_teamhgg_game()


@pytest.fixture(scope="session")
def scratch_game(load_teamhgg_game: Callable[[], GameData]) -> GameData:
    """A game in English (TeamHGG) that tests may run queries on, which rewrite its
    relevance state (ability flags, armour no_skills and danger)."""
    return load_teamhgg_game()


@pytest.fixture(scope="session")
def scratch_charm_tables(scratch_game: GameData) -> CharmTables:
    """Charm tables for ``scratch_game``: they are keyed by its abilities."""
    return generate_charm_tables(scratch_game)


@pytest.fixture(scope="session")
def charm_tables(teamhgg_game: GameData) -> CharmTables:
    """Generated charm tables for ``teamhgg_game`` (about a second). Tests must not mutate them."""
    return generate_charm_tables(teamhgg_game)


@pytest.fixture(scope="session")
def validity(charm_tables: CharmTables, teamhgg_game: GameData) -> CharmValidity:
    """CharmExists / CharmIsIllegal over ``charm_tables``."""
    return build_charm_validity(charm_tables, ability_count=len(teamhgg_game.abilities))


@pytest.fixture(scope="session")
def charm_location_index(charm_tables: CharmTables, teamhgg_game: GameData) -> CharmLocationIndex:
    """FindCharm2's table entries grouped by ability, over ``charm_tables``."""
    return CharmLocationIndex.build(charm_tables, abilities=teamhgg_game.abilities)


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
def relevance_goldens(repo_root: Path) -> list[RelevanceGolden]:
    """Relevance output for every committed corpus, relevance-only and trace query."""
    tests_dir = repo_root / "tests"
    return read_relevance_goldens(
        query_dirs=[
            tests_dir / "corpus",
            tests_dir / "relevance",
            tests_dir / "traces" / "queries",
        ],
        golden_dir=tests_dir / "golden" / "relevance",
    )


@pytest.fixture
def attack() -> Ability:
    return Ability(name="Attack", static_index=0)


@pytest.fixture
def defense() -> Ability:
    return Ability(name="Defense", static_index=1)


@pytest.fixture
def make_armor() -> Callable[..., Armor]:
    """Builds an armour piece for pure-logic tests: HR 1, both genders and hunter types,
    no slots and no skills unless given."""

    def make(
        name: str = "Piece", abilities: list[tuple[Ability, int]] | None = None, **fields: Any
    ):
        values: dict[str, Any] = {
            "index": 0,
            "gender": Gender.BOTH_GENDERS,
            "hunter_type": HunterType.BOTH_TYPES,
            "rarity": 1,
            "num_slots": 0,
            "hr": 1,
            "elder_star": 1,
            "defence": 10,
            "max_defence": 20,
            "fire_res": 0,
            "water_res": 0,
            "ice_res": 0,
            "thunder_res": 0,
            "dragon_res": 0,
            "is_piercing": False,
        }
        values.update(fields)
        pairs = [AbilityPair(ability=ability, amount=amount) for ability, amount in abilities or []]
        armor = Armor(name=name, abilities=pairs, **values)
        return armor

    return make


@pytest.fixture
def make_query() -> Callable[..., Query]:
    """Builds a Blademaster, male, HR 6 / village 6 query with every armour toggle on."""

    def make(rel_abilities: list[Ability] | None = None, **fields: Any):
        values: dict[str, Any] = {
            "skills": [],
            "hunter_type": HunterType.BLADEMASTER,
            "gender": Gender.MALE,
            "hr": 6,
            "elder_star": 6,
            "weapon_slots_allowed": 0,
            "include_piercings": True,
            "allow_bad": False,
            "allow_event": True,
            "allow_low_rank": True,
        }
        values.update(fields)
        query = Query(rel_abilities=list(rel_abilities or []), **values)
        return query

    return make


@pytest.fixture
def attack_sharp_query_json() -> dict[str, Any]:
    """A valid query file's contents (Attack Up [Med] + Sharp Sword, HR 6), fresh per test."""
    spec = {
        "id": "t01",
        "description": "Attack Up [Med] + Sharp Sword",
        "language": "English (TeamHGG)",
        "hunter_type": "blademaster",
        "gender": "male",
        "hr": 6,
        "elder_star": 6,
        "weapon_slots": 0,
        "allow_bad": False,
        "include_piercings": True,
        "allow_event": True,
        "allow_low_rank": True,
        "skills": [1, 12],
        "skill_names": ["Attack Up [Med]", "Sharp Sword"],
    }
    return spec


@pytest.fixture(scope="session")
def best_decorations_golden(golden_data_dir: Path) -> Any:
    """Harness best-decorations output: the query-based GetBestDecoration grid."""
    return read_golden(golden_data_dir / "best-decorations.json.gz")


@pytest.fixture(scope="session")
def solution_probes_golden(golden_data_dir: Path) -> Any:
    """Harness solution-probes output: GetScore's point_score comparisons."""
    return read_golden(golden_data_dir / "solution-probes.json.gz")


@pytest.fixture(scope="session")
def charm_location_golden(golden_data_dir: Path) -> Any:
    """Harness charm-location output: FindCharm2 calls and parsed charm names."""
    return read_golden(golden_data_dir / "charm-location.json.gz")


@pytest.fixture(scope="session")
def games_by_language(legacy_data_dir: Path) -> dict[str, GameData]:
    """A game in each shipped language. Tests must not mutate them."""
    games = {}
    for language_dir in sorted((legacy_data_dir / "Languages").iterdir()):
        game = load_game_data(legacy_data_dir)
        apply_language(game, language_dir)
        games[language_dir.name] = game
    return games


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
def personal_relevance_goldens(savefile_dir: Path) -> list[RelevanceGolden]:
    """Relevance output for the personal corpus queries (their charm fields aren't read)."""
    corpus_dir = savefile_dir / "corpus"
    golden_dir = savefile_dir / "golden" / "relevance"
    if not corpus_dir.is_dir():
        pytest.skip("no personal corpus in tests/savefile/corpus")
    if not golden_dir.is_dir():
        pytest.skip("no personal relevance goldens; run scripts/windows/generate-goldens.ps1")
    return read_relevance_goldens(query_dirs=[corpus_dir], golden_dir=golden_dir)


@pytest.fixture(scope="session")
def trace_goldens(repo_root: Path) -> list[TraceGolden]:
    """MatchesQuery traces for every committed trace spec."""
    tests_dir = repo_root / "tests"
    return read_trace_goldens(
        spec_dir=tests_dir / "traces", golden_dir=tests_dir / "golden" / "traces"
    )


@pytest.fixture(scope="session")
def personal_trace_goldens(savefile_dir: Path) -> list[TraceGolden]:
    """MatchesQuery traces for the personal corpus queries."""
    spec_dir = savefile_dir / "traces"
    golden_dir = savefile_dir / "golden" / "traces"
    if not spec_dir.is_dir():
        pytest.skip("no personal trace specs in tests/savefile/traces")
    if not golden_dir.is_dir():
        pytest.skip("no personal trace goldens; run scripts/windows/generate-goldens.ps1")
    return read_trace_goldens(spec_dir=spec_dir, golden_dir=golden_dir)


@pytest.fixture(scope="session")
def save_bytes(savefile_dir: Path) -> bytes:
    """Your MHP3rd save file, as the import dialog reads it."""
    path = savefile_dir / "MHP3RD.BIN"
    if not path.is_file():
        pytest.skip("no save file in tests/savefile/MHP3RD.BIN")
    return path.read_bytes()


@pytest.fixture(scope="session")
def save_system_layer(save_bytes: bytes) -> bytes:
    """The save with its system layer decrypted (about a second)."""
    return decrypt_system_layer(save_bytes)


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


@pytest.fixture(scope="session")
def save_game_layer(save_system_layer: bytes) -> bytes:
    """The save with both layers decrypted."""
    return decrypt_game_layer(save_system_layer)
