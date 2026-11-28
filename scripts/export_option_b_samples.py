#!/usr/bin/env python3
"""
方案 B（版本 2：拆成 Part 1 / Part 2 两期独立短课）非破坏性导出脚本（export_option_b_samples.py）
严格只读原文件，绝不覆盖、替换或删除 /Volumes/刚认识不久/JustMet英语素材库/episodes 中的任何源视频或伴音！
导出结果统一写入 episodes/trimmed/ 子目录，并生成：
  - <新标题>.trimmed.mp4（帧精确拼接，零关键帧偏移）
  - <新标题>.trimmed.m4a（与视频毫秒级同步）
  - <新标题>.jpg（从导出视频提取的高清封面）
  - <新标题>.polished.json（按精确累计偏移 remap_time 重算后的双语字幕、IPA 与重点词）
  - scripts/cut_sheets/trimmed_manifest.json（供 sync_episodes.py 用新拆集替代原超长集上架）
"""
import json
import pathlib
import re
import shutil
import subprocess
import sys
from urllib.parse import unquote

ROOT = pathlib.Path(__file__).resolve().parent.parent
EPISODES_DIR = ROOT / "content" / "episodes"
TRIMMED_DIR = EPISODES_DIR / "trimmed"
LOCAL_JS = ROOT / "js" / "local_episodes.js"
DRAFT_JSON = ROOT / "scripts" / "cut_sheets" / "option_b_3samples_draft.json"
MANIFEST_JSON = ROOT / "scripts" / "cut_sheets" / "trimmed_manifest.json"

PAD_SEC = 0.25


def find_ffmpeg() -> str:
    for p in (
        shutil.which("ffmpeg"),
        "/opt/homebrew/bin/ffmpeg",
        "/usr/local/bin/ffmpeg",
        "/Applications/VideoFusion-macOS.app/Contents/Resources/ffmpeg",
    ):
        if p and pathlib.Path(p).exists():
            return str(p)
    raise RuntimeError("未找到 ffmpeg，请先安装或确认路径。")


def pick_video_encoder(ffmpeg_bin: str):
    res = subprocess.run([ffmpeg_bin, "-encoders"], capture_output=True, text=True)
    if "h264_videotoolbox" in res.stdout:
        return ["-c:v", "h264_videotoolbox", "-allow_sw", "1", "-b:v", "1800k", "-pix_fmt", "yuv420p"]
    if "libx264" in res.stdout:
        return ["-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-pix_fmt", "yuv420p"]
    return ["-c:v", "mpeg4", "-q:v", "5"]


def sanitize_filename(name: str) -> str:
    return re.sub(r'[\\/*?"<>|]', "_", name).strip()


def probe_afinfo_dur(path: pathlib.Path) -> float:
    res = subprocess.run(["/usr/bin/afinfo", str(path)], capture_output=True, text=True)
    m = re.search(r"estimated duration:\s*([0-9.]+)\s*sec", res.stdout)
    return float(m.group(1)) if m else 0.0


def build_filter_and_export(ffmpeg_bin: str, vid_enc, src_vid: pathlib.Path, src_aud: pathlib.Path, windows, out_vid: pathlib.Path, out_aud: pathlib.Path, out_jpg: pathlib.Path):
    n = len(windows)
    # 1) 导出帧精确拼接视频（静音，与现有双轨架构保持一致，且体积更小）
    v_filters = []
    v_inputs = []
    for i, (s, e) in enumerate(windows):
        v_filters.append(f"[0:v]trim=start={s:.3f}:end={e:.3f},setpts=PTS-STARTPTS[v{i}]")
        v_inputs.append(f"[v{i}]")
    v_filters.append(f"{''.join(v_inputs)}concat=n={n}:v=1:a=0[vout]")
    v_cmd = [
        ffmpeg_bin, "-y", "-hide_banner", "-loglevel", "error",
        "-i", str(src_vid),
        "-filter_complex", ";".join(v_filters),
        "-map", "[vout]",
        "-an",
        *vid_enc,
        "-movflags", "+faststart",
        str(out_vid),
    ]
    subprocess.run(v_cmd, check=True)

    # 2) 导出毫秒级同步伴音 .m4a
    a_filters = []
    a_inputs = []
    for i, (s, e) in enumerate(windows):
        a_filters.append(f"[0:a]atrim=start={s:.3f}:end={e:.3f},asetpts=PTS-STARTPTS[a{i}]")
        a_inputs.append(f"[a{i}]")
    a_filters.append(f"{''.join(a_inputs)}concat=n={n}:v=0:a=1[aout]")
    a_cmd = [
        ffmpeg_bin, "-y", "-hide_banner", "-loglevel", "error",
        "-i", str(src_aud),
        "-filter_complex", ";".join(a_filters),
        "-map", "[aout]",
        "-c:a", "aac", "-b:a", "128k",
        str(out_aud),
    ]
    subprocess.run(a_cmd, check=True)

    # 3) 从导出视频第 3 秒提取高清封面
    j_cmd = [
        ffmpeg_bin, "-y", "-hide_banner", "-loglevel", "error",
        "-ss", "3.0", "-i", str(out_vid),
        "-vframes", "1", "-q:v", "3",
        str(out_jpg),
    ]
    subprocess.run(j_cmd, check=True)


