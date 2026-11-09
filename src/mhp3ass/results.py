"""A search's result list and its duplicate removal.

Ported from ``Form1::HashArmor``, ``SolutionExists``, ``AddSolution( String^,
Solution^ )`` and ``AddSolutions`` (``legacy/Form1.h:1691-1746``), as the
harness's ``ResultSet`` (``harness/src/SearchDump.cpp``) collects them.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field

from mhp3ass.charms.naming import charm_name
from mhp3ass.model import Armor
from mhp3ass.solution.state import LegacyNullReferenceError, Solution


def hash_armor(armors: Sequence[Armor | None]) -> int:
    """``HashArmor`` (Form1.h:1691-1699): each slot's armour index shifted by
    three bits per slot, summed.

    The shifts overlap (indices go up to 225), so different armour sets can
    share a hash (quirk 4). The original shifts a 32-bit ``unsigned``, which
    would only overflow for an index of 2**20 or more. It dereferences every
    slot, so an empty one throws.
    """
    total = 0
    for slot, armor in enumerate(armors):
        if armor is None:
            raise LegacyNullReferenceError(f"HashArmor dereferences the empty slot {slot}")
        total += armor.index << (slot * 3)
    return total


@dataclass
class ResultSet:
    """``Form1``'s ``all_solutions`` and ``existing_armor`` for one search.

    Charmed solutions are kept once per (charm name, armour hash), the first
    one to arrive (quirk 5: which one depends on arrival order); charm-free
    solutions are always kept. ``existing_armor`` persists across calls, as
    the original only clears it when a new search starts (Form1.h:1257).
    """

    all_solutions: list[Solution] = field(default_factory=list)
    existing_armor: dict[str, set[int]] = field(default_factory=dict)

    def _solution_exists(self, name: str, solution: Solution) -> bool:
        """``SolutionExists`` (Form1.h:1701-1721): records the hash if it is new."""
        # The original adds the charm's entry before hashing, so it stays even
        # when HashArmor throws.
        hashes = self.existing_armor.setdefault(name, set())
        armor_hash = hash_armor(solution.armors)
        if armor_hash in hashes:
            return True
        hashes.add(armor_hash)
        return False

    def add_solution(self, name: str, solution: Solution) -> bool:
        """``AddSolution( String^, Solution^ )`` (Form1.h:1723-1730): keep
        ``solution`` under the charm name ``name`` unless the key is taken."""
        if self._solution_exists(name, solution):
            return False
        self.all_solutions.append(solution)
        return True

    def add_solutions(self, solutions: Iterable[Solution]) -> list[Solution]:
        """``AddSolutions`` (Form1.h:1732-1746): the solutions it kept, in order.

        The key is the charm's name after ``MatchesQuery`` reduced it, so
        different templates can meet on one name. A charm ``MatchesQuery``
        removed makes the solution charm-free.
        """
        added = []
        for solution in solutions:
            if solution.charm is None:
                self.all_solutions.append(solution)
                added.append(solution)
            elif self.add_solution(charm_name(solution.charm), solution):
                added.append(solution)
        return added
