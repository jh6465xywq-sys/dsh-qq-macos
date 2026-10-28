#!/usr/bin/env bash
# 一键部署的"骨架"：能自动的自动，必须人的停下来等。
# 用法：bash deploy.sh [--from N] [--check]
set -uo pipefail
cd "$(dirname "$0")" || exit 1

FROM=0
CHECK_ONLY=0
while [ $# -gt 0 ]; do
  case "$1" in
    --from) FROM="$2"; shift 2 ;;
    --check) CHECK_ONLY=1; shift ;;
    *) shift ;;
  esac
done

ok()   { printf '  \033[32m✅\033[0m %s\n' "$1"; }
bad()  { printf '  \033[31m❌\033[0m %s\n' "$1"; }
warn() { printf '  \033[33m⚠️\033[0m  %s\n' "$1"; }
step() { printf '\n\033[1m── %s ──\033[0m\n' "$1"; }

FAILED=0
need() { if [ "$FROM" -le "$1" ] && [ "$CHECK_ONLY" -eq 0 ]; then return 0; else return 1; fi; }

# ---------- 0. 环境 ----------
step "0. 环境自检"
VER=$(sw_vers -productVersion | cut -d. -f1)
[ "$VER" -ge 14 ] && ok "macOS $VER" || { bad "macOS $VER < 14"; FAILED=1; }
[ "$(uname -m)" = "arm64" ] && ok "Apple Silicon" || warn "Intel（能用，镜像要换 amd64）"
command -v git >/dev/null && ok "git" || { bad "缺 git"; FAILED=1; }
FREE=$(df -g "$HOME" | tail -1 | awk '{print $4}')
[ "${FREE:-0}" -ge 20 ] && ok "磁盘 ${FREE}GB" || warn "磁盘只剩 ${FREE}GB，建议 20GB+"
[ -f .env ] && ok ".env 已存在" || warn "还没有 .env（cp .env.example .env 后填）"

if command -v node >/dev/null; then ok "node $(node -v)"
elif [ -x "/Applications/DeepSeek Harness.app/Contents/Resources/runtime/primary-runtime/dependencies/node/bin/node" ]; then
  ok "node（DSH 内置）"; export PATH="/Applications/DeepSeek Harness.app/Contents/Resources/runtime/primary-runtime/dependencies/node/bin:$PATH"
else bad "缺 node（第 3 步要用）→ 装 DSH 或 brew install node"; FAILED=1; fi

command -v pnpm >/dev/null && ok "pnpm" || warn "缺 pnpm → corepack enable pnpm（第 3 步会自动尝试）"
command -v docker >/dev/null && ok "docker" || warn "缺 docker → 第 1 步会装"
command -v colima >/dev/null && ok "colima" || warn "缺 colima → 第 1 步会装"

if [ "$CHECK_ONLY" -eq 1 ]; then
  echo; [ "$FAILED" -eq 0 ] && echo "自检通过，可以开工。" || echo "自检有问题，先修。"
  exit "$FAILED"
fi

# ---------- 1. 底座 ----------
if need 1; then
  step "1. Docker + colima + 镜像"
  if command -v docker >/dev/null && docker ps >/dev/null 2>&1; then
    ok "docker 已在跑，跳过"
  else
    bash scripts/01-colima.sh || { bad "01-colima.sh 失败"; exit 1; }
  fi
  docker images | grep -q snowluma && ok "镜像已就位" || bad "镜像缺失"
fi

# ---------- 2. 容器 + 扫码（必须人） ----------
if need 2; then
  step "2. 起 SnowLuma 容器"
  if docker ps --format '{{.Names}}' | grep -q '^snowluma$'; then
    ok "容器已在运行"
  else
    bash scripts/02-snowluma.sh || { bad "02-snowluma.sh 失败"; exit 1; }
  fi

  echo
  warn "接下来必须你自己做："
  echo "     1. 打开 http://127.0.0.1:6081/vnc.html"
  echo "     2. 密码见 .env 的 VNC_PASSWD"
  echo "     3. 用手机 QQ（小号）扫里面的二维码"
  echo
  read -r -p "   扫完了吗？(y/n) " ans
  if [ "${ans:-n}" != "y" ]; then echo " 停在这里，扫完再跑：bash deploy.sh --from 3"; exit 0; fi

  step "2b. 验证登录"
  if docker logs --tail 80 snowluma 2>&1 | grep -q "session started"; then
    ok "QQ 已登录"
  else
    bad "没看到 session started"
    echo "     看日志：docker logs --tail 50 snowluma"
    echo "     见 docs/99-踩坑总表.md A1/A2"
    exit 1
  fi
fi

# ---------- 3. 桥接 ----------
if need 3; then
  step "3. 装 qq-bridge + 打补丁"
  [ -f "$HOME/dafeiyu/qq-bridge/src/bridge.js" ] && ok "代码已在" || bash scripts/03-bridge.sh || { bad "03-bridge.sh 失败"; exit 1; }
  node --check "$HOME/dafeiyu/qq-bridge/src/bridge.js" 2>/dev/null && ok "语法通过" || bad "语法错误"
fi

# ---------- 4. 配置 ----------
if need 4; then
  step "4. 检查配置一致性"
  CFG="$HOME/dafeiyu/qq-bridge/config.json"
  if [ -f "$CFG" ]; then
    TOKEN=$(/usr/bin/python3 -c "import json;print(json.load(open('$CFG'))['snowluma']['accessToken'])" 2>/dev/null)
    if [ -n "${TOKEN:-}" ] && [ "$TOKEN" != "<填你自己的>" ]; then
      R=$(curl -s --max-time 5 "http://127.0.0.1:3000/get_login_info?access_token=$TOKEN" | head -c 120)
      echo "$R" | grep -q 'retcode":0' && ok "OneBot 认证通过" || { bad "OneBot 认证失败"; echo "     $R"; echo "     见 AGENTS.md 第 4 步"; }
    else
      warn "config.json 里 token 还没填"
    fi
  else
    warn "没有 config.json，先按 docs/03-桥接.md 建一份"
  fi
fi

# ---------- 5. DSH ----------
if need 5; then
  step "5. 接 DSH"
  N=$(grep -c "mcp-snowluma" "$HOME/.dsh/profiles/desktop/cordis.patch.yml" 2>/dev/null || echo 0)
  [ "$N" -gt 0 ] && ok "MCP 已注册（$N 处）" || warn "还没接，跑：cd ~/dafeiyu/qq-bridge && node scripts/setup-dsh.mjs desktop"
  [ "$N" -gt 0 ] && warn "改完 MCP 必须重启 DSH 才生效"
fi

# ---------- 6. 起服务 ----------
if need 6; then
  step "6. 起桥接"
  if pgrep -f "qq-bridge/src/bridge.js" >/dev/null; then
    ok "bridge 在跑"
  else
    bash scripts/start-bridge.sh && ok "已启动" || bad "启动失败"
  fi
  echo
  echo "   控制台: http://127.0.0.1:3100"
  echo "   日志:   tail -f /tmp/qqbridge.out"
fi

echo
[ "$FAILED" -eq 0 ] && echo "完成。用大号给小号发一句「在吗」试试。" || echo "有步骤没通过，看上面的红字。"
