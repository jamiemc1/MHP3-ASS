"""The differential-fuzz corpus: reproducible from its seed, runnable, and covering its quotas."""

from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import pytest

from mhp3ass.charms.my_charms import LineOutcome, load_my_charms
from mhp3ass.charms.validity import CharmValidity
from mhp3ass.data.loaders import other_hunter_types_skill, read_skill_types
from mhp3ass.query import QuerySpec
from mhp3ass.relevance import formulate_query
from mhp3ass.search import SearchData


@dataclass(frozen=True)
class FuzzFacts:
    """What one fuzz query covers, worked out from its file."""

    query_id: str
    file_stem: str
    language: str
    charm_mode: str
    hr: int
    skill_count: int
    outcomes: tuple[LineOutcome, ...]
    auto_guard: bool
    auto_guard_charm: bool
    torso_up: bool
    empty_slot: bool
    cross_type: bool


@pytest.fixture(scope="module")
def fuzz_dir(repo_root: Path) -> Path:
    return repo_root / "tests" / "fuzz"


@pytest.fixture(scope="module")
def fuzz_facts(
    fuzz_dir: Path,
    search_data_by_language: dict[str, SearchData],
    validity: CharmValidity,
    legacy_data_dir: Path,
    tmp_path_factory: pytest.TempPathFactory,
) -> list[FuzzFacts]:
    """Builds every query as the GUI would and loads its my-charms lines as ``LoadCustom`` does.

    The search games are query-mutable: formulating a query rewrites all their
    relevance state. ``validity`` only reads abilities' static indices, so it
    serves every language.
    """
    skill_types = read_skill_types(legacy_data_dir / "skills.txt")
    charms_dir = tmp_path_factory.mktemp("fuzz-my-charms")
    facts = []
    for path in sorted(fuzz_dir.glob("f*.json")):
        contents = json.loads(path.read_text(encoding="utf-8"))
        game = search_data_by_language[contents["language"]].game
        spec = QuerySpec.from_json(contents)
        query = formulate_query(game, spec)
        charms_path = charms_dir / f"{path.stem}.txt"
        charms_path.write_text("\n".join(contents["my_charms"]) + "\n", encoding="utf-8")
        loaded = load_my_charms(charms_path, game, validity)
        sizes = [len(pieces) for pieces in query.rel_armor]
        facts.append(
            FuzzFacts(
                query_id=contents["id"],
                file_stem=path.stem,
                language=contents["language"],
                charm_mode=contents["charm_mode"],
                hr=spec.hr,
                skill_count=len(spec.skills),
                outcomes=tuple(line.outcome for line in loaded.lines),
                auto_guard=any(skill.ability.auto_guard for skill in query.skills),
                auto_guard_charm=any(
                    len(charm.abilities) == 1 and charm.abilities[0].ability.auto_guard
                    for charm in loaded.charms
                ),
                torso_up=any(armor.torso_inc for pieces in query.rel_armor for armor in pieces),
                empty_slot=0 in sizes,
                cross_type=any(
                    other_hunter_types_skill(skill_types[index], spec.hunter_type)
                    for index in spec.skills
                ),
            )
        )
    return facts


def test_corpus_matches_its_seed(repo_root):
    script = repo_root / "scripts" / "generate_fuzz_corpus.py"
    result = subprocess.run(
        [sys.executable, str(script), "--check"], capture_output=True, text=True, check=False
    )

    assert [result.returncode, result.stderr] == [0, ""]


def test_queries_are_numbered_f001_to_f500(fuzz_facts):
    ids = [facts.query_id for facts in fuzz_facts]
    stems = [facts.file_stem for facts in fuzz_facts]

    assert [ids, stems] == [[f"f{number:03d}" for number in range(1, 501)]] * 2


def test_my_charms_lines_load_and_only_ten_queries_have_illegal_ones(fuzz_facts):
    # Building every query in fuzz_facts already checked the GUI could run it.
    other_outcomes = [
        facts.query_id
        for facts in fuzz_facts
        if set(facts.outcomes) - {LineOutcome.ACCEPTED, LineOutcome.REJECTED}
    ]
    with_rejections = [
        facts.query_id for facts in fuzz_facts if LineOutcome.REJECTED in facts.outcomes
    ]

    assert [other_outcomes, len(with_rejections)] == [[], 10]


def test_quotas_are_met(fuzz_facts):
    def count(predicate) -> int:
        matching = sum(1 for facts in fuzz_facts if predicate(facts))
        return matching

    def auto_guard_worker(facts: FuzzFacts) -> bool:
        # StartSearch's Auto-Guard path runs only in these modes (Form1.h:1274).
        reached = facts.auto_guard and facts.charm_mode in ("slotted", "one_skill", "two_skill")
        return reached

    minimums = {
        "auto_guard_with_charm": (count(lambda f: auto_guard_worker(f) and f.auto_guard_charm), 13),
        "auto_guard_without_charm": (
            count(lambda f: auto_guard_worker(f) and not f.auto_guard_charm),
            12,
        ),
        "torso_up": (count(lambda f: f.torso_up), 50),
        "empty_slot": (count(lambda f: f.empty_slot), 25),
        "cross_type": (count(lambda f: f.cross_type), 25),
        "two_skill_below_hr_5": (count(lambda f: f.charm_mode == "two_skill" and f.hr < 5), 50),
        "one_skill_hr_3_or_less": (count(lambda f: f.charm_mode == "one_skill" and f.hr <= 3), 25),
        "not_english_teamhgg": (count(lambda f: f.language != "English (TeamHGG)"), 25),
    }
    for mode in ("none", "my_charms", "slotted", "one_skill", "two_skill"):
        minimums[f"mode_{mode}"] = (count(lambda f, mode=mode: f.charm_mode == mode), 75)
    short = {name: counts for name, counts in minimums.items() if counts[0] < counts[1]}
    skill_counts = sorted({facts.skill_count for facts in fuzz_facts})

    assert [short, skill_counts] == [{}, [1, 2, 3, 4, 5, 6]]
