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

"""Convert tabular documents through SUMTAB's common table/schema model.""";

import argparse;
import csv;
from datetime import date, datetime;
from decimal import Decimal, InvalidOperation;
import gzip;
import hashlib;
import json;
import os;
from pathlib import Path;
import sqlite3;
import struct;
from typing import Iterable;

try:
    from sumcore.schema import canonical_type;
except ModuleNotFoundError as exc:
    if exc.name == "sumcore.schema":
        raise ImportError(
            "tableconvert requires sumcore>=0.1.0a22; upgrade sumCore before SumDoc."
        ) from exc;
    raise;
from sumdoc.common import GlobalOptions, Reporter, ensure_parent, require_input_file;
from sumdoc.sumtab import (
    SumColumn,
    SumIndex,
    SumTable,
    normalize_record_separator,
    normalize_separator,
    read_sumtab,
    write_sumtab,
);


FORMAT_SUFFIXES = {
    ".sumtab": "sumtab",
    ".csv": "csv",
    ".tsv": "tsv",
    ".sumx": "sumx",
    ".sqlite": "sqlite",
    ".sqlite3": "sqlite",
    ".db": "sqlite",
    ".dbf": "dbf",
    ".parquet": "parquet",
};

DBF_CODEPAGES = {
    0x01: "cp437",
    0x02: "cp850",
    0x03: "cp1252",
    0x57: "cp1252",
    0x64: "cp852",
    0x65: "cp866",
    0x66: "cp865",
    0xC8: "cp1250",
    0xC9: "cp1251",
    0xCA: "cp1254",
    0xCB: "cp1253",
};

DBF_PROFILES = {
    0x02: "foxbase",
    0x03: "dbase3",
    0x04: "dbase4",
    0x05: "dbase5",
    0x30: "visual-foxpro",
    0x31: "visual-foxpro-autoincrement",
    0x83: "dbase3-memo",
    0x8B: "dbase4-memo",
    0xF5: "foxpro-memo",
};


def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="tableconvert",
        description="Convert tabular files using SUMTAB as the native SUM table/schema model.",
    );
    parser.add_argument("input", nargs="?", help="Input table/document.");
    parser.add_argument("output", nargs="?", help="Output table/document. Default: INPUT.sumtab.");
    parser.add_argument("--table", help="SQLite table to read/write when the database contains more than one table.");
    parser.add_argument("--profile", default="auto", help="Destination profile/dialect. Default: auto.");
    parser.add_argument("--encoding", default="auto", help="Text/DBF encoding. Default: auto.");
    parser.add_argument(
        "--separator", "--field-separator", "--fs",
        dest="separator",
        default="pipe",
        help=(
            "SUMTAB field separator: named alias, 0xNN, or one ASCII character. "
            "Useful aliases include pipe, tab, comma, semicolon, us. Default: pipe."
        ),
    );
    parser.add_argument(
        "--record-separator", "--rs",
        default="lf",
        help=(
            "SUMTAB record separator: named alias, 0xNN, or one ASCII character. "
            "Useful aliases include lf, cr, nul, rs. Default: lf."
        ),
    );
    parser.add_argument("--no-cache", action="store_true", help="Disable SumDoc conversion-cache checks.");
    parser.add_argument("--list-formats", action="store_true", help="List currently implemented table formats.");
    return (parser);


def detect_format(path: Path) -> str:
    lower = path.name.lower();
    if lower.endswith(".csv.gz"):
        return ("csv.gz");
    if lower.endswith(".tsv.gz"):
        return ("tsv.gz");
    suffix = path.suffix.lower();
    if suffix in FORMAT_SUFFIXES:
        return (FORMAT_SUFFIXES[suffix]);
    if suffix == ".rds":
        return ("rds");
    if suffix == ".fst":
        return ("fst");
    raise ValueError("Unsupported table format for '{}'.".format(path.name));


def default_output_path(input_path: Path) -> Path:
    name = input_path.name;
    for ending in (".csv.gz", ".tsv.gz"):
        if name.lower().endswith(ending):
            name = name[:-len(ending)];
            return (input_path.with_name(name + ".sumtab"));
    if input_path.suffix.lower() == ".sumtab":
        raise ValueError("A SUMTAB input requires an explicit output format.");
    return (input_path.with_suffix(".sumtab"));


def _open_text(path: Path, mode: str, encoding: str):
    if path.name.lower().endswith(".gz"):
        return (gzip.open(path, mode + "t", encoding=encoding, newline=""));
    return (path.open(mode, encoding=encoding, newline=""));


def _text_encoding(path: Path, requested: str) -> str:
    if requested.lower() != "auto":
        return (requested);
    # SUM's portable output is UTF-8. For legacy input, try UTF-8 first and
    # then Latin-1, which is a deterministic one-byte fallback rather than a
    # locale-dependent implicit decode.
    try:
        if path.name.lower().endswith(".gz"):
            with gzip.open(path, "rt", encoding="utf-8") as handle:
                handle.read(65536);
        else:
            path.read_text(encoding="utf-8");
        return ("utf-8");
    except UnicodeDecodeError:
        return ("latin-1");


def _try_date(text: str):
    try:
        return (date.fromisoformat(text));
    except ValueError:
        return (None);


def _try_datetime(text: str):
    if "T" not in text and " " not in text:
        return (None);
    try:
        return (datetime.fromisoformat(text));
    except ValueError:
        return (None);


