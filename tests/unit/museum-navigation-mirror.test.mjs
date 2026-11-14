/**
 * Museum navigation.js cross-repo mirror — art-side inspection + drift pin.
 * Lane RSIPIPE-06-NAVIGATION-1102, campaign RSI-PIPE-1102, 2026-11-02.
 *
 * Seed: code_map_rsi_targets generation ccc6b10cf4e942b58e445dc57655dbc2,
 * kind=near_duplicate, tier=T0, rankScore=7.397343 — BAND-ORDER ONLY, not a
 * measured quantity. The seed paired
 *   projects/art/patent-portfolio/museum/navigation.js  (blob bd836bd95975…)
 *   projects/awkronos/patents/museum/navigation.js      (blob d20f2aa3d96e…)
 * Both pinned identities are stale against the published tips: the generation scored art's
 * parked checkout and a banked pre-port `wip` commit in patents, not either published surface.
 * That census reading, with every hex it names, lives in
 * patent-portfolio/NEAR-DUPLICATE-TWINS.json under `census_provenance` — re-measured from both
 * object databases on every run, so it is not restated here. See
 * patent-portfolio/DEBT-museum-navigation-duplication.md for the full history — the pair is a
 * declared canonical↔mirror pair with zero content drift below the two doc headers, not
 * actionable copy debt.
 *
 * Producer action, converted in-lane: "RECORD similarity-scored class (SimHash
 * Hamming) for inspection" — computed live from the published bytes on this host
 * (T5 below), never inherited from the seed's numbers. "Measure raw-byte
 * differences and compare both sides' unique behavior before proposing any
 * consolidation" — done as a sha256 pin on each file's body-below-doc-header.
 * The two instruments are NOT interchangeable and are not used as an
 * either/or cross-check: sha256 is the exact byte pin that gates (T1, T2, T5),
 * SimHash is the coarse similarity CLASS that gets recorded and never gates.
 * A positive control (below) proves why: a one-line body edit leaves the
 * SimHash signature UNCHANGED while sha256 catches it on the first byte, so a
 * SimHash "distance 0" would certify divergence as identity if it were allowed
 * to assert anything. Similarity alone never authorizes merging or deleting
 * files, and nothing here merges or deletes anything.
 *
 * The gap this closes: `tests/unit/` has never covered navigation.js at all —
 * `git grep -l navigation <art-tip> -- tests` returns zero files (recorded in
 * DEBT-museum-navigation-duplication.md, residual 1). The `patents` side carries
 * a 6-leg guard (tests/CENSUS-museum-navigation-mirror.check.mjs, wired to a
 * tracked .githooks/pre-commit); the `art` side carries only prose. The
 * canonical declaration is the copy that can rot silently. This file is the
 * art-side tripwire for that.
 *
 * Positive controls (why an identity check that cannot go red proves nothing):
 * three were run before this file was committed. (1) In a scratch copy of a
 * minimal fake repo: appending one token to the module body turned T1 and T2
 * red ("blob sha1 drifted", "body is 49774 B, expected 49768") — while the
 * SimHash body distance stayed 0. That second half of the observation is why T5
 * records SimHash instead of asserting on it. (2) In the seat itself, driving
 * the mirror leg through ARTNAV_MIRROR_PATH at a full-size doctored copy of the
 * mirror: T5's sha256 leg goes red ("mirror body diverged…"). (3) The same leg
 * pointed at a nonexistent path: one honest skip, rc=0. See the lane receipts.
 *
 * Mirror path, overridable for host-local/known-positive runs (same convention
 * as tests/unit/identity-coherence.test.mjs's KAGAMI_COLONIES_PY /
 * WADDLE_TOKENS_JSON):
 *   ARTNAV_MIRROR_PATH  default /Users/schizodactyl/projects/awkronos/patents/museum/navigation.js
 * The mirror leg SKIPS honestly when absent — UNMEASURED, not drift, not pass.
 */
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync, existsSync } from "node:fs";
import { createHash } from "node:crypto";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

import { readRegister } from "./twin-measure.mjs";

