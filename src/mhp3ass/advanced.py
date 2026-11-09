"""Advanced search: choosing which armour pieces and decorations a search may use.

Ported from ``frmAdvanced`` (``legacy/frmAdvanced.h:35-102``, ``:581-656``:
the constructor, ``CreateResult``, ``CheckResult``, ``DefaultChecked`` and
``ClearChecked``) and from ``Form1::btnAdvancedSearch_Click``
(``legacy/Form1.h:1420-1459``) with the handlers that forget the remembered
ticks (``DeleteOptions`` and its callers).

The dialog lists each slot's inferior pieces (``inf_armor``) and the inferior
decorations, ticking (and showing in bold) those the quick search would use
(``rel_*``). Searching rebuilds ``rel_*`` from the ticks, in ``inf`` order.
The caller runs ``formulate_query`` before opening the dialog, as the
original does even when the dialog is then cancelled.

Ticks are kept as the original's ``Result_t``: five armour lists in
``ArmorType`` order, then the decorations, one ``bool`` per listed item.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from mhp3ass.model import Armor, ArmorType, Decoration, HunterType
from mhp3ass.query import Query


@dataclass(frozen=True)
class Listed[T]:
    """One listed item and whether the quick search uses it (ticked and bold by default)."""

    item: T
    default: bool


@dataclass(frozen=True)
class AdvancedChoices:
    """What the dialog lists: per slot the inferior pieces, then the inferior decorations."""

    armor: list[list[Listed[Armor]]]
    decorations: list[Listed[Decoration]]

    def default_ticks(self) -> list[list[bool]]:
        """The six boxes' default ticks, in ``Result_t`` order."""
        defaults = [[listed.default for listed in slot] for slot in self.armor]
        defaults.append([listed.default for listed in self.decorations])
        return defaults


class ArmorOption(Enum):
    """The Options menu toggles, which call ``OptionsChanged``."""

    ALLOW_BAD_SKILLS = "allow_bad_skills"
    ALLOW_PIERCINGS = "allow_piercings"
    ALLOW_EVENT_ARMOR = "allow_event_armor"
    ALLOW_LOW_RANK_ARMOR = "allow_low_rank_armor"


def advanced_choices(query: Query) -> AdvancedChoices:
    """The ``frmAdvanced`` constructor's lists (frmAdvanced.h:79-92), for a formulated query."""
    armor = [
        [
            Listed(item=piece, default=piece in query.rel_armor[armor_type.value])
            for piece in query.inf_armor[armor_type.value]
        ]
        for armor_type in ArmorType
    ]
    decorations = [
        Listed(item=decoration, default=decoration in query.rel_decorations)
        for decoration in query.inf_decorations
    ]
    choices = AdvancedChoices(armor=armor, decorations=decorations)
    return choices


def check_result(
    defaults: list[list[bool]], remembered: list[list[bool]] | None
) -> list[list[bool]]:
    """``CheckResult`` (frmAdvanced.h:648-656): the ticks the dialog opens with.

    Remembered ticks replace the defaults by position; a shorter remembered
    list leaves the rest at their defaults. A longer one raises
    ``IndexError``, where the original's ``Items[ j ]`` throws
    ``ArgumentOutOfRangeException`` before the dialog opens. The original
    then keeps the remembered ticks, so every later Advanced Search on that
    page throws too until something forgets them; ``RememberedTicks`` keeps
    them likewise. The lists only change on changes that forget the ticks,
    so shipped data can't reach this.
    """
    ticks = [list(box) for box in defaults]
    if remembered is None:
        return ticks
    for box_index, box in enumerate(ticks):
        for position, ticked in enumerate(remembered[box_index]):
            if position >= len(box):
                raise IndexError(
                    f"remembered tick {position} is past the {len(box)} items of box {box_index}"
                )
            box[position] = ticked
    return ticks


def default_box(ticks: list[list[bool]], defaults: list[list[bool]], box: int) -> list[list[bool]]:
    """A box's Default button (``DefaultChecked``): tick exactly the bold items."""
    updated = [list(other) for other in ticks]
    updated[box] = list(defaults[box])
    return updated


def clear_box(ticks: list[list[bool]], box: int) -> list[list[bool]]:
    """A box's None button (``ClearChecked``): untick everything in it."""
    updated = [list(other) for other in ticks]
    updated[box] = [False] * len(updated[box])
    return updated


def apply_selection(query: Query, ticks: list[list[bool]]) -> None:
    """``btnAdvancedSearch_Click`` after Search (Form1.h:1442-1456): rebuild ``query``'s
    ``rel_armor`` and ``rel_decorations`` from the ticks, in ``inf`` order.

    A slot with nothing ticked ends up empty, which the search fills with an
    empty slot.
    """
    for armor_type in ArmorType:
        slot = armor_type.value
        query.rel_armor[slot] = [
            piece
            for piece, ticked in zip(query.inf_armor[slot], ticks[slot], strict=True)
            if ticked
        ]
    query.rel_decorations = [
        decoration
        for decoration, ticked in zip(query.inf_decorations, ticks[len(ArmorType)], strict=True)
        if ticked
    ]


@dataclass
class RememberedTicks:
    """``blast_options`` and ``glast_options``: the last dialog's ticks per hunter page.

    Pages are ``HunterType.BLADEMASTER`` and ``HunterType.GUNNER``. Ticks are
    kept by position, so they are only valid while the dialog's lists stay
    the same; the original forgets them on the changes that can alter them.
    """

    by_page: dict[HunterType, list[list[bool]] | None] = field(
        default_factory=lambda: dict.fromkeys([HunterType.BLADEMASTER, HunterType.GUNNER])
    )

    def ticks_for(self, page: HunterType) -> list[list[bool]] | None:
        ticks = self.by_page[_page(page)]
        return ticks

    def dialog_closed(self, page: HunterType, ticks: list[list[bool]] | None) -> None:
        """Record the dialog's result: its ticks after Search or Cancel (``CreateResult``),
        ``None`` after the window's close button, which forgets the page's ticks."""
        self.by_page[_page(page)] = None if ticks is None else [list(box) for box in ticks]

    def skill_or_filter_changed(self, current_page: HunterType) -> None:
        """A skill or skill-filter drop-down changed: forget the page showing at the time."""
        self.by_page[_page(current_page)] = None

    def rank_or_gender_changed(self) -> None:
        """HR, village quests or gender changed (``HRChanged``, ``DeleteOptions``)."""
        self.forget_all()

    def option_toggled(self, option: ArmorOption) -> None:
        """An Options toggle changed (``OptionsChanged``): all but Allow Bad Skills forget."""
        if option is not ArmorOption.ALLOW_BAD_SKILLS:
            self.forget_all()

    def forget_all(self) -> None:
        """``DeleteOptions``."""
        for page in self.by_page:
            self.by_page[page] = None


def _page(hunter_type: HunterType) -> HunterType:
    if hunter_type is HunterType.BOTH_TYPES:
        raise ValueError("the hunter pages are Blademaster and Gunner")
    return hunter_type
