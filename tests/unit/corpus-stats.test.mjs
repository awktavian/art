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

const SCRIPT = join(dirname(fileURLToPath(import.meta.url)), "..", "..", "scripts", "sync-corpus-stats.mjs");

const tile = (val, label) =>
  `<div class="arch-stat"><div class="arch-stat-val">${val}</div><div class="arch-stat-label">${label}</div></div>`;

function fixtureRepo(pageTiles) {
  const repo = mkdtempSync(join(tmpdir(), "corpus-stats-"));
  mkdirSync(join(repo, "scripts"), { recursive: true });
  mkdirSync(join(repo, "wiles"), { recursive: true });
  cpSync(SCRIPT, join(repo, "scripts", "sync-corpus-stats.mjs"));
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
