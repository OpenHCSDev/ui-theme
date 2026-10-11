"""Colour values a scheme states, and a terminal's palette.

A scheme states each of its colours as one of three kinds:

- `Rgb`: a 24-bit colour, optionally translucent;
- `AnsiColour`: one of a terminal's sixteen palette slots;
- `TerminalDefault`: the terminal's own default foreground or background.

The last two belong to terminals. A terminal backend can emit them natively, so
they follow the terminal's palette live (pywal recolours every open terminal).
Every other backend asks for `rgb()`, which reads them from the scheme's
`TerminalPalette`.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, replace
from typing import TYPE_CHECKING, Any, ClassVar

if TYPE_CHECKING:
    from ui_theme.backend import TerminalBackend


class Colour(ABC):
    """A colour a scheme states."""

    # True for colours the terminal supplies: they cannot be blended without
    # reading them from a palette.
    from_terminal: ClassVar[bool] = False

    @abstractmethod
    def rgb(self, palette: TerminalPalette, *, background: bool) -> Rgb:
        """This colour in 24 bits, reading terminal colours from `palette`."""

    @abstractmethod
    def native(self, backend: TerminalBackend[Any]) -> Any:
        """This colour as a terminal backend emits it."""


@dataclass(frozen=True)
class Rgb(Colour):
    """A 24-bit colour; its text form (pywal's) is `#rrggbb`."""

    red: int
    green: int
    blue: int
    alpha: float = 1.0

    @classmethod
    def parse(cls, text: str, alpha: float = 1.0) -> Rgb:
        if not (isinstance(text, str) and len(text) == 7 and text[0] == "#"):
            raise ValueError(f"Expected a #rrggbb colour, got {text!r}")
        value = int(text[1:], 16)
        return cls(value >> 16, (value >> 8) & 0xFF, value & 0xFF, alpha)

    @property
    def hex(self) -> str:
        return f"#{self.red:02x}{self.green:02x}{self.blue:02x}"

    @property
    def triple(self) -> tuple[int, int, int]:
        return self.red, self.green, self.blue

    @property
    def luminance(self) -> float:
        """Relative luminance (sRGB), 0 for black and 1 for white."""

        def linear(channel: int) -> float:
            value = channel / 255
            return value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4

        return 0.2126 * linear(self.red) + 0.7152 * linear(self.green) + 0.0722 * linear(self.blue)

    @property
    def brightness(self) -> float:
        """Perceived brightness, 0 for black and 1 for white."""
        return (299 * self.red + 587 * self.green + 114 * self.blue) / 255_000

    @property
    def inverse(self) -> Rgb:
        return Rgb(255 - self.red, 255 - self.green, 255 - self.blue, self.alpha)

    def with_alpha(self, alpha: float) -> Rgb:
        return replace(self, alpha=alpha)

    def blend(self, other: Rgb, amount: float, alpha: float | None = None) -> Rgb:
        """The colour `amount` of the way from this one to `other` (0 is this, 1 is other)."""
        if amount <= 0:
            return self
        if amount >= 1:
            return other
        return Rgb(
            int(self.red + (other.red - self.red) * amount),
            int(self.green + (other.green - self.green) * amount),
            int(self.blue + (other.blue - self.blue) * amount),
            self.alpha + (other.alpha - self.alpha) * amount if alpha is None else alpha,
        )

    def under(self, layer: Rgb) -> Rgb:
        """This colour with a translucent `layer` painted over it."""
        return self.blend(layer, layer.alpha, 1.0)

    def contrast_text(self, alpha: float) -> Rgb:
        """White or black, whichever reads on this colour, at `alpha`."""
        return (WHITE if self.brightness < 0.5 else BLACK).with_alpha(alpha)

    def rgb(self, palette: TerminalPalette, *, background: bool) -> Rgb:
        return self

    def native(self, backend: TerminalBackend[Any]) -> Any:
        return backend.rgb(self)


WHITE = Rgb(255, 255, 255)
BLACK = Rgb(0, 0, 0)


@dataclass(frozen=True)
class AnsiColour(Colour):
    """One of a terminal's sixteen palette colours."""

    index: int

    from_terminal = True
    NAMES: ClassVar[tuple[str, ...]] = (
        "black", "red", "green", "yellow", "blue", "magenta", "cyan", "white")

    def __post_init__(self) -> None:
        if not 0 <= self.index < 16:
            raise ValueError(f"A terminal has ANSI colours 0-15, not {self.index}")

    @property
    def name(self) -> str:
        base = self.NAMES[self.index % 8]
        return f"bright_{base}" if self.index >= 8 else base

    def rgb(self, palette: TerminalPalette, *, background: bool) -> Rgb:
        return palette.ansi[self.index]

    def native(self, backend: TerminalBackend[Any]) -> Any:
        return backend.ansi(self)


(BLACK_ANSI, RED, GREEN, YELLOW, BLUE, MAGENTA, CYAN, WHITE_ANSI,
 BRIGHT_BLACK, BRIGHT_RED, BRIGHT_GREEN, BRIGHT_YELLOW, BRIGHT_BLUE, BRIGHT_MAGENTA, BRIGHT_CYAN,
 BRIGHT_WHITE) = (AnsiColour(index) for index in range(16))


@dataclass(frozen=True)
class TerminalDefault(Colour):
    """The terminal's default colour: its foreground for text, its background behind it."""

    from_terminal = True

    def rgb(self, palette: TerminalPalette, *, background: bool) -> Rgb:
        return palette.background if background else palette.foreground

    def native(self, backend: TerminalBackend[Any]) -> Any:
        return backend.terminal_default()


TERMINAL_DEFAULT = TerminalDefault()


@dataclass(frozen=True)
class TerminalPalette:
    """A terminal's colours: ANSI 0–15, the default foreground and background, the cursor."""

    background: Rgb
    foreground: Rgb
    cursor: Rgb
    ansi: tuple[Rgb, ...]

    def __post_init__(self) -> None:
        if len(self.ansi) != 16:
            raise ValueError(f"A terminal palette has 16 ANSI colours, not {len(self.ansi)}")

    @classmethod
    def of(cls, background: str, foreground: str, *ansi: str) -> TerminalPalette:
        return cls(Rgb.parse(background), Rgb.parse(foreground), Rgb.parse(foreground),
                   tuple(map(Rgb.parse, ansi)))

    @property
    def dark(self) -> bool:
        return self.background.luminance < 0.5
