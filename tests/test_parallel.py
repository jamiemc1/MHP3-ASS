"""``plan_tasks``: every (worker, head piece) once, in loop order, about four tasks per process."""

from __future__ import annotations

from dataclasses import replace
from itertools import product

import pytest

from mhp3ass.parallel import Task, plan_tasks
from mhp3ass.query import QuerySpec
from mhp3ass.relevance import formulate_query
from mhp3ass.results.result_set import solution_line
from mhp3ass.search import armor_choices, run_worker
from solution_trace import template_charm


def _coverage_errors(tasks: list[Task], worker_count: int, head_count: int) -> list[str]:
    """What is wrong with ``tasks`` as a split of every worker's head range, in order."""
    errors = []
    keys = [(task.worker, task.head_start) for task in tasks]
    if keys != sorted(keys):
        errors.append("not in (worker, head_start) order")
    for worker in range(worker_count):
        ranges = [(task.head_start, task.head_stop) for task in tasks if task.worker == worker]
        covered = [head for start, stop in ranges for head in range(start, stop)]
        if covered != list(range(head_count)):
            errors.append(f"worker {worker} covers {ranges}")
        if any(stop <= start for start, stop in ranges):
            errors.append(f"worker {worker} has an empty range in {ranges}")
    if {task.worker for task in tasks} != set(range(worker_count)):
        errors.append("workers missing or out of range")
    return errors


@pytest.mark.parametrize(
    ("worker_count", "head_count", "jobs"),
    list(product([1, 2, 5, 6, 40, 50], [1, 3, 16, 22, 100], [1, 4, 8])),
)
def test_tasks_cover_every_head_piece_of_every_worker_in_order(worker_count, head_count, jobs):
    tasks = plan_tasks(worker_count=worker_count, head_count=head_count, jobs=jobs)
    assert _coverage_errors(tasks, worker_count, head_count) == []


def test_single_worker_is_split_into_four_tasks_per_process():
    tasks = plan_tasks(worker_count=1, head_count=100, jobs=8)
    sizes = [task.head_stop - task.head_start for task in tasks]
    assert len(tasks) == 32
    assert sizes == [4] * 4 + [3] * 28


def test_chunks_never_split_a_head_piece():
    tasks = plan_tasks(worker_count=1, head_count=16, jobs=8)
    assert tasks == [Task(worker=0, head_start=head, head_stop=head + 1) for head in range(16)]


def test_many_workers_get_one_task_each():
    tasks = plan_tasks(worker_count=40, head_count=22, jobs=8)
    assert tasks == [Task(worker=worker, head_start=0, head_stop=22) for worker in range(40)]


def test_every_worker_is_split_the_same_way():
    tasks = plan_tasks(worker_count=6, head_count=22, jobs=6)
    ranges = [(task.head_start, task.head_stop) for task in tasks if task.worker == 0]
    assert ranges == [(0, 6), (6, 12), (12, 17), (17, 22)]
    assert len(tasks) == 24


def test_no_workers_means_no_tasks():
    tasks = plan_tasks(worker_count=0, head_count=5, jobs=4)
    assert tasks == []


@pytest.fixture
def g13_query_and_templates(search_goldens, trace_goldens, scratch_game):
    """g13's query (one-skill mode, four workers) and its workers' charm templates."""
    golden = next(golden for golden in search_goldens if golden.query["id"] == "g13")
    trace = next(golden for golden in trace_goldens if golden.query["id"] == "g13")
    query = formulate_query(scratch_game, QuerySpec.from_json(golden.query))
    templates = [
        template_charm(worker["template"], scratch_game) for worker in trace.header["workers"]
    ]
    return query, templates


def test_tasks_concatenated_in_order_give_each_workers_serial_solutions(
    g13_query_and_templates, scratch_game
):
    query, templates = g13_query_and_templates
    skill_index = {skill: index for index, skill in enumerate(scratch_game.skills)}
    head_count = len(armor_choices(query)[0])
    tasks = plan_tasks(worker_count=len(templates), head_count=head_count, jobs=3)
    merged: list[list[str]] = [[] for _ in templates]
    for task in tasks:
        head_range = query.rel_armor[0][task.head_start : task.head_stop]
        task_query = replace(query, rel_armor=[head_range, *query.rel_armor[1:]])
        solutions = run_worker(task_query, templates[task.worker], scratch_game)
        merged[task.worker] += [solution_line(solution, skill_index) for solution in solutions]
    serial = [
        [
            solution_line(solution, skill_index)
            for solution in run_worker(query, template, scratch_game)
        ]
        for template in templates
    ]
    assert head_count > 1
    assert len(tasks) > len(templates)
    assert merged == serial


@pytest.mark.parametrize(
    "arguments",
    [
        {"worker_count": -1, "head_count": 5, "jobs": 4},
        {"worker_count": 2, "head_count": 0, "jobs": 4},
        {"worker_count": 2, "head_count": 5, "jobs": 0},
        {"worker_count": 2, "head_count": 5, "jobs": 4, "tasks_per_job": 0},
    ],
    ids=["negative-workers", "no-head-pieces", "no-jobs", "no-tasks-per-job"],
)
def test_invalid_arguments_raise(arguments):
    with pytest.raises(ValueError):
        plan_tasks(**arguments)
