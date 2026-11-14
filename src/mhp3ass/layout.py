"""The main screen's layout at each terminal width.

Not a port: the TUI's own layout. The screen takes one width class, by the
widest breakpoint it reaches, as Textual's ``HORIZONTAL_BREAKPOINTS`` give
it (the CSS is written ``Screen.-narrow …``):

- ``-narrow`` (under 110 columns): the table only, with the charm drop-down
  in its title line; Enter or ``i`` opens the inspector over the table;
- ``-medium`` (110-149): the table with the charm drop-down, and the
  inspector beside it;
- ``-wide`` (150-219): the charm sidebar, the table and the inspector;
- ``-huge`` (220 and over): as wide, with a wider inspector and the
  table's pieces and charm named in full.

The thresholds are starting values, to be tuned by trying them.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, StrEnum


class WidthClass(StrEnum):
    """The screen's width class, as its CSS class names it."""

    NARROW = "-narrow"
    MEDIUM = "-medium"
    WIDE = "-wide"
    HUGE = "-huge"


class InspectorPlace(Enum):
    """Where the inspector shows: beside the table, or over it on request."""

    BESIDE = "beside"
    OVER = "over"


def width_breakpoints() -> list[tuple[int, str]]:
    """Each width class's least width, for ``HORIZONTAL_BREAKPOINTS``."""
    breakpoints = [
        (0, WidthClass.NARROW.value),
        (110, WidthClass.MEDIUM.value),
        (150, WidthClass.WIDE.value),
        (220, WidthClass.HUGE.value),
    ]
    return breakpoints


def breakpoint_class(size: int, breakpoints: list[tuple[int, str]]) -> str:
    """The class of the highest of ``breakpoints`` that ``size`` reaches,
    as Textual picks it."""
    reached = [(least, name) for least, name in breakpoints if size >= least]
    if not reached:
        raise ValueError(f"no breakpoint covers {size}")
    name = max(reached)[1]
    return name


@dataclass(frozen=True)
class Layout:
    """What the main screen shows at one size."""

    width: WidthClass

    @property
    def sidebar(self) -> bool:
        """The charm sidebar shows; otherwise the charm drop-down does."""
        shown = self.width in (WidthClass.WIDE, WidthClass.HUGE)
        return shown

    @property
    def inspector(self) -> InspectorPlace:
        place = InspectorPlace.OVER if self.width is WidthClass.NARROW else InspectorPlace.BESIDE
        return place

    @property
    def full_names(self) -> bool:
        """The table names the pieces and charm in full, not shortened."""
        full = self.width is WidthClass.HUGE
        return full


def layout_for(width: int) -> Layout:
    """The layout of a terminal ``width`` columns wide."""
    layout = Layout(width=WidthClass(breakpoint_class(width, width_breakpoints())))
    return layout
