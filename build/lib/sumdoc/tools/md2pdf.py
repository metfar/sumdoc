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

from sumdoc.common import GlobalOptions, Reporter, read_text_input, resolve_single_output, write_binary_output;
from sumdoc.tools.md2html import DEFAULT_CSS, build_document;


def import_weasyprint():
    """Import WeasyPrint only when md2pdf is used.""";
    try:
        from weasyprint import HTML;
    except ImportError as error:
        raise ImportError("WeasyPrint is required for md2pdf.") from error;
    return (HTML);


def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="md2pdf", description="Convert Markdown or terminal text to PDF.");
    parser.add_argument("input", nargs="?", default="-", help="Markdown input file, or - for stdin. Default: stdin.");
    parser.add_argument("--name", help="Base output name when stdin is combined with --output-dir.");
    parser.add_argument("--title", help="Document title. Default: the input filename stem or Document.");
    parser.add_argument("--css", help="CSS file to embed in the generated PDF.");
    parser.add_argument("--base-url", help="Base URL used to resolve relative images and links.");
    parser.add_argument(
        "--line-breaks", "--hard-wrap",
        action="store_true",
        help="Render every input newline as a line break while retaining Markdown parsing.",
    );
    parser.add_argument(
        "--terminal", "--preformatted",
        action="store_true",
        help="Render input as preformatted terminal text instead of parsing it as Markdown.",
    );
    parser.add_argument(
        "--ansi",
        action="store_true",
        help="Convert ANSI SGR colors and styles. This implies --terminal.",
    );
    parser.add_argument("--encoding", default="utf-8", help="Text encoding. Default: utf-8.");
    return (parser);


def main(arguments: list[str] | None, options: GlobalOptions) -> int:
    args = create_parser().parse_args(arguments);
    reporter = Reporter(options);
    markdown_text, input_path = read_text_input(args.input, args.encoding);
    title = args.title or (input_path.stem if input_path is not None else args.name or "Document");
    css_text = DEFAULT_CSS;
    if args.css:
        css_text = Path(args.css).expanduser().resolve().read_text(encoding=args.encoding);
    html_text = build_document(
        markdown_text,
        title,
        css_text,
        fragment=False,
        line_breaks=args.line_breaks,
        terminal=args.terminal,
        use_ansi=args.ansi,
    );
    HTML = import_weasyprint();
    if args.base_url:
        base_url = args.base_url;
    elif input_path is not None:
        base_url = str(input_path.parent);
    else:
        base_url = None;
    pdf_bytes = HTML(string=html_text, base_url=base_url).write_pdf();
    output_path = resolve_single_output(input_path, options, ".pdf", args.name);
    write_binary_output(pdf_bytes, output_path, options);
    if output_path is not None:
        reporter.success(f"PDF written to: {output_path}");
    return (0);
