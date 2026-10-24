// Verses: a dark candlelit tunnel (the classic demoscene tunnel: angle and 1/r as texture
// coordinates) of stone bricks with candles in niches, and sheet ghosts drifting toward us.
// Speed follows rms: depth is `travel`, the running integral of an rms-driven speed.
// On each bone flash one ghost swoops past close to the camera.
const float K = 0.30;             // tunnel radius on screen at depth 1
const float NU = 24.0;            // bricks around
const float BRICK = 0.12;         // brick length along the tunnel, depth units
const int GHOSTS = 6;

float brick_hash(vec2 id) { return rnd(id.x * 37.0 + id.y * 1031.0 + 11.0); }

// candle niche in brick `id`, seen from local coords f (0..1 in the brick); returns
// (flame, light pool)
vec2 candle(vec2 id, vec2 f) {
    if (brick_hash(id) > 0.10) return vec2(0.0);
    float flick = 0.65 + 0.35 * vnoise(vec2(t * 9.0, id.x * 3.1 + id.y * 1.7)) + 0.6 * flash;
    vec2 d = (f - vec2(0.5, 0.42)) * vec2(1.0, 0.55);
    float flame = exp(-dot(d, d) / 0.003) * flick;
    float pool = exp(-dot(f - 0.5, f - 0.5) / 0.35) * flick;
    return vec2(flame, pool);
}

// a sheet ghost of size s at pos, tilted sw; returns (emission, rim)
vec2 ghost(vec2 p, vec2 pos, float s, float sw, float fk) {
    vec2 g = (p - pos) / s;
    g = mat2(cos(sw), -sin(sw), sin(sw), cos(sw)) * g;
    float wave = 0.09 * sin(g.x * 11.0 + t * 4.0 + fk);
    float head = length(g - vec2(0.0, 0.3)) - 0.5;
    float body = max(abs(g.x) - 0.5, max(g.y - 0.3, (-0.85 + wave) - g.y));
    float d = min(head, body);
    float eyes = min(length(g - vec2(-0.18, 0.38)), length(g - vec2(0.18, 0.38))) - 0.085;
    float mouth = length((g - vec2(0.0, 0.12)) * vec2(1.6, 1.0)) - 0.08;
    float holes = min(eyes, mouth);
    float wisp = fbm(g * 2.5 + vec2(0.0, t * 0.6) + fk);
    // the hem dissolves: below the waist the sheet fades into tattered wisps
    float hem = smoothstep(-0.9, -0.1, g.y + 0.35 * (wisp - 0.5));
    float inside = (1.0 - smoothstep(-0.06, 0.06, d)) * hem;
    float rim = exp(-d * d / 0.006) * hem;
    float hollow = 1.0 - smoothstep(-0.01, 0.03, holes);
    return vec2((inside * (0.12 + 0.30 * wisp) + rim * 0.28) * (1.0 - hollow), rim);
}

void main() {
    vec2 p = P();
    vec2 c = 0.07 * vec2(sin(t * 0.31), cos(t * 0.23));
    vec2 q = p - c;
    float r = max(length(q), 1e-3);
    float a = atan(q.y, q.x);
    float z = K / r;
    float px = 2.0 / res.y;                                   // one pixel in P units
    vec3 e = vec3(0.0);

    // bricks
    float u = a / 6.2831853 + 0.035 * sin(z * 0.3 + t * 0.2);
    float v = z + travel;
    float row = floor(v / BRICK);
    float uu = u * NU + 0.5 * mod(row, 2.0);
    vec2 id = vec2(mod(floor(uu), NU), row);
    vec2 f = vec2(fract(uu), fract(v / BRICK));
    // mortar, antialiased with the analytic footprint of a pixel in brick units
    float au = NU / (6.2831853 * r) * px, av = K / (r * r) * px / BRICK;
    float mu = min(f.x, 1.0 - f.x), mv = min(f.y, 1.0 - f.y);
    float mortar = max(1.0 - smoothstep(0.0, 0.04 + au, mu), 1.0 - smoothstep(0.0, 0.05 + av, mv));
    float fade = exp(-z * 0.30);
    float stone = 0.03 + 0.06 * fbm(vec2(f.x * 3.0, f.y * 2.0) + id * 1.7);

    // candles: this brick's flame, and light pools from the 3 x 3 bricks around
    vec2 own = candle(id, f);
    float light = 0.0;
    for (int dy = -1; dy <= 1; dy++)
        for (int dx = -1; dx <= 1; dx++) {
            vec2 nid = vec2(mod(id.x + float(dx), NU), id.y + float(dy));
            light += candle(nid, f - vec2(dx, dy)).y;
        }
    // dark stone faces, and the mortar as a faint phosphor grid that the candles warm
    float wall = stone * (0.5 + 2.0 * light) * (1.0 - mortar);
    wall += mortar * (0.10 + 0.28 * light + 0.30 * kick);
    e.r += wall * fade * (0.8 + 0.4 * low);
    e.r += own.x * 0.9 * fade;
    e.b += own.x * 0.55 * fade;

    // the far dark, with a violet breath down the middle
    e.g += 0.14 * exp(-r * r / 0.012) * (0.5 + rms);

    // sheet ghosts: each at a depth that shrinks as it drifts toward us, then loops
    for (int k = 0; k < GHOSTS; k++) {
        float fk = float(k);
        float zg = 0.45 + 11.0 * fract(rnd(fk + 1.0) - travel * 0.07 - t * 0.02);
        float vis = smoothstep(11.0, 7.0, zg) * smoothstep(0.45, 1.3, zg);
        if (vis <= 0.0) continue;
        float th = rnd(fk + 21.0) * 6.2831853 + 0.25 * sin(t * 0.4 + fk);
        float rho = 0.55 + 0.30 * rnd(fk + 41.0);
        vec2 pos = c + K * rho / zg * vec2(cos(th), sin(th));
        float s = K * 0.32 / zg;
        vec2 gr = ghost(p, pos, s, 0.25 * sin(t * 0.7 + fk * 2.0), fk);
        float ghost = gr.x, rim = gr.y;
        e.g += ghost * vis * (0.8 + 0.4 * mid);
        e.r += rim * vis * 0.03;
    }

    // on each bone flash one ghost swoops past close to the camera, large and translucent,
    // from a side seeded by the flash's index
    const float SWOOP = 1.5;
    if (since_bone < SWOOP) {
        float k = float(bone_n);
        float d = since_bone / SWOOP;
        float th = rnd(k * 3.0 + 101.0) * 6.2831853;
        // in screen terms: grows from small to bigger than the frame while sliding outward
        float size = mix(0.15, 1.7, d * d);
        vec2 pos = c + mix(0.15, 1.3, d * d) * vec2(cos(th), sin(th));
        vec2 gr = ghost(p, pos, size, 0.6 * (rnd(k + 7.0) - 0.5) + 0.8 * d * sign(cos(th)), k);
        float vis = smoothstep(0.0, 0.15, d) * (1.0 - smoothstep(0.65, 1.0, d)) * 0.6;
        e.g += gr.x * vis;
        e.b += gr.y * vis * 0.25;
    }
    frag = vec4(e, 1.0);
}
