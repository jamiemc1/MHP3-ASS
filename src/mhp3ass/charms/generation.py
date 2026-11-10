"""Every charm the game can produce, from its own random number generator.

Ported from ``Omaget``, ``RemoveDuplicates`` and
``CharmDatabase::GenerateCharmTable`` (``legacy/CharmDatabase.cpp:526-961``).
For each charm kind and each of the 12 charm tables, the simulator walks the
game's RNG cycle from the table's seed and records every charm it yields.

Charm types index the results as ``2 - omakbn``: 0 mystery, 1 shining,
2 timeworn. Where the original's ``Assert`` would fire (a no-op in its
Release build), this raises instead; on the shipped tables none fires.

``rnd`` and ``getSlot``'s threshold search are lookup tables, and the
per-charm steps run inline in one loop per table. The charm-database golden
pins the output, including every list's order.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass
from functools import cache

from mhp3ass.charms.naming import hash_function
from mhp3ass.charms.tables import SKILL_TABLES, SLOT_THRESHOLDS
from mhp3ass.data import GameData
from mhp3ass.model import Ability, AbilityPair, Charm


def f32(value: float) -> float:
    """Round to IEEE single precision, as a C++ ``float`` stores it."""
    rounded = struct.unpack("<f", struct.pack("<f", value))[0]
    return rounded


def rnd(n: int) -> int:
    """``Omaget::rnd`` (CharmDatabase.cpp:695-705); ``n`` is in 0..65535.

    Every intermediate is non-negative, so Python's floor division matches
    C++'s truncation.
    """
    if not 0 <= n < 65536:
        raise ValueError(f"rnd needs 0 <= n < 65536, got {n}")
    if n == 0:
        return 176
    x = n * 16 - n * 4 - n
    y = x * 16
    z = y * 11367737 // 4294967296
    m = y - ((y - z) // 2 + z) // 32768 * 65363
    next_n = m & 0xFFFF
    return next_n


@cache
def rnd_table() -> tuple[int, ...]:
    """``rnd(n)`` for every 16-bit ``n``, so the simulator indexes rather than computes."""
    table = tuple(rnd(n) for n in range(65536))
    return table


@cache
def rank_point(max1: int, point1: int, max2: int | None, point2: int) -> int:
    """``Omaget::getRankPoint`` (CharmDatabase.cpp:773-785) in single precision.

    ``max2`` is None when the second skill doesn't count (absent, no points,
    or the same ability as the first).
    """
    weight1 = f32(max1 / 10.0)
    points = f32(point1 / weight1)
    if max2 is not None:
        weight2 = f32(max2 / 10.0)
        points = f32(points + f32(point2 / weight2))
    rank = int(points)
    return rank


@cache
def slot_lookup(kind: int) -> tuple[tuple[int, ...], ...]:
    """``getSlot``'s threshold search (CharmDatabase.cpp:761-771) for every rank and roll.

    ``slot_lookup(kind)[rank][n % 100]`` is the slot count: the first
    threshold the roll doesn't exceed, or 0 if it exceeds them all.
    """
    lookup = tuple(
        tuple(
            next((index for index, limit in enumerate(thresholds) if roll <= limit), 0)
            for roll in range(100)
        )
        for thresholds in SLOT_THRESHOLDS[kind]
    )
    return lookup


@dataclass
class CharmTables:
    """``CharmDatabase``'s generated tables (CharmDatabase.h:18-27)."""

    # [charm type][slots]: highest points seen per ability, in first-seen order.
    max_points: list[list[dict[Ability, int]]]
    # Useful two-skill charms per ability pair. [a][b] and [b][a] are the same list.
    two_skill: dict[Ability, dict[Ability, list[Charm]]]
    # Every charm's hash, sorted, without duplicates.
    charm_hashes: list[int]
    # [table][charm type][slots]: hashes in the order the simulator found them.
    table_hashes: list[list[list[list[int]]]]


