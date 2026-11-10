"""Splitting a search into tasks for a process pool, and running them there.

Not a port of an original module: the original runs one thread per charm
template (``legacy/Form1.h:1852-1930``). Here each worker's combinations are
also split into contiguous ranges of head pieces, so a search with a single
template still spreads over several processes. ``run_worker`` loops over head
pieces outermost, so a worker's solutions are the concatenation of its tasks'
solutions in ``head_start`` order.

``SearchPool`` runs the tasks in spawned processes. Each process rebuilds the
game and the query from the query's spec (a fresh game per query, as
``relevance.py`` asks) and sends its solutions back as ``SolutionRecord``s.
The merge puts them in task order, whatever order the tasks finish in, and
replays the serial search's rule for a worker that raises: that worker and
every later one are left out, even if they already ran. Progress is counted
where the original reports it, after each (head, body) pair (Form1.h:1874-1890).
"""

from __future__ import annotations

import itertools
import multiprocessing
import os
import queue
import time
from collections.abc import Callable, Mapping, Sequence
from concurrent.futures import Future, ProcessPoolExecutor, wait
from dataclasses import dataclass
from math import ceil, prod
from multiprocessing.queues import Queue
from pathlib import Path
from types import TracebackType
from typing import TypeIs

from mhp3ass.data import GameData, apply_language, load_game_data
from mhp3ass.model import Charm
from mhp3ass.query import Query, QuerySpec
from mhp3ass.relevance import formulate_query
from mhp3ass.search import (
    PoolResult,
    StepReporter,
    WorkerError,
    armor_choices,
    language_dir,
    paused_gc,
    run_worker,
)
from mhp3ass.solution.record import (
    CharmRecord,
    RecordIndex,
    SolutionRecord,
    charm_from_record,
    charm_record,
    to_record,
)
from mhp3ass.solution.state import LegacyNullReferenceError


@dataclass(frozen=True, slots=True)
class Task:
    """The combinations of one worker whose head piece is in ``[head_start, head_stop)``."""

    worker: int
    head_start: int
    head_stop: int


def plan_tasks(worker_count: int, head_count: int, jobs: int, tasks_per_job: int = 4) -> list[Task]:
    """Tasks covering every (worker, head piece) exactly once, in (worker, head_start) order.

    Aims for about ``tasks_per_job`` tasks per process so that slow tasks even
    out. Every worker is split the same way, into at most ``head_count``
    ranges whose sizes differ by at most one, larger first; once there are
    that many workers or more, each worker is one task, however long it takes.
    ``head_count`` is ``len(armor_choices(query)[0])``: the head slot's choices
    after an empty slot is padded with ``None``, so at least 1.
    """
    if worker_count < 0:
        raise ValueError(f"worker_count must not be negative, not {worker_count}")
    if head_count < 1:
        raise ValueError(
            f"head_count counts the padded head choices, so it is at least 1, not {head_count}"
        )
    if jobs < 1:
        raise ValueError(f"jobs must be at least 1, not {jobs}")
    if tasks_per_job < 1:
        raise ValueError(f"tasks_per_job must be at least 1, not {tasks_per_job}")
    if worker_count == 0:
        return []
    chunks_per_worker = min(head_count, ceil(jobs * tasks_per_job / worker_count))
    base_size, larger_chunks = divmod(head_count, chunks_per_worker)
    tasks = []
    for worker in range(worker_count):
        head_start = 0
        for chunk in range(chunks_per_worker):
            size = base_size + 1 if chunk < larger_chunks else base_size
            tasks.append(Task(worker=worker, head_start=head_start, head_stop=head_start + size))
            head_start += size
    return tasks


def default_jobs(max_jobs: int = 8) -> int:
    """Processes for a search: one per CPU this process may use, at most
    ``max_jobs`` (more than 8 lose on a Mac, whose efficiency cores finish late)."""
    cpu_count = os.process_cpu_count()
    jobs = min(max_jobs, cpu_count if cpu_count is not None else 1)
    return jobs


class ChildStateError(RuntimeError):
    """A pool process couldn't rebuild the parent's query, or rebuilt a different one."""


def armor_choice_indices(query: Query) -> tuple[tuple[int, ...], ...]:
    """Each slot's padded armour choices (``armor_choices``) by index, -1 for the padding."""
    indices = tuple(
        tuple(-1 if armor is None else armor.index for armor in choices)
        for choices in armor_choices(query)
    )
    return indices


@dataclass(frozen=True)
class PoolSearch:
    """What a pool process needs to rebuild a search: the data folder, the
    query's spec, and the parent's padded armour choices per slot by index,
    which the rebuilt query must match."""

    data_dir: Path
    query: QuerySpec
    armor_indices: tuple[tuple[int, ...], ...]

    @classmethod
    def for_query(cls, data_dir: Path, spec: QuerySpec, query: Query) -> PoolSearch:
        """``query`` is the parent's ``formulate_query`` of ``spec``."""
        search = cls(data_dir=data_dir, query=spec, armor_indices=armor_choice_indices(query))
        return search

    @property
    def head_count(self) -> int:
        return len(self.armor_indices[0])

    @property
    def combinations_per_head(self) -> int:
        combinations = prod(len(choices) for choices in self.armor_indices[1:])
        return combinations


