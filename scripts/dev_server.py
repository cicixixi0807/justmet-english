#!/usr/bin/env python3
"""
支持 HTTP Range（206 Partial Content）+ 实时真词典 API (/api/define) 的本地服务：
1. 大体积 MP4/MP3 视频秒级拖动、逐句跳转、双轨音画同步；
2. 点击任意单词或完整短语调用 /api/define，依次走：
   ① 外接硬盘持久化缓存（_dictionary_cache.json）
   ② Gemini 实时词典（需 GEMINI_API_KEY）
   ③ 国内直连可用兜底：有道词典 API（支持整段英文短语，如 show of hands / used to be / at least / first time）
   ④ Free Dictionary API（仅限单词级兜底，绝不把短语截断为第一个单词）
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


def query_youdao_domestic(word: str, context: str = ""):
    """国内直连可用的有道词典兜底（支持完整英文短语整段查询）"""
    q = urllib.parse.quote(word.strip())
    headers = {"User-Agent": "Mozilla/5.0"}
    # 1) 有道 suggest 接口（国内稳定、响应快、原生支持短语）
    try:
        url = f"https://dict.youdao.com/suggest?num=3&ver=3.0&doctype=json&cache=false&le=en&q={q}"
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=6) as resp:
            body = json.loads(resp.read().decode("utf-8"))
            entries = (body.get("data") or {}).get("entries") or []
            # 优先精确匹配完整词/短语
            exact = next((e for e in entries if (e.get("entry") or "").strip().lower() == word.strip().lower()), None)
            chosen = exact or (entries[0] if entries else None)
            if chosen and chosen.get("explain"):
                expl = chosen["explain"].strip()
                # 拆分词性与中文释义
                pos_m = re.match(r"^([a-z]+\.)\s*(.+)$", expl)
                pos = pos_m.group(1) if pos_m else ("phrase" if " " in word.strip() else "word")
                zh = pos_m.group(2) if pos_m else expl
                return {
                    "headword": word.strip(),
                    "pos": pos,
                    "type": "expression" if " " in word.strip() else "vocab",
                    "level": "有道词典",
                    "us": "",
                    "uk": "",
                    "meanings": [{"zh": zh, "en": ""}],
                    "exampleEn": context or "",
                    "exampleZh": "",
                }
    except Exception:
        pass
    return None


def query_real_dictionary(word: str, context: str = ""):
    key = word.strip().lower()
    if key in DICT_CACHE:
        cached = DICT_CACHE[key]
        # 避免历史旧缓存里把英文释义直接填进 zh 的脏条目继续污染短语
        if isinstance(cached, dict) and cached.get("meanings"):
            return cached, "cache", ""

    errors = []
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
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
                with urllib.request.urlopen(req, timeout=10) as resp:
                    body = json.loads(resp.read().decode("utf-8"))
                    text = body["candidates"][0]["content"]["parts"][0]["text"]
                    entry = json.loads(text)
                    if isinstance(entry, dict) and entry.get("meanings"):
                        entry["headword"] = entry.get("headword") or word.strip()
                        DICT_CACHE[key] = entry
                        save_dict_cache(DICT_CACHE)
                        return entry, "gemini", ""
            except Exception as exc:
                errors.append(f"gemini({m}): {type(exc).__name__}")
                continue
    else:
        errors.append("未配置 GEMINI_API_KEY")

    # 国内可用兜底：有道词典（支持完整英文短语整段查询）
    yd = query_youdao_domestic(word, context)
    if yd:
        DICT_CACHE[key] = yd
        save_dict_cache(DICT_CACHE)
        return yd, "youdao", ""
    errors.append("youdao: 不可达或未收录")

    # 仅对单个英文单词尝试 Free Dictionary API（绝不把短语截断成第一个单词）
    if " " not in key:
        try:
            url = f"https://api.dictionaryapi.dev/api/v2/entries/en/{urllib.parse.quote(key)}"
            with urllib.request.urlopen(url, timeout=6) as resp:
                arr = json.loads(resp.read().decode("utf-8"))
                if isinstance(arr, list) and arr:
                    item = arr[0]
                    phon = item.get("phonetic") or next((p.get("text") for p in item.get("phonetics", []) if p.get("text")), "")
                    ms = item.get("meanings", [])
                    pos = ms[0].get("partOfSpeech", "word") if ms else "word"
                    defs = []
                    ex_en = ""
                    for m_obj in ms[:2]:
                        for d in m_obj.get("definitions", [])[:1]:
                            en_def = d.get("definition", "")
                            if en_def:
                                defs.append({"en": en_def, "zh": ""})
                            if not ex_en and d.get("example"):
                                ex_en = d["example"]
                    if defs:
                        entry = {
                            "headword": word.strip(),
                            "pos": pos,
                            "type": "vocab",
                            "level": "英英词典兜底",
                            "us": phon,
                            "uk": phon,
                            "meanings": defs,
                            "exampleEn": ex_en or context or "",
                            "exampleZh": "",
                        }
                        DICT_CACHE[key] = entry
                        save_dict_cache(DICT_CACHE)
                        return entry, "dictionaryapi", ""
        except Exception as exc:
            errors.append(f"dictionaryapi: {type(exc).__name__}")

    return None, "none", "；".join(errors)


class RangeHTTPRequestHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def do_GET(self):
        parsed = urllib.parse.urlsplit(self.path)
        if parsed.path == "/api/define":
            qs = urllib.parse.parse_qs(parsed.query)
            word = (qs.get("word") or [""])[0].strip()
            context = (qs.get("context") or [""])[0].strip()
            if not word:
                payload = json.dumps({"ok": False, "entry": None, "error": "缺少查询词"}, ensure_ascii=False).encode("utf-8")
            else:
                entry, source, err = query_real_dictionary(word, context)
                payload = json.dumps(
                    {"ok": bool(entry), "entry": entry, "source": source, "error": err},
                    ensure_ascii=False,
                ).encode("utf-8")
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
