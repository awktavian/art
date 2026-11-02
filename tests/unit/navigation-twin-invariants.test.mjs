/**
 * navigation.js duplicate-twin invariants — the twin-merge / canonical-id RULES of the
 * museum twin family, asserted as rules rather than as pins.
 * Lane L33, campaign FIFTY-1102, 2026-11-02, on art origin/main
 * 6529725ad1b33eddf4a525c7b80403cf771990f0 (the RSIPIPE2-01-NAV-TWIN-1102 landing).
 *
 * WHY A THIRD FILE ON THIS PAIR. The family already has two, and neither is this:
 *   tests/unit/museum-navigation-mirror.test.mjs   T1-T5 — art-side byte pins + drift tripwire
 *   tests/unit/museum-twin-register.test.mjs       R1-R10 — the register's numbers vs the tree
 *   scripts/twin-register.mjs + NEAR-DUPLICATE-TWINS.json — the producer and its register
 * Those grade VALUES: this blob equals that hex, this row exists, this pin is current. What
 * they do not grade is the SHAPE of the rule that produced the values — whether a canonical
 * id could come out differently on another run, whether the pair relation is symmetric
 * enough that reading it from the mirror side gives the same verdict, whether adding a row
 * could silently produce a SECOND navigation entry, and what the helpers do with an empty or
 * single-element input. A rule that is only ever exercised on the one live family it was
 * written for is a rule whose failure modes are unmeasured. This file exercises the shape,
 * against the real bytes and the real register, and it adds no new pin: nothing here is a
 * second copy of a hex that lives in the register (the family's own `law.one_ssot`).
 *
 * THE FOUR INVARIANTS, and the leg that holds each:
 *   canonical id chosen deterministically ......... N1, N2
 *   twin detection is symmetric ................... N3
 *   no duplicate nav entries after merge .......... N4, N5, N7
 *   empty/one-entry degenerate cases are typed .... N6
 * N1 re-derives every register id from the row's own kind + leaf name and refuses any row
 * whose authored id differs — so an id is a function of the pair, not prose that happens to
 * look like one. N2 checks the canonical side is a member of the producer's typed enum and
 * that navigation.js's bytes RIGHT NOW carry the marker that side claims. N3 swaps the pair
 * through the producer's own instruments and requires the verdict to swap with it. N4 merges
 * the two `colonies` tables navigation.js actually carries. N5/N7 merge the register with a
 * duplicate candidate and require one survivor. N6 feeds empty and single-element inputs to
 * the helpers and requires a typed answer — a value or a NAMED refusal — never a crash.
 *
 * POSITIVE CONTROLS, run in a /tmp copy of this file plus the two inputs it reads (never
 * against the seat's files). Each block restored both inputs first, so a red leg names the one
 * thing that moved. An invariant that cannot go red certifies nothing. Measured:
 *   untouched copy                      rc=0, 7 green            (the harness is faithful)
 *   one byte flipped in navigation.js   N3 red — "art body sha drifted from the register"
 *   'crystal' repeated in the wing table N4 red — "the merged sequence is not the canonical
 *                                       menu table" (and N3, since the body moved)
 *   a register row's kind renamed       N1 red — 'register kind "museum-module-renamed" has no
 *                                       id prefix in this rule', with N5/N7 following
 *   canonical_side flipped to patents   N2 red — "navigation.js's canonical side moved"
 *   the DECLARATION line deleted        N2 red — "navigation.js's header markers are not what
 *                                       the register recorded", plus N3 (the body changed)
 *   a second navigation row re-added    N1 red — "id is not derivable from kind spec", and N5
 *                                       red — "art paths are not unique across pairs"
 *   ART_TWIN_MIRROR_REPO with no such object
 *                                       N3 SKIPS (typed UNMEASURED), everything else green,
 *                                       rc=0 — which is not a pass for that leg.
 *
 * Node builtins + `tests/unit/twin-measure.mjs`, the family's ONE measurement implementation —
 * so these legs grade the functions the register is actually built from, not a re-derivation
 * written here. No npm install, no network, no credentials.
 *
 * Mirror location, same override convention as the rest of the family
 * (ART_TWIN_MIRROR_REPO in scripts/twin-register.mjs and museum-twin-register.test.mjs):
 *   ART_TWIN_MIRROR_REPO  default /Users/schizodactyl/projects/awkronos/patents
 * The mirror tip is read from the register's own basis.patents_tip, so this file never
 * invents a ref, and every mirror leg SKIPS (typed UNMEASURED) when the object is absent.
 */
