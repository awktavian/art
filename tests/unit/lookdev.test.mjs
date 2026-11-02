/**
 * Look-dev gate — art's deterministic camera/lighting/material corpus.
 * Lane R46-ART-LOOKDEV, wave RSI40-1102.
 *
 * This is the fold-time before/after signal the V10 visual ledger asked art to
 * adopt from waddle's `apps/hub/public/snowball/src/lookdev.js` discipline. The
 * receipts live in `tests/lookdev/receipts.json`; the harness is
 * `tests/lookdev/lookdev.mjs` (run it directly for the human report:
 * `node tests/lookdev/lookdev.mjs`, `--update` to re-stamp, `--falsify=all`,
 * `--drill`).
 *
 * Four claims, each falsifiable, none of them a paraphrase of the code under
 * test (the register this lane took from waddle's
 * `theorem-penguin-corpus.golden.test.ts`):
 *
 *   1. THE DOUBLE IS FAITHFUL WHERE IT CLAIMS TO BE. The museum modules import
 *      `three`; art has no node_modules and no build step, so the harness runs
 *      them against a bounded r160 double (the importmap pin in
 *      patent-portfolio/index.html). A double that gets sRGB transfer, the
 *      perspective frustum, or an `isMeshStandardMaterial` flag wrong does not
 *      pin the look — it pins a description of it. So the double is tested
 *      against arithmetic, not against itself.
 *   2. THE CORPUS IS DETERMINISTIC ACROSS RUNS AND ACROSS RUN HISTORY. Same
 *      hashes twice in one process, and a second `runAll()` that cannot see the
 *      first one's module singletons.
 *   3. THE RECEIPTS ARE SENSITIVE TO THEIR OWN INPUTS. Every harness pin has a
 *      declared scene set that must move when it is perturbed — exactly, not
 *      "something moved".
 *   4. A SOURCE EDIT MOVES A RECEIPT. `--drill` changes one digit in a COPY of
 *      patent-portfolio/museum/lighting.js (the in-flight lanes own the real
 *      file, so nothing in the repo is touched) and requires the untouched copy
 *      to reproduce the stamped hash first. Control, then edit.
 *
 * What a DRIFT result means at fold time: a lighting/material/palette surface
 * moved. That is the designed signal, not necessarily a failure — V5 is editing
 * museum lighting and materials right now, so its fold is EXPECTED to flip
 * `museum.*` receipts. The fold that must re-stamp is the one that inspects the
 * diff first; this gate refuses to let that inspection be skipped.
 *
 * Boundary is declared, not implied: COVERAGE in the harness names what the
 * corpus cannot see (main.js renderer assembly, Math.random geometry builders,
 * three/addons post-processing, pixel-level GLSL evaluation) and what does not
 * exist at this base (V6's demos/groups/ atlas, a path-traced demo). The last
 * test asserts that this lane reached none of the in-flight write-sets.
 */
