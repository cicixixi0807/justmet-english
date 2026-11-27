#!/usr/bin/env python3
"""
零配置智能同步脚本：
直接把视频(.mp4/.mov/.webm)、音频(.mp3/.m4a/.wav)、字幕(.srt/.vtt/.txt)、封面(.jpg/.png/.webp)
全部丢进 content/episodes/（外接硬盘 /Volumes/刚认识不久/JustMet英语素材库/episodes）即可！
无需新建子文件夹，无需写 meta.json，脚本会自动：
  1. 按同名文件自动把视频/音频 + 字幕（支持单双语字幕或 .en.srt + .zh.srt 自动合并）+ 封面归为同一集；
  2. 根据文件名与字幕语速/词汇自动判断 1–5 星难度、8 大分类标签与博主名；
  3. 同时兼容子文件夹模式，生成 js/local_episodes.js 供网站直接播放。

用法：
  python3 scripts/sync_episodes.py
  python3 scripts/sync_episodes.py --media-base-url https://cdn.example.com/episodes
"""

import argparse
import html
import json
import re
import struct
from datetime import datetime
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parent.parent
EPISODES_DIR = ROOT / "content" / "episodes"
OUTPUT_JS = ROOT / "js" / "local_episodes.js"

VIDEO_EXTS = {".mp4", ".webm", ".mov", ".m4v"}
AUDIO_EXTS = {".mp3", ".m4a", ".wav", ".ogg", ".aac"}
SUB_EXTS = {".srt", ".vtt", ".txt"}
IMG_EXTS = {".jpg", ".jpeg", ".png", ".webp"}

KNOWN_KEYWORDS = [
    ("on the same page", "pink"),
    ("break the ice", "pink"),
    ("walk through", "indigo"),
    ("circle back", "indigo"),
    ("touch base", "indigo"),
    ("small talk", "indigo"),
    ("figure out", "indigo"),
    ("hit it off", "pink"),
    ("push back", "indigo"),
    ("stand out", "pink"),
    ("catch up", "indigo"),
    ("wing it", "orange"),
    ("overthinking", "orange"),
    ("bandwidth", "orange"),
    ("takeaway", "pink"),
    ("boundary", "pink"),
    ("burnout", "orange"),
    ("swamped", "orange"),
    ("genuine", "orange"),
    ("aligned", "orange"),
    ("low-key", "orange"),
    ("vibe", "orange"),
]

TAG_RULES = [
    ("购物", ["grocery", "shop", "shopping", "store", "mall", "buy", "bag", "haul", "超市", "购物", "买"]),
    ("美食", ["food", "coffee", "restaurant", "cook", "cooking", "order", "eat", "cafe", "bakery", "美食", "点餐", "咖啡", "做饭"]),
    ("旅行", ["travel", "trip", "airport", "hotel", "city", "vacation", "vlog", "tokyo", "paris", "nyc", "旅行", "旅游", "出行"]),
    ("名人访谈", ["vogue", "73 questions", "interview", "jensen", "jennie", "emma", "taylor", "kendall", "eileen", "访谈", "采访", "谷爱凌", "黄仁勋"]),
    ("个人成长", ["ted", "imposter", "confidence", "boundary", "boundaries", "habit", "growth", "mindset", "overthinking", "podcast", "成长", "自信", "边界", "内耗"]),
    ("日常对话", ["conversation", "small talk", "speak", "talk", "chat", "dialogue", "对话", "寒暄", "口语"]),
    ("生活英语", ["vocabulary", "phrases", "english", "lesson", "teacher", "vanessa", "lucy", "ariannita", "生活英语", "词汇"]),
    ("生活", ["living alone", "morning routine", "daily", "life", "apartment", "home", "day in my life", "独居", "日常", "生活"]),
]

SPEAKER_RULES = [
    ("Ariannita la Gringa", ["ariannita", "la gringa", "downtown vocabulary", "english lesson at the airport", "english phrases for ordering food", "grocery shopping with your english teacher", "how to order coffee in english", "how to order fast food", "shopping at the best mall"]),
    ("Speak English With Vanessa", ["vanessa", "speakenglishwithvanessa", "daily life english", "grocery store vocabulary", "real life english around the city", "speak american english around town"]),
    ("Michelle Choi", ["michelle choi", "living alone diaries", "homebody on holiday", "homebody in new york", "dobby"]),
    ("English with Lucy", ["english with lucy", "lucy"]),
    ("Jenn Im", ["jenn im"]),
    ("Eva Meloche", ["eva meloche"]),
    ("Sydney Serena", ["sydney serena"]),
    ("Taylor R", ["taylor r"]),
    ("Emma Watson · Vogue", ["emma watson"]),
    ("Kendall Jenner · Vogue", ["kendall jenner"]),
    ("Taylor Swift · Vogue", ["taylor swift"]),
    ("Vogue", ["vogue", "73 questions", "in the bag"]),
    ("Celeste Headlee · TED", ["celeste headlee"]),
    ("Chris Fenning · TED", ["chris fenning"]),
    ("TED-Ed", ["imposter syndrome", "ted-ed", "maya angelou"]),
    ("TED", ["ted", "tedx"]),
    ("Jensen Huang", ["jensen", "黄仁勋"]),
    ("Ali Abdaal", ["ali abdaal"]),
    ("Jay Shetty", ["jay shetty"]),
    ("谷爱凌", ["eileen gu", "谷爱凌"]),
]