def remap_sentences(orig_sents, windows):
    """按拼接后的 windows 列表精确重算每句 start/end，保留双语、IPA、重点词"""
    remapped = []
    offset = 0.0
    for w_start, w_end in windows:
        w_dur = w_end - w_start
        for s in orig_sents:
            st = float(s["start"])
            en = float(s["end"])
            # 只保留完整落在该窗口内的句子
            if st >= w_start - 0.05 and en <= w_end + 0.05:
                new_st = round(max(offset, offset + (st - w_start)), 2)
                new_en = round(min(offset + w_dur, offset + (en - w_start)), 2)
                if new_en > new_st + 0.05:
                    ns = dict(s)
                    ns["start"] = new_st
                    ns["end"] = new_en
                    remapped.append(ns)
        offset += w_dur

    # 确保 0 重叠并重编 id
    for i in range(len(remapped) - 1):
        ns = float(remapped[i + 1]["start"])
        if remapped[i]["end"] > ns - 0.04:
            remapped[i]["end"] = round(min(ns, max(remapped[i]["start"] + 0.10, ns - 0.04)), 2)
    for idx, s in enumerate(remapped, start=1):
        s["id"] = idx
    return remapped


def main():
    ffmpeg_bin = find_ffmpeg()
    vid_enc = pick_video_encoder(ffmpeg_bin)
    print(f"[info] 使用 ffmpeg: {ffmpeg_bin} | 编码器: {' '.join(vid_enc)}")

    TRIMMED_DIR.mkdir(parents=True, exist_ok=True)
    txt = LOCAL_JS.read_text(encoding="utf-8")
    episodes = json.loads(re.search(r"LOCAL_EPISODES = (\[.*\]);", txt, re.S).group(1))
    ep_by_num = {e["number"]: e for e in episodes}
    draft = json.loads(DRAFT_JSON.read_text(encoding="utf-8"))

    manifest = {
        "scheme": "Option B - Version 2 (Part 1 / Part 2 splits for 3 samples)",
        "replacesTitles": [],
        "entries": [],
    }

    for sample in draft["samples"]:
        num = sample["number"]
        ep = ep_by_num[num]
        src_vid = ROOT / unquote(ep["mediaUrl"][2:])
        src_aud = ROOT / unquote(ep["audioUrl"][2:])
        orig_dur = float(sample["originalDurationSec"])
        manifest["replacesTitles"].append(ep["title"])

        for part_key in ("part1", "part2"):
            part = sample["partSplitOption"][part_key]
            new_title = part["newTitle"]
            safe_stem = sanitize_filename(new_title)
            out_vid = TRIMMED_DIR / f"{safe_stem}.trimmed.mp4"
            out_aud = TRIMMED_DIR / f"{safe_stem}.trimmed.m4a"
            out_jpg = TRIMMED_DIR / f"{safe_stem}.jpg"
            out_sub = TRIMMED_DIR / f"{safe_stem}.polished.json"

            # 每段加 0.25s 呼吸缓冲（并防止窗口重叠）
            windows = []
            for seg in part["segments"]:
                ws = round(max(0.0, float(seg["startSec"]) - PAD_SEC), 3)
                we = round(min(orig_dur, float(seg["endSec"]) + PAD_SEC), 3)
                if windows and ws <= windows[-1][1]:
                    ws = round(windows[-1][1] + 0.01, 3)
                windows.append((ws, we))

            print(f"\n[export] {num} {part_key} -> {safe_stem} ({len(windows)} 段, 预计 {sum(e-s for s,e in windows):.1f}s)")
            build_filter_and_export(ffmpeg_bin, vid_enc, src_vid, src_aud, windows, out_vid, out_aud, out_jpg)
            actual_dur = probe_afinfo_dur(out_aud)
            remapped = remap_sentences(ep["sentences"], windows)
            out_sub.write_text(json.dumps(remapped, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"  [ok] 导出完成: afinfo={actual_dur:.2f}s | 字幕={len(remapped)}句 | mp4={out_vid.stat().st_size/1024/1024:.1f}MB | m4a={out_aud.stat().st_size/1024/1024:.1f}MB")

            manifest["entries"].append({
                "sourceNumber": num,
                "sourceTitle": ep["title"],
                "part": part_key,
                "title": new_title,
                "speaker": ep["speaker"],
                "region": ep["region"],
                "difficulty": ep["difficulty"],
                "tags": ep["tags"],
                "sceneBadge": ep["sceneBadge"],
                "videoFile": out_vid.name,
                "audioFile": out_aud.name,
                "coverFile": out_jpg.name,
                "polishedFile": out_sub.name,
                "durationSec": round(actual_dur, 2),
                "windows": windows,
            })

    MANIFEST_JSON.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n[done] 全部 6 个 Part 1/Part 2 副本已安全导出至 {TRIMMED_DIR}，清单写入 {MANIFEST_JSON}")


if __name__ == "__main__":
    main()
