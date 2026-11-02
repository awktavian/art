/**
 * shaders.js — hand-written GLSL ES 3.00 for the CFSG group atlas.
 *
 * No library, no build step, no CDN: WebGL2 and this file. Four passes render
 * into one float scene target with a real depth attachment, and one resolve
 * pass folds them into a progressive accumulation buffer:
 *
 *   1. manifold   fullscreen, raymarched. The recursive Coxeter lattice the
 *                 families stand on — a folded pillar-and-beam temple whose
 *                 symmetry angle is a uniform, so the ground shares the atlas's
 *                 geometry language. Writes gl_FragDepth reconstructed through
 *                 the same projection the raster passes use, which is what
 *                 makes occlusion between raymarched and rasterised geometry
 *                 correct instead of approximate.
 *   2. nodes      one instanced billboard per group (42). Each fragment
 *                 reconstructs its exact world ray from the interpolated
 *                 billboard position — no direction approximation — marches the
 *                 node's own SDF (a sphere carved by the m-fold Coxeter wedge
 *                 derived from its Cartan matrix, or left smooth where CFSG
 *                 states no Cartan matrix), shadows against three lights, then
 *                 takes one diffuse bounce that re-marches the manifold field.
 *                 Primary + shadow + one GI bounce per sample: the path-traced
 *                 half of the piece.
 *   3. filaments  instanced ribbons: Y443's Nielsen adjacency, the diagram
 *                 automorphisms, the drawn cycle structure of the permutation
 *                 carriers, the 2A suborbit ring. Additive, depth-tested.
 *   4. points     instanced sprites: the root systems (E8's 240 roots are the
 *                 brightest object on screen and they are computed, not drawn),
 *                 Y443's generators, the cyclic-prime and alternating arms.
 *
 * Determinism: the sampler's RNG is a 32-bit integer hash of
 * (seed, pixel, frameIndex, sampleIndex) — the same input always gives the
 * same path, so accumulation order cannot drift. The renderer's deterministic
 * mode never reads a clock, so `tools/determinism.mjs` can pin frames.
 */

import { FAR } from "./mat4.js";

export { FAR };

/** Vertex shader shared by every fullscreen pass. */
export const VS_FULL = `#version 300 es
precision highp float;
const vec2 CORNERS[3] = vec2[3](vec2(-1.0, -1.0), vec2(3.0, -1.0), vec2(-1.0, 3.0));
out vec2 v_uv;
void main() {
  vec2 p = CORNERS[gl_VertexID];
  v_uv = p * 0.5 + 0.5;
  gl_Position = vec4(p, 0.0, 1.0);
}`;

/**
 * The common chunk: seeded integer hash sampler, polar Coxeter fold, signed
 * distances, the manifold field, and the depth reconstruction that keeps the
 * raymarch and the raster passes in one depth buffer.
 */
