# -*-coding: utf-8 -*-
"""
从《三国演义》原文统计高频词，生成 wiki/entity 下的 Markdown 词条。
具体个体 -> wiki/entity/entity/；抽象概念 -> wiki/entity/concept/
"""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / "source" / "three_kingdoms.txt"
LINKED_SOURCE = SOURCE
ENTITY_DIR = ROOT / "wiki" / "entity" / "entity"
CONCEPT_DIR = ROOT / "wiki" / "concept" / "concept"
WIKILINK_RE = re.compile(r"\[\[(?:([^|\]]+)\|)?([^\]]+)\]\]")

# 共现次数达到该阈值才写入「相关」链接
MIN_COOCCUR = 3
TOP_RELATED = 18

# 细分类 -> 顶层分类（entity | concept）
KIND_ENTITY = "entity"
KIND_CONCEPT = "concept"
CONCEPT_SUBTYPES = frozenset({"势力", "组织", "事件"})

# 实体定义：(规范名, 细分类, [检索用别名/关键词])
ENTITIES: list[tuple[str, str, list[str]]] = [
    # 人物
    ("刘备", "人物", ["刘备", "刘玄德", "玄德", "先主", "皇叔", "汉中王"]),
    ("关羽", "人物", ["关羽", "关公", "云长", "关云长", "美髯公"]),
    ("张飞", "人物", ["张飞", "翼德", "张翼德"]),
    ("诸葛亮", "人物", ["诸葛亮", "孔明", "卧龙", "武乡侯"]),
    ("曹操", "人物", ["曹操", "孟德", "阿瞒", "魏王"]),
    ("孙权", "人物", ["孙权", "仲谋", "吴侯"]),
    ("周瑜", "人物", ["周瑜", "公瑾"]),
    ("吕布", "人物", ["吕布", "奉先", "温侯"]),
    ("赵云", "人物", ["赵云", "子龙", "赵子龙"]),
    ("司马懿", "人物", ["司马懿", "仲达", "司马仲达"]),
    ("董卓", "人物", ["董卓", "董贼", "太师"]),
    ("袁绍", "人物", ["袁绍", "本初", "袁本初"]),
    ("马超", "人物", ["马超", "孟起", "马孟起"]),
    ("黄忠", "人物", ["黄忠", "汉升"]),
    ("姜维", "人物", ["姜维", "伯约"]),
    ("魏延", "人物", ["魏延", "文长"]),
    ("庞统", "人物", ["庞统", "士元", "凤雏"]),
    ("孙策", "人物", ["孙策", "伯符", "小霸王"]),
    ("陆逊", "人物", ["陆逊", "伯言"]),
    ("曹丕", "人物", ["曹丕", "子桓"]),
    ("刘禅", "人物", ["刘禅", "阿斗", "后主"]),
    ("公孙瓒", "人物", ["公孙瓒"]),
    ("刘表", "人物", ["刘表", "景升"]),
    ("刘璋", "人物", ["刘璋", "季玉"]),
    ("张辽", "人物", ["张辽", "文远"]),
    ("徐晃", "人物", ["徐晃", "公明"]),
    ("张郃", "人物", ["张郃", "儁乂"]),
    ("许褚", "人物", ["许褚", "仲康"]),
    ("典韦", "人物", ["典韦"]),
    ("荀彧", "人物", ["荀彧", "文若"]),
    ("郭嘉", "人物", ["郭嘉", "奉孝"]),
    ("贾诩", "人物", ["贾诩", "文和"]),
    ("夏侯惇", "人物", ["夏侯惇", "元让"]),
    ("夏侯渊", "人物", ["夏侯渊", "妙才"]),
    ("曹仁", "人物", ["曹仁", "子孝"]),
    ("曹洪", "人物", ["曹洪", "子廉"]),
    ("张角", "人物", ["张角", "天公将军"]),
    ("华雄", "人物", ["华雄"]),
    ("颜良", "人物", ["颜良"]),
    ("文丑", "人物", ["文丑"]),
    ("貂蝉", "人物", ["貂蝉"]),
    ("孙尚香", "人物", ["孙尚香", "孙夫人"]),
    ("甘宁", "人物", ["甘宁", "兴霸"]),
    ("太史慈", "人物", ["太史慈", "子义"]),
    ("鲁肃", "人物", ["鲁肃", "子敬"]),
    ("吕蒙", "人物", ["吕蒙", "子明"]),
    ("黄盖", "人物", ["黄盖", "公覆"]),
    ("程普", "人物", ["程普", "德谋"]),
    ("韩当", "人物", ["韩当", "义公"]),
    ("孙坚", "人物", ["孙坚", "文台"]),
    ("马谡", "人物", ["马谡", "幼常"]),
    ("马岱", "人物", ["马岱"]),
    ("关平", "人物", ["关平"]),
    ("张苞", "人物", ["张苞"]),
    ("关兴", "人物", ["关兴", "安国"]),
    ("邓艾", "人物", ["邓艾", "士载"]),
    ("钟会", "人物", ["钟会", "士季"]),
    ("司马昭", "人物", ["司马昭", "子上"]),
    ("司马师", "人物", ["司马师", "子元"]),
    ("王允", "人物", ["王允", "子师"]),
    ("李儒", "人物", ["李儒"]),
    ("张让", "人物", ["张让"]),
    ("何进", "人物", ["何进"]),
    ("卢植", "人物", ["卢植", "子干"]),
    ("皇甫嵩", "人物", ["皇甫嵩", "义真"]),
    ("朱儁", "人物", ["朱儁", "公伟"]),
    ("袁术", "人物", ["袁术", "公路"]),
    ("孟获", "人物", ["孟获"]),
    ("祝融夫人", "人物", ["祝融", "祝融夫人"]),
    ("华佗", "人物", ["华佗", "元化"]),
    ("左慈", "人物", ["左慈"]),
    ("于吉", "人物", ["于吉"]),
    # 地点
    ("洛阳", "地点", ["洛阳"]),
    ("长安", "地点", ["长安"]),
    ("许昌", "地点", ["许昌", "许都"]),
    ("邺城", "地点", ["邺城", "邺都", "邺"]),
    ("成都", "地点", ["成都", "益州城"]),
    ("荆州", "地点", ["荆州", "荆襄"]),
    ("益州", "地点", ["益州", "西川"]),
    ("江东", "地点", ["江东", "江左"]),
    ("赤壁", "地点", ["赤壁"]),
    ("夷陵", "地点", ["夷陵", "猇亭"]),
    ("街亭", "地点", ["街亭"]),
    ("祁山", "地点", ["祁山"]),
    ("汉中", "地点", ["汉中"]),
    ("樊城", "地点", ["樊城"]),
    ("新野", "地点", ["新野"]),
    ("官渡", "地点", ["官渡"]),
    ("白帝城", "地点", ["白帝城", "白帝"]),
    ("麦城", "地点", ["麦城"]),
    ("定军山", "地点", ["定军山"]),
    ("虎牢关", "地点", ["虎牢关", "虎牢"]),
    ("汜水关", "地点", ["汜水关"]),
    ("潼关", "地点", ["潼关"]),
    ("剑阁", "地点", ["剑阁"]),
    ("南蛮", "地点", ["南蛮", "南中"]),
    ("西凉", "地点", ["西凉"]),
    ("冀州", "地点", ["冀州"]),
    ("幽州", "地点", ["幽州"]),
    ("并州", "地点", ["并州"]),
    ("徐州", "地点", ["徐州"]),
    ("扬州", "地点", ["扬州"]),
    ("江夏", "地点", ["江夏"]),
    ("襄阳", "地点", ["襄阳"]),
    ("建业", "地点", ["建业", "石头城"]),
    ("濡须", "地点", ["濡须", "濡须口"]),
    ("合肥", "地点", ["合肥", "合淝"]),
    # 概念：势力 / 组织 / 事件
    ("蜀汉", "势力", ["蜀汉", "蜀国", "蜀兵", "蜀军"]),
    ("曹魏", "势力", ["曹魏", "魏国", "魏兵", "魏军", "曹军"]),
    ("东吴", "势力", ["东吴", "吴国", "吴兵", "吴军"]),
    ("黄巾", "势力", ["黄巾", "黄巾贼", "黄巾军"]),
    ("十常侍", "组织", ["十常侍"]),
    ("汉室", "势力", ["汉室"]),
    ("桃园结义", "事件", ["桃园", "桃园结义", "三结义"]),
    ("赤壁之战", "事件", ["火烧赤壁", "赤壁火", "赤壁之战"]),
    ("官渡之战", "事件", ["官渡之战", "官渡之役"]),
    ("夷陵之战", "事件", ["夷陵之战", "猇亭之战"]),
    ("五丈原", "事件", ["五丈原"]),
    ("三顾茅庐", "事件", ["三顾", "茅庐"]),
    ("单刀赴会", "事件", ["单刀赴会"]),
    ("七擒孟获", "事件", ["七擒", "七擒孟获"]),
    # 器物
    ("青龙偃月刀", "器物", ["青龙偃月刀", "青龙刀", "冷艳锯"]),
    ("丈八蛇矛", "器物", ["丈八蛇矛", "丈八矛"]),
    ("方天画戟", "器物", ["方天画戟", "画戟"]),
    ("赤兔马", "器物", ["赤兔", "赤兔马"]),
    ("传国玉玺", "器物", ["传国玺", "玉玺", "传国玉玺"]),
    ("七星宝刀", "器物", ["七宝刀", "七星宝刀"]),
]

