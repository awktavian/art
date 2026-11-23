/**
 * The one vocabulary for what the corpus-stat gate MEASURED.
 *
 * Written by lane ART-RSI-ec1fe7, campaign ENGINE-COVERAGE-1119, 2026-11-23.
 *
 * `scripts/sync-corpus-stats.mjs` grades the stat tiles on `wiles/index.html`
 * against a proof report; `scripts/check-site.mjs` runs it as a leg of
 * `npm run test:static`. Until now the leg had one exit code (1) and one
 * sentence, so every state the child could reach — a page that genuinely
 * disagrees with a verified report, a corpus the compiler has not verified at
 * all, a crash — arrived at the reader as the same claim:
 *
 *   wiles/index.html: corpus statistics disagree with /tmp/proof-report.json
 *   (fix: node scripts/sync-corpus-stats.mjs)
 *
 * Measured at trunk `f7aeee4` on Studio, that sentence was false in three ways:
 *
 * 1. IT CLAIMED A COMPARISON THAT NEVER RAN. The live `hong` row is
 *    `build_status=UNMEASURED` (build_exit 124), so the child refused to
 *    compare anything — its own stderr says `Refusing to publish them as
 *    fact` — while the parent asserted the page DISAGREED with the report.
 * 2. THE CURE IT PRESCRIBES CANNOT BE PERFORMED. `node scripts/sync-corpus-stats.mjs`
 *    exits 1 with the same refusal (measured this turn), and the DEBT note at
 *    `patent-portfolio/DEBT-museum-navigation-duplication.md` records what it
 *    would do if it could: rewrite a published page from a host-local file.
 *    Three lanes have inherited that red and worked around it by pointing
 *    `PROOF_REPORT_PATH` at a nonexistent file to buy the documented skip
 *    (`NOTES.md` §Gate) — a gate whose only readable outcome is a lie teaches
 *    its users to bypass it.
 * 3. IT NAMED A FILE IT DID NOT READ. With `PROOF_REPORT_PATH` overridden the
 *    child honours the override; the parent still printed the default path
 *    (measured: `PROOF_REPORT_PATH=/tmp/claude/hong-drift.json` printed
 *    `disagree with /tmp/proof-report.json`).
 *
 * So: the child states, in one machine line, the state it reached and the
 * inputs it reached it from; the parent builds its sentence from those fields
 * and never from a guess. `rc` semantics are unchanged — an unverified source
 * stays red, which is the whole reason this gate exists — so nothing here
 * widens what the gate accepts. What changes is that a reader can act on it.
 *
 * The contract, one line on the child's stdout:
 *
 *   corpus-stats-state: {"state":"unverified_source","report":"/tmp/…","page":"wiles/index.html",…}
 *
 * `state` is one of `pass | drift | unverified_source | no_verdict | error`.
 * A torn or absent line parses to null, and the parent then says only that the
 * leg exited nonzero without a typed state — still never a drift claim.
 */
import { spawnSync } from "node:child_process";

export const STATE_LINE_KEY = "corpus-stats-state:";

/** The states the corpus-stat leg can reach, and what each one means for the reader. */
export const STATE = {
  /** Every graded page matches a report row that is itself in good standing. */
  PASS: "pass",
  /** A graded, verified row disagrees with the page. Art-side fix exists. */
  DRIFT: "drift",
  /** The report carries no verified measurement for that corpus: nothing was compared. */
  UNVERIFIED_SOURCE: "unverified_source",
  /** No evidence to grade against (no report, too old, or the row is older than the bound). */
  NO_VERDICT: "no_verdict",
  /** The leg broke: unparseable report, missing tile, unexpected throw. */
  ERROR: "error",
};

/** @returns {string} the one-line contract the parent parses. */
export function formatStateLine(payload) {
  const clean = {};
  for (const [k, v] of Object.entries(payload)) {
    if (v === null || v === undefined || v === "") continue;
    clean[k] = v;
  }
  return `${STATE_LINE_KEY} ${JSON.stringify(clean)}`;
}

/** @returns {object|null} the last typed state in `text`, or null when there is none. */
export function parseStateLine(text) {
  if (typeof text !== "string" || !text.includes(STATE_LINE_KEY)) return null;
  let found = null;
  for (const line of text.split("\n")) {
    const at = line.indexOf(STATE_LINE_KEY);
    if (at === -1) continue;
    try {
      const obj = JSON.parse(line.slice(at + STATE_LINE_KEY.length).trim());
      if (obj && typeof obj === "object" && typeof obj.state === "string") found = obj;
    } catch {
      // A torn line is not a state. Fall through to the honest unknown text.
    }
  }
  return found;
}

