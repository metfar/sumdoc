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

from sumdoc.tools.fontbitmap import BitmapFont, decode_fnt, encode_fnt, render_banner;


def _test_font() -> BitmapFont:
    blank = (0, 0, 0, 0, 0, 0, 0, 0);
    glyphs = [blank for _ in range(256)];
    glyphs[ord("A")] = (0b0110, 0b1001, 0b1001, 0b1111, 0b1001, 0b1001, 0b1001, 0);
    glyphs[ord("?")] = (0b1110, 0b0001, 0b0010, 0b0100, 0b0100, 0, 0b0100, 0);
    return (BitmapFont(4, 8, 0, tuple(glyphs)));


def test_sum_fnt_roundtrip():
    font = _test_font();
    restored = decode_fnt(encode_fnt(font));
    assert restored == font;


def test_banner_uses_bitmap_rows():
    text = render_banner("A", _test_font(), on="#", off=".", gap=0, trim=False);
    assert text.splitlines()[0] == ".##.";
    assert text.splitlines()[3] == "####";


def test_missing_character_falls_back_to_question_mark():
    font = _test_font();
    assert font.glyph(0x20ac) == font.glyph(ord("?"));


def test_banner_supports_multiple_lines():
    text = render_banner("A\nA", _test_font(), on="#", off=".", gap=0, trim=False);
    lines = text.splitlines();
    assert len(lines) == 16;
    assert lines[0] == ".##.";
    assert lines[8] == ".##.";


def test_banner_supports_vertical_line_gap():
    text = render_banner("A\nA", _test_font(), on="#", off=".", gap=0, trim=False, line_gap=1);
    lines = text.splitlines();
    assert len(lines) == 17;
    assert lines[8] == "";
    assert lines[9] == ".##.";
