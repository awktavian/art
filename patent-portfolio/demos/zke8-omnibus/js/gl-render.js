/**
 * gl-render.js — the live WebGL2 path for both demos.
 *
 * Each fragment shader is a LINE-BY-LINE transcription of the CPU reference in
 * e8-core.js and ref-render.js, not a re-derivation of it:
 *
 *   tri / carrier      <- carrierAt()          (exactly specified ops only)
 *   roundEven4         <- roundEven()          (GLSL's roundEven is the same
 *                                                half-to-even rule; it is written
 *                                                out here because the coset scan
 *                                                needs floor()+d() anyway)
 *   nearestE8v         <- nearestE8()          (zke8 examples/raw-nearest-e8.e8
 *                                                :13-141, ABI v1 conservative CPU
 *                                                provider)
 *   the level loop     <- residualLadder()     (e8_lattice_protocol.py:285-315)
 *   classOf            <- normClass()          (f2_8: 1 zero + 135 singular +
 *                                                120 root, e8_alphabet.py:110-120)
 *   hueRgb             <- hueRgb()             (same piecewise formula)
 *   the 8-lane pass    <- rootLabelAnalytic()  (the closed form the parity harness
 *                                                falsified against the 240-row
 *                                                table over 202,551 samples,
 *                                                226 of them exact shell ties)
 *
 * The colour equation is identical too, so the ONLY difference between the live
 * canvas and the pinned reference is arithmetic width: float32 on the GPU versus
 * float64 in the carrier and integer-exact code legs on the CPU. That difference
 * is measurable and the page measures it (the "GPU vs reference" delta in the pin
 * panel), because a disclosed gap is a spec and an undisclosed one is a bug.
 *
 * The level-scale ladder is uploaded from the CPU's frozen table, so the GPU
 * cannot invent its own decay. Scanlines and vignette are CSS overlays, deliberately
 * NOT in the shader, so nothing that is not math touches the compared bytes.
 */

import { LEVEL_SCALES, LADDER_MAX_LEVELS, BOUNDARY_EPS } from './e8-core.js';

const VS = `#version 300 es
in vec2 aPos;
void main() { gl_Position = vec4(aPos, 0.0, 1.0); }
`;

// ---------------------------------------------------------------------------
// Shared prelude: uniforms, the triangle carrier, the hue wheel.
// ---------------------------------------------------------------------------

const PRELUDE = `#version 300 es
precision highp float;
precision highp int;

uniform vec2  uRes;
uniform float uTime;
uniform vec4  uLanes[8];    // (fx, fy, phi, omega) per lane; phase in cycle fractions
uniform float uAmp;
uniform float uScales[16];  // the frozen level ladder, uploaded from the CPU table
uniform int   uLevels;
uniform int   uMinLevels;
uniform float uBoundaryEps;
uniform float uThresholdSq;   // threshold^2 * 8 -- the protocol's own stop test
uniform float uEpsDraw;       // filament radius: |advantage| <= this glows

out vec4 outColor;

// carrierAt(): triangle wave. No trigonometry anywhere in either demo, on purpose --
// sin() is implementation-approximated in both ECMA-262 and the GLSL spec, and an
// approximated function in the carrier would make the byte-pin engine-dependent.
float tri(float x) {
  float p = x - floor(x);
  return p < 0.5 ? 4.0 * p - 1.0 : 3.0 - 4.0 * p;
}

void carrier(vec2 q, out vec4 va, out vec4 vb) {
  va = vec4(0.0);
  vb = vec4(0.0);
  for (int k = 0; k < 8; k++) {
    vec4 L = uLanes[k];
    float val = uAmp * tri(L.x * q.x + L.y * q.y + L.z + uTime * L.w);
    if (k < 4) va[k] = val; else vb[k - 4] = val;
  }
}

float lane8(vec4 a, vec4 b, int k) { return k < 4 ? a[k] : b[k - 4]; }

// The house palette (e8-core.js VOID/ICE/GOLD), declared ONCE in the prelude so
// both fragment shaders paint the same colours: dark void, ice, gold.
const vec3 VOID3 = vec3(0.016, 0.020, 0.031);
const vec3 GOLD3 = vec3(0.788, 0.635, 0.153);
const vec3 ICE3  = vec3(0.0, 0.808, 0.820);

// hueRgb(): the same piecewise-linear wheel as the reference, arithmetic only.
vec3 hueRgb(float hue, float sat, float light) {
  float h = hue - floor(hue);
  float m2 = light <= 0.5 ? light * (1.0 + sat) : light + sat - light * sat;
  float m1 = 2.0 * light - m2;
  vec3 out3;
  for (int c = 0; c < 3; c++) {
    float hh = h + (c == 0 ? 0.3333333333333333 : (c == 1 ? 0.0 : -0.3333333333333333));
    if (hh < 0.0) hh += 1.0;
    if (hh > 1.0) hh -= 1.0;
    float v = hh < 0.16666666666666666 ? m1 + (m2 - m1) * 6.0 * hh
            : hh < 0.5                 ? m2
            : hh < 0.6666666666666666  ? m1 + (m2 - m1) * (0.6666666666666666 - hh) * 6.0
                                       : m1;
    out3[c] = v;
  }
  return out3;
}
`;

