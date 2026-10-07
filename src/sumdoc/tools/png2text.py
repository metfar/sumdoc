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
import shutil;
from pathlib import Path;

from sumdoc.common import GlobalOptions, Reporter, require_input_file, resolve_single_output, write_text_output;


CONSOLE_MARKERS = ("===", "---", "Dep. Variable:", "Model:", "In [", "Out[");
TERMINAL_MARKERS = ("#!/", "/bin/", "sudo ", "grep ", "sed ", "awk ", "cat ", "kill ", "unlink ", "$ ", "|", "> ");
OCR_MODES = ("auto", "document", "screen", "terminal");
MODE_DEFAULTS = {
    "document": (3, 2.0),
    "screen": (6, 4.0),
    "terminal": (6, 4.0),
};


def import_ocr_modules():
    try:
        import cv2;
        import pytesseract;
    except ImportError as error:
        raise ImportError("opencv-python and pytesseract are required for png2text.") from error;
    return (cv2, pytesseract);


def validate_tesseract(pytesseract, language: str) -> None:
    executable = getattr(pytesseract.pytesseract, "tesseract_cmd", "tesseract");
    if executable == "tesseract" and shutil.which(executable) is None:
        raise RuntimeError(
            "Tesseract OCR executable was not found. Install the system package first "
            "(Debian/Ubuntu: sudo apt install tesseract-ocr)."
        );
    if executable != "tesseract" and shutil.which(executable) is None and not Path(executable).is_file():
        raise RuntimeError(f"Configured Tesseract OCR executable was not found: '{executable}'.");
    try:
        installed_languages = set(pytesseract.get_languages(config=""));
    except pytesseract.TesseractNotFoundError as error:
        raise RuntimeError(
            "Tesseract OCR executable was not found or is not in PATH. "
            "On Debian/Ubuntu install it with: sudo apt install tesseract-ocr"
        ) from error;
    requested_languages = [item for item in language.split("+") if item];
    missing_languages = [item for item in requested_languages if item not in installed_languages];
    if missing_languages:
        missing = ", ".join(missing_languages);
        raise RuntimeError(
            f"Tesseract language data not installed: {missing}. "
            "Install the corresponding tesseract-ocr-<lang> package."
        );


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


def detect_mode(image, cv2, pytesseract, language: str) -> tuple[str, str]:
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY);
    preview = cv2.resize(gray, None, fx=2.0, fy=2.0, interpolation=cv2.INTER_CUBIC);
    quick_text = pytesseract.image_to_string(
        preview,
        config="--oem 1 --psm 6 -c preserve_interword_spaces=1",
        lang=language,
    );
    dark_ratio = float((gray < 96).sum()) / float(gray.size);
    terminal_score = sum(1 for marker in TERMINAL_MARKERS if marker in quick_text);
    console_score = sum(1 for marker in CONSOLE_MARKERS if marker in quick_text);
    if dark_ratio >= 0.55 and (terminal_score > 0 or console_score > 0):
        return ("terminal", quick_text);
    if dark_ratio >= 0.55:
        return ("screen", quick_text);
    if terminal_score >= 2:
        return ("terminal", quick_text);
    return ("document", quick_text);


def preprocess_image(image, mode: str, scale: float, cv2):
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY);
    if mode in ("screen", "terminal"):
        gray = cv2.resize(gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC);
        clahe = cv2.createCLAHE(clipLimit=1.5, tileGridSize=(8, 8));
        return (clahe.apply(gray));
    if scale != 1.0:
        gray = cv2.resize(gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC);
    return (gray);


def extract_text(image_path: Path, language: str, mode: str, psm: int | None,
                 scale: float | None, cv2, pytesseract) -> str:
    image = cv2.imread(str(image_path));
    if image is None:
        raise ValueError(f"OpenCV could not read the image: '{image_path}'.");
    selected_mode = mode;
    if selected_mode == "auto":
        selected_mode, _ = detect_mode(image, cv2, pytesseract, language);
    default_psm, default_scale = MODE_DEFAULTS[selected_mode];
    selected_psm = default_psm if psm is None else psm;
    selected_scale = default_scale if scale is None else scale;
    prepared = preprocess_image(image, selected_mode, selected_scale, cv2);
    config = f"--oem 1 --psm {selected_psm} -c preserve_interword_spaces=1";
    text = pytesseract.image_to_string(prepared, config=config, lang=language).strip();
    return (f"```text\n{text}\n```\n");


def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="png2text",
        description="Extract Markdown text, code, or tables from an image using local OCR.",
    );
    parser.add_argument("image", help="Input image file.");
    parser.add_argument("--name", help="Base output name used with --output-dir.");
    parser.add_argument("--lang", default="eng", help="Tesseract language code. Default: eng.");
    parser.add_argument(
        "--mode",
        choices=OCR_MODES,
        default="auto",
        help="OCR profile: auto, document, screen, or terminal. Default: auto.",
    );
    parser.add_argument(
        "--psm",
        type=int,
        default=None,
        help="Override Tesseract page segmentation mode. Defaults depend on --mode.",
    );
    parser.add_argument(
        "--scale",
        type=float,
        default=None,
        help="Override image scaling factor before OCR. Defaults: document=2, screen/terminal=4.",
    );
    parser.add_argument("--empty-threshold", type=float, default=0.20, help="Reject table detection above this empty-cell ratio. Default: 0.20.");
    parser.add_argument("--no-table-detection", action="store_true", help="Skip img2table table detection.");
    parser.add_argument("--plain", action="store_true", help="Do not wrap OCR text in a Markdown code block.");
    parser.add_argument("--encoding", default="utf-8", help="Output encoding. Default: utf-8.");
    return (parser);


def main(arguments: list[str] | None, options: GlobalOptions) -> int:
    args = create_parser().parse_args(arguments);
    if args.scale is not None and args.scale <= 0:
        raise ValueError("--scale must be greater than zero.");
    reporter = Reporter(options);
    image_path = require_input_file(args.image, (".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff", ".webp"));
    cv2, pytesseract = import_ocr_modules();
    validate_tesseract(pytesseract, args.lang);
    image = cv2.imread(str(image_path));
    if image is None:
        raise ValueError(f"OpenCV could not read the image: '{image_path}'.");
    selected_mode = args.mode;
    quick_text = "";
    if selected_mode == "auto":
        selected_mode, quick_text = detect_mode(image, cv2, pytesseract, args.lang);
        reporter.verbose(f"OCR mode automatically selected: {selected_mode}.");
    else:
        reporter.verbose(f"OCR mode selected: {selected_mode}.");
    console_like = selected_mode == "terminal" or any(marker in quick_text for marker in CONSOLE_MARKERS);
    result = None;
    if console_like:
        reporter.verbose("Console/terminal pattern detected; table detection was skipped.");
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
        result = extract_text(image_path, args.lang, selected_mode, args.psm, args.scale, cv2, pytesseract);
        if args.plain and result.startswith("```text\n"):
            result = result[len("```text\n"):];
            if result.endswith("\n```\n"):
                result = result[:-5] + "\n";
    output_path = resolve_single_output(image_path, options, ".md", args.name);
    write_text_output(result, output_path, options, args.encoding);
    if output_path is not None:
        reporter.success(f"Markdown written to: {output_path}");
    return (0);
