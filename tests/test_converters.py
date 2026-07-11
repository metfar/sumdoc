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

from sumdoc.common import GlobalOptions;
from sumdoc.tools import html2md, md2html, pdf2png, pdf2txt;


def test_markdown_html_round_trip(tmp_path):
    markdown_path = tmp_path / "sample.md";
    html_path = tmp_path / "sample.html";
    roundtrip_path = tmp_path / "roundtrip.md";
    markdown_path.write_text("# SumDoc\n\n| A | B |\n|---|---|\n| 1 | 2 |\n", encoding="utf-8");
    result = md2html.main([str(markdown_path)], GlobalOptions(output=str(html_path)));
    assert result == 0;
    assert "<h1>SumDoc</h1>" in html_path.read_text(encoding="utf-8");
    result = html2md.main([str(html_path)], GlobalOptions(output=str(roundtrip_path)));
    assert result == 0;
    assert "SumDoc" in roundtrip_path.read_text(encoding="utf-8");


def test_pdf_render_and_text_extract(tmp_path):
    fitz = pytest.importorskip("fitz");
    pdf_path = tmp_path / "sample.pdf";
    document = fitz.open();
    page = document.new_page(width=595.275590551, height=841.889763780);
    page.insert_text((72, 72), "Hello from SumDoc");
    document.save(str(pdf_path));
    document.close();
    png_path = tmp_path / "page.png";
    result = pdf2png.main(
        [str(pdf_path), "--pages", "1", "--dpi", "300"],
        GlobalOptions(output=str(png_path), quiet=True),
    );
    assert result == 0;
    assert png_path.exists();
    pixmap = fitz.Pixmap(str(png_path));
    assert pixmap.width == 2481;
    assert pixmap.height == 3508;
    text_path = tmp_path / "sample.txt";
    result = pdf2txt.main(
        [str(pdf_path)],
        GlobalOptions(output=str(text_path), quiet=True),
    );
    assert result == 0;
    assert "Hello from SumDoc" in text_path.read_text(encoding="utf-8");


def test_md2html_line_breaks_preserve_input_lines():
    html = md2html.build_document(
        "one\ntwo\n",
        "Lines",
        md2html.DEFAULT_CSS,
        line_breaks=True,
    );
    assert "one<br" in html;
    assert "two" in html;


def test_md2html_terminal_mode_preserves_whitespace_and_strips_ansi():
    source = "one\n\x1b[01;34mtwo\x1b[0m\n";
    html = md2html.build_document(
        source,
        "Terminal",
        md2html.DEFAULT_CSS,
        terminal=True,
    );
    assert '<pre class="terminal"><code>one\ntwo\n</code></pre>' in html;
    assert "\x1b" not in html;


def test_md2html_ansi_mode_converts_sgr_to_html():
    source = "one\n\x1b[01;34mtwo\x1b[0m\n";
    html = md2html.build_document(
        source,
        "ANSI",
        md2html.DEFAULT_CSS,
        use_ansi=True,
    );
    assert "ansi-fg-bright-blue" in html;
    assert "two</span>\n" in html;
    assert "\x1b" not in html;