// There is deliberately NO vignette, scanline, bloom or tone curve in either
// shader: the CPU reference applies no post, so anything in the shader that is
// not the ported math would silently invalidate the GPU-vs-reference byte
// comparison. Vignette and scanlines are CSS overlays on the canvas element, for
// the same reason -- they are presentation, and the pin does not describe them.

// ---------------------------------------------------------------------------
// nearestE8, in the two-vec4 lane model.
// ---------------------------------------------------------------------------

const NEAREST = `
// roundEven(): half-to-even, i.e. C rint() under the default rounding mode and
// GLSL's own roundEven. Math.round-style half-UP is NOT what the estate kernel
// uses, so this is spelled out rather than left to the built-in.
float roundEven1(float x) {
  float f = floor(x);
  float d = x - f;
  if (d > 0.5) return f + 1.0;
  if (d < 0.5) return f;
  return mod(f, 2.0) == 0.0 ? f : f + 1.0;
}
vec4 roundEven4(vec4 x) {
  return vec4(roundEven1(x.x), roundEven1(x.y), roundEven1(x.z), roundEven1(x.w));
}

// nearestE8(): the conservative decode. oBoundary is the case the CPU provider
// kernel REFUSES with status 6 (|advantage| <= eps) and the torch leg silently
// resolves by keeping D8 -- the demo draws it instead of hiding it.
void nearestE8v(vec4 a, vec4 b, out vec4 oa, out vec4 ob, out float oBoundary, out float oCoset, out float oAdv) {
  vec4 z0a = roundEven4(a), z0b = roundEven4(b);
  vec4 sha = a - 0.5, shb = b - 0.5;
  vec4 z1a = roundEven4(sha), z1b = roundEven4(shb);

  int sum0 = int(z0a.x) + int(z0a.y) + int(z0a.z) + int(z0a.w)
           + int(z0b.x) + int(z0b.y) + int(z0b.z) + int(z0b.w);
  int sum1 = int(z1a.x) + int(z1a.y) + int(z1a.z) + int(z1a.w)
           + int(z1b.x) + int(z1b.y) + int(z1b.z) + int(z1b.w);
  bool odd0 = mod(float(sum0), 2.0) != 0.0;
  bool odd1 = mod(float(sum1), 2.0) != 0.0;

  // Strict greater-than: the first largest-residual lane wins, which is the
  // kernel's own scan order (law at raw-nearest-e8.e8:23-24, the comparisons at
  // :46-49 and :55-58).
  int best0 = 0, best1 = 0;
  float maxR0 = -1.0, maxR1 = -1.0;
  for (int lane = 0; lane < 8; lane++) {
    float xi = lane8(a, b, lane);
    float r0 = abs(xi - lane8(z0a, z0b, lane));
    if (r0 > maxR0) { maxR0 = r0; best0 = lane; }
    float r1 = abs(xi - 0.5 - lane8(z1a, z1b, lane));
    if (r1 > maxR1) { maxR1 = r1; best1 = lane; }
  }

  // Centered distance advantage.
  float adv = 0.0;
  for (int lane = 0; lane < 8; lane++) {
    float xi = lane8(a, b, lane);
    float ai = lane8(z0a, z0b, lane);
    float bi = lane8(z1a, z1b, lane);
    if (odd0 && lane == best0) ai += (xi - ai >= 0.0) ? 1.0 : -1.0;
    if (odd1 && lane == best1) bi += (xi - 0.5 - bi >= 0.0) ? 1.0 : -1.0;
    bi += 0.5;
    float delta = bi - ai;
    adv += delta * (2.0 * (xi - ai) - delta);
  }

  oAdv = adv;
  oBoundary = abs(adv) <= uBoundaryEps ? 1.0 : 0.0;
  bool choose1 = oBoundary > 0.5 ? false : adv > 0.0;   // an exact zero keeps D8
  oCoset = choose1 ? 1.0 : 0.0;

  oa = vec4(0.0); ob = vec4(0.0);
  for (int lane = 0; lane < 8; lane++) {
    float xi = lane8(a, b, lane);
    float val;
    if (choose1) {
      val = lane8(z1a, z1b, lane);
      if (odd1 && lane == best1) val += (xi - 0.5 - val >= 0.0) ? 1.0 : -1.0;
      val += 0.5;
    } else {
      val = lane8(z0a, z0b, lane);
      if (odd0 && lane == best0) val += (xi - val >= 0.0) ? 1.0 : -1.0;
      // The kernel canonicalizes an uncorrected -0.0 lane to +0.0 so its bytes
      // match what Torch materializes (raw-nearest-e8.e8:128-133). Value-inert
      // downstream here, but the shader is a transcription of that kernel, so it
      // carries the same line rather than a claim that it does.
      else if (odd0 && xi == 0.0 && val == 0.0) val = 0.0;
    }
    if (lane < 4) oa[lane] = val; else ob[lane - 4] = val;
  }
}

// normClass() on a doubled integer point: 0 zero | 1 root (q=1) | 2 singular
// (q=0) | 3 UNDECLARED. q = ||x||^2/2 mod 2 with w = 2x integral, so this is
// integer arithmetic on the GPU as well.
int classOf(vec4 a, vec4 b) {
  int s2 = 0;
  bool nonzero = false;
  for (int lane = 0; lane < 8; lane++) {
    float x = lane8(a, b, lane);
    int w = int(round(x * 2.0));
    if (w != 0) nonzero = true;
    s2 += w * w;
  }
  if (!nonzero) return 0;
  if (s2 % 8 != 0) return 3;
  // Integer remainder, NOT mod(): GLSL ES has no int overload of mod, so
  // mod(s2/8, 2) is a compile error (measured on Chromium/SwiftShader).
  // s2 % 8 == 0 here, so s2/8 is exact and q % 2 is the parity of q(x).
  int q = s2 / 8;
  return (q % 2 == 1) ? 1 : 2;
}
`;

