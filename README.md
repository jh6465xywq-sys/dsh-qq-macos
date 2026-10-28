# dsh-qq-macos

在 macOS 上把 [DeepSeek Harness](https://github.com/deepseek-ai) 接进 QQ：会聊天、接梗、发表情包、发语音（可以克隆指定音色）、写空间说说。

> ### 🤖 让 AI 自己装
>
> 这个仓库带 [AGENTS.md](AGENTS.md)——一份写给 **AI agent** 的作业书。
> 把你的 AI 叫过来，丢这句话就行：
>
> ```text
> https://github.com/jh6465xywq-sys/dsh-qq-macos
> 按 AGENTS.md 帮我在 macOS 上部署一套。
> 每一步都要验证，需要我配合的（比如扫码）停下来问我。
> ```
>
> 它会自己跑环境自检、起容器、打补丁、接 DSH。
> 只有**扫码登录 QQ** 那一步必须你来（手机扫码没法自动化）。
>
> 不想用 AI 就自己跑：`cp .env.example .env && bash deploy.sh`

这不是源码包，是一份**流程 + 补丁**。跟着走大约 20 分钟能跑通，前提是你按顺序来。

---

## 先说结论：Mac 上有三条路，只有一条能走

| 路线 | 结果 | 原因 |
|---|---|---|
| NapCat macOS 安装器 | ❌ 装完自报成功，实际不加载 | 改不动 `/Applications/QQ.app`（TCC App Management 拦的是**发起进程**，不是文件权限）；且新版 QQ 把入口压进了 asar |
| Lagrange.OneBot | ❌ 登录卡死 | 依赖的签名服务器全线 404，没有公共实例可用 |
| **SnowLuma 跑在 Linux 容器里** | ✅ | SnowLuma 官方不发 macOS 二进制，但它支持 Linux + arm64，用 colima 起个轻量虚拟机跑容器，再用 noVNC 在你浏览器里扫码 |

本仓库走第三条。`docs/01-为什么难.md` 里有前两条路的完整失败记录，包括每一条报错原文——想省时间的可以直接跳过。

---

## 最终长这样

```
你的 Mac
├── colima 轻量 Linux 虚拟机
│   └── Docker 容器（arm64）
│       ├── Linux QQ（真客户端，不是协议端）
│       ├── SnowLuma（协议转换 → OneBot v11）
│       └── noVNC（把容器里的界面映射到浏览器 :6081）
├── qq-bridge（Node，:3100 控制台）
│   ├── OneBot ←→ DSH API 的翻译层
│   ├── 人格/记忆/语音/表情包/空间说说
│   └── MCP server（把能力开成 AI 可直接调的工具）
└── DeepSeek Harness（本体，用自定义 preset 当人格）
```

消息流：`QQ 好友发消息 → Linux QQ → SnowLuma → OneBot WS :3001 → qq-bridge → DSH → 回复原路返回`

---

## 能实现什么

- **正常聊天**，语气自然，会分多条发、会引用、会 @ 人
- **表情包**：从收藏里按语境挑一张发出去；看到有意思的会自己收藏
- **语音**：文字转成**指定音色**的语音条发出去（音色可以是任何人给的 3–10 秒素材）
- **空间说说**：发说说、看说说、点赞
- **长期记忆**：记住对方说过的事，换天再聊还记得
- **主动不发**：只在该说话时说话，不会刷屏（概率和场景双重约束）

---

## 前置条件

- macOS 13+，Apple Silicon 或 Intel 都能用
- 磁盘 ≥ 15 GB（容器镜像 + 模型），内存 ≥ 16 GB（克隆语音建议 32 GB）
- 一个**小号 QQ**。⚠️ 这是非官方协议端，主号别用
- 能装 Homebrew（本仓库的脚本用它装 colima）

---

## 快速开始

```bash
git clone https://github.com/<you>/dsh-qq-macos.git
cd dsh-qq-macos
cp .env.example .env      # 填你自己的，这个文件不会被提交
```

然后按顺序读、按顺序做，**不要跳**：

| 步骤 | 文档 | 大约耗时 |
|---|---|---|
| 1 | [`docs/02-底座.md`](docs/02-底座.md) — colima + Docker + SnowLuma + noVNC 扫码 | 8 分钟（首次要下镜像） |
| 2 | [`docs/03-桥接.md`](docs/03-桥接.md) — qq-bridge、DSH preset、MCP 挂载 | 6 分钟 |
| 3 | [`docs/04-人格.md`](docs/04-人格.md) — 角色卡怎么写才像人 | 5 分钟 |
| 4 | [`docs/06-表情包与说说.md`](docs/06-表情包与说说.md) — 打补丁、灌表情包 | 4 分钟 |
| 5 | [`docs/05-语音.md`](docs/05-语音.md) — 语音条 + 音色克隆（**可选**，重） | 25 分钟 |
| 6 | [`docs/09-运维.md`](docs/09-运维.md) — 守护进程、开机自启、看日志 | 3 分钟 |

跑不通就先翻 [`docs/99-踩坑总表.md`](docs/99-踩坑总表.md)。那里的每一条都是真实撞过的，报错原文照抄，可以直接搜。

---

## 目录

```
docs/       流程文档，按顺序读
patches/    对上游 qq-bridge 的补丁，git apply 就能用
scripts/    一键脚本（起容器、装桥接、装守护进程）
voice-lab/  声音实验室，独立网页，用来试音色（可选）
```

补丁说明见 [`patches/README.md`](patches/README.md)。打之前请先确认你的 qq-bridge 版本对得上。

---

## 已知限制

- **这不是官方 API**。用的是真 QQ 客户端 + 协议转换，稳定性取决于 SnowLuma 上游。账号有风险，用小号。
- **微信/手机扫码**：登录时 QQ 会要你在手机上确认设备，这是正常的。
- **语音克隆不是开箱即用**。GPT-SoVITS 在 Mac 上要装 PyTorch，占 4 GB 左右，CPU 合成一句话 3–6 秒。不想折腾可以用系统 `say` 兜底（`docs/05-语音.md` 有备选方案）。
- 说话带**幻觉**：模型偶尔会编。人格卡里要写死「不确定就说不记得」。

---

## 依赖与致谢

本仓库**不包含**以下项目的代码，只提供集成流程和补丁：

- [SnowLuma](https://github.com/SnowLuma/SnowLuma) — 协议端，OneBot 11 实现
- [qq-bridge](https://github.com/Derpyu520/qq-bridge) — OneBot ←→ DSH 的桥接与控制台
- [GPT-SoVITS](https://github.com/RVC-Boss/GPT-SoVITS) — 语音克隆（可选）
- [colima](https://github.com/abiosoft/colima) — macOS 上的轻量 Linux 虚拟机
- 灵感来自 B 站 [@四分一只在努力](https://space.bilibili.com/) 与 [@泽轩604](https://space.bilibili.com/) 的教程，以及 [ai.baomiao.cn](https://ai.baomiao.cn)

如果这些项目的作者希望调整引用方式，开 issue 告诉我。

---

## License

MIT。文档和补丁随便用；上游项目的代码遵循它们各自的协议。