def _infer_column(name: str, values: list[str]) -> SumColumn:
    present = [value for value in values if value != ""];
    if not present:
        return (SumColumn(name=name, logical_type="VARCHAR", declared_type="VARCHAR", length=1));
    upper = [value.strip().upper() for value in present];
    if all(value in ("TRUE", "FALSE", "YES", "NO", "Y", "N", "T", "F") for value in upper):
        return (SumColumn(name=name, logical_type="LOGICAL", declared_type="LOGICAL"));
    try:
        [int(value) for value in present];
        return (SumColumn(name=name, logical_type="INTEGER", declared_type="INTEGER"));
    except ValueError:
        pass;
    try:
        decimals = [Decimal(value) for value in present];
        max_scale = max(max(-number.as_tuple().exponent, 0) for number in decimals);
        max_precision = max(len(number.as_tuple().digits) for number in decimals);
        return (SumColumn(
            name=name,
            logical_type="NUMERIC",
            declared_type="NUMERIC({},{})".format(max_precision, max_scale),
            precision=max_precision,
            scale=max_scale,
        ));
    except (InvalidOperation, ValueError):
        pass;
    if all(_try_date(value) is not None for value in present):
        return (SumColumn(name=name, logical_type="DATE", declared_type="DATE"));
    if all(_try_datetime(value) is not None for value in present):
        return (SumColumn(name=name, logical_type="DATETIME", declared_type="DATETIME"));
    maximum = max(len(value) for value in present);
    logical = "TEXT" if maximum > 65535 else "VARCHAR";
    declared = logical if logical == "TEXT" else "VARCHAR({})".format(maximum or 1);
    return (SumColumn(name=name, logical_type=logical, declared_type=declared, length=None if logical == "TEXT" else max(maximum, 1)));


def _coerce_text(value: str, column: SumColumn):
    if value == "":
        return (None);
    logical = column.logical_type;
    if logical == "INTEGER":
        return (int(value));
    if logical == "NUMERIC":
        return (Decimal(value));
    if logical == "FLOAT":
        return (float(value));
    if logical == "LOGICAL":
        return (value.strip().upper() in ("TRUE", "YES", "Y", "T", "1"));
    if logical == "DATE":
        return (date.fromisoformat(value));
    if logical == "DATETIME":
        return (datetime.fromisoformat(value));
    return (value);


def read_delimited(path: Path, delimiter: str, encoding: str) -> SumTable:
    used_encoding = _text_encoding(path, encoding);
    with _open_text(path, "r", used_encoding) as handle:
        reader = csv.reader(handle, delimiter=delimiter);
        try:
            header = next(reader);
        except StopIteration as exc:
            raise ValueError("Delimited input is empty.") from exc;
        raw_rows = [row for row in reader];
    if not header:
        raise ValueError("Delimited input has no header.");
    for row_number, row in enumerate(raw_rows, start=2):
        if len(row) != len(header):
            raise ValueError("Row {} has {} columns; expected {}.".format(row_number, len(row), len(header)));
    columns = [
        _infer_column(name, [row[index] for row in raw_rows])
        for index, name in enumerate(header)
    ];
    rows = [tuple(_coerce_text(value, column) for value, column in zip(row, columns)) for row in raw_rows];
    return (SumTable(
        columns=columns,
        rows=rows,
        metadata={"source_format": "CSV" if delimiter == "," else "TSV", "source_encoding": used_encoding},
    ));


def _textify(value) -> str:
    if value is None:
        return ("");
    if isinstance(value, bool):
        return ("TRUE" if value else "FALSE");
    if isinstance(value, Decimal):
        return (format(value, "f"));
    if isinstance(value, (date, datetime)):
        return (value.isoformat());
    if isinstance(value, (bytes, bytearray, memoryview)):
        return (bytes(value).hex().upper());
    if isinstance(value, (dict, list, tuple, set)):
        if isinstance(value, set):
            value = sorted(value, key=repr);
        return (json.dumps(value, ensure_ascii=False, separators=(",", ":")));
    return (str(value));


def write_delimited(table: SumTable, path: Path, delimiter: str) -> None:
    ensure_parent(path);
    with _open_text(path, "w", "utf-8") as handle:
        writer = csv.writer(handle, delimiter=delimiter, lineterminator="\n");
        writer.writerow(table.column_names);
        for row in table.rows:
            writer.writerow([_textify(value) for value in row]);


def _sqlite_quote(name: str) -> str:
    return ('"{}"'.format(name.replace('"', '""')));


def _sqlite_tables(connection) -> list[str]:
    return ([row[0] for row in connection.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' AND name NOT LIKE '__sum_%' ORDER BY name"
    )]);


def _declared_details(declared: str) -> tuple[str, int | None, int | None, int | None]:
    source = (declared or "TEXT").strip();
    logical = canonical_type(source);
    length = None;
    precision = None;
    scale = None;
    if "(" in source and source.endswith(")"):
        body = source.split("(", 1)[1][:-1];
        parts = [part.strip() for part in body.split(",")];
        try:
            if logical in ("CHARACTER", "VARCHAR") and parts:
                length = int(parts[0]);
            elif logical == "NUMERIC" and parts:
                precision = int(parts[0]);
                scale = int(parts[1]) if len(parts) > 1 else 0;
        except ValueError:
            pass;
    if source.upper() in ("CURRENCY", "MONEY"):
        precision = 19;
        scale = 4;
    return (logical, length, precision, scale);


_SUM_SCHEMA_TABLE = "__sum_schema";