import { test } from "node:test";
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { existsSync, readFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

import {
  CONTRACT,
  COVERAGE,
  DRILL,
  PERTURB,
  RECEIPT_FILE,
  RIG,
  SENSITIVITY,
  THREE,
  canonical,
  corpus,
  digestOf,
  inDeterministicContext,
  makeRecordingCanvas,
  readReceipts,
  runAll,
  runDrill,
} from "../lookdev/lookdev.mjs";
import { createThreeDouble, r160 } from "../lookdev/three-double.mjs";

const REPO = resolve(dirname(fileURLToPath(import.meta.url)), "..", "..");
const HEX64 = /^[0-9a-f]{64}$/;

let report = null;
async function corpusReport() {
  if (!report) report = await runAll();
  return report;
}

// ═══════════════════════════════════════════════════════════════════════════
// 1. THE DOUBLE IS FAITHFUL WHERE IT CLAIMS TO BE
// ═══════════════════════════════════════════════════════════════════════════
test("double: sRGB<->linear transfer matches the value three r160 stores", () => {
  // three's Color.setHex(0xff8000) is sRGB->linear: (1, 0.2158612, 0) at 1e-6.
  const c = new THREE.Color(0xff8000);
  assert.equal(Math.round(c.r * 1e6), 1000000);
  assert.equal(Math.round(c.g * 1e6), 215861);
  assert.equal(Math.round(c.b * 1e6), 0);
  assert.equal(c.getHexString(), "ff8000", "round-trip must return the authored hex");
  // The dark museum background is NOT linear-black: quantization error here would
  // make every fog receipt a lie about the look.
  const bg = new THREE.Color(0x1e1a30);
  assert.ok(bg.r > 0 && bg.b > bg.r, `0x1e1a30 must lift blue: ${[bg.r, bg.g, bg.b]}`);
  assert.equal(new THREE.Color(0x000000).getHex(), 0);
  assert.equal(new THREE.Color(0xffffff).getHex(), 0xffffff);
  // The gamma curve must BRACKET the identity in both directions. (Written down
  // because the first draft of this assertion had the inequality backwards and
  // only the test caught it: SRGBToLinear(0.5)=0.0387, LinearToSRGB(0.5)=0.7322 —
  // decoding darkens, encoding lifts.) The round-trip tolerance is 1e-4, NOT the
  // harness's 1e-6 receipt quantum, because three r160's own constants are
  // approximations: it encodes with pow(c, 0.41666) instead of 1/2.4, and the
  // seam disagreement is ~3e-5. The double is faithful to three, which is the
  // contract; matching the sRGB standard better than three does would be a fork.
  for (const x of [0.001, 0.04045, 0.05, 0.5, 0.9]) {
    assert.ok(r160.SRGBToLinear(x) < x, `decode must darken: SRGBToLinear(${x}) = ${r160.SRGBToLinear(x)}`);
    assert.ok(r160.LinearToSRGB(x) > x, `encode must lift: LinearToSRGB(${x}) = ${r160.LinearToSRGB(x)}`);
    assert.ok(Math.abs(r160.LinearToSRGB(r160.SRGBToLinear(x)) - x) < 1e-4,
      `round-trip at ${x}: ${r160.LinearToSRGB(r160.SRGBToLinear(x))}`);
  }
  // three's piecewise legs, checked against the IEC 61966-2-1 reference formula
  // (an INDEPENDENT computation, not a transcription of the double's own source):
  // three uses algebraically-optimised constants, so the check is agreement to
  // 1e-5 per leg, which is a real falsifier for a mis-copied constant.
  const iecDecode = (x) => (x <= 0.04045 ? x / 12.92 : Math.pow((x + 0.055) / 1.055, 2.4));
  const iecEncode = (x) => (x <= 0.0031308 ? x * 12.92 : 1.055 * Math.pow(x, 1 / 2.4) - 0.055);
  for (const x of [0.001, 0.02, 0.04045, 0.05, 0.137, 0.5, 0.7354, 0.9, 1]) {
    assert.ok(Math.abs(r160.SRGBToLinear(x) - iecDecode(x)) < 1e-5, `decode leg off at ${x}`);
    assert.ok(Math.abs(r160.LinearToSRGB(x) - iecEncode(x)) < 1e-5, `encode leg off at ${x}`);
  }
  // 0x80 must round-trip to 128/255 through both legs. Tolerance 1e-4 because
  // three encodes with pow(c, 0.41666) (1/2.4 = 0.4166667), a ~6e-6 skew that
  // compounds at the 8-bit boundary.
  assert.ok(Math.abs(r160.LinearToSRGB(0.2158612) - 128 / 255) < 1e-4, "0xff8000's green is 128/255 in sRGB");
  // Out-of-gamut must clamp, not go NaN. Found by testing: without three's
  // clamp-first, a negative channel hit Math.pow(-x, 0.41666) and poisoned every
  // downstream hex with NaN — a loud failure at worst, an unreproducible receipt at best.
  assert.equal(r160.LinearToSRGB(-0.2), 0);
  assert.equal(Math.round(r160.LinearToSRGB(1.5) * 1e9), 1e9);
  const hot = new THREE.Color();
  hot.setRGB(2, -1, 0.5);
  const hx = hot.getHex();
  assert.ok(Number.isInteger(hx) && hx >= 0 && hx <= 0xffffff, `out-of-gamut getHex must stay 24-bit: ${hx}`);
  assert.equal(hx, (255 << 16) | (0 << 8) | Math.round(iecEncode(0.5) * 255),
    "clamp maps (2,-1,0.5) to red-saturated/blue at 8 bits, cross-checked against the IEC encode");
});

test("double: PerspectiveCamera frustum and depth range are real projection", () => {
  const cam = new THREE.PerspectiveCamera(70, 1, 0.1, 500);
  cam.position.set(0, 0, 0);
  cam.lookAt(0, 0, -1);
  cam.updateMatrixWorld();
  // near plane maps to ndc.z = -1, far to +1 (three's convention).
  const zn = new THREE.Vector3(0, 0, -0.1).project(cam);
  const zf = new THREE.Vector3(0, 0, -500).project(cam);
  assert.equal(Math.round(zn.z * 1e6), -1000000);
  assert.equal(Math.round(zf.z * 1e6), 1000000);
  // Half-height at the near plane is near*tan(fov/2): ndc.y of that point is +-1.
  const edge = new THREE.Vector3(0, 0.1 * Math.tan((70 * Math.PI) / 360), -0.1).project(cam);
  assert.equal(Math.round(edge.y * 1e6), 1000000);
  // An off-axis point at fov 70/aspect 1 lands outside ndc — and at exactly
  // 1/tan(fov/2), which is the analytic answer. A placeholder projection that
  // only got the depth range right would pass the tests above and fail here.
  const side = new THREE.Vector3(1, 0, -1).project(cam);
  assert.equal(Math.round(side.x * 1e6), Math.round((1 / Math.tan((35 * Math.PI) / 180)) * 1e6),
    `ndc.x must be 1/tan(35deg) at z=-1: got ${side.x}`);
  assert.ok(side.x > 1, "an off-axis point must fall outside the frustum");
});

test("double: a degenerate camera throws instead of leaking NaN into a receipt", () => {
  const cam = new THREE.PerspectiveCamera(70, 1, 0.1, 500);
  cam.position.set(0, 1.7, 0);
  cam.lookAt(0, 1.7, 0); // eye == target
  assert.throws(() => cam.updateMatrixWorld(), /zero-length camera forward axis/);
  const up = new THREE.PerspectiveCamera(70, 1, 0.1, 500);
  up.position.set(0, 0, 0);
  up.lookAt(0, -1, 0); // forward parallel to up
  assert.throws(() => up.updateMatrixWorld(), /up is parallel/);
});

test("double: material params passed to a constructor beat the class default", () => {
  // Regression found while building this harness: subclass field assignments land
  // AFTER super(), so a naive double silently overwrites the caller's values and
  // every material receipt becomes a description of the double.
  const m = new THREE.MeshPhysicalMaterial({ roughness: 0.05, metalness: 0.5, color: 0x123456 });
  assert.equal(m.roughness, 0.05);
  assert.equal(m.metalness, 0.5);
  assert.equal(m.color.getHexString(), "123456");
  assert.equal(m.clearcoat, 0, "untouched defaults still come from the class");
  assert.equal(m.type, "MeshPhysicalMaterial");
});

test("double: r160 identity flags art's own code branches on", () => {
  // measured: applyEnvironmentMapToScene() applied to 0 materials until these
  // existed, because it selects on isMeshStandardMaterial/isMeshPhysicalMaterial.
  const std = new THREE.MeshStandardMaterial();
  const phys = new THREE.MeshPhysicalMaterial();
  assert.equal(std.isMeshStandardMaterial, true);
  assert.equal(phys.isMeshPhysicalMaterial, true);
  assert.equal(phys.isMeshStandardMaterial, true, "physical extends standard in r160");
  assert.equal(new THREE.MeshBasicMaterial().isMeshBasicMaterial, true);
  assert.equal(new THREE.MeshPhysicalMaterial().isMaterial, true);
  assert.equal(new THREE.DataTexture(new Uint8Array(4), 1, 1).isTexture, true);
  // r160 does NOT define material.dispersion — the museum guards on it, and a
  // double that invents the field would pin a capability the browser lacks.
  assert.equal("dispersion" in new THREE.MeshPhysicalMaterial(), false);
});

test("double: Math.random is refused on sight", () => {
  assert.throws(() => THREE.MathUtils.randFloat(0, 1), /Math.random\(\) is not allowed/);
});

test("double: construction ids and the dispose tally reset per scene", () => {
  const recorder = { disposes: [], events: [] };
  const d = createThreeDouble(recorder);
  const a = new d.THREE.MeshPhysicalMaterial();
  d.reset();
  const b = new d.THREE.MeshPhysicalMaterial();
  assert.equal(a.id, b.id, "a receipt must not depend on which scene ran first");
  const pm = new d.THREE.PMREMGenerator({});
  pm.fromScene({}, 0.04, 0.1, 40);
  assert.match(recorder.events.at(-1), /PMREM\.fromScene\(sigma=0\.04,near=0\.1,far=40\)/);
  d.reset();
  assert.equal(recorder.events.length, 0);
});

test("recorder: the 2D context records state and op order, and refuses the unknown", () => {
  const { canvas, ops, ctx } = makeRecordingCanvas(8, 4);
  ctx.fillStyle = "#ff0000";
  ctx.fillRect(0, 0, 8, 4);
  const g = ctx.createRadialGradient(4, 2, 0, 4, 2, 4);
  g.addColorStop(0, "rgba(1, 2, 3, 0.5)");
  g.addColorStop(1, "transparent");
  ctx.strokeStyle = g;
  ctx.beginPath();
  ctx.arc(4, 2, 1, 0, Math.PI * 2);
  ctx.stroke();
  assert.equal(canvas.getContext(), ctx);
  assert.deepEqual(ops.map((o) => o[0]), [
    "set", "fillRect", "createRadialGradient", "rad", "rad.stop", "rad.stop",
    "set", "beginPath", "arc", "stroke",
  ], "the stream is the receipt: order is load-bearing, and building a gradient " +
     "is itself an op (a hidden cached gradient would otherwise digest unchanged)");
  assert.equal(ctx.fillStyle, "#ff0000");
  // The gradient must carry its own stops into the stream — this is how a
  // palette change reaches a 2D receipt.
  assert.match(JSON.stringify(ops), /rgba\(1, 2, 3, 0.5\)/);
  assert.throws(() => ctx.conicGradientNotARealThing, /unrecorded 2D member read/);
  assert.throws(() => { ctx.globalRotation = 1; }, /unrecorded 2D member write/);
});

test("digest: quantized, key-sorted, and NaN-refusing", () => {
  assert.equal(digestOf({ b: 1, a: 2 }), digestOf({ a: 2, b: 1 }), "key order must not matter");
  assert.notEqual(digestOf({ a: [1, 2] }), digestOf({ a: [2, 1] }), "array order must matter");
  assert.equal(digestOf({ a: 1.0000000001 }), digestOf({ a: 1 }), "quantized to 1e-6");
  assert.notEqual(digestOf({ a: 1.000001 }), digestOf({ a: 1 }));
  assert.throws(() => digestOf({ a: NaN }), /NaN in receipt/);
  assert.equal(canonical(JSON.parse('{"a":null}')), '{"a":null}');
  // Infinity is a legal three default (MeshPhysicalMaterial.attenuationDistance);
  // it must encode to a stable sentinel, not the invalid JSON literal.
  assert.equal(canonical({ a: Infinity }), '{"a":"inf"}');
  const long = "x".repeat(300);
  assert.match(canonical({ s: long }), /__text":300,"sha256"/, "GLSL-sized strings hash instead of dumping");
  assert.equal(digestOf({ s: long }), digestOf({ s: long }));
  assert.notEqual(digestOf({ s: long }), digestOf({ s: `${long}y` }));
});

// ═══════════════════════════════════════════════════════════════════════════
// 2. THE CORPUS IS DETERMINISTIC
// ═══════════════════════════════════════════════════════════════════════════
test("corpus: five pinned scenes, each digesting a real art module", async () => {
  const r = await corpusReport();
  assert.deepEqual(
    r.scenes.map((s) => s.id),
    [
      "museum.rotunda-hero",
      "museum.wing-forge",
      "museum.material-and-env-contract",
      "gen.colony-atlas",
      "gen.spark-frame-1024",
    ],
  );
  for (const s of r.scenes) {
    assert.match(s.hash, HEX64, `${s.id} hash shape`);
    assert.ok(["lookGraph", "drawStream"].includes(s.kind), `${s.id} kind`);
    assert.ok(s.surfaces.length > 0, `${s.id} names no subject module`);
    for (const surf of s.surfaces) {
      if (surf.endsWith(")")) continue; // annotated entry, e.g. "architecture.js (createMuseumMaterials)"
      const clean = surf.split(" ")[0];
      assert.ok(existsSync(join(REPO, clean)), `${s.id} pins a path that is not in the repo: ${surf}`);
    }
  }
  // The two kinds are both present — this is not a single-surface token test.
  assert.ok(r.scenes.some((s) => s.kind === "drawStream") && r.scenes.some((s) => s.kind === "lookGraph"));
});

test("determinism: double run in one process, and re-run against the stamped file", async () => {
  const first = await corpusReport();
  const second = await runAll();
  const stamped = readReceipts();
  assert.equal(stamped.contract, CONTRACT, "receipts.json was stamped under a different contract");
  for (const s of first.scenes) {
    assert.equal(second.byId[s.id].hash, s.hash, `${s.id} moved between runs of the same process`);
    assert.equal(stamped.scenes[s.id].hash, s.hash,
      `${s.id} DRIFTS from receipts.json — a lighting/material/palette surface moved. ` +
      `Inspect the diff, then re-stamp with: node tests/lookdev/lookdev.mjs --update`);
  }
  for (const id of Object.keys(stamped.scenes)) {
    assert.ok(first.byId[id], `receipts.json pins ${id}, which the corpus no longer runs`);
  }
});

test("determinism: run history cannot reach into a receipt", async () => {
  // patent-portfolio/lib/materials.js keeps currentQuality, pmremGenerator and
  // globalEnvMap as module singletons. A second pass must reproduce the first
  // pass's material receipt exactly, or the corpus is only deterministic in the
  // narrow case where it is the first thing that ever ran.
  const a = await runAll();
  const b = await runAll();
  const c = await runAll();
  for (const id of Object.keys(a.byId)) {
    assert.equal(b.byId[id].hash, a.byId[id].hash, `${id} differs on pass 2`);
    assert.equal(c.byId[id].hash, a.byId[id].hash, `${id} differs on pass 3`);
  }
  const mat = a.byId["museum.material-and-env-contract"].graph;
  // One PMREM owner (V10's ask): exactly one generator construction, one cube
  // update, one fromCubemap — and no second PMREM anywhere in the scene.
  const pmremEvents = mat.pmrem.events.filter((e) => e.startsWith("PMREM."));
  assert.deepEqual(pmremEvents.filter((e) => e.startsWith("PMREM.from")), ["PMREM.fromCubemap(CubeRenderTargetTexture)"]);
  assert.equal(mat.pmrem.events.filter((e) => e.startsWith("CubeCamera.update")).length, 1);
  assert.equal(mat.pmrem.events.filter((e) => e.startsWith("PMREM.compileEquirectangularShader")).length, 1);
  // One dispose owner: the scene released geometry, materials, textures and the
  // cube target it built. A zero here means the tally is not being recorded.
  assert.ok(mat.pmrem.disposes.length > 30, `dispose tally too small to be real: ${mat.pmrem.disposes.length}`);
  assert.ok(mat.pmrem.disposes.some((d) => d.startsWith("renderTarget:")), "the cube render target was never disposed");
});

test("determinism: Math.random cannot be digested, by construction", async () => {
  // The trap itself.
  await assert.rejects(
    inDeterministicContext(() => Math.random()),
    /Math\.random\(\) reached a pinned scene/,
    "the random trap must fire before a hash is ever taken",
  );
  // And the reason the corpus's exclusion rule exists: every Math.random site in
  // patent-portfolio/lib/materials.js sits BEHIND a DOM call (createMarbleMaterial
  // at :720, createNoiseTexture at :933-954), so the museum's texture builders are
  // refused twice over — no canvas, then no dice. Both shapes are refusals; the
  // thing this test forbids is a third outcome, a silently stamped hash.
  const { createMarbleMaterial, createNoiseTexture } = await import(
    new URL("../../patent-portfolio/lib/materials.js", import.meta.url)
  );
  for (const [name, fn] of [["createMarbleMaterial", createMarbleMaterial], ["createNoiseTexture", () => createNoiseTexture(8)]]) {
    await assert.rejects(inDeterministicContext(fn), (err) => {
      assert.match(
        `${name}: ${err.message}`,
        /Math\.random\(\) reached a pinned scene|document is not defined/,
        `${name} failed for a reason the boundary list does not name`,
      );
      return true;
    });
  }
});

test("lighting: the wing receipt actually sees the zone transition it pins", async () => {
  const r = await corpusReport();
  const wing = r.byId["museum.wing-forge"].graph;
  const hero = r.byId["museum.rotunda-hero"].graph;
  const densities = wing.timeline.map((s) => s.fog.density);
  assert.ok(densities.at(-1) > densities[0], "ganzfeld density must climb toward the wing target");
  const hexes = wing.timeline.map((s) => s.fog.color.hex);
  assert.notEqual(hexes[0], hexes.at(-1), "fog colour must lerp toward the Forge profile");
  assert.equal(new Set(hero.timeline.map((s) => s.fog.density)).size, 1, "rotunda fog is pinned at 0.004");
  // The god-ray breathing is time-varying: a flat receipt would mean update()
  // never ran and the corpus would be pinning the constructor, not the look.
  const suns = hero.timeline.map((s) => s.sun.intensity);
  assert.ok(new Set(suns).size === suns.length, "sunlight intensity must move every sample");
  // And the dispose path is exercised: teardown must empty the stage (V10's
  // "one dispose owner"). 29 lights is the rotunda's own count at this base.
  assert.equal(hero.teardown.lightsBefore, hero.timeline.at(-1).lights.length);
  assert.equal(hero.teardown.lightsAfter, 0, "TurrellLighting.dispose() leaked a light");
  assert.deepEqual(hero.teardown.leaked, []);
  assert.ok(hero.tally.disposes.length > 0, "no dispose tally recorded");
});

// ═══════════════════════════════════════════════════════════════════════════
// 3. SENSITIVITY: every pin must move exactly the scenes it claims to reach
// ═══════════════════════════════════════════════════════════════════════════
test("falsifier: perturbing a pin constant moves the declared scene set, and only it", async () => {
  const baseline = await runAll();
  for (const [axis, pins] of Object.entries(PERTURB)) {
    const moved = await runAll(pins);
    const changed = moved.scenes.filter((s) => baseline.byId[s.id].hash !== s.hash).map((s) => s.id);
    const required = SENSITIVITY[axis];
    assert.ok(required, `axis "${axis}" has no declared sensitivity — declare which scenes it must reach`);
    assert.deepEqual(
      changed.slice().sort(),
      required.slice().sort(),
      `axis ${axis}: expected exactly [${required}] to move, got [${changed}]`,
    );
  }
  // The required falsifier from the brief, stated as its own failure message.
  const perturbedSeed = await runAll(PERTURB.seed);
  for (const id of SENSITIVITY.seed) {
    assert.notEqual(
      perturbedSeed.byId[id].hash,
      baseline.byId[id].hash,
      `perturbing the seed constant left ${id} unchanged: the receipt is a paraphrase, not the look`,
    );
  }
});

test("falsifier: the corpus is not sensitive to wall clock or process noise", async () => {
  const a = await runAll();
  await new Promise((r) => setTimeout(r, 35));
  const b = await runAll();
  for (const s of a.scenes) assert.equal(b.byId[s.id].hash, s.hash, `${s.id} moved with elapsed time`);
});

test("sensitivity: the 2D receipt sees the drawing, not a metadata paraphrase", async () => {
  const r = await corpusReport();
  const spark = r.byId["gen.spark-frame-1024"].graph;
  assert.ok(spark.ops.count > 1000, `only ${spark.ops.count} ops recorded — the stream is thin`);
  // Same seed, same op count, same stream digest: the metadata alone (burstCount
  // etc.) would survive a broken renderer; the stream would not.
  const again = (await runAll({ genSeed: "kagami" })).byId["gen.spark-frame-1024"];
  assert.equal(again.graph.ops.count, spark.ops.count);
  const meta = spark.meta.params;
  assert.ok(meta.burstCount >= 4 && meta.particleCount >= 100, "spark's own parameter floors moved");
});

test("coverage: the atlas digest carries every colony from the real palette table", async () => {
  const r = await corpusReport();
  const atlas = r.byId["gen.colony-atlas"].graph;
  assert.deepEqual(atlas.grid.colonies, ["spark", "forge", "flow", "nexus", "beacon", "grove", "crystal"]);
  assert.equal(atlas.cells.length, atlas.grid.seeds.length * atlas.grid.colonies.length);
  assert.equal(atlas.grid.cells[0], atlas.grid.seeds.length);
  for (const cell of atlas.cells) {
    assert.notEqual(cell.palette, null);
    assert.notEqual(cell.shifted, cell.palette, "the second draw of the same rng must differ — PRNG state is being consumed");
  }
});

// ═══════════════════════════════════════════════════════════════════════════
// 4. SOURCE DRILL — a one-digit edit must move a receipt
// ═══════════════════════════════════════════════════════════════════════════
test("drill: an untouched copy reproduces the stamp, a one-digit edit breaks it", async () => {
  const d = await runDrill();
  assert.equal(
    d.controlMatchesPinned,
    true,
    `drill control (${d.controlHash.slice(0, 16)}) did not reproduce the stamped ${DRILL.scene} receipt ` +
      `(${String(d.pinnedHash).slice(0, 16)}) — the scratch run is not equivalent, so the edit proves nothing`,
  );
  assert.equal(
    d.editedDiffers,
    true,
    `changing "${DRILL.pattern}" to "${DRILL.replacement}" left the receipt IDENTICAL — ` +
      `a lighting edit could fold with every receipt green`,
  );
});

// ═══════════════════════════════════════════════════════════════════════════
// 5. DECLARED BOUNDARY + WRITE-SET RESPECT
// ═══════════════════════════════════════════════════════════════════════════
test("boundary: every unreachable surface is named with a reason", () => {
  assert.ok(COVERAGE.length >= 5, "the boundary list shrank — an unexplained gap is how drift hides");
  const kinds = new Set();
  for (const c of COVERAGE) {
    assert.ok(["boundary", "absent"].includes(c.kind), `unknown coverage kind "${c.kind}"`);
    assert.ok(c.surface && c.why && c.why.length > 40, `${c.surface}: a boundary without a reason is a TODO`);
    kinds.add(c.kind);
  }
  assert.deepEqual([...kinds].sort(), ["absent", "boundary"]);
  // The V10 ask that cannot be pinned yet stays visible as a typed absence.
  assert.ok(COVERAGE.some((c) => c.kind === "absent" && /demos\/groups/.test(c.surface)));
  assert.ok(COVERAGE.some((c) => /main\.js/.test(c.surface)), "the renderer-assembly gap must stay declared");
});

test("write-set: this lane reached none of the in-flight lanes' paths", async () => {
  const r = await corpusReport();
  const specs = await corpus();
  const touched = [
    ...r.scenes.flatMap((s) => s.surfaces),
    ...specs.flatMap((s) => s.surfaces),
    RECEIPT_FILE.replace(REPO + "/", ""),
  ];
  const forbidden = [
    "patent-portfolio/demos/",   // V6 + V7
    "data/",                     // V6
    "zke8/",                     // V7
    "sitemap", "robots.txt", "llms.txt", "scripts/check-site.mjs", // CS1
  ];
  for (const entry of touched) {
    for (const f of forbidden) {
      assert.ok(!entry.startsWith(f) && !entry.includes(`/demos/`),
        `lookdev pins ${entry}, which is inside an in-flight write-set (${f})`);
    }
  }
  // And the harness files themselves are inside tests/lookdev/, the one new path
  // this lane was granted.
  const self = readFileSync(join(REPO, "tests/lookdev/lookdev.mjs"), "utf8");
  assert.ok(self.includes("registerHooks"), "the shim is what makes this run without a dependency");
  assert.ok(!/require\(['"]three['"]\)/.test(self));
  const pkg = JSON.parse(readFileSync(join(REPO, "package.json"), "utf8"));
  assert.ok(!pkg.dependencies || Object.keys(pkg.dependencies).every((d) => d !== "three"), "no three dependency added");
  assert.ok(!pkg.devDependencies?.three, "no three devDependency added");
  const lines = self.split("\n").length;
  assert.ok(lines > 400, `harness is ${lines} lines — too small to be a real port`);
  const digest = createHash("sha256").update(self).digest("hex").slice(0, 12);
  assert.match(digest, /^[0-9a-f]{12}$/, "digest self-check wiring");
});

test("receipts file: is machine-shaped and points at the harness as its only writer", () => {
  const stamped = readReceipts();
  assert.match(stamped.note, /never hand-edit/);
  assert.ok(/--update/.test(stamped.note), "the re-stamp route must be recorded in the artifact");
  for (const [id, row] of Object.entries(stamped.scenes)) {
    assert.match(row.hash, HEX64, `${id} is not a sha256`);
    assert.ok(row.bytes > 1000, `${id} digests ${row.bytes} bytes — a receipt that small is not the look`);
    assert.ok(row.title && row.surfaces.length, `${id} row lost its provenance`);
  }
  assert.ok(stamped.pinnedAtBase === "unknown" || /^[0-9a-f]{40}$/.test(stamped.pinnedAtBase),
    `pinnedAtBase "${stamped.pinnedAtBase}" is not a commit sha — stamp with LOOKDEV_BASE=$(git rev-parse HEAD)`);
});
