"""The main screen's layout at each terminal size.

Not a port: the TUI's own layout. The screen takes one width class and one
height class, each by the largest breakpoint it reaches, as Textual's
``HORIZONTAL_BREAKPOINTS`` and ``VERTICAL_BREAKPOINTS`` give them (the CSS
is written ``Screen.-narrow …``). The widths:

- ``-narrow`` (under 110 columns): the table only, with the charm drop-down
  at the top of the sets; Enter or ``i`` opens the inspector over the table;
- ``-medium`` (110-149): the table with the charm drop-down, and the
  inspector beside it;
- ``-wide`` (150-219): the charm sidebar, the table and the inspector;
- ``-huge`` (220 and over): as wide, with a wider inspector and the
  table's pieces and charm named in full.

The heights:

- ``-short`` (under 30 rows): the query editor, opened over results,
  takes the results' place until it is collapsed again;
- ``-normal`` (30-45): the editor opens above the results;
- ``-tall`` (46 and over): as normal, and a narrow screen is laid out as
  a portrait, the inspector below the table following the cursor.

At 60 columns or 16 rows and below, the screen is small: the table only, with a
note in place of the footer.

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


class HeightClass(StrEnum):
    """The screen's height class, as its CSS class names it."""

    SHORT = "-short"
    NORMAL = "-normal"
    TALL = "-tall"


class InspectorPlace(Enum):
    """Where the inspector shows: beside the table, below it, or over it on request."""

    BESIDE = "beside"
    BELOW = "below"
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


def height_breakpoints() -> list[tuple[int, str]]:
    """Each height class's least height, for ``VERTICAL_BREAKPOINTS``."""
    breakpoints = [
        (0, HeightClass.SHORT.value),
        (30, HeightClass.NORMAL.value),
        (46, HeightClass.TALL.value),
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
    """What the main screen shows at one size; ``small``: at most 60
    columns or 16 rows."""

    width: WidthClass
    height: HeightClass
    small: bool

    @property
    def sidebar(self) -> bool:
        """The charm sidebar shows; otherwise the charm drop-down does,
        unless the screen is small."""
        shown = self.width in (WidthClass.WIDE, WidthClass.HUGE) and not self.small
        return shown

    @property
    def inspector(self) -> InspectorPlace:
        if self.small or (self.width is WidthClass.NARROW and self.height is not HeightClass.TALL):
            return InspectorPlace.OVER
        if self.width is WidthClass.NARROW:
            return InspectorPlace.BELOW
        return InspectorPlace.BESIDE

    @property
    def editor_over_results(self) -> bool:
        """The query editor, opened over results, takes their place."""
        over = self.height is HeightClass.SHORT
        return over

    @property
    def full_names(self) -> bool:
        """The table names the pieces and charm in full, not shortened."""
        full = self.width is WidthClass.HUGE
        return full


def layout_for(width: int, height: int) -> Layout:
    """The layout of a terminal ``width`` columns wide and ``height`` rows high."""
    layout = Layout(
        width=WidthClass(breakpoint_class(width, width_breakpoints())),
        height=HeightClass(breakpoint_class(height, height_breakpoints())),
        small=width <= 60 or height <= 16,
    )
    return layout