def _sum_schema_exists(connection) -> bool:
    row = connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (_SUM_SCHEMA_TABLE,),
    ).fetchone();
    return (row is not None);


def _sum_schema_columns(connection, table_name: str):
    if not _sum_schema_exists(connection):
        return ([]);
    rows = connection.execute(
        "SELECT column_name, logical_type, declared_type, length, precision, scale, nullable, primary_key, unique_value, autoinum, default_sql, references_value "
        "FROM __sum_schema WHERE table_name=? ORDER BY ordinal",
        (table_name,),
    ).fetchall();
    return ([SumColumn(
        name=row[0],
        logical_type=row[1],
        declared_type=row[2],
        length=row[3],
        precision=row[4],
        scale=row[5],
        nullable=bool(row[6]),
        primary_key=bool(row[7]),
        unique=bool(row[8]),
        autoinum=bool(row[9]),
        default=row[10],
        references=row[11],
    ) for row in rows]);


def _write_sum_schema(connection, table_name: str, columns: list[SumColumn]) -> None:
    connection.execute(
        "CREATE TABLE IF NOT EXISTS __sum_schema ("
        "table_name TEXT NOT NULL, ordinal INTEGER NOT NULL, column_name TEXT NOT NULL, "
        "logical_type TEXT NOT NULL, declared_type TEXT, length INTEGER, precision INTEGER, scale INTEGER, "
        "nullable INTEGER NOT NULL, primary_key INTEGER NOT NULL, unique_value INTEGER NOT NULL, autoinum INTEGER NOT NULL, "
        "default_sql TEXT, references_value TEXT, PRIMARY KEY(table_name, ordinal))"
    );
    connection.execute("DELETE FROM __sum_schema WHERE table_name=?", (table_name,));
    for ordinal, column in enumerate(columns):
        connection.execute(
            "INSERT INTO __sum_schema VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                table_name, ordinal, column.name, column.logical_type, column.declared_type,
                column.length, column.precision, column.scale,
                1 if column.nullable else 0, 1 if column.primary_key else 0,
                1 if column.unique else 0, 1 if column.autoinum else 0,
                column.default, column.references,
            ),
        );


def read_sqlite(path: Path, table_name: str | None) -> SumTable:
    from sumcore.sumx_interchange import is_sumx_database, load_table;
    if is_sumx_database(path):
        if not table_name:
            with sqlite3.connect(path) as connection:
                names = [row[0] for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE '__sumx_%' AND name NOT LIKE 'sqlite_%'")];
            if len(names) != 1:
                raise ValueError("Native sumX database requires --table (unless exactly one user table exists).");
            table_name = names[0];
        return load_table(path, table_name);
    connection = sqlite3.connect(path);
    try:
        tables = _sqlite_tables(connection);
        if not tables:
            raise ValueError("SQLite database contains no user tables.");
        if table_name is None:
            if len(tables) != 1:
                raise ValueError("SQLite database contains multiple tables; use --table. Available: {}.".format(", ".join(tables)));
            table_name = tables[0];
        if table_name not in tables:
            raise ValueError("SQLite table '{}' was not found.".format(table_name));
        master = connection.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (table_name,)
        ).fetchone();
        table_sql = master[0] if master and master[0] else "";
        columns = _sum_schema_columns(connection, table_name);
        sum_storage = bool(columns);
        if not columns:
            columns = [];
            for _cid, name, declared, notnull, default, pk in connection.execute(
                "PRAGMA table_info({})".format(_sqlite_quote(table_name))
            ):
                logical, length, precision, scale = _declared_details(declared);
                upper_sql = table_sql.upper();
                autoinum = bool(pk and "AUTOINCREMENT" in upper_sql);
                columns.append(SumColumn(
                    name=name,
                    logical_type=logical,
                    declared_type=declared or logical,
                    length=length,
                    precision=precision,
                    scale=scale,
                    nullable=not bool(notnull),
                    primary_key=bool(pk),
                    autoinum=autoinum,
                    default=default,
                ));
        select_sql = "SELECT {} FROM {}".format(
            ", ".join(_sqlite_quote(column.name) for column in columns),
            _sqlite_quote(table_name),
        );
        raw_rows = connection.execute(select_sql).fetchall();
        rows = [];
        for raw in raw_rows:
            converted = [];
            for value, column in zip(raw, columns):
                if value is None:
                    converted.append(None);
                elif column.logical_type == "LOGICAL":
                    if isinstance(value, str):
                        converted.append(value.strip().upper() not in ("", "0", "FALSE", "F", "NO", "N", "OFF"));
                    else:
                        converted.append(bool(value));
                elif column.logical_type == "NUMERIC":
                    if sum_storage:
                        scale = int(column.scale or 0);
                        converted.append(Decimal(int(value)) / Decimal(10 ** scale));
                    else:
                        converted.append(Decimal(str(value)));
                elif column.logical_type == "DATE":
                    converted.append(date.fromisoformat(str(value)));
                elif column.logical_type == "DATETIME":
                    converted.append(datetime.fromisoformat(str(value)));
                else:
                    converted.append(value);
            rows.append(tuple(converted));
        indexes = [];
        for _seq, name, unique, origin, _partial in connection.execute(
            "PRAGMA index_list({})".format(_sqlite_quote(table_name))
        ):
            if origin in ("pk", "u"):
                continue;
            index_sql_row = connection.execute(
                "SELECT sql FROM sqlite_master WHERE type='index' AND name=?", (name,)
            ).fetchone();
            infos = list(connection.execute("PRAGMA index_info({})".format(_sqlite_quote(name))));
            names = tuple(row[2] for row in infos if row[2] is not None);
            expression = None;
            if any(row[2] is None for row in infos) and index_sql_row and index_sql_row[0]:
                sql = index_sql_row[0];
                left = sql.find("(");
                right = sql.rfind(")");
                if left >= 0 and right > left:
                    expression = sql[left + 1:right];
            indexes.append(SumIndex(name=name, columns=names, unique=bool(unique), expression=expression, origin=origin or "user"));
        return (SumTable(
            columns=columns,
            rows=rows,
            indexes=indexes,
            metadata={"source_format": "SQLite", "table": table_name},
        ));
    finally:
        connection.close();


