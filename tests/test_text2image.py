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

import os;

import pytest;

from sumdoc.common import GlobalOptions;
from sumdoc.registry import resolve_tool;
from sumdoc.tools.text2image import render_text_png, text2image_main;


def test_writeonimage_is_text2image_alias():
    assert resolve_tool("writeOnImage") is resolve_tool("text2image");
    assert resolve_tool("writeonimage") is resolve_tool("text2image");


def test_render_text_png_produces_png():
    pytest.importorskip("PIL");
    data = render_text_png("La casa roja 4", font_size=16);
    assert data.startswith(b"\x89PNG\r\n\x1a\n");


def test_text2image_file_is_private_by_default(tmp_path):
    pytest.importorskip("PIL");
    output = tmp_path / "password.png";
    result = text2image_main(["secret", "value"], GlobalOptions(output=str(output), quiet=True));
    assert result == 0;
    assert output.read_bytes().startswith(b"\x89PNG\r\n\x1a\n");
    assert (os.stat(output).st_mode & 0o777) == 0o600;


def test_historical_out_option_still_works(tmp_path):
    pytest.importorskip("PIL");
    output = tmp_path / "legacy.png";
    result = text2image_main(["legacy", f"--out={output}"], GlobalOptions(quiet=True));
    assert result == 0;
    assert output.exists();
