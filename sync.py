"""Sync: the section map and the music-driven uniforms, at 30 fps video frames.

Adapted from ~/lpwdemo/sync.py. Big onsets are picked the same way (loudness jump over the
previous 0.2 s, the top BONE_PCT of each section), but here they also have to sit on a beat,
and they flash bone-white rather than inverting: "occasional", so never closer than
BONE_GAP seconds apart (well under the 3 per second photosensitivity cap). Quiet sections
(the intro, the breakdown) and everything after the music ends get no bone flashes.
"""
import json, os
import numpy as np

FPS = 30
BONE_PCT = 12                    # percent of each section's on-beat onsets that flash bone
BONE_GAP = 1.5                   # s between bone flashes, at least
BONE_ON_BEAT = 0.12              # s; an onset this close to a tracked beat counts as on it
NO_BONE = {"intro", "breakdown"}
WOBBLE_FULL = 40.0               # cents of tape wobble that count as full warp
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

    def uniforms(self, t):
        s = self.section(t)
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
                "beat": beat, "since_beat": since_beat}

if __name__ == "__main__":
    s = Sync()
    print(f"{s.duration:.3f} s, {s.n_frames} frames @ {FPS} fps, {len(s.onset_t)} onsets, "
          f"{len(s.beat_t)} beats, {len(s.bone_t)} bone flashes")
    for x in s.sections:
        n = int(((s.bone_t >= x["start"]) & (s.bone_t < x["end"])).sum())
        print(f"  {x['name']:13s} bone flashes {n}")
    g = np.diff(s.bone_t)
    print(f"min gap {g.min():.2f} s ({1 / g.min():.2f}/s max)")
