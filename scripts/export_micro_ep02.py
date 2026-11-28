#!/usr/bin/env python3
"""
当前 EP 02（local-10-Busking-part2）→ 4 条确认短课非破坏性导出脚本（export_micro_ep02.py）
- 原片一律不动，仅从现有 EP 02 副本切出 4 个新短课至 content/episodes/trimmed/。
- 同步修正 catalog_order.json 中 EP 49 / EP 53 讲者为 Michelle Choi。
- 不自行打乱或重编号已有剧集。
"""
import json
import pathlib
import re
import shutil
import subprocess
from urllib.parse import unquote

ROOT = pathlib.Path(__file__).resolve().parent.parent
TRIMMED_DIR = ROOT / "content" / "episodes" / "trimmed"
LOCAL_JS = ROOT / "js" / "local_episodes.js"
DRAFT_JSON = ROOT / "scripts" / "cut_sheets" / "micro_lessons_ep02_draft.json"
MANIFEST_JSON = ROOT / "scripts" / "cut_sheets" / "trimmed_manifest.json"
ORDER_JSON = ROOT / "scripts" / "cut_sheets" / "catalog_order.json"

PAD_SEC = 0.20


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


def export_one(ffmpeg_bin, src_vid, src_aud, ws, we, out_vid, out_aud, out_jpg):
    subprocess.run([
        ffmpeg_bin, "-y", "-hide_banner", "-loglevel", "error",
        "-ss", f"{ws:.3f}", "-to", f"{we:.3f}", "-i", str(src_vid),
        "-filter_complex", "[0:v]scale=-2:min(720\\,ih),setpts=PTS-STARTPTS[v0]",
        "-map", "[v0]", "-an", "-c:v", "h264_videotoolbox", "-allow_sw", "1",
        "-b:v", "1500k", "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(out_vid),
    ], check=True)
    subprocess.run([
        ffmpeg_bin, "-y", "-hide_banner", "-loglevel", "error",
        "-ss", f"{ws:.3f}", "-to", f"{we:.3f}", "-i", str(src_aud),
        "-filter_complex", "[0:a]asetpts=PTS-STARTPTS[a0]",
        "-map", "[a0]", "-c:a", "aac", "-b:a", "128k", str(out_aud),
    ], check=True)
    subprocess.run([
        ffmpeg_bin, "-y", "-hide_banner", "-loglevel", "error",
        "-ss", "2.0", "-i", str(out_vid), "-vframes", "1", "-q:v", "3", str(out_jpg),
    ], check=True)


def main():
    ffmpeg_bin = find_ffmpeg()

    # 1. Update catalog_order.json speaker for EP 49 & EP 53 -> Michelle Choi
    order_list = json.loads(ORDER_JSON.read_text(encoding="utf-8"))
    for item in order_list:
        if item["newNumber"] in ("EP 49", "EP 53"):
            item["speaker"] = "Michelle Choi"
    ORDER_JSON.write_text(json.dumps(order_list, ensure_ascii=False, indent=2), encoding="utf-8")

    txt = LOCAL_JS.read_text(encoding="utf-8")
    episodes = json.loads(re.search(r"LOCAL_EPISODES = (\[.*\]);", txt, re.S).group(1))
    ep02 = next(e for e in episodes if e["id"] == "local-10-Busking-part2")

    draft = json.loads(DRAFT_JSON.read_text(encoding="utf-8"))
    manifest = json.loads(MANIFEST_JSON.read_text(encoding="utf-8"))

    old_entry = next(e for e in manifest["entries"] if e["title"] == ep02["title"])
    src_vid = ROOT / unquote(ep02["mediaUrl"][2:])
    src_aud = ROOT / unquote(ep02["audioUrl"][2:])
    src_dur = probe_afinfo_dur(src_aud)

    new_entries = []
    for idx, item in enumerate(draft["microLessons"], start=1):
        id0, id1 = int(item["firstSentenceId"]), int(item["lastSentenceId"])
        sub = [s for s in ep02["sentences"] if id0 <= s["id"] <= id1]
        ws = round(max(0.0, float(sub[0]["start"]) - PAD_SEC), 3)
        we = round(min(src_dur, float(sub[-1]["end"]) + PAD_SEC), 3)

        final_title = item["newTitle"]
        safe_stem = sanitize_filename(final_title)
        out_vid = TRIMMED_DIR / f"{safe_stem}.micro.mp4"
        out_aud = TRIMMED_DIR / f"{safe_stem}.micro.m4a"
        out_jpg = TRIMMED_DIR / f"{safe_stem}.jpg"
        out_sub = TRIMMED_DIR / f"{safe_stem}.polished.json"

        print(f"[export {idx}/4] EP 02 #{id0}–#{id1} ({we - ws:.1f}s) -> {final_title}")
        export_one(ffmpeg_bin, src_vid, src_aud, ws, we, out_vid, out_aud, out_jpg)
        actual_dur = probe_afinfo_dur(out_aud)

        remapped = []
        for s in sub:
            ns = dict(s)
            ns["start"] = round(max(0.0, float(s["start"]) - ws), 2)
            ns["end"] = round(min(actual_dur, float(s["end"]) - ws), 2)
            remapped.append(ns)
        for i in range(len(remapped) - 1):
            nxt_s = float(remapped[i + 1]["start"])
            if remapped[i]["end"] > nxt_s - 0.04:
                remapped[i]["end"] = round(min(nxt_s, max(remapped[i]["start"] + 0.10, nxt_s - 0.04)), 2)
        for si, s in enumerate(remapped, start=1):
            s["id"] = si
        out_sub.write_text(json.dumps(remapped, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"  [ok] afinfo={actual_dur:.2f}s | {len(remapped)}句 | mp4={out_vid.stat().st_size/1024/1024:.1f}MB")

        new_entries.append({
            "sourceNumber": "EP 02",
            "sourceTitle": old_entry["sourceTitle"],
            "part": f"downtown_micro{idx}",
            "title": final_title,
            "speakerOverride": "Vanessa",
            "tierOverride": "A",
            "date": old_entry.get("date", "2026/11/26"),
            "videoFile": out_vid.name,
            "audioFile": out_aud.name,
            "coverFile": out_jpg.name,
            "polishedFile": out_sub.name,
            "durationSec": round(actual_dur, 2),
            "windows": [[ws, we]],
        })

    manifest["entries"] = [e for e in manifest["entries"] if e["title"] != ep02["title"]] + new_entries
    MANIFEST_JSON.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    draft["status"] = "APPROVED_AND_EXPORTED"
    DRAFT_JSON.write_text(json.dumps(draft, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n[done] EP 02 的 4 条短课已非破坏性导出至 {TRIMMED_DIR}。")


if __name__ == "__main__":
    main()
