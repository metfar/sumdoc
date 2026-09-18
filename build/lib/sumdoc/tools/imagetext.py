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

"""Render raster images as ASCII, ANSI half blocks, or Unicode Braille.""";

import argparse;
from pathlib import Path;
import math;

from sumdoc.ansi import BRIGHT_COLORS, NORMAL_COLORS;
from sumdoc.common import GlobalOptions, Reporter, require_input_file, write_text_output;


IMAGE_SUFFIXES = (
    ".png", ".webp", ".jpg", ".jpeg", ".gif", ".bmp", ".tif", ".tiff",
);
ASCII_STYLES = {
    "ascii": " .:-=+*#%@",
    "dos": " ░▒▓█",
    "blocks": " ▏▎▍▌▋▊▉▇█",
};
LINE_GLYPHS = {
    "ascii": {
        0x0: " ", 0x1: "|", 0x2: "-", 0x3: "+",
        0x4: "|", 0x5: "|", 0x6: "+", 0x7: "+",
        0x8: "-", 0x9: "+", 0xA: "-", 0xB: "+",
        0xC: "+", 0xD: "+", 0xE: "+", 0xF: "+",
    },
    "light": {
        0x0: " ", 0x1: "╵", 0x2: "╶", 0x3: "└",
        0x4: "╷", 0x5: "│", 0x6: "┌", 0x7: "├",
        0x8: "╴", 0x9: "┘", 0xA: "─", 0xB: "┴",
        0xC: "┐", 0xD: "┤", 0xE: "┬", 0xF: "┼",
    },
    "heavy": {
        0x0: " ", 0x1: "╹", 0x2: "╺", 0x3: "┗",
        0x4: "╻", 0x5: "┃", 0x6: "┏", 0x7: "┣",
        0x8: "╸", 0x9: "┛", 0xA: "━", 0xB: "┻",
        0xC: "┓", 0xD: "┫", 0xE: "┳", 0xF: "╋",
    },
};
MIXED_LINE_GLYPHS = {
    (1, 0, 0, 0): "╵", (2, 0, 0, 0): "╹",
    (0, 1, 0, 0): "╶", (0, 2, 0, 0): "╺",
    (0, 0, 1, 0): "╷", (0, 0, 2, 0): "╻",
    (0, 0, 0, 1): "╴", (0, 0, 0, 2): "╸",
    (1, 0, 1, 0): "│", (2, 0, 2, 0): "┃",
    (1, 0, 2, 0): "╽", (2, 0, 1, 0): "╿",
    (0, 1, 0, 1): "─", (0, 2, 0, 2): "━",
    (0, 1, 0, 2): "╼", (0, 2, 0, 1): "╾",
    (1, 1, 0, 0): "└", (2, 2, 0, 0): "┗",
    (2, 1, 0, 0): "┖", (1, 2, 0, 0): "┕",
    (0, 1, 1, 0): "┌", (0, 2, 2, 0): "┏",
    (0, 1, 2, 0): "┎", (0, 2, 1, 0): "┍",
    (0, 0, 1, 1): "┐", (0, 0, 2, 2): "┓",
    (0, 0, 2, 1): "┒", (0, 0, 1, 2): "┑",
    (1, 0, 0, 1): "┘", (2, 0, 0, 2): "┛",
    (2, 0, 0, 1): "┚", (1, 0, 0, 2): "┙",
    (1, 1, 0, 1): "┴", (2, 2, 0, 2): "┻",
    (1, 2, 0, 2): "┷", (2, 1, 0, 1): "┸",
    (0, 1, 1, 1): "┬", (0, 2, 2, 2): "┳",
    (0, 2, 1, 2): "┯", (0, 1, 2, 1): "┰",
    (1, 1, 1, 0): "├", (2, 2, 2, 0): "┣",
    (1, 2, 1, 0): "┝", (2, 1, 2, 0): "┠",
    (1, 0, 1, 1): "┤", (2, 0, 2, 2): "┫",
    (1, 0, 1, 2): "┥", (2, 0, 2, 1): "┨",
    (1, 1, 1, 1): "┼", (2, 2, 2, 2): "╋",
    (2, 1, 2, 1): "╂", (1, 2, 1, 2): "┿",
};
ARROW_GLYPHS = {
    "ascii": {"left": "<", "right": ">", "up": "^", "down": "v"},
    "unicode": {"left": "⯇", "right": "⯈", "up": "⯅", "down": "⯆"},
};
ARROW_TEMPLATES = {
    "right": (
        "00100",
        "00010",
        "11111",
        "00010",
        "00100",
    ),
    "left": (
        "00100",
        "01000",
        "11111",
        "01000",
        "00100",
    ),
    "up": (
        "00100",
        "01110",
        "10101",
        "00100",
        "00100",
    ),
    "down": (
        "00100",
        "00100",
        "10101",
        "01110",
        "00100",
    ),
};
QUADRANT_CHARS = {
    0x0: " ",
    0x1: "▘",
    0x2: "▝",
    0x3: "▀",
    0x4: "▖",
    0x5: "▌",
    0x6: "▞",
    0x7: "▛",
    0x8: "▗",
    0x9: "▚",
    0xA: "▐",
    0xB: "▜",
    0xC: "▄",
    0xD: "▙",
    0xE: "▟",
    0xF: "█",
};
XTERM_LEVELS = (0, 95, 135, 175, 215, 255);


