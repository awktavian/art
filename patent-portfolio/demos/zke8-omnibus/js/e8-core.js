/**
 * e8-core.js — the estate's E8 machinery, ported to the browser verbatim.
 *
 * THIS MODULE IS PURE: no DOM, no WebGL, no imports. It is the canonical CPU
 * reference for both demos in this directory and it is imported directly by
 * `tools/determinism-harness.mjs` under node. The GPU path re-implements the
 * SAME formulas in GLSL; where the GPU cannot carry the reference exactly, the
 * reference in this file is the truth and the inset rendered from it is what
 * the byte-pin hashes. See README.md "Determinism and disclosure".
 *
 * Provenance of every number here (kagami/zke8 are READ-ONLY sources):
 *
 *  - The 240-root enumeration order is `generate_e8_roots`,
 *    kagami packages/kagami_math/dimensions.py:233-291: type 1 = (±1,±1,0^6)
 *    over lexicographic pairs i<j and sign pairs [1,-1]x[1,-1] (112 rows), then
 *    type 2 = (±1/2)^8 over `bits` 0..255 with even popcount, root[k] = -0.5 iff
 *    bit k is set (128 rows). Row order MATTERS: it is what makes a root INDEX
 *    mean the same thing here as it does in the estate codec.
 *  - root_index = argmax <root, v>, deterministic FIRST-OCCURRENCE tie-break,
 *    zero vector -> index 0 by convention:
 *    kagami packages/kagami/core/digest/e8_period_codec.py:696-719 (and the
 *    exact-integer doubled table leg at :610-613, :715).
 *  - nearest_e8 (Conway-Sloane E8 = D8 u (D8 + 1/2*1)) with the estate's own
 *    float guards, strict-greater-than residual tie rule, centered distance
 *    ADVANTAGE coset comparison, and its typed exact-boundary refusal:
 *    zke8 examples/raw-nearest-e8.e8:13-141 (ABI v1 conservative CPU provider;
 *    its caller law at :3 — any nonzero status makes the caller discard output).
 *  - Residual ladder: scale_i = clamp(initial_scale / decay^i, 1e-6) with
 *    initial_scale = 2.0, decay = sqrt(240), max_levels = 16, min_levels = 1,
 *    adaptive stop at ||r||^2 < threshold^2 * 8:
 *    kagami packages/kagami_math/e8_lattice_protocol.py:175-182 (config),
 *    :224-228 (level scales), :285-315 (the quantize/subtract/stop loop),
 *    :349-359 (decode = sum of half-step codes times level scale).
 *  - The codec's own stop slack sqrt(8)*1e-6: e8_period_codec.py:192, and its
 *    exact-domain bound MAX_EXACT_COORD = 4_000_000: e8_period_codec.py:186.
 *  - f2_8 = E8/2E8 class algebra: ALPHA_ORDER 256, ROOT_COUNT 240,
 *    ROOT_CLASS_COUNT 120, SINGULAR_CLASS_COUNT 135, zero class 1, Arf 0, and
 *    the q(x) = ||x||^2/2 mod 2 refinement:
 *    kagami packages/kagami_math/e8_alphabet.py:105-121 and :12-45 (declared
 *    constants; q is canonical on even lattices).
 *  - The seeded PRNG is the house mechanism (Xorshift128+ over an FNV-1a
 *    4-lane seed hash), ported from art gen/lib/prng.js:12-62.
 *
 * WHAT THIS IS NOT: this is not a certificate. The estate's own disclosure is
 * inherited: the Grails/Perception/E8Decoder.lean row behind exact nearest-point
 * semantics is EXPIRED as measured 2026-10-01 and the kernel cert is PENDING
 * (e8_period_codec.py:8-13, e8_lattice_quantizer.py:139-146), so nothing here
 * claims IEEE-exact or certified arithmetic. It claims BYTE-EXACT REPRODUCIBILITY
 * of a stated float64 algorithm, which is a different and much smaller thing.
 */

// ---------------------------------------------------------------------------
// Declared constants (values, not display copies)
// ---------------------------------------------------------------------------

export const ROOT_COUNT = 240;
export const ALPHA_ORDER = 256;
export const ROOT_CLASS_COUNT = 120;
export const SINGULAR_CLASS_COUNT = 135;

export const E8_COVERING_RADIUS = Math.SQRT2; // sqrt(2), Conway-Sloane
export const MAX_EXACT_COORD = 4_000_000;

/** decay = sqrt(240) — the kissing number's square root is the level ladder's
 *  geometric ratio. e8_lattice_protocol.py:180. */
