"""Cancelling a search: ``run_search`` raises ``SearchCancelled`` serially and
in the pool, and the pool searches correctly afterwards."""

from __future__ import annotations

import multiprocessing
from dataclasses import dataclass
from multiprocessing.sharedctypes import Synchronized
from threading import Event

import pytest

from mhp3ass import parallel
from mhp3ass.parallel import PoolSearch, Task, plan_tasks
from mhp3ass.results.result_set import solution_lines
from mhp3ass.search import SearchCancelled, run_search


@dataclass(frozen=True)
class OneTaskSearch:
    """g16 (no charms, one worker) as a single pool task, its serial
    solutions, and the shared value a pool's processes read cancels from."""

    search: PoolSearch
    task: Task
    serial_count: int
    cancelled: Synchronized[int]


@pytest.fixture
def g16_as_one_task_in_this_process(
    corpus_spec, legacy_data_dir, search_data_for, serial_search, monkeypatch
) -> OneTaskSearch:
    """Installs the state a pool process gets from its initializer, so
    ``_run_task`` can run here."""
    spec = corpus_spec("corpus/g16-attack-sharp-no-charms.json")
    serial = serial_search("g16-attack-sharp-no-charms.json")
    search = PoolSearch.for_query(legacy_data_dir, spec=spec.query, query=serial.query)
    [task] = plan_tasks(worker_count=1, head_count=search.head_count, jobs=1, tasks_per_job=1)
    context = multiprocessing.get_context("spawn")
    cancelled: Synchronized[int] = context.Value("q", -1)
    monkeypatch.setattr(
        parallel,
        "_process",
        parallel._ProcessState(progress=context.Queue(), cancelled=cancelled),
    )
    one_task = OneTaskSearch(
        search=search,
        task=task,
        serial_count=len(serial.workers[0].found),
        cancelled=cancelled,
    )
    return one_task


def test_a_task_of_a_cancelled_search_stops(g16_as_one_task_in_this_process):
    one_task = g16_as_one_task_in_this_process
    one_task.cancelled.value = 5

    with pytest.raises(SearchCancelled, match="search 5 was cancelled"):
        parallel._run_task(5, 0, one_task.search, one_task.task, None)


def test_a_task_of_a_later_search_than_the_cancelled_one_runs(g16_as_one_task_in_this_process):
    one_task = g16_as_one_task_in_this_process
    one_task.cancelled.value = 4

    records = parallel._run_task(5, 0, one_task.search, one_task.task, None)

    assert len(records) == one_task.serial_count > 0


@pytest.fixture
def cancelled() -> Event:
    """A cancel event that is already set."""
    event = Event()
    event.set()
    return event


def test_a_search_cancelled_before_it_starts_raises(
    corpus_spec, search_data_for, pool_or_serial, cancelled
):
    spec = corpus_spec("corpus/g16-attack-sharp-no-charms.json")

    with pytest.raises(SearchCancelled):
        run_search(spec, data=search_data_for(spec), pool=pool_or_serial, cancel=cancelled)


def test_a_search_cancelled_part_way_raises_before_checking_every_combination(
    corpus_spec, search_data_for, pool_or_serial
):
    """g18: six-skill Blademaster search, no charms, 1.17M combinations, none match."""
    spec = corpus_spec("corpus/g18-six-skills.json")
    cancel = Event()
    reports: list[tuple[int, int]] = []

    def cancel_at_first_report(done: int, total: int) -> None:
        reports.append((done, total))
        cancel.set()

    with pytest.raises(SearchCancelled):
        run_search(
            spec,
            data=search_data_for(spec),
            pool=pool_or_serial,
            on_progress=cancel_at_first_report,
            cancel=cancel,
        )

    assert reports != []
    assert all(done < total for done, total in reports)


def test_an_unset_cancel_changes_nothing_in_the_serial_search(
    corpus_spec, search_data_for, serial_search
):
    """Serial only: there an unset cancel adds a check at every step."""
    spec = corpus_spec("corpus/g16-attack-sharp-no-charms.json")
    data = search_data_for(spec)

    result = run_search(spec, data=data, cancel=Event())

    expected = serial_search("g16-attack-sharp-no-charms.json")
    assert solution_lines(result, game=data.game) == solution_lines(expected, game=data.game)


def test_the_pool_searches_as_before_after_a_cancel(
    corpus_spec, search_data_for, serial_search, search_pool, cancelled
):
    """The cancelled search's tasks start on the idle processes and finish
    unread; the next search's results and progress are its own."""
    spec = corpus_spec("corpus/g16-attack-sharp-no-charms.json")
    data = search_data_for(spec)
    with pytest.raises(SearchCancelled):
        run_search(spec, data=data, pool=search_pool, cancel=cancelled)
    reports: list[tuple[int, int]] = []

    after = run_search(
        spec,
        data=data,
        pool=search_pool,
        on_progress=lambda done, total: reports.append((done, total)),
    )

    expected = serial_search("g16-attack-sharp-no-charms.json")
    assert solution_lines(after, game=data.game) == solution_lines(expected, game=data.game)
    assert reports[-1][0] == reports[-1][1]
    assert all(done <= total for done, total in reports)
