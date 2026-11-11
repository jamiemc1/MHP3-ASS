"""Cancelling a search: ``run_search`` raises ``SearchCancelled`` serially and
in the pool, and the pool searches correctly afterwards."""

from __future__ import annotations

from threading import Event

import pytest

from mhp3ass.results.result_set import solution_lines
from mhp3ass.search import SearchCancelled, run_search


@pytest.fixture
def cancelled() -> Event:
    """A cancel event that is already set."""
    event = Event()
    event.set()
    return event


def test_a_search_cancelled_before_it_starts_raises(
    corpus_spec, search_data_for, pool_or_serial, cancelled
):
    spec = corpus_spec("corpus/g16-attack-sharp-no-charms.json")

    with pytest.raises(SearchCancelled):
        run_search(spec, data=search_data_for(spec), pool=pool_or_serial, cancel=cancelled)


def test_a_search_cancelled_part_way_raises_before_checking_every_combination(
    corpus_spec, search_data_for, pool_or_serial
):
    """g18: six-skill Blademaster search, no charms, 1.17M combinations, none match."""
    spec = corpus_spec("corpus/g18-six-skills.json")
    cancel = Event()
    reports: list[tuple[int, int]] = []

    def cancel_at_first_report(done: int, total: int) -> None:
        reports.append((done, total))
        cancel.set()

    with pytest.raises(SearchCancelled):
        run_search(
            spec,
            data=search_data_for(spec),
            pool=pool_or_serial,
            on_progress=cancel_at_first_report,
            cancel=cancel,
        )

    assert reports != []
    assert all(done < total for done, total in reports)


def test_an_unset_cancel_changes_nothing_in_the_serial_search(
    corpus_spec, search_data_for, serial_search
):
    """Serial only: there an unset cancel adds a check at every step."""
    spec = corpus_spec("corpus/g16-attack-sharp-no-charms.json")
    data = search_data_for(spec)

    result = run_search(spec, data=data, cancel=Event())

    expected = serial_search("g16-attack-sharp-no-charms.json")
    assert solution_lines(result, game=data.game) == solution_lines(expected, game=data.game)


def test_the_pool_searches_as_before_after_a_cancel(
    corpus_spec, search_data_for, serial_search, search_pool, cancelled
):
    """The cancelled search's tasks start on the idle processes and finish
    unread; the next search's results and progress are its own."""
    spec = corpus_spec("corpus/g16-attack-sharp-no-charms.json")
    data = search_data_for(spec)
    with pytest.raises(SearchCancelled):
        run_search(spec, data=data, pool=search_pool, cancel=cancelled)
    reports: list[tuple[int, int]] = []

    after = run_search(
        spec,
        data=data,
        pool=search_pool,
        on_progress=lambda done, total: reports.append((done, total)),
    )

    expected = serial_search("g16-attack-sharp-no-charms.json")
    assert solution_lines(after, game=data.game) == solution_lines(expected, game=data.game)
    assert reports[-1][0] == reports[-1][1]
    assert all(done <= total for done, total in reports)
