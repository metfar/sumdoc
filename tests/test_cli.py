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

from pathlib import Path;

import pytest;

from sumdoc.cli import extract_global_options, select_tool;


def test_global_options_can_appear_anywhere():
    tool_name, options, remaining = extract_global_options([
        "input.pdf", "--dpi", "600", "-o", "page.png", "--tool", "pdf2png",
    ]);
    assert tool_name == "pdf2png";
    assert options.output == "page.png";
    assert remaining == ["input.pdf", "--dpi", "600"];


def test_output_and_output_dir_are_mutually_exclusive():
    with pytest.raises(ValueError):
        extract_global_options(["-o", "one.txt", "-d", "out"]);


def test_invocation_name_selects_alias():
    tool, remaining = select_tool(None, "/usr/local/bin/png2md", ["image.png"]);
    assert tool.name == "png2text";
    assert remaining == ["image.png"];


def test_subcommand_selects_tool():
    tool, remaining = select_tool(None, "sumdoc", ["html2md", "page.html"]);
    assert tool.name == "html2md";
    assert remaining == ["page.html"];
