"""``SearchPool``: searches in spawned processes give each worker's serial
solutions, merged in task order whatever order the tasks finish in, with
progress counted in combinations."""

from __future__ import annotations

import multiprocessing
from concurrent.futures import Future
from dataclasses import dataclass, replace
from functools import lru_cache
from itertools import accumulate
from math import prod

import pytest

from mhp3ass.charms.my_charms import load_query_my_charms
from mhp3ass.parallel import (
    ChildStateError,
    PoolSearch,
    ProgressTally,
    RebuiltSearch,
    SearchPool,
    Task,
    armor_choice_indices,
    default_jobs,
    merge_tasks,
    plan_tasks,
    task_outcomes,
)
from mhp3ass.results.result_set import skill_indices, solution_line
from mhp3ass.search import StepReporter, armor_choices, run_search, worker_charms
from mhp3ass.solution.record import SolutionRecord, from_record
from mhp3ass.solution.state import LegacyNullReferenceError


@dataclass(frozen=True)
class PoolComparison:
    """One query searched serially and in the pool: each worker's solution
    lines both ways, the pool's progress reports, and the combinations checked."""

    serial: list[list[str]]
    pooled: list[list[str]]
    pooled_error: str | None
    reports: list[tuple[int, int]]
    combinations: int


@pytest.fixture(scope="module")
def compare_with_serial(corpus_spec, legacy_data_dir, search_data_for, search_pool, serial_search):
    """Search a public corpus query with ``run_search`` and in the session pool,
    once per query for the module."""

    @lru_cache(maxsize=8)
    def compare(file_name: str) -> PoolComparison:
        spec = corpus_spec(f"corpus/{file_name}")
        data = search_data_for(spec)
        serial = serial_search(file_name)
        reports: list[tuple[int, int]] = []
        pooled = search_pool.run(
            data_dir=legacy_data_dir,
            spec=spec.query,
            query=serial.query,
            templates=[worker.template for worker in serial.workers],
            game=data.game,
            on_progress=lambda done, total: reports.append((done, total)),
        )
        skill_index = skill_indices(data.game)
        comparison = PoolComparison(
            serial=[
                [solution_line(solution, skill_index) for solution in worker.found]
                for worker in serial.workers
            ],
            pooled=[
                [solution_line(from_record(record, data.game), skill_index) for record in worker]
                for worker in pooled.workers
            ],
            pooled_error=None if pooled.error is None else repr(pooled.error),
            reports=reports,
            combinations=len(serial.workers)
            * prod(len(choices) for choices in armor_choices(serial.query)),
        )
        return comparison

    return compare


@pytest.mark.parametrize(
    "file_name",
    [
        "g13-hr3-attack-health-one-skill.json",
        "g16-attack-sharp-no-charms.json",
        "1a-attack-sharp-default-charms.json",
    ],
    ids=["g13-one-skill-4-workers", "g16-no-charms-1-worker", "1a-my-charms-6-workers"],
)
def test_pool_gives_each_workers_serial_solutions(compare_with_serial, file_name):
    comparison = compare_with_serial(file_name)

    assert comparison.pooled_error is None
    assert all(comparison.serial)
    assert comparison.pooled == comparison.serial


def test_progress_rises_to_every_combination_of_every_worker(compare_with_serial):
    comparison = compare_with_serial("g13-hr3-attack-health-one-skill.json")
    done = [report[0] for report in comparison.reports]

    assert {report[1] for report in comparison.reports} == {comparison.combinations}
    assert done == sorted(done)
    assert comparison.reports[-1] == (comparison.combinations, comparison.combinations)


