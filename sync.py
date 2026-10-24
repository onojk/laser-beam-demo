"""Sync: the section map and the music-driven uniforms, at 30 fps video frames.

Adapted from ~/lpwdemo/sync.py. Big onsets are picked the same way (loudness jump over the
previous 0.2 s, the top BONE_PCT of each section), but here they also have to sit on a beat,
and they flash bone-white rather than inverting: "occasional", so never closer than
BONE_GAP seconds apart (well under the 3 per second photosensitivity cap). Quiet sections
(the intro, the breakdown) and everything after the music ends get no bone flashes.

Strong onsets (KICK_MIN and up) lift the glow, at most one per KICK_GAP (under 3 per second),
except in the breakdown. Tunnel speed and theremin-plasma speed are integrated (travel,
htravel) so they follow the music without ever jumping. The outro's collapse, tape stop and
final snap are timed here too.
"""
import json, os
import numpy as np

FPS = 30
BONE_PCT = 12                    # percent of each section's on-beat onsets that flash bone
BONE_GAP = 1.5                   # s between bone flashes, at least
BONE_ON_BEAT = 0.12              # s; an onset this close to a tracked beat counts as on it
NO_BONE = {"intro", "breakdown"}
WOBBLE_FULL = 40.0               # cents of tape wobble that count as full warp
KICK_MIN = 0.55                  # onset strength (0..1 among onsets) that flashes the frame
KICK_GAP = 0.34                  # s between kick flashes, at least: under 3 per second
TRAVEL = (0.35, 2.2)             # tunnel speed = a + b * rms (smoothed 0.25 s), depth units / s
NO_SCROLLER = {"breakdown", "outro"}
MAX_ONS = 64                     # onset times passed to a shader per section
HIGHTIME = (0.3, 1.7)            # theremin plasma speed = a + b * high, so it never jumps
QUIET = {"breakdown"}            # stripped down: no kick lift either, let the whisper breathe
COLLAPSE = 19.6                  # s from the outro's start until everything is one laser line
SNAP = 0.1                       # s: the line shrinks to a dot before the music's end, then black
HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, "cache")