REGION_RULES = [
    ("英国", ["emma watson", "lucy", "ali abdaal", "london", "british", "victoria beckham"]),
    ("加拿大", ["bob the canadian", "canada"]),
]

COVER_GRADIENTS = [
    "linear-gradient(135deg, #F4D9D0 0%, #D98B7A 100%)",
    "linear-gradient(135deg, #F7E1D7 0%, #E6A995 100%)",
    "linear-gradient(135deg, #E7D8C9 0%, #B88B72 100%)",
    "linear-gradient(135deg, #F0D5DC 0%, #C77C8E 100%)",
    "linear-gradient(135deg, #DCE7E2 0%, #6D9A86 100%)",
    "linear-gradient(135deg, #DDE4F0 0%, #6B82A8 100%)",
]


def normalize_stem(filename: str) -> str:
    """去掉扩展名、yt-dlp 格式后缀（.f401 / .f140-10）及常见语言后缀（.en / .zh-Hans），把同一集文件归为一组"""
    stem = Path(filename).stem
    # 先去掉 yt-dlp 音画流后缀如 .f401 / .f616 / .f140-10 / .f399-sr
    stem = re.sub(r"\.f\d+(?:-[a-z0-9]+)?$", "", stem, flags=re.IGNORECASE)
    # 再去掉语言/封面后缀
    stem = re.sub(
        r"[\._\-](en|en-us|en-gb|zh|zh-cn|zh-hans|zh-hant|chs|cht|bilingual|sub|subtitle|cover|thumb)$",
        "",
        stem,
        flags=re.IGNORECASE,
    )
    return stem.strip()


def parse_timestamp(ts: str) -> float:
    ts = ts.strip().replace(",", ".")
    parts = ts.split(":")
    if len(parts) == 3:
        h, m, s = parts
        return int(h) * 3600 + int(m) * 60 + float(s)
    if len(parts) == 2:
        m, s = parts
        return int(m) * 60 + float(s)
    return 0.0


STOP_WORDS = {
    "about", "above", "after", "again", "against", "almost", "already", "always", "among", "another",
    "anyone", "anything", "around", "because", "become", "before", "being", "below", "between", "cannot",
    "could", "doing", "during", "either", "enough", "every", "everyone", "everything", "first", "found",
    "getting", "going", "gonna", "great", "having", "hello", "heres", "however", "inside", "instead",
    "into", "just", "knowing", "later", "least", "leave", "little", "looking", "making", "maybe", "might",
    "never", "nothing", "often", "other", "others", "outside", "people", "person", "place", "please",
    "pretty", "quite", "really", "right", "saying", "second", "should", "since", "small", "someone",
    "something", "sometimes", "sorry", "start", "still", "stuff", "thank", "thanks", "thats", "their",
    "theirs", "there", "these", "theyre", "thing", "things", "think", "thinking", "those", "though",
    "through", "today", "together", "tomorrow", "trying", "under", "until", "using", "usually", "very",
    "video", "wanna", "wanted", "wants", "watch", "watching", "welcome", "where", "which", "while",
    "whose", "without", "would", "youll", "youre", "yours", "youtube", "channel", "guys"
}

USEFUL_PHRASES = [
    ("welcome back", "indigo"),
    ("let's go", "indigo"),
    ("a lot of", "indigo"),
    ("make sure", "indigo"),
    ("find out", "indigo"),
    ("pick up", "indigo"),
    ("check out", "indigo"),
    ("looking for", "indigo"),
    ("would like", "indigo"),
    ("how much", "indigo"),
    ("excuse me", "pink"),
    ("for here or to go", "pink"),
    ("on the side", "pink"),
    ("out of stock", "pink"),
    ("in season", "pink"),
    ("go ahead", "indigo"),
    ("kind of", "indigo"),
    ("sort of", "indigo"),
    ("hang out", "indigo"),
    ("end up", "indigo"),
    ("come up with", "indigo"),
    ("get used to", "pink"),
    ("pay attention", "pink"),
    ("in charge of", "pink"),
]


