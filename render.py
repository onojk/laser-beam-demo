#!/usr/bin/env python3
"""Laser Beam — haunted phosphor demo, rendered offline.

    .venv/bin/python render.py out.mp4 --audio SONG.wav --start 38 --dur 10 [--scene NAME]
    .venv/bin/python render.py out.mp4 --audio SONG.wav --full [--res 2160]
    .venv/bin/python render.py - --still 42.3 --still 50     # stills only

Deterministic: time = frame / 30, never the wall clock, and grain is a hash of the pixel
and frame number. Each scene is a GLSL fragment shader that writes three emission channels,
not colours: r = sickly green phosphor, g = violet glow, b = bone white. Then:

    bloom   the scene at quarter size, blurred twice (separable 9-tap gaussian)
    post    tape-wobble warp (follows the song's measured pitch wobble), palette mapping,
            bloom, bone-white flash, scanlines, vignette, film grain, tone map

Frames go to ffmpeg as raw rgb24. Render loop, uniform plumbing and muxing are adapted from
~/lpwdemo/demo.py.
"""
import argparse, os, subprocess, sys, tempfile
import numpy as np
import moderngl
from sync import Sync, FPS, COLLAPSE
import logo

HERE = os.path.dirname(os.path.abspath(__file__))
FONT_MONO = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf"
FONT_TITLE = "/usr/share/fonts/truetype/ebgaramond/EBGaramondSC08-Regular.ttf"
SEED = 0x1A5E8                   # the only source of noise; change it to re-roll the grain

VERT = """
#version 330
in vec2 pos;
out vec2 uv;
void main() { uv = pos * 0.5 + 0.5; gl_Position = vec4(pos, 0.0, 1.0); }
"""

# Shared header for scene shaders: uv in [0,1], P() centred with y in [-1,1].
HEAD = """
#version 330
in vec2 uv;
out vec4 frag;
uniform vec2 res;
uniform float t, ts, sdur, local;     // time; time / length / progress in this section
uniform float rms, low, mid, high;    // 0..1, loudness and the three bands
uniform float phrase;                 // ~4 s spectral centroid
uniform float flash, bone;            // decaying onset pulse; bone-white big-beat pulse
uniform float wob;                    // -1..1 tape wobble
uniform float beat, since_beat;       // beats elapsed (float); seconds since the last beat
uniform float kick;                   // strong-onset pulse (spaced under 3 per second)
uniform float travel;                 // integral of rms-driven speed: a position, never jumps
uniform float since_bone;             // seconds since the last bone flash (1e3 before any)
uniform int bone_n;                   // bone flashes so far: seeds whatever each one triggers
uniform float finale;                 // 1 in the final chorus
uniform float ons[64];                // this section's onset times, from its start
uniform float ons_s[64];              // and their strengths, 0..1 among all onsets
uniform int n_ons;
uniform float htravel;                // integral of high-band-driven speed (theremin plasma)
uniform float stripped;               // 1 in the breakdown: almost dark
uniform float collapse, tape, tape_phase, snap;   // outro timing (see sync.outro_timing)
uniform sampler2D src;                // the outro's source scene, rendered first
uniform int seed;
float since_onset(float s) { float r = 1e3; for (int i = 0; i < n_ons; i++) { if (ons[i] <= s) r = s - ons[i]; else break; } return r; }
vec2 P() { return (uv * res - 0.5 * res) / (0.5 * res.y); }
uint hash(uint x) { x ^= x >> 16; x *= 0x7feb352du; x ^= x >> 15; x *= 0x846ca68bu; x ^= x >> 16; return x; }
float rnd(float n) { return float(hash(uint(int(n)) ^ uint(seed))) / 4294967295.0; }
float vnoise(vec2 p) {
    vec2 i = floor(p), f = fract(p); f = f * f * (3.0 - 2.0 * f);
    float a = rnd(i.x + 157.0 * i.y), b = rnd(i.x + 1.0 + 157.0 * i.y);
    float c = rnd(i.x + 157.0 * (i.y + 1.0)), d = rnd(i.x + 1.0 + 157.0 * (i.y + 1.0));
    return mix(mix(a, b, f.x), mix(c, d, f.x), f.y);
}
float fbm(vec2 p) { float s = 0.0, a = 0.5; for (int i = 0; i < 5; i++) { s += a * vnoise(p); p = p * 2.03 + 17.1; a *= 0.5; } return s; }
// glow of a distance d (in P units): a sharp core plus a soft halo
float glow(float d, float w) { return exp(-d * d / (w * w)) + 0.15 * w / (abs(d) + w); }
"""