def _sqlite_type(column: SumColumn) -> str:
    if column.logical_type == "INTEGER":
        return ("INTEGER");
    if column.logical_type == "NUMERIC":
        if column.precision is not None:
            return ("NUMERIC({},{})".format(column.precision, column.scale or 0));
        return ("NUMERIC");
    if column.logical_type == "FLOAT":
        return ("REAL");
    if column.logical_type == "LOGICAL":
        return ("INTEGER");
    if column.logical_type == "BLOB":
        return ("BLOB");
    return ("TEXT");


def _sqlite_value(value, column: SumColumn, sum_storage: bool = True):
    if value is None:
        return (None);
    if column.logical_type == "LOGICAL":
        return (1 if value else 0);
    if column.logical_type == "NUMERIC":
        number = value if isinstance(value, Decimal) else Decimal(str(value));
        if sum_storage:
            scale = int(column.scale or 0);
            quantum = Decimal(1).scaleb(-scale);
            number = number.quantize(quantum);
            return (int(number * (10 ** scale)));
        return (str(number));
    if column.logical_type in ("DATE", "TIME", "DATETIME", "UUID"):
        return (str(value));
    if column.logical_type in ("JSON", "ARRAY", "LIST", "DICT", "SET", "TUPLE", "OBJECT") and not isinstance(value, str):
        if isinstance(value, set):
            value = sorted(value, key=repr);
        return (json.dumps(value, ensure_ascii=False, separators=(",", ":")));
    if isinstance(value, memoryview):
        return (value.tobytes());
    return (value);


def write_sqlite(table: SumTable, path: Path, table_name: str | None) -> None:
    from sumcore.sumx_interchange import is_sumx_database, import_table;
    if is_sumx_database(path):
        import tempfile;
        with tempfile.TemporaryDirectory() as directory:
            intermediate = Path(directory) / 'data.sumtab';
            write_sumtab(table, intermediate);
            import_table(path, table_name or table.metadata.get('table') or path.stem, intermediate);
        return;
    ensure_parent(path);
    name = table_name or table.metadata.get("table") or path.stem;
    connection = sqlite3.connect(path);
    try:
        connection.execute("DROP TABLE IF EXISTS {}".format(_sqlite_quote(name)));
        definitions = [];
        for column in table.columns:
            part = "{} {}".format(_sqlite_quote(column.name), _sqlite_type(column));
            if column.primary_key:
                part += " PRIMARY KEY";
            if column.autoinum:
                if _sqlite_type(column) != "INTEGER":
                    raise ValueError("SQLite AUTOINCREMENT requires INTEGER PRIMARY KEY.");
                if not column.primary_key:
                    part += " PRIMARY KEY";
                part += " AUTOINCREMENT";
            if not column.nullable and not column.primary_key:
                part += " NOT NULL";
            if column.unique and not column.primary_key:
                part += " UNIQUE";
            if column.default is not None:
                part += " DEFAULT {}".format(column.default);
            definitions.append(part);
        connection.execute("CREATE TABLE {} ({})".format(_sqlite_quote(name), ", ".join(definitions)));
        _write_sum_schema(connection, name, table.columns);
        if table.rows:
            placeholders = ",".join("?" for _ in table.columns);
            sql = "INSERT INTO {} ({}) VALUES ({})".format(
                _sqlite_quote(name),
                ",".join(_sqlite_quote(column.name) for column in table.columns),
                placeholders,
            );
            connection.executemany(sql, [
                tuple(_sqlite_value(value, column) for value, column in zip(row, table.columns))
                for row in table.rows
            ]);
        for index in table.indexes:
            if index.origin in ("pk", "u"):
                continue;
            body = index.expression;
            if not body:
                if not index.columns:
                    continue;
                body = ", ".join(_sqlite_quote(column) for column in index.columns);
            connection.execute(
                "CREATE {}INDEX {} ON {} ({})".format(
                    "UNIQUE " if index.unique else "",
                    _sqlite_quote(index.name),
                    _sqlite_quote(name),
                    body,
                )
            );
        connection.commit();
    finally:
        connection.close();


def _dbf_profile(version: int) -> str:
    return (DBF_PROFILES.get(version, "dbf-0x{:02X}".format(version)));


def _dbf_encoding(mark: int, requested: str) -> str:
    if requested.lower() != "auto":
        return (requested);
    return (DBF_CODEPAGES.get(mark, "cp1252"));


def _dbf_companions(path: Path) -> list[Path]:
    companions = [];
    for suffix in (".ndx", ".idx", ".cdx", ".mdx"):
        candidate = path.with_suffix(suffix);
        if candidate.exists():
            companions.append(candidate);
        candidate_upper = path.with_suffix(suffix.upper());
        if candidate_upper.exists() and candidate_upper not in companions:
            companions.append(candidate_upper);
    return (companions);


