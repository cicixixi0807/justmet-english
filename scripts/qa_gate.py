#!/usr/bin/env python3
"""
独立质检子 Agent 专用硬性质量门禁脚本（qa_gate.py）
任一红线不达标即返回非 0 退出码（FAIL），强制打回主 Agent 返工！

用法：
  python3 scripts/qa_gate.py            # 全量检查（含本地音视频/封面存在性 + afinfo 伴音时长核对）
  python3 scripts/qa_gate.py --no-media # 无本地媒资环境专用（跳过硬盘音视频检查，严格执行全部字幕、skipRanges 与品牌红线）
"""
import argparse
import json
import pathlib
import re
import subprocess
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


def probe_afinfo_duration(path: pathlib.Path):
    if not path.exists():
        return None
    try:
        res = subprocess.run(["/usr/bin/afinfo", str(path)], capture_output=True, text=True, timeout=8)
        if res.returncode == 0:
            m = re.search(r"estimated duration:\s*([0-9.]+)\s*sec", res.stdout)
            if m:
                return float(m.group(1))
    except Exception:
        return None
    return None


def is_interval_covered(start: float, end: float, skip_ranges, tol: float = 0.25) -> bool:
    """检查 [start, end] 是否被 skip_ranges 覆盖（允许边界容差 tol 秒）"""
    if end - start <= 0.5:
        return True
    cur = start + tol
    target = end - tol
    if cur >= target:
        return True
    for rs, re_ in sorted((float(r[0]), float(r[1])) for r in skip_ranges if isinstance(r, list) and len(r) == 2):
        if re_ <= cur:
            continue
        if rs > cur + 0.15:
            return False
        cur = max(cur, re_)
        if cur >= target:
            return True
    return cur >= target


