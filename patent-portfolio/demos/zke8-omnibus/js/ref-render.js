/**
 * ref-render.js — the CPU reference renderer. Canonical, engine-independent.
 *
 * This is the module the byte-pin hashes. Its only imports are e8-core.js and,
 * for the optional estate seed law, seed-stream.js (which itself imports only
 * sha256.js) — and it uses ONLY operations ECMA-262 exactly specifies (+ - * / ,
 * Math.abs, Math.floor, Math.round, Math.max/min, Math.sqrt, Math.fround) — no
 * Math.sin, no Math.pow, no Math.random. The carrier is a triangle wave for the
 * same reason (see e8-core.js "The 8-lane carrier field"). So a digest computed
 * here is a property of the seed, the frame number and the named seed law, not of
 * the JS engine, which is what makes "same seed -> same rendered output" a
 * checkable claim. The engine half of that is not taken on trust:
 * tools/browser-check.mjs requires the in-browser SHA-256 of the same frame to
 * EQUAL the node-pinned digest.
 *
 * The GPU path in gl-render.js draws the same two functions; the inset this file
 * paints is the certificate, and it is the thing whose SHA-256 is quoted.
 */

import {
  carrierAt,
  fieldCoefficients,
  residualLadder,
  rootLabelAnalytic,
  doubledCoords,
  normClass,
  nearestE8,
  LEVEL_SCALES,
  E8_COVERING_RADIUS,
  VOID,
  ICE,
  GOLD,
} from './e8-core.js';
import { fieldCoefficientsEstate } from './seed-stream.js';

const clamp01 = (x) => (x < 0 ? 0 : x > 1 ? 1 : x);
const byte = (x) => Math.round(clamp01(x) * 255);

/** The diagnostic key for an UNDECLARED f2_8 class (Σw² not divisible by 8, so
 *  the point is not in the lattice at all). Loud on purpose. The shader uses
 *  vec3(1,0,1) for the same case. It should never appear; if it does, the demo
 *  is showing a real defect instead of painting over it. */
const MAGENTA = [1.0, 0.0, 1.0];

/** Pixel -> carrier domain. Aspect-corrected, origin centred, one unit of `v`
 *  equals one unit of `u` on the shorter axis. */
export function uvOf(px, py, w, h, out) {
  const aspect = w > h ? w / h : 1;
  const aspectY = h > w ? h / w : 1;
  out[0] = ((px + 0.5) / w * 2 - 1) * aspect;
  out[1] = ((py + 0.5) / h * 2 - 1) * aspectY;
  return out;
}

// ---------------------------------------------------------------------------
// Colour keys. Hues come from a piecewise-linear wheel (no trig, no pow), then
// every demo composes inside the house palette: dark void, ice, gold.
// ---------------------------------------------------------------------------

/** hue in [0,1) -> linear RGB, pure arithmetic. */
export function hueRgb(hue, sat, light, out) {
  const h = hue - Math.floor(hue);
  const m2 = light <= 0.5 ? light * (1 + sat) : light + sat - light * sat;
  const m1 = 2 * light - m2;
  for (let c = 0; c < 3; c++) {
    let hh = h + (c === 0 ? 1 / 3 : c === 1 ? 0 : -1 / 3);
    if (hh < 0) hh += 1;
    if (hh > 1) hh -= 1;
    out[c] = hh < 1 / 6 ? m1 + (m2 - m1) * 6 * hh
      : hh < 1 / 2 ? m2
        : hh < 2 / 3 ? m1 + (m2 - m1) * (2 / 3 - hh) * 6
          : m1;
  }
  return out;
}

// ---------------------------------------------------------------------------
// TECHNIQUE 1 — the residual ladder. Nested E8 Voronoi cells at sqrt(240)
// spacing ratios, drawn as the codec that produces them.
// ---------------------------------------------------------------------------

/**
 * Paint one frame of the residual-E8 ladder into `target` (RGBA, w*h*4).
 *
 * What each channel of the visual is a picture OF:
 *   cell hue      -> the f2_8 class of the level-0 codeword: 1 zero class,
 *                    120 root (q=1) classes, 135 singular (q=0) classes
 *                    (e8_alphabet.py:110-120) — the lattice's own quotient, not
 *                    a palette index.
 *   cell value    -> 1 - ||residual|| / covering radius: how deep inside a cell
 *                    the carrier landed. sqrt(2) is the E8 covering radius
 *                    (e8_period_codec.py:189, declared bound :41).
 *   filament      -> the exact-boundary set, i.e. where the estate's conservative
 *                    CPU provider kernel REFUSES with status 6
 *                    (raw-nearest-e8.e8:100-102). The demo draws the refusal.
 *   nesting ratio -> level i cells are sqrt(240)x finer than level i-1
 *                    (e8_lattice_protocol.py:180).
 */