def read_dbf(path: Path, encoding: str) -> SumTable:
    with path.open("rb") as handle:
        header = handle.read(32);
        if len(header) != 32:
            raise ValueError("DBF header is incomplete.");
        version = header[0];
        record_count = struct.unpack("<I", header[4:8])[0];
        header_length = struct.unpack("<H", header[8:10])[0];
        record_length = struct.unpack("<H", header[10:12])[0];
        codepage_mark = header[29];
        used_encoding = _dbf_encoding(codepage_mark, encoding);
        descriptors = [];
        while handle.tell() < header_length:
            first = handle.read(1);
            if not first:
                raise ValueError("DBF field descriptor block ended unexpectedly.");
            if first == b"\r":
                break;
            rest = handle.read(31);
            if len(rest) != 31:
                raise ValueError("DBF field descriptor is incomplete.");
            desc = first + rest;
            raw_name = desc[:11].split(b"\x00", 1)[0];
            name = raw_name.decode("ascii", errors="replace").strip();
            field_type = chr(desc[11]);
            length = desc[16];
            decimals = desc[17];
            descriptors.append((name, field_type, length, decimals));
        handle.seek(header_length);
        columns = [];
        for name, field_type, length, decimals in descriptors:
            if field_type == "C":
                columns.append(SumColumn(name, "CHARACTER", "CHARACTER({})".format(length), length=length));
            elif field_type in ("N", "Y"):
                precision = max(length - (1 if decimals else 0), 1);
                columns.append(SumColumn(name, "NUMERIC", "NUMERIC({},{})".format(precision, decimals), precision=precision, scale=decimals));
            elif field_type == "F":
                columns.append(SumColumn(name, "FLOAT", "FLOAT"));
            elif field_type == "L":
                columns.append(SumColumn(name, "LOGICAL", "LOGICAL"));
            elif field_type == "D":
                columns.append(SumColumn(name, "DATE", "DATE"));
            elif field_type == "I":
                columns.append(SumColumn(name, "INTEGER", "INTEGER"));
            elif field_type == "M":
                columns.append(SumColumn(name, "MEMO", "MEMO"));
            else:
                columns.append(SumColumn(name, "BLOB", "DBF_{}".format(field_type)));
        rows = [];
        deleted = 0;
        for _ in range(record_count):
            record = handle.read(record_length);
            if len(record) < record_length:
                break;
            if record[:1] == b"*":
                deleted += 1;
                continue;
            offset = 1;
            values = [];
            for (_name, field_type, length, decimals), column in zip(descriptors, columns):
                raw = record[offset:offset + length];
                offset += length;
                if field_type == "I" and length == 4:
                    values.append(struct.unpack("<i", raw)[0]);
                    continue;
                text = raw.decode(used_encoding, errors="replace").strip();
                if text == "" or text == "?":
                    values.append(None);
                elif field_type == "C":
                    values.append(raw.decode(used_encoding, errors="replace").rstrip());
                elif field_type in ("N", "Y"):
                    values.append(Decimal(text));
                elif field_type == "F":
                    values.append(float(text));
                elif field_type == "L":
                    values.append(text.upper() in ("Y", "T"));
                elif field_type == "D" and len(text) == 8:
                    values.append(date(int(text[:4]), int(text[4:6]), int(text[6:8])));
                elif field_type == "M":
                    # Memo contents live in a companion DBT/FPT file. Preserve
                    # the pointer text rather than pretending it is the memo.
                    values.append(text);
                else:
                    values.append(bytes(raw));
            rows.append(tuple(values));
    companions = _dbf_companions(path);
    metadata = {
        "source_format": "DBF",
        "dbf_profile": _dbf_profile(version),
        "dbf_version_byte": "0x{:02X}".format(version),
        "source_encoding": used_encoding,
        "deleted_records_skipped": str(deleted),
    };
    if companions:
        metadata["source_index_companions"] = ",".join(item.name for item in companions);
        metadata["source_index_definitions"] = "not-decoded";
    return (SumTable(columns=columns, rows=rows, metadata=metadata));


def _dbf_field(column: SumColumn, rows: list[tuple[object, ...]], index: int, profile: str):
    logical = column.logical_type;
    if len(column.name.encode("ascii", errors="ignore")) != len(column.name) or len(column.name) > 10:
        raise ValueError("DBF field names must be ASCII and at most 10 characters: '{}'.".format(column.name));
    if logical in ("CHARACTER", "VARCHAR", "TEXT"):
        maximum = max([len(str(row[index]).encode("cp1252", errors="replace")) for row in rows if row[index] is not None] or [1]);
        length = column.length or maximum;
        length = max(length, maximum, 1);
        if length > 254:
            raise ValueError("DBF auto profile cannot store '{}' wider than 254 bytes without a memo file.".format(column.name));
        return ("C", length, 0);
    if logical == "INTEGER":
        width = max([len(str(row[index])) for row in rows if row[index] is not None] or [1]);
        return ("N", max(width, 1), 0);
    if logical == "NUMERIC":
        scale = column.scale or 0;
        precision = column.precision or 18;
        width = precision + (1 if scale else 0) + 1;
        return ("N", min(max(width, 2), 20), scale);
    if logical == "FLOAT":
        return ("F", 20, 8);
    if logical == "LOGICAL":
        return ("L", 1, 0);
    if logical == "DATE":
        return ("D", 8, 0);
    raise ValueError("DBF {} profile cannot represent SUM type {} for field '{}'.".format(profile, logical, column.name));


