/**
 * Museum navigation.js cross-repo mirror — art-side inspection + drift pin.
 * Lane RSIPIPE-06-NAVIGATION-1102, campaign RSI-PIPE-1102, 2026-11-02.
 *
 * Seed: code_map_rsi_targets generation ccc6b10cf4e942b58e445dc57655dbc2,
 * kind=near_duplicate, tier=T0, rankScore=7.397343 — BAND-ORDER ONLY, not a
 * measured quantity. The seed paired
 *   projects/art/patent-portfolio/museum/navigation.js  (blob bd836bd95975…)
 *   projects/awkronos/patents/museum/navigation.js      (blob d20f2aa3d96e…)
 * Both pinned identities are stale against the published tips re-measured here:
 * art's main moved to blob 6567e4f71f87… at tip bb0f227 (PR #16, lane
 * MUSEUM-NAVJS-1030) and patents' main moved to blob 66dd3d5da57a… at tip
 * c7b7ac1 (port 72faa42 + the RSI-PATENTS-PORTFOLD-1028 / PATENTS-GUARD-WIRE-1028
 * chain). See patent-portfolio/DEBT-museum-navigation-duplication.md for the
 * full history — this row is a declared canonical↔mirror pair with zero content
 * drift below the two doc headers, not actionable copy debt.
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

const REPO = resolve(dirname(fileURLToPath(import.meta.url)), "..", "..");
const CANONICAL = join(REPO, "patent-portfolio", "museum", "navigation.js");

const MIRROR =
  process.env.ARTNAV_MIRROR_PATH ||
  "/Users/schizodactyl/projects/awkronos/patents/museum/navigation.js";

// Measured 2026-11-02 at art origin/main bb0f227693e97f6b4dd83dcd079c33501b0441e3.
// Every figure below is a measurement, taken with the exact code in this file,
// not lifted from the DEBT note.
const EXPECTED_CANONICAL_BLOB = "6567e4f71f87d6dc72b5840bd89354f5abc9b752";
const EXPECTED_CANONICAL_SHA256 =
  "aba48a95050f8d94a1f20c40688243d9834a8424c9c00b62ebe74280fb02f9e9";
const EXPECTED_BODY_SHA256 =
  "1e2054a6b765ab682868986813090b392ab191ae01cdfd8a31c37c6130d64c7c";
const EXPECTED_BODY_LINES = 1234;
const EXPECTED_BODY_BYTES = 49768;

// Sentinel lines from art's own NEAR-DUPLICATE DECLARATION block (see residual 1
// of DEBT-museum-navigation-duplication.md). These three sentences describe the
// fork in the PRESENT TENSE with numbers that were true pre-port and are false
// at today's published bytes — recorded here on purpose, not fixed here. This
// test does not assert the prose is TRUE; it asserts the prose is UNCHANGED, so
// no future edit lands silently. Editing this block is the four-file, two-repo
// coordinated fold residual 1 describes (art's navigation.js, the patents
// mirror's own header, tests/CENSUS-museum-navigation-mirror.md's receipt, and
// leg 4 of tests/CENSUS-museum-navigation-mirror.check.mjs, which hardcodes
// these same art-side literals). One repo moving alone makes the other's guard
// read a row it has just made false. A red on this leg means: go read residual
// 1 and do the whole fold, not just the file that tripped.
const DECLARATION_SENTINELS = [
  " * A second copy of this module lives in another repository and is now 231 lines",
  " *   Delta: 117 insertions / 231 deletions across 19 hunks",
  " * RULE — never edit both copies. Change navigation HERE, then port it whole to the",
];

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

// ── T3: the canonical declaration prose does not rot silently ───────────────
test("navigation.js NEAR-DUPLICATE DECLARATION block is unchanged, not merely present", () => {
  const text = readRepoFile(CANONICAL);
  for (const sentinel of DECLARATION_SENTINELS) {
    assert.ok(
      text.includes(sentinel),
      `declaration sentinel vanished from navigation.js's header: ${JSON.stringify(
        sentinel
      )} — refreshing this prose is residual 1 of patent-portfolio/DEBT-museum-navigation-duplication.md: a four-file, two-repo coordinated fold, not a single-file edit. A red here means the fold was started in only one repo.`
    );
  }
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
