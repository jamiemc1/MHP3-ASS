"""The search's progress: a bar weighted by armour combinations and a cat
whose tail wags while the search runs (quirk 40, changed by design)."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.content import Content
from textual.timer import Timer
from textual.widgets import Label, ProgressBar, Static


def cat_frames() -> list[str]:
    """A sitting cat, three lines high, wagging its tail and blinking once."""
    body = ["  /\\_/\\  ", " ( o.o ) ", "  /|_|\\"]
    blink = ["  /\\_/\\  ", " ( -.- ) ", "  /|_|\\"]
    tails = [
        ["     ", "   ) ", "_/   "],
        ["   _ ", "  /  ", "_/   "],
        ["     ", "  (  ", "_/   "],
        ["     ", "   ) ", "_/   "],
        ["     ", "     ", "__~  "],
        ["     ", "     ", "__/  "],
    ]
    frames = []
    for step in range(12):
        face = blink if step == 5 else body
        tail = tails[step % len(tails)]
        lines = [face_line + tail_line for face_line, tail_line in zip(face, tail, strict=True)]
        frames.append("\n".join(lines))
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
    """Shown only while a search runs."""

    DEFAULT_CSS = """
    SearchProgress {
        height: 3;
        padding: 0 2;
        display: none;
    }
    SearchProgress.running {
        display: block;
    }
    SearchProgress CatSpinner {
        width: 16;
    }
    SearchProgress ProgressBar {
        margin-top: 1;
        width: 52;
    }
    SearchProgress Label {
        padding: 1 2;
        color: $text-muted;
    }
    """

    def compose(self) -> ComposeResult:
        yield CatSpinner()
        yield ProgressBar(show_percentage=False, show_eta=False)
        yield Label("esc cancel")

    def start(self) -> None:
        self.query_one(ProgressBar).update(total=None, progress=0)
        self.query_one(CatSpinner).start()
        self.add_class("running")

    def advance(self, done: int, total: int) -> None:
        self.query_one(ProgressBar).update(total=total, progress=done)

    def stop(self) -> None:
        self.query_one(CatSpinner).stop()
        self.remove_class("running")
