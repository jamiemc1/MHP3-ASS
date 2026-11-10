"""Time the Python search: start-up, then each query's ``run_search``.

Not a test (timings on a laptop are too noisy to gate on): the output is a
Markdown report for PR bodies, to compare before and after a change. Every
time is the median of ``--runs`` runs, wall clock.

- **Start-up:** importing the package (``python -X importtime`` on the
  ``mhp3ass`` console script, in a new process), loading the data files,
  generating the charm tables, applying the language, building the charm
  checks, and formulating query 1a; then a cold ``mhp3ass search`` of 1a,
  start to finish in a new process
- **Searches:** each query's ``run_search`` on data already loaded (the TUI's
  warm path), split into the workers (each worker's loop and its duplicate
  removal, as ``run_search`` reports them) and everything else (my-charms
  loading, relevance, dispatch). Calls are combinations times workers, and
  µs/call is the workers' time over them. The solution count is checked
  against the query's golden manifest, so a report never times a search
  that found the wrong number. Peak RSS is the process's high-water mark
  so far, so it only grows down the table

Queries: the public corpus, the personal corpus when ``tests/savefile/corpus``
is there, and the heaviest fuzz queries (``--all-fuzz`` for all 500).

    uv run python scripts/benchmark_search.py
    uv run python scripts/benchmark_search.py --runs 1 --only 1a g18 --no-startup
"""

from __future__ import annotations

import argparse
import gc
import json
import math
import platform
import resource
import statistics
import subprocess
import sys
import sysconfig
import tempfile
import time
from collections.abc import Callable
from contextlib import nullcontext
from dataclasses import dataclass
from pathlib import Path

from mhp3ass.charms.generation import generate_charm_tables
from mhp3ass.charms.validity import build_charm_validity
from mhp3ass.data import apply_language, load_game_data
from mhp3ass.query import SearchSpec
from mhp3ass.relevance import formulate_query
from mhp3ass.results.result_set import SearchResult
from mhp3ass.search import SearchData, WorkerProgress, armor_choices, paused_gc, run_search


@dataclass(frozen=True)
class BenchmarkQuery:
    """A query file and the golden manifest its solution count is checked against."""

    name: str
    path: Path
    manifest_path: Path


@dataclass(frozen=True)
class SearchTiming:
    """One query's medians and the counts from its last run."""

    name: str
    worker_count: int
    calls: int
    accepted: int
    solutions: int
    search_seconds: float
    worker_seconds: float
    peak_rss_mb: float


def median_seconds(run: Callable[[], float], runs: int) -> float:
    """The median of ``runs`` timings that ``run`` returns."""
    timings = [run() for _ in range(runs)]
    median = statistics.median(timings)
    return median


def elapsed(action: Callable[[], object]) -> float:
    """How long ``action`` took, in seconds."""
    start = time.perf_counter()
    action()
    seconds = time.perf_counter() - start
    return seconds


def peak_rss_mb() -> float:
    """This process's peak resident set so far (``ru_maxrss`` is bytes on macOS, KiB on Linux)."""
    max_rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    scale = 1 if sys.platform == "darwin" else 1024
    megabytes = max_rss * scale / 1e6
    return megabytes


def console_script() -> Path:
    """The installed ``mhp3ass`` command."""
    script = Path(sysconfig.get_path("scripts")) / "mhp3ass"
    if not script.is_file():
        raise FileNotFoundError(f"no mhp3ass console script at {script}; run uv sync")
    return script


def import_seconds() -> float:
    """Cumulative import time of ``mhp3ass.cli`` in a new interpreter, from ``-X importtime``."""
    completed = subprocess.run(
        [sys.executable, "-X", "importtime", str(console_script()), "--version"],
        capture_output=True,
        text=True,
        check=True,
    )
    # Lines read "import time: <self us> | <cumulative us> | <module>".
    for line in completed.stderr.splitlines():
        fields = line.removeprefix("import time:").split("|")
        if len(fields) == 3 and fields[2].strip() == "mhp3ass.cli":
            seconds = int(fields[1]) / 1e6
            return seconds
    raise ValueError("-X importtime reported no mhp3ass.cli import")


def cold_search_seconds(query_path: Path, data_dir: Path) -> float:
    """``mhp3ass search`` of one query in a new process, writing its outputs."""
    with tempfile.TemporaryDirectory() as out_dir:
        command = [
            str(console_script()),
            "search",
            str(query_path),
            "--out",
            f"{out_dir}/q",
            "--data-dir",
            str(data_dir),
        ]
        seconds = elapsed(lambda: subprocess.run(command, capture_output=True, check=True))
    return seconds


