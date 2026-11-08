"""Write the differential-fuzz corpus, ``tests/fuzz/fNNN.json``, from a seed.

Each query is one the GUI could have run (``QuerySpec`` + ``build_query``
accept it), in the corpus schema of ``tests/corpus/README.md``, with an
explicit ``my_charms`` list of generated charms: Auto-Guard reads the list
in every charm mode but none and my charms (``Form1.h:1274-1290``).

The generator draws a pool of candidates, measures each with the relevance
and charm ports (``formulate_query``, ``get_charms``), drops those over the
evaluation cap (armour combinations times workers), fills the quotas in pool
order, then tops up in pool order. The measurements only pick queries; the
harness defines their results. ``--check`` regenerates the corpus in memory
and fails if the committed files differ (a test runs this).

Only ``random.Random.random()`` is used: Python guarantees its sequence
across versions, but not that of ``choice``, ``sample`` or ``randrange``.

Usage:
    uv run python scripts/generate_fuzz_corpus.py [--seed 9] [--count 500] [--check]
"""

from __future__ import annotations

import argparse
import json
import math
import random
import sys
import tempfile
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path

from mhp3ass.armor import armor_available
from mhp3ass.charms.comparison import add_charm_to_optimal_list
from mhp3ass.charms.for_query import get_charms
from mhp3ass.charms.generation import CharmTables, generate_charm_tables
from mhp3ass.charms.my_charms import LineOutcome, load_my_charms, my_charms_text
from mhp3ass.charms.validity import (
    CharmValidity,
    build_charm_validity,
    decode_charm_hash,
    generated_charm,
)
from mhp3ass.data import GameData, apply_language, load_game_data
from mhp3ass.data.loaders import other_hunter_types_skill, read_skill_types
from mhp3ass.model import Ability, AbilityPair, ArmorType, Charm, Gender, HunterType
from mhp3ass.query import Query, QuerySpec, build_query, offered_skills
from mhp3ass.relevance import formulate_query


class Rng:
    """Seeded helpers built only on ``random()``, whose sequence Python keeps stable."""

    def __init__(self, seed: int):
        self._random = random.Random(seed)

    def random(self) -> float:
        value = self._random.random()
        return value

    def chance(self, probability: float) -> bool:
        hit = self.random() < probability
        return hit

    def randint(self, low: int, high: int) -> int:
        """Uniform in ``low..high`` inclusive."""
        value = low + int(self.random() * (high - low + 1))
        return value

    def choice[T](self, items: Sequence[T]) -> T:
        item = items[self.randint(0, len(items) - 1)]
        return item

    def weighted_index(self, weights: Sequence[float]) -> int:
        target = self.random() * sum(weights)
        running = 0.0
        for index, weight in enumerate(weights):
            running += weight
            if target < running:
                return index
        last = len(weights) - 1
        return last

    def shuffle[T](self, items: list[T]) -> None:
        """Fisher-Yates, in place."""
        for i in range(len(items) - 1, 0, -1):
            j = self.randint(0, i)
            items[i], items[j] = items[j], items[i]

    def sample[T](self, items: Sequence[T], count: int) -> list[T]:
        """``count`` distinct positions of ``items``, in draw order."""
        pool = list(items)
        picked = []
        for _ in range(min(count, len(pool))):
            index = self.randint(0, len(pool) - 1)
            picked.append(pool.pop(index))
        return picked


@dataclass
class Catalogue:
    """The game data and the lookups the samplers draw from."""

    game: GameData
    tables: CharmTables
    validity: CharmValidity
    languages: list[str]
    offered: list[int]
    # Skill index -> skills.txt type column (0 both, 1 Blademaster, 2 Gunner).
    skill_types: list[int]
    offered_by_ability: dict[Ability, list[int]]
    decoration_abilities: list[Ability]
    # Every generated hash, sorted, and those holding each ability (by static index).
    hashes: list[int]
    hashes_by_ability: dict[int, list[int]]
    auto_guard_hash: int


@dataclass
class Candidate:
    """One drawn query, before measurement."""

    number: int
    language: str
    hunter_type: HunterType
    gender: Gender
    hr: int
    elder_star: int
    weapon_slots: int
    allow_bad: bool
    include_piercings: bool
    allow_event: bool
    allow_low_rank: bool
    charm_mode: str
    sampler: str
    skills: list[int]
    my_charms: list[Charm]
    illegal_charms: int


