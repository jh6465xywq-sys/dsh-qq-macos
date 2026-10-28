#!/usr/bin/env bash
# 起 colima 虚拟机。首次会下载虚拟机镜像，国内可能很慢。
set -euo pipefail

command -v colima >/dev/null || { echo "先装 colima: brew install colima docker"; exit 1; }

if colima status >/dev/null 2>&1; then
  echo "colima 已在运行"
else
  echo "启动 colima（4 CPU / 8G / 40G）…"
  colima start --cpu 4 --memory 8 --disk 40
fi

docker version --format 'docker client {{.Client.Version}}'
echo "✅ 底座就绪"