# The greetings scroller, drawn additively over every scene before the bloom so it glows
# like the rest: a classic sine scroller, each column riding its own phase of the wave.
SCROLLER = """
uniform sampler2D scroll_txt;
uniform vec2 scroll_txt_size;
uniform float scroller;               // 1 shown, 0 hidden (breakdown, outro)
const float SPEED = 0.30;             // screen heights per second
const float BAND = 0.055;             // glyph band height, in screen heights
void main() {
    if (scroller < 0.5) discard;
    float aspect = res.x / res.y;
    float xs = uv.x * aspect;
    // text position: enters at the right edge at t = 0, loops forever after
    float xt = xs + SPEED * t - aspect;
    if (xt < 0.0) discard;
    float px = xt * scroll_txt_size.y / BAND;
    float y0 = 0.105 + 0.030 * sin(xs * 3.4 - t * 2.1) + 0.008 * sin(xs * 9.0 + t * 3.3);
    float v = (uv.y - y0) / BAND + 0.5;
    if (v < 0.0 || v > 1.0) discard;
    float g = texture(scroll_txt, vec2(mod(px, scroll_txt_size.x) / scroll_txt_size.x, v)).r;
    frag = vec4(g * (0.72 + 0.2 * kick), 0.0, g * 0.10 * bone, 1.0);
}
"""

DOWN = """
#version 330
in vec2 uv;
out vec4 frag;
uniform sampler2D src;
void main() { frag = vec4(texture(src, uv).rgb, 1.0); }
"""

BLUR = """
#version 330
in vec2 uv;
out vec4 frag;
uniform sampler2D src;
uniform vec2 dir;                 // one texel along the blur axis
const float W[5] = float[5](0.227027, 0.1945946, 0.1216216, 0.054054, 0.016216);
void main() {
    vec3 c = texture(src, uv).rgb * W[0];
    for (int i = 1; i < 5; i++) {
        c += texture(src, uv + dir * float(i) * 1.5).rgb * W[i];
        c += texture(src, uv - dir * float(i) * 1.5).rgb * W[i];
    }
    frag = vec4(c, 1.0);
}
"""