const COMMON = `
precision highp float;
precision highp int;
uniform vec2 u_res;
uniform float u_far;
uniform uint u_seed;
uniform int u_frame;
uniform vec3 u_cam;
uniform mat4 u_view;
uniform mat4 u_proj;

const float PI = 3.141592653589793;

vec3 viewToWorld(vec3 v) { return transpose(mat3(u_view)) * v; }

/* --- sampler RNG: deterministic in (seed, pixel, frame, sample) ---------- */
uint hashu(uint x) {
  x ^= x >> 16u;
  x *= 0x21f0aaadu;
  x ^= x >> 15u;
  x *= 0x735a2d97u;
  x ^= x >> 15u;
  return x;
}
float rnd(inout uint state) {
  state = hashu(state + 0x9e3779b9u);
  return float(state >> 8) * (1.0 / 16777216.0);
}
vec3 cosLobe(vec3 n, inout uint state) {
  vec3 t = abs(n.y) < 0.9 ? normalize(cross(n, vec3(0.0, 1.0, 0.0))) : cross(n, vec3(1.0, 0.0, 0.0));
  vec3 b = cross(n, t);
  float a = rnd(state) * 6.2831853;
  float r = sqrt(rnd(state));
  return normalize(t * cos(a) * r + b * sin(a) * r + n * sqrt(max(0.0, 1.0 - r)));
}

/* --- depth: one mapping for every pass ----------------------------------- */
float depthOf(vec3 world) {
  vec4 c = u_proj * u_view * vec4(world, 1.0);
  return clamp(c.z / c.w * 0.5 + 0.5, 0.0, 1.0);
}

/* --- geometry ------------------------------------------------------------ */
vec2 foldWedge(vec2 p, float a) {
  float s = 2.0 * a;
  float ang = mod(atan(p.y, p.x), s);
  if (ang > a) ang = s - ang;
  return length(p) * vec2(cos(ang), sin(ang));
}
mat2 rot2(float a) { float c = cos(a), s = sin(a); return mat2(c, -s, s, c); }
float sdSphere(vec3 p, float r) { return length(p) - r; }
float sdBox(vec3 p, vec3 b) {
  vec3 q = abs(p) - b;
  return length(max(q, 0.0)) + min(max(q.x, max(q.y, q.z)), 0.0);
}
float sdRoundBox(vec3 p, vec3 b, float r) { return sdBox(p, b) - r; }

/* --- the manifold: a recursive Coxeter lattice -------------------------- */
uniform float u_foldA;
/*
 * The manifold is a FOUNDATION, not a forest. The ground plane is y = -3.0 and
 * every pillar is founded on it (pillar crowns at y = -1.70, lintel tops at y = -1.60), so the
 * camera always looks across the lattice and never through it, and the atlas's
 * own volume stays unobstructed above the plinth.
 *
 * The tiling is periodic in the folded plane only: height stays a world height.
 * Wrapping y as well (an earlier version did) repeats the pillars through the
 * whole sky, which is what put translucent horizontal slabs through the middle
 * of the cluster in a screenshot — a bug caught by looking, not by review.
 * Each level folds its (x, z) through the Coxeter wedge first, so the field
 * carries the same 6-fold symmetry as the nodes carved by their own m.
 */
float mapLattice(vec3 p) {
  float d = p.y + 3.0 + 0.42 * cos(p.x * 0.17) * sin(p.z * 0.17);
  vec2 xz = p.xz;
  for (int level = 0; level < 2; level++) {
    vec2 folded = foldWedge(xz, u_foldA + float(level) * 0.16);
    vec2 cell = mod(folded, vec2(6.0)) - vec2(3.0);
    float pillar = sdRoundBox(vec3(cell.x, p.y + 2.35, cell.y), vec3(0.28, 0.65, 0.28), 0.05);
    // lintels run between neighbouring pillars: thin, and short enough that the
    // grid reads as structure rather than as a wall across the horizon
    float beam = sdRoundBox(vec3(cell.x, p.y + 1.82, cell.y), vec3(2.1, 0.075, 0.16), 0.03);
    d = min(d, min(pillar, beam));
    xz = rot2(PI / 6.0) * folded * 0.62;
  }
  return d;
}
vec3 nrmLattice(vec3 p) {
  vec2 e = vec2(0.0016, 0.0);
  return normalize(vec3(
    mapLattice(p + e.xyy) - mapLattice(p - e.xyy),
    mapLattice(p + e.yxy) - mapLattice(p - e.yxy),
    mapLattice(p + e.yyx) - mapLattice(p - e.yyx)));
}
bool marchLattice(vec3 ro, vec3 rd, float tmax, float eps, int steps, out float tOut) {
  float t = 0.0;
  tOut = tmax;
  for (int i = 0; i < steps; i++) {
    vec3 p = ro + rd * t;
    float d = mapLattice(p);
    if (d < eps * (1.0 + t)) { tOut = t; return true; }
    t += max(d, eps);
    if (t > tmax) return false;
  }
  return false;
}

/* --- light rig ----------------------------------------------------------- */
uniform vec4 u_light0;
uniform vec4 u_light1;
uniform vec4 u_light2;
vec3 lights(vec3 p, vec3 n) {
  vec4 L[3] = vec4[3](u_light0, u_light1, u_light2);
  vec3 acc = vec3(0.0);
  for (int i = 0; i < 3; i++) {
    vec3 dl = L[i].xyz - p;
    float dist = length(dl);
    vec3 ld = dl / max(dist, 1e-5);
    float ndl = max(dot(n, ld), 0.0);
    if (ndl <= 0.0) continue;
    float att = 1.0 / (1.0 + 0.05 * dist * dist);
    float st;
    bool blocked = marchLattice(p + n * 0.03, ld, dist - 0.03, 0.004, 34, st);
    acc += L[i].w * ndl * att * (blocked ? 0.10 : 1.0);
  }
  return acc * vec3(0.86, 0.92, 1.0);
}
vec3 sky(vec3 rd) {
  float up = clamp(rd.y * 0.5 + 0.5, 0.0, 1.0);
  vec3 voidA = vec3(0.017, 0.014, 0.032);
  vec3 voidB = vec3(0.005, 0.006, 0.014);
  float band = exp(-pow((rd.y - 0.05) * 2.6, 2.0)) * 0.085;
  return mix(voidB, voidA, up) + vec3(0.30, 0.58, 0.72) * band;
}
`;

