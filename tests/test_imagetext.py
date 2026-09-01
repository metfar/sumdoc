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

import pytest;

from sumdoc.common import GlobalOptions;
from sumdoc.registry import resolve_tool;
from sumdoc.tools import imagetext;


def test_image2ascii_is_image2text_alias():
    assert resolve_tool("image2ascii") is resolve_tool("image2text");


def test_mosaic_maps_two_by_two_quadrant(tmp_path):
    Image = pytest.importorskip("PIL.Image");
    source = tmp_path / "quadrant.png";
    output = tmp_path / "quadrant.txt";
    image = Image.new("RGB", (2, 2), (255, 255, 255));
    image.putpixel((0, 0), (0, 0, 0));
    image.save(source, "PNG");
    result = imagetext.image2text_main(
        [str(source), "--style", "mosaic", "--width", "1", "--height", "1",
         "--background", "white", "--threshold", "128"],
        GlobalOptions(output=str(output), quiet=True),
    );
    assert result == 0;
    assert output.read_text(encoding="utf-8") == "▘\n";


def test_braille_maps_first_dot(tmp_path):
    Image = pytest.importorskip("PIL.Image");
    source = tmp_path / "dot.png";
    output = tmp_path / "dot.txt";
    image = Image.new("RGB", (2, 4), (255, 255, 255));
    image.putpixel((0, 0), (0, 0, 0));
    image.save(source, "PNG");
    result = imagetext.image2braille_main(
        [str(source), "--width", "1", "--height", "1", "--background", "white",
         "--threshold", "128"],
        GlobalOptions(output=str(output), quiet=True),
    );
    assert result == 0;
    assert output.read_text(encoding="utf-8") == "⠁\n";


def test_ansi_uses_truecolor_half_block(tmp_path):
    Image = pytest.importorskip("PIL.Image");
    source = tmp_path / "colors.png";
    output = tmp_path / "colors.ansi";
    image = Image.new("RGB", (1, 2), (0, 0, 0));
    image.putpixel((0, 0), (255, 0, 0));
    image.putpixel((0, 1), (0, 0, 255));
    image.save(source, "PNG");
    result = imagetext.image2ansi_main(
        [str(source), "--width", "1", "--height", "1"],
        GlobalOptions(output=str(output), quiet=True),
    );
    assert result == 0;
    text = output.read_text(encoding="utf-8");
    assert "\x1b[38;2;255;0;0m" in text;
    assert "\x1b[48;2;0;0;255m" in text;
    assert "▀" in text;
    assert text.endswith("\x1b[0m\n");


def test_vertical_and_bottom_labels_are_deterministic():
    text = imagetext.decorate_lines(["abcd", "efgh", "ijkl"], 4, "xy", "z");
    assert text == "x abcd\ny efgh\n  ijkl\n   z  \n";


def test_crop_rejects_complete_image():
    with pytest.raises(ValueError, match="complete image"):
        imagetext.parse_crop("2,0,2,0", (4, 4));


def render_semigraphics_cell(tmp_path, active_pixels, line_style="light", arrow_style="unicode"):
    Image = pytest.importorskip("PIL.Image");
    source = tmp_path / "cell.png";
    output = tmp_path / "cell.txt";
    image = Image.new("RGB", (5, 5), (255, 255, 255));
    for x_value, y_value in active_pixels:
        image.putpixel((x_value, y_value), (0, 0, 0));
    image.save(source, "PNG");
    result = imagetext.image2text_main(
        [str(source), "--style", "semigraphics", "--width", "1", "--height", "1",
         "--background", "white", "--threshold", "128", "--line-style", line_style,
         "--arrow-style", arrow_style],
        GlobalOptions(output=str(output), quiet=True),
    );
    assert result == 0;
    return (output.read_text(encoding="utf-8"));


def test_semigraphics_detects_horizontal_line(tmp_path):
    assert render_semigraphics_cell(tmp_path, {(column, 2) for column in range(5)}) == "─\n";


def test_semigraphics_detects_vertical_line(tmp_path):
    assert render_semigraphics_cell(tmp_path, {(2, row) for row in range(5)}) == "│\n";


def test_semigraphics_detects_cross(tmp_path):
    pixels = {(column, 2) for column in range(5)} | {(2, row) for row in range(5)};
    assert render_semigraphics_cell(tmp_path, pixels) == "┼\n";


def test_semigraphics_detects_unicode_right_arrow(tmp_path):
    pixels = {(2, 0), (3, 1), (0, 2), (1, 2), (2, 2), (3, 2), (4, 2), (3, 3), (2, 4)};
    assert render_semigraphics_cell(tmp_path, pixels) == "⯈\n";


def test_semigraphics_supports_ascii_arrows(tmp_path):
    pixels = {(2, 0), (3, 1), (0, 2), (1, 2), (2, 2), (3, 2), (4, 2), (3, 3), (2, 4)};
    assert render_semigraphics_cell(tmp_path, pixels, arrow_style="ascii") == ">\n";


def test_semigraphics_supports_heavy_lines(tmp_path):
    assert render_semigraphics_cell(
        tmp_path,
        {(column, 2) for column in range(5)},
        line_style="heavy",
    ) == "━\n";


def test_ansi_semigraphics_colors_horizontal_line(tmp_path):
    Image = pytest.importorskip("PIL.Image");
    source = tmp_path / "red-line.png";
    output = tmp_path / "red-line.ansi";
    image = Image.new("RGB", (5, 5), (255, 255, 255));
    for column in range(5):
        image.putpixel((column, 2), (255, 0, 0));
    image.save(source, "PNG");
    result = imagetext.image2ansi_main(
        [str(source), "--style", "semigraphics", "--width", "1", "--height", "1",
         "--background", "white", "--threshold", "128"],
        GlobalOptions(output=str(output), quiet=True),
    );
    assert result == 0;
    text = output.read_text(encoding="utf-8");
    assert "\x1b[38;2;255;0;0m" in text;
    assert "─" in text;
    assert text.endswith("\x1b[0m\n");


def test_ansi_semigraphics_supports_unicode_arrow(tmp_path):
    Image = pytest.importorskip("PIL.Image");
    source = tmp_path / "arrow.png";
    output = tmp_path / "arrow.ansi";
    pixels = {(2, 0), (3, 1), (0, 2), (1, 2), (2, 2), (3, 2), (4, 2), (3, 3), (2, 4)};
    image = Image.new("RGB", (5, 5), (255, 255, 255));
    for x_value, y_value in pixels:
        image.putpixel((x_value, y_value), (0, 0, 255));
    image.save(source, "PNG");
    result = imagetext.image2ansi_main(
        [str(source), "--style", "semigraphics", "--width", "1", "--height", "1",
         "--background", "white", "--threshold", "128"],
        GlobalOptions(output=str(output), quiet=True),
    );
    assert result == 0;
    text = output.read_text(encoding="utf-8");
    assert "\x1b[38;2;0;0;255m" in text;
    assert "⯈" in text;


def test_semigraphics_detects_mixed_weight_cross(tmp_path):
    pixels = {(column, 2) for column in range(5)};
    pixels |= {(column, row) for row in range(5) for column in (1, 2, 3)};
    assert render_semigraphics_cell(tmp_path, pixels, line_style="mixed") == "╂\n";


def test_semigraphics_detects_mixed_weight_corner(tmp_path):
    pixels = {(column, row) for row in range(3) for column in (1, 2, 3)};
    pixels |= {(column, 2) for column in range(2, 5)};
    assert render_semigraphics_cell(tmp_path, pixels, line_style="mixed") == "┖\n";