def test_progress_arrives_from_inside_running_tasks(corpus_spec, legacy_data_dir, search_data_for):
    """With one process and no throttling, some report must fall between task
    boundaries: only a pool process's own messages can put it there."""
    spec = corpus_spec("corpus/g16-attack-sharp-no-charms.json")
    data = search_data_for(spec)
    serial = run_search(spec, data=data)
    search = PoolSearch.for_query(legacy_data_dir, spec=spec.query, query=serial.query)
    tasks = plan_tasks(worker_count=1, head_count=search.head_count, jobs=1)
    boundaries = set(
        accumulate(
            [(task.head_stop - task.head_start) * search.combinations_per_head for task in tasks],
            initial=0,
        )
    )
    reported: list[int] = []

    with SearchPool(jobs=1, progress_interval=0.0) as pool:
        pool.run(
            data_dir=legacy_data_dir,
            spec=spec.query,
            query=serial.query,
            templates=[worker.template for worker in serial.workers],
            game=data.game,
            on_progress=lambda done, total: reported.append(done),
        )

    assert len(tasks) == 4
    assert [done for done in reported if done not in boundaries] != []


def test_start_launches_every_process_before_the_first_search():
    existing = set(multiprocessing.active_children())

    with SearchPool(jobs=2) as pool:
        before_start = len(set(multiprocessing.active_children()) - existing)
        pool.start()
        after_start = len(set(multiprocessing.active_children()) - existing)

    assert [before_start, after_start] == [0, 2]


def test_a_throwing_worker_ends_the_merge_as_in_the_serial_search(
    empty_armor_spec, legacy_data_dir, search_data_for, search_pool
):
    data = search_data_for(empty_armor_spec)
    serial = run_search(empty_armor_spec, data=data, record_exceptions=True)
    loaded = load_query_my_charms(
        empty_armor_spec.my_charms, game=data.game, validity=data.validity
    )
    templates = worker_charms(
        serial.query,
        charm_mode=empty_armor_spec.charm_mode,
        my_charms=loaded.charms,
        tables=data.tables,
    )
    skill_index = skill_indices(data.game)
    reports: list[tuple[int, int]] = []

    pooled = search_pool.run(
        data_dir=legacy_data_dir,
        spec=empty_armor_spec.query,
        query=serial.query,
        templates=templates,
        game=data.game,
        on_progress=lambda done, total: reports.append((done, total)),
    )

    assert [len(templates), serial.worker_count] == [3, 3]
    assert reports[-1][0] < reports[-1][1]
    assert serial.exception is not None
    assert pooled.error is not None
    assert [pooled.error.worker, type(pooled.error.error)] == [
        serial.exception.worker,
        LegacyNullReferenceError,
    ]
    assert [
        [solution_line(from_record(record, data.game), skill_index) for record in worker]
        for worker in pooled.workers
    ] == [
        [solution_line(solution, skill_index) for solution in worker.found]
        for worker in serial.workers
    ]


@pytest.fixture
def three_worker_tasks() -> list[Task]:
    """Three workers, two tasks each."""
    return plan_tasks(worker_count=3, head_count=4, jobs=1, tasks_per_job=6)


def _record(marker: int) -> SolutionRecord:
    """A distinguishable record; the merge never looks inside one."""
    record = SolutionRecord(
        armors=(marker, -1, -1, -1, -1),
        charm=None,
        decorations=(),
        body_decorations=(),
        non_body_decorations=(),
        extra_skills=(),
        bad_skills=(),
        abilities=(),
        torso_slots_spare=0,
        torso_multiplier=1,
        total_slots_spare=0,
        fire_res=0,
        ice_res=0,
        water_res=0,
        thunder_res=0,
        dragon_res=0,
        defence=0,
        max_defence=0,
        rarity=0,
        difficulty=0,
        slots_spare=None,
    )
    return record


def test_merge_follows_task_order_not_completion_order(three_worker_tasks):
    reversed_completion = {
        number: [_record(number)] for number in reversed(range(len(three_worker_tasks)))
    }

    merged = merge_tasks(three_worker_tasks, outcomes=reversed_completion, worker_count=3)

    assert [len(three_worker_tasks), merged.error] == [6, None]
    assert [[record.armors[0] for record in worker] for worker in merged.workers] == [
        [0, 1],
        [2, 3],
        [4, 5],
    ]