def find_highlights(en_text: str):
    found = []
    used_spans = []
    lower = en_text.lower()

    def overlaps(s, e):
        return any(not (e <= us or s >= ue) for us, ue in used_spans)

    # 1) 优先匹配核心短语与地道表达
    for phrase, chip in KNOWN_KEYWORDS + USEFUL_PHRASES:
        idx = lower.find(phrase)
        if idx != -1 and not overlaps(idx, idx + len(phrase)):
            # 确保单词边界
            before_ok = idx == 0 or not lower[idx - 1].isalpha()
            after_ok = idx + len(phrase) == len(lower) or not lower[idx + len(phrase)].isalpha()
            if before_ok and after_ok:
                found.append({"text": en_text[idx : idx + len(phrase)], "key": phrase, "chip": chip})
                used_spans.append((idx, idx + len(phrase)))
        if len(found) >= 3:
            return found

    # 2) 自动补充本句最有学习价值的实词（长度 >= 5 且非停用词），保证挖空/听写词每句都有高质量考点
    candidates = []
    for m in re.finditer(r"\b[A-Za-z][a-z]{4,}\b", en_text):
        w = m.group(0)
        wl = w.lower()
        if wl in STOP_WORDS or overlaps(m.start(), m.end()):
            continue
        candidates.append((len(w), m.start(), m.end(), w, wl))

    # 优先选信息量更高的较长实词
    candidates.sort(key=lambda x: (-x[0], x[1]))
    chips = ["orange", "pink", "indigo"]
    for _, s, e, w, wl in candidates:
        if len(found) >= 2:
            break
        if overlaps(s, e):
            continue
        found.append({"text": w, "key": wl, "chip": chips[len(found) % len(chips)]})
        used_spans.append((s, e))

    # 按在句中出现顺序排列
    found.sort(key=lambda item: en_text.find(item["text"]))
    return found


def parse_srt_or_vtt(content: str):
    content = content.replace("\r\n", "\n").replace("\r", "\n")
    is_auto_vtt = "<c>" in content or bool(re.search(r"<\d{2}:\d{2}:\d{2}\.\d{3}>", content))
    content = re.sub(r"^WEBVTT.*?\n\n", "", content, flags=re.DOTALL)
    blocks = re.split(r"\n{2,}", content.strip())
    raw_cues = []
    time_re = re.compile(
        r"(\d{1,2}:\d{2}:\d{2}[.,]\d{1,3}|\d{1,2}:\d{2}[.,]\d{1,3})\s*-->\s*(\d{1,2}:\d{2}:\d{2}[.,]\d{1,3}|\d{1,2}:\d{2}[.,]\d{1,3})"
    )
    for block in blocks:
        lines = [l.strip() for l in block.split("\n") if l.strip()]
        if not lines:
            continue
        time_idx = -1
        m = None
        for i, line in enumerate(lines):
            m = time_re.search(line)
            if m:
                time_idx = i
                break
        if time_idx == -1 or not m:
            continue
        start = round(parse_timestamp(m.group(1)), 2)
        end = round(parse_timestamp(m.group(2)), 2)
        text_lines = [
            html.unescape(re.sub(r"<[^>]+>", "", l)).replace("\u00a0", " ").strip()
            for l in lines[time_idx + 1 :]
        ]
        # 清理 >> 说话人箭头及 [Music] / [Applause] / ♪ 等非语音噪声
        cleaned_lines = []
        for l in text_lines:
            l = re.sub(r"^\s*>>\s*", "", l)
            l = re.sub(r"\[(?:music|applause|laughter|cheering|silence|inaudible|音乐|掌声|笑声)\]", "", l, flags=re.I)
            l = re.sub(r"♪.*?♪|♪", "", l)
            l = re.sub(r"\s+", " ", l).strip()
            if l:
                cleaned_lines.append(l)
        text_lines = cleaned_lines
        if not text_lines:
            continue

        has_zh = any(re.search(r"[\u4e00-\u9fff]", l) for l in text_lines)
        has_en = any(re.search(r"[A-Za-z]", l) for l in text_lines)

        if has_zh and has_en:
            en_parts = [l for l in text_lines if not re.search(r"[\u4e00-\u9fff]", l)]
            zh_parts = [l for l in text_lines if re.search(r"[\u4e00-\u9fff]", l)]
            en = " ".join(en_parts) if en_parts else text_lines[0]
            zh = " ".join(zh_parts)
        elif has_zh and not has_en:
            en = ""
            zh = " ".join(text_lines)
        else:
            # 区分 YouTube 滚动自动字幕（两行中第一行重复上一条） vs 人工双行字幕（两行是同一句的前后半句！）
            if is_auto_vtt and len(text_lines) >= 2 and raw_cues and text_lines[0].lower() in raw_cues[-1]["en"].lower():
                en = text_lines[-1]
            else:
                en = " ".join(text_lines)
            zh = ""

        # 跳过 YouTube 自动字幕 0.01s 瞬时重复残片
        if raw_cues and en and raw_cues[-1]["en"].lower() == en.lower():
            raw_cues[-1]["end"] = max(raw_cues[-1]["end"], end)
            continue
        if is_auto_vtt and end - start < 0.15 and len(en) < 12:
            continue

        raw_cues.append({
            "start": start,
            "end": max(end, start + 0.6),
            "en": en,
            "zh": zh,
        })

    return raw_cues


