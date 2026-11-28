#!/usr/bin/env python3
"""
Non-destructive export for:
1. EP 74 (`local-49-trimmed-49-part2`):
   - Hard-cut [13.40, 20.92], #26 + [149.77, 152.89], [154.99, 157.39], and channel outro [203.63, end]
   - Acoustic-calibrated splits for #2 (3 parts), #3 (2 parts), #31 (2 parts), and #36 first half
   - Empty skipRanges, recomputed difficulty via 5-factor infer_difficulty
2. The other 24 approved first-30s (>= 2.0s) skipRanges across 22 unique episodes:
   - Non-destructive `.introcut.trimmed.mp4` + `.introcut.trimmed.m4a`
   - Shift all sentence timestamps and remaining skipRanges accurately
   - NEVER modify original source files, NEVER reorder 83 episodes, dates, or ids.
"""
import json
import re
import subprocess
import sys
import urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import sync_episodes  # noqa: E402

FFMPEG = "/Applications/VideoFusion-macOS.app/Contents/Resources/ffmpeg"
CATALOG_PATH = ROOT / "js" / "local_episodes.js"
SKIP_DRAFT_PATH = ROOT / "scripts" / "cut_sheets" / "skip_ranges_first30s_draft.json"
REPORT_PATH = ROOT / "scripts" / "cut_sheets" / "export_ep74_and_24_introcuts_report.json"


def probe_duration_afinfo(path: Path) -> float:
    out = subprocess.check_output(["afinfo", str(path)], text=True)
    m = re.search(r"estimated duration:\s*([0-9.]+)\s*sec", out)
    if not m:
        raise RuntimeError(f"Could not parse afinfo duration for {path}")
    return float(m.group(1))


def fmt_duration(sec: float) -> str:
    total = int(round(sec))
    return f"{total // 60:02d}:{total % 60:02d}"


def run_ffmpeg_concat(src_mp4: Path, src_m4a: Path, windows: list[tuple[float, float]], out_mp4: Path, out_m4a: Path) -> float:
    filter_parts = []
    concat_inputs = []
    for idx, (s, e) in enumerate(windows):
        filter_parts.append(f"[0:v]trim=start={s:.3f}:end={e:.3f},setpts=PTS-STARTPTS[v{idx}]")
        filter_parts.append(f"[1:a]atrim=start={s:.3f}:end={e:.3f},asetpts=PTS-STARTPTS[a{idx}]")
        concat_inputs.append(f"[v{idx}][a{idx}]")
    if len(windows) == 1:
        filter_complex = ";".join(filter_parts)
        map_v, map_a = "[v0]", "[a0]"
    else:
        filter_complex = ";".join(filter_parts) + f";{''.join(concat_inputs)}concat=n={len(windows)}:v=1:a=1[v][a]"
        map_v, map_a = "[v]", "[a]"

    cmd_mp4 = [
        FFMPEG, "-y", "-hide_banner", "-loglevel", "error",
        "-i", str(src_mp4),
        "-i", str(src_m4a),
        "-filter_complex", filter_complex,
        "-map", map_v, "-map", map_a,
        "-c:v", "h264_videotoolbox", "-allow_sw", "1", "-b:v", "2600k", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "128k", "-ar", "44100",
        "-movflags", "+faststart",
        str(out_mp4),
    ]
    subprocess.run(cmd_mp4, check=True)

    cmd_m4a = [
        FFMPEG, "-y", "-hide_banner", "-loglevel", "error",
        "-i", str(out_mp4),
        "-vn", "-c:a", "copy",
        str(out_m4a),
    ]
    subprocess.run(cmd_m4a, check=True)
    return probe_duration_afinfo(out_m4a)


def map_time(t: float, cuts: list[tuple[float, float]]) -> float:
    shift = 0.0
    for c_s, c_e in cuts:
        if t >= c_e:
            shift += (c_e - c_s)
        elif t > c_s:
            shift += (t - c_s)
    return round(max(0.0, t - shift), 2)


