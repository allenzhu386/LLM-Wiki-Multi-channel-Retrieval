#!/bin/zsh
# 重建知识库索引（使用系统 Python）
set -e

ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

PYTHON=python3

line=$(grep -E '^[[:space:]]*export[[:space:]]+DASHSCOPE_API_KEY=' "$HOME/.zshrc" 2>/dev/null | tail -1)
[[ -n "$line" ]] && eval "$line"

if [[ -n "$DASHSCOPE_API_KEY" ]]; then
  export DASHSCOPE_API_KEY="$("$PYTHON" -c "from rag.llm import normalize_api_key; import os; print(normalize_api_key(os.environ.get('DASHSCOPE_API_KEY','')))")"
fi

if ! "$PYTHON" -c "import dashscope" 2>/dev/null; then
  echo "安装依赖..."
  "$PYTHON" -m pip install -r requirements.txt --user
fi

"$PYTHON" -c "from rag.llm import ensure_api_key; ensure_api_key()"

echo "开始灌库（原文 + wiki + 向量）..."
"$PYTHON" -m rag.ingest
echo "完成。数据目录: $ROOT/data/"
