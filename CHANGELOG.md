## 0.3.0 - 2026-10-03

- Promote WeasyPrint (`WeasyPrint>=60`) to a normal SumDoc dependency because PDF generation is now part of the baseline document toolchain rather than an optional Markdown extra.
- Add `font2fnt` with `ttf2fnt` / `otf2fnt` aliases to rasterize vector fonts into the documented SUM-FNT v1 bitmap format.
- Add `sumdoc banner` with `sumbanner` / `fontbanner` subcommand aliases for compact bitmap-font banners that no longer require the original vector font at render time.
- Keep source TTF/OTF files external: SumDoc does not bundle personal or third-party fonts and only converts fonts explicitly supplied by the user.
- Establish 4x8 / 256-code Latin-1 conversion as the initial practical bitmap-font profile, while leaving the SUM font/charset architecture open for the larger shared SUM charset in a later core milestone.
- Close the 0.2.x integration cycle (help documents, clipboard utilities, rich Markdown rendering, installed multicall aliases, and secure `text2image`) and begin the 0.3 document-production milestone.

## 0.2.12 - 2026-10-03

- Integrated the historical `writeOnImage` utility as the canonical `text2image` SumDoc tool, preserving `writeOnImage`/`writeonimage` aliases.
- Added stdin and clipboard input so passwords and other secrets do not need to appear in shell history or process arguments.
- Preserved the original blue/yellow color defaults while removing the hard-coded personal font path; `--font`, `--size`, foreground/background colors, padding, and `--show` are available.
- Output files default to mode 0600 for safer handling of generated password images; `--public` opts back into normal umask-based permissions.
- Added compatibility for the historical `--out=` option and regression tests.
- The test suite now contains 59 passing tests.

## 0.2.10 - 2026-10-03

- Integrated the historical `lessrich` Markdown console renderer as the `md2rich` SumDoc tool.
- Added `lessrich` and `markdown2rich` aliases so the original command name remains available through SumDoc multicall links.
- Added right/center/left Markdown table alignment, escaped-pipe handling, multiple input files, `--width`, and `--no-color`.
- Added the optional `rich` dependency group and included it in `all`.

## 0.2.9 - 2026-09-18

- Paste Special image-to-text now produces color-independent ASCII art using a luminance character ramp instead of Unicode block cells whose shape depended on foreground/background colors.
- The optional OCR overlay remains available on top of the ASCII representation.

# SumDoc changelog

## 0.2.8 - 2026-09-18

- Bound clipboard subprocess reads so X11 owners cannot stall context-menu creation indefinitely.
- Build Paste Special choices from advertised MIME/TARGET types without eagerly reading HTML, RTF, URI or image payloads.

## 0.2.7 - 2026-09-17

- Added the `sumdoc help SOURCE` interactive document browser.
- `sumdoc help` now opens ordinary Markdown files, compiled `.helpdb` files, and directories of Markdown documents through the reusable `sumTUI.HelpBrowser`.
- Ordinary Markdown headings become navigable/searchable topics while retaining their original Markdown body.
- Directory browsing recursively groups Markdown documents and their sections into one corpus.
- Added `--topic`, `--query`, `--title`, `--theme`, and `--backend tui|gui` help-browser options.
- Kept `help` as a `sumdoc` subcommand only, avoiding installation of a generic `help` executable/symlink.
- Added an optional `help` dependency group for `sumTUI>=0.8.0a26`; the `all` extra includes it.

## 0.2.5 - 2026-09-17

- Integrated the historical standalone `md2html` dark presentation as SumDoc's default HTML style.
- Added `--style dark|light` / `--theme` while retaining `--css` for arbitrary embedded stylesheets.
- Preserved the classic `border="1"` table fallback for LMS/editor compatibility, with `--no-table-border-fallback` to disable it.
- Kept `md2pdf` on the light print-oriented stylesheet so HTML styling does not make PDFs dark by default.
- Moved the reusable parts of `clipinfo`, `clipbesttype`, `clip2png`, and `clip2rtf` into SumDoc clipboard services and multicall tools.
- Added environment-aware clipboard backend selection: Wayland is used only with a live Wayland socket; otherwise X11 uses `xclip`, with `xsel` as a plain-text fallback.
- Added `clip2md`, including HTML → Markdown and RTF → Markdown conversion; RTF prefers `pandoc`, then `unrtf`, then a plain-text fallback.

## 0.2.4 - 2026-09-17

- Fixed Markdown help parsing so commas inside one `Notes` bullet are preserved instead of being mistaken for list separators.
- Kept comma splitting for `See also` and `Aliases`, where comma-separated entries are intentional.
- Aligned SumDoc with the reusable navigable-help work used by the SUM r20 shell line.

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

