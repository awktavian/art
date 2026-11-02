/**
 * browser-check.mjs — the GPU half of the verification, executed.
 *
 * The node harness can only prove the CPU reference is deterministic. This file
 * answers the question the brief actually asks — does the port WORK in a browser,
 * and how far is the WebGL2 float32 path from the canonical float64 path — by
 * serving the demo directory over http on a loopback port, driving headless
 * Chromium, and reading the numbers the page measured about itself
 * (`globalThis.__v7`, published by js/shell.js).
 *
 * Four claims, each with a denominator:
 *   1. the page loads with no uncaught error and no console error;
 *   2. the in-browser SHA-256 of the CPU reference frame EQUALS the digest the
 *      node harness pinned -- cross-engine identity of the canonical path. Graded
 *      once per SEED LAW (house and estate), each against its own pin row, and the
 *      page's own report of which law it is drawing is checked first, so a
 *      mis-parsed #law can only ever fail loudly;
 *   3. the analytic root label matches the 240-row table over 20,000 in-browser
 *      vectors, and the ladder respects the covering-radius bound;
 *   4. the GPU-vs-reference per-byte delta, printed as measured, plus the reduced
 *      -motion path (the page must start PAUSED and say so).
 *
 * Degrades honestly:
 *   no playwright install  -> SKIPPED (rc 0), because "not installed" is not a
 *                              rendering failure and must not read as one;
 *   WebGL2 refused         -> SKIPPED_GPU (rc 0) with the typed refusal code,
 *                              and claims 1-3 are still graded;
 *   a page error, a pin DIFFER, or a nonzero mismatch -> rc 1.
 *
 *   node tools/browser-check.mjs            # both demo pages
 *   node tools/browser-check.mjs --root     # only the root shell
 */

import { createRequire } from 'node:module';
import { createServer } from 'node:http';
import { readFile, writeFile } from 'node:fs/promises';
import { extname, join, normalize, sep } from 'node:path';
import { fileURLToPath } from 'node:url';

const HERE = fileURLToPath(new URL('.', import.meta.url));
const ROOT = join(HERE, '..');

const MIME = {
  '.html': 'text/html; charset=utf-8',
  '.js': 'text/javascript; charset=utf-8',
  '.mjs': 'text/javascript; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.svg': 'image/svg+xml',
};

// Resolved from an existing install if one is reachable; never installed here.
const CANDIDATES = [
  process.env.PLAYWRIGHT_CORE_PATH,
  '/Users/schizodactyl/projects/art/node_modules/playwright-core',
  '/Users/schizodactyl/projects/awkronos-waddle/node_modules/playwright-core',
].filter(Boolean);

function loadPlaywright() {
  const req = createRequire(import.meta.url);
  const tried = [];
  for (const c of CANDIDATES) {
    try {
      const mod = req(c);
      return { chromium: mod.chromium, from: c, version: req(join(c, 'package.json')).version };
    } catch (err) {
      tried.push(`${c} (${err.code || err.name})`);
    }
  }
  return { error: `playwright-core not reachable: ${tried.join(', ')}` };
}

function staticServer() {
  return new Promise((resolve) => {
    const srv = createServer(async (req, res) => {
      try {
        const url = new URL(req.url, 'http://127.0.0.1');
        let rel = decodeURIComponent(url.pathname);
        if (rel.endsWith('/')) rel += 'index.html';
        // Contain to the demo directory: a loopback server that escapes its root
        // is just an information leak with a port number.
        const abs = normalize(join(ROOT, rel));
        if (abs !== ROOT && !abs.startsWith(ROOT + sep)) {
          res.writeHead(403).end('outside root');
          return;
        }
        const body = await readFile(abs);
        res.writeHead(200, {
          'content-type': MIME[extname(abs)] || 'application/octet-stream',
          'cache-control': 'no-store',
        }).end(body);
      } catch {
        res.writeHead(404, { 'content-type': 'text/plain' }).end('not found');
      }
    });
    srv.listen(0, '127.0.0.1', () => resolve({ srv, port: srv.address().port }));
  });
}

