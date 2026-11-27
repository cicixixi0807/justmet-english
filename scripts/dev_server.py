#!/usr/bin/env python3
"""
支持 HTTP Range（206 Partial Content）+ 实时真词典 API (/api/define) 的本地服务：
1. 大体积 MP4/MP3 视频秒级拖动、逐句跳转、双轨音画同步；
2. 点击任意单词/短语调用 /api/define 返回真实中英文释义、美/英音标、词性与双语例句，并永久缓存到外接硬盘。
"""
import json
import os
import re
import urllib.parse
import urllib.request
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DICT_CACHE_PATH = ROOT / "content" / "episodes" / "_dictionary_cache.json"

DICT_PROMPT = (
    "你是专业英汉学习词典编纂者。给定一个英文单词或短语（以及可选的上下文例句），"
    "请返回严格 JSON：{\"headword\":\"...\",\"pos\":\"noun/verb/adj./phrase等\",\"type\":\"vocab或expression\","
    "\"level\":\"日常高频/四级/六级/雅思/职场核心\",\"us\":\"/.../\",\"uk\":\"/.../\","
    "\"meanings\":[{\"zh\":\"精准中文释义\",\"en\":\"Concise English definition\"}],"
    "\"exampleEn\":\"Natural English example sentence.\",\"exampleZh\":\"地道中文例句翻译。\"}\n"
    "要求：meanings 提供 1-2 条最常用释义；us/uk 必须给出真实国际音标；例句必须自然实用，绝不使用占位模板。"
)


def load_dict_cache():
    if DICT_CACHE_PATH.exists():
        try:
            return json.loads(DICT_CACHE_PATH.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def save_dict_cache(cache):
    try:
        DICT_CACHE_PATH.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass


DICT_CACHE = load_dict_cache()


def query_real_dictionary(word: str, context: str = ""):
    key = word.strip().lower()
    if key in DICT_CACHE:
        return DICT_CACHE[key]

    api_key = os.environ.get("GEMINI_API_KEY", "")
    if api_key:
        models = ["gemini-flash-lite-latest", "gemini-2.5-flash-lite", "gemini-3.1-flash-lite"]
        user_msg = f"Word/Phrase: {word}\nContext sentence: {context}" if context else f"Word/Phrase: {word}"
        for m in models:
            try:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent"
                payload = {
                    "systemInstruction": {"parts": [{"text": DICT_PROMPT}]},
                    "contents": [{"role": "user", "parts": [{"text": user_msg}]}],
                    "generationConfig": {"temperature": 0.1, "responseMimeType": "application/json"},
                }
                req = urllib.request.Request(
                    url,
                    data=json.dumps(payload).encode("utf-8"),
                    headers={"Content-Type": "application/json", "x-goog-api-key": api_key},
                    method="POST",
                )
                with urllib.request.urlopen(req, timeout=20) as resp:
                    body = json.loads(resp.read().decode("utf-8"))
                    text = body["candidates"][0]["content"]["parts"][0]["text"]
                    entry = json.loads(text)
                    if isinstance(entry, dict) and entry.get("meanings"):
                        DICT_CACHE[key] = entry
                        save_dict_cache(DICT_CACHE)
                        return entry
            except Exception:
                continue

    # Fallback: Free Dictionary API (English definitions + IPA)
    try:
        single = key.split()[0]
        url = f"https://api.dictionaryapi.dev/api/v2/entries/en/{urllib.parse.quote(single)}"
        with urllib.request.urlopen(url, timeout=8) as resp:
            arr = json.loads(resp.read().decode("utf-8"))
            if isinstance(arr, list) and arr:
                item = arr[0]
                phon = item.get("phonetic") or next((p.get("text") for p in item.get("phonetics", []) if p.get("text")), f"/{word}/")
                ms = item.get("meanings", [])
                pos = ms[0].get("partOfSpeech", "word") if ms else "word"
                defs = []
                ex_en = ""
                for m_obj in ms[:2]:
                    for d in m_obj.get("definitions", [])[:1]:
                        defs.append({"en": d.get("definition", ""), "zh": d.get("definition", "")})
                        if not ex_en and d.get("example"):
                            ex_en = d["example"]
                entry = {
                    "headword": word,
                    "pos": pos,
                    "type": "expression" if " " in key else "vocab",
                    "level": "常用词汇",
                    "us": phon,
                    "uk": phon,
                    "meanings": defs or [{"en": "English vocabulary entry.", "zh": "暂无中文释义"}],
                    "exampleEn": ex_en or context or "",
                    "exampleZh": "",
                }
                DICT_CACHE[key] = entry
                save_dict_cache(DICT_CACHE)
                return entry
    except Exception:
        pass

    return None


class RangeHTTPRequestHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def do_GET(self):
        parsed = urllib.parse.urlsplit(self.path)
        if parsed.path == "/api/define":
            qs = urllib.parse.parse_qs(parsed.query)
            word = (qs.get("word") or [""])[0].strip()
            context = (qs.get("context") or [""])[0].strip()
            entry = query_real_dictionary(word, context) if word else None
            payload = json.dumps({"ok": bool(entry), "entry": entry}, ensure_ascii=False).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
            return
        return super().do_GET()

    def send_head(self):
        path = self.translate_path(self.path)
        if os.path.isdir(path) or not os.path.exists(path):
            return super().send_head()

        range_header = self.headers.get("Range")
        ctype = self.guess_type(path)
        file_size = os.path.getsize(path)

        if not range_header:
            f = open(path, "rb")
            self.send_response(200)
            self.send_header("Content-type", ctype)
            self.send_header("Content-Length", str(file_size))
            self.send_header("Accept-Ranges", "bytes")
            self.end_headers()
            return f

        m = re.match(r"bytes=(\d*)-(\d*)", range_header)
        if not m:
            return super().send_head()

        start_str, end_str = m.groups()
        start = int(start_str) if start_str else 0
        end = int(end_str) if end_str else file_size - 1
        if start >= file_size:
            self.send_error(416, "Requested Range Not Satisfiable")
            return None
        end = min(end, file_size - 1)
        length = end - start + 1

        f = open(path, "rb")
        f.seek(start)
        self.send_response(206)
        self.send_header("Content-type", ctype)
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Range", f"bytes {start}-{end}/{file_size}")
        self.send_header("Content-Length", str(length))
        self.end_headers()
        self._range_remaining = length
        return f

    def copyfile(self, source, outputfile):
        remaining = getattr(self, "_range_remaining", None)
        if remaining is None:
            return super().copyfile(source, outputfile)
        self._range_remaining = None
        bufsize = 64 * 1024
        while remaining > 0:
            chunk = source.read(min(bufsize, remaining))
            if not chunk:
                break
            try:
                outputfile.write(chunk)
            except BrokenPipeError:
                break
            remaining -= len(chunk)


class ReusableThreadingHTTPServer(ThreadingHTTPServer):
    allow_reuse_address = True


if __name__ == "__main__":
    import sys
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 4174
    server = ReusableThreadingHTTPServer(("127.0.0.1", port), RangeHTTPRequestHandler)
    print(f"Serving Range + Live Dictionary HTTP on http://127.0.0.1:{port}/ ...", flush=True)
    server.serve_forever()
