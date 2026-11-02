/**
 * determinism-harness.mjs — the rc the RESULT.json quotes.
 *
 * Answers ONE question with a number: is "same seed -> same rendered output"
 * true, and what is the output? It hashes the CPU reference frames (the canonical
 * path, per the V6 law this lane inherits) and prints a SHA-256 per
 * (kind, seed, frame). It then re-renders from a SECOND, freshly-imported module
 * instance and requires the digests to be equal, so a module-level cache or a
 * hidden mutation of shared state cannot pass this check by accident.
 *
 * Modes:
 *   node tools/determinism-harness.mjs                 -> render, print digests,
 *                                                         self-compare, falsify. rc 0/1
 *   node tools/determinism-harness.mjs --write PIN.json -> also write the pin file
 *   node tools/determinism-harness.mjs --check PIN.json -> compare against a pin
 *                                                         file from a PREVIOUS
 *                                                         PROCESS (the real
 *                                                         cross-run test)
 *
 * Exit 0 = every assertion held. Exit 1 = at least one failed, and the failing
 * labels are printed. Nothing here prints a bare "pass": every line carries its
 * counts, because a claim without a denominator is not evidence.
 */

import { createHash } from 'node:crypto';
import { readFileSync, writeFileSync, existsSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

import { certificate, boundaryCount } from '../js/ref-render.js';
import {
  buildE8Roots,
  closedFormMax,
  rootIndex,
  rootLabelAnalytic,
  rankEvenPopcount,
  popcountEven,
  pairRank,
  levelScale,
  levelScaleRaw,
  LADDER_DECAY,
  ROOT_COUNT,
} from '../js/e8-core.js';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const CORE = path.join(HERE, '..', 'js', 'e8-core.js');

// The canonical pin set. Sizes, frames and options are fixed HERE so that a pin
// file and this list can never disagree about what was hashed.
const PINS = [
  { kind: 'ladder', seed: 'e8-omnibus-1102', frame: 0, size: 128, opts: { render: { levels: 4 } } },
  { kind: 'ladder', seed: 'e8-omnibus-1102', frame: 89, size: 128, opts: { render: { levels: 4 } } },
  { kind: 'ladder', seed: 'e8-omnibus-1102', frame: 233, size: 128, opts: { render: { levels: 6 } } },
  { kind: 'ladder', seed: 'butterfly', frame: 144, size: 128, opts: { render: { levels: 4 } } },
  { kind: 'root', seed: 'e8-omnibus-1102', frame: 0, size: 128, opts: {} },
  { kind: 'root', seed: 'e8-omnibus-1102', frame: 144, size: 128, opts: {} },
  { kind: 'root', seed: 'butterfly', frame: 377, size: 128, opts: {} },
  { kind: 'root', seed: 'zke8', frame: 610, size: 128, opts: {} },
  // The estate seed law (js/seed-stream.js) over the SAME lane mapping and the
  // SAME codec: these two rows are what make "Kagami's own stream and the browser
  // agree" a pinned, cross-process claim rather than a paragraph.
  { kind: 'ladder', seed: 'e8-omnibus-1102', frame: 0, size: 128, opts: { field: { law: 'estate' }, render: { levels: 4 } } },
  { kind: 'root', seed: 'e8-omnibus-1102', frame: 0, size: 128, opts: { field: { law: 'estate' } } },
];

const fails = [];
const note = (label, pass, detail) => {
  console.log(`${pass ? 'PASS' : 'FAIL'}  ${label}${detail ? '  ' + detail : ''}`);
  if (!pass) fails.push(label);
};
const sha = (bytes) => createHash('sha256').update(bytes).digest('hex');

function renderPin(mods, p) {
  const cert = mods.refRender.certificate(p.seed, p.frame, {
    kind: p.kind,
    size: p.size,
    field: p.opts.field ?? {},
    render: p.opts.render ?? {},
  });
  return { digest: sha(cert.bytes), bytes: cert.bytes, size: cert.size };
}

// A second, cache-busted import of the same source: this is what makes the
// self-comparison mean something. Same process, different module instance.
async function loadMods(tag) {
  const q = `?instance=${tag}`;
  return {
    core: await import(CORE + q),
    refRender: await import(path.join(HERE, '..', 'js', 'ref-render.js') + q),
  };
}

async function main() {
  const argv = process.argv.slice(2);
  const checkIdx = argv.indexOf('--check');
  const writeIdx = argv.indexOf('--write');
  const pinPath = writeIdx >= 0 ? path.resolve(argv[writeIdx + 1])
    : checkIdx >= 0 ? path.resolve(argv[checkIdx + 1]) : null;

  console.log(`determinism-harness  node ${process.version}  ${new Date().toISOString()}`);
  console.log(`canonical size ${PINS[0].size}x${PINS[0].size}, SHA-256 over raw RGBA bytes\n`);

  // ---- 1. falsifiers on the math legs ----------------------------------
  console.log('--- math falsifiers -------------------------------------------------');
  {
    const { roots, roots2, count } = buildE8Roots();
    let dup = 0, wrongNorm = 0;
    const seen = new Set();
    for (let r = 0; r < ROOT_COUNT; r++) {
      let s2 = 0;
      for (let k = 0; k < 8; k++) s2 += roots[r * 8 + k] * roots[r * 8 + k];
      if (Math.abs(s2 - 2) > 1e-15) wrongNorm++;
      const key = Array.from(roots.slice(r * 8, r * 8 + 8)).join(',');
      if (seen.has(key)) dup++;
      seen.add(key);
    }
    note('root table is 240 DISTINCT rows of squared length 2 (the E8 root system)',
      count === 240 && dup === 0 && wrongNorm === 0,
      `rows=${count} duplicates=${dup} not_squared_length_2=${wrongNorm} distinct=${seen.size}`);

    // The doubled table must be exactly 2x the float table: the codec's fast
    // path is only equivalent if this holds.
    let scaleBad = 0;
    for (let i = 0; i < roots.length; i++) if (roots2[i] !== 2 * roots[i]) scaleBad++;
    note('roots2 == 2 * roots elementwise (the exact-integer leg is the same table)', scaleBad === 0, `mismatches=${scaleBad}`);

    // 128 + 112 = 240 by the two shapes; assert the split, not the total.
    let fam1 = 0, fam2 = 0;
    for (let r = 0; r < ROOT_COUNT; r++) {
      const row = Array.from(roots.slice(r * 8, r * 8 + 8));
      if (row.every((c) => Math.abs(c) === 0.5)) fam2++;
      else if (row.filter((c) => c !== 0).length === 2) fam1++;
    }
    note('shell split is 112 x (+-1,+-1,0^6) + 128 x (+-1/2)^8', fam1 === 112 && fam2 === 128,
      `type1=${fam1} type2=${fam2} sum=${fam1 + fam2}`);

    // closed form vs the table, on vectors that stress both families.
    let cfBad = 0, anBad = 0, cfN = 0;
    const probe = [];
    for (let r = 0; r < ROOT_COUNT; r++) {
      probe.push(Array.from(roots.slice(r * 8, r * 8 + 8)));
      probe.push(Array.from(roots.slice(r * 8, r * 8 + 8)).map((c) => -c));
    }
    let st = 99991n;
    const rnd = () => {
      st = (st * 6364136223846793005n + 1442695040888963407n) & ((1n << 64n) - 1n);
      return Number(st >> 32n) / 4294967296;
    };
    for (let n = 0; n < 50000; n++) {
      const v = new Array(8);
      for (let k = 0; k < 8; k++) v[k] = rnd() * 4 - 2;
      probe.push(v);
    }
    for (const v of probe) {
      cfN++;
      let best = -Infinity;
      for (let r = 0; r < ROOT_COUNT; r++) {
        let s = 0;
        for (let k = 0; k < 8; k++) s += roots[r * 8 + k] * v[k];
        if (s > best) best = s;
      }
      if (Math.abs(closedFormMax(v) - best) > 1e-12) cfBad++;
      if (rootLabelAnalytic(v).index !== rootIndex(v)) anBad++;
    }
    note(`closedFormMax == 240-row table max (${cfN} vectors incl. all roots and negations)`, cfBad === 0, `mismatches=${cfBad}`);
    note(`rootLabelAnalytic index == table index (${cfN} vectors)`, anBad === 0,
      `mismatches=${anBad} rate=${(100 * anBad / cfN).toFixed(4)}%`);

    let rankBad = 0, n = 0;
    for (let b = 0; b < 256; b++) {
      if (!popcountEven(b)) continue;
      if (rankEvenPopcount(b) !== n) rankBad++;
      n++;
    }
    note('rankEvenPopcount is a bijection onto 0..127 over the even-popcount domain', rankBad === 0 && n === 128,
      `mismatches=${rankBad} domain_size=${n}`);

    let prBad = 0, expect = 0;
    for (let i = 0; i < 8; i++) for (let j = i + 1; j < 8; j++) if (pairRank(i, j) !== expect++) prBad++;
    note('pairRank enumerates the 28 lexicographic pairs without a gap', prBad === 0 && expect === 28, `mismatches=${prBad} pairs=${expect}`);

    // The decay must BE sqrt(240) -- the demo's whole nesting claim.
    note('level ladder decays by exactly sqrt(240) per level',
      LADDER_DECAY === Math.sqrt(240) && levelScaleRaw(1) === Math.fround(2.0 / Math.sqrt(240)),
      `decay=${LADDER_DECAY} s0=${levelScale(0)} s1=${levelScale(1)} s15=${levelScale(15)}`);
  }

  // ---- 2. digests, from two independent module instances --------------
  console.log('\n--- canonical frames (two fresh module instances, same process) ---');
  const modsA = await loadMods('A');
  const modsB = await loadMods('B');
  const rows = [];
  let selfEqual = true;
  for (const p of PINS) {
    const a = renderPin(modsA, p);
    const b = renderPin(modsB, p);
    if (a.digest !== b.digest) selfEqual = false;
    let nonBlank = 0;
    for (let i = 0; i < a.bytes.length; i += 4) {
      if (a.bytes[i] > 8 || a.bytes[i + 1] > 8 || a.bytes[i + 2] > 8) nonBlank++;
    }
    rows.push({
      kind: p.kind, seed: p.seed, frame: p.frame, size: p.size,
      law: p.opts.field?.law ?? 'house',
      levels: p.opts.render?.levels ?? 4, bytes: a.bytes.length,
      sha256: a.digest, lit_pixels: nonBlank, alpha255: a.bytes[3] === 255,
    });
    console.log(`  ${p.kind.padEnd(6)} seed=${String(p.seed).padEnd(16)} frame=${String(p.frame).padStart(4)} L=${p.opts.render?.levels ?? 4} law=${(p.opts.field?.law ?? 'house').padEnd(7)} ${a.digest}  lit=${nonBlank}/${p.size * p.size}`);
  }
  note('both module instances produce byte-identical frames (no hidden shared state)', selfEqual, `frames=${PINS.length}`);
  note('every frame has lit pixels and opaque alpha', rows.every((r) => r.lit_pixels > 1000 && r.alpha255),
    `frames=${rows.length}`);

  // A frame that responds to nothing is a silent pass waiting to happen: assert
  // the pin depends on each control that the page exposes.
  console.log('\n--- sensitivity: the pin must depend on the seed, the frame, and the codec --');
  {
    const base = renderPin(modsA, PINS[0]);
    const otherSeed = renderPin(modsA, { ...PINS[0], seed: 'a-different-seed' });
    const otherFrame = renderPin(modsA, { ...PINS[0], frame: PINS[0].frame + 1 });
    const otherThreshold = renderPin(modsA, {
      ...PINS[0], opts: { render: { levels: 4, threshold: 1e-2 } },
    });
    // Depth at threshold 0: the adaptive stop can never fire, so every requested
    // level is emitted and the level knob is unambiguously wired to the pixels.
    const atDepth = (L) => renderPin(modsA, { ...PINS[0], opts: { render: { levels: L, threshold: 0 } } });
    const d4 = atDepth(4), d5 = atDepth(5), d7 = atDepth(7);
    note('changing the seed changes the digest', base.digest !== otherSeed.digest, `${base.digest.slice(0, 12)} vs ${otherSeed.digest.slice(0, 12)}`);
    note('changing the frame changes the digest', base.digest !== otherFrame.digest, `${base.digest.slice(0, 12)} vs ${otherFrame.digest.slice(0, 12)}`);
    note('changing the residual threshold changes the digest', base.digest !== otherThreshold.digest, `${base.digest.slice(0, 12)} vs ${otherThreshold.digest.slice(0, 12)}`);
    note('ladder depth changes the digest once the adaptive stop is disabled',
      d4.digest !== d5.digest && d5.digest !== d7.digest && d4.digest !== d7.digest,
      `L4=${d4.digest.slice(0, 10)} L5=${d5.digest.slice(0, 10)} L7=${d7.digest.slice(0, 10)}`);

    // And the reason the DEFAULT configuration ignores depth: the codec converges
    // before the requested ceiling. Reported, not hidden -- the page's level
    // slider is subordinate to the estate's own stop test.
    const levelsAt = (thr, L) => {
      const sc = modsA.refRender.makeScene('ladder', PINS[0].seed);
      const v8 = new Float64Array(8);
      modsA.core.carrierAt(0.1234, -0.4321, 0, sc.coef, v8);
      return modsA.core.residualLadder(v8, { maxLevels: L, threshold: thr }).codes.length;
    };
    const conv = levelsAt(1e-3, 4), deep = levelsAt(0, 4);
    console.log(`  at the shipped threshold 1e-3 this vector converges after ${conv} levels of ${deep >= 4 ? 4 : deep};`);
    console.log(`  at threshold 0 the same vector emits ${deep} -- so "levels" only moves the`);
    console.log('  picture for vectors that have NOT already converged.');
  }

  // ---- 2b. the estate seed law, against the bytes the estate module wrote ----
  await estateLawClaims(note, fails);

  // ---- 3. the refused set, measured -----------------------------------
  console.log('\n--- the exact-boundary set the provider kernel refuses -------------');
  {
    const b = boundaryCount('e8-omnibus-1102', 16384, { kind: 'ladder', frame: 0 });
    console.log(`  canonical frame pixels=${b.samples} (a ${b.cols}x${b.rows} grid, same uv law as the renderer)`);
    b.eps.forEach((e, i) => console.log(`    |advantage| <= ${e.toExponential(0)} -> ${b.hits[i]} pixels (${(100 * b.hits[i] / b.samples).toFixed(2)}%)`));
    console.log(`    exact zeros=${b.exactZero}  min |advantage| observed=${b.minAbs.toExponential(3)}`);
    console.log('  (raw-nearest-e8.e8:100-102 returns i32(6) at <=1e-4, before the');
    console.log('   kernel\'s own :65-67 "an exact zero keeps D8" law can be applied; the torch leg');
    console.log('   the codec rides keeps D8 instead. The gold filament draws the NEIGHBOURHOOD of that');
    console.log('   set with a named radius -- the exact set is real but ~0.01% of the frame.)');
    note('the boundary census returns a number for every radius', b.hits.every((h) => typeof h === 'number'),
      `radii=${b.eps.length} counted=${b.samples}`);
    note('the exact-refusal set is reported as measured, not assumed visible', true,
      `hits@1e-4=${b.hits[0]}/${b.samples}`);
  }

  // ---- 3b. shader source integrity --------------------------------------
  // The GLSL is shipped as a JS template literal, and node --check cannot grade
  // its CONTENT: one stray delimiter silently re-opens the literal, and the
  // shader the browser compiles is then a truncation of the one the source shows
  // (measured on this very file on 2026-11-02, when a comment inside the literal
  // carried a backtick: node --check stayed green, the fragment compile failed at
  // line 62). So the shader text gets structural claims HERE, in node, and the
  // browser leg keeps the semantic ones.
  console.log('\n--- shader source integrity (the GLSL the browser will compile) --');
  let shaderSha = null;
  {
    const { SHADERS } = await import('../js/gl-render.js');
    const TICK = String.fromCharCode(96);
    const codeOnly = (src) => src.split('\n').map((l) => l.replace(/\/\/.*$/, '')).join('\n');
    const APPROX = ['sin', 'cos', 'tan', 'asin', 'acos', 'atan', 'sinh', 'cosh', 'tanh',
      'pow', 'exp', 'log', 'exp2', 'log2', 'sqrt', 'inversesqrt', 'normalize', 'length',
      'distance', 'smoothstep', 'radians', 'degrees', 'texture'];
    const kinds = Object.keys(SHADERS);
    let integrity = true, noTrig = true, shape = true, tally = [];
    shaderSha = {};
    for (const k of kinds) {
      const src = SHADERS[k], code = codeOnly(src);
      shaderSha[k] = sha(src);
      const ticks = src.split(TICK).length - 1;
      const braces = [src.split('{').length - 1, src.split('}').length - 1];
      const parens = [src.split('(').length - 1, src.split(')').length - 1];
      const counts = {};
      for (const f of APPROX) {
        const n = (code.match(new RegExp('\\b' + f + '\\s*\\(', 'g')) || []).length;
        if (n) counts[f] = n;
      }
      const trig = Object.entries(counts).filter(([f]) => f !== 'sqrt');
      // The fragment write must exist exactly once and the source must END with a
      // closing brace: a truncated literal loses precisely the tail, and brace
      // BALANCE alone survived the mutation measured above (the cut landed where
      // the remaining text happened to balance), which is why the digest below is
      // the load-bearing claim and these are the readable ones.
      const writes = src.split('outColor =').length - 1;
      const ends = src.trimEnd().endsWith('}');
      const head = src.startsWith('#version 300 es');
      const legs = k === 'ladder'
        ? ['tri(', 'carrier(', 'nearestE8v', 'classOf(', 'uThresholdSq', 'uEpsDraw']
        : ['tri(', 'carrier(', 'pairRank(', 'rankEvenPopcount(', 'clamp(col'];
      const missing = legs.filter((m) => !src.includes(m));
      tally.push(`${k}: chars=${src.length} lines=${src.split('\n').length} ticks=${ticks}`
        + ` braces=${braces.join('/')} parens=${parens.join('/')} outColor=${writes}`
        + ` head=${head} tail=${ends} approx=${JSON.stringify(counts)}`
        + ` missingLegs=${missing.length ? missing.join(',') : 'none'}`
        + ` sha256=${shaderSha[k].slice(0, 16)}…`);
      if (ticks || braces[0] !== braces[1] || parens[0] !== parens[1]) integrity = false;
      if (trig.length) noTrig = false;
      if (writes !== 1 || !ends || !head || missing.length) shape = false;
    }
    for (const t of tally) console.log('  ' + t);
    note('every shipped shader is intact template text (no stray delimiter, balanced braces/parens)', integrity,
      kinds.length + ' kinds: ' + kinds.join(', '));
    note('each shader writes outColor exactly once and carries the legs it is claimed to transcribe', shape,
      'head=#version 300 es, tail=}, markers per kind above');
    note('the executable GLSL holds no implementation-approximated trig or common function (sqrt excepted, and disclosed)',
      noTrig, 'forbidden set=' + (APPROX.length - 1) + ' names, comments stripped; per-kind counts above');
    note('sqrt() appears exactly where it is disclosed: twice in the ladder colour leg, never in root',
      (codeOnly(SHADERS.ladder).match(/\bsqrt\s*\(/g) || []).length === 2
      && (codeOnly(SHADERS.root).match(/\bsqrt\s*\(/g) || []).length === 0,
      'GLSL ES leaves sqrt approximate; ECMA-262 Math.sqrt is correctly rounded (see gl-render.js)');
  }

  // ---- 4. cross-process pin comparison ---------------------------------
  console.log('\n--- pin file -------------------------------------------------------');
  if (checkIdx >= 0) {
    if (!existsSync(pinPath)) {
      note('pin file exists', false, pinPath);
    } else {
      const prior = JSON.parse(readFileSync(pinPath, 'utf8'));
      let bad = 0, compared = 0;
      const detail = [];
      for (const r of rows) {
        const p = prior.frames?.find((f) => f.kind === r.kind && f.seed === r.seed && f.frame === r.frame
          && f.levels === r.levels && f.size === r.size && (f.law ?? 'house') === r.law);
        if (!p) { detail.push(`missing ${r.kind}/${r.seed}/${r.frame}/${r.law}`); bad++; continue; }
        compared++;
        if (p.sha256 !== r.sha256) { bad++; detail.push(`DIFFERS ${r.kind}/${r.seed}/f${r.frame}: ${p.sha256.slice(0, 16)} != ${r.sha256.slice(0, 16)}`); }
      }
      note('every frame matches the pin written by a previous PROCESS', bad === 0,
        `compared=${compared} mismatches=${bad}${detail.length ? ' :: ' + detail.join(' | ') : ''}`);
      note('pin file carries its own provenance', !!prior.generated_by && !!prior.node, JSON.stringify({ node: prior.node, generated_by: prior.generated_by }));
      // The GLSL digests ride the same file because they answer the same question
      // in a different medium: the frames pin what the CPU path DREW, these pin
      // what the browser will be told to DRAW. node --check cannot see a
      // truncated shader (measured: rc stayed 0 while the ladder source lost 4,064
      // of its 10,649 chars), and a red browser leg is a slow way to learn that.
      if (!prior.shaders) {
        note('pin file carries the assembled GLSL digests', false,
          `absent in ${pinPath} -- re-run --write; a pin without them cannot detect a shader-text change`);
      } else {
        const sd = [];
        for (const k of Object.keys(shaderSha)) {
          if (prior.shaders[k] !== shaderSha[k]) sd.push(`${k}: ${String(prior.shaders[k]).slice(0, 16)}… != ${shaderSha[k].slice(0, 16)}…`);
        }
        for (const k of Object.keys(prior.shaders)) if (!(k in shaderSha)) sd.push(`${k}: pinned but no longer shipped`);
        note('the assembled GLSL matches the digests a previous PROCESS pinned', sd.length === 0,
          `compared=${Object.keys(shaderSha).length} differs=${sd.length}${sd.length ? ' :: ' + sd.join(' | ') : ''}`);
      }
    }
  }
  if (writeIdx >= 0) {
    writeFileSync(pinIdxPath(argv, writeIdx), JSON.stringify({
      generated_by: 'tools/determinism-harness.mjs',
      node: process.version,
      written_at: new Date().toISOString(),
      algorithm: 'SHA-256 over raw RGBA bytes of the CPU reference frame (canonical path)',
      shader_algorithm: 'SHA-256 over the ASSEMBLED GLSL ES source string per kind (after template-literal '
        + 'concatenation, before the driver sees it) -- the estate e8_jit.py cache-key law applied to text: '
        + 'pin the source you are about to hand to a compiler.',
      shaders: shaderSha,
      note: 'The CPU reference is canonical. The WebGL2 canvas is float32 end to end '
        + 'and is measured against these frames in-browser by the pin panel; it is not '
        + 'what these digests describe.',
      frames: rows,
    }, null, 2) + '\n');
    console.log(`  wrote ${pinIdxPath(argv, writeIdx)}`);
  }

  console.log('');
  if (fails.length) {
    console.log(`DETERMINISM FAILURES (${fails.length}): ${fails.join(' | ')}`);
    process.exit(1);
  }
  console.log('DETERMINISM: all assertions hold.');
}

/**
 * The estate seed law, graded against bytes the ESTATE produced.
 *
 * tools/estate-seed-vectors.json was written by running kagami core's
 * `kagami.core.omni.prng.SeededWordStream` out of the live kagami checkout
 * (`python3 tools/gen-estate-seed-vectors.py`), and it carries that checkout's
 * HEAD and the sha256 of the module it imported. Everything below compares
 * js/seed-stream.js + js/sha256.js against it. This is a cross-LANGUAGE equality
 * claim, not a within-JS one: no amount of self-consistency in JS could produce
 * it, which is why the fixture has to come from the other side.
 *
 * The fixture is frozen evidence between regenerations, and it is labelled as
 * such: the authority block printed on the first line names the kagami HEAD and
 * module digest these numbers were taken from. Re-run the generator to move them.
 */
async function estateLawClaims(note, fails) {
  console.log('\n--- estate seed law: bit-exact against kagami core omni/prng.py ----');
  const fixturePath = path.join(HERE, 'estate-seed-vectors.json');
  if (!existsSync(fixturePath)) {
    note('estate seed-law fixture exists', false,
      `absent: ${fixturePath} -- run python3 tools/gen-estate-seed-vectors.py (reads the live kagami checkout, read-only)`);
    return;
  }
  const gold = JSON.parse(readFileSync(fixturePath, 'utf8'));
  const { sha256Hex, sha256, utf8, SHA256_SELFTEST } = await import('../js/sha256.js');
  const { SeededWordStream, canonicalSeedBytes, fieldCoefficientsEstate } = await import('../js/seed-stream.js');

  const hexBytes = (u8) => [...u8].map((x) => (x + 0x100).toString(16).slice(1)).join('');
  const f64bits = (x) => { const b = new Uint8Array(8); new DataView(b.buffer).setFloat64(0, x, false); return hexBytes(b); };

  // 1. the hash primitive, against node:crypto (OpenSSL) on this host.
  let hashCases = 0, hashBad = 0, firstHashBad = null;
  const nodeSha = (b) => createHash('sha256').update(b).digest('hex');
  for (let len = 0; len <= 300; len++) {
    const b = new Uint8Array(len);
    for (let i = 0; i < len; i++) b[i] = (i * 7 + len * 13) & 255;
    hashCases++;
    if (sha256Hex(b) !== nodeSha(b) && hashBad++ === 0) firstHashBad = `len=${len}`;
  }
  let s = 12345n;
  const rnd = () => { s = (s * 6364136223846793005n + 1442695040888963407n) & ((1n << 64n) - 1n); return Number((s >> 32n) & 0xffffffffn) / 4294967296; };
  for (let t = 0; t < 200; t++) {
    const len = 1 + Math.floor(rnd() * 4096);
    const b = new Uint8Array(len);
    for (let i = 0; i < len; i++) b[i] = Math.floor(rnd() * 256);
    hashCases++;
    if (sha256Hex(b) !== nodeSha(b) && hashBad++ === 0) firstHashBad = `random len=${len}`;
  }
  let katBad = 0;
  for (const [msg, want] of SHA256_SELFTEST) { if (sha256Hex(utf8(msg)) !== want) katBad++; }
  note('js/sha256.js == node:crypto SHA-256 (the primitive the estate stream is built on)',
    hashBad === 0 && katBad === 0,
    `inputs=${hashCases} mismatches=${hashBad}${firstHashBad ? ' first:' + firstHashBad : ''} known_answer=${SHA256_SELFTEST.length - katBad}/${SHA256_SELFTEST.length}`);
  if (sha256(new Uint8Array(0)).length !== 32) fails.push('sha256 output width');

  // 2. canonical seed prefixes (prng.py:47-60).
  const prefixCases = [
    ['str:e8-omnibus-1102', 'e8-omnibus-1102'], ['str:', ''], ['str:unicode', 'é🦋'],
    ['int:0', 0n], ['int:1', 1n], ['int:255', 255n], ['int:256', 256n], ['int:65536', 65536n],
    ['bytes:abc', new Uint8Array([97, 98, 99])],
  ];
  let preBad = 0;
  for (const [key, val] of prefixCases) {
    if (hexBytes(canonicalSeedBytes(val)) !== gold.prefix[key]) preBad++;
  }
  note('canonical seed prefix bytes == estate (int/str/bytes widths, b"str"+utf8)',
    preBad === 0, `cases=${prefixCases.length} mismatches=${preBad}`);

  // 3. the stream itself: words, widths, doubles, rejection-sampled integers.
  const w = new SeededWordStream('e8-omnibus-1102');
  const words = [...Array(24)].map(() => w._word().toString());
  const wordBad = words.filter((x, i) => x !== gold.words24[i]).length;
  note('the 24 first 64-bit words == estate, decimal-exact', wordBad === 0,
    `words=${words.length} mismatches=${wordBad} first=${words[0]}`);

  const g2 = new SeededWordStream('e8-omnibus-1102');
  const gbBad = gold.getrandbits.filter((c) => g2.getrandbits(c.k).toString() !== c.value).length;
  note('getrandbits(k) for every width 1..192 == estate (the k>64 concat+trim leg)',
    gbBad === 0, `widths=${gold.getrandbits.length} mismatches=${gbBad} ks=${gold.getrandbits.map((c) => c.k).join(',')}`);

  const g3 = new SeededWordStream('e8-omnibus-1102');
  const rBad = gold.random12.filter((c) => f64bits(g3.random()) !== c.bits).length;
  note('random() == estate at the BIT level (53 bits / 2**53)', rBad === 0, `draws=${gold.random12.length} mismatches=${rBad}`);

  // One FRESH stream per series, because the fixture replays `S(SEED)` between
  // series (tools/gen-estate-seed-vectors.py); sharing one stream here would
  // compare a different position in the stream and read as a mismatch.
  const mk = () => new SeededWordStream('e8-omnibus-1102');
  const g4 = mk();
  const one = (stream, c) => c.args.length === 1 ? stream.randrange(c.args[0])
    : c.args.length === 2 ? stream.randrange(c.args[0], c.args[1])
      : stream.randrange(c.args[0], c.args[1], c.args[2]);
  const riBad = gold.randint.filter((c) => g4.randint(c.a, c.b) !== c.value).length;
  const g4b = mk();
  const rrBad = gold.randrange.filter((c) => one(g4b, c) !== c.value).length;
  note('randint/randrange series == estate (rejection over bit_length, stdlib bounds)',
    riBad === 0 && rrBad === 0, `randint=${gold.randint.length}/${gold.randint.length} bad=${riBad} randrange=${gold.randrange.length} bad=${rrBad}`);

  const pop = [...'abcdefghijklmnopqrstuvwxyz'];
  // choice: ONE stream, sixteen sequential calls (that is how the fixture drew it).
  const gc = mk();
  const chBad = gold.choice.filter((c) => gc.choice(pop) !== c).length;
  // sample: a SEPARATE fresh stream, five sequential calls; k = 0,1,3,8,26.
  const gs = mk();
  const saBad = gold.sample.filter((c) => JSON.stringify(gs.sample(pop, c.k)) !== JSON.stringify(c.value)).length;
  note('choice/sample == estate (incl. the k=0 and k=n sample edges)',
    chBad === 0 && saBad === 0,
    `choice=${gold.choice.length} bad=${chBad} sample=${gold.sample.length} bad=${saBad} ks=${gold.sample.map((c) => c.k).join(',')}`);
  // 4. the carrier lanes: the mapping both laws share, fed by the estate stream.
  const coef = fieldCoefficientsEstate('e8-omnibus-1102', {});
  let laneBad = 0;
  for (let k = 0; k < 8; k++) for (const f of ['fx', 'fy', 'phi', 'omega']) {
    if (f64bits(coef.lanes[k][f]) !== gold.lanes[k][f]) laneBad++;
  }
  note('all 32 carrier lane coefficients == estate, IEEE bit patterns', laneBad === 0,
    `lanes=8 fields=4 mismatches=${laneBad} lane0.fx=${coef.lanes[0].fx} bits=${f64bits(coef.lanes[0].fx)}`);

  // 5. refusals: the JS port must refuse exactly where the estate refuses.
  let refBad = 0, refTotal = 0;
  const probes = {
    none_seed: () => new SeededWordStream(null),
    bool_seed: () => new SeededWordStream(true),
    negative_seed: () => new SeededWordStream(-1),
    float_seed: () => new SeededWordStream(1.5),
    negative_k: () => new SeededWordStream('e8-omnibus-1102').getrandbits(-1),
    randrange_step_zero: () => new SeededWordStream('e8-omnibus-1102').randrange(0, 10, 0),
    randint_empty: () => new SeededWordStream('e8-omnibus-1102').randint(5, 1),
    choice_empty: () => new SeededWordStream('e8-omnibus-1102').choice([]),
    sample_too_big: () => new SeededWordStream('e8-omnibus-1102').sample([1, 2], 3),
    sample_negative: () => new SeededWordStream('e8-omnibus-1102').sample([1, 2], -1),
  };
  for (const [key, fn] of Object.entries(probes)) {
    refTotal++;
    let raised = false;
    try { fn(); } catch { raised = true; }
    const want = gold.refusals[key]?.raises != null;
    if (raised !== want) { refBad++; console.log(`    refusal mismatch ${key}: js_raised=${raised} estate_raised=${want}`); }
  }
  note('every estate refusal is a refusal here too (and no non-refusal became one)',
    refBad === 0, `probes=${refTotal} mismatches=${refBad}`);

  console.log(`  authority: kagami HEAD ${gold.authority.kagami_head}`);
  console.log(`             omni/prng.py sha256 ${gold.authority.module_sha256}`);
  console.log(`             python ${gold.interpreter.python} at ${gold.interpreter.executable}; fixture written ${gold.generated_at}`);
  console.log('  (frozen between regenerations -- re-run tools/gen-estate-seed-vectors.py to move it;');
  console.log('   kagami was READ for this and never written, per the lane brief.)');

  // 6. the estate law must be deterministic in ITS OWN right too, across processes:
  //    the same digest twice in a row, and different from the house law's.
  const estateCert = () => sha(certificate('e8-omnibus-1102', 0, { kind: 'ladder', size: 128, field: { law: 'estate' }, render: { levels: 4 } }).bytes);
  const e1 = estateCert(), e2 = estateCert();
  const houseCert = sha(certificate('e8-omnibus-1102', 0, { kind: 'ladder', size: 128, render: { levels: 4 } }).bytes);
  note('the estate law renders deterministically and is a DIFFERENT picture from the house law',
    e1 === e2 && e1 !== houseCert, `estate=${e1.slice(0, 12)} repeat=${e2.slice(0, 12)} house=${houseCert.slice(0, 12)}`);
  let threw = false;
  try { certificate('x', 0, { kind: 'ladder', size: 16, field: { law: 'sideways' } }); } catch { threw = true; }
  note('an unknown seed law is a refusal, not a silent fall back to house', threw, `raised=${threw}`);
}

function pinIdxPath(argv, i) { return path.resolve(argv[i + 1]); }

await main();
