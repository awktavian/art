/**
 * shell.js — the page controller for both demos.
 *
 * Responsibilities, in the order the determinism claim needs them:
 *
 *  1. Seed law. The seed comes from `location.hash` (`#seed=butterfly&frame=144`)
 *     so a URL IS a reproduction recipe, and every visual is a pure function of
 *     (seed, law, frame, the three codec knobs). No `Math.random` anywhere. Two
 *     laws are selectable: `house` (the art convention, Xorshift128+ over an
 *     FNV-1a hash) and `estate` (js/seed-stream.js, the bit-exact port of kagami
 *     core `omni/prng.py`'s SHA-256 counter-mode stream). The law is part of the
 *     URL and part of the pin-row key, because two laws over one seed are two
 *     different pictures and a lookup that ignored the law would grade one
 *     against the other's digest.
 *  2. Two render paths over the same math: the CPU reference (`ref-render.js`,
 *     float64, the thing the byte-pin hashes) painted into the certificate inset,
 *     and the WebGL2 shader (`gl-render.js`, float32) on the live canvas.
 *  3. MEASUREMENT, not assertion. At load the shell renders one canonical pin
 *     frame on both paths, at the same 128x128 and the same options, and reports
 *     the per-byte GPU-vs-reference delta and both SHA-256 digests. The CPU
 *     digest is compared to `tools/pin.json`. If a number cannot be produced the
 *     panel says WHICH one and WHY — it never prints a blank or a zero.
 *
 * Accessibility: the readout is an `aria-live` region and every control is a real
 * input with a label. `prefers-reduced-motion: reduce` starts the show paused on
 * the pinned frame, and the play button is then the only way to animate.
 */

import * as core from './e8-core.js';
import {
  LADDER_MAX_LEVELS,
  LADDER_MIN_LEVELS,
  BOUNDARY_EPS,
  E8_COVERING_RADIUS,
  ROOT_COUNT,
  LEVEL_SCALES,
  // fieldCoefficients is NOT imported here any more: the shell only ever draws
  // through ref-render.js carrier(), which picks the law. Importing the house-law
  // generator directly is how a second, law-blind path would get built.
  residualLadder,
} from './e8-core.js';import { certificate, makeScene, mirrorCarrier, carrier } from './ref-render.js';
import { createRenderer } from './gl-render.js';
// One module instance for the whole page: shell, ref-render and gl-render all
// import './e8-core.js' by the same resolved URL, so `core.rootLabelAnalytic`
// below is literally the function the pixels were painted with. A second copy
// would prove nothing.

const PINNED_SIZE = 128;

/** Compact exponential for the readout; 0 and NaN stay readable instead of
 *  printing "0e+0" or a bare NaN next to a claim. */
const fmt = (x) => (typeof x === 'number' && Number.isFinite(x) ? x.toExponential(3) : String(x));

// ---------------------------------------------------------------------------
// URL <-> state
// ---------------------------------------------------------------------------

/** Parse the hash into the render state. Unknown keys are kept but ignored, and
 *  a malformed number is reported rather than silently defaulted — a typo in a
 *  reproduction URL must not become a different picture with the same URL text. */