@dataclass
class Measured:
    candidate: Candidate
    evaluations: int
    workers: int
    features: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class Quota:
    feature: str
    minimum: int


def language_folders(languages_dir: Path) -> list[str]:
    """Language folders in the GUI's menu order (NTFS order: case-insensitive names)."""
    folders = sorted(
        (path.name for path in languages_dir.iterdir() if path.is_dir()), key=str.upper
    )
    return folders


def build_catalogue(data_dir: Path) -> Catalogue:
    game = load_game_data(data_dir)
    apply_language(game, data_dir / "Languages" / "English (TeamHGG)")
    tables = generate_charm_tables(game)
    validity = build_charm_validity(tables, ability_count=len(game.abilities))
    skill_types = read_skill_types(data_dir / "skills.txt")
    if len(skill_types) != len(game.skills):
        raise ValueError(f"{len(skill_types)} skill types for {len(game.skills)} skills")
    offered = offered_skills(game)
    offered_by_ability: dict[Ability, list[int]] = {}
    for index in offered:
        offered_by_ability.setdefault(game.skills[index].ability, []).append(index)
    decoration_abilities: list[Ability] = []
    for decoration in game.decorations:
        ability = decoration.abilities[0].ability
        if ability in offered_by_ability and ability not in decoration_abilities:
            decoration_abilities.append(ability)
    hashes_by_ability: dict[int, list[int]] = {}
    for hashed in tables.charm_hashes:
        decoded = decode_charm_hash(hashed)
        hashes_by_ability.setdefault(decoded.ability1_index, []).append(hashed)
        if decoded.ability2_index != decoded.ability1_index:
            hashes_by_ability.setdefault(decoded.ability2_index, []).append(hashed)
    auto_guard = next(ability for ability in game.abilities if ability.auto_guard)
    auto_guard_hashes = hashes_by_ability[auto_guard.static_index]
    if len(auto_guard_hashes) != 1:
        raise ValueError(f"expected one Auto-Guard charm, found {len(auto_guard_hashes)}")
    catalogue = Catalogue(
        game=game,
        tables=tables,
        validity=validity,
        languages=language_folders(data_dir / "Languages"),
        offered=offered,
        skill_types=skill_types,
        offered_by_ability=offered_by_ability,
        decoration_abilities=decoration_abilities,
        hashes=tables.charm_hashes,
        hashes_by_ability=hashes_by_ability,
        auto_guard_hash=auto_guard_hashes[0],
    )
    return catalogue


def uniform_skills(
    rng: Rng, catalogue: Catalogue, hunter_type: HunterType, count: int, cross_weight: float = 0.3
) -> list[int]:
    """Distinct-ability skills from every offered one; cross-type skills weigh less."""
    skills: list[int] = []
    chosen: list[Ability] = []
    for _ in range(count):
        available = [
            index
            for index in catalogue.offered
            if catalogue.game.skills[index].ability not in chosen
        ]
        weights = [
            cross_weight
            if other_hunter_types_skill(catalogue.skill_types[index], hunter_type)
            else 1.0
            for index in available
        ]
        index = available[rng.weighted_index(weights)]
        skills.append(index)
        chosen.append(catalogue.game.skills[index].ability)
    return skills


def armour_seeded_skills(
    rng: Rng, catalogue: Catalogue, settings: Query, count: int, torso_up_weight: float = 3.0
) -> list[int]:
    """One offered skill per positive ability of a random piece available to ``settings``
    (hunter type, gender, rank and the armour toggles), topped up from decoration
    abilities, in random order."""
    pieces = [
        armor
        for armor_type in ArmorType
        for armor in catalogue.game.armors[armor_type]
        if armor_available(armor, settings)
    ]
    # With no piece available (low rank off at a low HR), every skill comes from decorations.
    abilities: list[Ability] = []
    if pieces:
        weights = [torso_up_weight if armor.torso_inc else 1.0 for armor in pieces]
        seed_piece = pieces[rng.weighted_index(weights)]
        abilities = [
            pair.ability
            for pair in seed_piece.abilities
            if pair.amount > 0 and pair.ability in catalogue.offered_by_ability
        ]
    rng.shuffle(abilities)
    abilities = abilities[:count]
    top_up = [ability for ability in catalogue.decoration_abilities if ability not in abilities]
    while len(abilities) < count and top_up:
        abilities.append(top_up.pop(rng.randint(0, len(top_up) - 1)))
    skills = [rng.choice(catalogue.offered_by_ability[ability]) for ability in abilities]
    rng.shuffle(skills)
    return skills


