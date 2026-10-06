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

"""Interactive document/help browser entry point.""";

import argparse;

from sumdoc.common import GlobalOptions;
from sumdoc.helpview import load_help_source;


def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="sumdoc help",
        description="Explore Markdown, .helpdb, or a Markdown directory with the SUM HelpBrowser.",
    );
    parser.add_argument("source", help="Markdown/.helpdb file or directory containing Markdown documents.");
    parser.add_argument("--topic", help="Open a topic/section initially.");
    parser.add_argument("--query", default="", help="Initial topic filter/search text.");
    parser.add_argument("--title", help="Override the document/help title.");
    parser.add_argument("--theme", default="DOS", help="SUM UI theme. Default: DOS.");
    parser.add_argument("--backend", default="tui", choices=("tui", "gui"), help="Viewer backend. Default: tui.");
    return (parser);


def _run_browser(corpus, args) -> int:
    from sumtui import run_help_browser;
    result = run_help_browser(
        corpus,
        title=args.title or getattr(corpus, "title", "SUM Documentation"),
        topic=args.topic,
        query=args.query,
        theme=args.theme,
        backend=args.backend,
    );
    return (int(result or 0));


def help_main(arguments: list[str] | None, options: GlobalOptions) -> int:
    if options.output is not None or options.output_dir is not None:
        raise ValueError("sumdoc help is interactive and does not use --output/--output-dir.");
    args = create_parser().parse_args(arguments);
    corpus = load_help_source(args.source, title=args.title);
    return (_run_browser(corpus, args));
