#!/usr/bin/env bash
# 每 30 秒检查一次，挂了就拉起来。
set -uo pipefail
BRIDGE="${BRIDGE:-$HOME/dafeiyu/qq-bridge}"
LOG=/tmp/watchdog.log

while true; do
  if ! pgrep -f "qq-bridge/src/bridge.js" >/dev/null; then
    echo "[$(date '+%F %T')] bridge 挂了，重启" >> "$LOG"
    ( cd "$BRIDGE" && nohup node src/bridge.js >> /tmp/qqbridge.out 2>&1 & )
  fi

  if command -v docker >/dev/null; then
    if [ "$(docker inspect -f '{{.State.Running}}' snowluma 2>/dev/null)" != "true" ]; then
      echo "[$(date '+%F %T')] 容器挂了，重启" >> "$LOG"
      docker start snowluma >/dev/null 2>&1 || true
    fi
  fi

  sleep 30
done
