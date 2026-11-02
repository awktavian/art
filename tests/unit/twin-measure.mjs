/**
 * Museum twin-family measurement helpers — the ONE implementation behind:
 *
 *   patent-portfolio/NEAR-DUPLICATE-TWINS.json    — the register (generated DATA)
 *   scripts/twin-register.mjs                     — regenerates / checks that register
 *   tests/unit/museum-twin-register.test.mjs      — the art-side tripwire
 *
 * Why one module and not three copies of `sha256`: this family's anchor pair,
 * `museum/navigation.js`, is declared in four places across two repos, and the recorded
 * failure mode of that arrangement is a declaration that rots silently while its guard
 * stays green — patent-portfolio/DEBT-museum-navigation-duplication.md residuals 1 and 2,
 * and the patents receipt's own warning that its leg 4 keeps matching a dead hex. A
 * measurement restated in a second implementation is how that happens. Numbers come from
 * here, or they are not in this tree.
 *
 * Node builtins only: `npm run test:unit` stays offline and credential-free, like the rest
 * of tests/unit/.
 */
import { createHash } from "node:crypto";
import { readFileSync, existsSync, writeFileSync, mkdirSync } from "node:fs";
import { execFileSync } from "node:child_process";
import { tmpdir } from "node:os";
import { join } from "node:path";

export { existsSync, readFileSync };

/** sha256 of a string or buffer, hex. */
export function sha256Hex(input) {
  return createHash("sha256").update(input).digest("hex");
}

/** git's own blob identity for these bytes: sha1("blob <len>\0" + bytes). */
export function gitBlobSha1(input) {
  const buf = Buffer.isBuffer(input) ? input : Buffer.from(input, "utf8");
  const h = createHash("sha1");
  h.update(`blob ${buf.length}\0`, "utf8");
  h.update(buf);
  return h.digest("hex");
}

export function readText(path) {
  return readFileSync(path, "utf8");
}

/**
 * Whole-file identity of text. `lines` counts newline characters — the figure `wc -l`
 * prints for these files, all of which end in exactly one final newline — so a number here
 * is comparable with the patents receipt and with the DEBT note without re-deriving it.
 */
export function fileStats(text) {
  const buf = Buffer.from(text, "utf8");
  return {
    bytes: buf.length,
    lines: text.split("\n").length - 1,
    blob: gitBlobSha1(buf),
    sha256: sha256Hex(buf),
  };
}

/**
 * Stats for a text SLICE. A body's "blob" is not a git object anybody can check out, so
 * this drops it rather than reporting a hash a reader could never resolve; identity for a
 * slice is sha256 + byte/line counts.
 */
export function sliceStats(text) {
  const buf = Buffer.from(text, "utf8");
  return {
    bytes: buf.length,
    lines: text.split("\n").length - 1,
    sha256: sha256Hex(buf),
  };
}

/**
 * Body under a run of leading `//` line-comments (and blank lines). This is the recipe the
 * four spec twins satisfy: art now carries a 5-line PROVENANCE header, patents a 3-line
 * one, and what is identical is everything below them. It is deliberately NOT a whole-file
 * claim — the whole files differ by the header, by design.
 */
export function belowCommentHeader(text) {
  const lines = text.split("\n");
  let i = 0;
  while (i < lines.length && (lines[i].startsWith("//") || lines[i].trim() === "")) i++;
  return lines.slice(i).join("\n");
}

/**
 * Body under the opening block doc comment, skipping any `//` pre-header first — byte-for-
 * byte the recipe of tests/unit/museum-navigation-mirror.test.mjs's `belowDocHeader` and of
 * the patents receipt's `tail -n +37` / `tail -n +51` (canonical body 1234 lines / 49768 B,
 * mirror body the same). The tripwire's consistency leg asserts that agreement instead of
 * trusting this sentence.
 */
