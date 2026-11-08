#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#pylint:disable=W0301
#
#  Copyright 2018-2026 William Martinez Bas <metfar@gmail.com>
#  GPL-2.0-or-later
#
"""Bidirectional SUMTAB/native sumX interchange regression tests.""";

from decimal import Decimal;
from pathlib import Path;
import sqlite3;

import pytest;
from sumcore.sumtab import SumColumn, SumIndex, SumTable, read_sumtab, write_sumtab;
from sumcore.sumx_interchange import import_table, export_table, is_sumx_database;
from sumdoc.tools.tableconvert import read_sqlite, read_table, write_table, create_parser;


def _sample():
    return SumTable(columns=[
        SumColumn('id', 'INTEGER', primary_key=True, nullable=False),
        SumColumn('descripcion', 'VARCHAR', length=40),
        SumColumn('valor', 'NUMERIC', precision=12, scale=3),
        SumColumn('activo', 'LOGICAL'),
    ], rows=[
        (1, 'café', Decimal('123.450'), True),
        (2, 'ñandú', Decimal('-0.125'), False),
        (3, None, None, None),
    ], indexes=[SumIndex('idx_descripcion', ('descripcion',))]);


def test_sumx_roundtrip_native_schema(tmp_path):
    model = _sample();
    source = tmp_path / 'in.sumtab';
    database = tmp_path / 'data.sumx';
    result = tmp_path / 'out.sumtab';
    write_sumtab(model, source);
    assert import_table(database, 'datos', source) == 3;
    assert is_sumx_database(database);
    assert export_table(database, 'datos', result) == 3;
    output = read_sumtab(result);
    assert output.rows == model.rows;
    assert [(c.name,c.logical_type,c.scale,c.length) for c in output.columns] == [
        (c.name,c.logical_type,c.scale,c.length) for c in model.columns
    ];
    assert [(i.name,i.columns,i.unique) for i in output.indexes] == [('idx_descripcion',('descripcion',),False)];
    assert read_sqlite(database, 'datos').rows == model.rows;


def test_sumdoc_native_extension(tmp_path):
    model = _sample();
    options = create_parser().parse_args(['--table', 'datos']);
    path = tmp_path / 'datos.sumx';
    write_table(model, path, 'sumx', options);
    assert read_table(path, 'sumx', options).rows == model.rows;


def test_sumx_import_does_not_replace_table(tmp_path):
    file = tmp_path / 'in.sumtab';
    write_sumtab(_sample(), file);
    db = tmp_path / 'base.sumx';
    import_table(db, 'datos', file);
    with pytest.raises(ValueError, match='already exists'):
        import_table(db, 'datos', file);
    assert len(read_sqlite(db, 'datos').rows) == 3;


def test_sumx_unknown_index_expression_is_rejected(tmp_path):
    model = _sample();
    model.indexes = [SumIndex('expression_idx', expression='UPPER(descripcion)')];
    file = tmp_path / 'in.sumtab';
    write_sumtab(model, file);
    db = tmp_path / 'base.sumx';
    with pytest.raises(ValueError, match='Expression indexes'):
        import_table(db, 'datos', file);
    with sqlite3.connect(db) as conn:
        assert not conn.execute("SELECT 1 FROM sqlite_master WHERE name='datos'").fetchone();