const REPO = resolve(dirname(fileURLToPath(import.meta.url)), "..", "..");
const CANONICAL = join(REPO, "patent-portfolio", "museum", "navigation.js");

const MIRROR =
  process.env.ARTNAV_MIRROR_PATH ||
  "/Users/schizodactyl/projects/awkronos/patents/museum/navigation.js";

// Whole-file identity of the canonical copy, measured 2026-11-14 by lane RST-TWINFOLD-1114 at
// these bytes. The identity moved when DEBT-museum-navigation-duplication.md residual 1 was
// folded: the header's pre-port narrative and the digests it restated were removed, the module
// body was not touched, which is why the three body pins below are the 2026-11-02 figures
// unchanged. These two literals are NOT the only copy of this fact and must never become one
// again — tests/unit/museum-twin-register.test.mjs R2 re-measures them against the working tree
// and R3 requires the register's row, these literals and the tree to name identical bytes. To
// move them: re-measure with `git hash-object` / `shasum -a 256` on the file, then regenerate
// the register with `node scripts/twin-register.mjs --write`, in the same commit.
const EXPECTED_CANONICAL_BLOB = "23e82b62e0abe42deaa3d348584ac1de50106aae";
const EXPECTED_CANONICAL_SHA256 =
  "eb4b3f8dd4d85a95d6004d2c68b8c2560d2d4951944515ce7f397593c7c8adb6";
const EXPECTED_BODY_SHA256 =
  "1e2054a6b765ab682868986813090b392ab191ae01cdfd8a31c37c6130d64c7c";
const EXPECTED_BODY_LINES = 1234;
const EXPECTED_BODY_BYTES = 49768;

// The register row this file's canonical copy points at. T3 reads the pointer out of the
// header, resolves it here, and checks the register's numbers against these bytes.
const REGISTER_ID = "museum.navigation.js";
const POINTER_RE = /NEAR-DUPLICATE-TWINS\.json id "([^"]+)"/;

function readRepoFile(rel) {
  return readFileSync(rel, "utf8");
}

/**
 * The module body: everything after the block-comment close token that ends the
 * opening doc comment, skipping any leading line-comment or blank lines first
 * (so the mirror's PROVENANCE pre-header, absent on canonical, does not shift
 * where the body starts). Matches the `tail -n +37` / `tail -n +51` recipe of
 * the patents receipt: 1234 lines on both sides.
 */
function belowDocHeader(text) {
  const lines = text.split("\n");
  let i = 0;
  while (i < lines.length && (lines[i].startsWith("//") || lines[i].trim() === "")) i++;
  if (!lines[i] || !lines[i].trimStart().startsWith("/*")) {
    throw new Error(`no doc header opening at line ${i + 1}`);
  }
  let j = i;
  while (j < lines.length && !lines[j].includes("*/")) j++;
  if (j >= lines.length) throw new Error("doc header never closes");
  return lines.slice(j + 1).join("\n");
}

function sha256(str) {
  return createHash("sha256").update(str, "utf8").digest("hex");
}

function gitBlobSha1(str) {
  const buf = Buffer.from(str, "utf8");
  const h = createHash("sha1");
  h.update(`blob ${buf.length}\0`, "utf8");
  h.update(buf);
  return h.digest("hex");
}

/**
 * 64-bit SimHash over 3-word shingles, sha256-truncated as the per-shingle
 * hash. Deterministic and dependency-free. This is a COARSE similarity class,
 * the same family of instrument the RSI seed's near_duplicate row is scored
 * with — deliberately NOT used for exact identity: a positive control showed a
 * one-line body edit leaves this signature unchanged. Only sha256 pins bytes.
 */
function simhash64(text, k = 3) {
  const tokens = text.toLowerCase().match(/\w+/gu) || [];
  const v = new Array(64).fill(0);
  for (let i = 0; i + k <= tokens.length; i++) {
    const d = createHash("sha256").update(tokens.slice(i, i + k).join(" "), "utf8").digest();
    const h = d.readBigUInt64BE(0);
    for (let b = 0; b < 64; b++) v[b] += (h >> BigInt(b)) & 1n ? 1 : -1;
  }
  let sig = 0n;
  for (let b = 0; b < 64; b++) if (v[b] > 0) sig |= 1n << BigInt(b);
  return sig;
}

