"""Colour schemes: what each semantic colour is in one theme.

Something drawn asks for a `ThemeColour` (primary, warning, muted, ...); the
active scheme supplies it. Every scheme states the eight core colours. It may
also state layer colours (surface, panel, boost) and element colours; where it
does not, each backend lays out its own surfaces.
"""

from __future__ import annotations

from abc import abstractmethod
from collections.abc import Callable, Mapping
from functools import cached_property
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, ClassVar, Self, cast

from metaclass_registry import AutoRegisterMeta  # type: ignore[import-untyped]

from ui_theme.colour import (
    Colour,
    PaletteSource,
    Rgb,
    TerminalOwnedPalette,
    TerminalPalette,
    ThemeValue,
    require_terminal_palette,
)

if TYPE_CHECKING:
    from ui_theme.backend import TerminalBackend


class ThemePart:
    """A declared interface part owns its variable name."""

    name: ClassVar[str]


class ThemeColour(ThemePart, metaclass=AutoRegisterMeta):
    """A semantic colour; its `name` is the one every backend and scheme uses."""

    __registry_key__ = "name"
    __registry__: ClassVar[dict[str, type[ThemeColour]]]
    # Drawn behind content rather than as content (decides the terminal default).
    background: ClassVar[bool] = False

    @classmethod
    def members(cls) -> tuple[type[Self], ...]:
        return tuple(member for member in ThemeColour.__registry__.values() if issubclass(member, cls))

    @classmethod
    def rgb(cls, scheme: ColourScheme) -> Rgb:
        """This colour in 24 bits under `scheme`, which keeps what it resolved."""
        return scheme.rgb(cls)

    @classmethod
    def resolved_in(cls, scheme: ColourScheme) -> Rgb:
        """This colour resolved afresh: a terminal colour is read from its palette, a blend
        searched for its tier."""
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


class ElementColour(ThemeColour):
    """A declared interface part; an unstated ordinary element has no value."""

    @classmethod
    def value(cls, scheme: ColourScheme) -> Colour:
        return cast(Colour, scheme.elements[cls])

    @classmethod
    def rgb(cls, scheme: ColourScheme) -> Rgb:
        return cls.value(scheme).rgb(scheme.terminal.resolve(require_terminal_palette),
                                     background=cls.background)


class DerivedElementColour(ElementColour):
    """A part whose declaration supplies its value when a scheme leaves it unstated."""

    @classmethod
    def value(cls, scheme: ColourScheme) -> Colour:
        return super().value(scheme) if cls in scheme.elements else cls.derive(scheme)

    @classmethod
    def derive(cls, scheme: ColourScheme) -> Colour:
        raise NotImplementedError


class BlockCursorBackgroundColour(DerivedElementColour):
    name = "block-cursor-background"
    background = True

    @classmethod
    def derive(cls, scheme: ColourScheme) -> Colour:
        return scheme.colours[PrimaryColour]


class BlockCursorForegroundColour(DerivedElementColour):
    name = "block-cursor-foreground"

    @classmethod
    def derive(cls, scheme: ColourScheme) -> Rgb:
        # The cursor's existing 87% ink at eight-bit colour precision.
        return BlockCursorBackgroundColour.rgb(scheme).contrast_text(0xDD / 255)


class FooterKeyForegroundColour(ElementColour):
    name = "footer-key-foreground"


class InputSelectionBackgroundColour(ElementColour):
    name = "input-selection-background"
    background = True


class ButtonForegroundColour(ElementColour):
    name = "button-color-foreground"


class InputCursorForegroundColour(ElementColour):
    name = "input-cursor-foreground"


class InputCursorBackgroundColour(ElementColour):
    name = "input-cursor-background"
    background = True


class BorderColour(ElementColour):
    name = "border"


class BlurredBorderColour(ElementColour):
    name = "border-blurred"


class FooterBackgroundColour(ElementColour):
    name = "footer-background"
    background = True


class ForegroundMutedColour(ElementColour):
    name = "foreground-muted"


class FooterDescriptionForegroundColour(ElementColour):
    name = "footer-description-foreground"


class AnsiBackgroundColour(ElementColour):
    name = "ansi-background"
    background = True


class AnsiForegroundColour(ElementColour):
    name = "ansi-foreground"


class InputSelectionForegroundColour(ElementColour):
    name = "input-selection-foreground"


class ScreenSelectionBackgroundColour(ElementColour):
    name = "screen-selection-background"
    background = True


class ScreenSelectionForegroundColour(ElementColour):
    name = "screen-selection-foreground"


class ScrollbarColour(ElementColour):
    name = "scrollbar"


class ScrollbarHoverColour(ElementColour):
    name = "scrollbar-hover"


class ScrollbarActiveColour(ElementColour):
    name = "scrollbar-active"


class ScrollbarBackgroundColour(ElementColour):
    name = "scrollbar-background"
    background = True


class ScrollbarCornerColour(ElementColour):
    name = "scrollbar-corner-color"
    background = True


class ScrollbarBackgroundHoverColour(ElementColour):
    name = "scrollbar-background-hover"
    background = True


