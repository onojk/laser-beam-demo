// Instrumental break: a theremin-wave plasma driven by the high band.
//
// The classic plasma (a sum of sines, here of distance to wandering centres too) is drawn as
// glowing iso-contours rather than filled, so the ground stays dark: green and violet bands,
// moving at a speed integrated from the high band (htravel) and denser when it's loud.
// Across it runs the theremin itself: an oscilloscope wave strung between the pitch rod
// (right) and the volume loop (left). Its pitch follows the spectral centroid, its vibrato
// the tape wobble, its amplitude the high band, with phosphor afterimages trailing.
const int TRAILS = 5;

float plasma(vec2 p, float h) {
    vec2 c1 = vec2(0.9 * sin(h * 0.31), 0.5 * cos(h * 0.23));
    vec2 c2 = vec2(0.8 * cos(h * 0.19 + 1.0), 0.6 * sin(h * 0.27 + 2.0));
    return sin(p.x * 2.6 + h * 0.7) + sin(p.y * 3.1 - h * 0.5)
         + sin(length(p - c1) * 5.5 - h * 1.1) + sin(length(p - c2) * 4.3 + h * 0.9);
}

void main() {
    vec2 p = P();
    vec3 e = vec3(0.0);
    float h = htravel;

    // plasma contours, antialiased by the field's own gradient
    float v = plasma(p, h) * (1.0 + 0.6 * high);
    float dens = 1.1 + 0.9 * high;
    float f = v * dens;
    float w = fwidth(f);
    float d = abs(fract(f) - 0.5);
    float line = 1.0 - smoothstep(0.0, 0.05 + w, 0.5 - d);
    float band = mod(floor(f), 2.0);
    float fade = 0.35 + 0.65 * smoothstep(1.9, 0.2, length(p * vec2(0.6, 1.0)));
    e.r += line * (0.12 + 0.35 * high) * (1.0 - band) * fade;
    e.g += line * (0.14 + 0.40 * high) * band * fade;
    e.g += 0.05 * (0.5 + 0.5 * sin(v * 1.5)) * fade;                 // faint fill between

    // the theremin: rod and loop
    float rod = abs(p.x - 1.42);
    e.r += glow(rod, 0.004) * step(abs(p.y + 0.05), 0.55) * 0.5;
    vec2 lq = (p - vec2(-1.42, -0.05)) / vec2(0.08, 0.16);
    e.r += glow((length(lq) - 1.0) * 0.08, 0.004) * 0.5;

    // the wave, strung between them; trails are the same wave a little earlier, dimmer
    float pitch = 7.0 + 14.0 * phrase;
    float vib = 0.06 * sin(t * 6.3) + 0.25 * wob;
    float amp = 0.04 + 0.30 * high + 0.08 * flash;
    float span = smoothstep(1.42, 1.30, abs(p.x));
    for (int k = 0; k < TRAILS; k++) {
        float dt = float(k) * 0.045;
        float y = -0.05 + amp * span * sin(p.x * pitch * (1.0 + vib) - (h - dt * 2.0) * 9.0)
                * (0.8 + 0.2 * sin(p.x * 1.7 + t));
        float g = glow(p.y - y, 0.005 + 0.002 * float(k)) * pow(0.55, float(k));
        e.r += g * (1.0 + 0.6 * kick);
        e.b += g * 0.35 * (k == 0 ? 1.0 : 0.0) * (0.4 + high);
    }
    frag = vec4(e, 1.0);
}
