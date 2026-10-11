"""The backend interface drives a terminal-cell backend and a CSS backend the same way.

Neither backend is a real toolkit: the cell backend paints a row of cells as
colour names, the CSS backend writes declarations for an element. Both are
driven by the same effects and the same clock.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ui_theme.backend import Backend, TerminalBackend
from ui_theme.catalog import SCHEMES
from ui_theme.clock import AnimationClock
from ui_theme.colour import AnsiColour, Rgb, TerminalPalette
from ui_theme.depth import TrueColourDepth
from ui_theme.effects import (
    ACTIVITY_SWEEP, NEW_MESSAGE, TAB_WIPE, Band, Gradient, Mix, PlayedText, TextFrame,
)
from ui_theme.scheme import AccentColour, ColourScheme, PrimaryColour, SecondaryColour, ThemeColour
from ui_theme.splash import loading_splash

ANSI_DARK = next(scheme for scheme in SCHEMES if scheme.name == "ansi-dark")
NORD = next(scheme for scheme in SCHEMES if scheme.name == "nord")


class CellBackend(Backend[dict, str, list, int], TerminalBackend[tuple]):
    """A terminal: a paint is one row of cells, each a colour; ANSI colours stay native."""

    depth = TrueColourDepth

    def __init__(self, scheme: ColourScheme) -> None:
        self.scheme = scheme

    def theme(self, scheme: ColourScheme) -> dict:
        return {colour.name: value.native(self) for colour, value in scheme.colours.items()}

    def colour(self, colour: type[ThemeColour]) -> str:
        return self.scheme.colours[colour].native(self)

    def palette(self, palette: TerminalPalette) -> tuple:
        return tuple(colour.hex for colour in palette.ansi)

    def rgb(self, colour: Rgb) -> str:
        return colour.hex

    def ansi(self, colour: AnsiColour) -> str:
        return f"ansi_{colour.name}"

    def terminal_default(self) -> str:
        return "default"

    def _mixed(self, start: type[ThemeColour], end: type[ThemeColour], amount: float) -> str:
        if self.scheme.from_terminal:
            # Terminal colours cannot be blended; they step.
            return self.colour(start if amount < 0.5 else end)
        return Mix(start, end, amount).rgb(self.scheme).hex

    def paint_gradient(self, frame: Gradient, width: int) -> list:
        return [self._mixed(*frame.at((cell + 0.5) / width)) for cell in range(width)]

    def paint_mix(self, frame: Mix, width: int) -> list:
        return [self._mixed(frame.start, frame.end, frame.amount)] * width

    def paint_band(self, frame: Band, width: int) -> list:
        return [self.colour(frame.colour) if frame.covers((cell + 0.5) / width) else None
                for cell in range(width)]

    def paint_text(self, frame: TextFrame, width: int) -> list:
        return ["".join(character for character, _ in line)[:width] for line in frame.lines]


class CssBackend(Backend[str, str, str, str]):
    """A web view: no cells and no terminal colours; a paint is CSS for one element."""

    def __init__(self, scheme: ColourScheme) -> None:
        self.scheme = scheme

    def theme(self, scheme: ColourScheme) -> str:
        return ":root{" + "".join(f"--{colour.name}:{scheme.rgb(colour).hex};"
                                  for colour in scheme.colours) + "}"

    def colour(self, colour: type[ThemeColour]) -> str:
        return self.scheme.rgb(colour).hex

    def paint_gradient(self, frame: Gradient, selector: str) -> str:
        stops = ",".join(self.colour(stop) for stop in (*frame.stops, frame.stops[0]))
        return (f"{selector}{{background:linear-gradient(90deg,{stops});"
                f"background-size:100% 100%;background-position:{frame.offset * 100:.1f}% 0}}")

    def paint_mix(self, frame: Mix, selector: str) -> str:
        return f"{selector}{{color:{frame.rgb(self.scheme).hex}}}"

    def paint_band(self, frame: Band, selector: str) -> str:
        colour = self.colour(frame.colour)
        start, end = max(0.0, frame.start) * 100, min(1.0, frame.end) * 100
        return (f"{selector}{{background:linear-gradient(90deg,transparent {start:.1f}%,"
                f"{colour} {start:.1f}%,{colour} {end:.1f}%,transparent {end:.1f}%)}}")

    def paint_text(self, frame: TextFrame, selector: str) -> str:
        return "".join(f'<span style="color:{colour.hex}">{character}</span>' if colour else character
                       for line in frame.lines for character, colour in line)


@dataclass(eq=False)
class Target:
    """An element a frontend shows; records each paint."""

    backend: Backend
    where: object
    animation_visible: bool = True
    paints: list = field(default_factory=list)

    def repaint(self) -> None:
        self.paints.append(self.animation.frame().paint(self.backend, self.where))


class Timer:
    def __init__(self) -> None:
        self.time = 0.0
        self.intervals: list[float | None] = []

    def __call__(self) -> float:
        return self.time


def run(clock: AnimationClock, timer: Timer, seconds: float) -> None:
    while timer.intervals[-1] is not None and timer.time < seconds:
        timer.time += timer.intervals[-1]
        clock.tick()


def backends(scheme: ColourScheme) -> tuple[Backend, ...]:
    return CellBackend(scheme), CssBackend(scheme)


def test_both_backends_draw_a_scheme_through_the_same_interface():
    cells, css = backends(ANSI_DARK)
    assert cells.theme(ANSI_DARK)["primary"] == "ansi_blue"
    assert cells.palette(ANSI_DARK.terminal)[4] == ANSI_DARK.terminal.ansi[4].hex
    assert f"--primary:{ANSI_DARK.terminal.ansi[4].hex}" in css.theme(ANSI_DARK)
    assert CssBackend(NORD).colour(PrimaryColour) == "#88c0d0"


def test_one_clock_runs_a_fade_and_a_wipe_in_both_backends_and_stops_when_they_finish():
    timer = Timer()
    clock = AnimationClock(timer.intervals.append, timer)
    targets = []
    for backend, where in zip(backends(NORD), (20, ".message")):
        for effect in (NEW_MESSAGE.ending_at(SecondaryColour), TAB_WIPE):
            target = Target(backend, where)
            target.animation = clock.start(effect, target)
            targets.append(target)
    assert timer.intervals[-1] == 1 / TAB_WIPE.frames_per_second
    run(clock, timer, 2.0)
    assert timer.intervals[-1] is None and not clock.running
    cell_fade, cell_wipe, css_fade, css_wipe = targets
    # The fade ends on the role's colour, starting near the accent.
    accent, secondary = NORD.rgb(AccentColour).hex, NORD.rgb(SecondaryColour).hex
    assert cell_fade.paints[-1] == [secondary] * 20
    assert css_fade.paints[-1] == f".message{{color:{secondary}}}"
    assert cell_fade.paints[0][0] != secondary and css_fade.paints[0] != css_fade.paints[-1]
    assert accent != secondary
    # The wipe crosses the line once and leaves nothing.
    assert any(any(cell_wipe.paints[i]) for i in range(len(cell_wipe.paints) - 1))
    assert cell_wipe.paints[-1] == [None] * 20
    assert "transparent 100.0%" in css_wipe.paints[-1]
    # Each effect painted at its own rate.
    assert len(cell_fade.paints) <= NEW_MESSAGE.duration * NEW_MESSAGE.frames_per_second + 2


def test_a_hidden_target_is_not_painted_until_its_effect_finishes():
    timer = Timer()
    clock = AnimationClock(timer.intervals.append, timer)
    target = Target(CellBackend(NORD), 10, animation_visible=False)
    target.animation = clock.start(NEW_MESSAGE.ending_at(PrimaryColour), target)
    run(clock, timer, 1.0)
    assert len(target.paints) == 1  # its final frame only


def test_the_sweep_is_a_function_of_time_and_terminal_colours_step():
    timer = Timer()
    clock = AnimationClock(timer.intervals.append, timer)
    target = Target(CellBackend(ANSI_DARK), 9)
    target.animation = clock.start(ACTIVITY_SWEEP, target)
    timer.time = 0.25
    first = target.animation.frame().paint(target.backend, 9)
    timer.time = 1.25
    assert target.animation.frame().paint(target.backend, 9) == first
    assert set(first) <= {"ansi_blue", "ansi_green", "ansi_cyan"}
    clock.stop(target)
    assert timer.intervals[-1] is None


def test_animation_off_shows_final_frames_and_never_ticks():
    timer = Timer()
    clock = AnimationClock(timer.intervals.append, timer, enabled=False)
    target = Target(CssBackend(NORD), ".tab")
    target.animation = clock.start(TAB_WIPE, target)
    assert timer.intervals == [] and target.animation.frame() == TAB_WIPE.final


def test_a_text_effect_is_built_in_advance_and_played_by_both_backends():
    played = loading_splash("Loading history").build(NORD)
    assert isinstance(played, PlayedText) and played.duration <= 2.0 + 1 / 30
    final = played.final
    assert "".join(character for character, _ in final.lines[0]) == "Loading history"
    # The text ends in a gradient over the scheme's colours.
    colours = [colour for character, colour in final.lines[0] if character != " "]
    assert None not in colours and len(set(colours)) > 2
    cells, css = backends(NORD)
    assert final.paint(cells, 40) == ["Loading history"]
    assert final.paint(css, "#splash").count("<span") == len("Loadinghistory")
