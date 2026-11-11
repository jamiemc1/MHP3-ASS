"""``settings.cfg`` save and load against the harness's ``results`` goldens
(``harness/src/ResultsDump.cpp``).

Each corpus query's search is saved as ``SaveConfig`` writes it, then loaded as
``LoadConfig`` does: into a fresh result set (start-up) and into the one the
search filled (quirk 46). Each GUI capture's ``settings.cfg`` is loaded once.
Every step must match the harness: where each line went, the list sizes, the
charm map, the loaded solutions' stats and the file the load re-saves.

The default run checks the goldens of at most 8,000 lines; ``pytest -m fuzz``
checks every one.
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Any

import pytest

from goldens import ResultsGolden, read_results_goldens
from mhp3ass.data import GameData
from mhp3ass.data.languages import language_folders
from mhp3ass.query import SearchSpec
from mhp3ass.results.result_set import ResultSet, SearchResult, lines_of, skill_indices
from mhp3ass.results.view import ResultsView
from mhp3ass.search import SearchData
from mhp3ass.settings_cfg import SettingsCfg, load_results, read_settings_cfg
from mhp3ass.skill_picker import SkillSelection
from mhp3ass.solution.state import Solution


def _crlf_sha256(lines: Iterable[str]) -> str:
    """``SaveConfig``'s solution lines as ``StreamWriter`` writes them: UTF-8, CRLF."""
    text = "".join(f"{line}\r\n" for line in lines)
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return digest


def _stats_sha256(solutions: Sequence[Solution]) -> str:
    """The harness's ``StatsSha256``: what ``CalculateData`` and the slot fields leave."""
    rows = []
    for solution in solutions:
        if solution.slots_spare is None:
            raise ValueError("a loaded solution has its spare slots from its line")
        fields = [
            solution.defence,
            solution.max_defence,
            solution.rarity,
            solution.difficulty,
            solution.fire_res,
            solution.ice_res,
            solution.thunder_res,
            solution.water_res,
            solution.dragon_res,
            solution.total_slots_spare,
            *solution.slots_spare[1:4],
        ]
        rows.append(" ".join(str(field) for field in fields))
    text = "".join(f"{row}\n" for row in rows)
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return digest


def _charm_map(view: ResultsView) -> list[dict[str, Any]]:
    charm_map = [
        {"name": name, "count": len(positions)} for name, positions in view.by_charm.items()
    ]
    return charm_map


def _placements(lines: Sequence[str], view: ResultsView, game: GameData) -> str:
    """Where each loaded line went, read back from the lists: ``a`` all
    solutions, ``n`` the charm-free list, ``d`` dropped as a duplicate. A ``?``
    marks list entries no line accounts for."""
    skill_index = skill_indices(game)
    kept = lines_of(view.all_solutions, skill_index)
    charm_free = lines_of(view.no_charm_solutions, skill_index)
    kept_at = 0
    charm_free_at = 0
    placements = []
    for line in lines:
        if kept_at < len(kept) and line == kept[kept_at]:
            placements.append("a")
            kept_at += 1
        elif charm_free_at < len(charm_free) and line == charm_free[charm_free_at]:
            placements.append("n")
            charm_free_at += 1
        else:
            placements.append("d")
    if kept_at < len(kept) or charm_free_at < len(charm_free):
        placements.append("?")
    return "".join(placements)


def _settings_holding(lines: Sequence[str]) -> SettingsCfg:
    """A version 2 file ``check_header`` accepts, holding ``lines``."""
    empty_row = SkillSelection(
        blademaster_filter=-1, blademaster_skill=-1, gunner_filter=-1, gunner_skill=-1
    )
    settings = SettingsCfg(
        version="2",
        language_index=0,
        last_search_gunner=False,
        hunter_tab=0,
        male=True,
        allow_bad=False,
        allow_piercings=True,
        allow_event=True,
        allow_low_rank=True,
        sort_index=-1,
        charm_select_index=-1,
        hr=6,
        elder_star=6,
        weapon_slots=0,
        skill_selections=(empty_row,) * 6,
        solution_lines=tuple(lines),
    )
    return settings


def _load_step(
    step: str, settings: SettingsCfg, game: GameData, results: ResultSet, language_count: int
) -> dict[str, Any]:
    view = load_results(
        settings=settings, game=game, results=results, language_count=language_count
    )
    lines = settings.solution_lines
    observed = {
        "step": step,
        "line_count": len(lines),
        "placements": _placements(lines, view, game),
        "all_count": len(view.all_solutions),
        "no_charm_count": len(view.no_charm_solutions),
        "charm_map": _charm_map(view),
        "all_stats_sha256": _stats_sha256(view.all_solutions),
        "no_charm_stats_sha256": _stats_sha256(view.no_charm_solutions),
        "resaved_sha256": _crlf_sha256(lines_of(view.all_solutions, skill_indices(game))),
    }
    return observed


def _query_steps(search: SearchResult, game: GameData, language_count: int) -> list[dict[str, Any]]:
    """The harness's three ``results`` steps for one search; none when no worker ran."""
    if search.worker_count == 0:
        return []
    view = ResultsView.from_search(search.results)
    saved_lines = lines_of(view.all_solutions, skill_indices(game))
    saved = {
        "step": "save",
        "all_count": len(view.all_solutions),
        "no_charm_count": len(view.no_charm_solutions),
        "charm_map": _charm_map(view),
        "saved_sha256": _crlf_sha256(saved_lines),
    }
    settings = _settings_holding(saved_lines)
    # A copy, so the session's search result stays as the search left it.
    searched = ResultSet(
        existing_armor={name: set(hashes) for name, hashes in search.results.existing_armor.items()}
    )
    steps = [
        saved,
        _load_step("load", settings, game, ResultSet(), language_count),
        _load_step("load_after_search", settings, game, searched, language_count),
    ]
    return steps


