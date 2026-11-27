#!/usr/bin/env python3
"""
一键 AI 字幕精校脚本（补标点断句 + 地道中文翻译 + IPA 音标 + 重点词提取）
原生支持 Google Gemini API（gemini-2.5-flash），同时兼容 DeepSeek / OpenAI！
精校结果自动缓存在外接硬盘 episodes/<标题>.polished.json，永不重复计费。

用法示例：
  GEMINI_API_KEY="AIza..." python3 scripts/ai_polish_subtitles.py
  GEMINI_API_KEY="AIza..." python3 scripts/ai_polish_subtitles.py --only "Kendall"
"""

import argparse
import json
import os
import re
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EPISODES_DIR = ROOT / "content" / "episodes"
LOCAL_JS = ROOT / "js" / "local_episodes.js"

SYSTEM_PROMPT = (
    "你是资深英语精听课程编辑（对标 SayBreeze 品质）。给定一批来自 YouTube 的字幕句子（可能缺少英文标点、大小写、中文翻译或音标），"
    "请保持每条的 id 不变，做 4 项精校并返回严格 JSON：{\"items\": [{\"id\": 1, \"en\": \"...\", \"zh\": \"...\", \"ipa\": \"/.../\", \"highlights\": [{\"text\": \"...\", \"key\": \"...\", \"chip\": \"orange|indigo|pink\"}]}]}。\n"
    "严格要求：\n"
    "1. en：补全准确的英文标点符号（句号、问号、感叹号、逗号）与首字母大写，不改变原意，不删除原词；\n"
    "2. zh：提供自然、地道、口语化的简体中文翻译；\n"
    "3. ipa：提供整句美式 IPA 音标（用 /.../ 包裹）；\n"
    "4. highlights：为每句挑出 1–2 个最值得中国学习者掌握的核心词或地道短语（text 必须严格一字不差地出现在精校后的 en 中，不要挑人名或无意义虚词；chip：orange=实用实词，indigo=短语搭配，pink=高频地道表达）。"
)


def call_gemini(batch_json: str, api_key: str, model: str = "gemini-3.8-flash"):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    payload = {
        "systemInstruction": {"parts": [{"text": SYSTEM_PROMPT}]},
        "contents": [{"role": "user", "parts": [{"text": batch_json}]}],
        "generationConfig": {
            "temperature": 0.2,
            "responseMimeType": "application/json",
        },
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "x-goog-api-key": api_key},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        body = json.loads(resp.read().decode("utf-8"))
        text = body["candidates"][0]["content"]["parts"][0]["text"]
        return json.loads(text)


def call_openai_compat(batch_json: str, api_key: str, base_url: str, model: str):
    url = base_url.rstrip("/") + "/chat/completions"
    payload = {
        "model": model,
        "temperature": 0.2,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": batch_json},
        ],
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        body = json.loads(resp.read().decode("utf-8"))
        return json.loads(body["choices"][0]["message"]["content"])


def polish_batch(batch, provider, api_key, base_url, model):
    compact_in = [{"id": s["id"], "en": s["en"], "zh": s["zh"]} for s in batch]
    batch_json = json.dumps(compact_in, ensure_ascii=False)

    last_err = None
    fallback_models = [
        model,
        "gemini-2.5-flash-lite",
        "gemini-3.1-flash-lite",
        "gemini-flash-latest",
        "gemini-3.5-flash-lite",
        "gemini-3.5-flash",
    ]
    for attempt in range(len(fallback_models)):
        cur_model = fallback_models[attempt] if provider == "gemini" else model
        try:
            if provider == "gemini":
                res = call_gemini(batch_json, api_key, cur_model)
            else:
                res = call_openai_compat(batch_json, api_key, base_url, model)
            items_list = res if isinstance(res, list) else (res.get("items", []) if isinstance(res, dict) else [])
            by_id = {item["id"]: item for item in items_list if isinstance(item, dict) and "id" in item}
            out = []
            for s in batch:
                p = by_id.get(s["id"])
                if p:
                    new_s = dict(s)
                    new_s["en"] = p.get("en") or s["en"]
                    new_s["zh"] = p.get("zh") or s["zh"]
                    new_s["ipa"] = p.get("ipa") or s.get("ipa", "")
                    hls = [
                        h for h in (p.get("highlights") or [])
                        if isinstance(h, dict) and h.get("text") and h["text"] in new_s["en"]
                    ]
                    if hls:
                        new_s["highlights"] = hls
                    out.append(new_s)
                else:
                    out.append(s)
            return out
        except Exception as exc:
            last_err = exc
            time.sleep(2 * (attempt + 1))
    print(f"   [warn] 本批精校失败，保留原字幕: {last_err}")
    return None


