#!/usr/bin/env python3
"""
第二批全库 ≤10 分钟非破坏性导出脚本（export_batch2_under10m.py）
- 把剩余全部 19 集 >10 分钟的 2★–5★ 进阶课按自然句/场景边界拆成 5–9.5 分钟短课（绝不带“精编版”三字）。
- 100% 非破坏性：原视频/伴音完整保留在 episodes/ 不动，新副本输出至 episodes/trimmed/。
- 顺带清理所有片头长音乐（如 EP 10/20 13s 片头）与片尾长音乐（如 EP 09 58s 片尾）。
"""
import json
import pathlib
import re
import shutil
import subprocess
from urllib.parse import unquote

ROOT = pathlib.Path(__file__).resolve().parent.parent
EPISODES_DIR = ROOT / "content" / "episodes"
TRIMMED_DIR = EPISODES_DIR / "trimmed"
LOCAL_JS = ROOT / "js" / "local_episodes.js"
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
    raise RuntimeError("未找到 ffmpeg")


def sanitize_filename(name: str) -> str:
    return re.sub(r'[\\/*?"<>|]', "_", name).strip()


def probe_afinfo_dur(path: pathlib.Path) -> float:
    res = subprocess.run(["/usr/bin/afinfo", str(path)], capture_output=True, text=True)
    m = re.search(r"estimated duration:\s*([0-9.]+)\s*sec", res.stdout)
    return float(m.group(1)) if m else 0.0