export function renderLadderFrame(w, h, t, coef, opts, target) {
  const levels = opts.levels ?? 4;
  const threshold = opts.threshold ?? 1e-3;
  const glow = opts.glow ?? 1.0;   // default 1.0 matches the shader, which has no glow term
  const uv = [0, 0];
  const v8 = new Float64Array(8);
  const cellTint = [0, 0, 0];

  for (let py = 0; py < h; py++) {
    for (let px = 0; px < w; px++) {
      if (opts.only && !opts.only.has(py * w + px)) continue;
      uvOf(px, py, w, h, uv);
      (opts.carrierFn || carrierAt)(uv[0], uv[1], t, coef, v8);
      // opts.simulateF32 is the harness's control experiment, not a render mode
      // the pages use: round the carrier to float32 before the ladder, which is
      // the one place the GPU path genuinely differs from this reference (the
      // shader's carrier is float32 by construction). If that alone moves the
      // picture, then the GPU-vs-reference tail is the codec's discontinuity, not
      // a transcription error -- and the harness says which it is, with a count.
      if (opts.simulateF32) for (let k = 0; k < 8; k++) v8[k] = Math.fround(v8[k]);
      const L = residualLadder(v8, { maxLevels: levels, threshold });
      const n = L.codes.length;

      // Depth inside the level-0 cell, scaled by the covering radius.
      const depth = n > 0 ? clamp01(1 - Math.sqrt(L.residualNorms[0]) / (E8_COVERING_RADIUS * 2)) : 0;

      // Class of the level-0 codeWORD (the lattice point, not the scaled
      // contribution) -> hue key. contribs[i] is multiplied by the level scale
      // and is therefore not a lattice point at all; doubling it yields non-
      // integers and no f2_8 class. points[i] is. This distinction is what the
      // first draft of this line got wrong.
      const cls = n > 0 ? normClass(doubledCoords(L.points[0])) : 'zero';
      // 'undeclared' is a separate key and loud (magenta), NOT folded into the
      // zero class: coalescing an absence into a nearby value is the bug the
      // estate's own absence law names (e8_period_codec.py:47-58).
      const hue = cls === 'root' ? 0.11 : cls === 'singular' ? 0.49 : cls === 'zero' ? 0.62 : 0.83;
      const sat = cls === 'zero' ? 0.15 : cls === 'root' ? 0.85 : cls === 'singular' ? 0.6 : 1.0;
      const light = cls === 'undeclared' ? 0.5 : 0.28 + 0.34 * depth;
      hueRgb(hue + depth * 0.04, sat, light, cellTint);

      let r = VOID[0] + cellTint[0] * (0.35 + 0.65 * glow);
      let g = VOID[1] + cellTint[1] * (0.35 + 0.65 * glow);
      let b = VOID[2] + cellTint[2] * (0.35 + 0.65 * glow);

      // Finer levels: each contributes a proportional line-work weight.
      for (let i = 1; i < n; i++) {
        const rn = Math.sqrt(L.residualNorms[i]);
        const wgt = clamp01(1 - rn * 4) / (i + 1);
        if (wgt <= 0) continue;
        const c = normClass(doubledCoords(L.points[i]));
        const key = c === 'root' ? GOLD : c === 'singular' ? ICE : c === 'undeclared' ? MAGENTA : VOID;
        r += key[0] * wgt * 0.55;
        g += key[1] * wgt * 0.55;
        b += key[2] * wgt * 0.55;
      }

      // The refused set and its NEIGHBOURHOOD. The kernel's own radius is 1e-4
      // (raw-nearest-e8.e8:100-102) and at that radius only ~0.01% of a canonical
      // frame is inside the set (measured: 2 of 16384 pixels, see the harness
      // output), so the glow is a ramp over |advantage| with a NAMED radius, not
      // a claim that you are looking at the exact refusal set. The shader uses
      // this identical expression (gl-render.js, uEpsDraw).
      const epsDraw = opts.epsDraw ?? 0.02;
      let filament = 0;
      for (let i = 0; i < n; i++) {
        const a = Math.abs(L.advantages[i]);
        filament = Math.max(filament, clamp01(1 - a / epsDraw) / (i + 1));
      }
      if (L.stops === 'boundary') filament = 1;
      r += GOLD[0] * filament * 0.9;
      g += GOLD[1] * filament * 0.9;
      b += GOLD[2] * filament * 0.55;

      const o = (py * w + px) * 4;
      target[o] = byte(r);
      target[o + 1] = byte(g);
      target[o + 2] = byte(b);
      target[o + 3] = 255;
    }
  }
  return target;
}

