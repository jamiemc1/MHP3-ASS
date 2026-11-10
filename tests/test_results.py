"""``ResultSet`` (AddSolutions' duplicate removal) against the harness's candidates
files, plus the rules no golden reaches; and the same removal on records."""

from __future__ import annotations

from dataclasses import dataclass, replace

import pytest

from goldens import SearchGolden
from mhp3ass.charms.naming import charm_name
from mhp3ass.data import GameData
from mhp3ass.model import AbilityPair, ArmorType, Charm
from mhp3ass.query import SearchSpec
from mhp3ass.results.result_set import (
    ResultSet,
    SolutionList,
    hash_armor,
    hash_armor_indices,
    lines_sha256,
    record_line,
    skill_indices,
    solution_line,
)
from mhp3ass.search import run_search
from mhp3ass.solution.record import (
    CharmRecord,
    RecordIndex,
    SolutionRecord,
    charm_from_record,
    to_record,
)
from mhp3ass.solution.state import LegacyNullReferenceError, Solution


def _candidate_solution(line: str, game: GameData) -> Solution:
    """A solution with the armour and charm a solution line names; nothing else
    is filled in, since duplicate removal reads only those."""
    fields = [int(field) for field in line.split()]
    # -1 is an empty slot; a negative index would otherwise pick the last piece.
    armors = [
        None
        if fields[armor_type.value] == -1
        else game.armors[armor_type][fields[armor_type.value]]
        for armor_type in ArmorType
    ]
    position = 9
    position += 1 + fields[position]
    position += 1 + fields[position]
    charm = None
    if position < len(fields):
        num_slots, pair_count = fields[position], fields[position + 1]
        pairs = fields[position + 2 : position + 2 + 2 * pair_count]
        charm = Charm(
            num_slots=num_slots,
            abilities=[
                AbilityPair(ability=game.abilities[ability], amount=amount)
                for amount, ability in zip(pairs[::2], pairs[1::2], strict=True)
            ],
        )
    solution = Solution(armors=armors, charm=charm)
    return solution


def _replay(golden: SearchGolden, game: GameData) -> dict[str, object]:
    candidates = golden.candidates or []
    results = ResultSet()
    # Keyed by the solutions themselves (identity), which keeps them alive.
    lines: dict[Solution, str] = {}
    names_match = True
    added_by_worker = []
    for worker in range(golden.manifest["worker_count"]):
        solutions = []
        for candidate in candidates:
            if candidate.worker != worker:
                continue
            solution = _candidate_solution(candidate.solution_line, game)
            name = "" if solution.charm is None else charm_name(solution.charm)
            names_match = names_match and name == candidate.charm_name
            lines[solution] = candidate.solution_line
            solutions.append(solution)
        added = results.add_solutions(solutions)
        added_by_worker.append(lines_sha256([lines[solution] for solution in added]))
    kept = [lines[solution] for solution in results.all_solutions]
    replay = {
        "names_match": names_match,
        "added_sha256": added_by_worker,
        "solutions": kept,
        "solutions_sha256": lines_sha256(kept),
    }
    return replay


def test_replaying_candidates_keeps_the_harness_solutions(search_goldens, games_by_language):
    replayed = {}
    expected = {}
    for golden in search_goldens:
        if golden.candidates is None:
            continue
        query_id = golden.manifest["id"]
        replayed[query_id] = _replay(golden, games_by_language[golden.query["language"]])
        expected[query_id] = {
            "names_match": True,
            "added_sha256": [worker["added_sha256"] for worker in golden.manifest["workers"]],
            "solutions": golden.solution_lines,
            "solutions_sha256": golden.manifest["solutions_sha256"],
        }

    assert [sorted(replayed), replayed] == [["g03", "g04", "g13"], expected]


@pytest.fixture
def charm(attack) -> Charm:
    return Charm(num_slots=1, abilities=[AbilityPair(ability=attack, amount=4)])


@pytest.fixture
def pieces(make_armor):
    """One armour piece per index 0-8, usable in any slot."""
    return [make_armor(f"Piece {index}", index=index) for index in range(9)]


def test_hash_overlaps_between_slots(pieces):
    """Quirk 4: index 8 in the head and index 1 in the body hash alike."""
    head_8 = [pieces[8], pieces[0], pieces[0], pieces[0], pieces[0]]
    body_1 = [pieces[0], pieces[1], pieces[0], pieces[0], pieces[0]]

    assert [hash_armor(head_8), hash_armor(body_1)] == [8, 8]