const LAUNCH_ARGS = ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader',
  '--disable-dev-shm-usage', '--allow-file-access-from-files'];

// The hub page is shipped code too: it fetches tools/pin.json and renders a
// table whose columns are decided in three places at once (thead, the cells
// array, the error row's colSpan). Nothing else grades that, so it gets its own
// leg -- the failure mode is a table that quietly drops or shifts a column, which
// would print an estate-law digest under the house-law heading.
async function checkHub(chromium, base) {
  const out = { errors: [], consoleErrors: [], head: [], body: [], footText: '' };
  const browser = await chromium.launch({ headless: true, args: LAUNCH_ARGS });
  try {
    const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 }, deviceScaleFactor: 1 });
    const p = await ctx.newPage();
    p.on('pageerror', (e) => out.errors.push(String(e && e.stack ? e.stack.split('\n')[0] : e)));
    p.on('console', (m) => { if (m.type() === 'error') out.consoleErrors.push(m.text()); });
    await p.goto(`${base}/index.html`, { waitUntil: 'load' });
    await p.waitForFunction(
      () => {
        const r = document.getElementById('pin-rows');
        return r && r.querySelectorAll('tr').length > 0 && !/loading/i.test(r.textContent);
      },
      null, { timeout: 60000 },
    );
    out.head = await p.$$eval('#pin-table thead th', (ts) => ts.map((t) => t.textContent.trim()));
    out.body = await p.$$eval('#pin-rows tr', (trs) => trs.map((tr) => [...tr.children].map((td) => td.textContent.trim())));
    const foot = await p.$('#pin-foot');
    out.footText = foot ? await p.evaluate((el) => el.textContent, foot) : '';
  } finally {
    await browser.close();
  }
  return out;
}

async function checkPage(chromium, base, page, expect) {
  const out = { page: page.path, title: null, errors: [], consoleErrors: [], v7: null };
  const browser = await chromium.launch({ headless: true, args: LAUNCH_ARGS });
  try {
    const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 }, deviceScaleFactor: 1 });
    const p = await ctx.newPage();
    p.on('pageerror', (e) => out.errors.push(String(e && e.stack ? e.stack.split('\n')[0] : e)));
    p.on('console', (m) => { if (m.type() === 'error') out.consoleErrors.push(m.text()); });
    await p.goto(`${base}/${page.path}${page.hash || ''}`, { waitUntil: 'load' });
    await p.waitForFunction(
      () => document.getElementById('readout') && /sha256|REFUSAL|UNAVAILABLE/.test(document.getElementById('readout').textContent),
      null, { timeout: expect.timeoutMs || 90000 },
    );
    out.title = await p.title();
    out.readout = await p.$eval('#readout', (el) => el.textContent);
    out.v7 = await p.evaluate(() => (globalThis.__v7 ? JSON.parse(JSON.stringify(globalThis.__v7)) : null));
    // Reduced motion: the page must refuse to animate and say why.
    if (page.reducedMotion) {
      await p.emulateMedia({ reducedMotion: 'reduce' });
      await p.reload({ waitUntil: 'load' });
      await p.waitForFunction(() => globalThis.__v7 && /reduced-motion/.test(document.getElementById('readout').textContent),
        null, { timeout: 90000 });
      out.reduced = await p.evaluate(() => ({ playing: globalThis.__v7.state.playing, note: /PAUSED/.test(document.getElementById('readout').textContent) }));
    }
  } finally {
    await browser.close();
  }
  return out;
}

const fails = [];
const note = (label, pass, detail) => {
  console.log(`${pass === true ? 'PASS' : pass === 'SKIP' ? 'SKIPPED' : 'FAIL'}  ${label}${detail ? '  ' + detail : ''}`);
  if (pass === false) fails.push(label);
};

const pw = loadPlaywright();
if (pw.error) {
  console.log(`browser-check: SKIPPED -- ${pw.error}`);
  console.log('  The CPU canonical path is still graded by tools/determinism-harness.mjs;');
  console.log('  this file only grades the in-browser GPU leg, and "not installed" is not a rendering failure.');
  process.exit(0);
}
console.log(`browser-check  playwright-core ${pw.version} from ${pw.from}`);

