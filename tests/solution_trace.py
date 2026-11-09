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
from mhp3ass.search import armor_choices, dotnet_exception_type
from mhp3ass.solution import finish, has_enough_points, match
from mhp3ass.solution.bad_skills import fix_bad_skills, reorder_gems
from mhp3ass.solution.charm_reduction import (
    rearrange_decorations,
    reduce_charm,
    reduce_skills,
    reduce_slots,
)
from mhp3ass.solution.extra_skills import calculate_extra_skills
from mhp3ass.solution.fill import calculate_decorations
from mhp3ass.solution.initial import get_initial_data
from mhp3ass.solution.state import (
    CalculationData,
    LegacyNullReferenceError,
    Solution,
    new_calculation_data,
)


@dataclass(frozen=True)
class TraceCase:
    """One sampled combination, with the trace's full state after each stage."""

    label: str
    query: Query
    armors: list[Armor | None]
    template: Charm | None
    # Stage name -> every field as of that stage (the trace stores changes only).
    states: dict[str, dict[str, Any]]
    # Stage name -> the stage's results (points: accepted; fix_bad: called,
    # result; reorder: result), for the stages that have any.
    results: dict[str, dict[str, Any]]
    # The .NET exception type the original threw, or None.
    exception: str | None


# The trace fields that are a stage's results rather than solution state.
RESULT_FIELDS = frozenset({"accepted", "called", "result"})


@dataclass(frozen=True)
class Stage:
    """One replayed stage: ``run`` returns the stage's results (or ``None``), and
    ``applies`` says, from the port's results so far, whether ``MatchesQuery``
    runs this stage at all. A stage without ``applies`` runs whenever the trace
    has it."""

    name: str
    run: Callable[[CalculationData], dict[str, Any] | None]
    applies: Callable[[CalculationData, dict[str, dict[str, Any]]], bool] | None = None


def template_charm(template: dict[str, Any] | None, game: GameData) -> Charm | None:
    """A worker's charm template as a trace header records it (``None`` for no charm)."""
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
    not_state = RESULT_FIELDS | {"stage"}
    state: dict[str, Any] = {}
    states = {}
    for stage in stages:
        state.update({key: value for key, value in stage.items() if key not in not_state})
        states[stage["stage"]] = dict(state)
    return states