export function belowDocHeader(text) {
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

/** Body dispatch. An unknown recipe name is a refusal, never a silent fallback. */
export function bodyOf(text, recipe) {
  if (recipe === "doc-header") return belowDocHeader(text);
  if (recipe === "comment-header") return belowCommentHeader(text);
  if (recipe === "whole") return text;
  throw new Error(`unknown body recipe ${JSON.stringify(recipe)}`);
}

/** Body identity for a pair, computed with that pair's declared recipe. */
export function bodyPair(artText, patText, recipe) {
  const a = bodyOf(artText, recipe);
  const p = bodyOf(patText, recipe);
  const as = sliceStats(a);
  const ps = sliceStats(p);
  return { recipe, art: as, patents: ps, identical: as.sha256 === ps.sha256 && as.bytes === ps.bytes };
}

/**
 * Divergence measured with the instrument the receipts already quote — `/usr/bin/diff` in
 * its normal format. Returns the hunk count and the one-sided line counts (art-only = `<`,
 * patents-only = `>`), plus a sha256 over each side's unique lines in order: the pin that
 * lets a future consolidation lane prove it is carrying the same divergent content this
 * register recorded, rather than a fresh derivation of it. Nothing here deletes anything;
 * these digests exist so the divergent bytes are declared instead of dropped.
 */
export function divergence(artText, patText, tag) {
  const dir = join(tmpdir(), "art-twin-register");
  mkdirSync(dir, { recursive: true });
  const fa = join(dir, `${tag}.a`);
  const fp = join(dir, `${tag}.p`);
  writeFileSync(fa, artText, "utf8");
  writeFileSync(fp, patText, "utf8");
  let out = "";
  try {
    out = execFileSync("/usr/bin/diff", [fa, fp], { encoding: "utf8" });
  } catch (err) {
    if (typeof err?.stdout !== "string") throw err; // rc 2 = real trouble; rc 1 = they differ
    out = err.stdout;
  }
  let hunks = 0;
  const artOnly = [];
  const patOnly = [];
  for (const line of out.split("\n")) {
    if (/^[0-9]+(,[0-9]+)?[acd][0-9]+(,[0-9]+)?$/.test(line)) {
      hunks += 1;
    } else if (line.startsWith("< ")) {
      artOnly.push(line.slice(2));
    } else if (line.startsWith("> ")) {
      patOnly.push(line.slice(2));
    }
  }
  return {
    instrument: "/usr/bin/diff normal format; hunk header lines counted, '<'/'>' lines pooled",
    hunks,
    art_only_lines: artOnly.length,
    patents_only_lines: patOnly.length,
    art_only_sha256: artOnly.length ? sha256Hex(artOnly.join("\n")) : null,
    patents_only_sha256: patOnly.length ? sha256Hex(patOnly.join("\n")) : null,
  };
}

/**
 * Which declaration markers a file actually carries in its leading comment run — measured,
 * not asserted, so "declared" in the register means "a grep of these bytes finds it" and a
 * silently deleted header goes red in the tripwire.
 *
 * Each row carries the matched LINE, not just the marker name, because the words are loose:
 * `museum/lighting.js` matches `names-mirror` on "DERIVED from art/lib/design-tokens.js
 * (single waddle mirror)" — a sentence about design tokens, not a twin declaration. Without
 * the line, a measured marker would read as a claim the file never made; with it, the register
 * is self-disclosing and the authored `declaration.status` beside it stays the narrower claim.
 */
export function headerMarkers(text) {
  const head = text.split("\n").slice(0, 40);
  const markers = [];
  const push = (marker, re) => {
    for (let i = 0; i < head.length; i++) {
      if (re.test(head[i])) {
        markers.push({ marker, line: i + 1, text: head[i].trim() });
        break;
      }
    }
  };
  push("NEAR-DUPLICATE-DECLARATION", /NEAR-DUPLICATE DECLARATION/);
  push("PROVENANCE", /^\s*\/\/\s*PROVENANCE/);
  push("names-canonical", /CANONICAL/i);
  push("names-mirror", /mirror/i);
  return markers;
}

/** Reads and parses the register. One parser, so no consumer re-derives its shape. */
export function readRegister(root) {
  const path = join(root, "patent-portfolio", "NEAR-DUPLICATE-TWINS.json");
  if (!existsSync(path)) throw new Error(`twins register absent at ${path}`);
  return JSON.parse(readFileSync(path, "utf8"));
}
