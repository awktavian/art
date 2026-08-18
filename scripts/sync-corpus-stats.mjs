#!/usr/bin/env node
/**
 * Generate and gate the corpus statistics published by the art pages.
 *
 * WHY THIS EXISTS
 * ---------------
 * `wiles/index.html` published a four-tile "The Architecture" panel -- files,
 * lines, theorems, sorry -- typed by hand against the `hong` corpus. All four
 * had drifted: 169 files against 241, 75,792 lines against 112,674, 2,290
 * theorems against 3,229, and "13 sorry" for a corpus that is sorry-free.
 *
 * That last one is the dangerous shape. The residual did not vanish; it moved
 * from `sorry` markers to open scientific goals, of which hong has 45. A page
 * that shows a shrinking sorry count while the real open work is invisible is
 * telling a story of closure that the compiler does not support. The tile now
 * names whichever residual actually exists, and never reports zero when open
 * goals remain.
 *
 *   node scripts/sync-corpus-stats.mjs            # rewrite the pages
 *   node scripts/sync-corpus-stats.mjs --check    # gate, exit 1 on drift
 *
 * `--check` runs inside `scripts/check-site.mjs`. Where no proof report exists
 * (CI, a fresh clone) it prints SKIPPED and renders no verdict -- deliberately
 * distinct from passing.
 */
import { readFileSync, writeFileSync, existsSync } from "node:fs";
import { resolve, dirname, relative } from "node:path";
import { fileURLToPath } from "node:url";

const REPO = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const REPORT = process.env.PROOF_REPORT_PATH ?? "/tmp/proof-report.json";
const MAX_AGE_HOURS = Number(process.env.PROOF_REPORT_MAX_AGE_HOURS ?? "24");

/** page -> the Lean corpus whose statistics it publishes. */
const PAGES = [{ file: "wiles/index.html", project: "hong" }];

class Skip extends Error {}

function loadRows() {
  if (!existsSync(REPORT)) throw new Skip(`no proof report at ${REPORT}`);
  let parsed;
  try {
    parsed = JSON.parse(readFileSync(REPORT, "utf8"));
  } catch (e) {
    throw new Error(`proof report at ${REPORT} is not valid JSON: ${e.message}`);
  }
  if (parsed && !Array.isArray(parsed) && Array.isArray(parsed.projects)) parsed = parsed.projects;
  if (!Array.isArray(parsed)) {
    throw new Error(`proof report at ${REPORT} is malformed: expected a top-level list (schema v3)`);
  }
  const rows = new Map(parsed.filter((r) => r && typeof r.name === "string").map((r) => [r.name, r]));

  for (const { project } of PAGES) {
    const r = rows.get(project);
    if (!r) throw new Error(`corpus "${project}" is absent from ${REPORT} — refusing to publish a guess`);
    if (r.build_status !== "GREEN") {
      throw new Error(
        `corpus "${project}" is ${r.build_status}: its counts are UNVERIFIED, ` +
          `neither zero nor trustworthy. Refusing to publish them as fact.`,
      );
    }
  }
  const stamps = [...rows.values()].map((r) => r.generated_at).filter((v) => typeof v === "number");
  if (stamps.length === 0) throw new Error("proof report carries no generated_at — freshness unestablished");
  const ageH = (Date.now() / 1000 - Math.max(...stamps)) / 3600;
  if (ageH > MAX_AGE_HOURS) {
    throw new Skip(`proof report is STALE (${ageH.toFixed(1)}h old, max ${MAX_AGE_HOURS}h)`);
  }
  return rows;
}

const fmt = (n) => Number(n).toLocaleString("en-US");

/**
 * The residual tile. `sorry` alone understates a corpus whose open work has
 * moved into named scientific goals, so the label follows the residual that
 * actually exists rather than the one the page was built around.
 */
function residual(row) {
  const sorries = Number(row.sorry_count ?? 0);
  if (sorries > 0) return { value: fmt(sorries), label: "sorry" };
  const open = Number(row.scientific_open_count ?? 0);
  if (open > 0) return { value: fmt(open), label: open === 1 ? "open goal" : "open goals" };
  return { value: "0", label: "sorry" };
}

function setTile(html, label, value, file) {
  const re = new RegExp(
    `(<div class="arch-stat-val">)[^<]*(</div><div class="arch-stat-label">${label}</div>)`,
  );
  if (!re.test(html)) throw new Error(`${file}: could not locate the "${label}" tile`);
  return html.replace(re, (_m, a, b) => `${a}${value}${b}`);
}

function render(html, row, file) {
  const res = residual(row);
  html = setTile(html, "files", fmt(row.files), file);
  html = setTile(html, "lines", fmt(row.lines), file);
  html = setTile(html, "theorems", fmt(row.theorems), file);
  // The residual tile's LABEL is generated too, so it cannot keep saying
  // "sorry" over a number that is no longer a sorry count.
  const resRe = /(<div class="arch-stat-val">)[^<]*(<\/div><div class="arch-stat-label">)(?:sorry|open goals?)(<\/div>)/;
  if (!resRe.test(html)) throw new Error(`${file}: could not locate the residual tile`);
  html = html.replace(resRe, (_m, a, b, c) => `${a}${res.value}${b}${res.label}${c}`);
  return html;
}

function run(check) {
  let rows;
  try {
    rows = loadRows();
  } catch (e) {
    if (e instanceof Skip) {
      console.log(`corpus stats: SKIPPED (no verdict) — ${e.message}`);
      return 0;
    }
    console.error(`corpus stats: FAIL — ${e.message}`);
    return 1;
  }

  let drifted = false;
  for (const { file, project } of PAGES) {
    const path = resolve(REPO, file);
    const current = readFileSync(path, "utf8");
    let expected;
    try {
      expected = render(current, rows.get(project), file);
    } catch (e) {
      console.error(`corpus stats: FAIL — ${e.message}`);
      return 1;
    }
    if (!check) {
      if (expected !== current) {
        writeFileSync(path, expected, "utf8");
        console.log(`corpus stats: rewrote ${relative(REPO, path)}`);
      }
      continue;
    }
    if (expected === current) continue;
    drifted = true;
    console.error(`corpus stats: DRIFT in ${file} (corpus "${project}")`);
    const a = current.split("\n");
    const b = expected.split("\n");
    for (let i = 0; i < Math.max(a.length, b.length); i++) {
      if (a[i] !== b[i]) {
        console.error(`  page: ${(a[i] ?? "").trim()}`);
        console.error(`  live: ${(b[i] ?? "").trim()}`);
      }
    }
  }

  if (!check) return 0;
  if (!drifted) {
    console.log("corpus stats: PASS — the pages match the live proof report");
    return 0;
  }
  console.error("  fix: node scripts/sync-corpus-stats.mjs");
  return 1;
}

process.exit(run(process.argv.includes("--check")));