def test_merge_drops_the_first_throwing_worker_and_every_later_one(three_worker_tasks):
    first_error = LegacyNullReferenceError("worker 1, second task")
    later_error = KeyError("worker 2")
    outcomes = {
        5: [_record(5)],
        4: later_error,
        3: first_error,
        2: [_record(2)],
        1: [_record(1)],
        0: [_record(0)],
    }

    merged = merge_tasks(three_worker_tasks, outcomes=outcomes, worker_count=3)

    assert merged.error is not None
    assert [merged.error.worker, merged.error.error] == [1, first_error]
    assert [[record.armors[0] for record in worker] for worker in merged.workers] == [[0, 1]]


def test_merge_allows_missing_tasks_only_after_a_throwing_one(three_worker_tasks):
    cancelled_after_error = {0: [_record(0)], 1: KeyError("worker 0"), 3: [_record(3)]}
    missing_without_error = {0: [_record(0)], 1: [_record(1)], 3: [_record(3)]}

    merged = merge_tasks(three_worker_tasks, outcomes=cancelled_after_error, worker_count=3)

    assert merged.error is not None
    assert [merged.error.worker, merged.workers] == [0, []]
    with pytest.raises(ValueError, match="task 2"):
        merge_tasks(three_worker_tasks, outcomes=missing_without_error, worker_count=3)


def test_step_reporter_sends_running_totals_at_most_once_per_interval():
    sent: list[int] = []
    times = iter([0.0, 0.03, 0.06, 0.12, 0.15, 0.25])
    reporter = StepReporter(send=sent.append, interval=0.1, clock=lambda: next(times))

    for _ in range(5):
        reporter.add(10)

    assert sent == [30, 50]


def test_progress_tally_keeps_the_highest_report_and_counts_finished_tasks_in_full():
    tally = ProgressTally([100, 50])

    tally.report(0, 40)
    tally.report(0, 20)
    tally.report(1, 80)
    after_reports = tally.done
    tally.finish(0)

    assert [after_reports, tally.done, tally.total] == [90, 150, 150]


def test_a_rebuilt_query_must_match_the_parents_armour_choices(
    one_skill_spec, legacy_data_dir, search_data_for
):
    serial = run_search(one_skill_spec, data=search_data_for(one_skill_spec))
    search = PoolSearch.for_query(legacy_data_dir, spec=one_skill_spec.query, query=serial.query)
    heads, *other_slots = search.armor_indices
    one_head_fewer = replace(search, armor_indices=(heads[:-1], *other_slots))
    heads_reordered = replace(search, armor_indices=(heads[::-1], *other_slots))

    rebuilt = RebuiltSearch.rebuild(search)

    assert armor_choice_indices(rebuilt.query) == search.armor_indices
    assert len(heads) > 1
    with pytest.raises(ChildStateError, match="armour choices"):
        RebuiltSearch.rebuild(one_head_fewer)
    with pytest.raises(ChildStateError, match="armour choices"):
        RebuiltSearch.rebuild(heads_reordered)


def _finished(outcome: list[SolutionRecord] | Exception) -> Future[list[SolutionRecord]]:
    future: Future[list[SolutionRecord]] = Future()
    if isinstance(outcome, Exception):
        future.set_exception(outcome)
    else:
        future.set_result(outcome)
    return future


def test_outcomes_stop_at_the_first_search_error_whatever_later_tasks_raised():
    first_error = LegacyNullReferenceError("task 1")
    futures = [
        _finished([_record(0)]),
        _finished(first_error),
        _finished(ValueError("task 2: a pool failure the serial search never reaches")),
    ]

    outcomes = task_outcomes(futures)

    assert sorted(outcomes) == [0, 1]
    assert outcomes[1] is first_error


def test_outcomes_raise_a_pool_failure_before_the_first_search_error():
    futures = [
        _finished([_record(0)]),
        _finished(ChildStateError("task 1")),
        _finished(LegacyNullReferenceError("task 2")),
    ]

    with pytest.raises(ChildStateError, match="task 1"):
        task_outcomes(futures)


def test_default_jobs_is_one_per_cpu_up_to_eight():
    jobs = default_jobs()

    assert 1 <= jobs <= 8
    assert default_jobs(max_jobs=1) == 1