import { test } from "node:test";
import assert from "node:assert/strict";
import { existsSync, readFileSync } from "node:fs";
import { execFileSync } from "node:child_process";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

import {
  fileStats,
  sliceStats,
  bodyOf,
  bodyPair,
  divergence,
  headerMarkers,
  belowCommentHeader,
  readRegister,
} from "./twin-measure.mjs";

const REPO = resolve(dirname(fileURLToPath(import.meta.url)), "..", "..");
const NAV_REL = "patent-portfolio/museum/navigation.js";
const REGISTER = readRegister(REPO);
const NAV = REGISTER.pairs.find((p) => p.id === "museum.navigation.js");
assert.ok(NAV, "the register must carry a museum.navigation.js row for this file to mean anything");

const MIRROR_REPO =
  process.env.ART_TWIN_MIRROR_REPO || "/Users/schizodactyl/projects/awkronos/patents";
const MIRROR_TIP = REGISTER.basis.patents_tip;

const artText = readFileSync(join(REPO, NAV_REL), "utf8");

/** Bytes at the register's recorded PUBLISHED tip; null = this host cannot read it. */
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

const leaf = (p) => p.split("/").pop();
/** The producer's id rule, read off PAIRS in scripts/twin-register.mjs: kind prefix + leaf. */
const KIND_PREFIX = { "museum-module": "museum", spec: "spec" };
const deriveId = (row) => `${KIND_PREFIX[row.kind]}.${leaf(row.art.path)}`;

/**
 * The merge this family needs: order-stable dedup by canonical id, with every collision
 * REPORTED rather than resolved silently. `rejected` is the typed absence — a merged register
 * that dropped a row without saying so is exactly how a second navigation entry appears.
 */
function mergeById(rows) {
  const byId = new Map();
  const rejected = [];
  for (const row of rows) {
    const id = deriveId(row);
    const seen = byId.get(id);
    if (seen === undefined) byId.set(id, row);
    else rejected.push({ id, kept: seen.art.sha256, dropped: row.art.sha256 });
  }
  return { ids: [...byId.keys()], rows: [...byId.values()], rejected };
}

/**
 * The same shape over a navigation entry table: dedupe by name, order-stable, collisions
 * reported. A blank name is not an entry and not a duplicate — it is counted in `blanks`, so
 * an empty input answers with a typed shape instead of inventing an entry. Used on the two
 * `colonies` literals navigation.js carries and on the degenerate empty/one-entry cases in N6.
 */
function mergeEntries(lists) {
  const flat = lists.flat();
  const seen = new Set();
  const duplicates = [];
  const entries = [];
  let blanks = 0;
  for (const name of flat) {
    if (!name) {
      blanks += 1;
      continue;
    }
    if (seen.has(name)) duplicates.push(name);
    else {
      seen.add(name);
      entries.push(name);
    }
  }
  return { entries, duplicates, blanks };
}

// ── N1: the canonical id is a function of the pair, not prose ─────────────────
/**
 * Every register id re-derived from that row's own kind + leaf name. This is the determinism
 * leg: an authored id that a reader cannot reproduce from the row's paths is a second place
 * the pair is named, and the family's recorded failure mode is a name that rots. It also
 * proves the pairing rule itself — the two sides of a twin share a leaf name — because the
 * id derives identically from either side's path.
 */
test("navigation twin: every canonical id re-derives from its own kind and leaf name", () => {
  const kinds = new Set(REGISTER.pairs.map((p) => p.kind));
  for (const k of kinds) {
    assert.ok(KIND_PREFIX[k], `register kind ${JSON.stringify(k)} has no id prefix in this rule`);
  }
  for (const row of REGISTER.pairs) {
    assert.equal(
      deriveId(row),
      row.id,
      `${row.id}: id is not derivable from kind ${row.kind} + leaf ${leaf(row.art.path)}`,
    );
    assert.equal(
      `${KIND_PREFIX[row.kind]}.${leaf(row.patents.path)}`,
      row.id,
      `${row.id}: the id derives differently from the mirror side's leaf name — the pair is not a twin of one file`,
    );
    assert.equal(deriveId(row), deriveId(row), `${row.id}: derivation is not stable across calls`);
  }
  // The pair this lane is about, by name, so a rename cannot pass by accident.
  assert.equal(deriveId(NAV), "museum.navigation.js");
  assert.equal(NAV.art.path, NAV_REL);
  assert.equal(leaf(NAV.patents.path), leaf(NAV.art.path));
});

