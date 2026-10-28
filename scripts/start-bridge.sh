#!/usr/bin/env bash
# 启动 bridge，自动探测 DSH 端口。
set -euo pipefail
cd "$(dirname "$0")/.."
[ -f .env ] && set -a && . ./.env && set +a
BRIDGE="${BRIDGE:-$HOME/dafeiyu/qq-bridge}"

if pgrep -f "qq-bridge/src/bridge.js" >/dev/null; then
  echo "bridge 已在运行"; exit 0
fi

PORT=$(python3 scripts/find-dsh-port.py 2>/dev/null || echo "")
if [ -n "$PORT" ]; then
  echo "探测到 DSH 端口: $PORT"
  python3 - "$BRIDGE/config.json" "$PORT" <<'PY'
import json, sys
p, port = sys.argv[1], sys.argv[2]
c = json.load(open(p, encoding='utf-8'))
c.setdefault('dsh', {})['baseUrl'] = f'http://127.0.0.1:{port}'
json.dump(c, open(p, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
print('  已写入', p)
PY
fi

cd "$BRIDGE"
nohup node src/bridge.js >> /tmp/qqbridge.out 2>&1 &
sleep 4
curl -s -o /dev/null -w "控制台: %{http_code}\n" http://127.0.0.1:3100/ || true
echo "日志: tail -f /tmp/qqbridge.out"
