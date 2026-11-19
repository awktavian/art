/**
 * proof/SUPERSEDED.md and proof-galaxy/SUPERSEDED.md — the supersession
 * statement of the two archived static exhibits, and who owns it.
 *
 * On 2026-04-26 both archived directories received the same statement, and
 * by 2026-11-14 the two files were byte-identical copies of one git blob
 * (ab8fa176) — two tombstones, one statement, no named source of truth
 * (code-map row `proof-galaxy/SUPERSEDED.md`: "Pick a source of truth…").
 * The adjudication `patent-portfolio/reports/src-ssot-adjudication-1114.md`
 * ruled `proof/SUPERSEDED.md` canonical — its body primarily describes the
 * `art/proof/` scroll-essay — and reduced `proof-galaxy/SUPERSEDED.md` to a
 * pointer that keeps the tombstone. That fold landed in `eb240f2`.
 *
 * The property under test is the authority split itself: exactly one file
 * holds the statement, the other routes readers to it, and the two are never
 * again byte-identical copies with equal claim. A prose "read the other one"
 * note is not a defense; this pin is.
 */
import assert from "node:assert/strict";
import test from "node:test";
import { readFileSync, existsSync } from "node:fs";

const canonicalPath = new URL("../../proof/SUPERSEDED.md", import.meta.url);
const pointerPath = new URL("../../proof-galaxy/SUPERSEDED.md", import.meta.url);

const canonical = () => readFileSync(canonicalPath, "utf8");
const pointer = () => readFileSync(pointerPath, "utf8");

// First-person authority declaration ("this file is the source of truth").
// A pointer may *mention* the phrase to route readers; only the canonical
// copy may claim it for itself.
const SELF_DECLARATION = /this file is the source of truth/i;

test("both archived exhibits keep a tombstone", () => {
  // The adjudication's fold rule: "Do not delete this tombstone — an
  // archived directory with no tombstone loses the reason it is empty."
  for (const [where, p] of [["proof/", canonicalPath], ["proof-galaxy/", pointerPath]]) {
    assert.ok(existsSync(p), `${where}SUPERSEDED.md is missing — archived dirs need their tombstone`);
    assert.ok(readFileSync(p, "utf8").trim().length > 0, `${where}SUPERSEDED.md is empty`);
  }
});

test("the two tombstones are not byte-identical copies", () => {
  // The defect this row was minted from: git said
  // `rev-parse HEAD:proof/SUPERSEDED.md` and `HEAD:proof-galaxy/SUPERSEDED.md`
  // returned the same blob, so "which copy should a reader trust" had no
  // answer in the files themselves.
  assert.notEqual(canonical(), pointer(), "tombstones are byte-identical again — the SSOT conflict is back");
});

test("exactly one copy declares itself the source of truth", () => {
  const declaresCanonical = SELF_DECLARATION.test(canonical());
  const declaresPointer = SELF_DECLARATION.test(pointer());
  assert.ok(declaresCanonical, "proof/SUPERSEDED.md does not declare itself the source of truth");
  assert.ok(!declaresPointer, "proof-galaxy/SUPERSEDED.md claims authority for itself — it must only point");
});

test("the pointer routes readers to the canonical path and the target resolves", () => {
  // The pointer's load-bearing act is the link; pin the exact relative path
  // so renaming the canonical file without updating the pointer goes red.
  assert.match(pointer(), /\.\.\/proof\/SUPERSEDED\.md/, "pointer no longer names ../proof/SUPERSEDED.md");
  const target = new URL("../proof/SUPERSEDED.md", pointerPath);
  assert.equal(target.href, canonicalPath.href, "pointer target resolves somewhere other than the canonical copy");
});

test("the statement's substance lives only in the canonical copy", () => {
  // Load-bearing facts of the record: the successor dashboard, the archive
  // path (kept as history, explicitly not a restore source), and the
  // cluster description of both exhibits. Duplication here is how the
  // original conflict was able to drift in two places at once.
  const p = pointer();
  assert.ok(!/8736/.test(p), "pointer repeats the dashboard address — keep facts in the canonical copy");
  assert.ok(!/backup-2026-04-26-viz/.test(p), "pointer repeats the archive record — keep facts in the canonical copy");
  const c = canonical();
  assert.match(c, /http:\/\/100\.92\.215\.26:8736/, "canonical copy lost the successor pointer");
  assert.match(c, /backup-2026-04-26-viz\/art-superseded/, "canonical copy lost the archive record");
  assert.match(c, /not a reachable restore source/, "canonical copy lost the correction that the archive path is history, not a restore source");
});
