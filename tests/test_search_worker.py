"""``run_worker`` against the harness's search goldens: the second net.

The traces sample combinations; this replays every combination of each
corpus query, worker by worker, with the charm templates the trace headers
record (StartSearch's dispatch is ported later). Where the golden keeps
every solution a worker found, in order (the candidates files, or a single
worker whose solutions were all kept), the lists must be equal; elsewhere
each worker's count must match the manifest's ``found`` and every kept
solution must be one the port found. Queries over 200,000 combinations
(g18, and the personal g17) are left to the full search.
"""

from __future__ import annotations

from math import prod

from goldens import SearchGolden, TraceGolden
from mhp3ass.charms.naming import charm_name
from mhp3ass.data import GameData
from mhp3ass.query import QuerySpec
from mhp3ass.relevance import formulate_query
from mhp3ass.results.result_set import solution_line
from mhp3ass.search import run_worker
from solution_trace import template_charm


def _worker_mismatches(
    search_goldens: list[SearchGolden],
    trace_goldens: list[TraceGolden],
    game: GameData,
    max_combinations: int = 200_000,
) -> list[str]:
    skill_index = {skill: index for index, skill in enumerate(game.skills)}
    traces = {golden.query["id"]: golden for golden in trace_goldens}
    mismatches = []
    for golden in search_goldens:
        query_id = golden.query["id"]
        query = formulate_query(game, QuerySpec.from_json(golden.query))
        if prod(max(len(slot), 1) for slot in query.rel_armor) > max_combinations:
            continue
        workers = golden.manifest["workers"]
        templates = [
            template_charm(worker["template"], game)
            for worker in traces[query_id].header["workers"]
        ]
        if len(templates) != len(workers):
            mismatches.append(f"{query_id}: {len(templates)} templates, {len(workers)} workers")
            continue
        found_lines = set()
        for number, (worker, template) in enumerate(zip(workers, templates, strict=True)):
            solutions = run_worker(query, template, game)
            found = [
                (
                    charm_name(solution.charm) if solution.charm is not None else "",
                    solution_line(solution, skill_index),
                )
                for solution in solutions
            ]
            found_lines.update(line for _, line in found)
            template_name = charm_name(template) if template is not None else None
            # One worker whose solutions were all kept: the solutions file is its list.
            whole_result = (
                len(workers) == 1 and worker["found"] == golden.manifest["solution_count"]
            )
            if template_name != worker["charm"] or len(found) != worker["found"]:
                mismatches.append(
                    f"{query_id} worker {number}: {len(found)} found, {template_name}"
                )
            elif golden.candidates is not None:
                expected = [
                    (candidate.charm_name, candidate.solution_line)
                    for candidate in golden.candidates
                    if candidate.worker == number
                ]
                if found != expected:
                    mismatches.append(f"{query_id} worker {number}: candidates differ")
            elif whole_result and [line for _, line in found] != golden.solution_lines:
                mismatches.append(f"{query_id} worker {number}: solutions differ")
        missing = set(golden.solution_lines) - found_lines
        if missing:
            mismatches.append(f"{query_id}: {len(missing)} kept solutions not found")
    return mismatches


def test_workers_find_what_the_harness_found(search_goldens, trace_goldens, scratch_game):
    assert _worker_mismatches(search_goldens, trace_goldens, scratch_game) == []


def test_personal_workers_find_what_the_harness_found(
    personal_search_goldens, personal_trace_goldens, scratch_game
):
    assert _worker_mismatches(personal_search_goldens, personal_trace_goldens, scratch_game) == []