/* ------------------------------------------------------------------ 1 */
export const FS_MANIFOLD = `#version 300 es
${COMMON}
uniform float u_time;
out vec4 o_color;
void main() {
  vec2 uv = gl_FragCoord.xy / u_res;
  vec2 ndc = uv * 2.0 - 1.0;
  vec4 f = u_proj * vec4(ndc, -1.0, 1.0);
  vec3 rd = normalize(viewToWorld(f.xyz / f.w));
  uint state = uint(gl_FragCoord.x) * 1973u + uint(gl_FragCoord.y) * 8191u + uint(u_frame) * 331u;
  state = hashu(state ^ u_seed);

  vec3 ro = u_cam;
  float t;
  vec3 col;
  if (marchLattice(ro, rd, 70.0, 0.0018, 96, t)) {
    vec3 p = ro + rd * t;
    vec3 n = nrmLattice(p);
    /*
     * Four luminous spokes across the floor: the four arms of knownSimpleOrders.
     * The band coordinate is the angle folded into four periods and measured to
     * the nearest sector wall, so arm is 1 ON a spoke and 0 off it. (An earlier
     * version folded the wrong way and arm was 1 over 90% of the plane, which is
     * why the lower half of the frame was one cyan wash — caught on a screenshot,
     * not in review.)
     */
    float spoke = fract(atan(p.z, p.x) / (PI * 0.5));
    // 1 - smoothstep with ascending edges: GLSL leaves edge0 >= edge1 undefined
    float arm = 1.0 - smoothstep(0.0, 0.045, min(spoke, 1.0 - spoke));
    vec3 base = mix(vec3(0.030, 0.036, 0.055), vec3(0.062, 0.075, 0.105), 0.5 + 0.5 * sin(p.y * 0.4));
    col = base * lights(p, n) * 0.62;
    col += arm * vec3(0.035, 0.150, 0.185) * (0.55 + 0.45 * sin(length(p.xz) * 0.6 - u_time * 0.02));
    // one diffuse bounce, marched against the manifold again
    vec3 gd = cosLobe(n, state);
    float gt;
    if (marchLattice(p + n * 0.03, gd, 26.0, 0.004, 44, gt)) {
      vec3 gp = p + n * 0.03 + gd * gt;
      col += vec3(0.075, 0.085, 0.115) * lights(gp, nrmLattice(gp)) * 0.34 * max(dot(n, gd), 0.0);
    } else {
      col += sky(gd) * max(dot(n, gd), 0.0) * 0.22;
    }
    // depth fade: the lattice dissolves into the void by ~35 units, so the
    // cluster reads against black rather than against an endless floor.
    col = mix(col, sky(rd), 1.0 - exp(-pow(t * 0.044, 1.7)));
    o_color = vec4(col, 1.0);
    gl_FragDepth = depthOf(p);
  } else {
    o_color = vec4(sky(rd), 1.0);
    gl_FragDepth = 1.0;
  }
}`;

