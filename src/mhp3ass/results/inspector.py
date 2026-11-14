"""The inspector's text for one set: label and text lines.

A new layout of what ``Form1::UpdateResultString`` writes for a result
(``legacy/Form1.h:1569-1655``), in its wording: the pieces with their "or
anything with" notes, the charm, the jewels with counts (split into the
chest's and the rest when Torso Inc makes the chest's count more, which the
original doesn't show; quirk 53), the spare slots,
the extra skills, every stat the sort can use, and under the difficulty the
materials it comes from.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from mhp3ass.charms.naming import charm_name
from mhp3ass.data.strings import DisplayStrings, StringIndex
from mhp3ass.data.text import as_signed
from mhp3ass.results.details import (
    ArmorLine,
    ArmorNote,
    ChestJewels,
    CorrectedJewels,
    DecorationCount,
    PlacementPending,
    SlotsSpare,
    SolutionDetails,
    UnbuildableJewels,
    UnknownPlacement,
)
from mhp3ass.results.difficulty import hard_materials
from mhp3ass.solution.state import Solution


@dataclass(frozen=True)
class InspectorLine:
    """``label`` is blank on a line that carries on the one above."""

    label: str
    text: str


def note_text(line: ArmorLine, strings: DisplayStrings) -> str | None:
    """A piece's note, as ``UpdateResultString`` appends it (Form1.h:1577-1585)."""
    match line.note:
        case None:
            return None
        case ArmorNote.ANY_WITH_SLOTS:
            slots = line.armor.num_slots
            opening = (
                StringIndex.OR_ANYTHING_WITH_SINGULAR
                if slots == 1
                else StringIndex.OR_ANYTHING_WITH_PLURAL
            )
            closing = StringIndex.SLOT_BRACKET if slots == 1 else StringIndex.SLOTS_BRACKET
            note = f"{strings.static(opening)} {slots} {strings.static(closing)}"
            return note
        case ArmorNote.ANY_TORSO_INC:
            return strings.static(StringIndex.OR_ANYTHING_WITH_TORSO_INC)


def spare_text(spare: SlotsSpare, strings: DisplayStrings) -> str:
    """The spare slots line (Form1.h:1608-1632): ``1 slot spare``, ``3 slots
    spare``, or with the groups, ``4 slots spare (1+1+2)``."""
    if spare.total == 1:
        return f"1 {strings.static(StringIndex.SLOT_SPARE)}"
    slots_spare = f"{spare.total} {strings.static(StringIndex.SLOTS_SPARE)}"
    if spare.groups is None:
        return slots_spare
    groups = "+".join(str(size) for size in spare.groups)
    text = f"{slots_spare} ({groups})"
    return text


def jewel_lines(details: SolutionDetails) -> list[InspectorLine]:
    """The jewel counts under "Jewels"; for a set where a jewel's place
    changes its points (``details.chest_jewels``), the chest's under
    "Chest xN", N being how many times its points count ("none" when it
    takes none), and the rest under "Elsewhere". A Torso Inc set whose
    placement isn't known, or waits for a search to finish, keeps the one
    list, saying which.

    A set whose listed jewels can't be placed (quirk 52) shows the version
    that builds instead, after a note, and under "Builds with" the charm it
    needs when that isn't the listed one; one no jewel list builds keeps the
    listed jewels and says why."""
    jewels = details.chest_jewels
    match jewels:
        case ChestJewels():
            return _split_lines(jewels)
        case CorrectedJewels(charm_changed=False):
            note = "(the listed jewels don't fit; these build it)"
            return [InspectorLine(label="Jewels", text=note), *_split_lines(jewels.jewels)]
        case CorrectedJewels():
            note = "(the listed charm and jewels don't fit; these build it)"
            charm = "no charm" if jewels.charm is None else charm_name(jewels.charm)
            lines = [
                InspectorLine(label="Jewels", text=note),
                InspectorLine(label="Builds with", text=charm),
                *_split_lines(jewels.jewels),
            ]
            return lines
    lines = _counted_lines("Jewels", details.decorations)
    match jewels:
        case UnknownPlacement():
            lines.append(InspectorLine(label="", text="(placement not known)"))
        case PlacementPending(while_searching=True):
            lines.append(InspectorLine(label="", text="(placement after the search)"))
        case PlacementPending():
            lines.append(InspectorLine(label="", text="(working out jewels…)"))
        case UnbuildableJewels():
            lines.append(
                InspectorLine(label="", text=f"(can't be built as listed: {_why(jewels)})")
            )
    return lines