class Sync:
    def __init__(self, features=os.path.join(CACHE, "features.json"),
                 sections=os.path.join(CACHE, "sections.json")):
        f = json.load(open(features))
        self.ffps = f["fps"]
        self.duration = f["duration"]
        self.tempo = f["tempo"]
        self.beat_t = np.array(f["beats"])
        for k in ("rms", "low", "mid", "high", "onset_strength", "centroid_slow", "wobble_cents"):
            setattr(self, k, np.array(f[k], "f4"))
        self.onset_t = np.nonzero(np.array(f["onset"]))[0] / self.ffps
        self.sections = json.load(open(sections))["sections"]
        self.n_frames = int(round(self.duration * FPS))
        self.outro = self.sections[-1]
        self.music_end = self.outro.get("music_end", self.duration)

        # bone flashes: big, on-beat onsets
        k = max(1, int(0.2 * self.ffps))
        idx = (self.onset_t * self.ffps).round().astype(int)
        jump = np.array([self.rms[i] - self.rms[max(0, i - k):i + 1].min() for i in idx])
        near = np.abs(self.onset_t[:, None] - self.beat_t[None, :]).min(axis=1) <= BONE_ON_BEAT
        big = np.zeros(len(idx), bool)
        for s in self.sections:
            m = (self.onset_t >= s["start"]) & (self.onset_t < min(s["end"], self.music_end)) & near
            if m.sum() >= 2 and s["name"] not in NO_BONE:
                big |= m & (jump >= np.percentile(jump[m], 100 - BONE_PCT))
        self.bone_t, last = [], -1e9
        for t in self.onset_t[big]:
            if t - last >= BONE_GAP:
                self.bone_t.append(t); last = t
        self.bone_t = np.array(self.bone_t)

        # kick flashes: strong onsets anywhere the music plays, spaced under 3 per second
        st = self.onset_strength[idx]
        self.kick_t, self.kick_s, last = [], [], -1e9
        for t, v in zip(self.onset_t, st):
            if v >= KICK_MIN and t - last >= KICK_GAP and t < self.music_end:
                self.kick_t.append(t); self.kick_s.append(float(v)); last = t
        self.kick_t, self.kick_s = np.array(self.kick_t), np.array(self.kick_s)

        # travel: integral of the tunnel speed, so speed follows rms and position never jumps
        n = int(0.25 * self.ffps)
        sm = np.convolve(np.pad(self.rms, (n // 2, n - n // 2 - 1), mode="edge"), np.ones(n) / n, "valid")
        self.travel = np.r_[0, np.cumsum(TRAVEL[0] + TRAVEL[1] * sm)[:-1]] / self.ffps
        sm = np.convolve(np.pad(self.high, (n // 2, n - n // 2 - 1), mode="edge"), np.ones(n) / n, "valid")
        self.htravel = np.r_[0, np.cumsum(HIGHTIME[0] + HIGHTIME[1] * sm)[:-1]] / self.ffps
        self.tape_from = self.outro.get("tape_stop_from", self.music_end)

    def at(self, arr, t):
        """arr (at the features' frame rate) at time t, linearly interpolated."""
        x = min(len(arr) - 1.0, max(0.0, t * self.ffps))
        i = int(x); j = min(len(arr) - 1, i + 1)
        return float(arr[i] + (arr[j] - arr[i]) * (x - i))

    def since(self, times, t):
        i = np.searchsorted(times, t, side="right") - 1
        return 1e3 if i < 0 else float(t - times[i])

    def section(self, t):
        for s in self.sections:
            if s["start"] <= t < s["end"]:
                return s
        return self.sections[-1]

    def beat(self, t):
        """(beats elapsed as a float, seconds since the last beat)."""
        b = self.beat_t
        i = int(np.searchsorted(b, t, side="right")) - 1
        if i < 0:
            return t / (b[0] if b[0] > 0 else 1) - 1.0, 1e3
        nxt = b[i + 1] if i + 1 < len(b) else b[i] + 60 / self.tempo
        return i + (t - b[i]) / (nxt - b[i]), float(t - b[i])

    def section_onsets(self, s):
        """This section's onset times relative to its start, and their strengths (at most
        MAX_ONS of each)."""
        m = (self.onset_t >= s["start"]) & (self.onset_t < s["end"])
        t = self.onset_t[m][:MAX_ONS]
        st = np.array([self.at(self.onset_strength, x) for x in t], "f4")
        return (t - s["start"]).astype("f4"), st

    def outro_timing(self, t):
        """collapse 0..1 (eased in), tape-stop progress 0..1 and its phase (the integral of a
        speed falling as (1 - x)^2, in seconds of tape), and the snap 0..1 before the end."""
        c = min(1.0, max(0.0, (t - self.outro["start"]) / COLLAPSE))
        D = self.music_end - self.tape_from
        x = min(1.0, max(0.0, (t - self.tape_from) / D))
        phase = D * (x - x * x + x ** 3 / 3)
        snap = min(1.0, max(0.0, (t - (self.music_end - SNAP)) / SNAP))
        return {"collapse": c * c * (3 - 2 * c), "tape": x, "tape_phase": phase, "snap": snap}

    def uniforms(self, t):
        s = self.section(t)
        ons, ons_s = self.section_onsets(s)
        ki = np.searchsorted(self.kick_t, t, side="right") - 1
        beat, since_beat = self.beat(t)
        so = self.since(self.onset_t, t)
        i = np.searchsorted(self.onset_t, t, side="right") - 1
        strength = self.at(self.onset_strength, self.onset_t[i]) if i >= 0 else 0.0
        return {"t": t, "ts": t - s["start"], "sdur": s["end"] - s["start"],
                "local": (t - s["start"]) / (s["end"] - s["start"]),
                "rms": self.at(self.rms, t), "low": self.at(self.low, t),
                "mid": self.at(self.mid, t), "high": self.at(self.high, t),
                "phrase": self.at(self.centroid_slow, t),
                "flash": strength * float(np.exp(-so / 0.18)),
                "bone": float(np.exp(-self.since(self.bone_t, t) / 0.10)),
                "wob": float(np.clip(self.at(self.wobble_cents, t) / WOBBLE_FULL, -1, 1)),
                "beat": beat, "since_beat": since_beat,
                "kick": 0.0 if ki < 0 or s["name"] in QUIET
                        else self.kick_s[ki] * float(np.exp(-(t - self.kick_t[ki]) / 0.12)),
                "travel": self.at(self.travel, t), "htravel": self.at(self.htravel, t),
                "ons": ons, "ons_s": ons_s, "n_ons": len(ons),
                "stripped": 1.0 if s["name"] in QUIET else 0.0,
                "since_bone": self.since(self.bone_t, t),
                "bone_n": int(np.searchsorted(self.bone_t, t, side="right")),
                "finale": 1.0 if s["name"] == "final_chorus" else 0.0,
                "scroller": 0.0 if s["name"] in NO_SCROLLER else 1.0,
                **self.outro_timing(t)}

if __name__ == "__main__":
    s = Sync()
    print(f"{s.duration:.3f} s, {s.n_frames} frames @ {FPS} fps, {len(s.onset_t)} onsets, "
          f"{len(s.beat_t)} beats, {len(s.bone_t)} bone flashes")
    for x in s.sections:
        n = int(((s.bone_t >= x["start"]) & (s.bone_t < x["end"])).sum())
        print(f"  {x['name']:13s} bone flashes {n}")
    g = np.diff(s.bone_t)
    print(f"bone min gap {g.min():.2f} s ({1 / g.min():.2f}/s max)")
    g = np.diff(s.kick_t)
    print(f"kick flashes {len(s.kick_t)} of {len(s.onset_t)} onsets; min gap {g.min():.2f} s "
          f"({1 / g.min():.2f}/s max)")
    v1 = next(x for x in s.sections if x["name"] == "verse1")
    a, b = s.at(s.travel, v1["start"]), s.at(s.travel, v1["end"])
    print(f"verse1 travel {b - a:.1f} depth units over {v1['end'] - v1['start']:.1f} s "
          f"({(b - a) / (v1['end'] - v1['start']):.2f}/s mean)")