def import_image_modules():
    """Load Pillow only when an image-to-text tool is used.""";
    from PIL import Image, ImageEnhance;
    return (Image, ImageEnhance);


def create_common_parser(prog: str, description: str) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog=prog, description=description);
    parser.add_argument("inputs", nargs="+", help="Input image file or non-recursive directory.");
    parser.add_argument("-w", "--width", type=int, default=80, metavar="COLUMNS",
                        help="Image width in terminal columns. Default: 80.");
    parser.add_argument("-H", "--height", type=int, metavar="ROWS",
                        help="Force the image height in terminal rows.");
    parser.add_argument("--cell-aspect", type=float, default=0.5, metavar="RATIO",
                        help="Terminal cell width/height ratio. Default: 0.5.");
    parser.add_argument("--background", default="auto", metavar="COLOR",
                        help="auto, light, dark, #RRGGBB, or R,G,B. Default: auto.");
    parser.add_argument("--crop", metavar="L,T,R,B",
                        help="Remove left, top, right, and bottom margins in source pixels.");
    parser.add_argument("--mode", choices=("luminance", "difference"), default="luminance",
                        help="Measure brightness or distance from the background.");
    parser.add_argument("--chart", action="store_true",
                        help="Chart-friendly difference mode; suppresses flat backgrounds.");
    parser.add_argument("--contrast", type=float, default=1.0, metavar="FACTOR",
                        help="Contrast factor applied before rendering. Default: 1.0.");
    parser.add_argument("--gamma", type=float, default=1.0, metavar="FACTOR",
                        help="Output strength gamma. Default: 1.0.");
    parser.add_argument("--invert", action="store_true", help="Invert foreground strength.");
    parser.add_argument("--left-label", metavar="TEXT",
                        help="Place a vertical text label at the left, one character per row.");
    parser.add_argument("--bottom-label", metavar="TEXT",
                        help="Center a plain-text label below the rendered image.");
    return (parser);


def create_ascii_parser() -> argparse.ArgumentParser:
    parser = create_common_parser(
        "image2text",
        "Render images as portable ASCII or DOS/Spectrum-style Unicode blocks.",
    );
    parser.add_argument("--style", choices=("ascii", "dos", "blocks", "mosaic", "semigraphics"),
                        default="ascii", help="Character style. Default: ascii.");
    parser.add_argument("--chars", metavar="CHARACTERS",
                        help="Custom darkening ramp, from blank/light to dense/dark.");
    parser.add_argument("--threshold", type=int, default=24, choices=range(0, 256),
                        metavar="0-255", help="Threshold used by mosaic/semigraphics modes. Default: 24.");
    parser.add_argument("--line-style", choices=("ascii", "light", "heavy", "mixed"), default="light",
                        help="Line glyph family used by semigraphics. Default: light.");
    parser.add_argument("--arrow-style", choices=("ascii", "unicode"), default="unicode",
                        help="Arrow glyph family used by semigraphics. Default: unicode.");
    return (parser);


def create_ansi_parser() -> argparse.ArgumentParser:
    parser = create_common_parser(
        "image2ansi",
        "Render images with ANSI foreground/background colors and half-block characters.",
    );
    parser.add_argument("--colors", choices=("truecolor", "256", "16"), default="truecolor",
                        help="ANSI color space. Default: truecolor.");
    parser.add_argument("--style", choices=("halfblock", "semigraphics"), default="halfblock",
                        help="ANSI cell renderer. Default: halfblock.");
    parser.add_argument("--threshold", type=int, default=24, choices=range(0, 256),
                        metavar="0-255", help="Threshold used by semigraphics. Default: 24.");
    parser.add_argument("--line-style", choices=("ascii", "light", "heavy", "mixed"), default="light",
                        help="Line glyph family used by semigraphics. Default: light.");
    parser.add_argument("--arrow-style", choices=("ascii", "unicode"), default="unicode",
                        help="Arrow glyph family used by semigraphics. Default: unicode.");
    return (parser);