class ScrollbarBackgroundActiveColour(ElementColour):
    name = "scrollbar-background-active"
    background = True


class BlockHoverBackgroundColour(ElementColour):
    name = "block-hover-background"
    background = True


class ThemeTextStyle(ThemePart):
    """A declared text-emphasis part, rather than a colour."""


class BlockCursorTextStyle(ThemeTextStyle):
    name = "block-cursor-text-style"


class InputCursorTextStyle(ThemeTextStyle):
    name = "input-cursor-text-style"


class ButtonFocusTextStyle(ThemeTextStyle):
    name = "button-focus-text-style"


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
    """A colour no scheme states: a point on the way from the background to the foreground.

    Each member answers how far along the way it sits, so the same declaration steps
    lighter in a dark theme and darker in a light one. Members state what they must
    look like (a lightness step, a readable contrast), not a share of the way: a fixed
    share shrinks to nothing in a scheme whose foreground is close to its background.
    """

    @classmethod
    def resolve_rgb(cls, read: Callable[[type[ThemeColour]], Rgb]) -> Rgb:
        background, foreground = BackgroundColour.resolve_rgb(read), ForegroundColour.resolve_rgb(read)
        return background.blend(foreground, cls.blend_amount(background, foreground, read))

    @classmethod
    @abstractmethod
    def blend_amount(cls, background: Rgb, foreground: Rgb, read: Callable[[type[ThemeColour]], Rgb]) -> float:
        """How far from `background` toward `foreground` this colour sits, 0 to 1."""

    @staticmethod
    def first_amount(background: Rgb, foreground: Rgb, reaches: Callable[[Rgb], bool], least: float = 0.0) -> float:
        """The smallest amount from `least` up whose blend `reaches` its target; the
        foreground itself (1) when no blend does. `reaches` holds more as the amount grows."""
        if reaches(background.blend(foreground, least)):
            return least
        if not reaches(foreground):
            return 1.0
        low, high = least, 1.0
        for _ in range(24):
            middle = (low + high) / 2
            low, high = (low, middle) if reaches(background.blend(foreground, middle)) else (middle, high)
        return high


# Areas that touch (the page and a sidebar, a sidebar and its alternate rows, a row and its
# hover) differ by at least this much CIELAB lightness. A just-noticeable difference is about
# 2 in ideal viewing. Daylight reflected off a phone's glass washes out dark tones most, which
# is where a dark theme's surfaces sit (L* 5 to 25), so tiers keep three times that: still a
# separate surface at a glance outdoors.
TIER_GAP = 6.0


class ToneColour(BlendColour):
    """A surface a visible step off the background that sets one screen area apart.

    The transcript stays on the background itself; every other area is a tier further
    toward the foreground than the surfaces it sits on or beside (`over`): at least
    `TIER_GAP` of CIELAB lightness past the furthest of them.
    """

    background = True
    over: ClassVar[tuple[type[ThemeColour], ...]] = ()
    # A state raised over its surface (hovered, focused, the open tab), not an area: the item
    # on it is the one in focus and draws in the foreground, so secondary text is not read there.
    raised: ClassVar[bool] = False

    @classmethod
    def blend_amount(cls, background: Rgb, foreground: Rgb, read: Callable[[type[ThemeColour]], Rgb]) -> float:
        start = background.lightness
        reach = max((abs(surface.resolve_rgb(read).lightness - start) + TIER_GAP for surface in cls.over),
                    default=TIER_GAP)
        return cls.first_amount(background, foreground, lambda colour: abs(colour.lightness - start) >= reach)


class SidebarToneColour(ToneColour):
    """The channel and thread sidebars, beside the page."""

    name = "tone-sidebar"


class PromptToneColour(ToneColour):
    """The prompt area under the transcript."""

    name = "tone-prompt"


class AlternateRowToneColour(ToneColour):
    """Every other row of a sidebar list, one tier off the sidebar."""

    name = "tone-alternate-row"
    over = (SidebarToneColour,)


class HeaderToneColour(ToneColour):
    """The tab bar along the top, one tier off the sidebar and the page it sits above."""

    name = "tone-header"
    over = (SidebarToneColour,)


class FooterToneColour(ToneColour):
    """The key bar along the bottom, one tier off the prompt it sits under."""

    name = "tone-footer"
    over = (PromptToneColour,)


class TurnBandColour(ToneColour):
    """A quiet separator surface between a transcript and its prompt, one tier off the prompt."""

    name = "turn-band"
    over = (PromptToneColour,)


class InputToneColour(ToneColour):
    """The field a reader types into: one tier off the prompt area and the band of delivery and
    queue lines above it, so the box to type in is never the same surface as either."""

    name = "tone-input"
    over = (PromptToneColour, TurnBandColour)


class FloatToneColour(ToneColour):
    """A panel floating over the screen (a menu, a notice): one tier off the page, sidebars
    and prompt it opens over, so it reads as lifted off them."""

    name = "tone-float"
    over = (SidebarToneColour, PromptToneColour)


