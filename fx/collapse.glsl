// Outro: everything streaks inward and collapses into one green laser line.
//
// The film's own scenes are replayed into `src` in turn (tunnel, the pipes and quartet, the
// archive; see render.py OUTRO_SOURCES) while `collapse` squeezes them toward the centre line,
// each tap of a motion streak sampled a little further out, so the picture smears inward as
// it goes. What's left is the laser line: it holds and breathes with the music, wobbles ever
// slower through the tape stop (tape_phase is the slowing tape's own clock), sags as the pitch
// drops, then snaps to a dot like an old CRT switching off. Black follows (post gain 0).
const int TAPS = 12;

void main() {
    vec2 p = P();
    vec3 e = vec3(0.0);
    float c = collapse;

    // the squeezed, streaking picture
    float sy = max(1.0 - c, 0.004);
    float sx = 1.0 - 0.35 * c;
    vec3 acc = vec3(0.0);
    float wsum = 0.0;
    for (int k = 0; k < TAPS; k++) {
        float fk = float(k) / float(TAPS - 1);
        float reach = 1.0 + fk * 0.9 * c;                         // further out = earlier
        vec2 q = vec2(0.5 + (uv.x - 0.5) / sx * mix(1.0, reach, 0.25), 0.5 + (uv.y - 0.5) / sy * reach);
        float w = 1.0 - 0.7 * fk;
        if (all(greaterThanEqual(q, vec2(0.0))) && all(lessThanEqual(q, vec2(1.0))))
            acc += texture(src, q).rgb * w;
        wsum += w;
    }
    float pic = 1.0 - smoothstep(0.85, 1.0, c);
    e += acc / wsum * (1.0 + 2.5 * c) * pic;

    // the laser line, born as the picture thins
    float born = smoothstep(0.55, 0.95, c);
    float x = tape;
    float amp = (0.004 + 0.002 * rms) * (1.0 - x) + 0.07 * x * (1.0 - 0.5 * x);
    float freq = mix(9.0, 2.5, x);
    float y = amp * sin(p.x * freq - tape_phase * 14.0) - 0.10 * x * x;
    float half_len = mix(1.95, 0.0, snap);
    float along = max(0.0, abs(p.x) - half_len);
    float d = length(vec2(along, p.y - y));
    float width = (0.0035 + 0.002 * rms + 0.002 * kick) * (1.0 + 0.8 * snap);
    float core = glow(d, width) * born;
    e.r += core * (1.2 + 0.5 * rms + 1.5 * snap);
    e.b += glow(d, width * 0.5) * born * (0.25 + 0.4 * bone + 1.2 * snap);
    e.g += glow(d, 0.05) * born * 0.10 * (1.0 - snap);
    frag = vec4(e, 1.0);
}