def create_braille_parser() -> argparse.ArgumentParser:
    parser = create_common_parser(
        "image2braille",
        "Render images with Unicode Braille cells, optionally using ANSI color.",
    );
    parser.set_defaults(mode="difference");
    parser.add_argument("--threshold", type=int, default=24, choices=range(0, 256),
                        metavar="0-255", help="Dot activation threshold. Default: 24.");
    parser.add_argument("--color", action="store_true", help="Color active Braille cells with ANSI.");
    parser.add_argument("--colors", choices=("truecolor", "256", "16"), default="truecolor",
                        help="ANSI color space used with --color. Default: truecolor.");
    return (parser);


def validate_dimensions(args: argparse.Namespace) -> None:
    if args.width < 1:
        raise ValueError("--width must be greater than zero.");
    if args.height is not None and args.height < 1:
        raise ValueError("--height must be greater than zero.");
    if args.cell_aspect <= 0:
        raise ValueError("--cell-aspect must be greater than zero.");
    if args.contrast <= 0:
        raise ValueError("--contrast must be greater than zero.");
    if args.gamma <= 0:
        raise ValueError("--gamma must be greater than zero.");


def collect_inputs(input_texts: list[str]) -> list[Path]:
    """Expand image files and non-recursive directories into a stable list.""";
    paths = [];
    for input_text in input_texts:
        path = Path(input_text).expanduser().resolve();
        if not path.exists():
            raise FileNotFoundError(f"Input path does not exist: '{path}'.");
        if path.is_dir():
            paths.extend(sorted(
                child for child in path.iterdir()
                if child.is_file() and child.suffix.lower() in IMAGE_SUFFIXES
            ));
        else:
            paths.append(require_input_file(str(path), IMAGE_SUFFIXES));
    if not paths:
        expected = ", ".join(IMAGE_SUFFIXES);
        raise ValueError(f"No supported images were found. Expected: {expected}.");
    return (paths);


def parse_rgb(text: str) -> tuple[int, int, int] | None:
    """Parse a user-supplied RGB color, or return None for automatic detection.""";
    normalized = text.strip().lower();
    if normalized == "auto":
        return (None);
    if normalized in ("light", "white"):
        return ((255, 255, 255));
    if normalized in ("dark", "black"):
        return ((0, 0, 0));
    if normalized.startswith("#") and len(normalized) == 7:
        try:
            return ((
                int(normalized[1:3], 16),
                int(normalized[3:5], 16),
                int(normalized[5:7], 16),
            ));
        except ValueError as error:
            raise ValueError(f"Invalid background color: '{text}'.") from error;
    fields = normalized.split(",");
    if len(fields) == 3:
        try:
            values = tuple(int(field.strip()) for field in fields);
        except ValueError as error:
            raise ValueError(f"Invalid background color: '{text}'.") from error;
        if all(0 <= value <= 255 for value in values):
            return (values);
    raise ValueError(f"Invalid background color: '{text}'.");



def parse_crop(text: str | None, size: tuple[int, int]) -> tuple[int, int, int, int] | None:
    """Parse source-pixel crop margins and return a Pillow crop box.""";
    if text is None:
        return (None);
    fields = text.split(",");
    if len(fields) != 4:
        raise ValueError("--crop requires four comma-separated margins: left,top,right,bottom.");
    try:
        left, top, right, bottom = (int(field.strip()) for field in fields);
    except ValueError as error:
        raise ValueError("--crop margins must be integers.") from error;
    if min(left, top, right, bottom) < 0:
        raise ValueError("--crop margins cannot be negative.");
    width, height = size;
    if left + right >= width or top + bottom >= height:
        raise ValueError("--crop removes the complete image.");
    return ((left, top, width - right, height - bottom));

def dominant_colors(image, limit: int = 2) -> tuple[tuple[int, int, int], ...]:
    """Estimate the most common visible RGB background colors.""";
    Image, _ImageEnhance = import_image_modules();
    rgba = image.convert("RGBA");
    white = Image.new("RGBA", rgba.size, (255, 255, 255, 255));
    composite = Image.alpha_composite(white, rgba).convert("RGB");
    sample = composite.copy();
    sample.thumbnail((128, 128), Image.Resampling.BILINEAR);
    quantized = sample.quantize(colors=16, method=Image.Quantize.MEDIANCUT);
    counts = quantized.getcolors();
    if not counts:
        return (((255, 255, 255),));
    palette = quantized.getpalette();
    colors = [];
    for _count, palette_index in sorted(counts, reverse=True):
        offset = palette_index * 3;
        color = tuple(palette[offset:offset + 3]);
        if colors and max(color) - min(color) > 12:
            continue;
        if all(sum((color[channel] - previous[channel]) ** 2 for channel in range(3)) >= 144
               for previous in colors):
            colors.append(color);
        if len(colors) >= limit:
            break;
    return (tuple(colors));