@dataclass(frozen=True, eq=False)
class RebuiltSearch:
    """A pool process's own game and query for one ``PoolSearch``."""

    search: PoolSearch
    game: GameData
    query: Query
    index: RecordIndex

    @classmethod
    def rebuild(cls, search: PoolSearch) -> RebuiltSearch:
        """Load the game in the query's language and formulate the query on it.

        Raises ``ChildStateError`` if that raises an error a worker could also
        raise (the parent formulated the same query without one, so it must
        not pass for a worker's), or if the armour choices differ from the parent's.
        """
        try:
            game = load_game_data(search.data_dir)
            apply_language(game, language_dir(search.data_dir, search.query.language))
            query = formulate_query(game, search.query)
        except (LegacyNullReferenceError, LookupError) as error:
            raise ChildStateError(f"rebuilding query {search.query.id} raised {error!r}") from error
        armor_indices = armor_choice_indices(query)
        if armor_indices != search.armor_indices:
            raise ChildStateError(
                f"rebuilt query {search.query.id} has armour choices {armor_indices}, "
                f"the parent's has {search.armor_indices}"
            )
        rebuilt = cls(search=search, game=game, query=query, index=RecordIndex.for_game(game))
        return rebuilt


class ProgressTally:
    """Combinations checked so far over a search's tasks. A task's reports are
    running totals that may arrive late or out of order, so each counts only
    if it is higher; a finished task counts in full."""

    def __init__(self, task_sizes: list[int]):
        self._sizes = task_sizes
        self._done = [0] * len(task_sizes)

    def report(self, number: int, done: int) -> None:
        self._done[number] = max(self._done[number], min(done, self._sizes[number]))

    def finish(self, number: int) -> None:
        self._done[number] = self._sizes[number]

    @property
    def done(self) -> int:
        return sum(self._done)

    @property
    def total(self) -> int:
        return sum(self._sizes)


def is_search_error(error: BaseException) -> TypeIs[LegacyNullReferenceError | LookupError]:
    """Whether ``error`` is one ``run_worker`` itself can raise, which the
    serial search records or propagates; anything else is a failure of the
    pool and fails the search."""
    search_error = isinstance(error, (LegacyNullReferenceError, LookupError))
    return search_error


@dataclass(frozen=True, slots=True)
class ProgressReport:
    """A pool process's running total of combinations checked in one task."""

    search_id: int
    task: int
    done: int


def merge_tasks(
    tasks: list[Task],
    outcomes: Mapping[int, list[SolutionRecord] | Exception],
    worker_count: int,
) -> PoolResult:
    """Concatenate the tasks' solutions per worker in task order.

    ``outcomes`` holds each task's records or search error by task number, in
    any order. The first task in order that raised ends the merge: its worker
    and every later one are left out, as in the serial search. Tasks after it
    may be missing (cancelled).
    """
    workers: list[list[SolutionRecord]] = [[] for _ in range(worker_count)]
    for number, task in enumerate(tasks):
        if number not in outcomes:
            raise ValueError(f"task {number} has no outcome and no earlier task raised")
        outcome = outcomes[number]
        if isinstance(outcome, Exception):
            failed = PoolResult(
                workers=workers[: task.worker],
                error=WorkerError(worker=task.worker, error=outcome),
            )
            return failed
        workers[task.worker].extend(outcome)
    merged = PoolResult(workers=workers, error=None)
    return merged


def task_outcomes(
    futures: list[Future[list[SolutionRecord]]],
) -> dict[int, list[SolutionRecord] | Exception]:
    """Each finished task's records by task number, in task order, up to and
    including the first search error; raises any other error before it.

    Tasks after the first search error are never looked at, whatever they
    raised: the serial search would never have run them.
    """
    outcomes: dict[int, list[SolutionRecord] | Exception] = {}
    for number, future in enumerate(futures):
        if future.cancelled():
            raise RuntimeError(f"task {number} was cancelled before any task raised")
        error = future.exception()
        if error is None:
            outcomes[number] = future.result()
        elif is_search_error(error):
            outcomes[number] = error
            break
        else:
            raise error
    return outcomes


@dataclass
class _ProcessState:
    """A pool process's progress queue and interval, and its last rebuilt search."""

    progress: Queue[ProgressReport] | None = None
    progress_interval: float = 0.1
    search: RebuiltSearch | None = None


# Set in each pool process by its initializer; the parent never touches it.
_process = _ProcessState()


