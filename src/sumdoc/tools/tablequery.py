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

"""Small read-only SQL console for SUMTAB collections.

A directory acts as a catalog root. SUMTAB files in the root are unqualified
SQL tables; first-level subdirectories act as SQL schemas, so
``HR/DEPARTMENTS.sumtab`` is addressed as ``HR.DEPARTMENTS``.

The query engine is SQLite from Python's standard library. SUMTAB remains the
storage format; only tables referenced by a SELECT are materialized into an
in-memory SQLite database for the duration of the command.
""";

import argparse;
from sumui.cli import SumArgumentParser;
from datetime import date, datetime, time;
from decimal import Decimal;
from pathlib import Path;
import re;
import sqlite3;

from sumdoc.common import GlobalOptions, Reporter;
from sumdoc.sumtab import SumColumn, SumTable, read_sumtab;


_SELECT_TABLE_RE = re.compile(
    r"(?is)\b(?:from|join)\s+((?:[A-Za-z_][\w$]*\.)?[A-Za-z_][\w$]*)"
);


def create_parser() -> argparse.ArgumentParser:
    parser = SumArgumentParser(
        prog="tablequery",
        description="Run simple read-only SQL queries against SUMTAB files.",
    );
    parser.add_argument(
        "path",
        nargs="?",
        default=".",
        help=(
            "SUMTAB file or catalog directory. First-level directories are schemas. "
            "Default: current directory."
        ),
    );
    parser.add_argument(
        "-e", "--execute",
        help="Execute one command and exit. Without this option an interactive console is started.",
    );
    return (parser);


def _quote(identifier: str) -> str:
    return ('"{}"'.format(identifier.replace('"', '""')));


def _case_match(directory: Path, wanted: str, suffix: str | None = None) -> Path | None:
    if not directory.is_dir():
        return (None);
    wanted_lower = wanted.lower();
    for child in directory.iterdir():
        name = child.stem if suffix and child.is_file() and child.suffix.lower() == suffix else child.name;
        if name.lower() == wanted_lower:
            if suffix is None or (child.is_file() and child.suffix.lower() == suffix):
                return (child);
    return (None);


def _catalog_root(path: Path) -> Path:
    if path.is_dir():
        return (path.resolve());
    if path.is_file() and path.suffix.lower() == ".sumtab":
        return (path.parent.resolve());
    raise FileNotFoundError("SUMTAB catalog path was not found: '{}'".format(path));


def _schemas(root: Path) -> list[str]:
    names = [];
    if any(root.glob("*.sumtab")):
        names.append("<root>");
    for directory in sorted((item for item in root.iterdir() if item.is_dir()), key=lambda p: p.name.lower()):
        if any(directory.glob("*.sumtab")):
            names.append(directory.name);
    return (names);


def _tables(root: Path, schema: str | None) -> list[str]:
    directory = root;
    if schema and schema.lower() not in ("<root>", "root", "."):
        matched = _case_match(root, schema);
        if matched is None or not matched.is_dir():
            raise ValueError("SUMTAB schema '{}' was not found.".format(schema));
        directory = matched;
    return ([path.stem for path in sorted(directory.glob("*.sumtab"), key=lambda p: p.name.lower())]);


def _resolve_table(root: Path, name: str, preferred_file: Path | None = None) -> tuple[str | None, str, Path]:
    if "." in name:
        schema, table = name.split(".", 1);
        directory = _case_match(root, schema);
        if directory is None or not directory.is_dir():
            raise ValueError("SUMTAB schema '{}' was not found.".format(schema));
        path = _case_match(directory, table, ".sumtab");
        if path is None:
            raise ValueError("SUMTAB table '{}.{}' was not found.".format(schema, table));
        return (directory.name, path.stem, path.resolve());

    if preferred_file is not None:
        if preferred_file.stem.lower() == name.lower():
            return (None, preferred_file.stem, preferred_file.resolve());
        if name.lower() == "table":
            # Convenient implicit alias when the console was opened on one
            # specific SUMTAB file: SELECT * FROM table.
            return (None, "table", preferred_file.resolve());

    path = _case_match(root, name, ".sumtab");
    if path is not None:
        return (None, path.stem, path.resolve());

    matches = [];
    for directory in root.iterdir():
        if not directory.is_dir():
            continue;
        candidate = _case_match(directory, name, ".sumtab");
        if candidate is not None:
            matches.append((directory.name, candidate.stem, candidate.resolve()));
    if len(matches) == 1:
        return (matches[0]);
    if len(matches) > 1:
        raise ValueError(
            "Table '{}' is ambiguous; qualify it as SCHEMA.TABLE.".format(name)
        );
    raise ValueError("SUMTAB table '{}' was not found.".format(name));


