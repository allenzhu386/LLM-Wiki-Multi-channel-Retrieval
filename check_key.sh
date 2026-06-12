#!/bin/zsh
# 检查 DashScope 密钥配置（不打印完整密钥）
cd "$(dirname "$0")"
source "$HOME/.zshrc" 2>/dev/null || true

python3 <<'PY'
import os, re
from pathlib import Path

raw = os.environ.get("DASHSCOPE_API_KEY", "")
print("1. 当前环境变量 DASHSCOPE_API_KEY:")
if not raw:
    print("   [未设置]")
else:
    print(f"   长度={len(raw)}")
    non = [(i, c) for i, c in enumerate(raw) if ord(c) > 127]
    if non:
        print(f"   [含中文/非ASCII] 位置 {non[0][0]} 起，共 {len(non)} 个字符")
        print("   前20字符 repr:", repr(raw[:20]))
    else:
        print("   [纯英文] 前缀:", raw[:8] + "..." if len(raw) > 8 else raw)

zshrc = Path.home() / ".zshrc"
print("\n2. ~/.zshrc 中的配置行:")
if zshrc.exists():
    lines = [l for l in zshrc.read_text(encoding="utf-8", errors="replace").splitlines()
             if "DASHSCOPE_API_KEY" in l and not l.strip().startswith("#")]
    if not lines:
        print("   [未找到 DASHSCOPE_API_KEY]")
    for l in lines:
        show = l if len(l) < 60 else l[:30] + "..." + l[-15:]
        bad = any(ord(c) > 127 for c in l.split("=", 1)[-1] if "=" in l)
        print(f"   {'[含中文-需修改]' if bad else '[OK]'} {show}")
else:
    print("   [无 ~/.zshrc]")

print("\n3. 自动提取 sk- 密钥:")
m = re.search(r"(sk-[A-Za-z0-9_-]+)", raw)
if m:
    k = m.group(1)
    print(f"   可正常使用，长度={len(k)}，前缀 {k[:10]}...")
else:
    print("   [失败] 请把 ~/.zshrc 改成:")
    print('   export DASHSCOPE_API_KEY=sk-你的密钥')
PY
