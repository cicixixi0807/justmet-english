#!/usr/bin/env python3
"""
独立质检子 Agent 专用硬性质量门禁脚本（qa_gate.py）
任一红线不达标即返回非 0 退出码（FAIL），强制打回主 Agent 返工！

用法：
  python3 scripts/qa_gate.py            # 全量检查（含本地音视频/封面文件存在性）
  python3 scripts/qa_gate.py --no-media # 无本地媒资环境专用（跳过硬盘音视频检查，严格执行全部字幕与品牌红线）
"""
import argparse
import json
import pathlib
import re
import sys
from urllib.parse import unquote

ROOT = pathlib.Path(__file__).resolve().parent.parent
LOCAL_JS = ROOT / "js" / "local_episodes.js"

# 与 AGENTS.md 完全对齐的红线阈值
MAX_LOW_START_RATE = 0.5   # 小写开头半截句比例上限（%）
MAX_NO_PUNCT_RATE = 0.6    # 缺句末标点比例上限（%）

STAGE_CARD_RE = re.compile(
    r"\((?:friendly\s+music|upbeat\s+music|soft\s+music|gentle\s+music|music|applause|laughter|cheering|alarm\s+beeping|clapping|sighs|groans)\)",
    re.I,
)
GARBLED_OUTRO_RE = re.compile(r"\bI'm\s+don't\b", re.I)


def main():
    parser = argparse.ArgumentParser(description="Just Met 独立质检门禁脚本")
    parser.add_argument(
        "--no-media",
        action="store_true",
        help="无本地 content/episodes 媒资时跳过音视频/封面磁盘存在性检查，仍严格执行全部字幕与品牌红线",
    )
    args = parser.parse_args()

    txt = LOCAL_JS.read_text(encoding="utf-8")
    data = json.loads(re.search(r"LOCAL_EPISODES = (\[.*\]);", txt, re.S).group(1))

    failures = []
    total_sents = 0
    empty_zh = 0
    punct_only_zh = 0
    bgm_bloated = 0
    overlaps = 0
    low_starts = 0
    no_punct = 0
    missing_media = 0
    stage_cards = 0
    garbled_cards = 0
    adj_dups = 0
    invalid_skips = 0

    for ep in data:
        sents = ep.get("sentences", [])
        if len(sents) <= 1:
            failures.append(f"{ep['number']} ({ep['title']}): 无有效字幕 (n={len(sents)})")

        if not args.no_media:
            for key in ("mediaUrl", "audioUrl", "coverImage"):
                val = ep.get(key) or ""
                if val.startswith("./"):
                    rel = unquote(val[2:])
                    if not (ROOT / rel).exists():
                        missing_media += 1
                        failures.append(f"{ep['number']} 缺失文件: {rel}")

        for r in ep.get("skipRanges", []):
            if not (isinstance(r, list) and len(r) == 2 and float(r[0]) < float(r[1])):
                invalid_skips += 1

        for i, s in enumerate(sents):
            total_sents += 1
            en = (s.get("en") or "").strip()
            zh = (s.get("zh") or "").strip()
            dur = float(s["end"]) - float(s["start"])
            wc = max(1, len(en.split()))
            if not zh:
                empty_zh += 1
            elif not re.search(r"[\u4e00-\u9fffA-Za-z0-9]", zh):
                punct_only_zh += 1
            if dur > max(12.0, wc * 0.75 + 3.0):
                bgm_bloated += 1
            if re.match(r"^[a-z]", en):
                low_starts += 1
            if not re.search(r'[.?!\"\'\)”’]$', en):
                no_punct += 1
            if STAGE_CARD_RE.search(en):
                stage_cards += 1
            if GARBLED_OUTRO_RE.search(en):
                garbled_cards += 1
            if i + 1 < len(sents):
                nxt = sents[i + 1]
                if float(s["end"]) > float(nxt["start"]):
                    overlaps += 1
                if en == (nxt.get("en") or "").strip() and float(s["start"]) == float(nxt["start"]):
                    adj_dups += 1

    low_rate = (low_starts / max(1, total_sents)) * 100
    no_p_rate = (no_punct / max(1, total_sents)) * 100

    if empty_zh > 0:
        failures.append(f"存在 {empty_zh} 句缺少中文翻译")
    if punct_only_zh > 0:
        failures.append(f"存在 {punct_only_zh} 句纯标点无效中文（如 '。'）")
    if bgm_bloated > 0:
        failures.append(f"存在 {bgm_bloated} 句夹杂超长纯音乐拖尾")
    if overlaps > 0:
        failures.append(f"存在 {overlaps} 处时间轴重叠")
    if stage_cards > 0:
        failures.append(f"存在 {stage_cards} 句舞台/音乐说明（如 (friendly music)/(Applause)）被当成学习卡片")
    if garbled_cards > 0:
        failures.append(f"存在 {garbled_cards} 句精校失败残句（如 I'm don't）")
    if adj_dups > 0:
        failures.append(f"存在 {adj_dups} 处相邻重复字幕卡片")
    if invalid_skips > 0:
        failures.append(f"存在 {invalid_skips} 处非法 skipRanges 区间")
    if low_rate > MAX_LOW_START_RATE:
        failures.append(f"小写开头半截句比例过高：{low_rate:.2f}% (> {MAX_LOW_START_RATE}%)")
    if no_p_rate > MAX_NO_PUNCT_RATE:
        failures.append(f"缺句末标点比例过高：{no_p_rate:.2f}% (> {MAX_NO_PUNCT_RATE}%)")

    # 品牌文案红线检查
    for fname in ("index.html", "js/data.js", "js/views.js", "js/practice.js"):
        content = (ROOT / fname).read_text(encoding="utf-8")
        if "CiCi" in content:
            failures.append(f"{fname} 出现错误大小写 CiCi")
        if "免费" in content:
            failures.append(f"{fname} 出现禁用词「免费」")
        if "全年" in content:
            failures.append(f"{fname} 出现禁用词「全年」")

    print("=== Just Met 独立质检门禁报告 ===")
    if args.no_media:
        print("[mode] --no-media（跳过本地硬盘媒资存在性检查，严格执行全部字幕与品牌红线）")
    print(f"剧集数: {len(data)} | 总句数: {total_sents}")
    print(
        f"缺中文: {empty_zh} | 纯标点中文: {punct_only_zh} | 超长BGM拖尾: {bgm_bloated} | "
        f"重叠: {overlaps} | 舞台/音乐卡: {stage_cards} | 残句: {garbled_cards} | "
        f"相邻重复: {adj_dups} | 缺文件: {missing_media}"
    )
    print(
        f"小写开头: {low_starts} ({low_rate:.2f}% <= {MAX_LOW_START_RATE}%) | "
        f"缺句末标点: {no_punct} ({no_p_rate:.2f}% <= {MAX_NO_PUNCT_RATE}%)"
    )

    if failures:
        print("\n❌ VERDICT: FAIL（禁止交付，必须先修复以下问题）：")
        for f in failures[:15]:
            print("  -", f)
        sys.exit(1)
    else:
        print("\n✅ VERDICT: PASS（全部红线指标达标，允许交付）")
        sys.exit(0)


if __name__ == "__main__":
    main()
