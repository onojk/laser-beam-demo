"""The "LASER BEAM" vector logo: an angular stroke font (Vectrex style) on a 4 x 6 grid,
laid out as line segments in the shaders' P() space, in drawing order, with each segment's
running path length so the intro can draw it in with a moving pen.
"""
import numpy as np

# each glyph: a list of polylines, points on a 4 wide x 6 tall grid, origin bottom left
GLYPHS = {
    "L": [[(0, 6), (0, 0), (4, 0)]],
    "A": [[(0, 0), (0, 4), (2, 6), (4, 4), (4, 0)], [(0, 3), (4, 3)]],
    "S": [[(4, 5), (3, 6), (1, 6), (0, 5), (0, 4), (1, 3), (3, 3), (4, 2), (4, 1), (3, 0), (1, 0), (0, 1)]],
    "E": [[(4, 6), (0, 6), (0, 0), (4, 0)], [(0, 3), (3, 3)]],
    "R": [[(0, 0), (0, 6), (3, 6), (4, 5), (4, 4), (3, 3), (0, 3)], [(2, 3), (4, 0)]],
    "B": [[(0, 0), (0, 6), (3, 6), (4, 5), (4, 4), (3, 3), (0, 3)], [(3, 3), (4, 2), (4, 1), (3, 0), (0, 0)]],
    "M": [[(0, 0), (0, 6), (2, 3), (4, 6), (4, 0)]],
}
ADVANCE, SPACE = 5.6, 3.0         # grid units per letter, extra for a word gap

def segments(text="LASER BEAM", width=1.55, centre=(0.0, 0.0)):
    """(segs[N, 4] as x0 y0 x1 y1, cum[N, 2] as path length at each end, total length)."""
    x, pts = 0.0, []
    for ch in text:
        if ch == " ":
            x += SPACE
            continue
        for line in GLYPHS[ch]:
            for a, b in zip(line, line[1:]):
                pts.append((x + a[0], a[1], x + b[0], b[1]))
        x += ADVANCE
    segs = np.array(pts, "f4")
    span = x - (ADVANCE - 4)
    k = width / span
    segs[:, [0, 2]] = (segs[:, [0, 2]] - span / 2) * k + centre[0]
    segs[:, [1, 3]] = (segs[:, [1, 3]] - 3) * k + centre[1]
    lens = np.hypot(segs[:, 2] - segs[:, 0], segs[:, 3] - segs[:, 1])
    cum = np.stack([np.r_[0, np.cumsum(lens)[:-1]], np.cumsum(lens)], axis=1).astype("f4")
    return segs, cum, float(cum[-1, 1])

if __name__ == "__main__":
    s, c, total = segments()
    print(f"{len(s)} segments, path length {total:.3f}, "
          f"x {s[:, [0, 2]].min():.3f}..{s[:, [0, 2]].max():.3f}, "
          f"y {s[:, [1, 3]].min():.3f}..{s[:, [1, 3]].max():.3f}")