def _start_process(progress: Queue[ProgressReport], progress_interval: float) -> None:
    # A process exits without waiting for unsent reports: once its tasks are
    # done the parent counts them in full, and waiting on a full pipe nobody
    # reads any more would hang the pool's shutdown.
    progress.cancel_join_thread()
    _process.progress = progress
    _process.progress_interval = progress_interval


def _run_task(
    search_id: int, number: int, search: PoolSearch, task: Task, template: CharmRecord | None
) -> list[SolutionRecord]:
    """One task in a pool process: the worker's solutions over the task's head range."""
    progress = _process.progress
    if progress is None:
        raise RuntimeError("_run_task runs only in a SearchPool process")
    rebuilt = _process.search
    if rebuilt is None or rebuilt.search != search:
        rebuilt = RebuiltSearch.rebuild(search)
        _process.search = rebuilt
    charm = charm_from_record(template, rebuilt.game)
    reporter = StepReporter(
        send=lambda done: progress.put(ProgressReport(search_id=search_id, task=number, done=done)),
        interval=_process.progress_interval,
    )
    with paused_gc():
        solutions = run_worker(
            rebuilt.query,
            charm,
            rebuilt.game,
            head_start=task.head_start,
            head_stop=task.head_stop,
            on_step=reporter.add,
        )
        records = [to_record(solution, rebuilt.index) for solution in solutions]
    return records


class SearchPool:
    """A persistent pool of spawned processes that run a search's tasks.

    ``jobs`` defaults to ``default_jobs()``. ``progress_interval`` (seconds)
    throttles both each process's progress messages and ``on_progress``.
    Close the pool (or use it as a context manager) to stop the processes.
    One search runs at a time.
    """

    def __init__(self, jobs: int | None = None, progress_interval: float = 0.1):
        self.jobs = jobs if jobs is not None else default_jobs()
        if self.jobs < 1:
            raise ValueError(f"jobs must be at least 1, not {self.jobs}")
        self._progress_interval = progress_interval
        context = multiprocessing.get_context("spawn")
        self._progress: Queue[ProgressReport] = context.Queue()
        self._executor = ProcessPoolExecutor(
            max_workers=self.jobs,
            mp_context=context,
            initializer=_start_process,
            initargs=(self._progress, progress_interval),
        )
        self._search_ids = itertools.count()

    def run(
        self,
        *,
        data_dir: Path,
        spec: QuerySpec,
        query: Query,
        templates: Sequence[Charm | None],
        game: GameData,
        on_progress: Callable[[int, int], None] | None = None,
    ) -> PoolResult:
        """Every worker's solutions for ``query`` (the parent's ``formulate_query``
        of ``spec`` on ``game``, loaded from ``data_dir``), one worker per template.

        ``on_progress(done, total)`` gets the combinations checked so far over
        all workers, at most once per ``progress_interval`` and once at the end.
        A search error in a worker ends up in the result, and the progress then
        stops short of the total; any other error in a pool process, up to the
        first search error in task order, is raised.
        """
        search = PoolSearch.for_query(data_dir, spec=spec, query=query)
        tasks = plan_tasks(
            worker_count=len(templates), head_count=search.head_count, jobs=self.jobs
        )
        template_records = [charm_record(template, game) for template in templates]
        tally = ProgressTally(
            [(task.head_stop - task.head_start) * search.combinations_per_head for task in tasks]
        )
        search_id = next(self._search_ids)
        futures = [
            self._executor.submit(
                _run_task, search_id, number, search, task, template_records[task.worker]
            )
            for number, task in enumerate(tasks)
        ]
        numbers = {future: number for number, future in enumerate(futures)}
        pending: set[Future[list[SolutionRecord]]] = set(futures)
        last_reported = time.monotonic()
        while pending:
            # The floor keeps the parent from spinning when reports are unthrottled.
            finished, pending = wait(pending, timeout=max(self._progress_interval, 0.01))
            for future in finished:
                number = numbers[future]
                if future.cancelled():
                    continue
                if future.exception() is None:
                    tally.finish(number)
                else:
                    for later in futures[number + 1 :]:
                        later.cancel()
            self._read_progress(search_id, tally)
            now = time.monotonic()
            if (
                on_progress is not None
                and pending
                and now - last_reported >= self._progress_interval
            ):
                on_progress(tally.done, tally.total)
                last_reported = now
        if on_progress is not None:
            on_progress(tally.done, tally.total)
        outcomes = task_outcomes(futures)
        result = merge_tasks(tasks, outcomes=outcomes, worker_count=len(templates))
        return result

    def _read_progress(self, search_id: int, tally: ProgressTally) -> None:
        """Count every queued report for this search; drop older searches' late ones."""
        while True:
            try:
                report = self._progress.get_nowait()
            except queue.Empty:
                return
            if report.search_id == search_id:
                tally.report(report.task, report.done)

    def close(self) -> None:
        self._executor.shutdown(cancel_futures=True)
        self._progress.close()
        self._progress.join_thread()

    def __enter__(self) -> SearchPool:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()
