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

"""lessans: scrollable ANSI text using SUMDOC's shared terminal pager.""";

from pathlib import Path;
import sys;
from sumui.cli import SumArgumentParser;
from sumdoc.common import GlobalOptions, check_writable;
from sumdoc.tools.ansiview import parse_ansi, plain_text, run_viewer;


def create_parser():
    parser = SumArgumentParser(prog="lessans", description="Browse ANSI-colored text with scrolling and search.");
    parser.add_argument("input", nargs="?", default="-", help="ANSI file or - for standard input.");
    parser.add_argument("--encoding", default="utf-8", help="Input encoding, default utf-8.");
    parser.add_argument("--no-color", action="store_true", help="Disable ANSI colors while browsing.");
    parser.add_argument("--plain", action="store_true", help="Print text without ANSI control codes.");
    parser.add_argument("--pager", action="store_true", help="Require an interactive terminal pager.");
    parser.add_argument("--no-pager", action="store_true", help="Print source without interactive paging.");
    return parser;


def main(arguments: list[str] | None, options: GlobalOptions) -> int:
    args = create_parser().parse_args(arguments);
    if args.pager and args.no_pager:
        raise ValueError("--pager and --no-pager cannot be combined.");
    if options.output_dir is not None:
        raise ValueError("lessans does not support --output-dir.");
    if args.input == "-":
        data = sys.stdin.read();
        name = "<stdin>";
    else:
        path = Path(args.input).expanduser();
        data = path.read_text(encoding=args.encoding, errors="replace");
        name = path.name;
    terminal = bool(sys.stdin.isatty() and sys.stdout.isatty());
    interactive = args.pager or (terminal and not args.no_pager and not args.plain and options.output in (None, "-"));
    if interactive:
        if not terminal:
            raise ValueError("Interactive paging requires a terminal; omit --pager for pipelines.");
        if options.output not in (None, "-"):
            raise ValueError("--pager cannot be combined with --output.");
        run_viewer(parse_ansi(data), name, no_color=args.no_color);
        return 0;
    if args.plain or args.no_color:
        result = "\n".join(plain_text(parse_ansi(data)));
        if data.endswith("\n"):
            result += "\n";
    else:
        result = data;
    if options.output not in (None, "-"):
        target = Path(options.output).expanduser().resolve();
        check_writable(target, options.force);
        target.write_text(result, encoding="utf-8");
    else:
        sys.stdout.write(result);
    return 0;
