"""``SolutionRecord``: corpus solutions survive the round trip.

Every solution of every worker of the cheaper corpus queries (one per charm
mode at least) goes to a record, through pickle, and back against the same
game; every field must come back equal, game records as the same objects and
``abilities`` in the same order.
"""

from __future__ import annotations

import pickle
from dataclasses import dataclass, fields, replace
from math import prod
from typing import Any

import pytest

from mhp3ass.model import AbilityPair, ArmorType, Charm
from mhp3ass.query import QuerySpec
from mhp3ass.relevance import formulate_query
from mhp3ass.search import run_worker
from mhp3ass.solution.record import CharmRecord, RecordIndex, from_record, to_record
from mhp3ass.solution.state import Solution
from solution_trace import template_charm


@dataclass
class RoundTrip:
    failures: list[str]
    checked: int
    charm_modes: set[str]


def _charm_differences(original: Charm | None, rebuilt: Charm | None) -> list[str]:
    if original is None or rebuilt is None:
        return [] if original is rebuilt else [f"charm {original!r} became {rebuilt!r}"]
    differences = [
        f"charm {name}"
        for name in ("num_slots", "custom", "hacked")
        if getattr(original, name) != getattr(rebuilt, name)
    ]
    original_pairs = [(pair.ability, pair.amount) for pair in original.abilities]
    rebuilt_pairs = [(pair.ability, pair.amount) for pair in rebuilt.abilities]
    same_pairs = len(original_pairs) == len(rebuilt_pairs) and all(
        a is b and m == n for (a, m), (b, n) in zip(original_pairs, rebuilt_pairs, strict=True)
    )
    if not same_pairs:
        differences.append("charm abilities")
    return differences


def _same_objects(original: list[Any], rebuilt: list[Any]) -> bool:
    same = len(original) == len(rebuilt) and all(
        a is b for a, b in zip(original, rebuilt, strict=True)
    )
    return same


def _differences(original: Solution, rebuilt: Solution) -> list[str]:
    """The ``Solution`` fields that differ: game records by identity, the rest by value."""
    differences = []
    for field in fields(Solution):
        name = field.name
        before = getattr(original, name)
        after = getattr(rebuilt, name)
        if name == "charm":
            differences += _charm_differences(before, after)
        elif name == "abilities":
            if not _same_objects(list(before), list(after)) or list(before.values()) != list(
                after.values()
            ):
                differences.append(name)
        elif name in (
            "armors",
            "decorations",
            "body_decorations",
            "non_body_decorations",
            "extra_skills",
            "bad_skills",
        ):
            if not _same_objects(before, after):
                differences.append(name)
        elif before != after or type(before) is not type(after):
            differences.append(name)
    return differences


def _round_trip_failures(search_goldens, trace_goldens, game, max_evaluations):
    """Solutions whose round trip changed a field, the solutions checked and their
    charm modes, over the queries of at most ``max_evaluations`` combinations
    across all workers."""
    index = RecordIndex.for_game(game)
    traces = {golden.query["id"]: golden for golden in trace_goldens}
    failures = []
    checked = 0
    charm_modes = set()
    for golden in search_goldens:
        query_id = golden.query["id"]
        query = formulate_query(game, QuerySpec.from_json(golden.query))
        workers = traces[query_id].header["workers"]
        combinations = prod(max(len(slot), 1) for slot in query.rel_armor)
        if combinations * len(workers) > max_evaluations:
            continue
        charm_modes.add(golden.query["charm_mode"])
        for number, worker in enumerate(workers):
            template = template_charm(worker["template"], game)
            solutions = run_worker(query, template, game)
            records = pickle.loads(
                pickle.dumps([to_record(solution, index) for solution in solutions])
            )
            for solution, record in zip(solutions, records, strict=True):
                differences = _differences(solution, from_record(record, game))
                if differences:
                    failures.append(f"{query_id} worker {number}: {differences}")
            checked += len(solutions)
    result = RoundTrip(failures=failures, checked=checked, charm_modes=charm_modes)
    return result


def test_corpus_solutions_survive_the_round_trip(search_goldens, trace_goldens, scratch_game):
    result = _round_trip_failures(
        search_goldens, trace_goldens, scratch_game, max_evaluations=50_000
    )
    assert result.failures == []
    assert result.checked > 0
    assert result.charm_modes == {"slotted", "one_skill", "two_skill", "none"}


def test_personal_solutions_survive_the_round_trip(
    personal_search_goldens, personal_trace_goldens, scratch_game
):
    result = _round_trip_failures(
        personal_search_goldens, personal_trace_goldens, scratch_game, max_evaluations=15_000
    )
    assert result.failures == []
    assert result.checked > 0
    assert "my_charms" in result.charm_modes


@pytest.fixture
def index(teamhgg_game):
    return RecordIndex.for_game(teamhgg_game)


