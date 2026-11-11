"""``ResultsView``: the result lists behind the sort and charm filter
drop-downs (Form1.h:1723-1802, :1981-1996, :2102-2130, :2226-2253), on two
corpus searches and on synthetic lists."""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from goldens import SearchGolden
from mhp3ass.model import Ability, AbilityPair, Charm
from mhp3ass.query import SearchSpec
from mhp3ass.results.result_set import ResultSet, skill_indices
from mhp3ass.results.sorting import SortKey
from mhp3ass.results.view import CharmFilter, FilterKind, ResultsView, SolutionSelection
from mhp3ass.solution.state import Solution


@dataclass(frozen=True)
class CorpusSearch:
    """A corpus query's search: its result set, its kept solutions' lines,
    and the harness's golden for it."""

    results: ResultSet
    lines: list[str]
    golden: SearchGolden


@pytest.fixture(scope="module")
def corpus_searches(
    search_goldens, search_data_by_language, pooled_searches
) -> dict[str, CorpusSearch]:
    """1a (my charms, with a charm-free worker) and g13 (one-skill charms,
    whose harness candidates name every solution's charm), from the session's
    searches; views only read them."""
    searches = {}
    for golden in search_goldens:
        query_id = golden.manifest["id"]
        if query_id not in ("1a", "g13"):
            continue
        spec = SearchSpec.from_json(golden.query)
        data = search_data_by_language[spec.query.language]
        result = pooled_searches[query_id]
        searches[query_id] = CorpusSearch(
            results=result.results,
            lines=result.results.all_solutions.lines(skill_indices(data.game)),
            golden=golden,
        )
    return searches


@pytest.fixture
def my_charms_search(corpus_searches) -> CorpusSearch:
    return corpus_searches["1a"]


@pytest.fixture
def one_skill_search(corpus_searches) -> CorpusSearch:
    return corpus_searches["g13"]


def _has_charm(line: str) -> bool:
    """Whether a solution line ends in charm fields: they follow the armour,
    the four spare-slot counts, and the counted decorations and extra skills."""
    fields = [int(field) for field in line.split()]
    position = 9
    position += 1 + fields[position]
    position += 1 + fields[position]
    has_charm = position < len(fields)
    return has_charm


def test_a_search_shows_all_its_solutions_in_arrival_order(my_charms_search):
    view = ResultsView.from_search(my_charms_search.results)

    assert [view.charm_filter, view.sort_key] == [CharmFilter.every_solution(), SortKey.NONE]
    assert view.final.positions == list(range(len(view.all_solutions)))
    assert my_charms_search.lines == my_charms_search.golden.solution_lines


def _charm_free_positions(view: ResultsView) -> list[int]:
    """Where a search's charm-free solutions are in ``all_solutions``: the
    search files them as a selection of that list."""
    no_charm = view.no_charm_solutions
    assert isinstance(no_charm, SolutionSelection)
    assert no_charm.source is view.all_solutions
    return no_charm.positions


def test_the_charm_free_solutions_are_the_search_lines_without_a_charm(my_charms_search):
    lines = my_charms_search.lines
    expected = [line for line in my_charms_search.golden.solution_lines if not _has_charm(line)]
    view = ResultsView.from_search(my_charms_search.results)
    charm_free = _charm_free_positions(view)

    view.select_filter(CharmFilter.charm_free())

    assert view.final.source is view.all_solutions
    assert [[lines[position] for position in charm_free], view.final.positions] == [
        expected,
        charm_free,
    ]
    assert len(expected) == 7241


def test_each_charm_lists_its_solutions_in_arrival_order(one_skill_search):
    """g13's charms are reduced as they match: some lose every skill ("O--"
    is still a charm), and some are removed, which leaves those solutions
    charm-free (the harness names them "")."""
    lines = one_skill_search.lines
    name_by_line = {
        candidate.solution_line: candidate.charm_name
        for candidate in one_skill_search.golden.candidates or []
    }
    expected: dict[str, list[str]] = {}
    for line in one_skill_search.golden.solution_lines:
        expected.setdefault(name_by_line[line], []).append(line)
    charm_free = expected.pop("")
    view = ResultsView.from_search(one_skill_search.results)

    by_charm = {
        name: [lines[position] for position in positions]
        for name, positions in view.by_charm.items()
    }

    assert [list(by_charm), by_charm] == [list(expected), expected]
    assert [lines[position] for position in _charm_free_positions(view)] == charm_free
    assert "O--" in by_charm
    assert len(charm_free) > 0


