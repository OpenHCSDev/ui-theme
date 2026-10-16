"""Animated effects, described over time and semantic colour.

An effect is a function of time: `frame(elapsed)` says what it shows that long
after it started, so a skipped tick shows the right state on the next one. A
frame names theme colours and fractions of the thing it decorates (a line, a
bar, a block of text), never pixels or terminal cells: a terminal backend
samples it into cells, Qt into a painter, a web view into CSS.

Frames:

- `Gradient`: theme colours repeating along a line, shifted by a fraction;
- `Ribbon`: a finite gradient with tapered, fractional-height ink;
- `Mix`: one colour part of the way from one theme colour to another;
- `Band`: a theme colour over a span of a line;
- `TextFrame`: lines of text, each character in its own colour.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from math import cos, tau
from typing import TYPE_CHECKING, Any, Generic, TypeVar

from ui_theme.colour import Rgb
from ui_theme.scheme import (
    AccentColour, PrimaryColour,
    BackgroundColour, ColourScheme, ForegroundColour, MutedColour, ThemeColour,
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

    def sample(self, position: float) -> tuple[type[ThemeColour], type[ThemeColour], float, float]:
        """Colour stops, blend and fraction of the target's ink height at this point."""
        return (*self.at(position), 1.0)

    def paint(self, backend: Backend[Any, Any, Any, Any], target: Any) -> Any:
        return backend.paint_gradient(self, target)


@dataclass(frozen=True)
class Ribbon(Gradient):
    """A finite gradient with a bright core and tapered, fractional-height tails."""

    start: float
    end: float
    thickness: float

    def sample(self, position: float) -> tuple[type[ThemeColour], type[ThemeColour], float, float]:
        place = (position - self.start) / (self.end - self.start)
        if not 0 < place < 1:
            return (*self.at(0), 0.0)
        # Sample the finite palette, without wrapping its last stop to its first.
        start, end, amount = self.at(place * (len(self.stops) - 1) / len(self.stops))
        # Ease between colour stops; taper just the ends, not the whole line
        # into a dome. The bright body keeps the declared thin ink height.
        amount = amount * amount * (3 - 2 * amount)
        edge = min(1.0, 8 * place, 8 * (1 - place))
        edge = edge * edge * (3 - 2 * edge)
        return start, end, amount, self.thickness * edge


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
    """`colour` over `start`–`end`."""

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

    @staticmethod
    def phase(elapsed: float, period: float) -> float:
        return (elapsed / period) % 1.0

    @classmethod
    def oscillation(cls, elapsed: float, period: float) -> float:
        return (1 - cos(tau * cls.phase(elapsed, period))) / 2

    @staticmethod
    def progress(elapsed: float, duration: float) -> float:
        return min(1.0, max(0.0, elapsed / duration))


@dataclass(frozen=True)
class GradientSweep(Effect[Gradient]):
    """A band of theme colours moving along a line, one pass per period."""

    stops: tuple[type[ThemeColour], ...]
    period: float
    frames_per_second: float
    duration: float | None = None

    def frame(self, elapsed: float) -> Gradient:
        return Gradient(self.stops, self.phase(elapsed, self.period))

    @property
    def final(self) -> Gradient:
        return Gradient(self.stops, 0.0)


@dataclass(frozen=True)
class BreathingSweep(Effect[Ribbon]):
    """A tapered gradient travels, shrinks and expands; its size is never progress."""

    stops: tuple[type[ThemeColour], ...]
    period: float
    breathing_period: float
    minimum_width: float
    maximum_width: float
    minimum_thickness: float
    maximum_thickness: float
    frames_per_second: float
    duration: float | None = None

    def frame(self, elapsed: float) -> Ribbon:
        breath = self.oscillation(elapsed, self.breathing_period)
        width = self.minimum_width + (self.maximum_width - self.minimum_width) * breath
        thickness = self.minimum_thickness + (self.maximum_thickness - self.minimum_thickness) * breath
        lead = self.phase(elapsed, self.period) * (1 + width)
        return Ribbon(self.stops, 0.0, lead - width, lead, thickness)

    @property
    def final(self) -> Ribbon:
        width = (self.minimum_width + self.maximum_width) / 2
        thickness = (self.minimum_thickness + self.maximum_thickness) / 2
        return Ribbon(self.stops, 0.0, (1 - width) / 2, (1 + width) / 2, thickness)

@dataclass(frozen=True)
class Pulse(Effect[Mix]):
    """A colour mix breathes between declared bounds, without a frame counter."""

    start: type[ThemeColour]
    end: type[ThemeColour]
    minimum: float
    maximum: float
    period: float
    frames_per_second: float
    duration: float | None = None

    def frame(self, elapsed: float) -> Mix:
        return Mix(self.start, self.end,
                   self.maximum - (self.maximum - self.minimum) * self.oscillation(elapsed, self.period))

    @property
    def final(self) -> Mix:
        return Mix(self.start, self.end, self.maximum)


@dataclass(frozen=True)
class Fade(Effect[Mix]):
    """From one theme colour to another, easing out, over `duration` seconds."""

    start: type[ThemeColour]
    end: type[ThemeColour]
    duration: float
    frames_per_second: float

    def frame(self, elapsed: float) -> Mix:
        progress = self.progress(elapsed, self.duration)
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
        lead = self.progress(elapsed, self.duration) * (1 + self.width)
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
    def duration(self) -> float | None:  # type: ignore[override]
        return len(self.frames) / self.frames_per_second

    def frame(self, elapsed: float) -> TextFrame:
        return self.frames[self._frame_index(max(0, int(elapsed * self.frames_per_second)))]

    def _frame_index(self, index: int) -> int:
        return min(len(self.frames) - 1, index)

    @property
    def final(self) -> TextFrame:
        return self.frames[-1]


class LoopingText(PlayedText):
    """The same text playback, wrapping instead of finishing; final stays static when disabled."""

    @property
    def duration(self) -> None:
        return None

    def _frame_index(self, index: int) -> int:
        return index % len(self.frames)


# Single-cell activity ink; None inherits the frontend label's existing style.
SPINNER = LoopingText(
    tuple(TextFrame((((glyph, None),),)) for glyph in "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"),
    frames_per_second=10,
)

# The busy indicator while an agent works.
ACTIVITY_SWEEP = BreathingSweep(
    (AccentColour, PrimaryColour, AccentColour),
    period=3.2, breathing_period=2.7, minimum_width=0.06, maximum_width=0.22,
    minimum_thickness=1.0, maximum_thickness=1.0, frames_per_second=20,
)

# Goal standby is a quiet marker, not a claim of active work.
STANDBY_PULSE = Pulse(
    BackgroundColour, MutedColour, minimum=0.45, maximum=1.0,
    period=1.6, frames_per_second=20,
)

# A message that has just arrived: its colour fades from the accent to its own.
NEW_MESSAGE = Fade(AccentColour, AccentColour, duration=0.4, frames_per_second=30)

# Text that has just arrived on a live tail: it rises out of the background
# into its own colours (a backend blends each run's colour, not one colour).
NEW_TEXT = Fade(BackgroundColour, ForegroundColour, duration=0.35, frames_per_second=30)

# The current tab's underline when a tab is chosen.
TAB_WIPE = Wipe(AccentColour, width=0.35, duration=0.25, frames_per_second=60)