@pytest.fixture
def hand_built_solution(teamhgg_game):
    """A solution with an empty head slot, a hacked custom charm without pairs, a
    decoration in each list, a bad skill and abilities in a non-sorted order."""
    game = teamhgg_game
    solution = Solution(
        armors=[None] + [game.armors[armor_type][1] for armor_type in list(ArmorType)[1:]],
        charm=Charm(num_slots=2, abilities=[], custom=True, hacked=True),
        decorations=[game.decorations[3], game.decorations[0]],
        body_decorations=[game.decorations[3]],
        non_body_decorations=[game.decorations[0]],
        extra_skills=[game.skills[5]],
        bad_skills=[game.skills[2]],
        abilities={game.abilities[9]: -2, game.abilities[1]: 7},
        torso_slots_spare=1,
        torso_multiplier=2,
        total_slots_spare=4_294_967_295,
        defence=10,
        slots_spare=[0, 1, 0, 1],
    )
    return solution


def test_hand_built_solution_survives_the_round_trip(hand_built_solution, index, teamhgg_game):
    record = to_record(hand_built_solution, index)
    rebuilt = from_record(record, teamhgg_game)
    assert _differences(hand_built_solution, rebuilt) == []
    assert record.armors[0] == -1
    assert rebuilt.charm is not None
    assert rebuilt.charm.abilities == []


def test_charmless_solution_without_slots_keeps_none(index, teamhgg_game):
    solution = Solution(armors=[None] * 5, charm=None)
    rebuilt = from_record(to_record(solution, index), teamhgg_game)
    assert rebuilt.charm is None
    assert rebuilt.slots_spare is None


def test_charm_pairs_keep_their_order(index, teamhgg_game):
    game = teamhgg_game
    charm = Charm(
        num_slots=1,
        abilities=[
            AbilityPair(ability=game.abilities[20], amount=5),
            AbilityPair(ability=game.abilities[4], amount=-3),
        ],
    )
    solution = Solution(armors=[None] * 5, charm=charm)
    record = to_record(solution, index)
    assert record.charm is not None
    assert record.charm.abilities == ((20, 5), (4, -3))


@pytest.fixture
def empty_record(index):
    """The record of a solution with every slot empty and no charm."""
    record = to_record(Solution(armors=[None] * 5, charm=None), index)
    return record


@pytest.mark.parametrize(
    "changes",
    [
        {"armors": (-2, -1, -1, -1, -1)},
        {"armors": (-1, -1, -1, -1, 100_000)},
        {"armors": (-1, -1, -1, -1)},
        {"decorations": (-1,)},
        {"body_decorations": (100_000,)},
        {"non_body_decorations": (-1,)},
        {"extra_skills": (-1,)},
        {"bad_skills": (100_000,)},
        {"abilities": ((-1, 3),)},
        {"abilities": ((3, 5), (3, -2))},
        {"charm": CharmRecord(num_slots=1, abilities=((-1, 2),), custom=False, hacked=False)},
    ],
    ids=[
        "armour-below-empty",
        "armour-past-end",
        "four-slots",
        "decoration-negative",
        "body-decoration-past-end",
        "non-body-decoration-negative",
        "extra-skill-negative",
        "bad-skill-past-end",
        "ability-negative",
        "ability-twice",
        "charm-ability-negative",
    ],
)
def test_bad_record_raises(changes, empty_record, teamhgg_game):
    with pytest.raises(ValueError):
        from_record(replace(empty_record, **changes), teamhgg_game)


def test_record_with_every_index_in_range_rebuilds(empty_record, teamhgg_game):
    record = replace(empty_record, decorations=(0,), extra_skills=(0,), abilities=((3, 5),))
    rebuilt = from_record(record, teamhgg_game)
    assert rebuilt.decorations == [teamhgg_game.decorations[0]]
    assert rebuilt.extra_skills == [teamhgg_game.skills[0]]
    assert rebuilt.abilities == {teamhgg_game.abilities[3]: 5}


@pytest.fixture(scope="module")
def other_game(load_teamhgg_game):
    """A second copy of the same game: equal data, different record objects."""
    return load_teamhgg_game()


def _mixed_solution(own, other, foreign_field):
    """A solution with a head piece, a charm pair, a decoration, an extra skill and
    an ability total, each from ``own`` except ``foreign_field``'s, from ``other``."""

    def source(field):
        return other if field == foreign_field else own

    solution = Solution(
        armors=[source("armour").armors[ArmorType.HEAD][1], None, None, None, None],
        charm=Charm(
            abilities=[AbilityPair(ability=source("charm_ability").abilities[4], amount=2)]
        ),
        decorations=[source("decoration").decorations[0]],
        extra_skills=[source("extra_skill").skills[0]],
        abilities={source("ability").abilities[9]: 1},
    )
    return solution


@pytest.mark.parametrize(
    "foreign_field",
    ["armour", "decoration", "extra_skill", "ability", "charm_ability"],
)
def test_record_from_another_game_raises(foreign_field, index, teamhgg_game, other_game):
    solution = _mixed_solution(teamhgg_game, other_game, foreign_field)
    with pytest.raises(ValueError):
        to_record(solution, index)


def test_solution_of_the_index_game_does_not_raise(index, teamhgg_game, other_game):
    solution = _mixed_solution(teamhgg_game, other_game, foreign_field=None)
    record = to_record(solution, index)
    assert record.armors == (1, -1, -1, -1, -1)
    assert record.extra_skills == (0,)