const { srv, port } = await staticServer();
const base = `http://127.0.0.1:${port}`;
console.log(`  serving ${ROOT} at ${base}\n`);

const pin = JSON.parse(await readFile(join(ROOT, 'tools', 'pin.json'), 'utf8'));
const onlyRoot = process.argv.includes('--root');
const PAGES = [
  // Each kind runs twice, once per SEED LAW, against its own pin row. The house
  // law is the art convention (Xorshift128+ over FNV-1a); the estate law is
  // js/seed-stream.js, the port of kagami core omni/prng.py. Grading both is the
  // point: the estate rows are the cross-language claim (Chromium drawing the
  // picture Kagami's own stream seeds), and they are only meaningful if the
  // lookup cannot fall back to a house row of the same (kind, seed, frame, levels).
  { path: 'residual-ladder/index.html', kind: 'ladder', law: 'house', reducedMotion: true, label: 'residual-ladder  house law' },
  { path: 'residual-ladder/index.html', kind: 'ladder', law: 'estate', hash: '#law=estate', reducedMotion: false, label: 'residual-ladder  ESTATE law (kagami omni/prng.py stream)' },
  { path: 'root-shell/index.html', kind: 'root', law: 'house', reducedMotion: false, label: 'root-shell  house law' },
  { path: 'root-shell/index.html', kind: 'root', law: 'estate', hash: '#law=estate', reducedMotion: false, label: 'root-shell  ESTATE law (kagami omni/prng.py stream)' },
].filter((p) => !onlyRoot || p.kind === 'root');

