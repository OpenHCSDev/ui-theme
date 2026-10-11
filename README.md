# ui-theme

Colour meaning for any user interface, with no UI toolkit imported:

- `ui_theme.colour`: colour values (24-bit, a terminal's ANSI slots, the terminal default) and terminal palettes.
- `ui_theme.scheme`: semantic colours (`ThemeColour`) and colour schemes.
- `ui_theme.catalog`: the built-in schemes and default terminal palettes.
- `ui_theme.wal`: pywal's `colors.json`, decoded once into a palette and a scheme.
- `ui_theme.depth`: a terminal's colour depth (terminal backends only).
- `ui_theme.effects`: animated effects as functions of time over semantic colour.
- `ui_theme.splash`: TerminalTextEffects effects built in advance (run off the UI thread).
- `ui_theme.clock`: one animation clock for every running effect.
- `ui_theme.backend`: what a frontend implements (`Backend`, plus `TerminalBackend` for terminals).

A frontend writes one backend adapter. Toad's Textual adapter lives in Toad.
