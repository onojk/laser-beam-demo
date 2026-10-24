// Choruses: an organ-pipe wall lit by copper bars, and the ghost barbershop quartet.
//
// Copper bars (the classic raster effect: horizontal gradient bars bobbing on sines) run
// across the whole frame, dim on the wall and bright where they cross the pipes, whose
// cylindrical shading catches them. The bars swell with the low band. Each pipe also
// "speaks" from its mouth on the beat.
// In front, four glowing ghost heads in boater hats: bass, baritone, lead, tenor. Each lights
// up and opens its mouth with its band (low, low+mid, mid, high), and they sway together on
// the beat. In the final chorus all four are lit and the bars burn brightest.
const int NP = 27;                // pipes
const float SPAN = 3.3;           // façade width, P units
const float FOOT = -0.70;         // pipe feet stand here (above the scroller)
const int BARS = 7;

float pipe_top(int i) {
    float x = (float(i) + 0.5) / float(NP) * 2.0 - 1.0;            // -1..1 across the façade
    // a central tower, two flanking towers, flats between; small seeded variation
    float h = 0.85 * pow(1.0 - abs(x), 0.7) + 0.35;
    h += 0.30 * exp(-pow((abs(x) - 0.62) / 0.08, 2.0));
    h += 0.06 * (rnd(float(i) + 300.0) - 0.5);
    return min(FOOT + 0.12 + h * 1.25, 0.92);
}

float raster(float y, out float violet) {
    float g = 0.0; violet = 0.0;
    float w = 0.030 * (0.7 + 1.3 * low) * (1.0 + 0.3 * finale);
    for (int k = 0; k < BARS; k++) {
        float fk = float(k);
        float yk = 0.55 * sin(t * (0.55 + 0.11 * fk) + fk * 0.9) + 0.12 * sin(t * 1.7 + fk * 2.3);
        // classic copper profile: a bright core with soft shoulders
        float b = exp(-pow((y - yk) / w, 2.0)) + 0.35 * exp(-pow((y - yk) / (3.0 * w), 2.0));
        if (k % 2 == 0) g += b; else violet += b;
    }
    float amp = (0.35 + 0.9 * low) * (1.0 + 0.3 * finale);
    violet *= amp; return g * amp;
}

// one quartet head: silhouette distance in head units (boater hat, head, neck, shoulders)
float head_sdf(vec2 g) {
    float head = (length(g / vec2(0.30, 0.38)) - 1.0) * 0.30;
    float neck = max(abs(g.x) - 0.12, abs(g.y + 0.45) - 0.12);
    vec2 s = (g - vec2(0.0, -0.82)) / vec2(0.78, 0.36);
    float shoulders = (length(s) - 1.0) * 0.36;
    float brim = max(abs(g.x) - 0.50, abs(g.y - 0.27) - 0.030);
    float crown = max(abs(g.x) - 0.29, abs(g.y - 0.39) - 0.10);
    return min(min(min(head, neck), shoulders), min(brim, crown));
}