class SurfaceHoverColour(ToneColour):
    """A hovered or focused control, raised one tier off the rows and bars it is drawn over."""

    name = "surface-hover"
    over = (AlternateRowToneColour, HeaderToneColour, FooterToneColour)
    raised = True


class FloatHoverToneColour(ToneColour):
    """A hovered or focused item inside a floating panel, one tier off the panel."""

    name = "tone-float-hover"
    over = (FloatToneColour,)
    raised = True


class SelectedTabToneColour(ToneColour):
    """The open tab, raised one tier off the tab bar."""

    name = "tone-selected-tab"
    over = (HeaderToneColour,)
    raised = True


class TextBlendColour(BlendColour):
    """Text the foreground part of the way over the background, kept readable.

    It sits at least `least` of the way, and further toward the foreground until it reads
    at `minimum_contrast` on the background and on every area tone, as far as the foreground
    itself reads there. A raised tone (a hover, the open tab) does not hold it back.
    """

    least: ClassVar[float]
    minimum_contrast: ClassVar[float] = 4.5

    @classmethod
    def resting_surfaces(cls) -> tuple[type[ThemeColour], ...]:
        """The surfaces text is read on: the page and every area tone, none of the raised ones."""
        return (BackgroundColour, *(tone for tone in ToneColour.members() if not tone.raised))

    @classmethod
    def blend_amount(cls, background: Rgb, foreground: Rgb, read: Callable[[type[ThemeColour]], Rgb]) -> float:
        floors = {surface: min(cls.minimum_contrast, foreground.contrast(surface))
                  for surface in (surface.resolve_rgb(read) for surface in cls.resting_surfaces())}
        return cls.first_amount(
            background, foreground,
            lambda colour: all(colour.contrast(surface) >= floor for surface, floor in floors.items()), cls.least)


class RuleColour(TextBlendColour):
    """A rule or divider line: as quiet as it can be while it still reads as a line on every
    surface (WCAG's 3:1 for parts of the interface that are not text)."""

    name = "rule"
    least = 0.0
    minimum_contrast = 3.0


class MutedColour(TextBlendColour):
    """Secondary text: the foreground part of the way over the background.

    Terminal colours cannot be blended without their palette; a terminal
    backend that emits them natively dims the foreground instead.
    """

    name = "muted"
    least = 0.6


class TextStyle(ThemeValue, Enum):
    """How an element's text is emphasised."""

    NONE = "none"
    REVERSE = "reverse"

    def variable[Palette](self, backend: TerminalBackend[Palette]) -> str:
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
    elements: Mapping[type[ThemePart], ThemeValue] = field(default_factory=dict)

    def __post_init__(self) -> None:
        missing = [colour.name for colour in CoreColour.members() if colour not in self.colours]
        if missing:
            raise ValueError(f"Scheme {self.name!r} does not state {', '.join(missing)}")
        derived = [colour.name for colour in self.colours
                   if not issubclass(colour, (CoreColour, LayerColour))]
        if derived:
            raise ValueError(f"Scheme {self.name!r} states derived colours: {', '.join(derived)}")

    @property
    def resolved_colours(self) -> Mapping[type[ThemeColour], Colour]:
        elements = self.resolved_elements
        return {**self.colours, **{member: cast(Colour, elements[member])
                                  for member in ElementColour.members() if member in elements}}

    @property
    def resolved_elements(self) -> Mapping[type[ThemePart], ThemeValue]:
        """Stated parts and the cursor declarations' own derivations; no generic fallback."""
        return {**self.elements,
                **{member: member.value(self) for member in DerivedElementColour.members()}}

    @property
    def from_terminal(self) -> bool:
        """True when the scheme uses the terminal's own colours (an ANSI theme)."""
        return self.colours[BackgroundColour].from_terminal

    def rgb(self, colour: type[ThemeColour]) -> Rgb:
        """`colour` under this scheme, resolved once: a scheme's colours are fixed, and resolving
        a blend searches for its tier (9,089 resolutions in one Qt scroll session, 2026-11-18).
        A scheme drawn in the terminal's own palette is read afresh, as the palette may arrive
        after the scheme does."""
        if self.from_terminal:
            return colour.resolved_in(self)
        kept = self.resolved_rgb
        if colour not in kept:
            kept[colour] = colour.resolved_in(self)
        return kept[colour]

    @cached_property
    def resolved_rgb(self) -> dict[type[ThemeColour], Rgb]:
        """The colours resolved so far under this scheme."""
        return {}


def scheme_of_palette(name: str, palette: TerminalPalette) -> ColourScheme:
    """Wallpaper accents as true colour, with the error role's own failure red."""
    slot = palette.ansi
    return ColourScheme(name, palette.dark, {
        ForegroundColour: palette.foreground, BackgroundColour: palette.background,
        PrimaryColour: slot[4], SecondaryColour: slot[6], AccentColour: slot[5],
        SuccessColour: slot[2], WarningColour: slot[3], ErrorColour: ErrorColour.palette_colour,
    }, palette)
