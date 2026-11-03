# zke8 Omnibus — the estate's lattice codec, drawn in a browser

Two demoscene pages and one index, built from techniques that already run inside
Kagami: the residual E8 lattice quantizer, the codec's 240-root `root_index`, and
`core/omni/prng.py`'s seeded word stream. Vanilla ES modules, **no build step and
no dependency added by this directory** — the only non-shipped requirement is
`playwright-core`, needed solely for the browser leg of the battery. Measured
provenance: `package.json` at the repo root declares exactly one devDependency,
`@playwright/test@1.61.1`, and `playwright-core` reaches it transitively (measured
chain: `@playwright/test` 1.61.1 → `playwright` 1.61.1 → `playwright-core` 1.61.1),
so `npm ci` in a clone supplies it; `tools/browser-check.mjs` resolves it from
whatever install is reachable and **never installs anything** — it tries
`PLAYWRIGHT_CORE_PATH`, then the bare specifiers `playwright-core` and
`@playwright/test`, then two host absolute paths, and prints `SKIPPED` with each
candidate's failure code, exiting 0, if none resolve.

Written against a live read of two other trees, both **read-only** from here:

| source | identity |
|---|---|
| `~/projects/kagami` (the estate) | HEAD `9604d939ea137eb4a75cf26509924a50ec4cb243` |
| `~/zke8` (the `.e8` language and its compilers) | HEAD `f6f435dc597dde68565a6eaf14753a63693f64f5` |

The full technique survey, with file:line citations and the reasons some surveyed
machinery was *not* ported, is in the lane's SPEC:
`.claude/campaigns/RSI40-1102/results/V7/demoscene-tech-spec.md`.

## Pages

| page | what it is | the estate object it draws |
|---|---|---|
| `residual-ladder/` | nested Voronoi cells: how many shells deep is this pixel | `ResidualE8LatticeVQ` (`kagami_math/e8_lattice_protocol.py:210-320`), `nearest_e8` (`e8_core.py:111-149`), the provider kernel (`zke8/examples/raw-nearest-e8.e8:13-141`) |
| `root-shell/` | the 240 E8 roots as a direction code — hue *is* the index | `root_index` (`core/digest/e8_period_codec.py:688-719`), root enumeration (`kagami_math/dimensions.py:233-291`), the f2_8 class alphabet (`e8_alphabet.py:39, 110-120`) |

## Run it

```bash
# any static server, from the repo root
python3 -m http.server -d patent-portfolio/demos/zke8-omnibus 8080
# then http://127.0.0.1:8080/residual-ladder/index.html
```

Once published to `main`, GitHub Pages serves the index at
`https://awktavian.github.io/art/patent-portfolio/demos/zke8-omnibus/`.

## The URL is the recipe

Every parameter lives in the hash, so a screenshot is reproducible by URL:

```
#seed=<string>&law=house|estate&frame=<int>&levels=<1..16>
&threshold=<float>&epsDraw=<float>&amplitude=<float>
```

Defaults: `seed=e8-omnibus-1102`, `law=house`, `frame=0`, `levels=4`,
`threshold=0.001`, `epsDraw=0.02`, `amplitude=1.5`. Anything unparseable is
**reported in the panel and then defaulted** — `law=omnibus` never quietly
renders the house picture while claiming the estate law.

`law` is the interesting one. `house` is this repo's convention (Xorshift128+ over
an FNV-1a seed hash). `estate` is `js/seed-stream.js`, a bit-exact port of
`packages/kagami/core/omni/prng.py:47-144` — SHA-256 in counter mode over a
canonical seed prefix, big-endian 64-bit words, top-k-bits `getrandbits`, 53-bit
`random()`, and one JS refusal per Python refusal. Both laws fill the same eight
carrier lanes through the same mapping, so switching the law changes nothing but
the uniform source. `#law=estate` is therefore a claim about *Kagami's* picture,
and it is graded: `tools/gen-estate-seed-vectors.py` runs the real module out of
the live checkout, the harness compares this port against those bytes, and
`tools/browser-check.mjs` re-grades the estate frame in Chromium against its own
pinned digest.

## Checkers

