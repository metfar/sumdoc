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

"""Dependency-free codec for SUMTAB, the native SUM tabular interchange format.

SUMTAB is intentionally line-oriented and simple enough to implement in
sumBASIC.  The first line identifies the format.  META, FIELD and INDEX records
follow, then DATA marks the beginning of rows.  Fields are tab-separated and
use a tiny escape set: \\, \\t, \\n and \\r.  The unescaped token \\N means NULL.
""";

from dataclasses import dataclass, field;
from datetime import date, datetime, time;
from decimal import Decimal;
from pathlib import Path;
import json;
import math;
import uuid;

from sumcore.schema import SUMTAB_FORMAT, canonical_type;


MAGIC = "SUMTAB";
VERSION = "1";
NULL_TOKEN = r"\N";


@dataclass(frozen=True)
class SumColumn:
    name: str;
    logical_type: str = "TEXT";
    declared_type: str | None = None;
    length: int | None = None;
    precision: int | None = None;
    scale: int | None = None;
    nullable: bool = True;
    primary_key: bool = False;
    unique: bool = False;
    autoinum: bool = False;
    default: str | None = None;
    references: str | None = None;

    def __post_init__(self):
        object.__setattr__(self, "logical_type", canonical_type(self.logical_type));
        if self.declared_type is None:
            object.__setattr__(self, "declared_type", self.logical_type);


@dataclass(frozen=True)
class SumIndex:
    """Portable index definition, not a copy of a native index file.""";

    name: str;
    columns: tuple[str, ...] = ();
    unique: bool = False;
    expression: str | None = None;
    origin: str = "user";


@dataclass
class SumTable:
    columns: list[SumColumn];
    rows: list[tuple[object, ...]] = field(default_factory=list);
    indexes: list[SumIndex] = field(default_factory=list);
    metadata: dict[str, str] = field(default_factory=dict);

    def __post_init__(self):
        width = len(self.columns);
        for row in self.rows:
            if len(row) != width:
                raise ValueError(
                    "SUMTAB row has {} values but schema has {} columns.".format(
                        len(row), width
                    )
                );

    @property
    def column_names(self) -> tuple[str, ...]:
        return (tuple(column.name for column in self.columns));


def _escape(text: object) -> str:
    source = str(text);
    return (
        source.replace("\\", "\\\\")
        .replace("\t", "\\t")
        .replace("\n", "\\n")
        .replace("\r", "\\r")
    );


def _unescape(text: str) -> str:
    out = [];
    index = 0;
    while index < len(text):
        char = text[index];
        if char != "\\" or index + 1 >= len(text):
            out.append(char);
            index += 1;
            continue;
        code = text[index + 1];
        if code == "\\":
            out.append("\\");
        elif code == "t":
            out.append("\t");
        elif code == "n":
            out.append("\n");
        elif code == "r":
            out.append("\r");
        else:
            # Forward-compatible rule: an unknown escape keeps the slash.
            out.append("\\");
            out.append(code);
        index += 2;
    return ("".join(out));


def _optional_int(value: str) -> int | None:
    return (None if value == "" else int(value));


def _bool_field(value: str) -> bool:
    return (value == "1");


def _serialize_value(value: object, column: SumColumn) -> str:
    if value is None:
        return (NULL_TOKEN);
    logical = column.logical_type;
    if logical == "LOGICAL":
        return ("TRUE" if bool(value) else "FALSE");
    if logical == "BLOB":
        if isinstance(value, memoryview):
            value = value.tobytes();
        if isinstance(value, bytearray):
            value = bytes(value);
        if not isinstance(value, bytes):
            raise TypeError("BLOB column '{}' expects bytes.".format(column.name));
        return (value.hex().upper());
    if logical == "DATE" and isinstance(value, date) and not isinstance(value, datetime):
        return (value.isoformat());
    if logical == "TIME" and isinstance(value, time):
        return (value.isoformat());
    if logical == "DATETIME" and isinstance(value, datetime):
        return (value.isoformat());
    if logical == "NUMERIC":
        number = value if isinstance(value, Decimal) else Decimal(str(value));
        if column.scale is not None:
            return (format(number, ".{}f".format(int(column.scale))));
        return (format(number, "f"));
    if logical == "FLOAT" and isinstance(value, float):
        if math.isnan(value):
            return ("NaN");
        if math.isinf(value):
            return ("Infinity" if value > 0 else "-Infinity");
        return (repr(value));
    if logical == "UUID" and isinstance(value, uuid.UUID):
        return (str(value));
    if logical in ("JSON", "ARRAY", "LIST", "DICT", "SET", "TUPLE", "OBJECT"):
        if not isinstance(value, str):
            if isinstance(value, set):
                value = sorted(value, key=repr);
            value = json.dumps(value, ensure_ascii=False, separators=(",", ":"));
    return (_escape(value));


def _parse_value(token: str, column: SumColumn) -> object:
    if token == NULL_TOKEN:
        return (None);
    logical = column.logical_type;
    text = _unescape(token);
    if logical == "INTEGER":
        return (int(text));
    if logical == "NUMERIC":
        return (Decimal(text));
    if logical == "FLOAT":
        return (float(text));
    if logical == "LOGICAL":
        upper = text.strip().upper();
        if upper in ("TRUE", "T", "YES", "Y", "1"):
            return (True);
        if upper in ("FALSE", "F", "NO", "N", "0"):
            return (False);
        raise ValueError("Invalid LOGICAL value {!r}.".format(text));
    if logical == "DATE":
        return (date.fromisoformat(text));
    if logical == "TIME":
        return (time.fromisoformat(text));
    if logical == "DATETIME":
        return (datetime.fromisoformat(text));
    if logical == "BLOB":
        return (bytes.fromhex(text));
    if logical == "UUID":
        return (uuid.UUID(text));
    if logical in ("JSON", "ARRAY", "LIST", "DICT", "SET", "TUPLE", "OBJECT"):
        try:
            value = json.loads(text);
            if logical == "SET" and isinstance(value, list):
                return (set(value));
            if logical == "TUPLE" and isinstance(value, list):
                return (tuple(value));
            return (value);
        except json.JSONDecodeError:
            return (text);
    return (text);


