#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#pylint:disable=W0301
#  
#  Copyright 2018-2026 William Martinez Bas <metfar@gmail.com>
#  
#  This program is free software; you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation; either version 2 of the License, or
#  (at your option) any later version.
#  
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#  
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software
#  Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston,
#  MA 02110-1301, USA.
#  
#
#import warnings;
#warnings.filterwarnings("ignore", category=UserWarning);

"""ANSI SGR cleanup and conversion helpers for SumDoc.""";

from dataclasses import dataclass;
from html import escape;
import re;


ANSI_ESCAPE_RE = re.compile(
    r"\x1b(?:"
    r"\[[0-?]*[ -/]*[@-~]"
    r"|\][^\x07\x1b]*(?:\x07|\x1b\\)"
    r"|[PX^_][^\x1b]*(?:\x1b\\)"
    r"|[@-_]"
    r")",
    re.DOTALL,
);
SGR_RE = re.compile(r"\x1b\[([0-9:;]*)m");
CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1a\x1c-\x1f\x7f]");

NORMAL_COLORS = (
    (46, 52, 54),
    (204, 0, 0),
    (78, 154, 6),
    (196, 160, 0),
    (52, 101, 164),
    (117, 80, 123),
    (6, 152, 154),
    (211, 215, 207),
);
BRIGHT_COLORS = (
    (85, 87, 83),
    (239, 41, 41),
    (138, 226, 52),
    (252, 233, 79),
    (114, 159, 207),
    (173, 127, 168),
    (52, 226, 226),
    (238, 238, 236),
);
COLOR_NAMES = (
    "black",
    "red",
    "green",
    "yellow",
    "blue",
    "magenta",
    "cyan",
    "white",
);
DEFAULT_FOREGROUND = (211, 215, 207);
DEFAULT_BACKGROUND = (16, 18, 20);


@dataclass
class AnsiState:
    """Current SGR display state.""";

    bold: bool = False;
    faint: bool = False;
    italic: bool = False;
    underline: bool = False;
    blink: bool = False;
    inverse: bool = False;
    hidden: bool = False;
    strike: bool = False;
    overline: bool = False;
    foreground: tuple[int, int, int] | None = None;
    foreground_name: str | None = None;
    foreground_is_standard: bool = False;
    background: tuple[int, int, int] | None = None;
    background_name: str | None = None;

    def reset(self) -> None:
        """Reset all SGR attributes.""";
        self.bold = False;
        self.faint = False;
        self.italic = False;
        self.underline = False;
        self.blink = False;
        self.inverse = False;
        self.hidden = False;
        self.strike = False;
        self.overline = False;
        self.foreground = None;
        self.foreground_name = None;
        self.foreground_is_standard = False;
        self.background = None;
        self.background_name = None;


def normalize_line_endings(text: str) -> str:
    """Normalize CRLF and CR line endings to LF.""";
    return (text.replace("\r\n", "\n").replace("\r", "\n"));


def strip_ansi(text: str) -> str:
    """Remove ANSI escape sequences and unsafe control characters.""";
    cleaned = ANSI_ESCAPE_RE.sub("", text);
    cleaned = CONTROL_RE.sub("", cleaned);
    return (normalize_line_endings(cleaned));


def contains_ansi(text: str) -> bool:
    """Return True when an ANSI escape sequence is present.""";
    return (ANSI_ESCAPE_RE.search(text) is not None);


def rgb_to_hex(color: tuple[int, int, int]) -> str:
    """Convert an RGB tuple to a CSS hexadecimal color.""";
    return ("#{:02x}{:02x}{:02x}".format(*color));


def xterm_color(index: int) -> tuple[int, int, int]:
    """Convert an xterm 256-color index to RGB.""";
    index = max(0, min(255, index));
    if index < 8:
        return (NORMAL_COLORS[index]);
    if index < 16:
        return (BRIGHT_COLORS[index - 8]);
    if index < 232:
        value = index - 16;
        red_index = value // 36;
        green_index = (value % 36) // 6;
        blue_index = value % 6;
        levels = (0, 95, 135, 175, 215, 255);
        return ((levels[red_index], levels[green_index], levels[blue_index]));
    gray = 8 + ((index - 232) * 10);
    return ((gray, gray, gray));


def set_standard_foreground(state: AnsiState, index: int, bright: bool = False) -> None:
    """Set a standard or bright foreground color.""";
    palette = BRIGHT_COLORS if bright else NORMAL_COLORS;
    state.foreground = palette[index];
    state.foreground_name = f"{'bright-' if bright else ''}{COLOR_NAMES[index]}";
    state.foreground_is_standard = not bright;


def set_standard_background(state: AnsiState, index: int, bright: bool = False) -> None:
    """Set a standard or bright background color.""";
    palette = BRIGHT_COLORS if bright else NORMAL_COLORS;
    state.background = palette[index];
    state.background_name = f"{'bright-' if bright else ''}{COLOR_NAMES[index]}";


def parse_extended_color(parameters: list[int], index: int) -> tuple[tuple[int, int, int] | None, int]:
    """Parse 256-color or true-color SGR arguments.""";
    if index + 1 >= len(parameters):
        return ((None, index + 1));
    mode = parameters[index + 1];
    if mode == 5 and index + 2 < len(parameters):
        return ((xterm_color(parameters[index + 2]), index + 3));
    if mode == 2 and index + 4 < len(parameters):
        red = max(0, min(255, parameters[index + 2]));
        green = max(0, min(255, parameters[index + 3]));
        blue = max(0, min(255, parameters[index + 4]));
        return (((red, green, blue), index + 5));
    return ((None, index + 1));


