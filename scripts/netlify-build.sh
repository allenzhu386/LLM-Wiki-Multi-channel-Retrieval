#!/bin/bash
# Netlify 构建：根据环境变量生成 web/config.js
set -e
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

API_URL="${RAG_API_URL:-}"
API_URL="${API_URL%/}"

if [ -z "$API_URL" ]; then
  echo "警告: 未设置 RAG_API_URL，前端将无法访问 API（请在 Netlify 环境变量中配置）"
fi

cat > web/config.js <<EOF
// 由 Netlify 构建自动生成
window.API_BASE = "${API_URL}";
EOF

echo "已生成 web/config.js -> API_BASE=${API_URL:-<空>}"