def test_a_colliding_armour_set_with_the_same_charm_is_dropped(pieces, charm):
    first = Solution(armors=[pieces[8], *[pieces[0]] * 4], charm=charm.copy())
    collision = Solution(armors=[pieces[0], pieces[1], *[pieces[0]] * 3], charm=charm.copy())
    results = ResultSet()

    added = results.add_solutions([first, collision])

    assert [added, results.all_solutions] == [[first], [first]]


def test_the_same_armour_with_another_charm_is_kept(pieces, charm, defense):
    other_charm = Charm(num_slots=1, abilities=[AbilityPair(ability=defense, amount=4)])
    first = Solution(armors=[pieces[2]] * 5, charm=charm)
    second = Solution(armors=[pieces[2]] * 5, charm=other_charm)
    results = ResultSet()

    added = results.add_solutions([first, second])

    assert [added, results.all_solutions, sorted(results.existing_armor)] == [
        [first, second],
        [first, second],
        ["+4 Attack O--", "+4 Defense O--"],
    ]


def test_charm_free_solutions_are_never_de_duplicated(pieces):
    first = Solution(armors=[pieces[3]] * 5, charm=None)
    repeat = Solution(armors=[pieces[3]] * 5, charm=None)
    results = ResultSet()

    added = results.add_solutions([first, repeat])

    assert [added, results.all_solutions, results.existing_armor] == [
        [first, repeat],
        [first, repeat],
        {},
    ]


def test_duplicates_are_removed_across_calls(pieces, charm):
    """The key set lasts the whole search, so a later worker's repeat is dropped."""
    first = Solution(armors=[pieces[4]] * 5, charm=charm.copy())
    repeat = Solution(armors=[pieces[4]] * 5, charm=charm.copy())
    results = ResultSet()

    first_added = results.add_solutions([first])
    second_added = results.add_solutions([repeat])

    assert [first_added, second_added, results.all_solutions] == [[first], [], [first]]


def test_add_solution_keys_on_the_given_name(pieces, charm):
    first = Solution(armors=[pieces[5]] * 5, charm=charm)
    results = ResultSet()

    kept = [
        results.add_solution("+4 Attack O--", first),
        results.add_solution("+4 Attack O--", first),
        results.add_solution("another name", first),
    ]

    assert [kept, results.all_solutions] == [[True, False, True], [first, first]]


def test_a_charmed_solution_with_an_empty_slot_throws(pieces, charm):
    """Quirk T: HashArmor dereferences every slot; the charm's key is added first."""
    solution = Solution(armors=[pieces[1], None, pieces[1], pieces[1], pieces[1]], charm=charm)
    results = ResultSet()

    with pytest.raises(LegacyNullReferenceError):
        results.add_solutions([solution])

    assert [results.all_solutions, results.existing_armor] == [[], {"+4 Attack O--": set()}]


def test_a_throw_part_way_keeps_what_was_added_before_it(pieces, charm):
    """As in the original, solutions added before the throw stay in the list."""
    kept = Solution(armors=[pieces[1]] * 5, charm=charm.copy())
    empty_slot = Solution(armors=[pieces[2], None, pieces[2], pieces[2], pieces[2]], charm=charm)
    results = ResultSet()

    with pytest.raises(LegacyNullReferenceError):
        results.add_solutions([kept, empty_slot])

    assert [results.all_solutions, results.existing_armor] == [
        [kept],
        {"+4 Attack O--": {hash_armor(kept.armors)}},
    ]


@dataclass(frozen=True)
class RecordReplay:
    """One corpus query's workers, de-duplicated once as solutions (the search)
    and once as their records: kept lines, each worker's added lines, the keys."""

    solution_lines: list[str]
    record_lines: list[str]
    rebuilt_lines: list[str]
    added_by_solutions: list[list[str]]
    added_by_records: list[list[str]]
    keys_by_solutions: dict[str, set[int]]
    keys_by_records: dict[str, set[int]]
    found: int
    found_lines_differ: int


@pytest.fixture(scope="module")
def record_replays(repo_root, search_data_by_language) -> dict[str, RecordReplay]:
    """g13 (four one-skill workers that repeat each other's sets) and g19 (one
    worker that repeats its own), searched serially and replayed as records."""
    replays = {}
    for file_name in (
        "g13-hr3-attack-health-one-skill.json",
        "g19-gunner-load-up-piercings-event.json",
    ):
        spec = SearchSpec.from_file(repo_root / "tests" / "corpus" / file_name)
        data = search_data_by_language[spec.query.language]
        searched = run_search(spec, data=data)
        index = RecordIndex.for_game(data.game)
        skill_index = skill_indices(data.game)
        from_records = ResultSet()
        added_by_records = []
        found_lines_differ = 0
        for worker in searched.workers:
            records = [to_record(solution, index) for solution in worker.found]
            found_lines_differ += sum(
                record_line(record) != solution_line(solution, skill_index)
                for record, solution in zip(records, worker.found, strict=True)
            )
            added = from_records.add_records(SolutionList.of_records(records, data.game))
            added_by_records.append(added.lines(skill_index))
        replays[spec.query.id] = RecordReplay(
            solution_lines=searched.results.all_solutions.lines(skill_index),
            record_lines=from_records.all_solutions.lines(skill_index),
            rebuilt_lines=[
                solution_line(solution, skill_index) for solution in from_records.all_solutions
            ],
            added_by_solutions=[
                [solution_line(solution, skill_index) for solution in worker.added]
                for worker in searched.workers
            ],
            added_by_records=added_by_records,
            keys_by_solutions=searched.results.existing_armor,
            keys_by_records=from_records.existing_armor,
            found=sum(len(worker.found) for worker in searched.workers),
            found_lines_differ=found_lines_differ,
        )
    return replays


