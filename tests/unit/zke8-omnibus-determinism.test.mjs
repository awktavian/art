/**
 * patent-portfolio/demos/zke8-omnibus — the pin gate for the E8 omnibus pages.
 *
 * The property under test is that the demo's determinism claims are CHECKABLE
 * by CI and that the two checkers most likely to go silently vacuous still
 * FIRE. The lane that shipped these pages (RSI40-1102 V7, 2026-11-02) measured
 * three false-green traps, and every leg below is pinned to one of them:
 *
 *   1. `node --check` inspects only its FIRST file argument. A battery written
 *      `node --check js/*.js tools/*.mjs` reports rc=0 while a later file is
 *      syntactically broken. Measured on node v26.3.0 on this host.
 *   2. A citation comment carried a stray backtick into a GLSL template
 *      literal, the assembled ladder shader silently lost 4,064 of its 10,649
 *      characters, `node --check` stayed green, and only a real browser
 *      compile noticed. The fix is the SHA-256 of each kind's assembled GLSL
 *      in tools/pin.json — the estate's own JIT cache-key law
 *      (zke8/scripts/e8_jit.py:12-13) applied to source text.
 *   3. A pin file that is absent, or whose rows no frame matches, must be a
 *      FAILURE rather than a quiet "nothing to compare".
 *
 * Mutation legs run against a THROWAWAY COPY of the directory, never the
 * shipped tree, and the copy is asserted not to be inside a git work tree —
 * that is also how the offline-portability claim is earned: neither checker
 * reads the kagami checkout, torch, or `git`. Both read only files committed
 * beside them.
 */
