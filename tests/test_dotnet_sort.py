"""The .NET Framework 4.8 introsort (ArraySortHelper<T>.IntrospectiveSort).

Expected permutations are traced by hand from the reference source; the
harness's sort probe will pin them against .NET itself.
"""

from __future__ import annotations

import random

import pytest

from mhp3ass.results import dotnet_sort
from mhp3ass.results.dotnet_sort import floor_log2, introsort


def by_key(a, b):
    result = (a[0] > b[0]) - (a[0] < b[0])
    return result


def median_of_three_killer(n):
    """Values that drive the partitioning to its worst case (McIlroy's adversary).

    Values start undecided; when two undecided values meet, the likely pivot (the
    last undecided value compared, else the second) is fixed to the next smallest
    value. Sorting the result repeats the same comparisons, so every partition is
    lopsided.
    """
    undecided = n
    values = [undecided] * n
    next_value = 0
    candidate = None

    def fix(index):
        nonlocal next_value
        values[index] = next_value
        next_value += 1

    def adversary(x, y):
        nonlocal candidate
        if values[x] == undecided and values[y] == undecided:
            fix(x if x == candidate else y)
        if values[x] == undecided:
            candidate = x
        elif values[y] == undecided:
            candidate = y
        return values[x] - values[y]

    introsort(list(range(n)), compare=adversary, array_length=2**30)
    for index in range(n):
        if values[index] == undecided:
            fix(index)
    return values


@pytest.fixture
def heapsort_sizes(monkeypatch):
    """Records the size of every range the introsort hands to heapsort."""
    sizes = []
    heapsort = dotnet_sort._heapsort

    def recording_heapsort(keys, lo, hi, compare):
        sizes.append(hi - lo + 1)
        heapsort(keys, lo=lo, hi=hi, compare=compare)

    monkeypatch.setattr(dotnet_sort, "_heapsort", recording_heapsort)
    return sizes


@pytest.fixture
def paired_killer():
    """64 elements labelled by position, keyed in tied pairs over a median-of-three killer."""
    items = [(value // 2, index) for index, value in enumerate(median_of_three_killer(64))]
    return items


@pytest.mark.parametrize(("n", "expected"), [(1, 1), (2, 2), (3, 2), (16, 5), (17, 5), (64, 7)])
def test_floor_log2_counts_halvings(n, expected):
    assert floor_log2(n) == expected


@pytest.mark.parametrize("size", [0, 1, 2, 3, 15, 16, 17, 100, 1000])
def test_sorts_by_the_comparison(size):
    rng = random.Random(size)
    items = [(rng.randrange(10), index) for index in range(size)]

    introsort(items, compare=by_key)

    assert [key for key, _ in items] == sorted(key for key, _ in items)


def test_two_ties_stay_in_place():
    items = [(1, "a"), (1, "b")]

    introsort(items, compare=by_key)

    assert items == [(1, "a"), (1, "b")]


def test_three_element_network_reverses_ties():
    items = [(1, "a"), (1, "b"), (0, "c")]

    introsort(items, compare=by_key)

    assert items == [(0, "c"), (1, "b"), (1, "a")]


def test_insertion_sort_up_to_16_keeps_ties_in_order():
    keys = [3, 1, 2, 1, 3, 2, 1, 3, 2, 1, 3, 2, 1, 3, 2, 1]
    items = [(key, index) for index, key in enumerate(keys)]

    introsort(items, compare=by_key)

    assert items == sorted(items, key=lambda item: item[0])


def test_partitioning_17_equal_elements_moves_them():
    items = [(0, index) for index in range(17)]

    introsort(items, compare=by_key)

    assert [index for _, index in items] == [
        0,
        14,
        13,
        12,
        11,
        10,
        9,
        15,
        8,
        6,
        5,
        4,
        3,
        2,
        1,
        7,
        16,
    ]


def test_killer_input_falls_back_to_heapsort(heapsort_sizes):
    items = [(value, index) for index, value in enumerate(median_of_three_killer(64))]

    introsort(items, compare=by_key)

    assert heapsort_sizes
    assert [key for key, _ in items] == list(range(64))


def test_backing_array_length_changes_tie_order(paired_killer):
    """The depth limit comes from the List's capacity, so the same elements can end in a
    different order when the List has grown past its count."""
    at_count = list(paired_killer)
    at_four_times_count = list(paired_killer)

    introsort(at_count, compare=by_key, array_length=64)
    introsort(at_four_times_count, compare=by_key, array_length=256)

    assert [key for key, _ in at_count] == [key for key, _ in at_four_times_count]
    assert at_count != at_four_times_count


def test_array_shorter_than_the_list_raises():
    with pytest.raises(ValueError, match="shorter than the list"):
        introsort([(0, 0), (1, 1)], compare=by_key, array_length=1)
