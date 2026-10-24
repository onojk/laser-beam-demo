#!/usr/bin/env python3
"""sections.py — cache/features.json -> cache/sections.json, and print the section map.

    .venv/bin/python sections.py

Boundaries are read off the features (novelty peaks, rms steps, band shifts; each one's
reason is kept in "why"), then snapped to the nearest tracked beat within half a second,
so every hard cut lands on a beat. Confirmed against the lyric sheet on 2026-10-23.
"""
import json, os
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
FEATURES = os.path.join(HERE, "cache", "features.json")
OUT = os.path.join(HERE, "cache", "sections.json")

# (name, scene, start s, why)
RAW = [
    ("intro",       "musicbox", 0.0,    "quiet open, -28 dBFS, centroid low; rms rises at 0:14"),
    ("verse1",      "tunnel",   14.0,   "rms steps up 0.07 -> 0.17 by 0:17; onsets pick up"),
    ("chorus1",     "organ",    42.27,  "novelty 0.47 and the biggest step so far: -26 -> -20 dBFS, low band 0.12 -> 0.36"),
    ("verse2",      "tunnel",   65.17,  "novelty 0.23; onset density rises to 2.6-2.9/s at an even level"),
    ("chorus2",     "organ",    98.47,  "re-entry after the 1:34.5 dip (rms 0.21 -> 0.42, novelty 0.26; 1:33.2 peak 0.40 is the dip's start)"),
    ("break",       "theremin", 131.73, "instrumental break (lyric sheet); re-entry after the 2:09.5 dip, high band climbs"),
    ("bridge",      "bells",    163.17, "'if no one reads it / the machine is listening' (lyric sheet); novelty 0.24, low band drops"),
    ("breakdown",   "bells",    185.53, "near-whisper (lyric sheet); strongest dropout, -16.6 -> -28 dBFS, novelty 0.85"),
    ("final_chorus", "organ",   208.13, "biggest chorus (lyric sheet); highest high band and centroid in the song"),
    ("outro",       "collapse", 232.37, "outro (lyric sheet); novelty 0.48, high band collapses 0.62 -> 0.10"),
]
# outro landmarks: the last beat (4:28.13, the lyric sheet's 4:28.1) ends the music; the tape
# stop runs the two bars (8 beats) before it; black from there through the tail
MUSIC_END_RAW = 268.1

def build():
    f = json.load(open(FEATURES))
    beats = np.array(f["beats"])
    secs = []
    for name, scene, t, why in RAW:
        snapped = t
        if t > 0:
            b = beats[np.argmin(np.abs(beats - t))]
            if abs(b - t) <= 0.5:
                snapped = float(b)
        secs.append({"name": name, "scene": scene, "start": round(snapped, 3),
                     "raw": t, "why": why})
    for i, s in enumerate(secs):
        s["end"] = secs[i + 1]["start"] if i + 1 < len(secs) else round(f["duration"], 3)
    k = int(np.argmin(np.abs(beats - MUSIC_END_RAW)))
    secs[-1]["music_end"] = round(float(beats[k]), 3)
    secs[-1]["tape_stop_from"] = round(float(beats[k - 8]), 3)
    json.dump({"source": "cache/features.json", "provisional": False,
               "confirmed": "lyric sheet, 2026-10-23", "sections": secs},
              open(OUT, "w"), indent=1)
    return f, secs

def mmss(t):
    return f"{int(t // 60)}:{t % 60:05.2f}"

if __name__ == "__main__":
    f, secs = build()
    fps = f["fps"]
    rms, onset, high, low = (np.array(f[k]) for k in ("rms", "onset", "high", "low"))
    beats = np.array(f["beats"])
    bar = 4 * 60 / f["tempo"]
    print(f"tempo {f['tempo']:.2f} bpm, bar {bar:.3f} s, duration {f['duration']:.3f} s, "
          f"{len(secs)} sections\n")
    print(f"{'#':>2} {'name':13s} {'scene':9s} {'start':>8s} {'end':>8s} {'len':>6s} {'bars':>5s} "
          f"{'snap':>6s} {'beats':>5s} {'ons':>4s} {'rms':>5s} {'low':>5s} {'high':>5s}")
    for i, s in enumerate(secs):
        a, b = int(s["start"] * fps), int(s["end"] * fps)
        nb = int(((beats >= s["start"]) & (beats < s["end"])).sum())
        print(f"{i + 1:2d} {s['name']:13s} {s['scene']:9s} {mmss(s['start']):>8s} {mmss(s['end']):>8s} "
              f"{s['end'] - s['start']:5.1f}s {(s['end'] - s['start']) / bar:5.1f} "
              f"{s['start'] - s['raw']:+6.2f} {nb:5d} {int(onset[a:b].sum()):4d} "
              f"{rms[a:b].mean():5.2f} {low[a:b].mean():5.2f} {high[a:b].mean():5.2f}")
    o = secs[-1]
    print(f"\noutro: tape stop {mmss(o['tape_stop_from'])} -> {mmss(o['music_end'])} "
          f"({o['music_end'] - o['tape_stop_from']:.2f} s), black {mmss(o['music_end'])} -> "
          f"{mmss(o['end'])} ({o['end'] - o['music_end']:.2f} s)")
    print(f"wrote {OUT}")
