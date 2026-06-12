# -*-coding: utf-8 -*-
"""
从原文按回目切分，在 wiki/index 生成摘要与知识库总索引。
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from build_entities import _ENTITY_LIST

ROOT = Path(__file__).resolve().parent
PLAIN = ROOT / "source" / "three_kingdoms.txt.plain.bak"
INDEX_DIR = ROOT / "wiki" / "index"
CHAPTER_DIR = INDEX_DIR / "chapters"
PART_DIR = INDEX_DIR / "parts"

CHAPTER_HEAD = re.compile(
    r"正文\s*(第[一二三四五六七八九十百零]+回)\s+([^\n]+)"
)
SENT_SPLIT = re.compile(r"(?<=[。！？；])")
SKIP_LINE = re.compile(
    r"^(分节阅读|——|　　|滚滚长|话说天下大势|毕竟.*且听下文分解)"
)

# 四部划分（120 回）
PARTS = [
    (1, 30, "群雄崛起", "黄巾之乱、董卓之乱、诸侯讨董、吕布覆灭、曹操迎天子"),
    (31, 60, "魏吴争锋", "官渡赤壁、刘备入蜀、汉中争夺、关羽北伐与败亡"),
    (61, 90, "三国鼎立", "夷陵、南蛮、北伐、东吴继统、诸葛亮卒"),
    (91, 120, "三国归晋", "姜维北伐、司马氏专权、魏灭蜀、晋灭吴"),
]

# (检索词, 规范名)，长词优先
TERM_TO_CANONICAL: list[tuple[str, str]] = []
_seen_term: set[str] = set()
for name, _, kws in _ENTITY_LIST:
    for term in [name] + kws:
        if term not in _seen_term:
            _seen_term.add(term)
            TERM_TO_CANONICAL.append((term, name))
TERM_TO_CANONICAL.sort(key=lambda x: len(x[0]), reverse=True)


@dataclass
class Chapter:
    ordinal: int
    label: str
    title: str
    body: str
    char_count: int
    entities: list[tuple[str, int]]
    summary: str
    opening: str


def cn_segment_to_int(seg: str) -> int:
    digit = {"零": 0, "一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}
    if not seg:
        return 0
    if seg == "十":
        return 10
    if len(seg) == 2 and seg[0] == "十":
        return 10 + digit.get(seg[1], 0)
    if len(seg) == 2 and seg[1] == "十":
        return digit.get(seg[0], 0) * 10
    if "百" in seg:
        parts = seg.split("百", 1)
        h = digit.get(parts[0], 1) if parts[0] else 1
        rest = parts[1] if len(parts) > 1 else ""
        if not rest:
            return h * 100
        if rest == "十":
            return h * 100 + 10
        if rest.startswith("十"):
            return h * 100 + 10 + digit.get(rest[1], 0)
        if "十" in rest:
            a, b = rest.split("十", 1)
            return h * 100 + digit.get(a, 0) * 10 + digit.get(b, 0)
        return h * 100 + digit.get(rest, 0)
    if "十" in seg:
        a, b = seg.split("十", 1)
        return digit.get(a, 0) * 10 + digit.get(b, 0)
    return digit.get(seg, 0)


def chapter_label_to_int(label: str) -> int:
    m = re.match(r"第(.+)回", label)
    if not m:
        return 0
    return cn_segment_to_int(m.group(1))


def split_chapters(raw: str) -> list[tuple[str, str, str]]:
    raw = re.sub(r"分节阅读\s*\d+\s*\n", "\n", raw)
    matches = list(CHAPTER_HEAD.finditer(raw))
    out: list[tuple[str, str, str]] = []
    for i, m in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(raw)
        body = raw[m.end() : end].strip()
        out.append((m.group(1), m.group(2).strip(), body))
    return out


def count_entities(body: str, top_n: int = 10) -> list[tuple[str, int]]:
    plain = re.sub(r"\s+", "", body)
    c: Counter[str] = Counter()
    used = [False] * len(plain)
    for term, canonical in TERM_TO_CANONICAL:
        start = 0
        while True:
            idx = plain.find(term, start)
            if idx == -1:
                break
            if not any(used[idx : idx + len(term)]):
                for j in range(idx, idx + len(term)):
                    used[j] = True
                c[canonical] += 1
            start = idx + 1
    return c.most_common(top_n)


def pick_sentences(body: str, entities: list[tuple[str, int]], limit: int = 3) -> list[str]:
    names = {n for n, _ in entities}
    scored: list[tuple[int, str]] = []
    for line in body.splitlines():
        line = line.strip()
        if not line or SKIP_LINE.search(line):
            continue
        for s in SENT_SPLIT.split(line):
            s = s.strip()
            if not (20 <= len(s) <= 180):
                continue
            if any(x in s for x in ("诗曰", "后人有", "分节阅读", "临江仙")):
                continue
            hit = sum(1 for n in names if n in s)
            scored.append((hit * 10 + min(len(s), 80), s))
    scored.sort(key=lambda x: -x[0])
    out: list[str] = []
    seen: set[str] = set()
    for _, s in scored:
        if s in seen:
            continue
        seen.add(s)
        out.append(s)
        if len(out) >= limit:
            break
    return out


def make_summary(title: str, sents: list[str], entities: list[tuple[str, int]]) -> str:
    parts: list[str] = []
    half = re.split(r"\s+", title, maxsplit=1)
    if len(half) >= 2:
        parts.append(f"本回上半「{half[0]}」，下半「{half[1]}」。")
    elif title:
        parts.append(f"本回题旨：{title}。")
    if sents:
        parts.append("".join(sents[:2]))
    if entities:
        names = "、".join(n for n, _ in entities[:6])
        parts.append(f"主要涉及：{names}等。")
    text = "".join(parts)
    return text[:420] + ("……" if len(text) > 420 else "")


def build_chapter(ordinal: int, label: str, title: str, body: str) -> Chapter:
    plain = re.sub(r"\s+", "", body)
    entities = count_entities(body)
    sents = pick_sentences(body, entities)
    opening = sents[0] if sents else ""
    summary = make_summary(title, sents, entities)
    return Chapter(
        ordinal=ordinal,
        label=label,
        title=title,
        body=body,
        char_count=len(plain),
        entities=entities,
        summary=summary,
        opening=opening,
    )


def chapter_filename(ch: Chapter) -> str:
    return f"{ch.label}.md"


def render_chapter_md(ch: Chapter, prev_ch: Chapter | None, next_ch: Chapter | None) -> str:
    ent_lines = [
        f"- [[{name}]]（{cnt} 次）" for name, cnt in ch.entities if cnt > 0
    ]
    nav = []
    if prev_ch:
        nav.append(f"[[{prev_ch.label}]]（{prev_ch.title[:16]}…）")
    if next_ch:
        nav.append(f"[[{next_ch.label}]]（{next_ch.title[:16]}…）")
    lines = [
        f"# {ch.label} {ch.title}",
        "",
        f"- **回次**：{ch.ordinal} / 120",
        f"- **字数**：约 {ch.char_count} 字",
        f"- **原文**：`source/three_kingdoms.txt`（链化正文）",
        "",
        "## 摘要",
        "",
        ch.summary,
        "",
    ]
    if ch.opening and ch.opening not in ch.summary:
        lines.extend(["## 开篇", "", ch.opening, ""])
    if ent_lines:
        lines.extend(["## 主要实体", ""] + ent_lines + [""])
    if nav:
        lines.extend(["## 相邻回目", "", " · ".join(nav), ""])
    lines.extend(
        [
            "## 说明",
            "",
            "本页由 `build_index_summaries.py` 据原文自动抽取生成，供知识库索引与检索。",
            "",
        ]
    )
    return "\n".join(lines)


def render_part_md(
    part_no: int,
    name: str,
    hint: str,
    chapters: list[Chapter],
) -> str:
    total_chars = sum(c.char_count for c in chapters)
    ent: Counter[str] = Counter()
    for c in chapters:
        ent.update(dict(c.entities))
    top_ent = ent.most_common(12)
    title_list = "；".join(f"{c.label}{c.title[:10]}" for c in chapters[:8])
    if len(chapters) > 8:
        title_list += f"……等共 {len(chapters)} 回"
    lines = [
        f"# 第{part_no}部 · {name}",
        "",
        f"- **回目范围**：第 {chapters[0].ordinal} — {chapters[-1].ordinal} 回",
        f"- **字数**：约 {total_chars} 字",
        f"- **梗概**：{hint}",
        "",
        "## 本部高频实体",
        "",
    ]
    for n, cnt in top_ent:
        lines.append(f"- [[{n}]]（本部共 {cnt} 次提及）")
    lines.extend(["", "## 包含回目", ""])
    for c in chapters:
        lines.append(f"- [[{c.label}|{c.ordinal:03d} · {c.title}]]")
    lines.append("")
    return "\n".join(lines)


def render_master_index(chapters: list[Chapter]) -> str:
    total = sum(c.char_count for c in chapters)
    lines = [
        "# 三国演义 · 知识库总索引",
        "",
        "基于 `source/three_kingdoms.txt` 原文构建的摘要索引，供检索、分块与后续 RAG / 图谱扩展。",
        "",
        "## 文献与词条",
        "",
        "| 资源 | 路径 | 说明 |",
        "| --- | --- | --- |",
        "| 链化原文 | `source/three_kingdoms.txt` | 含 `[[实体]]` 双向链接的全文 |",
        "| 无链接备份 | `source/three_kingdoms.txt.plain.bak` | 摘要统计用纯文本 |",
        "| 具体实体 | `wiki/entity/entity/` | 人物、地点、器物词条 |",
        "| 概念 | `wiki/concept/concept/` | 势力、事件、组织词条 |",
        "",
        f"- **规模**：全書 **120** 回，约 **{total:,}** 字",
        "- **摘要目录**：`wiki/index/chapters/`（逐回一页）",
        "- **分部索引**：`wiki/index/parts/`（四部各一页）",
        "",
        "## 四部结构",
        "",
        "| 部 | 回目 | 索引 |",
        "| --- | --- | --- |",
    ]
    for i, (lo, hi, name, hint) in enumerate(PARTS, 1):
        lines.append(
            f"| {i} | 第{lo}—{hi}回 · {name} | [[parts/第{i}部-{name}]] |"
        )
    lines.extend(
        [
            "",
            "## 回目摘要索引",
            "",
            "| 回 | 标题 | 字数 | 摘要 | 详页 |",
            "| ---: | --- | ---: | --- | --- |",
        ]
    )
    for ch in chapters:
        short = ch.summary.replace("|", "｜").replace("\n", "")[:72]
        if len(ch.summary) > 72:
            short += "…"
        lines.append(
            f"| {ch.ordinal} | {ch.title} | {ch.char_count} | {short} | "
            f"[[chapters/{ch.label}]] |"
        )
    lines.extend(
        [
            "",
            "## 使用说明",
            "",
            "1. 检索某一回：打开 `chapters/` 下对应文件，或在本表搜索标题/摘要。",
            "2. 构建知识库：以本索引为目录，将各回摘要与 `wiki/entity` 词条、`source` 原文块对齐。",
            "3. 重新生成：在项目根目录执行 `python3 build_index_summaries.py`。",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    if not PLAIN.exists():
        raise FileNotFoundError(f"缺少原文备份：{PLAIN}")

    raw = PLAIN.read_text(encoding="utf-8")
    chunks = split_chapters(raw)
    if len(chunks) != 120:
        print(f"警告：解析到 {len(chunks)} 回，预期 120 回")

    chapters: list[Chapter] = []
    for i, (label, title, body) in enumerate(chunks, 1):
        chapters.append(build_chapter(i, label, title, body))

    INDEX_DIR.mkdir(parents=True, exist_ok=True)
    CHAPTER_DIR.mkdir(parents=True, exist_ok=True)
    PART_DIR.mkdir(parents=True, exist_ok=True)

    for i, ch in enumerate(chapters):
        prev_c = chapters[i - 1] if i > 0 else None
        next_c = chapters[i + 1] if i + 1 < len(chapters) else None
        path = CHAPTER_DIR / chapter_filename(ch)
        path.write_text(render_chapter_md(ch, prev_c, next_c), encoding="utf-8")

    for part_no, (lo, hi, name, hint) in enumerate(PARTS, 1):
        subset = [c for c in chapters if lo <= c.ordinal <= hi]
        part_path = PART_DIR / f"第{part_no}部-{name}.md"
        part_path.write_text(render_part_md(part_no, name, hint, subset), encoding="utf-8")

    (INDEX_DIR / "index.md").write_text(render_master_index(chapters), encoding="utf-8")

    print(f"总索引 -> {INDEX_DIR / 'index.md'}")
    print(f"回目摘要 {len(chapters)} 篇 -> {CHAPTER_DIR}")
    print(f"分部索引 {len(PARTS)} 篇 -> {PART_DIR}")


if __name__ == "__main__":
    main()