class _CharmSimulator:
    """``Omaget`` (CharmDatabase.cpp:526-879) for one charm kind."""

    def __init__(self, kind: int, game: GameData, tables: CharmTables):
        self.kind = kind
        self.game = game
        self.tables = tables
        # Omaget's constructor (CharmDatabase.cpp:535-551): FURU, HIKA, NAZO (no second skill).
        skill_tables_by_kind = {0: (0, 1), 1: (2, 3), 2: (4, None)}
        first_table, second_table = skill_tables_by_kind[kind]
        self.skill1 = SKILL_TABLES[first_table]
        self.skill2 = SKILL_TABLES[second_table] if second_table is not None else ()
        # isSkill2 (CharmDatabase.cpp:719-730): a second skill when rndChange(n) reaches this.
        second_skill_thresholds = {0: 25, 1: 35}
        self.second_skill_threshold = second_skill_thresholds.get(kind)

    def simulate_table(self, table_number: int, seed: int) -> None:
        """Every charm on one table's RNG cycle, in order.

        One pass of the loop is ``SimulateCharm`` (CharmDatabase.cpp:553-587)
        with its ``getPoint2MaxMin`` (:737-752), ``getSlot`` (:761-771) and
        ``UpdateTable`` (:854-878) steps. ``m % 100`` is ``rndChange``
        (:787-792), the last two decimal digits. The second ability enters the hash
        whenever it differs from the first, even with no points; the tables
        only take it with points.
        """
        step = rnd_table()
        slots_by_rank = slot_lookup(self.kind)
        skill1_rows = self.skill1
        skill2_rows = self.skill2
        skill1_count = len(skill1_rows)
        skill2_count = len(skill2_rows)
        threshold = self.second_skill_threshold
        ordered = self.game.ordered_abilities
        ability_count = len(self.game.abilities)
        best_by_slots = self.tables.max_points[2 - self.kind]
        hashes_by_slots = self.tables.table_hashes[table_number][2 - self.kind]
        all_hashes = self.tables.charm_hashes
        n = seed
        while True:
            m = step[n]
            ability1_index, _, max1 = skill1_rows[m % skill1_count]
            m = step[m]
            point1 = m % max1 + 1
            m = step[m]
            second_row = None
            point2 = -9999
            if threshold is not None and m % 100 >= threshold:
                m = step[m]
                rolled_row = skill2_rows[m % skill2_count]
                m = step[m]
                # getPoint2MaxMin: odd n gives 1..max, even min..0.
                minimum, maximum = (1, rolled_row[2]) if m & 1 else (rolled_row[1], 0)
                m = step[m]
                point2 = m % (maximum - minimum + 1) + minimum
                if rolled_row[0] != ability1_index:
                    second_row = rolled_row
            m = step[m]
            # getRankPoint counts the second skill only with points (CharmDatabase.cpp:778).
            counts_second = second_row is not None and point2 > 0
            rank = rank_point(
                max1=max1,
                point1=point1,
                max2=second_row[2] if second_row is not None and counts_second else None,
                point2=point2 if counts_second else 0,
            )
            slots = slots_by_rank[rank][m % 100]

            ability1 = ordered[ability1_index]
            ability2 = None
            best = best_by_slots[slots]
            _report_single(best=best, ability=ability1, points=point1)
            if second_row is not None:
                ability2 = ordered[second_row[0]]
                if point2 > 0:
                    _report_single(best=best, ability=ability2, points=point2)
                    self._report_pair(
                        ability1=ability1,
                        points1=point1,
                        ability2=ability2,
                        points2=point2,
                        slots=slots,
                    )
            charm_hash = hash_function(
                num_slots=slots,
                ability1=ability1,
                points1=point1,
                ability2=ability2,
                points2=point2,
                ability_count=ability_count,
            )
            all_hashes.append(charm_hash)
            hashes_by_slots[slots].append(charm_hash)

            n = step[n]
            if n == seed:
                break

    def _report_pair(
        self, ability1: Ability, points1: int, ability2: Ability, points2: int, slots: int
    ) -> None:
        """``ReportAbilityScore`` for two skills (CharmDatabase.cpp:810-852).

        Removes listed charms the new one beats; adds it unless a listed
        charm is at least as good. List order matters.
        """
        charms = self.tables.two_skill[ability1][ability2]
        if charms is not self.tables.two_skill[ability2][ability1]:
            raise ValueError(
                f"two-skill table not symmetrical for {ability1.name}, {ability2.name}"
            )
        index = 0
        while index < len(charms):
            charm = charms[index]
            listed = [pair.ability for pair in charm.abilities]
            if listed not in ([ability1, ability2], [ability2, ability1]):
                raise ValueError(f"listed charm doesn't match {ability1.name}, {ability2.name}")
            end1 = 1 if charm.abilities[0].ability is not ability1 else 0
            end2 = 1 - end1
            amount1 = charm.abilities[end1].amount
            amount2 = charm.abilities[end2].amount
            if slots > charm.num_slots:
                dominated = amount1 <= points1 and amount2 <= points2
            elif points1 > amount1:
                dominated = charm.num_slots <= slots and amount2 <= points2
            elif points2 > amount2:
                dominated = charm.num_slots <= slots and amount1 <= points1
            else:
                return
            if dominated:
                del charms[index]
            else:
                index += 1
        new_charm = Charm(
            num_slots=slots,
            abilities=[
                AbilityPair(ability=ability1, amount=points1),
                AbilityPair(ability=ability2, amount=points2),
            ],
        )
        charms.append(new_charm)


