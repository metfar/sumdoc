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
"""Hybrid text/graphics terminal renderer for SUMDOC OCR images.""";
import math;
from collections import Counter;
from PIL import Image;

DOTS = ((0, 0, 0x01), (0, 1, 0x02), (0, 2, 0x04), (0, 3, 0x40),
        (1, 0, 0x08), (1, 1, 0x10), (1, 2, 0x20), (1, 3, 0x80));

def get_words(path, psm, lang, pytesseract):
    from pytesseract import Output;
    data = pytesseract.image_to_data(str(path), lang=lang,
                                      config=f'--oem 1 --psm {psm}', output_type=Output.DICT);
    words = [];
    for i, value in enumerate(data['text']):
        value = value.strip();
        if not value:
            continue;
        words.append(dict(text=value, x=int(data['left'][i]), y=int(data['top'][i]),
                          w=int(data['width'][i]), h=int(data['height'][i]),
                          conf=float(data['conf'][i])));
    return words;


def background_color(image):
    thumb = image.resize((96, 64));
    colors = [tuple((v // 16) * 16 for v in pix) for pix in thumb.get_flattened_data()];
    return Counter(colors).most_common(1)[0][0];

def sample_foreground(image, box, fallback=(230, 230, 230)):
    """Choose a foreground color with maximum contrast to the local background.""";
    x, y, w, h = box;
    width, height = image.size;
    x0 = max(0, min(width - 1, int(x)));
    y0 = max(0, min(height - 1, int(y)));
    x1 = max(x0 + 1, min(width, int(x + w)));
    y1 = max(y0 + 1, min(height, int(y + h)));
    colors = image.crop((x0, y0, x1, y1)).resize((min(64, x1-x0), min(32, y1-y0))).get_flattened_data();
    back = background_color(image);
    candidates = [c for c in colors if sum((int(c[k])-back[k])**2 for k in range(3)) > 1600];
    if not candidates:
        return fallback;
    return tuple(int(sorted(c[k] for c in candidates)[len(candidates)//2]) for k in range(3));

def ansi_format(grid, fg, bg, color):
    if not color:
        return '\n'.join(''.join(line) for line in grid) + '\n';
    lines = [];
    for y, line in enumerate(grid):
        last = ''.join(line);
        out = [];
        current = None;
        for x, c in enumerate(line[:len(last)]):
            state = (fg[y][x], bg[y][x]);
            if state != current:
                front, back = state;
                out.append(f'\033[38;2;{front[0]};{front[1]};{front[2]}m');
                out.append(f'\033[48;2;{back[0]};{back[1]};{back[2]}m');
                current = state;
            out.append(c);
        out.append('\033[0m');
        lines.append(''.join(out));
    return '\n'.join(lines) + '\n';

def render(image, words, cols, aspect, threshold, confidence, visual=True, color=False):
    width, height = image.size;
    rows = max(1, round(cols * height / width / aspect));
    back = background_color(image);
    small = image.resize((cols * 2, rows * 4), Image.Resampling.BOX).convert('RGB');
    cell_colors = image.resize((cols, rows), Image.Resampling.BOX).convert('RGB');
    pixels = small.load();
    grid = [[' ' for _ in range(cols)] for _ in range(rows)];
    fg = [[(230, 230, 230) for _ in range(cols)] for _ in range(rows)];
    bg = [[back for _ in range(cols)] for _ in range(rows)];
    if visual:
      for row in range(rows):
        for col in range(cols):
            mask = 0;
            for dx, dy, bit in DOTS:
                rgb = pixels[col * 2 + dx, row * 4 + dy];
                distance = math.sqrt(sum((int(rgb[i]) - back[i]) ** 2 for i in range(3)));
                if distance >= threshold:
                    mask |= bit;
            if mask:
                grid[row][col] = chr(0x2800 + mask);
                if color:
                    color_samples = [];
                    for dx, dy, bit in DOTS:
                        if mask & bit:
                            color_samples.append(pixels[col * 2 + dx, row * 4 + dy]);
                    fg[row][col] = tuple(sum(c[k] for c in color_samples)//len(color_samples) for k in range(3));
            if color:
                # Preserve the original background even under foreground braille dots.
                bg[row][col] = cell_colors.getpixel((col, row));
    # Protect OCR regions from graphic noise, including the space between glyphs.
    valid = [w for w in words if w['conf'] >= confidence];
    for w in valid:
        x0 = max(0, int(w['x'] / width * cols));
        x1 = min(cols, math.ceil((w['x'] + w['w']) / width * cols));
        y0 = max(0, int(w['y'] / height * rows));
        y1 = min(rows, math.ceil((w['y'] + w['h']) / height * rows));
        for y in range(max(0, y0 - 1), min(rows, y1 + 1)):
            for x in range(max(0, x0 - 1), min(cols, x1 + 1)):
                grid[y][x] = ' ';
                fg[y][x] = (230, 230, 230);
                bg[y][x] = cell_colors.getpixel((x, y)) if color else back;
    # Place real, selectable Unicode text, not glyphs reconstructed from dots.
    valid.sort(key=lambda w: (w['y'] // max(1, height // rows), w['x']));
    for w in valid:
        row = max(0, min(rows - 1, round((w['y'] + w['h'] / 2) / height * rows)));
        col = max(0, min(cols - 1, round(w['x'] / width * cols)));
        txt = w['text'];
        # Preserve word integrity: move left when a scaled word would be clipped.
        if len(txt) > cols:
            continue;
        col = min(col, cols - len(txt));
        if any(grid[row][i].isascii() and grid[row][i] not in (' ',) for i in range(col, col + len(txt))):
            free = next((start for start in range(max(0, col - 3), min(cols - len(txt) + 1, col + 5))
                         if all(grid[row][k] == ' ' or not grid[row][k].isascii()
                                for k in range(start, start + len(txt)))), None);
            if free is None:
                continue;
            col = free;
        word_color = sample_foreground(image, (w['x'], w['y'], w['w'], w['h']));
        for i, char in enumerate(txt):
            grid[row][col + i] = char;
            fg[row][col + i] = word_color;
            bg[row][col + i] = cell_colors.getpixel((col + i, row)) if color else back;
    return ansi_format(grid, fg, bg, color);

