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
from datetime import datetime;
from html.parser import HTMLParser;
from io import BytesIO;
import importlib.util;
import os;
from pathlib import Path;
import re;
import shutil;
import subprocess;
import tempfile;
from typing import Callable, Mapping, Sequence;


URI_TYPES = (
    "text/uri-list",
);

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

GENERAL_PRIORITY = IMAGE_TYPES + URI_TYPES + DOCUMENT_TEXT_TYPES;
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


def _run(command: Sequence[str], input_bytes: bytes | None = None, timeout: float = 1.5) -> bytes:
    result = subprocess.run(
        list(command),
        input=input_bytes,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        check=True,
        timeout=max(0.1, float(timeout)),
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


class _FirstImageSourceParser(HTMLParser):
    def __init__(self):
        super().__init__();
        self.src = None;

    def handle_starttag(self, tag, attrs):
        if self.src is not None or str(tag).lower() != "img":
            return;
        values = dict(attrs);
        value = values.get("src");
        if value:
            self.src = str(value);


def clipboard_url(backend: ClipboardBackend | None = None) -> str | None:
    """Return a URL/filename advertised by the clipboard when one really exists.""";
    selected = backend or detect_backend();
    if selected is None:
        return (None);
    types = available_types(selected);
    index = _type_index(types);
    for preferred in URI_TYPES:
        key = normalize_type(preferred);
        if key in index:
            text = decode_text(read_type(index[key], selected).data);
            for line in text.splitlines():
                value = line.strip();
                if value and not value.startswith("#"):
                    return (value);
    html_type = index.get("text/html");
    if html_type:
        parser = _FirstImageSourceParser();
        try:
            parser.feed(decode_text(read_type(html_type, selected).data));
        except Exception:
            return (None);
        return (parser.src);
    return (None);


def _image_from_content(content: ClipboardContent):
    try:
        from PIL import Image;
    except ImportError as error:
        raise ImportError("Pillow is required for clipboard image conversion.") from error;
    return (Image.open(BytesIO(content.data)).convert("RGB"));


def clipboard_image_content(backend: ClipboardBackend | None = None) -> ClipboardContent | None:
    return (read_best("image", backend));


def image_placeholder(content: ClipboardContent) -> str:
    """Describe a clipboard image without inventing a source URL or filename.""";
    image = _image_from_content(content);
    width, height = image.size;
    mime = normalize_type(content.mime_type);
    label = mime.split("/", 1)[-1].upper() if "/" in mime else mime.upper();
    name = clipboard_url(content.backend) or "clipboard image";
    return ("┌─ Image ──────────────────────────────┐\n"
            "│ {name}\n"
            "│ {width} × {height} · {kind}\n"
            "└──────────────────────────────────────┘".format(
                name=name, width=width, height=height, kind=label));


def image_to_ocr_text(content: ClipboardContent) -> str:
    """Extract OCR text from a clipboard image when pytesseract is available.""";
    try:
        import pytesseract;
    except ImportError as error:
        raise ImportError("pytesseract is required for Paste Special → OCR text.") from error;
    image = _image_from_content(content);
    text = pytesseract.image_to_string(image);
    return (str(text).rstrip() + ("\n" if str(text).strip() else ""));


def image_to_ascii_text(content: ClipboardContent, width: int = 72, with_ocr: bool = False) -> str:
    """Render a clipboard image as DOS/Spectrum-style Unicode blocks, optionally overlaying OCR words.""";
    image = _image_from_content(content);
    from PIL import ImageEnhance, ImageFilter, ImageOps;
    raw = ImageOps.autocontrast(image.convert("RGB"));
    original_width, original_height = raw.size;
    target_width = max(8, int(width));
    target_height = max(1, int((original_height / max(1, original_width)) * target_width * 0.45));
    gray = ImageOps.invert(raw.convert("L")).filter(ImageFilter.MaxFilter(3));
    gray = ImageEnhance.Contrast(gray).enhance(2.0).resize((target_width, target_height));
    pixels = gray.load();
    grid = [[" " for _ in range(target_width)] for _ in range(target_height)];
    for y in range(target_height):
        for x in range(target_width):
            value = pixels[x, y];
            if value > 160:
                grid[y][x] = "█";
            elif value > 80:
                grid[y][x] = "▓";
            elif value > 30:
                grid[y][x] = "░";
    if with_ocr:
        try:
            import pytesseract;
            data = pytesseract.image_to_data(raw, config="--psm 11", output_type=pytesseract.Output.DICT);
            for index, text in enumerate(data.get("text", [])):
                word = str(text).strip();
                try:
                    confidence = float(data.get("conf", [0])[index]);
                except (ValueError, TypeError, IndexError):
                    confidence = 0;
                if not word or confidence <= 35:
                    continue;
                gx = int((data["left"][index] / original_width) * target_width);
                gy = int(((data["top"][index] + data["height"][index] / 2) / original_height) * target_height);
                if not (0 <= gy < target_height):
                    continue;
                for dx in range(-1, len(word) + 1):
                    if 0 <= gx + dx < target_width:
                        grid[gy][gx + dx] = " ";
                for offset, char in enumerate(word):
                    if 0 <= gx + offset < target_width:
                        grid[gy][gx + offset] = char;
        except ImportError:
            pass;
    return ("\n".join("".join(row).rstrip() for row in grid).rstrip() + "\n");


def save_clipboard_image_asset(content: ClipboardContent, directory: str | Path = "images") -> Path:
    """Save a clipboard bitmap as a portable PNG asset and return its path.""";
    target_dir = Path(directory).expanduser();
    target_dir.mkdir(parents=True, exist_ok=True);
    stem = datetime.now().strftime("clipboard-%Y%m%d-%H%M%S");
    target = target_dir / f"{stem}.png";
    suffix = 1;
    while target.exists():
        target = target_dir / f"{stem}-{suffix}.png";
        suffix += 1;
    image = _image_from_content(content);
    image.save(target, "PNG");
    return (target);


def special_paste_options(backend: ClipboardBackend | None = None) -> list[tuple[str, str]]:
    """Return context-sensitive Paste Special choices as (id, label) pairs.""";
    selected = backend or detect_backend();
    if selected is None:
        return ([]);
    types = available_types(selected);
    index = _type_index(types);
    result = [];
    if choose_best_type(types, "text") is not None:
        result.append(("plain", "As plain text"));
        result.append(("markdown", "As Markdown"));
    if "text/html" in index:
        result.append(("html", "As HTML source"));
    if "text/rtf" in index or "application/rtf" in index:
        result.append(("rtf", "As RTF source"));
    has_uri = any(normalize_type(value) in index for value in URI_TYPES);
    has_html = "text/html" in index;
    if has_uri or has_html:
        result.append(("url", "As URL / filename"));
    if choose_best_type(types, "image") is not None:
        has_pillow = importlib.util.find_spec("PIL") is not None;
        has_ocr = has_pillow and importlib.util.find_spec("pytesseract") is not None;
        if has_uri or has_html or has_pillow:
            result.append(("markdown-image", "As Markdown image"));
        if has_ocr:
            result.append(("ocr", "As OCR text"));
        if has_pillow:
            result.append(("ascii", "As ASCII/Unicode art"));
            if has_ocr:
                result.append(("ascii-ocr", "As ASCII/Unicode art + OCR"));
            result.append(("placeholder", "As image placeholder"));
    return (result);


def special_paste_text(kind: str, backend: ClipboardBackend | None = None) -> str:
    """Materialize one Paste Special representation as editor-insertable text.""";
    selected = backend or detect_backend();
    if selected is None:
        raise RuntimeError("No supported clipboard backend is active.");
    kind = str(kind).strip().lower();
    types = available_types(selected);
    index = _type_index(types);
    if kind == "plain":
        for key in ("text/plain;charset=utf-8", "utf8_string", "text/plain", "string"):
            if key in index:
                return (decode_text(read_type(index[key], selected).data));
        content = read_best("text", selected);
        if content is None:
            raise RuntimeError("Clipboard has no textual representation.");
        return (content_to_markdown(content));
    if kind == "markdown":
        content = read_best("text", selected);
        if content is None:
            raise RuntimeError("Clipboard has no document representation.");
        return (content_to_markdown(content));
    if kind == "html":
        if "text/html" not in index:
            raise RuntimeError("Clipboard does not advertise HTML.");
        return (decode_text(read_type(index["text/html"], selected).data));
    if kind == "rtf":
        key = "text/rtf" if "text/rtf" in index else "application/rtf";
        if key not in index:
            raise RuntimeError("Clipboard does not advertise RTF.");
        return (decode_text(read_type(index[key], selected).data));
    if kind == "url":
        value = clipboard_url(selected);
        if not value:
            raise RuntimeError("Clipboard does not advertise an image URL or filename.");
        return (value);
    content = read_best("image", selected);
    if content is None:
        raise RuntimeError("Clipboard has no compatible image representation.");
    if kind == "placeholder":
        return (image_placeholder(content));
    if kind == "ocr":
        return (image_to_ocr_text(content));
    if kind == "ascii":
        return (image_to_ascii_text(content, with_ocr=False));
    if kind == "ascii-ocr":
        return (image_to_ascii_text(content, with_ocr=True));
    if kind == "markdown-image":
        source = clipboard_url(selected);
        if source:
            return (f"![clipboard image]({source})");
        path = save_clipboard_image_asset(content);
        return (f"![clipboard image]({path.as_posix()})");
    raise ValueError(f"Unknown Paste Special representation: {kind}.");