def split_long_sentence_cues(cues):
    """如果单条字幕内部包含多个完整句子（如 'Hello! How are you?'），按字符比例精准拆分为独立单句"""
    out = []
    for c in cues:
        en = c["en"].strip()
        zh = c["zh"].strip()
        if not en:
            out.append(c)
            continue
        # 仅在句末标点后紧跟空格和大写字母时切分（避免切分 Mr. / U.S. / 3.5）
        parts = re.split(r'(?<=[.?!])\s+(?=[A-Z"\'\(])', en)
        if len(parts) <= 1:
            out.append(c)
            continue
        total_len = max(1, sum(len(p) for p in parts))
        dur = max(0.4, c["end"] - c["start"])
        zh_parts = re.split(r'(?<=[。？！])\s*', zh) if zh else []
        zh_parts = [zp for zp in zh_parts if zp]
        cur_t = c["start"]
        for i, p in enumerate(parts):
            seg_dur = dur * (len(p) / total_len)
            seg_end = c["end"] if i == len(parts) - 1 else round(cur_t + seg_dur, 2)
            seg_zh = zh_parts[i] if i < len(zh_parts) else (zh if i == 0 and not zh_parts else "")
            out.append({
                "start": round(cur_t, 2),
                "end": round(max(seg_end, cur_t + 0.3), 2),
                "en": p.strip(),
                "zh": seg_zh.strip(),
            })
            cur_t = seg_end
    return out


def merge_into_complete_sentences(cues):
    """将按屏幕行宽切碎的短字幕，智能合并为按标点断句的完整自然句，且每张卡只放 1 句（与 SayBreeze 精听体验一致）"""
    if not cues:
        return []

    # 先把含多句的 cue 拆成单句单元，再把跨 cue 的半句合并成完整单句
    cues = split_long_sentence_cues(cues)
    has_punctuation_mostly = sum(1 for c in cues if re.search(r"[.?!]", c["en"])) > len(cues) * 0.25

    merged = []
    buf = None

    def flush():
        nonlocal buf
        if not buf:
            return
        en_clean = re.sub(r"\s+", " ", buf["en"]).strip()
        zh_clean = re.sub(r"\s+", " ", buf["zh"]).strip()
        if en_clean or zh_clean:
            merged.append({
                "id": len(merged) + 1,
                "start": round(buf["start"], 2),
                "end": round(max(buf["end"], buf["start"] + 0.4), 2),
                "speaker": "Speaker",
                "en": en_clean,
                "ipa": "",
                "zh": zh_clean,
                "highlights": find_highlights(en_clean),
            })
        buf = None

    for c in cues:
        if buf is None:
            buf = dict(c)
        else:
            gap = c["start"] - buf["end"]
            combined_dur = c["end"] - buf["start"]
            combined_len = len(buf["en"]) + len(c["en"])
            ends_sentence = bool(re.search(r'[.?!。？！]["\'\u201d\u2019]?$', buf["en"].strip()))

            # 有标点的字幕按句号/问号/感叹号合句；无标点的自动字幕按停顿和 7s/95字符 节奏切分，避免出现超大段落
            max_dur = 10.5 if has_punctuation_mostly else 7.0
            max_len = 140 if has_punctuation_mostly else 95
            max_gap = 1.2 if has_punctuation_mostly else 0.45

            if not ends_sentence and gap < max_gap and combined_dur <= max_dur and combined_len <= max_len:
                if c["en"]:
                    buf["en"] = (buf["en"] + " " + c["en"]).strip()
                if c["zh"]:
                    buf["zh"] = (buf["zh"] + ("" if buf["zh"].endswith(("，", "。", "！", "？")) else " ") + c["zh"]).strip()
                buf["end"] = max(buf["end"], c["end"])
            else:
                flush()
                buf = dict(c)

    flush()

    # 针对无标点的 YouTube 自动字幕，避免把悬挂词（如 Let's / how / what's / your / favorite / the / to）留在上一句末尾
    if not has_punctuation_mostly and len(merged) >= 2:
        dangling_tails = {
            "a", "an", "the", "my", "your", "his", "her", "its", "our", "their", "this", "that",
            "these", "those", "to", "of", "in", "on", "at", "for", "with", "from", "by", "about",
            "and", "or", "but", "so", "if", "when", "where", "how", "what", "what's", "who", "who's",
            "why", "which", "let's", "i'm", "you're", "we're", "they're", "favorite", "very", "most",
            "do", "does", "did", "can", "could", "would", "should", "will", "are", "is", "was", "were"
        }
        for i in range(len(merged) - 1):
            w1 = merged[i]["en"].split()
            w2 = merged[i + 1]["en"].split()
            moved = []
            # 最多向后移 3 个悬挂词，保证语义连贯（如 "what's your favorite" -> 移到 "memory..." 前）
            while len(w1) > 4 and len(moved) < 3 and w1[-1].lower().strip(",.?!") in dangling_tails:
                moved.insert(0, w1.pop())
            if moved:
                merged[i]["en"] = " ".join(w1)
                merged[i + 1]["en"] = " ".join(moved + w2)
                merged[i]["highlights"] = find_highlights(merged[i]["en"])
                merged[i + 1]["highlights"] = find_highlights(merged[i + 1]["en"])

    # 严格保证时间轴 0 重叠（每句结束时间严格 <= 下一句开始时间 - 0.04s）
    for i in range(len(merged) - 1):
        next_start = merged[i + 1]["start"]
        if merged[i]["end"] > next_start - 0.04:
            merged[i]["end"] = round(max(merged[i]["start"] + 0.15, next_start - 0.04), 2)
        if merged[i]["end"] > next_start:
            merged[i]["end"] = round(next_start, 2)

    return merged


