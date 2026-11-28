#!/usr/bin/env python3
"""
3 个试水源（EP 16 / EP 15 / EP 11）→ 9 条 1–3 分钟独立小场景短课非破坏性导出脚本（export_micro_pilots.py）
- 原片一律不动，仅从现有 trimmed 副本按确认的精确句边界切出 9 个新副本至 content/episodes/trimmed/。
- 不扩展到 EP 12 或其他任何来源。
- 同步在 trimmed_manifest.json 中将 EP 06（Why Adding More Is Slowing Your Business Down）加入 delistedTitles（只下架、原片保留不删）。
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
DRAFT_JSON = ROOT / "scripts" / "cut_sheets" / "micro_lessons_3pilots_draft.json"
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

    # 仅替换这 3 个试水源对应的旧条目（EP 16 / EP 15 / EP 11），绝不动 EP 12 或其他任何源！
    pilot_old_titles = {
        by_num["EP 16"]["title"],
        by_num["EP 15"]["title"],
        by_num["EP 11"]["title"],
    }
    pilot_src_meta = {}
    for e in manifest["entries"]:
        if e["title"] in pilot_old_titles:
            pilot_src_meta[e["title"]] = {
                "sourceTitle": e["sourceTitle"],
                "date": e.get("date", "2026/11/26"),
            }

    # 更新第 7 条与第 9 条用户确认标题
    TITLE_UPDATES = {
        "小镇伴手礼店淘宝：风铃、明信片与焦糖爆米花": "小镇伴手礼店：风铃、明信片与焦糖爆米花",
        "甜品柜台点单：问招牌、点曲奇与无现金刷卡": "甜品柜台点单：问招牌、点焦糖布蕾与无现金刷卡",
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

        final_title = TITLE_UPDATES.get(item["newTitle"], item["newTitle"])
        item["newTitle"] = final_title
        safe_stem = sanitize_filename(final_title)
        out_vid = TRIMMED_DIR / f"{safe_stem}.micro.mp4"
        out_aud = TRIMMED_DIR / f"{safe_stem}.micro.m4a"
        out_jpg = TRIMMED_DIR / f"{safe_stem}.jpg"
        out_sub = TRIMMED_DIR / f"{safe_stem}.polished.json"

        print(f"[export {idx}/9] {ep_num} #{id0}–#{id1} ({we - ws:.1f}s) -> {final_title}")
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
            "part": f"micro{idx}",
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

    # 替换旧的 3 个试水条目，保留其他所有条目（包括 EP 12）不动
    kept_entries = [e for e in manifest["entries"] if e["title"] not in pilot_old_titles]
    manifest["entries"] = kept_entries + new_entries
    # 确认下架 EP 06（只下架目录，硬盘原片完整保留）
    delisted = set(manifest.get("delistedTitles") or [])
    delisted.add("Why Adding More Is Slowing Your Business Down")
    manifest["delistedTitles"] = sorted(delisted)
    MANIFEST_JSON.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    # 同步更新 draft 状态为 APPROVED_AND_EXPORTED
    draft["status"] = "APPROVED_AND_EXPORTED"
    DRAFT_JSON.write_text(json.dumps(draft, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n[done] 9 条试水短课已非破坏性导出至 {TRIMMED_DIR}，EP 06 已下架（原片保留）。")


if __name__ == "__main__":
    main()
