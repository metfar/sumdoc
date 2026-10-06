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
from pathlib import Path;
import sys;

from sumdoc import __version__;
from sumdoc.common import GlobalOptions, safe_symlink;
from sumdoc.registry import TOOLS, all_invocation_names, resolve_tool;


PROGRAM_NAMES = {"sumdoc", "sumdoc.py", "__main__.py"};


def invocation_name(argv0: str) -> str:
    name = Path(argv0).name;
    if name.endswith(".py") and name not in PROGRAM_NAMES:
        name = name[:-3];
    return (name.lower());


def _take_value(arguments: list[str], index: int, option: str) -> tuple[str, int]:
    if index + 1 >= len(arguments):
        raise ValueError(f"Missing value after '{option}'.");
    return (arguments[index + 1], index + 2);


def extract_global_options(arguments: list[str]) -> tuple[str | None, GlobalOptions, list[str]]:
    tool_name = None;
    options = GlobalOptions();
    remaining = [];
    index = 0;
    scanning = True;
    while index < len(arguments):
        argument = arguments[index];
        if argument == "--":
            remaining.extend(arguments[index:]);
            break;
        if scanning and argument in ("-t", "--tool"):
            tool_name, index = _take_value(arguments, index, argument);
            continue;
        if scanning and argument.startswith("--tool="):
            tool_name = argument.split("=", 1)[1];
            index += 1;
            continue;
        if scanning and argument in ("-o", "--output"):
            options.output, index = _take_value(arguments, index, argument);
            continue;
        if scanning and argument.startswith("--output="):
            options.output = argument.split("=", 1)[1];
            index += 1;
            continue;
        if scanning and argument in ("-d", "--output-dir", "--outputdir"):
            options.output_dir, index = _take_value(arguments, index, argument);
            continue;
        if scanning and (argument.startswith("--output-dir=") or argument.startswith("--outputdir=")):
            options.output_dir = argument.split("=", 1)[1];
            index += 1;
            continue;
        if scanning and argument in ("-f", "--force", "--overwrite"):
            options.force = True;
            index += 1;
            continue;
        if scanning and argument in ("-q", "--quiet"):
            options.quiet = True;
            index += 1;
            continue;
        if scanning and argument in ("-v", "--verbose"):
            options.verbose += 1;
            index += 1;
            continue;
        remaining.append(argument);
        index += 1;
    options.validate();
    return (tool_name, options, remaining);


def select_tool(explicit_name: str | None, argv0: str,
                arguments: list[str]) -> tuple[object | None, list[str]]:
    if explicit_name is not None:
        tool = resolve_tool(explicit_name);
        if tool is None:
            raise ValueError(f"Unknown tool: '{explicit_name}'.");
        return (tool, arguments);
    called_as = invocation_name(argv0);
    tool = resolve_tool(called_as);
    if tool is not None:
        return (tool, arguments);
    if arguments and resolve_tool(arguments[0]) is not None:
        return (resolve_tool(arguments[0]), arguments[1:]);
    return (None, arguments);


def show_general_help(file=sys.stdout) -> None:
    print("SumDoc - small Unix-style document conversion tools", file=file);
    print("", file=file);
    print("Usage:", file=file);
    print("  sumdoc TOOL [GLOBAL OPTIONS] [TOOL OPTIONS]", file=file);
    print("  sumdoc --tool TOOL [GLOBAL OPTIONS] [TOOL OPTIONS]", file=file);
    print("  TOOL [GLOBAL OPTIONS] [TOOL OPTIONS]    # through a symbolic link", file=file);
    print("", file=file);
    print("Global options may appear before or after tool-specific arguments:", file=file);
    print("  -t, --tool NAME          Select a tool explicitly.", file=file);
    print("  -o, --output FILE        Write one exact output file.", file=file);
    print("  -d, --output-dir DIR     Generate output names inside a directory.", file=file);
    print("  -f, --force              Replace existing output files.", file=file);
    print("  -q, --quiet              Suppress informational messages.", file=file);
    print("  -v, --verbose            Show additional diagnostic information.", file=file);
    print("      --list-tools         List canonical tools and aliases.", file=file);
    print("      --install-links DIR  Create multicall symbolic links.", file=file);
    print("      --remove-links DIR   Remove SumDoc symbolic links.", file=file);
    print("      --version            Show the SumDoc version.", file=file);
    print("  -h, --help               Show this help or the selected tool help.", file=file);
    print("", file=file);
    print("Tools:", file=file);
    for tool in TOOLS:
        aliases = f" (aliases: {', '.join(tool.aliases)})" if tool.aliases else "";
        print(f"  {tool.name:<12} {tool.description}{aliases}", file=file);