def dumps(table: SumTable) -> str:
    lines = [f"{MAGIC}\t{VERSION}"];
    metadata = {
        "schema": SUMTAB_FORMAT,
        "encoding": "UTF-8",
        "separator": "TAB",
        "null": NULL_TOKEN,
    };
    metadata.update({str(key): str(value) for key, value in table.metadata.items()});
    for key, value in metadata.items():
        lines.append("META\t{}\t{}".format(_escape(key), _escape(value)));
    for column in table.columns:
        lines.append("\t".join((
            "FIELD",
            _escape(column.name),
            _escape(column.logical_type),
            _escape(column.declared_type or column.logical_type),
            "" if column.length is None else str(column.length),
            "" if column.precision is None else str(column.precision),
            "" if column.scale is None else str(column.scale),
            "1" if column.nullable else "0",
            "1" if column.primary_key else "0",
            "1" if column.unique else "0",
            "1" if column.autoinum else "0",
            "" if column.default is None else _escape(column.default),
            "" if column.references is None else _escape(column.references),
        )));
    for index in table.indexes:
        fields = [
            "INDEX",
            _escape(index.name),
            "1" if index.unique else "0",
            _escape(index.origin),
            "" if index.expression is None else _escape(index.expression),
        ];
        fields.extend(_escape(column) for column in index.columns);
        lines.append("\t".join(fields));
    lines.append("DATA");
    for row in table.rows:
        lines.append("\t".join(
            _serialize_value(value, column)
            for value, column in zip(row, table.columns)
        ));
    return ("\n".join(lines) + "\n");


def loads(text: str) -> SumTable:
    raw_lines = text.splitlines();
    if not raw_lines:
        raise ValueError("Empty SUMTAB document.");
    header = raw_lines[0].split("\t");
    if len(header) != 2 or header[0] != MAGIC:
        raise ValueError("Not a SUMTAB document.");
    if header[1] != VERSION:
        raise ValueError("Unsupported SUMTAB version: {}.".format(header[1]));
    columns = [];
    indexes = [];
    metadata = {};
    rows = [];
    in_data = False;
    for line_number, line in enumerate(raw_lines[1:], start=2):
        if not in_data:
            if line == "DATA":
                in_data = True;
                continue;
            if not line:
                continue;
            parts = line.split("\t");
            kind = parts[0];
            if kind == "META":
                if len(parts) != 3:
                    raise ValueError("Invalid META record at line {}.".format(line_number));
                metadata[_unescape(parts[1])] = _unescape(parts[2]);
                continue;
            if kind == "FIELD":
                if len(parts) != 13:
                    raise ValueError("Invalid FIELD record at line {}.".format(line_number));
                columns.append(SumColumn(
                    name=_unescape(parts[1]),
                    logical_type=_unescape(parts[2]),
                    declared_type=_unescape(parts[3]) or None,
                    length=_optional_int(parts[4]),
                    precision=_optional_int(parts[5]),
                    scale=_optional_int(parts[6]),
                    nullable=_bool_field(parts[7]),
                    primary_key=_bool_field(parts[8]),
                    unique=_bool_field(parts[9]),
                    autoinum=_bool_field(parts[10]),
                    default=None if parts[11] == "" else _unescape(parts[11]),
                    references=None if parts[12] == "" else _unescape(parts[12]),
                ));
                continue;
            if kind == "INDEX":
                if len(parts) < 5:
                    raise ValueError("Invalid INDEX record at line {}.".format(line_number));
                indexes.append(SumIndex(
                    name=_unescape(parts[1]),
                    unique=_bool_field(parts[2]),
                    origin=_unescape(parts[3]) or "user",
                    expression=None if parts[4] == "" else _unescape(parts[4]),
                    columns=tuple(_unescape(value) for value in parts[5:]),
                ));
                continue;
            raise ValueError("Unknown SUMTAB record {!r} at line {}.".format(kind, line_number));
        if not columns and line:
            raise ValueError("SUMTAB DATA section has no FIELD definitions.");
        parts = line.split("\t");
        if len(parts) != len(columns):
            raise ValueError(
                "SUMTAB data row at line {} has {} fields; expected {}.".format(
                    line_number, len(parts), len(columns)
                )
            );
        rows.append(tuple(_parse_value(token, column) for token, column in zip(parts, columns)));
    if not in_data:
        raise ValueError("SUMTAB document has no DATA section.");
    return (SumTable(columns=columns, rows=rows, indexes=indexes, metadata=metadata));


def write_sumtab(table: SumTable, path: str | Path) -> Path:
    target = Path(path).expanduser().resolve();
    target.parent.mkdir(parents=True, exist_ok=True);
    target.write_text(dumps(table), encoding="utf-8", newline="\n");
    return (target);


def read_sumtab(path: str | Path) -> SumTable:
    source = Path(path).expanduser().resolve();
    return (loads(source.read_text(encoding="utf-8")));


__all__ = [
    "MAGIC",
    "VERSION",
    "NULL_TOKEN",
    "SumColumn",
    "SumIndex",
    "SumTable",
    "dumps",
    "loads",
    "read_sumtab",
    "write_sumtab",
];
