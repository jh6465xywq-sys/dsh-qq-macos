#!/usr/bin/env bash
# 底座：colima（轻量 Linux 虚拟机）+ docker CLI。
#
# 两个坑写在前面：
#  1. colima 找 lima 不是纯看 PATH，软链过去它可能找不到 share/ 目录——所以这里用真实路径。
#  2. colima status 会做依赖自检，lima 布局不对时报错但退出码仍是 0——所以用 docker ps 判断。
set -uo pipefail

ARCH=$(uname -m)
[ "$ARCH" = "arm64" ] && ABI=arm64 || ABI=amd64
BIN="$HOME/bin/dafeiyu"      # 真实目录，lima 的 bin/ share/ libexec/ 都在里面
mkdir -p "$BIN"
export PATH="$BIN/bin:$BIN:$HOME/.local/bin:$PATH"

have() { command -v "$1" >/dev/null 2>&1; }
dl() { curl -fL --progress-bar -o "$1" "$2" || curl -fL --progress-bar -o "$1" "https://ghfast.top/$2"; }

latest_tag() { curl -sL "https://api.github.com/repos/$1/releases/latest" | grep -m1 '"tag_name"' | sed 's/.*"v\?\([^"]*\)".*/\1/'; }

install_lima() {
  have limactl && return 0
  local v; v=$(latest_tag lima-vm/lima)
  echo "== 装 lima ${v:-latest}"
  local tmp; tmp=$(mktemp -d)
  dl "$tmp/lima.tgz" "https://github.com/lima-vm/lima/releases/download/v${v}/lima-${v}-Darwin-${ABI}.tar.gz" || return 1
  tar -xzf "$tmp/lima.tgz" -C "$tmp" || return 1
  # 保持 bin/ share/ libexec/ 结构，别打散
  if [ -d "$tmp/lima" ]; then cp -R "$tmp/lima"/* "$BIN"/; else cp -R "$tmp"/* "$BIN"/; fi
  rm -rf "$tmp"
  export PATH="$BIN/bin:$PATH"
  have limactl && echo "   ✅ $(limactl --version 2>&1 | head -1)"
}

install_colima() {
  have colima && return 0
  local v; v=$(latest_tag abiosoft/colima)
  echo "== 装 colima ${v:-latest}"
  dl "$BIN/colima" "https://github.com/abiosoft/colima/releases/download/v${v}/colima-Darwin-${ABI}" || return 1
  chmod +x "$BIN/colima"
  have colima && echo "   ✅ $(colima version 2>&1 | head -1)"
}

install_docker_cli() {
  have docker && return 0
  echo "== 装 docker CLI（只是客户端，引擎在虚拟机里）"
  local a; [ "$ABI" = arm64 ] && a=aarch64 || a=x86_64
  local tmp; tmp=$(mktemp -d)
  dl "$tmp/docker.tgz" "https://download.docker.com/mac/static/stable/${a}/docker-28.5.1.tgz" || { echo "   跳过（可后装 brew install docker）"; return 0; }
  tar -xzf "$tmp/docker.tgz" -C "$tmp" && cp "$tmp/docker/docker" "$BIN/" && chmod +x "$BIN/docker"
  rm -rf "$tmp"
}

# 有 brew 且缺东西时优先 brew（更省心），否则二进制
if ! have colima || ! have limactl || ! have docker; then
  if have brew; then
    echo "== 用 brew 装 colima + docker + lima"
    brew install colima docker lima || true
  fi
  install_lima; install_colima; install_docker_cli
fi

have colima  || { echo "❌ colima 不可用"; exit 1; }
have limactl || { echo "❌ limactl 不可用（检查 $BIN/bin）"; exit 1; }

# 用 docker ps 判断是否已经在跑（colima status 不可靠）
if docker ps >/dev/null 2>&1; then
  echo "✅ 底座已在运行"
else
  echo "== 启动虚拟机（4C/8G/40G，首次要下 Linux 镜像，可能 5-15 分钟）"
  if ! colima start --cpu 4 --memory 8 --disk 40; then
    cat <<'MSG'

❌ 启动失败。最常见是镜像下载被墙（报 error resolving download URL）。
   绕法 A：挂代理后重跑
   绕法 B：colima start --verbose 看它要下哪个 URL，手动下载后放到 ~/.lima/_config/
MSG
    exit 1
  fi
  sleep 3
  docker ps >/dev/null 2>&1 && echo "✅ 底座就绪" || { echo "❌ 虚拟机起来了但 docker 不通，试 docker context use colima"; exit 1; }
fi