def parse_plain_txt(content: str):
    lines = [l.strip() for l in content.replace("\r\n", "\n").split("\n") if l.strip()]
    sentences = []
    for i in range(0, len(lines), 2):
        en = lines[i]
        zh = lines[i + 1] if i + 1 < len(lines) else ""
        idx = len(sentences) + 1
        sentences.append({
            "id": idx,
            "start": (idx - 1) * 7,
            "end": idx * 7,
            "speaker": "Speaker",
            "en": en,
            "ipa": "",
            "zh": zh,
            "highlights": find_highlights(en),
        })
    return sentences


def parse_subtitle_files(sub_files):
    """支持单个双语字幕，或自动合并 .en.srt + .zh.srt 两个字幕文件"""
    if not sub_files:
        return []

    en_file = next((f for f in sub_files if re.search(r"[\._\-](en|en-us|en-gb|en-orig)$", f.stem, re.I)), None)
    zh_file = next((f for f in sub_files if re.search(r"[\._\-](zh|zh-cn|zh-hans|zh-hant|chs|cht)$", f.stem, re.I)), None)

    def load_one(f: Path):
        raw = f.read_text(encoding="utf-8", errors="ignore")
        return parse_srt_or_vtt(raw) if f.suffix.lower() in {".srt", ".vtt"} else parse_plain_txt(raw)

    if en_file and zh_file and en_file != zh_file:
        en_cues = load_one(en_file)
        zh_cues = load_one(zh_file)
        for item in en_cues:
            mid = (item["start"] + item["end"]) / 2.0
            overlapping = [
                z for z in zh_cues
                if (z["start"] <= item["end"] - 0.1 and z["end"] >= item["start"] + 0.1)
                or abs((z["start"] + z["end"]) / 2.0 - mid) <= 1.2
            ]
            if overlapping:
                best = min(overlapping, key=lambda z: abs((z["start"] + z["end"]) / 2.0 - mid))
                item["zh"] = best["zh"] or best["en"]
        return merge_into_complete_sentences(en_cues)

    chosen = en_file or sub_files[0]
    cues = load_one(chosen)
    if chosen.suffix.lower() in {".srt", ".vtt"}:
        return merge_into_complete_sentences(cues)
    return cues


def infer_tags(title: str, sentences):
    sample = (title + " " + " ".join(s["en"] for s in sentences[:12])).lower()
    tags = []
    for tag, kws in TAG_RULES:
        if any(kw in sample for kw in kws):
            tags.append(tag)
        if len(tags) >= 3:
            break
    return tags or ["生活英语", "日常对话"]


def infer_speaker(title: str, sentences=None):
    sample = (title + " " + " ".join(s.get("en", "") for s in (sentences or [])[:6])).lower()
    for sp, kws in SPEAKER_RULES:
        if any(kw in sample for kw in kws):
            return sp
    return "YouTube 博主"


def infer_region(title: str, speaker: str):
    sample = (title + " " + speaker).lower()
    for reg, kws in REGION_RULES:
        if any(kw in sample for kw in kws):
            return reg
    return "美国"


def infer_difficulty(title: str, sentences):
    lower = title.lower()
    if any(k in lower for k in ["jensen", "黄仁勋", "podcast", "keynote", "economics", "ceo"]):
        return 5
    if any(k in lower for k in ["vogue", "73 questions", "interview", "ted", "imposter", "访谈"]):
        return 4
    if any(k in lower for k in ["grocery", "ordering food", "beginner", "vocabulary", "shop in english"]):
        return 1
    if not sentences:
        return 2
    total_words = sum(len(s["en"].split()) for s in sentences)
    total_sec = max(1.0, sentences[-1]["end"] - sentences[0]["start"])
    wpm = (total_words / total_sec) * 60.0
    if wpm < 105:
        return 1
    if wpm < 130:
        return 2
    if wpm < 155:
        return 3
    if wpm < 180:
        return 4
    return 5


def format_duration(sec: float) -> str:
    total = max(1, int(round(sec)))
    return f"{total // 60:02d}:{total % 60:02d}"


def inspect_mp4_tracks(path: Path):
    """快速读取 MP4 头部/尾部 moov 原子，识别是否含视频轨/音频轨以及真实时长（秒）"""
    try:
        size = path.stat().st_size
        chunk = min(size, 3 * 1024 * 1024)
        with path.open("rb") as f:
            head = f.read(chunk)
            data = head
            if b"moov" not in head and size > chunk:
                f.seek(max(0, size - chunk))
                data = f.read(chunk)
        has_v = b"vide" in data
        has_a = b"soun" in data
        dur = None
        idx = data.find(b"mvhd")
        if idx != -1 and idx + 36 <= len(data):
            ver = data[idx + 4]
            if ver == 0:
                ts, d = struct.unpack(">II", data[idx + 16 : idx + 24])
                dur = round(d / ts, 2) if ts else None
            elif ver == 1:
                ts, d = struct.unpack(">IQ", data[idx + 24 : idx + 36])
                dur = round(d / ts, 2) if ts else None
        return {"has_video": has_v, "has_audio": has_a, "duration": dur}
    except Exception:
        return {"has_video": True, "has_audio": True, "duration": None}


