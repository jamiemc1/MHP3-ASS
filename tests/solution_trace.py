"""Replays the harness's MatchesQuery trace samples through the Python port.

The test-side counterpart of the harness's stepped copy
(``harness/src/TraceDump.cpp``): for each sampled combination it rebuilds the
armour and charm, runs the port's stage functions in ``MatchesQuery``'s order
and compares each stage's state with the trace's (format in
``tests/traces/README.md``).
"""

from __future__ import annotations

from collections.abc import Callable, Iterator, Sequence
from dataclasses import dataclass
from typing import Any

from goldens import TraceGolden
from mhp3ass.data import GameData
from mhp3ass.model import AbilityPair, Armor, Charm, Skill
from mhp3ass.query import Query, QuerySpec
from mhp3ass.relevance import formulate_query
from mhp3ass.solution.state import CalculationData, Solution, new_calculation_data


@dataclass(frozen=True)
class TraceCase:
    """One sampled combination, with the trace's full state after each stage."""

    label: str
    query: Query
    armors: list[Armor | None]
    template: Charm | None
    # Stage name -> every field as of that stage (the trace stores changes only).
    states: dict[str, dict[str, Any]]


def _template_charm(template: dict[str, Any] | None, game: GameData) -> Charm | None:
    if template is None:
        return None
    charm = Charm(
        num_slots=template["num_slots"],
        abilities=[
            AbilityPair(ability=game.abilities[index], amount=amount)
            for index, amount in template["abilities"]
        ],
        custom=template["custom"],
    )
    return charm


def _full_states(stages: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Each stage's complete state: the trace's deltas applied in order."""
    results = {"stage", "accepted", "called", "result"}
    state: dict[str, Any] = {}
    states = {}
    for stage in stages:
        state.update({key: value for key, value in stage.items() if key not in results})
        states[stage["stage"]] = dict(state)
    return states


def trace_cases(goldens: list[TraceGolden], game: GameData) -> Iterator[TraceCase]:
    """Every sample of every golden, as a case to replay.

    Building a query rewrites ``game``'s relevance flags, which the stage
    functions read, so a golden's cases are only valid until the next
    golden's are produced: replay each case as it comes.
    """
    for golden in goldens:
        query = formulate_query(game, QuerySpec.from_json(golden.query))
        # DoWork's nullptr piece for an empty slot (Form1.h:1865-1869).
        slots: list[list[Armor | None]] = [list(slot) or [None] for slot in query.rel_armor]
        templates = [
            _template_charm(worker["template"], game) for worker in golden.header["workers"]
        ]
        for sample in golden.samples:
            armors = [
                slot[position] for slot, position in zip(slots, sample["combination"], strict=True)
            ]
            indices = [armor.index if armor is not None else -1 for armor in armors]
            if indices != sample["armor"]:
                raise ValueError(f"{golden.name}: relevance disagrees with sample armour {sample}")
            case = TraceCase(
                label=f"{golden.name} worker {sample['worker']} {sample['combination']}",
                query=query,
                armors=armors,
                template=templates[sample["worker"]],
                states=_full_states(sample["stages"]),
            )
            yield case


def snapshot(solution: Solution, data: CalculationData, skill_index: dict[Skill, int]) -> dict:
    """The port's state in the trace's field format."""
    charm = solution.charm
    state = {
        "decorations": [decoration.index for decoration in solution.decorations],
        "body_decorations": [decoration.index for decoration in solution.body_decorations],
        "non_body_decorations": [decoration.index for decoration in solution.non_body_decorations],
        "abilities": [
            [ability.static_index, points] for ability, points in solution.abilities.items()
        ],
        "extra_skills": [skill_index[skill] for skill in solution.extra_skills],
        "bad_skills": [skill_index[skill] for skill in solution.bad_skills],
        "charm": None
        if charm is None
        else {
            "num_slots": charm.num_slots,
            "abilities": [[pair.ability.static_index, pair.amount] for pair in charm.abilities],
        },
        "torso_slots_spare": solution.torso_slots_spare,
        "torso_multiplier": solution.torso_multiplier,
        "total_slots_spare": solution.total_slots_spare,
        "slots_spare": solution.slots_spare,
        "need": [[ability.static_index, points] for ability, points in data.need.items()],
        "defence": solution.defence,
        "max_defence": solution.max_defence,
        "rarity": solution.rarity,
        "difficulty": solution.difficulty,
        "fire_res": solution.fire_res,
        "ice_res": solution.ice_res,
        "water_res": solution.water_res,
        "thunder_res": solution.thunder_res,
        "dragon_res": solution.dragon_res,
    }
    return state


def stage_mismatches(
    goldens: list[TraceGolden],
    game: GameData,
    stages: Sequence[tuple[str, Callable[[CalculationData], None]]],
) -> list[str]:
    """Replays ``stages`` (name, port function) in order for every sample and lists
    each stage whose state differs from the trace's, with the differing fields.

    A sample stops at the first stage its trace doesn't have (it was rejected
    or threw earlier).
    """
    skill_index = {skill: index for index, skill in enumerate(game.skills)}
    mismatches = []
    for case in trace_cases(goldens, game):
        charm = case.template.copy() if case.template is not None else None
        solution = Solution(armors=list(case.armors), charm=charm)
        data = new_calculation_data(solution, case.query)
        for name, run_stage in stages:
            if name not in case.states:
                break
            run_stage(data)
            ours = snapshot(solution, data, skill_index)
            expected = case.states[name]
            # Every field on both sides: a field the trace never wrote counts as a
            # difference, not as unchecked.
            fields = expected.keys() | ours.keys()
            differing = sorted(key for key in fields if ours.get(key) != expected.get(key))
            if differing:
                mismatches.append(f"{case.label} {name}: {differing}")
                break
    return mismatches
