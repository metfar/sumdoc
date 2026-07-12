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
from io import BytesIO;
import logging;
from pathlib import Path;
import sys;

from sumdoc.common import GlobalOptions, Reporter, check_writable, require_input_file;


FORMAT_EXTENSIONS = {"text": ".txt", "html": ".html", "xml": ".xml", "tag": ".tag"};


def import_pdfminer():
    try:
        import pdfminer.high_level;
        import pdfminer.layout;
    except ImportError as error:
        raise ImportError("pdfminer.six is required for pdf2txt.") from error;
    return (pdfminer.high_level, pdfminer.layout);


def parse_pages(specification: str | None) -> set[int] | None:
    if not specification:
        return (None);
    pages = set();
    for item in specification.replace(" ", "").split(","):
        if not item:
            continue;
        if "-" in item:
            limits = item.split("-", 1);
            if len(limits) != 2 or not limits[0].isdigit() or not limits[1].isdigit():
                raise ValueError(f"Invalid page range: '{item}'.");
            start = int(limits[0]);
            end = int(limits[1]);
            if start > end:
                start, end = end, start;
            if start < 1:
                raise ValueError("Page numbers begin at 1.");
            pages.update(range(start - 1, end));
        else:
            if not item.isdigit() or int(item) < 1:
                raise ValueError(f"Invalid page number: '{item}'.");
            pages.add(int(item) - 1);
    return (pages);


def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="pdf2txt",
        description="Extract text, HTML, XML, or tagged output from PDF files using pdfminer.six.",
    );
    parser.add_argument("files", nargs="+", help="One or more input PDF files.");
    parser.add_argument("-p", "--pages", help="Pages to extract, for example: 1,3-5. Default: all pages.");
    parser.add_argument("-m", "--max-pages", type=int, default=0, help="Maximum pages to extract. Zero means no limit.");
    parser.add_argument("-P", "--password", default="", help="Password for encrypted PDF files.");
    parser.add_argument("-R", "--rotation", type=int, default=0, help="Page rotation in degrees.");
    parser.add_argument(
        "--format", "--output-type",
        choices=("text", "html", "xml", "tag"),
        default="text",
        dest="output_type",
        help="Output format. Default: text.",
    );
    parser.add_argument("-c", "--codec", default="utf-8", help="Output encoding. Default: utf-8.");
    parser.add_argument("--image-dir", help="Directory used by pdfminer.six for extracted images.");
    parser.add_argument("--no-layout", action="store_true", help="Disable layout analysis parameters.");
    parser.add_argument("--detect-vertical", action="store_true", help="Consider vertical text during layout analysis.");
    parser.add_argument("--all-texts", action="store_true", help="Analyze text inside figures.");
    parser.add_argument("--char-margin", type=float, default=2.0);
    parser.add_argument("--word-margin", type=float, default=0.1);
    parser.add_argument("--line-margin", type=float, default=0.5);
    parser.add_argument("--boxes-flow", type=float, default=0.5);
    parser.add_argument("--layout-mode", choices=("normal", "exact", "loose"), default="normal");
    parser.add_argument("--scale", type=float, default=1.0, help="HTML output scale. Default: 1.0.");
    parser.add_argument("--strip-control", action="store_true", help="Strip control characters from XML output.");
    parser.add_argument("--disable-caching", action="store_true");
    parser.add_argument("--debug", action="store_true", help="Enable pdfminer.six debug logging.");
    return (parser);


def extract_one(path: Path, args, high_level, layout) -> bytes:
    if args.no_layout:
        laparams = None;
    else:
        laparams = layout.LAParams(
            all_texts=args.all_texts,
            detect_vertical=args.detect_vertical,
            word_margin=args.word_margin,
            char_margin=args.char_margin,
            line_margin=args.line_margin,
            boxes_flow=args.boxes_flow,
        );
    output = BytesIO();
    with path.open("rb") as input_stream:
        high_level.extract_text_to_fp(
            input_stream,
            output,
            output_type=args.output_type,
            codec=args.codec,
            laparams=laparams,
            maxpages=args.max_pages,
            page_numbers=parse_pages(args.pages),
            password=args.password,
            scale=args.scale,
            rotation=args.rotation,
            layoutmode=args.layout_mode,
            output_dir=args.image_dir,
            strip_control=args.strip_control,
            debug=args.debug,
            disable_caching=args.disable_caching,
        );
    return (output.getvalue());


def output_path_for(path: Path, args, options: GlobalOptions) -> Path | None:
    if options.output is not None:
        if len(args.files) != 1:
            raise ValueError("--output can only be used with one input PDF. Use --output-dir for multiple files.");
        if options.output == "-":
            return (None);
        return (Path(options.output).expanduser().resolve());
    if options.output_dir is not None:
        directory = Path(options.output_dir).expanduser().resolve();
        directory.mkdir(parents=True, exist_ok=True);
        return (directory / f"{path.stem}{FORMAT_EXTENSIONS[args.output_type]}");
    return (None);


def main(arguments: list[str] | None, options: GlobalOptions) -> int:
    args = create_parser().parse_args(arguments);
    reporter = Reporter(options);
    if args.output_type == "text" and options.output not in (None, "-"):
        suffix = Path(options.output).suffix.lower();
        inferred = {".htm": "html", ".html": "html", ".xml": "xml", ".tag": "tag"};
        args.output_type = inferred.get(suffix, args.output_type);
    high_level, layout = import_pdfminer();
    if args.debug:
        logging.basicConfig(level=logging.DEBUG);
    inputs = [require_input_file(value, (".pdf",)) for value in args.files];
    for index, path in enumerate(inputs):
        reporter.info(f"Extracting: {path}");
        data = extract_one(path, args, high_level, layout);
        output_path = output_path_for(path, args, options);
        if output_path is None:
            if index > 0 and args.output_type == "text":
                sys.stdout.buffer.write(b"\n");
            sys.stdout.buffer.write(data);
            sys.stdout.buffer.flush();
        else:
            check_writable(output_path, options.force);
            output_path.write_bytes(data);
            reporter.success(f"Output written to: {output_path}");
    return (0);
