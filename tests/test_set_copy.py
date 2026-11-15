from __future__ import annotations

import pytest

from mhp3ass.results.details import (
    ChestJewels,
    Placement,
    PlacementPending,
    SolutionDetails,
    UnknownPlacement,
)
from mhp3ass.set_copy import copied_notice, jewels_being_worked_out, system_copy_command


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
        extra_skills=(),
    )
    return details


def test_the_notice_names_the_copied_set():
    notice = copied_notice(1234, details=_details(None))

    assert notice == "Copied set 1,234."


def test_a_set_copied_during_a_search_says_its_jewels_arent_placed():
    notice = copied_notice(7, details=_details(PlacementPending(while_searching=True)))

    assert notice == (
        "Copied set 7, without its jewels' places: copy it again after the search for them."
    )


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
