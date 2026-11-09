"""Splitting a search into tasks for a process pool.

Not a port of an original module: the original runs one thread per charm
template (``legacy/Form1.h:1852-1930``). Here each worker's combinations are
also split into contiguous ranges of head pieces, so a search with a single
template still spreads over several processes. ``run_worker`` loops over head
pieces outermost, so a worker's solutions are the concatenation of its tasks'
solutions in ``head_start`` order.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import ceil


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
    ranges whose sizes differ by at most one, larger first. ``head_count``
    counts the head slot's choices after an empty slot is padded, so it is at
    least 1.
    """
    if worker_count < 0:
        raise ValueError(f"worker_count must not be negative, not {worker_count}")
    if head_count < 1:
        raise ValueError(f"head_count must be at least 1, not {head_count}")
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
