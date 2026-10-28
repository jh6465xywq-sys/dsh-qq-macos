#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
声音克隆实验室 —— 独立于 QQ / 大肥鱼 的本地小工具。

它只做一件事：给一段参考音频 + 那句音频的文字，用 GPT-SoVITS 把任意文字念出来。

为什么要单独做一个：
  qq-bridge 里那套合成是"绑在 QQ 消息上"的，想玩一次得让机器人在群里说话，
  素材、台词、参数都写死在 config.json 里。这个工具把这些拆出来，随手换人、随手试。

三个能力：
  1. 上传 / 拖入 / 直接录一段参考音频 → 自动转写成文字（faster-whisper）
  2. 任意文字 → 用那段参考音频的声音念出来，页面里直接听、直接下载
  3. 存进声音库，下次点一下就能用

依赖：同目录跑在 GPT-SoVITS 的 .venv 里（whisper 和音频库都装在那儿），
      并且 GPT-SoVITS 的 api_v2.py 已经在 9880 上跑着。
"""

import base64
import io
import json
import os
import re
import struct
import sys
import threading
import time
import urllib.error
import urllib.request
import wave
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HOME = Path.home()
LAB = HOME / "dafeiyu" / "voice-lab"
VOICES = LAB / "voices"
UPLOADS = LAB / "uploads"
for d in (LAB, VOICES, UPLOADS):
    d.mkdir(parents=True, exist_ok=True)

TTS_API = os.environ.get("VOICE_LAB_TTS_API", "http://127.0.0.1:9880")
PORT = int(os.environ.get("VOICE_LAB_PORT", "9881"))

# ---------------------------------------------------------------- whisper
_whisper_model = None
_whisper_lock = threading.Lock()


def get_whisper():
    """懒加载。第一次调用要几十秒（下模型 + 加载），之后常驻。"""
    global _whisper_model
    with _whisper_lock:
        if _whisper_model is None:
            from faster_whisper import WhisperModel
            _whisper_model = WhisperModel("small", device="cpu", compute_type="int8")
        return _whisper_model


def transcribe(wav_path: Path) -> str:
    model = get_whisper()
    segments, _ = model.transcribe(str(wav_path), language="zh")
    return "".join(s.text for s in segments).strip()


# ---------------------------------------------------------------- 音频小工具
def wav_info(path: Path):
    try:
        with wave.open(str(path)) as w:
            frames = w.getnframes()
            rate = w.getframerate()
            return {"seconds": round(frames / rate, 2), "rate": rate, "channels": w.getnchannels()}
    except Exception:
        return None


def decode_data_url(data_url: str) -> bytes:
    m = re.match(r"data:audio/[^;]+;base64,(.*)$", data_url, re.S)
    if not m:
        raise ValueError("音频格式不认识（需要 data URL）")
    return base64.b64decode(m.group(1))


def tts(text: str, ref_audio: Path, prompt_text: str, speed: float, temperature: float) -> bytes:
    payload = {
        "text": text,
        "text_lang": "zh",
        "ref_audio_path": str(ref_audio),
        "prompt_lang": "zh",
        "prompt_text": prompt_text,
        "text_split_method": "cut5",
        "batch_size": 1,
        "media_type": "wav",
        "streaming_mode": False,
        "speed_factor": speed,
        "temperature": temperature,
    }
    req = urllib.request.Request(
        f"{TTS_API}/tts",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"content-type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=300) as resp:
        return resp.read()


# ---------------------------------------------------------------- 页面
PAGE = r"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>声音实验室</title>
<style>
  :root{--bg:#0f1115;--card:#171a21;--line:#252a34;--fg:#e6e9ef;--dim:#8b93a3;--acc:#4f8cff;--ok:#3ecf8e;--warn:#f0b429;--err:#ff6b6b}
  *{box-sizing:border-box}
  body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.6 -apple-system,"PingFang SC","Helvetica Neue",sans-serif;padding:24px}
  .wrap{max-width:1000px;margin:0 auto}
  h1{font-size:20px;margin:0 0 4px}
  .sub{color:var(--dim);font-size:13px;margin-bottom:20px}
  .grid{display:grid;grid-template-columns:1fr 1fr;gap:16px}
  @media(max-width:820px){.grid{grid-template-columns:1fr}}
  .card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:16px}
  .card h2{font-size:14px;margin:0 0 12px;color:var(--dim);font-weight:600;letter-spacing:.5px}
  .drop{border:1.5px dashed var(--line);border-radius:10px;padding:22px;text-align:center;color:var(--dim);cursor:pointer;transition:.15s}
  .drop:hover,.drop.over{border-color:var(--acc);color:var(--fg);background:#1b2130}
  .drop b{color:var(--fg)}
  textarea{width:100%;background:#0c0e13;border:1px solid var(--line);border-radius:8px;color:var(--fg);padding:10px;font:inherit;resize:vertical;min-height:70px}
  textarea:focus,input:focus{outline:none;border-color:var(--acc)}
  input[type=range]{width:100%;accent-color:var(--acc)}
  .row{display:flex;gap:10px;align-items:center;margin:10px 0}
  .row label{width:88px;color:var(--dim);font-size:13px;flex:none}
  .val{width:56px;text-align:right;color:var(--acc);font-variant-numeric:tabular-nums;font-size:13px}
  button{background:var(--acc);color:#fff;border:0;border-radius:8px;padding:9px 18px;font:inherit;font-weight:600;cursor:pointer}
  button:disabled{background:#2b3444;color:#6b7party;cursor:not-allowed;opacity:.6}
  button.ghost{background:transparent;border:1px solid var(--line);color:var(--fg);font-weight:500}
  .btnrow{display:flex;gap:10px;margin-top:14px;flex-wrap:wrap}
  .hint{font-size:12px;color:var(--dim);margin-top:8px}
  .hint.warn{color:var(--warn)}
  .hint.err{color:var(--err)}
  .hint.ok{color:var(--ok)}
  audio{width:100%;margin-top:12px}
  .voices{display:flex;flex-wrap:wrap;gap:8px;margin-top:8px}
  .chip{background:#0c0e13;border:1px solid var(--line);border-radius:20px;padding:5px 12px;font-size:13px;cursor:pointer}
  .chip:hover{border-color:var(--acc)}
  .tag{display:inline-block;background:#0c0e13;border:1px solid var(--line);border-radius:6px;padding:1px 7px;font-size:12px;color:var(--dim);margin-left:6px}
  #log{font-size:12px;color:var(--dim);margin-top:10px;white-space:pre-wrap;max-height:90px;overflow:auto}
</style></head><body>
<div class="wrap">
  <h1>声音实验室</h1>
  <div class="sub">参考音频 + 它的文字 → 任意文字用这个声音念出来。全部在本机跑。</div>

  <div class="grid">
    <div class="card">
      <h2>① 参考声音</h2>
      <div class="drop" id="drop">
        <div>把音频拖到这里，或<b>点击选择</b></div>
        <div style="font-size:12px;margin-top:6px">wav / m4a / mp3，3–10 秒最好</div>
      </div>
      <input type="file" id="file" accept="audio/*" hidden>
      <div class="btnrow">
        <button class="ghost" id="rec">● 录一段</button>
        <button class="ghost" id="reuse">用上次的</button>
      </div>
      <div class="hint" id="refinfo">还没选参考音频</div>
      <div style="margin-top:14px">
        <div style="font-size:13px;color:var(--dim);margin-bottom:6px">这段音频里说的是什么（必须一字不差）</div>
        <textarea id="promptText" placeholder="点上面的「转写成文字」，或自己填"></textarea>
      </div>
      <div class="btnrow"><button id="asr">转写成文字</button></div>
      <div class="hint" id="asrinfo"></div>
    </div>

    <div class="card">
      <h2>② 要它说什么</h2>
      <textarea id="text" style="min-height:110px" placeholder="随便写，比如：今天天气不错，我们出去走走吧。">今天天气不错，我们出去走走吧。</textarea>
      <div class="row"><label>语速</label><input type="range" id="speed" min="0.7" max="1.4" step="0.05" value="1"><div class="val" id="speedv">1.00</div></div>
      <div class="row"><label>稳定度</label><input type="range" id="temp" min="0.3" max="1.2" step="0.05" value="0.7"><div class="val" id="tempv">0.70</div></div>
      <div class="hint">语速 1.0 = 参考音频本人的语速；稳定度越低越稳、越高越活</div>
      <div class="btnrow">
        <button id="go">合成</button>
        <button class="ghost" id="save">存进声音库</button>
      </div>
      <div class="hint" id="status"></div>
      <audio id="player" controls hidden></audio>
      <div class="btnrow" id="dlrow" hidden><a id="dl" download="voice.wav"><button class="ghost">下载 wav</button></a></div>
      <div id="log"></div>
    </div>
  </div>

  <div class="card" style="margin-top:16px">
    <h2>③ 声音库</h2>
    <div class="voices" id="voiceList"><span class="hint">还没有存过的声音</span></div>
  </div>
</div>

<script>
const $ = id => document.getElementById(id);
let refBlob = null, refName = '', refData = null, lastUrl = null;

const log = m => { $('log').textContent = m; };

// ---------- 任意音频 → 32k 单声道 wav（浏览器解码，服务端不依赖 ffmpeg）
async function toWav(blob){
  const buf = await blob.arrayBuffer();
  const ctx = new OfflineAudioContext(1, 1, 32000);
  const audio = await ctx.decodeAudioData(buf);
  // 重采样到 32k：用 OfflineAudioContext 再跑一遍
  const target = 32000;
  const off = new OfflineAudioContext(1, Math.ceil(audio.duration * target), target);
  const src = off.createBufferSource(); src.buffer = audio; src.connect(off.destination); src.start();
  const rendered = await off.startRendering();
  const data = rendered.getChannelData(0);
  const pcm = new Int16Array(data.length);
  for (let i=0;i<data.length;i++){ const s=Math.max(-1,Math.min(1,data[i])); pcm[i]= s<0 ? s*0x8000 : s*0x7fff; }
  const hdr = new ArrayBuffer(44), v = new DataView(hdr);
  const ws = (o,s)=>{ for(let i=0;i<s.length;i++) v.setUint8(o+i, s.charCodeAt(i)); };
  ws(0,'RIFF'); v.setUint32(4, 36+pcm.byteLength, true); ws(8,'WAVE');
  ws(12,'fmt '); v.setUint32(16,16,true); v.setUint16(20,1,true); v.setUint16(22,1,true);
  v.setUint32(24,target,true); v.setUint32(28,target*2,true); v.setUint16(32,2,true); v.setUint16(34,16,true);
  ws(36,'data'); v.setUint32(40, pcm.byteLength, true);
  return new Blob([hdr, pcm], {type:'audio/wav'});
}
const b64 = blob => new Promise(r=>{ const fr=new FileReader(); fr.onload=()=>r(fr.result); fr.readAsDataURL(blob); });

async function useBlob(blob, name){
  $('refinfo').textContent = '正在处理…';
  try{
    const wav = await toWav(blob);
    refBlob = wav; refName = name || '上传的音频';
    refData = await b64(wav);
    const secs = (wav.size - 44) / 2 / 32000;
    let cls = '', tip = '';
    if (secs < 3){ cls='warn'; tip='（太短，合成会很飘，建议 3 秒以上）'; }
    else if (secs > 10){ cls='warn'; tip='（太长，模型会截断，建议 10 秒以内）'; }
    $('refinfo').className = 'hint ' + (cls||'ok');
    $('refinfo').textContent = `已就绪：${refName} · ${secs.toFixed(1)} 秒${tip}`;
    lang_auto_asr();
  }catch(e){ $('refinfo').className='hint err'; $('refinfo').textContent='这个文件解不开：'+e.message; }
}

// ---------- 上传 / 拖拽 / 录音
$('drop').onclick = ()=> $('file').click();
$('file').onchange = e => { const f=e.target.files[0]; if(f) useBlob(f, f.name); };
['dragenter','dragover'].forEach(ev=>$('drop').addEventListener(ev,e=>{e.preventDefault();$('drop').classList.add('over');}));
['dragleave','drop'].forEach(ev=>$('drop').addEventListener(ev,e=>{e.preventDefault();$('drop').classList.remove('over');}));
$('drop').addEventListener('drop', e=>{ const f=e.dataTransfer.files[0]; if(f) useBlob(f,f.name); });

let rec=null, chunks=[];
$('rec').onclick = async ()=>{
  if(rec && rec.state==='recording'){ rec.stop(); return; }
  try{
    const stream = await navigator.mediaDevices.getUserMedia({audio:true});
    chunks=[]; rec = new MediaRecorder(stream);
    rec.ondataavailable = e=>chunks.push(e.data);
    rec.onstop = async ()=>{
      stream.getTracks().forEach(t=>t.stop());
      $('rec').textContent='● 录一段';
      const blob = new Blob(chunks, {type: rec.mimeType});
      await useBlob(blob, '刚才录的');
    };
    rec.start(); $('rec').textContent='■ 停止';
  }catch(e){ $('refinfo').className='hint err'; $('refinfo').textContent='录音打不开：'+e.message+'（要用 localhost 或 https 打开）'; }
};
$('reuse').onclick = async ()=>{
  const r = await fetch('/api/last'); const j = await r.json();
  if(j.ok){ refBlob = null; refData = j.data; refName='上次用的'; $('refinfo').className='hint ok'; $('refinfo').textContent='已载入上次的参考音频'; $('promptText').value=j.promptText||''; }
  else { $('refinfo').className='hint warn'; $('refinfo').textContent='还没有上次的记录'; }
};

// ---------- 转写
async function lang_auto_asr(){
  const t = $('promptText').value.trim();
  if(t) return;  // 已经有文字就不自动覆盖
  $('asrinfo').textContent = '自动转写中…（第一次要加载模型，约 30 秒）';
  await doAsr(true);
}
$('asr').onclick = ()=> doAsr(false);
async function doAsr(silent){
  if(!refData){ if(!silent){$('asrinfo').className='hint warn'; $('asrinfo').textContent='先选一段参考音频';} return; }
  try{
    const r = await fetch('/api/asr', {method:'POST', headers:{'content-type':'application/json'}, body: JSON.stringify({audio: refData})});
    const j = await r.json();
    if(j.ok){ $('promptText').value = j.text; $('asrinfo').className='hint ok'; $('asrinfo').textContent='转写完成，核对一下有没有错字'; }
    else { $('asrinfo').className='hint err'; $('asrinfo').textContent = j.error; }
  }catch(e){ $('asrinfo').className='hint err'; $('asrinfo').textContent='转写失败：'+e.message; }
}

// ---------- 合成
$('speed').oninput = ()=> $('speedv').textContent = (+$('speed').value).toFixed(2);
$('temp').oninput  = ()=> $('tempv').textContent  = (+$('temp').value).toFixed(2);

$('go').onclick = async ()=>{
  if(!refData){ $('status').className='hint warn'; $('status').textContent='先选一段参考音频'; return; }
  const pt = $('promptText').value.trim();
  if(!pt){ $('status').className='hint warn'; $('status').textContent='参考音频的文字还空着，先转写或手填'; return; }
  const text = $('text').value.trim();
  if(!text){ $('status').className='hint warn'; $('status').textContent='要合成的文字是空的'; return; }
  $('go').disabled = true; $('status').className='hint'; $('status').textContent='合成中…';
  const t0 = performance.now();
  try{
    const r = await fetch('/api/tts', {method:'POST', headers:{'content-type':'application/json'},
      body: JSON.stringify({audio: refData, promptText: pt, text, speed: +$('speed').value, temperature: +$('temp').value})});
    const j = await r.json();
    if(!j.ok) throw new Error(j.error);
    const bytes = atob(j.wav); const arr = new Uint8Array(bytes.length);
    for(let i=0;i<bytes.length;i++) arr[i]=bytes.charCodeAt(i);
    const blob = new Blob([arr], {type:'audio/wav'});
    if(lastUrl) URL.revokeObjectURL(lastUrl);
    lastUrl = URL.createObjectURL(blob);
    $('player').src = lastUrl; $('player').hidden=false; $('player').play();
    $('dl').href = lastUrl;
    $('dlrow').hidden = false;
    $('status').className='hint ok';
    $('status').textContent = `好了 · ${(blob.size/1024).toFixed(0)} KB · ${((performance.now()-t0)/1000).toFixed(1)} 秒`;
  }catch(e){ $('status').className='hint err'; $('status').textContent='失败：'+e.message; }
  $('go').disabled = false;
};

// ---------- 声音库
async function loadVoices(){
  const r = await fetch('/api/voices'); const j = await r.json();
  const box = $('voiceList');
  if(!j.voices.length){ box.innerHTML='<span class="hint">还没有存过的声音</span>'; return; }
  box.innerHTML='';
  j.voices.forEach(v=>{
    const el = document.createElement('span');
    el.className='chip';
    el.innerHTML = `${v.name}<span class="tag">${v.seconds}s</span>`;
    el.onclick = async ()=>{
      const rr = await fetch('/api/voice?name='+encodeURIComponent(v.name)); const jj = await rr.json();
      if(jj.ok){ refData = jj.data; refName = v.name; $('promptText').value = jj.promptText;
        $('refinfo').className='hint ok'; $('refinfo').textContent = `已载入「${v.name}」· ${v.seconds} 秒`; }
    };
    box.appendChild(el);
  });
}
$('save').onclick = async ()=>{
  if(!refData){ $('status').className='hint warn'; $('status').textContent='先选参考音频'; return; }
  const name = prompt('给这个声音起个名字', refName.replace(/\.[^.]+$/,'') || '新声音');
  if(!name) return;
  const r = await fetch('/api/voices', {method:'POST', headers:{'content-type':'application/json'},
    body: JSON.stringify({name, audio: refData, promptText: $('promptText').value.trim()})});
  const j = await r.json();
  $('status').className = j.ok ? 'hint ok' : 'hint err';
  $('status').textContent = j.ok ? `已存进声音库：${name}` : j.error;
  loadVoices();
};
loadVoices();
</script></body></html>
"""


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _json(self, obj, code=200):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("content-type", "application/json; charset=utf-8")
        self.send_header("content-length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _body(self):
        n = int(self.headers.get("content-length") or 0)
        return json.loads(self.rfile.read(n) or b"{}")

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            body = PAGE.encode("utf-8")
            self.send_response(200)
            self.send_header("content-type", "text/html; charset=utf-8")
            self.send_header("content-length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if self.path == "/api/voices":
            out = []
            for meta in sorted(VOICES.glob("*.json")):
                try:
                    d = json.loads(meta.read_text("utf-8"))
                    wav = VOICES / f"{d['name']}.wav"
                    if wav.exists():
                        info = wav_info(wav) or {}
                        out.append({"name": d["name"], "seconds": info.get("seconds", 0)})
                except Exception:
                    continue
            self._json({"ok": True, "voices": out})
            return
        if self.path.startswith("/api/voice?"):
            from urllib.parse import parse_qs, urlparse
            name = (parse_qs(urlparse(self.path).query).get("name") or [""])[0]
            wav = VOICES / f"{name}.wav"
            meta = VOICES / f"{name}.json"
            if not wav.exists():
                self._json({"ok": False, "error": "没有这个声音"}, 404)
                return
            data = "data:audio/wav;base64," + base64.b64encode(wav.read_bytes()).decode()
            pt = ""
            if meta.exists():
                pt = json.loads(meta.read_text("utf-8")).get("promptText", "")
            self._json({"ok": True, "data": data, "promptText": pt})
            return
        if self.path == "/api/last":
            p = UPLOADS / "last.wav"
            m = UPLOADS / "last.json"
            if p.exists():
                data = "data:audio/wav;base64," + base64.b64encode(p.read_bytes()).decode()
                pt = json.loads(m.read_text("utf-8")).get("promptText", "") if m.exists() else ""
                self._json({"ok": True, "data": data, "promptText": pt})
            else:
                self._json({"ok": False})
            return
        self._json({"ok": False, "error": "not found"}, 404)

    def do_POST(self):
        try:
            if self.path == "/api/asr":
                body = self._body()
                raw = decode_data_url(body.get("audio", ""))
                p = UPLOADS / "ref.wav"
                p.write_bytes(raw)
                text = transcribe(p)
                self._json({"ok": True, "text": text})
                return

            if self.path == "/api/tts":
                body = self._body()
                raw = decode_data_url(body.get("audio", ""))
                p = UPLOADS / "ref.wav"
                p.write_bytes(raw)
                info = wav_info(p) or {}
                secs = info.get("seconds", 0)
                if secs < 1.0:
                    self._json({"ok": False, "error": f"参考音频只有 {secs} 秒，太短了"})
                    return
                wav = tts(
                    body.get("text", "").strip(),
                    p,
                    body.get("promptText", "").strip(),
                    float(body.get("speed") or 1.0),
                    float(body.get("temperature") or 0.7),
                )
                # 留一份给「用上次的」
                (UPLOADS / "last.wav").write_bytes(raw)
                (UPLOADS / "last.json").write_text(
                    json.dumps({"promptText": body.get("promptText", "")}, ensure_ascii=False), "utf-8"
                )
                self._json({"ok": True, "wav": base64.b64encode(wav).decode()})
                return

            if self.path == "/api/voices":
                body = self._body()
                name = re.sub(r"[/\\:*?\"<>|]", "_", (body.get("name") or "").strip())[:40]
                if not name:
                    self._json({"ok": False, "error": "名字空着"})
                    return
                raw = decode_data_url(body.get("audio", ""))
                (VOICES / f"{name}.wav").write_bytes(raw)
                (VOICES / f"{name}.json").write_text(
                    json.dumps({"name": name, "promptText": body.get("promptText", "")}, ensure_ascii=False), "utf-8"
                )
                self._json({"ok": True})
                return
        except Exception as e:
            self._json({"ok": False, "error": f"{type(e).__name__}: {e}"})
            return
        self._json({"ok": False, "error": "not found"}, 404)


def main():
    import socket

    # 预热 whisper：不预热的话第一次点转写要干等半分钟，体验很差
    threading.Thread(target=lambda: (get_whisper(), print("[lab] whisper 就绪", flush=True)), daemon=True).start()

    srv = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    print(f"[lab] http://127.0.0.1:{PORT}", flush=True)
    try:
        ip = socket.gethostbyname(socket.gethostname())
        if not ip.startswith("127."):
            print(f"[lab] 局域网（手机也能开）：http://{ip}:{PORT}", flush=True)
    except Exception:
        pass
    srv.serve_forever()


if __name__ == "__main__":
    main()
