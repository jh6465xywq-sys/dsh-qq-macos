# AGENTS.md — 给 AI 的作业书

> 这份文件是写给 **AI agent** 的，不是写给人看的。
> 人类请读 [README.md](README.md)。

你的任务：在这台 Mac 上，把一个 AI 人格接进 QQ，让它能聊天、发表情、发语音、写空间说说。

预计 40–90 分钟，取决于网速和你的用户配合度。

---

## 0. 开工前必读

### 0.1 三条铁律

1. **只用小号。** 绝不把主号接进来。需要用户提供一个小号 QQ（能扫码登录即可）。
2. **每一步都要验证，不要假设成功。** 本项目里有一半的坑都是"命令返回 0 但实际没生效"。
3. **不要跳过第 2 步的登录验证。** 后面所有失败都是它的连锁反应。

### 0.2 你需要问用户拿的东西

一次性问清楚，别反复打断：

| 需要 | 用途 | 备注 |
|---|---|---|
| 小号 QQ 号 | 机器人账号 | 必须是能扫码登录的 |
| 大号 QQ 号 | 只有这个人能和机器人私聊 | 白名单 |
| DSH 的 API key | 桥接调模型 | 在 DSH 设置里 |
| 可选：语音克隆参考音频 | 3–10 秒人声 | 没有就用系统 TTS 兜底 |

### 0.3 环境自检（先跑，缺什么补什么）

```bash
sw_vers -productVersion     # 必须 >= 14
uname -m                    # arm64 或 x86_64 都行
command -v git || echo "缺 git"
command -v docker || echo "缺 docker（第 1 步会装）"
df -h ~ | tail -1           # 至少 20GB 可用
lsof -nP -iTCP:3000 -iTCP:3001 -iTCP:6081 -iTCP:3100 -sTCP:LISTEN 2>/dev/null
```

端口被占用就先解决，别硬上。

---

## 1. 验证底座（Docker + 容器）

```bash
bash scripts/01-colima.sh
```

**成功标志**（必须三条全绿，缺一不可）：

```bash
colima status | grep -q Running && echo "1/3 VM ok"
docker ps >/dev/null 2>&1 && echo "2/3 docker ok"
docker images | grep -q snowluma && echo "3/3 image ok"
```

如果 `colima start` 报 `error resolving download URL`，是 GitHub 被墙：
镜像下载走 `--cpu` 那步之前先设代理，或者手动下载 linux 镜像放到 `~/.colima/`。

---

## 2. 起容器并登录 QQ ⚠️ 关键步骤

```bash
bash scripts/02-snowluma.sh
```

**这一步必须让人来做**（扫码）。你的职责是：

1. 跑脚本，等容器起来
2. 告诉用户："打开 http://127.0.0.1:6081/vnc.html，密码在 .env 的 VNC_PASSWD，用手机 QQ 扫里面的码"
3. **等用户说"扫完了"**
4. 然后验证：

```bash
docker logs --tail 50 snowluma | grep -E "login detected|session started"
```

**必须看到这两行**，否则不要往下走：

```
[Hook] login detected: PID=xx UIN=<小号QQ>
[OneBot] session started: UIN=<小号QQ>
```

没有 → 回看 `99-踩坑总表.md` 的 A1/A2。

---

## 3. 装桥接

```bash
bash scripts/03-bridge.sh
```

**成功标志**：

```bash
test -f ~/dafeiyu/qq-bridge/src/bridge.js && echo "code ok"
node --check ~/dafeiyu/qq-bridge/src/bridge.js && echo "syntax ok"
for p in patches/0*.patch; do echo -n "$p: "; done; echo
```

补丁必须 5/5 干净应用。有一个失败就停下来看 `patches/README.md`，别硬改。

---

## 4. 填配置（最容易出错的地方）

`~/dafeiyu/qq-bridge/config.json` 里**三个值必须完全一致**，否则发送必然 401：

1. SnowLuma 的 OneBot HTTP token
2. SnowLuma 的 OneBot WS token
3. `config.json` 的 `snowluma.accessToken`

**注意**：容器里有**两个** onebot 配置文件，改错的那个不生效：

```
/app/data/config/onebot.json              ← 改了不生效
/app/data/config/onebot_<QQ号>.json        ← 改这个
```

第二个是 QQ 登录后生成的实际配置。两个都改最稳。

**验证**（应该返回 `retcode:0`，不是 `1401`）：

```bash
TOKEN=$(python3 -c "import json;print(json.load(open('$HOME/dafeiyu/qq-bridge/config.json'))['snowluma']['accessToken'])")
curl -s "http://127.0.0.1:3000/get_login_info?access_token=$TOKEN" | head -c 200
```

---

## 5. 接 DSH

```bash
cd ~/dafeiyu/qq-bridge
node scripts/setup-dsh.mjs desktop
```

**成功标志**：

```bash
grep -c "mcp-snowluma" ~/.dsh/profiles/desktop/cordis.patch.yml   # 应该是 2 或 3
```

然后**必须让用户重启 DSH**，否则 MCP 工具不会加载。重启后你应该能在工具列表里看到：

```
qq_send_message  qq_get_recent_messages  qq_speak  qq_qzone_send  qq_memory_recall
```

看不到 → 检查 `cordis.patch.yml` 的 `cwd` 是不是还写着 Windows 路径（见过这个 bug）。

---

## 6. 冒烟测试

```bash
bash scripts/start-bridge.sh
```

让用户用大号给机器人发一句"在吗"。

**成功标志**（`/tmp/qqbridge.out`）：

```
BRIDGE_OK session=... len=...
SENT ... 段
```

**失败对照表**：

| 报错 | 去看 |
|---|---|
| `unauthorized` / `401` | 第 4 步，token 不一致 |
| `session/model-unavailable` | provider id 写错，见 D2 |
| `图地址解析到内网被拦截` | 打 `0004` 补丁，见 C3 |
| 回的内容像"我是 AI 助手" | 人格没生效，见 `04-人格.md` |

---

## 禁止事项

- ❌ 不要让用户用主号扫码
- ❌ 不要在 `config.json` 里留明文 key 然后提交到 git
- ❌ 不要跳过第 2 步的日志验证
- ❌ 不要自己编造 SnowLuma 的 API（不确定就 `docker exec` 进去看）
- ❌ 不要在没有用户明确同意时，让它给陌生人发消息

---

## 出问题时

1. 先看 `docs/99-踩坑总表.md`——20 条报错原文 → 真正原因 → 修法
2. 还不行就看 `docs/09-运维.md` 的「常见故障与恢复」
3. 仍然不行，把这个仓库的 `99-踩坑总表.md` 整篇读一遍再动手

**记住**：这个项目最大的时间黑洞不是"配置难"，而是**报了错但看起来像成功**。每步都要有独立的验证手段。