// ── N2: the canonical side is typed, and navigation.js's bytes are the evidence ─
/**
 * `declaration.canonical_side` is authored once in scripts/twin-register.mjs and is the only
 * thing that decides "undeclared". So it must come from a closed enum, and for navigation.js
 * it must be backed by the marker it claims: art's header names itself CANONICAL. The marker
 * is re-measured from these bytes here and now, and compared with what the register recorded,
 * so a deleted header line reddens this leg instead of quietly narrowing a claim.
 */
test("navigation twin: the canonical side is a typed choice the file's own bytes support", () => {
  const ENUM = new Set(["art", "patents", "none-declared"]);
  for (const row of REGISTER.pairs) {
    const side = row.declaration.canonical_side;
    assert.ok(ENUM.has(side), `${row.id}: canonical_side ${JSON.stringify(side)} is outside ${[...ENUM]}`);
    // A declared side must name one of the two sides of ITS OWN pair.
    if (side !== "none-declared") {
      assert.ok(["art", "patents"].includes(side), `${row.id}: declared side must be a side`);
      assert.ok(
        side === "art" ? row.art.path : row.patents.path,
        `${row.id}: declared ${side} but that side names no path`,
      );
    }
  }
  assert.equal(NAV.declaration.canonical_side, "art", "navigation.js's canonical side moved");

  const now = headerMarkers(artText);
  assert.deepEqual(
    now.map((m) => m.marker),
    NAV.art.header_markers.map((m) => m.marker),
    "navigation.js's header markers are not what the register recorded — the declaration moved",
  );
  const canonical = now.find((m) => m.marker === "NEAR-DUPLICATE-DECLARATION");
  assert.ok(canonical, "navigation.js no longer carries the NEAR-DUPLICATE DECLARATION line");
  assert.match(canonical.text, /this copy is CANONICAL/, `${canonical.text} does not claim canonical`);
  assert.equal(canonical.line, 10, "the declaration moved off line 10 without the register moving");

  // Degenerate: a file with no header at all reports NO markers — an empty typed answer.
  assert.deepEqual(headerMarkers(""), []);
  assert.deepEqual(headerMarkers("   \n"), []);
});

// ── N3: twin detection is symmetric ───────────────────────────────────────────
/**
 * The pair relation must not depend on which copy you happen to be standing in. Forward and
 * reverse runs go through the producer's own instruments: `bodyPair` must reach the same
 * verdict with the arguments swapped, and `divergence` must swap its one-sided counts.
 *
 * What is deliberately NOT claimed: the per-side unique-line DIGESTS are not swap-equal,
 * measured here at these bytes — `/usr/bin/diff` groups context differently per direction,
 * so the pooled line order differs and so does its sha256. The counts are the symmetric
 * quantity; the digests are pinned beside the direction that produced them (in the register)
 * and asserted only to be well-formed here. Saying "symmetric" about the digests would be a
 * claim these instruments do not support.
 */
