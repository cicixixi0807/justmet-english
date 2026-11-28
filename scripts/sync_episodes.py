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
    ("购物", ["grocery", "supermarket", "shopping", "mall", "thrift", "haul", "self-checkout", "shoplifting", "超市", "购物", "逛街", "百货"]),
    ("美食", ["pizza", "coffee", "restaurant", "bakery", "chipotle", "chick-fil-a", "mcdonald", "fast food", "pasta", "breakfast", "salad", "cook", "cooking", "meal", "meals", "snacks", "candy", "popcorn", "hot dog", "美食", "点餐", "咖啡", "做饭", "意面", "早餐", "甜点"]),
    ("旅行", ["travel", "trip", "airport", "hotel", "vacation", "holiday", "skiing", "slope", "chair lift", "subway", "downtown", "旅行", "旅游", "机场", "酒店", "滑雪", "度假"]),
    ("名人访谈", ["vogue", "73 questions", "victoria beckham", "emma watson", "kendall jenner", "taylor swift", "jensen", "名人访谈"]),
    ("个人成长", ["ted", "tedx", "imposter syndrome", "better conversation", "start any conversation", "confidence", "boundary", "boundaries", "mindset", "overthinking", "business", "成长", "演讲", "沟通技巧"]),
    ("日常对话", ["conversation", "small talk", "slang", "interviewing native", "what do you do for a living", "can you understand", "日常对话", "地道对话", "俚语", "街头采访"]),
    ("生活英语", ["vocabulary", "phrases", "english lesson", "around town", "around the city", "household chores", "buy a house", "car", "bank", "post office", "religious", "生活英语", "词汇", "实用英语"]),
    ("生活", ["living alone", "morning routine", "daily routine", "day in my life", "busy day", "apartment", "alone in new york", "alone but not lonely", "what i spend", "makeup", "独居", "日常", "生活"]),
]

SPEAKER_RULES = [
    # 讲者一律写片中主人公真名（绝不用 Vogue / TED / TED-Ed / YouTube 博主 代替人名）
    ("Victoria Beckham", ["victoria beckham"]),
    ("Emma Watson", ["emma watson"]),
    ("Kendall Jenner", ["kendall jenner"]),
    ("Taylor Swift", ["taylor swift"]),
    ("Celeste Headlee", ["celeste headlee", "10 ways to have a better conversation"]),
    ("Chris Fenning", ["chris fenning", "start any conversation the right way"]),
    ("Elizabeth Cox", ["elizabeth cox", "imposter syndrome"]),
    ("Bob the Canadian", ["bob the canadian", "daily routine in english by watching me act out", "learn english at a hotel", "hotel in canada"]),
    ("Sydney Serena", ["sydney serena", "alone in new york", "alone but not lonely", "what i eat as a busy girl", "what i spend in a week", "it's sid", "it's syd"]),
    ("Ariannita la Gringa", [
        "ariannita", "arianita", "la gringa", "lagringa", "liginga",
        "downtown vocabulary", "english lesson at the airport", "english phrases for ordering food",
        "grocery shopping with your english teacher", "how to order coffee in english",
        "how to order fast food", "how to order food in a restaurant", "mall vocabulary",
        "car vocabulary", "household chores", "how to buy a house", "religious vocabulary",
        "essential english for skiing", "st. patrick", "patrick’s day", "patrick's day",
        "what do you do for a living", "can you understand my friend", "chipotle", "cincinnati",
    ]),
    ("Speak English With Vanessa", [
        "vanessa", "speakenglishwithvanessa", "daily life english", "grocery store vocabulary",
        "real life english around the city", "speak american english around town", "order pizza in english", "order food in english",
    ]),
    ("Michelle Choi", ["michelle choi", "living alone diaries", "homebody on holiday", "homebody in new york", "dobby"]),
    ("English with Lucy", ["english with lucy"]),
    ("Jenn Im", ["jenn im"]),
    ("Eva Meloche", ["eva meloche"]),
    ("Taylor R", ["taylor r"]),
    ("Jensen Huang", ["jensen", "黄仁勋"]),
    ("Ali Abdaal", ["ali abdaal"]),
    ("Jay Shetty", ["jay shetty"]),
    ("谷爱凌", ["eileen gu", "谷爱凌"]),
]

