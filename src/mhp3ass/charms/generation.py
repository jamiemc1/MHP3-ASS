"""Every charm the game can produce, from its own random number generator.

Ported from ``Omaget``, ``RemoveDuplicates`` and
``CharmDatabase::GenerateCharmTable`` (``legacy/CharmDatabase.cpp:526-961``).
For each charm kind and each of the 12 charm tables, the simulator walks the
game's RNG cycle from the table's seed and records every charm it yields.

Charm types index the results as ``2 - omakbn``: 0 mystery, 1 shining,
2 timeworn.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass
from functools import cache

from mhp3ass.charms.naming import hash_function
from mhp3ass.charms.tables import SKILL_TABLES, SLOT_THRESHOLDS
from mhp3ass.data import GameData
from mhp3ass.model import Ability, AbilityPair, Charm

_SINGLE = struct.Struct("<f")


def f32(value: float) -> float:
    """Round to IEEE single precision, as a C++ ``float`` stores it."""
    rounded = _SINGLE.unpack(_SINGLE.pack(value))[0]
    return rounded


def rnd(n: int) -> int:
    """``Omaget::rnd`` (CharmDatabase.cpp:695-705); ``n`` is in 0..65535.

    Every intermediate is non-negative, so Python's floor division matches
    C++'s truncation.
    """
    if n == 0:
        return 176
    x = n * 16 - n * 4 - n
    y = x * 16
    z = y * 11367737 // 4294967296
    m = y - ((y - z) // 2 + z) // 32768 * 65363
    next_n = m & 0xFFFF
    return next_n


def rnd_change(n: int) -> int:
    """``Omaget::rndChange`` (CharmDatabase.cpp:787-792): the last two decimal digits."""
    digits = n - n // 100 * 100
    return digits


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


@dataclass(frozen=True)
class PointRange:
    minimum: int
    maximum: int


def _point2_range(n: int, skill_row: tuple[int, ...]) -> PointRange:
    """``getPoint2MaxMin`` (CharmDatabase.cpp:737-752): odd n gives 1..max, even min..0."""
    _, minimum, maximum = skill_row
    if n & 1:
        return PointRange(minimum=1, maximum=maximum)
    return PointRange(minimum=minimum, maximum=0)


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
        self.table_number = 0
        # Omaget's constructor (CharmDatabase.cpp:535-551): FURU, HIKA, NAZO (no second skill).
        skill_tables_by_kind = {0: (0, 1), 1: (2, 3), 2: (4, None)}
        first_table, second_table = skill_tables_by_kind[kind]
        self.skill1 = SKILL_TABLES[first_table]
        self.skill2 = SKILL_TABLES[second_table] if second_table is not None else None

    def simulate_charm(self, n: int) -> None:
        """``SimulateCharm`` (CharmDatabase.cpp:553-587)."""
        n = rnd(n)
        skill1 = n % len(self.skill1)
        n = rnd(n)
        point1 = n % self.skill1[skill1][2] + 1
        n = rnd(n)
        skill2 = -9999
        point2 = -9999
        if self._has_second_skill(n) and self.skill2 is not None:
            n = rnd(n)
            skill2 = n % len(self.skill2)
            n = rnd(n)
            point_range = _point2_range(n=n, skill_row=self.skill2[skill2])
            n = rnd(n)
            point2 = n % (point_range.maximum - point_range.minimum + 1) + point_range.minimum
        n = rnd(n)
        slots = self._slots(n=n, skill1=skill1, point1=point1, skill2=skill2, point2=point2)
        self._update_table(skill1=skill1, point1=point1, skill2=skill2, point2=point2, slots=slots)

    def _has_second_skill(self, n: int) -> bool:
        """``isSkill2`` (CharmDatabase.cpp:719-730)."""
        thresholds = {0: 25, 1: 35}
        threshold = thresholds.get(self.kind)
        has_second = threshold is not None and rnd_change(n) >= threshold
        return has_second

    def _slots(self, n: int, skill1: int, point1: int, skill2: int, point2: int) -> int:
        """``getSlot`` (CharmDatabase.cpp:761-771)."""
        roll = rnd_change(n)
        rank = rank_point(
            max1=self.skill1[skill1][2],
            point1=point1,
            max2=self._counted_second_max(skill1=skill1, skill2=skill2, point2=point2),
            point2=point2,
        )
        thresholds = SLOT_THRESHOLDS[self.kind][rank]
        slots = next((index for index, limit in enumerate(thresholds) if roll <= limit), 0)
        return slots

    def _counted_second_max(self, skill1: int, skill2: int, point2: int) -> int | None:
        """The second skill's max when ``getRankPoint`` counts it (CharmDatabase.cpp:778)."""
        if self.skill2 is None or skill2 < 0 or point2 <= 0:
            return None
        if self.skill1[skill1][0] == self.skill2[skill2][0]:
            return None
        second_max = self.skill2[skill2][2]
        return second_max

    def _update_table(self, skill1: int, point1: int, skill2: int, point2: int, slots: int) -> None:
        """``UpdateTable`` (CharmDatabase.cpp:854-878).

        The second ability enters the hash whenever it differs from the
        first, even with no points; the tables only take it with points.
        """
        ordered = self.game.ordered_abilities
        ability1 = ordered[self.skill1[skill1][0]]
        ability2 = None
        self._report_single(ability=ability1, points=point1, slots=slots)
        has_other_second = (
            self.skill2 is not None
            and skill2 >= 0
            and self.skill1[skill1][0] != self.skill2[skill2][0]
        )
        if self.skill2 is not None and has_other_second:
            ability2 = ordered[self.skill2[skill2][0]]
            if point2 > 0:
                self._report_single(ability=ability2, points=point2, slots=slots)
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
            ability_count=len(self.game.abilities),
        )
        self.tables.charm_hashes.append(charm_hash)
        self.tables.table_hashes[self.table_number][2 - self.kind][slots].append(charm_hash)

    def _report_single(self, ability: Ability, points: int, slots: int) -> None:
        """``ReportAbilityScore`` for one skill (CharmDatabase.cpp:794-808): keep the max."""
        best = self.tables.max_points[2 - self.kind][slots]
        if ability in best:
            best[ability] = max(best[ability], points)
        else:
            best[ability] = points

    def _report_pair(
        self, ability1: Ability, points1: int, ability2: Ability, points2: int, slots: int
    ) -> None:
        """``ReportAbilityScore`` for two skills (CharmDatabase.cpp:810-852).

        Removes listed charms the new one beats; adds it unless a listed
        charm is at least as good. List order matters.
        """
        charms = self.tables.two_skill[ability1][ability2]
        index = 0
        while index < len(charms):
            charm = charms[index]
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
            simulator.table_number = table_number
            n = seed
            while True:
                simulator.simulate_charm(n)
                n = rnd(n)
                if n == seed:
                    break
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
