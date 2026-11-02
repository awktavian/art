/**
 * Scoped tests for the CFSG group atlas (lane V6, RSI40-1102).
 *
 * Run from the repository root with:
 *   node --test patent-portfolio/demos/groups/tests/*.test.mjs
 *
 * These are the invariants the piece rests on, checked against the shipped
 * artifacts rather than against the generator's own opinions:
 *
 *   1. data integrity — every order the atlas prints is either re-derived from
 *      the published Lie-type formula with BigInt arithmetic, or at minimum
 *      consistent between its factorisation and its decimal value;
 *   2. provenance integrity — every pointer in data/provenance.json resolves to
 *      a real file in the cfsg checkout, at a line that exists, whose bytes
 *      still hash to the recorded sha256, and whose quote is the text that is
 *      actually on that line (verbatim pointers) or is labelled as the
 *      generator's own note with the real line kept beside it (derived);
 *   3. scene integrity — the layout built from the data is finite,
 *      self-consistent, and byte-stable, and the CPU picker agrees with the
 *      projection that put the pixel there;
 *   4. the falsifier itself — the pure-CPU reference rasterizer is
 *      byte-identical across runs at a fixed seed and differs at another.
 *
 * No browser, no GPU, no network: everything here runs in node against the
 * committed artifacts. The browser tier is `tools/determinism.mjs` (run it with
 * `node tools/determinism.mjs --require-gpu`); it needs Playwright and a WebGL2
 * context, and it is the thing that pins the rendered bytes.
 */