export const LADDER_DECAY = Math.sqrt(240);
export const LADDER_INITIAL_SCALE = 2.0;
export const LADDER_MAX_LEVELS = 16;
export const LADDER_MIN_LEVELS = 1;
/** stop when mean residual norm is small; the protocol squares the threshold and
 *  multiplies by 8 coordinates (e8_lattice_protocol.py:283), i.e. ||r|| < sqrt(8)*thr. */
export const LADDER_RESIDUAL_THRESHOLD = 1e-3;
export const SCALE_CLAMP_MIN = 1e-6; // :286 `.clamp(min=1e-6)`

/** The exact-boundary guard carried over from the CPU provider kernel:
 *  |advantage| <= 1e-4 is REFUSED there (raw-nearest-e8.e8:100-102, status 6).
 *  Here it is not an error — it is the Voronoi cell boundary, and the demos
 *  DRAW it. */
export const BOUNDARY_EPS = 1e-4;

/** fround: one IEEE-754 binary32 rounding of a JS (binary64) value. Used to run
 *  the ladder in the source's own precision class instead of a finer one, and
 *  to keep the CPU reference and the GLSL path in the same arithmetic. */
const f32 = Math.fround;

// ---------------------------------------------------------------------------
// Round-half-to-even (C `rint` under the default mode, GLSL `roundEven`).
// JS Math.round is half-UP, which is NOT what the estate kernel uses, so this
// helper exists and every use is deliberate.
// ---------------------------------------------------------------------------

export function roundEven(x) {
  const f = Math.floor(x);
  const d = x - f;
  if (d > 0.5) return f + 1;
  if (d < 0.5) return f;
  return f % 2 === 0 ? f : f + 1;
}

// ---------------------------------------------------------------------------
// The 240 roots, in the estate's enumeration order.
// ---------------------------------------------------------------------------

function pairIndexTable() {
  // Lexicographic combinations of 2 from 8, i<j — dimensions.py:258.
  const order = [];
  let p = 0;
  for (let i = 0; i < 8; i++) {
    for (let j = i + 1; j < 8; j++) order[p++] = [i, j];
  }
  return order;
}

const PAIRS = pairIndexTable();

/** Build the 240x8 root table as Float64 (exact: every entry is 0, ±1/2 or ±1)
 *  plus the doubled integer table the codec's fast path uses
 *  (e8_period_codec.py:610-613, `roots2 = (roots * 2).to(int64)`). */
export function buildE8Roots() {
  const roots = new Float64Array(ROOT_COUNT * 8);
  const roots2 = new Int32Array(ROOT_COUNT * 8);
  let r = 0;
  // Type 1: (±1, ±1, 0^6) — 112 rows.
  for (const [i, j] of PAIRS) {
    for (const si of [1, -1]) {
      for (const sj of [1, -1]) {
        const row = roots.subarray(r * 8, r * 8 + 8);
        const row2 = roots2.subarray(r * 8, r * 8 + 8);
        for (let k = 0; k < 8; k++) {
          const v = k === i ? si : k === j ? sj : 0;
          row[k] = v;
          row2[k] = 2 * v;
        }
        r++;
      }
    }
  }
  // Type 2: (±1/2)^8 with even minus count — 128 rows, bits ascending.
  for (let bits = 0; bits < 256; bits++) {
    let pop = 0;
    for (let k = 0; k < 8; k++) if ((bits >> k) & 1) pop++;
    if (pop % 2 !== 0) continue;
    const row = roots.subarray(r * 8, r * 8 + 8);
    const row2 = roots2.subarray(r * 8, r * 8 + 8);
    for (let k = 0; k < 8; k++) {
      const s = ((bits >> k) & 1) === 1 ? -1 : 1;
      row[k] = 0.5 * s;
      row2[k] = s;
    }
    r++;
  }
  if (r !== ROOT_COUNT) throw new Error(`root table built ${r} rows, expected ${ROOT_COUNT}`);
  return { roots, roots2, count: r };
}

let _table = null;
export function rootTable() {
  if (_table === null) _table = buildE8Roots();
  return _table;
}

// ---------------------------------------------------------------------------
// root_index: argmax <root, v> over the 240 roots, first-occurrence tie-break.
// ---------------------------------------------------------------------------

/** Integral coords exactly as `_integral_coords` does (e8_period_codec.py:303-322):
 *  integer-valued floats inside +-MAX_EXACT_COORD, else null (reference path). */
export function integralCoords(v) {
  const out = new Array(8);
  for (let k = 0; k < 8; k++) {
    const c = v[k];
    if (!Number.isFinite(c) || c < -MAX_EXACT_COORD || c > MAX_EXACT_COORD) return null;
    const ci = Math.trunc(c);
    if (ci !== c) return null;
    out[k] = ci;
  }
  return out;
}