def _dbf_profile_auto(table: SumTable) -> str:
    # The first writer intentionally targets the broadly compatible dBASE III
    # record model. Future profiles can extend the field map without changing
    # the CLI contract; --profile defaults to auto from day one.
    for index, column in enumerate(table.columns):
        _dbf_field(column, table.rows, index, "dbase3");
    return ("dbase3");


def write_dbf(table: SumTable, path: Path, profile: str, encoding: str) -> None:
    selected = _dbf_profile_auto(table) if profile.lower() == "auto" else profile.lower();
    if selected not in ("dbase3", "dbase-iii", "dbaseiii"):
        raise ValueError("DBF writer currently implements the dbase3 profile; requested '{}'.".format(selected));
    used_encoding = "cp1252" if encoding.lower() == "auto" else encoding;
    fields = [_dbf_field(column, table.rows, index, selected) for index, column in enumerate(table.columns)];
    record_length = 1 + sum(field[1] for field in fields);
    header_length = 32 + 32 * len(fields) + 1;
    now = date.today();
    header = bytearray(32);
    header[0] = 0x03;
    header[1] = max(now.year - 1900, 0) & 0xFF;
    header[2] = now.month;
    header[3] = now.day;
    header[4:8] = struct.pack("<I", len(table.rows));
    header[8:10] = struct.pack("<H", header_length);
    header[10:12] = struct.pack("<H", record_length);
    header[29] = 0x03 if used_encoding.lower().replace("-", "") in ("cp1252", "windows1252") else 0x00;
    ensure_parent(path);
    with path.open("wb") as handle:
        handle.write(header);
        offset = 1;
        for column, (field_type, length, decimals) in zip(table.columns, fields):
            desc = bytearray(32);
            name = column.name.encode("ascii");
            desc[:len(name)] = name;
            desc[11] = ord(field_type);
            desc[12:16] = struct.pack("<I", offset);
            desc[16] = length;
            desc[17] = decimals;
            handle.write(desc);
            offset += length;
        handle.write(b"\r");
        for row in table.rows:
            record = bytearray(b" " * record_length);
            offset = 1;
            for value, column, (field_type, length, decimals) in zip(row, table.columns, fields):
                if value is None:
                    raw = b" " * length;
                elif field_type == "C":
                    encoded = str(value).encode(used_encoding);
                    if len(encoded) > length:
                        raise ValueError("Value for DBF field '{}' exceeds width {}.".format(column.name, length));
                    raw = encoded.ljust(length, b" ");
                elif field_type in ("N", "F"):
                    if field_type == "N" and decimals:
                        text = ("{:0.%df}" % decimals).format(Decimal(value));
                    elif field_type == "F":
                        text = ("{:0.%df}" % decimals).format(float(value));
                    else:
                        text = str(int(value));
                    raw = text.encode("ascii").rjust(length, b" ");
                    if len(raw) > length:
                        raise ValueError("Numeric value for DBF field '{}' exceeds width {}.".format(column.name, length));
                elif field_type == "L":
                    raw = (b"T" if bool(value) else b"F");
                elif field_type == "D":
                    if isinstance(value, date):
                        text = value.strftime("%Y%m%d");
                    else:
                        text = date.fromisoformat(str(value)).strftime("%Y%m%d");
                    raw = text.encode("ascii");
                else:
                    raise ValueError("Unsupported DBF field type {}.".format(field_type));
                record[offset:offset + length] = raw[:length];
                offset += length;
            handle.write(record);
        handle.write(b"\x1A");


def _from_pandas(frame, source_format: str = "Pandas") -> SumTable:
    try:
        import pandas as pd;
    except ImportError as exc:
        raise ImportError("Converting a pandas DataFrame needs pandas.") from exc;

    columns = [];
    for name in frame.columns:
        series = frame[name];
        dtype = str(series.dtype).lower();
        if "category" in dtype:
            maximum = max([len(str(value)) for value in series.dropna().tolist()] or [1]);
            columns.append(SumColumn(str(name), "VARCHAR", "VARCHAR({})".format(maximum), length=maximum));
        elif "int" in dtype:
            columns.append(SumColumn(str(name), "INTEGER", str(series.dtype)));
        elif "float" in dtype:
            columns.append(SumColumn(str(name), "FLOAT", str(series.dtype)));
        elif "bool" in dtype:
            columns.append(SumColumn(str(name), "LOGICAL", str(series.dtype)));
        elif "datetime" in dtype:
            columns.append(SumColumn(str(name), "DATETIME", str(series.dtype)));
        elif "timedelta" in dtype:
            columns.append(SumColumn(str(name), "FLOAT", str(series.dtype)));
        else:
            maximum = max([len(str(value)) for value in series.dropna().tolist()] or [1]);
            columns.append(SumColumn(str(name), "VARCHAR", "VARCHAR({})".format(maximum), length=maximum));

    rows = [];
    for record in frame.itertuples(index=False, name=None):
        converted = [];
        for value in record:
            if value is None:
                converted.append(None);
                continue;
            try:
                missing = pd.isna(value);
                if isinstance(missing, bool) and missing:
                    converted.append(None);
                    continue;
            except Exception:  # pylint:disable=broad-exception-caught
                pass;
            if hasattr(value, "to_pydatetime"):
                value = value.to_pydatetime();
            elif hasattr(value, "item"):
                try:
                    value = value.item();
                except Exception:  # pylint:disable=broad-exception-caught
                    pass;
            converted.append(value);
        rows.append(tuple(converted));
    return (SumTable(columns=columns, rows=rows, metadata={"source_format": source_format}));


