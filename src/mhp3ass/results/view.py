"""The result lists behind the "Sort Results By" and charm filter drop-downs.

Ported from ``Form1``'s result lists (``legacy/Form1.h:110-113``),
``AddSolution( String^, Solution^ )`` and ``AddSolutions``'s filing
(``:1723-1746``), ``UpdateCharmComboBox`` (``:1748-1802``),
``cmbSort_SelectedIndexChanged`` (``:1981-1996``),
``cmbCharms_SelectedIndexChanged`` (``:2226-2253``) and the results part of
``LanguageSelect_Click`` (``:2102-2112``, ``:2124-2130``).

Which list holds which solutions is the original's, since ``settings.cfg``
and the filters are built from them: ``all_solutions`` in arrival order, the
charm-free ones, and each charm name's solutions. How they are shown is the
port's own: a sort is stable from the order on screen, None shows the
arrival order (quirk 27), and the charm names are listed in case-insensitive
alphabetical order rather than by the Windows culture's rules (quirk 42).
"""

from __future__ import annotations

import functools
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from enum import Enum
from typing import Any, overload

from mhp3ass.results.result_set import ResultSet, charm_names
from mhp3ass.results.sorting import SortKey, solution_comparison
from mhp3ass.solution.state import Solution


class SolutionSelection(Sequence[Solution]):
    """Some of ``source``'s solutions, by position, in the given order.

    Solutions are read from ``source`` only when asked for, so a
    ``SolutionList``'s records are rebuilt only when shown or sorted.
    """

    def __init__(self, source: Sequence[Solution], positions: Sequence[int]):
        self.source = source
        self.positions = list(positions)

    def __len__(self) -> int:
        return len(self.positions)

    @overload
    def __getitem__(self, index: int) -> Solution: ...

    @overload
    def __getitem__(self, index: slice) -> list[Solution]: ...

    def __getitem__(self, index: int | slice) -> Solution | list[Solution]:
        if isinstance(index, slice):
            solutions = [self.source[position] for position in self.positions[index]]
            return solutions
        solution = self.source[self.positions[index]]
        return solution

    def __iter__(self) -> Iterator[Solution]:
        for position in self.positions:
            yield self.source[position]

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Sequence) or isinstance(other, str):
            return NotImplemented
        same = list(self) == list(other)
        return same

    def __repr__(self) -> str:
        return f"SolutionSelection({self.positions!r})"


def sorted_positions(
    source: Sequence[Solution], positions: Sequence[int], key: SortKey
) -> list[int]:
    """``SortResults`` on ``source``'s solutions at ``positions``: stable, so
    ties keep the order of ``positions``; None leaves it alone. Each solution
    is read from ``source`` once."""
    comparison = solution_comparison(key)
    if comparison is None:
        return list(positions)
    solution_order = functools.cmp_to_key(comparison)

    def order_of(position: int) -> Any:
        order = solution_order(source[position])
        return order

    ordered = sorted(positions, key=order_of)
    return ordered


class FilterKind(Enum):
    """The three kinds of ``cmbCharms`` item."""

    NONE = "none"
    ALL = "all"
    CHARM = "charm"


@dataclass(frozen=True)
class CharmFilter:
    """A ``cmbCharms`` item: None (the charm-free solutions), All, or one
    charm's solutions by its name."""

    kind: FilterKind
    charm_name: str | None = None

    def __post_init__(self) -> None:
        if (self.kind is FilterKind.CHARM) != (self.charm_name is not None):
            raise ValueError(
                f"a {self.kind.value} filter can't have the charm name {self.charm_name!r}"
            )

    @classmethod
    def charm_free(cls) -> CharmFilter:
        return cls(kind=FilterKind.NONE)

    @classmethod
    def every_solution(cls) -> CharmFilter:
        return cls(kind=FilterKind.ALL)

    @classmethod
    def charm(cls, name: str) -> CharmFilter:
        return cls(kind=FilterKind.CHARM, charm_name=name)


def _positions_by_charm(names: Sequence[str]) -> dict[str, list[int]]:
    """``charm_solution_map`` as positions: each charm name (in the order the
    names first appear) and where its solutions are."""
    by_charm: dict[str, list[int]] = {}
    for position, name in enumerate(names):
        if name != "":
            by_charm.setdefault(name, []).append(position)
    return by_charm