// ---------------------------------------------------------------------------
// TECHNIQUE 2 — the root shell. 240 direction codes, the two shell families,
// and the Weyl-chamber walls where the argmax changes hands.
// ---------------------------------------------------------------------------

/**
 * Paint one frame of the E8 root-shell direction field into `target`.
 *
 *   hue      -> the estate's root index 0..239 (the analytic closed form,
 *                verified against the 240-row table by the harness), folded so
 *                neighbouring regions share a hue lane.
 *   value    -> max over the shell, normalised by the largest value the shell can
 *                take on an 8-lane carrier of amplitude A (which is A*sqrt(2) for
 *                the half-shell and 2A for the integer shell).
 *   seam     -> family 1 (112 rows, (+-1,+-1,0^6)) vs family 2 (128 rows,
 *                (+-1/2)^8, even minus count) — the shape split documented at
 *                dimensions.py:238-241. Drawn as the bright fold line.
 *   walls    -> where the two largest lanes nearly tie (a1 ~ a2), i.e. the
 *                chamber walls of the root-system tessellation.
 */
export function renderRootFrame(w, h, t, coef, opts, target) {
  const amplitude = coef.amplitude;
  const wallWidth = opts.wallWidth ?? 0.06;
  const uv = [0, 0];
  const v8 = new Float64Array(8);
  const rgb = [0, 0, 0];

  for (let py = 0; py < h; py++) {
    for (let px = 0; px < w; px++) {
      if (opts.only && !opts.only.has(py * w + px)) continue;
      uvOf(px, py, w, h, uv);
      (opts.carrierFn || carrierAt)(uv[0], uv[1], t, coef, v8);
      if (opts.simulateF32) for (let k = 0; k < 8; k++) v8[k] = Math.fround(v8[k]);
      if (opts.perturb) { const { eps, delta } = opts.perturb; for (let k = 0; k < 8; k++) v8[k] += eps * delta[k]; }
      const lab = rootLabelAnalytic(v8);

      let a1 = -Infinity, a2 = -Infinity, sum = 0, min = Infinity, negatives = 0;
      for (let k = 0; k < 8; k++) {
        const m = Math.abs(v8[k]);
        sum += m;
        if (v8[k] < 0) negatives++;
        if (m < min) min = m;
        if (m > a1) { a2 = a1; a1 = m; } else if (m > a2) a2 = m;
      }
      const norm = lab.family === 2 ? amplitude : 2 * amplitude;
      const value = clamp01(lab.value / norm);
      // 240 bands, so the hue IS the estate's root index, mapped to the wheel.
      const hue = (lab.index % 240) / 240 + (lab.family === 2 ? 0.5 / 240 : 0);
      hueRgb(hue, 0.72 - 0.2 * value, 0.1 + 0.42 * value, rgb);

      let r = VOID[0] + rgb[0];
      let g = VOID[1] + rgb[1];
      let b = VOID[2] + rgb[2];

      // Family seam: |type1 - type2| small, i.e. the two shapes of the root
      // system ((+-1,+-1,0^6) and (+-1/2)^8) have an equal claim. Byte-identical
      // expression to the shader's (gl-render.js ROOT_FS), not a look-alike.
      const type1 = a1 + a2;
      const type2 = (sum - (negatives % 2 === 0 ? 0 : 2 * min)) * 0.5;
      const seam = clamp01(1 - Math.abs(type1 - type2) / (wallWidth * amplitude * 8));
      // Chamber wall: the two largest lanes tie, so the argmax pair changes.
      const wall = clamp01(1 - (a1 - a2) / (wallWidth * amplitude * 4));

      r += GOLD[0] * seam * 0.85 + ICE[0] * wall * 0.5;
      g += GOLD[1] * seam * 0.85 + ICE[1] * wall * 0.5;
      b += GOLD[2] * seam * 0.45 + ICE[2] * wall * 0.65;

      const o = (py * w + px) * 4;
      target[o] = byte(r);
      target[o + 1] = byte(g);
      target[o + 2] = byte(b);
      target[o + 3] = 255;
    }
  }
  return target;
}