// ---------------------------------------------------------------------------
// Demo 1 — the residual ladder.
// ---------------------------------------------------------------------------

const LADDER_FS = PRELUDE + NEAREST + `
void main() {
  // Reference convention: u = (px+0.5)/w*2-1, v = ((py+0.5)/h*2-1) with py
  // counted DOWN from the top. gl_FragCoord.y counts UP, so v is negated here --
  // without that the canvas is a mirror image of the pinned bytes.
  float u = gl_FragCoord.x / uRes.x * 2.0 - 1.0;
  float v = 1.0 - gl_FragCoord.y / uRes.y * 2.0;
  float aspect = uRes.x > uRes.y ? uRes.x / uRes.y : 1.0;
  float aspectY = uRes.y > uRes.x ? uRes.y / uRes.x : 1.0;
  vec2 q = vec2(u * aspect, v * aspectY);

  vec4 a, b;
  carrier(q, a, b);

  vec4 qa = vec4(0.0), qb = vec4(0.0);
  float filament = 0.0;
  vec3 col = VOID3;
  bool haveBase = false;

  for (int i = 0; i < 16; i++) {
    if (i >= uLevels) break;
    float s = uScales[i];
    vec4 sa = vec4((a.x - qa.x) / s, (a.y - qa.y) / s, (a.z - qa.z) / s, (a.w - qa.w) / s);
    vec4 sb = vec4((b.x - qb.x) / s, (b.y - qb.y) / s, (b.z - qb.z) / s, (b.w - qb.w) / s);
    vec4 ya, yb;
    float bound, coset, adv;
    nearestE8v(sa, sb, ya, yb, bound, coset, adv);
    // The neighbourhood of the refusal set, with the radius named by a uniform:
    // at the kernel's own 1e-4 only ~0.01% of a frame is inside it (measured by
    // the harness), so the glow is a ramp over |advantage| and the panel prints
    // the radius rather than implying it is the exact set.
    filament = max(filament, clamp(1.0 - abs(adv) / uEpsDraw, 0.0, 1.0) / float(i + 1));

    vec4 ca = ya * s, cb = yb * s;
    qa += ca; qb += cb;

    float rn = 0.0;
    for (int lane = 0; lane < 4; lane++) {
      float ra = a[lane] - qa[lane];
      float rb = b[lane] - qb[lane];
      rn += ra * ra + rb * rb;
    }

    // The ONE place the two paths are not provably identical: sqrt() is used
    // twice below, in the COLOUR leg. GLSL ES 3.00 leaves sqrt implementation-
    // approximated, while ECMA-262 requires Math.sqrt to be the correctly-rounded
    // value -- so a depth can round differently here than in the reference. It
    // cannot flip a DECISION: coset, level count and class are computed from
    // exactly-specified ops (floor, round, abs, integer arithmetic) alone. The
    // worst this can do is move a byte by about one level, which is why
    // browser-check's mirror identity is MEASURED on this driver rather than
    // proved from the source, and why the pin is the CPU frame, never the GPU's.
    int cls = classOf(ya, yb);
    if (i == 0) {
      // renderLadderFrame(): depth, class hue, saturation, light -- the same four
      // numbers, including the UNDECLARED key (0.83 / 1.0 / 0.5), which the
      // reference keeps loud instead of folding into the zero class.
      float depth = clamp(1.0 - sqrt(rn) * 0.35355339059327376, 0.0, 1.0);
      float hue = cls == 1 ? 0.11 : cls == 2 ? 0.49 : cls == 3 ? 0.83 : 0.62;
      float sat = cls == 0 ? 0.15 : cls == 1 ? 0.85 : cls == 3 ? 1.0 : 0.6;
      float light = cls == 3 ? 0.5 : 0.28 + 0.34 * depth;
      vec3 tint = hueRgb(hue + depth * 0.04, sat, light);
      // glow is fixed at 1.0 in the reference, so the (0.35 + 0.65 * glow) gain
      // is 1.0 -- written out so the two paths are visibly the same equation.
      col = VOID3 + tint * 1.0;
      haveBase = true;
    } else {
      float wgt = clamp(1.0 - sqrt(rn) * 4.0, 0.0, 1.0) / float(i + 1);
      vec3 key = cls == 1 ? GOLD3 : cls == 2 ? ICE3 : cls == 3 ? vec3(1.0, 0.0, 1.0) : VOID3;
      col += key * wgt * 0.55;
    }
    if (cls == 3) break;   // an undeclared class stops the loop loudly

    // residualLadder()'s stop test, verbatim: e8_lattice_protocol.py:310-315.
    // It sits AFTER the paint. The protocol pushes the level and only then
    // breaks, so the converged level IS part of the code list and the reference paints
    // it; testing before the paint dropped level 0 for every pixel that
    // converged on the first pass -- a systematic colour offset dressed up as
    // float32 noise (measured with tools/browser-check.mjs).
    if (i + 1 >= uMinLevels && rn < uThresholdSq) break;
  }
  if (!haveBase) col = VOID3;

  // The refused set, in gold: exactly where the conservative kernel says
  // "I will not choose", which is also the Voronoi cell edge.
  col += vec3(GOLD3.x * filament * 0.9, GOLD3.y * filament * 0.9, GOLD3.z * filament * 0.55);

  outColor = vec4(clamp(col, 0.0, 1.0), 1.0);
}
`;

