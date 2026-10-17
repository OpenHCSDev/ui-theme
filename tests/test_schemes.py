"""Colour values, schemes, the catalog, pywal's file and colour depth."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

from ui_theme.catalog import DARK_PALETTE, LIGHT_PALETTE, SCHEMES
from ui_theme.colour import BLUE, TERMINAL_DEFAULT, Rgb
from ui_theme.scheme import (
    BackgroundColour, BlendColour, ColourScheme, CoreColour, ErrorColour, ForegroundColour, MutedColour,
    PrimaryColour, SecondaryColour,
)
from ui_theme.wal import WalFile

SRC = Path(__file__).parents[1] / "src"

WAL = {
    "wallpaper": "/wallpapers/moss.jpg",
    "alpha": "100",
    "special": {"background": "#0b0b0d", "foreground": "#c3c3c3", "cursor": "#c3c3c3"},
    "colors": {f"color{index}": f"#{index:02x}{index:02x}{index:02x}" for index in range(16)},
}


def test_the_package_imports_no_ui_toolkit_and_nothing_of_comms():
    code = (
        "import sys, pkgutil, importlib, ui_theme\n"
        "for module in pkgutil.walk_packages(ui_theme.__path__, 'ui_theme.'):\n"
        "    importlib.import_module(module.name)\n"
        "from ui_theme.catalog import SCHEMES\n"
        "from ui_theme.splash import loading_splash\n"
        "loading_splash('toad').build(SCHEMES[0])\n"
        "bad = sorted(name for name in sys.modules if name.split('.')[0] in "
        "('toad', 'textual', 'rich', 'agent_comms', 'PyQt6', 'PySide6'))\n"
        "print(','.join(bad))\n"
    )
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True,
                            check=True, env={"PYTHONPATH": ":".join([str(SRC), *sys.path])})
    assert result.stdout.strip() == ""


def test_wal_file_preserves_accents_and_uses_the_error_role_red(tmp_path):
    path = tmp_path / WalFile.NAME
    path.write_text(json.dumps(WAL))
    scheme = WalFile.read(path).scheme
    assert scheme.name == "wal" and scheme.dark and not scheme.from_terminal
    assert scheme.rgb(BackgroundColour) == Rgb(0x0b, 0x0b, 0x0d)
    assert (scheme.rgb(PrimaryColour), scheme.rgb(SecondaryColour), scheme.rgb(ErrorColour)) == (
        Rgb(4, 4, 4), Rgb(6, 6, 6), Rgb(0xe0, 0x6c, 0x75))
    assert scheme.terminal.ansi[1] == Rgb(1, 1, 1)
    assert scheme.terminal.ansi[15] == Rgb(15, 15, 15)


def test_wal_file_reads_pywal16_checksum_metadata_without_changing_the_palette(tmp_path):
    path = tmp_path / WalFile.NAME
    path.write_text(json.dumps({**WAL, "checksum": "0123456789abcdef0123456789abcdef"}))
    assert WalFile.read(path) == WalFile.decode(WAL)


@pytest.mark.parametrize("missing", WAL)
def test_wal_file_still_requires_palette_fields_with_checksum_metadata(missing):
    data = {**WAL, "checksum": "0123456789abcdef0123456789abcdef"}
    del data[missing]
    with pytest.raises(ValueError):
        WalFile.decode(data)


@pytest.mark.parametrize("change", [
    {"unknown": "x"},
    {"special": {**WAL["special"], "cursor": "red"}},
    {"special": {**WAL["special"], "extra": "#000000"}},
    {"colors": {**WAL["colors"], "color0": "#00000"}},
    {"alpha": 100},
])
@pytest.mark.parametrize("metadata", [{}, {"checksum": "0123456789abcdef0123456789abcdef"}])
def test_wal_file_rejects_what_pywal_does_not_write(change, metadata):
    with pytest.raises(ValueError):
        WalFile.decode({**WAL, **metadata, **change})


def test_wal_directory_honours_pywal_cache_dir():
    assert str(WalFile.directory({"HOME": "/h"})) == "/h/.cache/wal"
    assert str(WalFile.directory({"HOME": "/h", "PYWAL_CACHE_DIR": "/w"})) == "/w"


@pytest.mark.parametrize("environment, depth", [
    ({"TERM": "st-256color", "COLORTERM": "truecolor"}, "truecolor"),
    ({"TERM": "xterm-256color"}, "256"),
    ({"TERM": "xterm-direct"}, "truecolor"),
    ({"TERM": "linux"}, "standard"),
    ({"TERM": "dumb"}, "standard"),
])
def test_colour_depth_of_terminal(environment, depth):
    # terminfo is set up once per process, so each terminal is asked in its own.
    code = ("import json, sys; from ui_theme.depth import ColourDepth; "
            "print(ColourDepth.of_terminal(json.loads(sys.argv[1])).name)")
    result = subprocess.run([sys.executable, "-c", code, json.dumps(environment)],
                            capture_output=True, text=True, check=True,
                            env={"PYTHONPATH": ":".join([str(SRC), *sys.path])})
    assert result.stdout.strip() == depth


def test_every_scheme_answers_every_core_and_derived_colour_in_24_bits():
    names = [scheme.name for scheme in SCHEMES]
    assert len(names) == len(set(names)) == 21
    for scheme in SCHEMES:
        for colour in CoreColour.members():
            assert isinstance(scheme.rgb(colour), Rgb)
        for colour in BlendColour.members():
            assert scheme.rgb(colour) == scheme.rgb(BackgroundColour).blend(scheme.rgb(ForegroundColour), colour.amount)
        assert scheme.terminal is (DARK_PALETTE if scheme.dark else LIGHT_PALETTE)


def test_terminal_colours_are_read_from_the_palette_for_backends_that_are_not_terminals():
    ansi_dark = next(scheme for scheme in SCHEMES if scheme.name == "ansi-dark")
    assert ansi_dark.from_terminal
    assert ansi_dark.colours[PrimaryColour] is BLUE
    assert ansi_dark.rgb(PrimaryColour) == DARK_PALETTE.ansi[4]
    assert ansi_dark.colours[ForegroundColour] is TERMINAL_DEFAULT
    assert ansi_dark.rgb(ForegroundColour) == DARK_PALETTE.foreground
    assert ansi_dark.rgb(BackgroundColour) == DARK_PALETTE.background
    muted = ansi_dark.rgb(MutedColour)
    assert muted == DARK_PALETTE.background.blend(DARK_PALETTE.foreground, MutedColour.amount)


def test_a_scheme_must_state_every_core_colour_and_no_derived_one():
    colours = dict(next(iter(SCHEMES)).colours)
    del colours[ErrorColour]
    with pytest.raises(ValueError, match="error"):
        ColourScheme("x", True, colours, DARK_PALETTE)
    with pytest.raises(ValueError, match="muted"):
        ColourScheme("x", True, {**SCHEMES[0].colours, MutedColour: Rgb(1, 1, 1)}, DARK_PALETTE)

