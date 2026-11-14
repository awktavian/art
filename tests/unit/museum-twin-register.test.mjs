/**
 * Museum twin family — art-side tripwire over the twins register.
 * Lane RSIPIPE2-01-NAV-TWIN-1102, campaign RSI-PIPE2-1102, 2026-11-02.
 *
 * Seed: code_map_rsi_targets generation ccc6b10cf4e942b58e445dc57655dbc2,
 * kind=near_duplicate, path projects/art/patent-portfolio/museum/navigation.js,
 * rankScore 27.74 — BAND ORDER, not a measured quantity.
 *
 * The group that row names is art `patent-portfolio/museum/navigation.js` x
 * `~/projects/awkronos/patents/museum/navigation.js`. That pair is not open copy debt: it was
 * closed as a declared canonical->mirror pair in 2026-10-26 (patents port 72faa42), its
 * bodies are cmp-identical below the two doc headers at today's published tips (re-measured
 * here, rc=0), the patents side carries a 6-leg receipt guard wired to a tracked pre-commit,
 * and the art side has carried a 5-leg drift pin since 2026-11-02 (museum-navigation-mirror
 * .test.mjs, lane RSIPIPE-06-NAVIGATION-1102). What the row actually exposes — and what the
 * census cannot see — is recorded in the register's census_provenance block: both of the
 * pair's pinned identities are NON-PUBLISHED trees (art's parked checkout at 054c275, and a
 * banked `wip` commit in patents that is not an ancestor of its own main).
 *
 * So this lane does not merge and does not delete. It consolidates the DECLARATION. Before
 * this lane the family's facts were restated in four places across two repos — art's module
 * header, art's DEBT note, art's mirror test, and the patents receipt — and the recorded
 * failure of that arrangement is a declaration rotting while its guard stays green. Now:
 *
 *   patent-portfolio/NEAR-DUPLICATE-TWINS.json    one register (generated data)
 *   tests/unit/twin-measure.mjs                   one measurement implementation
 *   scripts/twin-register.mjs                     one re-measure / staleness check
 *   this file                                     one tripwire
 *
 * Divergent content is DECLARED, with a digest per side of each delta — never dropped. The
 * five undeclared sibling pairs (architecture, lighting, wayfinding, wing-enhancements,
 * museum.spec) get pins here for the first time; before this file, a silent edit to any of
 * them went unremarked by any art test. Nothing in this lane touches navigation.js bytes.
 *
 * Node builtins + the sibling test's own source, like the rest of tests/unit/: offline, no
 * credentials. The mirror legs read patents' PUBLISHED tip by the 40-hex the register
 * recorded, via that repo's object db — not its working tree, which is parked (the DEBT
 * note's residual-2 lesson: a reading taken from a working tree is not a published surface).
 * Absent repo/object -> an honest skip, typed UNMEASURED, never a pass.
 *
 * Positive controls run before this file was committed (see the lane receipts): a mutated
 * byte in an art museum module reddens R2; deleting one PROVENANCE header line reddens R4
 * and R6; pointing the mirror leg at a repo with no such object produces the skip, rc=0.
 *
 * Override, same convention family as ARTNAV_MIRROR_PATH / KAGAMI_COLONIES_PY:
 *   ART_TWIN_MIRROR_REPO  default /Users/schizodactyl/projects/awkronos/patents
 */
import { test } from "node:test";
import assert from "node:assert/strict";
import { existsSync, readFileSync } from "node:fs";
import { execFileSync } from "node:child_process";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

import {
  readText,
  fileStats,
  bodyOf,
  sliceStats,
  headerMarkers,
  readRegister,
} from "./twin-measure.mjs";

const REPO = resolve(dirname(fileURLToPath(import.meta.url)), "..", "..");
const REGISTER = readRegister(REPO);
const MIRROR_REPO =
  process.env.ART_TWIN_MIRROR_REPO || "/Users/schizodactyl/projects/awkronos/patents";
const MIRROR_TIP = REGISTER.basis.patents_tip;

/** Bytes at a PUBLISHED tip in the mirror repo's object db; null when this host cannot resolve it. */
function mirrorAtTip(relPath) {
  if (!existsSync(MIRROR_REPO) || !MIRROR_TIP) return null;
  try {
    return execFileSync("git", ["-C", MIRROR_REPO, "show", `${MIRROR_TIP}:${relPath}`], {
      encoding: "utf8",
      maxBuffer: 64 * 1024 * 1024,
    });
  } catch {
    return null;
  }
}