def _stage_results(stages: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    results = {
        stage["stage"]: {key: value for key, value in stage.items() if key in RESULT_FIELDS}
        for stage in stages
        if RESULT_FIELDS & stage.keys()
    }
    return results


def trace_cases(goldens: list[TraceGolden], game: GameData) -> Iterator[TraceCase]:
    """Every sample of every golden, as a case to replay.

    Building a query rewrites ``game``'s relevance flags, which the stage
    functions read, so a golden's cases are only valid until the next
    golden's are produced: replay each case as it comes.
    """
    for golden in goldens:
        query = formulate_query(game, QuerySpec.from_json(golden.query))
        slots = armor_choices(query)
        templates = [
            template_charm(worker["template"], game) for worker in golden.header["workers"]
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
                results=_stage_results(sample["stages"]),
                exception=sample["exception"],
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


def _difference(
    case: TraceCase,
    name: str,
    results: dict[str, Any] | None,
    data: CalculationData,
    skill_index: dict[Skill, int],
) -> str | None:
    """How the port's state and results after stage ``name`` differ from the trace's."""
    ours = snapshot(data.solution, data, skill_index)
    expected = case.states[name]
    # Every field on both sides: a field the trace never wrote counts as a
    # difference, not as unchecked.
    fields = expected.keys() | ours.keys()
    differing = sorted(key for key in fields if ours.get(key) != expected.get(key))
    expected_results = case.results.get(name, {})
    if (results or {}) != expected_results:
        differing.append(f"results {results} != {expected_results}")
    difference = f"{case.label} {name}: {differing}" if differing else None
    return difference


def _dotnet_exception(error: Exception) -> str:
    """The .NET exception type the port's exception stands for; re-raises an
    error the original never raises."""
    exception_type = dotnet_exception_type(error)
    if exception_type is None:
        raise error
    return exception_type


def _threw_difference(
    case: TraceCase, stage: Stage, data: CalculationData, skill_index: dict[Skill, int]
) -> str | None:
    """Runs a stage the original threw in: the port must raise the same exception
    type and leave the state the trace's ``threw`` stage recorded."""
    try:
        stage.run(data)
    except (LegacyNullReferenceError, LookupError) as error:
        raised = _dotnet_exception(error)
    else:
        difference = f"{case.label} {stage.name}: port didn't raise {case.exception}"
        return difference
    differing = []
    if raised != case.exception:
        differing.append(f"raised {raised}, not {case.exception}")
    ours = snapshot(data.solution, data, skill_index)
    expected = case.states["threw"]
    differing += sorted(
        key for key in expected.keys() | ours.keys() if ours.get(key) != expected.get(key)
    )
    difference = f"{case.label} {stage.name} (threw): {differing}" if differing else None
    return difference


def stage_mismatches(
    goldens: list[TraceGolden],
    game: GameData,
    stages: Sequence[Stage],
) -> list[str]:
    """Replays ``stages`` in order for every sample and lists each stage whose
    state or results differ from the trace's, with the differing fields.

    A stage without ``applies`` runs when the trace has it; a sample stops at
    the first such stage its trace lacks (it was rejected or threw earlier).
    A stage with ``applies`` must be in the trace exactly when ``applies``
    says ``MatchesQuery`` runs it, and is skipped when it doesn't. Where the
    original threw inside a stage, the trace has a ``threw`` stage instead:
    the port must raise there too, with the same exception type and state.
    """
    skill_index = {skill: index for index, skill in enumerate(game.skills)}
    mismatches = []
    for case in trace_cases(goldens, game):
        charm = case.template.copy() if case.template is not None else None
        solution = Solution(armors=list(case.armors), charm=charm)
        data = new_calculation_data(solution, case.query)
        results_so_far: dict[str, dict[str, Any]] = {}
        for stage in stages:
            traced = stage.name in case.states
            runs = traced if stage.applies is None else stage.applies(data, results_so_far)
            threw_here = runs and not traced and "threw" in case.states
            if threw_here:
                difference = _threw_difference(case, stage, data, skill_index)
                if difference is not None:
                    mismatches.append(difference)
                break
            if stage.applies is None and not traced:
                break
            if runs != traced:
                mismatches.append(f"{case.label} {stage.name}: port runs it {runs}")
                break
            if not runs:
                continue
            results = stage.run(data)
            difference = _difference(case, stage.name, results, data, skill_index)
            if difference is not None:
                mismatches.append(difference)
                break
            results_so_far[stage.name] = results or {}
    return mismatches


def _points_check(data: CalculationData) -> dict[str, Any]:
    results = {"accepted": has_enough_points(data)}
    return results


def fill_as_matches_query(data: CalculationData) -> None:
    """MatchesQuery's filling pass (Solution.cpp:673): both flags set, whatever the query."""
    calculate_decorations(data, allow_bad=True, allow_detrimental=True)


def _extra(data: CalculationData) -> None:
    calculate_extra_skills(data)


def matches_query_stages(game: GameData) -> list[Stage]:
    """MatchesQuery's stages (Solution.cpp:672-722), with CheckBadSkills'
    short-circuit (:114) unrolled into its two repairs, as the harness traces
    them."""

    def accepted(data: CalculationData, results: dict[str, dict[str, Any]]) -> bool:
        return results["points"]["accepted"]

    def needs_fixing(data: CalculationData, results: dict[str, dict[str, Any]]) -> bool:
        fixing = (
            accepted(data, results)
            and not data.query.allow_bad
            and len(data.solution.bad_skills) > 0
        )
        return fixing

    def fix_bad(data: CalculationData) -> dict[str, Any]:
        called = data.solution.total_slots_spare > 0
        fixed = called and fix_bad_skills(data, game)
        results = {"called": called, "result": fixed}
        return results

    def fix_failed(data: CalculationData, results: dict[str, dict[str, Any]]) -> bool:
        failed = "fix_bad" in results and not results["fix_bad"]["result"]
        return failed

    def reorder(data: CalculationData) -> dict[str, Any]:
        results = {"result": reorder_gems(data, game)}
        return results

    def passes_bad_skills(data: CalculationData, results: dict[str, dict[str, Any]]) -> bool:
        """Past CheckBadSkills: no repair was needed, or one worked. Read from the
        repairs' results, since ExtraSkills recomputes bad_skills later on."""
        if "extra" not in results:
            return False
        if "fix_bad" not in results:
            return True
        if results["fix_bad"]["result"]:
            return True
        passes = "reorder" in results and results["reorder"]["result"]
        return passes

    # The charm branch is chosen before any charm stage runs, and ReduceCharm
    # (the last but one) is the only one that can null the charm
    # (Solution.cpp:687-700).
    def generated_charm(data: CalculationData, results: dict[str, dict[str, Any]]) -> bool:
        charm = data.solution.charm
        generated = passes_bad_skills(data, results) and charm is not None and not charm.custom
        return generated

    def rearranges(data: CalculationData, results: dict[str, dict[str, Any]]) -> bool:
        charm = data.solution.charm
        custom = passes_bad_skills(data, results) and charm is not None and charm.custom
        return custom or "skills_reduced" in results

    def after(previous: str) -> Callable[[CalculationData, dict[str, dict[str, Any]]], bool]:
        def follows(data: CalculationData, results: dict[str, dict[str, Any]]) -> bool:
            return previous in results

        return follows

    stages = [
        Stage(name="initial", run=get_initial_data),
        Stage(name="decorated", run=fill_as_matches_query),
        Stage(name="points", run=_points_check),
        Stage(name="extra", run=_extra, applies=accepted),
        Stage(name="fix_bad", run=fix_bad, applies=needs_fixing),
        Stage(name="reorder", run=reorder, applies=fix_failed),
        Stage(name="slots_reduced", run=reduce_slots, applies=generated_charm),
        Stage(name="skills_reduced", run=reduce_skills, applies=after("slots_reduced")),
        Stage(name="rearranged", run=rearrange_decorations, applies=rearranges),
        Stage(name="charm_reduced", run=reduce_charm, applies=after("skills_reduced")),
        Stage(name="extra_final", run=_extra, applies=after("charm_reduced")),
        Stage(name="final", run=finish, applies=passes_bad_skills),
    ]
    return stages


def _outcome(case: TraceCase) -> str:
    """What the harness recorded: accepted, rejected_points, rejected_bad_skills or exception."""
    if case.exception is not None:
        return "exception"
    if "final" in case.states:
        return "accepted"
    if not case.results["points"]["accepted"]:
        return "rejected_points"
    return "rejected_bad_skills"


def matches_query_mismatches(goldens: list[TraceGolden], game: GameData) -> list[str]:
    """Runs MatchesQuery's body once per sample and compares how it ended
    (accepted, which check rejected it, or the exception type) and its state,
    ``need`` included, with the trace's last stage (``final``, the stage it
    was rejected at, or ``threw``)."""
    skill_index = {skill: index for index, skill in enumerate(game.skills)}
    mismatches = []
    for case in trace_cases(goldens, game):
        charm = case.template.copy() if case.template is not None else None
        solution = Solution(armors=list(case.armors), charm=charm)
        data = new_calculation_data(solution, case.query)
        raised = None
        try:
            outcome = match(data, game).value
        except (LegacyNullReferenceError, LookupError) as error:
            raised = _dotnet_exception(error)
            outcome = "exception"
        expected = _outcome(case)
        if outcome != expected or raised != case.exception:
            mismatches.append(f"{case.label}: {outcome} {raised}, not {expected} {case.exception}")
            continue
        last_stage = list(case.states)[-1]
        ours = snapshot(solution, data, skill_index)
        expected_state = case.states[last_stage]
        differing = sorted(
            key
            for key in ours.keys() | expected_state.keys()
            if ours.get(key) != expected_state.get(key)
        )
        if differing:
            mismatches.append(f"{case.label} after {last_stage}: {differing}")
    return mismatches
