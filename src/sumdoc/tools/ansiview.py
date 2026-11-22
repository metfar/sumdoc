#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#pylint:disable=W0301
#  
#  Copyright 2018- William Martinez Bas <metfar@gmail.com>
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
"""lessans: scrollable read-only viewer for ANSI SGR text with 24-bit colors.

Supports vertical and horizontal scrolling, search, and terminal resize.
Only SGR (colors/attributes) is interpreted: all other terminal escapes are
ignored, so an input file cannot execute arbitrary terminal commands.
""";

import argparse;
import os;
import re;
import select;
import shutil;
import signal;
import sys;
import termios;
import tty;
import unicodedata;
from dataclasses import dataclass;

try:
    from wcwidth import wcwidth as glyph_width;
except ImportError:
    def glyph_width(ch):
        if unicodedata.combining(ch):
            return 0;
        return 2 if unicodedata.east_asian_width(ch) in ('W', 'F') else 1;

ESC = '\x1b';
ANSI_RE = re.compile(r'\x1b\[[0-?]*[ -/]*[@-~]|\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)|\x1b.', re.DOTALL);
CSI_SGR = re.compile(r'^\x1b\[([0-9;:]*)m$');
BASIC_COLORS = ((0,0,0),(205,0,0),(0,205,0),(205,205,0),(0,0,238),(205,0,205),(0,205,205),(229,229,229),
                (127,127,127),(255,0,0),(0,255,0),(255,255,0),(92,92,255),(255,0,255),(0,255,255),(255,255,255));

@dataclass(frozen=True)
class Style:
    fg: object = None;
    bg: object = None;
    bold: bool = False;
    underline: bool = False;
    reverse: bool = False;

@dataclass(frozen=True)
class Cell:
    char: str;
    style: Style;
    continuation: bool = False;