def read_fst(path: Path) -> SumTable:
    try:
        from fstio import metadata_fst, read_fst as fstio_read_fst;
    except ImportError as exc:
        raise ImportError(
            "Native FST conversion needs the optional fstio backend. "
            "Install it with 'pip install fstio' or 'pip install sumdoc[fst]'."
        ) from exc;

    frame = fstio_read_fst(str(path));
    table = _from_pandas(frame, source_format="FST");

    try:
        metadata = metadata_fst(str(path));
        table.metadata["fst_rows"] = str(metadata.num_rows);
        keys = tuple(getattr(metadata, "keys", ()) or ());
        if keys:
            table.metadata["fst_keys"] = ",".join(str(key) for key in keys);
            table.indexes.append(SumIndex(
                name="fst_key",
                columns=tuple(str(key) for key in keys),
                unique=False,
                origin="fst-key",
            ));
    except Exception:  # pylint:disable=broad-exception-caught
        # Reading the data succeeded; metadata enrichment must not make the
        # conversion fail if an older/newer fstio metadata API is encountered.
        pass;

    table.metadata["source_backend"] = "fstio";
    return (table);


def read_parquet(path: Path) -> SumTable:
    try:
        import pandas as pd;
    except ImportError as exc:
        raise ImportError("Parquet conversion needs pandas plus a Parquet engine such as pyarrow.") from exc;
    try:
        frame = pd.read_parquet(path);
    except ImportError as exc:
        raise ImportError("Parquet conversion needs a Parquet engine such as pyarrow.") from exc;
    return (_from_pandas(frame, source_format="Parquet"));


def write_parquet(table: SumTable, path: Path) -> None:
    try:
        import pandas as pd;
    except ImportError as exc:
        raise ImportError("Parquet conversion needs pandas plus a Parquet engine such as pyarrow.") from exc;
    frame = pd.DataFrame(table.rows, columns=table.column_names);
    try:
        frame.to_parquet(path, index=False);
    except ImportError as exc:
        raise ImportError("Parquet conversion needs a Parquet engine such as pyarrow.") from exc;


def read_table(path: Path, fmt: str, args) -> SumTable:
    if fmt == "sumtab":
        return (read_sumtab(path));
    if fmt in ("csv", "csv.gz"):
        return (read_delimited(path, ",", args.encoding));
    if fmt in ("tsv", "tsv.gz"):
        return (read_delimited(path, "\t", args.encoding));
    if fmt == "sumx":
        from sumcore.sumx_interchange import load_table;
        if not args.table:
            with sqlite3.connect(path) as connection:
                tables = _sqlite_tables(connection);
            if len(tables) != 1:
                raise ValueError("sumX file requires --table unless it contains exactly one user table.");
            return load_table(path, tables[0]);
        return load_table(path, args.table);
    if fmt == "sqlite":
        return (read_sqlite(path, args.table));
    if fmt == "dbf":
        return (read_dbf(path, args.encoding));
    if fmt == "parquet":
        return (read_parquet(path));
    if fmt == "rds":
        raise ImportError("Native RDS conversion is reserved for the SUM table backend; no dependency-free RDS reader is installed yet.");
    if fmt == "fst":
        return (read_fst(path));
    raise ValueError("Unsupported input format: {}.".format(fmt));


def write_table(table: SumTable, path: Path, fmt: str, args) -> None:
    if fmt == "sumtab":
        write_sumtab(
            table,
            path,
            separator=normalize_separator(args.separator),
            record_separator=normalize_record_separator(args.record_separator),
        );
        return;
    if fmt in ("csv", "csv.gz"):
        write_delimited(table, path, ",");
        return;
    if fmt in ("tsv", "tsv.gz"):
        write_delimited(table, path, "\t");
        return;
    if fmt == "sumx":
        from sumcore.sumx_interchange import import_table;
        import tempfile;
        with tempfile.TemporaryDirectory() as directory:
            intermediate = Path(directory) / 'data.sumtab';
            write_sumtab(table, intermediate);
            import_table(path, args.table or table.metadata.get('table') or path.stem, intermediate);
        return;
    if fmt == "sqlite":
        write_sqlite(table, path, args.table);
        return;
    if fmt == "dbf":
        write_dbf(table, path, args.profile, args.encoding);
        return;
    if fmt == "parquet":
        write_parquet(table, path);
        return;
    raise ValueError("Unsupported output format: {}.".format(fmt));


def _source_paths(path: Path, fmt: str) -> list[Path]:
    paths = [path];
    if fmt == "dbf":
        # Companion files influence the meaning of a DBF dataset. Index file
        # definitions are not decoded yet, but changing one invalidates cache
        # metadata so a future decoder will never reuse a stale conversion.
        for suffix in (".dbt", ".fpt", ".ndx", ".idx", ".cdx", ".mdx"):
            for candidate in (path.with_suffix(suffix), path.with_suffix(suffix.upper())):
                if candidate.exists() and candidate not in paths:
                    paths.append(candidate);
    return (paths);


