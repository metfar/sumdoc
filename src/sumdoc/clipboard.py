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
import os;
from pathlib import Path;
import re;
import shutil;
import subprocess;
import tempfile;
from typing import Callable, Mapping, Sequence;


IMAGE_TYPES = (
    "image/png",
    "image/jpeg",
    "image/jpg",
    "image/webp",
    "image/gif",
    "image/bmp",
);

DOCUMENT_TEXT_TYPES = (
    "text/markdown",
    "text/x-markdown",
    "text/html",
    "text/rtf",
    "application/rtf",
    "text/plain;charset=utf-8",
    "utf8_string",
    "text/plain",
    "string",
);

GENERAL_PRIORITY = IMAGE_TYPES + DOCUMENT_TEXT_TYPES;
TEXT_PRIORITY = DOCUMENT_TEXT_TYPES;
DOCUMENT_PRIORITY = DOCUMENT_TEXT_TYPES;


@dataclass(frozen=True)
class ClipboardBackend:
    """Selected operating-system clipboard transport.""";

    name: str;
    provider: str;


@dataclass(frozen=True)
class ClipboardContent:
    """One clipboard representation together with its transport metadata.""";

    mime_type: str;
    data: bytes;
    backend: ClipboardBackend;


def _wayland_socket_exists(env: Mapping[str, str], exists: Callable[[str], bool]) -> bool:
    display = env.get("WAYLAND_DISPLAY", "").strip();
    if not display:
        return (False);
    if display.startswith("/"):
        return (exists(display));
    runtime = env.get("XDG_RUNTIME_DIR", "").strip();
    if not runtime:
        return (False);
    return (exists(str(Path(runtime) / display)));


def detect_backend(env: Mapping[str, str] | None = None,
                   which: Callable[[str], str | None] = shutil.which,
                   exists: Callable[[str], bool] = os.path.exists) -> ClipboardBackend | None:
    """Select a clipboard transport without probing a display family that is not active.""";
    environment = os.environ if env is None else env;
    if _wayland_socket_exists(environment, exists) and which("wl-paste"):
        return (ClipboardBackend("wayland", "wl-paste"));
    if environment.get("DISPLAY", "").strip():
        if which("xclip"):
            return (ClipboardBackend("x11", "xclip"));
        if which("xsel"):
            return (ClipboardBackend("x11", "xsel"));
    return (None);


def _run(command: Sequence[str], input_bytes: bytes | None = None) -> bytes:
    result = subprocess.run(
        list(command),
        input=input_bytes,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        check=True,
    );
    return (result.stdout);


def _unique(items: Sequence[str]) -> list[str]:
    seen = set();
    ordered = [];
    for item in items:
        value = item.strip();
        if value and value.lower() not in seen:
            seen.add(value.lower());
            ordered.append(value);
    return (ordered);


def available_types(backend: ClipboardBackend | None = None) -> list[str]:
    """Return MIME/TARGET representations advertised by the current clipboard.""";
    selected = backend or detect_backend();
    if selected is None:
        return ([]);
    if selected.provider == "wl-paste":
        data = _run(["wl-paste", "--list-types"]);
        return (_unique(data.decode("utf-8", errors="ignore").splitlines()));
    if selected.provider == "xclip":
        data = _run(["xclip", "-selection", "clipboard", "-t", "TARGETS", "-o"]);
        text = data.decode("utf-8", errors="ignore").replace("\r", " ").replace("\n", " ");
        return (_unique(text.split()));
    if selected.provider == "xsel":
        # xsel does not provide the same useful TARGETS enumeration API as xclip.
        # It remains a text-only fallback.;
        return (["text/plain;charset=utf-8", "text/plain"]);
    return ([]);


def read_type(mime_type: str, backend: ClipboardBackend | None = None) -> ClipboardContent:
    """Read one exact clipboard representation as bytes.""";
    selected = backend or detect_backend();
    if selected is None:
        raise RuntimeError("No supported clipboard backend is active.");
    if selected.provider == "wl-paste":
        data = _run(["wl-paste", "--type", mime_type, "--no-newline"]);
    elif selected.provider == "xclip":
        data = _run(["xclip", "-selection", "clipboard", "-t", mime_type, "-o"]);
    elif selected.provider == "xsel":
        if normalize_type(mime_type) not in ("text/plain", "text/plain;charset=utf-8", "utf8_string", "string"):
            raise RuntimeError("xsel fallback only supports plain text clipboard content.");
        data = _run(["xsel", "--clipboard", "--output"]);
    else:
        raise RuntimeError(f"Unsupported clipboard provider: {selected.provider}.");
    return (ClipboardContent(mime_type, data, selected));


