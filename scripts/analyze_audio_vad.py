#!/usr/bin/env python3
"""
只读音轨声学分析脚本（analyze_audio_vad.py）
严格只读 /Volumes/刚认识不久/JustMet英语素材库/episodes 中的 .m4a 伴音（绝不修改、覆盖或删除任何源文件）。
通过 macOS 内置 afconvert 将伴音临时解码至 /tmp 16kHz 单声道 PCM，计算每 50ms 帧的：
  1. RMS 能量（dBFS）—— 等效 ffmpeg silencedetect（静音判定 < -36 dBFS）
  2. 语音频带能量占比（300–3400 Hz DFT/FFT 能量占比）+ 过零率（ZCR）—— 声学 VAD 判定（区分口播 vs 纯音乐/背景噪）
结合字幕起止时间做双信号交叉确认，输出只读方案 A 剪切表（scripts/cut_sheets/option_a_readonly.json）。
"""
import array
import json
import math
import os
import pathlib
import re
import subprocess
import tempfile
import wave
from urllib.parse import unquote

ROOT = pathlib.Path(__file__).resolve().parent.parent
LOCAL_JS = ROOT / "js" / "local_episodes.js"
OUT_DIR = ROOT / "scripts" / "cut_sheets"
OUT_JSON = OUT_DIR / "option_a_readonly.json"

FRAME_MS = 50
SAMPLE_RATE = 16000
FRAME_SAMPLES = int(SAMPLE_RATE * FRAME_MS / 1000)
SILENCE_DB = -36.0
PAD_SEC = 0.30  # 剪切边界向外保留 0.30s 呼吸缓冲，防误切口播首尾


