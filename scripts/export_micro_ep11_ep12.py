#!/usr/bin/env python3
"""
当前 EP 11（Chick-fil-A）与 EP 12（麦当劳）→ 6 条确认短课非破坏性导出脚本（export_micro_ep11_ep12.py）
- 原片一律不动，仅从现有 trimmed 副本按确认的精确句边界切出 6 个新副本至 content/episodes/trimmed/。
- 不扩展到 EP 10 或其他任何源。
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
DRAFT_JSON = ROOT / "scripts" / "cut_sheets" / "micro_lessons_ep11_ep12_draft.json"
MANIFEST_JSON = ROOT / "scripts" / "cut_sheets" / "trimmed_manifest.json"

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
        "-ss", "2.5", "-i", str(out_vid), "-vframes", "1", "-q:v", "3", str(out_jpg),
    ], check=True)


def main():
    ffmpeg_bin = find_ffmpeg()
    txt = LOCAL_JS.read_text(encoding="utf-8")
    episodes = json.loads(re.search(r"LOCAL_EPISODES = (\[.*\]);", txt, re.S).group(1))
    by_num = {e["number"]: e for e in episodes}

    draft = json.loads(DRAFT_JSON.read_text(encoding="utf-8"))
    manifest = json.loads(MANIFEST_JSON.read_text(encoding="utf-8"))

    # 仅替换当前 EP 11 与 EP 12，绝不动 EP 10 或其他源
    pilot_old_titles = {
        by_num["EP 11"]["title"],
        by_num["EP 12"]["title"],
    }
    pilot_src_meta = {}
    for e in manifest["entries"]:
        if e["title"] in pilot_old_titles:
            pilot_src_meta[e["title"]] = {
                "sourceTitle": e["sourceTitle"],
                "date": e.get("date", "2026/11/26"),
            }

    new_entries = []
    for idx, item in enumerate(draft["microLessons"], start=1):
        ep_num = item["sourceEpisode"][:5]
        ep = by_num[ep_num]
        src_vid = ROOT / unquote(ep["mediaUrl"][2:])
        src_aud = ROOT / unquote(ep["audioUrl"][2:])
        src_dur = probe_afinfo_dur(src_aud)

        id0, id1 = int(item["firstSentenceId"]), int(item["lastSentenceId"])
        sub = [s for s in ep["sentences"] if id0 <= s["id"] <= id1]
        ws = round(max(0.0, float(sub[0]["start"]) - PAD_SEC), 3)
        we = round(min(src_dur, float(sub[-1]["end"]) + PAD_SEC), 3)

        final_title = item["newTitle"]
        safe_stem = sanitize_filename(final_title)
        out_vid = TRIMMED_DIR / f"{safe_stem}.micro.mp4"
        out_aud = TRIMMED_DIR / f"{safe_stem}.micro.m4a"
        out_jpg = TRIMMED_DIR / f"{safe_stem}.jpg"
        out_sub = TRIMMED_DIR / f"{safe_stem}.polished.json"

        print(f"[export {idx}/6] {ep_num} #{id0}–#{id1} ({we - ws:.1f}s) -> {final_title}")
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

        meta = pilot_src_meta.get(ep["title"], {"sourceTitle": ep["title"], "date": ep.get("date", "2026/11/26")})
        new_entries.append({
            "sourceNumber": ep_num,
            "sourceTitle": meta["sourceTitle"],
            "part": f"fastfood_micro{idx}",
            "title": final_title,
            "speakerOverride": "Speak English With Vanessa",
            "tierOverride": "A",
            "date": meta["date"],
            "videoFile": out_vid.name,
            "audioFile": out_aud.name,
            "coverFile": out_jpg.name,
            "polishedFile": out_sub.name,
            "durationSec": round(actual_dur, 2),
            "windows": [[ws, we]],
        })

    kept_entries = [e for e in manifest["entries"] if e["title"] not in pilot_old_titles]
    manifest["entries"] = kept_entries + new_entries
    MANIFEST_JSON.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    draft["status"] = "APPROVED_AND_EXPORTED"
    DRAFT_JSON.write_text(json.dumps(draft, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n[done] EP 11 & EP 12 的 6 条短课已非破坏性导出至 {TRIMMED_DIR}。")


if __name__ == "__main__":
    main()
