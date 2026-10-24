// Bridge and breakdown: church-bell shockwaves and the archive that is listening.
//
// Bridge: a bell swings at the top, one swing per two beats, and every onset sends a
// shockwave ring out from its mouth. Below, the archive: catalogue cards bearing lines from
// the song turn slowly on a carousel, drifting like pages being filed, legible as they pass
// the front and dim behind.
// Breakdown (stripped = 1): almost dark. Only the strong onsets ring, faintly and slowly, and a
// single dim ghost head listens in the middle. Nothing else.
uniform sampler2D archive;
uniform int n_cards;

const vec2 BELL = vec2(0.0, 0.62);   // pivot
const float CARD_W = 0.60, CARD_H = 0.060;   // 10:1, the atlas cells' aspect

// the quartet's head silhouette (same as organ.glsl)
float head_sdf(vec2 g) {
    float head = (length(g / vec2(0.30, 0.38)) - 1.0) * 0.30;
    float neck = max(abs(g.x) - 0.12, abs(g.y + 0.45) - 0.12);
    vec2 s = (g - vec2(0.0, -0.82)) / vec2(0.78, 0.36);
    float shoulders = (length(s) - 1.0) * 0.36;
    float brim = max(abs(g.x) - 0.50, abs(g.y - 0.27) - 0.030);
    float crown = max(abs(g.x) - 0.29, abs(g.y - 0.39) - 0.10);
    return min(min(min(head, neck), shoulders), min(brim, crown));
}

// distance to a bell outline hanging from the origin (y down), in P units
float bell_sdf(vec2 q) {
    float y = -q.y;                                       // 0 at the pivot, + downward
    float yy = clamp(y, 0.04, 0.36);
    float u = (yy - 0.04) / 0.32;
    float w = 0.075 + 0.035 * u + 0.095 * pow(u, 5.0);    // a straight waist, then the flare
    float side = abs(abs(q.x) - w);
    if (y < 0.04 || y > 0.36) side = 1e3;
    float crown = abs(length(q - vec2(0.0, -0.04)) - 0.075);
    if (q.y < -0.04) crown = 1e3;
    float lip = abs(y - 0.36) + max(0.0, abs(q.x) - 0.205);
    return min(min(side, crown), lip);
}

void main() {
    vec2 p = P();
    vec3 e = vec3(0.0);
    bool quiet = stripped > 0.5;

    // where rings start: the bell's mouth, or the middle in the breakdown
    float swing = 0.22 * sin(3.14159 * beat * 0.5);
    vec2 mouth = quiet ? vec2(0.0, 0.05) : BELL + vec2(-sin(swing), -cos(swing)) * 0.36;

    // shockwave rings, one per onset (in the breakdown only the strong ones, slow and faint)
    for (int i = 0; i < n_ons; i++) {
        float age = ts - ons[i];
        if (age < 0.0) break;
        if (quiet && ons_s[i] < 0.55) continue;
        float life = quiet ? 5.0 : 3.2;
        if (age > life) continue;
        float r = age * (quiet ? 0.22 : 0.62);
        float d = length((p - mouth) * vec2(1.0, quiet ? 1.0 : 1.15)) - r;
        float a = exp(-age * (quiet ? 0.7 : 1.1)) * (0.35 + 0.65 * ons_s[i]);
        float ring = glow(d, 0.004 + 0.008 * age) * a;
        if (quiet) {
            e.g += ring * 0.22;
            e.r += ring * 0.05;
        } else {
            e.r += ring * 0.55;
            e.g += ring * 0.45 + glow(d - 0.03, 0.02 + 0.01 * age) * a * 0.15;
        }
    }

    if (quiet) {
        // one dim ghost head, breathing with the whisper
        vec2 g = (p - vec2(0.0, -0.05)) / 0.30;
        float d = head_sdf(g);
        float fadeb = smoothstep(-1.15, -0.6, g.y);
        float breathe = 0.5 + 0.5 * rms;
        float eyes = min(length(g - vec2(-0.11, 0.05)), length(g - vec2(0.11, 0.05))) - 0.045;
        float rim = exp(-d * d / 0.0015) * fadeb;
        float inside = (1.0 - smoothstep(-0.02, 0.02, d)) * fadeb;
        float hollow = 1.0 - smoothstep(-0.01, 0.02, eyes);
        e.g += (rim * 0.125 + inside * 0.031 * (1.0 - hollow)) * breathe;
        e.r += rim * 0.0375 * breathe;
        frag = vec4(e, 1.0);
        return;
    }

    // the bell
    vec2 q = p - BELL;
    q = mat2(cos(swing), sin(swing), -sin(swing), cos(swing)) * q;
    float bd = bell_sdf(q);
    float strike = exp(-since_onset(ts) / 0.25);
    e.r += glow(bd, 0.005) * (0.55 + 0.8 * strike);
    e.b += glow(bd, 0.004) * strike * 0.5;
    e.g += glow(bd, 0.03) * 0.12;
    float clapper = length(q - vec2(0.03 * sin(t * 3.0), -0.33)) - 0.022;
    e.r += glow(clapper, 0.006) * 0.6;
    e.r += glow(abs(p.x - BELL.x) + max(0.0, p.y - 0.98) + max(0.0, BELL.y - p.y), 0.003) * 0.3;

    // the archive carousel
    float rot = ts * 0.16;
    for (int k = 0; k < n_cards; k++) {
        float fk = float(k);
        float a = fk / float(n_cards) * 6.2831853 + rot;
        float z = cos(a);                                     // +1 front, -1 back
        float sc = 0.78 + 0.30 * z;
        vec2 c = vec2(1.18 * sin(a), -0.10 - 0.16 * z + 0.035 * sin(ts * 0.6 + fk * 1.3));
        // a page turned edge-on as it swings round the side
        float wid = CARD_W * sc * mix(0.15, 1.0, abs(z));
        vec2 l = (p - c) / vec2(wid, CARD_H * sc);
        if (abs(l.x) > 1.08 || abs(l.y) > 1.6) continue;
        float bright = mix(0.22, 1.0, smoothstep(-0.6, 0.9, z));
        float frame = max(abs(l.x) - 1.0, abs(l.y) - 1.0);
        e.g += glow(frame * CARD_H * sc, 0.0025) * 0.30 * bright;
        e.g += step(frame, 0.0) * 0.025 * bright;
        if (abs(l.x) < 1.0 && abs(l.y) < 1.0) {
            float row = (1.0 - (fk + 1.0) / float(n_cards)) + (l.y * 0.5 + 0.5) / float(n_cards);
            float txt = texture(archive, vec2(l.x * 0.5 + 0.5, row)).r;
            e.r += txt * 0.85 * bright * (0.85 + 0.3 * flash);
            e.b += txt * bone * 0.4 * bright;
        }
    }
    // a dim violet hush under everything
    e.g += 0.05 * smoothstep(0.55, 0.95, fbm(p * 1.3 + vec2(0.0, t * 0.05)));
    frag = vec4(e, 1.0);
}
