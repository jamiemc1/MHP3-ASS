"""``ResultSet`` (AddSolutions' duplicate removal) against the harness's candidates
files, plus the rules no golden reaches."""

from __future__ import annotations

import pytest

from goldens import SearchGolden, lines_sha256
from mhp3ass.charms.naming import charm_name
from mhp3ass.data import GameData
from mhp3ass.model import AbilityPair, ArmorType, Charm
from mhp3ass.results import ResultSet, hash_armor
from mhp3ass.solution.state import LegacyNullReferenceError, Solution


def _candidate_solution(line: str, game: GameData) -> Solution:
    """A solution with the armour and charm a solution line names; nothing else
    is filled in, since duplicate removal reads only those."""
    fields = [int(field) for field in line.split()]
    armors = [game.armors[armor_type][fields[armor_type.value]] for armor_type in ArmorType]
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
    solution = Solution(armors=list(armors), charm=charm)
    return solution


def _replay(golden: SearchGolden, game: GameData) -> dict[str, object]:
    candidates = golden.candidates or []
    results = ResultSet()
    lines = {}
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
            lines[id(solution)] = candidate.solution_line
            solutions.append(solution)
        added = results.add_solutions(solutions)
        added_by_worker.append(lines_sha256([lines[id(solution)] for solution in added]))
    kept = [lines[id(solution)] for solution in results.all_solutions]
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

    assert results.add_solutions([first, second]) == [first, second]


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