def prepare_image(path: Path, background_text: str, contrast: float, crop_text: str | None):
    """Open, orient, composite, and contrast-adjust one input image.""";
    Image, ImageEnhance = import_image_modules();
    with Image.open(path) as source:
        source.seek(0);
        rgba = source.convert("RGBA");
    crop_box = parse_crop(crop_text, rgba.size);
    if crop_box is not None:
        rgba = rgba.crop(crop_box);
    requested_background = parse_rgb(background_text);
    detected_backgrounds = (requested_background,) if requested_background is not None else dominant_colors(rgba);
    detected_background = detected_backgrounds[0];
    canvas = Image.new("RGBA", rgba.size, detected_background + (255,));
    image = Image.alpha_composite(canvas, rgba).convert("RGB");
    if contrast != 1.0:
        image = ImageEnhance.Contrast(image).enhance(contrast);
    return ((image, detected_backgrounds));


def output_rows(image, width: int, height: int | None, cell_aspect: float) -> int:
    """Calculate terminal rows while compensating for non-square character cells.""";
    if height is not None:
        return (height);
    ratio = image.height / image.width;
    return (max(1, int(round(ratio * width * cell_aspect))));


def luminance(color: tuple[int, int, int]) -> float:
    return ((0.2126 * color[0]) + (0.7152 * color[1]) + (0.0722 * color[2]));


def flattened_data(image):
    """Return Pillow pixel data without using its deprecated getdata alias.""";
    if hasattr(image, "get_flattened_data"):
        return (image.get_flattened_data());
    return (image.getdata());


def pixel_strength(color: tuple[int, int, int], backgrounds: tuple[tuple[int, int, int], ...],
                   mode: str, invert: bool, gamma: float) -> int:
    """Return a normalized 0..255 foreground strength.""";
    background = backgrounds[0];
    if mode == "difference":
        distance = min(
            math.sqrt(sum((color[index] - candidate[index]) ** 2 for index in range(3)))
            for candidate in backgrounds
        );
        value = min(255.0, distance / math.sqrt(3.0));
    else:
        light_background = luminance(background) >= 127.5;
        value = 255.0 - luminance(color) if light_background else luminance(color);
    if invert:
        value = 255.0 - value;
    normalized = max(0.0, min(1.0, value / 255.0));
    adjusted = pow(normalized, 1.0 / gamma);
    return (int(round(adjusted * 255.0)));


def strength_image(image, backgrounds: tuple[tuple[int, int, int], ...], size: tuple[int, int],
                   mode: str, invert: bool, gamma: float):
    """Resize an RGB image and convert it to an 8-bit foreground-strength image.""";
    Image, _ImageEnhance = import_image_modules();
    resized = image.resize(size, Image.Resampling.LANCZOS);
    strengths = Image.new("L", size);
    strengths.putdata([
        pixel_strength(pixel, backgrounds, mode, invert, gamma)
        for pixel in flattened_data(resized)
    ]);
    return ((resized, strengths));


def binary_patch(pixels, left: int, top: int, size: int, threshold: int) -> tuple[tuple[bool, ...], ...]:
    """Read one square binary patch from a Pillow pixel-access object.""";
    return (tuple(
        tuple(pixels[left + column, top + row] >= threshold for column in range(size))
        for row in range(size)
    ));


def arrow_template_bits(template: tuple[str, ...]) -> set[tuple[int, int]]:
    """Convert a compact arrow template into active coordinates.""";
    return ({
        (column, row)
        for row, line in enumerate(template)
        for column, value in enumerate(line)
        if value == "1"
    });


def detect_arrow(patch: tuple[tuple[bool, ...], ...]) -> str | None:
    """Recognize a small arrow by Jaccard similarity against directional templates.""";
    active = {
        (column, row)
        for row, line in enumerate(patch)
        for column, value in enumerate(line)
        if value
    };
    if not active:
        return (None);
    ranked = [];
    for direction, template in ARROW_TEMPLATES.items():
        expected = arrow_template_bits(template);
        union = active | expected;
        similarity = len(active & expected) / len(union) if union else 0.0;
        ranked.append((similarity, direction));
    ranked.sort(reverse=True);
    best_score, best_direction = ranked[0];
    second_score = ranked[1][0];
    if best_score >= 0.68 and (best_score - second_score) >= 0.08:
        return (best_direction);
    return (None);