def export_ep74(ep: dict) -> dict:
    src_mp4 = (ROOT / urllib.parse.unquote(ep["mediaUrl"].lstrip("./"))).resolve()
    src_m4a = (ROOT / urllib.parse.unquote(ep["audioUrl"].lstrip("./"))).resolve()
    out_dir = src_mp4.parent
    stem = re.sub(r"\.(clean\.)?trimmed\.mp4$", "", src_mp4.name)
    out_mp4 = out_dir / f"{stem}.clean.trimmed.mp4"
    out_m4a = out_dir / f"{stem}.clean.trimmed.m4a"

    # Hard cuts:
    # 1) [13.40, 20.92]
    # 2) #26 [147.25, 149.77] + [149.77, 152.89] -> [147.25, 152.89]
    # 3) [154.99, 157.39]
    # 4) Channel outro from 203.63 to end
    windows = [
        (0.0, 13.40),
        (20.92, 147.25),
        (152.89, 154.99),
        (157.39, 203.63),
    ]
    cuts = [
        (13.40, 20.92),
        (147.25, 152.89),
        (154.99, 157.39),
    ]

    actual_dur = run_ffmpeg_concat(src_mp4, src_m4a, windows, out_mp4, out_m4a)

    # Build acoustic-calibrated sentences (#1..#36 first half, dropping #26 and #37..#41)
    new_sents = []
    for s in ep["sentences"]:
        sid = s["id"]
        if sid == 26 or sid >= 37:
            continue
        if sid == 2:
            parts = [
                (20.92, 32.25, "I am so full of all the food that I ate inside the store.",
                 "我在店里吃了好多东西，现在撑得不行。",
                 "/aɪ æm soʊ fʊl əv ɔːl ðə fuːd ðæt aɪ eɪt ɪnˈsaɪd ðə stɔːr/",
                 [{"text": "inside the store", "key": "inside the store", "chip": "teal"}]),
                (32.50, 38.05, "But now I'm going to show you the third way to order food, and that is through the drive-thru.",
                 "但现在我要带你们看第三种点餐方式，就是免下车得来速点餐。",
                 "/bʌt naʊ aɪm ˈɡoʊɪŋ tə ʃoʊ ju ðə θɜːrd weɪ tu ˈɔːrdər fuːd ænd ðæt ɪz θruː ðə ˈdraɪv θruː/",
                 [{"text": "drive-thru", "key": "drive-thru", "chip": "indigo"}]),
                (38.25, 44.61, "I actually don't know what I'm going to order because I'm full, so maybe I'll order something for my dad.",
                 "其实我也不知道要再点什么，因为我已经很饱了，也许给爸爸点点什么吧。",
                 "/aɪ ˈæktʃuəli doʊnt noʊ wʌt aɪm ˈɡoʊɪŋ tu ˈɔːrdər bɪˈkɔːz aɪm fʊl soʊ ˈmeɪbi aɪl ˈɔːrdər ˈsʌmθɪŋ fɔːr maɪ dæd/",
                 []),
            ]
            for ps, pe, pen, pzh, pipa, phl in parts:
                new_sents.append({
                    "id": len(new_sents) + 1,
                    "start": map_time(ps, cuts),
                    "end": map_time(pe, cuts),
                    "speaker": s.get("speaker", "Speaker"),
                    "en": pen,
                    "ipa": pipa,
                    "zh": pzh,
                    "highlights": phl,
                })
        elif sid == 3:
            parts = [
                (44.65, 49.90, "As you can see, you order food through the drive-thru like this truck is doing right now.",
                 "你看，就像前面那辆皮卡现在这样，直接开车走得来速车道点餐。",
                 "/æz ju kæn siː ju ˈɔːrdər fuːd θruː ðə ˈdraɪv θruː laɪk ðɪs trʌk ɪz ˈduːɪŋ raɪt naʊ/",
                 [{"text": "As you can see", "key": "as you can see", "chip": "pink"}]),
                (50.10, 55.77, "And it's called drive-thru because you need a car and you drive through it in a lane.",
                 "之所以叫 drive-thru，是因为你得开着车，沿着车道一路开过去点单取餐。",
                 "/ænd ɪts kɔːld ˈdraɪv θruː bɪˈkɔːz ju niːd ə kɑːr ænd ju draɪv θruː ɪt ɪn ə leɪn/",
                 [{"text": "drive through", "key": "drive through", "chip": "indigo"}]),
            ]
            for ps, pe, pen, pzh, pipa, phl in parts:
                new_sents.append({
                    "id": len(new_sents) + 1,
                    "start": map_time(ps, cuts),
                    "end": map_time(pe, cuts),
                    "speaker": s.get("speaker", "Speaker"),
                    "en": pen,
                    "ipa": pipa,
                    "zh": pzh,
                    "highlights": phl,
                })
        elif sid == 31:
            parts = [
                (163.70, 169.25, "As you can see, I just paid through the first window for my ice cream.",
                 "你看，我刚才在第一个窗口付了冰淇淋的钱。",
                 "/æz ju kæn siː aɪ dʒʌst peɪd θruː ðə fɜːrst ˈwɪndoʊ fɔːr maɪ aɪs kriːm/",
                 [{"text": "first window", "key": "first window", "chip": "teal"}]),
                (169.45, 176.36, "But I didn't get my ice cream just yet because I have to go to the second window and pick it up.",
                 "不过我还没拿到冰淇淋，因为得开到第二个窗口去取餐。",
                 "/bʌt aɪ ˈdɪdənt ɡet maɪ aɪs kriːm dʒʌst jet bɪˈkɔːz aɪ hæv tə ɡoʊ tə ðə ˈsekənd ˈwɪndoʊ ænd pɪk ɪt ʌp/",
                 [{"text": "pick it up", "key": "pick it up", "chip": "pink"}]),
            ]
            for ps, pe, pen, pzh, pipa, phl in parts:
                new_sents.append({
                    "id": len(new_sents) + 1,
                    "start": map_time(ps, cuts),
                    "end": map_time(pe, cuts),
                    "speaker": s.get("speaker", "Speaker"),
                    "en": pen,
                    "ipa": pipa,
                    "zh": pzh,
                    "highlights": phl,
                })
        elif sid == 36:
            new_sents.append({
                "id": len(new_sents) + 1,
                "start": map_time(197.36, cuts),
                "end": min(round(actual_dur, 2), map_time(203.63, cuts)),
                "speaker": s.get("speaker", "Speaker"),
                "en": "I'm gonna go ahead and lick this ice cream, because if not, it will melt down onto the cone.",
                "ipa": "/aɪm ˈɡʌnə ɡoʊ əˈhed ænd lɪk ðɪs aɪs kriːm bɪˈkɔːz ɪf nɑːt ɪt wɪl melt daʊn ˈɑːntu ðə koʊn/",
                "zh": "我得赶紧舔一口这个冰淇淋，不然它就要化下来流到蛋筒上了。",
                "highlights": [{"text": "go ahead", "key": "go ahead", "chip": "indigo"}],
            })
        else:
            ns = dict(s)
            ns["id"] = len(new_sents) + 1
            ns["start"] = map_time(s["start"], cuts)
            ns["end"] = min(round(actual_dur, 2), map_time(s["end"], cuts))
            new_sents.append(ns)

    # Guard against any micro overlap
    for i in range(1, len(new_sents)):
        if new_sents[i]["start"] < new_sents[i - 1]["end"]:
            new_sents[i]["start"] = new_sents[i - 1]["end"]

    rel_mp4 = "./content/episodes/trimmed/" + urllib.parse.quote(out_mp4.name)
    rel_m4a = "./content/episodes/trimmed/" + urllib.parse.quote(out_m4a.name)
    dur_sec = int(round(actual_dur))
    new_diff = sync_episodes.infer_difficulty(
        ep["title"], new_sents, duration_sec=dur_sec,
        speaker=ep["speaker"], tags=ep.get("tags"), skip_ranges=[]
    )

    old_dur = ep["durationLabel"]
    old_diff = ep["difficulty"]
    ep["mediaUrl"] = rel_mp4
    ep["audioUrl"] = rel_m4a
    ep["durationSec"] = dur_sec
    ep["durationLabel"] = fmt_duration(actual_dur)
    ep["difficulty"] = new_diff
    ep["skipRanges"] = []
    ep["sentences"] = new_sents

    return {
        "number": ep["number"],
        "id": ep["id"],
        "speaker": ep["speaker"],
        "oldDuration": old_dur,
        "newDuration": ep["durationLabel"],
        "actualDurationSec": round(actual_dur, 2),
        "oldDifficulty": old_diff,
        "newDifficulty": new_diff,
        "sentenceCount": len(new_sents),
        "skipRangesCount": 0,
        "firstSentence": f"#1 [{new_sents[0]['start']}-{new_sents[0]['end']}] {new_sents[0]['en']}",
        "lastSentence": f"#{new_sents[-1]['id']} [{new_sents[-1]['start']}-{new_sents[-1]['end']}] {new_sents[-1]['en']}",
    }