function hamming64(a, b) {
  let x = a ^ b;
  let c = 0;
  while (x > 0n) {
    c += Number(x & 1n);
    x >>= 1n;
  }
  return c;
}

// ── T1: the canonical file is byte-identical to its own published pin ───────
test("navigation.js canonical: blob sha1 and whole-file sha256 match the published tip", () => {
  const text = readRepoFile(CANONICAL);
  assert.equal(
    gitBlobSha1(text),
    EXPECTED_CANONICAL_BLOB,
    "navigation.js blob sha1 drifted — see patent-portfolio/DEBT-museum-navigation-duplication.md before editing, and read T3's note on the fold protocol"
  );
  assert.equal(sha256(text), EXPECTED_CANONICAL_SHA256, "navigation.js whole-file sha256 drifted");
});

// ── T2: the module body below the doc header is the pinned, guard-known body ─
test("navigation.js body-below-doc-header is the same bytes the patents receipt pins", () => {
  const body = belowDocHeader(readRepoFile(CANONICAL));
  const bodyBytes = Buffer.byteLength(body, "utf8");
  assert.equal(bodyBytes, EXPECTED_BODY_BYTES, `body is ${bodyBytes} B, expected ${EXPECTED_BODY_BYTES}`);
  assert.equal(
    sha256(body),
    EXPECTED_BODY_SHA256,
    "navigation.js module body (not comments) changed — this is a behavior change to the canonical file, and the mirror copy must be ported to match, per DEBT-museum-navigation-duplication.md's RULE"
  );
  assert.equal(
    (body.match(/\n/g) || []).length,
    EXPECTED_BODY_LINES,
    "body line count drifted"
  );
});

// ── T3: the canonical header points at the register and restates no figure ───
/**
 * This leg used to be its opposite. Old T3 asserted that three sentences of the pre-port
 * narrative were still present — a guard that could only redden by re-pasting the rot, and
 * which therefore certified false prose as green. Residual 1 is now folded: every number that
 * describes this pair (blobs, sizes, line counts, the delta, the census legs) is produced by
 * scripts/twin-register.mjs into patent-portfolio/NEAR-DUPLICATE-TWINS.json, and the header
 * names none of them. What is checked here is therefore the shape that keeps it true: the
 * pointer resolves to a real row, the register's row agrees with these bytes, and no digest or
 * delta figure has crept back into the header.
 *
 * Falsifiers, both run before this was committed: editing the register's art blob for this row
 * reddens assert 3 naming both hexes; re-pasting a 40-hex into the header reddens assert 2 on
 * the offending line. Neither needs a second edit to this file.
 */
function docHeaderOf(text) {
  const lines = text.split("\n");
  const end = lines.findIndex((l) => l.includes("*/"));
  assert.ok(end >= 0, "navigation.js has no doc-header close token");
  return lines.slice(0, end + 1).join("\n");
}