_seen: set[str] = set()
_ENTITY_LIST: list[tuple[str, str, list[str]]] = []
for name, subtype, aliases in ENTITIES:
    if name in _seen:
        continue
    _seen.add(name)
    keys = list(dict.fromkeys([name] + aliases))
    _ENTITY_LIST.append((name, subtype, keys))

MIN_FREQ_ENTITY = 30
MIN_FREQ_CONCEPT = 1  # 概念词条量少，预定义项均生成页面


def top_kind(subtype: str) -> str:
    return KIND_CONCEPT if subtype in CONCEPT_SUBTYPES else KIND_ENTITY


def load_text() -> str:
    """用于词频统计的纯文本（优先无链接备份）。"""
    plain_bak = SOURCE.with_suffix(SOURCE.suffix + ".plain.bak")
    path = plain_bak if plain_bak.exists() else SOURCE
    raw = path.read_text(encoding="utf-8")
    raw = re.sub(r"分节阅读\s*\d+", "", raw)
    raw = re.sub(r"\s+", "", raw)
    return raw


def count_term(text: str, term: str) -> int:
    return len(re.findall(re.escape(term), text))


def split_sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[。！？；])", text)
    return [p.strip() for p in parts if len(p.strip()) >= 8]


def pick_contexts(text: str, keywords: list[str], limit: int = 3) -> list[str]:
    kws = [k for k in keywords if k]
    if not kws:
        return []
    sents = split_sentences(text)
    scored: list[tuple[int, str]] = []
    for s in sents:
        if not any(k in s for k in kws):
            continue
        if len(s) < 12 or len(s) > 160:
            continue
        noise = s.count("、") * 4 + s.count("卿") * 2 + s.count("诗") * 3
        score = len(s) + sum(s.count(k) * 8 for k in kws) - noise
        if score < 10:
            continue
        scored.append((score, s))
    scored.sort(key=lambda x: -x[0])
    out: list[str] = []
    seen: set[str] = set()
    for _, s in scored:
        snippet = s[:220] + ("……" if len(s) > 220 else "")
        if snippet in seen:
            continue
        seen.add(snippet)
        out.append(snippet)
        if len(out) >= limit:
            break
    return out