def indexed_color(n):
    if n < 16:
        return BASIC_COLORS[n];
    if n < 232:
        v = n - 16;
        conv = (0, 95, 135, 175, 215, 255);
        return (conv[v // 36], conv[(v // 6) % 6], conv[v % 6]);
    g = 8 + 10 * (n - 232);
    return (g, g, g);

def sgr(style, values):
    fg, bg, bold, underline, reverse = style.fg, style.bg, style.bold, style.underline, style.reverse;
    args = [int(x) if x else 0 for x in values.replace(':',';').split(';')];
    i = 0;
    while i < len(args):
        code = args[i];
        if code == 0:
            fg, bg, bold, underline, reverse = None, None, False, False, False;
        elif code == 1:
            bold = True;
        elif code == 22:
            bold = False;
        elif code == 4:
            underline = True;
        elif code == 24:
            underline = False;
        elif code == 7:
            reverse = True;
        elif code == 27:
            reverse = False;
        elif code == 39:
            fg = None;
        elif code == 49:
            bg = None;
        elif 30 <= code <= 37 or 90 <= code <= 97:
            fg = indexed_color(code - 30 if code <= 37 else code - 90 + 8);
        elif 40 <= code <= 47 or 100 <= code <= 107:
            bg = indexed_color(code - 40 if code <= 47 else code - 100 + 8);
        elif code in (38, 48) and i + 1 < len(args):
            dest = 'fg' if code == 38 else 'bg';
            mode = args[i + 1];
            rgb = None;
            if mode == 2 and i + 4 < len(args):
                rgb = tuple(max(0, min(255, v)) for v in args[i+2:i+5]);
                i += 4;
            elif mode == 5 and i + 2 < len(args):
                rgb = indexed_color(max(0, min(255, args[i+2])));
                i += 2;
            if rgb is not None:
                if dest == 'fg':
                    fg = rgb;
                else:
                    bg = rgb;
        i += 1;
    return Style(fg, bg, bold, underline, reverse);

def parse_ansi(data):
    """Return lines of terminal display cells; ANSI escapes are zero-width.""";
    lines = [[]];
    style = Style();
    pos = 0;
    while pos < len(data):
        if data[pos] == ESC:
            match = ANSI_RE.match(data, pos);
            if match:
                sg = CSI_SGR.match(match.group());
                if sg:
                    style = sgr(style, sg.group(1));
                pos = match.end();
                continue;
            pos += 1;
            continue;
        ch = data[pos];
        pos += 1;
        if ch == '\n':
            lines.append([]);
            continue;
        if ch == '\r':
            continue;
        if ch == '\t':
            for _ in range(8 - len(lines[-1]) % 8):
                lines[-1].append(Cell(' ', style));
            continue;
        if unicodedata.category(ch) in ('Cc', 'Cf'):
            continue;
        w = glyph_width(ch);
        if w == 0:
            if lines[-1]:
                prev = lines[-1][-1];
                lines[-1][-1] = Cell(prev.char + ch, prev.style, prev.continuation);
            continue;
        if w < 0:
            continue;
        lines[-1].append(Cell(ch, style));
        if w == 2:
            lines[-1].append(Cell('', style, True));
    if lines and not lines[-1]:
        lines.pop();
    return lines or [[]];

def style_code(s):
    code = ['0'];
    if s.bold:
        code.append('1');
    if s.underline:
        code.append('4');
    if s.reverse:
        code.append('7');
    if s.fg is not None:
        code.extend(('38','2',str(s.fg[0]),str(s.fg[1]),str(s.fg[2])));
    if s.bg is not None:
        code.extend(('48','2',str(s.bg[0]),str(s.bg[1]),str(s.bg[2])));
    return ESC + '[' + ';'.join(code) + 'm';

def render_line(cells, left, width):
    """Render exactly width columns; avoid partial wide glyphs.""";
    output = [];
    old = None;
    col = left;
    right = left + width;
    while col < right:
        cell = cells[col] if col < len(cells) else Cell(' ', Style());
        if cell.continuation or (col + 1 < len(cells) and cells[col + 1].continuation and col + 1 >= right):
            cell = Cell(' ', cell.style);
        if cell.style != old:
            output.append(style_code(cell.style));
            old = cell.style;
        output.append(cell.char or ' ');
        if cell.char and col + 1 < len(cells) and cells[col + 1].continuation:
            col += 2;
        else:
            col += 1;
    output.append(ESC + '[0m');
    return ''.join(output);

def plain_text(lines):
    return [''.join(c.char for c in row if not c.continuation) for row in lines];

class Viewer:
    def __init__(self, lines, name, no_color=False):
        self.lines = lines;
        self.text = plain_text(lines);
        self.name = name;
        self.top = 0;
        self.left = 0;
        self.no_color = no_color;
        self.message = '';
        self.search = '';
        self.last_match = -1;
        self.running = True;

    def size(self):
        t = shutil.get_terminal_size((80, 24));
        return max(10, t.columns), max(3, t.lines);

    def draw(self):
        width, height = self.size();
        page = height - 1;
        self.top = max(0, min(self.top, max(0, len(self.lines) - page)));
        buffer = [ESC + '[H'];
        for y in range(page):
            row = self.lines[self.top + y] if self.top + y < len(self.lines) else [];
            if self.no_color:
                row = [Cell(c.char, Style(), c.continuation) for c in row];
            # Reserve last column: some terminals auto-wrap on the right edge.
            buffer.append(render_line(row, self.left, width - 1));
            buffer.append(ESC + '[K');
            if y + 1 < page:
                buffer.append('\r\n');
        status = f' {self.name}  lines {self.top+1}-{min(len(self.lines),self.top+page)}/{len(self.lines)}  col {self.left+1}  [q quit, / search, arrows/PgUp/PgDn] ';
        if self.message:
            status = self.message;
        status = status[:width-1].ljust(width-1);
        buffer.extend(('\r\n', ESC+'[0;7m', status, ESC+'[0m', ESC+'[K'));
        os.write(sys.stdout.fileno(), ''.join(buffer).encode('utf-8', 'replace'));

    def prompt(self, title):
        width, height = self.size();
        os.write(sys.stdout.fileno(), (f'{ESC}[{height};1H{ESC}[0;7m{title}{ESC}[0m{ESC}[K').encode());
        value = '';
        while True:
            key = read_key();
            if key in ('\r','\n'):
                return value;
            if key in ('\x1b', '\x03'):
                return None;
            if key in ('\x7f', '\b'):
                value = value[:-1];
            elif key and key.isprintable() and len(value) < 200:
                value += key;
            os.write(sys.stdout.fileno(), (f'{ESC}[{height};1H{ESC}[0;7m{title}{value[:max(0,width-len(title)-1)]}{ESC}[0m{ESC}[K').encode('utf-8'));

    def find_next(self, backwards=False):
        if not self.search:
            return;
        indices = range(self.top-1, -1, -1) if backwards else range(self.top+1, len(self.text));
        found = next((i for i in indices if self.search.casefold() in self.text[i].casefold()), None);
        if found is None:
            indices = range(len(self.text)-1, self.top-1, -1) if backwards else range(0, self.top+1);
            found = next((i for i in indices if self.search.casefold() in self.text[i].casefold()), None);
        if found is not None:
            self.top = found;
            self.message = '';
        else:
            self.message = 'Not found: ' + self.search;

    def handle(self, key):
        width, height = self.size();
        page = height - 1;
        self.message = '';
        if key in ('q', 'Q', '\x03'):
            self.running = False;
        elif key in ('j', '\x1b[B', '\r', '\n'):
            self.top += 1;
        elif key in ('k', '\x1b[A'):
            self.top -= 1;
        elif key in (' ', '\x1b[6~', '\x06'):
            self.top += page;
        elif key in ('b', '\x1b[5~', '\x02'):
            self.top -= page;
        elif key in ('h', '\x1b[D'):
            self.left = max(0, self.left-4);
        elif key in ('l', '\x1b[C'):
            self.left += 4;
        elif key in ('\x1b[1;5D',):
            self.left = max(0, self.left-(width-1));
        elif key in ('\x1b[1;5C',):
            self.left += width-1;
        elif key in ('g', '\x1b[H', '\x1b[1~'):
            self.top = 0;
        elif key in ('G', '\x1b[F', '\x1b[4~'):
            self.top = max(0, len(self.lines)-page);
        elif key == '0':
            self.left = 0;
        elif key == '/':
            query = self.prompt('/');
            if query:
                self.search = query;
                self.find_next();
        elif key == 'n':
            self.find_next();
        elif key == 'N':
            self.find_next(backwards=True);
        elif key == '?':
            self.message = 'j/k up/down | space/b page | h/l left/right | g/G ends | / search | n/N next/prev | q quit';
        self.top = max(0, min(self.top, max(0, len(self.lines)-page)));

def read_key():
    data = os.read(sys.stdin.fileno(), 1);
    if not data:
        return 'q';
    if data == b'\x1b':
        more = bytearray(data);
        while len(more) < 16 and select.select([sys.stdin], [], [], 0.025)[0]:
            c = os.read(sys.stdin.fileno(), 1);
            if not c:
                break;
            more.extend(c);
            if c.isalpha() or c == b'~':
                break;
        return more.decode('utf-8', 'replace');
    if data[0] >= 128:
        more = bytearray(data);
        for _ in range(3):
            if not select.select([sys.stdin], [], [], 0.03)[0]:
                break;
            more.extend(os.read(sys.stdin.fileno(), 1));
            try:
                return more.decode('utf-8');
            except UnicodeDecodeError:
                continue;
        return more.decode('utf-8', 'replace');
    return data.decode('latin-1');

def run_viewer(lines, name, no_color=False):
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        raise RuntimeError('Interactive mode requires a TTY; use --plain for a pipe.');
    fd = sys.stdin.fileno();
    old = termios.tcgetattr(fd);
    old_winch = signal.getsignal(signal.SIGWINCH);
    v = Viewer(lines, name, no_color=no_color);
    try:
        tty.setraw(fd);
        signal.signal(signal.SIGWINCH, lambda *_: None);
        os.write(sys.stdout.fileno(), (ESC+'[?1049h'+ESC+'[?25l'+ESC+'[2J').encode());
        while v.running:
            v.draw();
            v.handle(read_key());
    finally:
        os.write(sys.stdout.fileno(), (ESC+'[0m'+ESC+'[?25h'+ESC+'[?1049l').encode());
        termios.tcsetattr(fd, termios.TCSADRAIN, old);
        signal.signal(signal.SIGWINCH, old_winch);

def main():
    ap = argparse.ArgumentParser(description='Scrollable ANSI/true-color terminal viewer (less -R compatible for SGR).');
    ap.add_argument('file', nargs='?', default='-', help='ANSI/text file, or - for stdin');
    ap.add_argument('--plain', action='store_true', help='Print extracted text without ANSI (for pipelines)');
    ap.add_argument('--no-color', action='store_true', help='Display without ANSI colors');
    args = ap.parse_args();
    if args.file == '-':
        data = sys.stdin.read();
        name = '<stdin>';
    else:
        with open(args.file, 'r', encoding='utf-8', errors='replace') as stream:
            data = stream.read();
        name = os.path.basename(args.file);
    lines = parse_ansi(data);
    if args.plain:
        print('\n'.join(plain_text(lines)));
        return;
    try:
        run_viewer(lines, name, args.no_color);
    except RuntimeError as exc:
        ap.error(str(exc));