def illegal_charm(rng: Rng, catalogue: Catalogue) -> Charm:
    """A generated charm's first skill at 14 or 15 points, more than any charm holds
    (charm generation stays below 14)."""
    template = generated_charm(rng.choice(catalogue.hashes), catalogue.game)
    first = template.abilities[0]
    charm = Charm(
        num_slots=template.num_slots,
        abilities=[AbilityPair(ability=first.ability, amount=rng.randint(14, 15))],
    )
    if catalogue.validity.exists(charm) or not catalogue.validity.is_illegal(charm):
        raise ValueError(f"{charm} was meant to be illegal")
    return charm


def draw_my_charms(
    rng: Rng, catalogue: Catalogue, skills: list[int], with_illegal: bool
) -> list[Charm]:
    """Generated charms holding a query ability, plus noise, weakened copies, duplicates,
    slot-only charms, the Auto-Guard charm for half the Auto-Guard queries, and
    optionally a few illegal ones; shuffled. At most 40 lines."""
    game = catalogue.game
    relevant_hashes = list(
        dict.fromkeys(
            hashed
            for index in skills
            for hashed in catalogue.hashes_by_ability.get(
                game.skills[index].ability.static_index, []
            )
        )
    )
    picked = rng.sample(relevant_hashes, rng.randint(0, 12))
    picked += rng.sample(catalogue.hashes, rng.randint(0, 20))
    charms = [generated_charm(hashed, game) for hashed in picked]
    for charm in charms:
        first = charm.abilities[0]
        if first.amount > 1 and rng.chance(0.2):
            first.amount = rng.randint(1, first.amount - 1)
    if rng.chance(0.2):
        charms += [Charm(num_slots=rng.randint(1, 3)) for _ in range(rng.randint(1, 2))]
    if charms and rng.chance(0.2):
        charms += [rng.choice(charms).copy() for _ in range(rng.randint(1, 2))]
    has_auto_guard = any(game.skills[index].ability.auto_guard for index in skills)
    if has_auto_guard and rng.chance(0.5):
        charms.append(generated_charm(catalogue.auto_guard_hash, game))
    if with_illegal:
        charms += [illegal_charm(rng, catalogue) for _ in range(rng.randint(1, 3))]
    rng.shuffle(charms)
    return charms


def draw_candidate(
    rng: Rng, catalogue: Catalogue, number: int, illegal_chance: float = 0.01
) -> Candidate:
    english = "English (TeamHGG)"
    others = [language for language in catalogue.languages if language != english]
    language = english if rng.chance(0.85) else rng.choice(others)
    hunter_type = rng.choice([HunterType.BLADEMASTER, HunterType.GUNNER])
    gender = rng.choice([Gender.MALE, Gender.FEMALE])
    hr = rng.randint(1, 6)
    elder_star = rng.randint(1, 6)
    weapon_slots = rng.randint(0, 3)
    allow_bad = rng.chance(0.3)
    include_piercings = rng.chance(0.8)
    allow_event = rng.chance(0.8)
    allow_low_rank = rng.chance(0.8)
    charm_mode = rng.choice(["none", "my_charms", "slotted", "one_skill", "two_skill"])
    skill_count = rng.randint(1, 6)
    if rng.chance(0.5):
        sampler = "uniform"
        skills = uniform_skills(rng, catalogue, hunter_type=hunter_type, count=skill_count)
    else:
        sampler = "armour-seeded"
        settings = Query(
            skills=[],
            hunter_type=hunter_type,
            gender=gender,
            hr=hr,
            elder_star=elder_star,
            weapon_slots_allowed=weapon_slots,
            include_piercings=include_piercings,
            allow_bad=allow_bad,
            allow_event=allow_event,
            allow_low_rank=allow_low_rank,
        )
        skills = armour_seeded_skills(rng, catalogue, settings=settings, count=skill_count)
    with_illegal = rng.chance(illegal_chance)
    my_charms = draw_my_charms(rng, catalogue, skills=skills, with_illegal=with_illegal)
    illegal_charms = sum(
        not catalogue.validity.exists(charm) and catalogue.validity.is_illegal(charm)
        for charm in my_charms
    )
    candidate = Candidate(
        number=number,
        language=language,
        hunter_type=hunter_type,
        gender=gender,
        hr=hr,
        elder_star=elder_star,
        weapon_slots=weapon_slots,
        allow_bad=allow_bad,
        include_piercings=include_piercings,
        allow_event=allow_event,
        allow_low_rank=allow_low_rank,
        charm_mode=charm_mode,
        sampler=sampler,
        skills=skills,
        my_charms=my_charms,
        illegal_charms=illegal_charms,
    )
    return candidate


