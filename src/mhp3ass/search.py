"""A search: which charm templates it searches, each worker's loop, and the run
that merges the workers' solutions.

Ported from ``Form1::StartSearch`` (``legacy/Form1.h:1251-1375``),
``Form1::backgroundWorker1_DoWork`` (``legacy/Form1.h:1852-1930``) and
``backgroundWorker1_RunWorkerCompleted`` (``legacy/Form1.h:1804-1836``),
without the threads, in the order the harness's ``SearchDump::Run``
(``harness/src/SearchDump.cpp``) runs them. The workers run one after
another, or in a ``WorkerPool`` (``parallel.SearchPool``); the results are
merged in worker order either way. A cancelled search raises
``SearchCancelled`` and returns nothing, unlike the original's, which keeps
its partial results (quirk 38).
"""

from __future__ import annotations

import gc
import time
from collections.abc import Callable, Generator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from math import prod
from pathlib import Path
from threading import Event
from typing import Protocol, TypeIs

from mhp3ass.charms.comparison import add_charm_to_optimal_list
from mhp3ass.charms.for_query import get_charms
from mhp3ass.charms.generation import CharmTables, generate_charm_tables
from mhp3ass.charms.my_charms import load_query_my_charms, my_charms_illegal
from mhp3ass.charms.validity import CharmValidity, build_charm_validity
from mhp3ass.data import GameData, apply_language, load_game_data
from mhp3ass.decorations import NoDecorationsError
from mhp3ass.model import Armor, Charm
from mhp3ass.query import CharmMode, Query, QuerySpec, SearchSpec
from mhp3ass.relevance import formulate_query
from mhp3ass.results.result_set import (
    ResultSet,
    SearchException,
    SearchResult,
    SolutionList,
    WorkerResult,
)
from mhp3ass.solution import matches_query
from mhp3ass.solution.charm_reduction import LegacyListIndexError
from mhp3ass.solution.fill import UndefinedScoreError
from mhp3ass.solution.record import SolutionRecord
from mhp3ass.solution.state import LegacyNullReferenceError, Solution


def language_dir(data_dir: Path, language: str) -> Path:
    """The folder of ``language``'s translation files; raises ``FileNotFoundError``
    if the game data has no such language."""
    folder = data_dir / "Languages" / language
    if not folder.is_dir():
        raise FileNotFoundError(f"no language folder {folder}")
    return folder


@dataclass(frozen=True)
class SearchData:
    """What a search reads besides the query: the game in one language, its
    charm tables, the charm checks my-charms loading needs, and the data
    folder they came from (a pool's processes load their own game from it)."""

    game: GameData
    tables: CharmTables
    validity: CharmValidity
    data_dir: Path

    @classmethod
    def load(cls, data_dir: Path, language: str) -> SearchData:
        """The data files, then the charm tables, then the language, in the
        GUI's start-up order (Form1.h:309-322)."""
        translations = language_dir(data_dir, language)
        game = load_game_data(data_dir)
        tables = generate_charm_tables(game)
        apply_language(game, translations)
        validity = build_charm_validity(tables, ability_count=len(game.abilities))
        search_data = cls(game=game, tables=tables, validity=validity, data_dir=data_dir)
        return search_data


