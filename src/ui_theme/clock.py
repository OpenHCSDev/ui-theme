"""One animation clock for every running effect.

Paint derives from one clock-owned instant: a target reads `animation.frame()`
without sampling wall time or holding a frame counter. A backend gives the
clock one timer (`schedule`). It ticks at the fastest visible effect's rate
(a hidden effect asks only for the tick at its finish),
repaints visible targets together when their shared cadence boundary changes,
gives each finished effect one last paint and stops ticking when nothing runs.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from time import monotonic
from typing import Generic, Protocol, TypeVar

from ui_theme.effects import Effect, Frame

FrameT = TypeVar("FrameT", bound=Frame, covariant=True)


class AnimationTarget(Protocol):
    """Something an effect decorates, as the frontend sees it."""

    @property
    def animation_visible(self) -> bool:
        """True while painting it would show on screen."""

    def repaint(self) -> None:
        """Ask the frontend to paint it again (it reads its frame when it paints)."""


@dataclass(frozen=True, eq=False)
class Animation(Generic[FrameT]):
    """One effect's lifetime; the clock owns its target association and cadence."""

    clock: AnimationClock
    effect: Effect[FrameT]
    started: float

    @property
    def elapsed(self) -> float:
        return max(0.0, self.clock.time - self.started)

    @property
    def finished(self) -> bool:
        return not self.clock.enabled or self.effect.finished(self.elapsed)

    def frame(self) -> FrameT:
        """What the effect shows now; its final frame once finished or when animation is off."""
        return self.at(0.0)

    def at(self, position: float) -> FrameT:
        """What the effect shows now for a row `position` of the way through its target.

        One body, so a row cannot lose the phase time a continuous effect reads from the
        clock, nor the finished and animation-off answers. An effect that treats its rows
        alike ignores the position (Effect.at).
        """
        if self.finished:
            return self.effect.final
        return self.effect.at(self.effect.phase_time(self.elapsed, self.clock.time), position)

    def stop(self) -> None:
        self.clock.running.pop(self, None)
        self.clock.refresh()

    def interval(self, visible: bool) -> float | None:
        """When it next needs a tick: its frames on the clock's medium while seen, only its
        finish while hidden."""
        if visible:
            return self.effect.shown_every(self.clock.frame_interval, self.clock.ambient_interval)
        return self.effect.remaining(self.elapsed)


class AnimationClock:
    """Runs every animation's cadence from one timer."""

    def __init__(self, schedule: Callable[[float | None], None],
                 now: Callable[[], float] = monotonic, *, enabled: bool = True,
                 frame_interval: float = 1 / 60) -> None:
        # `schedule(interval)` asks the backend to call `tick` every `interval`
        # seconds, or to stop calling it when interval is None.
        self.schedule = schedule
        # How often the medium shows a frame; motion ticks at it (`DisplayRate`).
        self._frame_interval = frame_interval
        self.now = now
        # One paint instant. Painting never samples wall time; ticks
        # advance this instant and invalidate the due targets together.
        self.time = now()
        self.enabled = enabled
        self.running: dict[Animation[Frame], AnimationTarget] = {}
        self._interval: float | None = None
        self._ambient_interval = 0.0

    @property
    def frame_interval(self) -> float:
        return self._frame_interval

    @frame_interval.setter
    def frame_interval(self, seconds: float) -> None:
        """The medium changed how often it shows a frame (another screen, a new refresh rate):
        running motion ticks at the new interval from now on."""
        self._frame_interval = seconds
        self.refresh()

    @property
    def ambient_interval(self) -> float:
        """How often the medium affords a frame of motion nobody asked for
        (`Effect.shown_every`), in seconds; 0 where a frame costs nothing worth counting."""
        return self._ambient_interval

    @ambient_interval.setter
    def ambient_interval(self, seconds: float) -> None:
        """The frontend measured what showing a frame costs its thread: ambient effects
        tick at what it affords from now on."""
        self._ambient_interval = seconds
        self.refresh()

    def start(self, effect: Effect[FrameT], target: AnimationTarget) -> Animation[FrameT]:
        """Run an effect; independent effects on one target share this clock."""
        animation: Animation[FrameT] = Animation(self, effect, self.now())
        if self.enabled:
            self.running[animation] = target
            self.refresh()
        return animation

    def stop(self, target: AnimationTarget) -> None:
        for animation, owner in tuple(self.running.items()):
            if owner is target:
                del self.running[animation]
        self.refresh()

    def tick(self) -> None:
        previous = self.time
        now = self.time = self.now()
        repaint: set[AnimationTarget] = set()
        visible: dict[AnimationTarget, bool] = {}
        for animation, target in list(self.running.items()):
            effect = animation.effect
            finished = animation.finished
            if finished:
                del self.running[animation]
            if target not in visible:
                visible[target] = target.animation_visible
            if finished or (visible[target] and self.frame_began(effect, previous) != self.frame_began(effect, now)):
                repaint.add(target)
        for target in repaint:
            target.repaint()
        self._refresh(visible)

    def frame_began(self, effect: Effect[Frame], instant: float) -> float:
        return effect.frame_began(instant, self._frame_interval, self._ambient_interval)

    def refresh(self) -> None:
        self._refresh({})

    def _refresh(self, visible: dict[AnimationTarget, bool]) -> None:
        def _interval(animation: Animation[Frame], target: AnimationTarget) -> float | None:
            if target not in visible:
                visible[target] = target.animation_visible
            return animation.interval(visible[target])
        intervals = (_interval(a, t) for a, t in tuple(self.running.items()))
        interval = min((seconds for seconds in intervals if seconds is not None and self.enabled), default=None)
        if interval != self._interval:
            if self._interval is None and interval is not None:
                self.time = self.now()
            self._interval = interval
            self.schedule(interval)
