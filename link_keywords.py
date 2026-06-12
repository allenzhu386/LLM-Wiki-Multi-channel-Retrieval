# -*-coding: utf-8 -*-
"""
将 source/three_kingdoms.txt 中的实体/概念关键词替换为 Obsidian 双向链接 [[...]]。
"""

from __future__ import annotations

import re
import shutil
from pathlib import Path

from build_entities import (
    MIN_FREQ_ENTITY,
    SOURCE,
    _ENTITY_LIST,
    discover_places,
    load_text,
    top_kind,
)

# 易误链的短词，不参与替换
LINK_SKIP_TERMS = frozenset(
    {
        "邺",  # 单字，误链过多
        "三顾",
        "茅庐",
        "七擒",
        "画戟",
        "桃园",  # 章回题「宴桃园…」等，宜用完整词「桃园结义」
        "三结义",
    }
)

# 带上下文约束的匹配（正则片段，须能接在 re.compile 的 alternation 中）
TERM_PATTERN_OVERRIDES: dict[str, str] = {
    "江东": r"(?<!长)江东",  # 避免「长江东逝水」误链
}

BACKUP_SUFFIX = ".plain.bak"


def build_term_map(extra_places: list[str] | None = None) -> dict[str, tuple[str, str]]:
    """
    检索词 -> (规范名, kind)。
    同一检索词只保留一条（先出现的定义优先）。
    """
    term_map: dict[str, tuple[str, str]] = {}
    for name, subtype, keywords in _ENTITY_LIST:
        kind = top_kind(subtype)
        for kw in keywords:
            if not kw or kw in LINK_SKIP_TERMS or len(kw) < 2:
                continue
            if kw not in term_map:
                term_map[kw] = (name, kind)
    if extra_places:
        for place in extra_places:
            if place not in term_map and len(place) >= 2:
                term_map[place] = (place, "entity")
    return term_map


def sorted_terms(term_map: dict[str, tuple[str, str]]) -> list[str]:
    """长词优先，避免短词截断长词。"""
    return sorted(term_map.keys(), key=len, reverse=True)


def make_wikilink(term: str, canonical: str) -> str:
    if term == canonical:
        return f"[[{canonical}]]"
    return f"[[{canonical}|{term}]]"


def term_to_pattern(term: str) -> str:
    return TERM_PATTERN_OVERRIDES.get(term, re.escape(term))


def linkify_plain(segment: str, terms: list[str], term_map: dict[str, tuple[str, str]]) -> str:
    if not segment or not terms:
        return segment
    pattern = re.compile("|".join(term_to_pattern(t) for t in terms))
    parts: list[str] = []
    last = 0
    for m in pattern.finditer(segment):
        parts.append(segment[last : m.start()])
        term = m.group()
        canonical, _ = term_map[term]
        parts.append(make_wikilink(term, canonical))
        last = m.end()
    parts.append(segment[last:])
    return "".join(parts)


def linkify_segment(segment: str, terms: list[str], term_map: dict[str, tuple[str, str]]) -> str:
    """跳过已是 [[wikilink]] 的片段。"""
    chunks = re.split(r"(\[\[[^\]]*\]\])", segment)
    out: list[str] = []
    for chunk in chunks:
        if chunk.startswith("[[") and chunk.endswith("]]"):
            out.append(chunk)
        else:
            out.append(linkify_plain(chunk, terms, term_map))
    return "".join(out)


def linkify_line(line: str, terms: list[str], term_map: dict[str, tuple[str, str]]) -> str:
    return linkify_segment(line, terms, term_map)


def linkify_file_content(content: str, terms: list[str], term_map: dict[str, tuple[str, str]]) -> str:
    lines = content.splitlines(keepends=True)
    return "".join(linkify_line(line, terms, term_map) for line in lines)


def strip_section_markers(content: str) -> str:
    return re.sub(r"^分节阅读\s*\d+\s*$", "", content, flags=re.MULTILINE)


def main() -> None:
    if not SOURCE.exists():
        raise FileNotFoundError(SOURCE)

    collapsed = load_text()
    known = {name for name, _, _ in _ENTITY_LIST}
    extra_places = [p for p, _ in discover_places(collapsed, known)]
    term_map = build_term_map(extra_places)
    terms = sorted_terms(term_map)

    backup = SOURCE.with_suffix(SOURCE.suffix + BACKUP_SUFFIX)
    if backup.exists():
        raw = backup.read_text(encoding="utf-8")
        print(f"自备份恢复后重新链化 -> {backup}")
    else:
        raw = SOURCE.read_text(encoding="utf-8")
        shutil.copy2(SOURCE, backup)
        print(f"已备份原文 -> {backup}")

    linked = strip_section_markers(raw)
    linked = linkify_file_content(linked, terms, term_map)
    SOURCE.write_text(linked, encoding="utf-8")

    # 统计链接次数
    link_count = len(re.findall(r"\[\[[^\]]+\]\]", linked))
    print(f"已写入双向链接 -> {SOURCE}")
    print(f"检索词 {len(terms)} 个，生成 wikilink {link_count} 处")


if __name__ == "__main__":
    main()
