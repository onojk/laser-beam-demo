// Intro: a music-box cylinder made of dots, then "LASER BEAM" drawn in as a vector logo.
//
// The cylinder lies along x, turned a little (YAW) so its end caps show, turning toward the
// viewer's top. Its decorative
// pins are a seeded pattern; the bright pins are the intro's real onsets, placed on the drum
// so each one reaches the comb exactly when its note sounds, and plucks its tine.
// From DRAW_AT the cylinder rises and dims while a pen draws the logo, stroke by stroke.
uniform vec4 segs[64];            // logo segments, x0 y0 x1 y1, in drawing order
uniform vec2 cum[64];             // path length at each segment's start and end
uniform int n_segs;
uniform float pen_len;

const float OMEGA = 0.9;          // drum rotation, rad / s
const float COMB = 1.2;           // drum angle where the comb touches (up from facing us)
const float YAW = 0.30;           // the drum is turned this far, so its end caps show
const float PERSP = 0.20;         // perspective strength (nearer points spread out)
const int NC = 22;                // pin columns (tines)
const int NR = 40;                // pin rows around the drum
const float DRAW_AT = 7.2;        // s: the pen starts (beat 8)
const float DRAW_DUR = 5.2;       // s: the pen finishes at 12.4, then the logo holds

// a point on the drum (x along the axis, angle a up from facing us) -> screen xy, and depth
// toward the viewer in z
vec3 proj(float x, float a, float R) {
    float z = R * cos(a);
    float xs = x * cos(YAW) + z * sin(YAW);
    float zs = -x * sin(YAW) + z * cos(YAW);
    float f = 1.0 / (1.0 - PERSP * zs);
    return vec3(vec2(xs, R * sin(a)) * f, zs);
}

// a drum dot: gaussian only (glow()'s long tail, summed over hundreds of dots, would light
// up the loop's bounding box)
float pin(float d, float w) { return exp(-d * d / (w * w)); }

float seg_dist(vec2 p, vec2 a, vec2 b) {
    vec2 pa = p - a, ba = b - a;
    return length(pa - ba * clamp(dot(pa, ba) / max(dot(ba, ba), 1e-9), 0.0, 1.0));
}

