/**
 * scripts/sync-corpus-stats.mjs — the corpus-tile gate behind `test:static`.
 *
 * The property under test is that a tile is only ever published or compared
 * when the proof report MEASURES it. The 2026-09 schema-v4 refactor dropped
 * `theorems` and `scientific_open_count` from live rows while the native
 * declaration inventory resolves; the old code turned those absences into a
 * literal "NaN" tile (sync path) and a fabricated "0 sorry" closure claim
 * (check path). Both are the false-zero class this script was written to
 * prevent. The gate must still FIRE, though: a measured disagreement is rc=1,
 * never a silent pass.
 */
import assert from "node:assert/strict";
import test from "node:test";
import { spawnSync } from "node:child_process";
import { cpSync, mkdirSync, mkdtempSync, readFileSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const HERE = dirname(fileURLToPath(import.meta.url));
const SCRIPT = join(HERE, "..", "..", "scripts", "sync-corpus-stats.mjs");
const STATE_LIB = join(HERE, "..", "..", "scripts", "corpus-stats-state.mjs");
const { gateFailure, parseStateLine, runCorpusGate, STATE } = await import(STATE_LIB);

const tile = (val, label) =>
  `<div class="arch-stat"><div class="arch-stat-val">${val}</div><div class="arch-stat-label">${label}</div></div>`;

function fixtureRepo(pageTiles) {
  const repo = mkdtempSync(join(tmpdir(), "corpus-stats-"));
  mkdirSync(join(repo, "scripts"), { recursive: true });
  mkdirSync(join(repo, "wiles"), { recursive: true });
  cpSync(SCRIPT, join(repo, "scripts", "sync-corpus-stats.mjs"));
  cpSync(STATE_LIB, join(repo, "scripts", "corpus-stats-state.mjs"));
  writeFileSync(
    join(repo, "wiles", "index.html"),
    [tile(pageTiles.files, "files"), tile(pageTiles.lines, "lines"), tile(pageTiles.theorems, "theorems"), tile(pageTiles.residual, pageTiles.residualLabel)].join("\n") + "\n",
  );
  return repo;
}

function writeReport(repo, row) {
  const path = join(repo, "report.json");
  writeFileSync(path, JSON.stringify([row]));
  return path;
}

const baseRow = (stats) => ({
  name: "hong",
  build_status: "GREEN",
  generated_at: Date.now() / 1000,
  ...stats,
});

function run(repo, reportPath, check) {
  // Spawn the FIXTURE COPY, never the original: the script resolves its repo
  // root from its own path, so running the original would rewrite the real
  // pages instead of the fixture (measured the first time this test suite ran).
  return spawnSync(process.execPath, [join(repo, "scripts", "sync-corpus-stats.mjs"), ...(check ? ["--check"] : [])], {
    encoding: "utf8",
    env: { ...process.env, PROOF_REPORT_PATH: reportPath, PROOF_REPORT_MAX_AGE_HOURS: "24" },
  });
}

const page = (t) => ({ files: t.files, lines: t.lines, theorems: t.theorems, residual: t.residual, residualLabel: t.residualLabel });

test("a MEASURED tile that disagrees with the report fails the gate", () => {
  const repo = fixtureRepo(page({ files: 268, lines: "124,563", theorems: "3,768", residual: 42, residualLabel: "open goals" }));
  const report = writeReport(repo, baseRow({ files: 311, lines: 147310, theorems: "3,768", sorry_count: 0, scientific_open_count: 42 }));
  const res = run(repo, report, true);
  assert.equal(res.status, 1, "the rule must still fire on a genuine drift: " + res.stdout + res.stderr);
  assert.match(res.stderr, /DRIFT/);
});

test("sync republishes measured tiles and the gate then passes", () => {
  const repo = fixtureRepo(page({ files: 268, lines: "124,563", theorems: "3,768", residual: 42, residualLabel: "open goals" }));
  const report = writeReport(repo, baseRow({ files: 311, lines: 147310, theorems: 3800, sorry_count: 0, scientific_open_count: 42 }));
  assert.equal(run(repo, report, false).status, 0);
  const html = readFileSync(join(repo, "wiles", "index.html"), "utf8");
  assert.match(html, /311<\/div><div class="arch-stat-label">files/);
  assert.match(html, /147,310<\/div><div class="arch-stat-label">lines/);
  assert.match(html, /3,800<\/div><div class="arch-stat-label">theorems/);
  assert.equal(run(repo, report, true).status, 0);
});

test("UNMEASURED counts render no digit: no NaN, no fabricated 0 sorry", () => {
  const repo = fixtureRepo(page({ files: 268, lines: "124,563", theorems: "3,768", residual: 42, residualLabel: "open goals" }));
  // Schema-v4 row: sorry_count measured at 0, theorem and open-goal counts absent.
  const report = writeReport(repo, baseRow({ files: 311, lines: 147310, sorry_count: 0 }));
  const check = run(repo, report, true);
  assert.equal(check.status, 1, "files/lines are measured and drift, so the gate still fires");
  assert.match(check.stdout, /UNMEASURED .*theorems, residual/);
  assert.doesNotMatch(check.stdout + check.stderr, /NaN/);

  assert.equal(run(repo, report, false).status, 0);
  const html = readFileSync(join(repo, "wiles", "index.html"), "utf8");
  assert.match(html, /311<\/div><div class="arch-stat-label">files/); // measured: republished
  assert.match(html, /3,768<\/div><div class="arch-stat-label">theorems/); // unmeasured: left alone
  assert.match(html, /42<\/div><div class="arch-stat-label">open goals/); // residual: left alone
  assert.doesNotMatch(html, /NaN|>0<\/div><div class="arch-stat-label">sorry/);
  assert.equal(run(repo, report, true).status, 0); // gate now clean, with UNMEASURED noted
});

test("residual follows whichever count the report actually measures", () => {
  const report = (stats) => {
    const repo = fixtureRepo(page({ files: 1, lines: 1, theorems: 1, residual: 1, residualLabel: "sorry" }));
    const path = writeReport(repo, baseRow({ files: 1, lines: 1, theorems: 1, ...stats }));
    assert.equal(run(repo, path, false).status, 0);
    return readFileSync(join(repo, "wiles", "index.html"), "utf8");
  };
  assert.match(report({ sorry_count: 13, scientific_open_count: 42 }), /13<\/div><div class="arch-stat-label">sorry/);
  assert.match(report({ sorry_count: 0, scientific_open_count: 7 }), /7<\/div><div class="arch-stat-label">open goals/);
  assert.match(report({ sorry_count: 0, scientific_open_count: 0 }), /0<\/div><div class="arch-stat-label">sorry/);
  // sorry-free with NO open-goal measurement must not render a closure tile at all.
  assert.match(report({ sorry_count: 0 }), /1<\/div><div class="arch-stat-label">sorry/);
});

test("an absent report prints SKIPPED and exits 0 — absence is not a pass", () => {
  const repo = fixtureRepo(page({ files: 1, lines: 1, theorems: 1, residual: 1, residualLabel: "sorry" }));
  const res = run(repo, join(repo, "missing.json"), true);
  assert.equal(res.status, 0);
  assert.match(res.stdout, /SKIPPED \(no verdict\)/);
});

// ── What the leg MEASURED, not just whether it was red ───────────────────────
// `scripts/check-site.mjs` used to book one sentence for every nonzero exit:
//   wiles/index.html: corpus statistics disagree with /tmp/proof-report.json
//   (fix: node scripts/sync-corpus-stats.mjs)
// Measured at trunk f7aeee4 on Studio, with the live report whose hong row is
// build_status=UNMEASURED / build_exit=124, that claim was false three ways: no
// comparison had run, the named path was not the path read under a
// PROOF_REPORT_PATH override, and the prescribed fix exits 1 on the same row —
// which is how three lanes ended up pointing PROOF_REPORT_PATH at a nonexistent
// file to buy the skip (NOTES.md §Gate). The legs below pin the typed contract
// that replaces it, and they do NOT relax any exit code: an unverified corpus
// stays rc=1, as the first leg asserts.

/** A row aged `ageH` hours, GREEN unless told otherwise. */
const agedRow = (stats, ageH = 0) => ({
  name: "hong",
  build_status: "GREEN",
  generated_at: Date.now() / 1000 - ageH * 3600,
  ...stats,
});

const stateOf = (res) => parseStateLine(res.stdout + res.stderr);

test("a corpus the compiler has not verified refuses, rc 1, and is never called drift", () => {
  const repo = fixtureRepo(page({ files: 1, lines: 1, theorems: 1, residual: 1, residualLabel: "sorry" }));
  const report = writeReport(
    repo,
    agedRow({ files: 1, lines: 1, theorems: 1, sorry_count: 0, scientific_open_count: 0,
      build_status: "UNMEASURED", build_exit: 124, facts_status: "EXPIRED",
      partial_reasons: ["build_deferred:timeout_no_verdict"] }),
  );
  const res = run(repo, report, true);
  assert.equal(res.status, 1, "unverified stays red — this leg is what forbids weakening it");
  assert.match(res.stderr, /REFUSED — source unverified/);
  const state = stateOf(res);
  assert.equal(state.state, STATE.UNVERIFIED_SOURCE);
  assert.equal(state.build_status, "UNMEASURED");
  assert.equal(state.build_exit, 124, "the row's own cause rides on the state line");
  assert.equal(state.report, report, "the state names the file actually read");
  // The cure it prescribes must be one that works. `sync` cannot run against an
  // unverified row (measured rc 1 at trunk), so it must not be offered.
  assert.doesNotMatch(res.stdout + res.stderr, /fix: node scripts\/sync-corpus-stats\.mjs/);
  assert.doesNotMatch(res.stdout + res.stderr, /DRIFT/);
});

test("a refusal outranks a stale file: age never quiets an unverified corpus", () => {
  const repo = fixtureRepo(page({ files: 1, lines: 1, theorems: 1, residual: 1, residualLabel: "sorry" }));
  // Unverified AND 400h past the bound: the pre-2026-11-23 order refused on the
  // row first, and reordering those two passes would turn that red into silence.
  const report = writeReport(
    repo,
    agedRow({ files: 1, lines: 1, theorems: 1, sorry_count: 0, scientific_open_count: 0, build_status: "UNMEASURED" }, 400),
  );
  const res = run(repo, report, true);
  assert.equal(res.status, 1);
  assert.equal(stateOf(res).state, STATE.UNVERIFIED_SOURCE);
});

test("an out-of-bounds ROW renders no verdict for its page — never a PASS", () => {
  const tiles = page({ files: 311, lines: "147,310", theorems: "3,768", residual: 42, residualLabel: "open goals" });
  const stats = { files: 311, lines: 147310, theorems: 3768, sorry_count: 0, scientific_open_count: 42 };
  const repo = fixtureRepo(tiles);
  // The exact Studio shape: hong's own row is 85h old — past the 24h bound the
  // script declares — while another row in the same file is one minute old.
  // At trunk this printed `PASS — the pages match the live proof report`, rc 0.
  const report = join(repo, "two-row.json");
  writeFileSync(report, JSON.stringify([agedRow(stats, 85), { ...agedRow(stats, 0), name: "decoy" }]));
  const stale = run(repo, report, true);
  assert.match(stale.stdout, /SKIPPED \(no verdict\)/);
  assert.doesNotMatch(stale.stdout + stale.stderr, /PASS/, "a pass earned from an 85h-old row is the false green this leg forbids");
  assert.equal(stateOf(stale).state, STATE.NO_VERDICT);
  assert.equal(stateOf(stale).graded, 0);
  // Control: the same page, the same digits, one fresh row — grades and passes.
  const freshReport = writeReport(repo, agedRow(stats, 1));
  const fresh = run(repo, freshReport, true);
  assert.equal(fresh.status, 0, fresh.stdout + fresh.stderr);
  assert.match(fresh.stdout, /PASS/);
  assert.equal(stateOf(fresh).state, STATE.PASS);
  assert.equal(stateOf(fresh).row_age_h, 1);
});

test("the page's own digits are named, so a no-verdict cannot be read as a drift claim", () => {
  const repo = fixtureRepo(page({ files: 1, lines: 1, theorems: 1, residual: 1, residualLabel: "sorry" }));
  const drift = writeReport(repo, agedRow({ files: 999, lines: 2, theorems: 3, sorry_count: 0, scientific_open_count: 0 }));
  const res = run(repo, drift, true);
  assert.equal(res.status, 1);
  assert.match(res.stderr, /DRIFT/);
  const state = stateOf(res);
  assert.equal(state.state, STATE.DRIFT);
  assert.equal(state.page, "wiles/index.html");
  // A drift has a cure that works, so it keeps being offered — only for drift.
  assert.match(res.stderr, /fix: node scripts\/sync-corpus-stats\.mjs/);
});

test("check-site's sentence is built from the child's measurement", () => {
  const repo = fixtureRepo(page({ files: 1, lines: 1, theorems: 1, residual: 1, residualLabel: "sorry" }));
  const call = (reportPath) =>
    runCorpusGate({
      script: join(repo, "scripts", "sync-corpus-stats.mjs"),
      env: { ...process.env, PROOF_REPORT_PATH: reportPath },
      log: () => {},
    });

  const unverified = call(
    writeReport(repo, agedRow({ files: 1, lines: 1, theorems: 1, sorry_count: 0, scientific_open_count: 0,
      build_status: "UNMEASURED", build_exit: 124 })),
  );
  assert.equal(unverified.rc, 1);
  assert.match(unverified.failure, /NOT COMPARED/);
  assert.match(unverified.failure, /build_status=UNMEASURED/);
  assert.match(unverified.failure, /is not a drift finding/);
  assert.match(unverified.failure, new RegExp(unverified.state.report.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")));
  assert.doesNotMatch(unverified.failure, /corpus statistics disagree/);

  const drifted = call(
    writeReport(repo, agedRow({ files: 42, lines: 42, theorems: 42, sorry_count: 0, scientific_open_count: 0 })),
  );
  assert.equal(drifted.rc, 1);
  assert.match(drifted.failure, /corpus statistics disagree with/);
  // The defect this replaces: the parent printed the DEFAULT path whatever the
  // child read. The fixture path is not /tmp/proof-report.json.
  assert.ok(drifted.failure.includes(drifted.state.report), "the sentence names the file the child opened");
  assert.doesNotMatch(drifted.failure, /\/tmp\/proof-report\.json/);

  const absent = call(join(repo, "nothing-at-all.json"));
  assert.equal(absent.rc, 0);
  assert.equal(absent.failure, null, "a no-verdict leg books no failure");
});

test("a missing or torn state line is reported as unknown, never as drift", () => {
  assert.equal(parseStateLine("corpus stats: PASS\n"), null);
  assert.equal(parseStateLine('corpus-stats-state: {"state":'), null);
  assert.equal(parseStateLine('corpus-stats-state: {"state":"drift"}').state, "drift");
  const unknown = gateFailure(null, 1);
  assert.doesNotMatch(unknown, /disagree/);
  assert.doesNotMatch(unknown, /proof-report\.json/);
  assert.match(unknown, /without a typed state line/);
  // An invented state cannot smuggle a page name into the sentence either.
  assert.match(gateFailure({ state: "unverified_source" }, 1), /^corpus stats:/);
});
