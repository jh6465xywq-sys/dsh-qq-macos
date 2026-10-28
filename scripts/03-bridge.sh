#!/usr/bin/env bash
# 装 qq-bridge、打补丁、装 DSH preset。
set -euo pipefail
cd "$(dirname "$0")/.."
REPO_ROOT="$(pwd)"
BRIDGE="${BRIDGE:-$HOME/dafeiyu/qq-bridge}"

command -v pnpm >/dev/null || { echo "先装 pnpm: npm i -g pnpm"; exit 1; }

if [ ! -d "$BRIDGE" ]; then
  mkdir -p "$(dirname "$BRIDGE")"
  git clone https://github.com/Derpyu520/qq-bridge.git "$BRIDGE"
fi

cd "$BRIDGE"
pnpm install --prod

echo "== 打补丁"
for p in "$REPO_ROOT"/patches/0*.patch; do
  name=$(basename "$p")
  if git apply --check "$p" 2>/dev/null; then
    git apply "$p"; echo "  ✅ $name"
  else
    echo "  ⚠️  $name 冲突，需要手动改（见 patches/README.md）"
  fi
done

node --check src/bridge.js && echo "语法 OK"

echo "== 装 DSH preset + MCP"
node scripts/setup-dsh.mjs desktop || echo "setup 失败，检查 DSH_HOME"

cat <<'MSG'

下一步：
  1. 把 .env 里的值填进 config.json（或用 config.example.json 生成）
  2. 重启 DSH，让 MCP 生效
  3. 跑 scripts/start-bridge.sh
MSG