void main() {
    vec2 p = P();
    vec3 e = vec3(0.0);

    float rise = smoothstep(DRAW_AT - 0.5, DRAW_AT + 2.0, ts);
    float sc = mix(1.0, 0.55, rise);
    vec2 c = vec2(0.0, mix(0.05, 0.47, rise));
    float lit = smoothstep(0.0, 1.2, ts) * mix(1.0, 0.5, rise);
    float R = 0.42 * sc, L = 0.92 * sc;
    vec2 q = p - c;
    float rot = OMEGA * ts;
    float colw = 2.0 * L / float(NC);
    float dot_r = 0.0065 * sc;
    // nearest column, ignoring the yaw (the loops below search either side of it)
    int col0 = int(floor((q.x / cos(YAW) + L) / colw));

    // drum: decorative pins (seeded), front bright, back faint through the ghostly drum;
    // end caps as rings of dots
    if (abs(q.x) < L + R && abs(q.y) < R * 1.3) {
        for (int r = 0; r < NR; r++) {
            float a = (float(r) + 0.5) * 6.2831853 / float(NR) + rot;
            for (int dc = -2; dc <= 2; dc++) {
                int c = col0 + dc;
                if (c < 0 || c >= NC || rnd(float(c * 131 + r * 7 + 5)) > 0.30) continue;
                vec3 s = proj(-L + (float(c) + 0.5) * colw, a, R);
                float d = length(q - s.xy);
                e.r += pin(d, dot_r * (0.6 + 0.4 * abs(s.z / R))) * (s.z > 0.0 ? 0.40 : 0.09) * lit;
            }
            for (int k = -1; k <= 1; k += 2) {
                vec3 s = proj(float(k) * L, a, R);
                float d = length(q - s.xy);
                e.r += pin(d, dot_r * 0.6) * (s.z > 0.0 ? 0.30 : 0.10) * lit;
                e.g += pin(d, dot_r * 2.0) * 0.06 * lit;
            }
        }
    }
    // silhouette edges, top and bottom, as dotted lines
    for (int k = -1; k <= 1; k += 2) {
        vec3 a0 = proj(-L, float(k) * 1.5707963, R), a1 = proj(L, float(k) * 1.5707963, R);
        vec2 ba = a1.xy - a0.xy;
        float h = clamp(dot(q - a0.xy, ba) / dot(ba, ba), 0.0, 1.0);
        float hs = (floor(h * 80.0) + 0.5) / 80.0;
        float d = length(q - mix(a0.xy, a1.xy, hs));
        e.r += glow(d, 0.004 * sc) * 0.22 * lit;
        e.g += glow(d, 0.010 * sc) * 0.08 * lit;
    }

    // onset pins: each reaches the comb at its onset, then flares
    int tcol = -1;
    float tine_hit[3] = float[3](0.0, 0.0, 0.0);
    for (int i = 0; i < n_ons; i++) {
        float a = COMB + OMEGA * (ts - ons[i]);
        int pc = int(rnd(float(i) * 7.0 + 3.0) * float(NC));
        vec3 s = proj(-L + (float(pc) + 0.5) * colw, a, R);
        if (s.z < -0.2 * R) continue;
        float since = ts - ons[i];
        float pluck = since >= 0.0 ? exp(-since / 0.35) : 0.0;
        float d = length(q - s.xy);
        float b = (0.55 + 2.2 * pluck) * smoothstep(-0.2, 0.3, s.z / R);
        e.r += glow(d, dot_r * 1.5) * b * lit;
        e.b += glow(d, dot_r * 1.2) * pluck * 0.8 * lit;
        int dc = pc - col0;
        if (dc >= -1 && dc <= 1) tine_hit[dc + 1] += pluck;
    }

    // the comb: one tine per column standing on the drum at the comb angle, and its bar
    float th = 0.20 * sc;
    vec3 bar0 = proj(-L, COMB, R), bar1 = proj(L, COMB, R);
    for (int dc = -1; dc <= 1; dc++) {
        int c = col0 + dc;
        if (c < 0 || c >= NC) continue;
        vec3 s = proj(-L + (float(c) + 0.5) * colw, COMB, R);
        if (q.y < s.y || q.y > s.y + th) continue;
        float hit = tine_hit[dc + 1];
        float wig = 0.004 * sc * hit * sin(ts * 55.0) * (q.y - s.y) / th;
        float d = abs(q.x - s.x - wig);
        e.r += glow(d, 0.0025 * sc) * (0.22 + 1.6 * hit) * lit;
        e.b += glow(d, 0.0020 * sc) * hit * 0.5 * lit;
    }
    {
        vec2 a0 = bar0.xy + vec2(0.0, th), a1 = bar1.xy + vec2(0.0, th);
        vec2 ba = a1 - a0;
        float d = length(q - a0 - ba * clamp(dot(q - a0, ba) / dot(ba, ba), 0.0, 1.0));
        e.r += glow(d, 0.004 * sc) * 0.35 * lit;
    }

    // violet breath around the drum and a faint fog
    e.g += 0.10 * exp(-dot(q / vec2(L * 1.3, R * 1.6), q / vec2(L * 1.3, R * 1.6))) * (0.6 + rms) * lit;
    e.g += 0.06 * smoothstep(0.55, 0.95, fbm(p * 1.4 + vec2(t * 0.04, 0.0))) * smoothstep(0.0, 2.0, ts);

    // the logo, drawn by a pen at constant speed; the pen head burns bone-white
    float drawn = clamp((ts - DRAW_AT) / DRAW_DUR, 0.0, 1.0) * pen_len;
    if (drawn > 0.0) {
        float d = 1e3;
        vec2 head = vec2(0.0);
        for (int i = 0; i < n_segs; i++) {
            if (cum[i].x >= drawn) break;
            vec2 a = segs[i].xy, b = segs[i].zw;
            float f = clamp((drawn - cum[i].x) / max(cum[i].y - cum[i].x, 1e-6), 0.0, 1.0);
            b = a + (b - a) * f;
            d = min(d, seg_dist(p, a, b));
            head = b;
        }
        float done = step(pen_len - 1e-4, drawn);
        float hum = 0.92 + 0.08 * sin(t * 7.0 + p.x * 3.0);
        e.r += glow(d, 0.0045) * (1.1 + 0.6 * flash + 0.5 * kick) * hum;
        e.g += glow(d, 0.02) * 0.18;
        float hd = length(p - head);
        e.b += glow(hd, 0.010) * 1.6 * (1.0 - done);
        e.r += glow(hd, 0.025) * 0.5 * (1.0 - done);
        e.b += glow(d, 0.004) * bone;
    }
    frag = vec4(e, 1.0);
}
