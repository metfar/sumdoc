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
import re;
import sys;

from sumdoc.common import GlobalOptions, Reporter, check_writable;


_TABLE_DIVIDER_CELL = re.compile(r"^\s*:?-{3,}:?\s*$");


def import_rich():
    """Import Rich only when terminal-rich Markdown rendering is requested.""";
    try:
        from rich import box;
        from rich.console import Console;
        from rich.markdown import Markdown;
        from rich.table import Table;
    except ImportError as error:
        raise ImportError("Rich is required for md2rich/lessrich.") from error;
    return (box, Console, Markdown, Table);


def _split_table_row(line: str) -> list[str]:
    """Split a Markdown table row while preserving escaped vertical bars.""";
    source = line.strip();
    if source.startswith("|"):
        source = source[1:];
    if source.endswith("|") and not source.endswith(r"\|"):
        source = source[:-1];
    cells = [];
    buffer = [];
    escaped = False;
    code = False;
    for character in source:
        if escaped:
            if character == "|":
                buffer.append("|");
            else:
                buffer.append("\\");
                buffer.append(character);
            escaped = False;
            continue;
        if character == "\\":
            escaped = True;
            continue;
        if character == "`":
            code = not code;
            buffer.append(character);
            continue;
        if character == "|" and not code:
            cells.append("".join(buffer).strip());
            buffer = [];
            continue;
        buffer.append(character);
    if escaped:
        buffer.append("\\");
    cells.append("".join(buffer).strip());
    return (cells);


def _table_alignment(divider_cell: str) -> str:
    cell = divider_cell.strip();
    left = cell.startswith(":");
    right = cell.endswith(":");
    if left and right:
        return ("center");
    if right:
        return ("right");
    return ("left");


def _is_divider_row(line: str, expected_columns: int) -> bool:
    cells = _split_table_row(line);
    if len(cells) != expected_columns:
        return (False);
    return (all(_TABLE_DIVIDER_CELL.match(cell) is not None for cell in cells));


def _render_table(console, Table, box, header_line: str, divider_line: str,
                  data_lines: list[str]) -> None:
    headers = _split_table_row(header_line);
    dividers = _split_table_row(divider_line);
    table = Table(show_header=True, header_style="bold cyan", box=box.HEAVY_HEAD);
    for header, divider in zip(headers, dividers):
        table.add_column(header, justify=_table_alignment(divider));
    for row_line in data_lines:
        cells = _split_table_row(row_line);
        if len(cells) < len(headers):
            cells.extend([""] * (len(headers) - len(cells)));
        elif len(cells) > len(headers):
            cells = cells[:len(headers) - 1] + [" | ".join(cells[len(headers) - 1:])];
        table.add_row(*cells);
    console.print(table);


def render_markdown(console, text: str) -> None:
    """Render Markdown using Rich, with SumDoc table alignment and borders.""";
    box, _Console, Markdown, Table = import_rich();
    lines = text.splitlines();
    buffer = [];
    index = 0;

    def flush_buffer() -> None:
        if not buffer:
            return;
        console.print(Markdown("\n".join(buffer)));
        buffer.clear();

    while index < len(lines):
        if index + 1 < len(lines):
            headers = _split_table_row(lines[index]);
            if len(headers) > 1 and _is_divider_row(lines[index + 1], len(headers)):
                flush_buffer();
                data_lines = [];
                cursor = index + 2;
                while cursor < len(lines):
                    row = lines[cursor];
                    if not row.strip():
                        break;
                    cells = _split_table_row(row);
                    if len(cells) <= 1:
                        break;
                    data_lines.append(row);
                    cursor += 1;
                _render_table(console, Table, box, lines[index], lines[index + 1], data_lines);
                index = cursor;
                continue;
        buffer.append(lines[index]);
        index += 1;
    flush_buffer();


def _read_inputs(inputs: list[str], encoding: str) -> str:
    if not inputs or inputs == ["-"]:
        return (sys.stdin.read());
    chunks = [];
    for input_name in inputs:
        if input_name == "-":
            chunks.append(sys.stdin.read());
            continue;
        path = Path(input_name).expanduser().resolve();
        if not path.exists():
            raise FileNotFoundError(f"Input file does not exist: '{path}'.");
        if not path.is_file():
            raise ValueError(f"Input path is not a file: '{path}'.");
        chunks.append(path.read_text(encoding=encoding));
    return ("\n".join(chunks));


def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="lessrich",
        description="Read Markdown as rich terminal text.",
    );
    parser.add_argument("input", nargs="*", help="Markdown files, or - for stdin. Default: stdin.");
    parser.add_argument("--width", type=int, help="Rendering width in terminal columns.");
    parser.add_argument("--no-color", action="store_true", help="Disable ANSI colors and styles.");
    parser.add_argument("--encoding", default="utf-8", help="Text encoding. Default: utf-8.");
    return (parser);


def main(arguments: list[str] | None, options: GlobalOptions) -> int:
    args = create_parser().parse_args(arguments);
    reporter = Reporter(options);
    _box, Console, _Markdown, _Table = import_rich();
    source = _read_inputs(args.input, args.encoding);
    output_handle = None;
    try:
        if options.output not in (None, "-"):
            output_path = Path(options.output).expanduser().resolve();
            check_writable(output_path, options.force);
            output_handle = output_path.open("w", encoding=args.encoding);
            stream = output_handle;
        else:
            if options.output_dir is not None:
                raise ValueError("lessrich/md2rich does not support --output-dir; use --output for one rendered stream.");
            stream = sys.stdout;
        console = Console(
            file=stream,
            width=args.width,
            color_system=None if args.no_color else "auto",
            force_terminal=False if args.no_color else None,
        );
        render_markdown(console, source);
    finally:
        if output_handle is not None:
            output_handle.close();
    if options.output not in (None, "-"):
        reporter.success(f"Rich Markdown written to: {Path(options.output).expanduser().resolve()}");
    return (0);
