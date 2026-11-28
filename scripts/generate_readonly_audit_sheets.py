#!/usr/bin/env python3
"""
Generate READ-ONLY audit & cut sheets (NO media exported, NO subtitles modified):
1. scripts/cut_sheets/skip_ranges_first30s_draft.json
   - All 63 episodes with skipRanges (~1474s total)
   - All 34 segments starting within the first 30 seconds (with prev/next sentence context)
2. scripts/cut_sheets/ep74_and_long_sentences_draft.json
   - EP 74 exact split plan (#2, #3, #31, #36, #41) + confirmed skipRange [13.40, 20.92] + channel outro flag
   - All 105 remaining catalog long sentences (dur >= 15s or words >= 40) split into complete-thought sub-sentences
"""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CATALOG_PATH = ROOT / "js" / "local_episodes.js"
OUT_SKIP = ROOT / "scripts" / "cut_sheets" / "skip_ranges_first30s_draft.json"
OUT_LONG = ROOT / "scripts" / "cut_sheets" / "ep74_and_long_sentences_draft.json"

PRIORITY_ARIANNITA = {"EP 80", "EP 76", "EP 36", "EP 74"}


def word_count(text: str) -> int:
    return len(re.findall(r"[A-Za-z0-9']+", text))


def clean_cap(s: str) -> str:
    s = s.strip()
    if not s:
        return s
    # Strip leading dangling comma/semicolon
    s = re.sub(r"^[,;:\s]+", "", s)
    if s and s[0].islower():
        s = s[0].upper() + s[1:]
    if s and s[-1] not in ".?!":
        s = s.rstrip(",;:") + "."
    return s


def split_into_thought_chunks(text: str, total_dur: float) -> list[str]:
    """
    Split a long English subtitle into complete-thought chunks (~<=10s / <=25 words each).
    Priority:
      1) Existing sentence terminators (. ? ! ;)
      2) Natural clause boundaries (, but / , so / , and then / , and / , because / , which / , when)
    Never splits inside a short phrase (< 7 words on either side).
    """
    text = text.strip()
    # Step 1: split on hard sentence boundaries (. ? ! ;)
    raw_parts = re.split(r"(?<=[.?!;])\s+", text)
    parts = [p.strip() for p in raw_parts if p.strip()]

    # Merge very tiny fragments (<5 words) with neighbor
    merged = []
    for p in parts:
        if merged and word_count(p) < 5:
            merged[-1] = merged[-1] + " " + p
        else:
            merged.append(p)
    parts = merged

    # Step 2: iteratively split any part that is still too long (>26 words or estimated >10.5s)
    total_w = max(1, word_count(text))
    conj_patterns = [
        r",\s+(?=(?:but|so|and then|and I|and we|and you|and they|and it|and that|and this|and there|because|which|when|while|however|though)\b)",
        r"\s+(?=(?:but then|and then|so then|because I|because we|because you|because it|but I|but we|but you|but it|so I|so we|so you)\b)",
        r",\s+(?=(?:and|or|then|now|also)\b)",
    ]

    def split_once(seg: str):
        wc = word_count(seg)
        if wc < 16:
            return None
        mid_target = wc / 2.0
        best = None
        best_dist = 1e9
        for pat in conj_patterns:
            for m in re.finditer(pat, seg, flags=re.I):
                left = seg[: m.start()].strip()
                right = seg[m.end() :].strip()
                lw, rw = word_count(left), word_count(right)
                if lw >= 7 and rw >= 7:
                    dist = abs(lw - mid_target)
                    if dist < best_dist:
                        best_dist = dist
                        best = (left, right)
            if best:
                return best
        # Fallback: comma near middle if both sides >= 8 words
        for m in re.finditer(r",\s+", seg):
            left = seg[: m.start()].strip()
            right = seg[m.end() :].strip()
            lw, rw = word_count(left), word_count(right)
            if lw >= 8 and rw >= 8:
                dist = abs(lw - mid_target)
                if dist < best_dist:
                    best_dist = dist
                    best = (left, right)
        return best

    queue = list(parts)
    final_parts = []
    while queue:
        seg = queue.pop(0)
        est_dur = total_dur * (word_count(seg) / total_w)
        if (word_count(seg) >= 26 or est_dur >= 10.5) and word_count(seg) >= 16:
            sp = split_once(seg)
            if sp:
                queue.insert(0, sp[1])
                queue.insert(0, sp[0])
                continue
        final_parts.append(clean_cap(seg))

    return final_parts


def allocate_timestamps(chunks: list[str], start: float, end: float, gap: float = 0.04) -> list[dict]:
    weights = [max(1, word_count(c)) for c in chunks]
    total_w = sum(weights)
    usable = max(0.2, (end - start) - gap * (len(chunks) - 1))
    cur = start
    out = []
    for idx, (c, w) in enumerate(zip(chunks, weights)):
        dur = usable * (w / total_w)
        s_t = round(cur, 2)
        e_t = round(end, 2) if idx == len(chunks) - 1 else round(cur + dur, 2)
        out.append({
            "part": idx + 1,
            "start": s_t,
            "end": e_t,
            "durationSec": round(e_t - s_t, 2),
            "words": word_count(c),
            "en": c,
        })
        cur = e_t + gap
    return out