def discover_places(text: str, known: set[str]) -> list[tuple[str, int]]:
    suffix = ("州", "郡", "城", "关", "江", "山")
    c: Counter[str] = Counter()
    for m in re.finditer(r"[\u4e00-\u9fff]{2,4}", text):
        w = m.group()
        if any(w.endswith(s) for s in suffix) and w not in known:
            c[w] += 1
    return [(w, n) for w, n in c.most_common(80) if n >= MIN_FREQ_ENTITY]


def build_alias_breakdown(text: str, keywords: list[str]) -> list[tuple[str, int]]:
    rows = [(k, count_term(text, k)) for k in keywords]
    return sorted(rows, key=lambda x: -x[1])


def compute_cooccurrence(
    linked_text: str, valid_names: set[str]
) -> dict[str, Counter[str]]:
    """从已链化原文中统计同句共现，用于人物/实体间双向链接。"""
    co: dict[str, Counter[str]] = defaultdict(Counter)
    for sent in re.split(r"(?<=[。！？；\n])", linked_text):
        targets = [
            t
            for t in dict.fromkeys(
                (m.group(1) or m.group(2)) for m in WIKILINK_RE.finditer(sent)
            )
            if t in valid_names
        ]
        if len(targets) < 2:
            continue
        for i, a in enumerate(targets):
            for b in targets[i + 1 :]:
                co[a][b] += 1
                co[b][a] += 1
    return co