def startup_report(data_dir: Path, query_path: Path, runs: int) -> list[str]:
    """Markdown rows for each start-up step and the cold search of ``query_path``."""
    spec = SearchSpec.from_file(query_path)
    language_dir = data_dir / "Languages" / spec.query.language

    def load_seconds() -> float:
        seconds = elapsed(lambda: load_game_data(data_dir))
        return seconds

    def tables_seconds() -> float:
        game = load_game_data(data_dir)
        seconds = elapsed(lambda: generate_charm_tables(game))
        return seconds

    def language_seconds() -> float:
        game = load_game_data(data_dir)
        seconds = elapsed(lambda: apply_language(game, language_dir))
        return seconds

    def validity_seconds() -> float:
        game = load_game_data(data_dir)
        tables = generate_charm_tables(game)
        seconds = elapsed(lambda: build_charm_validity(tables, ability_count=len(game.abilities)))
        return seconds

    def relevance_seconds() -> float:
        game = load_game_data(data_dir)
        apply_language(game, language_dir)
        seconds = elapsed(lambda: formulate_query(game, spec.query))
        return seconds

    steps = [
        ("Imports (`mhp3ass.cli`, new process)", import_seconds),
        ("Load data files", load_seconds),
        ("Charm tables", tables_seconds),
        ("Language", language_seconds),
        ("Charm checks (validity)", validity_seconds),
        (f"Relevance (`formulate_query`, {spec.query.id})", relevance_seconds),
        (
            f"Cold `mhp3ass search {spec.query.id} --out`",
            lambda: cold_search_seconds(query_path, data_dir=data_dir),
        ),
    ]
    rows = ["| Step | Median |", "|---|---|"]
    for label, step in steps:
        seconds = median_seconds(step, runs)
        rows.append(f"| {label} | {seconds * 1000:,.0f} ms |")
    return rows


@dataclass(frozen=True)
class SearchRun:
    """One ``run_search``: its result, its wall time and the workers' share of it."""

    result: SearchResult
    search_seconds: float
    worker_seconds: float


def run_once(spec: SearchSpec, data: SearchData, pause_gc: bool) -> SearchRun:
    """One timed ``run_search``, inside ``paused_gc()`` if ``pause_gc``."""
    worker_seconds = []

    def on_worker_done(progress: WorkerProgress) -> None:
        worker_seconds.append(progress.seconds)

    start = time.perf_counter()
    with paused_gc() if pause_gc else nullcontext():
        result = run_search(spec, data=data, on_worker_done=on_worker_done)
    search_seconds = time.perf_counter() - start
    run = SearchRun(
        result=result, search_seconds=search_seconds, worker_seconds=sum(worker_seconds)
    )
    return run


def time_search(query: BenchmarkQuery, data: SearchData, runs: int, pause_gc: bool) -> SearchTiming:
    """``run_search`` on ``query``, ``runs`` times; raises if a run's solution
    count differs from the golden manifest's."""
    spec = SearchSpec.from_file(query.path)
    manifest = json.loads(query.manifest_path.read_text(encoding="utf-8"))
    expected_solutions = manifest["solution_count"]
    search_timings = []
    worker_timings = []
    run = None
    for _ in range(runs):
        # Drop the previous run's solutions first, so no run pays for them.
        run = None
        gc.collect()
        run = run_once(spec, data=data, pause_gc=pause_gc)
        solutions = len(run.result.results.all_solutions)
        if solutions != expected_solutions:
            raise ValueError(
                f"{query.name}: {solutions:,} solutions, the golden has {expected_solutions:,}"
            )
        search_timings.append(run.search_seconds)
        worker_timings.append(run.worker_seconds)
    if run is None:
        raise ValueError("runs must be at least 1")
    result = run.result
    combinations = math.prod(len(slot) for slot in armor_choices(result.query))
    timing = SearchTiming(
        name=query.name,
        worker_count=result.worker_count,
        calls=combinations * len(result.workers),
        accepted=sum(len(worker.found) for worker in result.workers),
        solutions=len(result.results.all_solutions),
        search_seconds=statistics.median(search_timings),
        worker_seconds=statistics.median(worker_timings),
        peak_rss_mb=peak_rss_mb(),
    )
    return timing


