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

from dataclasses import dataclass;
from importlib import import_module;
from typing import Callable;


@dataclass(frozen=True)
class ToolSpec:
    """Describe a SumDoc tool without importing its optional dependencies.""";

    name: str;
    module: str;
    description: str;
    aliases: tuple[str, ...] = ();
    entry_point: str = "main";

    def load(self) -> Callable[[list[str], object], int]:
        module = import_module(self.module);
        return (getattr(module, self.entry_point));


TOOLS = (
    ToolSpec(
        "image2text",
        "sumdoc.tools.imagetext",
        "Render images as ASCII, blocks, or topology-aware semigraphics.",
        aliases=("image2ascii",),
        entry_point="image2text_main",
    ),
    ToolSpec(
        "image2ansi",
        "sumdoc.tools.imagetext",
        "Render images as ANSI color half-blocks or semigraphics.",
        entry_point="image2ansi_main",
    ),
    ToolSpec(
        "image2braille",
        "sumdoc.tools.imagetext",
        "Render images as Unicode Braille, optionally with ANSI color.",
        entry_point="image2braille_main",
    ),
    ToolSpec(
        "png2webp",
        "sumdoc.tools.imageconvert",
        "Convert PNG images to WebP.",
        aliases=("image2webp",),
        entry_point="png2webp_main",
    ),
    ToolSpec(
        "webp2png",
        "sumdoc.tools.imageconvert",
        "Convert WebP images to PNG.",
        aliases=("image2png",),
        entry_point="webp2png_main",
    ),
    ToolSpec(
        "pdf2png",
        "sumdoc.tools.pdf2png",
        "Render PDF pages as PNG images.",
    ),
    ToolSpec(
        "pdf2txt",
        "sumdoc.tools.pdf2txt",
        "Extract text, HTML, XML, or tagged output from PDF files.",
        aliases=("pdf2text",),
    ),
    ToolSpec(
        "png2text",
        "sumdoc.tools.png2text",
        "Extract Markdown text, code, or tables from an image using OCR.",
        aliases=("png2md", "image2md"),
    ),
    ToolSpec(
        "markdown2helpdb",
        "sumdoc.tools.helpconv",
        "Compile editable Sum help Markdown to versioned .helpdb JSON.",
        aliases=("md2helpdb",),
        entry_point="markdown2helpdb_main",
    ),
    ToolSpec(
        "helpdb2markdown",
        "sumdoc.tools.helpconv",
        "Reconstruct editable Markdown from a versioned .helpdb file.",
        aliases=("helpdb2md",),
        entry_point="helpdb2markdown_main",
    ),
    ToolSpec(
        "md2html",
        "sumdoc.tools.md2html",
        "Convert Markdown or terminal text to a complete HTML document.",
        aliases=("markdown2html",),
    ),
    ToolSpec(
        "html2md",
        "sumdoc.tools.html2md",
        "Convert HTML to Markdown.",
        aliases=("html2markdown",),
    ),
    ToolSpec(
        "md2pdf",
        "sumdoc.tools.md2pdf",
        "Convert Markdown or terminal text to PDF, including pipelines.",
        aliases=("md2pdfpipe", "markdown2pdf"),
    ),
);

TOOL_BY_NAME = {};
for _tool in TOOLS:
    TOOL_BY_NAME[_tool.name] = _tool;
    for _alias in _tool.aliases:
        TOOL_BY_NAME[_alias] = _tool;


def resolve_tool(name: str | None) -> ToolSpec | None:
    if name is None:
        return (None);
    return (TOOL_BY_NAME.get(name.lower()));


def all_invocation_names() -> tuple[str, ...]:
    names = [];
    for tool in TOOLS:
        names.append(tool.name);
        names.extend(tool.aliases);
    return (tuple(names));
