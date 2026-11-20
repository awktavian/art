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
 * Two of those sentences were live claims when this file was written and are dated now
 * (2026-11-20, lane IDLE-ART-1120). The `60bf2e08` patents tip the register had frozen into
 * basis.patents_tip no longer exists in that repo's object db, and the "6-leg receipt guard wired
 * to a tracked pre-commit" is not on patents' published main at all — so every mirror leg that
 * reached patents through the recorded hex was SKIPPING, not checking, while the suite stayed
 * green. R12 measures the mirror's live tip instead, and R13 measures whether each guard the
 * register names is present. Both were written after that was found, and R13's positive controls
 * are the record of it.
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

/** Does a ref carry a path? true/false measured, null when the ref itself is unresolvable. */
function presenceAt(repo, ref, relPath) {
  if (!ref) return null;
  try {
    const out = execFileSync("git", ["-C", repo, "ls-tree", "--name-only", ref, "--", relPath], {
      encoding: "utf8",
      stdio: ["ignore", "pipe", "ignore"],
    });
    return out.trim().length > 0;
  } catch {
    return null;
  }
}

/** Bytes of a path at an explicit ref in the mirror repo's object db; null when unresolvable. */
function mirrorBytesAt(ref, relPath) {
  if (!ref || !existsSync(MIRROR_REPO)) return null;
  try {
    return execFileSync("git", ["-C", MIRROR_REPO, "show", `${ref}:${relPath}`], {
      encoding: "utf8",
      maxBuffer: 64 * 1024 * 1024,
    });
  } catch {
    return null;
  }
}

/**
 * patents' LIVE published main, resolved by the same two-step the writer uses
 * (scripts/twin-register.mjs liveTip: ls-remote, then the local remote-tracking ref). R12 and R13
 * share this one resolution, because two ways of asking "which surface is published" is how the
 * register and its tripwire end up measuring different repos.
 */
