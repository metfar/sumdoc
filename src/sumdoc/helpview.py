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

"""Adapters that expose ordinary Markdown documents through SUM's HelpBrowser.""";

from dataclasses import dataclass;
from pathlib import Path;
import re;

from sumdoc.helpdb import HelpCorpus;


_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$");
_INLINE_MARKUP_RE = re.compile(r"[`*_~]+|\[([^\]]+)\]\([^)]*\)");
_EXCLUDED_DOC_DIRS = {".git", ".hg", ".svn", ".pytest_cache", "__pycache__", "build", "dist", ".venv", "venv", "node_modules"};


@dataclass(frozen=True)
class MarkdownHelpTopic:
    """One navigable section extracted from an ordinary Markdown document.""";

    name: str;
    category: str;
    summary: str;
    body: str;
    aliases: tuple = tuple();
    see_also: tuple = tuple();

    def markdown(self) -> str:
        body = str(self.body or "").strip();
        if body:
            return (f"# {self.name}\n\n{body}");
        return (f"# {self.name}");


class MarkdownHelpCorpus:
    """HelpBrowser-compatible corpus generated from ordinary Markdown files.""";

    def __init__(self, title: str, topics=None, intro: str = ""):
        self.title = str(title or "Documentation");
        self.intro = str(intro or "").strip();
        self.topics = tuple(topics or ());
        self._topic_map = {topic.name.casefold(): topic for topic in self.topics};

    @staticmethod
    def _summary(text: str) -> str:
        in_fence = False;
        paragraph = [];
        for line in str(text or "").splitlines():
            stripped = line.strip();
            if stripped.startswith("```") or stripped.startswith("~~~"):
                in_fence = not in_fence;
                continue;
            if in_fence:
                continue;
            if stripped.startswith("#"):
                continue;
            if not stripped:
                if paragraph:
                    break;
                continue;
            if stripped.startswith(("- ", "* ", "+ ")):
                stripped = stripped[2:].strip();
            paragraph.append(stripped);
        value = " ".join(paragraph).strip();
        value = _INLINE_MARKUP_RE.sub(lambda match: match.group(1) or "", value);
        return (value[:157] + "...") if len(value) > 160 else value;

    @staticmethod
    def _heading_events(text: str) -> list[tuple[int, int, str]]:
        events = [];
        in_fence = False;
        for index, line in enumerate(str(text).splitlines()):
            stripped = line.strip();
            if stripped.startswith("```") or stripped.startswith("~~~"):
                in_fence = not in_fence;
                continue;
            if in_fence:
                continue;
            match = _HEADING_RE.match(line);
            if match is not None:
                events.append((index, len(match.group(1)), match.group(2).strip()));
        return (events);

    @classmethod
    def from_markdown(cls, text: str, title: str | None = None, category: str = "Document"):
        source = str(text or "").replace("\r\n", "\n").replace("\r", "\n");
        lines = source.split("\n");
        events = cls._heading_events(source);
        document_title = str(title or "").strip();
        h1 = next((event for event in events if event[1] == 1), None);
        if not document_title:
            document_title = h1[2] if h1 is not None else "Documentation";
        first_section_line = min((line for line, level, _name in events if level >= 2), default=len(lines));
        intro_start = (h1[0] + 1) if h1 is not None else 0;
        intro = "\n".join(lines[intro_start:first_section_line]).strip();
        section_events = [event for event in events if event[1] >= 2];
        if not section_events:
            body = source.strip();
            topic_name = document_title;
            topic = MarkdownHelpTopic(topic_name, category, cls._summary(body), body);
            return cls(document_title, [topic], intro="");

        topics = [];
        names_seen = {};
        parent_h2 = None;
        for position, event in enumerate(section_events):
            line_index, level, heading = event;
            if level == 2:
                parent_h2 = heading;
            end_index = len(lines);
            for later in section_events[position + 1:]:
                if later[1] <= level:
                    end_index = later[0];
                    break;
            body = "\n".join(lines[line_index + 1:end_index]).strip();
            topic_category = category if level == 2 else (parent_h2 or category);
            base_name = heading;
            count = names_seen.get(base_name.casefold(), 0) + 1;
            names_seen[base_name.casefold()] = count;
            if count == 1:
                topic_name = base_name;
            elif parent_h2:
                topic_name = f"{parent_h2} — {base_name}";
            else:
                topic_name = f"{base_name} ({count})";
            topics.append(MarkdownHelpTopic(
                topic_name,
                topic_category,
                cls._summary(body),
                body,
            ));
        return cls(document_title, topics, intro=intro);

    @classmethod
    def from_files(cls, paths: list[Path], root: Path | None = None, title: str | None = None):
        topics = [];
        intro_parts = [];
        used_names = set();
        root_path = root.resolve() if root is not None else None;
        for path in sorted(paths, key=lambda item: str(item).casefold()):
            resolved = path.resolve();
            relative = resolved.relative_to(root_path) if root_path is not None else Path(resolved.name);
            label = str(relative.with_suffix(""));
            corpus = cls.from_markdown(resolved.read_text(encoding="utf-8"), title=resolved.stem, category=label);
            if corpus.intro:
                intro_parts.append(f"**{relative}** — {cls._summary(corpus.intro)}");
            for topic in corpus.topics:
                name = topic.name;
                if name.casefold() in used_names:
                    name = f"{label} — {name}";
                used_names.add(name.casefold());
                topics.append(MarkdownHelpTopic(name, label, topic.summary, topic.body));
        corpus_title = str(title or (root_path.name if root_path is not None else "Documentation"));
        return cls(corpus_title, topics, intro="\n\n".join(intro_parts));

    def find_topic(self, name):
        raw = str(name or "").strip().casefold();
        if raw in self._topic_map:
            return (self._topic_map[raw]);
        matches = [topic for key, topic in self._topic_map.items() if key.startswith(raw)] if raw else [];
        return matches[0] if len(matches) == 1 else None;

    def index_markdown(self):
        lines = [f"# {self.title}", ""];
        if self.intro:
            lines.extend([self.intro, ""]);
        categories = {};
        for topic in self.topics:
            categories.setdefault(topic.category or "Document", []).append(topic);
        for category, topics in categories.items():
            lines.extend([f"## {category}", ""]);
            for topic in topics:
                summary = f" — {topic.summary}" if topic.summary else "";
                lines.append(f"- **{topic.name}**{summary}");
            lines.append("");
        return ("\n".join(lines).rstrip());