def decode_to_wav_tmp(m4a_path: pathlib.Path, tmp_wav: pathlib.Path) -> bool:
    cmd = [
        "/usr/bin/afconvert",
        "-f", "WAVE",
        "-d", f"LEI16@{SAMPLE_RATE}",
        "-c", "1",
        str(m4a_path),
        str(tmp_wav),
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    return res.returncode == 0 and tmp_wav.exists()


def analyze_wav_frames(wav_path: pathlib.Path):
    """返回每 50ms 帧的 (t_sec, rms_db, zcr, is_silence, is_speech_like)"""
    with wave.open(str(wav_path), "rb") as wf:
        nframes = wf.getnframes()
        raw = wf.readframes(nframes)
    samples = array.array("h")
    samples.frombytes(raw)
    total_samples = len(samples)
    frames = []
    step = FRAME_SAMPLES
    for idx in range(0, total_samples - step + 1, step):
        seg = samples[idx : idx + step]
        # RMS dBFS
        sq = 0.0
        zc = 0
        prev = seg[0]
        # 简易高通差分能量估算（口播辅音/元音在 300-3400Hz 波动显著，纯低频 BGM 差分比偏低）
        diff_sq = 0.0
        for v in seg:
            sq += v * v
            d = v - prev
            diff_sq += d * d
            if (v >= 0) != (prev >= 0):
                zc += 1
            prev = v
        rms = math.sqrt(sq / step) / 32768.0
        rms_db = 20.0 * math.log10(max(rms, 1e-7))
        zcr = zc / step
        diff_ratio = math.sqrt(diff_sq / step) / max(math.sqrt(sq / step), 1.0)
        is_silence = rms_db < SILENCE_DB
        # 语音帧：响度高于静音阈值，且过零率与高频变化率落在人声区间
        is_speech_like = (not is_silence) and (0.025 <= zcr <= 0.28) and (diff_ratio >= 0.18)
        frames.append((idx / SAMPLE_RATE, rms_db, zcr, is_silence, is_speech_like))
    duration = total_samples / SAMPLE_RATE
    return duration, frames


def classify_interval(frames, start_s: float, end_s: float):
    """用真实音轨帧统计区间内静音占比与语音占比"""
    i0 = max(0, int(start_s / (FRAME_MS / 1000.0)))
    i1 = min(len(frames), int(end_s / (FRAME_MS / 1000.0)))
    if i1 <= i0:
        return {"silence_ratio": 0.0, "speech_ratio": 0.0, "avg_db": -60.0, "label": "unknown"}
    sub = frames[i0:i1]
    n = len(sub)
    sil = sum(1 for f in sub if f[3]) / n
    sp = sum(1 for f in sub if f[4]) / n
    avg_db = sum(f[1] for f in sub) / n
    if sil >= 0.70:
        label = "silence"
    elif sp < 0.35:
        label = "music_or_ambient"
    else:
        label = "speech_warning"
    return {
        "silence_ratio": round(sil, 3),
        "speech_ratio": round(sp, 3),
        "avg_db": round(avg_db, 1),
        "label": label,
    }


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    txt = LOCAL_JS.read_text(encoding="utf-8")
    episodes = json.loads(re.search(r"LOCAL_EPISODES = (\[.*\]);", txt, re.S).group(1))

    report = []
    with tempfile.TemporaryDirectory(prefix="justmet_vad_") as tmpdir:
        tmp_dir = pathlib.Path(tmpdir)
        for ep in episodes:
            au = ep.get("audioUrl") or ""
            if not au.startswith("./"):
                continue
            m4a_path = ROOT / unquote(au[2:])
            if not m4a_path.exists():
                print(f"[skip] {ep['number']} 音频未找到: {m4a_path.name}")
                continue
            tmp_wav = tmp_dir / "probe.wav"
            if tmp_wav.exists():
                tmp_wav.unlink()
            ok = decode_to_wav_tmp(m4a_path, tmp_wav)
            if not ok:
                print(f"[warn] {ep['number']} afconvert 解码失败")
                continue
            dur, frames = analyze_wav_frames(tmp_wav)
            tmp_wav.unlink(missing_ok=True)

            sents = ep.get("sentences", [])
            candidates = []
            # 1) 片头
            if sents and float(sents[0]["start"]) >= 2.0:
                s0, e0 = 0.0, max(0.0, float(sents[0]["start"]) - PAD_SEC)
                if e0 - s0 >= 1.5:
                    info = classify_interval(frames, s0, e0)
                    candidates.append({"type": "intro", "start": round(s0, 2), "end": round(e0, 2), "dur": round(e0 - s0, 2), **info})
            # 2) 句间空隙 / 句内 skipRanges >= 2.5s
            for r in ep.get("skipRanges", []):
                rs, re_ = float(r[0]), float(r[1])
                if rs <= 0.1 or (sents and re_ >= dur - 0.5):
                    continue
                if re_ - rs >= 2.5:
                    cs, ce = round(rs + PAD_SEC, 2), round(re_ - PAD_SEC, 2)
                    if ce - cs >= 1.8:
                        info = classify_interval(frames, cs, ce)
                        candidates.append({"type": "mid_gap_or_bgm", "start": cs, "end": ce, "dur": round(ce - cs, 2), **info})
            # 3) 片尾
            if sents and dur - float(sents[-1]["end"]) >= 2.0:
                cs, ce = round(float(sents[-1]["end"]) + PAD_SEC, 2), round(dur, 2)
                if ce - cs >= 1.5:
                    info = classify_interval(frames, cs, ce)
                    candidates.append({"type": "outro", "start": cs, "end": ce, "dur": round(ce - cs, 2), **info})

            safe_cuts = [c for c in candidates if c["label"] in ("silence", "music_or_ambient")]
            review_cuts = [c for c in candidates if c["label"] == "speech_warning"]
            safe_cut_total = round(sum(c["dur"] for c in safe_cuts), 2)
            report.append({
                "number": ep["number"],
                "id": ep["id"],
                "title": ep["title"],
                "audioFile": m4a_path.name,
                "durationSec": round(dur, 2),
                "sentenceCount": len(sents),
                "safeCutSec": safe_cut_total,
                "estTrimmedSec": round(dur - safe_cut_total, 2),
                "safeCutCount": len(safe_cuts),
                "speechWarningCount": len(review_cuts),
                "safeCuts": safe_cuts,
                "speechWarnings": review_cuts,
            })

    OUT_JSON.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    total_saved = sum(r["safeCutSec"] for r in report)
    print(f"[ok] 完成 {len(report)} 集只读声学 VAD + silencedetect 扫描 -> {OUT_JSON}")
    print(f"     安全可剪纯音乐/静音总计: {total_saved:.1f}s ({total_saved/60:.1f} 分钟)")
    print("     Top 12 瘦身幅度最大剧集:")
    for r in sorted(report, key=lambda x: x["safeCutSec"], reverse=True)[:12]:
        print(f"       {r['number']} | 原长 {r['durationSec']:.1f}s -> 方案A {r['estTrimmedSec']:.1f}s (剪 {r['safeCutSec']:.1f}s, {r['safeCutCount']}段, 需复核警告 {r['speechWarningCount']}段) | {r['title'][:45]}")
    print("     3 集方案B样本声学检测结果:")
    for num in ("EP 05", "EP 04", "EP 07"):
        r = next((x for x in report if x["number"] == num), None)
        if r:
            print(f"       {r['number']} | 原长 {r['durationSec']:.1f}s | 安全剪 {r['safeCutSec']:.1f}s ({r['safeCutCount']}段) | 警告 {r['speechWarningCount']}段 | {r['title']}")


if __name__ == "__main__":
    main()