// ---------------------------------------------------------------------------
// Frame driver shared by both demos: seed -> coefficients -> frame.
// ---------------------------------------------------------------------------

/**
 * The ONE place a seed law is chosen. `field.law` is 'house' (Xorshift128+ over
 * the FNV-1a seed hash, the art repo's convention and every pre-existing pin) or
 * 'estate' (SHA-256 counter mode, js/seed-stream.js, a bit-exact port of kagami
 * core omni/prng.py:63-104 -- see tools/estate-seed-vectors.json for the golden
 * bytes the port is graded against). Both laws feed the SAME lane mapping,
 * e8-core.js:fieldFromUniform, so the pictures differ only in where their uniforms
 * came from, and a reader can attribute a frame to a generator by one field.
 */
export function carrier(seed, fieldOpts = {}) {
  const law = fieldOpts.law ?? 'house';
  if (law === 'estate') return fieldCoefficientsEstate(seed, fieldOpts);
  if (law === 'house') return fieldCoefficients(seed, fieldOpts);
  throw new Error(`unknown seed law ${JSON.stringify(law)} (expected 'house' or 'estate')`);
}

export function makeScene(kind, seed, opts = {}) {
  const coef = carrier(seed, opts.field ?? {});
  const render = kind === 'root' ? renderRootFrame : renderLadderFrame;
  return {
    kind,
    seed: String(seed),
    coef,
    render: (w, h, t, o, target) => render(w, h, t, coef, o, target),
    alloc: (w, h) => new Uint8ClampedArray(w * h * 4),
  };
}

/** The certificate: a small canonical frame whose bytes are what gets hashed.
 *  128x128 is chosen so the harness finishes fast and so the inset is legible
 *  blown up beside the live canvas. */
export function certificate(seed, frameIndex, opts = {}) {
  const size = opts.size ?? 128;
  const scene = makeScene(opts.kind ?? 'ladder', seed, opts);
  const buf = scene.alloc(size, size);
  scene.render(size, size, frameIndex, opts.render ?? {}, buf);
  return { size, bytes: buf, frameIndex };
}

// ---------------------------------------------------------------------------
// THE SHADER MIRROR — the leg that finally names the GPU/reference delta.
//
// Three probes failed before this one, and each failure is why the next is
// shaped as it is:
//
//  1. Sort the disagreement by |coset advantage|. FALSE: disagree median 2.78e-1
//     vs the frame's 3.32e-1 (ratio 0.84 — distributed like the frame). The ladder
//     has four step functions, not one: the coset sign, the per-lane roundEven
//     boundaries, the bestIndex argmax tie, and the protocol's stop test. Distance
//     to one says nothing about another.
//  2. Perturb the carrier by eps*delta in one fixed direction. 54% coverage. Wrong
//     instrument: float32 does not add a vector along `delta`, it rounds each lane
//     in whatever direction its own bits say.
//  3. Round the carrier once to float32 (`Math.fround`). Predicted 3 of 48. Right
//     mechanism, wrong MAGNITUDE: fround lands within 0.5 ulp of the exact value,
//     while the shader's carrier is a float32 expression tree (eight products,
//     seven sums, a floor, a compare) several ulps away, from float32-uploaded
//     coefficients. And a carrier error of 1 ulp is AMPLIFIED by the ladder: level
//     3 divides by s_3 = 2/sqrt(240)^3 = 5.4e-4, so 1.2e-7 of absolute error
//     becomes ~2e-4 in that level's coordinates — exactly the size of the
//     |advantage| values the disagreeing pixels turned out to have.
//
// So stop modelling the error and REPRODUCE the arithmetic: re-evaluate the
// fragment shader's own carrier expression in IEEE float32, op by op, with the
// uniforms' widths (gl.uniform4fv uploads float32, so the lane coefficients are
// fround(coef)), then run it through the unchanged reference ladder (which is
// already float32 op-by-op, because e8_lattice_protocol.py:264-295 is). The claim
// is then not "the two paths are within tolerance" but "a CPU program predicts
// every byte the GPU produces" — measured at 48/48 disagreeing pixels, worst
// residual 0 levels, on the canonical frame. The leftover difference against the
// float64 reference is the shader's float32 colour leg (hue wheel, filament ramp,
// byte quantisation), which moves a byte by about one level; that is what the
// <=2-level residual in tools/disagreement-triage.mjs is scoring.
//
// Fusion is reported, not assumed. GLSL does not pin whether a*b+c contracts into
// one rounding, so both mirrors are measured: `nofma` rounds every multiply and
// every add, `fma` fuses. On this device `nofma` reproduced all 48 pixels exactly
// and `fma` only 26, of which 21 are pixels insensitive to fusion. A port that
// asserted "float32 is enough" without naming the fusion discipline would be
// guessing.
// ---------------------------------------------------------------------------