import assert from "node:assert/strict";
import test from "node:test";
import { spawnSync } from "node:child_process";
import { cpSync, mkdtempSync, readdirSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const HERE = dirname(fileURLToPath(import.meta.url));
const REPO = join(HERE, "..", "..");
const DEMO = join(REPO, "patent-portfolio", "demos", "zke8-omnibus");

function copyDemo(label) {
  const root = mkdtempSync(join(tmpdir(), `zke8-omnibus-${label}-`));
  const dst = join(root, "zke8-omnibus");
  cpSync(DEMO, dst, { recursive: true });
  return dst;
}

function node(args, cwd) {
  return spawnSync(process.execPath, args, { cwd, encoding: "utf8" });
}

const shipped = (rel) => join(DEMO, rel);
const inCopy = (copy, rel) => join(copy, rel);
const readCopy = (copy, rel) => readFileSync(inCopy(copy, rel), "utf8");

function swapFile(abs, find, replace) {
  const src = readFileSync(abs, "utf8");
  assert.equal(src.split(find).length - 1, 1, `expected exactly one occurrence of ${find}`);
  writeFileSync(abs, src.replaceAll(find, replace));
}

// --------------------------------------------------------------------------
test("the demo directory is not a git work tree, so an offline clone can grade it", () => {
  // Not a test of the demo — a precondition of the next two legs. If someone
  // ever moves these checkers behind a `git rev-parse`, this fails first and
  // says why.
  const copy = copyDemo("precond");
  const probe = spawnSync("git", ["rev-parse", "--is-inside-work-tree"], { cwd: copy, encoding: "utf8" });
  assert.notEqual(probe.status, 0, "the throwaway copy must not resolve a work tree: " + probe.stdout);
  rmSync(join(copy, ".."), { recursive: true, force: true });
});

test("the determinism harness re-hashes the shipped pin, offline and git-free", () => {
  const copy = copyDemo("harness");
  const res = node(["tools/determinism-harness.mjs", "--check", "tools/pin.json"], copy);
  assert.match(res.stdout, /all assertions hold/, res.stdout + res.stderr);
  assert.equal(res.status, 0);
  // The legs whose green is the point of this file.
  assert.match(res.stdout, /every frame matches the pin written by a previous PROCESS\s+compared=10 mismatches=0/);
  assert.match(res.stdout, /the assembled GLSL matches the digests a previous PROCESS pinned\s+compared=2 differs=0/);
  rmSync(join(copy, ".."), { recursive: true, force: true });
});

test("estate parity grades the committed fixture, offline and git-free", () => {
  const copy = copyDemo("parity");
  const res = node(["tools/estate-parity.mjs"], copy);
  assert.equal(res.status, 0, res.stdout + res.stderr);
  assert.match(res.stdout, /PARITY: all assertions hold/);
  const fails = res.stdout.split("\n").filter((l) => l.startsWith("FAIL"));
  assert.equal(fails.length, 0, "FAIL lines: " + fails.join(" | "));
  rmSync(join(copy, ".."), { recursive: true, force: true });
});

test("a GLSL-only change goes red on the shader digest while node --check stays green", () => {
  // Trap 2, as a permanent leg: the mutated comparison is inside the browser's
  // shader only, so every CPU frame digest still matches. This is the ONLY leg
  // in the suite that can see a GPU-text edit.
  const copy = copyDemo("glsl");
  const shader = inCopy(copy, "js/gl-render.js");
  swapFile(shader, "if (r0 > maxR0) { maxR0 = r0; best0 = lane; }",
    "if (r0 >= maxR0) { maxR0 = r0; best0 = lane; }");

  const check = node(["--check", "js/gl-render.js"], copy);
  assert.equal(check.status, 0, "node --check must stay blind to shader TEXT: " + check.stderr);

  const res = node(["tools/determinism-harness.mjs", "--check", "tools/pin.json"], copy);
  assert.equal(res.status, 1, "the shader digest leg must fire on mutated GLSL: " + res.stdout);
  assert.match(res.stdout, /FAIL\s+the assembled GLSL matches the digests/);
  // And it must fire ALONE: the frames themselves are untouched by a GLSL edit.
  assert.doesNotMatch(res.stdout, /FAIL\s+every frame matches the pin/);
  rmSync(join(copy, ".."), { recursive: true, force: true });
});

test("a stray delimiter in a shader literal is caught, never a silent truncation", () => {
  // The exact defect class that shipped once: a backtick inside the template
  // literal ends it. Here the injected text is not valid JS outside the
  // literal, so the module no longer loads at all — which is what makes this
  // leg worth having separately from the digest leg above.
  const copy = copyDemo("tick");
  const shader = inCopy(copy, "js/gl-render.js");
  swapFile(shader, "// :46-49 and :55-58).", "// :46-49 and :55-58); a stray `delimiter` here.");

  const res = node(["tools/determinism-harness.mjs", "--check", "tools/pin.json"], copy);
  assert.equal(res.status, 1, "a truncated shader must not grade green: " + res.stdout);
  rmSync(join(copy, ".."), { recursive: true, force: true });
});

test("a tampered frame digest fails, and an absent pin file fails", () => {
  // Trap 3: absence and mismatch must both be red. A pin lookup that found no
  // row would otherwise report compared=0 as a pass.
  const tampered = copyDemo("pin-tamper");
  const pinPath = inCopy(tampered, "tools/pin.json");
  const pin = JSON.parse(readFileSync(pinPath, "utf8"));
  const last = pin.frames.length - 1;
  pin.frames[last].sha256 = pin.frames[last].sha256.replace(/.$/, (c) => (c === "a" ? "b" : "a"));
  writeFileSync(pinPath, JSON.stringify(pin, null, 2) + "\n");
  const res = node(["tools/determinism-harness.mjs", "--check", "tools/pin.json"], tampered);
  assert.equal(res.status, 1, res.stdout);
  assert.match(res.stdout, /FAIL\s+every frame matches the pin written by a previous PROCESS/);
  rmSync(join(tampered, ".."), { recursive: true, force: true });

  const missing = copyDemo("pin-absent");
  rmSync(inCopy(missing, "tools/pin.json"));
  const gone = node(["tools/determinism-harness.mjs", "--check", "tools/pin.json"], missing);
  assert.equal(gone.status, 1, "an absent pin must not be a vacuous green: " + gone.stdout);
  assert.match(gone.stdout, /FAIL\s+pin file exists|DETERMINISM FAILURES/);
  rmSync(join(missing, ".."), { recursive: true, force: true });
});

test("every shipped module parses under its OWN node --check invocation", () => {
  // Trap 1. The loop is not style: `node --check a b` inspects only `a`.
  const files = ["js/e8-core.js", "js/gl-render.js", "js/ref-render.js", "js/seed-stream.js",
    "js/sha256.js", "js/shell.js",
    "tools/browser-check.mjs", "tools/determinism-harness.mjs", "tools/disagreement-triage.mjs",
    "tools/estate-parity.mjs"];
  const onDisk = [...readdirSync(join(DEMO, "js")).filter((f) => f.endsWith(".js")).map((f) => `js/${f}`),
    ...readdirSync(join(DEMO, "tools")).filter((f) => f.endsWith(".mjs")).map((f) => `tools/${f}`)].sort();
  assert.deepEqual(onDisk, [...files].sort(),
    "the enumerated list drifted from the shipped tree");
  for (const f of files) {
    const res = node(["--check", f], DEMO);
    assert.equal(res.status, 0, `node --check ${f}: ${res.stderr}`);
  }

  // And record what this node build does with the multi-argument form, so the
  // claim above is re-measured every CI run instead of being inherited from a
  // comment. If node ever fixes --check to read every argument, this leg still
  // passes — it only prints the opposite truth.
  const copy = copyDemo("check-arity");
  const good = inCopy(copy, "js/sha256.js");
  const bad = inCopy(copy, "v7-broken.js");
  writeFileSync(bad, "this is not javascript ((((\n");
  const both = node(["--check", good, bad], copy);
  const individually = node(["--check", bad], copy);
  if (both.status === 0 && individually.status !== 0) {
    console.log(`NOTE  node ${process.versions.node}: \`node --check A B\` returned rc=0 while `
      + `\`node --check B\` returned rc=${individually.status} — the first-argument-only trap still `
      + "holds, so the per-file loop above is load-bearing.");
  } else {
    console.log(`NOTE  node ${process.versions.node}: \`node --check A B\` returned rc=${both.status} `
      + `(B alone: rc=${individually.status}) — this node build no longer shows the `
      + "first-argument-only behaviour measured on 2026-11-02; update the README row, keep the loop.");
  }
  rmSync(join(copy, ".."), { recursive: true, force: true });
});

test("the pin's GLSL digests are the digests the harness computes from the shipped source", () => {
  // tools/pin.json names the digests; js/gl-render.js is their subject. The hub
  // page prints them only after reading the pin at run time (index.html:264-269
  // slices String(v).slice(0,16) out of pin.shaders), so the file-level
  // invariant worth pinning is pin-vs-source, not pin-vs-markup — the markup
  // leg is graded in Chromium by tools/browser-check.mjs.
  const pin = JSON.parse(readFileSync(shipped("tools/pin.json"), "utf8"));
  assert.ok(pin.shaders && pin.shaders.ladder && pin.shaders.root, "pin.json must carry per-kind GLSL digests");
  const res = node(["tools/determinism-harness.mjs", "--check", "tools/pin.json"], DEMO);
  assert.equal(res.status, 0, `harness --check from the shipped tree: ${res.stdout}${res.stderr}`);
  for (const [kind, digest] of Object.entries(pin.shaders)) {
    assert.match(res.stdout, new RegExp(`${kind}:.*sha256=${digest.slice(0, 16)}`),
      `the ${kind} digest the pin names is not the one the harness computed from js/gl-render.js`);
  }
});
