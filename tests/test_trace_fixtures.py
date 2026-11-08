"""Checks that the MatchesQuery trace goldens are current and internally consistent.

The harness already throws if its stepped copy of MatchesQuery ends in a
different state from the original. These tests check what it can't: that
each trace matches its spec and query, that its samples are combinations the
search really runs, that its census adds up and agrees with the search
goldens, and that every sample's stages follow MatchesQuery's order.
"""

from __future__ import annotations

import json
from math import prod
from pathlib import Path
from typing import Any

from goldens import TraceGolden, read_golden


def _stale_traces(goldens: list[TraceGolden]) -> list[str]:
    """Traces whose spec or query changed after the golden was generated."""
    stale = [
        golden.name
        for golden in goldens
        if json.loads(golden.header["query_json"]) != golden.query
        or json.loads(golden.header["spec_json"]) != golden.spec
    ]
    return stale


def test_trace_goldens_are_current(trace_goldens: list[TraceGolden]):
    assert _stale_traces(trace_goldens) == []


def test_personal_trace_goldens_are_current(personal_trace_goldens: list[TraceGolden]):
    assert _stale_traces(personal_trace_goldens) == []


def test_every_trace_golden_has_a_spec(repo_root: Path):
    tests_dir = repo_root / "tests"
    spec_names = {path.stem for path in (tests_dir / "traces").glob("*.json")}
    golden_names = {
        path.name.removesuffix(".jsonl.gz")
        for path in (tests_dir / "golden" / "traces").glob("*.jsonl.gz")
    }

    assert golden_names == spec_names


def _golden_dir_for(golden: TraceGolden, repo_root: Path) -> Path:
    """The golden folder for the trace's query: personal specs and their queries keep
    theirs in tests/savefile. Decided by the spec's own location, because the query
    path is resolved and tests/savefile/ may hold symlinks."""
    savefile_dir = repo_root / "tests" / "savefile"
    if golden.spec_path.is_relative_to(savefile_dir):
        return savefile_dir / "golden"
    return repo_root / "tests" / "golden"


def _relevant_armor(golden: TraceGolden, repo_root: Path) -> list[list[int]]:
    """Relevant armour indices per slot, with DoWork's nullptr (-1) for an empty slot."""
    relevance_path = (
        _golden_dir_for(golden, repo_root) / "relevance" / f"{golden.query_path.stem}.json.gz"
    )
    relevance = read_golden(relevance_path)
    slots = [
        [entry["index"] for entry in listing["relevant"]] or [-1]
        for listing in relevance["armor"].values()
    ]
    return slots


def _misplaced_samples(goldens: list[TraceGolden], repo_root: Path) -> list[str]:
    """Samples whose positions, armour or loop index don't match the relevant armour."""
    misplaced = []
    for golden in goldens:
        slots = _relevant_armor(golden, repo_root)
        sizes = [len(slot) for slot in slots]
        for sample in golden.samples:
            positions = sample["combination"]
            armor = [slot[position] for slot, position in zip(slots, positions, strict=True)]
            index = 0
            for size, position in zip(sizes, positions, strict=True):
                index = index * size + position
            if (
                armor != sample["armor"]
                or index != sample["index"]
                or sample["worker"] >= len(golden.header["workers"])
            ):
                misplaced.append(f"{golden.name} worker {sample['worker']} {positions}")
    return misplaced


def test_trace_samples_are_combinations_the_search_runs(
    trace_goldens: list[TraceGolden], repo_root: Path
):
    assert _misplaced_samples(trace_goldens, repo_root) == []


def test_personal_trace_samples_are_combinations_the_search_runs(
    personal_trace_goldens: list[TraceGolden], repo_root: Path
):
    assert _misplaced_samples(personal_trace_goldens, repo_root) == []


def _census_problems(goldens: list[TraceGolden], repo_root: Path) -> list[str]:
    """Workers whose census doesn't account for every combination exactly once,
    or whose small search wasn't sampled completely."""
    problems = []
    for golden in goldens:
        combinations = prod(len(slot) for slot in _relevant_armor(golden, repo_root))
        for worker in golden.header["workers"]:
            census = worker["census"]
            outcomes = (
                census["accepted"]
                + census["rejected_points"]
                + census["rejected_bad_skills"]
                + census["exception"]
            )
            exceptions = sum(worker["exception_types"].values())
            sampled = sum(1 for sample in golden.samples if sample["worker"] == worker["worker"])
            fully_sampled = worker["combinations"] > 500 or sampled == worker["combinations"]
            if not (
                outcomes == worker["combinations"] == combinations
                and exceptions == census["exception"]
                and fully_sampled
            ):
                problems.append(f"{golden.name} worker {worker['worker']}")
    return problems


def test_trace_census_covers_every_combination(trace_goldens: list[TraceGolden], repo_root: Path):
    assert _census_problems(trace_goldens, repo_root) == []


def test_personal_trace_census_covers_every_combination(
    personal_trace_goldens: list[TraceGolden], repo_root: Path
):
    assert _census_problems(personal_trace_goldens, repo_root) == []


def _search_disagreements(goldens: list[TraceGolden], repo_root: Path) -> list[str]:
    """Corpus traces whose workers or accepted counts differ from the search golden's.

    The search golden's "found" is MatchesQuery's accept count per worker, before
    duplicate removal, so the two harness commands must agree on it.
    """
    disagreements = []
    for golden in goldens:
        manifest_path = (
            _golden_dir_for(golden, repo_root)
            / "search"
            / f"{golden.query_path.stem}.manifest.json"
        )
        if not manifest_path.is_file():
            continue
        manifest = read_golden(manifest_path)
        from_search = [(worker["charm"], worker["found"]) for worker in manifest["workers"]]
        from_trace = [
            (worker["charm"], worker["census"]["accepted"]) for worker in golden.header["workers"]
        ]
        if from_search != from_trace:
            disagreements.append(golden.name)
    return disagreements