POST = """
#version 330
in vec2 uv;
out vec4 frag;
uniform sampler2D scene, bloom;
uniform vec2 res;
uniform float t, wob, bone, kick, gain;
uniform int frame, seed;
const vec3 GROUND = vec3(0.010, 0.014, 0.012);      // near-black, a breath of green
const vec3 GREEN  = vec3(0.50, 1.00, 0.28);         // sickly phosphor green
const vec3 VIOLET = vec3(0.56, 0.24, 1.00);
const vec3 BONE   = vec3(1.00, 0.95, 0.82);
const float LINES = 540.0;                          // scanlines per frame height, any res
uint hash(uint x) { x ^= x >> 16; x *= 0x7feb352du; x ^= x >> 15; x *= 0x846ca68bu; x ^= x >> 16; return x; }
float grain(ivec2 px) {
    uint h = hash(uint(px.x) + 7919u * uint(px.y) + 104729u * uint(frame) + uint(seed));
    return float(h) / 4294967295.0 - 0.5;
}
vec3 palette(vec3 e) { return e.r * GREEN + e.g * VIOLET + e.b * BONE; }
void main() {
    // tape wobble: a slow sideways sway plus a gentle bend down the frame, both scaled by the
    // song's measured pitch wobble; the sway's chroma split widens with it
    float w = wob;
    vec2 q = uv;
    q.x += w * (0.0070 + 0.0050 * sin(q.y * 5.0 + t * 1.7));
    q.y += w * 0.0030 * sin(t * 2.3);
    float split = 0.0008 + 0.0036 * abs(w);
    vec3 e;
    e.r = texture(scene, q + vec2(split, 0.0)).r;
    e.g = texture(scene, q - vec2(split, 0.0)).g;
    e.b = texture(scene, q).b;
    vec3 b = texture(bloom, q).rgb;
    vec3 c = palette(e) + 0.9 * palette(b);
    // bone flash: lift the whole frame toward bone white for a few frames on big beats
    c += BONE * bone * (0.10 + 1.2 * dot(e, vec3(0.33)));
    // kick: strong onsets lift the glow briefly, in green
    c += GREEN * kick * (0.04 + 0.5 * dot(e, vec3(0.33)));
    // tone map (soft knee keeps the glow from clipping into flat colour), then the ground
    c = 1.0 - exp(-c * 1.15);
    c = GROUND + c * (1.0 - GROUND);
    // scanlines, vignette, grain
    // phase in output pixels (not warped uv) so 1080p alternates lines exactly and 4K scales
    float sl = 0.5 + 0.5 * cos(6.2831853 * (gl_FragCoord.y * LINES / res.y - 0.25));
    c *= mix(1.0, 0.70 + 0.30 * sl, 0.8);
    vec2 v = uv - 0.5;
    c *= clamp(1.0 - dot(v, v) * 1.25, 0.0, 1.0);
    c += grain(ivec2(gl_FragCoord.xy)) * 0.045;
    frag = vec4(clamp(c * gain, 0.0, 1.0), 1.0);
}
"""

