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

"""Convert editable Sum help Markdown to and from versioned ``.helpdb``.""";

import argparse;
from pathlib import Path;
import sys;

from sumdoc.common import GlobalOptions, Reporter, check_writable;
from sumdoc.helpdb import HelpCorpus;


def _read_text(path_text: str, encoding: str) -> tuple[str, Path | None]:
    if path_text == "-":
        return (sys.stdin.read(), None);
    path = Path(path_text).expanduser().resolve();
    if not path.exists():
        raise FileNotFoundError(f"Input file does not exist: '{path}'.");
    if not path.is_file():
        raise IsADirectoryError(f"Input is not a regular file: '{path}'.");
    return (path.read_text(encoding=encoding), path);


def _output_path(input_path: Path | None, positional_output: str | None,
                 options: GlobalOptions, extension: str) -> Path | None:
    if positional_output is not None and (options.output is not None or options.output_dir is not None):
        raise ValueError("Use either a positional output file or -o/--output/--output-dir, not both.");
    if positional_output == "-" or options.output == "-":
        return (None);
    if positional_output is not None:
        return (Path(positional_output).expanduser().resolve());
    if options.output is not None:
        return (Path(options.output).expanduser().resolve());
    if options.output_dir is not None:
        if input_path is None:
            raise ValueError("--output-dir requires a file input; use -o with stdin.");
        return (Path(options.output_dir).expanduser().resolve() / input_path.with_suffix(extension).name);
    if input_path is None:
        return (None);
    return (input_path.with_suffix(extension));


def _write_text(text: str, output_path: Path | None, options: GlobalOptions,
                encoding: str) -> None:
    if output_path is None:
        sys.stdout.write(text);
        if text and not text.endswith("\n"):
            sys.stdout.write("\n");
        return;
    output_path.parent.mkdir(parents=True, exist_ok=True);
    check_writable(output_path, options.force);
    output_path.write_text(text, encoding=encoding);


def create_markdown2helpdb_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="markdown2helpdb",
        description="Compile editable Markdown help to a versioned .helpdb JSON file.",
    );
    parser.add_argument("input", nargs="?", default="-", help="Markdown input file, or - for stdin.");
    parser.add_argument("output", nargs="?", help="Optional output file. Default: INPUT.helpdb; stdin defaults to stdout.");
    parser.add_argument("--encoding", default="utf-8", help="Text encoding. Default: utf-8.");
    parser.add_argument("--indent", type=int, default=2, help="JSON indentation. Default: 2.");
    return (parser);


def create_helpdb2markdown_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="helpdb2markdown",
        description="Reconstruct editable Markdown from a versioned .helpdb JSON file.",
    );
    parser.add_argument("input", nargs="?", default="-", help=".helpdb input file, or - for stdin.");
    parser.add_argument("output", nargs="?", help="Optional output file. Default: INPUT.md; stdin defaults to stdout.");
    parser.add_argument("--encoding", default="utf-8", help="Text encoding. Default: utf-8.");
    return (parser);


def markdown2helpdb_main(arguments: list[str] | None, options: GlobalOptions) -> int:
    args = create_markdown2helpdb_parser().parse_args(arguments);
    reporter = Reporter(options);
    source, input_path = _read_text(args.input, args.encoding);
    corpus = HelpCorpus.from_markdown(source);
    output_path = _output_path(input_path, args.output, options, ".helpdb");
    _write_text(corpus.to_helpdb(indent=args.indent), output_path, options, args.encoding);
    if output_path is not None:
        reporter.success(f"Help database written to: {output_path}");
    return (0);


def helpdb2markdown_main(arguments: list[str] | None, options: GlobalOptions) -> int:
    args = create_helpdb2markdown_parser().parse_args(arguments);
    reporter = Reporter(options);
    source, input_path = _read_text(args.input, args.encoding);
    corpus = HelpCorpus.from_helpdb(source);
    output_path = _output_path(input_path, args.output, options, ".md");
    _write_text(corpus.to_markdown(), output_path, options, args.encoding);
    if output_path is not None:
        reporter.success(f"Markdown help written to: {output_path}");
    return (0);


def _direct_entry() -> int:
    from sumdoc.cli import entry_point;
    return (entry_point(sys.argv[1:]));


def markdown2helpdb_entry_point() -> int:
    return (_direct_entry());


def helpdb2markdown_entry_point() -> int:
    return (_direct_entry());


if __name__ == "__main__":
    from sumdoc.cli import entry_point;
    raise SystemExit(entry_point(["markdown2helpdb"] + sys.argv[1:]));