@dataclass
class ResultsView:
    """``Form1``'s result lists and the two drop-downs' selections.

    ``all_solutions`` and ``no_charm_solutions`` are the lists
    ``settings.cfg`` and the filters are built from. ``by_charm`` holds each
    charm name's solutions as positions in ``all_solutions``, which always
    holds them (``AddSolution`` files a charmed solution in both).
    ``final`` is what the selections show (``final_solutions``): its
    positions are in ``all_solutions``, except under None when the
    charm-free list is a separate one (a load files charm-free lines
    outside ``all_solutions``).

    The view takes the lists as they are when it is built: after solutions
    are added to them, build a new view.
    """

    all_solutions: Sequence[Solution]
    no_charm_solutions: Sequence[Solution]
    by_charm: dict[str, list[int]]
    sort_key: SortKey
    charm_filter: CharmFilter
    final: SolutionSelection

    @classmethod
    def _showing_all(
        cls,
        all_solutions: Sequence[Solution],
        no_charm_solutions: Sequence[Solution],
        names: Sequence[str],
        sort_key: SortKey,
    ) -> ResultsView:
        """The lists with ``all_solutions``' charm ``names``, showing All."""
        view = cls(
            all_solutions=all_solutions,
            no_charm_solutions=no_charm_solutions,
            by_charm=_positions_by_charm(names),
            sort_key=sort_key,
            charm_filter=CharmFilter.every_solution(),
            final=SolutionSelection(all_solutions, []),
        )
        view.show_filter()
        return view

    @classmethod
    def of_lists(
        cls,
        all_solutions: Sequence[Solution],
        no_charm_solutions: Sequence[Solution],
        sort_key: SortKey = SortKey.NONE,
    ) -> ResultsView:
        """The lists once filled, showing All sorted by ``sort_key``, as
        ``UpdateCharmComboBox( 1 )`` does at the end of a search or a load
        (Form1.h:1831, :455). The sort selection carries over between searches."""
        view = cls._showing_all(
            all_solutions=all_solutions,
            no_charm_solutions=no_charm_solutions,
            names=charm_names(all_solutions),
            sort_key=sort_key,
        )
        return view

    @classmethod
    def from_search(cls, results: ResultSet, sort_key: SortKey = SortKey.NONE) -> ResultsView:
        """A finished search's lists: ``AddSolutions`` files each charm-free
        solution in ``all_solutions`` and in ``no_charm_solutions``, so the
        charm-free list is a selection of ``all_solutions``."""
        all_solutions = results.all_solutions
        names = charm_names(all_solutions)
        charm_free = [position for position, name in enumerate(names) if name == ""]
        view = cls._showing_all(
            all_solutions=all_solutions,
            no_charm_solutions=SolutionSelection(all_solutions, charm_free),
            names=names,
            sort_key=sort_key,
        )
        return view

    def charm_filter_names(self) -> list[str]:
        """The charm names the filter offers after None and All: every charmed
        solution's name once, in case-insensitive alphabetical order."""
        names = sorted(self.by_charm, key=str.casefold)
        return names

    def show_filter(self) -> None:
        """``cmbCharms_SelectedIndexChanged``: rebuild ``final`` from the
        filter's list in arrival order, then sort it. A charm name with no
        solutions shows nothing."""
        charm_filter = self.charm_filter
        source = self.all_solutions
        positions: Sequence[int] = []
        no_charm = self.no_charm_solutions
        if charm_filter.kind is FilterKind.NONE:
            if isinstance(no_charm, SolutionSelection) and no_charm.source is source:
                positions = no_charm.positions
            else:
                source = no_charm
                positions = range(len(source))
        elif charm_filter.kind is FilterKind.ALL:
            positions = range(len(source))
        elif charm_filter.charm_name is not None and charm_filter.charm_name in self.by_charm:
            positions = self.by_charm[charm_filter.charm_name]
        self.final = SolutionSelection(source, sorted_positions(source, positions, self.sort_key))

    def select_filter(self, charm_filter: CharmFilter) -> None:
        """Choose a charm filter item."""
        self.charm_filter = charm_filter
        self.show_filter()

    def select_sort(self, key: SortKey) -> None:
        """``cmbSort_SelectedIndexChanged``: sort what is shown by ``key``,
        from its current order, so ties keep the previous sort's order.
        None shows the filter's list in arrival order."""
        if key == self.sort_key:
            return
        self.sort_key = key
        if len(self.final) == 0:
            return
        if key is SortKey.NONE:
            self.show_filter()
            return
        self.final = SolutionSelection(
            self.final.source,
            sorted_positions(self.final.source, self.final.positions, key),
        )

    def relanguage(self) -> None:
        """The results part of ``LanguageSelect_Click``, after the game's
        records have been renamed (``apply_language``): rebuild ``by_charm``
        under the new names, keep the selected charm under its new name
        (``UpdateCharmComboBox`` looks up the selected charm's ``GetName()``),
        and show the filter again.

        The new name is that of the selected charm's first solution. A
        selected name with no solutions has no charm to follow, so All is
        shown instead, as the drop-down does when nothing is selected.
        """
        names = charm_names(self.all_solutions)
        charm_filter = self.charm_filter
        if charm_filter.kind is FilterKind.CHARM and charm_filter.charm_name is not None:
            selected = self.by_charm.get(charm_filter.charm_name, [])
            self.charm_filter = (
                CharmFilter.charm(names[selected[0]]) if selected else CharmFilter.every_solution()
            )
        self.by_charm = _positions_by_charm(names)
        self.show_filter()