def test_the_filter_offers_each_charm_once_ignoring_case(one_skill_search):
    view = ResultsView.from_search(one_skill_search.results)

    names = view.charm_filter_names()

    assert names == sorted(view.by_charm, key=str.casefold)
    assert len(names) > 1


def test_a_charm_filter_shows_that_charms_solutions(one_skill_search):
    view = ResultsView.from_search(one_skill_search.results)
    name = view.charm_filter_names()[0]

    view.select_filter(CharmFilter.charm(name))

    assert view.final.positions == view.by_charm[name]


@pytest.fixture
def alternating_fire_rising_defence():
    """Eight charm-free solutions: fire res 1, 0, 1, 0, ... and defence tied
    in pairs (0, 0, 1, 1, ...), so a fire sort's ties show the order it was given."""
    solutions = [
        Solution(armors=[None] * 5, charm=None, fire_res=1 - index % 2, defence=index // 2)
        for index in range(8)
    ]
    return solutions


@pytest.fixture
def alternating_view(alternating_fire_rising_defence) -> ResultsView:
    view = ResultsView.of_lists(
        all_solutions=alternating_fire_rising_defence, no_charm_solutions=[]
    )
    return view


def test_a_sort_change_sorts_from_the_order_shown(alternating_view):
    alternating_view.select_sort(SortKey.DEFENCE)

    alternating_view.select_sort(SortKey.FIRE_RES)

    assert alternating_view.final.positions == [6, 4, 2, 0, 7, 5, 3, 1]


def test_none_shows_the_arrival_order_again(alternating_view):
    alternating_view.select_sort(SortKey.DEFENCE)

    alternating_view.select_sort(SortKey.NONE)

    assert alternating_view.final.positions == list(range(8))


def test_a_filter_change_sorts_its_list_from_arrival_order(alternating_view):
    """Only the current key counts: the defence sort before it leaves no trace."""
    alternating_view.select_sort(SortKey.DEFENCE)
    alternating_view.select_sort(SortKey.FIRE_RES)

    alternating_view.select_filter(CharmFilter.every_solution())

    assert alternating_view.final.positions == [0, 2, 4, 6, 1, 3, 5, 7]


def test_selecting_the_shown_sort_again_changes_nothing(alternating_view):
    alternating_view.select_sort(SortKey.DEFENCE)
    alternating_view.select_sort(SortKey.FIRE_RES)

    alternating_view.select_sort(SortKey.FIRE_RES)

    assert alternating_view.final.positions == [6, 4, 2, 0, 7, 5, 3, 1]


def test_the_sort_carries_over_to_a_new_search(alternating_fire_rising_defence):
    view = ResultsView.of_lists(
        all_solutions=alternating_fire_rising_defence,
        no_charm_solutions=[],
        sort_key=SortKey.DEFENCE,
    )

    assert [view.charm_filter, view.final.positions] == [
        CharmFilter.every_solution(),
        [6, 7, 4, 5, 2, 3, 0, 1],
    ]


@pytest.fixture
def evasion() -> Ability:
    return Ability(name="evasion", static_index=2)


@pytest.fixture
def guard() -> Ability:
    return Ability(name="Guard", static_index=3)


@pytest.fixture
def mixed_view(make_armor, attack, guard, evasion) -> ResultsView:
    """Three charm-free solutions and four charmed ones under three +2 charms,
    the guard charm's arriving first; defence 1-7 tells them apart, and each
    wears its own armour so none is a duplicate."""

    def plus_two(ability: Ability) -> Charm:
        return Charm(num_slots=0, abilities=[AbilityPair(ability=ability, amount=2)])

    charms = [
        plus_two(guard),
        None,
        plus_two(attack),
        None,
        plus_two(evasion),
        plus_two(guard),
        None,
    ]
    defences = [5, 1, 3, 2, 4, 6, 7]
    solutions = [
        Solution(armors=[make_armor(index=index)] * 5, charm=charm, defence=defence)
        for index, (charm, defence) in enumerate(zip(charms, defences, strict=True))
    ]
    results = ResultSet()
    results.add_solutions(solutions)
    view = ResultsView.from_search(results)
    return view


def _defences(solutions) -> list[int]:
    defences = [solution.defence for solution in solutions]
    return defences


def test_the_lists_hold_what_add_solutions_filed(mixed_view):
    defences_by_charm = {
        name: _defences(mixed_view.all_solutions[position] for position in positions)
        for name, positions in mixed_view.by_charm.items()
    }

    assert _defences(mixed_view.no_charm_solutions) == [1, 2, 7]
    assert [list(defences_by_charm), defences_by_charm] == [
        ["+2 Guard ---", "+2 Attack ---", "+2 evasion ---"],
        {"+2 Guard ---": [5, 6], "+2 Attack ---": [3], "+2 evasion ---": [4]},
    ]


def test_charm_names_are_listed_ignoring_case(mixed_view):
    """Ordinal order would put "+2 Guard" before "+2 evasion"'s lower-case e."""
    assert mixed_view.charm_filter_names() == ["+2 Attack ---", "+2 evasion ---", "+2 Guard ---"]


def test_a_charm_name_with_no_solutions_shows_nothing(mixed_view):
    mixed_view.select_filter(CharmFilter.charm("+9 Nothing ---"))

    assert [len(mixed_view.final), mixed_view.charm_filter.kind] == [0, FilterKind.CHARM]


def test_a_sort_chosen_while_nothing_shows_applies_to_the_next_filter(mixed_view):
    mixed_view.select_filter(CharmFilter.charm("+9 Nothing ---"))

    mixed_view.select_sort(SortKey.DEFENCE)
    mixed_view.select_filter(CharmFilter.charm_free())

    assert [mixed_view.sort_key, _defences(mixed_view.final)] == [SortKey.DEFENCE, [7, 2, 1]]


def test_a_language_change_keeps_the_selected_charm_under_its_new_name(mixed_view, guard):
    mixed_view.select_filter(CharmFilter.charm("+2 Guard ---"))
    guard.name = "Garde"

    mixed_view.relanguage()

    assert [mixed_view.charm_filter, list(mixed_view.by_charm), _defences(mixed_view.final)] == [
        CharmFilter.charm("+2 Garde ---"),
        ["+2 Garde ---", "+2 Attack ---", "+2 evasion ---"],
        [5, 6],
    ]


def test_a_language_change_keeps_none_selected(mixed_view, guard):
    mixed_view.select_filter(CharmFilter.charm_free())
    guard.name = "Garde"

    mixed_view.relanguage()

    assert [mixed_view.charm_filter, _defences(mixed_view.final)] == [
        CharmFilter.charm_free(),
        [1, 2, 7],
    ]


def test_a_language_change_follows_the_selected_charm_into_a_shared_name(mixed_view, evasion):
    """Names rebuild by name, as the original's map does: a charm renamed onto
    another's name joins its list, and the selection follows it there."""
    mixed_view.select_filter(CharmFilter.charm("+2 evasion ---"))
    evasion.name = "Guard"

    mixed_view.relanguage()

    assert [mixed_view.charm_filter, list(mixed_view.by_charm), _defences(mixed_view.final)] == [
        CharmFilter.charm("+2 Guard ---"),
        ["+2 Guard ---", "+2 Attack ---"],
        [5, 4, 6],
    ]


def test_a_language_change_shows_all_for_a_name_with_no_solutions(mixed_view, guard):
    mixed_view.select_filter(CharmFilter.charm("+9 Nothing ---"))
    guard.name = "Garde"

    mixed_view.relanguage()

    assert [mixed_view.charm_filter, len(mixed_view.final)] == [CharmFilter.every_solution(), 7]


def test_a_selection_equals_the_solutions_it_holds(mixed_view):
    charm_free = mixed_view.no_charm_solutions

    assert charm_free == [mixed_view.all_solutions[position] for position in (1, 3, 6)]
    assert charm_free != [mixed_view.all_solutions[1]]


@pytest.mark.parametrize(
    ("kind", "name"),
    [(FilterKind.CHARM, None), (FilterKind.NONE, "+2 Guard ---"), (FilterKind.ALL, "")],
)
def test_only_a_charm_filter_names_a_charm(kind, name):
    with pytest.raises(ValueError, match="charm name"):
        CharmFilter(kind=kind, charm_name=name)