def patch_connectivity(patch: tuple[tuple[bool, ...], ...]) -> int:
    """Return N/E/S/W bits only when a stroke reaches the center continuously.""";
    center = len(patch) // 2;
    span = tuple(range(max(0, center - 1), min(len(patch), center + 2)));
    north_path = [any(patch[row][column] for column in span) for row in range(0, center + 1)];
    east_path = [any(patch[row][column] for row in span)
                 for column in range(center, len(patch))];
    south_path = [any(patch[row][column] for column in span)
                  for row in range(center, len(patch))];
    west_path = [any(patch[row][column] for row in span) for column in range(0, center + 1)];
    minimum_path = center;
    north = north_path[0] and sum(north_path) >= minimum_path;
    east = east_path[-1] and sum(east_path) >= minimum_path;
    south = south_path[-1] and sum(south_path) >= minimum_path;
    west = west_path[0] and sum(west_path) >= minimum_path;
    mask = 0;
    if north:
        mask |= 0x1;
    if east:
        mask |= 0x2;
    if south:
        mask |= 0x4;
    if west:
        mask |= 0x8;
    return (mask);


def patch_direction_weights(patch: tuple[tuple[bool, ...], ...], connectivity: int) -> tuple[int, int, int, int]:
    """Estimate light/heavy stroke weight for N/E/S/W directions.""";
    center = len(patch) // 2;
    span = tuple(range(max(0, center - 1), min(len(patch), center + 2)));

    north_width = sum(patch[0][column] for column in span);
    east_width = sum(patch[row][-1] for row in span);
    south_width = sum(patch[-1][column] for column in span);
    west_width = sum(patch[row][0] for row in span);
    north = (2 if north_width >= 2 else 1) if connectivity & 0x1 else 0;
    east = (2 if east_width >= 2 else 1) if connectivity & 0x2 else 0;
    south = (2 if south_width >= 2 else 1) if connectivity & 0x4 else 0;
    west = (2 if west_width >= 2 else 1) if connectivity & 0x8 else 0;
    return ((north, east, south, west));


def mixed_line_character(patch: tuple[tuple[bool, ...], ...], connectivity: int) -> str:
    """Select a mixed-weight box-drawing glyph when the topology supports one.""";
    weights = patch_direction_weights(patch, connectivity);
    if weights in MIXED_LINE_GLYPHS:
        return (MIXED_LINE_GLYPHS[weights]);
    connected_weights = [weight for weight in weights if weight];
    family = "heavy" if connected_weights and (sum(connected_weights) / len(connected_weights)) >= 1.5 else "light";
    return (LINE_GLYPHS[family][connectivity]);


def patch_quadrants(patch: tuple[tuple[bool, ...], ...]) -> int:
    """Reduce a 5x5 patch to the four Unicode quadrant bits.""";
    size = len(patch);
    middle = size // 2;
    regions = (
        (range(0, middle + 1), range(0, middle + 1), 0x1),
        (range(middle, size), range(0, middle + 1), 0x2),
        (range(0, middle + 1), range(middle, size), 0x4),
        (range(middle, size), range(middle, size), 0x8),
    );
    pattern = 0;
    for columns, rows, bit in regions:
        values = [patch[row][column] for row in rows for column in columns];
        if values and (sum(values) / len(values)) >= 0.34:
            pattern |= bit;
    return (pattern);


def semigraphics_character(patch: tuple[tuple[bool, ...], ...], line_style: str,
                           arrow_style: str) -> str:
    """Classify a binary cell as arrow, box-drawing line, quadrant, or shade.""";
    active_count = sum(value for row in patch for value in row);
    if active_count == 0:
        return (" ");
    arrow = detect_arrow(patch);
    if arrow is not None:
        return (ARROW_GLYPHS[arrow_style][arrow]);
    density = active_count / (len(patch) * len(patch[0]));
    connectivity = patch_connectivity(patch);
    center = len(patch) // 2;
    center_active = patch[center][center] or any(
        patch[row][column]
        for row in range(center - 1, center + 2)
        for column in range(center - 1, center + 2)
    );
    maximum_line_density = 0.76 if line_style == "mixed" else 0.60;
    if center_active and connectivity.bit_count() >= 2 and density <= maximum_line_density:
        if line_style == "mixed":
            return (mixed_line_character(patch, connectivity));
        return (LINE_GLYPHS[line_style][connectivity]);
    quadrant_pattern = patch_quadrants(patch);
    if quadrant_pattern not in (0x0, 0xF):
        return (QUADRANT_CHARS[quadrant_pattern]);
    if density >= 0.72:
        return ("█");
    if density >= 0.48:
        return ("▓");
    if density >= 0.25:
        return ("▒");
    return ("░");


