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
from html import escape;
from pathlib import Path;
import re;

from sumdoc.ansi import ansi_to_html, strip_ansi;
from sumdoc.common import GlobalOptions, Reporter, read_text_input, resolve_single_output, write_text_output;


DARK_CSS = """:root {
  --bg: #0b0d10;
  --panel: #0e1216;
  --grid: #1b222a;
  --grid-strong: #2a333d;
  --text: #d6dde5;
  --muted: #8aa0b2;
  --accent: #1ec8ff;
  --code-bg: #101419;
}
* { box-sizing: border-box; }
html, body { min-height: 100%; }
body {
  background: var(--bg);
  color: var(--text);
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
  line-height: 1.55;
  margin: 0 auto;
  max-width: 78rem;
  padding: 24px 28px 60px 28px;
}
a { color: var(--accent); }
a:visited { color: #a98cff; }
h1 {
  color: var(--accent);
  letter-spacing: 2px;
  font-weight: 800;
  margin: 0 0 16px 0;
  text-transform: uppercase;
}
h2, h3, h4, h5, h6 { color: var(--text); }
hr { border: 0; border-top: 1px solid var(--grid-strong); }
blockquote {
  border-left: 3px solid var(--grid-strong);
  color: var(--muted);
  margin-left: 0;
  padding-left: 1rem;
}
pre {
  background: var(--code-bg);
  border: 1px solid var(--grid-strong);
  overflow-x: auto;
  padding: 1rem;
}
code {
  background: rgba(255,255,255,0.04);
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
  padding: 0.08em 0.25em;
}
pre code { background: transparent; padding: 0; }
pre.terminal {
  background: #101214;
  color: #d3d7cf;
  line-height: 1.25;
  tab-size: 8;
  white-space: pre;
}
.ansi-blink { animation: sumdoc-ansi-blink 1s steps(1, end) infinite; }
@keyframes sumdoc-ansi-blink { 50% { opacity: 0; } }
table {
  background: var(--panel);
  border: 1px solid var(--grid-strong);
  border-collapse: collapse;
  table-layout: fixed;
  width: 100%;
}
thead th {
  border-bottom: 2px solid var(--grid-strong);
  color: var(--text);
  font-weight: 800;
  padding: 10px 12px;
  text-align: left;
}
th, td {
  border-left: 1px solid var(--grid);
  border-right: 1px solid var(--grid);
  padding: 8px 12px;
  text-align: left;
}
tr { border-bottom: 1px solid var(--grid); }
tr:nth-child(even) td { background: rgba(255,255,255,0.02); }
img { height: auto; max-width: 100%; }
.numbers { font-size: 14px; letter-spacing: 2px; margin: 8px 0 22px 2px; }
.table-wrap { background: var(--panel); border: 1px solid var(--grid-strong); padding: 2px; }
.footer { color: var(--muted); display: flex; justify-content: space-between; margin-top: 16px; }
.center { color: var(--muted); letter-spacing: 2px; margin-top: 40px; text-align: center; }
.codecol { width: 18%; }
.subjectcol { width: 62%; }
.reqcol { width: 20%; }
""";


LIGHT_CSS = """body { font-family: sans-serif; line-height: 1.5; margin: 2rem auto; max-width: 70rem; padding: 0 1rem; }
pre { overflow-x: auto; padding: 1rem; background: #f4f4f4; }
code { font-family: monospace; }
pre.terminal { background: #101214; color: #d3d7cf; line-height: 1.25; tab-size: 8; white-space: pre; }
pre.terminal code { font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace; }
.ansi-blink { animation: sumdoc-ansi-blink 1s steps(1, end) infinite; }
@keyframes sumdoc-ansi-blink { 50% { opacity: 0; } }
table { border-collapse: collapse; }
th, td { border: 1px solid #888; padding: 0.4rem 0.6rem; text-align: left; }
img { max-width: 100%; height: auto; }
""";

# Historical md2html behavior is the Sum dark presentation.  Keep the public
# constant for callers that imported it before style presets existed.;
DEFAULT_CSS = DARK_CSS;
STYLE_PRESETS = {"dark": DARK_CSS, "light": LIGHT_CSS};


def _table_border_fallback(html_fragment: str) -> str:
    """Add the classic HTML table border attribute for restrictive LMS editors.""";
    pattern = re.compile(r"<table(?![^>]*\bborder\s*=)([^>]*)>", re.IGNORECASE);
    return (pattern.sub(r'<table border="1"\1>', html_fragment));


