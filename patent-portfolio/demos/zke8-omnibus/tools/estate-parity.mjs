/**
 * estate-parity.mjs — check the browser port against the estate's OWN outputs.
 *
 * Reads `estate-e8.json` (dumped by dump_estate_e8.py, which imports
 * kagami_math.dimensions.generate_e8_roots, kagami.core.digest.e8_period_codec.
 * E8PeriodCodec.root_index, kagami_math.e8_lattice_quantizer.nearest_e8 and
 * kagami_math.e8_lattice_protocol.ResidualE8LatticeVQ) and compares, element by
 * element, against js/e8-core.js.
 *
 * rc 0 = every asserted equality holds. rc 1 = at least one failed.
 * Prints counts, never a bare pass.
 */
import { readFileSync } from 'node:fs';
import path from 'node:path';
import {
  buildE8Roots,
  rootIndex,
  closedFormMax,
  nearestE8,
  residualLadder,
  levelScale,
  levelScaleRaw,
  LADDER_DECAY,
  classQ,
  doubledCoords,
  normClass,
  rootTable,
  rootLabelAnalytic,
  pairRank,
  rankEvenPopcount,
  popcountEven,
} from '../js/e8-core.js';

const HERE = path.dirname(new URL(import.meta.url).pathname);
const data = JSON.parse(readFileSync(path.join(HERE, 'estate-e8.json'), 'utf8'));

const fails = [];
const note = (label, pass, detail) => {
  console.log(`${pass ? 'PASS' : 'FAIL'}  ${label}${detail ? '  ' + detail : ''}`);
  if (!pass) fails.push(label);
};

// --- 1. the 240-row root table, row order included -------------------------
{
  const { roots } = buildE8Roots();
  let bad = 0;
  let firstBad = null;
  for (let r = 0; r < 240; r++) {
    for (let k = 0; k < 8; k++) {
      if (roots[r * 8 + k] !== data.roots[r][k]) {
        bad++;
        if (firstBad === null) firstBad = `row ${r} lane ${k}: js ${roots[r * 8 + k]} vs estate ${data.roots[r][k]}`;
      }
    }
  }
  note('roots table 240x8 elementwise identical (order included)', bad === 0, `mismatches=${bad}${firstBad ? ' first=' + firstBad : ''}`);
}

// --- 2. root_index over 512 vectors ---------------------------------------
{
  let bad = 0;
  const firsts = [];
  const closedBad = [];
  data.vectors.forEach((v, i) => {
    const js = rootIndex(v);
    if (js !== data.root_index[i]) {
      bad++;
      if (firsts.length < 3) firsts.push(`#${i} js=${js} estate=${data.root_index[i]} v=[${v.slice(0, 3).join(',')},...]`);
    }
    // closed form must equal the table maximum value.
    const { roots } = rootTable();
    let best = -Infinity;
    for (let r = 0; r < 240; r++) {
      let s = 0;
      for (let k = 0; k < 8; k++) s += roots[r * 8 + k] * v[k];
      if (s > best) best = s;
    }
    const cf = closedFormMax(v);
    if (Math.abs(cf - best) > 1e-12) closedBad.push(`#${i} cf=${cf} table=${best}`);
  });
  note('root_index identical to E8PeriodCodec.root_index over 512 vectors', bad === 0, `mismatches=${bad}${firsts.length ? ' e.g. ' + firsts.join(' | ') : ''}`);
  note('closedFormMax == table argmax value over 512 vectors', closedBad.length === 0, `mismatches=${closedBad.length}${closedBad.length ? ' e.g. ' + closedBad[0] : ''}`);
}

