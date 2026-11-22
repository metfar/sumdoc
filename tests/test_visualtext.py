#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#pylint:disable=W0301
#
#  Copyright 2018-2026 William Martinez Bas <metfar@gmail.com>
#  Licensed under GPL-2.0-or-later.
#
import re;
from PIL import Image;
from sumdoc.tools.visualtext import render;
from sumdoc.tools.png2text import create_parser;

ESC = re.compile(r"\x1b\[[0-9;]*m");

def test_all_four_modes_and_exact_width():
    img = Image.new("RGB", (100, 60), (24, 32, 40));
    words = [{"text": "HELLO", "x": 10, "y": 10, "w": 40, "h": 12, "conf": 90.0}];
    for visual in (False, True):
        for color in (False, True):
            output = render(img, words, 40, 1.65, 50, 25, visual=visual, color=color);
            lines = output.splitlines();
            assert lines;
            assert all(len(ESC.sub("", line)) == 40 for line in lines);
            assert any("HELLO" in ESC.sub("", line) for line in lines);
            assert ("\x1b[" in output) == color;

def test_parser_visual_flags():
    args = create_parser().parse_args(["a.png", "--visual", "--color", "--width", "160"]);
    assert args.visual and args.color and args.width == 160;