def _stat_signature(paths: Iterable[Path]):
    return ([{
        "path": str(path.resolve()),
        "size": path.stat().st_size,
        "mtime_ns": path.stat().st_mtime_ns,
    } for path in paths]);


def _cache_root() -> Path:
    base = os.environ.get("XDG_CACHE_HOME");
    if base:
        return (Path(base).expanduser().resolve() / "sumdoc" / "tableconvert");
    return (Path.home() / ".cache" / "sumdoc" / "tableconvert");


def _cache_path(source: Path, target: Path, options: dict) -> Path:
    payload = json.dumps({
        "source": str(source.resolve()),
        "target": str(target.resolve()),
        "options": options,
    }, sort_keys=True, separators=(",", ":")).encode("utf-8");
    key = hashlib.sha256(payload).hexdigest();
    return (_cache_root() / (key + ".json"));


def _load_cache(path: Path):
    try:
        return (json.loads(path.read_text(encoding="utf-8")));
    except (OSError, json.JSONDecodeError):
        return (None);


def _target_signature(path: Path):
    if not path.exists():
        return (None);
    stat = path.stat();
    return ({"size": stat.st_size, "mtime_ns": stat.st_mtime_ns});


def _cache_status(source_paths: list[Path], target: Path, cache_file: Path):
    record = _load_cache(cache_file);
    if record is None or not target.exists():
        return ("missing", record);
    current_source = _stat_signature(source_paths);
    current_target = _target_signature(target);
    if record.get("target") != current_target:
        return ("target-modified", record);
    if record.get("source") == current_source:
        return ("current", record);
    return ("source-changed", record);


def _write_cache(cache_file: Path, source_paths: list[Path], target: Path, info: dict) -> None:
    cache_file.parent.mkdir(parents=True, exist_ok=True);
    record = {
        "source": _stat_signature(source_paths),
        "target": _target_signature(target),
        "conversion": info,
    };
    cache_file.write_text(json.dumps(record, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8");


def main(arguments: list[str] | None, options: GlobalOptions) -> int:
    args = create_parser().parse_args(arguments);
    reporter = Reporter(options);
    if args.list_formats:
        print("sumtab\tnative SUM table/schema format");
        print("csv/csv.gz\tportable delimited text");
        print("tsv/tsv.gz\tportable tab-delimited text");
        print("sqlite/sqlite3/db\tSQLite database with schema/index definitions");
        print("sumx\tnative sumX SQLite database with sumX metadata");
        print("dbf\tdBASE-compatible table; destination profile defaults to auto");
        print("parquet\toptional pandas/Parquet backend");
        print("rds\treserved native backend (not implemented in this revision)");
        print("fst\tnative read-only backend via optional fstio");
        return (0);
    if args.input is None:
        raise ValueError("tableconvert requires an input file unless --list-formats is used.");
    source = require_input_file(args.input);
    if args.output and options.output is not None:
        raise ValueError("Specify the output either positionally or with --output, not both.");
    if options.output_dir is not None:
        raise ValueError("tableconvert uses one exact output file; --output-dir is not applicable.");
    output_text = options.output or args.output;
    target = Path(output_text).expanduser().resolve() if output_text else default_output_path(source);
    if target == source:
        raise ValueError("Input and output paths must be different.");
    source_format = detect_format(source);
    target_format = detect_format(target);
    ensure_parent(target);
    cache_options = {
        "source_format": source_format,
        "target_format": target_format,
        "table": args.table,
        "profile": args.profile,
        "encoding": args.encoding,
        "separator": normalize_separator(args.separator) if target_format == "sumtab" else None,
        "record_separator": (
            normalize_record_separator(args.record_separator)
            if target_format == "sumtab" else None
        ),
    };
    source_paths = _source_paths(source, source_format);
    cache_file = _cache_path(source, target, cache_options);
    if not args.no_cache and not options.force:
        status, _record = _cache_status(source_paths, target, cache_file);
        if status == "current":
            reporter.success("Using current cached conversion '{}'.".format(target));
            return (0);
        if status == "target-modified":
            raise FileExistsError("Output was modified after SumDoc created it: '{}'. Use --force to replace it.".format(target));
        if status == "missing" and target.exists():
            raise FileExistsError("Output already exists and is not owned by this conversion cache: '{}'. Use --force to replace it.".format(target));
        # source-changed is safe: the target still matches the previous cached
        # product, so it can be refreshed automatically.
    elif target.exists() and options.force:
        reporter.verbose("Force enabled; replacing '{}'.".format(target));
    table = read_table(source, source_format, args);
    table.metadata.setdefault("source_path", str(source));
    table.metadata.setdefault("source_format", source_format.upper());
    table.metadata["sumtab_native_format"] = "sumtab/1";
    write_table(table, target, target_format, args);
    if not args.no_cache:
        _write_cache(cache_file, source_paths, target, cache_options);
    reporter.success(
        "Converted '{}' ({}) to '{}' ({}) with {} rows and {} columns.".format(
            source, source_format, target, target_format, len(table.rows), len(table.columns)
        )
    );
    if source_format == "dbf" and table.metadata.get("source_index_definitions") == "not-decoded":
        reporter.warning(
            "xBase index companions were detected. This revision preserves their presence in SUMTAB metadata but does not decode NDX/IDX/CDX/MDX expressions yet."
        );
    return (0);


__all__ = [
    "detect_format",
    "read_table",
    "write_table",
    "read_dbf",
    "write_dbf",
    "read_sqlite",
    "write_sqlite",
    "main",
];