def test_trace_accepts_match_search_goldens(trace_goldens: list[TraceGolden], repo_root: Path):
    assert _search_disagreements(trace_goldens, repo_root) == []


def test_personal_trace_accepts_match_search_goldens(
    personal_trace_goldens: list[TraceGolden], repo_root: Path
):
    assert _search_disagreements(personal_trace_goldens, repo_root) == []


def test_every_corpus_query_is_traced(trace_goldens: list[TraceGolden], repo_root: Path):
    corpus = {path.resolve() for path in (repo_root / "tests" / "corpus").glob("*.json")}
    traced = {golden.query_path for golden in trace_goldens}

    assert corpus - traced == set()


def _expected_stages(
    sample: dict[str, Any], template: dict[str, Any] | None, allow_bad: bool
) -> list[str]:
    """MatchesQuery's stage order (Solution.cpp:672-722) for one sample.

    The branches come from the query and the worker's charm template; only the
    two repair results and the points check come from the sample itself.
    """
    stages = {stage["stage"]: stage for stage in sample["stages"]}
    expected = ["initial", "decorated", "points"]
    if "points" in stages and not stages["points"]["accepted"]:
        return expected
    expected.append("extra")
    # extra lists bad_skills only when CalculateExtraSkills found some.
    has_bad_skills = bool(stages.get("extra", {}).get("bad_skills"))
    if not allow_bad and has_bad_skills:
        expected.append("fix_bad")
        if "fix_bad" in stages and not stages["fix_bad"]["result"]:
            expected.append("reorder")
            if "reorder" in stages and not stages["reorder"]["result"]:
                return expected
    if template is not None and template["custom"]:
        expected.append("rearranged")
    elif template is not None:
        expected += [
            "slots_reduced",
            "skills_reduced",
            "rearranged",
            "charm_reduced",
            "extra_final",
        ]
    expected.append("final")
    return expected


def _expected_outcome(names: list[str]) -> str:
    if names[-1] == "final":
        return "accepted"
    if names[-1] == "points":
        return "rejected_points"
    return "rejected_bad_skills"


def _misordered_samples(goldens: list[TraceGolden]) -> list[str]:
    """Samples whose stages don't follow MatchesQuery, or whose outcome doesn't match them.

    A sample that threw stops part-way: a proper prefix of the stages, then "threw".
    """
    misordered = []
    for golden in goldens:
        templates = [worker["template"] for worker in golden.header["workers"]]
        for sample in golden.samples:
            names = [stage["stage"] for stage in sample["stages"]]
            expected = _expected_stages(
                sample,
                template=templates[sample["worker"]],
                allow_bad=golden.query["allow_bad"],
            )
            if sample["outcome"] == "exception":
                before_throw = names[:-1]
                consistent = (
                    sample["exception"] is not None
                    and names[-1:] == ["threw"]
                    and before_throw == expected[: len(before_throw)]
                    and len(before_throw) < len(expected)
                )
            else:
                consistent = (
                    sample["exception"] is None
                    and names == expected
                    and sample["outcome"] == _expected_outcome(names)
                )
            if not consistent:
                misordered.append(
                    f"{golden.name} worker {sample['worker']} {sample['combination']}"
                )
    return misordered


def test_trace_stages_follow_matches_query(trace_goldens: list[TraceGolden]):
    assert _misordered_samples(trace_goldens) == []


def test_personal_trace_stages_follow_matches_query(personal_trace_goldens: list[TraceGolden]):
    assert _misordered_samples(personal_trace_goldens) == []


def _incomplete_snapshots(goldens: list[TraceGolden]) -> list[str]:
    """Samples whose initial or final stage doesn't list every snapshot field
    (tests/traces/README.md); the other stages list only what changed."""
    fields = {
        "decorations",
        "body_decorations",
        "non_body_decorations",
        "abilities",
        "extra_skills",
        "bad_skills",
        "charm",
        "torso_slots_spare",
        "torso_multiplier",
        "total_slots_spare",
        "slots_spare",
        "need",
        "defence",
        "max_defence",
        "rarity",
        "difficulty",
        "fire_res",
        "ice_res",
        "water_res",
        "thunder_res",
        "dragon_res",
    }
    incomplete = []
    for golden in goldens:
        for sample in golden.samples:
            complete = [
                stage for stage in sample["stages"] if stage["stage"] in {"initial", "final"}
            ]
            if any(set(stage) - {"stage"} != fields for stage in complete):
                incomplete.append(
                    f"{golden.name} worker {sample['worker']} {sample['combination']}"
                )
    return incomplete


def test_trace_initial_and_final_stages_are_complete(trace_goldens: list[TraceGolden]):
    assert _incomplete_snapshots(trace_goldens) == []


def test_personal_trace_initial_and_final_stages_are_complete(
    personal_trace_goldens: list[TraceGolden],
):
    assert _incomplete_snapshots(personal_trace_goldens) == []


def test_trace_point_scores_match_the_probe(
    trace_goldens: list[TraceGolden], solution_probes_golden: Any
):
    """point_score's neighbours are read again after each trace's searches: they mustn't move."""
    ranks = {golden.name: golden.header["point_score_rank"] for golden in trace_goldens}

    assert ranks == {name: solution_probes_golden["point_score_rank"] for name in ranks}
