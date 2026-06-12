# -*-coding: utf-8 -*-
"""
以阵营为核心生成人物关系图谱：阵营页、Mermaid 图、人物词条双向链接（含事件标注）。
"""

from __future__ import annotations

import re
from pathlib import Path

from character_relations import (
    FACTIONS,
    RELATION_EDGES,
    CHARACTER_FACTION,
    edge_label,
    faction_of,
    neighbors_of,
)

ROOT = Path(__file__).resolve().parent
FACTION_DIR = ROOT / "wiki" / "faction"
ENTITY_DIR = ROOT / "wiki" / "entity" / "entity"
CONCEPT_DIR = ROOT / "wiki" / "concept" / "concept"

RELATION_SECTION = "## 阵营与人物关系"
RELATION_END = "## 相关人物（原文共现）"


def mermaid_id(name: str) -> str:
    return "N_" + re.sub(r"[^\w]", "_", name)


def mermaid_edge(a: str, b: str, tags: list[str]) -> str:
    label = edge_label(tags).replace('"', "'")
    if len(label) > 28:
        label = label[:26] + "…"
    return f'  {mermaid_id(a)} -->|"{label}"| {mermaid_id(b)}'


def mermaid_nodes(names: set[str]) -> list[str]:
    return [f'  {mermaid_id(n)}["{n}"]' for n in sorted(names)]


def faction_link(name: str) -> str:
    fid = faction_of(name)
    if not fid:
        return "—"
    return f"[[{FACTIONS[fid]['name']}]]"


def render_relation_table(name: str, edges: list[tuple[str, list[str]]]) -> list[str]:
    lines = [
        "## 阵营与人物关系",
        "",
        f"- **所属阵营**：{faction_link(name)}",
        "",
        "以下链接均为**双向**：对方词条内亦有指向本文的链接与相同缘由。",
        "",
    ]
    if not edges:
        lines.append("（暂无结构化关系边，见阵营页或原文共现。）\n")
        return lines
    lines.extend(
        [
            "| 对方 | 关系 · 事件/缘由 |",
            "| --- | --- |",
        ]
    )
    for other, tags in sorted(edges, key=lambda x: x[0]):
        label = edge_label(tags)
        lines.append(f"| [[{other}]] | {label} |")
    lines.append("")
    return lines


def render_faction_mermaid(fid: str, internal_only: bool = False) -> str:
    members = set(FACTIONS[fid]["members"])
    edges: list[tuple[str, str, list[str]]] = []
    for x, y, tags in RELATION_EDGES:
        if x not in members and y not in members:
            continue
        if internal_only and (x not in members or y not in members):
            continue
        if internal_only:
            if x in members and y in members:
                edges.append((x, y, tags))
        else:
            edges.append((x, y, tags))

    nodes: set[str] = set()
    for x, y, _ in edges:
        nodes.add(x)
        nodes.add(y)

    lines = ["```mermaid", "flowchart LR"]
    lines.extend(mermaid_nodes(nodes))
    seen: set[frozenset] = set()
    for x, y, tags in edges:
        key = frozenset({x, y})
        if key in seen:
            continue
        seen.add(key)
        lines.append(mermaid_edge(x, y, tags))
    lines.append("```")
    return "\n".join(lines)


def render_faction_page(fid: str) -> str:
    meta = FACTIONS[fid]
    name = meta["name"]
    members = meta["members"]
    concept = meta.get("concept")

    lines = [
        f"# {name} · 人物关系",
        "",
        meta["summary"],
        "",
    ]
    if concept:
        lines.extend([f"概念词条：[[{concept}]]", ""])

    lines.extend(["## 阵营成员", ""])
    for m in members:
        lines.append(f"- [[{m}]]")
    lines.append("")

    lines.extend(["## 阵营内关系图", "", render_faction_mermaid(fid, internal_only=True), ""])

    lines.extend(["## 阵营内关系（双向链接）", ""])
    inner: list[tuple[str, str, list[str]]] = []
    member_set = set(members)
    for x, y, tags in RELATION_EDGES:
        if x in member_set and y in member_set:
            inner.append((x, y, tags))
    for x, y, tags in inner:
        lab = edge_label(tags)
        lines.append(f"- [[{x}]] ↔ [[{y}]]：**{lab}**")
    lines.append("")

    lines.extend(["## 对外关系", ""])
    outer: list[tuple[str, str, list[str]]] = []
    for x, y, tags in RELATION_EDGES:
        if (x in member_set) ^ (y in member_set):
            outer.append((x, y, tags))
    for x, y, tags in outer:
        lab = edge_label(tags)
        lines.append(f"- [[{x}]] ↔ [[{y}]]：**{lab}**")
    lines.append("")

    lines.extend(
        [
            "## 说明",
            "",
            "由 `build_faction_graph.py` 根据 `character_relations.py` 生成。",
            "在 Obsidian 关系图中以本阵营成员为簇，沿链接线查看标注事件。",
            "",
        ]
    )
    return "\n".join(lines)


