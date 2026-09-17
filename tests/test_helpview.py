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

from pathlib import Path;

from sumdoc.common import GlobalOptions;
from sumdoc.helpview import MarkdownHelpCorpus, load_help_source;


def test_generic_markdown_becomes_navigable_topics():
    source = """# Demo Project

Intro paragraph.

## Installation

Install **this** package.

### Linux

Run `pip install demo`.

## Usage

Use it carefully.
""";
    corpus = MarkdownHelpCorpus.from_markdown(source);
    assert corpus.title == "Demo Project";
    assert [topic.name for topic in corpus.topics] == ["Installation", "Linux", "Usage"];
    assert corpus.find_topic("Linux").category == "Installation";
    assert "Run `pip install demo`." in corpus.find_topic("Linux").markdown();
    assert "Installation" in corpus.index_markdown();


def test_headings_inside_code_fences_are_not_topics():
    source = """# Demo

## Real

```markdown
## Not a topic
```
""";
    corpus = MarkdownHelpCorpus.from_markdown(source);
    assert [topic.name for topic in corpus.topics] == ["Real"];


def test_markdown_without_sections_is_one_topic():
    corpus = MarkdownHelpCorpus.from_markdown("Just one paragraph.", title="Note");
    assert corpus.title == "Note";
    assert len(corpus.topics) == 1;
    assert corpus.topics[0].name == "Note";
    assert "Just one paragraph." in corpus.topics[0].markdown();


def test_directory_help_loads_markdown_recursively(tmp_path):
    (tmp_path / "README.md").write_text("# Root\n\n## Overview\n\nRoot text.\n", encoding="utf-8");
    nested = tmp_path / "guides";
    nested.mkdir();
    (nested / "install.md").write_text("# Install\n\n## Linux\n\nLinux text.\n", encoding="utf-8");
    hidden = tmp_path / ".pytest_cache";
    hidden.mkdir();
    (hidden / "README.md").write_text("# Hidden\n\n## Ignore\n\nNo.\n", encoding="utf-8");
    corpus = load_help_source(str(tmp_path));
    names = [topic.name for topic in corpus.topics];
    assert "Overview" in names;
    assert "Linux" in names;
    assert "Ignore" not in names;
    linux = corpus.find_topic("Linux");
    assert linux.category == "guides/install";


def test_helpdb_can_be_opened_directly(tmp_path):
    from sumdoc.helpdb import HelpCorpus;
    source = """# Language

## Commands

### PRINT

Print text.

#### Syntax

```basic
PRINT value
```

#### Functional example

```basic
PRINT 1
```
""";
    database = tmp_path / "language.helpdb";
    database.write_text(HelpCorpus.from_markdown(source).to_helpdb(), encoding="utf-8");
    corpus = load_help_source(str(database));
    assert corpus.title == "Language";
    assert corpus.find_topic("PRINT") is not None;


def test_help_main_loads_document_before_starting_browser(tmp_path, monkeypatch):
    from sumdoc.tools import helpview;
    source = tmp_path / "README.md";
    source.write_text("# Project\n\n## Usage\n\nHello.\n", encoding="utf-8");
    captured = {};

    def fake_run(corpus, args):
        captured["title"] = corpus.title;
        captured["topic"] = args.topic;
        return 0;

    monkeypatch.setattr(helpview, "_run_browser", fake_run);
    result = helpview.help_main([str(source), "--topic", "Usage"], GlobalOptions());
    assert result == 0;
    assert captured == {"title": "Project", "topic": "Usage"};