def normalize_type(mime_type: str) -> str:
    return (mime_type.strip().lower().replace(" ", ""));


def _type_index(available: Sequence[str]) -> dict[str, str]:
    index = {};
    for item in available:
        index.setdefault(normalize_type(item), item);
    return (index);


def choose_best_type(available: Sequence[str], kind: str = "any") -> str | None:
    """Choose the richest usable representation for the requested content family.""";
    index = _type_index(available);
    priorities = {
        "any": GENERAL_PRIORITY,
        "text": TEXT_PRIORITY,
        "document": DOCUMENT_PRIORITY,
        "image": IMAGE_TYPES,
    };
    if kind not in priorities:
        raise ValueError(f"Unknown clipboard content kind: {kind}.");
    for preferred in priorities[kind]:
        key = normalize_type(preferred);
        if key in index:
            return (index[key]);
    # X11 applications sometimes advertise text/plain with additional parameters.;
    if kind in ("any", "text", "document"):
        for key, original in index.items():
            if key.startswith("text/plain;"):
                return (original);
    return (None);


def read_best(kind: str = "any", backend: ClipboardBackend | None = None) -> ClipboardContent | None:
    selected = backend or detect_backend();
    if selected is None:
        return (None);
    types = available_types(selected);
    best = choose_best_type(types, kind=kind);
    if best is None:
        return (None);
    return (read_type(best, selected));


def decode_text(data: bytes) -> str:
    for encoding in ("utf-8", "utf-16", "latin-1"):
        try:
            return (data.decode(encoding));
        except UnicodeDecodeError:
            continue;
    return (data.decode("utf-8", errors="replace"));


def _rtf_plain_fallback(data: bytes) -> str:
    """Last-resort RTF text extraction when no richer converter is installed.""";
    text = data.decode("latin-1", errors="replace");
    text = re.sub(r"\\'([0-9a-fA-F]{2})", lambda match: bytes.fromhex(match.group(1)).decode("cp1252", errors="replace"), text);
    text = text.replace("\\par", "\n").replace("\\line", "\n").replace("\\tab", "\t");
    text = re.sub(r"\\[a-zA-Z]+-?\d* ?", "", text);
    text = text.replace("\\{", "{").replace("\\}", "}").replace("\\\\", "\\");
    text = text.replace("{", "").replace("}", "");
    return (text.strip() + "\n");


def rtf_to_markdown(data: bytes) -> str:
    """Convert RTF to Markdown, preferring converters that preserve rich formatting.""";
    pandoc = shutil.which("pandoc");
    if pandoc:
        try:
            result = subprocess.run(
                [pandoc, "--from=rtf", "--to=gfm"],
                input=data,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                check=True,
            );
            if result.stdout:
                return (decode_text(result.stdout));
        except subprocess.CalledProcessError:
            pass;
    unrtf = shutil.which("unrtf");
    if unrtf:
        try:
            with tempfile.NamedTemporaryFile(suffix=".rtf") as source:
                source.write(data);
                source.flush();
                result = subprocess.run(
                    [unrtf, "--html", "--nopict", source.name],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.DEVNULL,
                    check=True,
                );
            from sumdoc.tools.html2md import html_to_markdown;
            return (html_to_markdown(decode_text(result.stdout)));
        except (subprocess.CalledProcessError, OSError):
            pass;
    return (_rtf_plain_fallback(data));


def content_to_markdown(content: ClipboardContent) -> str:
    """Convert a textual clipboard representation to editable Markdown.""";
    mime_type = normalize_type(content.mime_type);
    if mime_type in ("text/markdown", "text/x-markdown"):
        return (decode_text(content.data));
    if mime_type == "text/html":
        from sumdoc.tools.html2md import html_to_markdown;
        return (html_to_markdown(decode_text(content.data)));
    if mime_type in ("text/rtf", "application/rtf"):
        return (rtf_to_markdown(content.data));
    if mime_type.startswith("text/plain") or mime_type in ("utf8_string", "string"):
        return (decode_text(content.data));
    raise ValueError(f"Clipboard type '{content.mime_type}' cannot be converted to Markdown text.");
