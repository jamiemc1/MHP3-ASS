from __future__ import annotations

import pytest

from mhp3ass.results.details import (
    ChestJewels,
    Placement,
    PlacementPending,
    SolutionDetails,
    UnknownPlacement,
)
from mhp3ass.set_copy import jewels_being_worked_out, system_copy_command


@pytest.mark.parametrize(
    ("platform", "command"),
    [("darwin", ["pbcopy"]), ("linux", None), ("win32", None)],
)
def test_only_macos_copies_through_a_command_as_well(platform, command):
    assert system_copy_command(platform) == command


def _details(chest_jewels: Placement) -> SolutionDetails:
    details = SolutionDetails(
        armors=(),
        charm=None,
        decorations=(),
        chest_jewels=chest_jewels,
        slots_spare=None,
        sort_value=None,
        extra_skills=(),
    )
    return details


def test_a_placement_being_worked_out_isnt_ready():
    details = _details(PlacementPending(while_searching=False))

    assert jewels_being_worked_out(details) is True


@pytest.mark.parametrize(
    "chest_jewels",
    [
        None,
        ChestJewels(multiplier=2, chest=(), elsewhere=()),
        UnknownPlacement(),
        PlacementPending(while_searching=True),
    ],
)
def test_a_placement_known_or_waiting_for_the_search_is_ready(chest_jewels):
    assert jewels_being_worked_out(_details(chest_jewels)) is False
