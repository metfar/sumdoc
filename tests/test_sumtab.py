#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#pylint:disable=W0301

from datetime import date, datetime;
from pathlib import Path;
from decimal import Decimal;
import sqlite3;

from sumdoc.common import GlobalOptions;
from sumdoc.sumtab import SumColumn, SumIndex, SumTable, dumps, loads, read_sumtab, write_sumtab;
from sumdoc.tools import tableconvert, tablequery;


def sample_table():
    return SumTable(
        columns=[
            SumColumn("id", "INTEGER", "AUTONUM", nullable=False, primary_key=True, autoinum=True),
            SumColumn("name", "VARCHAR", "VARCHAR(40)", length=40),
            SumColumn("amount", "NUMERIC", "CURRENCY", precision=19, scale=4),
            SumColumn("active", "LOGICAL", "BOOLEAN"),
            SumColumn("created", "DATE", "DATE"),
            SumColumn("note", "TEXT", "TEXT"),
        ],
        rows=[
            (1, "Ana\tPérez", Decimal("12.3400"), True, date(2026, 10, 10), "line 1 | line 2\nline 3"),
            (2, r"literal \N", None, False, None, ""),
        ],
        indexes=[SumIndex("idx_name", ("name",), unique=False)],
        metadata={"table": "people"},
    );


def test_sumtab_round_trip_preserves_schema_values_and_indexes():
    table = sample_table();
    restored = loads(dumps(table));
    assert restored.column_names == table.column_names;
    assert restored.columns[2].declared_type == "CURRENCY";
    assert restored.columns[2].precision == 19;
    assert restored.columns[2].scale == 4;
    assert restored.rows == table.rows;
    assert restored.indexes == table.indexes;
    assert restored.metadata["schema"] == "sumtab/1";



def test_sumtab_defaults_to_pipe_and_escapes_pipe_values():
    table = sample_table();
    encoded = dumps(table);
    assert encoded.startswith("SUMTAB1 FS=7C RS=0A\n");
    assert "META|separator|PIPE" in encoded;
    assert "META|record_separator|LF" in encoded;
    assert "line 1 \\x7C line 2\\nline 3" in encoded;
    restored = loads(encoded);
    assert restored.rows == table.rows;
    assert restored.metadata["separator"] == "PIPE";
    assert restored.metadata["record_separator"] == "LF";


def test_sumtab_supports_tab_and_custom_single_character_separators():
    table = sample_table();
    tab_text = dumps(table, separator="tab");
    assert tab_text.startswith("SUMTAB1 FS=09 RS=0A\n");
    assert loads(tab_text).rows == table.rows;

    semi_text = dumps(table, separator=";");
    assert semi_text.startswith("SUMTAB1 FS=3B RS=0A\n");
    assert "META;separator;SEMICOLON" in semi_text;
    assert loads(semi_text).rows == table.rows;


def test_sumtab_supports_raw_us_rs_and_nul_record_separators():
    table = sample_table();
    raw_text = dumps(table, separator="us", record_separator="rs");
    assert raw_text.startswith("SUMTAB1 FS=1F RS=1E\n");
    assert "\x1f" in raw_text;
    assert "\x1e" in raw_text;
    assert loads(raw_text).rows == table.rows;

    nul_text = dumps(table, separator="pipe", record_separator="nul");
    assert nul_text.startswith("SUMTAB1 FS=7C RS=00\n");
    assert "\x00" in nul_text;
    assert loads(nul_text).rows == table.rows;


def test_sumtab_reader_accepts_legacy_pipe_header():
    current = dumps(sample_table());
    payload = current.split("\n", 1)[1];
    legacy = "SUMTAB|1\n" + payload;
    restored = loads(legacy);
    assert restored.rows == sample_table().rows;
    assert restored.metadata["record_separator"] == "LF";