@pytest.mark.parametrize("query_id", ["g13", "g19"])
def test_records_keep_the_solutions_the_search_keeps(record_replays, query_id):
    replay = record_replays[query_id]

    assert replay.found_lines_differ == 0
    assert len(replay.record_lines) < replay.found
    assert replay.record_lines == replay.solution_lines
    assert replay.rebuilt_lines == replay.solution_lines
    assert replay.added_by_records == replay.added_by_solutions
    assert replay.keys_by_records == replay.keys_by_solutions


@pytest.fixture
def empty_record(teamhgg_game) -> SolutionRecord:
    """A record of a charm-free solution with every slot empty and slots counted."""
    solution = Solution(armors=[None] * 5, charm=None, slots_spare=[0, 0, 0, 0])
    record = to_record(solution, RecordIndex.for_game(teamhgg_game))
    return record


@pytest.fixture
def attack_record() -> CharmRecord:
    """+4 of ability 1 with one slot."""
    return CharmRecord(num_slots=1, abilities=((1, 4),), custom=False, hacked=False)


def test_a_record_is_rebuilt_once_and_then_read_as_that_solution(empty_record, teamhgg_game):
    solutions = SolutionList.of_records(
        [replace(empty_record, armors=(2, 2, 2, 2, 2))], teamhgg_game
    )

    first_read = solutions[0]

    assert solutions[0] is first_read
    assert first_read.armors == [teamhgg_game.armors[armor_type][2] for armor_type in ArmorType]


def test_kept_records_are_the_same_solutions_in_every_list(
    empty_record, attack_record, teamhgg_game
):
    """Found, added and all_solutions share one rebuilt Solution per record, as
    the search's lists share one Solution object."""
    first = replace(empty_record, armors=(3, 3, 3, 3, 3), charm=attack_record)
    repeat = replace(first, total_slots_spare=1)
    found = SolutionList.of_records([first, repeat], teamhgg_game)
    results = ResultSet()

    added = results.add_records(found)

    assert [len(found), len(added), len(results.all_solutions)] == [2, 1, 1]
    assert results.all_solutions[0] is added[0] is found[0]
    assert found[0] in results.all_solutions
    assert found[1] not in results.all_solutions


def test_charm_names_come_from_the_records(empty_record, attack_record, teamhgg_game):
    charmed = replace(empty_record, charm=attack_record)
    found = SolutionList.of_records([charmed, empty_record], teamhgg_game)

    names = found.charm_names()

    assert names == [charm_name(charm_from_record(attack_record, teamhgg_game)), ""]


def test_a_charmed_record_with_an_empty_slot_throws(empty_record, attack_record, teamhgg_game):
    """Quirk T on records: the charm's key is added before the hash throws."""
    kept = replace(empty_record, armors=(1, 1, 1, 1, 1), charm=attack_record)
    empty_slot = replace(empty_record, armors=(1, -1, 1, 1, 1), charm=attack_record)
    results = ResultSet()

    name = charm_name(charm_from_record(attack_record, teamhgg_game))

    with pytest.raises(LegacyNullReferenceError):
        results.add_records(SolutionList.of_records([kept, empty_slot], teamhgg_game))

    assert [results.all_solutions.lines({}), results.existing_armor] == [
        [record_line(kept)],
        {name: {hash_armor_indices(kept.armors)}},
    ]


def test_charm_free_records_are_never_de_duplicated(empty_record, teamhgg_game):
    results = ResultSet()

    added = results.add_records(SolutionList.of_records([empty_record, empty_record], teamhgg_game))

    assert [len(added), len(results.all_solutions), results.existing_armor] == [2, 2, {}]


def test_a_record_line_needs_the_slots_counted(empty_record):
    with pytest.raises(ValueError, match="slots"):
        record_line(replace(empty_record, slots_spare=None))
