# -*-coding: utf-8 -*-
"""
生成交互式 HTML 人物关系图（可直接用浏览器打开）。
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from character_relations import (
    FACTIONS,
    RELATION_EDGES,
    CHARACTER_FACTION,
    edge_label,
)

ROOT = Path(__file__).resolve().parent
OUT_DIR = ROOT / "wiki" / "faction"
HTML_FILE = OUT_DIR / "人物关系图.html"

FACTION_COLORS = {
    "shu": {"bg": "#8B2500", "border": "#5C1800", "name": "蜀汉"},
    "wei": {"bg": "#1A5276", "border": "#0E2F44", "name": "曹魏"},
    "wu": {"bg": "#1E6B3A", "border": "#0F3D22", "name": "东吴"},
    "qun": {"bg": "#5D6D7E", "border": "#34495E", "name": "群雄"},
    "other": {"bg": "#95A5A6", "border": "#7F8C8D", "name": "其他"},
}


def build_graph_data() -> dict:
    nodes: dict[str, dict] = {}
    for fid, meta in FACTIONS.items():
        color = FACTION_COLORS[fid]
        for name in meta["members"]:
            nodes[name] = {
                "id": name,
                "label": name,
                "group": fid,
                "faction": meta["name"],
                "color": color,
            }

    edges = []
    seen_edge: set[frozenset] = set()
    for a, b, tags in RELATION_EDGES:
        for n in (a, b):
            if n not in nodes:
                fid = CHARACTER_FACTION.get(n, "other")
                if fid == "other" or fid not in FACTION_COLORS:
                    color = FACTION_COLORS["other"]
                    faction_name = "其他"
                    group = "other"
                else:
                    color = FACTION_COLORS[fid]
                    faction_name = FACTIONS[fid]["name"]
                    group = fid
                nodes[n] = {
                    "id": n,
                    "label": n,
                    "group": group,
                    "faction": faction_name,
                    "color": color,
                }
        key = frozenset({a, b})
        if key in seen_edge:
            continue
        seen_edge.add(key)
        lab = edge_label(tags)
        if len(lab) > 36:
            lab = lab[:34] + "…"
        same = CHARACTER_FACTION.get(a) == CHARACTER_FACTION.get(b) and CHARACTER_FACTION.get(a)
        edges.append(
            {
                "from": a,
                "to": b,
                "label": lab,
                "title": edge_label(tags),
                "dashes": not same,
            }
        )

    return {"nodes": list(nodes.values()), "edges": edges}


def render_html(data: dict) -> str:
    payload = json.dumps(data, ensure_ascii=False)
    legend = "".join(
        f'<span class="leg" style="background:{FACTION_COLORS[f]["bg"]}">{FACTION_COLORS[f]["name"]}</span>'
        for f in ("shu", "wei", "wu", "qun")
    )
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>三国演义 · 人物关系图</title>
  <script src="https://unpkg.com/vis-network/standalone/umd/vis-network.min.js"></script>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ font-family: "PingFang SC", "Microsoft YaHei", sans-serif; background: #1a1a2e; color: #eee; }}
    #header {{
      padding: 12px 16px; background: #16213e; border-bottom: 1px solid #0f3460;
      display: flex; flex-wrap: wrap; align-items: center; gap: 12px;
    }}
    h1 {{ font-size: 18px; font-weight: 600; }}
    .legend {{ display: flex; gap: 8px; flex-wrap: wrap; }}
    .leg {{ padding: 4px 10px; border-radius: 4px; font-size: 12px; }}
    .btns {{ display: flex; gap: 6px; flex-wrap: wrap; }}
  button {{
      padding: 6px 12px; border: none; border-radius: 4px; cursor: pointer;
      background: #0f3460; color: #eee; font-size: 13px;
    }}
    button:hover {{ background: #e94560; }}
    button.active {{ background: #e94560; }}
    #graph {{ width: 100vw; height: calc(100vh - 56px); background: #0d0d1a; }}
    #tip {{
      position: fixed; bottom: 12px; left: 12px; max-width: 360px;
      padding: 10px 14px; background: rgba(22,33,62,.95); border-radius: 8px;
      font-size: 13px; line-height: 1.5; display: none; border: 1px solid #0f3460;
    }}
  </style>
</head>
<body>
  <div id="header">
    <h1>三国演义 · 阵营人物关系图</h1>
    <div class="legend">{legend}<span class="leg" style="background:#555">虚线=跨阵营</span></div>
    <div class="btns">
      <button class="active" data-filter="all">全部</button>
      <button data-filter="shu">蜀汉</button>
      <button data-filter="wei">曹魏</button>
      <button data-filter="wu">东吴</button>
      <button data-filter="qun">群雄</button>
    </div>
  </div>
  <div id="graph"></div>
  <div id="tip"></div>
  <script>
    const RAW = {payload};
    const container = document.getElementById("graph");
    const tip = document.getElementById("tip");

    function visNodes(filter) {{
      return RAW.nodes
        .filter(n => filter === "all" || n.group === filter)
        .map(n => ({{
          id: n.id,
          label: n.label,
          title: n.faction + "\\n" + n.id,
          color: {{ background: n.color.bg, border: n.color.border, highlight: {{ background: "#e94560", border: "#fff" }} }},
          font: {{ color: "#fff", size: 14 }},
        }}));
    }}

    function visEdges(filter, nodeIds) {{
      return RAW.edges
        .filter(e => nodeIds.has(e.from) && nodeIds.has(e.to))
        .map((e, i) => ({{
          id: i,
          from: e.from,
          to: e.to,
          label: e.label,
          title: e.title,
          font: {{ color: "#ddd", size: 11, strokeWidth: 0, align: "middle" }},
          color: {{ color: e.dashes ? "rgba(200,200,200,.6)" : "rgba(233,69,96,.85)" }},
          dashes: e.dashes,
          smooth: {{ type: "curvedCW", roundness: 0.15 }},
        }}));
    }}

    let network = null;
    function draw(filter) {{
      const nodes = visNodes(filter);
      const ids = new Set(nodes.map(n => n.id));
      const edges = visEdges(filter, ids);
      const data = {{ nodes: new vis.DataSet(nodes), edges: new vis.DataSet(edges) }};
      const options = {{
        nodes: {{ shape: "dot", size: 22, borderWidth: 2 }},
        edges: {{
          width: 1.5,
          arrows: {{ to: {{ enabled: false }} }},
          labelHighlightBold: true,
        }},
        physics: {{
          enabled: true,
          solver: "forceAtlas2Based",
          forceAtlas2Based: {{ gravitationalConstant: -42, springLength: 120, avoidOverlap: 0.8 }},
          stabilization: {{ iterations: 180 }},
        }},
        interaction: {{ hover: true, tooltipDelay: 80, zoomView: true, dragView: true }},
      }};
      if (network) network.destroy();
      network = new vis.Network(container, data, options);
      network.on("hoverEdge", p => {{
        if (p.edge !== undefined) {{
          const e = edges.get(p.edge);
          tip.style.display = "block";
          tip.textContent = e.from + " → " + e.to + "\\n" + (e.title || e.label);
        }}
      }});
      network.on("blurEdge", () => {{ tip.style.display = "none"; }});
      network.once("stabilizationIterationsDone", () => network.setOptions({{ physics: false }}));
    }}

    document.querySelectorAll(".btns button").forEach(btn => {{
      btn.addEventListener("click", () => {{
        document.querySelectorAll(".btns button").forEach(b => b.classList.remove("active"));
        btn.classList.add("active");
        draw(btn.dataset.filter);
      }});
    }});

    draw("all");
  </script>
</body>
</html>
"""


