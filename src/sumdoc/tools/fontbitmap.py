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

"""Bitmap font conversion and compact banner rendering for SumDoc.

SUM-FNT v1 is intentionally small and deterministic:

    8 bytes  magic: b"SUMFNT1\\0"
    1 byte   glyph width in pixels
    1 byte   glyph height in pixels
    2 bytes  first character code (little-endian)
    2 bytes  glyph count (little-endian)
    1 byte   bytes per bitmap row
    1 byte   flags (reserved, currently zero)
    ...      glyph rows, MSB first, contiguous by character code

The v1 character map is contiguous.  The initial SumDoc converter emits the
256 Latin-1 code points (0..255); a later format revision can add arbitrary
Unicode maps without changing the bitmap editor model.
""";

import argparse;
from dataclasses import dataclass;
from pathlib import Path;
import struct;
import sys;

from sumdoc.common import GlobalOptions, Reporter, check_writable, require_input_file, resolve_single_output, write_binary_output, write_text_output;


MAGIC = b"SUMFNT1\0";
HEADER = struct.Struct("<8sBBHHBB");


@dataclass(frozen=True)
class BitmapFont:
    width: int;
    height: int;
    first: int;
    glyphs: tuple[tuple[int, ...], ...];

    @property
    def count(self) -> int:
        return (len(self.glyphs));

    @property
    def bytes_per_row(self) -> int:
        return ((self.width + 7) // 8);

    def glyph(self, codepoint: int) -> tuple[int, ...]:
        index = codepoint - self.first;
        if index < 0 or index >= self.count:
            index = ord("?") - self.first;
        if index < 0 or index >= self.count:
            return (tuple(0 for _ in range(self.height)));
        return (self.glyphs[index]);


def _parse_cell(value: str) -> tuple[int, int]:
    normalized = value.lower().replace("×", "x");
    try:
        width_text, height_text = normalized.split("x", 1);
        width = int(width_text);
        height = int(height_text);
    except (ValueError, TypeError) as error:
        raise argparse.ArgumentTypeError("cell must be WIDTHxHEIGHT, for example 4x8 or 8x16") from error;
    if width < 1 or width > 32 or height < 1 or height > 64:
        raise argparse.ArgumentTypeError("cell dimensions must be between 1x1 and 32x64");
    return (width, height);


def encode_fnt(font: BitmapFont) -> bytes:
    bytes_per_row = font.bytes_per_row;
    header = HEADER.pack(MAGIC, font.width, font.height, font.first, font.count, bytes_per_row, 0);
    body = bytearray();
    max_row = (1 << font.width) - 1;
    for glyph in font.glyphs:
        if len(glyph) != font.height:
            raise ValueError("Every glyph must contain exactly font.height rows.");
        for row in glyph:
            if row < 0 or row > max_row:
                raise ValueError("A glyph row contains pixels outside the declared width.");
            shifted = row << (bytes_per_row * 8 - font.width);
            body.extend(shifted.to_bytes(bytes_per_row, "big"));
    return (header + bytes(body));


def decode_fnt(data: bytes) -> BitmapFont:
    if len(data) < HEADER.size:
        raise ValueError("FNT file is too short.");
    magic, width, height, first, count, bytes_per_row, flags = HEADER.unpack(data[:HEADER.size]);
    if magic != MAGIC:
        raise ValueError("Not a SUM-FNT v1 file.");
    if flags != 0:
        raise ValueError("Unsupported SUM-FNT flags.");
    expected_bpr = (width + 7) // 8;
    if bytes_per_row != expected_bpr:
        raise ValueError("Invalid SUM-FNT row size.");
    expected = HEADER.size + count * height * bytes_per_row;
    if len(data) != expected:
        raise ValueError(f"Invalid SUM-FNT size: expected {expected} bytes, got {len(data)}.");
    glyphs = [];
    offset = HEADER.size;
    shift = bytes_per_row * 8 - width;
    for _index in range(count):
        rows = [];
        for _row in range(height):
            value = int.from_bytes(data[offset:offset + bytes_per_row], "big") >> shift;
            rows.append(value);
            offset += bytes_per_row;
        glyphs.append(tuple(rows));
    return (BitmapFont(width, height, first, tuple(glyphs)));


def load_fnt(path: Path) -> BitmapFont:
    return (decode_fnt(path.read_bytes()));


def _render_glyph(font, character: str, target_width: int, target_height: int,
                  threshold: int, oversample: int) -> tuple[int, ...]:
    try:
        from PIL import Image, ImageDraw;
    except ImportError as error:
        raise ImportError("Pillow is required for font2fnt.") from error;
    ascent, descent = font.getmetrics();
    nominal_width = max(1, int(round(font.getlength("M"))));
    canvas_width = max(nominal_width, int(round(font.getlength(character or " "))), 1);
    canvas_height = max(1, ascent + descent);
    image = Image.new("L", (canvas_width, canvas_height), 0);
    draw = ImageDraw.Draw(image);
    draw.text((0, ascent), character, font=font, fill=255, anchor="ls");
    resized = image.resize((target_width, target_height), Image.Resampling.LANCZOS);
    rows = [];
    pixels = resized.load();
    for y in range(target_height):
        row = 0;
        for x in range(target_width):
            row <<= 1;
            if pixels[x, y] >= threshold:
                row |= 1;
        rows.append(row);
    return (tuple(rows));


def convert_vector_font(path: Path, width: int, height: int, first: int = 0,
                        count: int = 256, threshold: int = 96,
                        oversample: int = 8) -> BitmapFont:
    try:
        from PIL import ImageFont;
    except ImportError as error:
        raise ImportError("Pillow is required for font2fnt.") from error;
    if first < 0 or first > 0xffff or count < 1 or first + count > 0x10000:
        raise ValueError("Character range must fit within U+0000..U+FFFF for SUM-FNT v1.");
    if threshold < 0 or threshold > 255:
        raise ValueError("--threshold must be between 0 and 255.");
    if oversample < 1 or oversample > 32:
        raise ValueError("--oversample must be between 1 and 32.");
    pixel_size = max(8, height * oversample);
    vector_font = ImageFont.truetype(str(path), pixel_size);
    glyphs = [];
    for codepoint in range(first, first + count):
        character = bytes([codepoint]).decode("latin-1") if first == 0 and count == 256 else chr(codepoint);
        if codepoint < 32 or 127 <= codepoint < 160:
            glyphs.append(tuple(0 for _ in range(height)));
            continue;
        glyphs.append(_render_glyph(vector_font, character, width, height, threshold, oversample));
    return (BitmapFont(width, height, first, tuple(glyphs)));


def _font2fnt_output(input_path: Path, options: GlobalOptions) -> Path | None:
    return (resolve_single_output(input_path, options, ".fnt"));


def font2fnt_main(arguments: list[str] | None, options: GlobalOptions) -> int:
    parser = argparse.ArgumentParser(
        prog="font2fnt",
        description="Rasterize a TTF/OTF font into the compact SUM-FNT bitmap format.",
    );
    parser.add_argument("input", help="Input .ttf or .otf font.");
    parser.add_argument("--cell", type=_parse_cell, default=(4, 8), metavar="WxH",
                        help="Bitmap cell size. Default: 4x8.");
    parser.add_argument("--threshold", type=int, default=96,
                        help="Raster threshold 0..255. Lower values preserve more pixels. Default: 96.");
    parser.add_argument("--oversample", type=int, default=8,
                        help="Vector rasterization scale before reduction. Default: 8.");
    parser.add_argument("--first", type=lambda value: int(value, 0), default=0,
                        help="First character code. Default: 0.");
    parser.add_argument("--count", type=int, default=256,
                        help="Number of consecutive characters. Default: 256 (Latin-1 for 0..255).");
    args = parser.parse_args(arguments);
    input_path = require_input_file(args.input, (".ttf", ".otf"));
    width, height = args.cell;
    reporter = Reporter(options);
    font = convert_vector_font(input_path, width, height, args.first, args.count,
                               args.threshold, args.oversample);
    data = encode_fnt(font);
    output_path = _font2fnt_output(input_path, options);
    if output_path is not None:
        check_writable(output_path, options.force);
    write_binary_output(data, output_path, options);
    if output_path is not None:
        reporter.success(
            f"SUM-FNT written to: {output_path} ({font.width}x{font.height}, {font.count} glyphs)."
        );
    return (0);


def render_banner(text: str, font: BitmapFont, on: str = "█", off: str = " ",
                  gap: int = 1, trim: bool = True) -> str:
    if gap < 0:
        raise ValueError("gap cannot be negative.");
    separator = off * gap;
    lines = [];
    glyphs = [font.glyph(ord(character)) for character in text];
    for y in range(font.height):
        pieces = [];
        for glyph in glyphs:
            row = glyph[y];
            piece = "".join(on if row & (1 << (font.width - x - 1)) else off for x in range(font.width));
            pieces.append(piece);
        line = separator.join(pieces);
        lines.append(line.rstrip() if trim else line);
    return ("\n".join(lines) + "\n");


def banner_main(arguments: list[str] | None, options: GlobalOptions) -> int:
    parser = argparse.ArgumentParser(
        prog="sumdoc banner",
        description="Render text banners using a SUM-FNT bitmap font.",
    );
    parser.add_argument("text", nargs="*", help="Banner text. If omitted, read stdin.");
    parser.add_argument("--font", required=True, help="SUM-FNT .fnt file.");
    parser.add_argument("--on", default="█", help="Character used for lit pixels. Default: █.");
    parser.add_argument("--off", default=" ", help="Character used for unlit pixels. Default: space.");
    parser.add_argument("--gap", type=int, default=1, help="Columns between glyphs. Default: 1.");
    parser.add_argument("--no-trim", action="store_true", help="Keep trailing blank pixels on every row.");
    args = parser.parse_args(arguments);
    if len(args.on) != 1 or len(args.off) != 1:
        raise ValueError("--on and --off must each be exactly one character.");
    if args.text:
        text = " ".join(args.text);
    elif not sys.stdin.isatty():
        text = sys.stdin.read().rstrip("\n");
    else:
        raise ValueError("Provide banner text or pipe it through stdin.");
    font_path = require_input_file(args.font, (".fnt",));
    font = load_fnt(font_path);
    result = render_banner(text, font, args.on, args.off, args.gap, trim=not args.no_trim);
    output_path = resolve_single_output(None, options, ".txt", name="banner");
    write_text_output(result, output_path, options);
    Reporter(options).verbose(f"Rendered with {font.width}x{font.height} SUM-FNT '{font_path.name}'.");
    return (0);
