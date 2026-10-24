// Look test (Stage 2): every element of the palette in one frame, nothing scene-specific.
// Violet fog drifting, a green laser line that hums with the mid band, rings that pulse out
// on each beat with the low band, the title in green with a violet halo, bone on big beats.
uniform sampler2D title;
uniform vec2 title_size;

void main() {
    vec2 p = P();
    vec3 e = vec3(0.0);

    // violet fog: slow fbm, breathing with rms
    float fog = fbm(p * 1.6 + vec2(t * 0.05, -t * 0.03));
    fog = smoothstep(0.52, 0.95, fog + 0.15 * fbm(p * 4.0 - t * 0.1));
    e.g += fog * (0.10 + 0.22 * rms);

    // rings from the centre, one per beat, fading as they grow
    float r = length(p * vec2(1.0, 1.15));
    float age = fract(beat);
    float ring = glow(r - age * 1.6, 0.012 + 0.02 * age) * (1.0 - age) * (0.3 + 0.9 * low);
    e.r += ring * 0.8;
    e.g += ring * 0.25;

    // the laser line: a horizontal beam with a slow sine hum
    float y = -0.55 + 0.03 * sin(p.x * 3.0 + t * 1.3) * (0.3 + mid);
    float line = glow(p.y - y, 0.004 + 0.003 * mid);
    e.r += line * (0.9 + 0.8 * flash);
    e.b += line * 0.25 * flash;

    // title: sampled from the drawtext texture, with a violet halo under it
    vec2 tuv = (p - vec2(0.0, 0.08)) / vec2(1.6, 0.30) + 0.5;
    if (all(greaterThan(tuv, vec2(0.0))) && all(lessThan(tuv, vec2(1.0)))) {
        float g = texture(title, tuv).r;
        e.r += g * (0.75 + 0.5 * flash);
        e.b += g * bone * 0.8;
    }
    e.g += 0.12 * exp(-pow(length((p - vec2(0.0, 0.08)) * vec2(0.7, 2.5)), 2.0)) * (0.5 + rms);

    // bone channel also catches the brightest parts on big beats
    e.b += bone * 0.3 * (e.r + e.g);
    frag = vec4(e, 1.0);
}