test("navigation twin: body identity and divergence give the same verdict from either side", (t) => {
  const patText = mirrorAtTip(NAV.patents.path);
  if (patText === null) {
    t.skip(
      `UNMEASURED: no ${NAV.patents.path} at ${MIRROR_TIP || "a recorded tip"} in ${MIRROR_REPO} on this host`,
    );
    return;
  }
  const recipe = NAV.body_identity.recipe;
  const fwd = bodyPair(artText, patText, recipe);
  const rev = bodyPair(patText, artText, recipe);
  assert.equal(fwd.identical, rev.identical, "body identity depends on which side is read first");
  assert.deepEqual(
    { a: fwd.art.sha256, b: fwd.patents.sha256 },
    { a: rev.patents.sha256, b: rev.art.sha256 },
    "swapping the pair did not swap the two body digests",
  );
  // And the register's recorded art-side body is the same digest this run recomputes.
  assert.equal(fwd.art.sha256, NAV.body_identity.art.sha256, "art body sha drifted from the register");
  assert.equal(fwd.art.bytes, NAV.body_identity.art.bytes);
  assert.equal(fwd.art.lines, NAV.body_identity.art.lines);

  const dFwd = divergence(artText, patText, "L33-nav-fwd");
  const dRev = divergence(patText, artText, "L33-nav-rev");
  // The digests are NOT asserted swap-equal (see the header): each is only required to be
  // well-formed when that side actually has unique lines, and null when it has none.
  for (const [label, d] of [["fwd", dFwd], ["rev", dRev]]) {
    for (const [countField, digestField] of [["art_only_lines", "art_only_sha256"], ["patents_only_lines", "patents_only_sha256"]]) {
      const digest = d[digestField];
      if (d[countField] === 0) assert.equal(digest, null, `${label}: no unique lines must report a null digest`);
      else assert.match(digest, /^[0-9a-f]{64}$/, `${label}: ${digestField} is not 64 hex`);
    }
  }
  assert.equal(dFwd.hunks, dRev.hunks, `hunk count is not direction-independent: ${dFwd.hunks} vs ${dRev.hunks}`);
  assert.equal(
    dFwd.art_only_lines,
    dRev.patents_only_lines,
    `art-only ${dFwd.art_only_lines} != reverse patents-only ${dRev.patents_only_lines}`,
  );
  assert.equal(
    dFwd.patents_only_lines,
    dRev.art_only_lines,
    `patents-only ${dFwd.patents_only_lines} != reverse art-only ${dRev.art_only_lines}`,
  );
  // The register recorded the forward direction; this run must reproduce it.
  assert.equal(dFwd.hunks, NAV.divergence.hunks, "divergence hunks drifted from the register");
  assert.equal(
    dFwd.art_only_lines,
    NAV.divergence.art_only_lines,
    "art-only line count drifted from the register",
  );
  assert.equal(
    dFwd.patents_only_lines,
    NAV.divergence.patents_only_lines,
    "patents-only line count drifted from the register",
  );
  assert.equal(dFwd.art_only_sha256, NAV.divergence.art_only_sha256, "art-only digest drifted");
  assert.equal(dFwd.patents_only_sha256, NAV.divergence.patents_only_sha256, "patents-only digest drifted");
});

// ── N4: no duplicate nav entries in the tables navigation.js itself carries ────
/**
 * navigation.js declares the wing set twice: the gallery-menu table (rotunda + seven) and the
 * teleport table (seven), plus a parallel `wingNames` display table. The fork this pair closed
 * carried a teleport table that sent Crystal Wing to the same position as the Vestibule — a
 * duplicate entry wearing two different names. So the invariants are: each table is
 * duplicate-free on its own; the merge introduces NO new entry; the cross-table overlap is
 * exactly the wing set (the menu table is rotunda + wings, so a colony renamed in one table
 * only would surface as an entry the other cannot reach); and the colony→display-name map is
 * injective, with rotunda unreachable through the wing index. Parsed from these bytes, never
 * transcribed.
 *
 * Stated precisely because the naive claim is false: "merge the two tables and see zero
 * duplicates" cannot hold for a pair where one table is a strict subset of the other — the
 * overlap is the whole point of the second table. Measured here: the forward merge reports 7
 * cross-table repeats, exactly the wing set. What must be zero is the count WITHIN a table and
 * the set of entries the merge ADDS.
 */