def keywords_for(name: str) -> list[str]:
    for n, _, kw in _ENTITY_LIST:
        if n == name:
            return kw
    return [name]


def _top_by_subtype(
    name: str,
    co: Counter[str],
    name_meta: dict[str, str],
    subtype: str,
    *,
    exclude: set[str] | None = None,
) -> list[tuple[str, int]]:
    exclude = exclude or set()
    rows = [
        (other, n)
        for other, n in co.most_common()
        if other != name
        and other not in exclude
        and name_meta.get(other) == subtype
        and n >= MIN_COOCCUR
    ]
    return rows[:TOP_RELATED]


def render_related_sections(
    name: str,
    subtype: str,
    co_graph: dict[str, Counter[str]],
    name_meta: dict[str, str],
) -> list[str]:
    """生成实体之间的 wikilink 区块（图谱边）。"""
    co = co_graph.get(name, Counter())
    if not co and subtype != "人物":
        return []
    lines: list[str] = []
    rel_done: set[str] = set()

    if subtype == "人物":
        chars = _top_by_subtype(name, co, name_meta, "人物", exclude=rel_done)
        if chars:
            lines.extend(["## 相关人物（原文共现）", ""])
            for other, n in chars:
                lines.append(f"- [[{other}]]（同句共现 {n} 次）")
            lines.append("")

        places = _top_by_subtype(name, co, name_meta, "地点")
        if places:
            lines.extend(["## 相关地点", ""])
            for other, n in places:
                lines.append(f"- [[{other}]]（{n} 次）")
            lines.append("")

        concepts = [
            (o, n)
            for o, n in co.most_common()
            if name_meta.get(o) in CONCEPT_SUBTYPES and n >= MIN_COOCCUR
        ][:12]
        if concepts:
            lines.extend(["## 相关概念", ""])
            for other, n in concepts:
                lines.append(f"- [[{other}]]（{n} 次）")
            lines.append("")
        return lines

    if subtype == "地点":
        chars = _top_by_subtype(name, co, name_meta, "人物")
        if chars:
            lines.extend(["## 相关人物", ""])
            for other, n in chars:
                lines.append(f"- [[{other}]]（{n} 次）")
            lines.append("")
        places = _top_by_subtype(name, co, name_meta, "地点")
        if places:
            lines.extend(["## 相关地点", ""])
            for other, n in places:
                lines.append(f"- [[{other}]]（{n} 次）")
            lines.append("")
        return lines

    if subtype in CONCEPT_SUBTYPES:
        chars = _top_by_subtype(name, co, name_meta, "人物")
        if chars:
            lines.extend(["## 相关人物", ""])
            for other, n in chars:
                lines.append(f"- [[{other}]]（{n} 次）")
            lines.append("")
        return lines

    # 器物等
    chars = _top_by_subtype(name, co, name_meta, "人物")
    if chars:
        lines.extend(["## 相关人物", ""])
        for other, n in chars:
            lines.append(f"- [[{other}]]（{n} 次）")
        lines.append("")
    return lines


def render_page_md(
    name: str,
    kind: str,
    subtype: str,
    total: int,
    alias_rows: list[tuple[str, int]],
    contexts: list[str],
    co_graph: dict[str, Counter[str]],
    name_meta: dict[str, str],
) -> str:
    kind_label = "具体实体" if kind == KIND_ENTITY else "概念"
    lines = [
        f"# {name}",
        "",
        f"- **分类**：{kind_label}（`{kind}`）",
        f"- **细类**：{subtype}",
        f"- **全文出现次数**：{total}",
        "",
    ]
    hits = [(k, n) for k, n in alias_rows if n > 0]
    if hits:
        lines.append("## 用词频次")
        lines.append("")
        lines.append("| 用词 | 次数 |")
        lines.append("| --- | ---: |")
        for k, n in hits:
            label = f"{k}（正名）" if k == name else k
            lines.append(f"| {label} | {n} |")
        lines.append("")

    lines.extend(render_related_sections(name, subtype, co_graph, name_meta))

    if contexts:
        lines.append("## 原文例句")
        lines.append("")
        for i, s in enumerate(contexts, 1):
            lines.append(f"{i}. {s}")
        lines.append("")

    lines.append("## 说明")
    lines.append("")
    lines.append(
        f"本页由 `source/three_kingdoms.txt` 词频统计自动生成；"
        f"「{name}」归入 **{kind}** / {subtype}。"
    )
    lines.append("")
    return "\n".join(lines)