def _sqlite_type(column: SumColumn) -> str:
    if column.logical_type in ("INTEGER", "LOGICAL"):
        return ("INTEGER");
    if column.logical_type in ("NUMERIC", "FLOAT"):
        return ("REAL");
    if column.logical_type == "BLOB":
        return ("BLOB");
    return ("TEXT");


def _sqlite_value(value, column: SumColumn):
    if value is None:
        return (None);
    if column.logical_type == "LOGICAL":
        return (1 if bool(value) else 0);
    if isinstance(value, Decimal):
        return (float(value));
    if isinstance(value, (date, datetime, time)):
        return (value.isoformat());
    if isinstance(value, (list, tuple, set, dict)):
        return (str(value));
    return (value);


def _attach_schema(connection: sqlite3.Connection, schema: str) -> None:
    existing = [row[1].lower() for row in connection.execute("PRAGMA database_list")];
    if schema.lower() not in existing:
        connection.execute("ATTACH DATABASE ':memory:' AS {}".format(_quote(schema)));


def _load_table(connection: sqlite3.Connection, schema: str | None, table_name: str, path: Path) -> SumTable:
    table = read_sumtab(path);
    if schema is not None:
        _attach_schema(connection, schema);
        target = "{}.{}".format(_quote(schema), _quote(table_name));
    else:
        target = _quote(table_name);
    definitions = ", ".join(
        "{} {}".format(_quote(column.name), _sqlite_type(column))
        for column in table.columns
    );
    connection.execute("DROP TABLE IF EXISTS {}".format(target));
    connection.execute("CREATE TABLE {} ({})".format(target, definitions));
    if table.rows:
        placeholders = ",".join("?" for _ in table.columns);
        connection.executemany(
            "INSERT INTO {} VALUES ({})".format(target, placeholders),
            [
                tuple(_sqlite_value(value, column) for value, column in zip(row, table.columns))
                for row in table.rows
            ],
        );
    return (table);


def _format_value(value) -> str:
    if value is None:
        return ("NULL");
    if isinstance(value, bytes):
        return ("0x" + value.hex().upper());
    return (str(value));


def _is_numeric(value) -> bool:
    return (isinstance(value, (int, float, Decimal)) and not isinstance(value, bool));


def render_table(headers: list[str], rows: list[tuple]) -> str:
    text_rows = [[_format_value(value) for value in row] for row in rows];
    widths = [len(str(header)) for header in headers];
    for row in text_rows:
        for index, value in enumerate(row):
            widths[index] = max(widths[index], len(value));

    def border(left: str, middle: str, right: str, fill: str = "═") -> str:
        return (left + middle.join(fill * (width + 2) for width in widths) + right);

    lines = [border("╒", "╤", "╕")];
    header_cells = [" " + str(header).ljust(widths[index]) + " " for index, header in enumerate(headers)];
    lines.append("│" + "│".join(header_cells) + "│");
    lines.append(border("╞", "╪", "╡"));
    for row_index, (original, row) in enumerate(zip(rows, text_rows)):
        cells = [];
        for index, value in enumerate(row):
            if _is_numeric(original[index]):
                cells.append(" " + value.rjust(widths[index]) + " ");
            else:
                cells.append(" " + value.ljust(widths[index]) + " ");
        lines.append("│" + "│".join(cells) + "│");
        if row_index != len(text_rows) - 1:
            lines.append(border("├", "┼", "┤", "─"));
    lines.append(border("╘", "╧", "╛"));
    return ("\n".join(lines));


def _describe(root: Path, name: str, preferred_file: Path | None) -> str:
    schema, table_name, path = _resolve_table(root, name, preferred_file);
    table = read_sumtab(path);
    rows = [];
    for column in table.columns:
        flags = [];
        if column.primary_key:
            flags.append("PRIMARY KEY");
        if column.unique:
            flags.append("UNIQUE");
        if column.autoinum:
            flags.append("AUTOINUM");
        rows.append((
            column.name,
            column.declared_type or column.logical_type,
            "YES" if column.nullable else "NO",
            ", ".join(flags),
            column.default or "",
        ));
    title = "{}.{}".format(schema, table_name) if schema else table_name;
    output = [title, render_table(["COLUMN_NAME", "TYPE", "NULLABLE", "KEY", "DEFAULT"], rows)];
    if table.indexes:
        index_rows = [
            (index.name, ", ".join(index.columns), "YES" if index.unique else "NO", index.expression or "")
            for index in table.indexes
        ];
        output.extend(("", render_table(["INDEX_NAME", "COLUMNS", "UNIQUE", "EXPRESSION"], index_rows)));
    return ("\n".join(output));