/**
 * Dominant-direction root code 0..239. Mirrors `E8PeriodCodec.root_index`:
 * the exact doubled-integer leg when the vector is integral
 * (e8_period_codec.py:712-719), the float64 matmul leg otherwise (:688-694).
 * Ties resolve to the FIRST row (argmax semantics of numpy/torch), and the zero
 * vector therefore lands on index 0 "by convention" (:699-701).
 */
export function rootIndex(v) {
  const { roots, roots2 } = rootTable();
  const w = integralCoords(v);
  let best = -Infinity;
  let bestIdx = 0;
  if (w !== null) {
    for (let r = 0; r < ROOT_COUNT; r++) {
      let s = 0;
      const off = r * 8;
      for (let k = 0; k < 8; k++) s += roots2[off + k] * w[k];
      if (s > best) { best = s; bestIdx = r; }
    }
    return bestIdx;
  }
  for (let r = 0; r < ROOT_COUNT; r++) {
    let s = 0;
    const off = r * 8;
    for (let k = 0; k < 8; k++) s += roots[off + k] * v[k];
    if (s > best) { best = s; bestIdx = r; }
  }
  return bestIdx;
}

/**
 * Closed form for max over the root shell — the GPU-portable leg, and the
 * reason a browser can afford this at all (a 240-row dot-product sweep per
 * pixel is ~2k FMAs; this is a single pass over 8 lanes).
 *
 * The two families maximize differently (dimensions.py:238-241 gives the two
 * shapes, so this is arithmetic on those shapes, not a fitted approximation):
 *
 *   type-1 rows are (+-1, +-1, 0^6)   -> max = a1 + a2, the two largest |v|
 *   type-2 rows are (+-1/2)^8, even minus count
 *                                     -> max = (sum|v| - (odd negatives ? 2*min|v| : 0)) / 2
 *   max over the shell = max(type1, type2)
 *
 * The /2 on the second branch is the type-2 coordinate magnitude; dropping it
 * is exactly the factor-of-two that the first parity run against the table
 * caught (512/512 vectors, cf = 2 x table). Verified by
 * `tools/determinism-harness.mjs` as a falsifier: closedFormMax(v) must equal
 * the 240-row table maximum for every sampled v.
 */
export function closedFormMax(v) {
  let sum = 0;
  let min = Infinity;
  let negatives = 0;
  let a1 = -Infinity;
  let a2 = -Infinity;
  for (let k = 0; k < 8; k++) {
    const m = Math.abs(v[k]);
    sum += m;
    if (v[k] < 0) negatives++;
    if (m < min) min = m;
    if (m > a1) { a2 = a1; a1 = m; } else if (m > a2) a2 = m;
  }
  const type1 = a1 + a2;
  const type2 = (sum - (negatives % 2 === 0 ? 0 : 2 * min)) * 0.5;
  return Math.max(type1, type2);
}

// ---------------------------------------------------------------------------
// The analytic 240-root label — a CLOSED FORM for the same argmax, so a GPU can
// carry the estate's own index instead of an approximation of it.
//
// The enumeration (dimensions.py:256-270) is regular enough to invert:
//   rows 0..111   : (i,j) lexicographic with i<j, then (si,sj) in
//                   [1,-1]x[1,-1]                       -> idx = pairRank*4 + siBit*2 + sjBit
//   rows 112..239 : `bits` ascending over 0..255 with even popcount,
//                   root[k] = -1/2 iff bit k is set     -> idx = 112 + rankEvenPopcount(bits)
// The maximizing row is read off |v| directly: family 1 wants the two largest
// lanes with matching signs; family 2 wants sign(v) everywhere, with the
// cheapest lane (smallest |v|) flipped when that pattern has an odd number of
// negatives. `tools/determinism-harness.mjs` falsifies this against the table.
// ---------------------------------------------------------------------------

/** Row of the pair (i,j), i<j, in lexicographic combinations order. */
export function pairRank(i, j) {
  return 7 * i - (i * (i - 1)) / 2 + (j - i - 1);
}

/** Position of `bits` among the even-popcount values of 0..255, ascending.
 *  Derivation: for each set bit k>0 exactly half of the 2^k suffixes fix the
 *  parity, contributing 2^(k-1); a set bit 0 contributes 1 iff the parity of the
 *  bits above it is already even. Spot-checked against a brute-force count in
 *  the harness (all 256 values). */
export function rankEvenPopcount(bits) {
  let rank = 0;
  let prefix = 0;
  for (let k = 7; k >= 0; k--) {
    if ((bits >> k) & 1) {
      rank += k >= 1 ? 1 << (k - 1) : (prefix % 2 === 0 ? 1 : 0);
      prefix++;
    }
  }
  return rank;
}

