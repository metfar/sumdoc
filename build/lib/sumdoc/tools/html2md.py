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

from sumdoc.common import GlobalOptions, Reporter, read_text_input, resolve_single_output, write_text_output;


def import_markdownify():
    try:
        import markdownify;
    except ImportError as error:
        raise ImportError("markdownify is required for html2md.") from error;
    return (markdownify);


def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="html2md", description="Convert HTML to Markdown.");
    parser.add_argument("input", nargs="?", default="-", help="HTML input file, or - for stdin. Default: stdin.");
    parser.add_argument("--name", help="Base output name when stdin is combined with --output-dir.");
    parser.add_argument(
        "--heading-style",
        choices=("ATX", "ATX_CLOSED", "SETEXT", "UNDERLINED"),
        default="ATX",
        help="Markdown heading style. Default: ATX.",
    );
    parser.add_argument("--bullets", default="*+-", help="Bullet characters to cycle through. Default: *+-.");
    parser.add_argument("--strip", nargs="*", help="HTML tags to remove while retaining their contents.");
    parser.add_argument("--encoding", default="utf-8", help="Text encoding. Default: utf-8.");
    return (parser);


def main(arguments: list[str] | None, options: GlobalOptions) -> int:
    args = create_parser().parse_args(arguments);
    reporter = Reporter(options);
    html_text, input_path = read_text_input(args.input, args.encoding);
    markdownify = import_markdownify();
    markdown_text = markdownify.markdownify(
        html_text,
        heading_style=args.heading_style,
        bullets=args.bullets,
        strip=args.strip,
    );
    output_path = resolve_single_output(input_path, options, ".md", args.name);
    write_text_output(markdown_text, output_path, options, args.encoding);
    if output_path is not None:
        reporter.success(f"Markdown written to: {output_path}");
    return (0);
