# r20 coordinated release

- Aligned with SUM r20 architecture and package versions.

# Changelog

## 0.2.1 - 2026-09-01

- Made SumDoc the canonical owner of the Sum help-document model and Markdown ↔ `.helpdb` conversion.
- Added the pure-Python `sumdoc.helpdb` parser/serializer with the versioned schema used by the Sum help system.
- Added `markdown2helpdb` / `md2helpdb` and `helpdb2markdown` / `helpdb2md` to the multicall registry.
- Added direct `markdown2helpdb` and `helpdb2markdown` console entry points for convenient build/documentation workflows.
- Kept Markdown as the human-editable source of truth; `.helpdb` remains a regenerable JSON cache/interchange format.
- Added round-trip, alias, direct-command, and registry regression tests.

## 0.2.0 - 2026-09-01

- Established the current Sum ecosystem release line for the independent document-conversion toolkit.
- Preserved the complete 0.1.5 feature set: topology-aware semigraphics, ANSI/Braille rendering, PNG/WebP conversion, PDF tools, Markdown/HTML/PDF conversion and OCR-oriented image-to-text tooling.
- Kept `sumdoc` independent of `sumTUI` and `sumIDE`; the version bump aligns packaging/documentation with the current ecosystem without adding a UI dependency.
- Cleaned release metadata and retained the multicall command/alias architecture.

## 0.1.5 - 2026-07-16

- Added the topology-aware `semigraphics` style to `image2text`.
- Added horizontal, vertical, corner, tee, and crossing detection using ASCII, light Unicode, or heavy Unicode line glyphs.
- Added directional arrow detection with `<`, `>`, `^`, `v` or `⯇`, `⯈`, `⯅`, `⯆` output.
- Combined line and arrow recognition with quadrant blocks and `░▒▓█` density shading for DOS/Spectrum-like diagrams.
- Added `--line-style ascii|light|heavy|mixed` and `--arrow-style ascii|unicode`.
- Added mixed-weight box drawing such as `┥`, `┨`, `┝`, `┠`, `┷`, `┸`, `┯`, `┰`, `╂`, and `┿` by estimating stroke thickness independently in each direction.
- Added colored semigraphics to `image2ansi`, so structural glyphs can continue through ANSI-to-HTML pipelines.
- Added ten regression tests for lines, intersections, arrows, heavy and mixed glyphs, and ANSI color; the suite now contains 29 passing tests.

## 0.1.4 - 2026-07-16

- Added `image2text` with the `image2ascii` alias for portable ASCII rendering.
- Added `dos`, `blocks`, and 2x2 `mosaic` styles using DOS/Spectrum-like Unicode block characters.
- Added `image2ansi` with true-color, xterm-256, and 16-color half-block output.
- Added `image2braille`, including optional ANSI color for active Braille cells.
- Added chart-friendly dual-background suppression, source-pixel cropping, contrast, gamma, inversion, and terminal aspect correction.
- Added deterministic `--left-label` and `--bottom-label`; the left label is written one character per row.
- Documented ANSI-to-HTML pipelines through `md2html --ansi`.
- Added six image-rendering and multicall tests; the suite now contains 19 passing tests.

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
