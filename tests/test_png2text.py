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

from types import SimpleNamespace;

import pytest;

from sumdoc.tools import png2text;


def test_mode_defaults_favour_terminal_screenshots():
    assert png2text.MODE_DEFAULTS["document"] == (3, 2.0);
    assert png2text.MODE_DEFAULTS["screen"] == (6, 4.0);
    assert png2text.MODE_DEFAULTS["terminal"] == (6, 4.0);


def test_parser_accepts_terminal_mode():
    args = png2text.create_parser().parse_args(["screen.png", "--mode", "terminal"]);
    assert args.mode == "terminal";
    assert args.psm is None;
    assert args.scale is None;


def test_validate_tesseract_reports_missing_executable(monkeypatch):
    fake = SimpleNamespace(
        pytesseract=SimpleNamespace(tesseract_cmd="tesseract"),
        TesseractNotFoundError=RuntimeError,
    );
    monkeypatch.setattr(png2text.shutil, "which", lambda _name: None);
    with pytest.raises(RuntimeError, match="sudo apt install tesseract-ocr"):
        png2text.validate_tesseract(fake, "eng");


def test_validate_tesseract_reports_missing_language(monkeypatch):
    fake = SimpleNamespace(
        pytesseract=SimpleNamespace(tesseract_cmd="tesseract"),
        TesseractNotFoundError=RuntimeError,
        get_languages=lambda config="": ["eng", "osd"],
    );
    monkeypatch.setattr(png2text.shutil, "which", lambda _name: "/usr/bin/tesseract");
    with pytest.raises(RuntimeError, match="spa"):
        png2text.validate_tesseract(fake, "eng+spa");