def _why(jewels: UnbuildableJewels) -> str:
    reason = jewels.reason
    if reason.bad_skills:
        names = ", ".join(skill.name for skill in reason.bad_skills)
        verb = "stays" if len(reason.bad_skills) == 1 else "stay"
        return f"{names} {verb} active"
    if not reason.short:
        return "the skills can't all reach their points together"
    short = ", ".join(
        f"{line.skill.ability.name} reaches {line.most} of {line.skill.points_required}"
        for line in reason.short
    )
    return short


def _split_lines(jewels: ChestJewels) -> list[InspectorLine]:
    chest_label = f"Chest x{jewels.multiplier}"
    chest_lines = _counted_lines(chest_label, jewels.chest)
    if not chest_lines:
        chest_lines = [InspectorLine(label=chest_label, text="none")]
    lines = chest_lines + _counted_lines("Elsewhere", jewels.elsewhere)
    return lines


def _counted_lines(label: str, counts: Sequence[DecorationCount]) -> list[InspectorLine]:
    """``label`` on the first count's line, blank on the rest."""
    lines = [
        InspectorLine(
            label=label if number == 0 else "", text=f"{count.count}x {count.decoration.name}"
        )
        for number, count in enumerate(counts)
    ]
    return lines


def inspector_lines(
    solution: Solution,
    details: SolutionDetails,
    strings: DisplayStrings,
    piece_labels: Sequence[str],
) -> list[InspectorLine]:
    """``solution``'s lines from its ``details``; ``piece_labels`` name the five
    armour slots in order. An empty slot has no line."""
    lines = []
    armor_lines = iter(details.armors)
    for label, armor in zip(piece_labels, solution.armors, strict=True):
        if armor is None:
            continue
        line = next(armor_lines)
        lines.append(InspectorLine(label=label, text=armor.name))
        note = note_text(line, strings)
        if note is not None:
            lines.append(InspectorLine(label="", text=note))
    if details.charm is not None:
        lines.append(InspectorLine(label="Charm", text=charm_name(details.charm)))
    lines.extend(jewel_lines(details))
    if details.slots_spare is not None:
        lines.append(InspectorLine(label="Spare", text=spare_text(details.slots_spare, strings)))
    for number, skill in enumerate(details.extra_skills):
        lines.append(InspectorLine(label="Extra" if number == 0 else "", text=skill.name))
    stats = [
        (StringIndex.BASE_DEFENCE, as_signed(solution.defence)),
        (StringIndex.MAX_DEFENCE, as_signed(solution.max_defence)),
        (StringIndex.FIRE_RES, solution.fire_res),
        (StringIndex.WATER_RES, solution.water_res),
        (StringIndex.THUNDER_RES, solution.thunder_res),
        (StringIndex.ICE_RES, solution.ice_res),
        (StringIndex.DRAGON_RES, solution.dragon_res),
        (StringIndex.RARITY, as_signed(solution.rarity)),
        (StringIndex.DIFFICULTY, as_signed(solution.difficulty)),
    ]
    lines.extend(
        InspectorLine(label=strings.static(index), text=str(value)) for index, value in stats
    )
    # Under the difficulty: the materials that make it up.
    lines.extend(
        InspectorLine(label="", text=f"{part.count}x {part.material.name}")
        for part in hard_materials(solution)
    )
    return lines
