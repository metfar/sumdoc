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
import os;
import sys;

from sumdoc.common import GlobalOptions, Reporter, check_writable;


def _parse_color(value: str) -> tuple[int, int, int, int]:
    """Parse #RRGGBB, #RRGGBBAA, or r,g,b[,a].""";
    text = value.strip();
    if text.startswith("#"):
        digits = text[1:];
        if len(digits) not in (6, 8):
            raise argparse.ArgumentTypeError("hex colors must be #RRGGBB or #RRGGBBAA");
        try:
            parts = [int(digits[index:index + 2], 16) for index in range(0, len(digits), 2)];
        except ValueError as error:
            raise argparse.ArgumentTypeError(f"invalid color: {value}") from error;
        if len(parts) == 3:
            parts.append(255);
        return (tuple(parts));
    try:
        parts = [int(item.strip()) for item in text.split(",")];
    except ValueError as error:
        raise argparse.ArgumentTypeError(f"invalid color: {value}") from error;
    if len(parts) not in (3, 4) or any(item < 0 or item > 255 for item in parts):
        raise argparse.ArgumentTypeError("colors must contain 3 or 4 values between 0 and 255");
    if len(parts) == 3:
        parts.append(255);
    return (tuple(parts));


def _clipboard_text() -> str:
    from sumdoc.clipboard import content_to_markdown, read_best;
    content = read_best("text");
    if content is None:
        raise RuntimeError("Clipboard has no compatible textual representation.");
    return (content_to_markdown(content).rstrip("\n"));


def _input_text(words: list[str], use_clipboard: bool) -> tuple[str, str]:
    if use_clipboard:
        if words:
            raise ValueError("text arguments and --clipboard cannot be used together.");
        return (_clipboard_text(), "clipboard");
    if words:
        return (" ".join(words), "arguments");
    if not sys.stdin.isatty():
        return (sys.stdin.read().rstrip("\n"), "stdin");
    raise ValueError("Provide text arguments, pipe text through stdin, or use --clipboard.");


def _load_font(font_name: str | None, font_size: int):
    try:
        from PIL import ImageFont;
    except ImportError as error:
        raise ImportError("Pillow is required for text2image/writeOnImage.") from error;
    if font_name:
        return (ImageFont.truetype(str(Path(font_name).expanduser()), font_size));
    for candidate in ("DejaVuSansMono.ttf", "DejaVuSans.ttf"):
        try:
            return (ImageFont.truetype(candidate, font_size));
        except OSError:
            continue;
    return (ImageFont.load_default());


def render_text_png(text: str, font_name: str | None = None, font_size: int = 16,
                    foreground: tuple[int, int, int, int] = (187, 187, 0, 255),
                    background: tuple[int, int, int, int] = (0, 0, 128, 255),
                    padding: int | None = None) -> bytes:
    """Render text to PNG bytes using Pillow and measured glyph bounds.""";
    try:
        from PIL import Image, ImageDraw;
    except ImportError as error:
        raise ImportError("Pillow is required for text2image/writeOnImage.") from error;
    font = _load_font(font_name, font_size);
    inset = max(0, font_size // 2) if padding is None else max(0, padding);
    probe = Image.new("RGBA", (1, 1), background);
    draw = ImageDraw.Draw(probe);
    sample = text if text else " ";
    left, top, right, bottom = draw.multiline_textbbox((0, 0), sample, font=font, spacing=max(1, font_size // 4));
    width = max(1, right - left + inset * 2);
    height = max(1, bottom - top + inset * 2);
    image = Image.new("RGBA", (width, height), background);
    draw = ImageDraw.Draw(image);
    draw.multiline_text((inset - left, inset - top), text, font=font, fill=foreground,
                        spacing=max(1, font_size // 4));
    output = BytesIO();
    image.save(output, "PNG");
    return (output.getvalue());


def _write_png(data: bytes, path: Path | None, options: GlobalOptions, private: bool) -> None:
    if path is None:
        sys.stdout.buffer.write(data);
        sys.stdout.buffer.flush();
        return;
    check_writable(path, options.force);
    flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC;
    mode = 0o600 if private else 0o666;
    descriptor = os.open(path, flags, mode);
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(data);
    except Exception:
        try:
            os.close(descriptor);
        except OSError:
            pass;
        raise;
    if private:
        os.chmod(path, 0o600);


def text2image_main(arguments: list[str] | None, options: GlobalOptions) -> int:
    parser = argparse.ArgumentParser(
        prog="text2image",
        description="Render text as PNG. Prefer stdin or --clipboard for passwords/secrets.",
    );
    parser.add_argument("text", nargs="*", help="Text to render. Shell arguments may be visible in history/process listings.");
    parser.add_argument("--clipboard", action="store_true", help="Read text from the clipboard instead of command-line arguments.");
    parser.add_argument("--font", help="TrueType/OpenType font file. Defaults to a common Pillow-accessible sans/mono font.");
    parser.add_argument("--size", type=int, default=16, metavar="PX", help="Font size in pixels. Default: 16.");
    parser.add_argument("--foreground", "--fg", type=_parse_color, default=(187, 187, 0, 255),
                        help="Text color: #RRGGBB or r,g,b. Default matches historical writeOnImage.");
    parser.add_argument("--background", "--bg", type=_parse_color, default=(0, 0, 128, 255),
                        help="Background color: #RRGGBB or r,g,b. Default matches historical writeOnImage.");
    parser.add_argument("--padding", type=int, help="Padding in pixels. Default: half the font size.");
    parser.add_argument("--out", help="Compatibility alias for global -o/--output.");
    parser.add_argument("--show", action="store_true", help="Open the generated image with Pillow after writing it to a file.");
    parser.add_argument("--public", action="store_true", help="Do not force mode 0600 on an output file.");
    args = parser.parse_args(arguments);
    if args.size <= 0:
        raise ValueError("--size must be greater than zero.");
    if args.padding is not None and args.padding < 0:
        raise ValueError("--padding cannot be negative.");
    if options.output is not None and args.out is not None:
        raise ValueError("Use either -o/--output or --out, not both.");
    text, source = _input_text(args.text, args.clipboard);
    reporter = Reporter(options);
    if source == "arguments":
        reporter.warning("Command-line text can be recorded in shell history and process listings; use stdin or --clipboard for secrets.");
    data = render_text_png(text, args.font, args.size, args.foreground, args.background, args.padding);
    output_text = options.output or args.out;
    path = None if output_text in (None, "-") else Path(output_text).expanduser().resolve();
    _write_png(data, path, options, private=not args.public);
    if path is not None:
        reporter.success(f"PNG written to: {path}");
    if args.show:
        if path is None:
            reporter.warning("--show requires a file output (-o/--output or --out); image was written to stdout only.");
        else:
            try:
                from PIL import Image;
                Image.open(path).show();
            except ImportError as error:
                raise ImportError("Pillow is required for --show.") from error;
    return (0);