REGION_RULES = [
    ("英国", ["emma watson", "victoria beckham", "lucy", "ali abdaal", "london", "british"]),
    ("加拿大", ["bob the canadian", "hotel in canada", "canada"]),
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


ABBREV_RE = re.compile(
    r"\b(Mr|Mrs|Ms|Dr|St|Jr|Sr|Prof|vs|etc|e\.g|i\.e|a\.m|p\.m|U\.S|U\.K|U\.S\.A)\.",
    flags=re.IGNORECASE,
)

STAGE_EN_RE = re.compile(
    r"(?:\[(?:[^\[\]]{0,32}?(?:music|applause|laughter|cheering|silence|inaudible|bell|beeping|snorts?|sighs?|groans?|clapping|singing|音乐|掌声|笑声))[^\[\]]{0,16}\]|\((?:[^\(\)]{0,32}?(?:music|applause|laughter|cheering|silence|inaudible|bell|beeping|snorts?|sighs?|groans?|clapping|singing|alarm|chime|音乐|掌声|笑声))[^\(\)]{0,16}\)|♪[^♪]*♪|♪)",
    flags=re.IGNORECASE,
)

STAGE_ZH_RE = re.compile(
    r"(?:[\(（](?:[^\)）]{0,20}?(?:音乐|掌声|笑声|欢呼|闹钟|鸣响|铃声|叹气|鼓掌|静音))[^\)）]{0,8}[\)）]|\[(?:[^\]]{0,20}?(?:音乐|掌声|笑声))[^\]]{0,8}\])"
)


def strip_stage_directions(text: str, is_zh: bool = False) -> str:
    if not text:
        return ""
    s = STAGE_ZH_RE.sub("", text) if is_zh else STAGE_EN_RE.sub("", text)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def protect_abbrevs(text: str) -> str:
    return ABBREV_RE.sub(lambda m: m.group(0).replace(".", "<DOT>"), text).replace("...", "<ELLIPSIS>")


def restore_abbrevs(text: str) -> str:
    return text.replace("<ELLIPSIS>", "...").replace("<DOT>", ".")


def parse_srt_or_vtt(content: str, music_ranges_out=None):
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
        had_stage_only = any(STAGE_EN_RE.search(l) or STAGE_ZH_RE.search(l) for l in text_lines)
        cleaned_lines = []
        for l in text_lines:
            l = re.sub(r"^\s*>>\s*", "", l)
            l = strip_stage_directions(l, is_zh=False)
            l = strip_stage_directions(l, is_zh=True)
            l = re.sub(r"\s+", " ", l).strip()
            if l:
                cleaned_lines.append(l)
        text_lines = cleaned_lines
        if not text_lines:
            # 保留纯音乐/掌声 cue 的时间区间，写入 skipRanges 供播放器自动跳过！
            if had_stage_only and music_ranges_out is not None and end > start:
                music_ranges_out.append([start, end])
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
    """如果单条字幕内部包含多个完整句子（如 'Hello! How are you?'），保护缩写并按原 cue 边界精准拆分"""
    out = []
    for c in cues:
        en = c["en"].strip()
        zh = c["zh"].strip()
        if not en:
            out.append(c)
            continue
        en_prot = protect_abbrevs(en)
        parts = [restore_abbrevs(p).strip() for p in re.split(r'(?<=[.?!])\s+(?=[A-Z"\'\(])', en_prot) if p.strip()]
        if len(parts) <= 1:
            out.append(c)
            continue
        zh_parts = [zp.strip() for zp in re.split(r'(?<=[。？！])\s*', zh) if zp.strip()] if zh else []
        # 只有中英文句数一致（或无中文）时才拆分，绝不按汉字字数硬切中文！
        if zh and len(zh_parts) != len(parts):
            out.append(c)
            continue
        total_len = max(1, sum(len(p) for p in parts))
        dur = max(0.4, c["end"] - c["start"])
        cur_t = c["start"]
        for i, p in enumerate(parts):
            seg_dur = dur * (len(p) / total_len)
            seg_end = c["end"] if i == len(parts) - 1 else round(cur_t + seg_dur, 2)
            seg_zh = zh_parts[i] if i < len(zh_parts) else ""
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


def parse_subtitle_files(sub_files, music_ranges_out=None):
    """支持单个双语字幕，或自动合并 .en.srt + .zh.srt 两个字幕文件，并收集音乐 cue 区间"""
    if not sub_files:
        return []

    en_file = next((f for f in sub_files if re.search(r"[\._\-](en|en-us|en-gb|en-orig)$", f.stem, re.I)), None)
    zh_file = next((f for f in sub_files if re.search(r"[\._\-](zh|zh-cn|zh-hans|zh-hant|chs|cht)$", f.stem, re.I)), None)

    def load_one(f: Path, collect_music=False):
        raw = f.read_text(encoding="utf-8", errors="ignore")
        if f.suffix.lower() in {".srt", ".vtt"}:
            return parse_srt_or_vtt(raw, music_ranges_out=music_ranges_out if collect_music else None)
        return parse_plain_txt(raw)

    if en_file and zh_file and en_file != zh_file:
        en_cues = load_one(en_file, collect_music=True)
        zh_cues = load_one(zh_file, collect_music=False)
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
    cues = load_one(chosen, collect_music=True)
    if chosen.suffix.lower() in {".srt", ".vtt"}:
        return merge_into_complete_sentences(cues)
    return cues


def _kw_match(kw: str, sample: str) -> bool:
    if re.fullmatch(r"[a-z0-9\s\-'’\.]+", kw):
        return bool(re.search(rf"(?<![a-z0-9]){re.escape(kw)}(?![a-z0-9])", sample))
    return kw in sample


def infer_tags(title: str, sentences):
    title_l = title.lower()
    body_l = " ".join(s.get("en", "") for s in sentences[:25]).lower()
    tags = []
    for tag, kws in TAG_RULES:
        # 标题强命中，或正文命中 >= 2 个不同领域关键词，彻底杜绝 "in order to" / "order an Uber" / "childcare, food?" 误标
        title_hit = any(_kw_match(kw, title_l) for kw in kws)
        body_hits = sum(1 for kw in kws if _kw_match(kw, body_l))
        if title_hit or body_hits >= 2:
            tags.append(tag)
        if len(tags) >= 3:
            break
    return tags or ["生活英语", "日常对话"]


def infer_speaker(title: str, sentences=None, source_title: str = ""):
    sample = (title + " " + source_title + " " + " ".join(s.get("en", "") for s in (sentences or [])[:10])).lower()
    for sp, kws in SPEAKER_RULES:
        if any(_kw_match(kw, sample) for kw in kws):
            return sp
    # 尝试从前 5 句 "I'm X" / "My name is X" / "It's X" 抽取真名，绝不回退成 "YouTube 博主"
    intro_text = " ".join(s.get("en", "") for s in (sentences or [])[:5])
    m = re.search(r"\b(?:my name is|i'm|i am)\s+([A-Z][a-z]{2,15}(?:\s+[A-Z][a-z]{2,15})?)\b", intro_text)
    if m:
        cand = m.group(1)
        if cand.lower() not in {"here", "going", "sorry", "back", "excited", "doing", "ready", "still", "just", "kind"}:
            return cand
    return "待补讲者"


def infer_region(title: str, speaker: str, sentences=None):
    sample = (title + " " + speaker + " " + " ".join(s.get("en", "") for s in (sentences or [])[:6])).lower()
    for reg, kws in REGION_RULES:
        if any(_kw_match(kw, sample) for kw in kws):
            return reg
    return "美国"


ABSTRACT_WORKPLACE_TERMS = [
    "imposter syndrome", "perspective", "empathy", "vulnerability", "authentic", "authenticity",
    "assumption", "assumptions", "stereotype", "stereotypes", "productivity", "strategy",
    "revenue", "client", "clients", "business", "framework", "psychology", "research",
    "evidence", "argument", "economy", "inflation", "mortgage", "investment", "cultural",
    "tradition", "traditions", "philosophy", "religion", "religions", "politics",
    "professional", "corporate", "colleague", "colleagues", "leadership", "management",
    "negotiate", "negotiation", "feedback", "boundary", "boundaries", "burnout", "mindset",
    "priority", "priorities", "self-conscious", "introvert", "extrovert", "bias", "biases",
    "nuance", "metaphor", "conversation", "communicate", "communication", "masterclass",
    "meeting", "agenda", "context", "principle", "principles", "identity", "confidence",
    "anxiety", "depression", "therapy", "diagnosis", "accomplishment", "achievement",
    "fulfillment", "tectonic", "inexorable", "consequences", "responsibility", "opportunity",
]


def classify_scene_tier(title: str, source_title: str, speaker: str, tags, sentences):
    """
    场景分档（A / B / C）—— 看课的实际内容，不只看标题：
    - C 高信息密度：名人访谈（73 Questions/In The Bag）、TED/正式演讲、keynote、深度访谈、商业方法论
    - B 日常进阶：生活 vlog、多场景城市英语、内容较密的日常记录
    - A 入门情景：日常对话、生活英语教学、购物、点餐、词汇课、超市/咖啡店/酒店/机场/街头采访等情景教学
    返回 (tier, tier_reason, uncertain_flag)
    """
    combo = f"{title} {source_title} {speaker}".lower()
    body = " ".join(s.get("en", "") for s in (sentences or [])[:30]).lower()

    # C 档：正式演讲 / 名人访谈 / 商业深度内容
    c_signals = [
        "ted", "tedx", "ted-ed", "imposter syndrome", "73 questions", "in the bag", "vogue",
        "keynote", "podcast", "celeste headlee", "chris fenning", "elizabeth cox",
        "victoria beckham", "emma watson", "kendall jenner", "taylor swift", "jensen",
        "slowing your business down",
    ]
    if any(_kw_match(k, combo) for k in c_signals) or "名人访谈" in (tags or []):
        return "C", "高信息密度（正式演讲/名人访谈/商业观点）", False

    # B 档：生活 vlog、多场景城市英语、内容较密的日常记录
    b_signals = [
        "living alone diaries", "homebody", "alone in new york", "alone but not lonely",
        "what i eat", "what i spend", "productive & busy day", "natural korean makeup",
        "around the city", "around town", "buy a house", "can you understand my friend",
        "sydney serena", "michelle choi",
    ]
    if any(_kw_match(k, combo) for k in b_signals):
        # 标记边界项：多场景城市教学 / 买房 / 俚语访谈（介于 A 与 B 之间）
        borderline = any(_kw_match(k, combo) for k in ["around the city", "around town", "buy a house", "can you understand my friend"])
        reason = "日常进阶（多场景城市英语/生活记录）" if borderline else "日常进阶（生活Vlog/日常记录）"
        return "B", reason, borderline

    # A 档：生活英语教学、购物、点餐、词汇课、短情景对话
    a_signals = [
        "vocabulary", "grocery", "order", "ordering", "pizza", "coffee", "restaurant",
        "fast food", "chipotle", "mall", "car", "household chores", "airport", "hotel",
        "skiing", "daily routine", "religious", "st. patrick", "what do you do for a living",
        "ariannita", "bob the canadian", "vanessa",
    ]
    if any(_kw_match(k, combo) for k in a_signals) or any(_kw_match(k, body) for k in ["vocabulary", "grocery store", "order food"]):
        return "A", "入门情景（词汇/点餐/购物/生活情景教学）", False

    return "B", "日常进阶（默认归档，建议人工复核）", True


def compute_effective_wpm(sentences, skip_ranges=None) -> float:
    """按去掉 skipRanges / 纯音乐与句间空档后的有效口语时长计算 WPM"""
    if not sentences:
        return 130.0
    skips = skip_ranges or []
    total_words = 0
    spoken_sec = 0.0
    for s in sentences:
        en = (s.get("en") or "").strip()
        words = re.findall(r"[A-Za-z0-9']+", en)
        total_words += len(words)
        s0, s1 = float(s["start"]), float(s["end"])
        iskip = sum(
            max(0.0, min(s1, float(r[1])) - max(s0, float(r[0])))
            for r in skips
            if isinstance(r, list) and len(r) == 2
        )
        spoken_sec += max(0.15, (s1 - s0) - iskip)
    return round((total_words / max(1.0, spoken_sec)) * 60.0, 1)


def evaluate_difficulty_detail(title: str, source_title: str, speaker: str, tags, sentences, duration_sec: int, skip_ranges=None):
    """
    综合 5 维度（场景分档、时长、有效 WPM、字幕结构、抽象/学术/职场重点词）计算难度星级（1–5）。
    严格按规范：基准星（场景+时长） + 语速/重点词调整（合计限 ±1 星），并执行硬锁。
    """
    tier, tier_reason, uncertain = classify_scene_tier(title, source_title, speaker, tags, sentences)
    dur_min = float(duration_sec) / 60.0

    # 1) 基准星：场景 + 时长
    if tier == "A":
        base = 1 if dur_min <= 2.5 else (2 if dur_min <= 5.0 else 3)
    elif tier == "B":
        base = 2 if dur_min <= 5.0 else (3 if dur_min <= 8.0 else 4)
    else:  # C
        base = 3 if dur_min <= 5.0 else (4 if dur_min <= 8.0 else 5)

    # 2) 有效语速 WPM 调整
    wpm = compute_effective_wpm(sentences, skip_ranges)
    if wpm < 105.0:
        wpm_adj = -1
    elif wpm >= 180.0:
        wpm_adj = 1
    else:
        wpm_adj = 0

    # 3) 抽象/学术/职场/观点类重点词调整（词边界/短语匹配）
    full_en = " ".join((s.get("en") or "") for s in (sentences or [])).lower()
    distinct_hits = [term for term in ABSTRACT_WORKPLACE_TERMS if _kw_match(term, full_en)]
    sent_hits = sum(
        1 for s in (sentences or [])
        if any(_kw_match(term, (s.get("en") or "").lower()) for term in ABSTRACT_WORKPLACE_TERMS)
    )
    hit_ratio = sent_hits / max(1, len(sentences or []))
    lex_adj = 1 if (len(distinct_hits) >= 6 or (len(distinct_hits) >= 3 and hit_ratio >= 0.12)) else 0

    # 4) 合并微调（最多 ±1 星）+ 硬限制
    adj = max(-1, min(1, wpm_adj + lex_adj))
    star = base + adj

    notes = [f"{tier}档({dur_min:.1f}m)基准{base}★", f"WPM={wpm:.0f}({wpm_adj:+d})"]
    if lex_adj > 0:
        notes.append(f"抽象/职场词{len(distinct_hits)}个(+1)")

    if tier == "A" and dur_min <= 2.5:
        star = 1
        notes.append("A≤2.5m锁1★")
    elif tier == "A" and star > 3:
        star = 3
        notes.append("A档封顶3★")
    elif tier == "C" and dur_min > 8.0 and star < 4:
        star = 4
        notes.append("C>8m保底4★")

    star = max(1, min(5, star))
    return {
        "difficulty": star,
        "tier": tier,
        "wpm": wpm,
        "base": base,
        "wpm_adj": wpm_adj,
        "lex_adj": lex_adj,
        "uncertain": uncertain,
        "reason": "；".join(notes),
    }


def infer_difficulty(title: str, sentences, duration_sec: int = 0, source_title: str = "", speaker: str = "", tags=None, skip_ranges=None):
    return evaluate_difficulty_detail(title, source_title, speaker, tags, sentences, duration_sec, skip_ranges)["difficulty"]


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


def is_garbled_outro_fragment(en: str, zh: str) -> bool:
    """识别精校失败或片尾乱码残句（如 'Oh so, Hey, I'm don't for,'），禁止上架"""
    t = en.strip()
    if not t:
        return True
    # 典型乱码模式：I'm don't / 结尾为逗号且无主谓结构
    if re.search(r"\bI'm\s+don't\b", t, re.I):
        return True
    if t.endswith(",") and len(t.split()) <= 8 and not re.search(r"[.?!]", t):
        return True
    return False


def resegment_polished_sentences(sents, music_ranges_out=None):
    """
    工作包 2 核心重切算法：
    1. 清除 (friendly music)/(Applause)/(Laughter) 等舞台标记，纯音乐 cue 写入 music_ranges_out；
    2. 优先按原 cue 边界，只有一条 cue 内同时包含 >=2 个完整英文句且中文句数匹配时才在该 cue 内拆分——严禁按汉字字数硬切中文！
    3. 禁止跨过大空档（gap > 2.5s）合并半句，大空档直接写入 skipRanges；
    4. 取消 320 字符硬切断，放宽合并上限，彻底消除 EP 36 #74-75 / EP 12 #71-72 这类半句截断；
    5. 保留 IPA，过滤精校失败残句（如 EP 09 末句）和无有效中英文的噪声卡。
    """
    if not sents or len(sents) <= 1:
        return sents

    # 1) 清洗每条 cue 的音乐/掌声标记；只有中英文句数严格一致时才做 cue 内拆句，绝不从汉字中间切开！
    atoms = []
    for s in sents:
        raw_en = (s.get("en") or "").strip()
        raw_zh = (s.get("zh") or "").strip()
        had_stage = bool(STAGE_EN_RE.search(raw_en) or STAGE_ZH_RE.search(raw_zh))
        en = strip_stage_directions(raw_en, is_zh=False)
        zh = strip_stage_directions(raw_zh, is_zh=True)
        ipa = (s.get("ipa") or "").strip()
        st = float(s["start"])
        ed = float(s["end"])

        if not en or not re.search(r"[A-Za-z]", en):
            if had_stage and music_ranges_out is not None and ed > st:
                music_ranges_out.append([round(st, 2), round(ed, 2)])
            continue

        en_protected = protect_abbrevs(en)
        parts = [restore_abbrevs(p).strip() for p in re.split(r'(?<=[.?!])\s+', en_protected) if p.strip()]
        zh_parts = [zp.strip() for zp in re.split(r'(?<=[。？！])\s*', zh) if zp.strip()] if zh else []

        # 关键约束：仅当单条 cue 里出现多个完整句 且 中文句数与英文句数一致时才拆句；
        # 否则整条 cue 保持完整（禁止按字数把汉字从中间切开！），确保 EP 39 #56-57 零错位！
        if len(parts) > 1 and len(zh_parts) == len(parts):
            total_chars = max(1, sum(len(p) for p in parts))
            dur = max(0.3, ed - st)
            cur_t = st
            for idx, p in enumerate(parts):
                seg_dur = dur * (len(p) / total_chars)
                seg_end = ed if idx == len(parts) - 1 else round(cur_t + seg_dur, 2)
                seg_zh = zh_parts[idx]
                seg_hl = [h for h in (s.get("highlights") or []) if h.get("text") and h["text"] in p]
                atoms.append({
                    "start": round(cur_t, 2),
                    "end": round(max(seg_end, cur_t + 0.25), 2),
                    "en": p,
                    "zh": seg_zh,
                    "ipa": ipa if idx == 0 else "",
                    "highlights": seg_hl,
                })
                cur_t = seg_end
        else:
            atoms.append({
                "start": round(st, 2),
                "end": round(ed, 2),
                "en": en,
                "zh": zh,
                "ipa": ipa,
                "highlights": [h for h in (s.get("highlights") or []) if h.get("text") and h["text"] in en],
            })

    # 2) 合并未完成的半句：
    #    - 禁止跨过大空档（gap > 2.5s）合并（空档留给 skipRanges）；
    #    - 取消 320 字符硬截断，放宽到 750 字符以彻底避免 EP 36 #74-75 / EP 12 #71-72 被拦腰劈开！
    rebuilt = []
    buf = None

    def flush_buf():
        nonlocal buf
        if not buf:
            return
        en_final = re.sub(r"\s+", " ", buf["en"]).strip()
        zh_final = re.sub(r"\s+", " ", buf["zh"]).replace("……", "").strip()
        zh_final = re.sub(r"\.{3,}", "", zh_final).strip()
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
            gap = a["start"] - buf["end"]
            ends_clean = bool(re.search(r'(?<!\.\.)[.?!]["\'\u201d\u2019]?$', buf["en"].strip()))
            next_starts_lower = bool(re.match(r"^[a-z]", a["en"].strip()))
            next_is_tiny_tail = len(a["en"].split()) <= 2 and (next_starts_lower or not re.search(r"[\u4e00-\u9fff]", a["zh"]))
            if buf["en"].strip().endswith("...") and next_starts_lower:
                ends_clean = False
            combined_len = len(buf["en"]) + len(a["en"])

            # 同一句话跨纯音乐/空档（如 EP 39 #1 5.4s / #62 3.4s / #153 13.3s）合并成一张完整学习卡，并把中间纯音乐/空白写入 skipRanges；
            # 但超过 15s 的大场景切换（如 EP 19 49s 换景）绝不强行跨景合并。
            is_true_continuation = (
                (not ends_clean and gap <= 15.0)
                or (next_starts_lower and gap <= 2.5)
                or (next_is_tiny_tail and gap <= 15.0)
            )
            if is_true_continuation and combined_len <= 750:
                if gap > 0.5 and music_ranges_out is not None:
                    music_ranges_out.append([round(buf["end"], 2), round(a["start"], 2)])
                buf["en"] = (buf["en"].rstrip("….") if buf["en"].strip().endswith("...") and next_starts_lower else buf["en"]).strip()
                buf["en"] = (buf["en"] + " " + a["en"]).strip()
                if a["zh"] and re.search(r"[\u4e00-\u9fffA-Za-z0-9]", a["zh"]):
                    buf["zh"] = (buf["zh"].rstrip("….") + a["zh"]).strip()
                if a["ipa"] and buf["ipa"]:
                    buf["ipa"] = (buf["ipa"].rstrip("/") + " " + a["ipa"].lstrip("/")).strip()
                elif a["ipa"]:
                    buf["ipa"] = a["ipa"]
                buf["highlights"].extend(a["highlights"])
                buf["end"] = max(buf["end"], a["end"])
            else:
                if gap > 0.5 and music_ranges_out is not None:
                    music_ranges_out.append([round(buf["end"], 2), round(a["start"], 2)])
                # 若因超长换景（>15s）断开且上一句停在逗号/省略，自动补齐句末标点避免留下半截句
                if not ends_clean and gap > 15.0:
                    buf["en"] = buf["en"].rstrip(",;: ") + "."
                    if buf["zh"] and not buf["zh"].endswith(("。", "！", "？")):
                        buf["zh"] = buf["zh"].rstrip("，、 ") + "。"
                flush_buf()
                next_en = a["en"]
                if next_starts_lower:
                    next_en = next_en[0].upper() + next_en[1:]
                buf = {
                    "start": a["start"],
                    "end": a["end"],
                    "en": next_en,
                    "zh": a["zh"],
                    "ipa": a["ipa"],
                    "highlights": list(a["highlights"]),
                }

    flush_buf()

    # 3) 合理保护每句时长：扣除句内 skipRanges 后的实际口播时长若仍超长（短句收紧至 5.5s 下限，杜绝 2-5 词短句拖 12s 纯音乐），温和裁尾并写入 skipRanges
    for i, s in enumerate(rebuilt):
        wc = max(1, len(s["en"].split()))
        max_speech_dur = max(5.5, wc * 0.8 + 2.8)
        internal_skip = 0.0
        for rs, re_ in (music_ranges_out or []):
            ov = max(0.0, min(s["end"], re_) - max(s["start"], rs))
            internal_skip += ov
        spoken_dur = (s["end"] - s["start"]) - internal_skip
        if spoken_dur > max_speech_dur:
            excess = spoken_dur - max_speech_dur
            new_end = round(s["end"] - excess - 0.05, 2)
            if new_end > s["start"] + 0.5:
                if music_ranges_out is not None:
                    music_ranges_out.append([new_end, round(s["end"], 2)])
                s["end"] = new_end
        if i + 1 < len(rebuilt):
            ns = rebuilt[i + 1]["start"]
            if s["end"] > ns - 0.04:
                s["end"] = round(max(s["start"] + 0.15, ns - 0.04), 2)
            if s["end"] > ns:
                s["end"] = round(ns, 2)

    # 4) 过滤纯标点/无有效中英文的残片，以及片尾精校失败乱码（如 EP 09 末句）或片尾截断半句（如 EP 06 末句）
    cleaned = [
        s for s in rebuilt
        if re.search(r"[A-Za-z]", s["en"])
        and re.search(r"[\u4e00-\u9fffA-Za-z0-9]", s["zh"])
        and not is_garbled_outro_fragment(s["en"], s["zh"])
    ]

    # 检查末句是否为被片尾强行截断的无标点半句（如 EP 06 末句 "and I'll see you"）
    if cleaned and not re.search(r'[.?!]["\'\u201d\u2019]?$', cleaned[-1]["en"].strip()):
        last_en = cleaned[-1]["en"].strip()
        if re.search(r"\band I'll see you$", last_en, re.I):
            cleaned[-1]["en"] = re.sub(r"\band I'll see you$", "and I'll see you there!", last_en, flags=re.I)
            if re.search(r"[，,]?\s*我们$", cleaned[-1]["zh"].strip()):
                cleaned[-1]["zh"] = re.sub(r"[，,]?\s*我们$", "，我们下期见！", cleaned[-1]["zh"].strip())
        elif re.search(r"\b(see you|thank you|thanks for)\b", last_en, re.I):
            cleaned[-1]["en"] = last_en.rstrip(",;:") + "."
            if cleaned[-1]["zh"] and not cleaned[-1]["zh"].endswith(("。", "！", "？")):
                cleaned[-1]["zh"] = cleaned[-1]["zh"].rstrip("，、") + "。"

    # 5) 过滤相邻完全重复句或紧跟的尾部回声残片（如 EP 23 "St. Patrick's Day?" 后的重复 "Patrick's Day?"）
    deduped = []
    for s in cleaned:
        if deduped:
            prev_en = deduped[-1]["en"].strip().lower()
            cur_en = s["en"].strip().lower()
            if cur_en == prev_en or (
                len(cur_en) >= 12
                and prev_en.endswith(cur_en)
                and (float(s["start"]) - float(deduped[-1]["end"])) <= 0.6
            ):
                deduped[-1]["end"] = max(deduped[-1]["end"], s["end"])
                continue
        deduped.append(s)
    cleaned = deduped

    for idx, s in enumerate(cleaned, start=1):
        s["id"] = idx

    return cleaned


def build_skip_ranges(sentences, duration_sec, raw_music_ranges):
    """汇总所有应跳过区间：片头（0 -> 首句）、纯音乐 cue、句间空档（>0.5s）、片尾（末句 -> 结尾）"""
    ranges = []
    if sentences:
        first_start = float(sentences[0]["start"])
        if first_start > 0.5:
            ranges.append([0.0, round(first_start, 2)])
        for i in range(len(sentences) - 1):
            gap_start = float(sentences[i]["end"])
            gap_end = float(sentences[i + 1]["start"])
            if gap_end - gap_start > 0.5:
                ranges.append([round(gap_start, 2), round(gap_end, 2)])
        last_end = float(sentences[-1]["end"])
        if duration_sec and duration_sec - last_end > 0.5:
            ranges.append([round(last_end, 2), round(float(duration_sec), 2)])
    for r in raw_music_ranges or []:
        if len(r) == 2 and r[1] - r[0] > 0.4:
            ranges.append([round(float(r[0]), 2), round(float(r[1]), 2)])
    # 合并重叠/相邻的 skip 区间
    if not ranges:
        return []
    ranges.sort(key=lambda x: x[0])
    merged = [ranges[0]]
    for s, e in ranges[1:]:
        if s <= merged[-1][1] + 0.15:
            merged[-1][1] = max(merged[-1][1], e)
        else:
            merged.append([s, e])
    return merged


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

    # 若存在 AI 精校缓存（<标题>.polished.json），读取并按真实标点重新拆合，同时收集音乐/空档 skipRanges！
    polished_path = EPISODES_DIR / f"{raw_title}.polished.json"
    music_ranges = []
    sentences = []
    if polished_path.exists():
        try:
            raw_polished = json.loads(polished_path.read_text(encoding="utf-8"))
            sentences = resegment_polished_sentences(raw_polished, music_ranges_out=music_ranges)
        except Exception as exc:
            print(f"[warn] 读取/重切 {polished_path.name} 失败: {exc}")
            sentences = []
    if not sentences:
        sentences = parse_subtitle_files(sub_files, music_ranges_out=music_ranges)
    exact_duration = round(float(forced_duration), 2) if forced_duration else (round(float(sentences[-1]["end"]), 2) if sentences else 60.0)
    duration_sec = int(round(exact_duration))
    if not sentences:
        # 没有字幕文件的视频暂不公开上架，避免用户点开看到无字幕空页
        return None
    skip_ranges = build_skip_ranges(sentences, max(exact_duration, float(duration_sec)), music_ranges)

    title = meta.get("title") or raw_title
    speaker = meta.get("speaker") or infer_speaker(title, sentences)
    region = meta.get("region") or infer_region(title, speaker, sentences)
    tags = meta.get("tags") or infer_tags(title, sentences)
    difficulty = int(meta["difficulty"]) if meta.get("difficulty") else infer_difficulty(
        title, sentences, duration_sec, source_title=raw_title, speaker=speaker, tags=tags, skip_ranges=skip_ranges
    )
    # 校正已知的常见 ASR 专名与叠词错字
    for s in sentences:
        s["en"] = re.sub(r"\bArianita\s+(?:Lagringa|Liginga)\b", "Ariannita la Gringa", s["en"], flags=re.I)
        s["zh"] = re.sub(r"Arianita\s+(?:Lagringa|Liginga)", "Ariannita la Gringa", s["zh"], flags=re.I)
        s["en"] = re.sub(r"\bIt is a A little bit chilly\b", "It is a little bit chilly", s["en"])
    file_mtime = min((f.stat().st_mtime for f in files if f.exists()), default=datetime.now().timestamp())
    ep_date = meta.get("date") or datetime.fromtimestamp(file_mtime).strftime("%Y/%m/%d")

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
        "date": ep_date,
        "tags": tags,
        "coverGradient": meta.get("coverGradient") or COVER_GRADIENTS[(idx - 1) % len(COVER_GRADIENTS)],
        "coverImage": cover_url,
        "mediaUrl": media_url,
        "audioUrl": audio_url,
        "mediaKind": media_kind if media_url else "",
        "sceneBadge": meta.get("sceneBadge") or tags[0],
        "skipRanges": skip_ranges,
        "sentences": sentences,
    }