def main():
    parser = argparse.ArgumentParser(description="Just Met 独立质检门禁脚本")
    parser.add_argument(
        "--no-media",
        action="store_true",
        help="无本地 content/episodes 媒资时跳过音视频/封面磁盘存在性检查，仍严格执行全部字幕、skipRanges 与品牌红线",
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
    uncovered_intro = 0
    uncovered_gaps = 0
    uncovered_outro = 0
    half_sent_pairs = 0
    audio_dur_mismatch = 0

    for ep in data:
        sents = ep.get("sentences", [])
        skips = ep.get("skipRanges", [])
        dur_sec = float(ep.get("durationSec") or 0)
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
            # 有伴音 .m4a 时以 afinfo 伴音时长为准校验 durationSec 与片尾覆盖
            au = ep.get("audioUrl") or ""
            if au.startswith("./"):
                aud_path = ROOT / unquote(au[2:])
                aud_dur = probe_afinfo_duration(aud_path)
                if aud_dur is not None:
                    if abs(aud_dur - dur_sec) > 2.5:
                        audio_dur_mismatch += 1
                        failures.append(
                            f"{ep['number']} durationSec={dur_sec:.1f}s 与伴音 afinfo={aud_dur:.1f}s 不一致（请重跑 sync_episodes.py）"
                        )
                    dur_sec = aud_dur

        for r in skips:
            if not (isinstance(r, list) and len(r) == 2 and float(r[0]) < float(r[1])):
                invalid_skips += 1

        if sents:
            # 1) 片头（0 -> 首句 > 0.5s）必须被 skipRanges 覆盖
            first_start = float(sents[0]["start"])
            if first_start > 0.5 and not is_interval_covered(0.0, first_start, skips):
                uncovered_intro += 1
                failures.append(f"{ep['number']} 片头 [0.0, {first_start:.2f}] 未被 skipRanges 覆盖")

            # 2) 片尾（末句 -> durationSec > 0.5s）必须被 skipRanges 覆盖
            last_end = float(sents[-1]["end"])
            if dur_sec - last_end > 0.5 and not is_interval_covered(last_end, dur_sec, skips):
                uncovered_outro += 1
                failures.append(f"{ep['number']} 片尾 [{last_end:.2f}, {dur_sec:.2f}] 未被 skipRanges 覆盖")

        for i, s in enumerate(sents):
            total_sents += 1
            en = (s.get("en") or "").strip()
            zh = (s.get("zh") or "").strip()
            s_start = float(s["start"])
            s_end = float(s["end"])
            internal_skip = sum(
                max(0.0, min(s_end, float(r[1])) - max(s_start, float(r[0])))
                for r in skips
                if isinstance(r, list) and len(r) == 2
            )
            spoken_dur = (s_end - s_start) - internal_skip
            wc = max(1, len(en.split()))
            if not zh:
                empty_zh += 1
            elif not re.search(r"[\u4e00-\u9fffA-Za-z0-9]", zh):
                punct_only_zh += 1
            if spoken_dur > max(6.0, wc * 0.85 + 3.0):
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
                nxt_start = float(nxt["start"])
                nxt_en = (nxt.get("en") or "").strip()
                if s_end > nxt_start:
                    overlaps += 1
                if en == nxt_en and s_start == nxt_start:
                    adj_dups += 1
                # 3) 句间空隙 > 0.5s 必须被 skipRanges 覆盖
                if nxt_start - s_end > 0.5 and not is_interval_covered(s_end, nxt_start, skips):
                    uncovered_gaps += 1
                    if uncovered_gaps <= 5:
                        failures.append(f"{ep['number']} #{s['id']}->{nxt['id']} 句间空隙 [{s_end:.2f}, {nxt_start:.2f}] 未被 skipRanges 覆盖")
                # 4) 相邻半截句对检查：上一句缺真正句末标点（不含合法省略号+大写新句）或下一句小写续句
                prev_has_end = bool(re.search(r'(?<!\.\.)[.?!]["\'\u201d\u2019]?$', en))
                prev_ellipsis_to_upper = en.endswith("...") and bool(re.match(r"^[A-Z\"'\u201c]", nxt_en))
                nxt_starts_lower = bool(re.match(r"^[a-z]", nxt_en))
                if (not prev_has_end and not prev_ellipsis_to_upper) or nxt_starts_lower:
                    half_sent_pairs += 1
                    if half_sent_pairs <= 5:
                        failures.append(f"{ep['number']} #{s['id']}->{nxt['id']} 相邻半截句对: '{en[-30:]}' | '{nxt_en[:30]}'")

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
    if uncovered_intro > 0:
        failures.append(f"存在 {uncovered_intro} 集片头未覆盖 skipRanges")
    if uncovered_gaps > 0:
        failures.append(f"存在 {uncovered_gaps} 处句间空隙(>0.5s)未覆盖 skipRanges")
    if uncovered_outro > 0:
        failures.append(f"存在 {uncovered_outro} 集片尾未覆盖 skipRanges")
    if half_sent_pairs > 0:
        failures.append(f"存在 {half_sent_pairs} 组相邻半截句对（上一句缺句末标点或下一句小写续句）")
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
        print("[mode] --no-media（跳过本地硬盘媒资存在性及 afinfo 检查，严格执行全部字幕、skipRanges 与品牌红线）")
    print(f"剧集数: {len(data)} | 总句数: {total_sents}")
    print(
        f"缺中文: {empty_zh} | 纯标点中文: {punct_only_zh} | 超长BGM拖尾: {bgm_bloated} | "
        f"重叠: {overlaps} | 舞台/音乐卡: {stage_cards} | 残句: {garbled_cards} | "
        f"相邻重复: {adj_dups} | 半截句对: {half_sent_pairs} | 缺文件: {missing_media}"
    )
    print(
        f"未覆盖片头: {uncovered_intro} | 未覆盖句间(>0.5s): {uncovered_gaps} | "
        f"未覆盖片尾: {uncovered_outro} | 伴音时长偏差: {audio_dur_mismatch}"
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
