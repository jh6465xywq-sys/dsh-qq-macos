#!/usr/bin/env bash
# 装 qq-bridge、打补丁、装 DSH preset。
set -euo pipefail
cd "$(dirname "$0")/.."
REPO_ROOT="$(pwd)"
BRIDGE="${BRIDGE:-$HOME/dafeiyu/qq-bridge}"

# node：优先系统里的，其次 DSH 内置
if ! command -v node >/dev/null; then
  DSH_NODE="/Applications/DeepSeek Harness.app/Contents/Resources/runtime/primary-runtime/dependencies/node/bin"
  if [ -x "$DSH_NODE/node" ]; then export PATH="$DSH_NODE:$PATH"; else
    echo "缺 node。装法：brew install node，或先装 DeepSeek Harness（自带 node）"; exit 1
  fi
fi
echo "node $(node -v)"

# pnpm：没有就用 corepack 或 npx 兜底
if ! command -v pnpm >/dev/null; then
  if command -v corepack >/dev/null; then corepack enable pnpm 2>/dev/null || true; fi
fi
PNPM="pnpm"
command -v pnpm >/dev/null || PNPM="npx --yes pnpm@11"

if [ ! -d "$BRIDGE" ]; then
  mkdir -p "$(dirname "$BRIDGE")"
  # GitHub 直连不通就走镜像
  git clone --depth 1 https://github.com/Derpyu520/qq-bridge.git "$BRIDGE" 2>/dev/null \
    || git clone --depth 1 https://ghfast.top/https://github.com/Derpyu520/qq-bridge.git "$BRIDGE" \
    || { echo "克隆失败：检查网络或代理"; exit 1; }
fi

cd "$BRIDGE"
"$PNPM" install --prod

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
