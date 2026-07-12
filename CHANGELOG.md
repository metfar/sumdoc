# Changelog

## 0.1.3 - 2026-07-12

- Integrated the standalone image converter as the `png2webp` and `webp2png` multicall tools.
- Added the `image2webp` and `image2png` aliases.
- Added single-file and non-recursive directory conversion using SumDoc's shared output conventions.
- Added WebP quality control and lossless conversion.
- Added Pillow as the optional `image` dependency group and included it in `all`.
- Added PNG/WebP round-trip and batch-conversion tests.

## 0.1.1 - 2026-07-11

- Added `--line-breaks` / `--hard-wrap` to preserve source newlines while parsing Markdown.
- Added `--terminal` / `--preformatted` for exact line-oriented and whitespace-preserving HTML output.
- Added optional `--ansi` conversion for ANSI SGR styles, including standard, bright, 256-color, and true-color values.
- Made `--ansi` imply terminal mode and strip unsupported terminal-control sequences safely.
- Stripped raw ANSI escape sequences from ordinary Markdown output instead of leaking control characters into HTML.
- Added the same terminal, line-break, and ANSI options to `md2pdf`.
- Added regression tests for line preservation and ANSI conversion.

## 0.1.0 - 2026-07-11

- Created the `sumdoc` multicall executable.
- Added dispatch through `--tool`, symbolic-link invocation names, and subcommands.
- Standardized `-o/--output` and `-d/--output-dir` across all tools.
- Added `pdf2png`, `pdf2txt`, `png2text`, `md2html`, `html2md`, and `md2pdf`.
- Preserved historical aliases such as `png2md` and `md2pdfpipe`.
- Added symbolic-link installation and removal commands.
- Moved diagnostic messages to standard error for clean Unix pipelines.
- Added optional dependency groups, tests, and GPLv2-or-later licensing.
