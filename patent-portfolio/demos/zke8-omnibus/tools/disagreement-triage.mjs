/**
 * disagreement-triage.mjs — name the mechanism behind every GPU/CPU delta, or
 * record that it is unnamed.
 *
 * WHY THIS FILE EXISTS. The browser check measured 48 of 16384 pixels moving by
 * more than 8 colour levels between the WebGL2 float32 path and the float64 CPU
 * reference (0.29%), max 36 levels. A move that large cannot come from a smooth
 * term: rounding a float64 colour leg to float32 changes a byte by ~1e-5 levels.
 * It has to come from a DECISION — the coset choice, the number of levels the
 * protocol's stop test emits, or which f2_8 class the codeword lands in.
 *
 * The first instinct was to assert "float32 rounding at a discontinuity" and put
 * a tolerance on it. That is what this file refuses to do. It re-renders each
 * disagreeing pixel under named variants — each one a different mechanism the
 * shader could legitimately be exercising — and reports which variant reproduces
 * the GPU's actual bytes. A pixel no variant reproduces is written down as
 * UNNAMED, with its decision record, instead of being absorbed into a threshold.
 *
 * Variants (all on the reference code path, so they differ from the shader only
 * in the mechanism being switched):
 *   f32carrier  the carrier lanes rounded to float32 before the ladder — the one
 *               step the two paths really do compute at different widths
 *   allLevels   threshold 0: every requested level is emitted, nothing stops early
 *   n_plus_1    one more ladder level than the reference emitted
 *   n_minus_1   one fewer (>=1)
 *   noFilament  the refusal-neighbourhood glow switched off (epsDraw -> 1e-12)
 *
 * Usage:
 *   node tools/browser-check.mjs                           # dumps the detail files
 *   node tools/disagreement-triage.mjs [ladder|root] [house|estate]   # default: ladder house
 *
 * The second word is the SEED LAW the browser was rendering. Each kind now has a
 * dump per law (/tmp/v7-gpu-detail-<kind>-<law>.json), because the disagreeing
 * pixel SET is a property of the carrier coefficients as well as the driver: an
 * estate-law frame explained with house-law coefficients would be a mechanism
 * story told about the wrong picture. The law the file claims and the law it was
 * asked for are both checked, so a renamed dump cannot be read as the other one.
 */

