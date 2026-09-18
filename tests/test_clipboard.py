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

from sumdoc.clipboard import ClipboardBackend, ClipboardContent, choose_best_type, content_to_markdown, detect_backend;


def test_x11_is_selected_without_probing_wayland_when_wayland_display_is_unset():
    calls = [];
    def which(name):
        calls.append(name);
        return f"/usr/bin/{name}" if name in ("wl-paste", "xclip") else None;
    backend = detect_backend(
        env={"DISPLAY": ":3", "XDG_RUNTIME_DIR": "/run/user/1000"},
        which=which,
        exists=lambda _path: False,
    );
    assert backend == ClipboardBackend("x11", "xclip");
    assert "wl-paste" not in calls;
    assert calls == ["xclip"];


def test_wayland_requires_an_actual_socket_before_being_selected():
    backend = detect_backend(
        env={"WAYLAND_DISPLAY": "wayland-0", "XDG_RUNTIME_DIR": "/run/user/1000", "DISPLAY": ":0"},
        which=lambda name: f"/usr/bin/{name}" if name in ("wl-paste", "xclip") else None,
        exists=lambda path: path == "/run/user/1000/wayland-0",
    );
    assert backend == ClipboardBackend("wayland", "wl-paste");


def test_best_clipboard_type_keeps_rich_text_before_plain_text():
    types = ["UTF8_STRING", "text/plain", "text/rtf", "text/html"];
    assert choose_best_type(types, "text") == "text/html";


def test_markdown_clipboard_is_preferred_when_available():
    types = ["text/plain", "text/html", "text/markdown"];
    assert choose_best_type(types, "text") == "text/markdown";


def test_html_clipboard_converts_to_markdown():
    content = ClipboardContent(
        "text/html",
        b"<p><strong>Hello</strong> <em>world</em></p>",
        ClipboardBackend("x11", "xclip"),
    );
    markdown = content_to_markdown(content);
    assert "**Hello**" in markdown;
    assert "*world*" in markdown;


def test_special_paste_options_expose_rich_text_and_images(monkeypatch):
    import sumdoc.clipboard as clip;
    backend=ClipboardBackend("x11","xclip");
    monkeypatch.setattr(clip,"detect_backend",lambda:backend);
    monkeypatch.setattr(clip,"available_types",lambda _backend=None:["text/plain","text/html","text/rtf","image/png"]);
    monkeypatch.setattr(clip,"clipboard_url",lambda _backend=None:None);
    options=dict(clip.special_paste_options());
    assert "plain" in options;
    assert "markdown" in options;
    assert "html" in options;
    assert "rtf" in options;
    assert "markdown-image" in options;
    assert "ocr" in options;
    assert "ascii-ocr" in options;
    assert "placeholder" in options;


def test_image_to_ascii_text_is_plain_ascii_not_block_graphics():
    from io import BytesIO;
    from PIL import Image;
    import sumdoc.clipboard as clip;
    image=Image.new("L",(4,2),255);
    image.putpixel((0,0),0); image.putpixel((1,0),64); image.putpixel((2,0),128); image.putpixel((3,0),192);
    stream=BytesIO(); image.convert("RGB").save(stream,"PNG");
    content=ClipboardContent("image/png",stream.getvalue(),ClipboardBackend("x11","xclip"));
    text=clip.image_to_ascii_text(content,width=8,with_ocr=False);
    assert text.strip();
    assert not any(char in text for char in "█▓░▀▄▌▐");
    assert set(text)-set("@%#*+=-:. \n") == set();
