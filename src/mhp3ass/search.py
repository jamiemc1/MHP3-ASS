"""One search worker: every armour combination of a query with one charm template.

Ported from ``Form1::backgroundWorker1_DoWork`` (``legacy/Form1.h:1852-1930``),
without its progress reporting and cancellation. Starting the workers,
removing duplicates and the CLI arrive with the rest of the search.
"""

from __future__ import annotations

from mhp3ass.data import GameData
from mhp3ass.model import Armor, Charm
from mhp3ass.query import Query
from mhp3ass.solution import matches_query
from mhp3ass.solution.state import Solution


def armor_choices(query: Query) -> list[list[Armor | None]]:
    """Each slot's relevant armour, with one ``None`` for an empty slot.

    ``DoWork`` adds that ``nullptr`` to the query's own lists (Form1.h:1865-1869),
    so every later worker and reader sees it. Here the lists are copied: the
    workers that follow pad the same way, so the combinations are the same.
    """
    choices: list[list[Armor | None]] = [list(slot) or [None] for slot in query.rel_armor]
    return choices


def run_worker(query: Query, charm_template: Charm | None, game: GameData) -> list[Solution]:
    """``backgroundWorker1_DoWork`` (Form1.h:1852-1930): the solutions ``MatchesQuery``
    accepts, in loop order (head, then body, arms, waist, legs).

    Each combination gets its own copy of the charm template, as the original's
    ``gcnew Charm( qc->charm_template )`` does (deep: the pairs are copied too),
    so reducing one combination's charm never touches the template.
    """
    head, body, arms, waist, legs = armor_choices(query)
    solutions = []
    for head_piece in head:
        for body_piece in body:
            for arms_piece in arms:
                for waist_piece in waist:
                    for legs_piece in legs:
                        job = Solution(
                            armors=[head_piece, body_piece, arms_piece, waist_piece, legs_piece],
                            charm=charm_template.copy() if charm_template is not None else None,
                        )
                        if matches_query(job, query, game):
                            solutions.append(job)
    return solutions