def build_filter_and_export(ffmpeg_bin, src_vid, src_aud, windows, out_vid, out_aud, out_jpg):
    n = len(windows)
    v_cmd = [ffmpeg_bin, "-y", "-hide_banner", "-loglevel", "error"]
    v_filters, v_inputs = [], []
    for i, (s, e) in enumerate(windows):
        v_cmd.extend(["-ss", f"{s:.3f}", "-to", f"{e:.3f}", "-i", str(src_vid)])
        v_filters.append(f"[{i}:v]scale=-2:min(720\\,ih),setpts=PTS-STARTPTS[v{i}]")
        v_inputs.append(f"[v{i}]")
    if n == 1:
        v_cmd.extend(["-filter_complex", v_filters[0], "-map", "[v0]"])
    else:
        v_filters.append(f"{''.join(v_inputs)}concat=n={n}:v=1:a=0[vout]")
        v_cmd.extend(["-filter_complex", ";".join(v_filters), "-map", "[vout]"])
    v_cmd.extend(["-an", "-c:v", "h264_videotoolbox", "-allow_sw", "1", "-b:v", "1500k", "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(out_vid)])
    subprocess.run(v_cmd, check=True)

    a_cmd = [ffmpeg_bin, "-y", "-hide_banner", "-loglevel", "error"]
    a_filters, a_inputs = [], []
    for i, (s, e) in enumerate(windows):
        a_cmd.extend(["-ss", f"{s:.3f}", "-to", f"{e:.3f}", "-i", str(src_aud)])
        a_filters.append(f"[{i}:a]asetpts=PTS-STARTPTS[a{i}]")
        a_inputs.append(f"[a{i}]")
    if n == 1:
        a_cmd.extend(["-filter_complex", a_filters[0], "-map", "[a0]"])
    else:
        a_filters.append(f"{''.join(a_inputs)}concat=n={n}:v=0:a=1[aout]")
        a_cmd.extend(["-filter_complex", ";".join(a_filters), "-map", "[aout]"])
    a_cmd.extend(["-c:a", "aac", "-b:a", "128k", str(out_aud)])
    subprocess.run(a_cmd, check=True)

    subprocess.run([
        ffmpeg_bin, "-y", "-hide_banner", "-loglevel", "error",
        "-ss", "3.0", "-i", str(out_vid), "-vframes", "1", "-q:v", "3", str(out_jpg),
    ], check=True)


def remap_sentences(orig_sents, windows):
    remapped = []
    offset = 0.0
    for w_start, w_end in windows:
        w_dur = w_end - w_start
        for s in orig_sents:
            st, en = float(s["start"]), float(s["end"])
            if st >= w_start - 0.05 and en <= w_end + 0.05:
                new_st = round(max(offset, offset + (st - w_start)), 2)
                new_en = round(min(offset + w_dur, offset + (en - w_start)), 2)
                if new_en > new_st + 0.05:
                    ns = dict(s)
                    ns["start"] = new_st
                    ns["end"] = new_en
                    remapped.append(ns)
        offset += w_dur
    for i in range(len(remapped) - 1):
        ns = float(remapped[i + 1]["start"])
        if remapped[i]["end"] > ns - 0.04:
            remapped[i]["end"] = round(min(ns, max(remapped[i]["start"] + 0.10, ns - 0.04)), 2)
    for idx, s in enumerate(remapped, start=1):
        s["id"] = idx
    return remapped


def find_best_split_index(sents, target_ratio=0.5, min_sec=170.0, max_sec=555.0):
    t_start = float(sents[0]["start"])
    t_end = float(sents[-1]["end"])
    span = max(1.0, t_end - t_start)
    best_i = max(1, min(len(sents) - 1, int(len(sents) * target_ratio)))
    best_score = -1e9
    for i in range(1, len(sents) - 1):
        prev_s, cur_s = sents[i - 1], sents[i]
        left_dur = float(prev_s["end"]) - t_start
        right_dur = t_end - float(cur_s["start"])
        if left_dur < min_sec or right_dur < min_sec or left_dur > max_sec or right_dur > max_sec:
            continue
        gap = float(cur_s["start"]) - float(prev_s["end"])
        prev_en = prev_s["en"].strip()
        cur_en = cur_s["en"].strip()
        score = min(gap, 10.0) * 4.0 - abs((left_dur / span) - target_ratio) * 18.0
        if prev_en.endswith("?"):
            score -= 8.0
        if len(prev_en.split()) <= 3:
            score -= 3.0
        if re.match(r"^(Now|Next|All right|Alright|Okay|So now|Before|Here|Today|The next|Number|Rule|Another|Let's|Welcome|Hey|Hi)\b", cur_en):
            score += 6.0
        if re.match(r"^(And|But|Because|Or|Also|Which|That's|It's|He|She|They|We're)\b", cur_en):
            score -= 4.0
        if score > best_score:
            best_score = score
            best_i = i
    return best_i


def split_into_parts(sents):
    """自动拆成 2 段（每段 <= 9:15），超过 18:30 的拆成 3 段（每段 6–7 分钟）"""
    span = float(sents[-1]["end"]) - float(sents[0]["start"])
    if span > 1100:
        # 拆成 3 段：先在 ~1/3 处找切点，再在后 2/3 中点找切点
        i1 = find_best_split_index(sents, target_ratio=0.33, min_sec=260.0, max_sec=1100.0)
        rest = sents[i1:]
        i2_rel = find_best_split_index(rest, target_ratio=0.50, min_sec=240.0, max_sec=540.0)
        i2 = i1 + i2_rel
        return [
            ("part1", sents[:i1]),
            ("part2", sents[i1:i2]),
            ("part3", sents[i2:]),
        ]
    i = find_best_split_index(sents, target_ratio=0.50, min_sec=170.0, max_sec=555.0)
    return [
        ("part1", sents[:i]),
        ("part2", sents[i:]),
    ]


def main():
    ffmpeg_bin = find_ffmpeg()
    TRIMMED_DIR.mkdir(parents=True, exist_ok=True)
    txt = LOCAL_JS.read_text(encoding="utf-8")
    episodes = json.loads(re.search(r"LOCAL_EPISODES = (\[.*\]);", txt, re.S).group(1))
    over10 = sorted([e for e in episodes if e.get("durationSec", 0) > 600], key=lambda x: x["durationSec"], reverse=True)

    manifest = json.loads(MANIFEST_JSON.read_text(encoding="utf-8"))
    replaces = set(manifest.get("replacesTitles") or [])
    entries = list(manifest.get("entries") or [])

    print(f"[info] 第二批待拆分 >10 分钟剧集: {len(over10)} 集")
    for ep in over10:
        src_title = ep["title"]
        src_vid = ROOT / unquote(ep["mediaUrl"][2:])
        src_aud = ROOT / unquote(ep["audioUrl"][2:])
        orig_dur = probe_afinfo_dur(src_aud)
        replaces.add(src_title)
        entries = [e for e in entries if e.get("sourceTitle") != src_title]

        # 清理标题里的长竖线后缀以便命名更清爽，绝不加“精编版”
        base_title = re.sub(r"\s*[｜|]\s*$", "", src_title).strip()
        parts = split_into_parts(ep["sentences"])

        for p_idx, (part_key, p_sents) in enumerate(parts, start=1):
            new_title = f"{base_title} (Part {p_idx})"
            safe_stem = sanitize_filename(new_title)
            out_vid = TRIMMED_DIR / f"{safe_stem}.trimmed.mp4"
            out_aud = TRIMMED_DIR / f"{safe_stem}.trimmed.m4a"
            out_jpg = TRIMMED_DIR / f"{safe_stem}.jpg"
            out_sub = TRIMMED_DIR / f"{safe_stem}.polished.json"

            ws = round(max(0.0, float(p_sents[0]["start"]) - PAD_SEC), 3)
            we = round(min(orig_dur, float(p_sents[-1]["end"]) + PAD_SEC), 3)
            windows = [(ws, we)]

            print(f"[export] {ep['number']} {part_key} -> {new_title} ({we - ws:.1f}s, {len(p_sents)}句)")
            build_filter_and_export(ffmpeg_bin, src_vid, src_aud, windows, out_vid, out_aud, out_jpg)
            actual_dur = probe_afinfo_dur(out_aud)
            remapped = remap_sentences(p_sents, windows)
            out_sub.write_text(json.dumps(remapped, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"  [ok] afinfo={actual_dur:.2f}s | {len(remapped)}句 | mp4={out_vid.stat().st_size/1024/1024:.1f}MB")

            entries.append({
                "sourceNumber": ep["number"],
                "sourceTitle": src_title,
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

    manifest["replacesTitles"] = sorted(replaces)
    manifest["entries"] = entries
    MANIFEST_JSON.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n[done] 第二批全部导出完成！清单现含 {len(entries)} 个短课条目（全库均 <= 10 分钟）")


if __name__ == "__main__":
    main()