// ---------------------------------------------------------------------------
// Demo 2 — the root shell.
// ---------------------------------------------------------------------------

const ROOT_FS = PRELUDE + `
int pairRank(int i, int j) { return 7 * i - (i * (i - 1)) / 2 + (j - i - 1); }

int rankEvenPopcount(int bits) {
  int rank = 0;
  int prefix = 0;
  for (int k = 7; k >= 0; k--) {
    if (((bits >> k) & 1) == 1) {
      rank += (k >= 1) ? (1 << (k - 1)) : (mod(float(prefix), 2.0) == 0.0 ? 1 : 0);
      prefix++;
    }
  }
  return rank;
}

int popcountEven(int bits) {
  int p = 0;
  for (int k = 0; k < 8; k++) if (((bits >> k) & 1) == 1) p++;
  return (p % 2 == 0) ? 1 : 0;   // int parity: % not mod(), same reason as classOf
}

void main() {
  float u = gl_FragCoord.x / uRes.x * 2.0 - 1.0;
  float v = 1.0 - gl_FragCoord.y / uRes.y * 2.0;
  float aspect = uRes.x > uRes.y ? uRes.x / uRes.y : 1.0;
  float aspectY = uRes.y > uRes.x ? uRes.y / uRes.x : 1.0;
  vec2 q = vec2(u * aspect, v * aspectY);

  vec4 av, bv;
  carrier(q, av, bv);

  float sum = 0.0;
  float mn = 1e30;
  float a1 = -1e30, a2 = -1e30;
  int bits = 0, negatives = 0;
  for (int k = 0; k < 8; k++) {
    float x = lane8(av, bv, k);
    float mk = abs(x);
    sum += mk;
    if (x < 0.0) { negatives++; bits |= (1 << k); }
    if (mk < mn) mn = mk;
    if (mk > a1) { a2 = a1; a1 = mk; } else if (mk > a2) a2 = mk;
  }
  bool odd = mod(float(negatives), 2.0) != 0.0;
  float type1 = a1 + a2;
  float type2 = (sum - (odd ? 2.0 * mn : 0.0)) * 0.5;

  // Lexicographically first maximizing pair (28 integer candidates).
  int bestPair = -1;
  for (int i = 0; i < 8; i++) {
    float mi = abs(lane8(av, bv, i));
    for (int j = i + 1; j < 8; j++) {
      float mj = abs(lane8(av, bv, j));
      if (mi + mj == type1) {
        float xi = lane8(av, bv, i);
        float xj = lane8(av, bv, j);
        int cand = pairRank(i, j) * 4 + (xi < 0.0 ? 2 : 0) + (xj < 0.0 ? 1 : 0);
        if (bestPair < 0 || cand < bestPair) bestPair = cand;
      }
    }
  }
  // Minimum-integer maximizing half-integral sign pattern.
  int bestBits = odd ? (1 << 30) : bits;
  if (odd) {
    for (int k = 0; k < 8; k++) {
      if (abs(lane8(av, bv, k)) != mn) continue;
      int cand = bits ^ (1 << k);
      if (popcountEven(cand) == 1 && cand < bestBits) bestBits = cand;
    }
  }
  int fam2 = 112 + rankEvenPopcount(bestBits);

  int index; int family; float value;
  if (type1 > type2)       { index = bestPair;           family = 1; value = type1; }
  else if (type2 > type1)  { index = fam2;               family = 2; value = type2; }
  else                     { index = min(bestPair, fam2); family = 0; value = type1; }

  float norm = family == 2 ? uAmp : 2.0 * uAmp;
  float gval = clamp(value / norm, 0.0, 1.0);
  float hue = float(index) / 240.0 + (family == 2 ? 0.5 / 240.0 : 0.0);
  vec3 rgb = hueRgb(hue, 0.72 - 0.2 * gval, 0.10 + 0.42 * gval);
  vec3 col = VOID3 + rgb;

  // The two structural seams, both derived from the same |v| statistics:
  //   family tie  -> the two shells have equal claim (the |t1-|t2|| == 0 case)
  //   chamber wall-> the top two lanes tie, so the maximizing pair changes hands
  float seam = clamp(1.0 - abs(type1 - type2) / (0.06 * uAmp * 8.0), 0.0, 1.0);
  float wall = clamp(1.0 - (a1 - a2) / (0.06 * uAmp * 4.0), 0.0, 1.0);
  col += vec3(GOLD3.x * seam * 0.85 + ICE3.x * wall * 0.5,
              GOLD3.y * seam * 0.85 + ICE3.y * wall * 0.5,
              GOLD3.z * seam * 0.45 + ICE3.z * wall * 0.65);

  outColor = vec4(clamp(col, 0.0, 1.0), 1.0);
}
`;