def worker_charms(
    query: Query, charm_mode: CharmMode, my_charms: list[Charm], tables: CharmTables
) -> list[Charm | None]:
    """``StartSearch``'s charm templates, one per worker, in the order it starts them
    (``None`` is a charm-free worker).

    ``query`` must come from ``formulate_query`` on the game ``my_charms`` and
    ``tables`` belong to, with no other query formulated since: the my-charms
    comparisons read the abilities' ``relevant`` flags it sets.

    - No skills: no workers (the GUI does nothing, :1255)
    - Slotted, one- and two-skill modes with an Auto-Guard skill: only the
      first my-charm whose single ability is Auto-Guard, whatever its points
      or slots, or no workers without one (:1274-1291)
    - None: one charm-free worker
    - My charms: a charm-free worker, then the charms ``AddCharmToOptimalList``
      keeps, in list order (:1300-1313)
    - Slotted: a bare three-slot charm (:1314-1323)
    - One- and two-skill: ``GetCharms`` (:1324-1372)

    The my-charms templates are the given objects themselves; workers copy them.
    """
    if not query.skills:
        return []
    if charm_mode > CharmMode.MY_CHARMS:
        for ability in query.rel_abilities:
            if ability.auto_guard:
                auto_guard_charm = next(
                    (
                        charm
                        for charm in my_charms
                        if len(charm.abilities) == 1 and charm.abilities[0].ability is ability
                    ),
                    None,
                )
                auto_guard_workers: list[Charm | None] = (
                    [] if auto_guard_charm is None else [auto_guard_charm]
                )
                return auto_guard_workers
    workers: list[Charm | None]
    match charm_mode:
        case CharmMode.NONE:
            workers = [None]
        case CharmMode.MY_CHARMS:
            to_search: list[Charm] = []
            for charm in my_charms:
                add_charm_to_optimal_list(to_search, charm)
            workers = [None, *to_search]
        case CharmMode.SLOTTED:
            workers = [Charm(num_slots=3)]
        case CharmMode.ONE_SKILL | CharmMode.TWO_SKILL:
            charms = get_charms(
                query, tables=tables, use_two_skill_charms=charm_mode is CharmMode.TWO_SKILL
            )
            workers = list(charms)
    return workers


@contextmanager
def paused_gc() -> Generator[None]:
    """Turn off cyclic garbage collection for the block, then restore its previous state.

    Every accepted ``Solution`` stays alive until the search ends, so each
    young-generation collection walks all of them again; on accepted-heavy
    queries that is about a third of the search time. Reference counting still
    frees everything a combination drops: the search builds no reference cycles.

    The collector's switch is process-wide, so blocks must nest within one
    thread: two threads overlapping their blocks can switch it back on early.
    """
    was_enabled = gc.isenabled()
    gc.disable()
    try:
        yield
    finally:
        if was_enabled:
            gc.enable()


def armor_choices(query: Query) -> list[list[Armor | None]]:
    """Each slot's relevant armour, with one ``None`` for an empty slot.

    ``DoWork`` adds that ``nullptr`` to the query's own lists (Form1.h:1865-1869),
    so every later worker and reader sees it. Here the lists are copied: the
    workers that follow pad the same way, so the combinations are the same.
    """
    choices: list[list[Armor | None]] = [list(slot) or [None] for slot in query.rel_armor]
    return choices


def run_worker(
    query: Query,
    charm_template: Charm | None,
    game: GameData,
    *,
    head_start: int = 0,
    head_stop: int | None = None,
    on_step: Callable[[int], None] | None = None,
) -> list[Solution]:
    """``backgroundWorker1_DoWork`` (Form1.h:1852-1930): the solutions ``MatchesQuery``
    accepts, in loop order (head, then body, arms, waist, legs).

    Each combination gets its own copy of the charm template, as the original's
    ``gcnew Charm( qc->charm_template )`` does (deep: the pairs are copied too),
    so reducing one combination's charm never touches the template.

    ``head_start`` and ``head_stop`` limit the run to that range of the padded
    head choices; the ranges' solutions, concatenated in order, are the whole
    run's. ``on_step`` is called after each (head, body) pair with the number
    of combinations it checked, where the original reports progress (:1878-1890).
    """
    head, body, arms, waist, legs = armor_choices(query)
    combinations_per_step = len(arms) * len(waist) * len(legs)
    solutions = []
    for head_piece in head[head_start:head_stop]:
        for body_piece in body:
            for arms_piece in arms:
                for waist_piece in waist:
                    for legs_piece in legs:
                        job = Solution(
                            armors=[head_piece, body_piece, arms_piece, waist_piece, legs_piece],
                            charm=charm_template.copy() if charm_template is not None else None,
                        )
                        if matches_query(job, query, game):
                            solutions.append(job)
            if on_step is not None:
                on_step(combinations_per_step)
    return solutions


class StepReporter:
    """Adds up checked combinations and sends the running total at most once
    per ``interval`` seconds."""

    def __init__(
        self,
        send: Callable[[int], None],
        interval: float = 0.1,
        clock: Callable[[], float] = time.monotonic,
    ):
        self._send = send
        self._interval = interval
        self._clock = clock
        self._done = 0
        self._last_sent = clock()

    def add(self, combinations: int) -> None:
        self._done += combinations
        now = self._clock()
        if now - self._last_sent >= self._interval:
            self._send(self._done)
            self._last_sent = now

    def send_now(self) -> None:
        """Send the running total whatever the interval, as at the end of a search."""
        self._send(self._done)


