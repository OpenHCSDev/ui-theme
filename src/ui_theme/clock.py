"""One animation clock for every running effect.

Paint derives from time: a target reads `animation.frame()` when it paints,
which asks the clock for the time, so it never holds a frame counter. The
clock only says when to paint: a backend gives it one timer (`schedule`), the
clock ticks at the fastest running effect's rate, repaints the visible targets
whose next frame is due, gives each finished effect one last paint and stops
ticking when nothing runs.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
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
    """One effect running on one target since `started`."""

    clock: AnimationClock
    effect: Effect[FrameT]
    target: AnimationTarget
    started: float
    due: float = field(default=0.0)

    @property
    def elapsed(self) -> float:
        return self.clock.now() - self.started

    def frame(self) -> FrameT:
        """What the effect shows now; its final frame once finished or when animation is off."""
        if not self.clock.enabled:
            return self.effect.final
        elapsed = self.elapsed
        return self.effect.final if self.effect.finished(elapsed) else self.effect.frame(elapsed)


class AnimationClock:
    """Runs every animation's cadence from one timer."""

    def __init__(self, schedule: Callable[[float | None], None],
                 now: Callable[[], float] = monotonic, *, enabled: bool = True) -> None:
        # `schedule(interval)` asks the backend to call `tick` every `interval`
        # seconds, or to stop calling it when interval is None.
        self.schedule = schedule
        self.now = now
        self.enabled = enabled
        self.running: dict[AnimationTarget, Animation[Frame]] = {}
        self._interval: float | None = None

    def start(self, effect: Effect[FrameT], target: AnimationTarget) -> Animation[FrameT]:
        """Run `effect` on `target`, replacing what ran there."""
        now = self.now()
        animation: Animation[FrameT] = Animation(self, effect, target, now, now)
        if self.enabled:
            self.running[target] = animation  # type: ignore[assignment]
            self._reschedule()
        return animation

    def stop(self, target: AnimationTarget) -> None:
        if self.running.pop(target, None) is not None:
            self._reschedule()

    def tick(self) -> None:
        now = self.now()
        for target, animation in list(self.running.items()):
            finished = animation.effect.finished(now - animation.started)
            if finished:
                del self.running[target]
            if finished or (now >= animation.due and target.animation_visible):
                animation.due = now + 1 / animation.effect.frames_per_second
                target.repaint()
        self._reschedule()

    def _reschedule(self) -> None:
        interval = (1 / max(a.effect.frames_per_second for a in self.running.values())
                    if self.running else None)
        if interval != self._interval:
            self._interval = interval
            self.schedule(interval)
