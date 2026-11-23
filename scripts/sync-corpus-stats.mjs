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
 *
 * UNMEASURED IS NOT ZERO AND NOT NaN. The schema-v4 proof report (2026-09 kagami
 * refactor) carries files/lines/sorry_count on each project row but may omit the
 * theorem and scientific-open-goal counts entirely -- and while its native
 * declaration inventory is still resolving it publishes no numbers for them at
 * all. A missing count used to reach `Number(undefined)`: the sync path would
 * have published a literal "NaN" tile and the gate would have claimed a
 * "0 sorry" closure for a residual that was merely unmeasured. Both are
 * fabrications of exactly the shape this file exists to prevent, so an absent
 * count now renders no verdict: the tile is left unchanged and named on an
 * UNMEASURED line, and only the tiles the report actually measured are
 * compared. The residual tile additionally refuses to collapse to "0 sorry"
 * unless the open-goal count was also measured at zero.
 *
 * A ROW IS NOT A REPORT. The same argument applies one level down, and until
 * 2026-11-23 it was not applied: the freshness bound was judged on the FRESHEST
 * row in the file (`max(generated_at)` over every project), while the digits a
 * page publishes come from ONE named row. Measured on Studio at trunk `f7aeee4`:
 * the live report carries 43 rows whose freshest is 16.8 h old and whose `hong`
 * row is 84.9 h old -- 3.5x past the 24 h bound this file declares -- and a
 * GREEN-but-85-h-old `hong` row against a one-minute-old decoy row scored
 * `corpus stats: PASS -- the pages match the live proof report` (rc 0). A
 * "PASS" earned from a row the report itself no longer vouches for is the same
 * false green as a "0 sorry" earned from a missing count, so each page is now
 * graded against its OWN row's standing: verification first, then that row's
 * age. An out-of-bounds row renders no verdict for that page -- rc 0, loud, never
 * a pass -- exactly as an out-of-bounds report already did at file level.
 *
 * Every terminal outcome also prints one machine line, `corpus-stats-state:
 * {...}`, naming the state it reached and the report path it read it from;
 * `scripts/check-site.mjs` builds its own failure sentence from those fields
 * (see scripts/corpus-stats-state.mjs for why, and for the three false claims
 * that arrangement replaces).
 */
import { readFileSync, writeFileSync, existsSync } from "node:fs";
import { resolve, dirname, relative } from "node:path";
import { fileURLToPath } from "node:url";

import { STATE, formatStateLine } from "./corpus-stats-state.mjs";

const REPO = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const REPORT = process.env.PROOF_REPORT_PATH ?? "/tmp/proof-report.json";
const MAX_AGE_HOURS = Number(process.env.PROOF_REPORT_MAX_AGE_HOURS ?? "24");

/** page -> the Lean corpus whose statistics it publishes. */
const PAGES = [{ file: "wiles/index.html", project: "hong" }];

class Skip extends Error {
  constructor(message, reason) {
    super(message);
    this.reason = reason ?? "no_verdict";
  }
}

function loadRows() {
  if (!existsSync(REPORT)) throw new Skip(`no proof report at ${REPORT}`, "report_absent");
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

  const stamps = [...rows.values()].map((r) => r.generated_at).filter((v) => typeof v === "number");
  if (stamps.length === 0) throw new Error("proof report carries no generated_at — freshness unestablished");
  // Age is RETURNED, not thrown: an unverified corpus outranks a stale file, so
  // the refusal is decided first in run() and the file-level skip only abstains
  // over rows the compiler did verify. Reordering these two would turn a red
  // into a silence, which is the one thing this gate's law forbids.
  return { rows, reportAgeH: (Date.now() / 1000 - Math.max(...stamps)) / 3600 };
}

const round1 = (n) => Math.round(n * 10) / 10;

/** Age of one row in hours, or null when the row carries no timestamp to age it by. */
function rowAgeH(row) {
  if (typeof row.generated_at !== "number" || !Number.isFinite(row.generated_at)) return null;
  return (Date.now() / 1000 - row.generated_at) / 3600;
}

/**
 * Whether THIS row verifies the digits it carries — per corpus, not per file.
 *
 * Returns `{ grade: true, …evidence }` or `{ grade: false, state: unverified_source,
 * reason, …evidence }`. This is the refusal path (rc 1): the compiler has not
 * verified the corpus, which is exactly what this gate exists to catch. Age is
 * judged separately, after it, by `rowAgeVerdict`.
 */