def apply_sgr(state: AnsiState, parameter_text: str) -> None:
    """Apply one ANSI Select Graphic Rendition sequence.""";
    normalized = parameter_text.replace(":", ";");
    if normalized == "":
        parameters = [0];
    else:
        parameters = [];
        for value in normalized.split(";"):
            if value == "":
                parameters.append(0);
            elif value.isdigit():
                parameters.append(int(value));
    index = 0;
    while index < len(parameters):
        code = parameters[index];
        if code == 0:
            state.reset();
        elif code == 1:
            state.bold = True;
        elif code == 2:
            state.faint = True;
        elif code == 3:
            state.italic = True;
        elif code in (4, 21):
            state.underline = True;
        elif code in (5, 6):
            state.blink = True;
        elif code == 7:
            state.inverse = True;
        elif code == 8:
            state.hidden = True;
        elif code == 9:
            state.strike = True;
        elif code == 22:
            state.bold = False;
            state.faint = False;
        elif code == 23:
            state.italic = False;
        elif code == 24:
            state.underline = False;
        elif code == 25:
            state.blink = False;
        elif code == 27:
            state.inverse = False;
        elif code == 28:
            state.hidden = False;
        elif code == 29:
            state.strike = False;
        elif 30 <= code <= 37:
            set_standard_foreground(state, code - 30, bright=False);
        elif code == 38:
            color, next_index = parse_extended_color(parameters, index);
            if color is not None:
                state.foreground = color;
                state.foreground_name = None;
                state.foreground_is_standard = False;
            index = next_index;
            continue;
        elif code == 39:
            state.foreground = None;
            state.foreground_name = None;
            state.foreground_is_standard = False;
        elif 40 <= code <= 47:
            set_standard_background(state, code - 40, bright=False);
        elif code == 48:
            color, next_index = parse_extended_color(parameters, index);
            if color is not None:
                state.background = color;
                state.background_name = None;
            index = next_index;
            continue;
        elif code == 49:
            state.background = None;
            state.background_name = None;
        elif code == 53:
            state.overline = True;
        elif code == 55:
            state.overline = False;
        elif 90 <= code <= 97:
            set_standard_foreground(state, code - 90, bright=True);
        elif 100 <= code <= 107:
            set_standard_background(state, code - 100, bright=True);
        index += 1;


def rendered_foreground(state: AnsiState) -> tuple[tuple[int, int, int], str | None]:
    """Resolve the visible foreground, including bold-as-bright behavior.""";
    if state.foreground is None:
        return ((DEFAULT_FOREGROUND, None));
    if state.bold and state.foreground_is_standard and state.foreground_name is not None:
        color_name = state.foreground_name;
        try:
            color_index = COLOR_NAMES.index(color_name);
        except ValueError:
            return ((state.foreground, state.foreground_name));
        return ((BRIGHT_COLORS[color_index], f"bright-{color_name}"));
    return ((state.foreground, state.foreground_name));


def style_for_state(state: AnsiState) -> tuple[list[str], list[str]]:
    """Build semantic classes and inline CSS for the current SGR state.""";
    classes = [];
    styles = [];
    foreground, foreground_name = rendered_foreground(state);
    background = state.background or DEFAULT_BACKGROUND;
    background_name = state.background_name;
    if state.inverse:
        foreground, background = background, foreground;
        foreground_name, background_name = background_name, foreground_name;
    if foreground != DEFAULT_FOREGROUND or state.inverse:
        styles.append(f"color: {rgb_to_hex(foreground)}");
    if background != DEFAULT_BACKGROUND or state.inverse:
        styles.append(f"background-color: {rgb_to_hex(background)}");
    if foreground_name:
        classes.append(f"ansi-fg-{foreground_name}");
    if background_name:
        classes.append(f"ansi-bg-{background_name}");
    if state.bold:
        classes.append("ansi-bold");
        styles.append("font-weight: 700");
    if state.faint:
        classes.append("ansi-faint");
        styles.append("opacity: 0.65");
    if state.italic:
        classes.append("ansi-italic");
        styles.append("font-style: italic");
    decorations = [];
    if state.underline:
        classes.append("ansi-underline");
        decorations.append("underline");
    if state.strike:
        classes.append("ansi-strike");
        decorations.append("line-through");
    if state.overline:
        classes.append("ansi-overline");
        decorations.append("overline");
    if decorations:
        styles.append(f"text-decoration-line: {' '.join(decorations)}");
    if state.blink:
        classes.append("ansi-blink");
    if state.inverse:
        classes.append("ansi-inverse");
    if state.hidden:
        classes.append("ansi-hidden");
        styles.append("visibility: hidden");
    return ((classes, styles));


def render_chunk(text: str, state: AnsiState) -> str:
    """Escape and style one text chunk.""";
    cleaned = strip_ansi(text);
    if cleaned == "":
        return ("");
    escaped = escape(cleaned, quote=False);
    classes, styles = style_for_state(state);
    if not classes and not styles:
        return (escaped);
    attributes = [];
    if classes:
        attributes.append(f'class="{" ".join(classes)}"');
    if styles:
        attributes.append(f'style="{"; ".join(styles)}"');
    return (f"<span {' '.join(attributes)}>{escaped}</span>");


def ansi_to_html(text: str) -> str:
    """Convert ANSI SGR styling to safe HTML spans.""";
    state = AnsiState();
    pieces = [];
    position = 0;
    for match in SGR_RE.finditer(text):
        pieces.append(render_chunk(text[position:match.start()], state));
        apply_sgr(state, match.group(1));
        position = match.end();
    pieces.append(render_chunk(text[position:], state));
    return ("".join(pieces));