def markdown_to_fragment(markdown_text: str, line_breaks: bool = False,
                         table_border_fallback: bool = True) -> str:
    """Convert Markdown to an HTML fragment.""";
    markdown_text = strip_ansi(markdown_text);
    try:
        import markdown;
        extensions = ["tables", "fenced_code", "sane_lists"];
        if line_breaks:
            extensions.append("nl2br");
        fragment = markdown.markdown(
            markdown_text,
            extensions=extensions,
            output_format="html5",
        );
    except ImportError:
        try:
            import mistune;
        except ImportError as error:
            raise ImportError("Python-Markdown or Mistune is required for md2html.") from error;
        renderer = mistune.create_markdown(
            hard_wrap=line_breaks,
            plugins=["table", "strikethrough"],
        );
        fragment = renderer(markdown_text);
    if table_border_fallback:
        fragment = _table_border_fallback(fragment);
    return (fragment);


def terminal_to_fragment(text: str, use_ansi: bool = False) -> str:
    """Render line-oriented text as a preformatted terminal block.""";
    if use_ansi:
        content = ansi_to_html(text);
    else:
        content = escape(strip_ansi(text), quote=False);
    return (f'<pre class="terminal"><code>{content}</code></pre>');


def build_document(markdown_text: str, title: str, css_text: str, fragment: bool = False,
                   line_breaks: bool = False, terminal: bool = False,
                   use_ansi: bool = False, table_border_fallback: bool = True,
                   dark_metadata: bool = True) -> str:
    """Build an HTML fragment or a complete standalone document.""";
    terminal = terminal or use_ansi;
    if terminal:
        body = terminal_to_fragment(markdown_text, use_ansi=use_ansi);
    else:
        body = markdown_to_fragment(
            markdown_text,
            line_breaks=line_breaks,
            table_border_fallback=table_border_fallback,
        );
    if fragment:
        return (body);
    metadata = "";
    if dark_metadata:
        metadata = (
            ' data-color-mode="dark" data-light-theme="light" data-dark-theme="dark"'
            ' data-a11y-animated-images="system" data-a11y-link-underlines="true"'
        );
    return (
        "<!DOCTYPE html>\n"
        f"<html lang=\"en\"{metadata}>\n"
        "<head>\n"
        "  <meta charset=\"utf-8\">\n"
        "  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">\n"
        f"  <title>{escape(title)}</title>\n"
        "  <style>\n"
        f"{css_text.rstrip()}\n"
        "  </style>\n"
        "</head>\n"
        "<body>\n"
        f"{body}\n"
        "</body>\n"
        "</html>\n"
    );


def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="md2html", description="Convert Markdown or terminal text to HTML.");
    parser.add_argument("input", nargs="?", default="-", help="Markdown input file, or - for stdin. Default: stdin.");
    parser.add_argument("--name", help="Base output name when stdin is combined with --output-dir.");
    parser.add_argument("--title", help="HTML document title. Default: the input filename stem or Document.");
    parser.add_argument(
        "--style", "--theme",
        choices=tuple(STYLE_PRESETS),
        default="dark",
        help="Built-in HTML style. Default: dark (the historical SUM md2html presentation).",
    );
    parser.add_argument("--css", help="CSS file to embed instead of the selected built-in style.");
    parser.add_argument("--fragment", action="store_true", help="Write only the converted HTML fragment.");
    parser.add_argument(
        "--no-table-border-fallback",
        action="store_true",
        help="Do not add border=\"1\" to HTML tables. The fallback helps restrictive LMS editors.",
    );
    parser.add_argument(
        "--line-breaks", "--hard-wrap",
        action="store_true",
        help="Render every input newline as an HTML line break while retaining Markdown parsing.",
    );
    parser.add_argument(
        "--terminal", "--preformatted",
        action="store_true",
        help="Render input as preformatted terminal text instead of parsing it as Markdown.",
    );
    parser.add_argument(
        "--ansi",
        action="store_true",
        help="Convert ANSI SGR colors and styles to HTML. This implies --terminal.",
    );
    parser.add_argument("--encoding", default="utf-8", help="Text encoding. Default: utf-8.");
    return (parser);


def main(arguments: list[str] | None, options: GlobalOptions) -> int:
    args = create_parser().parse_args(arguments);
    reporter = Reporter(options);
    markdown_text, input_path = read_text_input(args.input, args.encoding);
    title = args.title or (input_path.stem if input_path is not None else args.name or "Document");
    css_text = STYLE_PRESETS[args.style];
    if args.css:
        css_text = Path(args.css).expanduser().resolve().read_text(encoding=args.encoding);
    html = build_document(
        markdown_text,
        title,
        css_text,
        fragment=args.fragment,
        line_breaks=args.line_breaks,
        terminal=args.terminal,
        use_ansi=args.ansi,
        table_border_fallback=not args.no_table_border_fallback,
        dark_metadata=(args.style == "dark" and not args.css),
    );
    output_path = resolve_single_output(input_path, options, ".html", args.name);
    write_text_output(html, output_path, options, args.encoding);
    if output_path is not None:
        reporter.success(f"HTML written to: {output_path}");
    return (0);