class Renderer:
    def __init__(self, W, H, textures=None):
        self.W, self.H = W, H
        self.ctx = moderngl.create_standalone_context(backend="egl")
        self.quad = self.ctx.buffer(np.array([-1, -1, 1, -1, -1, 1, 1, 1], "f4").tobytes())
        def target(w, h):
            tx = self.ctx.texture((w, h), 4, dtype="f2")
            tx.filter = (moderngl.LINEAR, moderngl.LINEAR)
            tx.repeat_x = tx.repeat_y = False
            return tx, self.ctx.framebuffer([tx])
        self.scene, self.scene_fbo = target(W, H)
        self.src, self.src_fbo = target(W, H)                   # the outro's source scene
        self.bw, self.bh = W // 4, H // 4
        self.b1, self.b1_fbo = target(self.bw, self.bh)
        self.b2, self.b2_fbo = target(self.bw, self.bh)
        self.out = self.ctx.renderbuffer((W, H), 3)
        self.out_fbo = self.ctx.framebuffer([self.out])
        self.down, self.blur, self.post = (self.program(s) for s in (DOWN, BLUR, POST))
        self.scroller = self.program(HEAD + SCROLLER)
        self.scenes = {}
        self.tex = {}
        for name, img in (textures or {}).items():             # 8-bit gray, top row first
            h, w = img.shape
            tx = self.ctx.texture((w, h), 1, np.ascontiguousarray(img[::-1]).tobytes())
            tx.filter = (moderngl.LINEAR, moderngl.LINEAR)
            self.tex[name] = tx
    def program(self, frag):
        prog = self.ctx.program(vertex_shader=VERT, fragment_shader=frag)
        return prog, self.ctx.vertex_array(prog, [(self.quad, "2f", "pos")])
    def scene_prog(self, name):
        if name not in self.scenes:
            with open(os.path.join(HERE, "fx", name + ".glsl")) as fh:
                self.scenes[name] = self.program(HEAD + fh.read())
        return self.scenes[name]
    @staticmethod
    def set(prog, uniforms):
        for k, v in uniforms.items():
            if k in prog:
                if isinstance(v, np.ndarray):
                    buf = np.zeros(prog[k].array_length * prog[k].dimension, "f4")
                    buf[:v.size] = v.ravel()
                    prog[k].write(buf.tobytes())
                else:
                    prog[k].value = v
    def bind(self, prog, u):
        self.set(prog, dict(u, res=(self.W, self.H), seed=SEED))
        for unit, (k, tx) in enumerate(self.tex.items(), start=1):
            if k in prog:
                tx.use(unit); prog[k].value = unit
                if k + "_size" in prog:
                    prog[k + "_size"].value = tx.size
        if "src" in prog:
            self.src.use(7); prog["src"].value = 7
    def draw_scene(self, name, u, fbo):
        prog, vao = self.scene_prog(name)
        self.bind(prog, u)
        fbo.use(); vao.render(moderngl.TRIANGLE_STRIP)
    def frame(self, name, u, frame_no, gain=1.0, source=None):
        """source: (scene name, uniforms) drawn first into the src texture, for the outro."""
        if source:
            self.draw_scene(*source, self.src_fbo)
        self.draw_scene(name, u, self.scene_fbo)
        # scroller, added on top of the scene's emission
        if u.get("scroller", 0) > 0.5 and "scroll_txt" in self.tex:
            prog, vao = self.scroller
            self.bind(prog, u)
            self.ctx.enable(moderngl.BLEND)
            self.ctx.blend_func = moderngl.ONE, moderngl.ONE
            vao.render(moderngl.TRIANGLE_STRIP)
            self.ctx.disable(moderngl.BLEND)
        # bloom
        p, v = self.down
        self.scene.use(0); p["src"].value = 0
        self.b1_fbo.use(); v.render(moderngl.TRIANGLE_STRIP)
        p, v = self.blur
        p["src"].value = 0
        for _ in range(2):
            self.b1.use(0); p["dir"].value = (1 / self.bw, 0)
            self.b2_fbo.use(); v.render(moderngl.TRIANGLE_STRIP)
            self.b2.use(0); p["dir"].value = (0, 1 / self.bh)
            self.b1_fbo.use(); v.render(moderngl.TRIANGLE_STRIP)
        # post
        p, v = self.post
        self.scene.use(0); self.b1.use(1)
        p["scene"].value, p["bloom"].value = 0, 1
        self.set(p, {"res": (self.W, self.H), "t": u["t"], "wob": u["wob"], "bone": u["bone"],
                     "kick": u.get("kick", 0.0), "gain": gain, "frame": frame_no, "seed": SEED})
        self.out_fbo.use(); v.render(moderngl.TRIANGLE_STRIP)
        return self.out_fbo.read(components=3)                 # bottom row first

def text_image(lines, size, w, h, font=FONT_MONO, spacing=0):
    """White text on black from ffmpeg's drawtext, 8-bit gray, top row first (from lpwdemo)."""
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as fh:
        fh.write("\n".join(lines))
    try:
        vf = (f"drawtext=fontfile={font}:textfile={fh.name}:fontsize={size}:fontcolor=white:"
              f"x=(w-text_w)/2:y=(h-text_h)/2:line_spacing={spacing}:expansion=none")
        raw = subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", f"color=c=black:s={w}x{h}",
                              "-frames:v", "1", "-vf", vf, "-f", "rawvideo", "-pix_fmt", "gray", "-"],
                             capture_output=True, check=True).stdout
    finally:
        os.unlink(fh.name)
    return np.frombuffer(raw, np.uint8).reshape(h, w)