import { readFileSync, existsSync, readdirSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';
import { makeScene, uvOf, mirrorCarrier, carrier } from '../js/ref-render.js';
import { carrierAt, residualLadder, normClass, doubledCoords } from '../js/e8-core.js';

const HERE = dirname(fileURLToPath(import.meta.url));
const argv = process.argv.slice(2);
const which = argv.includes('root') ? 'root' : 'ladder';
const law = argv.includes('estate') ? 'estate' : 'house';
// The dump directory is overridable so CI can grade the two identity guards
// below against a directory it owns. /tmp is shared with every other lane on
// this host, and this file's only input is whatever sits at that path — a
// default that a test has to write into is a test that races the fleet.
const DETAIL_DIR = process.env.V7_GPU_DETAIL_DIR || '/tmp';
const path = join(DETAIL_DIR, `v7-gpu-detail-${which}-${law}.json`);

if (!existsSync(path)) {
  let seen = [];
  try {
    seen = readdirSync(DETAIL_DIR).filter((f) => f.startsWith('v7-gpu-detail-'));
  } catch { /* a directory we cannot list is not a rendering failure; say so by absence */ }
  console.log(`triage: no detail file at ${path}. Run \`node tools/browser-check.mjs\` first —`
    + ` the per-pixel GPU bytes can only come from a real browser, not from here.`
    + (seen.length ? `\n  dumps present: ${seen.join(', ')}` : `\n  dumps present: none in ${DETAIL_DIR}`));
  process.exit(2);
}

const dump = JSON.parse(readFileSync(path, 'utf8'));
if ((dump.law ?? 'house') !== law) {
  console.log(`triage: ${path} was written under law=${JSON.stringify(dump.law)} but was asked for ${JSON.stringify(law)} --`
    + ` the file was renamed, not re-rendered. Refusing to explain one law's pixels with another law's coefficients.`);
  process.exit(2);
}
// The law guard alone was not enough, and this was measured, not assumed: with
// the LADDER/house dump renamed to v7-gpu-detail-root-house.json, this tool
// accepted it and "explained" 48 ladder pixels against root's carrier — 0/48
// reproduced, 48 UNEXPLAINED, rc=0. A file whose own `kind` field disagrees
// with the kind asked for is the same defect as a renamed law, so it is refused
// in the same place, before any scene is built. The field is REQUIRED rather
// than compared-if-present: `tools/browser-check.mjs` has always written it, so
// a dump without one is either hand-made or from a build older than this guard,
// and neither is evidence about the frame being asked about.
if ((dump.kind ?? null) !== which) {
  console.log(`triage: ${path} holds a dump of kind=${JSON.stringify(dump.kind ?? null)} but was asked for ${JSON.stringify(which)} --`
    + ` the file was renamed, not re-rendered, or it never named its kind. Refusing to explain one kind's pixels with another kind's carrier.`);
  process.exit(2);
}
const rows = dump.detail || [];
const size = dump.size;
const state = { levels: 4, threshold: 1e-3, epsDraw: 0.02, ...dump.state };
const only = new Set(rows.map((r) => r.idx));

const scene = makeScene(which, dump.seed ?? 'e8-omnibus-1102', { field: { amplitude: state.amplitude ?? 1.5 } });
const render = (over) => {
  const buf = scene.alloc(size, size);
  scene.render(size, size, dump.frame ?? 0, { ...state, only, ...over }, buf);
  return buf;
};
const VARIANTS = [
  ['f32carrier', { simulateF32: true }],
  ['allLevels', { threshold: 0 }],
  ['noFilament', { epsDraw: 1e-12 }],
];
// n_plus_1 / n_minus_1 need the per-pixel level count, so they are applied with a
// single global levels value only when it equals reference_n+1 for that pixel —
// which it cannot be, because pixels differ. Instead compute n per pixel from the
// codec itself and render those pixels at their own n+-1 by grouping.
const coef = carrier(dump.seed ?? 'e8-omnibus-1102', { amplitude: state.amplitude ?? 1.5, law });
const recs = new Map();
for (const r of rows) {
  const uv = [0, 0]; const v8 = new Float64Array(8);
  uvOf(r.px, r.py, size, size, uv);
  carrierAt(uv[0], uv[1], dump.frame ?? 0, coef, v8);
  const L = residualLadder(v8, { maxLevels: state.levels, threshold: state.threshold });
  recs.set(r.idx, {
    n: L.codes.length, stops: L.stops,
    cosets: L.cosets.join(''), classes: L.points.map((p) => normClass(doubledCoords(p))[0]),
    adv: L.advantages.map((a) => Math.abs(a)), rn: L.residualNorms, v8: Array.from(v8),
  });
}
const groups = new Map(); // key: `${levels}|simulateF32` -> Set of idx
for (const r of rows) {
  const n = recs.get(r.idx).n;
  for (const [name, lv] of [['n_plus_1', n + 1], ['n_minus_1', Math.max(1, n - 1)]]) {
    if (lv > 16) continue;
    const k = `${name}|${lv}`;
    if (!groups.has(k)) groups.set(k, { name, levels: lv, set: new Set() });
    groups.get(k).set.add(r.idx);
  }
}

const bufs = new Map();           // variant name -> Uint8ClampedArray (only `only` pixels are meaningful)
const addVariant = (name, over, levelsOverride) => {
  const buf = new Uint8ClampedArray(size * size * 4);
  scene.render(size, size, dump.frame ?? 0, { ...state, only, ...over, ...(levelsOverride ? { levels: levelsOverride } : {}) }, buf);
  bufs.set(name, buf);
};
for (const [name, over] of VARIANTS) addVariant(name, over);

// n_plus_1 / n_minus_1 are PER-PIXEL variants (each pixel's own level count +-1),
// so they are rendered in groups sharing a levels value and merged into one buffer
// per variant name. Grouping keeps it to ~4 full passes instead of 48.
for (const [name, delta] of [['n_plus_1', +1], ['n_minus_1', -1]]) {
  const byLevels = new Map();
  for (const r of rows) {
    const lv = Math.min(16, Math.max(1, recs.get(r.idx).n + delta));
    if (delta > 0 && lv > 16) continue;
    if (!byLevels.has(lv)) byLevels.set(lv, new Set());
    byLevels.get(lv).add(r.idx);
  }
  const acc = new Uint8ClampedArray(size * size * 4);
  for (const [lv, set] of byLevels) {
    const buf = scene.alloc(size, size);
    scene.render(size, size, dump.frame ?? 0, { ...state, levels: lv, only: set }, buf);
    for (const idx of set) for (let c = 0; c < 4; c++) acc[idx * 4 + c] = buf[idx * 4 + c];
  }
  bufs.set(name, acc);
}

// ---------------------------------------------------------------------------
// THE SHADER MIRROR (the shipped one, js/ref-render.js mirrorCarrier -- the
// triage must not carry a second implementation of the thing it is testing). The
// decisive question is sharper: can a CPU program, given the seed alone, PREDICT
// the bytes the GPU will produce? If it can, the shader is a transcription of the
// formula and nothing more.
//
// The mirror re-evaluates the fragment shader's carrier expression in IEEE
// float32, op by op, in the order GLSL writes it:
//
//     float val = uAmp * tri(L.x*q.x + L.y*q.y + L.z + uTime*L.w);
//     float tri(float x) { float p = x - floor(x);
//                          return p < 0.5 ? 4.0*p - 1.0 : 3.0 - 4.0*p; }
//
// with the uniforms' own widths: gl.uniform4fv uploads float32, so the lane
// coefficients are fround(coef) -- the reference keeps them in float64, which is
// a second, larger source of divergence than the carrier's arithmetic. u and v
// need no re-derivation at 128x128: (px+0.5)/128*2-1 is exact in binary (128 is a
// power of two, px+0.5 needs 8 bits), so float32 and float64 agree on the input
// itself and only the expression tree can differ.
//
// Two fusion modes are mirrored because GLSL does not pin them: `nofma` rounds
// every multiply and every add, `fma` lets the compiler contract a*b+c into one
// rounding (which JS can emulate exactly, since a float32 product fits in a
// float64 and the f64 sum of that with a float32 rounds only once here). Reporting
// BOTH, and which one matches better, is the honest version of "float32 is enough
// to predict the GPU": whether a driver fuses is not in the port's control.
// ---------------------------------------------------------------------------
for (const mode of ['nofma', 'fma']) {
  const buf = new Uint8ClampedArray(size * size * 4);
  scene.render(size, size, dump.frame ?? 0,
    { ...state, only, carrierFn: mirrorCarrier(coef, mode) }, buf);
  bufs.set(`mirror:${mode}`, buf);
}

const dist = (triple, buf, idx) => {
  let mx = 0;
  const src = rows.find((r) => r.idx === idx);
  for (let c = 0; c < 3; c++) {
    const d = Math.abs((buf ? buf[idx * 4 + c] : src.cpu[c]) - triple[c]);
    if (d > mx) mx = d;
  }
  return mx;
};

const tally = new Map();
const unexplained = [];
console.log(`triage ${which} · seed=${dump.seed} · law=${law} · frame=${dump.frame} · ${rows.length} pixels the GPU moved by >8 levels`);
if (rows.length === 0) {
  // A typed absence, not a pass. This frame's GPU bytes matched the float64
  // reference at every pixel (root-shell's argmax is a hard step, so float32
  // rarely flips it), so there is NO disagreement left to attribute to a
  // mechanism. Saying "0 of 0 explained" would read like a vacuous green; the
  // honest statement is that this dump contains no question. browser-check's
  // mirror claim is the one that grades a zero-disagreement frame.
  console.log('  nothing to triage: this dump holds no pixel over 8 levels, so no variant is asked to explain anything.');
  console.log('  (that is measured, not assumed: the count above is the GPU-vs-reference disagreement set the page itself published.)');
  process.exit(0);
}
console.log(`  variant buffers: ${[...bufs.keys()].join(', ')}\n`);
for (const r of rows) {
  const hits = [];
  let bestName = 'none', bestD = Infinity;
  for (const [name, buf] of bufs) {
    if (!buf) continue;
    const d = dist(r.gpu, buf, r.idx);
    if (d === 0) hits.push(name);
    if (d < bestD) { bestD = d; bestName = name; }
  }
  const rec = recs.get(r.idx);
  const tag = hits.length ? hits.join('+') : `nearest:${bestName}@${bestD}`;
  tally.set(tag, (tally.get(tag) || 0) + 1);
  if (!hits.length) unexplained.push({ r, rec, bestName, bestD });
}

console.log('  per-pixel records (first 12):');
for (const r of rows.slice(0, 12)) {
  const rec = recs.get(r.idx);
  const worst = Math.max(...[0, 1, 2].map((c) => Math.abs(r.gpu[c] - r.cpu[c])));
  console.log(`    ${String(r.px).padStart(3)},${String(r.py).padStart(3)} idx=${String(r.idx).padStart(5)} d=${String(worst).padStart(2)}`
    + ` n=${rec.n} stops=${rec.stops.padEnd(7)} cosets=${rec.cosets} classes=${rec.classes.join('')}`
    + ` |adv|=${rec.adv.map((a) => a.toExponential(1)).join(' ')} rn[0]=${rec.rn[0] ? rec.rn[0].toExponential(2) : 'n/a'}`
    + ` cpu=${r.cpu.join(',')} gpu=${r.gpu.join(',')}`);
}
console.log('\n  tally (variant exactly reproducing the GPU bytes):');
for (const [tag, n] of [...tally.entries()].sort((a, b) => b[1] - a[1])) {
  console.log(`    ${String(n).padStart(3)}x  ${tag}`);
}
// The mirror's score is reported separately and more finely than the "exact byte"
// tally, because the colour leg (hue wheel, filament ramp, byte quantisation) is
// float64 in the reference and float32 in the shader, and that alone moves a byte
// by about one level. So the question is not "0 levels" but "does the mirror reduce
// a 9..36 level decision gap to the <=2 level width of the colour leg".
for (const mode of ['nofma', 'fma']) {
  const buf = bufs.get(`mirror:${mode}`);
  const resid = rows.map((r) => dist(r.gpu, buf, r.idx));
  const cpuResid = rows.map((r) => dist(r.gpu, null, r.idx));
  const within = (arr, n) => arr.filter((d) => d <= n).length;
  console.log(`\n  mirror:${mode} (float32 carrier, ladder identical, colour leg still float64):`);
  console.log(`    residual |GPU - mirror| max-channel levels: <=1 ${within(resid, 1)}/${rows.length},`
    + ` <=2 ${within(resid, 2)}/${rows.length}, <=4 ${within(resid, 4)}/${rows.length},`
    + ` median ${resid.sort((a, b) => a - b)[Math.floor(resid.length / 2)]}, worst ${Math.max(...resid)}`);
  console.log(`    same pixels against the unperturbed float64 reference: <=2 ${within(cpuResid, 2)}/${rows.length},`
    + ` median ${cpuResid.sort((a, b) => a - b)[Math.floor(cpuResid.length / 2)]}, worst ${Math.max(...cpuResid)}`);
}

const exact = rows.length - unexplained.length;
console.log(`\n  ${exact}/${rows.length} pixels reproduced EXACTLY by a named variant;`
  + ` ${unexplained.length} UNEXPLAINED.`);
if (unexplained.length) {
  console.log('  unexplained pixels, with the best variant and how far off:');
  for (const u of unexplained.slice(0, 20)) {
    console.log(`    ${u.r.px},${u.r.py} best=${u.bestName} still ${u.bestD} levels off`
      + ` n=${u.rec.n} stops=${u.rec.stops} cosets=${u.rec.cosets} classes=${u.rec.classes.join('')}`
      + ` |adv|=${u.rec.adv.map((a) => a.toExponential(1)).join(' ')} cpu=${u.r.cpu.join(',')} gpu=${u.r.gpu.join(',')}`);
  }
}
// The stop-test margin distribution, because that is the other decision the codec
// makes and the one the earlier probes ignored entirely.
const stopSq = state.threshold * state.threshold * 8;
const stopMargins = rows.map((r) => {
  const rec = recs.get(r.idx);
  const last = rec.rn[rec.rn.length - 1];
  return Math.abs(last - stopSq) / stopSq;
});
const allMargins = [];
for (let py = 0; py < size; py++) {
  for (let px = 0; px < size; px++) {
    const uv = [0, 0]; const v8 = new Float64Array(8);
    uvOf(px, py, size, size, uv);
    carrierAt(uv[0], uv[1], dump.frame ?? 0, coef, v8);
    const L = residualLadder(v8, { maxLevels: state.levels, threshold: state.threshold });
    allMargins.push(Math.abs(L.residualNorms[L.residualNorms.length - 1] - stopSq) / stopSq);
  }
}
const rank = (arr, q) => { const a = [...arr].sort((x, y) => x - y); return a[Math.round(q * (a.length - 1))]; };
console.log(`\n  stop-test relative margin |rn-thr^2*8|/(thr^2*8): disagreeing pixels median ${rank(stopMargins, 0.5).toExponential(2)},`
  + ` frame median ${rank(allMargins, 0.5).toExponential(2)}, frame p1 ${rank(allMargins, 0.01).toExponential(2)}.`);
console.log(`  (fraction of the frame inside 1e-6 of the stop boundary: ${(allMargins.filter((m) => m < 1e-6).length / allMargins.length * 100).toFixed(3)}%;`
  + `  of the disagreeing pixels: ${(stopMargins.filter((m) => m < 1e-6).length / stopMargins.length * 100).toFixed(1)}%)`);
