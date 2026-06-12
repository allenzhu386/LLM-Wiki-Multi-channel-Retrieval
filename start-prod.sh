#!/bin/zsh
# 生产环境 API 服务（供 Netlify 前端或其它客户端调用）
set -e

ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"
PYTHON=python3

if [[ -z "$DASHSCOPE_API_KEY" ]] && [[ -f "$HOME/.zshrc" ]]; then
  line=$(grep -E '^[[:space:]]*export[[:space:]]+DASHSCOPE_API_KEY=' "$HOME/.zshrc" 2>/dev/null | tail -1)
  [[ -n "$line" ]] && eval "$line"
fi

if [[ -n "$DASHSCOPE_API_KEY" ]]; then
  export DASHSCOPE_API_KEY="$("$PYTHON" -c "
import os
from rag.llm import normalize_api_key
print(normalize_api_key(os.environ.get('DASHSCOPE_API_KEY', '')))
")"
fi

if [[ -z "$DASHSCOPE_API_KEY" ]] || [[ "$DASHSCOPE_API_KEY" != sk-* ]]; then
  echo "错误: 请设置 DASHSCOPE_API_KEY"
  exit 1
fi

if ! "$PYTHON" -c "import fastapi, uvicorn" 2>/dev/null; then
  "$PYTHON" -m pip install -r requirements.txt --user
fi

if [[ ! -f data/rag.db ]]; then
  echo "错误: 未找到 data/rag.db，请先执行: ./ingest.sh"
  exit 1
fi

HOST="${HOST:-0.0.0.0}"
PORT="${PORT:-8000}"
WORKERS="${WORKERS:-1}"

echo "API 服务: http://${HOST}:${PORT}"
echo "健康检查: http://${HOST}:${PORT}/api/health"
echo "Netlify 环境变量 RAG_API_URL 填: https://你的公网域名"

exec "$PYTHON" -m uvicorn api.main:app \
  --host "$HOST" \
  --port "$PORT" \
  --workers "$WORKERS"