const artPathOf = (row) => join(REPO, row.art.path);

// ── R1: the register is well-formed, and every row names a real file here ────
test("twins register: schema, unique ids, and no phantom rows", () => {
  assert.equal(REGISTER.schema, "art-museum-twin-register/1");
  assert.equal(REGISTER.generated_by, "scripts/twin-register.mjs");
  const ids = REGISTER.pairs.map((p) => p.id);
  assert.equal(new Set(ids).size, ids.length, "pair ids must be unique — pointers name them");
  for (const row of REGISTER.pairs) {
    for (const field of ["id", "kind", "art", "patents", "body_identity", "declaration", "guards", "disposition", "note"]) {
      assert.ok(row[field], `pair ${row.id} is missing ${field}`);
    }
    assert.ok(existsSync(artPathOf(row)), `register names ${row.art.path} but this tree has no such file`);
    assert.match(row.art.blob, /^[0-9a-f]{40}$/, `${row.id}: art blob must be full 40 hex`);
    assert.match(row.art.sha256, /^[0-9a-f]{64}$/, `${row.id}: art sha256 must be full 64 hex`);
  }
  // A pointer that resolves to nothing is how a declaration becomes folklore.
  for (const row of REGISTER.pairs) {
    const pointer = /NEAR-DUPLICATE-TWINS\.json id "([^"]+)"/.exec(readText(artPathOf(row)));
    if (pointer) assert.equal(pointer[1], row.id, `${row.id}: the in-file pointer names a different pair id`);
  }
  for (const law of Object.values(REGISTER.law)) assert.match(law, /\S/, "every law entry carries text");
});

// ── R2: every art pin is the byte truth of THIS tree ────────────────────────
test("twins register: each art-side pin equals this tree, blob for blob", () => {
  for (const row of REGISTER.pairs) {
    const now = fileStats(readText(artPathOf(row)));
    assert.equal(now.blob, row.art.blob, `${row.id}: art blob drifted from the register`);
    assert.equal(now.sha256, row.art.sha256, `${row.id}: art sha256 drifted from the register`);
    assert.equal(now.bytes, row.art.bytes, `${row.id}: art is ${now.bytes} B, register says ${row.art.bytes}`);
    assert.equal(now.lines, row.art.lines, `${row.id}: art is ${now.lines} lines, register says ${row.art.lines}`);
  }
});

// ── R3: navigation.js — register == the sibling drift pin == the tree ───────
/**
 * The anti-restatement leg. museum-navigation-mirror.test.mjs (lane RSIPIPE-06-NAVIGATION-1102)
 * hardcodes this pair's canonical pins; the register restates them as data. Two copies of a pin
 * drift, and the recorded consequence in this family is a guard matching a dead hex. This leg
 * makes the two agree or goes red, so the copies cannot diverge silently.
 */
