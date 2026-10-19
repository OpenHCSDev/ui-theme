"""What a frontend implements to draw ui_theme's schemes and effects.

Every backend maps a scheme to its own theme type, a theme colour to its own
colour type, and each kind of effect frame to its own paint. A backend that is
not a terminal sees only 24-bit colours (`ColourScheme.rgb` reads terminal
colours from the scheme's palette).

Terminals add a capability, `TerminalBackend`: they can emit the terminal's own
colours natively (so ANSI schemes follow the terminal's palette live), they map
a terminal palette to their palette type, and they have a colour depth.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Generic, TypeVar

from ui_theme.colour import AnsiColour, Colour, Rgb, TerminalPalette
from ui_theme.depth import ColourDepth
from ui_theme.effects import Band, Gradient, Mix, TextFrame
from ui_theme.scheme import ColourScheme, TextStyle, ThemeColour

ThemeT = TypeVar("ThemeT")
ColourT = TypeVar("ColourT")
PaintT = TypeVar("PaintT")
TargetT = TypeVar("TargetT")
PaletteT = TypeVar("PaletteT")


class Backend(ABC, Generic[ThemeT, ColourT, PaintT, TargetT]):
    """A frontend's drawing of schemes and effects.

    `TargetT` is what a paint is made for: a width in cells, a widget's
    rectangle, a CSS selector.
    """

    @abstractmethod
    def theme(self, scheme: ColourScheme) -> ThemeT:
        """`scheme` as this frontend's theme."""

    @abstractmethod
    def colour(self, colour: type[ThemeColour]) -> ColourT:
        """`colour` under the active scheme."""

    @abstractmethod
    def paint_gradient(self, frame: Gradient, target: TargetT) -> PaintT: ...

    @abstractmethod
    def paint_mix(self, frame: Mix, target: TargetT) -> PaintT: ...

    @abstractmethod
    def paint_band(self, frame: Band, target: TargetT) -> PaintT: ...

    @abstractmethod
    def paint_text(self, frame: TextFrame, target: TargetT) -> PaintT: ...


class TerminalBackend(Generic[PaletteT]):
    """The terminal capability; a terminal frontend's backend mixes it in."""

    depth: type[ColourDepth]

    @abstractmethod
    def palette(self, palette: TerminalPalette) -> PaletteT:
        """`palette` as the palette this terminal maps ANSI colours to."""

    @abstractmethod
    def rgb(self, colour: Rgb) -> Any: ...

    @abstractmethod
    def ansi(self, colour: AnsiColour) -> Any: ...

    @abstractmethod
    def terminal_default(self) -> Any: ...

    @abstractmethod
    def text_style(self, style: TextStyle) -> Any: ...

    @abstractmethod
    def colour_variable(self, colour: Colour) -> str:
        """Render a declared colour as this frontend's theme variable."""
