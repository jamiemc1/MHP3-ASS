"""A search: which charm templates it searches, each worker's loop, and the run
that merges the workers' solutions.

Ported from ``Form1::StartSearch`` (``legacy/Form1.h:1251-1375``),
``Form1::backgroundWorker1_DoWork`` (``legacy/Form1.h:1852-1930``) and
``backgroundWorker1_RunWorkerCompleted`` (``legacy/Form1.h:1804-1836``),
without the threads, progress reporting and cancellation, in the order the
harness's ``SearchDump::Run`` (``harness/src/SearchDump.cpp``) runs them.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from mhp3ass.charms.comparison import add_charm_to_optimal_list
from mhp3ass.charms.for_query import get_charms
from mhp3ass.charms.generation import CharmTables, generate_charm_tables
from mhp3ass.charms.my_charms import load_query_my_charms, my_charms_illegal
from mhp3ass.charms.validity import CharmValidity, build_charm_validity
from mhp3ass.data import GameData, apply_language, load_game_data
from mhp3ass.decorations import NoDecorationsError
from mhp3ass.model import Armor, Charm
from mhp3ass.query import CharmMode, Query, SearchSpec
from mhp3ass.relevance import formulate_query
from mhp3ass.results.result_set import ResultSet, SearchException, SearchResult, WorkerResult
from mhp3ass.solution import matches_query
from mhp3ass.solution.charm_reduction import LegacyListIndexError
from mhp3ass.solution.fill import UndefinedScoreError
from mhp3ass.solution.state import LegacyNullReferenceError, Solution


@dataclass(frozen=True)
class SearchData:
    """What a search reads besides the query: the game in one language, its
    charm tables, and the charm checks my-charms loading needs."""

    game: GameData
    tables: CharmTables
    validity: CharmValidity

    @classmethod
    def load(cls, data_dir: Path, language: str) -> SearchData:
        """The data files, then the charm tables, then the language, in the
        GUI's start-up order (Form1.h:309-322)."""
        language_dir = data_dir / "Languages" / language
        if not language_dir.is_dir():
            raise FileNotFoundError(f"no language folder {language_dir}")
        game = load_game_data(data_dir)
        tables = generate_charm_tables(game)
        apply_language(game, language_dir)
        validity = build_charm_validity(tables, ability_count=len(game.abilities))
        search_data = cls(game=game, tables=tables, validity=validity)
        return search_data


def worker_charms(
    query: Query, charm_mode: CharmMode, my_charms: list[Charm], tables: CharmTables
) -> list[Charm | None]:
    """``StartSearch``'s charm templates, one per worker, in the order it starts them
    (``None`` is a charm-free worker).

    ``query`` must come from ``formulate_query`` on the game ``my_charms`` and
    ``tables`` belong to, with no other query formulated since: the my-charms
    comparisons read the abilities' ``relevant`` flags it sets.

    - No skills: no workers (the GUI does nothing, :1255)
    - Slotted, one- and two-skill modes with an Auto-Guard skill: only the
      first my-charm whose single ability is Auto-Guard, whatever its points
      or slots, or no workers without one (:1274-1291)
    - None: one charm-free worker
    - My charms: a charm-free worker, then the charms ``AddCharmToOptimalList``
      keeps, in list order (:1300-1313)
    - Slotted: a bare three-slot charm (:1314-1323)
    - One- and two-skill: ``GetCharms`` (:1324-1372)

    The my-charms templates are the given objects themselves; workers copy them.
    """
    if not query.skills:
        return []
    if charm_mode > CharmMode.MY_CHARMS:
        for ability in query.rel_abilities:
            if ability.auto_guard:
                auto_guard_charm = next(
                    (
                        charm
                        for charm in my_charms
                        if len(charm.abilities) == 1 and charm.abilities[0].ability is ability
                    ),
                    None,
                )
                auto_guard_workers: list[Charm | None] = (
                    [] if auto_guard_charm is None else [auto_guard_charm]
                )
                return auto_guard_workers
    workers: list[Charm | None]
    match charm_mode:
        case CharmMode.NONE:
            workers = [None]
        case CharmMode.MY_CHARMS:
            to_search: list[Charm] = []
            for charm in my_charms:
                add_charm_to_optimal_list(to_search, charm)
            workers = [None, *to_search]
        case CharmMode.SLOTTED:
            workers = [Charm(num_slots=3)]
        case CharmMode.ONE_SKILL | CharmMode.TWO_SKILL:
            charms = get_charms(
                query, tables=tables, use_two_skill_charms=charm_mode is CharmMode.TWO_SKILL
            )
            workers = list(charms)
    return workers


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


def dotnet_exception_type(error: Exception) -> str | None:
    """The .NET exception type a port exception stands for, or ``None`` for an
    error the original never raises (such as ``UndefinedScoreError``, a
    port-side check where the original reads past its score table)."""
    exception_type = None
    if isinstance(error, LegacyNullReferenceError):
        exception_type = "NullReferenceException"
    elif isinstance(error, LegacyListIndexError):
        exception_type = "ArgumentOutOfRangeException"
    elif isinstance(error, (NoDecorationsError, KeyError)):
        exception_type = "KeyNotFoundException"
    elif isinstance(error, IndexError) and not isinstance(error, UndefinedScoreError):
        exception_type = "IndexOutOfRangeException"
    return exception_type


def dotnet_message(exception_type: str) -> str:
    """.NET Framework 4.8's default message for ``exception_type`` (unverified
    against a harness golden: none records an exception yet)."""
    messages = {
        "NullReferenceException": "Object reference not set to an instance of an object.",
        "ArgumentOutOfRangeException": (
            "Index was out of range. Must be non-negative and less than the size of the "
            "collection.\r\nParameter name: index"
        ),
        "KeyNotFoundException": "The given key was not present in the dictionary.",
        "IndexOutOfRangeException": "Index was outside the bounds of the array.",
    }
    message = messages[exception_type]
    return message


def run_search(spec: SearchSpec, data: SearchData, record_exceptions: bool = False) -> SearchResult:
    """One search, as the harness's ``SearchDump::Run`` runs it: load the query's
    charm lines, formulate the query, start the workers in ``StartSearch``'s
    order, run each in turn and merge its solutions in that order.

    ``data`` must be in ``spec``'s language. A worker that throws stops the
    search: with ``record_exceptions`` the result records it and leaves out
    that worker and the ones after it (the GUI shows a message box and loses
    that worker's result, Form1.h:1804-1811); without, the error propagates.
    Errors in duplicate removal (quirk T) always propagate, as in the harness.
    """
    loaded = load_query_my_charms(spec.my_charms, game=data.game, validity=data.validity)
    query = formulate_query(data.game, spec.query)
    templates = worker_charms(
        query, charm_mode=spec.charm_mode, my_charms=loaded.charms, tables=data.tables
    )
    results = ResultSet()
    workers = []
    exception = None
    for number, template in enumerate(templates):
        try:
            found = run_worker(query, template, data.game)
        except (LegacyNullReferenceError, LookupError) as error:
            exception_type = dotnet_exception_type(error)
            if not record_exceptions or exception_type is None:
                raise
            exception = SearchException(
                worker=number, type=exception_type, message=dotnet_message(exception_type)
            )
            break
        added = results.add_solutions(found)
        workers.append(WorkerResult(template=template, found=found, added=added))
    search_result = SearchResult(
        query=query,
        my_charms_loaded=len(loaded.charms),
        my_charms_illegal=my_charms_illegal(loaded),
        worker_count=len(templates),
        workers=workers,
        results=results,
        exceptions_recorded=record_exceptions,
        exception=exception,
    )
    return search_result