def resegment_polished_sentences(sents):
    """
    对已完成 AI 标点/双语精校的字幕，按真实句末标点（. ? ! / 。？！）重新拆合：
    彻底消灭「上一句结尾断在半截（It's just something you）+ 下一句开头小写（can do. Hey guys...）」的断句问题！
    时间轴按字符比例平滑插值，并保留高亮词与 IPA。
    """
    if not sents or len(sents) <= 1:
        return sents

    # 1) 把每条内部含多个句末标点的片段拆成原子子段（按字符占比精准插值时间轴）
    atoms = []
    for s in sents:
        en = (s.get("en") or "").strip()
        zh = (s.get("zh") or "").strip()
        ipa = (s.get("ipa") or "").strip()
        if not en:
            continue
        # 在句末标点 . ? ! 后紧跟空白处切开（保护缩写 Mr./a.m./p.m./U.S. 和省略号 ...）
        en_protected = re.sub(
            r"\b(Mr|Mrs|Ms|Dr|St|Jr|Sr|vs|etc|e\.g|i\.e|a\.m|p\.m|U\.S|U\.K)\.",
            lambda m: m.group(0).replace(".", "<DOT>"),
            en,
            flags=re.I,
        )
        en_protected = en_protected.replace("...", "<ELLIPSIS>")
        parts = [
            p.replace("<ELLIPSIS>", "...").replace("<DOT>", ".").strip()
            for p in re.split(r'(?<=[.?!])\s+', en_protected)
            if p.strip()
        ]
        if len(parts) <= 1:
            atoms.append({
                "start": float(s["start"]),
                "end": float(s["end"]),
                "en": en,
                "zh": zh,
                "ipa": ipa,
                "highlights": s.get("highlights") or [],
            })
            continue

        # 同步拆分中文（按句末标点 。？！）
        zh_parts = [zp.strip() for zp in re.split(r'(?<=[。？！])\s*', zh) if zp.strip()] if zh else []
        # 如果中文段数和英文段数一致，一一对应；否则按字符比例切分中文
        if len(zh_parts) != len(parts) and zh:
            zh_parts = []
            total_en = max(1, sum(len(p) for p in parts))
            z_pos = 0
            for idx, p in enumerate(parts):
                if idx == len(parts) - 1:
                    zh_parts.append(zh[z_pos:].strip())
                else:
                    take = max(1, int(round(len(zh) * (len(p) / total_en))))
                    zh_parts.append(zh[z_pos : z_pos + take].strip())
                    z_pos += take

        total_chars = max(1, sum(len(p) for p in parts))
        dur = max(0.3, float(s["end"]) - float(s["start"]))
        cur_t = float(s["start"])
        for idx, p in enumerate(parts):
            seg_dur = dur * (len(p) / total_chars)
            seg_end = float(s["end"]) if idx == len(parts) - 1 else round(cur_t + seg_dur, 2)
            seg_zh = zh_parts[idx] if idx < len(zh_parts) else ""
            seg_hl = [h for h in (s.get("highlights") or []) if h.get("text") and h["text"] in p]
            atoms.append({
                "start": round(cur_t, 2),
                "end": round(max(seg_end, cur_t + 0.25), 2),
                "en": p,
                "zh": seg_zh,
                "ipa": ipa if len(parts) == 1 else "",
                "highlights": seg_hl,
            })
            cur_t = seg_end

    # 2) 把没有句末标点的半截原子段向后合并，直到遇到真正的句末标点（. ? !）
    rebuilt = []
    buf = None

    def flush_buf():
        nonlocal buf
        if not buf:
            return
        en_final = re.sub(r"\s+", " ", buf["en"]).strip()
        zh_final = re.sub(r"\s+", " ", buf["zh"]).replace("……", "").strip()
        # 去掉合并后残留的句中省略号尾巴
        zh_final = re.sub(r"\.{3,}", "", zh_final).strip()
        # 复用已有高亮，不足则自动补充
        hls = []
        seen_hl = set()
        for h in buf["highlights"]:
            t = h.get("text", "")
            if t and t in en_final and t.lower() not in seen_hl:
                hls.append(h)
                seen_hl.add(t.lower())
        if not hls:
            hls = find_highlights(en_final)
        rebuilt.append({
            "id": len(rebuilt) + 1,
            "start": round(buf["start"], 2),
            "end": round(max(buf["end"], buf["start"] + 0.4), 2),
            "speaker": "Speaker",
            "en": en_final,
            "ipa": buf["ipa"],
            "zh": zh_final,
            "highlights": hls[:3],
        })
        buf = None

    for a in atoms:
        if buf is None:
            buf = {
                "start": a["start"],
                "end": a["end"],
                "en": a["en"],
                "zh": a["zh"],
                "ipa": a["ipa"],
                "highlights": list(a["highlights"]),
            }
        else:
            ends_clean = bool(re.search(r'(?<!\.\.)[.?!]["\'\u201d\u2019]?$', buf["en"].strip()))
            next_starts_lower = bool(re.match(r"^[a-z]", a["en"].strip()))
            next_is_tiny_tail = len(a["en"].split()) <= 2 and (next_starts_lower or not re.search(r"[\u4e00-\u9fff]", a["zh"]))
            if buf["en"].strip().endswith("...") and next_starts_lower:
                ends_clean = False
            combined_len = len(buf["en"]) + len(a["en"])
            # 只要上一句还没遇到真正的句末标点，或者下一段是小写/残片（如 "of effort to go" / "out."），就必须合并成完整一句，不被中间 BGM 时长强行截断！
            if (not ends_clean or next_starts_lower or next_is_tiny_tail) and combined_len <= 320:
                buf["en"] = (buf["en"] + " " + a["en"]).strip()
                if a["zh"] and re.search(r"[\u4e00-\u9fffA-Za-z0-9]", a["zh"]):
                    joiner = "" if (not buf["zh"] or buf["zh"][-1] in "，。！？、：；…") else ""
                    buf["zh"] = (buf["zh"].rstrip("….") + joiner + a["zh"]).strip()
                if a["ipa"] and buf["ipa"]:
                    buf["ipa"] = (buf["ipa"].rstrip("/") + " " + a["ipa"].lstrip("/")).strip()
                elif a["ipa"]:
                    buf["ipa"] = a["ipa"]
                buf["highlights"].extend(a["highlights"])
                buf["end"] = max(buf["end"], a["end"])
            else:
                flush_buf()
                buf = {
                    "start": a["start"],
                    "end": a["end"],
                    "en": a["en"],
                    "zh": a["zh"],
                    "ipa": a["ipa"],
                    "highlights": list(a["highlights"]),
                }

    flush_buf()

    # 3) 裁剪每句末尾多余的纯音乐/静音拖尾（避免 3 个词的句子被拉成 18 秒纯 BGM！）并严格保证 0 重叠
    for i, s in enumerate(rebuilt):
        wc = max(1, len(s["en"].split()))
        max_speech_dur = max(2.8, wc * 0.62 + 1.6)
        if s["end"] - s["start"] > max_speech_dur:
            s["end"] = round(s["start"] + max_speech_dur, 2)
        if i + 1 < len(rebuilt):
            ns = rebuilt[i + 1]["start"]
            if s["end"] > ns - 0.04:
                s["end"] = round(max(s["start"] + 0.15, ns - 0.04), 2)
            if s["end"] > ns:
                s["end"] = round(ns, 2)

    # 4) 过滤纯标点/无有效中文或无有效英文的残片
    cleaned = [
        s for s in rebuilt
        if re.search(r"[A-Za-z]", s["en"]) and re.search(r"[\u4e00-\u9fffA-Za-z0-9]", s["zh"])
    ]
    for idx, s in enumerate(cleaned, start=1):
        s["id"] = idx

    return cleaned