def search_row(timing: SearchTiming) -> str:
    """One Markdown row of the search table."""
    rejected = timing.calls - timing.accepted
    per_call = 1e6 * timing.worker_seconds / timing.calls if timing.calls else math.nan
    other_seconds = timing.search_seconds - timing.worker_seconds
    row = (
        f"| {timing.name} | {timing.worker_count} | {timing.calls:,} | {timing.accepted:,} | "
        f"{rejected:,} | {timing.solutions:,} | {timing.search_seconds:.2f} s | "
        f"{timing.worker_seconds:.2f} s | {other_seconds:.2f} s | {per_call:.1f} | "
        f"{timing.peak_rss_mb:,.0f} MB |"
    )
    return row


def corpus_queries(corpus_dir: Path, golden_dir: Path) -> list[BenchmarkQuery]:
    """Every query in ``corpus_dir`` paired with its manifest in ``golden_dir``."""
    queries = [
        BenchmarkQuery(
            name=path.stem.split("-")[0],
            path=path,
            manifest_path=golden_dir / f"{path.stem}.manifest.json",
        )
        for path in sorted(corpus_dir.glob("*.json"))
    ]
    return queries


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    repo_root = Path(__file__).resolve().parent.parent
    tests_dir = repo_root / "tests"
    parser.add_argument("--runs", type=int, default=5, help="runs per timing (median taken)")
    parser.add_argument(
        "--only", nargs="+", metavar="ID", help="only these queries (e.g. 1a g18 f305)"
    )
    parser.add_argument("--all-fuzz", action="store_true", help="all 500 fuzz queries")
    parser.add_argument(
        "--fuzz",
        nargs="*",
        default=["f305", "f058", "f081", "f362", "f099", "f244"],
        metavar="ID",
        help="fuzz queries to time (default: the heaviest; none with no IDs)",
    )
    parser.add_argument("--no-startup", action="store_true", help="skip the start-up timings")
    parser.add_argument(
        "--paused-gc", action="store_true", help="run each search inside paused_gc()"
    )
    parser.add_argument(
        "--data-dir", type=Path, default=repo_root / "legacy" / "Run" / "Data", help="game data"
    )
    args = parser.parse_args()
    if args.runs < 1:
        parser.error("--runs must be at least 1")

    queries = corpus_queries(tests_dir / "corpus", golden_dir=tests_dir / "golden" / "search")
    personal_dir = tests_dir / "savefile"
    if (personal_dir / "corpus").is_dir():
        queries += corpus_queries(
            personal_dir / "corpus", golden_dir=personal_dir / "golden" / "search"
        )
    fuzz_paths = sorted((tests_dir / "fuzz").glob("f*.json"))
    fuzz_names = {path.stem for path in fuzz_paths} if args.all_fuzz else set(args.fuzz)
    queries += [
        BenchmarkQuery(
            name=path.stem,
            path=path,
            manifest_path=tests_dir / "golden" / "fuzz" / f"{path.stem}.manifest.json",
        )
        for path in fuzz_paths
        if path.stem in fuzz_names
    ]
    if args.only:
        queries = [query for query in queries if query.name in args.only]

    commit = subprocess.run(
        ["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, cwd=repo_root
    ).stdout.strip()
    print(
        f"Commit {commit}, Python {platform.python_version()}, {platform.machine()}, "
        f"{platform.system()}; median of {args.runs}; GC "
        f"{'paused during each search' if args.paused_gc else 'on'}"
    )
    print()

    if not args.no_startup:
        startup_query = tests_dir / "corpus" / "1a-attack-sharp-default-charms.json"
        for row in startup_report(args.data_dir, query_path=startup_query, runs=args.runs):
            print(row)
        print()

    print(
        "| Query | Workers | Calls | Accepted | Rejected | Solutions | Search | Workers "
        "| Other | µs/call | Peak RSS |"
    )
    print("|---|---|---|---|---|---|---|---|---|---|---|")
    data_by_language: dict[str, SearchData] = {}
    total_search_seconds = 0.0
    for query in queries:
        language = SearchSpec.from_file(query.path).query.language
        if language not in data_by_language:
            data_by_language[language] = SearchData.load(args.data_dir, language=language)
        timing = time_search(
            query, data=data_by_language[language], runs=args.runs, pause_gc=args.paused_gc
        )
        total_search_seconds += timing.search_seconds
        print(search_row(timing), flush=True)
    print()
    print(
        f"{len(queries)} queries, {total_search_seconds:.1f} s of median search time in all; "
        "every solution count matches its golden"
    )


if __name__ == "__main__":
    main()