/**
 * The estate's root index, computed without touching the 240-row table.
 * Returns {index, family, value}, where `index` is required to be
 * IDENTICAL to `rootIndex(v)` — the table's first-occurrence argmax — and the
 * harness falsifies that equality rather than assuming it.
 *
 * Getting first-occurrence right is the whole difficulty, and the two families
 * need it differently:
 *
 *  family 1 (rows 0..111, ordered pairRank then (si,sj)): many pairs can tie the
 *   max (any {i,j} whose |v| pair sums to a1+a2), so the maximizing row is the
 *   LEXICOGRAPHICALLY FIRST such pair, not "the first lane that hit the max".
 *   A single 28-iteration masked min over i<j gets it, and 28 is affordable in a
 *   shader where 240 dot products (1920 FMAs) are not.
 *   Within a pair the sign loop runs [1,-1]x[1,-1], so a zero lane takes si=+1,
 *   i.e. siBit 0 — which `v < 0 ? 2 : 0` expresses exactly, including v = 0.
 *
 *  family 2 (rows 112..239, ordered by ascending `bits`): the max needs s = sign(v)
 *   on every lane, with one flip when that has an odd number of negatives; the
 *   flip must land on a LANE OF MINIMUM |v|, and to minimise `bits` it must be
 *   the flip that LOWERS the integer most — i.e. clearing the highest set bit
 *   among the tied-minimum negative lanes, not the first lane in scan order.
 *   (This is the case the first version of this function got wrong: it took scan
 *   order, which is the table's answer only when the minimum is unique.)
 *
 *  both shells tie (family 0): every type-1 row is numbered below every type-2
 *   row, so the table's first occurrence is the type-1 row, and `family` says so.
 */
export function rootLabelAnalytic(v) {
  const m = new Float64Array(8);
  let a1 = -Infinity, a2 = -Infinity;
  let min = Infinity;
  let sum = 0, negatives = 0, bits = 0;
  for (let k = 0; k < 8; k++) {
    m[k] = Math.abs(v[k]);
    sum += m[k];
    if (v[k] < 0) { negatives++; bits |= 1 << k; }
    if (m[k] < min) min = m[k];
    if (m[k] > a1) { a2 = a1; a1 = m[k]; } else if (m[k] > a2) a2 = m[k];
  }
  const type1 = a1 + a2;
  const odd = negatives % 2 === 1;
  const type2 = (sum - (odd ? 2 * min : 0)) * 0.5;

  // Lexicographically first maximizing pair.
  let bestPair = -1;
  for (let i = 0; i < 8; i++) {
    for (let j = i + 1; j < 8; j++) {
      if (m[i] + m[j] === type1) {
        const cand = pairRank(i, j) * 4 + (v[i] < 0 ? 2 : 0) + (v[j] < 0 ? 1 : 0);
        if (bestPair < 0 || cand < bestPair) bestPair = cand;
      }
    }
  }

  // Minimum-integer maximizing half-integral sign pattern.
  let bestBits = odd ? 1 << 30 : bits;
  if (odd) {
    for (let k = 0; k < 8; k++) {
      if (m[k] !== min) continue;
      const cand = bits ^ (1 << k);
      if (popcountEven(cand) && cand < bestBits) bestBits = cand;
    }
  }
  const fam2 = 112 + rankEvenPopcount(bestBits);

  if (type1 > type2) return { index: bestPair, family: 1, value: type1 };
  if (type2 > type1) return { index: fam2, family: 2, value: type2 };
  return { index: Math.min(bestPair, fam2), family: 0, value: type1 };
}

/** Even-popcount predicate (bits ascending enumeration is exactly the even-weight
 *  subsequence — dimensions.py:262-266). */
export function popcountEven(bits) {
  let p = 0;
  for (let k = 0; k < 8; k++) if ((bits >> k) & 1) p++;
  return p % 2 === 0;
}