import { test } from "node:test";
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { existsSync, readFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

import {
  buildLayout,
  encodeNodes,
  encodePoints,
  encodeFilaments,
  pickNode,
  cameraPoseAt,
  colorForCharacteristic,
  NODE_STRIDE,
  POINT_STRIDE,
  FILAMENT_STRIDE,
  LAYOUT_SCHEMA,
  LIE_FOLD_ANGLE,
  CAMERA_PERIOD_MS,
} from "../modules/layout.js";
import { frustum, lookAt, project, rayThrough, perspective, NEAR, FAR } from "../modules/mat4.js";
import { makeProvenanceReader, describeArms, describeNode, citeOf, attributionWord } from "../modules/describe.js";
import { renderReference } from "../tools/reference-raster.mjs";

const HERE = dirname(fileURLToPath(import.meta.url));
const GROUPS = resolve(HERE, "..");
const DATA = JSON.parse(readFileSync(join(GROUPS, "data/cfsg-families.json"), "utf8"));
const PROV = JSON.parse(readFileSync(join(GROUPS, "data/provenance.json"), "utf8"));

/**
 * The cfsg checkout the sidecar points into. Read-only here, and optional: on a
 * machine without it the citation test reports a typed skip rather than a green.
 */
const CFSG_ROOTS = [
  process.env.CFSG_ROOT,
  "/Users/schizodactyl/projects/cfsg",
].filter(Boolean);
const CFSG = CFSG_ROOTS.find((r) => existsSync(join(r, "CFSG/Statement.lean")));

// ---------------------------------------------------------------- 1. data

test("orders are re-derived from the published formulas where the notation allows it", () => {
  const gcd = (a, b) => {
    a = a < 0n ? -a : a; b = b < 0n ? -b : b;
    while (b) { const t = a % b; a = b; b = t; }
    return a;
  };
  // Only two term shapes are handled: an integer `gcd k (expr)` and the plain
  // `^ * / + - ()` arithmetic. The five families whose order polynomial is
  // written as a Lean `Finset.Icc` product (ordA, ordBC, ordD, ordTwistedA,
  // ordTwistedD) are NOT evaluated here — re-parsing them badly would be worse
  // than not re-parsing them at all, so they fall to the factorisation check
  // below and this test says so out loud.
  const compile = (formula, params) => {
    if (/[∏∈]|Icc/.test(formula)) return null;
    const src = formula
      .replace(/\bgcd\s+(\d+)\s+(\([^()]*\))/g, "gcdN($1n,$2)")
      .replace(/\^/g, "**")
      .replace(/\b(\d+)(?![\w.])/g, "$1n");
    if (/\bgcd\b/.test(src)) return null;
    try { return Function("gcdN", ...params, `return (${src});`); } catch { return null; }
  };

  let evaluated = 0;
  const unevaluated = [];
  for (const [id, family] of Object.entries(DATA.lieFamilies)) {
    if (!id.startsWith("ord") || !family.formula) continue;
    const fn = compile(family.formula, family.params);
    if (!fn) { unevaluated.push(`${id} (${family.displayName})`); continue; }
    for (const sample of family.sampleOrders || []) {
      const args = family.params.map((p) => sample[p]);
      assert.ok(!args.some((a) => a === undefined || a === null), `${id}: sample is missing a parameter`);
      const value = fn(gcd, ...args.map((a) => BigInt(a)));
      assert.equal(value, BigInt(sample.order), `${id} at ${JSON.stringify(args)}: formula and data disagree`);
      evaluated += 1;
    }
  }
  assert.ok(evaluated >= 20, `expected to re-derive at least 20 orders, got ${evaluated}`);
  assert.deepEqual(
    unevaluated.map((u) => u.split(" ")[0]).sort(),
    ["ordA", "ordBC", "ordD", "ordTwistedA", "ordTwistedD"],
    "the Icc-product families are the only ones not re-evaluated",
  );
});

test("every order is factorisation-consistent", () => {
  const product = (text) => text.split("·").reduce((acc, term) => {
    const m = /^\s*(\d+)(?:\^(\d+))?\s*$/.exec(term);
    assert.ok(m, `unparsable factor "${term}" in "${text}"`);
    return acc * (BigInt(m[1]) ** BigInt(m[2] || 1));
  }, 1n);

  const rows = [];
  for (const [id, family] of Object.entries(DATA.lieFamilies)) {
    if (!id.startsWith("ord")) continue;
    for (const s of family.sampleOrders || []) rows.push([`${id}@n=${s.n},q=${s.q}`, s.order, s.factorization]);
  }
  for (const s of DATA.sporadicOrders.asWritten || []) rows.push([`asWritten:${s.value}`, s.value, s.factorization]);
  for (const s of DATA.classification.alternatingSeries || []) rows.push([`A_${s.n}`, s.order, s.factorization]);
  for (const s of DATA.classification.cyclicPrimeSeries || []) rows.push([`C_${s.p}`, s.order, s.factorization]);

  assert.ok(rows.length >= 80, `only ${rows.length} factorised orders found`);
  for (const [where, decimal, factorization] of rows) {
    assert.equal(product(factorization), BigInt(decimal), `${where}: factorisation does not multiply to the order`);
  }
});

test("the generator's own self-checks all passed, and are named", () => {
  const checks = DATA.meta.selfChecks;
  assert.ok(Array.isArray(checks) && checks.length >= 15, "expected at least 15 self-check rows");
  for (const c of checks) {
    assert.ok(c.name, "every self-check carries a name");
    assert.equal(c.pass, true, `self-check failed: ${c.name}`);
  }
  const names = checks.map((c) => c.name).join("|");
  // the checks that would let a fabricated root system through
  for (const t of ["G2", "F4", "D4", "E6", "E7", "E8"]) {
    assert.match(names, new RegExp(`${t} root closure`), `${t} closure is not checked`);
  }
});

test("root systems are the ones the Cartan matrices generate", () => {
  // Independent re-computation of CFSG's own closure rule, in the basis the
  // data is written in: a root is a vector of simple-root coefficients, and
  //   s_i(v) = v - (Σ_j cartan[i][j]·v_j)·e_i
  // is the reflection in the i-th simple root (this is the rule describe.js
  // quotes back to the user, so the test checks the thing the page claims).
  const expected = { G2: 12, F4: 48, D4: 24, E6: 72, E7: 126, E8: 240 };
  for (const [type, count] of Object.entries(expected)) {
    const entry = DATA.exceptional[type];
    assert.ok(entry, `${type} is missing from the data`);
    assert.equal(entry.rootCount, count, `${type} root count`);
    assert.equal(entry.roots.length, count, `${type} roots listed`);
    assert.equal(entry.positiveCount, count / 2, `${type} positive roots`);
    assert.equal(entry.cartan.length, entry.rank, `${type} Cartan matrix is rank × rank`);
    for (let i = 0; i < entry.rank; i += 1) {
      assert.equal(entry.cartan[i][i], 2, `${type}: diagonal of a Cartan matrix is 2`);
      assert.equal(entry.cartan[i].length, entry.rank, `${type} row ${i} length`);
      for (let j = 0; j < entry.rank; j += 1) {
        if (i !== j) assert.ok(entry.cartan[i][j] <= 0, `${type}: off-diagonal entries are non-positive`);
      }
    }
    const C = entry.cartan.map((r) => r.map(BigInt));
    const key = (v) => v.join(",");
    const seen = new Set(entry.roots.map((v) => key(v.map(BigInt))));
    const reflect = (v, i) => {
      const pairing = C[i].reduce((acc, c, j) => acc + c * v[j], 0n);
      return v.map((x, j) => (j === i ? x - pairing : x));
    };
    for (const v of entry.roots) {
      const bv = v.map(BigInt);
      assert.ok(seen.has(key(bv.map((x) => -x))), `${type}: -${key(bv)} is missing (roots come in ±pairs)`);
      for (let i = 0; i < entry.rank; i += 1) {
        const r = reflect(bv, i);
        assert.ok(seen.has(key(r)), `${type}: s_${i}(${key(bv)}) = ${key(r)} is not a root`);
      }
    }
    assert.equal(new Set(entry.roots.map((v) => key(v.map(BigInt)))).size, count, `${type} roots repeat`);
    // reflections generate only the listed roots: closing under them adds nothing
    const closure = new Set(seen);
    let grew = true;
    while (grew) {
      grew = false;
      for (const k of [...closure]) {
        const v = k.split(",").map(BigInt);
        for (let i = 0; i < entry.rank; i += 1) {
          const r = key(reflect(v, i));
          if (!closure.has(r)) { closure.add(r); grew = true; }
        }
      }
    }
    assert.equal(closure.size, count, `${type}: closing the listed roots under the simple reflections yields ${closure.size}`);
  }
});

test("sporadic orders agree with the pinned set the source enumerates", () => {
  assert.equal(DATA.meta.crossChecks.sporadicOrderCount, 26);
  assert.equal(Object.keys(DATA.sporadics).filter((k) => !k.startsWith("_")).length, 26 + 1); // + Y443
  const pinned = new Set((DATA.sporadicOrders.asWritten || []).map((s) => s.value));
  for (const value of DATA.meta.crossChecks.theoremPinnedInSporadicSet) {
    assert.ok(pinned.has(value), `${value} is pinned in a theorem but absent from sporadicOrderList`);
  }
  for (const s of DATA.sporadicOrders.asWritten || []) {
    assert.equal(s.value, s.value.trim());
    assert.match(s.expression, /^\d+( \^ \d+)?( \* \d+( \^ \d+)?)*$/, "as-written expression is not the source's shape");
  }
});

test("the Y443 presentation is the one the certificate carries", () => {
  const y = DATA.monsterY443;
  assert.equal(y.generatorCount, 12, "Y443 is the 12-generator Nielsen presentation");
  assert.equal(y.adjacency.length, 8);
  assert.equal(new Set(y.generatorNames).size, y.generatorNames.length, "generator names repeat");
  for (const [a, b] of y.adjacency) {
    assert.ok(a >= 0 && a < y.generatorCount && b >= 0 && b < y.generatorCount, `adjacency index out of range: ${a},${b}`);
    assert.notEqual(a, b, "an involution is not adjacent to itself");
  }
  assert.ok(y.relatorFamilies.length >= 3, "the relator families are not recorded");
});

// ------------------------------------------------------------ 2. provenance

test("every provenance pointer resolves to real bytes at a real line", (t) => {
  if (!CFSG) {
    t.skip(`cfsg checkout not found (looked in ${CFSG_ROOTS.join(", ")}) — citations unverified on this host`);
    return;
  }
  const pointers = Object.entries(PROV.pointers);
  assert.ok(pointers.length >= 100, `only ${pointers.length} pointers`);
  let verbatim = 0;
  let derived = 0;
  for (const [pointer, entry] of pointers) {
    const rel = entry.file.replace(/^cfsg\//, "");
    const abs = join(CFSG, rel);
    assert.ok(existsSync(abs), `${pointer}: cited file does not exist (${abs})`);
    const bytes = readFileSync(abs);
    assert.equal(createHash("sha256").update(bytes).digest("hex"), entry.sha256,
      `${pointer}: the cited file has changed since the sidecar was written`);
    const lines = bytes.toString("utf8").split("\n");
    assert.ok(entry.line >= 1 && entry.line <= lines.length, `${pointer}: line ${entry.line} is out of range`);
    const line = lines[entry.line - 1];
    const flat = (s) => s.replace(/\s+/g, " ").trim();
    if (entry.quoteKind === "derived") {
      derived += 1;
      // the note is the generator's; the real source text is kept beside it
      assert.equal(flat(entry.sourceLine), flat(line), `${pointer}: derived sourceLine is not the cited line`);
      assert.ok(entry.attribution, `${pointer}: a derived pointer must say whose claim it is`);
    } else {
      verbatim += 1;
      assert.equal(entry.quoteKind, "verbatim", `${pointer}: quoteKind is neither verbatim nor derived`);
      assert.ok(flat(line).includes(flat(entry.quote)),
        `${pointer}: quote is not on ${entry.file}:${entry.line}\n  quote: ${entry.quote}\n  line: ${line}`);
    }
  }
  assert.ok(verbatim >= 90 && derived >= 10, `unexpected mix: ${verbatim} verbatim, ${derived} derived`);
});

test("the sidecar records the commit the data was lifted from", () => {
  assert.equal(PROV.source.commit, DATA.meta.sourceCommit);
  assert.equal(PROV.source.repo, DATA.meta.sourceRepo);
  if (CFSG) {
    const head = readFileSync(join(CFSG, ".git/HEAD"), "utf8").trim();
    const sha = /^ref: /.test(head)
      ? readFileSync(join(CFSG, ".git", head.replace("ref: ", "")), "utf8").trim()
      : head;
    // a moved checkout does not invalidate the sidecar — the per-file sha256
    // above is the binding — but it is worth knowing that it has moved.
    assert.ok(sha.length === 40 || sha === "", "could not read the cfsg HEAD");
  }
});

test("describe.js reports absence as absence, never as a number", () => {
  const reader = makeProvenanceReader(PROV);
  assert.equal(reader.loaded, true);
  assert.equal(reader.count, Object.keys(PROV.pointers).length);
  assert.equal(reader.has("/no/such/pointer"), false);
  assert.equal(reader.at("/no/such/pointer"), null);
  assert.equal(reader.cite("/no/such/pointer"), null);
  assert.deepEqual(reader.children("/no/such/pointer"), []);
  const empty = makeProvenanceReader(null);
  assert.equal(empty.loaded, false, "an unloaded sidecar must not read as zero pointers");
  assert.equal(empty.count, 0);
  assert.equal(citeOf(null), null);
  assert.ok(attributionWord("derived"), "attribution words are total");

  const arms = describeArms(DATA, reader);
  assert.equal(arms.length, 4, "knownSimpleOrders has four arms");
  for (const arm of arms) {
    assert.ok(arm.displayName && arm.membership, `${arm.id}: arm is missing its name or membership`);
    assert.match(arm.cite, /:\d+$/, `${arm.id}: the arm has no file:line`);
  }
  assert.deepEqual(arms.map((a) => a.index), [0, 1, 2, 3], "the arms are enumerated in the source's order");
});

test("no panel ever prints the word undefined, null or NaN", () => {
  // the display layer is where an unrecorded absence becomes a lie: a missing
  // key reaches the DOM as the string "undefined" unless the module says so
  // deliberately. `rank` did exactly that before it was recorded as null.
  const layout = buildLayout(DATA, makeProvenanceReader(PROV));
  const reader = makeProvenanceReader(PROV);
  const banned = /\b(undefined|NaN|null|Infinity)\b/;
  let rows = 0;
  for (const node of layout.nodes) {
    const panel = describeNode(node, DATA, reader);
    assert.ok(panel.title, `${node.label}: a panel with no title`);
    assert.ok(panel.kicker, `${node.label}: a panel with no kicker`);
    assert.ok(!banned.test(panel.title), `${node.label}: title leaks ${JSON.stringify(panel.title)}`);
    assert.ok(!banned.test(panel.kicker), `${node.label}: kicker leaks ${JSON.stringify(panel.kicker)}`);
    assert.ok(Array.isArray(panel.rows) && panel.rows.length >= 3, `${node.label}: fewer than three rows`);
    for (const row of panel.rows) {
      rows += 1;
      assert.ok(row.label, `${node.label}: a row with no label`);
      const text = String(row.value);
      assert.ok(!banned.test(text),
        `${node.label} / ${row.label}: value leaks "${text}" — record the absence instead`);
      assert.ok(text.length > 0, `${node.label} / ${row.label}: empty value`);
      // a row without a citation must say whose claim it is, or be marked absent
      assert.ok(row.cite || row.attribution || row.absent,
        `${node.label} / ${row.label}: an uncited, unattributed, unmarked-absent row`);
      if (row.cite) assert.match(row.cite, /^[\w./-]+:\d+$/, `${node.label} / ${row.label}: cite is not file:line — ${row.cite}`);
    }
  }
  assert.ok(rows >= 42 * 3, `only ${rows} rows across 42 panels`);
});

// -------------------------------------------------------------- 3. the scene

test("the layout is finite, self-consistent and byte-stable", () => {
  const layout = buildLayout(DATA, makeProvenanceReader(PROV));
  const s = layout.stats;
  assert.equal(s.layoutSchema, LAYOUT_SCHEMA);
  assert.equal(s.nodes, layout.nodes.length);
  assert.equal(s.points, layout.points.length);
  assert.equal(s.filaments, layout.filaments.length);
  assert.equal(s.sourceCommit, DATA.meta.sourceCommit);
  // 42 crystals: the 16 order polynomials CFSG states (Tits among them) plus
  // the 26 sporadics. 11 of the Lie families carry a literal rank, 5 are the
  // infinite series whose rank is the variable — the page says so, so check it.
  assert.equal(s.sporadics, 26);
  assert.equal(s.lieFamilies, 16);
  assert.equal(s.nodes, s.sporadics + s.lieFamilies);
  assert.equal(s.fixedRankTypes + s.seriesWithVariableRank, s.lieFamilies);
  assert.equal(s.seriesWithVariableRank, 5, "A, B/C, D, ²A, ²D are the variable-rank series");
  assert.equal(s.lieTagRows, 17, "the source's tag table has 17 rows");
  assert.equal(s.sporadicsWithPinnedOrder, 13, "the theorem pins 13 sporadic orders as decimals");
  assert.equal(s.coxeterFolded, 10, "types whose Cartan matrix is stated in the source");
  assert.equal(s.y443Edges, DATA.monsterY443.adjacency.length);
  assert.equal(s.selfChecksPassed, s.selfChecksTotal);
  assert.equal(s.selfChecksTotal, DATA.meta.selfChecks.length);
  assert.equal(s.provenancePointers, Object.keys(PROV.pointers).length);

  // every root dot that got plotted belongs to a family the source gives a root
  // system for, and the count adds up: 702, because the twisted types inherit
  // the untwisted system (²E6 draws E6's 72 roots, ²F4 and Tits draw F4's 48…)
  const lie = layout.nodes.filter((n) => n.kind === "lie");
  assert.equal(lie.reduce((a, n) => a + (n.rootCount || 0), 0), s.rootPoints);
  const perType = {};
  for (const n of lie) if (n.rootCount) perType[n.type] = (perType[n.type] || 0) + 1;
  const rootDots = layout.points.filter((p) => p.kind === "root");
  const dotsPerType = {};
  for (const p of rootDots) dotsPerType[p.type] = (dotsPerType[p.type] || 0) + 1;
  for (const [type, families] of Object.entries(perType)) {
    assert.equal(dotsPerType[type], DATA.exceptional[type].rootCount * families,
      `${type}: plotted dots do not match rootCount × families carrying it`);
    assert.equal(rootDots.filter((p) => p.family && lie.find((n) => n.type === type && n.familyId === p.family)).length,
      dotsPerType[type], `${type}: every dot names a family that carries the system`);
  }
  assert.equal(rootDots.length, s.rootPoints);
  assert.equal(
    s.rootPoints + layout.points.filter((p) => p.kind === "y443").length + s.suborbitPoints + s.armPoints,
    s.points, "the point buffer is roots + Y443 + suborbit + classification arms");
  assert.equal(layout.points.filter((p) => p.kind === "y443").length, DATA.monsterY443.generatorCount);
  // one filament per stated diagram swap: D4 triality and ²E6 are the two the
  // source lists, and each states its transpositions
  assert.equal(s.diagramEdges,
    Object.values(DATA.diagramAutomorphisms).reduce((a, d) => a + (d.swaps || []).length, 0));
  assert.deepEqual(Object.keys(DATA.diagramAutomorphisms).sort(), ["D4", "E6"]);
  assert.equal(s.filaments, s.diagramEdges + s.y443Edges + s.cycleEdges + 8,
    "filaments are diagram, Y443, cycle and suborbit edges (the suborbit graph has 8)");

  const finite = (v) => typeof v === "number" && Number.isFinite(v);
  for (const node of layout.nodes) {
    assert.ok(node.pos.every(finite), `${node.label}: position is not finite`);
    assert.ok(finite(node.radius) && node.radius > 0, `${node.label}: bad radius`);
    assert.ok(node.color.every((c) => finite(c) && c >= 0 && c <= 1), `${node.label}: colour out of range`);
    assert.ok(node.kind === "lie" || node.kind === "sporadic", `${node.label}: unknown kind`);
    assert.ok(node.rank === null || Number.isInteger(node.rank),
      `${node.label}: rank must be an integer or null, never absent`);
    assert.equal(node.rank === null, node.kind === "sporadic" || node.rankVaries === true,
      `${node.label}: an unpinned rank must be paired with rankVaries`);
    if (node.kind === "lie" && node.cartan) {
      // re-derive the residue independently: the facet fold is the LARGEST
      // 4·cos²(π/m) = c_ij·c_ji over adjacent simple-root pairs
      let best = 0;
      for (let i = 0; i < node.cartan.length; i += 1) {
        for (let j = 0; j < node.cartan.length; j += 1) {
          if (i === j) continue;
          best = Math.max(best, node.cartan[i][j] * node.cartan[j][i]);
        }
      }
      assert.equal(node.coxeter.product, best, `${node.label}: fold uses a different Cartan pair than the maximum`);
      assert.ok(best > 0, `${node.label}: a Cartan matrix with no adjacent pair should not be folded`);
      const theta = Math.acos(Math.sqrt(best) / 2);
      assert.ok(Math.abs(node.coxeter.theta - theta) < 1e-12, `${node.label}: fold angle is not arccos(√(c_ij c_ji)/2)`);
      assert.ok(finite(node.coxeter.theta) && node.coxeter.theta > 0 && node.coxeter.theta <= Math.PI / 3 + 1e-9,
        `${node.label}: fold angle out of range`);
      assert.ok(Number.isInteger(node.coxeter.m) && node.coxeter.m >= 3, `${node.label}: Coxeter number m`);
      assert.ok(Math.abs(4 * Math.cos(Math.PI / node.coxeter.m) ** 2 - best) < 1e-9,
        `${node.label}: m and 4·cos²(π/m) disagree with the Cartan product`);
    }
  }
  for (const p of layout.points) {
    assert.ok(p.pos.every(finite), "point position is not finite");
    assert.match(p.kind, /^(root|y443|suborbit|arm:)/, `unexpected point kind ${p.kind}`);
    // dots carry no per-point size: the encoder picks brightness by kind, so a
    // dot's provenance is the only thing that can be asserted per point. Every
    // plotted dot names the line it came from — no dot without a citation.
    assert.match(String(p.cite), /^[\w./-]+:\d+$/, `point ${p.kind} is plotted without a file:line`);
  }
  const pointBuf = encodePoints(layout.points);
  for (let i = 0; i < layout.points.length; i += 1) {
    const brightness = pointBuf[i * POINT_STRIDE + 4];
    assert.ok(Number.isFinite(brightness) && brightness > 0 && brightness <= 1,
      `point ${i} (${layout.points[i].kind}) encodes brightness ${brightness}`);
  }
  for (const f of layout.filaments) {
    assert.ok(f.from.every(finite) && f.to.every(finite), "filament endpoint is not finite");
    assert.ok(f.from.join() !== f.to.join(), "a filament connects a point to itself");
    assert.match(String(f.cite), /^[\w./-]+:\d+$/, `filament ${f.kind} is drawn without a file:line`);
  }

  // nothing on screen is untraceable: every crystal's own sidecar pointer
  // resolves, or has children that do. (The Monster's carrier node was the one
  // that did not — the panel showed a dangling pointer while its rows cited.)
  const reader = makeProvenanceReader(PROV);
  for (const node of layout.nodes) {
    assert.ok(node.pointer, `${node.label}: node carries no sidecar pointer`);
    const own = reader.has(node.pointer);
    const kids = reader.children(node.pointer).length;
    assert.ok(own || kids > 0, `${node.label}: pointer ${node.pointer} resolves to nothing in the sidecar`);
    if (own) assert.match(reader.cite(node.pointer), /^cfsg\/[\w./-]+:\d+$/, `${node.label}: its own pointer has no file:line`);
  }

  // byte-stable: the same data in, the same scene out
  const again = buildLayout(DATA, makeProvenanceReader(PROV));
  assert.equal(JSON.stringify(again.nodes), JSON.stringify(layout.nodes));
  assert.equal(JSON.stringify(again.points), JSON.stringify(layout.points));
  assert.equal(JSON.stringify(again.filaments), JSON.stringify(layout.filaments));
});

test("instance encoders fill exactly the stride they advertise", () => {
  const layout = buildLayout(DATA, makeProvenanceReader(PROV));
  // [buffer, count, stride, last written slot] — the last slot is padding and
  // must stay zero, or the shader's attribute layout and the encoder have
  // drifted apart (the failure mode is garbage crystals, not an exception).
  const cases = [
    ["nodes", encodeNodes(layout.nodes), layout.nodes.length, NODE_STRIDE, 14],
    ["points", encodePoints(layout.points), layout.points.length, POINT_STRIDE, 6],
    ["filaments", encodeFilaments(layout.filaments), layout.filaments.length, FILAMENT_STRIDE, 8],
  ];
  for (const [name, buffer, count, stride, last] of cases) {
    assert.ok(stride > last, `${name}: the declared stride does not cover its slots`);
    assert.equal(buffer.length, count * stride, `${name}: buffer length`);
    for (let i = 0; i < buffer.length; i += 1) {
      // NaN/Infinity in an instance attribute is undefined behaviour on the
      // GPU — it is not "a pixel that looks wrong". This caught a real one:
      // sporadic nodes have no rank, and `undefined === null` is false.
      assert.ok(Number.isFinite(buffer[i]), `${name}: non-finite float at index ${i} (node ${Math.floor(i / stride)}, slot ${i % stride})`);
    }
    for (let i = 0; i < count; i += 1) {
      for (let k = last + 1; k < stride; k += 1) {
        assert.equal(buffer[i * stride + k], 0, `${name}: padding slot ${k} is being written`);
      }
      if (name === "nodes") {
        // slot 14 is the instance id, and it must be the index the shader reads
        assert.equal(buffer[i * stride + 14], i, `${name}: instance id slot does not carry the index`);
      }
    }
  }
  // the sentinel the shader reads as "no rank in the source"
  const nodeBuf = encodeNodes(layout.nodes);
  const sporadicRanks = layout.nodes
    .map((n, i) => (n.kind === "sporadic" ? nodeBuf[i * NODE_STRIDE + 10] : null))
    .filter((v) => v !== null);
  assert.equal(sporadicRanks.length, layout.stats.sporadics);
  for (const r of sporadicRanks) assert.equal(r, -1, "sporadics must encode rank as the absence sentinel");
});

test("the picker agrees with the projector that placed the pixel", () => {
  const layout = buildLayout(DATA, makeProvenanceReader(PROV));
  const camera = layout.camera;
  const pose = cameraPoseAt(0.09, camera);
  const view = lookAt(pose, camera.target, [0, 1, 0]);
  const width = 1280;
  const height = 720;
  // exactly the rig the reference rasterizer uses, so the two agree by
  // construction rather than by coincidence
  const proj = frustum(camera.fovYDeg, width / height);
  const viewport = [0, 0, width, height];

  // independent ray/sphere solve — the test must not just re-run pickNode
  const front = (origin, dir, node) => {
    const o = origin.map((v, k) => v - node.pos[k]);
    const b = 2 * (o[0] * dir[0] + o[1] * dir[1] + o[2] * dir[2]);
    const c = o[0] * o[0] + o[1] * o[1] + o[2] * o[2] - node.radius * node.radius;
    const disc = b * b - 4 * c;
    return disc < 0 ? null : (-b - Math.sqrt(disc)) / 2;
  };

  let checked = 0;
  let exact = 0;
  layout.nodes.forEach((node, index) => {
    const px = project(node.pos, view, proj, viewport);
    if (!px) return;                                     // behind the camera
    if (px.depth < -1 || px.depth > 1) return;           // outside the depth range
    if (px.x < 2 || px.y < 2 || px.x > width - 2 || px.y > height - 2) return;
    checked += 1;
    const ndc = [(px.x / width) * 2 - 1, -((px.y / height) * 2 - 1)];
    const ray = rayThrough(ndc, pose, view, proj);
    // round trip: the ray through the projected centre must aim at the centre
    const aim = node.pos.map((v, k) => v - ray.origin[k]);
    const len = Math.hypot(...aim);
    const dot = (aim[0] * ray.direction[0] + aim[1] * ray.direction[1] + aim[2] * ray.direction[2]) / len;
    assert.ok(dot > 0.999, `node ${index}: the ray through its own pixel misses it (cos = ${dot})`);
    const hit = pickNode(layout.nodes, ray.origin, ray.direction);
    assert.ok(hit >= 0, `node ${index} (${node.label}) is on screen and its own centre is under the cursor, but nothing was picked`);
    if (hit === index) { exact += 1; return; }
    // otherwise the picker returned a nearer crystal — check that it really is
    const tHit = front(ray.origin, ray.direction, layout.nodes[hit]);
    const tSelf = front(ray.origin, ray.direction, node);
    assert.ok(tHit !== null, `picked ${hit} does not intersect the ray it was picked with`);
    assert.ok(tSelf !== null, `node ${index} intersects its own centre ray but was not hit`);
    assert.ok(tHit <= tSelf + 1e-9,
      `node ${index} (${node.label}, t=${tSelf.toFixed(3)}) is nearer than the picked ${hit} (${layout.nodes[hit].label}, t=${tHit.toFixed(3)})`);
  });
  assert.ok(checked >= 10, `only ${checked} nodes were on screen to check`);
  assert.ok(exact >= checked * 0.6, `only ${exact}/${checked} centre rays picked their own node — the silhouettes no longer mean anything`);

  // the picker's oracle, on rays that are not centred on anything: for a set of
  // deterministic directions, pickNode must return the node with the smallest
  // positive front-face distance — no phantom, and no nearer node skipped over
  const dirSet = [];
  let h = 0x811c9dc5;
  for (let k = 0; k < 400; k += 1) {
    h = Math.imul(h ^ (h >>> 15), 0x2c1b3c6d) >>> 0;
    const a = (h / 0xffffffff) * Math.PI * 2;
    h = Math.imul(h ^ (h >>> 13), 0x297a2d39) >>> 0;
    const y = (h / 0xffffffff) * 2 - 1;
    const r = Math.sqrt(Math.max(0, 1 - y * y));
    dirSet.push([Math.cos(a) * r, y, Math.sin(a) * r]);
  }
  let resolved = 0;
  for (const d of dirSet) {
    const origin = [pose[0], pose[1], pose[2]];
    const ts = layout.nodes.map((n) => front(origin, d, n));
    const positive = ts.map((t, i) => [t, i]).filter(([t]) => t !== null && t > 0.001);
    const expect = positive.length ? positive.reduce((a, b) => (b[0] < a[0] ? b : a))[1] : -1;
    assert.equal(pickNode(layout.nodes, origin, d), expect,
      `ray ${d.map((v) => v.toFixed(3)).join(",")}: the picker did not return the nearest crystal`);
    if (expect >= 0) resolved += 1;
  }
  assert.ok(resolved > 0 && resolved < dirSet.length,
    `every test ray hit something or none hit anything (resolved = ${resolved}) — the ray set is degenerate`);

  // and a ray aimed away from the constellation picks nothing
  const outward = pose.map((v) => v / Math.hypot(...pose));
  assert.equal(pickNode(layout.nodes, pose, outward), -1, "looking outward from the shell must pick nothing");
});

test("the camera rig is periodic and finite", () => {
  const layout = buildLayout(DATA, makeProvenanceReader(PROV));
  const camera = layout.camera;
  const a = cameraPoseAt(0, camera);
  const b = cameraPoseAt(1, camera);
  for (let i = 0; i < 3; i += 1) {
    assert.ok(Math.abs(a[i] - b[i]) < 1e-9, `phase 0 and phase 1 differ at axis ${i}`);
  }
  assert.ok(Number.isFinite(LIE_FOLD_ANGLE) && LIE_FOLD_ANGLE > 0 && LIE_FOLD_ANGLE < Math.PI / 2);
  assert.equal(CAMERA_PERIOD_MS, 6100);
  for (let phase = 0; phase < 1; phase += 0.05) {
    for (const v of cameraPoseAt(phase, camera)) assert.ok(Number.isFinite(v));
  }
  assert.ok(FAR > NEAR && NEAR > 0);
  const p = frustum(42, 16 / 9);
  assert.equal(p.length, 16);
  assert.ok(p.every(Number.isFinite));
  // the frustum helper takes degrees and the perspective one radians; they must
  // agree, or a camera change in one place silently zooms the render
  const fromRadians = perspective((42 * Math.PI) / 180, 16 / 9, NEAR, FAR);
  for (let i = 0; i < 16; i += 1) assert.ok(Math.abs(p[i] - fromRadians[i]) < 1e-9, `frustum/perspective differ at ${i}`);

  // the characteristic palette is a pure function: same prime, same colour;
  // different primes, different colours (2/3/5/7/11 are the ones CFSG names)
  const primes = [...new Set([
    ...layout.nodes.filter((n) => n.characteristic).map((n) => n.characteristic),
  ])].sort((a, b) => a - b);
  const colours = new Map();
  for (const prime of primes) {
    const c = colorForCharacteristic(prime);
    assert.equal(c.length, 3, `characteristic ${prime}: not an rgb triple`);
    assert.ok(c.every((v) => Number.isFinite(v) && v >= 0 && v <= 1), `characteristic ${prime}: colour out of range`);
    assert.deepEqual(colorForCharacteristic(prime), c, `characteristic ${prime}: the palette is not pure`);
    const key = c.map((v) => v.toFixed(4)).join(",");
    assert.ok(!colours.has(key), `characteristics ${colours.get(key)} and ${prime} render the same colour`);
    colours.set(key, prime);
  }
  assert.ok(primes.length >= 4, `only ${primes.length} characteristics are represented`);
});

// ------------------------------------------------------------- 4. the falsifier

test("the CPU reference rasterizer is byte-identical at a fixed seed", () => {
  const scene = buildLayout(DATA, makeProvenanceReader(PROV));
  const one = renderReference({ width: 64, height: 36, seed: 12345, frames: 2, phase: 0.09, layout: scene });
  const two = renderReference({ width: 64, height: 36, seed: 12345, frames: 2, phase: 0.09, layout: scene });
  assert.equal(one.sha256, two.sha256, "the same seed produced different bytes");
  assert.equal(one.pngSha256, two.pngSha256);
  assert.equal(Buffer.compare(one.png, two.png), 0, "the PNG payloads differ");
  assert.ok(one.stats.sphereHits > 100, "nothing was hit — the raster is not tracing the scene");
  assert.ok(one.stats.pointDots > 0, "no root points were plotted");
  assert.ok(one.stats.filamentCells > 0, "no filaments were drawn");

  const other = renderReference({ width: 64, height: 36, seed: 99991, frames: 2, phase: 0.09, layout: scene });
  assert.notEqual(other.sha256, one.sha256, "a different seed produced the same bytes");

  // the receipt names the mode it used, and echoes what it rendered — a pin
  // that does not say its own size and seed cannot be re-verified later
  assert.equal(one.stats.tier, "cpu-reference-rasterizer");
  assert.equal(one.stats.layoutSchema, LAYOUT_SCHEMA);
  assert.deepEqual([one.stats.width, one.stats.height, one.stats.frames, one.stats.seed], [64, 36, 2, "12345"]);
  assert.equal(one.stats.nodes, scene.stats.nodes);
  assert.equal(one.stats.points, scene.stats.points);
  assert.equal(one.stats.filaments, scene.stats.filaments);

  // single-sample render is stable too (this is what reduced motion asks for),
  // and a different camera phase gives different bytes — so the pin is pinning
  // geometry, not a constant buffer
  const a1 = renderReference({ width: 64, height: 36, seed: 12345, frames: 1, phase: 0.09, layout: scene });
  const a2 = renderReference({ width: 64, height: 36, seed: 12345, frames: 1, phase: 0.09, layout: scene });
  assert.equal(a1.sha256, a2.sha256, "a single converged sample is not reproducible");
  const moved = renderReference({ width: 64, height: 36, seed: 12345, frames: 1, phase: 0.42, layout: scene });
  assert.notEqual(moved.sha256, a1.sha256, "the camera phase does not reach the raster — the flythrough is decoration");
});

test("the reference PNG is a real PNG of the advertised size", () => {
  const scene = buildLayout(DATA, makeProvenanceReader(PROV));
  const shot = renderReference({ width: 40, height: 24, seed: 7, frames: 1, phase: 0.25, layout: scene });
  assert.equal(shot.png.subarray(0, 8).toString("hex"), "89504e470d0a1a0a");
  assert.equal(shot.png.readUInt32BE(16), 40);
  assert.equal(shot.png.readUInt32BE(20), 24);
  assert.equal(shot.rgba.length, 40 * 24 * 4);
  // the piece is not blank, and not white: it has content and it has a void
  let min = 255;
  let max = 0;
  let lit = 0;
  for (let i = 0; i < shot.rgba.length; i += 4) {
    const l = (shot.rgba[i] + shot.rgba[i + 1] + shot.rgba[i + 2]) / 3;
    min = Math.min(min, l); max = Math.max(max, l);
    if (l > 24) lit += 1;
  }
  assert.ok(max - min > 40, `frame has no dynamic range (${min}..${max})`);
  assert.ok(lit > 20 && lit < 40 * 24, `either empty or blown out: ${lit} lit pixels`);
});