/* ------------------------------------------------------------------ 2 */
export const VS_NODE = `#version 300 es
precision highp float;
uniform mat4 u_view;
uniform mat4 u_proj;
in vec2 a_corner;
in vec3 i_center;
in float i_radius;
in vec3 i_color;
in float i_theta;
in float i_kind;
in float i_m;
in float i_rank;
in float i_order;
in float i_char;
in float i_roots;
in float i_id;
out vec3 v_center;
out vec3 v_world;
out vec3 v_color;
out float v_theta;
out float v_kind;
out float v_m;
out float v_rank;
out float v_order;
out float v_char;
out float v_roots;
out float v_id;
out float v_radius;
void main() {
  float h = i_radius * 1.46;
  vec4 vp = u_view * vec4(i_center, 1.0);
  vp.xy += a_corner * h;
  // view-space billboard offset mapped back to world by the inverse rotation
  v_world = i_center + transpose(mat3(u_view)) * vec3(a_corner * h, 0.0);
  v_center = i_center;
  v_color = i_color;
  v_theta = i_theta;
  v_kind = i_kind;
  v_m = i_m;
  v_rank = i_rank;
  v_order = i_order;
  v_char = i_char;
  v_roots = i_roots;
  v_id = i_id;
  v_radius = i_radius;
  gl_Position = u_proj * vp;
}`;

