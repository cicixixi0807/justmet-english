#!/usr/bin/env python3
"""
Non-destructive trimmed export for EP 23 (`local-58-trimmed-58-part1`)
strictly following `scripts/cut_sheets/ep23_trim_draft.json`.
- Original files are NEVER modified or deleted.
- Outputs new `.clean.trimmed.mp4` and `.clean.trimmed.m4a` under `content/episodes/trimmed/`.
- Updates ONLY EP 23 in `js/local_episodes.js` (keeps id, number, date, title, speaker intact;
  empties `skipRanges`, sets 59 remapped sentences, duration, and difficulty=2).
"""
import json
import re
import subprocess
import urllib.parse
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FFMPEG = "/Applications/VideoFusion-macOS.app/Contents/Resources/ffmpeg"
DRAFT_PATH = ROOT / "scripts" / "cut_sheets" / "ep23_trim_draft.json"
CATALOG_PATH = ROOT / "js" / "local_episodes.js"


def probe_duration_afinfo(path: Path) -> float:
    out = subprocess.check_output(["afinfo", str(path)], text=True)
    m = re.search(r"estimated duration:\s*([0-9.]+)\s*sec", out)
    if not m:
        raise RuntimeError(f"Could not parse afinfo duration for {path}")
    return float(m.group(1))


def fmt_duration(sec: float) -> str:
    total = int(round(sec))
    return f"{total // 60:02d}:{total % 60:02d}"


