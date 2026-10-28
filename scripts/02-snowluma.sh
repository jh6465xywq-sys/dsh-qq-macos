#!/usr/bin/env bash
# 拉起 SnowLuma 容器。密码从 .env 的 VNC_PASSWD 读。
set -euo pipefail
cd "$(dirname "$0")/.."
[ -f .env ] && set -a && . ./.env && set +a

: "${VNC_PASSWD:?先在 .env 里设 VNC_PASSWD}"

docker pull motricseven7/snowluma:latest

if docker ps -a --format '{{.Names}}' | grep -qx snowluma; then
  echo "容器已存在，重启它"
  docker start snowluma
else
  docker run -d \
    --name snowluma \
    --restart unless-stopped \
    -p 127.0.0.1:3000:3000 \
    -p 127.0.0.1:3001:3001 \
    -p 127.0.0.1:5099:5099 \
    -p 127.0.0.1:6081:6081 \
    -e VNC_PASSWD="$VNC_PASSWD" \
    -e SNOWLUMA_SCREEN=1920x1080x24 \
    -e TZ=Asia/Shanghai \
    -v snowluma-data:/app/data \
    -v snowluma-config:/app/.config \
    -v snowluma-local:/app/.local/share \
    motricseven7/snowluma:latest
fi

sleep 8
docker ps --filter name=snowluma --format '{{.Status}}'
cat <<'MSG'

下一步：
  1. 打开 http://127.0.0.1:6081/vnc.html  输入 VNC_PASSWD，用手机 QQ 扫码（小号！）
  2. 打开 http://127.0.0.1:5099  配 OneBot：HTTP 3000 / WS 3001，两个 token 设成一样
  3. 看登录成功的四行日志：docker logs snowluma | tail -20
MSG
