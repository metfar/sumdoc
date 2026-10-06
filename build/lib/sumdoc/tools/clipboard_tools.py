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

import argparse;
from io import BytesIO;
from pathlib import Path;

from sumdoc.clipboard import (
    available_types,
    choose_best_type,
    content_to_markdown,
    detect_backend,
    normalize_type,
    read_best,
    read_type,
);
from sumdoc.common import GlobalOptions, Reporter, check_writable, write_binary_output, write_text_output;


def _active_backend():
    backend = detect_backend();
    if backend is None:
        raise RuntimeError("No supported clipboard backend is active (Wayland/X11).");
    return (backend);


def clipinfo_main(arguments: list[str] | None, options: GlobalOptions) -> int:
    parser = argparse.ArgumentParser(prog="clipinfo", description="Show clipboard backend and advertised formats.");
    parser.parse_args(arguments);
    backend = _active_backend();
    types = available_types(backend);
    lines = [
        f"Clipboard backend : {backend.name}",
        f"Provider          : {backend.provider}",
        "",
        "Available formats:",
    ];
    if types:
        lines.extend(f"  {item}" for item in types);
    else:
        lines.append("  (none reported)");
    lines.extend([
        "",
        f"Best content type : {choose_best_type(types, 'any') or '(none)'}",
        f"Best text type    : {choose_best_type(types, 'text') or '(none)'}",
        f"Best image type   : {choose_best_type(types, 'image') or '(none)'}",
    ]);
    write_text_output("\n".join(lines) + "\n", None if options.output is None else Path(options.output), options);
    return (0);


def clipbesttype_main(arguments: list[str] | None, options: GlobalOptions) -> int:
    parser = argparse.ArgumentParser(prog="clipbesttype", description="Select the richest compatible clipboard type.");
    parser.add_argument("--kind", choices=("any", "text", "document", "image"), default="any");
    args = parser.parse_args(arguments);
    backend = _active_backend();
    best = choose_best_type(available_types(backend), args.kind);
    if best is None:
        raise RuntimeError(f"Clipboard has no compatible {args.kind} representation.");
    write_text_output(best + "\n", None if options.output is None else Path(options.output), options);
    return (0);


def clip2md_main(arguments: list[str] | None, options: GlobalOptions) -> int:
    parser = argparse.ArgumentParser(prog="clip2md", description="Convert the richest textual clipboard representation to Markdown.");
    parser.add_argument("filename", nargs="?", help="Compatibility output filename; -o/--output is preferred.");
    args = parser.parse_args(arguments);
    content = read_best("text", _active_backend());
    if content is None:
        raise RuntimeError("Clipboard has no compatible text, HTML, Markdown, or RTF representation.");
    markdown = content_to_markdown(content);
    output = options.output or args.filename;
    path = None if output in (None, "-") else Path(output).expanduser().resolve();
    write_text_output(markdown, path, options);
    return (0);


def _image_to_png(data: bytes, mime_type: str) -> bytes:
    if normalize_type(mime_type) == "image/png":
        return (data);
    try:
        from PIL import Image;
    except ImportError as error:
        raise ImportError("Pillow is required to convert clipboard images to PNG.") from error;
    source = BytesIO(data);
    output = BytesIO();
    with Image.open(source) as image:
        image.save(output, "PNG");
    return (output.getvalue());


def clip2png_main(arguments: list[str] | None, options: GlobalOptions) -> int:
    parser = argparse.ArgumentParser(prog="clip2png", description="Save the richest clipboard image representation as PNG.");
    parser.add_argument("filename", nargs="?", help="Compatibility output filename; .png is added when omitted.");
    args = parser.parse_args(arguments);
    content = read_best("image", _active_backend());
    if content is None:
        raise RuntimeError("Clipboard has no compatible image representation.");
    data = _image_to_png(content.data, content.mime_type);
    output = options.output or args.filename;
    path = None;
    if output not in (None, "-"):
        path = Path(output).expanduser();
        if path.suffix.lower() != ".png":
            path = path.with_suffix(path.suffix + ".png") if path.suffix else path.with_suffix(".png");
        path = path.resolve();
    write_binary_output(data, path, options);
    return (0);


def _preferred_types_for_suffix(suffix: str) -> tuple[str, ...]:
    suffix = suffix.lower();
    if suffix == ".rtf":
        return ("text/rtf", "application/rtf");
    if suffix in (".html", ".htm"):
        return ("text/html",);
    if suffix in (".md", ".markdown"):
        return ("text/markdown", "text/x-markdown", "text/html", "text/rtf", "application/rtf", "text/plain;charset=utf-8", "text/plain");
    return ("text/plain;charset=utf-8", "utf8_string", "text/plain", "string");


def clip2rtf_main(arguments: list[str] | None, options: GlobalOptions) -> int:
    parser = argparse.ArgumentParser(
        prog="clip2rtf",
        description="Compatibility clipboard saver for RTF/HTML/text; output extension selects the representation.",
    );
    parser.add_argument("filename", nargs="?", help="Output filename. Defaults to stdout when possible.");
    args = parser.parse_args(arguments);
    output = options.output or args.filename;
    if output in (None, "-"):
        suffix = ".rtf";
        path = None;
    else:
        path = Path(output).expanduser().resolve();
        suffix = path.suffix or ".txt";
    backend = _active_backend();
    types = available_types(backend);
    index = {normalize_type(item): item for item in types};
    selected = None;
    for preferred in _preferred_types_for_suffix(suffix):
        if normalize_type(preferred) in index:
            selected = index[normalize_type(preferred)];
            break;
    if selected is None:
        if suffix.lower() in (".md", ".markdown"):
            content = read_best("text", backend);
            if content is None:
                raise RuntimeError("Clipboard has no compatible textual representation.");
            data = content_to_markdown(content).encode("utf-8");
        else:
            raise RuntimeError(f"Clipboard does not advertise a representation compatible with '{suffix}'.");
    else:
        content = read_type(selected, backend);
        if suffix.lower() in (".md", ".markdown"):
            data = content_to_markdown(content).encode("utf-8");
        else:
            data = content.data;
    if path is not None:
        check_writable(path, options.force);
        path.write_bytes(data);
        Reporter(options).success(f"Clipboard written to: {path}");
    else:
        write_binary_output(data, None, options);
    return (0);