def query_json(candidate: Candidate, game: GameData, query_id: str, description: str) -> dict:
    """The corpus file's contents; names come from ``game``'s current language."""
    charm_lines = my_charms_text(candidate.my_charms).splitlines()[1:]
    contents = {
        "id": query_id,
        "description": description,
        "language": candidate.language,
        "hunter_type": candidate.hunter_type.name.lower(),
        "gender": candidate.gender.name.lower(),
        "hr": candidate.hr,
        "elder_star": candidate.elder_star,
        "weapon_slots": candidate.weapon_slots,
        "allow_bad": candidate.allow_bad,
        "include_piercings": candidate.include_piercings,
        "allow_event": candidate.allow_event,
        "allow_low_rank": candidate.allow_low_rank,
        "charm_mode": candidate.charm_mode,
        "skills": candidate.skills,
        "skill_names": [game.skills[index].name for index in candidate.skills],
        "my_charms": charm_lines,
    }
    return contents


def legal_charms(candidate: Candidate, catalogue: Catalogue) -> list[Charm]:
    """The charms ``LoadCustom`` keeps: known hashes, or not ``CharmIsIllegal``."""
    legal = [
        charm
        for charm in candidate.my_charms
        if catalogue.validity.exists(charm) or not catalogue.validity.is_illegal(charm)
    ]
    return legal


def has_auto_guard_charm(charms: list[Charm]) -> bool:
    """A charm the Auto-Guard worker would take: Auto-Guard as its only ability."""
    found = any(
        len(charm.abilities) == 1 and charm.abilities[0].ability.auto_guard for charm in charms
    )
    return found


def worker_count(candidate: Candidate, query: Query, catalogue: Catalogue) -> int:
    """How many workers ``StartSearch`` starts (harness ``WorkerCharms``, Form1.h:1273-1373)."""
    legal = legal_charms(candidate, catalogue)
    mode = candidate.charm_mode
    if mode not in ("none", "my_charms") and any(
        ability.auto_guard for ability in query.rel_abilities
    ):
        workers = 1 if has_auto_guard_charm(legal) else 0
        return workers
    if mode in ("none", "slotted"):
        return 1
    if mode == "my_charms":
        optimal: list[Charm] = []
        for charm in legal:
            add_charm_to_optimal_list(optimal, charm)
        workers = 1 + len(optimal)
        return workers
    charms = get_charms(query, catalogue.tables, use_two_skill_charms=mode == "two_skill")
    workers = len(charms)
    return workers


def candidate_features(candidate: Candidate, catalogue: Catalogue) -> list[str]:
    """Quota features known without running the relevance port."""
    skills = [catalogue.game.skills[index] for index in candidate.skills]
    auto_guard = any(skill.ability.auto_guard for skill in skills)
    auto_guard_charm = has_auto_guard_charm(legal_charms(candidate, catalogue))
    # StartSearch takes the Auto-Guard path only in these modes (Form1.h:1274).
    auto_guard_worker = auto_guard and candidate.charm_mode in ("slotted", "one_skill", "two_skill")
    flags = {
        "auto_guard_charm": auto_guard_worker and auto_guard_charm,
        "auto_guard_no_charm": auto_guard_worker and not auto_guard_charm,
        "cross_type": any(
            other_hunter_types_skill(catalogue.skill_types[index], candidate.hunter_type)
            for index in candidate.skills
        ),
        "two_skill_hr_below_5": candidate.charm_mode == "two_skill" and candidate.hr < 5,
        "one_skill_hr_3_or_less": candidate.charm_mode == "one_skill" and candidate.hr <= 3,
        "illegal_charm_lines": candidate.illegal_charms > 0,
    }
    features = [name for name, present in flags.items() if present]
    return features