export const FS_NODE = `#version 300 es
${COMMON}
in vec3 v_center;
in vec3 v_world;
in vec3 v_color;
in float v_theta;
in float v_kind;
in float v_m;
in float v_rank;
in float v_order;
in float v_char;
in float v_roots;
in float v_id;
in float v_radius;
uniform float u_time;
uniform float u_focus;
uniform float u_hover;
out vec4 o_color;

/* The node's own shape: a sphere carved by its Coxeter wedge. Where CFSG
 * states no Cartan matrix (v_theta == 0) the node stays smooth with one band,
 * and that smooth silhouette is itself the datum — "no root system in the
 * source" — so the absence is drawn instead of hidden. */
float sdNode(vec3 p) {
  float s = length(p) / v_radius - 1.0;
  if (v_theta > 0.0) {
    vec3 f = p / v_radius;
    f.xy = foldWedge(f.xy, v_theta);
    float facet = sdBox(f - vec3(0.70, 0.0, 0.0), vec3(0.30, 0.17, 0.17));
    // the second facet is the first one reflected in the wedge wall: rotate the
    // folded (x, y) pair by 2θ, which is what a reflection across the wall does
    vec2 mirrored = rot2(2.0 * v_theta) * f.xy;
    float facet2 = sdBox(vec3(mirrored, f.z) - vec3(0.62, 0.0, 0.0), vec3(0.22, 0.13, 0.13));
    float ring = abs(length(f.zy) - 0.62) - 0.055;
    float carve = min(facet, min(facet2, ring));
    float star = sdSphere(f, 0.30);
    return min(max(s, -carve), star) * v_radius;
  }
  vec3 f = p / v_radius;
  float band = max(length(f) - 0.93, abs(f.y) - 0.045);
  return min(s, band) * v_radius;
}

vec3 nrmNode(vec3 p) {
  vec2 e = vec2(0.0024 * v_radius, 0.0);
  return normalize(vec3(
    sdNode(p + e.xyy) - sdNode(p - e.xyy),
    sdNode(p + e.yxy) - sdNode(p - e.yxy),
    sdNode(p + e.yyx) - sdNode(p - e.yyx)));
}

void main() {
  vec3 rd = normalize(v_world - u_cam);
  vec3 oc = u_cam - v_center;
  float b = dot(oc, rd);
  float rb = v_radius * 1.46;
  float c = dot(oc, oc) - rb * rb;
  float disc = b * b - c;
  if (disc < 0.0) discard;
  float t0 = max(-b - sqrt(disc), 0.0);
  float t1 = -b + sqrt(disc);
  if (t1 <= 0.0) discard;

  bool hit = false;
  float t = t0;
  vec3 p = u_cam;
  for (int i = 0; i < 64; i++) {
    p = u_cam + rd * t;
    float d = sdNode(p - v_center);
    if (d < 0.0016 * (1.0 + t)) { hit = true; break; }
    t += max(d, 0.005 * v_radius);
    if (t > t1) break;
  }
  if (!hit) discard;

  vec3 n = nrmNode(p - v_center);
  uint state = hashu(uint(gl_FragCoord.x) * 1973u + uint(gl_FragCoord.y) * 8191u
                   + uint(u_frame) * 331u + uint(v_id) * 7717u ^ u_seed);
  float focus = v_id == u_focus ? 1.0 : 0.0;
  float hover = v_id == u_hover ? 1.0 : 0.0;

  vec3 albedo = v_color;
  vec3 emissive = v_color * (0.20 + 0.75 * focus + 0.40 * hover);
  if (v_kind > 0.5) emissive *= 1.0 + 0.9 * pow(max(0.0, dot(n, -rd)), 2.0);

  vec3 col = albedo * lights(p, n) * 1.9 + emissive * 0.55;

  // the bounce: a hemisphere sample re-marched against the manifold
  vec3 gd = cosLobe(n, state);
  float gt;
  if (marchLattice(p + n * 0.03, gd, 30.0, 0.004, 40, gt)) {
    vec3 gp = p + n * 0.03 + gd * gt;
    col += albedo * vec3(0.07, 0.08, 0.11) * lights(gp, nrmLattice(gp)) * 1.8 * max(dot(n, gd), 0.0);
  } else {
    col += albedo * sky(gd) * max(dot(n, gd), 0.0);
  }
  // rim, not bloom: kept low so a dense rank column reads as separate
  // spheres instead of one white blob
  col += v_color * pow(1.0 - max(dot(n, -rd), 0.0), 3.5) * (0.30 + 0.85 * focus);

  gl_FragDepth = depthOf(p);
  o_color = vec4(col, 1.0);
}`;

/* ------------------------------------------------------------------ 3 */
export const VS_FILAMENT = `#version 300 es
precision highp float;
uniform mat4 u_view;
uniform mat4 u_proj;
in vec2 a_corner;
in vec3 i_from;
in vec3 i_to;
in float i_width;
in float i_tone;
in float i_id;
out float v_t;
out float v_tone;
out float v_id;
void main() {
  vec4 va = u_view * vec4(i_from, 1.0);
  vec4 vb = u_view * vec4(i_to, 1.0);
  float along = a_corner.y * 0.5 + 0.5;
  vec4 vp = mix(va, vb, along);
  vp.x += a_corner.x * i_width;
  v_t = along;
  v_tone = i_tone;
  v_id = i_id;
  gl_Position = u_proj * vp;
}`;

export const FS_FILAMENT = `#version 300 es
precision highp float;
in float v_t;
in float v_tone;
in float v_id;
uniform float u_time;
uniform float u_hover;
out vec4 o_color;
void main() {
  vec3 ice = vec3(0.36, 0.80, 0.92);
  vec3 gold = vec3(0.86, 0.68, 0.24);
  vec3 white = vec3(0.80, 0.86, 0.98);
  vec3 col = v_tone < 0.5 ? white : v_tone < 1.5 ? gold : v_tone < 2.5 ? ice : mix(ice, gold, 0.5);
  float core = 1.0 - abs(v_t - 0.5) * 2.0;
  float pulse = 0.55 + 0.45 * sin((v_t * 6.0 - u_time * 0.35 + v_id * 0.37) * 2.0);
  // Additive over an already-lit field: 150+ ribbons overlap in the middle of
  // the cluster, so the per-ribbon level has to be low or their intersection
  // blows out to white sheets (seen in a render, then fixed).
  o_color = vec4(col * core * (0.055 + 0.095 * pulse) * (1.0 + 1.4 * u_hover), 1.0);
}`;