test("navigation.js: the register and museum-navigation-mirror.test.mjs pin the same bytes", (t) => {
  const src = readText(join(REPO, "tests", "unit", "museum-navigation-mirror.test.mjs"));
  const lit = (name) => {
    const m = new RegExp(`const ${name} =\\s*\\n?\\s*"([0-9a-f]+)"`).exec(src) ||
      new RegExp(`const ${name} = "([0-9a-f]+)"`).exec(src);
    assert.ok(m, `could not read ${name} out of museum-navigation-mirror.test.mjs — did it get renamed?`);
    return m[1];
  };
  const num = (name) => {
    const m = new RegExp(`const ${name} = (\\d+);`).exec(src);
    assert.ok(m, `could not read ${name} out of museum-navigation-mirror.test.mjs`);
    return Number(m[1]);
  };
  const nav = REGISTER.pairs.find((p) => p.id === "museum.navigation.js");
  assert.ok(nav, "register lost the navigation.js pair");

  assert.equal(nav.art.blob, lit("EXPECTED_CANONICAL_BLOB"), "register and drift pin disagree on art's blob");
  assert.equal(nav.art.sha256, lit("EXPECTED_CANONICAL_SHA256"), "register and drift pin disagree on art's sha256");
  assert.equal(nav.body_identity.art.sha256, lit("EXPECTED_BODY_SHA256"), "register and drift pin disagree on the body sha");
  assert.equal(nav.body_identity.art.bytes, num("EXPECTED_BODY_BYTES"), "register and drift pin disagree on body bytes");
  assert.equal(nav.body_identity.art.lines, num("EXPECTED_BODY_LINES"), "register and drift pin disagree on body lines");

  // ...and both agree with the bytes actually in this tree.
  const treeBody = sliceStats(bodyOf(readText(artPathOf(nav)), nav.body_identity.recipe));
  assert.deepEqual(treeBody, nav.body_identity.art, "register's body stats are not this tree's body stats");

  // navigation.js is the file the census keeps naming, so the register, this tree and art's
  // published tip have to be the same statement. This leg USED to compare the register's
  // recorded published blob against the tree, which no seat could pass while folding residual 1:
  // a recorded tip value is stale the instant the fold lands, and the leg could not tell "a lane
  // edited navigation.js" from "this checkout is parked" — both read the same red, so the red
  // carried no information. Both facts are measured live now. R2 above already forces
  // register == tree; below, tree == the tip this host can see, and when they differ git proves
  // the checkout is not on that tip (merge-base --is-ancestor is the only thing that
  // distinguishes in-flight from behind — a range count is identical under fork and fast-forward).
  const pub = REGISTER.census_provenance.row_identities_and_what_they_are.art_leg.published;
  assert.equal(pub.state, "MEASURED", "art's published anchor is UNMEASURED on the host that wrote the register — regenerate where origin/main resolves");
  assert.match(pub.blob, /^[0-9a-f]{40}$/u, `${pub.ref}: the register recorded a published blob that is not 40 hex`);
  const PUB_REF = "refs/remotes/origin/main";
  const atTip = (() => {
    try {
      return execFileSync("git", ["-C", REPO, "show", `${PUB_REF}:${nav.art.path}`], {
        encoding: "utf8",
        maxBuffer: 64 * 1024 * 1024,
      });
    } catch {
      return null;
    }
  })();
  if (atTip === null) {
    t.skip(`${REPO} resolves no ${PUB_REF} — art's published surface is UNMEASURED here, not agreed`);
  } else {
    const liveBlob = fileStats(atTip).blob;
    if (liveBlob !== nav.art.blob) {
      // The difference has to be explained by work in flight, and there are exactly two ways
      // that is true: this checkout carries an uncommitted edit to the path, or HEAD is not on
      // the tip (a lane branch ahead of main). Anything else — clean tree, HEAD on the tip, and
      // the register still naming different bytes — means main moved and nobody re-measured.
      let dirty = false;
      try {
        dirty = execFileSync("git", ["-C", REPO, "status", "--porcelain", "--", nav.art.path], { encoding: "utf8" }).trim().length > 0;
      } catch {
        dirty = false;
      }
      let headOnTip = null;
      try {
        execFileSync("git", ["-C", REPO, "merge-base", "--is-ancestor", "HEAD", PUB_REF], { encoding: "utf8" });
        headOnTip = true;
      } catch (err) {
        headOnTip = typeof err?.status === "number" ? err.status === 0 : null;
      }
      assert.ok(
        dirty || headOnTip === false,
        `art's ${PUB_REF} carries ${liveBlob} for ${nav.art.path} but the register — pinned to this tree, which R2 confirms — carries ${nav.art.blob}, with a CLEAN worktree for that path and HEAD an ancestor of ${PUB_REF}. Nothing is in flight, so this is drift: main moved past a register nobody re-measured. Re-run node scripts/twin-register.mjs --write. (A fold in a seat passes this leg because either the file is dirty or the lane branch is ahead of main — the two states that explain a difference.)`
      );
      t.diagnostic(
        `in-flight: ${PUB_REF} (${liveBlob.slice(0, 12)}…) is not this checkout (${nav.art.blob.slice(0, 12)}…) — ${dirty ? "uncommitted edit to this path" : "HEAD is not on that tip"}; disclosed by git, not believed from a recorded value`
      );
    }
  }
});