test("navigation twin: the wing table adds no entry the menu table lacks, and no name repeats within a table", () => {
  const splitList = (inner) =>
    inner
      .split(",")
      .map((s) => s.trim().replace(/^['"]|['"]$/g, ""))
      .filter(Boolean);
  const coloniesLiterals = [...artText.matchAll(/const colonies = \[([^\]]*)\];/g)].map((m) =>
    splitList(m[1]),
  );
  assert.equal(coloniesLiterals.length, 2, `expected two colonies tables, found ${coloniesLiterals.length}`);
  const [menu, wing] = coloniesLiterals;
  const nameLiterals = [...artText.matchAll(/const wingNames = \[([^\]]*)\];/g)].map((m) =>
    splitList(m[1]),
  );
  assert.equal(nameLiterals.length, 1, `expected exactly one wingNames table, found ${nameLiterals.length}`);
  const wingNames = nameLiterals[0];

  for (const [label, list] of [["menu", menu], ["wing", wing], ["names", wingNames]]) {
    assert.equal(new Set(list).size, list.length, `${label} table carries a duplicate entry: ${list.join(",")}`);
  }

  // The merge introduces NO new entry: the canonical sequence stays the menu table, and the
  // repeats it reports are exactly the wing set (the second table restates seven of the eight
  // menu entries — that overlap is the design, so the claim is about WHAT repeats, not THAT).
  const merged = mergeEntries([menu, wing]);
  assert.deepEqual(merged.entries, menu, "the merged sequence is not the canonical menu table");
  assert.deepEqual(
    merged.duplicates,
    wing,
    `cross-table repeats are not exactly the wing set: ${JSON.stringify(merged.duplicates)}`,
  );
  assert.equal(merged.blanks, 0, "an empty name reached the nav entry merge");
  // A colony renamed in ONE table would surface here as an entry the other cannot reach.
  assert.deepEqual(
    wing.filter((n) => !menu.includes(n)),
    [],
    "the wing table names a colony the menu table cannot reach",
  );
  assert.deepEqual(
    menu.filter((n) => !wing.includes(n)),
    ["rotunda"],
    "the menu table is not exactly rotunda plus the wing set",
  );
  // Order-independence: which entries SURVIVE does not depend on merge order, only their order.
  const reversed = mergeEntries([wing, menu]);
  assert.deepEqual(
    [...reversed.entries].sort(),
    [...merged.entries].sort(),
    "merge order changed which entries survive — the canonical set is not order-independent",
  );
  assert.deepEqual(reversed.entries, wing.concat(["rotunda"]), "reverse merge did not stay order-stable");
  assert.deepEqual(
    reversed.duplicates,
    menu.filter((n) => n !== "rotunda"),
    "reverse merge reported a different overlap than the forward one",
  );
  assert.equal(reversed.blanks, merged.blanks);

  // The colony → display-name map is index-aligned and injective.
  assert.equal(wingNames.length, wing.length, "wingNames and the wing colonies table are not aligned");
  for (let i = 0; i < wing.length; i++) {
    assert.equal(
      wingNames[i].toLowerCase().startsWith(wing[i]),
      true,
      `index ${i}: ${wing[i]} maps to ${wingNames[i]} — the tables have drifted apart`,
    );
  }
  assert.ok(!wing.includes("rotunda"), "rotunda is reachable through the wing index");
  assert.ok(menu.includes("rotunda") && menu.indexOf("rotunda") === 0, "menu table no longer leads with rotunda");
});

// ── N5: the register merges to one row per pair, and nothing collides ──────────
/**
 * Row-level duplicate check over the real register: no two rows may claim the same canonical
 * id, the same art path, or the same mirror path, and a file cannot be both a twin and a
 * declared non-twin. Merging the register with itself must be the identity — the proof that
 * the register is already a fixed point, which is what makes it safe to call the SSOT.
 */
test("navigation twin: the register merges with itself as the identity, one navigation row", () => {
  const self = mergeById(REGISTER.pairs);
  assert.equal(self.rejected.length, 0, `self-merge rejected rows: ${JSON.stringify(self.rejected)}`);
  assert.deepEqual(self.ids, REGISTER.pairs.map(deriveId), "self-merge did not preserve the row set");
  assert.equal(self.rows.length, REGISTER.pairs.length);
  assert.equal(self.ids.filter((id) => id === "museum.navigation.js").length, 1, "not exactly one navigation row");

  for (const field of ["art", "patents"]) {
    const paths = REGISTER.pairs.map((p) => p[field].path);
    assert.equal(new Set(paths).size, paths.length, `${field} paths are not unique across pairs`);
  }
  const artPaths = new Set(REGISTER.pairs.map((p) => p.art.path));
  for (const n of REGISTER.not_twins.filter((n) => n.side === "art-only")) {
    assert.ok(!artPaths.has(n.path), `${n.path} is declared both a twin and a non-twin`);
  }
});

// ── N6: degenerate inputs answer, they do not crash ────────────────────────────
/**
 * The empty and one-element cases, straight into the family's measurement module. Two shapes
 * of honest answer: a typed value (empty stats, empty marker list, an all-identical pair) and
 * a NAMED refusal for an input that cannot mean anything (no doc header, unknown recipe). A
 * TypeError leaking out of either would be the crash this leg is here to rule out.
 */
test("navigation twin: empty and one-entry inputs produce typed answers, never a crash", () => {
  // Empty text has an identity, and it is git's own empty-blob identity.
  const empty = fileStats("");
  assert.equal(empty.bytes, 0);
  assert.equal(empty.lines, 0);
  assert.equal(empty.blob, "e69de29bb2d1d6434b8b29ae775ad8c2e48c5391");
  assert.equal(
    empty.sha256,
    "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
  );
  assert.equal(sliceStats("").bytes, 0);
  assert.equal(belowCommentHeader(""), "");
  assert.deepEqual(mergeEntries([]), { entries: [], duplicates: [], blanks: 0 });
  // A blank is not an entry and not a duplicate: it is counted, so an empty input answers.
  assert.deepEqual(mergeEntries(["", ""]), { entries: [], duplicates: [], blanks: 2 });
  assert.deepEqual(mergeById([]), { ids: [], rows: [], rejected: [] });

  // One-entry: a pair with itself is identical, and its divergence is a typed zero.
  const one = "export const x = 1;\n";
  assert.equal(bodyOf(one, "whole"), one);
  assert.equal(bodyPair(one, one, "whole").identical, true);
  const same = divergence(one, one, "L33-one-entry");
  assert.equal(same.hunks, 0);
  assert.equal(same.art_only_lines, 0);
  assert.equal(same.patents_only_lines, 0);
  assert.equal(same.art_only_sha256, null, "a side with no unique lines reports null, not a digest");
  assert.equal(same.patents_only_sha256, null);
  assert.deepEqual(mergeEntries(["rotunda"]), { entries: ["rotunda"], duplicates: [], blanks: 0 });
  assert.deepEqual(mergeEntries(["rotunda", "rotunda"]), {
    entries: ["rotunda"],
    duplicates: ["rotunda"],
    blanks: 0,
  });

  // Refusals are named, and named as Errors (not a TypeError from reading undefined).
  assert.throws(() => bodyOf(one, "no-such-recipe"), /^Error: unknown body recipe/);
  assert.throws(() => bodyOf("", "doc-header"), /^Error: no doc header opening/);
  assert.throws(() => bodyOf("/* never closes", "doc-header"), /doc header never closes/);
});

// ── N7: a second navigation row cannot sneak in ───────────────────────────────
/**
 * The merge's tie-break must be deterministic, because "first one wins" only means something
 * if the first one is well-defined. A duplicate candidate for this exact pair — same id, a
 * doctored pin — must be REJECTED into the typed `rejected` list, and the survivor must be
 * byte-identical to the register row it displaced. This is the guard against a re-added twin
 * row splitting `museum.navigation.js` into two entries with two different canonical claims.
 */
test("navigation twin: a duplicate candidate is rejected and the survivor is the register row", () => {
  const twinRow = { ...NAV, art: { ...NAV.art, sha256: "f".repeat(64) } };
  const merged = mergeById(REGISTER.pairs.concat([twinRow]));
  assert.equal(merged.rows.length, REGISTER.pairs.length, "a duplicate row enlarged the register");
  assert.equal(merged.rejected.length, 1, `expected one rejection, got ${JSON.stringify(merged.rejected)}`);
  assert.equal(merged.rejected[0].id, NAV.id);
  assert.equal(merged.rejected[0].kept, NAV.art.sha256, "the survivor is not the row the register carries");
  assert.equal(merged.rejected[0].dropped, "f".repeat(64));
  const survivor = merged.rows.find((r) => deriveId(r) === NAV.id);
  assert.deepEqual(survivor, NAV, "the surviving navigation row's bytes are not the register's row");

  // Candidate first, register second: the SAME id is rejected, so the outcome is a property
  // of the id, not of which list the caller happened to put down first.
  const flipped = mergeById([twinRow].concat(REGISTER.pairs));
  assert.equal(flipped.rejected.length, 1);
  assert.equal(flipped.rejected[0].id, NAV.id);
  assert.equal(flipped.ids.length, REGISTER.pairs.length);
});