function sourceStanding(row, project) {
  const evidence = row
    ? {
        build_status: row.build_status === undefined ? null : row.build_status,
        build_exit: Number.isFinite(row.build_exit) ? row.build_exit : undefined,
        facts_status: typeof row.facts_status === "string" ? row.facts_status : undefined,
        partial_reason:
          Array.isArray(row.partial_reasons) && row.partial_reasons.length ? row.partial_reasons[0] : undefined,
        row_age_h: (() => { const a = rowAgeH(row); return a === null ? undefined : round1(a); })(),
      }
    : { build_status: null };
  if (!row) {
    return {
      ...evidence,
      grade: false,
      state: STATE.UNVERIFIED_SOURCE,
      reason: `corpus "${project}" is absent from ${REPORT} — refusing to publish a guess`,
    };
  }
  if (row.build_status !== "GREEN") {
    return {
      ...evidence,
      grade: false,
      state: STATE.UNVERIFIED_SOURCE,
      reason:
        `corpus "${project}" is ${evidence.build_status ?? "<no build_status>"}: its counts are UNVERIFIED, ` +
        `neither zero nor trustworthy. Refusing to publish them as fact.`,
    };
  }
  return { ...evidence, grade: true };
}

/**
 * Whether the row is still evidence about TODAY. An out-of-bounds row supports
 * neither a pass nor a drift claim, so it abstains (rc 0, loud) rather than
 * grading — the same shape the file-level stale skip already had, one level
 * down. A row with no timestamp still grades; its absence is disclosed on the
 * state line as `row_age_h` omitted, never silently treated as fresh.
 */
function rowAgeVerdict(row, project, standing) {
  const age = rowAgeH(row);
  if (age !== null && age > MAX_AGE_HOURS) {
    return {
      ...standing,
      grade: false,
      state: STATE.NO_VERDICT,
      reason:
        `the row for corpus "${project}" is ${age.toFixed(1)}h old, past the ${MAX_AGE_HOURS}h bound this ` +
        `gate declares; a digit that old is not evidence about today's page`,
    };
  }
  return standing;
}

/** The one machine line. Printed once, whatever the outcome, with the path actually read. */
function emitState(fields) {
  const { grade, ...rest } = fields; // `grade` is internal control flow, never a published field
  console.log(formatStateLine({ report: REPORT, max_age_h: MAX_AGE_HOURS, ...rest }));
}

const fmt = (n) => Number(n).toLocaleString("en-US");

/** A measured count, or null when the report carries no number for it.
 *  null is "unmeasured": it renders no verdict and publishes no digit. */
function countOrNull(v) {
  if (typeof v === "boolean" || v === null || v === undefined) return null;
  const n = Number(v);
  return Number.isFinite(n) ? n : null;
}

/**
 * The residual tile. `sorry` alone understates a corpus whose open work has
 * moved into named scientific goals, so the label follows the residual that
 * actually exists rather than the one the page was built around. Returns null
 * when the report does not measure the residual: "no open-goal count" is not
 * evidence of closure, so no tile is rendered.
 */
function residual(row) {
  const sorries = countOrNull(row.sorry_count);
  if (sorries === null) return null;
  if (sorries > 0) return { value: fmt(sorries), label: "sorry" };
  const open = countOrNull(row.scientific_open_count);
  if (open === null) return null;
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
  const unmeasured = [];
  for (const tile of ["files", "lines", "theorems"]) {
    const n = countOrNull(row[tile]);
    if (n === null) {
      unmeasured.push(tile);
      continue;
    }
    html = setTile(html, tile, fmt(n), file);
  }
  const res = residual(row);
  if (res === null) {
    unmeasured.push("residual");
  } else {
    // The residual tile's LABEL is generated too, so it cannot keep saying
    // "sorry" over a number that is no longer a sorry count.
    const resRe = /(<div class="arch-stat-val">)[^<]*(<\/div><div class="arch-stat-label">)(?:sorry|open goals?)(<\/div>)/;
    if (!resRe.test(html)) throw new Error(`${file}: could not locate the residual tile`);
    html = html.replace(resRe, (_m, a, b, c) => `${a}${res.value}${b}${res.label}${c}`);
  }
  return { html, unmeasured };
}