/* ------------------------------------------------------------------ 4 */
export const VS_POINTS = `#version 300 es
precision highp float;
uniform mat4 u_view;
uniform mat4 u_proj;
uniform float u_pointScale;
in vec2 a_corner;
in vec3 i_pos;
in float i_kind;
in float i_size;
in float i_id;
out float v_kind;
out float v_id;
out vec2 v_c;
void main() {
  vec4 vp = u_view * vec4(i_pos, 1.0);
  vp.xy += a_corner * i_size * u_pointScale;
  v_kind = i_kind;
  v_id = i_id;
  v_c = a_corner;
  gl_Position = u_proj * vp;
}`;

export const FS_POINTS = `#version 300 es
precision highp float;
in float v_kind;
in float v_id;
in vec2 v_c;
uniform float u_time;
out vec4 o_color;
void main() {
  float r = length(v_c);
  // ascending edges: GLSL leaves edge0 >= edge1 undefined
  float disc = 1.0 - smoothstep(0.15, 1.0, r);
  if (disc < 0.002) discard;
  vec3 col = v_kind < 1.5 ? vec3(0.42, 0.88, 1.00)
           : v_kind < 2.5 ? vec3(0.92, 0.74, 0.28)
           : v_kind < 3.5 ? vec3(0.90, 0.52, 0.62)
           : vec3(0.90, 0.94, 1.00);
  float tw = 0.6 + 0.4 * sin(u_time * 0.9 + v_id * 2.399);
  o_color = vec4(col * (disc * 0.26 + exp(-r * r * 3.4) * 0.85) * tw, 1.0);
}`;

/* ------------------------------------------------------------------ 5 */
export const FS_ACCUMULATE = `#version 300 es
precision highp float;
uniform sampler2D u_scene;
uniform sampler2D u_accum;
uniform int u_frameCount;
in vec2 v_uv;
out vec4 o_color;
void main() {
  vec3 scene = texture(u_scene, v_uv).rgb;
  if (u_frameCount <= 1) { o_color = vec4(scene, 1.0); return; }
  vec3 prev = texture(u_accum, v_uv).rgb;
  o_color = vec4(mix(prev, scene, 1.0 / float(u_frameCount)), 1.0);
}`;

export const FS_DISPLAY = `#version 300 es
precision highp float;
uniform sampler2D u_accum;
uniform vec2 u_res;
uniform int u_frameCount;
in vec2 v_uv;
out vec4 o_color;
vec3 aces(vec3 x) {
  const float a = 2.51, b = 0.03, c = 2.43, d = 0.59, e = 0.14;
  return clamp((x * (a * x + b)) / (x * (c * x + d) + e), 0.0, 1.0);
}
void main() {
  vec3 col = aces(texture(u_accum, v_uv).rgb * 0.86);
  col = pow(col, vec3(1.0 / 2.2));
  // ordered dither, so a band-free frame is also a byte-stable one
  ivec2 px = ivec2(gl_FragCoord.xy);
  float bit = float((px.x & 3) * 4 + (px.y & 3));
  col += (bit / 16.0 - 0.46875) * 0.0075;
  float vig = 1.0 - 0.32 * pow(length(v_uv - 0.5) * 1.42, 2.4);
  o_color = vec4(col * vig, 1.0);
}`;

export const FS_BLANK = `#version 300 es
precision highp float;
out vec4 o_color;
void main() { o_color = vec4(0.0, 0.0, 0.0, 1.0); }`;