const SHADERS = { ladder: LADDER_FS, root: ROOT_FS };

// ---------------------------------------------------------------------------
// GL plumbing
// ---------------------------------------------------------------------------

/**
 * A typed refusal, never a blank canvas. The estate's absence law
 * (e8_period_codec.py:47-58) says a null must not be coalesced into a zero; the
 * same law applied to a browser feature says a missing WebGL2 context must name
 * itself, because "nothing drew" and "the platform refused" are different facts
 * and only one of them is debuggable.
 */
export function createRenderer(canvas, kind) {
  const gl = canvas.getContext('webgl2', {
    antialias: false,
    depth: false,
    stencil: false,
    alpha: false,
    premultipliedAlpha: false,
    preserveDrawingBuffer: true,
    powerPreference: 'high-performance',
  });
  if (!gl) {
    return refusal('webgl2_context_absent',
      'canvas.getContext("webgl2") returned null. The CPU reference panel, the '
      + 'byte-pin and the seed law are unaffected -- only the live canvas needs a GPU.');
  }
  const src = SHADERS[kind];
  if (!src) throw new Error(`gl-render: no shader for kind "${kind}"`);
  const program = buildProgram(gl, VS, src);
  if (!program) {
    return refusal('shader_compile_failed',
      `The ${kind} fragment shader did not compile on this driver. See the console `
      + 'for the numbered source dump and the driver log.');
  }

  const vao = gl.createVertexArray();
  gl.bindVertexArray(vao);
  const buf = gl.createBuffer();
  gl.bindBuffer(gl.ARRAY_BUFFER, buf);
  // One oversized triangle covering the viewport: no index buffer, no clear.
  gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 3, -1, -1, 3]), gl.STATIC_DRAW);
  const loc = gl.getAttribLocation(program, 'aPos');
  gl.enableVertexAttribArray(loc);
  gl.vertexAttribPointer(loc, 2, gl.FLOAT, false, 0, 0);
  gl.useProgram(program);

  const u = (n) => gl.getUniformLocation(program, n);
  const U = {
    res: u('uRes'), time: u('uTime'), lanes: u('uLanes[0]'), amp: u('uAmp'),
    scales: u('uScales[0]'), levels: u('uLevels'), minLevels: u('uMinLevels'),
    boundaryEps: u('uBoundaryEps'), thresholdSq: u('uThresholdSq'), epsDraw: u('uEpsDraw'),
  };

  const scales = new Float32Array(LADDER_MAX_LEVELS);
  for (let i = 0; i < LADDER_MAX_LEVELS; i++) scales[i] = LEVEL_SCALES[i];
  gl.uniform1fv(U.scales, scales);

  let w = 1, h = 1;
  const flat = new Float32Array(32);

  const api = {
    ok: true,
    refusal: null,
    kind,
    gl,
    size: () => ({ w, h }),
    resize(cssW, cssH, maxDpr = 2) {
      const dpr = Math.min(window.devicePixelRatio || 1, maxDpr);
      w = Math.max(1, Math.round(cssW * dpr));
      h = Math.max(1, Math.round(cssH * dpr));
      if (canvas.width !== w || canvas.height !== h) {
        canvas.width = w;
        canvas.height = h;
      }
      gl.viewport(0, 0, w, h);
      return { w, h, dpr };
    },
    draw(coef, t, state = {}) {
      gl.viewport(0, 0, w, h);
      gl.uniform2f(U.res, w, h);
      gl.uniform1f(U.time, t);
      gl.uniform1f(U.amp, coef.amplitude);
      gl.uniform1i(U.levels, state.levels ?? 4);
      gl.uniform1i(U.minLevels, state.minLevels ?? 1);
      gl.uniform1f(U.boundaryEps, state.boundaryEps ?? BOUNDARY_EPS);
      const thr = state.threshold ?? 1e-3;
      gl.uniform1f(U.thresholdSq, thr * thr * 8.0);
      gl.uniform1f(U.epsDraw, state.epsDraw ?? 0.02);
      for (let k = 0; k < 8; k++) {
        const L = coef.lanes[k];
        flat[k * 4] = L.fx;
        flat[k * 4 + 1] = L.fy;
        flat[k * 4 + 2] = L.phi;
        flat[k * 4 + 3] = L.omega;
      }
      gl.uniform4fv(U.lanes, flat);
      gl.drawArrays(gl.TRIANGLES, 0, 3);
    },
    /** RGBA bytes of the framebuffer, for the GPU-vs-reference measurement. */
    readPixels() {
      const out = new Uint8Array(w * h * 4);
      gl.readPixels(0, 0, w, h, gl.RGBA, gl.UNSIGNED_BYTE, out);
      return { w, h, bytes: out };
    },
    dispose() {
      gl.deleteProgram(program);
      gl.deleteBuffer(buf);
      gl.deleteVertexArray(vao);
    },
  };
  return api;
}