// ── R4: a deleted or added header marker is a declaration change, not a typo ─
test("header markers in the tree are the markers the register recorded", () => {
  for (const row of REGISTER.pairs) {
    const now = headerMarkers(readText(artPathOf(row)));
    assert.deepEqual(
      now,
      row.art.header_markers,
      `${row.id}: art header markers changed (${JSON.stringify(row.art.header_markers)} -> ${JSON.stringify(now)}) — the declaration block was edited or deleted; read the pair's disposition before committing`,
    );
  }
});

// ── R5: the declared recipe is what holds the pair together ─────────────────
test("each pair's body identity claim is recomputed under its own declared recipe", (t) => {
  for (const row of REGISTER.pairs) {
    const artBody = bodyOf(readText(artPathOf(row)), row.body_identity.recipe);
    assert.deepEqual(
      sliceStats(artBody),
      row.body_identity.art,
      `${row.id}: body under recipe ${row.body_identity.recipe} is not what the register recorded`,
    );
    if (row.patents.state === "UNMEASURED") continue;
    const patText = mirrorAtTip(row.patents.path);
    if (patText === null) {
      t.diagnostic(`${row.id}: mirror ${MIRROR_TIP}:${row.patents.path} unresolvable on this host — UNMEASURED, not drift`);
      continue;
    }
    const patBody = bodyOf(patText, row.body_identity.recipe);
    assert.deepEqual(sliceStats(patBody), row.body_identity.patents, `${row.id}: mirror body drifted from the register`);
    assert.equal(
      row.body_identity.identical,
      sliceStats(patBody).sha256 === sliceStats(artBody).sha256,
      `${row.id}: register's identical flag contradicts the bytes on this host`,
    );
  }
});