def render_semigraphics(image, backgrounds: tuple[tuple[int, int, int], ...],
                        args: argparse.Namespace) -> list[str]:
    """Render topology-aware DOS/Spectrum semigraphics using 5x5 source patches.""";
    rows = output_rows(image, args.width, args.height, args.cell_aspect);
    mode = "difference" if args.chart else args.mode;
    active_backgrounds = backgrounds if args.chart else backgrounds[:1];
    patch_size = 5;
    _resized, strengths = strength_image(
        image,
        active_backgrounds,
        (args.width * patch_size, rows * patch_size),
        mode,
        args.invert,
        args.gamma,
    );
    pixels = strengths.load();
    lines = [];
    for row in range(rows):
        characters = [];
        for column in range(args.width):
            patch = binary_patch(
                pixels,
                column * patch_size,
                row * patch_size,
                patch_size,
                args.threshold,
            );
            characters.append(semigraphics_character(patch, args.line_style, args.arrow_style));
        lines.append("".join(characters).rstrip());
    return (lines);


def render_ascii(image, backgrounds: tuple[tuple[int, int, int], ...], args: argparse.Namespace) -> list[str]:
    rows = output_rows(image, args.width, args.height, args.cell_aspect);
    mode = "difference" if args.chart else args.mode;
    active_backgrounds = backgrounds if args.chart else backgrounds[:1];
    if args.style == "semigraphics":
        return (render_semigraphics(image, backgrounds, args));
    if args.style == "mosaic":
        _resized, strengths = strength_image(
            image, active_backgrounds, (args.width * 2, rows * 2), mode, args.invert, args.gamma,
        );
        pixels = strengths.load();
        lines = [];
        for row in range(rows):
            characters = [];
            for column in range(args.width):
                pattern = 0;
                if pixels[column * 2, row * 2] >= args.threshold:
                    pattern |= 0x1;
                if pixels[(column * 2) + 1, row * 2] >= args.threshold:
                    pattern |= 0x2;
                if pixels[column * 2, (row * 2) + 1] >= args.threshold:
                    pattern |= 0x4;
                if pixels[(column * 2) + 1, (row * 2) + 1] >= args.threshold:
                    pattern |= 0x8;
                characters.append(QUADRANT_CHARS[pattern]);
            lines.append("".join(characters).rstrip());
        return (lines);
    characters = args.chars if args.chars is not None else ASCII_STYLES[args.style];
    if len(characters) < 2:
        raise ValueError("--chars must contain at least two characters.");
    _resized, strengths = strength_image(
        image, active_backgrounds, (args.width, rows), mode, args.invert, args.gamma,
    );
    lines = [];
    values = list(flattened_data(strengths));
    for row in range(rows):
        start = row * args.width;
        line = [];
        for value in values[start:start + args.width]:
            index = min(len(characters) - 1, int(value * len(characters) / 256));
            line.append(characters[index]);
        lines.append("".join(line).rstrip());
    return (lines);


def nearest_palette_index(color: tuple[int, int, int], palette: tuple[tuple[int, int, int], ...]) -> int:
    return (min(
        range(len(palette)),
        key=lambda index: sum((color[channel] - palette[index][channel]) ** 2 for channel in range(3)),
    ));


def rgb_to_xterm_index(color: tuple[int, int, int]) -> int:
    """Approximate an RGB color with an xterm-256 palette index.""";
    red, green, blue = color;
    cube_indexes = tuple(min(range(6), key=lambda index: abs(XTERM_LEVELS[index] - value))
                         for value in (red, green, blue));
    cube_index = 16 + (36 * cube_indexes[0]) + (6 * cube_indexes[1]) + cube_indexes[2];
    cube_color = tuple(XTERM_LEVELS[index] for index in cube_indexes);
    gray_index = min(range(24), key=lambda index: abs((8 + (10 * index)) - ((red + green + blue) / 3)));
    gray_color = (8 + (10 * gray_index),) * 3;
    cube_error = sum((color[channel] - cube_color[channel]) ** 2 for channel in range(3));
    gray_error = sum((color[channel] - gray_color[channel]) ** 2 for channel in range(3));
    return ((232 + gray_index) if gray_error < cube_error else cube_index);