def measure(candidate: Candidate, catalogue: Catalogue) -> Measured:
    """Evaluations and quota features, from the relevance and charm ports (English names)."""
    game = catalogue.game
    spec = QuerySpec.from_json(query_json(candidate, game, query_id="pool", description=""))
    query = formulate_query(game, spec)
    sizes = [len(pieces) for pieces in query.rel_armor]
    combinations = math.prod(max(size, 1) for size in sizes)
    workers = worker_count(candidate, query, catalogue)
    features = candidate_features(candidate, catalogue)
    if any(armor.torso_inc for pieces in query.rel_armor for armor in pieces):
        features.append("torso_up")
    if 0 in sizes:
        features.append("empty_slot")
    measured = Measured(
        candidate=candidate,
        evaluations=combinations * workers,
        workers=workers,
        features=features,
    )
    return measured


class Pool:
    """The drawn candidates, measured on first use: selection stops long before the end."""

    def __init__(self, candidates: list[Candidate], catalogue: Catalogue):
        self.candidates = candidates
        self.catalogue = catalogue
        self._measured: dict[int, Measured] = {}
        self._cheap: dict[int, list[str]] = {}

    def cheap_features(self, number: int) -> list[str]:
        """``candidate_features``, computed once per candidate."""
        if number not in self._cheap:
            self._cheap[number] = candidate_features(self.candidates[number], self.catalogue)
        return self._cheap[number]

    def measured(self, number: int) -> Measured:
        if number not in self._measured:
            self._measured[number] = measure(self.candidates[number], self.catalogue)
        return self._measured[number]


def select(pool: Pool, count: int, max_evaluations: int) -> list[Measured]:
    """Fill each quota in pool order, then top up in pool order, skipping candidates over
    the evaluation cap.

    Candidates with illegal charm lines are taken only by their own quota, so
    the corpus holds exactly that many.
    """
    quotas = [
        Quota("auto_guard_charm", 13),
        Quota("auto_guard_no_charm", 12),
        Quota("torso_up", 50),
        Quota("empty_slot", 25),
        Quota("cross_type", 25),
        Quota("two_skill_hr_below_5", 50),
        Quota("one_skill_hr_3_or_less", 25),
        Quota("illegal_charm_lines", 10),
    ]
    quota_total = sum(quota.minimum for quota in quotas)
    if count < quota_total:
        raise ValueError(f"--count {count} is below the {quota_total} queries the quotas need")
    measured_only = {"torso_up", "empty_slot"}
    selected: list[Measured] = []
    taken: set[int] = set()
    for quota in quotas:
        have = sum(quota.feature in measured.features for measured in selected)
        for candidate in pool.candidates:
            if have >= quota.minimum:
                break
            if candidate.number in taken:
                continue
            cheap = pool.cheap_features(candidate.number)
            if "illegal_charm_lines" in cheap and quota.feature != "illegal_charm_lines":
                continue
            if quota.feature not in measured_only and quota.feature not in cheap:
                continue
            measured = pool.measured(candidate.number)
            if quota.feature in measured.features and measured.evaluations <= max_evaluations:
                selected.append(measured)
                taken.add(candidate.number)
                have += 1
        if have < quota.minimum:
            raise ValueError(f"pool too small for quota {quota}: {have}")
    for candidate in pool.candidates:
        if len(selected) >= count:
            break
        if candidate.number in taken or candidate.illegal_charms > 0:
            continue
        measured = pool.measured(candidate.number)
        if measured.evaluations <= max_evaluations:
            selected.append(measured)
            taken.add(candidate.number)
    if len(selected) < count:
        raise ValueError(f"pool gave {len(selected)} queries, not {count}")
    selected.sort(key=lambda measured: measured.candidate.number)
    return selected


def description(measured: Measured) -> str:
    candidate = measured.candidate
    skills = "skill" if len(candidate.skills) == 1 else "skills"
    parts = [
        f"{candidate.sampler} sampler, charm mode {candidate.charm_mode}, "
        f"{len(candidate.skills)} {skills}"
    ]
    if measured.features:
        parts.append("quotas: " + ", ".join(measured.features))
    text = "; ".join(parts)
    return text