class SearchCancelled(Exception):
    """The caller's cancel event was set before the search finished."""


def raise_if_cancelled(cancel: Event | None) -> None:
    if cancel is not None and cancel.is_set():
        raise SearchCancelled("the search was cancelled")


def is_search_error(error: BaseException) -> TypeIs[LegacyNullReferenceError | LookupError]:
    """Whether ``error`` is one ``run_worker`` itself can raise, which the
    serial search records or propagates; anything else is a failure of the
    pool and fails the search."""
    search_error = isinstance(error, (LegacyNullReferenceError, LookupError))
    return search_error


@dataclass(frozen=True)
class WorkerError:
    """The first worker, in search order, whose search raised, and its error."""

    worker: int
    error: Exception


@dataclass(frozen=True)
class PoolResult:
    """Each worker's solutions in loop order, stopping before ``error``'s worker
    when one raised."""

    workers: list[list[SolutionRecord]]
    error: WorkerError | None


class WorkerPool(Protocol):
    """Runs a search's workers elsewhere (``parallel.SearchPool``)."""

    def run(
        self,
        *,
        data_dir: Path,
        spec: QuerySpec,
        query: Query,
        templates: Sequence[Charm | None],
        game: GameData,
        on_progress: Callable[[int, int], None] | None = None,
        cancel: Event | None = None,
    ) -> PoolResult: ...


def dotnet_exception_type(error: Exception) -> str | None:
    """The .NET exception type a port exception stands for, or ``None`` for an
    error the original never raises (such as ``UndefinedScoreError``, a
    port-side check where the original reads past its score table)."""
    exception_type = None
    if isinstance(error, LegacyNullReferenceError):
        exception_type = "NullReferenceException"
    elif isinstance(error, LegacyListIndexError):
        exception_type = "ArgumentOutOfRangeException"
    elif isinstance(error, (NoDecorationsError, KeyError)):
        exception_type = "KeyNotFoundException"
    elif isinstance(error, IndexError) and not isinstance(error, UndefinedScoreError):
        exception_type = "IndexOutOfRangeException"
    return exception_type


def dotnet_message(exception_type: str) -> str:
    """.NET Framework 4.8's default message for ``exception_type`` (unverified
    against a harness golden: none records an exception yet)."""
    messages = {
        "NullReferenceException": "Object reference not set to an instance of an object.",
        "ArgumentOutOfRangeException": (
            "Index was out of range. Must be non-negative and less than the size of the "
            "collection.\r\nParameter name: index"
        ),
        "KeyNotFoundException": "The given key was not present in the dictionary.",
        "IndexOutOfRangeException": "Index was outside the bounds of the array.",
    }
    message = messages[exception_type]
    return message


@dataclass(frozen=True)
class WorkerProgress:
    """A finished worker, for progress reports: its number of ``worker_count``,
    its result, and how long it took (in a pool, where the workers run
    together, how long merging its solutions took)."""

    number: int
    worker_count: int
    worker: WorkerResult
    seconds: float


def _recorded_exception(
    error: LegacyNullReferenceError | LookupError,
    worker: int,
    template: Charm | None,
    record_exceptions: bool,
) -> SearchException:
    """The record of a worker's throw; raises ``error`` itself unless
    ``record_exceptions`` and the original throws a .NET exception there."""
    exception_type = dotnet_exception_type(error)
    if not record_exceptions or exception_type is None:
        raise error
    exception = SearchException(
        worker=worker,
        type=exception_type,
        message=dotnet_message(exception_type),
        template=template,
    )
    return exception


