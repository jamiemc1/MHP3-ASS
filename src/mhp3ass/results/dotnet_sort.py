""".NET Framework 4.8's ``List<T>.Sort( Comparison<T> )``: an unstable introsort.

Transcribed from the .NET Framework 4.8 reference source,
``ArraySortHelper<T>.IntrospectiveSort`` and its helpers
(``ndp/clr/src/BCL/System/Collections/Generic/ArraySortHelper.cs``), which
``List<T>.Sort`` reaches through ``Array.Sort<T>( T[], int, int, IComparer<T> )``.
The original sorts its results with it (``legacy/Form1.h:2149-2172``).

Ties land wherever the partitioning leaves them, so the order of equal
elements depends on the order before the sort. Python's ``list.sort`` is
stable and gives different orders.

``ArraySortHelper<T>.Sort`` uses the introsort only for applications that
target .NET Framework 4.5 or later (``BinaryCompatibility``), and falls back
to the older depth-limited quicksort otherwise. The reference GUI and the
harness are built for 4.8 (``scripts/windows/build-legacy.ps1``,
``harness/Harness.vcxproj``); the upstream ``.vcproj`` targeted .NET 2.0,
whose quicksort orders ties differently and has no capacity-dependent depth
limit. The harness's sort probe confirms which sort the 4.8 build runs.
"""

from __future__ import annotations

from collections.abc import Callable


def floor_log2(n: int) -> int:
    """``IntrospectiveSortUtilities.FloorLog2``.

    Despite its name it counts the halvings until ``n`` reaches 0, which is
    ``floor(log2(n)) + 1`` for ``n >= 1``.
    """
    result = 0
    while n >= 1:
        result += 1
        n //= 2
    return result


def introsort[T](keys: list[T], compare: Callable[[T, T], int], array_length: int) -> None:
    """``ArraySortHelper<T>.IntrospectiveSort( keys, 0, keys.Count, compare )``, in place.

    The depth limit comes from ``array_length``, the length of the ``List``'s
    backing array (its capacity), not from the number of elements. A ``List``
    keeps its capacity through ``Clear``, so it is usually larger.
    """
    length = len(keys)
    if array_length < length:
        raise ValueError(f"array length {array_length} is shorter than the list ({length})")
    if length < 2:
        return
    _intro_sort(
        keys=keys,
        lo=0,
        hi=length - 1,
        depth_limit=2 * floor_log2(array_length),
        compare=compare,
    )


def _swap_if_greater[T](keys: list[T], compare: Callable[[T, T], int], a: int, b: int) -> None:
    if a != b and compare(keys[a], keys[b]) > 0:
        keys[a], keys[b] = keys[b], keys[a]


def _swap[T](keys: list[T], i: int, j: int) -> None:
    keys[i], keys[j] = keys[j], keys[i]


def _intro_sort[T](
    keys: list[T], lo: int, hi: int, depth_limit: int, compare: Callable[[T, T], int]
) -> None:
    """``IntroSort``: quicksort down to 16 elements, heapsort once the depth limit is spent."""
    while hi > lo:
        partition_size = hi - lo + 1
        if partition_size <= 16:
            if partition_size == 1:
                return
            if partition_size == 2:
                _swap_if_greater(keys, compare, lo, hi)
                return
            if partition_size == 3:
                _swap_if_greater(keys, compare, lo, hi - 1)
                _swap_if_greater(keys, compare, lo, hi)
                _swap_if_greater(keys, compare, hi - 1, hi)
                return
            _insertion_sort(keys, lo=lo, hi=hi, compare=compare)
            return
        if depth_limit == 0:
            _heapsort(keys, lo=lo, hi=hi, compare=compare)
            return
        depth_limit -= 1
        pivot_index = _pick_pivot_and_partition(keys, lo=lo, hi=hi, compare=compare)
        _intro_sort(keys=keys, lo=pivot_index + 1, hi=hi, depth_limit=depth_limit, compare=compare)
        hi = pivot_index - 1


def _pick_pivot_and_partition[T](
    keys: list[T], lo: int, hi: int, compare: Callable[[T, T], int]
) -> int:
    """``PickPivotAndPartition``: median of three, then Hoare-style partitioning."""
    middle = lo + ((hi - lo) >> 1)
    _swap_if_greater(keys, compare, lo, middle)
    _swap_if_greater(keys, compare, lo, hi)
    _swap_if_greater(keys, compare, middle, hi)

    pivot = keys[middle]
    _swap(keys, middle, hi - 1)
    left = lo
    right = hi - 1
    while left < right:
        left += 1
        while compare(keys[left], pivot) < 0:
            left += 1
        right -= 1
        while compare(pivot, keys[right]) < 0:
            right -= 1
        if left >= right:
            break
        _swap(keys, left, right)
    _swap(keys, left, hi - 1)
    return left


def _insertion_sort[T](keys: list[T], lo: int, hi: int, compare: Callable[[T, T], int]) -> None:
    for i in range(lo, hi):
        j = i
        item = keys[i + 1]
        while j >= lo and compare(item, keys[j]) < 0:
            keys[j + 1] = keys[j]
            j -= 1
        keys[j + 1] = item


def _heapsort[T](keys: list[T], lo: int, hi: int, compare: Callable[[T, T], int]) -> None:
    n = hi - lo + 1
    for i in range(n // 2, 0, -1):
        _down_heap(keys, i=i, n=n, lo=lo, compare=compare)
    for i in range(n, 1, -1):
        _swap(keys, lo, lo + i - 1)
        _down_heap(keys, i=1, n=i - 1, lo=lo, compare=compare)


def _down_heap[T](keys: list[T], i: int, n: int, lo: int, compare: Callable[[T, T], int]) -> None:
    item = keys[lo + i - 1]
    while i <= n // 2:
        child = 2 * i
        if child < n and compare(keys[lo + child - 1], keys[lo + child]) < 0:
            child += 1
        if not compare(item, keys[lo + child - 1]) < 0:
            break
        keys[lo + i - 1] = keys[lo + child - 1]
        i = child
    keys[lo + i - 1] = item
