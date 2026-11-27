#!/usr/bin/env python3
"""
独立质检子 Agent 专用硬性质量门禁脚本（qa_gate.py）
任一红线不达标即返回非 0 退出码（FAIL），强制打回主 Agent 返工！
"""
import json
import pathlib
import re
import sys
from urllib.parse import unquote

ROOT = pathlib.Path(__file__).resolve().parent.parent
LOCAL_JS = ROOT / "js" / "local_episodes.js"


def main():
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

    for ep in data:
        sents = ep.get("sentences", [])
        if len(sents) <= 1:
            failures.append(f"{ep['number']} ({ep['title']}): 无有效字幕 (n={len(sents)})")
        for key in ("mediaUrl", "audioUrl", "coverImage"):
            val = ep.get(key) or ""
            if val.startswith("./"):
                rel = unquote(val[2:])
                if not (ROOT / rel).exists():
                    missing_media += 1
                    failures.append(f"{ep['number']} 缺失文件: {rel}")

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
            if i + 1 < len(sents) and float(s["end"]) > float(sents[i + 1]["start"]):
                overlaps += 1

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
    if low_rate > 0.5:
        failures.append(f"小写开头半截句比例过高：{low_rate:.2f}% (> 0.5%)")
    if no_p_rate > 0.6:
        failures.append(f"缺句末标点比例过高：{no_p_rate:.2f}% (> 0.6%)")

    # 品牌文案红线检查
    for fname in ("index.html", "js/data.js", "js/views.js", "js/practice.js"):
        content = (ROOT / fname).read_text(encoding="utf-8")
        if "CiCi" in content:
            failures.append(f"{fname} 出现错误大小写 CiCi")
        if "免费" in content:
            failures.append(f"{fname} 出现禁用词「免费」")

    print(f"=== Just Met 独立质检门禁报告 ===")
    print(f"剧集数: {len(data)} | 总句数: {total_sents}")
    print(f"缺中文: {empty_zh} | 纯标点中文: {punct_only_zh} | 超长BGM拖尾: {bgm_bloated} | 重叠: {overlaps} | 缺文件: {missing_media}")
    print(f"小写开头: {low_starts} ({low_rate:.2f}%) | 缺句末标点: {no_punct} ({no_p_rate:.2f}%)")

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
