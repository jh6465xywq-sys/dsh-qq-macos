# 补丁说明

这些补丁打在 [qq-bridge](https://github.com/Derpyu520/qq-bridge) 上。

基准版本：`a49877f`（2026-10）。上游更新后可能冲突，冲突时对着 patch 手动改，逻辑都不复杂。

## 应用

```bash
cd ~/dafeiyu/qq-bridge
for p in ~/dsh-qq-macos/patches/0*.patch; do
  git apply --check "$p" && git apply "$p" && echo "✅ $(basename $p)" \
    || echo "⚠️  $(basename $p) 冲突"
done
node --check src/bridge.js
```

## 每个补丁做什么

| 补丁 | 文件 | 内容 |
|---|---|---|
| `0001-qzone-voice-strategy` | `src/bridge.js` | 空间说说 API（发/看/赞）、语音发送路由、语音权重注入唤醒提示 |
| `0002-long-memory` | `src/long-memory.js` | 新增：SQLite + 向量检索的长期记忆 |
| `0003-mcp-tools` | `src/mcp-snowluma-safe.js` | 把上面新增的能力开成 AI 可调用的 MCP 工具 |
| `0004-safe-fetch-fakeip` | `src/safe-fetch.js` | 放行 fake-ip 网段，修表情包「解析到内网被拦截」 |
| `0005-preset-voice-rule` | `dsh/agent-presets/qq-chat-v2/agent.cordis.yml` | 语音使用规则（概率 + 场景），进提示词 |

## 依赖关系

- `0003` 依赖 `0001` 和 `0002`（工具要调的路由得先存在）
- `0005` 单独可用，但只有配了 `0001` 的语音才会有意义

## 怎么验证

```bash
# 语法
node --check src/bridge.js

# 路由在不在
curl -s -H "x-console-token: $TOKEN" http://127.0.0.1:3100/api/qzone/list | head -c 100

# MCP 工具注册成功（重启 DSH 之后）
# 在 DSH 里应该能看到 qq_qzone_send / qq_speak / qq_memory_recall
```