// --- 3. nearest_e8 vs the torch quantizer ---------------------------------
{
  let agree = 0, boundary = 0, differ = 0, exactDelta = 0;
  const examples = [];
  let maxDelta = 0;
  // The default tie rule must match the protocol leg it feeds.
  data.vectors.forEach((v, i) => {
    const hit = nearestE8(v);
    if (hit.boundary) boundary++;
    const e = data.nearest_e8[i];
    let d = 0;
    for (let k = 0; k < 8; k++) d = Math.max(d, Math.abs(hit.q[k] - e[k]));
    maxDelta = Math.max(maxDelta, d);
    if (d === 0) agree++;
    else {
      differ++;
      if (examples.length < 4) examples.push(`#${i} d=${d.toFixed(6)} js=[${Array.from(hit.q).join(',')}] estate=[${e.join(',')}]`);
    }
  });
  note('nearest_e8 is BIT-identical to torch nearest_e8 over all 512 vectors (keepD8 leg)', differ === 0,
    `bitagree=${agree} exact_boundary_cases=${boundary} differs=${differ} maxDelta=${maxDelta}${examples.length ? ' e.g. ' + examples[0] : ''}`);
  // The provider-kernel leg must refuse exactly the boundary cases and agree elsewhere.
  let refused = 0, kept = 0, refuseMismatch = 0;
  data.vectors.forEach((v) => { const h = nearestE8(v, { tieBreak: 'refuse' }); if (h.status === 6) refused++; else kept++; });
  note("tieBreak:'refuse' reproduces the provider kernel's typed status 6", refused === boundary && kept === 512 - boundary,
    `refused=${refused} kept=${kept} boundary_count=${boundary} inconsistent=${refuseMismatch}`);
  let inE8 = 0, notInE8 = 0;
  data.vectors.forEach((v) => { const h = nearestE8(v); (classQ(doubledCoords(h.q)) === null ? notInE8++ : inE8++); });
  note('every emitted nearest point is an E8 point (q computable => in the lattice)', notInE8 === 0, `in_e8=${inE8} not_in_e8=${notInE8}`);
}

// --- 4. the residual ladder -----------------------------------------------
{
  let reconBad = 0, codeBad = 0, levelBad = 0, maxReconDelta = 0;
  const levelEx = [];
  data.ladder.per_vector_codes.forEach((estateCodes, i) => {
    const v = data.vectors[i];
    const l = residualLadder(v, { threshold: data.config.residual_threshold });
    if (l.codes.length !== estateCodes.length) {
      levelBad++;
      if (levelEx.length < 4) levelEx.push(`#${i} js=${l.codes.length} estate=${estateCodes.length}`);
    }
    const n = Math.min(l.codes.length, estateCodes.length);
    // Negative control: comparing only over min(len) made a zero-level port pass
    // the code assertion vacuously (measured on the first run: 18 vectors where
    // this port emitted 0 levels and the estate 3 still read "codes identical").
    // Lengths must agree before codes are allowed to count.
    let same = l.codes.length === estateCodes.length;
    for (let j = 0; j < n && same; j++) for (let k = 0; k < 8; k++) if (l.codes[j][k] !== estateCodes[j][k]) same = false;
    if (!same) codeBad++;
    // Compare against the batch-of-ONE reconstruction, not the batch-of-512 one:
    // the protocol's adaptive stop is batch-wide (torch.all over the batch,
    // e8_lattice_protocol.py:310-315), so the 512-vector run emits L=4 for every
    // vector and a per-vector port can never match that array. This is a
    // harness-leg correction found by running it, not a port defect.
    let d = 0;
    for (let k = 0; k < 8; k++) d = Math.max(d, Math.abs(l.q[k] - data.ladder.per_vector_recon[i][k]));
    maxReconDelta = Math.max(maxReconDelta, d);
    if (d > 0) reconBad++;
  });
  note(`ladder per-vector level counts match a batch-of-one estate run (first ${data.ladder.per_vector_codes.length} vectors)`, levelBad === 0, `mismatch=${levelBad}${levelEx.length ? ' e.g. ' + levelEx.join(' | ') : ''}`);
  note('ladder half-step CODES identical to the estate codes', codeBad === 0, `mismatch=${codeBad}`);
  note('ladder reconstruction BIT-identical to the estate batch-of-one output', reconBad === 0, `over=${reconBad} maxDelta=${maxReconDelta}`);
  const rawOk = data.ladder.level_scales.every((s, i) => s === levelScaleRaw(i));
  const usedOk = data.ladder.level_scales_used.every((s, i) => s === levelScale(i));
  note('raw float32 level-scale buffer matches (unclamped)', rawOk, '');
  note('use-site clamped level scales match (clamp min=1e-6)', usedOk, `first clamped index=${data.ladder.level_scales.findIndex((s) => s < Math.fround(1e-6))}`);
  console.log(`      estate batch-wide L was ${data.ladder.levels} for all 512; per-vector L: ${JSON.stringify(data.ladder.per_vector_levels.slice(0, 12))}...`);
}

