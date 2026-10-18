"""One animation clock for every running effect.

Paint derives from one clock-owned instant: a target reads `animation.frame()`
without sampling wall time or holding a frame counter. A backend gives the
clock one timer (`schedule`). It ticks at the fastest running effect's rate,
repaints visible targets together when their shared cadence boundary changes,
gives each finished effect one last paint and stops ticking when nothing runs.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from time import monotonic
from typing import Generic, Protocol, TypeVar

from ui_theme.effects import Effect, Frame

FrameT = TypeVar("FrameT", bound=Frame)


class AnimationTarget(Protocol):
    """Something an effect decorates, as the frontend sees it."""

    @property
    def animation_visible(self) -> bool:
        """True while painting it would show on screen."""

    def repaint(self) -> None:
        """Ask the frontend to paint it again (it reads its frame when it paints)."""


@dataclass(eq=False)
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
        if self.finished:
            return self.effect.final
        return self.effect.frame(self.effect.phase_time(self.elapsed, self.clock.time))

    def stop(self) -> None:
        self.clock.running.pop(self, None)
        self.clock.refresh()


class AnimationClock:
    """Runs every animation's cadence from one timer."""

    def __init__(self, schedule: Callable[[float | None], None],
                 now: Callable[[], float] = monotonic, *, enabled: bool = True) -> None:
        # `schedule(interval)` asks the backend to call `tick` every `interval`
        # seconds, or to stop calling it when interval is None.
        self.schedule = schedule
        self.now = now
        # One paint instant. Painting never samples wall time; ticks
        # advance this instant and invalidate the due targets together.
        self.time = now()
        self.enabled = enabled
        self.running: dict[Animation[Frame], AnimationTarget] = {}
        self._interval: float | None = None

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
        for animation, target in list(self.running.items()):
            effect = animation.effect
            finished = animation.finished
            if finished:
                del self.running[animation]
            if finished or (target.animation_visible
                    and effect.cadence_time(previous) != effect.cadence_time(now)):
                repaint.add(target)
        for target in repaint:
            target.repaint()
        self.refresh()

    def refresh(self) -> None:
        interval = min((1 / animation.effect.frames_per_second for animation, target in tuple(self.running.items())
                        if self.enabled and target.animation_visible), default=None)
        if interval != self._interval:
            if self._interval is None and interval is not None:
                self.time = self.now()
            self._interval = interval
            self.schedule(interval)