let exitCode = 0;
try {
  for (const page of PAGES) {
    const r = await checkPage(pw.chromium, base, page, {});
    console.log(`--- ${page.path}  ${page.label} (${r.title || 'no title'}) ---`);
    note('page loads with no uncaught error', r.errors.length === 0,
      r.errors.length ? r.errors.join(' | ') : `errors=0`);
    note('no console errors', r.consoleErrors.length === 0,
      r.consoleErrors.length ? r.consoleErrors.slice(0, 3).join(' | ') : 'console errors=0');
    if (!r.v7) { note('page published its measurement', false, 'globalThis.__v7 never appeared'); exitCode = 1; continue; }

    const c = r.v7.consistency || {};
    note('in-browser falsifier: analytic root label == 240-row table',
      c.ok === true,
      `samples=${c.samples} indexMismatch=${c.indexMismatch} maxMismatch=${c.maxMismatch} familyMismatch=${c.familyMismatch} ladderBoundViolations=${c.ladderBoundViolations}/${c.ladderSamples} stops=${JSON.stringify(c.stops)}`);

    // The URL asked for a law; the page must say it is drawing that one, or the
    // digest comparison below would be graded against a row the browser never
    // selected (an unknown #law value silently becomes house).
    note(`the page reports the seed law the URL asked for (${page.law})`,
      (r.v7.state.law ?? 'house') === page.law, `page says law=${JSON.stringify(r.v7.state.law ?? 'house')}`);
    const want = pin.frames.find((f) => f.kind === page.kind && f.seed === 'e8-omnibus-1102' && f.frame === 0 && f.size === 128
      && (f.law ?? 'house') === page.law
      && (page.kind !== 'ladder' || f.levels === r.v7.state.levels));
    const digest = typeof r.v7.digest === 'string' ? r.v7.digest : null;
    if (!digest) {
      note('in-browser SHA-256 of the reference frame', false, `refusal ${JSON.stringify(r.v7.digest)}`);
    } else if (!want) {
      note('in-browser SHA-256 of the reference frame', false, `no ${page.law}-law pin row matched the page default state`);
    } else {
      note(`in-browser SHA-256 == node pin for ${page.kind}/f0/${page.law} (cross-engine identity of the canonical path)`,
        digest === want.sha256, `browser=${digest.slice(0, 20)}… node=${want.sha256.slice(0, 20)}… ${digest === want.sha256 ? 'IDENTICAL' : 'DIFFERENT'}`);
    }

    const m = r.v7.measured || {};
    if (m.ok) {
      console.log(`  GPU vs reference @ ${m.size}: mean |delta| = ${m.meanAbsByte.toFixed(4)} of 255, max = ${m.maxAbsByte}, `
        + `exact bytes = ${m.bytesEqual}/${m.channelsTested} (${m.bytesEqualPct.toFixed(2)}%), bytes over 8 = ${m.bytesOver8} (${m.bytesOver8Pct.toFixed(3)}%)`);
      console.log(`  per channel ${m.perChannelMean}; worst ${m.worst}`);
      console.log(`  gpu sha256 ${m.gpuHex}`);
      // The law is a STATEMENT ABOUT WHERE, not a magic tolerance: the decode is
      // a step function, so float32 can only disagree with float64 at a coset tie.
      // Grading the disagreement set's |advantage| against the frame's own median
      // distinguishes "arithmetic width at a discontinuity" from "the shader
      // computes something else" -- the earlier ordering bug scored max=59 here and
      // looked exactly like precision noise until the boundary ratio was printed.
      // THE MIRROR LAW. The page re-evaluates the shader's own float32 carrier
      // expression on the CPU (ref-render.js mirrorCarrier) and runs it through the
      // unchanged reference ladder. That is not a tolerance -- it is a prediction of
      // the GPU's exact bytes, pixel by pixel, from the port's source alone. Three
      // weaker probes came first and each is recorded in ref-render.js: coset-advantage
      // sorting (ratio 0.84, refuted), a one-direction eps nudge (54% coverage, wrong
      // instrument), and rounding the carrier once to float32 (3 of 48, right
      // mechanism, wrong magnitude -- a 1-ulp carrier error is divided by the level
      // scale, so at level 3 it becomes ~2e-4, the size of these pixels' margins).
      const mt = m.mirror || {};
      note('GPU/reference disagreement is rare', m.disagreePct <= 1.0,
        `${m.disagreePixels} of ${m.pixels} pixels over 8 levels = ${m.disagreePct.toFixed(3)}% (ceiling 1%)`);
      note('the float32 mirror predicts EVERY disagreeing pixel byte for byte',
        m.disagreePixels === 0 ? 'SKIP' : mt.disagreeExact === mt.disagreePixels,
        m.disagreePixels === 0
          ? `vacuous-but-verified: the GPU frame needs no prediction here; the mirror reproduces ${mt.exactPixels}/${mt.pixels || m.pixels} pixels anyway at mode ${mt.mode}`
          : `${mt.mode}: ${mt.disagreeExact}/${mt.disagreePixels} disagreeing pixels byte-exact; whole frame ${mt.exactPixels}/${m.pixels} (${mt.exactPct.toFixed(2)}%), worst residual ${mt.maxResidual} levels; per mode `
          + (mt.modes || []).map((x) => `${x.mode}=${x.exactPct.toFixed(2)}%`).join(' '));
      // The claim is IDENTITY, not tolerance: a CPU evaluator of the shader's own
      // float32 arithmetic reproduces the GPU's framebuffer. The floors are 99%/8
      // levels rather than 100%/0 only because a driver free to fuse a*b+c can land
      // outside both mirrored disciplines; the mode that wins is printed, never assumed.
      note('the mirror predicts the GPU frame (identity, not a tolerance)',
        mt.exactPct >= 99 && mt.maxResidual <= 8,
        `${mt.exactPct.toFixed(2)}% of ${m.pixels} pixels identical byte-for-byte (floor 99), worst ${mt.maxResidual} levels (ceiling 8) — the GPU's bytes are predictable from the port's source alone`);
      const dump = { kind: page.kind, seed: r.v7.state.seed ?? null, frame: r.v7.state.frame ?? 0,
        law: r.v7.state.law ?? 'house',
        size: 128, state: { levels: r.v7.state.levels, threshold: r.v7.state.threshold, epsDraw: r.v7.state.epsDraw, amplitude: 1.5, law: r.v7.state.law ?? 'house' },
        gpuHex: m.gpuHex, detail: m.disagreeDetail || [] };
      // The law is in the FILE NAME. Two runs per kind (house, estate) writing one
      // path would leave the triage tool explaining whichever frame happened to land
      // last, with no way to tell which law produced the pixels.
      await writeFile(`/tmp/v7-gpu-detail-${page.kind}-${dump.law}.json`, JSON.stringify(dump));
      console.log(`  dumped ${dump.detail.length} disagreeing pixels -> /tmp/v7-gpu-detail-${page.kind}-${dump.law}.json`);
      note('GPU digest is reported as its own number, never as the pin', !!m.gpuHex && m.gpuHex !== digest,
        `gpu=${String(m.gpuHex).slice(0, 12)}… cpu=${String(digest).slice(0, 12)}…`);
    } else {
      note('GPU vs reference measured', 'SKIP', `refusal ${m.refusal}: ${String(m.detail).slice(0, 140)}`);
    }

    if (page.reducedMotion) {
      note('prefers-reduced-motion: reduce -> starts paused and says so',
        r.reduced && r.reduced.playing === false && r.reduced.note === true,
        JSON.stringify(r.reduced || null));
    }
    console.log('');
  }

  // ---- hub page: the pin table is shipped output, so it gets graded ----
  console.log('--- index.html  the hub (pin table rendered from tools/pin.json) ---');
  const hub = await checkHub(pw.chromium, base);
  note('the hub page loads with no uncaught error', hub.errors.length === 0,
    hub.errors.length ? hub.errors.join(' | ') : 'errors=0');
  note('no console errors on the hub', hub.consoleErrors.length === 0,
    hub.consoleErrors.length ? hub.consoleErrors.slice(0, 3).join(' | ') : 'console errors=0');
  note('the hub table renders one row per pinned frame',
    hub.body.length === pin.frames.length,
    `rows=${hub.body.length} pinned=${pin.frames.length}`);
  const colCount = hub.head.length;
  const ragged = hub.body.filter((r) => r.length !== colCount).length;
  const lawCol = hub.head.findIndex((h) => /law/i.test(h));
  const lawValues = lawCol >= 0 ? [...new Set(hub.body.map((r) => r[lawCol]))].sort() : [];
  note('every rendered row has exactly as many cells as the header',
    colCount > 0 && ragged === 0, `columns=${colCount} ragged=${ragged}`);
  note('the seed law column exists and holds only the two declared laws',
    lawCol >= 0 && lawValues.every((v) => v === 'house' || v === 'estate') && lawValues.length === 2,
    lawCol >= 0 ? `index=${lawCol} values=${JSON.stringify(lawValues)}` : 'no law column in the header');
  const wantDigests = pin.shaders
    ? Object.entries(pin.shaders).map(([k, v]) => `${k} ${String(v).slice(0, 16)}`)
    : [];
  note('the hub prints the GLSL source digests the pin file carries',
    wantDigests.length > 0 && wantDigests.every((d) => hub.footText.includes(d)),
    wantDigests.length
      ? `pinned=${wantDigests.length} found=${wantDigests.filter((d) => hub.footText.includes(d)).length} foot="${hub.footText.slice(0, 96)}…"`
      : 'ABSENT: pin.json carries no shaders block, so there is nothing to print');
  const frameMismatch = hub.body.filter((r) => {
    const row = pin.frames.find((f) => f.kind === (r[0].startsWith('Residual') ? 'ladder' : 'root')
      && f.seed === r[1] && 'f' + f.frame === r[2] && (f.law ?? 'house') === r[lawCol]
      && f.sha256 === r[colCount - 1]);
    return !row;
  }).length;
  note('each printed digest belongs to the row it is printed on (no column shift)',
    frameMismatch === 0, `rows=${hub.body.length} mismatched=${frameMismatch}`);
} catch (err) {
  console.log(`browser-check ERROR: ${err && err.stack ? err.stack : err}`);
  fails.push('driver crashed');
  exitCode = 1;   // a crash is not a pass: this file used to exit 0 here
} finally {
  srv.close();
}

if (fails.length) {
  console.log(`BROWSER CHECK FAILURES (${fails.length}): ${fails.join(' | ')}`);
  exitCode = 1;
} else {
  console.log('BROWSER CHECK: every graded claim held.');
}
process.exit(exitCode);