// --- 5. the f2_8 class partition on the emitted codewords -----------------
{
  const hist = { zero: 0, root: 0, singular: 0, undeclared: 0 };
  let rows = 0;
  data.vectors.forEach((v) => {
    const l = residualLadder(v, { maxLevels: 4 });
    l.codes.forEach((c) => {
      rows++;
      const y = new Float64Array(8);
      for (let k = 0; k < 8; k++) y[k] = c[k] / 2;
      hist[normClass(doubledCoords(y))]++;
    });
  });
  console.log(`      f2_8 class histogram over ${rows} emitted codewords: ${JSON.stringify(hist)}`);
  console.log(`      declared partition (e8_alphabet.py:110-120): 1 zero + 135 singular + 120 root = 256 classes`);
  note('emitted codewords all carry a declared class', hist.undeclared === 0, `undeclared=${hist.undeclared}`);
}

// --- 6. the analytic root label vs the 240-row table ----------------------
//
// This is the GPU-feasibility leg: a shader cannot afford 240 dot products per
// pixel (~1920 FMAs), so `rootLabelAnalytic` re-derives the SAME index from |v|
// in one pass. That is only worth shipping if it is provably the estate's index,
// so the assertion is equality with the table leg (and with the estate's own
// root_index) over every sample, with adversarial tie cases included because
// ties are where a closed form breaks.
{
  // 6a. the two ranking helpers, brute-forced against the enumeration itself.
  const { roots } = rootTable();
  let pairBad = 0;
  for (let i = 0; i < 8; i++) {
    for (let j = i + 1; j < 8; j++) {
      // Read the row off the table: the first type-1 row whose nonzero lanes are i,j.
      let expect = -1;
      for (let r = 0; r < 112; r++) {
        let nz = [];
        for (let k = 0; k < 8; k++) if (roots[r * 8 + k] !== 0) nz.push(k);
        if (nz.length === 2 && nz[0] === i && nz[1] === j) { expect = Math.floor(r / 4); break; }
      }
      if (expect !== pairRank(i, j)) pairBad++;
    }
  }
  note('pairRank matches the table pair order over all 28 pairs', pairBad === 0, `mismatches=${pairBad}`);

  // The domain of rankEvenPopcount is the even-popcount bit patterns, in
  // ascending order — that IS the enumeration (dimensions.py:262-266). Built
  // here by an independent count so the exported predicate is checked against
  // something other than itself.
  const evenBits = [];
  let domainBad = 0;
  for (let b = 0; b < 256; b++) {
    let pop = 0;
    for (let k = 0; k < 8; k++) if ((b >> k) & 1) pop++;
    if ((pop % 2 === 0) !== popcountEven(b)) domainBad++;
    if (pop % 2 === 0) evenBits.push(b);
  }

  let rankBad = 0;
  const seen = new Set();
  let rr = 0;
  for (const b of evenBits) {
    const got = rankEvenPopcount(b);
    if (got !== rr) rankBad++;
    if (seen.has(got)) rankBad++;
    seen.add(got);
    rr++;
  }
  // The odd-popcount patterns are OUT OF DOMAIN — the enumeration skips them
  // (dimensions.py:262-266), so there is nothing for rank() to return and no
  // assertion here about them. An earlier revision of this check asserted they
  // should read 0, which is not a property the function claims; it produced a
  // false FAIL for 128 patterns and no true information.
  note('rankEvenPopcount is the exact ascending rank over the 128 even-popcount patterns', rankBad === 0 && evenBits.length === 128 && seen.size === 128 && domainBad === 0,
    `mismatches=${rankBad} counted=${rr} distinct=${seen.size} predicate_vs_independent_count=${domainBad}`);

  // 6b. family / index equality against the table leg.
  const samples = [];
  data.vectors.forEach((v) => samples.push(Array.from(v)));
  // Deterministic extras: dense random, exact ties, zeros, duplicates.
  let s = 88172645463325252n;
  const rnd = () => { s = (s * 6364136223846793005n + 1442695040888963407n) & ((1n << 64n) - 1n); return Number(s >> 32n) / 4294967296; };
  for (let n = 0; n < 200000; n++) {
    const v = new Array(8);
    for (let k = 0; k < 8; k++) v[k] = rnd() * 4 - 2;
    samples.push(v);
  }
  // Tie-dense probes: a 6^3 grid of repeated magnitudes placed on the lanes, so
  // two and three lanes share |v| exactly. This is where a closed form and a
  // table scan actually disagree, if they do.
  {
    const steps = [-2, -1, -0.5, 0, 0.5, 1, 2];
    for (const a of steps) for (const b of steps) for (const c of steps) {
      samples.push([a, b, c, a, b, c, 0, 0]);
      samples.push([a, a, b, b, c, c, 0, 0]);
      samples.push([a, b, a, b, a, b, c, 0]);
    }
    // Every root, negated and slightly scaled: the max is attained ON the shell.
    const { roots } = rootTable();
    for (let r = 0; r < 240; r++) {
      const row = Array.from(roots.slice(r * 8, r * 8 + 8));
      samples.push(row, row.map((x) => -x), row.map((x) => x * 1.0000001), row.map((x) => x * 3));
    }
  }
  const adversarial = [
    [0, 0, 0, 0, 0, 0, 0, 0],                 // zero vector -> table convention index 0
    [1, 1, 1, 1, 1, 1, 1, 1],                 // all lanes tie; odd negatives = 0
    [-1, -1, -1, -1, -1, -1, -1, -1],         // 8 negatives (even) -> half shell wins
    [-1, -1, -1, -1, -1, -1, -1, 0],          // 7 negatives (odd), min at a zero lane
    [1, 1, 0, 0, 0, 0, 0, 0],                 // type1 == type2 exactly
    [2, 2, 2, 0, 0, 0, 0, 0],                 // three-way max tie
    [0.5, 0.5, -0.5, -0.5, 0.5, 0.5, -0.5, 0.5], // a root itself
    [-3, -3, -3, -3, -3, -3, -3, -3],         // odd negatives, all minima tied (the scan-order bug)
    [1, -1, 1, -1, 1, -1, 1, -2],             // unique min at the last lane
    [1e-9, 1, 1, 1, 1, 1, 1, 1],              // near-degenerate min
  ];
  for (let n = 0; n < 40; n++) {
    const v = new Array(8).fill(1);
    v[n % 8] = -1;                             // one negative, all-tie minima
    samples.push(v);
  }
  adversarial.forEach((v) => samples.push(v));

  let idxBad = 0, valBad = 0, famBad = 0, estateBad = 0, zeroCases = 0, tieCases = 0;
  const examples = [];
  samples.forEach((v, i) => {
    const lab = rootLabelAnalytic(v);
    const tbl = rootIndex(v);
    if (lab.index !== tbl) {
      idxBad++;
      if (examples.length < 6) examples.push(`#${i} analytic=${lab.index} table=${tbl} family=${lab.family} v=[${v.map((c) => c.toFixed ? c.toFixed(4) : c).join(',')}]`);
    }
    if (Math.abs(lab.value - closedFormMax(v)) > 0) valBad++;
    // Family must be a truthful statement about which shell holds the argmax.
    const row = new Array(8);
    for (let k = 0; k < 8; k++) row[k] = roots[lbl(lab.index) + k];
    if (lab.family === 0) tieCases++;
    const isHalf = Math.abs(row[0]) === 0.5;
    if (lab.family === 1 && isHalf) famBad++;
    if (lab.family === 2 && !isHalf) famBad++;
    if (i < data.vectors.length && lab.index !== data.root_index[i]) estateBad++;
    if (lab.index === 0 && v.every((c) => c === 0)) zeroCases++;
  });
  function lbl(ix) { return ix * 8; }

  note('rootLabelAnalytic index == table rootIndex over every sample', idxBad === 0,
    `samples=${samples.length} mismatches=${idxBad} shell_ties=${tieCases}${examples.length ? ' e.g. ' + examples[0] : ''}`);
  note('analytic value == closedFormMax (bitwise, not tolerance)', valBad === 0, `mismatches=${valBad}`);
  note('family label is consistent with the row it names', famBad === 0, `mismatches=${famBad}`);
  note('rootLabelAnalytic index == the ESTATE root_index over its own 512 vectors', estateBad === 0,
    `mismatches=${estateBad} zero_vector_rows_hit=${zeroCases}`);
  console.log('      disagreement detail (if any):');
  examples.slice(0, 6).forEach((e) => console.log(`        ${e}`));
}

console.log('');
if (fails.length) {
  console.log(`PARITY FAILURES (${fails.length}): ${fails.join(' | ')}`);
  process.exit(1);
}
console.log('PARITY: all assertions hold.');