def _step_differences(ours: list[dict[str, Any]], golden: list[dict[str, Any]]) -> str | None:
    if ours == golden:
        return None
    ours_by_step = {step["step"]: step for step in ours}
    differing = []
    for golden_step in golden:
        our_step = ours_by_step.get(golden_step["step"], {})
        keys = sorted(key for key in golden_step if our_step.get(key) != golden_step[key])
        if keys:
            differing.append(f"{golden_step['step']}: {keys}")
    steps = f"{[step['step'] for step in ours]} vs {[step['step'] for step in golden]}"
    return f"steps {steps}; {'; '.join(differing)}"


@pytest.fixture(scope="session")
def language_count(legacy_data_dir) -> int:
    return len(language_folders(legacy_data_dir / "Languages"))


def _query_differences(
    goldens: list[ResultsGolden],
    searches: dict[str, SearchResult],
    search_data: dict[str, SearchData],
    language_count: int,
) -> dict[str, str]:
    found = {}
    for golden in goldens:
        if golden.query is None:
            raise ValueError(f"{golden.name} is a results-file golden")
        language = SearchSpec.from_json(golden.query).query.language
        ours = _query_steps(
            searches[golden.query["id"]], search_data[language].game, language_count
        )
        difference = _step_differences(ours, golden.steps)
        if difference is not None:
            found[golden.name] = difference
    return found


def _capture_differences(
    goldens: list[ResultsGolden],
    gui_captures_dir: Path,
    languages: list[str],
    search_data: dict[str, SearchData],
    language_count: int,
) -> dict[str, str]:
    found = {}
    for golden in goldens:
        capture = golden.name.removeprefix("capture-")
        settings = read_settings_cfg(gui_captures_dir / capture / "settings.cfg")
        game = search_data[languages[settings.language_index]].game
        ours = [_load_step("load", settings, game, ResultSet(), language_count)]
        difference = _step_differences(ours, golden.steps)
        if difference is not None:
            found[golden.name] = difference
    return found


def _largest_step(golden: ResultsGolden) -> int:
    """The most lines any step of ``golden`` saves or loads."""
    largest = max(
        (step.get("line_count", step.get("all_count", 0)) for step in golden.steps), default=0
    )
    return largest


def _in_default_run(goldens: list[ResultsGolden]) -> list[ResultsGolden]:
    """The goldens of at most 8,000 lines, which include the all-charm-free and
    mixed files behind quirks 45 and 46; ``-m fuzz`` checks every one."""
    selected = [golden for golden in goldens if _largest_step(golden) <= 8000]
    return selected


@pytest.fixture(scope="session")
def public_results_goldens(repo_root) -> list[ResultsGolden]:
    return read_results_goldens(repo_root / "tests" / "golden" / "results")


@pytest.fixture(scope="session")
def personal_results_goldens(savefile_dir) -> list[ResultsGolden]:
    golden_dir = savefile_dir / "golden" / "results"
    if not golden_dir.is_dir():
        pytest.skip("no personal results goldens; run scripts/windows/generate-goldens.ps1")
    return read_results_goldens(golden_dir)


@pytest.fixture(scope="session")
def personal_query_results_goldens(personal_results_goldens) -> list[ResultsGolden]:
    return [golden for golden in personal_results_goldens if golden.query is not None]


@pytest.fixture(scope="session")
def capture_results_goldens(personal_results_goldens) -> list[ResultsGolden]:
    return [golden for golden in personal_results_goldens if golden.query is None]


@pytest.fixture(scope="session")
def languages(legacy_data_dir) -> list[str]:
    return language_folders(legacy_data_dir / "Languages")


@pytest.mark.parametrize(
    ("selection", "count"),
    [
        pytest.param(_in_default_run, 6, id="default"),
        pytest.param(list, 10, id="all", marks=pytest.mark.fuzz),
    ],
)
def test_corpus_results_save_and_load_as_the_harness_does(
    public_results_goldens,
    pooled_searches,
    search_data_by_language,
    language_count,
    selection,
    count,
):
    goldens = selection(public_results_goldens)

    found = _query_differences(goldens, pooled_searches, search_data_by_language, language_count)

    assert [len(goldens), found] == [count, {}]


@pytest.mark.parametrize(
    ("selection", "count"),
    [
        pytest.param(_in_default_run, 5, id="default"),
        pytest.param(list, 12, id="all", marks=pytest.mark.fuzz),
    ],
)
def test_personal_results_save_and_load_as_the_harness_does(
    personal_query_results_goldens,
    personal_pooled_searches,
    search_data_by_language,
    language_count,
    selection,
    count,
):
    goldens = selection(personal_query_results_goldens)

    found = _query_differences(
        goldens, personal_pooled_searches, search_data_by_language, language_count
    )

    assert [len(goldens), found] == [count, {}]


@pytest.mark.parametrize(
    ("selection", "count"),
    [
        pytest.param(_in_default_run, 11, id="default"),
        pytest.param(list, 20, id="all", marks=pytest.mark.fuzz),
    ],
)
def test_gui_captures_load_as_the_harness_does(
    capture_results_goldens,
    gui_captures_dir,
    languages,
    search_data_by_language,
    language_count,
    selection,
    count,
):
    goldens = selection(capture_results_goldens)

    found = _capture_differences(
        goldens, gui_captures_dir, languages, search_data_by_language, language_count
    )

    assert [len(goldens), found] == [count, {}]


def test_the_default_run_covers_the_load_quirks(capture_results_goldens):
    names = [golden.name for golden in _in_default_run(capture_results_goldens)]

    assert {"capture-12", "capture-16", "capture-20"} <= set(names)