// ---------------------------------------------------------------------------
// nearest_e8 — the Conway-Sloane exact nearest point, ported from
// zke8 examples/raw-nearest-e8.e8:13-141.
//
// status: 0 ok (:141) | 3 non-finite input (:36-38) | 4 |x| > 1024 (:39-41,
// the kernel's own radius, not the codec's MAX_EXACT_COORD) | 6 ambiguous
// boundary (|advantage| <= BOUNDARY_EPS, :100-102).
// The kernel's statuses 1 and 2 (:14-19) are batch-pointer guards with no
// per-vector analogue here.
//
// THE ESTATE'S OWN TWO LEGS DISAGREE AT THAT BOUNDARY, SO THE PORT CARRIES BOTH.
// The conservative CPU provider kernel REFUSES an ambiguous boundary
// (`return i32(6)`, raw-nearest-e8.e8:100-102) even though the law stated 33
// lines earlier in the same row — "Positive selects the shifted coset; an exact
// zero keeps D8" (:65-67) — says what to do there; the guard at :100 fires
// before :104's `choose1` could ever apply it. The quantization leg the
// codec rides does not refuse: ResidualE8LatticeVQ calls nearest_e8
// (e8_lattice_protocol.py:295 -> e8_lattice_quantizer.py:134-165), which picks a
// side. Measured, not assumed: at ladder level 0, 18 of 32 estate vectors are
// EXACT ties (half-integral lanes each contribute +-1/4 to the advantage and
// cancel to precisely 0.0), and a port carrying only the kernel's refusal emitted
// 0 levels where the estate emitted 3.
//
// `tieBreak` names which leg to match: 'keepD8' (default, the protocol leg)
// always returns a point; 'refuse' reproduces the provider kernel's status 6.
// Either way the result carries `boundary`, and both demos DRAW it — the case
// the kernel refuses is exactly the Voronoi cell edge.
// ---------------------------------------------------------------------------

export function nearestE8(x, opts = {}) {
  const tieBreak = opts.tieBreak ?? 'keepD8';
  const z0 = new Array(8);
  const z1 = new Array(8);
  let sum0 = 0;
  let sum1 = 0;
  let bestIndex0 = 0;
  let bestIndex1 = 0;
  let maxResidual0 = -1;
  let maxResidual1 = -1;

  // One linear scan finds both D8 candidates; STRICT greater-than keeps the
  // first-coordinate residual tie rule (the law at raw-nearest-e8.e8:23-24,
  // implemented by the `>` comparisons at :46-49 and :55-58).
  for (let lane = 0; lane < 8; lane++) {
    const xi = x[lane];
    if (!Number.isFinite(xi)) return { q: null, status: 3 };
    if (Math.abs(xi) > 1024.0) return { q: null, status: 4 }; // :39-41
    const r0 = roundEven(xi);
    z0[lane] = r0;
    sum0 += r0 | 0;
    const res0 = Math.abs(xi - r0);
    if (res0 > maxResidual0) { maxResidual0 = res0; bestIndex0 = lane; }
    const shifted = xi - 0.5;
    const r1 = roundEven(shifted);
    z1[lane] = r1;
    sum1 += r1 | 0;
    const res1 = Math.abs(shifted - r1);
    if (res1 > maxResidual1) { maxResidual1 = res1; bestIndex1 = lane; }
  }

  const odd0 = (sum0 & 1) !== 0;
  const odd1 = (sum1 & 1) !== 0;

  // Centered distance advantage: positive selects the shifted coset; an exact
  // zero keeps D8 (law :65-67, accumulation :68-99).
  let advantage = 0;
  for (let lane = 0; lane < 8; lane++) {
    const xi = x[lane];
    let a = z0[lane];
    if (odd0 && lane === bestIndex0) a += xi - a >= 0 ? 1 : -1;
    else if (odd0 && xi === 0 && a === 0) a = 0; // :80-84, -0.0 canonicalizes to +0.0
    let b = z1[lane];
    if (odd1 && lane === bestIndex1) b += xi - 0.5 - b >= 0 ? 1 : -1;
    b += 0.5;
    const delta = b - a;
    advantage += delta * (2 * (xi - a) - delta);
  }
  const boundary = Math.abs(advantage) <= BOUNDARY_EPS;
  if (boundary && tieBreak === 'refuse') return { q: null, status: 6, boundary: true, advantage };

  const choose1 = boundary ? false : advantage > 0;
  const q = new Float64Array(8);
  for (let lane = 0; lane < 8; lane++) {
    const xi = x[lane];
    if (choose1) {
      const shifted = xi - 0.5;
      let r = z1[lane];
      if (odd1 && lane === bestIndex1) r += shifted - r >= 0 ? 1 : -1;
      q[lane] = r + 0.5;
    } else {
      let r = z0[lane];
      if (odd0 && lane === bestIndex0) r += xi - r >= 0 ? 1 : -1;
      else if (odd0 && xi === 0 && r === 0) r = 0; // :128-133, the emit leg's own canonicalization
      q[lane] = r;
    }
  }
  return { q, status: 0, coset: choose1 ? 1 : 0, boundary, advantage };
}

/** Membership test for the visual's self-check: twice the point is integral and
 *  either all-even or all-odd coordinates with coordinate sum = 0 mod 4
 *  (e8_lattice_quantizer.py:159, the docstring's own assertion). */
