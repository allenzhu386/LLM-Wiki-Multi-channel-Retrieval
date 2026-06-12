#!/bin/zsh
# 三国演义智能问答库 — 启动（系统 Python，读取 ~/.zshrc 中的 DashScope）
set -e

ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"
PYTHON=python3

if ! command -v "$PYTHON" &>/dev/null; then
  echo "错误: 未找到 python3"
  exit 1
fi

# 从 ~/.zshrc 读取 export DASHSCOPE_API_KEY=... 行（覆盖 venv 里可能被污染的值）
load_dashscope_from_zshrc() {
  [[ -f "$HOME/.zshrc" ]] || return 1
  local line
  line=$(grep -E '^[[:space:]]*export[[:space:]]+DASHSCOPE_API_KEY=' "$HOME/.zshrc" 2>/dev/null | tail -1)
  [[ -n "$line" ]] || return 1
  eval "$line"
}

load_dashscope_from_zshrc || true

# 自动从值里提取 sk-xxxx（去掉中文说明、引号等）
if [[ -n "$DASHSCOPE_API_KEY" ]]; then
  export DASHSCOPE_API_KEY="$("$PYTHON" -c "
import os
from rag.llm import normalize_api_key
print(normalize_api_key(os.environ.get('DASHSCOPE_API_KEY', '')))
")"
fi

if ! "$PYTHON" -c "import fastapi, dashscope, uvicorn" 2>/dev/null; then
  echo "首次运行：正在安装依赖（pip install --user）..."
  "$PYTHON" -m pip install -r requirements.txt --user
fi

if [[ -z "$DASHSCOPE_API_KEY" ]] || [[ "$DASHSCOPE_API_KEY" != sk-* ]]; then
  echo "错误: 未找到有效的 DASHSCOPE_API_KEY（需 sk- 开头）"
  echo ""
  echo "请编辑 ~/.zshrc，只保留一行，例如："
  echo '  export DASHSCOPE_API_KEY=sk-xxxxxxxxxxxxxxxx'
  echo "（等号后不要写中文说明）"
  echo ""
  echo "保存后执行: source ~/.zshrc"
  echo "检查: echo \$DASHSCOPE_API_KEY"
  exit 1
fi

"$PYTHON" -c "from rag.llm import ensure_api_key; ensure_api_key(); print('DashScope 密钥 OK')"

PORT="${PORT:-8000}"
echo ""
echo "三国演义智能问答库"
echo "浏览器打开: http://127.0.0.1:${PORT}/"
echo "按 Ctrl+C 停止"
echo ""

exec "$PYTHON" -m uvicorn api.main:app --reload --host 127.0.0.1 --port "$PORT"