def render_overview() -> str:
    lines = [
        "# 人物关系图谱 · 阵营总览",
        "",
        "以**阵营**为簇组织人物，人物之间为**双向链接**；连线上文字见各阵营页或人物页的表格/Mermaid。",
        "",
        "| 阵营 | 说明 | 关系页 |",
        "| --- | --- | --- |",
    ]
    for fid, meta in FACTIONS.items():
        lines.append(f"| {meta['name']} | {meta['summary'][:36]}… | [[{meta['name']}]] |")
    lines.extend(
        [
            "",
            "## 三国鼎立关系示意",
            "",
            "```mermaid",
            "flowchart TB",
            '  SHU["蜀汉"]',
            '  WEI["曹魏"]',
            '  WU["东吴"]',
            '  SHU <-->|"赤壁联盟/夷陵对立"| WU',
            '  WEI <-->|"官渡/汉中/北伐"| SHU',
            '  WEI <-->|"赤壁/濡须/石亭"| WU',
            "```",
            "",
            "## 全图（核心人物）",
            "",
        ]
    )
    core = set()
    for fid in ("shu", "wei", "wu"):
        core.update(FACTIONS[fid]["members"][:8])
    core.update(["吕布", "董卓", "袁绍"])

    lines.append("```mermaid")
    lines.append("flowchart TB")
    lines.extend(mermaid_nodes(core))
    seen: set[frozenset] = set()
    for x, y, tags in RELATION_EDGES:
        if x not in core or y not in core:
            continue
        key = frozenset({x, y})
        if key in seen:
            continue
        seen.add(key)
        lines.append(mermaid_edge(x, y, tags))
    lines.append("```")
    lines.append("")
    lines.extend(
        [
            "## 使用说明",
            "",
            "1. 打开阵营页（如 [[蜀汉]]）查看本阵营内/对外全部标注关系。",
            "2. 打开人物页「阵营与人物关系」表，查看与该人物相关的双向链接。",
            "3. 重新生成：`python3 build_faction_graph.py`。",
            "",
        ]
    )
    return "\n".join(lines)


def patch_character_page(path: Path, name: str) -> bool:
    if not path.exists():
        return False
    text = path.read_text(encoding="utf-8")
    if "- **细类**：人物" not in text:
        return False

    edges = neighbors_of(name)
    new_block = "\n".join(render_relation_table(name, edges))
    if not new_block:
        return False

    if RELATION_SECTION in text:
        pattern = re.compile(
            r"## 阵营与人物关系\n.*?(?=\n## )",
            re.DOTALL,
        )
        if pattern.search(text):
            text = pattern.sub(new_block.rstrip() + "\n\n", text, count=1)
        else:
            old = re.compile(r"## 人物关系\n.*?(?=\n## )", re.DOTALL)
            text = old.sub(new_block.rstrip() + "\n\n", text, count=1)
    elif "## 人物关系" in text:
        old = re.compile(r"## 人物关系\n.*?(?=\n## )", re.DOTALL)
        text = old.sub(new_block.rstrip() + "\n\n", text, count=1)
    elif RELATION_END in text:
        text = text.replace(RELATION_END, new_block + RELATION_END, 1)
    else:
        text = text.rstrip() + "\n\n" + new_block

    path.write_text(text, encoding="utf-8")
    return True


def main() -> None:
    FACTION_DIR.mkdir(parents=True, exist_ok=True)

    (FACTION_DIR / "人物关系总览.md").write_text(
        render_overview(), encoding="utf-8"
    )

    for fid, meta in FACTIONS.items():
        fname = f"{meta['name']}.md"
        (FACTION_DIR / fname).write_text(render_faction_page(fid), encoding="utf-8")

    patched = 0
    all_chars = set(CHARACTER_FACTION.keys())
    for x, y, _ in RELATION_EDGES:
        all_chars.add(x)
        all_chars.add(y)

    for name in sorted(all_chars):
        path = ENTITY_DIR / f"{name}.md"
        if patch_character_page(path, name):
            patched += 1

    print(f"阵营页 -> {FACTION_DIR}（{len(FACTIONS)} 个阵营 + 总览）")
    print(f"已更新人物词条 {patched} 篇 -> {ENTITY_DIR}")
    print(f"关系边共 {len(RELATION_EDGES)} 条")


if __name__ == "__main__":
    main()
