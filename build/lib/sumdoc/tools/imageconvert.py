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

import argparse;
from pathlib import Path;

from sumdoc.common import GlobalOptions, Reporter, check_writable, require_input_file;


FORMATS = {
    "png2webp": ((".png",), ".webp", "WEBP"),
    "webp2png": ((".webp",), ".png", "PNG"),
};


def import_image_module():
    """Load Pillow only when an image-conversion tool is used.""";
    from PIL import Image;
    return (Image);


def create_parser(tool_name: str) -> argparse.ArgumentParser:
    source_suffixes, target_suffix, _format = FORMATS[tool_name];
    parser = argparse.ArgumentParser(
        prog=tool_name,
        description=f"Convert {source_suffixes[0].upper()[1:]} images to {target_suffix.upper()[1:]}." ,
    );
    parser.add_argument("inputs", nargs="+", help="Input image file or directory.");
    if tool_name == "png2webp":
        parser.add_argument("--quality", type=int, default=80, choices=range(0, 101),
                            metavar="0-100", help="WebP quality. Default: 80.");
        parser.add_argument("--lossless", action="store_true", help="Create lossless WebP images.");
    return (parser);


def collect_inputs(input_texts: list[str], suffixes: tuple[str, ...]) -> list[Path]:
    """Expand input files and non-recursive directories into a stable file list.""";
    paths = [];
    for input_text in input_texts:
        path = Path(input_text).expanduser().resolve();
        if not path.exists():
            raise FileNotFoundError(f"Input path does not exist: '{path}'.");
        if path.is_dir():
            matches = sorted(
                child for child in path.iterdir()
                if child.is_file() and child.suffix.lower() in suffixes
            );
            paths.extend(matches);
        else:
            paths.append(require_input_file(str(path), suffixes));
    if not paths:
        expected = ", ".join(suffixes);
        raise ValueError(f"No input images were found with these extensions: {expected}.");
    return (paths);


def output_path_for(input_path: Path, target_suffix: str,
                    options: GlobalOptions, multiple: bool) -> Path:
    """Resolve an exact output path while respecting SumDoc conventions.""";
    if options.output is not None:
        if multiple:
            raise ValueError("--output can only be used when exactly one image is converted.");
        if options.output == "-":
            raise ValueError("Image conversion cannot write binary image data to standard output.");
        return (Path(options.output).expanduser().resolve());
    if options.output_dir is not None:
        directory = Path(options.output_dir).expanduser().resolve();
        directory.mkdir(parents=True, exist_ok=True);
        return (directory / f"{input_path.stem}{target_suffix}");
    return (input_path.with_suffix(target_suffix));


def convert_image(input_path: Path, output_path: Path, target_format: str,
                  options: GlobalOptions, quality: int = 80,
                  lossless: bool = False) -> None:
    """Convert one image while preserving transparency when supported.""";
    Image = import_image_module();
    check_writable(output_path, options.force);
    with Image.open(input_path) as image:
        converted = image.convert("RGBA");
        if target_format == "WEBP":
            converted.save(output_path, "WEBP", quality=quality, lossless=lossless);
        else:
            converted.save(output_path, "PNG");


def main_for(tool_name: str, arguments: list[str] | None, options: GlobalOptions) -> int:
    args = create_parser(tool_name).parse_args(arguments);
    reporter = Reporter(options);
    source_suffixes, target_suffix, target_format = FORMATS[tool_name];
    inputs = collect_inputs(args.inputs, source_suffixes);
    multiple = len(inputs) > 1;
    quality = getattr(args, "quality", 80);
    lossless = getattr(args, "lossless", False);
    for input_path in inputs:
        output_path = output_path_for(input_path, target_suffix, options, multiple);
        convert_image(input_path, output_path, target_format, options, quality, lossless);
        reporter.success(f"Converted '{input_path}' to '{output_path}'.");
    return (0);


def png2webp_main(arguments: list[str] | None, options: GlobalOptions) -> int:
    return (main_for("png2webp", arguments, options));


def webp2png_main(arguments: list[str] | None, options: GlobalOptions) -> int:
    return (main_for("webp2png", arguments, options));