def run_search(
    spec: SearchSpec,
    data: SearchData,
    record_exceptions: bool = False,
    on_worker_done: Callable[[WorkerProgress], None] | None = None,
    *,
    pool: WorkerPool | None = None,
    on_progress: Callable[[int, int], None] | None = None,
    cancel: Event | None = None,
) -> SearchResult:
    """One search, as the harness's ``SearchDump::Run`` runs it: load the query's
    charm lines, formulate the query, start the workers in ``StartSearch``'s
    order, run each in turn and merge its solutions in that order.

    ``data`` must be in ``spec``'s language. A worker that throws stops the
    search: with ``record_exceptions`` the result records it and leaves out
    that worker and the ones after it (the GUI shows a message box and loses
    that worker's result, Form1.h:1804-1811); without, the error propagates.
    Errors in duplicate removal (quirk T) always propagate, as in the harness.
    ``on_worker_done`` is called after each worker's solutions are merged.

    With ``pool`` the workers run there at the same time, and their solutions
    come back as records and stay records until read (``SolutionList``); the
    result is the same, worker by worker. ``on_progress(done, total)`` gets
    the armour combinations checked so far over all workers, at most about
    ten times a second and once at the end (short of ``total`` when a worker
    threw), counting where the original reports progress (Form1.h:1874-1890).
    Cyclic garbage collection is off (``paused_gc``) while the workers run and
    their solutions are merged, callbacks included.

    Setting ``cancel`` (from another thread) stops the search and raises
    ``SearchCancelled``: before the setup, serially after the current
    (head, body) pair, in a pool within one progress interval (its tasks stop
    at their next step), and between the workers while their solutions are
    merged.
    """
    raise_if_cancelled(cancel)
    loaded = load_query_my_charms(spec.my_charms, game=data.game, validity=data.validity)
    query = formulate_query(data.game, spec.query)
    templates = worker_charms(
        query, charm_mode=spec.charm_mode, my_charms=loaded.charms, tables=data.tables
    )
    results = ResultSet()
    workers = []
    exception = None

    def report_worker(number: int, worker: WorkerResult, start: float) -> None:
        if on_worker_done is not None:
            progress = WorkerProgress(
                number=number,
                worker_count=len(templates),
                worker=worker,
                seconds=time.perf_counter() - start,
            )
            on_worker_done(progress)

    # Every solution found stays alive until the search ends, so collections
    # would walk them all again and again; nothing here builds a cycle.
    with paused_gc():
        if pool is not None:
            pooled = pool.run(
                data_dir=data.data_dir,
                spec=spec.query,
                query=query,
                templates=templates,
                game=data.game,
                on_progress=on_progress,
                cancel=cancel,
            )
            for number, records in enumerate(pooled.workers):
                raise_if_cancelled(cancel)
                start = time.perf_counter()
                found = SolutionList.of_records(records, data.game)
                added = results.add_records(found)
                worker = WorkerResult(template=templates[number], found=found, added=added)
                workers.append(worker)
                report_worker(number, worker, start)
            if pooled.error is not None:
                failed = pooled.error.worker
                error = pooled.error.error
                if not is_search_error(error):
                    raise error
                exception = _recorded_exception(
                    error,
                    worker=failed,
                    template=templates[failed],
                    record_exceptions=record_exceptions,
                )
        else:
            reporter = None
            total = 0
            if on_progress is not None:
                total = len(templates) * prod(len(choices) for choices in armor_choices(query))
                reporter = StepReporter(send=lambda done: on_progress(done, total))

            def step(combinations: int) -> None:
                raise_if_cancelled(cancel)
                if reporter is not None:
                    reporter.add(combinations)

            needs_steps = reporter is not None or cancel is not None
            for number, template in enumerate(templates):
                raise_if_cancelled(cancel)
                start = time.perf_counter()
                try:
                    found = run_worker(
                        query,
                        template,
                        data.game,
                        on_step=step if needs_steps else None,
                    )
                except (LegacyNullReferenceError, LookupError) as error:
                    exception = _recorded_exception(
                        error, worker=number, template=template, record_exceptions=record_exceptions
                    )
                    break
                added = results.add_solutions(found)
                worker = WorkerResult(template=template, found=found, added=added)
                workers.append(worker)
                report_worker(number, worker, start)
            if reporter is not None:
                reporter.send_now()
    search_result = SearchResult(
        query=query,
        my_charms_loaded=len(loaded.charms),
        my_charms_illegal=my_charms_illegal(loaded),
        worker_count=len(templates),
        workers=workers,
        results=results,
        exceptions_recorded=record_exceptions,
        exception=exception,
    )
    return search_result
