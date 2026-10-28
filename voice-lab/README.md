# 声音实验室

独立的本地网页，用来试音色，和 QQ 完全解耦。

```bash
python3 voice-lab.py     # 打开 http://127.0.0.1:9881
```

能干的：

- 拖任意音频（wav/m4a/mp3）进去，自动转写
- 换文案、调语速和稳定度
- 存多个声音，随时切换

调好参数之后，把对应的 `refAudio` / `promptText` / `speedFactor` 填进 qq-bridge 的 `config.json`。

## 为什么不用 ffmpeg

所有音频解码在**前端用 Web Audio API** 做，转成 32k 单声道 WAV 再发后端。所以不需要装 ffmpeg，也就不会遇到 `spawn ffprobe ENOENT`。

## 依赖

- Python 3.9+，标准库就够（`http.server` + `urllib`）
- 一个跑着的 GPT-SoVITS API（`api_v2.py`，默认 9880）