def test_tableconvert_separator_parameter_changes_sumtab_output(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache"));
    source = tmp_path / "sample.csv";
    source.write_text("id,name\n1,Ana\n", encoding="utf-8");
    target = tmp_path / "sample.sumtab";
    options = GlobalOptions(quiet=True);
    assert tableconvert.main([str(source), str(target), "--separator", "tab"], options) == 0;
    assert target.read_text(encoding="utf-8").startswith("SUMTAB1 FS=09 RS=0A\n");
    assert read_sumtab(target).rows == [(1, "Ana")];


def test_tableconvert_record_separator_parameter_changes_sumtab_output(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache"));
    source = tmp_path / "sample.csv";
    source.write_text("id,name\n1,Ana\n", encoding="utf-8");
    target = tmp_path / "sample.sumtab";
    options = GlobalOptions(quiet=True);
    assert tableconvert.main([
        str(source), str(target), "--fs", "us", "--rs", "rs"
    ], options) == 0;
    encoded = target.read_bytes().decode("utf-8");
    assert encoded.startswith("SUMTAB1 FS=1F RS=1E\n");
    assert read_sumtab(target).rows == [(1, "Ana")];

def test_sqlite_round_trip_regenerates_index_definition(tmp_path):
    table = sample_table();
    target = tmp_path / "people.sqlite";
    tableconvert.write_sqlite(table, target, "people");
    restored = tableconvert.read_sqlite(target, "people");
    assert [index.name for index in restored.indexes] == ["idx_name"];
    assert restored.indexes[0].columns == ("name",);
    assert restored.rows[0][2] == Decimal("12.3400");
    assert restored.rows[0][3] is True;
    assert restored.rows[1][3] is False;
    with sqlite3.connect(target) as connection:
        names = [row[1] for row in connection.execute("PRAGMA index_list(people)")];
    assert "idx_name" in names;


def test_dbf_auto_profile_round_trip_core_types(tmp_path):
    table = SumTable(
        columns=[
            SumColumn("ID", "INTEGER"),
            SumColumn("NAME", "CHARACTER", length=20),
            SumColumn("PRICE", "NUMERIC", precision=8, scale=2),
            SumColumn("ACTIVE", "LOGICAL"),
            SumColumn("CREATED", "DATE"),
        ],
        rows=[
            (1, "One", Decimal("12.50"), True, date(2026, 10, 10)),
            (2, "Two", Decimal("3.25"), False, date(2026, 10, 11)),
        ],
    );
    target = tmp_path / "sample.dbf";
    tableconvert.write_dbf(table, target, "auto", "auto");
    restored = tableconvert.read_dbf(target, "auto");
    assert restored.metadata["dbf_profile"] == "dbase3";
    assert restored.column_names == table.column_names;
    assert restored.rows[0][0] == Decimal("1");
    assert restored.rows[0][1] == "One";
    assert restored.rows[0][2] == Decimal("12.50");
    assert restored.rows[0][3] is True;
    assert restored.rows[0][4] == date(2026, 10, 10);


def test_tableconvert_defaults_to_sumtab_and_reuses_cache(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache"));
    source = tmp_path / "sample.csv";
    source.write_text("id,name\n1,Ana\n2,Seba\n", encoding="utf-8");
    options = GlobalOptions(quiet=True);
    assert tableconvert.main([str(source)], options) == 0;
    target = tmp_path / "sample.sumtab";
    assert target.exists();
    first_mtime = target.stat().st_mtime_ns;
    assert tableconvert.main([str(source)], options) == 0;
    assert target.stat().st_mtime_ns == first_mtime;
    restored = read_sumtab(target);
    assert restored.column_names == ("id", "name");
    assert restored.rows[1][1] == "Seba";


def test_tableconvert_list_formats_needs_no_input(capsys):
    assert tableconvert.main(["--list-formats"], GlobalOptions(quiet=True)) == 0;
    assert "sumtab" in capsys.readouterr().out;


def test_sqlite_expression_index_definition_is_portable(tmp_path):
    source = tmp_path / "source.sqlite";
    with sqlite3.connect(source) as connection:
        connection.execute("CREATE TABLE people (name TEXT)");
        connection.execute("CREATE INDEX idx_lower_name ON people (lower(name))");
        connection.execute("INSERT INTO people VALUES ('Ana')");
        connection.commit();
    table = tableconvert.read_sqlite(source, "people");
    assert len(table.indexes) == 1;
    assert table.indexes[0].name == "idx_lower_name";
    assert table.indexes[0].expression == "lower(name)";
    target = tmp_path / "target.sqlite";
    tableconvert.write_sqlite(table, target, "people");
    with sqlite3.connect(target) as connection:
        sql = connection.execute(
            "SELECT sql FROM sqlite_master WHERE type='index' AND name='idx_lower_name'"
        ).fetchone()[0];
    assert "lower(name)" in sql;


def test_fst_backend_uses_fstio_without_r(tmp_path, monkeypatch):
    import sys;
    import types;
    import pandas as pd;

    source = tmp_path / "sample.fst";
    source.write_bytes(b"placeholder");

    fake_meta = types.SimpleNamespace(
        num_rows=2,
        column_names=("id", "name", "active"),
        keys=("id",),
    );

    fake_module = types.SimpleNamespace(
        read_fst=lambda path: pd.DataFrame({
            "id": pd.Series([1, 2], dtype="Int32"),
            "name": ["Ana", "Seba"],
            "active": pd.Series([True, None], dtype="boolean"),
        }),
        metadata_fst=lambda path: fake_meta,
    );
    monkeypatch.setitem(sys.modules, "fstio", fake_module);

    table = tableconvert.read_fst(source);
    assert table.metadata["source_format"] == "FST";
    assert table.metadata["source_backend"] == "fstio";
    assert table.metadata["fst_rows"] == "2";
    assert table.indexes[0].columns == ("id",);
    assert table.rows == [(1, "Ana", True), (2, "Seba", None)];


def test_fst_backend_missing_dependency_has_install_hint(tmp_path, monkeypatch):
    import builtins;

    source = tmp_path / "sample.fst";
    source.write_bytes(b"placeholder");
    real_import = builtins.__import__;

    def fake_import(name, *args, **kwargs):
        if name == "fstio":
            raise ImportError("missing fstio");
        return real_import(name, *args, **kwargs);

    monkeypatch.setattr(builtins, "__import__", fake_import);
    try:
        tableconvert.read_fst(source);
    except ImportError as exc:
        assert "pip install sumdoc[fst]" in str(exc);
    else:
        raise AssertionError("Expected ImportError when fstio is unavailable.");


def test_sumdoc_declares_schema_capable_sumcore():
    pyproject = Path(__file__).resolve().parents[1] / "pyproject.toml";
    text = pyproject.read_text(encoding="utf-8");
    assert '"sumcore>=0.1.0a22"' in text;