Run from this directory. The rc column is what was measured on 2026-11-02.

| command | rc | what it proves |
|---|---|---|
| `npm run test:unit` (from the repo root) | 0 | 72 tests, 72 pass, 0 fail, 0 skipped — **10 of them are `tests/unit/zke8-omnibus-determinism.test.mjs`**, which puts this directory's determinism law inside CI's own gate: the shipped pin re-hashes green in a throwaway copy that is *not* a git work tree (so no estate checkout, no torch, no `git`), a GLSL-only comparison change goes red on the shader digest while `node --check` stays green, a stray delimiter in a shader literal goes red, a tampered frame digest goes red, an **absent** pin file goes red rather than reporting `compared=0` as a pass, the triage tool's two dump-identity guards (renamed law, renamed or unlabelled kind) are refused against a dump directory the test owns, the browser leg's unreachable-playwright branch is forced and required to print a typed `SKIPPED` naming every candidate **and zero PASS lines**, and the `node --check` arity trap is re-measured every run and printed as a NOTE. |
| `for f in js/*.js tools/*.mjs; do node --check "$f" \|\| echo "FAIL $f"; done` | 0 | all **ten** shipped modules parse (`ls js/*.js tools/*.mjs \| wc -l` → 10: six in `js/`, four in `tools/`; the unit test asserts that enumeration against the tree, so the list cannot silently lose a file). Use the loop, not `node --check a.js b.js`: **measured on this host, `--check` inspects only its first file argument and ignores the rest** (a broken second file still returned rc=0), so the glob form is a false green. And even the loop cannot see the *content* of the GLSL template literals — see the shader-digest row. |
| `node tools/determinism-harness.mjs --check tools/pin.json` | 0 | 34 assertions: the canonical frames re-hashed against a pin written by a previous **process**, two independently imported module instances agreeing in one process, the seed-law vectors against the estate's bytes, SHA-256 itself against `node:crypto` over 501 inputs, the root-label closed form against the 240-row table over 202,551 samples, and the GLSL source digests. |
| `node tools/browser-check.mjs` (`--root` to halve it) | 0 | headless Chromium: no uncaught error, no console error, the in-browser falsifier, the law the URL asked for, the in-browser SHA-256 equal to node's pin, GPU-vs-reference disagreement under 1% of pixels, and the float32 mirror reproducing the GPU's bytes. 42 PASS / 0 FAIL / 2 SKIPPED over 5 page loads. It resolves playwright from `PLAYWRIGHT_CORE_PATH`, then the bare specifiers, then two absolute host paths, and if none resolve it prints `SKIPPED` naming every candidate with its error code and exits **0 having graded nothing** — that rc is a typed absence, not a pass, and the unit gate now mutates the candidate list to force the branch and assert both halves of that sentence. |
| `node tools/estate-parity.mjs` | 0 | 18 claims against `tools/estate-e8.json` — the estate's own torch `nearest_e8`, level counts, half-step codes, reconstruction and `root_index`, elementwise. |
| `node tools/disagreement-triage.mjs [ladder\|root] [house\|estate]` | 0 ×4 | names a mechanism for every pixel the GPU moved by more than 8 levels, or writes it down as UNEXPLAINED. 48/48 (ladder/house) and 25/25 (ladder/estate) explained, 0 unexplained; root/house and root/estate hold 0 disagreeing pixels and print `nothing to triage` instead of a vacuous green. **rc=0 here means the triage RAN, not that the pixels were explained** — read the tally line. Its only input is the per-pixel GPU dump `browser-check` writes, and both identity axes of that dump are now required to match the frame asked for: a dump renamed across LAWS and a dump renamed (or unlabelled) across KINDS are each refused with rc=2. Three traps on this row, all measured here: the dumps sit at `${V7_GPU_DETAIL_DIR:-/tmp}/v7-gpu-detail-<kind>-<law>.json`, so a stale file from an earlier frame silently grades as a fresh one (before the kind guard shipped, a ladder/house dump renamed to `root-house.json` was ACCEPTED — `0/48 explained, 48 UNEXPLAINED, rc=0`); and the four legs must be invoked with **two separate argv words**, because in zsh `for a in "ladder house"; do … $a` passes ONE argument, `argv.includes('root')` is false for every iteration, and the same ladder/house leg reports `0 ×4` — the header line names the kind it actually graded, so read it. |

