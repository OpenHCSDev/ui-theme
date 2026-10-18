"""Colour schemes: what each semantic colour is in one theme.

Something drawn asks for a `ThemeColour` (primary, warning, muted, ...); the
active scheme supplies it. Every scheme states the eight core colours. It may
also state layer colours (surface, panel, boost) and element colours; where it
does not, each backend lays out its own surfaces.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any, ClassVar

from metaclass_registry import AutoRegisterMeta  # type: ignore[import-untyped]

from ui_theme.colour import Colour, PaletteSource, Rgb, TerminalOwnedPalette, TerminalPalette, require_terminal_palette

if TYPE_CHECKING:
    from ui_theme.backend import TerminalBackend


class ThemeColour(metaclass=AutoRegisterMeta):
    """A semantic colour; its `name` is the one every backend and scheme uses."""

    __registry_key__ = "name"
    __registry__: ClassVar[dict[str, type[ThemeColour]]]
    name: ClassVar[str | None] = None
    # Drawn behind content rather than as content (decides the terminal default).
    background: ClassVar[bool] = False

    @classmethod
    def members(cls) -> tuple[type[ThemeColour], ...]:
        return tuple(member for member in ThemeColour.__registry__.values() if issubclass(member, cls))

    @classmethod
    def rgb(cls, scheme: ColourScheme) -> Rgb:
        """This colour in 24 bits under `scheme`; a terminal colour is read from its palette."""
        return cls.resolve_rgb(lambda member: scheme.colours[member].rgb(
            scheme.terminal.resolve(require_terminal_palette), background=member.background))

    @classmethod
    def resolve_rgb(cls, read: Callable[[type[ThemeColour]], Rgb]) -> Rgb:
        """Resolve this declaration against the caller's already decoded palette."""
        return read(cls)


class CoreColour(ThemeColour):
    """A colour every scheme states."""


class LayerColour(ThemeColour):
    """A surface colour a scheme may state; otherwise the backend lays out its own."""

    background = True


class ForegroundColour(CoreColour):
    """Ordinary text."""

    name = "foreground"


class BackgroundColour(CoreColour):
    name = "background"
    background = True


class PrimaryColour(CoreColour):
    name = "primary"


class SecondaryColour(CoreColour):
    name = "secondary"


class AccentColour(CoreColour):
    name = "accent"


class SuccessColour(CoreColour):
    name = "success"


class WarningColour(CoreColour):
    name = "warning"


class BlockCursorBackgroundColour(ThemeColour):
    name = "block-cursor-background"
    background = True


class BlockCursorForegroundColour(ThemeColour):
    name = "block-cursor-foreground"


class ErrorColour(CoreColour):
    """Failures stay recognisably red in monochromatic wallpaper palettes."""

    name = "error"
    palette_colour: ClassVar[Rgb] = Rgb.parse("#e06c75")


class SurfaceColour(LayerColour):
    name = "surface"


class PanelColour(LayerColour):
    name = "panel"


class BoostColour(LayerColour):
    name = "boost"


class BlendColour(ThemeColour):
    """A colour no scheme states: the background `amount` of the way to the foreground.

    The same ratio steps lighter in a dark theme and darker in a light one.
    """

    amount: ClassVar[float]

    @classmethod
    def resolve_rgb(cls, read: Callable[[type[ThemeColour]], Rgb]) -> Rgb:
        return BackgroundColour.resolve_rgb(read).blend(ForegroundColour.resolve_rgb(read), cls.amount)


class MutedColour(BlendColour):
    """Secondary text: the foreground part of the way over the background.

    Terminal colours cannot be blended without their palette; a terminal
    backend that emits them natively dims the foreground instead.
    """

    name = "muted"
    amount = 0.6


class SurfaceHoverColour(BlendColour):
    """Raised surface behind hovered or focused project-search controls."""

    name = "surface-hover"
    amount = 0.12


class ToneColour(BlendColour):
    """A surface a slight step off the background that sets one screen area apart.

    The transcript stays on the background itself; every other area steps away from it.
    """

    background = True


class TurnBandColour(ToneColour):
    """A quiet separator surface between a transcript and its prompt."""

    name = "turn-band"
    amount = 0.08


class HeaderToneColour(ToneColour):
    """The tab bar along the top."""

    name = "tone-header"
    amount = 0.06


class SidebarToneColour(ToneColour):
    """The channel and thread sidebars."""

    name = "tone-sidebar"
    amount = 0.035


class AlternateRowToneColour(ToneColour):
    """Every other row of a sidebar list, one more step off the sidebar."""

    name = "tone-alternate-row"
    amount = 0.075


class PromptToneColour(ToneColour):
    """The prompt area under the transcript."""

    name = "tone-prompt"
    amount = 0.04


class FooterToneColour(ToneColour):
    """The key bar along the bottom."""

    name = "tone-footer"
    amount = 0.06


class TextStyle(Enum):
    """How an element's text is emphasised."""

    NONE = "none"
    REVERSE = "reverse"

    def native(self, backend: TerminalBackend[Any]) -> Any:
        """This text emphasis as a terminal backend emits it."""
        return backend.text_style(self)


@dataclass(frozen=True)
class ColourScheme:
    """One theme: its colours, whether it is dark, and the palette terminal colours come from.

    `elements` colours individual interface parts (a cursor, a selection, a
    border) by the part's design name; a backend applies the parts it has.
    """

    name: str
    dark: bool
    colours: Mapping[type[ThemeColour], Colour]
    terminal: PaletteSource = field(default_factory=TerminalOwnedPalette)
    elements: Mapping[str, Colour | TextStyle] = field(default_factory=dict)

    def __post_init__(self) -> None:
        missing = [colour.name for colour in CoreColour.members() if colour not in self.colours]
        if missing:
            raise ValueError(f"Scheme {self.name!r} does not state {', '.join(missing)}")
        derived = [colour.name for colour in self.colours
                   if not issubclass(colour, (CoreColour, LayerColour))]
        if derived:
            raise ValueError(f"Scheme {self.name!r} states derived colours: {', '.join(derived)}")

    @property
    def from_terminal(self) -> bool:
        """True when the scheme uses the terminal's own colours (an ANSI theme)."""
        return self.colours[BackgroundColour].from_terminal

    def rgb(self, colour: type[ThemeColour]) -> Rgb:
        return colour.rgb(self)


def scheme_of_palette(name: str, palette: TerminalPalette) -> ColourScheme:
    """Wallpaper accents as true colour, with the error role's own failure red."""
    slot = palette.ansi
    return ColourScheme(name, palette.dark, {
        ForegroundColour: palette.foreground, BackgroundColour: palette.background,
        PrimaryColour: slot[4], SecondaryColour: slot[6], AccentColour: slot[5],
        SuccessColour: slot[2], WarningColour: slot[3], ErrorColour: ErrorColour.palette_colour,
    }, palette)