function mirrorLiveTip() {
  if (!existsSync(MIRROR_REPO)) return null;
  try {
    const sha = execFileSync("git", ["-C", MIRROR_REPO, "ls-remote", "origin", "refs/heads/main"], { encoding: "utf8" })
      .trim()
      .split("\t")[0];
    if (/^[0-9a-f]{40}$/u.test(sha)) return { sha, source: "git ls-remote origin refs/heads/main (live)" };
  } catch {
    /* fall through to the local remote-tracking ref, as the writer does */
  }
  try {
    return {
      sha: execFileSync("git", ["-C", MIRROR_REPO, "rev-parse", "refs/remotes/origin/main"], { encoding: "utf8" }).trim(),
      source: "local refs/remotes/origin/main — ls-remote unavailable, so this can be stale",
    };
  } catch {
    return null;
  }
}

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
  assert.equal(
    pub.state,
    "MEASURABLE_ON_THIS_HOST",
    "art's published leg is UNMEASURABLE on the host that wrote the register — regenerate where origin/main resolves",
  );
  // This leg must hold NO digest. refs/remotes/origin/main is this repo's own tip, and the register
  // is committed into the commits that move it, so a recorded published-tip value is false as soon
  // as the fold that changed these bytes lands: `--check` cannot be satisfied on trunk and the
  // register names a hex its tests cannot recompute. Measured below instead, live, every run.
  assert.equal(
    pub.digest_recorded,
    false,
    `art_leg.published.digest_recorded is ${pub.digest_recorded} — a published-tip digest belongs to a moving ref this file is committed into, so it goes false on the next landing of these bytes. The live value is measured by this leg, not stored.`,
  );
  assert.doesNotMatch(
    JSON.stringify(pub),
    /\b[0-9a-f]{40}\b|\b[0-9a-f]{64}\b/u,
    "art_leg.published carries an identity digest again — no test can recompute it after the next push; R3 measures it live (see this leg's nature)",
  );
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

  // The census legs and the published surface are different bytes. That the two differ IS the
  // finding; if they ever collapse, the row is no longer a stale-tree artifact. Art's side of the
  // comparison is its own TREE (this file's pair row, re-measured by R2 every run) and not a stored
  // tip digest — see art_leg.published.nature for why a stored one could never stay true.
  assert.equal(art.published.state, "MEASURABLE_ON_THIS_HOST");
  const artTreeBlob = REGISTER.pairs.find((p) => p.id === "museum.navigation.js").art.blob;
  assert.match(artTreeBlob, HEX40);
  assert.notEqual(art.recorded_by_generation, artTreeBlob, "art's census anchor and its own tree collapsed — re-read the finding");
  assert.match(pat.published.blob, HEX40, "patents' published anchor is not a hex — it is recorded because patents is not this repo, and its tip is named in basis.patents_tip");
  assert.notEqual(pat.recorded_by_generation, pat.published.blob, "patents' census and published anchors collapsed — re-read the finding");

  if (mirrorAtTip("museum/navigation.js") !== null) {
    assert.equal(
      fileStats(mirrorAtTip("museum/navigation.js")).blob,
      pat.published.blob,
      "the published patents anchor the register names is not what that pinned tip actually carries",
    );
    // The census leg's content finding is that the generation scored bytes no published surface
    // carries. Whether the commit it indexed sits on main's history is a separate fact, and it
    // has moved on this host: at the tip this register was written against (60bf2e08, the ported
    // lineage) 58ef646 was NOT an ancestor of main; after lane IDLE-ART-1120 re-ported onto this
    // bank's surviving lineage it IS. So this leg no longer hard-codes one answer — it re-runs
    // the probe the register's own `command` names and requires the stored rc AND the sentence
    // beside it to agree with what patents' object db says now. Either can rot independently, and
    // a prose clause that outlives its measurement is how residual 1 went false while green.
    const indexedRef = /show ([0-9a-f]{7,40}):/u.exec(pat.re_measured_here.command)?.[1] ?? null;
    assert.ok(indexedRef, `census_provenance.patents_leg.re_measured_here.command does not name a resolvable rev to re-run: ${pat.re_measured_here.command}`);
    const ancestorRc = (() => {
      try {
        execFileSync("git", ["-C", MIRROR_REPO, "merge-base", "--is-ancestor", indexedRef, MIRROR_TIP], { stdio: "ignore" });
        return 0;
      } catch (err) {
        return typeof err?.status === "number" ? err.status : null;
      }
    })();
    if (ancestorRc !== null) {
      assert.equal(
        pat.re_measured_here.merge_base_is_ancestor_rc,
        ancestorRc,
        `census_provenance stores merge_base_is_ancestor_rc=${pat.re_measured_here.merge_base_is_ancestor_rc} but re-running the command this row names gives ${ancestorRc} against ${MIRROR_TIP.slice(0, 12)} — re-measure with node scripts/twin-register.mjs --write`,
      );
      const isAncestor = ancestorRc === 0;
      const clause = isAncestor ? "it IS an ancestor" : "it is NOT an ancestor";
      assert.ok(
        pat.what.includes(clause),
        `patents_leg.what asserts "${clause}" while this host measures merge_base_is_ancestor_rc=${ancestorRc}; the sentence must be regenerated, not re-worded by hand (${pat.what.slice(0, 120)}…)`,
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
 * A hand-edited hex in either direction, or a re-pasted count, reddens a leg here. (c) found at
 * the landing of residual 1, not before it: art_leg.published stored the blob this repo's own
 * origin/main carried at generation, so it was false the moment the fold landed and --check could
 * not be satisfied on trunk. That leg now stores no digest (R3 proves it stores none, and measures
 * the ref live); patents' published leg keeps its digest because patents is not this repo and the
 * commit it was read at is named in the file, which R10 and R11 assert by re-reading it.
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

  // 2. The register's own disclosure of which published leg stores a hex and which measures one.
  //    The rule the two legs differ by: a digest about a repo OTHER than this one may be recorded,
  //    because the commit it was read at is recorded with it and that repo's object db keeps
  //    answering for it. A digest about THIS repo's tip may not, because the register would have to
  //    name its own future to stay true.
  const pub = REGISTER.census_provenance.row_identities_and_what_they_are.art_leg.published;
  assert.match(
    pub.nature ?? "",
    /no digest is recorded/iu,
    "art_leg.published lost the disclosure that it stores no hex — a reader who finds no blob here needs to know the value is measured by R3, not missing"
  );
  assert.match(
    pub.measured_by ?? "",
    /museum-twin-register\.test\.mjs R3/u,
    "art_leg.published no longer names the leg that measures it live, so the absence of a hex here reads as an omission"
  );

  // 2b. Patents' published leg DOES store a hex, so prove it re-reads from the commit the file
  //     names. That is the whole difference between protected-by-data and folklore.
  const patPub = REGISTER.census_provenance.row_identities_and_what_they_are.patents_leg.published;
  assert.equal(
    patPub.digest_recorded,
    true,
    "patents_leg.published stopped recording its digest — patents is not this repo, so its tip CAN be named here and the hex stays re-readable; dropping it would lose the finding, not the rot"
  );
  assert.equal(
    patPub.re_readable_at,
    "basis.patents_tip",
    `patents_leg.published claims to be re-readable at "${patPub.re_readable_at}", which is not the commit the register records`
  );
  const patNavAtRecordedTip = mirrorAtTip("museum/navigation.js");
  if (patNavAtRecordedTip === null) {
    t.skip(`patents' museum/navigation.js unreadable at basis.patents_tip (${MIRROR_TIP}) — that leg's hex is UNVERIFIED on this host, not correct`);
  } else {
    const reRead = fileStats(patNavAtRecordedTip).blob;
    assert.equal(
      reRead,
      patPub.blob,
      `the register records patents' published navigation.js blob as ${patPub.blob} but patents' own object db says ${MIRROR_TIP} carries ${reRead} — a stored digest that does not re-read is the rot residual 1 closed, one row over`
    );
  }

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
    // The same law one type over: a hex written into prose is a second copy of a number with no
    // leg to recompute it, which is exactly how residual 1's header prose went false while staying
    // green. Measured across this register's prose rows before the law was written: zero digests,
    // so the law costs nothing today and catches the first one that appears.
    assert.doesNotMatch(
      text,
      HEX,
      `${where} restates an identity digest in prose — point at the row that measures it (pairs[i].art.blob, census_provenance…); a hex in prose is residual 1's defect with one fewer leg`
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

// ── R12: the register's mirror figures re-measure at the mirror's LIVE tip ───
/**
 * What this leg closes is a silence, not a wrong number. Every other mirror leg here reaches
 * patents through `mirrorAtTip`, which resolves the 40-hex this register froze into
 * basis.patents_tip. When that commit stops existing in patents' object db — a rewritten or
 * garbage-collected main does exactly that — each leg falls back to a skip and rc stays 0, so
 * the register can be describing a surface that no longer exists while the whole file is green.
 * The asymmetry that makes this a defect rather than a limitation: scripts/twin-register.mjs
 * measures its patents legs at the LIVE ref (`liveTip` → `git ls-remote origin refs/heads/main`,
 * then `git show <tip>:<path>`), so a stored `body_identity.identical` is a claim about a moving
 * ref, while the legs meant to keep it true re-read a frozen one. Recorded and measured here at
 * art d6741cd: `git -C <patents> cat-file -t 60bf2e082aea600217c78f698c1e101254ad1a54` exits 128
 * (object absent) while `git ls-remote origin refs/heads/main` answers c3f8333, whose
 * museum/navigation.js body is not the registered one. The pair had live drift and this file
 * reported nothing; only museum-navigation-mirror.test.mjs T5, which reads the working tree,
 * went red — and red with a message that cannot say which surface it measured.
 *
 * So the leg asks the question the writer actually answered when it wrote the figures: does the
 * mirror's live published tip still carry what this register says it carries? An honest skip is
 * reserved for the state where there is no patents repo or no live tip to ask — never for "the
 * hex I chose to believe is gone".
 *
 * Falsifiers, both run before this was committed (see the lane receipts): (1) register beside an
 * unported mirror → reds, naming recorded vs measured blobs for museum/navigation.js; (2) a
 * register whose patents blob was hand-edited while the mirror stayed put → reds on the same
 * row, because the comparison is against bytes patents' own object db returns, so green is
 * reachable only by the surfaces agreeing. Neither can be satisfied by editing this file.
 */
test("the register's mirror figures re-measure at the mirror repo's LIVE published tip, not only at the hex it recorded", (t) => {
  if (!existsSync(MIRROR_REPO)) {
    t.skip(`no patents checkout at ${MIRROR_REPO} — the live mirror surface is UNMEASURED on this host, not agreed`);
    return;
  }
  const liveTip = mirrorLiveTip();
  if (liveTip === null) {
    t.skip(`patents resolves no published main at ${MIRROR_REPO} — UNMEASURED on this host, not drift`);
    return;
  }

  // 1. The tip the legs go to fetch must still resolve where they fetch it. When a live tip
  //    answers but the recorded one does not, every recorded mirror figure is unverifiable and
  //    the cure is a re-measure, not a skip: the register is frozen to a commit that no longer
  //    exists, which is the same rot residual 1 closed one row over (see leg 2b above).
  const recordedResolves = (() => {
    try {
      execFileSync("git", ["-C", MIRROR_REPO, "cat-file", "-e", `${MIRROR_TIP}^{commit}`], { stdio: "ignore" });
      return true;
    } catch {
      return false;
    }
  })();
  assert.ok(
    recordedResolves || MIRROR_TIP === liveTip.sha,
    `basis.patents_tip ${MIRROR_TIP} does not resolve in patents' object db while its live tip ${liveTip.source} = ${liveTip.sha} does — the mirror figures in this register were measured at the live tip and can no longer be re-read at the hex this file names, so legs R5/R10/R11 are skipping instead of checking. Cure: node scripts/twin-register.mjs --write (and port the pair first if the live mirror body has moved).`
  );

  // 2. Every patents figure the register holds must be what the LIVE tip carries now, row by
  //    row, in one report rather than one per assertion.
  const drifts = [];
  for (const row of REGISTER.pairs) {
    if (!row.patents || row.patents.state === "UNMEASURED") continue;
    const live = mirrorBytesAt(liveTip.sha, row.patents.path);
    if (live === null) {
      drifts.push(`${row.id}: register records patents ${row.patents.path} (${row.patents.blob}) but the live tip ${liveTip.sha.slice(0, 12)} does not carry that path`);
      continue;
    }
    const now = fileStats(live);
    for (const k of ["bytes", "lines", "blob", "sha256"]) {
      if (now[k] !== row.patents[k]) {
        drifts.push(`${row.id}: patents.${k} registered ${row.patents[k]} but the live tip carries ${now[k]}`);
      }
    }
    if (!row.body_identity || row.body_identity.recipe === undefined) continue;
    const liveBody = sliceStats(bodyOf(live, row.body_identity.recipe));
    const artBody = sliceStats(bodyOf(readText(artPathOf(row)), row.body_identity.recipe));
    const stillIdentical = liveBody.sha256 === artBody.sha256 && liveBody.bytes === artBody.bytes;
    if (liveBody.sha256 !== row.body_identity.patents.sha256) {
      drifts.push(`${row.id}: patents body under recipe ${row.body_identity.recipe} registered ${row.body_identity.patents.sha256.slice(0, 12)}… but the live tip carries ${liveBody.sha256.slice(0, 12)}…`);
    }
    if (row.body_identity.identical !== stillIdentical) {
      drifts.push(`${row.id}: register asserts body_identity.identical=${row.body_identity.identical} while art's tree and the live mirror tip measure ${stillIdentical} — the pair's declared state is a stale claim, not a measurement`);
    }
  }
  assert.deepEqual(
    drifts,
    [],
    `the register's mirror legs disagree with patents' live published tip (${liveTip.source} = ${liveTip.sha}); re-measure with node scripts/twin-register.mjs --write, porting first where the disposition says canonical-first:\n${drifts.join("\n")}`
  );

  t.diagnostic(
    `mirror legs re-measured at the live tip: ${liveTip.source} = ${liveTip.sha}; basis.patents_tip ${MIRROR_TIP} ${recordedResolves ? "resolves" : "absent (== live tip, disclosed above)"}`
  );
});

// ── R13: a guards row names an instrument, so its existence is measured ─────
/**
 * The register's `guards` entries were the one kind of claim in this family that no leg checked.
 * Bytes, digests, divergence and the census prose all got re-measurement (R2, R3, R5, R10, R12);
 * the guard list stayed authored prose, and it went false in the way authored prose always goes
 * false here — silently, and in the direction that flatters the arrangement. Measured at art
 * d6741cd against patents' live main (`git ls-remote origin refs/heads/main`):
 * `tests/CENSUS-museum-navigation-mirror.check.mjs` and `tests/CENSUS-museum-navigation-mirror.md`
 * are not in that tree (`git ls-tree --name-only <tip> -- <path>` prints nothing for each, and
 * `git show ae04cdc1…:tests/CENSUS-museum-navigation-mirror.check.mjs` exits 128 with "path …
 * does not exist"), `.githooks/pre-commit` is not there either, and the clone sets no
 * `core.hooksPath`. Meanwhile the navigation pair's own guards row asserted the 6-leg mirror
 * guard "wired to a tracked .githooks/pre-commit" as a live instrument, and
 * museum-navigation-mirror.test.mjs's header repeated it. A reader of this family — which is to
 * say the next lane pointed at it by the RSI seed — was told the mirror side was gated when every
 * gate on the pair sits in art. That is a false statement about a permission boundary's cover, so
 * it is fixed by measurement rather than by re-wording.
 *
 * scripts/twin-register.mjs `guardLegs()` now emits each guard as {claim, side, path, state,
 * measured_by}, where `state` comes from `existsSync` (art side) or `git ls-tree` at the live
 * mirror tip (patents side), and R13 re-runs that same measurement and refuses a word that no
 * longer matches. Three properties this buys:
 *   - A restored mirror guard needs no prose edit: `--write` flips ABSENT → PRESENT by itself.
 *   - A hand-edited PRESENT goes red on the run that made the edit, naming the path.
 *   - A pair with NO live instrument anywhere cannot pass, whatever its prose says (leg 3).
 * The bare-string shape is refused rather than skipped, so a register generated before this
 * change cannot ride green: the cure it names is the regeneration, which is what happened here.
 *
 * Falsifiers run before committing (see the lane receipts): (1) the committed register at
 * art d6741cd, whose guards were plain strings → red on leg 1 with the regeneration cure; (2) the
 * regenerated register with `ABSENT` hand-flipped to `PRESENT` on the patents navigation row →
 * red naming that id and path; (3) `claimed_block` hand-flipped the same way on
 * museum.gallery-loader.js → red on the inside-the-file instrument; (4)
 * `ART_TWIN_MIRROR_REPO` pointed at a path with no checkout → the mirror legs fall to the
 * disclosed-unverifiable list, rc=0, never to PRESENT, and the art legs are still checked.
 * Leg 3 of this test (a pair with zero PRESENT guards fails) is the half that was missing: not
 * that an instrument went away, but that the register could keep saying it was there.
 */
test("guards: every instrument the register names is measured present, absent or unmeasured — and a pair is never left ungated", (t) => {
  const liveTip = mirrorLiveTip();
  const mirrorReachable = existsSync(MIRROR_REPO) && liveTip !== null;

  // 1 + 2. Shape, then the state word, measured per entry.
  const bad = [];
  const unverifiable = [];
  for (const row of REGISTER.pairs) {
    for (const g of row.guards) {
      if (typeof g === "string" || !g || typeof g.state !== "string") {
        bad.push(`${row.id}: guards entry is authored prose with no measured state (${JSON.stringify(g).slice(0, 70)}…) — regenerate the register with node scripts/twin-register.mjs --write`);
        continue;
      }
      if (!["PRESENT", "ABSENT", "UNMEASURED", "UNPARSEABLE"].includes(g.state)) {
        bad.push(`${row.id}: guards state "${g.state}" is outside the measured vocabulary`);
        continue;
      }
      // A host with no patents checkout cannot re-ask the mirror question — that is UNMEASURED,
      // which is neither a pass nor a mismatch. CI is such a host; the art legs still gate there.
      if (g.side !== "art" && !mirrorReachable) {
        unverifiable.push(`${row.id}: ${g.side} ${g.path} (recorded ${g.state}${g.claimed_block ? `/${g.claimed_block}` : ""})`);
        continue;
      }
      const measured = g.side === "art" ? existsSync(join(REPO, g.path)) : presenceAt(MIRROR_REPO, liveTip.sha, g.path);
      let expected = measured === true ? "PRESENT" : measured === false ? "ABSENT" : "UNMEASURED";
      // A guard that claims an instrument INSIDE a file is not satisfied by the file: the word
      // comes from both measurements, in the same order the producer combines them.
      const bytes = g.claimed_block === undefined || g.side === "art" ? null : mirrorBytesAt(liveTip.sha, g.path);
      const block =
        g.claimed_block === undefined
          ? undefined
          : g.side === "art"
            ? existsSync(join(REPO, g.path))
              ? "PRESENT"
              : "ABSENT"
            : bytes === null
              ? "UNMEASURED"
              : headerMarkers(bytes).some((m) => m.marker === "PROVENANCE")
                ? "PRESENT"
                : "ABSENT";
      if (block !== undefined && block !== "PRESENT") expected = block;
      if (g.state !== expected) {
        bad.push(
          `${row.id}: guards row asserts ${g.side} ${g.path} is ${g.state} while this host measures ${expected} (mirror tip ${liveTip ? liveTip.sha.slice(0, 12) : "unresolvable"}; ${g.measured_by})`
        );
      }
      if (g.claimed_block !== undefined) {
        if (g.claimed_block !== block) {
          bad.push(
            `${row.id}: guards row says the PROVENANCE block claimed inside ${g.path} is ${g.claimed_block}, headerMarkers over that ref's bytes say ${block} — a file on the surface is not the instrument claimed inside it`
          );
        }
      }
      if (g.hook_plumbing && liveTip) {
        const hook = presenceAt(MIRROR_REPO, liveTip.sha, ".githooks/pre-commit");
        const expectedHook = hook === true ? "PRESENT" : hook === false ? "ABSENT" : "UNMEASURED";
        if (g.hook_plumbing.githooks_pre_commit_at_tip !== expectedHook) {
          bad.push(`${row.id}: hook_plumbing.githooks_pre_commit_at_tip says ${g.hook_plumbing.githooks_pre_commit_at_tip}, measured ${expectedHook}`);
        }
        let hooksPath = "unset";
        try {
          hooksPath = execFileSync("git", ["-C", MIRROR_REPO, "config", "--get", "core.hooksPath"], { encoding: "utf8" }).trim() || "unset";
        } catch {
          hooksPath = "unset";
        }
        if (g.hook_plumbing.core_hooks_path !== hooksPath) {
          bad.push(`${row.id}: hook_plumbing.core_hooks_path says ${g.hook_plumbing.core_hooks_path}, this clone answers ${hooksPath}`);
        }
      }
    }
  }
  assert.deepEqual(bad, [], bad.join("\n"));

  // 3. Coverage, not wording: for a pair whose bodies are declared identical, SOME live
  //    instrument must actually guard it. This is the leg that would have caught the silent
  //    half of the defect — not that the mirror guard was gone, but that nothing said so.
  const ungated = [];
  for (const row of REGISTER.pairs) {
    const live = row.guards.filter((g) => typeof g === "object" && g.state === "PRESENT");
    if (live.length === 0) ungated.push(`${row.id}: no PRESENT guard leg on this host`);
  }
  assert.deepEqual(
    ungated,
    [],
    `pairs whose guards are all ABSENT/UNMEASURED are declared but unprotected — either restore an instrument or record the gap as a residual; do not leave the prose claiming coverage:\n${ungated.join("\n")}`
  );

  const nav = REGISTER.pairs.find((p) => p.id === "museum.navigation.js");
  t.diagnostic(
    `guard legs measured: navigation pair -> ${nav.guards.map((g) => `${g.side}:${g.state}`).join(", ")}; mirror hook plumbing -> ${JSON.stringify(nav.guards.find((g) => g.hook_plumbing)?.hook_plumbing ?? "none")}; pairs with >=1 PRESENT leg: ${REGISTER.pairs.length - ungated.length}/${REGISTER.pairs.length}` +
      (unverifiable.length ? `; mirror-side legs UNMEASURED on this host, not verified: ${unverifiable.join(" | ")}` : "")
  );
});