def foreground_code(color: tuple[int, int, int], color_mode: str) -> str:
    if color_mode == "truecolor":
        return (f"\x1b[38;2;{color[0]};{color[1]};{color[2]}m");
    if color_mode == "256":
        return (f"\x1b[38;5;{rgb_to_xterm_index(color)}m");
    palette = NORMAL_COLORS + BRIGHT_COLORS;
    index = nearest_palette_index(color, palette);
    code = (30 + index) if index < 8 else (90 + (index - 8));
    return (f"\x1b[{code}m");


def background_code(color: tuple[int, int, int], color_mode: str) -> str:
    if color_mode == "truecolor":
        return (f"\x1b[48;2;{color[0]};{color[1]};{color[2]}m");
    if color_mode == "256":
        return (f"\x1b[48;5;{rgb_to_xterm_index(color)}m");
    palette = NORMAL_COLORS + BRIGHT_COLORS;
    index = nearest_palette_index(color, palette);
    code = (40 + index) if index < 8 else (100 + (index - 8));
    return (f"\x1b[{code}m");


def average_patch_color(rgb_pixels, strength_pixels, left: int, top: int, size: int,
                        threshold: int) -> tuple[int, int, int]:
    """Average colors of active pixels in one semigraphics patch.""";
    colors = [];
    for row in range(size):
        for column in range(size):
            x_value = left + column;
            y_value = top + row;
            if strength_pixels[x_value, y_value] >= threshold:
                colors.append(rgb_pixels[x_value, y_value]);
    if not colors:
        center = size // 2;
        return (rgb_pixels[left + center, top + center]);
    return (tuple(
        int(round(sum(color[channel] for color in colors) / len(colors)))
        for channel in range(3)
    ));


def render_ansi_semigraphics(image, backgrounds: tuple[tuple[int, int, int], ...],
                             args: argparse.Namespace) -> list[str]:
    """Render colored topology-aware semigraphics with ANSI foreground colors.""";
    rows = output_rows(image, args.width, args.height, args.cell_aspect);
    mode = "difference" if args.chart else args.mode;
    active_backgrounds = backgrounds if args.chart else backgrounds[:1];
    patch_size = 5;
    resized, strengths = strength_image(
        image,
        active_backgrounds,
        (args.width * patch_size, rows * patch_size),
        mode,
        args.invert,
        args.gamma,
    );
    rgb_pixels = resized.load();
    strength_pixels = strengths.load();
    lines = [];
    for row in range(rows):
        cells = [];
        for column in range(args.width):
            left = column * patch_size;
            top = row * patch_size;
            patch = binary_patch(strength_pixels, left, top, patch_size, args.threshold);
            character = semigraphics_character(patch, args.line_style, args.arrow_style);
            color = average_patch_color(
                rgb_pixels,
                strength_pixels,
                left,
                top,
                patch_size,
                args.threshold,
            );
            cells.append((character, color));
        while cells and cells[-1][0] == " ":
            cells.pop();
        parts = [];
        current_color = None;
        for character, color in cells:
            if character != " " and color != current_color:
                parts.append(foreground_code(color, args.colors));
                current_color = color;
            parts.append(character);
        if current_color is not None:
            parts.append("\x1b[0m");
        lines.append("".join(parts));
    return (lines);


def render_ansi(image, backgrounds: tuple[tuple[int, int, int], ...], args: argparse.Namespace) -> list[str]:
    if args.style == "semigraphics":
        return (render_ansi_semigraphics(image, backgrounds, args));
    Image, _ImageEnhance = import_image_modules();
    rows = output_rows(image, args.width, args.height, args.cell_aspect);
    resized = image.resize((args.width, rows * 2), Image.Resampling.LANCZOS);
    pixels = resized.load();
    lines = [];
    for row in range(rows):
        parts = [];
        current_pair = None;
        for column in range(args.width):
            top = pixels[column, row * 2];
            bottom = pixels[column, (row * 2) + 1];
            pair = (top, bottom);
            if pair != current_pair:
                parts.append(foreground_code(top, args.colors));
                parts.append(background_code(bottom, args.colors));
                current_pair = pair;
            parts.append("▀");
        parts.append("\x1b[0m");
        lines.append("".join(parts));
    return (lines);


def braille_character(pattern: int) -> str:
    return (chr(0x2800 + pattern));