def load_help_source(path_text: str, title: str | None = None):
    """Load one Markdown/helpdb file or recursively expose a Markdown directory.""";
    path = Path(path_text).expanduser().resolve();
    if not path.exists():
        raise FileNotFoundError(f"Help source does not exist: '{path}'.");
    if path.is_dir():
        markdown_files = [];
        for pattern in ("*.md", "*.markdown", "*.mdown"):
            for item in path.rglob(pattern):
                if not item.is_file():
                    continue;
                relative = item.relative_to(path);
                directory_parts = relative.parts[:-1];
                if any(part in _EXCLUDED_DOC_DIRS or part.startswith(".") for part in directory_parts):
                    continue;
                markdown_files.append(item);
        unique_files = sorted(set(markdown_files), key=lambda item: str(item).casefold());
        if not unique_files:
            raise ValueError(f"No Markdown documents found under '{path}'.");
        return (MarkdownHelpCorpus.from_files(unique_files, root=path, title=title or path.name));
    suffix = path.suffix.casefold();
    source = path.read_text(encoding="utf-8");
    if suffix == ".helpdb":
        return (HelpCorpus.from_helpdb(source));
    if suffix in (".md", ".markdown", ".mdown", ".txt"):
        return (MarkdownHelpCorpus.from_markdown(source, title=title, category=path.stem));
    raise ValueError("Help source must be Markdown, .helpdb, a text file, or a directory containing Markdown files.");