def probe_audio_duration(path: Path):
    """优先用 macOS afinfo 读取伴音 .m4a 真实时长，避免不可靠的视频 metadata"""
    if not path or not path.exists():
        return None
    try:
        import subprocess
        res = subprocess.run(["/usr/bin/afinfo", str(path)], capture_output=True, text=True, timeout=8)
        if res.returncode == 0:
            m = re.search(r"estimated duration:\s*([0-9.]+)\s*sec", res.stdout)
            if m:
                return float(m.group(1))
    except Exception:
        return None
    return None


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

    # 0) 读取经用户确认并导出的方案 B 精编/拆集清单（scripts/cut_sheets/trimmed_manifest.json）
    manifest_path = ROOT / "scripts" / "cut_sheets" / "trimmed_manifest.json"
    trimmed_manifest = None
    replaced_titles = set()
    if manifest_path.exists():
        try:
            trimmed_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            replaced_titles = set(trimmed_manifest.get("replacesTitles") or [])
        except Exception as exc:
            print(f"[warn] 读取 trimmed_manifest.json 失败: {exc}")

    for stem, files in ordered_groups:
        # 若该超长集已由用户确认的 Part 1/Part 2 精编副本替代，则保留原文件不动，上架精编副本！
        if stem in replaced_titles:
            continue
        vid = next((f for f in files if f.suffix.lower() in VIDEO_EXTS), None)
        aud = next((f for f in files if f.suffix.lower() in AUDIO_EXTS), None)
        # 跳过正在下载中的（只有字幕/封面还没有任何已完成音视频文件）
        if not vid and not aud:
            continue
        dur = None
        # 有伴音 .m4a 时优先以伴音 afinfo 时长为准，不盲信视频 metadata
        if aud:
            dur = probe_audio_duration(aud)
        if not dur and vid and vid.suffix.lower() == ".mp4":
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

    # 1.5) 上架经用户确认的方案 B 精编/拆集副本（content/episodes/trimmed/），原超长文件完好保留在硬盘
    if trimmed_manifest:
        trimmed_dir = EPISODES_DIR / "trimmed"
        for entry in trimmed_manifest.get("entries", []):
            v_file = trimmed_dir / entry["videoFile"]
            a_file = trimmed_dir / entry["audioFile"]
            c_file = trimmed_dir / entry["coverFile"]
            p_file = trimmed_dir / entry["polishedFile"]
            if not v_file.exists() or not a_file.exists() or not p_file.exists():
                continue
            raw_sents = json.loads(p_file.read_text(encoding="utf-8"))
            for si in range(len(raw_sents) - 1):
                if float(raw_sents[si]["end"]) > float(raw_sents[si + 1]["start"]):
                    raw_sents[si]["end"] = round(float(raw_sents[si + 1]["start"]), 2)
            # 校正已知 ASR 错字与专名
            for s in raw_sents:
                s["en"] = re.sub(r"\bArianita\s+(?:Lagringa|Liginga)\b", "Ariannita la Gringa", s["en"], flags=re.I)
                s["zh"] = re.sub(r"Arianita\s+(?:Lagringa|Liginga)", "Ariannita la Gringa", s["zh"], flags=re.I)
                if s["en"].strip() == "It is a A little bit chilly.":
                    s["en"] = "It is a little bit chilly."
                    s["zh"] = "天气有点冷。"
                if s["en"].strip() == "It's said." and "alone in new york" in entry.get("sourceTitle", "").lower():
                    s["en"] = "It's Sid."
                    s["zh"] = "我是 Sid。"
            dur = probe_audio_duration(a_file) or float(entry.get("durationSec") or 0)
            exact_dur = round(float(dur), 2)
            dur_sec = int(round(exact_dur))
            skips = build_skip_ranges(raw_sents, max(exact_dur, float(dur_sec)), entry.get("internalSkips") or [])
            # 动态重新推断讲者、地区、标签、难度（不再死抄 manifest 旧值）
            ep_title = entry["title"]
            src_title = entry.get("sourceTitle") or ""
            ep_speaker = entry.get("speakerOverride") or infer_speaker(ep_title, raw_sents, source_title=src_title)
            ep_region = infer_region(ep_title + " " + src_title, ep_speaker, raw_sents)
            ep_tags = entry.get("tagsOverride") or infer_tags(ep_title, raw_sents)
            ep_diff = infer_difficulty(
                ep_title, raw_sents, dur_sec, source_title=src_title, speaker=ep_speaker, tags=ep_tags, skip_ranges=skips
            )
            ep_date = entry.get("date") or datetime.fromtimestamp(v_file.stat().st_mtime).strftime("%Y/%m/%d")
            rel_prefix = media_base_url.rstrip("/") if media_base_url else "./content/episodes"
            sub_path = f"{rel_prefix}/trimmed"
            slug = re.sub(r"[^a-zA-Z0-9_-]+", "-", ep_title).strip("-")[:32] or f"trimmed-{counter}"
            part_suffix = entry.get("part", f"p{counter}")
            episodes.append({
                "id": f"local-{counter}-{slug}-{part_suffix}",
                "number": f"EP {counter:02d}",
                "title": ep_title,
                "speaker": ep_speaker,
                "speakerAvatar": "./assets/hosts/cici_round.webp",
                "region": ep_region,
                "difficulty": ep_diff,
                "durationSec": dur_sec,
                "durationLabel": format_duration(dur_sec),
                "date": ep_date,
                "tags": ep_tags,
                "coverGradient": COVER_GRADIENTS[(counter - 1) % len(COVER_GRADIENTS)],
                "coverImage": f"{sub_path}/{quote(c_file.name)}" if c_file.exists() else "",
                "mediaUrl": f"{sub_path}/{quote(v_file.name)}",
                "audioUrl": f"{sub_path}/{quote(a_file.name)}",
                "mediaKind": "video",
                "sceneBadge": ep_tags[0],
                "skipRanges": skips,
                "sentences": raw_sents,
            })
            counter += 1

    # 2) 同时兼容 episodes/ 下的子文件夹模式（排除 trimmed 副本目录）
    folders = sorted(
        [p for p in EPISODES_DIR.iterdir() if p.is_dir() and not p.name.startswith(("_", ".")) and p.name != "trimmed"],
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