def check_query(contents: dict, measured: Measured, game: GameData, validity: CharmValidity):
    """The GUI could run it, and ``LoadCustom`` rejects exactly the illegal charm lines."""
    build_query(game, QuerySpec.from_json(contents))
    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder) / "mycharms.txt"
        path.write_text("\n".join(contents["my_charms"]) + "\n", encoding="utf-8")
        loaded = load_my_charms(path, game, validity)
    outcomes = [line.outcome for line in loaded.lines]
    rejected = outcomes.count(LineOutcome.REJECTED)
    accepted = outcomes.count(LineOutcome.ACCEPTED)
    expected_rejected = measured.candidate.illegal_charms
    if [accepted + rejected, rejected] != [len(outcomes), expected_rejected]:
        raise ValueError(f"{contents['id']}: my-charms outcomes {outcomes}")


def render(selected: list[Measured], catalogue: Catalogue, data_dir: Path) -> dict[str, str]:
    """File name -> contents, applying each language once (names change with it)."""
    files: dict[str, str] = {}
    ids = {
        measured.candidate.number: f"f{position:03d}"
        for position, measured in enumerate(selected, start=1)
    }
    for language in catalogue.languages:
        in_language = [measured for measured in selected if measured.candidate.language == language]
        if not in_language:
            continue
        apply_language(catalogue.game, data_dir / "Languages" / language)
        for measured in in_language:
            query_id = ids[measured.candidate.number]
            contents = query_json(
                measured.candidate,
                catalogue.game,
                query_id=query_id,
                description=description(measured),
            )
            check_query(contents, measured, game=catalogue.game, validity=catalogue.validity)
            text = json.dumps(contents, indent=2, ensure_ascii=False) + "\n"
            files[f"{query_id}.json"] = text
    apply_language(catalogue.game, data_dir / "Languages" / "English (TeamHGG)")
    ordered = dict(sorted(files.items()))
    return ordered


def summary(selected: list[Measured]) -> str:
    def counts(values: list[str]) -> str:
        tally = {value: values.count(value) for value in sorted(set(values))}
        text = ", ".join(f"{key} {value}" for key, value in tally.items())
        return text

    lines = [
        f"queries: {len(selected)}",
        "charm modes: " + counts([measured.candidate.charm_mode for measured in selected]),
        "skill counts: " + counts([str(len(measured.candidate.skills)) for measured in selected]),
        "samplers: " + counts([measured.candidate.sampler for measured in selected]),
        "languages: " + counts([measured.candidate.language for measured in selected]),
        "features: " + counts([feature for measured in selected for feature in measured.features]),
        "zero workers: " + str(sum(measured.workers == 0 for measured in selected)),
        "evaluations: "
        + f"total {sum(measured.evaluations for measured in selected)}, "
        + f"max {max(measured.evaluations for measured in selected)}",
    ]
    text = "\n".join(lines)
    return text


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--seed", type=int, default=9)
    parser.add_argument("--count", type=int, default=500)
    parser.add_argument("--pool", type=int, default=5000, help="candidates drawn before selection")
    parser.add_argument(
        "--max-evaluations", type=int, default=2_000_000, help="armour combinations times workers"
    )
    parser.add_argument("--out", type=Path, default=None, help="default: tests/fuzz")
    parser.add_argument("--check", action="store_true", help="fail if the committed files differ")
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parent.parent
    out = args.out if args.out is not None else repo_root / "tests" / "fuzz"
    data_dir = repo_root / "legacy" / "Run" / "Data"
    catalogue = build_catalogue(data_dir)
    rng = Rng(args.seed)
    candidates = [draw_candidate(rng, catalogue, number) for number in range(args.pool)]
    pool = Pool(candidates, catalogue)
    selected = select(pool, count=args.count, max_evaluations=args.max_evaluations)
    files = render(selected, catalogue, data_dir=data_dir)

    if args.check:
        committed = {path.name: path.read_text(encoding="utf-8") for path in out.glob("f*.json")}
        if committed != files:
            differing = sorted(
                name
                for name in set(committed) | set(files)
                if committed.get(name) != files.get(name)
            )
            raise SystemExit(f"{len(differing)} fuzz queries differ, e.g. {differing[:5]}")
        print(f"{len(files)} fuzz queries match seed {args.seed}")
        return
    out.mkdir(parents=True, exist_ok=True)
    for stale in out.glob("f*.json"):
        stale.unlink()
    for name, text in files.items():
        (out / name).write_text(text, encoding="utf-8")
    print(summary(selected), file=sys.stderr)
    print(f"wrote {len(files)} queries to {out}")


if __name__ == "__main__":
    main()