def list_tools() -> None:
    for tool in TOOLS:
        print(f"{tool.name}\t{tool.description}");
        for alias in tool.aliases:
            print(f"{alias}\tAlias for {tool.name}.");


def install_links(directory_text: str, argv0: str, force: bool) -> int:
    directory = Path(directory_text).expanduser().resolve();
    directory.mkdir(parents=True, exist_ok=True);
    target = Path(argv0).expanduser().resolve();
    if not target.exists():
        raise FileNotFoundError(f"Cannot locate the SumDoc executable: '{target}'.");
    if not target.is_file() or not target.stat().st_mode & 0o111:
        raise PermissionError(
            "Symbolic links require an installed executable. Run this command through the installed 'sumdoc' launcher."
        );
    created = 0;
    for name in all_invocation_names():
        link = directory / name;
        safe_symlink(target, link, force=force);
        created += 1;
    print(f"Created or verified {created} symbolic links in '{directory}'.", file=sys.stderr);
    return (0);


def remove_links(directory_text: str, argv0: str) -> int:
    directory = Path(directory_text).expanduser().resolve();
    target = Path(argv0).expanduser().resolve();
    removed = 0;
    for name in all_invocation_names():
        link = directory / name;
        if link.is_symlink() and link.resolve() == target:
            link.unlink();
            removed += 1;
    print(f"Removed {removed} SumDoc symbolic links from '{directory}'.", file=sys.stderr);
    return (0);


def _top_level_action(arguments: list[str], argv0: str, options: GlobalOptions) -> int | None:
    if "--version" in arguments:
        print(f"SumDoc {__version__}");
        return (0);
    if "--list-tools" in arguments:
        list_tools();
        return (0);
    for option, action in (("--install-links", install_links), ("--remove-links", remove_links)):
        if option in arguments:
            index = arguments.index(option);
            if index + 1 >= len(arguments):
                raise ValueError(f"Missing directory after '{option}'.");
            if action is install_links:
                return (action(arguments[index + 1], argv0, options.force));
            return (action(arguments[index + 1], argv0));
    return (None);


def entry_point(arguments: list[str] | None = None) -> int:
    argv0 = sys.argv[0];
    if arguments is None:
        arguments = sys.argv[1:];
    try:
        explicit_name, options, remaining = extract_global_options(list(arguments));
        action_result = _top_level_action(remaining, argv0, options);
        if action_result is not None:
            return (action_result);
        tool, tool_arguments = select_tool(explicit_name, argv0, remaining);
        if tool is None:
            if tool_arguments and tool_arguments[0] not in ("-h", "--help"):
                raise ValueError(
                    f"No tool was selected. Use --tool NAME or one of: {', '.join(t.name for t in TOOLS)}."
                );
            show_general_help();
            return (0);
        if tool_arguments and tool_arguments[0] == "--":
            tool_arguments = tool_arguments[1:];
        main = tool.load();
        return (main(tool_arguments, options));
    except KeyboardInterrupt:
        print("Interrupted.", file=sys.stderr);
        return (130);
    except (FileNotFoundError, FileExistsError, IsADirectoryError, PermissionError,
            RuntimeError, ValueError) as error:
        print(f"Error: {error}", file=sys.stderr);
        return (2);
    except ImportError as error:
        print(f"Error: missing optional dependency: {error}", file=sys.stderr);
        print("Install the required SumDoc feature group, for example: pip install 'sumdoc[all]'", file=sys.stderr);
        return (3);