def main():
    draft = json.loads(DRAFT_PATH.read_text(encoding="utf-8"))
    windows = draft["keptWindows"]
    assert len(windows) == 13, f"Expected 13 kept windows, got {len(windows)}"

    raw_js = CATALOG_PATH.read_text(encoding="utf-8")
    m = re.search(r"^(.*?=\s*)(\[.*\])(;\s*)$", raw_js, re.S)
    if not m:
        raise RuntimeError("Could not parse js/local_episodes.js")
    prefix, json_str, suffix = m.groups()
    episodes = json.loads(json_str)

    ep_idx = next(i for i, e in enumerate(episodes) if e["id"] == "local-58-trimmed-58-part1")
    ep = episodes[ep_idx]

    src_rel = urllib.parse.unquote(ep["mediaUrl"].lstrip("./"))
    src_mp4 = (ROOT / src_rel).resolve()
    if not src_mp4.exists():
        raise FileNotFoundError(f"Source MP4 not found: {src_mp4}")

    src_audio_rel = urllib.parse.unquote(ep["audioUrl"].lstrip("./"))
    src_m4a = (ROOT / src_audio_rel).resolve()
    if not src_m4a.exists():
        raise FileNotFoundError(f"Source M4A not found: {src_m4a}")

    out_dir = src_mp4.parent
    stem = src_mp4.name.replace(".trimmed.mp4", "")
    out_mp4 = out_dir / f"{stem}.clean.trimmed.mp4"
    out_m4a = out_dir / f"{stem}.clean.trimmed.m4a"

    # Build FFmpeg filter_complex for exact 13-window concat (video from input 0, audio from input 1)
    filter_parts = []
    concat_inputs = []
    for idx, w in enumerate(windows):
        s = w["startSec"]
        e = w["endSec"]
        filter_parts.append(f"[0:v]trim=start={s:.3f}:end={e:.3f},setpts=PTS-STARTPTS[v{idx}]")
        filter_parts.append(f"[1:a]atrim=start={s:.3f}:end={e:.3f},asetpts=PTS-STARTPTS[a{idx}]")
        concat_inputs.append(f"[v{idx}][a{idx}]")
    filter_complex = ";".join(filter_parts) + f";{''.join(concat_inputs)}concat=n={len(windows)}:v=1:a=1[v][a]"

    print(f"Exporting {out_mp4.name} from {src_mp4.name} + {src_m4a.name} ({len(windows)} windows)...")
    cmd_mp4 = [
        FFMPEG, "-y", "-hide_banner", "-loglevel", "error",
        "-i", str(src_mp4),
        "-i", str(src_m4a),
        "-filter_complex", filter_complex,
        "-map", "[v]", "-map", "[a]",
        "-c:v", "h264_videotoolbox", "-allow_sw", "1", "-b:v", "2800k", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "128k", "-ar", "44100",
        "-movflags", "+faststart",
        str(out_mp4),
    ]
    subprocess.run(cmd_mp4, check=True)

    print(f"Extracting companion audio {out_m4a.name}...")
    cmd_m4a = [
        FFMPEG, "-y", "-hide_banner", "-loglevel", "error",
        "-i", str(out_mp4),
        "-vn", "-c:a", "copy",
        str(out_m4a),
    ]
    subprocess.run(cmd_m4a, check=True)

    actual_dur = probe_duration_afinfo(out_m4a)
    print(f"Probed clean companion audio duration: {actual_dur:.2f}s ({fmt_duration(actual_dur)})")

    # Remap the 59 kept sentences (#3 .. #61) into new timeline
    orig_sents = ep["sentences"]
    new_sents = []
    cum_offset = 0.0
    for w in windows:
        w_start = w["startSec"]
        w_end = w["endSec"]
        f_id = w["firstSentenceId"]
        l_id = w["lastSentenceId"]
        for s in orig_sents:
            if f_id <= s["id"] <= l_id:
                ns = dict(s)
                ns["id"] = len(new_sents) + 1
                ns["start"] = round(cum_offset + max(0.0, s["start"] - w_start), 2)
                ns["end"] = round(cum_offset + min(w_end - w_start, s["end"] - w_start), 2)
                if ns["end"] > actual_dur:
                    ns["end"] = round(actual_dur, 2)
                new_sents.append(ns)
        cum_offset += (w_end - w_start)

    assert len(new_sents) == 59, f"Expected 59 sentences, got {len(new_sents)}"
    assert new_sents[0]["en"] == "I'm with Blurry Salman and this will be our first time.", new_sents[0]["en"]
    assert new_sents[-1]["en"] == "It's okay.", new_sents[-1]["en"]

    # Check consecutive gaps & overlaps
    for i in range(1, len(new_sents)):
        if new_sents[i]["start"] < new_sents[i - 1]["end"]:
            new_sents[i]["start"] = new_sents[i - 1]["end"]
        gap = new_sents[i]["start"] - new_sents[i - 1]["end"]
        if gap > 0.5:
            print(f"WARNING: gap {gap:.2f}s between #{i} and #{i+1}")

    rel_mp4_url = "./content/episodes/trimmed/" + urllib.parse.quote(out_mp4.name)
    rel_m4a_url = "./content/episodes/trimmed/" + urllib.parse.quote(out_m4a.name)

    ep["mediaUrl"] = rel_mp4_url
    ep["audioUrl"] = rel_m4a_url
    ep["durationSec"] = int(round(actual_dur))
    ep["durationLabel"] = fmt_duration(actual_dur)
    ep["difficulty"] = 2
    ep["skipRanges"] = []
    ep["sentences"] = new_sents

    episodes[ep_idx] = ep
    CATALOG_PATH.write_text(prefix + json.dumps(episodes, ensure_ascii=False, indent=2) + suffix, encoding="utf-8")

    # Also update draft status
    draft["status"] = "EXPORTED_NON_DESTRUCTIVE"
    draft["actualDurationSec"] = round(actual_dur, 2)
    draft["actualDurationLabel"] = fmt_duration(actual_dur)
    draft["exportedMediaUrl"] = rel_mp4_url
    draft["exportedAudioUrl"] = rel_m4a_url
    DRAFT_PATH.write_text(json.dumps(draft, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print("SUCCESS:")
    print(f"  EP: {ep['number']} | id={ep['id']} | speaker={ep['speaker']} | difficulty={ep['difficulty']}★")
    print(f"  Duration: {ep['durationLabel']} ({actual_dur:.2f}s) | skipRanges={len(ep['skipRanges'])}")
    print(f"  Sentences: {len(new_sents)}")
    print(f"  First (#1): [{new_sents[0]['start']} - {new_sents[0]['end']}] {new_sents[0]['en']}")
    print(f"  Last  (#59): [{new_sents[-1]['start']} - {new_sents[-1]['end']}] {new_sents[-1]['en']}")


if __name__ == "__main__":
    main()
