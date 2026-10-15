"""Text effects from TerminalTextEffects, built in advance into `PlayedText`.

Building an effect does its path and gradient work up front (tens to hundreds
of milliseconds), so `TextEffect.build` belongs off the UI thread, in a worker
process. It reads each character's position, symbol and colour straight from
the effect's state, so no terminal output is produced or parsed back.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ui_theme.colour import Rgb
from ui_theme.effects import PlayedText, TextFrame
from ui_theme.scheme import AccentColour, ColourScheme, PrimaryColour, SecondaryColour, ThemeColour


@dataclass(frozen=True)
class TextEffect:
    """A TerminalTextEffects effect over `text`, finishing in the scheme's colours."""

    effect: str
    text: str
    stops: tuple[type[ThemeColour], ...]
    frames_per_second: float
    # The longest it may play; longer effects show every n-th frame.
    longest: float

    def build(self, scheme: ColourScheme) -> PlayedText:
        from importlib import import_module

        from terminaltexteffects.utils.graphics import Color, Gradient

        module = import_module(f"terminaltexteffects.effects.effect_{self.effect}")
        effect = module.get_effect_resources()[1](self.text)
        effect.terminal_config.frame_rate = 0
        # Preparation follows its input canvas, never a worker's terminal size.
        effect.terminal_config.ignore_terminal_dimensions = True
        effect.effect_config.final_gradient_stops = tuple(
            Color(scheme.rgb(stop).hex[1:]) for stop in self.stops)
        effect.effect_config.final_gradient_direction = Gradient.Direction.HORIZONTAL
        iterator = iter(effect)
        frames = [_text_frame(iterator.terminal) for _ in _advance(iterator)]
        step = max(1, -(-len(frames) // int(self.longest * self.frames_per_second)))
        kept = frames[step - 1::step]
        if kept[-1] is not frames[-1]:
            kept.append(frames[-1])
        return PlayedText(tuple(kept), self.frames_per_second)


def _advance(iterator: Any) -> Any:
    for _ in iterator:
        yield


def _text_frame(terminal: Any) -> TextFrame:
    canvas = terminal.canvas
    rows: list[list[tuple[str, Rgb | None]]] = [
        [(" ", None)] * canvas.right for _ in range(canvas.top)]
    for character in sorted(terminal.get_characters(), key=lambda c: c.layer):
        if not character.is_visible:
            continue
        coord = character.motion.current_coord
        if not (1 <= coord.row <= canvas.top and 1 <= coord.column <= canvas.right):
            continue
        visual = character.animation.current_character_visual
        colours = visual.colors
        colour = (Rgb.parse("#" + colours.fg_color.rgb_color)
                  if colours is not None and colours.fg_color is not None else None)
        rows[canvas.top - coord.row][coord.column - 1] = (visual.symbol, colour)
    return TextFrame(tuple(tuple(row) for row in rows))


def loading_splash(text: str) -> TextEffect:
    """The splash shown while history loads: the text swept into the theme's colours."""
    return TextEffect("sweep", text, (PrimaryColour, AccentColour, SecondaryColour),
                      frames_per_second=30, longest=2.0)