// ── R6: the four spec twins are identical below the header, and say so ──────
test("spec twins: identical below the header, different as whole files, pointer present", (t) => {
  for (const row of REGISTER.pairs.filter((p) => p.kind === "spec" && p.body_identity.identical)) {
    const art = readText(artPathOf(row));
    assert.match(art, /^\/\/ PROVENANCE: mirror of ~\/projects\/awkronos\/patents\//, `${row.id}: art lost its mirror provenance`);
    assert.match(art, /NEAR-DUPLICATE-TWINS\.json id/, `${row.id}: art lost its pointer to the twins register`);
    assert.ok(!/byte-identical as of 2026-08-18/.test(art), `${row.id}: the false whole-file claim is back — the pair is identical BELOW the header, and the header differs by design`);
    assert.equal(row.divergence.hunks, 1, `${row.id}: expected one header hunk, the body was edited`);
    assert.equal(row.art.lines - row.patents.lines, 2, `${row.id}: art's header should be 5 lines against patents' 3`);

    const patText = mirrorAtTip(row.patents.path);
    if (patText === null) {
      t.diagnostic(`${row.id}: mirror unresolvable — UNMEASURED`);
      continue;
    }
    assert.equal(fileStats(patText).blob, row.patents.blob, `${row.id}: mirror whole-file pin drifted`);
    assert.match(patText, /^\/\/ PROVENANCE: canonical source/, `${row.id}: patents no longer declares itself canonical for this spec`);
  }
});

// ── R7: museum.spec.js is a coverage gap, not a fork ────────────────────────
test("museum.spec.js: patents carries nothing art lacks (port-downward gap, not deletable)", (t) => {
  const row = REGISTER.pairs.find((p) => p.id === "spec.museum.spec.js");
  assert.ok(row, "register lost the museum.spec pair");
  assert.equal(row.declaration.status, "undeclared", "museum.spec.js is declared now — update the register and this leg");
  // Degrade on what THIS host can read, not on the register's recorded state: a register
  // generated where the mirror resolved must not make this leg claim a fresh cross-repo
  // measurement where none is possible.
  if (mirrorAtTip(row.patents.path) === null) {
    t.skip(`mirror ${MIRROR_TIP}:${row.patents.path} unresolvable on this host — the 89/0 split below is the register's recorded claim, not a re-measurement`);
  }
  assert.equal(row.divergence.art_only_lines, 89, "the art-only block changed size — re-measure before reading this as a gap");
  assert.equal(row.divergence.patents_only_lines, 0, "patents now carries unique lines — this is a fork again, not a subset");
  assert.match(row.disposition, /port DOWNWARD/i, "disposition no longer says what the measurement says");
});

// ── R8: the not_twins rows are still not twins ──────────────────────────────
test("not_twins: the art-only file exists here and the patents-only names have no art copy", () => {
  for (const n of REGISTER.not_twins) {
    if (n.side === "art-only") {
      assert.ok(existsSync(join(REPO, n.path)), `${n.path} is gone from art`);
      const now = fileStats(readText(join(REPO, n.path)));
      assert.equal(now.sha256, n.pins.sha256, `${n.path} drifted from its register pin`);
    } else {
      const base = n.path.split("/").pop();
      const inArt = execFileSync("git", ["-C", REPO, "ls-files", "**/" + base], { encoding: "utf8" }).trim();
      assert.equal(inArt, "", `patents-only ${base} now has an art copy at ${inArt} — it is a pair, not a not_twin`);
    }
  }
});

// ── R9: the geometry claim that makes "port navigation whole" safe ──────────
test("navigation.js's DIMENSIONS keys are re-derived here and agree in both architecture.js copies", (t) => {
  const nav = readText(join(REPO, "patent-portfolio", "museum", "navigation.js"));
  const keys = [...new Set([...nav.matchAll(/DIMENSIONS\.([A-Za-z0-9_.]+)/g)].map((m) => m[1]))];
  if (mirrorAtTip("museum/architecture.js") === null) {
    t.diagnostic(`mirror ${MIRROR_TIP}:museum/architecture.js unresolvable on this host — the agree/disagree rows are the register's recorded claim; art's side is re-read here`);
  }
  const g = REGISTER.geometry_agreement.sets;
  if (g.state === "UNMEASURED") return;

  // The register's read_by_navigation set must be EXACTLY what navigation.js reads, or the
  // agreement is over the wrong set. Re-derived from the file's own bytes every run.
  assert.deepEqual(
    Object.keys(g.read_by_navigation).sort(),
    keys.slice().sort(),
    `navigation.js reads ${JSON.stringify(keys)} but the register calls ${JSON.stringify(Object.keys(g.read_by_navigation))} "read_by_navigation" — re-measure the register; do not edit this leg`,
  );
  for (const [name, set] of [["read_by_navigation", g.read_by_navigation], ["debt_port_checklist", g.debt_port_checklist]]) {
    for (const [k, v] of Object.entries(set)) {
      assert.ok(v.art !== null, `${name}.${k}: the register recorded a null value — its extractor regex is broken, not the geometry`);
      assert.ok(v.agree, `${name}: DIMENSIONS ${k} disagrees — art ${v.art} vs patents ${v.patents}; the port-checklist claim in the register no longer holds`);
      // art's own value, re-read from this tree rather than trusted from the register
      const m = new RegExp(`${k.split(".")[0]}:\\s*\\{[\\s\\S]*?${k.split(".")[1]}:\\s*([0-9.]+)`).exec(
        readText(join(REPO, "patent-portfolio", "museum", "architecture.js")),
      );
      assert.ok(m, `could not re-read ${k} from art's architecture.js`);
      assert.equal(Number(m[1]), v.art, `${name}.${k}: register disagrees with art's own bytes`);
    }
  }

  // The recorded divergence stays a divergence: navigation.js must never start reading it.
  for (const [k, v] of Object.entries(g.diverged_unread)) {
    assert.ok(!v.agree, `DIMENSIONS ${k} now agrees in both copies — the register's declared-divergence row is stale, re-measure it`);
    assert.ok(!keys.includes(k), `navigation.js now reads ${k}, filed under diverged_unread — a port of navigation.js is no longer geometry-neutral`);
  }
});

// ── R10: the census-provenance claims are checked against this host's refs ──
test("census_provenance: the generation read real bytes, and both of its legs were parked trees", () => {
  const legs = REGISTER.census_provenance.row_identities_and_what_they_are;
  const art = legs.art_leg;
  const pat = legs.patents_leg;
  const HEX40 = /^[0-9a-f]{40}$/;

  // The generation is not wrong about what it read — it read the wrong tree.
  for (const [name, l] of [["art", art], ["patents", pat]]) {
    assert.match(l.recorded_by_generation, HEX40, `${name}: recorded hex is malformed`);
    assert.ok(
      l.re_measured_here.state === "UNMEASURED" || l.re_measured_here.agrees_with_generation === true,
      `${name}: re-measuring the commit the generation indexed gives ${l.re_measured_here.blob}, not the ${l.recorded_by_generation} the register claims — the census row this lane reasons from is not reproducible here`,
    );
  }

  // Both published anchors are measured hexes, distinct from the census legs. That the two
  // differ IS the finding; if they ever collapse, the row is no longer a stale-tree artifact.
  assert.equal(art.published.state, "MEASURED");
  assert.match(art.published.blob, HEX40);
  assert.notEqual(art.recorded_by_generation, art.published.blob, "art's census and published anchors collapsed — re-read the finding");
  assert.notEqual(pat.recorded_by_generation, pat.published.blob, "patents' census and published anchors collapsed — re-read the finding");

  if (mirrorAtTip("museum/navigation.js") !== null) {
    assert.equal(
      fileStats(mirrorAtTip("museum/navigation.js")).blob,
      pat.published.blob,
      "the published patents anchor the register names is not what that pinned tip actually carries",
    );
    // A banked wip commit that IS an ancestor of main would make the "not a published surface"
    // claim false. rc 0 = ancestor; the register's prose says it isn't, so rc must be non-zero.
    if (pat.re_measured_here.merge_base_is_ancestor_rc !== null) {
      assert.notEqual(
        pat.re_measured_here.merge_base_is_ancestor_rc,
        0,
        `${pat.recorded_by_generation.slice(0, 8)} is an ancestor of patents' main after all — the banked-wip reading in census_provenance is now wrong`,
      );
    }
  }

  const s = REGISTER.census_provenance.spec_pin_delta_summary;
  assert.equal(s.rows, REGISTER.pairs.filter((p) => p.kind === "spec").length, "spec_pin_delta rows no longer match the family's spec pairs");
  assert.equal(s.differing + s.unchanged, s.rows, "spec_pin_delta_summary does not add up");
  assert.equal(
    s.differing,
    REGISTER.census_provenance.spec_pin_delta.filter((r) => r.differs).length,
    "spec_pin_delta_summary.differing disagrees with its own rows",
  );
});

// ── R11: every live-surface claim is recomputed, in this file and in the prose ─
/**
 * Residual 1 was one instance of a defect that had two more copies in the register itself: a
 * claim about a MOVING surface, written into committed data as prose and then believed. (a) The
 * old residuals row asserted where this host's two checkouts sat relative to their tips ('7
 * behind', '2 behind' — both false the day they were written, and unfalsifiable afterwards).
 * (b) The old gallery-loader note asserted that the digests patents' mirror pins were "still
 * live at art d2ce9a4", quoting an art blob, an art sha256 and an art commit that nothing here
 * re-read. Both are gone from the prose: (a) is measured on every run below and printed, (b) is
 * parsed out of the mirror's own bytes by scripts/twin-register.mjs and compared with this tree.
 * A hand-edited hex in either direction, or a re-pasted count, reddens a leg here.
 *
 * Falsifiers run before commit: with the register's mirror_declaration_check.art_tree.blob
 * changed by one character, assert 3 names both hexes; with a 40-hex pasted back into patents'
 * mirror header, assert 5 names it; with a residual re-worded to '3 behind', assert 4 reddens.
 */
test("live-surface claims are recomputed: checkout positions measured, mirror declarations re-read, no count restated in prose", (t) => {
  const HEX = /\b[0-9a-f]{40}\b|\b[0-9a-f]{64}\b/gu;
  const behind = (repo, ref) => {
    try {
      return Number(execFileSync("git", ["-C", repo, "rev-list", "--count", `HEAD..${ref}`], { encoding: "utf8" }).trim());
    } catch {
      return null;
    }
  };

  // 1. Where the two checkouts actually sit. The register states no number for this on purpose:
  //    a committed working-tree position goes false at the next fetch or push. This is the one
  //    place the figure exists, and it is produced per run.
  const rows = [
    ["art", REPO],
    ["patents", MIRROR_REPO],
  ].map(([name, repo]) => [name, behind(repo, "refs/remotes/origin/main")]);
  for (const [name, n] of rows) {
    assert.ok(
      n === null || (Number.isInteger(n) && n >= 0),
      `${name}: git rev-list --count HEAD..refs/remotes/origin/main did not produce a non-negative integer (${n})`
    );
  }
  t.diagnostic(
    `checkout positions measured live (deliberately NOT recorded in the register): ${rows.map(([n, b]) => `${n} ${b === null ? "UNMEASURED" : `${b} behind`}`).join(", ")} — a parked checkout is why a closed twin pair keeps re-serving as copy debt, and fast-forwarding one belongs to whoever owns it, not to a lane`
  );

  // 2. The register's own disclosure that its published rows are dated observations, not pins.
  const pub = REGISTER.census_provenance.row_identities_and_what_they_are.art_leg.published;
  assert.match(
    pub.nature ?? "",
    /build-time observation/iu,
    "art_leg.published lost the disclosure that it is a dated reading, not a pin — R3 refuses to compare it with a later tip, and a reader needs to know why"
  );

  // 3. The mirror's art-digest declaration, re-read and re-measured rather than re-believed.
  const gl = REGISTER.pairs.find((p) => p.id === "museum.gallery-loader.js");
  assert.ok(gl, "register lost the gallery-loader pair");
  const chk = gl.mirror_declaration_check;
  if (!chk || chk.state !== "MEASURED") {
    t.skip(`mirror_declaration_check is ${chk ? chk.state : "absent"} — the mirror's declaration is UNMEASURED on this host, not true`);
  } else {
    const now = fileStats(readText(join(REPO, gl.art.path)));
    assert.equal(chk.art_tree.blob.measured, now.blob, `the register's mirror-check row says art's ${gl.art.path} is ${chk.art_tree.blob.measured} but this tree says ${now.blob} — hand-edited JSON?`);
    assert.equal(chk.art_tree.sha256.measured, now.sha256, `the register's mirror-check row does not carry this tree's sha256 for ${gl.art.path} — hand-edited JSON?`);
    assert.equal(
      chk.declaration_is_true_of_this_tree,
      true,
      `patents' museum/gallery-loader.js PROVENANCE pins art at blob ${chk.asserted.blob} / sha256 ${chk.asserted.sha256} (@ art ${chk.asserted.art_ref}), and art's tree carries ${now.blob} / ${now.sha256} — the mirror's declaration has gone false; move the mirror header (a patents-bound edit) or the pair moved and this row must follow it`
    );
  }

  // 4. No prose row may restate a checkout count or an identity digest that a leg does not
  //    recompute. This is the shape-law of the fold: prose points, numbers live in the register.
  const proseRows = [
    ...REGISTER.residuals.map((r, i) => [`residuals[${i}]`, r]),
    ...REGISTER.pairs.map((p) => [`pair ${p.id} note`, p.note]),
  ];
  for (const [where, text] of proseRows) {
    assert.doesNotMatch(
      text,
      /\b\d+ behind\b/u,
      `${where} states a checkout behind-count in prose — that figure is host state; R11 measures it and the row must name the command instead`
    );
  }

  // 5. Patents' navigation mirror header: pointer in, digests out. The one hex allowed to remain
  //    is this file's own pre-port recovery anchor, and it is allowed only because R10 re-reads
  //    it from patents' object db — the register does not take its word either.
  const navMirror = mirrorAtTip("museum/navigation.js");
  if (navMirror === null) {
    t.skip(`patents' museum/navigation.js unreadable at ${MIRROR_TIP} — the mirror header's shape is UNMEASURED here`);
  } else {
    const close = navMirror.split("\n").findIndex((l) => l.includes("*/"));
    const head = navMirror.split("\n").slice(0, close + 1).join("\n");
    assert.match(
      head,
      /NEAR-DUPLICATE-TWINS\.json id "museum\.navigation\.js"/u,
      "patents' mirror header lost its pointer into this register — the pair's numbers would again have no home either side can read"
    );
    const recoveryAnchor = REGISTER.census_provenance.row_identities_and_what_they_are.patents_leg.recorded_by_generation;
    const strays = (head.match(HEX) || []).filter((h) => h !== recoveryAnchor);
    assert.deepEqual(
      strays,
      [],
      `patents' mirror header restates ${strays.join(", ")} — an art-side identity written a second time is the fork residual 1 closed; only this file's own dated recovery anchor ${recoveryAnchor.slice(0, 12)}… may appear, and R10 re-reads even that from the object db`
    );
  }
});