def _select(root: Path, sql: str, preferred_file: Path | None) -> str:
    if not re.match(r"(?is)^\s*select\b", sql):
        raise ValueError("Only SELECT statements are allowed.");
    references = [];
    for match in _SELECT_TABLE_RE.finditer(sql):
        name = match.group(1);
        if name.lower() not in [item.lower() for item in references]:
            references.append(name);
    if not references:
        raise ValueError("SELECT must reference at least one SUMTAB table with FROM.");

    execution_sql = sql.rstrip().rstrip(";");
    if preferred_file is not None:
        # TABLE is a SQLite keyword.  When a single SUMTAB file is the catalog,
        # accept the convenient pseudo-name `table` and quote it before the
        # statement reaches SQLite.
        execution_sql = re.sub(
            r"(?is)\b(from|join)\s+table\b",
            lambda match: '{} "table"'.format(match.group(1)),
            execution_sql,
        );

    connection = sqlite3.connect(":memory:");
    try:
        loaded = set();
        for reference in references:
            schema, table_name, path = _resolve_table(root, reference, preferred_file);
            key = ((schema or "").lower(), table_name.lower());
            if key not in loaded:
                _load_table(connection, schema, table_name, path);
                loaded.add(key);
        cursor = connection.execute(execution_sql);
        headers = [description[0] for description in cursor.description or []];
        rows = cursor.fetchall();
        if not headers:
            return ("(no columns)");
        return (render_table(headers, rows));
    except sqlite3.Error as exc:
        raise ValueError("SQL error: {}".format(exc)) from exc;
    finally:
        connection.close();


def execute_command(root: Path, command: str, preferred_file: Path | None = None) -> str:
    text = command.strip();
    if not text:
        return ("");
    lowered = text.lower().rstrip(";").strip();
    if lowered in ("quit", "exit", ".quit", ".exit"):
        return ("__QUIT__");
    if lowered in ("help", "?", ".help"):
        return (
            "Commands:\n"
            "  list                         list SUMTAB schemas\n"
            "  show [SCHEMA]                list tables in a schema (or root)\n"
            "  describe [SCHEMA.]TABLE      show columns and indexes\n"
            "  select ... from TABLE ...    run a read-only SQL SELECT\n"
            "  quit                         leave the console"
        );
    if lowered == "list":
        rows = [(name,) for name in _schemas(root)];
        return (render_table(["SCHEMA_NAME"], rows) if rows else "(no SUMTAB schemas)");
    show_match = re.match(r"(?is)^show(?:\s+([A-Za-z_][\w$]*|<root>|\.))?\s*;?$", text);
    if show_match:
        schema = show_match.group(1);
        rows = [(name,) for name in _tables(root, schema)];
        return (render_table(["TABLE_NAME"], rows) if rows else "(no SUMTAB tables)");
    describe_match = re.match(r"(?is)^(?:describe|desc)\s+([A-Za-z_][\w$]*(?:\.[A-Za-z_][\w$]*)?)\s*;?$", text);
    if describe_match:
        return (_describe(root, describe_match.group(1), preferred_file));
    if re.match(r"(?is)^select\b", text):
        return (_select(root, text, preferred_file));
    raise ValueError("Unknown command. Type 'help' for the supported SUMTAB query commands.");


def main(arguments: list[str] | None, options: GlobalOptions) -> int:
    args = create_parser().parse_args(arguments);
    reporter = Reporter(options);
    path = Path(args.path).expanduser();
    preferred_file = path.resolve() if path.is_file() else None;
    root = _catalog_root(path);

    if args.execute is not None:
        result = execute_command(root, args.execute, preferred_file);
        if result and result != "__QUIT__":
            print(result);
        return (0);

    reporter.info("SUMTAB query console. Type 'help' for commands, 'quit' to leave.");
    while True:
        try:
            command = input("sumtab> ");
        except EOFError:
            print("");
            break;
        try:
            result = execute_command(root, command, preferred_file);
            if result == "__QUIT__":
                break;
            if result:
                print(result);
        except (FileNotFoundError, ValueError) as exc:
            print("Error: {}".format(exc));
    return (0);


__all__ = [
    "execute_command",
    "render_table",
    "main",
];