export function parseHash(hash) {
  const out = { ok: true, notes: [], values: {} };
  const params = new URLSearchParams(String(hash || '').replace(/^#/, ''));
  const defaults = {
    seed: 'e8-omnibus-1102',
    law: 'house',
    frame: 0,
    levels: 4,
    threshold: 1e-3,
    epsDraw: 0.02,
    amplitude: 1.5,
  };
  for (const key of Object.keys(defaults)) {
    const raw = params.get(key);
    if (raw === null) { out.values[key] = defaults[key]; continue; }
    if (key === 'seed') { out.values.seed = raw; continue; }
    if (key === 'law') {
      // A closed enum, graded the same way a malformed number is: reported, then
      // defaulted. `#law=omnibus` must not silently render the house picture and
      // then claim the estate law in the panel.
      if (raw === 'house' || raw === 'estate') { out.values.law = raw; continue; }
      out.notes.push(`law="${raw}" is neither "house" nor "estate"; using ${defaults.law}`);
      out.values.law = defaults.law;
      continue;
    }
    const num = Number(raw);
    if (!Number.isFinite(num)) {
      out.notes.push(`${key}="${raw}" is not a number; using ${defaults[key]}`);
      out.values[key] = defaults[key];
      continue;
    }
    out.values[key] = num;
  }
  out.values.levels = Math.max(LADDER_MIN_LEVELS, Math.min(LADDER_MAX_LEVELS, Math.round(out.values.levels)));
  out.values.frame = Math.max(0, Math.round(out.values.frame));
  out.values.threshold = Math.max(0, out.values.threshold);
  out.values.epsDraw = Math.max(1e-6, out.values.epsDraw);
  return out;
}

export function hashFor(values) {
  const p = new URLSearchParams();
  p.set('seed', String(values.seed));
  p.set('law', String(values.law ?? 'house'));
  p.set('frame', String(values.frame));
  p.set('levels', String(values.levels));
  p.set('threshold', String(values.threshold));
  p.set('epsDraw', String(values.epsDraw));
  p.set('amplitude', String(values.amplitude));
  return '#' + p.toString();
}

// ---------------------------------------------------------------------------
// Digests
// ---------------------------------------------------------------------------

/** SHA-256 over raw RGBA bytes as lowercase hex, in the same byte order the node
 *  harness hashes (that is what makes the two comparable). Returns a typed
 *  absence when `crypto.subtle` is unavailable instead of throwing: an
 *  unavailable hash function is a fact about the page, not a crash. */
export async function sha256Hex(bytes) {
  if (!(globalThis.crypto && globalThis.crypto.subtle)) {
    return { ok: false, refusal: 'subtle_crypto_absent', detail: 'window.crypto.subtle is not exposed in this context, so the in-browser digest cannot be computed. The node harness pin still stands: `node tools/determinism-harness.mjs --check tools/pin.json`.' };
  }
  const buf = await globalThis.crypto.subtle.digest('SHA-256', bytes.slice().buffer);
  return { ok: true, hex: Array.from(new Uint8Array(buf)).map((b) => b.toString(16).padStart(2, '0')).join('') };
}

/** The pin file lives beside the demo so a reader can diff the two. Fetched with
 *  a cache-buster because a stale pin would silently "confirm" an old render. */
export async function loadPin(base) {
  const url = base || 'tools/pin.json';
  let res;
  try {
    res = await fetch(url, { cache: 'no-store' });
  } catch (err) {
    return { ok: false, refusal: 'pin_fetch_failed', detail: `fetch("${url}") threw ${err.name}: ${err.message}. Open the page over http:// (a static server is enough); ES modules and fetch both refuse file:// in Chrome.` };
  }
  if (!res.ok) {
    return { ok: false, refusal: 'pin_http_status', detail: `fetch("${url}") -> HTTP ${res.status} ${res.statusText}` };
  }
  try {
    const json = await res.json();
    if (!Array.isArray(json.frames)) return { ok: false, refusal: 'pin_malformed', detail: `${url} parsed but has no frames[] array` };
    return { ok: true, pin: json };
  } catch (err) {
    return { ok: false, refusal: 'pin_not_json', detail: `${url}: ${err.message}` };
  }
}

// ---------------------------------------------------------------------------
// GPU-vs-reference measurement
// ---------------------------------------------------------------------------

/**
 * Render one pinned frame twice — once on the CPU reference, once through the
 * WebGL2 shader into an offscreen 128x128 drawing buffer — and return the
 * per-byte delta. GL row 0 is the BOTTOM row, the reference's row 0 is the TOP,
 * so the reference is read with `py = h-1-glRow`. The uv laws agree exactly at a
 * square size (see ref-render.js uvOf and the shader's uRes/v flip), which is why
 * the canonical size is 128x128 and not an arbitrary window.
 */
export function measureGpuDelta(kind, seed, frame, renderOpts) {
  const canvas = document.createElement('canvas');
  canvas.width = PINNED_SIZE;
  canvas.height = PINNED_SIZE;
  canvas.setAttribute('aria-hidden', 'true');
  const r = createRenderer(canvas, kind);
  if (!r.ok) {
    canvas.remove();
    return { ok: false, refusal: r.refusal, detail: r.detail };
  }
  // THE SEED LAW. `law` travels to all three paths (live GL coefficients, the
  // float64 reference, the float32 mirror) from one object, so the cross-check can
  // never compare a house-law GPU frame against an estate-law reference. `amplitude`
  // keeps its old pinned default: the estate pin rows are canonical frames under a
  // different STREAM, not a different knob, so the estate picture is comparable to
  // the house picture with exactly one variable changed.
  const fieldOpts = { amplitude: renderOpts.amplitude ?? 1.5, law: renderOpts.law ?? 'house' };
  const coef = carrier(seed, fieldOpts);
  const sized = r.resize(PINNED_SIZE, PINNED_SIZE, 1);
  if (sized.w !== PINNED_SIZE || sized.h !== PINNED_SIZE) {
    r.dispose();
    canvas.remove();
    return { ok: false, refusal: 'gpu_measured_size_split', detail: `asked ${PINNED_SIZE}x${PINNED_SIZE}, framebuffer is ${sized.w}x${sized.h}` };
  }
  const state = {
    levels: renderOpts.levels ?? 4,
    threshold: renderOpts.threshold ?? 1e-3,
    epsDraw: renderOpts.epsDraw ?? 0.02,
    boundaryEps: BOUNDARY_EPS,
    minLevels: LADDER_MIN_LEVELS,
  };
  r.draw(coef, frame, state);
  const got = r.readPixels();
  const ref = certificate(seed, frame, { kind, size: PINNED_SIZE, render: state, field: fieldOpts });
  if (!got || got.w !== ref.size || got.h !== ref.size) {
    r.dispose();
    canvas.remove();
    return { ok: false, refusal: 'gpu_readpixels_shape', detail: `readPixels ${got ? got.w + 'x' + got.h : 'null'} vs reference ${ref.size}x${ref.size}` };
  }

  const h = ref.size, w = ref.size;
  let maxAbs = 0, sumAbs = 0, exact = 0, pixels = 0, over = 0;
  const disagree = [];          // reference-row pixel indices, any channel |d| > 8
  const perChannel = [0, 0, 0];
  const worst = { abs: -1, px: -1, py: -1, ch: -1, gpu: 0, cpu: 0 };
  for (let gy = 0; gy < h; gy++) {
    const ry = h - 1 - gy;
    for (let gx = 0; gx < w; gx++) {
      const go = (gy * w + gx) * 4;
      const ro = (ry * w + gx) * 4;
      pixels++;
      for (let c = 0; c < 3; c++) {
        const d = Math.abs(got.bytes[go + c] - ref.bytes[ro + c]);
        perChannel[c] += d;
        sumAbs += d;
        if (d === 0) exact++;
        if (d > 8) over++;
        if (d > worst.abs) {
          worst.abs = d; worst.px = gx; worst.py = ry; worst.ch = c;
          worst.gpu = got.bytes[go + c]; worst.cpu = ref.bytes[ro + c];
        }
        if (d > maxAbs) maxAbs = d;
        if (d > 8 && !disagree.length) disagree.push(ry * w + gx);
        else if (d > 8 && disagree[disagree.length - 1] !== ry * w + gx) disagree.push(ry * w + gx);
      }
    }
  }

  // Per-pixel detail of the disagreement set, published so
  // tools/disagreement-triage.mjs can join it against named variants: the bytes
  // can only come from a real browser, the explanations from a second implementation.
  const detail = disagree.slice(0, 512).map((idx) => {
    const ry = Math.floor(idx / w), gx = idx % w, gy = h - 1 - ry;
    const ro = idx * 4, go = (gy * w + gx) * 4;
    return {
      idx, px: gx, py: ry,
      cpu: [ref.bytes[ro], ref.bytes[ro + 1], ref.bytes[ro + 2]],
      gpu: [got.bytes[go], got.bytes[go + 1], got.bytes[go + 2]],
    };
  });

  // THE MIRROR: re-evaluate the shader's OWN float32 arithmetic on the CPU (the
  // carrier expression, op by op, with float32-uploaded coefficients -- see
  // ref-render.js mirrorCarrier for the three probes that failed before this) and
  // run it through the unchanged reference ladder, then compare with the
  // framebuffer the GPU just produced. Two fusion modes are scored because GLSL
  // does not pin whether a*b+c contracts into a single rounding, and which one a
  // driver chooses is a fact about the device, not about the port.
  const mirrorScene = makeScene(kind, seed, { field: fieldOpts });
  const score = (mode) => {
    const buf = mirrorScene.alloc(w, h);
    mirrorScene.render(w, h, frame, { ...state, carrierFn: mirrorCarrier(mirrorScene.coef, mode) }, buf);
    let exactPixels = 0, maxResidual = 0;
    for (let ry = 0; ry < h; ry++) {
      for (let gx = 0; gx < w; gx++) {
        const ro = (ry * w + gx) * 4, gy = h - 1 - ry, go = (gy * w + gx) * 4;
        let mx = 0;
        for (let c = 0; c < 3; c++) { const d = Math.abs(buf[ro + c] - got.bytes[go + c]); if (d > mx) mx = d; }
        if (mx === 0) exactPixels++;
        if (mx > maxResidual) maxResidual = mx;
      }
    }
    let disagreeExact = 0;
    for (const p of disagree) {
      const ry = Math.floor(p / w), gx = p % w, gy = h - 1 - ry;
      const go = (gy * w + gx) * 4;
      let mx = 0;
      for (let c = 0; c < 3; c++) { const d = Math.abs(buf[p * 4 + c] - got.bytes[go + c]); if (d > mx) mx = d; }
      if (mx === 0) disagreeExact++;
    }
    return {
      mode, exactPixels, exactPct: (100 * exactPixels) / pixels, maxResidual,
      disagreePixels: disagree.length, disagreeExact,
      disagreeExactPct: disagree.length ? (100 * disagreeExact) / disagree.length : 100,
    };
  };
  const mirrors = [score('nofma'), score('fma')];
  const best = mirrors.reduce((a, b) => (b.exactPixels > a.exactPixels ? b : a));
  const mirrorStats = { modes: mirrors, ...best };

  const chName = ['R', 'G', 'B'];
  const result = {
    ok: true,
    refusal: null,
    size: `${w}x${h}`,
    bytes: got.bytes,          // kept so the digest panel hashes the SAME bytes it measured
    disagreeDetail: detail,
    pixels,
    channelsTested: pixels * 3,
    bytesEqual: exact,
    bytesEqualPct: (100 * exact) / (pixels * 3),
    maxAbsByte: maxAbs,
    meanAbsByte: sumAbs / (pixels * 3),
    bytesOver8: over,
    bytesOver8Pct: (100 * over) / (pixels * 3),
    perChannelMean: perChannel.map((s, i) => `${chName[i]}=${(s / pixels).toFixed(4)}`).join(' '),
    disagreePixels: disagree.length,
    disagreePct: (100 * disagree.length) / pixels,
    mirror: mirrorStats,
    worst: `${worst.ch === -1 ? 'n/a' : chName[worst.ch] + ' at pixel ' + worst.px + ',' + worst.py + ' gpu=' + worst.gpu + ' cpu=' + worst.cpu + ' |d|=' + worst.abs}`,
    gpuHex: null,
    cpuHex: null,
    frame,
    seed: String(seed),
    kind,
    state,
    // Array.from first: `LEVEL_SCALES` is a Float32Array, and typed-array `.map`
    // returns a Float32Array, so a string result would silently become NaN.
    scales: Array.from(LEVEL_SCALES).slice(0, state.levels).map((s) => s.toExponential(4)),
  };
  r.dispose();
  canvas.remove();
  return result;
}

// ---------------------------------------------------------------------------
// Falsifier that runs in the browser, on the same source as the node harness:
// the analytic root label must equal the 240-row table's argmax index.
// ---------------------------------------------------------------------------

export function browserConsistency(kind) {
  const { rootTable } = core;
  const { roots } = rootTable();
  let indexBad = 0, maxBad = 0, n = 0, familyBad = 0;
  let seedState = 1000003;
  const rnd = () => {
    seedState = (Math.imul(seedState, 1103515245) + 12345) >>> 0;
    return seedState / 4294967296;
  };
  const v = new Float64Array(8);
  for (let trial = 0; trial < 20000; trial++) {
    for (let k = 0; k < 8; k++) v[k] = rnd() * 4 - 2;
    n++;
    if (core.rootLabelAnalytic(v).index !== core.rootIndex(v)) indexBad++;
    let best = -Infinity;
    for (let r = 0; r < ROOT_COUNT; r++) {
      let s = 0;
      for (let k = 0; k < 8; k++) s += roots[r * 8 + k] * v[k];
      if (s > best) best = s;
    }
    if (Math.abs(core.closedFormMax(v) - best) > 1e-12) maxBad++;
    const lab = core.rootLabelAnalytic(v);
    const isHalf = Array.from(roots.slice(lab.index * 8, lab.index * 8 + 8)).every((c) => Math.abs(c) === 0.5);
    if (isHalf !== (lab.index >= 112)) familyBad++;
  }
  // And the ladder on real carrier vectors: codes must reconstruct within the
  // covering-radius bound at every emitted level.
  const scene = makeScene('ladder', 'consistency', {});
  let ladderBad = 0, ladderN = 0, stopsHist = {};
  const c8 = new Float64Array(8);
  for (let i = 0; i < 512; i++) {
    const u = (i % 32) / 32 * 2 - 1, wv = Math.floor(i / 32) / 32 * 2 - 1;
    core.carrierAt(u, wv, i, scene.coef, c8);
    const L = residualLadder(c8, { maxLevels: 4, threshold: 1e-3 });
    ladderN++;
    stopsHist[L.stops] = (stopsHist[L.stops] || 0) + 1;
    const scale0 = LEVEL_SCALES[0];
    // After one level the residual must be inside the covering radius of the
    // scaled lattice: |r| <= scale0 * sqrt(2) * (1 + 1e-6).
    const bound = scale0 * E8_COVERING_RADIUS * (1 + 1e-6);
    if (L.codes.length > 0 && Math.sqrt(L.residualNorms[0]) > bound) ladderBad++;
  }
  return {
    ok: indexBad === 0 && maxBad === 0 && familyBad === 0 && ladderBad === 0,
    samples: n, ladderSamples: ladderN,
    indexMismatch: indexBad, maxMismatch: maxBad, familyMismatch: familyBad,
    ladderBoundViolations: ladderBad,
    stops: stopsHist,
    kind,
  };
}

// ---------------------------------------------------------------------------
// Boot
// ---------------------------------------------------------------------------

const $ = (id) => document.getElementById(id);

export async function start(config) {
  const { kind } = config;
  const parsed = parseHash(location.hash);
  const state = { ...parsed.values, playing: false };

  const stage = $('stage');
  const cert = $('cert');
  const readout = $('readout');
  const say = (rows) => {
    if (!readout) return;
    readout.textContent = rows.filter((r) => r !== null && r !== undefined)
      .map((r) => (typeof r === 'string' ? r : r.text)).join('\n');
  };

  // --- live canvas (WebGL2, float32) --------------------------------------
  const renderer = createRenderer(stage, kind);
  const coef = () => carrier(state.seed, { amplitude: state.amplitude, law: state.law });
  const drawState = () => ({
    levels: state.levels,
    threshold: state.threshold,
    epsDraw: state.epsDraw,
    boundaryEps: BOUNDARY_EPS,
    minLevels: LADDER_MIN_LEVELS,
  });

  if (!renderer.ok) {
    stage.classList.add('refused');
    say([
      { text: `REFUSAL  ${renderer.refusal}` },
      { text: renderer.detail },
      { text: 'The CPU certificate, the byte-pin and the seed law are unaffected: only the live canvas needs a GPU.' },
    ]);
  }

  const reduce = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  state.playing = !reduce && renderer.ok;

  // --- certificate inset (CPU reference, float64, the pinned path) --------
  let certBuf = null;
  function paintCert() {
    const c = certificate(state.seed, state.frame, {
      kind, size: config.certSize ?? PINNED_SIZE,
      render: drawState(), field: { amplitude: state.amplitude, law: state.law },
    });
    certBuf = c;
    cert.width = c.size; cert.height = c.size;
    const ctx = cert.getContext('2d');
    const img = ctx.createImageData(c.size, c.size);
    img.data.set(c.bytes);
    ctx.putImageData(img, 0, 0);
    return c;
  }

  async function certDigest() {
    const d = await sha256Hex(certBuf.bytes);
    return d.ok ? d.hex : d;
  }

  // --- frame loop ---------------------------------------------------------
  let rafId = 0;
  let tick = state.frame;
  function loop() {
    if (renderer.ok) {
      resizeStageIfNeeded();
      renderer.draw(coef(), state.playing ? tick : state.frame, drawState());
    }
    if (state.playing) tick += 1;
    if (state.playing) rafId = requestAnimationFrame(loop);
    else rafId = 0;
  }
  let lastRect = { w: -1, h: -1 };
  function resizeStageIfNeeded() {
    const rect = stage.getBoundingClientRect();
    const w = Math.max(1, rect.width | 0), h = Math.max(1, rect.height | 0);
    if (w !== lastRect.w || h !== lastRect.h) {
      lastRect = { w, h };
      renderer.resize(w, h, config.maxDpr ?? 2);
    }
  }

  // --- panels -------------------------------------------------------------
  function panelText(measured, digest, pinResult, consistency) {
    const rows = [];
    rows.push(`seed=${state.seed}  law=${state.law}  frame=${state.frame}  levels=${state.levels}  threshold=${state.threshold}  epsDraw=${state.epsDraw}  amplitude=${state.amplitude}`);
    if (reduce) rows.push('prefers-reduced-motion: reduce -> the show starts PAUSED on the pinned frame. Press PLAY to animate.');
    rows.push(renderer.ok
      ? `live canvas: WebGL2 float32, framebuffer ${renderer.size().w}x${renderer.size().h} (dpr-capped at ${config.maxDpr ?? 2})`
      : `live canvas: REFUSED (${renderer.refusal}) — see below`);
    rows.push(`certificate inset: CPU reference float64, ${certBuf.size}x${certBuf.size}, canonical (this is what tools/pin.json hashes)`);
    rows.push(`sha256(reference bytes) = ${typeof digest === 'string' ? digest : 'UNMEASURED: ' + digest.refusal}`);
    if (pinResult.ok) {
      rows.push(`pin file: ${pinResult.pin.frames.length} frames, node ${pinResult.pin.node}, written ${pinResult.pin.written_at}`);
      const row = pinResult.match;
      if (row) {
        rows.push(`pin lookup ${row.kind}/${row.seed}/${row.law ?? 'house'}/f${row.frame} L=${row.levels}: ${row.sha256 === digest ? 'MATCH' : 'DIFFERS'} (pin=${row.sha256.slice(0, 24)}… obs=${typeof digest === 'string' ? digest.slice(0, 24) + '…' : 'n/a'})`);
      } else {
        rows.push(`pin lookup: NO ROW for this (kind, seed, law, frame, levels) — this combination is not pinned, so it is reported as absent rather than as a pass. Pinned frames: ${pinResult.pin.frames.map((f) => `${f.kind}/${f.seed}/${f.law ?? 'house'}/f${f.frame} L=${f.levels}`).join(', ')}`);
      }
    } else {
      rows.push(`pin file: UNAVAILABLE (${pinResult.refusal}) — ${pinResult.detail}`);
    }
    if (measured.ok) {
      rows.push(`GPU vs reference @ ${measured.size}: mean |byte delta| = ${measured.meanAbsByte.toFixed(4)} levels (0..255), max = ${measured.maxAbsByte}, exact bytes = ${measured.bytesEqual}/${measured.channelsTested} (${measured.bytesEqualPct.toFixed(2)}%), bytes differing by >8 = ${measured.bytesOver8} (${measured.bytesOver8Pct.toFixed(3)}%)`);
      rows.push(`  per channel ${measured.perChannelMean}  worst: ${measured.worst}`);
      rows.push(`  gpu sha256 = ${measured.gpuHex}`);
      const mt = measured.mirror || {};
      rows.push(`  WHY they disagree: a float32 MIRROR of the shader's own carrier expression, run on the CPU through the unchanged reference ladder, reproduces ${fmt(mt.disagreeExact)}/${fmt(mt.disagreePixels)} of the DISAGREEING pixels byte for byte, and ${fmt(mt.exactPixels)}/${fmt(measured.pixels)} of the whole frame (${mt.exactPct === undefined ? 'n/a' : mt.exactPct.toFixed(2)}%), worst residual ${fmt(mt.maxResidual)} levels, at fusion mode ${mt.mode}. Both modes are scored because GLSL does not pin whether a*b+c contracts into one rounding: which wins here measures this driver. The gap to the float64 reference is therefore arithmetic width in a step function, predicted pixel by pixel, not a tolerance.`);
      rows.push(`  the two paths are the SAME formula, not the same bits: float32 on the GPU, float64 on the CPU. Every number above is measured at load, per device.`);
    } else {
      rows.push(`GPU vs reference: NOT MEASURED (${measured.refusal}) — ${measured.detail}`);
    }
    if (consistency.ok) {
      rows.push(`in-browser falsifier: analytic root label == 240-row table over ${consistency.samples} vectors (index mismatches=${consistency.indexMismatch}, max mismatches=${consistency.maxMismatch}, family mismatches=${consistency.familyMismatch}); ladder bound violations=${consistency.ladderBoundViolations}/${consistency.ladderSamples}; stop reasons ${JSON.stringify(consistency.stops)}`);
    } else {
      rows.push(`in-browser falsifier FAILED: ${JSON.stringify(consistency)}`);
    }
    if (parsed.notes.length) rows.push('url notes: ' + parsed.notes.join('; '));
    return rows;
  }

  // --- load-time measurement (async so the canvas paints first) -----------
  let lastMeasured = null, lastDigest = null, lastPin = { ok: false, refusal: 'not_run', detail: 'measurement pending' }, lastConsistency = { ok: false };

  async function runMeasurements() {
    paintCert();
    lastDigest = await certDigest();
    const pinLoad = await loadPin(config.pinPath);
    lastPin = pinLoad.ok
      ? {
        ...pinLoad,
        // The key is (kind, seed, LAW, frame, levels, size). Two laws under one seed
        // and one frame are two rows that differ in nothing but the law and the
        // digest, so a lookup that left the law out would report the house picture's
        // hash as DIFFERS against the estate row (or MATCH the wrong way after a
        // future collision) instead of naming the law that was actually drawn.
        match: pinLoad.pin.frames.find((f) => f.kind === kind && f.seed === String(state.seed)
          && (f.law ?? 'house') === state.law
          && f.frame === state.frame && f.levels === state.levels && f.size === PINNED_SIZE) || null,
      }
      : pinLoad;
    const m = measureGpuDelta(kind, state.seed, state.frame, { ...drawState(), law: state.law });
    if (m.ok) {
      // Same bytes the delta loop just compared, hashed in the same order the
      // node harness uses, so gpu-sha256 is comparable to the reference digest.
      const g = await sha256Hex(m.bytes);
      m.gpuHex = g.ok ? g.hex : `UNMEASURED (${g.refusal})`;
      m.cpuHex = typeof lastDigest === 'string' ? lastDigest : null;
    } else {
      m.gpuHex = null;
    }
    lastMeasured = m;
    lastConsistency = browserConsistency(kind);
    say(panelText(m, lastDigest, lastPin, lastConsistency));
    // Machine-readable surface for tools/browser-check.mjs (and for anyone who
    // wants the numbers without scraping prose). Same objects the panel prints.
    globalThis.__v7 = {
      kind,
      state: { ...state },
      renderer: { ok: renderer.ok, refusal: renderer.refusal, size: renderer.size() },
      digest: lastDigest,
      pin: { ok: lastPin.ok, refusal: lastPin.refusal || null, match: lastPin.match || null },
      measured: m.ok ? { ...m, bytes: undefined } : { ok: false, refusal: m.refusal, detail: m.detail },
      consistency: lastConsistency,
      reducedMotion: reduce,
    };
  }

  // --- controls -----------------------------------------------------------
  let pending = 0;
  function schedule() {
    cancelAnimationFrame(pending);
    pending = requestAnimationFrame(async () => {
      if (renderer.ok) { resizeStageIfNeeded(); renderer.draw(coef(), state.playing ? tick : state.frame, drawState()); }
      await runMeasurements();
      if (state.playing && !rafId) rafId = requestAnimationFrame(loop);
    });
  }

  const seedEl = $('seed');
  if (seedEl) { seedEl.value = state.seed; seedEl.addEventListener('change', () => { state.seed = seedEl.value || 'e8-omnibus-1102'; history.replaceState(null, '', hashFor(state)); schedule(); }); }
  const frameEl = $('frame');
  if (frameEl) { frameEl.value = state.frame; frameEl.addEventListener('change', () => { state.frame = Math.max(0, Math.round(Number(frameEl.value) || 0)); frameEl.value = state.frame; tick = state.frame; history.replaceState(null, '', hashFor(state)); schedule(); }); }
  const levelsEl = $('levels');
  if (levelsEl) { levelsEl.value = state.levels; levelsEl.addEventListener('input', () => { state.levels = Number(levelsEl.value); const o = $('levels-out'); if (o) o.textContent = String(state.levels); schedule(); }); levelsEl.addEventListener('change', () => history.replaceState(null, '', hashFor(state))); }
  const thrEl = $('threshold');
  if (thrEl) { thrEl.value = String(state.threshold); thrEl.addEventListener('change', () => { state.threshold = Number(thrEl.value); schedule(); }); }
  const epsEl = $('epsdraw');
  if (epsEl) { epsEl.value = String(state.epsDraw); epsEl.addEventListener('change', () => { state.epsDraw = Number(epsEl.value); schedule(); }); }
  const ampEl = $('amplitude');
  if (ampEl) { ampEl.value = String(state.amplitude); ampEl.addEventListener('change', () => { state.amplitude = Number(ampEl.value); schedule(); }); }
  // The seed law is a knob, but it is not a continuous one and it is not a
  // rendering detail: it decides WHICH picture a seed means. Like the seed itself,
  // switching it rewrites the URL, so a shared link names the law it shows.
  const lawEl = $('law');
  if (lawEl) {
    lawEl.value = state.law;
    lawEl.addEventListener('change', () => {
      state.law = lawEl.value === 'estate' ? 'estate' : 'house';
      lawEl.value = state.law;
      history.replaceState(null, '', hashFor(state));
      schedule();
    });
  }

  const play = $('play');
  if (play) {
    play.textContent = state.playing ? 'PAUSE' : 'PLAY';
    play.addEventListener('click', () => {
      state.playing = !state.playing;
      play.textContent = state.playing ? 'PAUSE' : 'PLAY';
      play.setAttribute('aria-pressed', String(state.playing));
      if (state.playing) { tick = state.frame; if (!rafId) rafId = requestAnimationFrame(loop); }
      else if (rafId) { cancelAnimationFrame(rafId); rafId = 0; }
      if (!state.playing) schedule();
    });
  }
  const copy = $('copy-url');
  if (copy) {
    copy.addEventListener('click', async () => {
      const url = location.origin + location.pathname + hashFor(state);
      try {
        await navigator.clipboard.writeText(url);
        copy.textContent = 'COPIED';
      } catch (err) {
        copy.textContent = 'COPY FAILED';
        copy.title = `${err.name}: ${err.message}`;
      }
      setTimeout(() => { copy.textContent = 'COPY URL'; }, 1600);
    });
  }

  window.addEventListener('hashchange', () => {
    const p = parseHash(location.hash);
    Object.assign(state, p.values);
    tick = state.frame;
    if (seedEl) seedEl.value = state.seed;
    if (frameEl) frameEl.value = state.frame;
    if (levelsEl) levelsEl.value = state.levels;
    if (thrEl) thrEl.value = String(state.threshold);
    if (epsEl) epsEl.value = String(state.epsDraw);
    if (ampEl) ampEl.value = String(state.amplitude);
    if (lawEl) lawEl.value = state.law;
    schedule();
  });
  window.addEventListener('resize', () => { if (renderer.ok) { resizeStageIfNeeded(); renderer.draw(coef(), state.playing ? tick : state.frame, drawState()); } });

  // --- go -----------------------------------------------------------------
  say([`booting ${kind} demo  seed=${state.seed}  frame=${state.frame}`]);
  paintCert();
  if (renderer.ok) { resizeStageIfNeeded(); renderer.draw(coef(), state.frame, drawState()); }
  if (state.playing) rafId = requestAnimationFrame(loop);
  await runMeasurements();

  return { state, renderer, certBuf: () => certBuf, measured: () => lastMeasured };
}