def main():
    parser = argparse.ArgumentParser(description="使用 Gemini / DeepSeek / OpenAI 一键精校本地剧集字幕")
    parser.add_argument("--only", default="", help="只处理标题包含该关键词的剧集")
    parser.add_argument("--force", action="store_true", help="强制重新精校已缓存的剧集")
    parser.add_argument("--batch-size", type=int, default=35, help="每批处理的句子数")
    args = parser.parse_args()

    gemini_key = os.environ.get("GEMINI_API_KEY")
    deepseek_key = os.environ.get("DEEPSEEK_API_KEY")
    openai_key = os.environ.get("OPENAI_API_KEY") or os.environ.get("LLM_API_KEY")

    if gemini_key:
        provider = "gemini"
        api_key = gemini_key
        base_url = ""
        model = os.environ.get("GEMINI_MODEL", "gemini-flash-lite-latest")
    elif deepseek_key:
        provider = "openai"
        api_key = deepseek_key
        base_url = os.environ.get("LLM_BASE_URL", "https://api.deepseek.com/v1")
        model = os.environ.get("LLM_MODEL", "deepseek-chat")
    elif openai_key:
        provider = "openai"
        api_key = openai_key
        base_url = os.environ.get("LLM_BASE_URL", "https://api.openai.com/v1")
        model = os.environ.get("LLM_MODEL", "gpt-4o-mini")
    else:
        print("请先设置 GEMINI_API_KEY（或 DEEPSEEK_API_KEY / OPENAI_API_KEY）！")
        raise SystemExit(1)

    txt = LOCAL_JS.read_text(encoding="utf-8")
    episodes = json.loads(re.search(r"LOCAL_EPISODES = (\[.*\]);", txt, re.S).group(1))

    print(f"[info] 使用模型：{provider} ({model})")
    for ep in episodes:
        title = ep["title"]
        if args.only and args.only.lower() not in title.lower():
            continue
        # 断点续传：若已有部分缓存，只精校还没补齐 ipa 或 zh 的句子，绝不浪费已完成批次！
        cache_path = EPISODES_DIR / f"{title}.polished.json"
        sents = ep["sentences"]
        if cache_path.exists() and not args.force:
            try:
                cached = json.loads(cache_path.read_text(encoding="utf-8"))
                if len(cached) == len(sents):
                    sents = cached
            except Exception:
                pass

        if len(sents) <= 1:
            print(f"[skip] 无有效字幕：{title}", flush=True)
            continue

        todo_indices = [i for i, s in enumerate(sents) if not s.get("ipa") or not s.get("zh")]
        if not todo_indices and not args.force:
            print(f"[skip] 已 100% 精校：{cache_path.name}", flush=True)
            continue

        target_indices = list(range(len(sents))) if args.force else todo_indices
        print(f"[polish] 正在精校：{title}（待处理 {len(target_indices)}/{len(sents)} 句）...", flush=True)
        index_batches = [target_indices[i : i + args.batch_size] for i in range(0, len(target_indices), args.batch_size)]
        updated = [dict(s) for s in sents]
        succeeded_any = False

        from concurrent.futures import ThreadPoolExecutor, as_completed
        with ThreadPoolExecutor(max_workers=2) as pool:
            fut_map = {
                pool.submit(polish_batch, [updated[idx] for idx in idxs], provider, api_key, base_url, model): idxs
                for idxs in index_batches
            }
            for fut in as_completed(fut_map):
                idxs = fut_map[fut]
                res_batch = fut.result()
                if res_batch is not None and len(res_batch) == len(idxs):
                    for pos, new_s in zip(idxs, res_batch):
                        updated[pos] = new_s
                    succeeded_any = True

        if succeeded_any:
            cache_path.write_text(json.dumps(updated, ensure_ascii=False, indent=2), encoding="utf-8")
            rem = sum(1 for s in updated if not s.get("ipa") or not s.get("zh"))
            print(f"[done] ✅ 已保存进度 -> {cache_path.name}（剩余待补 {rem} 句）", flush=True)

    print("\n✅ 全部精校完成！请运行 python3 scripts/sync_episodes.py 同步到网站。")


if __name__ == "__main__":
    main()