function refusal(code, detail) {
  return {
    ok: false,
    refusal: code,
    detail,
    kind: null,
    gl: null,
    size: () => ({ w: 0, h: 0 }),
    resize() { return { w: 0, h: 0, dpr: 1 }; },
    draw() {},
    readPixels() { return null; },
    dispose() {},
  };
}

function buildProgram(gl, vsSrc, fsSrc) {
  const compile = (type, source, label) => {
    const s = gl.createShader(type);
    gl.shaderSource(s, source);
    gl.compileShader(s);
    if (!gl.getShaderParameter(s, gl.COMPILE_STATUS)) {
      const log = gl.getShaderInfoLog(s) || '(no log)';
      console.error(`[${label}] compile failed:\n${log}`);
      console.error(source.split('\n').map((l, i) => `${String(i + 1).padStart(3, ' ')}: ${l}`).join('\n'));
      gl.deleteShader(s);
      return null;
    }
    return s;
  };
  const vs = compile(gl.VERTEX_SHADER, vsSrc, 'vertex');
  const fs = compile(gl.FRAGMENT_SHADER, fsSrc, 'fragment');
  if (!vs || !fs) return null;
  const p = gl.createProgram();
  gl.attachShader(p, vs);
  gl.attachShader(p, fs);
  gl.linkProgram(p);
  if (!gl.getProgramParameter(p, gl.LINK_STATUS)) {
    console.error('[link]', gl.getProgramInfoLog(p));
    return null;
  }
  gl.deleteShader(vs);
  gl.deleteShader(fs);
  return p;
}

export { SHADERS };