def main():
    raw_js = CATALOG_PATH.read_text(encoding="utf-8")
    episodes = json.loads(re.search(r"=\s*(\[.*\]);?\s*$", raw_js, re.S).group(1))

    # ===== 1. skipRanges First-30s Read-Only Cut Sheet =====
    all_skip_eps = []
    first30_segments = []
    total_skip_sec = 0.0

    for ep in episodes:
        skips = ep.get("skipRanges") or []
        if not skips:
            continue
        ep_skip_sec = round(sum(max(0.0, r[1] - r[0]) for r in skips), 2)
        total_skip_sec += ep_skip_sec
        all_skip_eps.append({
            "number": ep["number"],
            "id": ep["id"],
            "speaker": ep["speaker"],
            "title": ep["title"],
            "skipCount": len(skips),
            "totalSkipSec": ep_skip_sec,
            "skipRanges": skips,
        })

        sents = ep["sentences"]
        for r_start, r_end in skips:
            if r_start >= 30.0:
                continue
            dur = round(r_end - r_start, 2)
            prev_s = None
            next_s = None
            for s in sents:
                if s["end"] <= r_start + 0.15:
                    prev_s = s
                elif next_s is None and s["start"] >= r_end - 0.15:
                    next_s = s
            first30_segments.append({
                "number": ep["number"],
                "id": ep["id"],
                "speaker": ep["speaker"],
                "title": ep["title"],
                "startSec": round(r_start, 2),
                "endSec": round(r_end, 2),
                "durationSec": dur,
                "ge2s": dur >= 2.0,
                "priorityCheck": (
                    "CONFIRMED_READY"
                    if (ep["id"] == "local-49-trimmed-49-part2" and abs(r_start - 13.4) < 0.1)
                    else ("ARIANNITA_PRIORITY" if ep["number"] in PRIORITY_ARIANNITA else "STANDARD")
                ),
                "prevSentence": f"#{prev_s['id']} [{prev_s['start']:.2f}-{prev_s['end']:.2f}] {prev_s['en']}" if prev_s else "片头 (0.00)",
                "nextSentence": f"#{next_s['id']} [{next_s['start']:.2f}-{next_s['end']:.2f}] {next_s['en']}" if next_s else "片尾",
            })

    first30_segments.sort(key=lambda x: (-x["durationSec"], x["number"]))

    skip_payload = {
        "status": "READONLY_DRAFT_AWAITING_APPROVAL",
        "sourceMediaModified": False,
        "summary": {
            "episodesWithSkipRanges": len(all_skip_eps),
            "totalSkipSec": round(total_skip_sec, 2),
            "first30sSegmentCount": len(first30_segments),
            "first30sGe2sCount": sum(1 for x in first30_segments if x["ge2s"]),
            "ariannitaPrioritySegments": [x for x in first30_segments if x["number"] in PRIORITY_ARIANNITA],
        },
        "first30sSegments": first30_segments,
        "all63EpisodesSkipSummary": all_skip_eps,
    }
    OUT_SKIP.write_text(json.dumps(skip_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    # ===== 2. EP 74 + 105 Long Sentences Read-Only Split Sheet =====
    ep74 = next(e for e in episodes if e["id"] == "local-49-trimmed-49-part2")
    s_by_id = {s["id"]: s for s in ep74["sentences"]}

    ep74_splits = [
        {
            "sentenceId": 2,
            "original": {"start": s_by_id[2]["start"], "end": s_by_id[2]["end"], "durationSec": round(s_by_id[2]["end"] - s_by_id[2]["start"], 2), "words": word_count(s_by_id[2]["en"]), "en": s_by_id[2]["en"]},
            "proposedParts": allocate_timestamps([
                "I am so full of all the food that I ate inside the store.",
                "But now I'm going to show you the third way to order food, and that is through the drive-thru.",
                "I actually don't know what I'm going to order because I'm full, so maybe I'll order something for my dad.",
            ], s_by_id[2]["start"], s_by_id[2]["end"]),
            "note": "按用户指定 3 句拆分；正式写回时将结合音频停顿做精确边界校准。",
        },
        {
            "sentenceId": 3,
            "original": {"start": s_by_id[3]["start"], "end": s_by_id[3]["end"], "durationSec": round(s_by_id[3]["end"] - s_by_id[3]["start"], 2), "words": word_count(s_by_id[3]["en"]), "en": s_by_id[3]["en"]},
            "proposedParts": allocate_timestamps([
                "As you can see, you order food through the drive-thru like this truck is doing right now.",
                "And it's called drive-thru because you need a car and you drive through it in a lane.",
            ], s_by_id[3]["start"], s_by_id[3]["end"]),
            "note": "按用户指定 2 句拆分。",
        },
        {
            "sentenceId": 31,
            "original": {"start": s_by_id[31]["start"], "end": s_by_id[31]["end"], "durationSec": round(s_by_id[31]["end"] - s_by_id[31]["start"], 2), "words": word_count(s_by_id[31]["en"]), "en": s_by_id[31]["en"]},
            "proposedParts": allocate_timestamps([
                "As you can see, I just paid through the first window for my ice cream.",
                "But I didn't get my ice cream just yet because I have to go to the second window and pick it up.",
            ], s_by_id[31]["start"], s_by_id[31]["end"]),
            "note": "拆为 2 个完整意群。",
        },
        {
            "sentenceId": 36,
            "original": {"start": s_by_id[36]["start"], "end": s_by_id[36]["end"], "durationSec": round(s_by_id[36]["end"] - s_by_id[36]["start"], 2), "words": word_count(s_by_id[36]["en"]), "en": s_by_id[36]["en"]},
            "proposedParts": allocate_timestamps([
                "I'm gonna go ahead and lick this ice cream, because if not, it will melt down onto the cone.",
                "Okay guys, that's it for today's YouTube video at McDonald's!",
            ], s_by_id[36]["start"], s_by_id[36]["end"]),
            "channelOutroFlag": True,
            "note": "后半句 'Okay guys, that's it for today's YouTube video at McDonald's!' 起为频道收尾，待确认是否一并裁掉 #36 后半至 #41。",
        },
        {
            "sentenceId": 41,
            "original": {"start": s_by_id[41]["start"], "end": s_by_id[41]["end"], "durationSec": round(s_by_id[41]["end"] - s_by_id[41]["start"], 2), "words": word_count(s_by_id[41]["en"]), "en": s_by_id[41]["en"]},
            "proposedParts": allocate_timestamps([
                "Let me know down below, because I would love to hear your review about this video and make more content for the next video.",
                "And don't forget to like and subscribe, bye!",
            ], s_by_id[41]["start"], s_by_id[41]["end"]),
            "channelOutroFlag": True,
            "note": "含结尾 'like and subscribe, bye!' 频道收尾，待确认是否从目录课中裁去 #36 后半–#41。",
        },
    ]

    other_long = []
    other_eps = set()
    for ep in episodes:
        for s in ep["sentences"]:
            dur = round(s["end"] - s["start"], 2)
            wc = word_count(s["en"])
            if dur >= 15.0 or wc >= 40:
                if ep["id"] == "local-49-trimmed-49-part2" and s["id"] == 2:
                    continue  # Already in ep74_splits
                chunks = split_into_thought_chunks(s["en"], dur)
                other_long.append({
                    "number": ep["number"],
                    "id": ep["id"],
                    "speaker": ep["speaker"],
                    "sentenceId": s["id"],
                    "originalStart": s["start"],
                    "originalEnd": s["end"],
                    "durationSec": dur,
                    "words": wc,
                    "originalEn": s["en"],
                    "proposedParts": allocate_timestamps(chunks, s["start"], s["end"]),
                })
                other_eps.add(ep["id"])

    long_payload = {
        "status": "READONLY_DRAFT_AWAITING_APPROVAL",
        "subtitlesModified": False,
        "summary": {
            "rule": "durationSec >= 15.0 OR words >= 40 (plus EP 74 #3/#31/#36/#41)",
            "totalCatalogLongSentences": len(other_long) + 1,
            "ep74LongIncluded": 1,
            "otherLongSentencesCount": len(other_long),
            "otherEpisodesCount": len(other_eps),
        },
        "ep74ReadonlyPlan": {
            "number": ep74["number"],
            "id": ep74["id"],
            "title": ep74["title"],
            "speaker": ep74["speaker"],
            "confirmedSkipRange": [13.4, 20.92],
            "otherSkipRanges": [[149.77, 152.89], [154.99, 157.39]],
            "channelOutroCandidate": {
                "range": "#36(后半) – #41 (约 204.2s – 233.65s)",
                "sentences": [
                    f"#{sid} [{s_by_id[sid]['start']:.2f}-{s_by_id[sid]['end']:.2f}] {s_by_id[sid]['en']}"
                    for sid in range(36, 42)
                ],
                "awaitingConfirmation": "是否从目录课裁去频道收尾（that's it for today's YouTube video 至 like and subscribe, bye!）",
            },
            "sentenceSplits": ep74_splits,
        },
        "other105LongSentences": other_long,
    }
    OUT_LONG.write_text(json.dumps(long_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print("WROTE:", OUT_SKIP.name, "| first30s:", len(first30_segments), "| ge2s:", sum(1 for x in first30_segments if x["ge2s"]))
    print("WROTE:", OUT_LONG.name, "| otherLong:", len(other_long), "| otherEps:", len(other_eps))
    print("\n--- Ariannita Priority (<30s) ---")
    for x in first30_segments:
        if x["number"] in PRIORITY_ARIANNITA:
            print(f"  {x['number']} ({x['id']}) [{x['startSec']}-{x['endSec']}] {x['durationSec']}s | {x['priorityCheck']}")
            print(f"    prev: {x['prevSentence']}")
            print(f"    next: {x['nextSentence']}")


if __name__ == "__main__":
    main()
