"""The search's progress: a one-line cat flicking its tail, beside a bar
weighted by armour combinations (quirk 40, changed by design). It shows
only once a search has run for a second; quicker searches never show it."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.content import Content
from textual.timer import Timer
from textual.widgets import Label, ProgressBar, Static


def cat_frames() -> list[str]:
    """A small cat, one line high, flicking its tail: ``~``, then the tilde
    operator (U+223C, a little higher), then ``⌒``, and back."""
    raised_tail = "\u223c"
    frames = ["~ᓚᘏᗢ", f"{raised_tail}ᓚᘏᗢ", "⌒ᓚᘏᗢ", f"{raised_tail}ᓚᘏᗢ"]
    return frames


class CatSpinner(Static):
    """Steps through ``cat_frames`` while running."""

    def __init__(self) -> None:
        self._frames = cat_frames()
        super().__init__(Content(self._frames[0]))
        self._step = 0
        self._timer: Timer | None = None

    def start(self) -> None:
        if self._timer is None:
            self._timer = self.set_interval(0.24, self._next_frame)

    def stop(self) -> None:
        if self._timer is not None:
            self._timer.stop()
            self._timer = None

    def _next_frame(self) -> None:
        self._step = (self._step + 1) % len(self._frames)
        self.update(Content(self._frames[self._step]))


class SearchProgress(Horizontal):
    """Shown while a search runs, from ``delay`` seconds after it starts."""

    DEFAULT_CSS = """
    SearchProgress {
        height: 1;
        padding: 0 2;
        display: none;
    }
    SearchProgress.running {
        display: block;
    }
    SearchProgress CatSpinner {
        width: 6;
    }
    SearchProgress ProgressBar {
        width: 52;
    }
    SearchProgress Label {
        padding: 0 2;
        color: $text-muted;
    }
    """

    def __init__(self, delay: float = 1.0) -> None:
        super().__init__()
        self._delay = delay
        self._reveal: Timer | None = None

    def compose(self) -> ComposeResult:
        yield CatSpinner()
        yield ProgressBar(show_percentage=False, show_eta=False)
        yield Label("esc cancel")

    def start(self) -> None:
        """Reset the bar, and show it if the search is still running after ``delay``."""
        self.query_one(ProgressBar).update(total=None, progress=0)
        self._reveal = self.set_timer(self._delay, self._show)

    def advance(self, done: int, total: int) -> None:
        self.query_one(ProgressBar).update(total=total, progress=done)

    def stop(self) -> None:
        if self._reveal is not None:
            self._reveal.stop()
            self._reveal = None
        self.query_one(CatSpinner).stop()
        self.remove_class("running")

    def _show(self) -> None:
        self._reveal = None
        self.query_one(CatSpinner).start()
        self.add_class("running")