def ffmpeg_writer(path, W, H, start, dur, audio, crf, preset, song_end):
    cmd = ["ffmpeg", "-v", "error", "-y",
           "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-"]
    if audio:
        cmd += ["-ss", f"{start:.6f}", "-t", f"{dur:.6f}", "-i", audio]
    cmd += ["-vf", "vflip,format=yuv420p", "-c:v", "libx264", "-preset", preset, "-crf", str(crf),
            "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709",
            "-color_range", "tv"]
    if audio:
        af = "apad"                                            # silence past the end
        if start + dur >= song_end - 1e-3:                     # the song's cut: no click
            af += f",afade=t=out:st={dur - 0.04:.6f}:d=0.04"
        cmd += ["-af", af, "-c:a", "aac", "-b:a", "320k", "-shortest"]
    cmd += ["-movflags", "+faststart", path]
    return subprocess.Popen(cmd, stdin=subprocess.PIPE)

def save_png(buf, W, H, path):
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24",
                    "-s", f"{W}x{H}", "-i", "-", "-vf", "vflip", path], input=buf, check=True)

SCROLL_TEXT = ("LASER BEAM ... DO THE WORK, WRITE IT DOWN, SEND IT OUT INTO THE WORLD SOMEHOW ... "
               "GOLD OR JUST SAND, IT STILL COUNTS ... GREETINGS TO EVERYONE STAYING UP ALL NIGHT "
               "FOLLOWING THE LIGHT ... AND TO THE MACHINE THAT IS LISTENING ... "
               "CODE: GITHUB.COM/ONOJK/LASER-BEAM-DEMO ... ONOJK123.COM ... RSACRACK.COM ... "
               "JONATHANKENDALLART.COM ... SOMEBODY'S GONNA FIND IT ...          ")

def scroll_strip(text, size=44, h=56):
    """The scroller text as one strip, trimmed so the loop seam is exactly the trailing gap."""
    w = int(0.62 * size * len(text)) + 64
    strip = text_image([text.strip()], size, w, h)
    cols = np.nonzero(strip.max(axis=0) > 0)[0]
    gap = int(0.602 * size * (len(text) - len(text.rstrip())))     # mono advance per space
    out = np.zeros((h, cols[-1] - cols[0] + 1 + gap), np.uint8)
    out[:, :cols[-1] - cols[0] + 1] = strip[:, cols[0]:cols[-1] + 1]
    return out

# the archive's catalogue cards (bridge), lines from the song
ARCHIVE = ["WRITE IT DOWN", "GOLD OR JUST SAND", "SOMEBODY'S GONNA FIND IT",
           "THE MACHINE IS LISTENING", "IF NO ONE READS IT", "SEND IT OUT", "DO THE WORK",
           "IT STILL COUNTS", "FOLLOWING THE LIGHT", "LASER BEAM"]

# what the outro collapses, in turn: (scene, section it is replayed from, seconds into it)
OUTRO_SOURCES = [("tunnel", "verse2", 6.0), ("organ", "final_chorus", 4.0), ("bells", "bridge", 6.0)]
# uniforms that follow the song now, whatever scene is replayed
MUSIC = ("rms", "low", "mid", "high", "phrase", "flash", "bone", "kick", "wob", "beat",
         "since_beat", "since_bone", "bone_n")