function run(check) {
  let loaded;
  try {
    loaded = loadRows();
  } catch (e) {
    if (e instanceof Skip) {
      console.log(`corpus stats: SKIPPED (no verdict) — ${e.message}`);
      emitState({ state: STATE.NO_VERDICT, reason: e.reason });
      return 0;
    }
    console.error(`corpus stats: FAIL — ${e.message}`);
    emitState({ state: STATE.ERROR, reason: e.message });
    return 1;
  }
  const { rows, reportAgeH } = loaded;

  // Pass 1 — verification, before any age is consulted (the pre-2026-11-23
  // order, kept on purpose): a corpus the compiler has not verified reddens the
  // leg whatever the file's age, so no stale-report skip can quiet a refusal.
  for (const { file, project } of PAGES) {
    const standing = sourceStanding(rows.get(project), project);
    if (standing.grade) continue;
    console.error(`corpus stats: REFUSED — source unverified for ${file}: ${standing.reason}`);
    emitState({ state: STATE.UNVERIFIED_SOURCE, page: file, project, ...standing });
    return 1;
  }

  // Pass 2 — the file-level bound, unchanged: too old a report is no evidence.
  if (reportAgeH > MAX_AGE_HOURS) {
    console.log(
      `corpus stats: SKIPPED (no verdict) — proof report is STALE (${reportAgeH.toFixed(1)}h old, ` +
        `max ${MAX_AGE_HOURS}h)`,
    );
    emitState({ state: STATE.NO_VERDICT, reason: "report_stale", report_age_h: round1(reportAgeH) });
    return 0;
  }

  let refusal = null;
  let hadUnmeasured = false;
  let graded = 0;
  let abstained = 0;
  let lastStanding = null;

  for (const { file, project } of PAGES) {
    const row = rows.get(project);
    // Pass 3 — the row-level bound. A verified row that is older than the
    // declared window abstains for ITS page; it does not certify one.
    const verdict = rowAgeVerdict(row, project, sourceStanding(row, project));
    if (!verdict.grade) {
      abstained++;
      console.log(`corpus stats: SKIPPED (no verdict) in ${file}: ${verdict.reason}`);
      continue;
    }
    graded++;
    lastStanding = { ...verdict, page: file, project };

    const path = resolve(REPO, file);
    const current = readFileSync(path, "utf8");
    let expected, unmeasured;
    try {
      ({ html: expected, unmeasured } = render(current, row, file));
    } catch (e) {
      console.error(`corpus stats: FAIL — ${e.message}`);
      emitState({ state: STATE.ERROR, page: file, project, reason: e.message, ...verdict });
      return 1;
    }
    if (unmeasured.length > 0) {
      hadUnmeasured = true;
      // stdout, like SKIPPED: check-site forwards the child's stdout even when
      // the gate passes, so the no-verdict line stays visible in the build log.
      console.log(
        `corpus stats: UNMEASURED in ${file}: ${unmeasured.join(", ")} — the live report carries ` +
          `no number for these tiles; they are left unchanged and compared against nothing.`,
      );
    }
    if (!check) {
      if (expected !== current) {
        writeFileSync(path, expected, "utf8");
        console.log(`corpus stats: rewrote ${relative(REPO, path)}`);
      }
      continue;
    }
    if (expected === current) continue;
    if (refusal === null) refusal = { state: STATE.DRIFT, page: file, project, ...verdict };
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

  if (refusal !== null) {
    emitState(refusal);
    console.error("  fix: node scripts/sync-corpus-stats.mjs");
    return 1;
  }

  if (graded === 0) {
    // Nothing was gradeable. That is an absence of evidence, never a pass.
    console.log(
      `corpus stats: SKIPPED (no verdict) — no page's row is in bounds ` +
        `(${abstained} abstention(s)); nothing was compared.`,
    );
    emitState({ state: STATE.NO_VERDICT, reason: "no gradeable row", graded: 0, abstained });
    return 0;
  }

  console.log(
    "corpus stats: PASS — the pages match the live proof report" +
      (hadUnmeasured ? " for every measured tile (see UNMEASURED above)" : "") +
      (abstained ? `; ${abstained} page(s) rendered no verdict, above` : ""),
  );
  emitState({ state: STATE.PASS, graded, abstained, ...(lastStanding ?? {}) });
  return 0;
}

process.exit(run(process.argv.includes("--check")));