export function isInE8(y) {
  let parity = null;
  let sum = 0;
  for (let k = 0; k < 8; k++) {
    const w = 2 * y[k];
    if (!Number.isInteger(w)) return false;
    const p = ((w % 2) + 2) % 2;
    if (parity === null) parity = p;
    else if (p !== parity) return false;
    sum += w;
  }
  return ((sum % 4) + 4) % 4 === 0;
}

// ---------------------------------------------------------------------------
// Residual E8 quantization ladder — the codec's actual modulation.
// ---------------------------------------------------------------------------

/** The level-scale ladder as a FROZEN TABLE, built by float64 multiplication and
 *  rounded once to float32. Three reasons it is a table and not a `Math.pow`
 *  call at use time:
 *
 *  1. It is the estate's own object. The source materializes exactly these 16
 *     float32 numbers into a registered buffer
 *     (e8_lattice_protocol.py:220-228), and this table was diffed against that
 *     buffer elementwise — 16/16 identical (see README "Parity").
 *  2. `Math.pow` is implementation-implemented in ECMA-262 (§22.1.5.14: the
 *     result is "implementation-approximated"), so a pow at use time makes the
 *     byte-pin engine-dependent. Multiplication and Math.sqrt are exactly
 *     specified, so this chain is not.
 *  3. The build was cross-checked: repeated multiplication and Math.pow agree on
 *     every entry at float32 granularity, and both equal the estate buffer. So
 *     the table costs nothing in trust.
 */
function buildLevelScales() {
  const out = new Float64Array(LADDER_MAX_LEVELS);
  let acc = 1;
  for (let i = 0; i < LADDER_MAX_LEVELS; i++) {
    out[i] = f32(LADDER_INITIAL_SCALE / acc);
    acc *= LADDER_DECAY;
  }
  return out;
}

const LEVEL_SCALES_RAW = buildLevelScales();
const CLAMPED_MIN = f32(SCALE_CLAMP_MIN);
const LEVEL_SCALES = Float64Array.from(LEVEL_SCALES_RAW, (s) => Math.max(s, CLAMPED_MIN));

/** Raw buffer value (unclamped), for diffing against the source's tensor. */
export function levelScaleRaw(i) {
  return LEVEL_SCALES_RAW[i];
}

/** The value the ladder actually uses: the buffer, clamped at the use site
 *  exactly as `self.level_scales[level].clamp(min=1e-6)` does
 *  (e8_lattice_protocol.py:286). Published separately because the source keeps
 *  them separate, and a port that folds the two together can be diffed against
 *  neither. First clamped index is 6 (measured). */
export function levelScale(i) {
  return LEVEL_SCALES[i];
}

export { LEVEL_SCALES, LEVEL_SCALES_RAW };

/**
 * Quantize x in R^8 to a list of E8 codewords, level by level, exactly as
 * `ResidualE8LatticeVQ.forward` does (e8_lattice_protocol.py:285-315):
 *
 *   residual = x; qsum = 0
 *   for i: y = nearest_e8(residual / s_i) * s_i
 *          qsum += y; residual = x - qsum
 *          codes[i] = 2 * (y / s_i)            (half-step integers)
 *          stop once i+1 >= min_levels and ||residual||^2 < threshold^2 * 8
 *
 * Returns per-level half-step codes plus the running reconstruction, so a
 * decoder (or a shader) can re-sum them: decode = sum_i codes[i]/2 * s_i
 * (e8_lattice_protocol.py:349-359).
 *
 * `maxLevels` and `threshold` are overridable for the demos; the defaults are
 * the estate's shipped config. A level that hits the kernel's typed refusal
 * (status 3/4/6) does NOT silently fall back — it is recorded in `stops` with
 * its status, because a demoscene that coalesces an absence into a zero has
 * inherited the estate's own worst bug (e8_period_codec.py:47-58, absence law).
 */