def _report_single(best: dict[Ability, int], ability: Ability, points: int) -> None:
    """``ReportAbilityScore`` for one skill (CharmDatabase.cpp:794-808): keep the max.

    ``best`` is the charm type's and slot count's entry in ``max_points``.
    """
    if points >= 14:
        raise ValueError(f"{points} points for {ability.name}: the original asserts < 14")
    current = best.get(ability)
    if current is None or points > current:
        best[ability] = points


def _empty_two_skill_table(abilities: list[Ability]) -> dict[Ability, dict[Ability, list[Charm]]]:
    """The ``table2`` set-up loop (CharmDatabase.cpp:905-924): one shared list per pair."""
    two_skill: dict[Ability, dict[Ability, list[Charm]]] = {}
    for i in range(1, len(abilities)):
        for j in range(i):
            ability_a = abilities[i]
            ability_b = abilities[j]
            two_skill.setdefault(ability_a, {})
            two_skill.setdefault(ability_b, {})
            if ability_b not in two_skill[ability_a]:
                shared: list[Charm] = []
                two_skill[ability_a][ability_b] = shared
                two_skill[ability_b][ability_a] = shared
    return two_skill


def generate_charm_tables(game: GameData) -> CharmTables:
    """``CharmDatabase::GenerateCharmTable`` (CharmDatabase.cpp:901-961)."""
    tables = CharmTables(
        max_points=[[{} for _ in range(4)] for _ in range(3)],
        two_skill=_empty_two_skill_table(game.abilities),
        charm_hashes=[],
        table_hashes=[[[[] for _ in range(4)] for _ in range(3)] for _ in range(12)],
    )
    table_seeds = [2, 5, 9, 26, 6, 4, 13, 18, 15, 1, 12, 3]
    for charm_type in range(3):
        simulator = _CharmSimulator(kind=2 - charm_type, game=game, tables=tables)
        for table_number, seed in enumerate(table_seeds):
            simulator.simulate_table(table_number=table_number, seed=seed)
    auto_guard = next((ability for ability in game.abilities if ability.auto_guard), None)
    if auto_guard is not None:
        auto_guard_hash = hash_function(
            num_slots=0,
            ability1=auto_guard,
            points1=10,
            ability2=None,
            points2=0,
            ability_count=len(game.abilities),
        )
        tables.charm_hashes.append(auto_guard_hash)
    # Sort() then RemoveDuplicates (CharmDatabase.cpp:881-899, :959-960).
    tables.charm_hashes = sorted(set(tables.charm_hashes))
    return tables
