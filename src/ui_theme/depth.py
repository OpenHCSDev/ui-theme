"""How many colours a host terminal shows: a fact of terminal backends only.

Decided once, at launch, from what the terminal advertises: `COLORTERM`, then
terminfo, then the suffix of `TERM`. Painted rows keep their terminal
sequences, so the depth cannot change while an app runs.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import ClassVar

try:
    import curses
except ModuleNotFoundError:
    # Python-for-Android and some embedded builds ship without `_curses`; a Qt or
    # non-terminal frontend never calls this path anyway, so the module import
    # must not fail just because terminfo is unavailable. The `of_terminal`
    # terminfo branch is skipped when `curses` is `None`, and the TERM suffix
    # heuristic answers.
    curses = None  # type: ignore[assignment]


class ColourDepth:
    # The terminal-standard name (COLORTERM, Rich, Textual) for this depth.
    name: ClassVar[str]

    @staticmethod
    def of_terminal(environment: Mapping[str, str]) -> type[ColourDepth]:
        if environment.get("COLORTERM", "").lower() in ("truecolor", "24bit"):
            return TrueColourDepth
        term = environment.get("TERM", "")
        if not term or term in ("dumb", "unknown"):
            return Ansi16Depth
        if curses is None:
            # No terminfo available: fall through to the TERM suffix heuristic.
            return Palette256Depth if term.endswith("256color") else Ansi16Depth
        try:
            curses.setupterm(term, -1)
        except curses.error:
            # No terminfo entry for TERM: the name is all the terminal said.
            pass
        else:
            if curses.tigetflag("Tc") == 1 or curses.tigetflag("RGB") == 1:
                return TrueColourDepth
            if curses.tigetnum("colors") >= 256:
                return Palette256Depth
        return Palette256Depth if term.endswith("256color") else Ansi16Depth


class TrueColourDepth(ColourDepth):
    name = "truecolor"


class Palette256Depth(ColourDepth):
    name = "256"


class Ansi16Depth(ColourDepth):
    name = "standard"