def export_introcut_episode(ep: dict, cuts_raw: list[tuple[float, float]]) -> tuple[str, dict, dict]:
    cuts = sorted(cuts_raw, key=lambda x: x[0])
    src_mp4 = (ROOT / urllib.parse.unquote(ep["mediaUrl"].lstrip("./"))).resolve()
    src_m4a = (ROOT / urllib.parse.unquote(ep["audioUrl"].lstrip("./"))).resolve()
    src_dur = probe_duration_afinfo(src_m4a)

    # Complementary kept windows
    windows = []
    cursor = 0.0
    for c_s, c_e in cuts:
        if c_s - cursor > 0.05:
            windows.append((cursor, c_s))
        cursor = max(cursor, c_e)
    if src_dur - cursor > 0.05:
        windows.append((cursor, src_dur))

    out_dir = ROOT / "content" / "episodes" / "trimmed"
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = re.sub(r"\.(introcut\.|clean\.)?trimmed\.mp4$", "", src_mp4.name)
    stem = re.sub(r"\.mp4$", "", stem)
    out_mp4 = out_dir / f"{stem}.introcut.trimmed.mp4"
    out_m4a = out_dir / f"{stem}.introcut.trimmed.m4a"

    actual_dur = run_ffmpeg_concat(src_mp4, src_m4a, windows, out_mp4, out_m4a)

    # Remap sentences
    new_sents = []
    for s in ep["sentences"]:
        ns = dict(s)
        ns["start"] = map_time(s["start"], cuts)
        ns["end"] = min(round(actual_dur, 2), map_time(s["end"], cuts))
        if ns["end"] <= ns["start"]:
            ns["end"] = round(min(actual_dur, ns["start"] + 0.1), 2)
        new_sents.append(ns)
    for i in range(1, len(new_sents)):
        if new_sents[i]["start"] < new_sents[i - 1]["end"]:
            new_sents[i]["start"] = new_sents[i - 1]["end"]

    # Remap remaining skipRanges (excluding the cut ranges)
    new_skips = []
    for r_s, r_e in ep.get("skipRanges") or []:
        is_cut = any(abs(r_s - cs) < 0.08 and abs(r_e - ce) < 0.08 for cs, ce in cuts)
        if is_cut:
            continue
        ns_s = map_time(r_s, cuts)
        ns_e = min(round(actual_dur, 2), map_time(r_e, cuts))
        if ns_e - ns_s > 0.05:
            new_skips.append([ns_s, ns_e])

    rel_mp4 = "./content/episodes/trimmed/" + urllib.parse.quote(out_mp4.name)
    rel_m4a = "./content/episodes/trimmed/" + urllib.parse.quote(out_m4a.name)
    dur_sec = int(round(actual_dur))
    old_dur = ep["durationLabel"]
    old_skips = len(ep.get("skipRanges") or [])

    updated_fields = {
        "mediaUrl": rel_mp4,
        "audioUrl": rel_m4a,
        "durationSec": dur_sec,
        "durationLabel": fmt_duration(actual_dur),
        "skipRanges": new_skips,
        "sentences": new_sents,
    }
    report_item = {
        "number": ep["number"],
        "id": ep["id"],
        "speaker": ep["speaker"],
        "cutRanges": [[round(a, 2), round(b, 2)] for a, b in cuts],
        "cutTotalSec": round(sum(b - a for a, b in cuts), 2),
        "oldDuration": old_dur,
        "newDuration": fmt_duration(actual_dur),
        "actualDurationSec": round(actual_dur, 2),
        "oldSkipCount": old_skips,
        "remainingSkipCount": len(new_skips),
    }
    return ep["id"], updated_fields, report_item