/** Short evidence tail for a refused row: the fields that say WHY the compiler abstained. */
function evidence(state) {
  const bits = [];
  if (state.build_status !== undefined) {
    bits.push(`build_status=${state.build_status === null ? "<absent>" : state.build_status}`);
  }
  if (state.build_exit !== undefined && state.build_exit !== null) bits.push(`build_exit=${state.build_exit}`);
  if (state.facts_status) bits.push(`facts_status=${state.facts_status}`);
  if (state.row_age_h !== undefined && state.row_age_h !== null) bits.push(`row_age=${state.row_age_h}h`);
  if (state.max_age_h !== undefined && state.max_age_h !== null) bits.push(`max=${state.max_age_h}h`);
  if (state.partial_reason) bits.push(`reason=${state.partial_reason}`);
  return bits.length ? ` (${bits.join(", ")})` : "";
}

/**
 * The sentence `check-site.mjs` books as its failure, built ONLY from fields
 * the child measured. The rule for every branch: say what was measured, name
 * the file it was measured from, and offer a cure that has been shown to work
 * for that state — or say plainly that no art-side cure exists.
 *
 * @param {object|null} state parsed from the child's state line, or null
 * @param {number|null} rc    the child's exit code
 * @returns {string}
 */
export function gateFailure(state, rc) {
  // The page is named only when the child measured one; inventing a path here
  // is the defect this module exists to remove.
  const page = state?.page ?? "corpus stats";
  const project = state?.project ? `"${state.project}"` : "the corpus";
  switch (state?.state) {
    case STATE.DRIFT:
      return (
        `${page}: corpus statistics disagree with ${state.report ?? "the proof report"} ` +
        `(state=drift; fix: node scripts/sync-corpus-stats.mjs)`
      );
    case STATE.UNVERIFIED_SOURCE:
      return (
        `${page}: corpus statistics NOT COMPARED — the proof report does not verify ` +
        `${project}${evidence(state)}${state.report ? ` at ${state.report}` : ""}. ` +
        `This is not a drift finding: the leg refused before comparing, and ` +
        `\`node scripts/sync-corpus-stats.mjs\` refuses the same row (rc 1), so no art-side ` +
        `commit clears it. The tiles keep the last verified digits; the leg grades again once ` +
        `the report carries build_status=GREEN for that corpus.`
      );
    case STATE.ERROR:
      return (
        `${page}: the corpus-stat leg could not grade (state=error` +
        `${state.reason ? `: ${state.reason}` : ""}${state.report ? `; report=${state.report}` : ""}). ` +
        `Nothing was compared — read node scripts/sync-corpus-stats.mjs --check for the cause.`
      );
    case STATE.NO_VERDICT:
      // The child prints its own no-verdict line and exits 0, so reaching the
      // failure list here means something else turned it red. Say only that.
      return (
        `${page}: the corpus-stat leg exited ${rc} after rendering no verdict ` +
        `(state=no_verdict; reason=${state.reason ?? "unstated"}) — read its output above.`
      );
    default:
      return (
        `corpus stats: the leg exited ${rc} without a typed state line, so nothing here can be ` +
        `attributed to a page or a report. Read node scripts/sync-corpus-stats.mjs --check.`
      );
  }
}

/**
 * Run the child leg exactly the way `check-site.mjs` does: forward its stdout
 * live, its stderr when it refused, and hand back the sentence to book.
 *
 * @param {{script: string, env?: object, execPath?: string, log?: (out: string, err: string) => void}} opts
 * @returns {{rc: number|null, state: object|null, failure: string|null, stdout: string, stderr: string}}
 */
export function runCorpusGate({ script, env = process.env, execPath = process.execPath, log }) {
  const gate = spawnSync(execPath, [script, "--check"], { encoding: "utf8", env });
  const stdout = gate.stdout ?? "";
  const stderr = gate.stderr ?? "";
  if (log) log(stdout, gate.status === 0 ? "" : stderr);
  else {
    if (stdout) process.stdout.write(stdout);
    if (gate.status !== 0 && stderr) process.stderr.write(stderr);
  }
  if (gate.status === 0) return { rc: 0, state: parseStateLine(stdout), failure: null, stdout, stderr };
  return {
    rc: gate.status,
    state: parseStateLine(stdout + stderr),
    failure: gateFailure(parseStateLine(stdout + stderr), gate.status),
    stdout,
    stderr,
  };
}