def build_episode_item(idx, raw_title, files, rel_folder, media_base_url, meta=None, extra_audio_file=None, forced_duration=None):
    meta = meta or {}
    media_file = next((f for f in files if f.suffix.lower() in VIDEO_EXTS), None)
    media_kind = "video"
    if not media_file:
        media_file = next((f for f in files if f.suffix.lower() in AUDIO_EXTS), None)
        media_kind = "audio"

    sub_files = [f for f in files if f.suffix.lower() in SUB_EXTS]
    cover_file = next((f for f in files if f.suffix.lower() in IMG_EXTS), None)

    if not media_file and not sub_files:
        return None

    # 若存在 AI 精校缓存（<标题>.polished.json），读取并按真实标点重新拆合，确保每句完整自然！
    polished_path = EPISODES_DIR / f"{raw_title}.polished.json"
    sentences = []
    if polished_path.exists():
        try:
            raw_polished = json.loads(polished_path.read_text(encoding="utf-8"))
            sentences = resegment_polished_sentences(raw_polished)
        except Exception as exc:
            print(f"[warn] 读取/重切 {polished_path.name} 失败: {exc}")
            sentences = []
    if not sentences:
        sentences = parse_subtitle_files(sub_files)
    duration_sec = int(round(forced_duration)) if forced_duration else (int(round(sentences[-1]["end"])) if sentences else 60)
    if not sentences:
        # 没有字幕文件的视频暂不公开上架，避免用户点开看到无字幕空页
        return None

    title = meta.get("title") or raw_title
    speaker = meta.get("speaker") or infer_speaker(title, sentences)
    region = meta.get("region") or infer_region(title, speaker)
    difficulty = int(meta.get("difficulty") or infer_difficulty(title, sentences))
    tags = meta.get("tags") or infer_tags(title, sentences)

    rel_prefix = media_base_url.rstrip("/") if media_base_url else "./content/episodes"
    sub_path = f"{rel_prefix}/{quote(rel_folder)}" if rel_folder else rel_prefix
    media_url = f"{sub_path}/{quote(media_file.name)}" if media_file else ""
    audio_url = f"{sub_path}/{quote(extra_audio_file.name)}" if extra_audio_file else ""
    cover_url = f"{sub_path}/{quote(cover_file.name)}" if cover_file else ""

    slug = re.sub(r"[^a-zA-Z0-9_-]+", "-", raw_title).strip("-")[:32] or f"item-{idx}"
    return {
        "id": meta.get("id") or f"local-{idx}-{slug}",
        "number": meta.get("number") or f"EP {idx:02d}",
        "title": title,
        "speaker": speaker,
        "speakerAvatar": meta.get("speakerAvatar") or "./assets/hosts/cici_round.webp",
        "region": region,
        "difficulty": difficulty,
        "durationSec": duration_sec,
        "durationLabel": format_duration(duration_sec),
        "date": meta.get("date") or datetime.now().strftime("%Y/%m/%d"),
        "tags": tags,
        "coverGradient": meta.get("coverGradient") or COVER_GRADIENTS[(idx - 1) % len(COVER_GRADIENTS)],
        "coverImage": cover_url,
        "mediaUrl": media_url,
        "audioUrl": audio_url,
        "mediaKind": media_kind if media_url else "",
        "sceneBadge": meta.get("sceneBadge") or tags[0],
        "sentences": sentences,
    }