test("navigation.js declaration points into the register, restates no figure, and the register agrees with these bytes", () => {
  const text = readRepoFile(CANONICAL);
  const header = docHeaderOf(text);

  // 1. the pointer is present and names THIS pair's row id.
  const pointer = POINTER_RE.exec(header);
  assert.ok(
    pointer,
    `navigation.js's header lost its pointer to the register (expected the form NEAR-DUPLICATE-TWINS.json id "${REGISTER_ID}") — prose without a pointer is how a figure becomes unwritable-and-uncheckable`
  );
  assert.equal(
    pointer[1],
    REGISTER_ID,
    `navigation.js's header points at register row "${pointer[1]}", not "${REGISTER_ID}"`
  );

  // 2. the header states no digest and no delta arithmetic — a second copy of a number here is
  //    a fork of the register, which is the failure that rotted once already.
  const restated = [
    [/\b[0-9a-f]{40}\b/gu, "a 40-hex git blob"],
    [/\b[0-9a-f]{64}\b/gu, "a 64-hex sha256"],
    [/\b\d+\s+(?:lines|insertions|deletions)\b/giu, "a line/delta count"],
    [/\bhunks?\b/giu, "a diff-hunk count"],
  ].flatMap(([re, what]) => (header.match(re) || []).map((m) => `${what} "${m}"`));
  assert.deepEqual(
    restated,
    [],
    `navigation.js's header restates ${restated.join(", ")} — numbers live in patent-portfolio/NEAR-DUPLICATE-TWINS.json id "${REGISTER_ID}"; pointing is allowed, restating is the fork that made the old prose silently false. Re-measured by museum-twin-register.test.mjs R2/R3.`
  );

  // 3. the register still describes THIS tree. Flip either side and this names both hexes.
  const register = readRegister(REPO);
  const row = register.pairs.find((p) => p.id === REGISTER_ID);
  assert.ok(row, `the register has no row "${REGISTER_ID}" that navigation.js can point at`);
  assert.equal(
    row.art.blob,
    gitBlobSha1(text),
    `register row "${REGISTER_ID}" pins art blob ${row.art.blob} but these bytes are ${gitBlobSha1(text)} — regenerate (node scripts/twin-register.mjs --write) or the pointer is folklore`
  );
  assert.equal(
    row.art.sha256,
    sha256(text),
    `register row "${REGISTER_ID}" pins art sha256 ${row.art.sha256} but these bytes hash to ${sha256(text)}`
  );
  assert.equal(
    row.body_identity.art.sha256,
    EXPECTED_BODY_SHA256,
    `register row "${REGISTER_ID}" and this file's body pin disagree — one of the two carriers of the body identity moved alone`
  );
  assert.equal(
    row.declaration.canonical_side,
    "art",
    `the register no longer declares art canonical, but navigation.js's header still says "this copy is CANONICAL"`
  );
});

// ── T4: the named exports and their one consumer site ────────────────────────
test("navigation.js exports MuseumNavigation and its single main.js consumer still imports it by that name", () => {
  const text = readRepoFile(CANONICAL);
  assert.match(text, /^export class MuseumNavigation \{$/m, "named export `MuseumNavigation` missing or renamed");
  assert.match(text, /^export default MuseumNavigation;$/m, "default export changed");

  const main = readRepoFile(join(REPO, "patent-portfolio", "main.js"));
  assert.match(
    main,
    /import \{ MuseumNavigation \} from ['"]\.\/museum\/navigation\.js['"];/,
    "main.js no longer imports MuseumNavigation from ./museum/navigation.js — the pairing this note describes is by this consumer, not just by filename"
  );
});

// ── T5: the mirror, when this host carries it, has an identical module body ──
test("navigation.js mirror copy has a sha256-identical module body; SimHash class recorded, not gated", (t) => {
  if (!existsSync(MIRROR)) {
    t.skip(`mirror absent: ${MIRROR} — UNMEASURED on this host, not drift, not pass`);
    return;
  }
  const canonText = readRepoFile(CANONICAL);
  const mirrorText = readFileSync(MIRROR, "utf8");
  const canonBody = belowDocHeader(canonText);
  const mirrorBody = belowDocHeader(mirrorText);

  assert.equal(
    sha256(mirrorBody),
    EXPECTED_BODY_SHA256,
    "mirror body diverged from the pinned canonical body — canonical-first: change art, then port whole, never hand-edit the delta into the mirror"
  );

  // Recorded, never asserted. SimHash is the seed's own class instrument, and
  // the positive control in this file's header shows it is lossy: it reports
  // distance 0 for two bodies that differ by an appended token. A number that
  // cannot go red on real divergence is a measurement of a class, not a proof
  // of identity, so identity stays with sha256 above and this stays a record.
  const bodyDistance = hamming64(simhash64(canonBody), simhash64(mirrorBody));
  const wholeFileDistance = hamming64(simhash64(canonText), simhash64(mirrorText));
  t.diagnostic(
    `simhash-hamming: body=${bodyDistance} whole-file=${wholeFileDistance} (of 64) — similarity class recorded for inspection only, per the seed's producer action; not a merge or deletion instruction, not a threshold this file gates on, and not an identity check (see header: positive control 1)`
  );
});