export function residualLadder(x, opts = {}) {
  const maxLevels = opts.maxLevels ?? LADDER_MAX_LEVELS;
  const threshold = opts.threshold ?? LADDER_RESIDUAL_THRESHOLD;
  const minLevels = opts.minLevels ?? LADDER_MIN_LEVELS;
  const codes = [];
  const contribs = [];
  const points = [];
  const statuses = [];
  const boundaries = [];
  const advantages = [];
  const scales = [];
  const residualNorms = [];
  const q = new Float64Array(8); // running reconstruction
  const thresholdSq = threshold * threshold * 8;

  let stops = 'levels';
  for (let i = 0; i < maxLevels; i++) {
    const s = levelScale(i);
    const scaled = new Float64Array(8);
    // float32 arithmetic, op by op, because the source tensor is float32
    // (e8_lattice_protocol.py:264-295): residual is a float32 difference and the
    // division by the level scale is a float32 quotient.
    for (let k = 0; k < 8; k++) scaled[k] = f32(f32(x[k] - q[k]) / s);
    const hit = nearestE8(scaled, { tieBreak: opts.tieBreak ?? 'keepD8' });
    if (hit.status !== 0) {
      stops = hit.status === 6 ? 'boundary' : `refused_${hit.status}`;
      break;
    }
    const code = new Int32Array(8);
    const y = new Float64Array(8);
    for (let k = 0; k < 8; k++) {
      code[k] = Math.round(2 * hit.q[k]); // half-step units, exact (:312)
      y[k] = f32(hit.q[k] * s); // nearest_e8(residual/s) * s, float32 (:295)
      q[k] = f32(q[k] + y[k]); // qsum accumulation is float32 too (:306)
    }
    codes.push(code);
    contribs.push(y);
    points.push(Float64Array.from(hit.q));
    statuses.push(hit.coset ?? 0);
    boundaries.push(hit.boundary === true);
    advantages.push(hit.advantage ?? 0);
    scales.push(s);
    let rn = 0;
    for (let k = 0; k < 8; k++) { const r = f32(x[k] - q[k]); rn += r * r; }
    residualNorms.push(rn);
    if (i + 1 >= minLevels && rn < thresholdSq) { stops = 'converged'; break; }
  }
  let rn = 0;
  for (let k = 0; k < 8; k++) { const r = x[k] - q[k]; rn += r * r; }
  return { codes, contribs, points, cosets: statuses, boundaries, advantages, scales, residualNorms, q, finalResidualSq: rn, stops };
}

// ---------------------------------------------------------------------------
// f2_8 = E8/2E8 class label, computed in the union model.
//
// q(x) = ||x||^2 / 2 mod 2 is canonical on the even lattice and invariant under
// x -> x + 2z, so it is a class function (e8_alphabet.py:12-45, :35-40). With
// w = 2x integral, ||x||^2/2 = sum(w^2)/8, exact in integers for every E8 point.
// The partition is 1 zero + 135 singular (q=0) + 120 root (q=1) = 256
// (e8_alphabet.py:110-120).
// ---------------------------------------------------------------------------

export function doubledCoords(y) {
  const w = new Int32Array(8);
  for (let k = 0; k < 8; k++) {
    const v = 2 * y[k];
    if (!Number.isInteger(v)) return null;
    w[k] = v;
  }
  return w;
}

export function classQ(w) {
  let s = 0;
  for (let k = 0; k < 8; k++) s += w[k] * w[k];
  if (s % 8 !== 0) return null; // not an E8 point in this model
  return ((s / 8) % 2 + 2) % 2;
}

export function isZeroClass(w) {
  for (let k = 0; k < 8; k++) if (w[k] !== 0) return false;
  return true;
}

/** 'zero' | 'root' | 'singular' by the declared partition (q, zero-ness).
 *  NOTE: q=1 <=> root class and q=0 nonzero <=> singular class is the declared
 *  law for E8/2E8 (e8_alphabet.py:41-44); this helper is used for COLORING, and
 *  the harness reports the measured class histogram so the 1/135/120 split is
 *  checked against the declaration rather than assumed. */
export function normClass(w) {
  if (isZeroClass(w)) return 'zero';
  const q = classQ(w);
  if (q === 1) return 'root';
  if (q === 0) return 'singular';
  return 'undeclared';
}

// ---------------------------------------------------------------------------
// House seeded PRNG — ported from art gen/lib/prng.js:12-62 (FNV-1a 4-lane seed
// hash feeding xorshift128+). Kept byte-faithful: a seed string must produce the
// same lane in the demos as it does in gen/.
// ---------------------------------------------------------------------------

export class PRNG {
  constructor(seed) {
    this.state = this._hashSeed(String(seed));
  }

  _hashSeed(str) {
    let h1 = 0x811c9dc5;
    let h2 = 0x811c9dc5 ^ 0xdeadbeef;
    let h3 = 0x811c9dc5 ^ 0xcafebabe;
    let h4 = 0x811c9dc5 ^ 0x12345678;
    for (let i = 0; i < str.length; i++) {
      const c = str.charCodeAt(i);
      h1 = Math.imul(h1 ^ c, 0x01000193);
      h2 = Math.imul(h2 ^ c, 0x01000193);
      h3 = Math.imul(h3 ^ c, 0x01000193);
      h4 = Math.imul(h4 ^ c, 0x01000193);
    }
    if (h1 === 0 && h2 === 0 && h3 === 0 && h4 === 0) h1 = 0x12345678;
    return [h1 >>> 0, h2 >>> 0, h3 >>> 0, h4 >>> 0];
  }

