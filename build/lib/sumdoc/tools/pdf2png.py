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
import sys;

from sumdoc.common import GlobalOptions, Reporter, check_writable, require_input_file;


POINTS_PER_INCH = 72.0;
A4_WIDTH_PT = 595.275590551;
A4_HEIGHT_PT = 841.889763780;
VALID_DPI = (300, 600);


def import_fitz():
    try:
        import pymupdf as fitz;
    except ImportError:
        try:
            import fitz;
        except ImportError as error:
            raise ImportError("PyMuPDF is required for pdf2png.") from error;
    return (fitz);


def parse_pages(specification: str | None, total_pages: int) -> list[int]:
    """Convert a 1-based expression such as 1,3-5 into zero-based indexes.""";
    if not specification:
        return (list(range(total_pages)));
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
            pages.update(range(start, end + 1));
        else:
            if not item.isdigit():
                raise ValueError(f"Invalid page number: '{item}'.");
            pages.add(int(item));
    invalid = sorted(number for number in pages if number < 1 or number > total_pages);
    if invalid:
        values = ", ".join(str(number) for number in invalid);
        raise ValueError(f"Page number(s) out of range: {values}. The PDF has {total_pages} page(s).");
    return (sorted(number - 1 for number in pages));


def page_render_area(page, fitz):
    rectangle = page.rect;
    if rectangle.width > 0 and rectangle.height > 0:
        return (None, False);
    return (fitz.Rect(0.0, 0.0, A4_WIDTH_PT, A4_HEIGHT_PT), True);


def render_page(page, dpi: int, fitz, area=None):
    arguments = {"colorspace": fitz.csRGB, "alpha": False};
    if area is not None:
        arguments["clip"] = area;
    try:
        return (page.get_pixmap(dpi=dpi, **arguments));
    except TypeError:
        scale = dpi / POINTS_PER_INCH;
        pixmap = page.get_pixmap(matrix=fitz.Matrix(scale, scale), **arguments);
        if hasattr(pixmap, "set_dpi"):
            pixmap.set_dpi(dpi, dpi);
        return (pixmap);


def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="pdf2png",
        description="Render selected PDF pages as individual 300 or 600 DPI PNG files.",
    );
    parser.add_argument("pdf", help="Input PDF file.");
    parser.add_argument(
        "--dpi",
        type=int,
        choices=VALID_DPI,
        default=300,
        help="Output resolution. Choices: 300 or 600. Default: 300.",
    );
    parser.add_argument(
        "-p", "--pages",
        help="Pages to render, for example: 1, 1,3,5, or 2-6. Default: all pages.",
    );
    parser.add_argument("--prefix", help="Generated filename prefix. Default: the PDF filename stem.");
    parser.add_argument("--password", help="Password for an encrypted PDF.");
    return (parser);


def main(arguments: list[str] | None, options: GlobalOptions) -> int:
    args = create_parser().parse_args(arguments);
    reporter = Reporter(options);
    fitz = import_fitz();
    pdf_path = require_input_file(args.pdf, (".pdf",));
    document = fitz.open(str(pdf_path));
    generated = 0;
    try:
        if document.needs_pass:
            if not args.password:
                raise PermissionError("The PDF is encrypted. Use --password to open it.");
            if not document.authenticate(args.password):
                raise PermissionError("The supplied PDF password is not valid.");
        total_pages = document.page_count;
        if total_pages == 0:
            raise ValueError("The PDF does not contain any pages.");
        selected = parse_pages(args.pages, total_pages);
        if options.output is not None and len(selected) != 1:
            raise ValueError("--output can only be used when exactly one PDF page is selected. Use --output-dir for multiple pages.");
        if options.output_dir is not None:
            output_dir = Path(options.output_dir).expanduser().resolve();
        elif options.output is None:
            output_dir = pdf_path.parent / f"{pdf_path.stem}_png";
        else:
            output_dir = None;
        if output_dir is not None:
            output_dir.mkdir(parents=True, exist_ok=True);
        prefix = args.prefix or pdf_path.stem;
        digits = max(3, len(str(total_pages)));
        reporter.info(f"Input PDF: {pdf_path}");
        reporter.info(f"Selected pages: {len(selected)} of {total_pages}");
        reporter.info(f"Resolution: {args.dpi} DPI");
        for index in selected:
            page_number = index + 1;
            if options.output == "-":
                output_path = None;
            elif options.output is not None:
                output_path = Path(options.output).expanduser().resolve();
            else:
                filename = f"{prefix}_page_{page_number:0{digits}d}.png";
                output_path = output_dir / filename;
            if output_path is not None and output_path.exists() and not options.force:
                reporter.warning(f"Skipped existing file: {output_path}");
                continue;
            if output_path is not None:
                check_writable(output_path, True);
            page = document.load_page(index);
            area, used_a4 = page_render_area(page, fitz);
            if used_a4:
                reporter.warning(f"Page {page_number} has no valid dimensions; A4 is being used as a fallback.");
            pixmap = render_page(page, args.dpi, fitz, area);
            if output_path is None:
                sys.stdout.buffer.write(pixmap.tobytes("png"));
                sys.stdout.buffer.flush();
                destination = "standard output";
            else:
                pixmap.save(str(output_path));
                destination = str(output_path);
            generated += 1;
            reporter.success(
                f"Page {page_number}/{total_pages}: {destination} ({pixmap.width}x{pixmap.height} px)"
            );
    finally:
        document.close();
    reporter.info(f"Generated {generated} PNG file(s).");
    return (0);