const f32 = Math.fround;

/** A float32 re-evaluation of gl-render.js's `carrier()`. Same signature as
 *  carrierAt, so a renderer takes it through opts.carrierFn.
 *  At a power-of-two width the pixel->uv map needs no mirroring: (px+0.5)/128*2-1
 *  is exact in binary (px+0.5 fits in 8 bits, 128 is a power of two), so float32
 *  and float64 agree on the INPUT and only the expression tree can differ. */
export function mirrorCarrier(coef, mode = 'nofma') {
  const lanes = coef.lanes.map((L) => [f32(L.fx), f32(L.fy), f32(L.phi), f32(L.omega)]);
  const amp = f32(coef.amplitude);
  return (u, v, t, _c, out) => {
    const uu = f32(u), vv = f32(v), tt = f32(t);
    for (let k = 0; k < 8; k++) {
      const [fx, fy, phi, om] = lanes[k];
      let arg;
      if (mode === 'fma') {
        // a float32 product fits exactly in a float64, so f64 a*b + c rounded once
        // is the fused rounding (double-rounding would need >53 significant bits).
        arg = f32(f32(f32(fx * uu + fy * vv) + phi) + tt * om);
      } else {
        const a = f32(fx * uu), b = f32(fy * vv);
        const c = f32(f32(a + b) + phi);
        arg = f32(c + f32(tt * om));
      }
      const p = f32(arg - Math.floor(arg));       // floor of a finite float32 is exact
      const w = f32(4.0 * p);                      // 4 is a power of two: exact scale
      const val = p < 0.5 ? f32(w - 1.0) : f32(3.0 - w);
      out[k] = f32(amp * val);
    }
    return out;
  };
}

/** Rank statistics over a Float64Array, by index sort (fine at 16k). */
export function quantiles(values, qs) {
  const a = Array.from(values).sort((x, y) => x - y);
  return qs.map((q) => a[Math.min(a.length - 1, Math.max(0, Math.round(q * (a.length - 1))))]);
}

/** A second, independent path to the same number: the set the conservative CPU
 *  provider kernel REFUSES, counted at the kernel's own tolerance and at wider
 *  ones. Measured on the reference frame, not asserted: on the triangle carrier
 *  the exact-boundary set is REAL but THIN -- 2 of 16384 pixels at the kernel's
 *  1e-4 (0.01%), 338 at 1e-2 (2.06%) -- and the minimum |advantage| observed in a
 *  canonical frame is 3.457e-5. So the filaments draw the NEIGHBOURHOOD of the
 *  refusal set, in an intensity ramp that names its own radius, and the demo says
 *  so on screen rather than implying the exact set is what you are seeing. */
export function boundaryCount(seed, samples = 4096, opts = {}) {
  const scene = makeScene(opts.kind ?? 'ladder', seed, opts);
  const v8 = new Float64Array(8);
  const cols = Math.round(Math.sqrt(samples));
  const rows = Math.ceil(samples / cols);
  const eps = opts.eps ?? [1e-4, 1e-3, 1e-2, 1e-1];
  const hits = eps.map(() => 0);
  let minAbs = Infinity;
  let exactZero = 0;
  let counted = 0;
  for (let i = 0; i < samples; i++) {
    const u = (i % cols + 0.5) / cols * 2 - 1;
    const vv = 1 - (Math.floor(i / cols) + 0.5) / rows * 2 - 1;
    carrierAt(u, vv, opts.frame ?? 0, scene.coef, v8);
    const h = nearestE8(v8, { tieBreak: 'refuse' });
    counted++;
    const a = Math.abs(h.status === 6 ? h.advantage : h.advantage ?? 0);
    if (a === 0) exactZero++;
    if (a < minAbs) minAbs = a;
    for (let j = 0; j < eps.length; j++) if (a <= eps[j]) hits[j]++;
  }
  return { samples: counted, eps, hits, exactZero, minAbs, cols, rows };
}
