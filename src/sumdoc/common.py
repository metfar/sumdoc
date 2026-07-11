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
from pathlib import Path;
import os;
import sys;


@dataclass
class GlobalOptions:
    """Options shared by every SumDoc tool.""";

    output: str | None = None;
    output_dir: str | None = None;
    force: bool = False;
    quiet: bool = False;
    verbose: int = 0;

    def validate(self) -> None:
        if self.output is not None and self.output_dir is not None:
            raise ValueError("--output and --output-dir cannot be used together.");


class Reporter:
    """Write diagnostics to stderr without contaminating pipeline output.""";

    def __init__(self, options: GlobalOptions):
        self.options = options;

    def info(self, message: str) -> None:
        if not self.options.quiet:
            print(f"[Info] {message}", file=sys.stderr);

    def verbose(self, message: str) -> None:
        if not self.options.quiet and self.options.verbose > 0:
            print(f"[Detail] {message}", file=sys.stderr);

    def warning(self, message: str) -> None:
        if not self.options.quiet:
            print(f"[Warning] {message}", file=sys.stderr);

    def success(self, message: str) -> None:
        if not self.options.quiet:
            print(f"[OK] {message}", file=sys.stderr);


def require_input_file(path_text: str, expected_suffixes: tuple[str, ...] = ()) -> Path:
    path = Path(path_text).expanduser().resolve();
    if not path.exists():
        raise FileNotFoundError(f"Input file does not exist: '{path}'.");
    if not path.is_file():
        raise ValueError(f"Input path is not a file: '{path}'.");
    if expected_suffixes and path.suffix.lower() not in expected_suffixes:
        expected = ", ".join(expected_suffixes);
        raise ValueError(f"Input file '{path.name}' must use one of these extensions: {expected}.");
    return (path);


def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True);


def check_writable(path: Path, force: bool) -> None:
    if path.exists() and path.is_dir():
        raise IsADirectoryError(f"Output path is a directory: '{path}'.");
    if path.exists() and not force:
        raise FileExistsError(f"Output file already exists: '{path}'. Use --force to replace it.");
    ensure_parent(path);


def automatic_output_path(input_path: Path | None, output_dir: str, extension: str,
                          name: str | None = None) -> Path:
    directory = Path(output_dir).expanduser().resolve();
    directory.mkdir(parents=True, exist_ok=True);
    if name:
        stem = Path(name).stem;
    elif input_path is not None:
        stem = input_path.stem;
    else:
        raise ValueError("--output-dir requires a named input file or the --name option.");
    return (directory / f"{stem}{extension}");


def resolve_single_output(input_path: Path | None, options: GlobalOptions,
                          extension: str, name: str | None = None) -> Path | None:
    options.validate();
    if options.output is not None:
        if options.output == "-":
            return (None);
        return (Path(options.output).expanduser().resolve());
    if options.output_dir is not None:
        return (automatic_output_path(input_path, options.output_dir, extension, name));
    return (None);


def read_text_input(path_text: str | None, encoding: str = "utf-8") -> tuple[str, Path | None]:
    if path_text in (None, "-"):
        return (sys.stdin.read(), None);
    path = require_input_file(path_text);
    return (path.read_text(encoding=encoding), path);


def write_text_output(text: str, path: Path | None, options: GlobalOptions,
                      encoding: str = "utf-8") -> None:
    if path is None:
        sys.stdout.write(text);
        if text and not text.endswith("\n"):
            sys.stdout.write("\n");
        return;
    check_writable(path, options.force);
    path.write_text(text, encoding=encoding);


def write_binary_output(data: bytes, path: Path | None, options: GlobalOptions) -> None:
    if path is None:
        sys.stdout.buffer.write(data);
        sys.stdout.buffer.flush();
        return;
    check_writable(path, options.force);
    path.write_bytes(data);


def safe_symlink(target: Path, link: Path, force: bool = False) -> None:
    if link.is_symlink():
        if link.resolve() == target.resolve():
            return;
        if not force:
            raise FileExistsError(f"A different symbolic link already exists: '{link}'.");
        link.unlink();
    elif link.exists():
        if not force:
            raise FileExistsError(f"A file already exists: '{link}'.");
        if link.is_dir():
            raise IsADirectoryError(f"Cannot replace directory with a symbolic link: '{link}'.");
        link.unlink();
    link.symlink_to(os.path.relpath(target, start=link.parent));