def main():
    raw_js = CATALOG_PATH.read_text(encoding="utf-8")
    m = re.search(r"^(.*?=\s*)(\[.*\])(;\s*)$", raw_js, re.S)
    prefix, json_str, suffix = m.groups()
    episodes = json.loads(json_str)
    ep_map = {e["id"]: e for e in episodes}

    # 1. Export EP 74 first
    print("=== [1/2] Exporting EP 74 clean trimmed ===", flush=True)
    ep74_rep = export_ep74(ep_map["local-49-trimmed-49-part2"])
    print("DONE EP 74:", json.dumps(ep74_rep, ensure_ascii=False), flush=True)

    # 2. Export the 24 approved first-30s >= 2s segments across 22 unique episodes
    skip_d = json.loads(SKIP_DRAFT_PATH.read_text(encoding="utf-8"))
    ge2 = [
        x for x in skip_d["first30sSegments"]
        if x["ge2s"] and not (x["id"] == "local-49-trimmed-49-part2" and abs(x["startSec"] - 13.4) < 0.1)
    ]
    assert len(ge2) == 24, f"Expected 24 segments, got {len(ge2)}"

    by_ep = {}
    for x in ge2:
        by_ep.setdefault(x["id"], []).append((x["startSec"], x["endSec"]))

    print(f"=== [2/2] Exporting {len(ge2)} intro-cut segments across {len(by_ep)} episodes (parallel=2) ===", flush=True)
    intro_reports = []
    with ThreadPoolExecutor(max_workers=2) as pool:
        futs = {
            pool.submit(export_introcut_episode, ep_map[eid], cuts): eid
            for eid, cuts in by_ep.items()
        }
        done_cnt = 0
        for fut in as_completed(futs):
            eid, fields, rep = fut.result()
            ep_map[eid].update(fields)
            intro_reports.append(rep)
            done_cnt += 1
            print(
                f"  [{done_cnt:02d}/{len(by_ep)}] {rep['number']} ({eid}): "
                f"{rep['oldDuration']} -> {rep['newDuration']} (cut {rep['cutTotalSec']}s, skips {rep['oldSkipCount']}->{rep['remainingSkipCount']})",
                flush=True,
            )

    intro_reports.sort(key=lambda x: int(x["number"].split()[1]))

    CATALOG_PATH.write_text(prefix + json.dumps(episodes, ensure_ascii=False, indent=2) + suffix, encoding="utf-8")
    REPORT_PATH.write_text(
        json.dumps({"ep74": ep74_rep, "introCut24Segments": intro_reports}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print("ALL DONE! Updated js/local_episodes.js and wrote", REPORT_PATH.name, flush=True)


if __name__ == "__main__":
    main()
