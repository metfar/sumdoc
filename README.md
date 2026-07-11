# SumDoc

SumDoc is a collection of small document-conversion tools joined into one Unix-style multicall program.

A single executable can behave as `pdf2png`, `pdf2txt`, `png2text`, `md2html`, `html2md`, or `md2pdf`, depending on the name used to invoke it. The design follows the same practical idea used by multicall programs such as BusyBox: one maintained core, many simple command names.

No useful program should disappear on a beach of scattered grains. SumDoc ties those grains together so that the tools can be installed, documented, tested, shared, and improved as one project.

## License

SumDoc is free software released under the GNU General Public License, version 2 or, at your option, any later version. See [LICENSE](LICENSE).

## Tools

| Tool | Purpose | Aliases |
|---|---|---|
| `pdf2png` | Render PDF pages as 300 or 600 DPI PNG files. | — |
| `pdf2txt` | Extract text, HTML, XML, or tagged data from PDF files. | `pdf2text` |
| `png2text` | Extract Markdown text, code, or tables from images using OCR. | `png2md`, `image2md` |
| `md2html` | Convert Markdown or preformatted terminal text to HTML. | `markdown2html` |
| `html2md` | Convert HTML to Markdown. | `html2markdown` |
| `md2pdf` | Convert Markdown or preformatted terminal text to PDF. | `md2pdfpipe`, `markdown2pdf` |

## Installation

Install the complete suite from the project directory:

```sh
python3 -m pip install --user '.[all]'
```

Install only the feature groups that are needed:

```sh
python3 -m pip install --user '.[pdf]'
python3 -m pip install --user '.[markdown]'
python3 -m pip install --user '.[ocr]'
```

The OCR tools also require a working Tesseract executable and the desired language data on the operating system.

## Multicall symbolic links

After installation, create the command links in a directory included in `PATH`:

```sh
sumdoc --install-links "$HOME/.local/bin"
```

This creates links such as:

```text
pdf2png   -> sumdoc
pdf2txt   -> sumdoc
png2text  -> sumdoc
md2html   -> sumdoc
html2md   -> sumdoc
md2pdf    -> sumdoc
```

Remove links created by the same executable:

```sh
sumdoc --remove-links "$HOME/.local/bin"
```

Use `--force` when an existing non-matching link should be replaced:

```sh
sumdoc --force --install-links "$HOME/.local/bin"
```

## Equivalent invocation forms

All three forms select the same tool:

```sh
pdf2png document.pdf --dpi 600
sumdoc --tool pdf2png document.pdf --dpi 600
sumdoc pdf2png document.pdf --dpi 600
```

The explicit tool selector can appear anywhere outside `--`:

```sh
sumdoc document.pdf --dpi 600 --tool pdf2png
```

Selection priority is:

1. `-t` or `--tool`;
2. the name used to invoke the executable through a symbolic link;
3. the first command argument when it names a registered tool.

## Common output options

Every linked tool accepts the same output convention:

```text
-o, --output FILE       Use one exact output filename.
-d, --output-dir DIR    Generate output filenames inside a directory.
```

The two options are mutually exclusive.

For a single-output conversion:

```sh
md2html README.md -o README.html
html2md page.html --output-dir markdown
```

For a multi-output conversion:

```sh
pdf2png book.pdf --dpi 600 -d pages
```

`pdf2png` accepts `--output` only when exactly one page is selected:

```sh
pdf2png book.pdf --pages 4 -o page-4.png
```

When a text conversion has neither `--output` nor `--output-dir`, its result is written to standard output. Diagnostics are written to standard error, keeping pipelines clean:

```sh
html2md page.html | md2pdf -o page.pdf
pdf2txt report.pdf | md2html -o report.html
```

When standard input is combined with `--output-dir`, provide a generated base name:

```sh
cat page.html | html2md -d output --name page
```

## Examples

Render selected PDF pages:

```sh
pdf2png document.pdf --dpi 300 --pages 1,3-5 -d pages
```

Extract text from a PDF:

```sh
pdf2txt document.pdf -o document.txt
```

Extract several PDFs into one directory:

```sh
pdf2txt one.pdf two.pdf --output-dir text
```

Run image OCR and produce Markdown:

```sh
png2text terminal.png -o terminal.md
```

Convert Markdown and HTML in either direction:

```sh
md2html notes.md -o notes.html
html2md notes.html -o notes.md
```

### Line breaks and terminal output

Markdown treats a single newline inside a paragraph as a soft line break. Browsers normally display that break as ordinary whitespace. Preserve each source newline while retaining Markdown parsing with:

```sh
printf 'one\ntwo\n' | md2html --line-breaks > lines.html
```

For command output, logs, source listings, or other text whose exact whitespace matters, use terminal mode:

```sh
ls --color=always | md2html --terminal > listing.html
```

Terminal mode preserves newlines, spaces, and tabs inside a `<pre>` block. ANSI escape sequences are removed unless color conversion is requested:

```sh
ls --color=always | md2html --ansi > colored-listing.html
```

`--ansi` converts ANSI SGR foreground colors, background colors, bold, faint, italic, underline, inverse, hidden, strike-through, overline, 256-color values, and true-color values into safe HTML. It implies `--terminal`. Other terminal-control sequences are removed; SumDoc does not attempt to emulate cursor movement or an interactive terminal.

The same options are available in `md2pdf`:

```sh
dmesg --color=always | md2pdf --ansi -o dmesg.pdf
```

Convert Markdown from standard input to PDF on standard output:

```sh
cat notes.md | md2pdf > notes.pdf
```

## Development

Run the test suite:

```sh
python3 -m pytest
```

Build source and wheel distributions:

```sh
python3 -m build
```

## Project principle

SumDoc is intentionally made from small operations that can be understood, combined, and reused. A child, student, teacher, administrator, or programmer should be able to take one command, solve one real problem, and then join it with another command when the problem grows.

A tool becomes more valuable when other people can study it, modify it, and pass it on.

<p align=center><b>- oOo -</b></p>