def render_sub_index(title: str, kind: str, rows: list[dict]) -> str:
    kind_label = "具体实体" if kind == KIND_ENTITY else "概念"
    lines = [
        f"# {title}",
        "",
        "纯目录页，**不含链接**，避免在关系图谱中成为中心节点。",
        "人物/地点之间的关系请打开各词条页的「人物关系」「相关人物」。",
        "",
        f"{kind_label}（`{kind}`），按全文出现频次降序：",
        "",
        "| 名称 | 细类 | 频次 |",
        "| --- | --- | ---: |",
    ]
    for r in rows:
        if r.get("kind") != kind:
            continue
        lines.append(f"| {r['name']} | {r['subtype']} | {r['freq']} |")
    n = sum(1 for r in rows if r.get("kind") == kind)
    lines.append("")
    lines.append(f"共 **{n}** 条。")
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    text = load_text()
    ENTITY_DIR.mkdir(parents=True, exist_ok=True)
    CONCEPT_DIR.mkdir(parents=True, exist_ok=True)

    stats: list[dict] = []
    known_names: set[str] = set()
    name_meta: dict[str, str] = {}

    for name, subtype, keywords in _ENTITY_LIST:
        kind = top_kind(subtype)
        alias_rows = build_alias_breakdown(text, keywords)
        total = sum(n for _, n in alias_rows)
        if total == 0:
            continue
        known_names.add(name)
        name_meta[name] = subtype
        contexts = pick_contexts(text, keywords)
        row = {
            "name": name,
            "kind": kind,
            "subtype": subtype,
            "freq": total,
            "file": None,
        }
        min_freq = MIN_FREQ_CONCEPT if kind == KIND_CONCEPT else MIN_FREQ_ENTITY
        stats.append(row)

    for place, freq in discover_places(text, known_names):
        if any(s["name"] == place for s in stats):
            continue
        name_meta[place] = "地点"
        stats.append(
            {
                "name": place,
                "kind": KIND_ENTITY,
                "subtype": "地点",
                "freq": freq,
                "file": f"{place}.md",
            }
        )

    valid_names = set(name_meta.keys())
    linked_raw = (
        LINKED_SOURCE.read_text(encoding="utf-8")
        if LINKED_SOURCE.exists()
        else ""
    )
    co_graph = compute_cooccurrence(linked_raw, valid_names)

    for row in stats:
        name = row["name"]
        subtype = row["subtype"]
        kind = row["kind"]
        min_freq = MIN_FREQ_CONCEPT if kind == KIND_CONCEPT else MIN_FREQ_ENTITY
        if row["freq"] < min_freq:
            continue
        kw = keywords_for(name)
        alias_rows = build_alias_breakdown(text, kw)
        contexts = pick_contexts(text, kw)
        md = render_page_md(
            name,
            kind,
            subtype,
            row["freq"],
            alias_rows,
            contexts,
            co_graph,
            name_meta,
        )
        out_dir = CONCEPT_DIR if kind == KIND_CONCEPT else ENTITY_DIR
        fname = f"{name}.md"
        (out_dir / fname).write_text(md, encoding="utf-8")
        row["file"] = fname

    stats.sort(key=lambda x: -x["freq"])
    (ENTITY_DIR / "实体目录.md").write_text(
        render_sub_index("具体实体目录", KIND_ENTITY, stats),
        encoding="utf-8",
    )
    (CONCEPT_DIR / "概念目录.md").write_text(
        render_sub_index("概念目录", KIND_CONCEPT, stats),
        encoding="utf-8",
    )
    # 移除旧版 index.md，避免图谱星形中心
    for old_index in (ENTITY_DIR / "index.md", CONCEPT_DIR / "index.md"):
        if old_index.exists():
            old_index.unlink()

    e_n = sum(1 for s in stats if s.get("kind") == KIND_ENTITY and s.get("file"))
    c_n = sum(1 for s in stats if s.get("kind") == KIND_CONCEPT and s.get("file"))
    print(f"entity: {e_n} 篇 -> {ENTITY_DIR}")
    print(f"concept: {c_n} 篇 -> {CONCEPT_DIR}")
    print(f"共现图谱边已写入各词条（共 {len(stats)} 条）")


if __name__ == "__main__":
    main()