def try_graphviz_png(data: dict, out_png: Path) -> bool:
    dot_lines = [
        "graph ThreeKingdoms {",
        '  rankdir=LR;',
        '  bgcolor="#1a1a2e";',
        '  node [fontname="PingFang SC", fontsize=11, style=filled, fontcolor=white];',
        '  edge [fontname="PingFang SC", fontsize=9, fontcolor="#cccccc"];',
    ]
    for n in data["nodes"]:
        c = n["color"]["bg"]
        dot_lines.append(f'  "{n["id"]}" [label="{n["id"]}", fillcolor="{c}"];')
    for e in data["edges"]:
        lab = e["label"].replace('"', "'")
        style = "dashed" if e["dashes"] else "solid"
        dot_lines.append(
            f'  "{e["from"]}" -- "{e["to"]}" [label="{lab}", style={style}];'
        )
    dot_lines.append("}")
    dot_path = out_png.with_suffix(".dot")
    dot_path.write_text("\n".join(dot_lines), encoding="utf-8")
    try:
        subprocess.run(
            ["dot", "-Tpng", str(dot_path), "-o", str(out_png)],
            check=True,
            capture_output=True,
            timeout=60,
        )
        return out_png.exists()
    except (FileNotFoundError, subprocess.CalledProcessError):
        return False


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    data = build_graph_data()
    HTML_FILE.write_text(render_html(data), encoding="utf-8")
    print(f"交互关系图 -> {HTML_FILE}")
    print(f"  节点 {len(data['nodes'])} 个，边 {len(data['edges'])} 条")
    print("  用浏览器直接打开该 HTML 文件即可。")

    png_path = OUT_DIR / "人物关系图.png"
    if try_graphviz_png(data, png_path):
        print(f"静态 PNG -> {png_path}")
    else:
        print("  （未安装 graphviz 的 dot，跳过 PNG；可 brew install graphviz 后重跑）")


if __name__ == "__main__":
    main()
