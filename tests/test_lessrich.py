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

from io import StringIO;

import pytest;

from sumdoc.common import GlobalOptions;
from sumdoc.registry import resolve_tool;


pytest.importorskip("rich");

from rich.console import Console;
from sumdoc.tools import lessrich;


def test_lessrich_is_registered_with_md2rich_aliases():
    assert resolve_tool("md2rich").module == "sumdoc.tools.lessrich";
    assert resolve_tool("lessrich").name == "md2rich";
    assert resolve_tool("markdown2rich").name == "md2rich";


def test_lessrich_table_alignment_and_escaped_pipe():
    target = StringIO();
    console = Console(file=target, width=60, color_system=None, force_terminal=False);
    lessrich.render_markdown(
        console,
        "# Informe\n\n| Concepto | Valor |\n|---|---:|\n| A\\|B | 120 |\n",
    );
    output = target.getvalue();
    assert "Informe" in output;
    assert "Concepto" in output;
    assert "A|B" in output;
    assert "120" in output;
    assert "┏" in output;


def test_lessrich_writes_output_file(tmp_path):
    source = tmp_path / "sample.md";
    target = tmp_path / "sample.txt";
    source.write_text("# SumDoc\n", encoding="utf-8");
    result = lessrich.main(
        [str(source), "--no-color", "--width", "50"],
        GlobalOptions(output=str(target), quiet=True),
    );
    assert result == 0;
    assert "SumDoc" in target.read_text(encoding="utf-8");