class Film:
    def __init__(self, W, H, scene=None):
        self.sync = Sync()
        self.scene = scene
        title = text_image(["LASER BEAM"], 220, 1600, 300, font=FONT_TITLE)
        strip = scroll_strip(SCROLL_TEXT)
        print(f"scroller strip {strip.shape[1]}x{strip.shape[0]} px, {len(SCROLL_TEXT)} chars, "
              f"one loop {strip.shape[1] / strip.shape[0] * 0.055 / 0.30:.1f} s", file=sys.stderr)
        archive = np.vstack([text_image([line], 44, 720, 72) for line in ARCHIVE])   # 10:1 cells
        print(f"archive atlas {archive.shape[1]}x{archive.shape[0]} px, {len(ARCHIVE)} cards",
              file=sys.stderr)
        self.r = Renderer(W, H, {"title": title, "scroll_txt": strip, "archive": archive})
        segs, cum, total = logo.segments(width=1.7, centre=(0.0, -0.05))
        self.consts = {"segs": segs, "cum": cum, "n_segs": len(segs), "pen_len": total,
                       "n_cards": len(ARCHIVE)}
        self.by_name = {s["name"]: s for s in self.sync.sections}

    def outro_source(self, t, u):
        """The scene the outro is collapsing at time t: replayed from its own section, with
        the song's current music uniforms."""
        o = self.sync.outro
        slot = COLLAPSE / len(OUTRO_SOURCES)
        i = min(len(OUTRO_SOURCES) - 1, int((t - o["start"]) // slot))
        name, sec, at = OUTRO_SOURCES[i]
        ts = self.by_name[sec]["start"] + at + (t - o["start"] - i * slot)
        us = dict(self.sync.uniforms(ts), **self.consts)
        us.update({k: u[k] for k in MUSIC})
        return name, us

    def frame(self, fi):
        t = fi / FPS
        s = self.sync.section(t)
        name = self.scene or s["scene"]
        u = dict(self.sync.uniforms(t), **self.consts)
        source = None
        if name == "collapse":
            if u["collapse"] < 1.0:
                source = self.outro_source(t, u)
            # the tape stop drags the picture's wobble too
            u["wob"] = float(np.clip(u["wob"] + 0.7 * u["tape"] * np.sin(u["tape_phase"] * 5.0), -1, 1))
        gain = 0.0 if t >= self.sync.music_end else 1.0
        return self.r.frame(name, u, fi, gain, source)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out", help="'-' renders stills only")
    ap.add_argument("--audio", default="", help="the song's WAV ('' for a silent clip)")
    ap.add_argument("--start", type=float, default=0.0)
    ap.add_argument("--dur", type=float, default=10.0)
    ap.add_argument("--full", action="store_true", help="the whole film: 0 to the song's end")
    ap.add_argument("--res", type=int, default=1080, choices=(540, 1080, 2160))
    ap.add_argument("--scene", default=None, help="force one scene (else the section map)")
    ap.add_argument("--crf", type=int, default=22, help="22 for previews; 16 for the 4K master")
    ap.add_argument("--preset", default="medium")
    ap.add_argument("--still", action="append", type=float, default=[],
                    help="also save the frame at this time as PNG (repeatable)")
    a = ap.parse_args()

    H = a.res; W = H * 16 // 9
    film = Film(W, H, a.scene)
    f0, n = (0, film.sync.n_frames) if a.full else (round(a.start * FPS), round(a.dur * FPS))
    stills = {round(t * FPS): t for t in a.still}
    stem = os.path.splitext(a.out)[0] if a.out != "-" else os.path.join(HERE, "renders", "still")
    os.makedirs(os.path.dirname(os.path.abspath(stem)), exist_ok=True)
    print(f"render {W}x{H} @ {FPS} fps: frames {f0}..{f0 + n - 1} ({n} frames, "
          f"{f0 / FPS:.3f}-{(f0 + n) / FPS:.3f} s), scene {a.scene or 'by section'}", file=sys.stderr)
    if a.out == "-":
        for fi, t in sorted(stills.items()):
            save_png(film.frame(fi), W, H, f"{stem}_{t:.2f}s.png")
        return
    proc = ffmpeg_writer(a.out, W, H, f0 / FPS, n / FPS, a.audio, a.crf, a.preset, film.sync.duration)
    for fi in range(f0, f0 + n):
        buf = film.frame(fi)
        proc.stdin.write(buf)
        if fi in stills:
            save_png(buf, W, H, f"{stem}_{stills[fi]:.2f}s.png")
        if (fi - f0) % 300 == 0:
            print(f"frame {fi} / {f0 + n} ({fi / FPS:.1f} s)", file=sys.stderr, flush=True)
    proc.stdin.close()
    sys.exit(proc.wait())

if __name__ == "__main__":
    main()