def render_braille(image, backgrounds: tuple[tuple[int, int, int], ...], args: argparse.Namespace) -> list[str]:
    rows = output_rows(image, args.width, args.height, args.cell_aspect);
    mode = "difference" if args.chart else args.mode;
    active_backgrounds = backgrounds if args.chart else backgrounds[:1];
    resized, strengths = strength_image(
        image, active_backgrounds, (args.width * 2, rows * 4), mode, args.invert, args.gamma,
    );
    rgb_pixels = resized.load();
    strength_pixels = strengths.load();
    dots = (
        (0, 0, 0x01), (0, 1, 0x02), (0, 2, 0x04), (1, 0, 0x08),
        (1, 1, 0x10), (1, 2, 0x20), (0, 3, 0x40), (1, 3, 0x80),
    );
    lines = [];
    for row in range(rows):
        parts = [];
        current_color = None;
        for column in range(args.width):
            pattern = 0;
            active_colors = [];
            for offset_x, offset_y, bit in dots:
                x = (column * 2) + offset_x;
                y = (row * 4) + offset_y;
                if strength_pixels[x, y] >= args.threshold:
                    pattern |= bit;
                    active_colors.append(rgb_pixels[x, y]);
            if pattern == 0:
                if args.color and current_color is not None:
                    parts.append("\x1b[0m");
                    current_color = None;
                parts.append(" ");
                continue;
            if args.color:
                average = tuple(
                    int(round(sum(color[channel] for color in active_colors) / len(active_colors)))
                    for channel in range(3)
                );
                if average != current_color:
                    parts.append(foreground_code(average, args.colors));
                    current_color = average;
            parts.append(braille_character(pattern));
        if args.color:
            parts.append("\x1b[0m");
        lines.append("".join(parts).rstrip());
    return (lines);


def decorate_lines(lines: list[str], content_width: int, left_label: str | None,
                   bottom_label: str | None) -> str:
    """Add deterministic chart labels without requiring OCR.""";
    decorated = list(lines);
    label = left_label or "";
    if label and len(decorated) < len(label):
        missing = len(label) - len(decorated);
        before = missing // 2;
        after = missing - before;
        decorated = ([" " * content_width] * before) + decorated + ([" " * content_width] * after);
    left_margin = 0;
    if label:
        start = (len(decorated) - len(label)) // 2;
        with_label = [];
        for index, line in enumerate(decorated):
            label_index = index - start;
            character = label[label_index] if 0 <= label_index < len(label) else " ";
            with_label.append(f"{character} {line}");
        decorated = with_label;
        left_margin = 2;
    if bottom_label:
        decorated.append((" " * left_margin) + bottom_label.center(content_width));
    return ("\n".join(decorated) + "\n");


def output_path_for(input_path: Path, options: GlobalOptions, extension: str,
                    multiple: bool) -> Path | None:
    if options.output is not None:
        if multiple:
            raise ValueError("--output can only be used with exactly one input image.");
        if options.output == "-":
            return (None);
        return (Path(options.output).expanduser().resolve());
    if options.output_dir is not None:
        directory = Path(options.output_dir).expanduser().resolve();
        directory.mkdir(parents=True, exist_ok=True);
        return (directory / f"{input_path.stem}{extension}");
    if multiple:
        raise ValueError("Multiple input images require --output-dir.");
    return (None);


def main_for(tool_name: str, arguments: list[str] | None, options: GlobalOptions) -> int:
    if tool_name == "image2text":
        parser = create_ascii_parser();
        renderer = render_ascii;
        default_extension = ".txt";
    elif tool_name == "image2ansi":
        parser = create_ansi_parser();
        renderer = render_ansi;
        default_extension = ".ansi";
    else:
        parser = create_braille_parser();
        renderer = render_braille;
        default_extension = ".txt";
    args = parser.parse_args(arguments);
    validate_dimensions(args);
    inputs = collect_inputs(args.inputs);
    multiple = len(inputs) > 1;
    reporter = Reporter(options);
    if tool_name == "image2braille" and args.color:
        default_extension = ".ansi";
    for input_path in inputs:
        image, backgrounds = prepare_image(input_path, args.background, args.contrast, args.crop);
        lines = renderer(image, backgrounds, args);
        text = decorate_lines(lines, args.width, args.left_label, args.bottom_label);
        output_path = output_path_for(input_path, options, default_extension, multiple);
        write_text_output(text, output_path, options);
        destination = "standard output" if output_path is None else f"'{output_path}'";
        reporter.success(f"Rendered '{input_path}' to {destination}.");
    return (0);


def image2text_main(arguments: list[str] | None, options: GlobalOptions) -> int:
    return (main_for("image2text", arguments, options));


def image2ansi_main(arguments: list[str] | None, options: GlobalOptions) -> int:
    return (main_for("image2ansi", arguments, options));


def image2braille_main(arguments: list[str] | None, options: GlobalOptions) -> int:
    return (main_for("image2braille", arguments, options));
