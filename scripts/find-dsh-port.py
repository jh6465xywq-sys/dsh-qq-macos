#!/usr/bin/env python3
"""探测 DSH Desktop 的 Web API 端口。

DSH Desktop 的 API 端口 = GUI 端口，每次启动都随机，所以不能写死。
原理：扫监听中的 TCP 端口，找属于 DeepSeek 进程的那个。
"""
import re
import subprocess
import sys


def main() -> int:
    try:
        out = subprocess.run(
            ["/usr/sbin/lsof", "-nP", "-iTCP", "-sTCP:LISTEN", "-F", "pn", "c"],
            capture_output=True, text=True, timeout=10,
        ).stdout
    except Exception as exc:  # noqa: BLE001
        print(f"探测失败: {exc}", file=sys.stderr)
        return 1

    cur_pid, cur_cmd, found = None, None, []
    for line in out.splitlines():
        if line.startswith("p"):
            cur_pid = line[1:]
        elif line.startswith("c"):
            cur_cmd = line[1:]
        elif line.startswith("n"):
            if cur_cmd and "eepSeek" in cur_cmd:
                m = re.search(r":(\d+)$", line[1:])
                if m:
                    found.append((int(m.group(1)), cur_pid, cur_cmd))

    if not found:
        print("没找到 DSH 的监听端口", file=sys.stderr)
        return 1

    port, pid, cmd = sorted(found)[0]
    print(port)
    print(f"  (pid={pid} cmd={cmd})", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
