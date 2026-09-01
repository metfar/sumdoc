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
"""Canonical Markdown/helpdb document model for Sum ecosystem help.

Markdown is the human-editable source format. ``.helpdb`` is a versioned JSON
cache/interchange format generated from Markdown. The conversion model lives in
SumDoc so UI packages only need to consume/render the resulting data.
""";
from dataclasses import dataclass;
import json;
from pathlib import Path;
import re;


@dataclass(frozen=True)
class HelpTopic:
    name: str;
    category: str;
    summary: str;
    syntax: tuple;
    example: str;
    notes: tuple = tuple();
    see_also: tuple = tuple();
    aliases: tuple = tuple();
    language: str = "text";

    def markdown(self):
        lines = ["# {}".format(self.name), "", self.summary, "", "## Syntax", "", "```{}".format(self.language)];
        lines.extend(self.syntax);
        lines.append("```");
        if self.notes:
            lines.extend(["", "## Notes", ""]);
            lines.extend(["- {}".format(item) for item in self.notes]);
        lines.extend(["", "## Functional example", "", "```{}".format(self.language)]);
        lines.extend(self.example.rstrip().splitlines());
        lines.append("```");
        if self.see_also:
            lines.extend(["", "## See also", "", ", ".join(self.see_also)]);
        if self.aliases:
            lines.extend(["", "## Aliases", "", ", ".join(self.aliases)]);
        return "\n".join(lines).rstrip();