`node tools/determinism-harness.mjs --write tools/pin.json` regenerates the pin
file; it is how `tools/pin.json` was written, and the frames came back identical.

## Files

```
js/e8-core.js       lattice semantics: coset decode, tie rule, exact-boundary
                    refusal (both estate legs), level ladder, f2_8 class,
                    root enumeration + the analytic closed form
js/seed-stream.js   kagami core/omni/prng.py, bit for bit, refusal for refusal
js/sha256.js        FIPS 180-4 SHA-256, synchronous and dependency-free
                    (K and H were derived in exact integer arithmetic)
js/ref-render.js    the canonical float64 CPU reference renderer, the float32
                    shader mirror, and carrier(seed, {law}) — one seed-path entry
js/gl-render.js     WebGL2: the GLSL, the uniforms, a typed refusal per driver
js/shell.js         URL state, panels, the certificate canvas, measurement
residual-ladder/    root-shell/    index.html
tools/              the four checkers above (harness, browser, parity, triage),
                    two fixture generators, the frozen
                    fixtures, and pin.json
../../tests/unit/zke8-omnibus-determinism.test.mjs
                    the CI leg: it runs the harness and the parity checker
                    offline, and mutation-tests the pin and the shader digest
                    against throwaway copies
```

## Determinism, and the three things it does not mean

* **The pin is the CPU reference.** `tools/pin.json` holds SHA-256 over the raw
  RGBA bytes of a 128×128 float64 reference frame, plus the seed law and codec
  state that produced it. The GPU is measured against those frames and reports
  its own digest separately; `browser-check` asserts the GPU digest is never
  silently used as the pin.
* **Only exactly-specified arithmetic is allowed on the pinned path.** No
  `Math.sin`, no `Math.pow`: the carrier is a triangle wave, the level scales are
  a frozen float32 table, the stream is BigInt words. The one named exception is
  on the GPU side only: the ladder's colour leg calls GLSL `sqrt()` twice, GLSL ES
  leaves `sqrt` implementation-approximated while ECMA-262 requires `Math.sqrt` to
  be correctly rounded, so the mirror's byte identity is a **measured property of
  the device under test** (SwiftShader/ANGLE on this host), not a proof about all
  drivers. It cannot flip a decision — coset, level count and class come from
  `floor`/`round`/`abs`/integer arithmetic alone.
* **`tools/pin.json` also pins the shader text.** `shaders.ladder` / `shaders.root`
  are SHA-256 over each kind's assembled GLSL, in the spirit of the estate's own
  JIT cache key (`zke8/scripts/e8_jit.py:12-13`), which hashes source before
  handing it to a compiler. This exists because a citation comment inside the
  template literal once carried a stray delimiter: the compiled ladder source
  silently lost 4,064 of its 10,649 characters, `node --check` stayed green, and
  only the browser noticed. Re-injecting that mutation makes the harness go red
  (rc=1) while `node --check` stays at rc=0 — the control is part of the design.
* **The estate fixtures are frozen between regenerations.**
  `tools/estate-e8.json` and `tools/estate-seed-vectors.json` move if the kagami
  checkout moves; the harness prints the HEAD and module sha256 it graded against
  so a stale fixture cannot pass silently. The 512 estate vectors are a sample,
  not a census.
* The estate's own exactness claims about `nearest_e8` carry an **EXPIRED** grails
  row and a PENDING kernel cert (`e8_core.py:120-129`). This port inherits the
  *law* and the typed refusals, not any certification.

## What is not claimed

Nothing here compiles anything in a browser. The estate's own browser legs are
`zke8/scripts/e8_wasm.py` (E8 → wasm32, loaded as committed bytes and checked
against a manifest) and `core/omni/reactor_jit.py` (an identity-gated compiled
twin); both are cited and neither is what this directory does. Speed is not
asserted anywhere in this port either — that is the estate's own discipline
(`reactor_jit.py:44-48`, "Speed is not asserted here"), and it is kept.
