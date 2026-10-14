"""Animated effects, described over time and semantic colour.

An effect is a function of time: `frame(elapsed)` says what it shows that long
after it started, so a skipped tick shows the right state on the next one. A
frame names theme colours and fractions of the thing it decorates (a line, a
bar, a block of text), never pixels or terminal cells: a terminal backend
samples it into cells, Qt into a painter, a web view into CSS.

Frames:

- `Gradient`: theme colours repeating along a line, shifted by a fraction;
- `Mix`: one colour part of the way from one theme colour to another;
- `Band`: a theme colour over a span of a line;
- `TextFrame`: lines of text, each character in its own colour.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Generic, TypeVar

from ui_theme.colour import Rgb
from ui_theme.scheme import (
    AccentColour, BackgroundColour, ColourScheme, ForegroundColour, PrimaryColour,
    SecondaryColour, ThemeColour,
)

if TYPE_CHECKING:
    from ui_theme.backend import Backend

FrameT = TypeVar("FrameT", bound="Frame")


class Frame(ABC):
    """What an effect shows at one moment."""

    @abstractmethod
    def paint(self, backend: Backend[Any, Any, Any, Any], target: Any) -> Any:
        """This frame in `backend`'s paint, for `target` (its geometry or element)."""


@dataclass(frozen=True)
class Gradient(Frame):
    """Theme colours repeating along a line, one cycle per line length, moved `offset` of it."""

    stops: tuple[type[ThemeColour], ...]
    offset: float

    def at(self, position: float) -> tuple[type[ThemeColour], type[ThemeColour], float]:
        """The two stops around `position` (0–1 along the line) and how far between them."""
        place = ((position - self.offset) % 1.0) * len(self.stops)
        index = int(place) % len(self.stops)
        return self.stops[index], self.stops[(index + 1) % len(self.stops)], place - int(place)

    def paint(self, backend: Backend[Any, Any, Any, Any], target: Any) -> Any:
        return backend.paint_gradient(self, target)


@dataclass(frozen=True)
class Mix(Frame):
    """A colour `amount` of the way from `start` to `end` (0 is start, 1 is end)."""

    start: type[ThemeColour]
    end: type[ThemeColour]
    amount: float

    def rgb(self, scheme: ColourScheme) -> Rgb:
        return scheme.rgb(self.start).blend(scheme.rgb(self.end), self.amount)

    def paint(self, backend: Backend[Any, Any, Any, Any], target: Any) -> Any:
        return backend.paint_mix(self, target)


@dataclass(frozen=True)
class Band(Frame):
    """`colour` over the span `start`–`end` (fractions of the line); nothing elsewhere."""

    colour: type[ThemeColour]
    start: float
    end: float

    def covers(self, position: float) -> bool:
        return self.start <= position < self.end

    def paint(self, backend: Backend[Any, Any, Any, Any], target: Any) -> Any:
        return backend.paint_band(self, target)


@dataclass(frozen=True)
class TextFrame(Frame):
    """Lines of text; each character with its colour (None: the ordinary text colour)."""

    lines: tuple[tuple[tuple[str, Rgb | None], ...], ...]

    def paint(self, backend: Backend[Any, Any, Any, Any], target: Any) -> Any:
        return backend.paint_text(self, target)


class Effect(ABC, Generic[FrameT]):
    """An animation: a frame for any time since it started."""

    # How often a frontend should show a new frame.
    frames_per_second: float
    # How long it runs; None runs until stopped.
    duration: float | None

    @abstractmethod
    def frame(self, elapsed: float) -> FrameT: ...

    @property
    @abstractmethod
    def final(self) -> FrameT:
        """What shows when it has finished, or when animation is off."""

    def finished(self, elapsed: float) -> bool:
        return self.duration is not None and elapsed >= self.duration


@dataclass(frozen=True)
class GradientSweep(Effect[Gradient]):
    """A band of theme colours moving along a line, one pass per period."""

    stops: tuple[type[ThemeColour], ...]
    period: float
    frames_per_second: float
    duration: float | None = None

    def frame(self, elapsed: float) -> Gradient:
        return Gradient(self.stops, (elapsed / self.period) % 1.0)

    @property
    def final(self) -> Gradient:
        return Gradient(self.stops, 0.0)


@dataclass(frozen=True)
class Fade(Effect[Mix]):
    """From one theme colour to another, easing out, over `duration` seconds."""

    start: type[ThemeColour]
    end: type[ThemeColour]
    duration: float
    frames_per_second: float

    def frame(self, elapsed: float) -> Mix:
        progress = min(1.0, max(0.0, elapsed / self.duration))
        return Mix(self.start, self.end, 1 - (1 - progress) ** 2)

    @property
    def final(self) -> Mix:
        return Mix(self.start, self.end, 1.0)

    def ending_at(self, end: type[ThemeColour]) -> Fade:
        return Fade(self.start, end, self.duration, self.frames_per_second)


@dataclass(frozen=True)
class Wipe(Effect[Band]):
    """A band of colour crossing a line once, leaving nothing behind."""

    colour: type[ThemeColour]
    width: float
    duration: float
    frames_per_second: float

    def frame(self, elapsed: float) -> Band:
        lead = min(1.0, max(0.0, elapsed / self.duration)) * (1 + self.width)
        return Band(self.colour, lead - self.width, lead)

    @property
    def final(self) -> Band:
        return Band(self.colour, 1.0, 1.0)


@dataclass(frozen=True)
class PlayedText(Effect[TextFrame]):
    """Text frames built in advance, shown at `frames_per_second`; the last one stays."""

    frames: tuple[TextFrame, ...]
    frames_per_second: float

    @property
    def duration(self) -> float:  # type: ignore[override]
        return len(self.frames) / self.frames_per_second

    def frame(self, elapsed: float) -> TextFrame:
        return self.frames[min(len(self.frames) - 1, max(0, int(elapsed * self.frames_per_second)))]

    @property
    def final(self) -> TextFrame:
        return self.frames[-1]


# The busy indicator while an agent works.
ACTIVITY_SWEEP = GradientSweep((PrimaryColour, AccentColour, SecondaryColour),
                               period=1.0, frames_per_second=15)

# A message that has just arrived: its colour fades from the accent to its own.
NEW_MESSAGE = Fade(AccentColour, AccentColour, duration=0.4, frames_per_second=30)

# Text that has just arrived on a live tail: it rises out of the background
# into its own colours (a backend blends each run's colour, not one colour).
NEW_TEXT = Fade(BackgroundColour, ForegroundColour, duration=0.35, frames_per_second=30)

# The current tab's underline when a tab is chosen.
TAB_WIPE = Wipe(AccentColour, width=0.35, duration=0.25, frames_per_second=60)