def scan_episodes(media_base_url: str):
    EPISODES_DIR.mkdir(parents=True, exist_ok=True)
    episodes = []
    counter = 1

    # 1) 直接平铺在 episodes/ 根目录的散装文件：先按同名（已自动去除 .f401/.f140/.en/.zh-Hans）分组！
    loose_files = sorted(
        [
            f for f in EPISODES_DIR.iterdir()
            if f.is_file() and not f.name.startswith(".") and f.name.lower() != "readme.md"
        ],
        key=lambda f: f.name.lower(),
    )
    valid_loose = [f for f in loose_files if f.suffix.lower() in (VIDEO_EXTS | AUDIO_EXTS | SUB_EXTS | IMG_EXTS)]

    # 按标准化标题名直接归组（同时处理 Stacher/yt-dlp 分离的 .f401.mp4 + .f140.m4a + .en.vtt + .zh-Hans.vtt + .webp）
    named_groups = {}
    for f in valid_loose:
        key = normalize_stem(f.name)
        named_groups.setdefault(key, []).append(f)

    # 按上传/写入时间先后排序（最早上传为 EP 01，最新上传编号最大，列表按最新优先展示）
    ordered_groups = sorted(
        named_groups.items(),
        key=lambda kv: min(f.stat().st_mtime for f in kv[1]),
    )

    for stem, files in ordered_groups:
        vid = next((f for f in files if f.suffix.lower() in VIDEO_EXTS), None)
        aud = next((f for f in files if f.suffix.lower() in AUDIO_EXTS), None)
        # 跳过正在下载中的（只有字幕/封面还没有任何已完成音视频文件）
        if not vid and not aud:
            continue
        dur = None
        if vid and vid.suffix.lower() == ".mp4":
            dur = inspect_mp4_tracks(vid).get("duration")
        ep = build_episode_item(
            counter,
            stem,
            [f for f in files if f != aud] if vid else files,
            "",
            media_base_url,
            extra_audio_file=aud if vid else None,
            forced_duration=dur,
        )
        if ep:
            episodes.append(ep)
            counter += 1

    # 2) 同时兼容 episodes/ 下的子文件夹模式
    folders = sorted(
        [p for p in EPISODES_DIR.iterdir() if p.is_dir() and not p.name.startswith(("_", "."))],
        key=lambda p: p.name.lower(),
    )
    for folder in folders:
        meta = {}
        meta_path = folder / "meta.json"
        if meta_path.exists():
            try:
                meta = json.loads(meta_path.read_text(encoding="utf-8"))
            except Exception as exc:
                print(f"[warn] 读取 {meta_path} 失败: {exc}")
        files = [f for f in folder.iterdir() if f.is_file() and not f.name.startswith(".")]
        ep = build_episode_item(counter, folder.name, files, folder.name, media_base_url, meta=meta)
        if ep:
            episodes.append(ep)
            counter += 1

    # 列表按最新上传优先展示（EP 32 在最前，EP 01 在最后，与 SayBreeze 一致）
    episodes.reverse()

    js_content = (
        "// 本文件由 scripts/sync_episodes.py 自动生成，请勿手工修改\n"
        f"export const LOCAL_EPISODES = {json.dumps(episodes, ensure_ascii=False, indent=2)};\n"
    )
    OUTPUT_JS.write_text(js_content, encoding="utf-8")
    print(f"[ok] 已智能识别并同步 {len(episodes)} 个本地剧集 -> {OUTPUT_JS}")


def main():
    parser = argparse.ArgumentParser(description="智能扫描 content/episodes 散装或子目录素材到 Just Met 网站")
    parser.add_argument("--media-base-url", default="", help="可选：线上视频/图片 CDN 前缀（如 Cloudflare R2 地址）")
    args = parser.parse_args()
    scan_episodes(args.media_base_url)


if __name__ == "__main__":
    main()
