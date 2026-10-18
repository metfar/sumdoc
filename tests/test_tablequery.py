#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#pylint:disable=W0301

from pathlib import Path;

from sumdoc.sumtab import SumColumn, SumTable, write_sumtab;
from sumdoc.tools import tablequery;


def _write_hr_catalog(root: Path):
    hr = root / "HR";
    hr.mkdir();
    write_sumtab(
        SumTable(
            columns=[
                SumColumn("DEPARTMENT_ID", "INTEGER"),
                SumColumn("DEPARTMENT_NAME", "VARCHAR"),
                SumColumn("MANAGER_ID", "INTEGER"),
                SumColumn("LOCATION_ID", "INTEGER"),
            ],
            rows=[
                (10, "Administration", 200, 1700),
                (20, "Marketing", 201, 1800),
                (40, "Human Resources", 203, 2400),
                (70, "Public Relations", 204, 2700),
                (110, "Accounting", 205, 1700),
            ],
        ),
        hr / "DEPARTMENTS.sumtab",
    );
    write_sumtab(
        SumTable(
            columns=[
                SumColumn("LOCATION_ID", "INTEGER"),
                SumColumn("CITY", "VARCHAR"),
            ],
            rows=[
                (1700, "Seattle"),
                (1800, "Toronto"),
            ],
        ),
        hr / "LOCATIONS.sumtab",
    );


def test_tablequery_list_show_describe_and_select(tmp_path):
    _write_hr_catalog(tmp_path);

    listed = tablequery.execute_command(tmp_path, "list");
    assert "SCHEMA_NAME" in listed;
    assert "HR" in listed;

    shown = tablequery.execute_command(tmp_path, "show HR");
    assert "TABLE_NAME" in shown;
    assert "DEPARTMENTS" in shown;
    assert "LOCATIONS" in shown;

    described = tablequery.execute_command(tmp_path, "describe HR.LOCATIONS");
    assert "COLUMN_NAME" in described;
    assert "LOCATION_ID" in described;
    assert "CITY" in described;

    selected = tablequery.execute_command(
        tmp_path,
        "select * from HR.DEPARTMENTS where MANAGER_ID > 200",
    );
    assert "Marketing" in selected;
    assert "Human Resources" in selected;
    assert "Public Relations" in selected;
    assert "Accounting" in selected;
    assert "Administration" not in selected;


def test_tablequery_rejects_non_select_sql(tmp_path):
    _write_hr_catalog(tmp_path);
    try:
        tablequery.execute_command(tmp_path, "delete from HR.DEPARTMENTS");
    except ValueError as exc:
        assert "Unknown command" in str(exc) or "Only SELECT" in str(exc);
    else:
        raise AssertionError("Expected a read-only query rejection.");


def test_tablequery_single_file_accepts_table_alias(tmp_path):
    path = tmp_path / "people.sumtab";
    write_sumtab(
        SumTable(
            columns=[SumColumn("id", "INTEGER"), SumColumn("name", "VARCHAR")],
            rows=[(1, "Ana"), (2, "Seba")],
        ),
        path,
    );
    result = tablequery.execute_command(tmp_path, "select * from table where id > 1", path);
    assert "Seba" in result;
    assert "Ana" not in result;