  next() {
    let [s0, s1, s2, s3] = this.state;
    const result = (s0 + s3) >>> 0;
    const t = s1 << 9;
    s2 ^= s0;
    s3 ^= s1;
    s1 ^= s2;
    s0 ^= s3;
    s2 ^= t;
    s3 = (s3 << 11) | (s3 >>> 21);
    this.state = [s0 >>> 0, s1 >>> 0, s2 >>> 0, s3 >>> 0];
    return result / 0xffffffff;
  }

  range(min, max) { return min + this.next() * (max - min); }
  int(min, max) { return Math.floor(this.range(min, max + 1)); }
}

// ---------------------------------------------------------------------------
// The 8-lane carrier field. Both demos read their R^8 vector from this one
// function, so the GPU and the CPU reference are driven by identical math.
//
//   v_k(u, v, t) = A * tri(fx_k*u + fy_k*v + (phi_k + t*omega_k)/TAU)
//
// `tri` is a triangle wave, not a sine, and that is a determinism decision
// rather than a taste one: Math.sin is implementation-approximated in
// ECMA-262 (§22.1.5.20), so a sine in the carrier would make the byte-pin
// engine-dependent. floor/abs/+/-/* are exactly specified, and GLSL
// implements the same four ops bit-for-bit, so the CPU reference and the
// shader are the same function rather than two approximations of it.
// Piecewise-linear harmonics are also the house sound of a demoscene carrier:
// hard facets instead of soft moiré.
// ---------------------------------------------------------------------------

export const TAU = 6.283185307179586; // 2*pi as one literal, never recomputed

/** Triangle wave of period 1, range [-1, 1], exact arithmetic only. */
export function tri(x) {
  const p = x - Math.floor(x);
  return p < 0.5 ? 4 * p - 1 : 3 - 4 * p;
}

/**
 * The lane law, factored out from any particular generator so the house PRNG and
 * the estate stream (js/seed-stream.js) differ ONLY in where their uniforms come
 * from — one copy of the mapping, two streams feeding it. `uniform()` must return
 * a double in [0,1]; the four draws per lane happen in this fixed order.
 *
 * The arithmetic is `min + u * (max - min)` with no other ops, so the eight lanes
 * out of a given uniform sequence are the same 64-bit IEEE patterns in Python, in
 * node and in Chromium; seed-stream.js exports the estate-law caller and the
 * harness compares lane bit patterns against what the real estate module produced.
 */
export function fieldFromUniform(uniform, opts = {}) {
  const amplitude = opts.amplitude ?? 1.5;
  const spatialMax = opts.spatialMax ?? 2.75;
  const temporalMax = opts.temporalMax ?? 1.6;
  const rnd = (min, max) => min + uniform() * (max - min);
  const lanes = [];
  for (let k = 0; k < 8; k++) {
    lanes.push({
      fx: rnd(-spatialMax, spatialMax),
      fy: rnd(-spatialMax, spatialMax),
      // phase and drift are stored as cycle fractions so the carrier never
      // needs a division by TAU at the pixel stage.
      phi: rnd(-0.5, 0.5),
      omega: rnd(-temporalMax, temporalMax) / TAU,
    });
  }
  return { lanes, amplitude, law: opts.law ?? 'house' };
}

/** House law: Xorshift128+ over the FNV-1a seed hash (the art repo's convention). */
export function fieldCoefficients(seed, opts = {}) {
  const rng = new PRNG(seed);
  return fieldFromUniform(() => rng.next(), { ...opts, law: 'house' });
}

/** Fill `out` (length 8) with the carrier vector at (u, v, t). Every op here is
 *  exactly specified, so this is reproducible across JS engines. */
export function carrierAt(u, v, t, coef, out) {
  for (let k = 0; k < 8; k++) {
    const L = coef.lanes[k];
    out[k] = coef.amplitude * tri(L.fx * u + L.fy * v + L.phi + t * L.omega);
  }
  return out;
}

// ---------------------------------------------------------------------------
// Palette — dark void, ice and gold, per the house convention (AGENTS.md
// "Conventions": dark void palette with ice #00ced1 and gold #c9a227). Colony
// hexes are NOT re-declared here (identity-coherence.test.mjs rejects a second
// COLONY_COLORS literal); these are demo surface colors only.
// ---------------------------------------------------------------------------

export const VOID = [0.016, 0.020, 0.031];
export const ICE = [0.0, 0.808, 0.820];
export const GOLD = [0.788, 0.635, 0.153];
