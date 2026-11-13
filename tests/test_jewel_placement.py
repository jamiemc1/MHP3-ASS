from __future__ import annotations

import pytest

from mhp3ass.results.placement import fits


@pytest.mark.parametrize(
    ("sizes", "groups", "fitted"),
    [
        ([], [], True),
        ([1], [], False),
        ([2, 1], [3], True),
        ([2, 2], [3], False),
        ([1, 1, 1], [1, 2], True),
        ([2], [1, 1], False),
        ([3, 1], [3, 1], True),
        ([1, 3], [1, 3], True),
        ([2, 2, 1, 1], [3, 3], True),
        ([2, 2, 2], [3, 3], False),
    ],
)
def test_jewels_fit_slot_groups_several_to_a_group(sizes, groups, fitted):
    assert fits(sizes, groups=groups) is fitted
