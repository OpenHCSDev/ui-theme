"""pywal's colour file, decoded once into a terminal palette and a scheme.

pywal (`wal -i`, `wal -R`) writes `colors.json` in its cache directory, in
place, and sends the same colours to every open terminal as OSC 4/10/11
sequences, so a scheme of terminal colours follows it without reading the
file. A true-colour scheme reads the file. The format is pywal's and is decoded
with optional checksum metadata written by pywal16. Colours still require
`#rrggbb` form; checksum metadata does not participate in the palette.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ui_theme.colour import Rgb, TerminalPalette
from ui_theme.scheme import ColourScheme, scheme_of_palette

COLOURS = tuple(f"color{index}" for index in range(16))
SPECIAL = ("background", "foreground", "cursor")


def _exact(value: Any, keys: tuple[str, ...], where: str,
           *, optional: tuple[str, ...] = ()) -> Mapping[str, Any]:
    if not isinstance(value, dict) or not set(keys) <= set(value) <= set(keys + optional):
        found = sorted(value) if isinstance(value, dict) else type(value).__name__
        raise ValueError(f"pywal's {where} requires keys {list(keys)}"
                         f" with optional {list(optional)}, not {found}")
    return value


@dataclass(frozen=True)
class WalFile:
    """`colors.json` as pywal writes it."""

    wallpaper: str
    alpha: str
    palette: TerminalPalette

    NAME = "colors.json"
    SCHEME = "wal"

    @staticmethod
    def directory(environment: Mapping[str, str]) -> Path:
        """pywal's cache directory: `PYWAL_CACHE_DIR`, else `~/.cache/wal`."""
        configured = environment.get("PYWAL_CACHE_DIR")
        return Path(configured) if configured else Path(environment["HOME"]) / ".cache" / "wal"

    @classmethod
    def decode(cls, data: Any) -> WalFile:
        top = _exact(data, ("wallpaper", "alpha", "special", "colors"), "file",
                     optional=("checksum",))
        special = _exact(top["special"], SPECIAL, "special")
        colours = _exact(top["colors"], COLOURS, "colors")
        for key in ("wallpaper", "alpha"):
            if not isinstance(top[key], str):
                raise ValueError(f"pywal's {key} is a string, not {top[key]!r}")
        background, foreground, cursor = (Rgb.parse(special[key]) for key in SPECIAL)
        return cls(top["wallpaper"], top["alpha"], TerminalPalette(
            background, foreground, cursor, tuple(Rgb.parse(colours[key]) for key in COLOURS)))

    @classmethod
    def read(cls, path: Path) -> WalFile:
        return cls.decode(json.loads(path.read_text(encoding="utf-8")))

    @property
    def scheme(self) -> ColourScheme:
        return scheme_of_palette(self.SCHEME, self.palette)