class HelpCorpus:
    def __init__(self, title, topics=None, intro=""):
        self.title = str(title or "Help");
        self.intro = str(intro or "").strip();
        self.topics = tuple(topics or ());
        self._topic_map = {topic.name.upper(): topic for topic in self.topics};
        self._aliases = {};
        for topic in self.topics:
            for alias in topic.aliases:
                self._aliases[str(alias).strip().upper()] = topic.name.upper();

    def topic_names(self):
        return [topic.name for topic in sorted(self.topics, key=lambda item: (item.category.casefold(), item.name.casefold()))];

    def find_topic(self, name):
        raw = str(name or "").strip().upper();
        raw = self._aliases.get(raw, raw);
        if raw in self._topic_map:
            return self._topic_map[raw];
        matches = [topic for key, topic in self._topic_map.items() if key.startswith(raw)] if raw else [];
        return matches[0] if len(matches) == 1 else None;

    def index_markdown(self):
        lines = ["# {}".format(self.title), ""];
        if self.intro:
            lines.extend([self.intro, ""]);
        categories = {};
        for topic in sorted(self.topics, key=lambda item: (item.category.casefold(), item.name.casefold())):
            categories.setdefault(topic.category, []).append(topic);
        for category, topics in categories.items():
            lines.extend(["## {}".format(category), ""]);
            for topic in topics:
                lines.append("- **{}** — {}".format(topic.name, topic.summary));
            lines.append("");
        return "\n".join(lines).rstrip();

    def to_dict(self):
        return {
            "schema_version": 1,
            "title": self.title,
            "intro": self.intro,
            "topics": [
                {
                    "name": topic.name,
                    "category": topic.category,
                    "summary": topic.summary,
                    "syntax": list(topic.syntax),
                    "example": topic.example,
                    "notes": list(topic.notes),
                    "see_also": list(topic.see_also),
                    "aliases": list(topic.aliases),
                    "language": topic.language,
                }
                for topic in self.topics
            ],
        };

    def to_helpdb(self, indent=2):
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=int(indent)) + "\n";

    def to_markdown(self):
        lines = ["# {}".format(self.title), ""];
        if self.intro:
            lines.extend([self.intro, ""]);
        current_category = None;
        for topic in self.topics:
            if topic.category != current_category:
                current_category = topic.category;
                lines.extend(["## {}".format(current_category), ""]);
            lines.extend(["### {}".format(topic.name), "", topic.summary, "", "#### Syntax", "", "```{}".format(topic.language)]);
            lines.extend(topic.syntax);
            lines.extend(["```", ""]);
            if topic.notes:
                lines.extend(["#### Notes", ""]);
                lines.extend(["- {}".format(item) for item in topic.notes]);
                lines.append("");
            lines.extend(["#### Functional example", "", "```{}".format(topic.language)]);
            lines.extend(topic.example.rstrip().splitlines());
            lines.extend(["```", ""]);
            if topic.see_also:
                lines.extend(["#### See also", "", ", ".join(topic.see_also), ""]);
            if topic.aliases:
                lines.extend(["#### Aliases", "", ", ".join(topic.aliases), ""]);
        return "\n".join(lines).rstrip() + "\n";

    @classmethod
    def from_dict(cls, data):
        if int(data.get("schema_version", 0)) != 1:
            raise ValueError("unsupported helpdb schema version");
        topics = [];
        for item in data.get("topics", []):
            topics.append(HelpTopic(
                str(item.get("name", "")),
                str(item.get("category", "General")),
                str(item.get("summary", "")),
                tuple(str(value) for value in item.get("syntax", [])),
                str(item.get("example", "")),
                tuple(str(value) for value in item.get("notes", [])),
                tuple(str(value) for value in item.get("see_also", [])),
                tuple(str(value) for value in item.get("aliases", [])),
                str(item.get("language", "text")),
            ));
        return cls(data.get("title", "Help"), topics, intro=data.get("intro", ""));

    @classmethod
    def from_helpdb(cls, text):
        return cls.from_dict(json.loads(str(text)));

    @classmethod
    def from_markdown(cls, text):
        source = str(text).replace("\r\n", "\n").replace("\r", "\n");
        lines = source.split("\n");
        title = "Help";
        intro_lines = [];
        topics = [];
        category = "General";
        topic_name = None;
        topic_summary = [];
        section = "summary";
        section_lines = [];
        sections = {};
        language = "text";
        in_fence = False;
        fence_language = "";

        def flush_section():
            nonlocal section_lines;
            sections[section] = list(section_lines);
            section_lines = [];

        def clean_paragraph(values):
            return " ".join(line.strip() for line in values if line.strip()).strip();

        def clean_list(values):
            result = [];
            for line in values:
                value = line.strip();
                if value.startswith("- ") or value.startswith("* "):
                    value = value[2:].strip();
                if value:
                    result.extend([item.strip() for item in value.split(",") if item.strip()]);
            return tuple(result);

        def clean_code(values):
            result = [];
            inside = False;
            for line in values:
                if line.strip().startswith("```"):
                    inside = not inside;
                    continue;
                if inside:
                    result.append(line);
            return result;

        def flush_topic():
            nonlocal topic_name, topic_summary, sections, section, section_lines, language;
            if topic_name is None:
                return;
            flush_section();
            summary = clean_paragraph(topic_summary);
            syntax_values = tuple(clean_code(sections.get("syntax", [])));
            example_values = clean_code(sections.get("functional example", []));
            notes_values = clean_list(sections.get("notes", []));
            see_values = clean_list(sections.get("see also", []));
            alias_values = clean_list(sections.get("aliases", []));
            topics.append(HelpTopic(topic_name, category, summary, syntax_values, "\n".join(example_values).rstrip(), notes_values, see_values, alias_values, language));
            topic_name = None;
            topic_summary = [];
            sections = {};
            section = "summary";
            section_lines = [];
            language = "text";

        seen_title = False;
        for line in lines:
            if line.startswith("# ") and not seen_title and topic_name is None:
                title = line[2:].strip() or "Help";
                seen_title = True;
                continue;
            if line.startswith("## ") and not line.startswith("### "):
                flush_topic();
                category = line[3:].strip() or "General";
                continue;
            if line.startswith("### ") and not line.startswith("#### "):
                flush_topic();
                topic_name = line[4:].strip();
                topic_summary = [];
                section = "summary";
                section_lines = [];
                sections = {};
                language = "text";
                continue;
            if topic_name is None:
                if seen_title and line.strip():
                    intro_lines.append(line.strip());
                continue;
            if line.startswith("#### "):
                flush_section();
                section = line[5:].strip().casefold();
                continue;
            if line.strip().startswith("```"):
                marker = line.strip()[3:].strip();
                if marker and section in ("syntax", "functional example") and language == "text":
                    language = marker;
                in_fence = not in_fence;
                section_lines.append(line);
                continue;
            if section == "summary":
                topic_summary.append(line);
            else:
                section_lines.append(line);
        flush_topic();
        return cls(title, topics, intro=" ".join(intro_lines).strip());


def load_help_markdown(path):
    return HelpCorpus.from_markdown(Path(path).read_text(encoding="utf-8"));


def load_helpdb(path):
    return HelpCorpus.from_helpdb(Path(path).read_text(encoding="utf-8"));