void main() {
    vec2 p = P();
    vec3 e = vec3(0.0);
    float vio;
    float cop = raster(p.y, vio);

    // the wall: the bars at low strength, with faint horizontal raster lines
    float lines = 0.75 + 0.25 * sin(p.y * 260.0);
    e.r += cop * 0.10 * lines;
    e.g += vio * 0.12 * lines;

    // pipes
    float pw = SPAN / float(NP);
    int i = int(floor((p.x + SPAN * 0.5) / pw));
    if (i >= 0 && i < NP) {
        float cx = -SPAN * 0.5 + (float(i) + 0.5) * pw;
        float lx = (p.x - cx) / (pw * 0.40);                     // -1..1 across the pipe
        float top = pipe_top(i);
        float foot_top = FOOT + 0.10;
        float halfw = p.y < foot_top ? mix(0.25, 1.0, (p.y - FOOT) / 0.10) : 1.0;
        if (abs(lx) < halfw && p.y > FOOT && p.y < top) {
            float cyl = sqrt(max(0.0, 1.0 - lx * lx));
            float hi = exp(-pow((lx - 0.35) / 0.18, 2.0));
            // the pipe speaks: a glow rising from its mouth, staggered across the façade
            float ph = fract(beat * 0.5 + rnd(float(i) + 500.0));
            float speak = exp(-ph * 4.0) * (0.3 + 0.9 * low) * exp(-max(0.0, p.y - foot_top) * 2.5);
            e.r += (0.03 + cop * 0.42) * cyl * cyl + hi * (0.06 + cop * 0.45) + speak * 0.4 * cyl;
            e.g += vio * 0.30 * cyl * cyl + hi * vio * 0.15;
            e.b += hi * cop * 0.15 * (0.3 + finale) + 0.25 * kick * hi;
            // the mouth: a dark notch with a lit lip
            float my = foot_top + 0.05;
            float mouth = max(abs(lx) - 0.55, abs(p.y - my) - 0.012 - 0.015 * (1.0 - abs(lx)));
            e *= mix(1.0, 0.15, step(mouth, 0.0));
            e.r += exp(-pow((p.y - my - 0.03) / 0.006, 2.0)) * step(abs(lx), 0.6) * (0.25 + speak);
            // the top: a lit rim
            e.r += exp(-pow((p.y - top) / 0.006, 2.0)) * 0.35 * cyl;
        }
    }

    // the quartet
    float sway = 0.035 * sin(3.14159 * beat);
    for (int k = 0; k < 4; k++) {
        float band = k == 0 ? low : k == 1 ? 0.5 * (low + mid) : k == 2 ? mid : high;
        float lit = smoothstep(0.18, 0.50, band);
        lit = max(lit, 0.9 * finale);
        vec2 pos = vec2(-0.84 + 0.56 * float(k) + sway, -0.32 + 0.015 * sin(t * 1.3 + float(k)));
        float sc = 0.24;
        vec2 g = (p - pos) / sc;
        g.x += 0.08 * sin(3.14159 * beat) * g.y;                   // lean into the sway
        float d = head_sdf(g);
        float fadeb = smoothstep(-1.15, -0.65, g.y);              // shoulders melt away
        float inside = (1.0 - smoothstep(-0.02, 0.02, d)) * fadeb;
        // face: hollow eyes and a singing O that opens with the band
        float eyes = min(length(g - vec2(-0.11, 0.05)), length(g - vec2(0.11, 0.05))) - 0.045;
        float open = 0.02 + 0.09 * band * (0.4 + 0.6 * lit);
        float mouth = length((g - vec2(0.0, -0.17)) / vec2(0.07, open)) - 1.0;
        float hollow = max(1.0 - smoothstep(-0.01, 0.02, eyes), 1.0 - smoothstep(-0.05, 0.05, mouth));
        float rim = exp(-d * d / 0.0015) * fadeb;
        float wisp = fbm(g * 3.0 + vec2(0.0, t * 0.5) + float(k) * 4.0);
        float body = inside * (0.05 + 0.40 * lit) * (0.6 + 0.6 * wisp) * (1.0 - hollow);
        // draw: a shadow halo and occlusion over the pipes behind, then the ghost's own glow
        e *= 1.0 - 0.75 * exp(-max(d, 0.0) * max(d, 0.0) / 0.03) * fadeb;
        e *= 1.0 - inside * 0.95;
        e.g += body + rim * (0.10 + 0.25 * lit);
        e.r += rim * (0.06 + 1.2 * lit);
        e.b += rim * lit * (0.25 + 0.5 * flash) + body * bone * 0.5;
        // the sung note: a soft violet halo off the mouth when lit
        e.g += lit * band * 0.25 * exp(-dot(g - vec2(0.0, -0.17), g - vec2(0.0, -0.17)) / 0.08) * (1.0 - inside);
    }
    frag = vec4(e, 1.0);
}
