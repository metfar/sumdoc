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

from sumdoc.common import GlobalOptions, Reporter, require_input_file, resolve_single_output, write_text_output;


CONSOLE_MARKERS = ("===", "---", "Dep. Variable:", "Model:", "In [", "Out[");


def import_ocr_modules():
    try:
        import cv2;
        import pytesseract;
    except ImportError as error:
        raise ImportError("opencv-python and pytesseract are required for png2text.") from error;
    return (cv2, pytesseract);


def try_extract_table(image_path: Path, language: str):
    try:
        from img2table.document import Image;
        from img2table.ocr import TesseractOCR;
    except ImportError:
        return (None);
    ocr = TesseractOCR(lang=language);
    document = Image(str(image_path));
    tables = document.extract_tables(ocr=ocr, implicit_rows=True, borderless_tables=True);
    if not tables:
        return (None);
    return (tables[0].df);


def extract_text(image_path: Path, language: str, psm: int, scale: float,
                 cv2, pytesseract) -> str:
    image = cv2.imread(str(image_path));
    if image is None:
        raise ValueError(f"OpenCV could not read the image: '{image_path}'.");
    if scale != 1.0:
        image = cv2.resize(image, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC);
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY);
    text = pytesseract.image_to_string(gray, config=f"--psm {psm}", lang=language).strip();
    return (f"```text\n{text}\n```\n");


def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="png2text",
        description="Extract Markdown text, code, or tables from an image using local OCR.",
    );
    parser.add_argument("image", help="Input image file.");
    parser.add_argument("--name", help="Base output name used with --output-dir.");
    parser.add_argument("--lang", default="eng", help="Tesseract language code. Default: eng.");
    parser.add_argument("--psm", type=int, default=4, help="Tesseract page segmentation mode. Default: 4.");
    parser.add_argument("--scale", type=float, default=2.0, help="Image scaling factor before OCR. Default: 2.0.");
    parser.add_argument("--empty-threshold", type=float, default=0.20, help="Reject table detection above this empty-cell ratio. Default: 0.20.");
    parser.add_argument("--no-table-detection", action="store_true", help="Skip img2table table detection.");
    parser.add_argument("--plain", action="store_true", help="Do not wrap OCR text in a Markdown code block.");
    parser.add_argument("--encoding", default="utf-8", help="Output encoding. Default: utf-8.");
    return (parser);


def main(arguments: list[str] | None, options: GlobalOptions) -> int:
    args = create_parser().parse_args(arguments);
    reporter = Reporter(options);
    image_path = require_input_file(args.image, (".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff", ".webp"));
    cv2, pytesseract = import_ocr_modules();
    preview = cv2.imread(str(image_path), cv2.IMREAD_GRAYSCALE);
    if preview is None:
        raise ValueError(f"OpenCV could not read the image: '{image_path}'.");
    quick_text = pytesseract.image_to_string(preview, config="--psm 3", lang=args.lang);
    console_like = any(marker in quick_text for marker in CONSOLE_MARKERS);
    result = None;
    if console_like:
        reporter.verbose("Console or statistical-report pattern detected; table detection was skipped.");
    elif not args.no_table_detection:
        dataframe = try_extract_table(image_path, args.lang);
        if dataframe is None:
            reporter.verbose("No table was detected, or img2table is not installed.");
        elif dataframe.empty:
            reporter.verbose("The detected table is empty.");
        else:
            empty_cells = dataframe.isna().sum().sum() + (dataframe == "").sum().sum();
            ratio = empty_cells / dataframe.size if dataframe.size else 1.0;
            if ratio <= args.empty_threshold:
                dataframe.columns = dataframe.iloc[0];
                dataframe = dataframe.iloc[1:];
                result = dataframe.to_markdown(index=False) + "\n";
                reporter.verbose("A valid table structure was detected.");
            else:
                reporter.verbose(f"Detected table rejected because {ratio:.1%} of its cells are empty.");
    if result is None:
        result = extract_text(image_path, args.lang, args.psm, args.scale, cv2, pytesseract);
        if args.plain and result.startswith("```text\n"):
            result = result[len("```text\n"):];
            if result.endswith("\n```\n"):
                result = result[:-5] + "\n";
    output_path = resolve_single_output(image_path, options, ".md", args.name);
    write_text_output(result, output_path, options, args.encoding);
    if output_path is not None:
        reporter.success(f"Markdown written to: {output_path}");
    return (0);
