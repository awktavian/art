/**
 * Identity coherence gate — art-scope colony identity machine-pins.
 * Lane DICT-B, 2026-09-29.
 *
 * Transplants the semantics of kagami `packages/kagami/hal/creator_micro/
 * color-coherence.test.mjs` (which already gates creator_micro ↔ colonies.py):
 * parse the authority from source, assert mirror == producer, SKIP HONESTLY
 * when the authority is absent (UNMEASURED ≠ drift ≠ pass), and refuse retired
 * surfaces. Not a new gate class — the same pattern applied to the two art
 * surfaces that were pinned only in prose.
 *
 * What is pinned:
 *   lib/design-tokens.js  ↔ waddle master colors.colony + colors.highContrast
 *                         ↔ genome colonies.py "## Fano Lines" (name→line, and
 *                           point indices via the genome's octonion subscripts)
 *   lib/kagami-voices.js  ↔ genome Fano supports (header, both e-notation and
 *                           named form), genome octonion basis fields,
 *                           AGENTS.md Colony→Voice table (persona + Cluedo colors)
 *   fork-block rule       : a COLONY_COLORS object literal may exist only in
 *                           lib/design-tokens.js; swept files must import it
 *   retired-surface rule  : lib/kagami-visuals.js stays gone; voices carries no
 *                           `efe:` / `leitmotif:` field declarations
 *   steamboat-willie      : PROJECT_VOICES entry extends forge, voice=echo
 *   derived CSS           : lib/colony-tokens.css passes the generator's --check
 *
 * A single colony hex inside a purpose-built table (SEMANTIC_COLORS, a wing
 * accent, PRIORITY_COLORS) is a vocabulary MEMBER, not a fork — membership is
 * not uniqueness, so this gate does not scan for hex occurrences; it scans for
 * re-declarations of the mapping itself.
 *
 * Authority paths, overridable for sandboxed/known-positive runs:
 *   KAGAMI_COLONIES_PY  default /Users/schizodactyl/Projects/kagami/packages/kagami/core/prompts/colonies.py
 *   WADDLE_TOKENS_JSON  default /Users/schizodactyl/projects/awkronos-waddle/packages/design-tokens/tokens.json
 */
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync, existsSync } from "node:fs";
import { readdirSync, statSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { execFileSync } from "node:child_process";

import { loadBrowserLib } from "./load-browser-lib.mjs";

const REPO = resolve(dirname(fileURLToPath(import.meta.url)), "..", "..");
const DESIGN_TOKENS = join(REPO, "lib", "design-tokens.js");

const COLONIES_PY =
  process.env.KAGAMI_COLONIES_PY ||
  "/Users/schizodactyl/Projects/kagami/packages/kagami/core/prompts/colonies.py";
const WADDLE_TOKENS =
  process.env.WADDLE_TOKENS_JSON ||
  "/Users/schizodactyl/projects/awkronos-waddle/packages/design-tokens/tokens.json";

function readAuthority(path, t) {
  if (!existsSync(path)) {
    t.skip(`authority absent: ${path} — UNMEASURED, not drift`);
    return null;
  }
  return readFileSync(path, "utf8");
}

/**
 * Parse the genome: colonies.py is the SSOT for colony identity. Returns
 * { byName: { spark: {color, octonion, idx} }, lines: [ [name,name,name], … ] }
 * or null when unparseable shape (caller must fail loudly, not silently).
 */
export function parseGenome(pyText) {
  // Precedent regex from creator_micro color-coherence.test.mjs, extended with
  // octonion (each ColonyPrompt(...) block carries name, color, octonion).
  const re =
    /ColonyPrompt\(\s*name="(\w+)",[\s\S]{0,400}?color="(#[0-9a-f]{6})",[\s\S]{0,200}?octonion="(e[_₀₁₂₃₄₅₆₇₈₉])"/g;
  const SUBS = { "₀": 0, "₁": 1, "₂": 2, "₃": 3, "₄": 4, "₅": 5, "₆": 6, "₇": 7, "₈": 8, "₉": 9 };
  const byName = {};
  let m;
  while ((m = re.exec(pyText))) {
    const [, name, color, oct] = m;
    const digit = [...oct].map((c) => SUBS[c]).filter((d) => d !== undefined);
    byName[name] = { color, octonion: oct, idx: digit[0] - 1 };
  }
  // Fano lines: inside each `## Fano Lines` block, lines `A × B = C`.
  const lines = [];
  const seen = new Set();
  const lineRe = /^\s*([A-Za-z]+) × ([A-Za-z]+) = ([A-Za-z]+)\s*$/;
  let inBlock = false;
  for (const raw of pyText.split("\n")) {
    const line = raw.trimEnd();
    if (/^\s*## Fano Lines\s*$/.test(line)) { inBlock = true; continue; }
    if (inBlock && /^\s*##/.test(line)) { inBlock = false; }
    if (!inBlock) continue;
    const lm = lineRe.exec(line);
    if (!lm) continue;
    // Normalize to the lowercase colony keys used by byName (genome writes
    // display names "Spark"; registry keys are "spark").
    const trip = [lm[1], lm[2], lm[3]].map((n) => n.toLowerCase());
    const key = [...trip].sort().join("|");
    if (!seen.has(key)) { seen.add(key); lines.push(trip); }
  }
  return { byName, lines };
}

// ── T1: the genome itself — seven colonies, seven true Fano lines ──────────
test("genome: colonies.py declares 7 colonies on 7 Fano lines (self-consistency)", (t) => {
  const text = readAuthority(COLONIES_PY, t);
  if (!text) return;
  const g = parseGenome(text);
  assert.ok(Object.keys(g.byName).length === 7, `expected 7 ColonyPrompt rows, got ${Object.keys(g.byName).length}`);
  assert.equal(g.lines.length, 7, `expected 7 distinct Fano lines, got ${g.lines.length}`);

  const octs = Object.values(g.byName).map((c) => c.octonion);
  assert.equal(new Set(octs).size, 7, "octonion subscripts must be unique per colony");
  const idxs = Object.values(g.byName).map((c) => c.idx);
  assert.deepEqual([...idxs].sort(), [0, 1, 2, 3, 4, 5, 6], "octonion subscripts e₁..e₇ must cover 0..6 once");

  // Fano axioms on the name level: 7 points, each on exactly 3 lines;
  // each pair of lines meets in exactly one point; each pair of points lies
  // on exactly one line. If this ever fails, the "one geometry" premise of the
  // genome is broken upstream — nothing downstream should paper over it.
  const points = Object.keys(g.byName);
  for (const p of points) {
    const n = g.lines.filter((L) => L.includes(p)).length;
    assert.equal(n, 3, `point ${p} lies on ${n} lines, expected 3`);
  }
  for (let i = 0; i < 7; i++)
    for (let j = i + 1; j < 7; j++) {
      const inter = g.lines[i].filter((x) => g.lines[j].includes(x));
      assert.equal(inter.length, 1, `lines ${g.lines[i]} ∩ ${g.lines[j]} = ${inter}, expected exactly 1 point`);
    }
  for (let a = 0; a < points.length; a++)
    for (let b = a + 1; b < points.length; b++) {
      const through = g.lines.filter((L) => L.includes(points[a]) && L.includes(points[b])).length;
      assert.equal(through, 1, `pair ${points[a]}/${points[b]} on ${through} lines, expected exactly 1`);
    }
});

// ── T2: design-tokens FANO_LINES == genome lines (index convention kept) ───
test("design-tokens FANO_LINES are the genome's 7 lines via the genome's own point indices", async (t) => {
  const text = readAuthority(COLONIES_PY, t);
  if (!text) return;
  const g = parseGenome(text);
  const dt = await import(DESIGN_TOKENS);

  // The index convention is NOT assumed to be identity: it is the genome's
  // octonion subscript (e₁ → 0-based 0 … e₇ → 6), cross-checked against
  // COLONY_FANO_MAP so the mapping itself cannot silently drift.
  for (const [name, c] of Object.entries(g.byName)) {
    assert.equal(dt.COLONY_FANO_MAP[name.toLowerCase()], c.idx,
      `COLONY_FANO_MAP[${name}] = ${dt.COLONY_FANO_MAP[name.toLowerCase()]} but genome octonion ${c.octonion} ⇒ ${c.idx}`);
  }
  assert.deepEqual([...dt.COLONY_ORDER].sort(), Object.keys(g.byName).map((n) => n.toLowerCase()).sort(),
    "COLONY_ORDER must be exactly the genome's colonies");

  const asIdxTri = (L) => L.map((n) => g.byName[n].idx).sort((a, b) => a - b);
  const genomeSet = g.lines.map(asIdxTri).map((L) => L.join(",")).sort();
  const artSet = dt.FANO_LINES.map((L) => [...L].sort((a, b) => a - b).join(",")).sort();
  assert.deepEqual(artSet, genomeSet,
    `art FANO_LINES (0-based) != genome lines mapped through octonion indices\n genome: ${genomeSet.join(" ; ")}\n art:    ${artSet.join(" ; ")}`);
});

// ── T3: FANO_POINTS draws those lines: 6 straight + the circle ─────────────
test("design-tokens FANO_POINTS render the genome lines (six collinear triples + one circle)", async (t) => {
  const dt = await import(DESIGN_TOKENS);
  const P = dt.FANO_POINTS;
  assert.equal(P.length, 7, "7 Fano points");
  assert.equal(new Set(P.map(String)).size, 7, "points must be distinct");
  const collinear = ([a, b, c]) =>
    Math.abs((P[b][0] - P[a][0]) * (P[c][1] - P[a][1]) - (P[c][0] - P[a][0]) * (P[b][1] - P[a][1])) < 1e-9;
  const circleLine = [1, 3, 5]; // Forge×Nexus=Grove — the diagram's circle
  let nonCollinear = 0;
  for (const L of dt.FANO_LINES) {
    if (collinear(L)) continue;
    nonCollinear++;
    assert.deepEqual([...L].sort((a, b) => a - b), circleLine,
      `only the circle line {1,3,5} may be non-collinear, got {${L}}`);
  }
  assert.equal(nonCollinear, 1, "exactly one line must be drawn as the circle");
});

// ── T4: design-tokens colors == waddle master (the old prose pin) ──────────
test("design-tokens COLONY_COLORS + HIGH_CONTRAST match waddle tokens.json field by field", async (t) => {
  const text = readAuthority(WADDLE_TOKENS, t);
  if (!text) return;
  const master = JSON.parse(text);
  const dt = await import(DESIGN_TOKENS);
  for (const colony of dt.COLONY_ORDER) {
    const w = master.colors.colony[colony];
    assert.ok(w, `waddle colors.colony.${colony} missing`);
    const a = dt.COLONY_COLORS[colony];
    assert.equal(a.hex.toLowerCase(), w.value.toLowerCase(), `${colony} hex: art ${a.hex} vs master ${w.value}`);
    assert.equal(a.num, parseInt(w.value.slice(1), 16), `${colony} numeric form disagrees with hex`);
    assert.deepEqual([...a.rgb], w.rgb, `${colony} rgb`);
    assert.equal(a.basis, w.basis, `${colony} octonion basis (ASCII form)`);
    assert.equal(a.name, w.name, `${colony} role name`);
    const hc = dt.HIGH_CONTRAST.colony[colony];
    assert.equal(hc, parseInt(master.colors.highContrast.colony[colony].slice(1), 16),
      `${colony} high-contrast: art 0x${hc.toString(16)} vs master ${master.colors.highContrast.colony[colony]}`);
  }
});

// ── T5: voices header states the genome's supports (both notations) ───────
test("kagami-voices header Fano table equals the genome lines (e-notation and named)", (t) => {
  const text = readAuthority(COLONIES_PY, t);
  if (!text) return;
  const g = parseGenome(text);
  const voices = readFileSync(join(REPO, "lib", "kagami-voices.js"), "utf8");
  const header = voices.split("*/")[0];

  // e-notation: e₂·e₄=e₆ etc. → name triples via genome octonions.
  const octByName = {};
  for (const [n, c] of Object.entries(g.byName)) octByName[c.octonion] = n.toLowerCase();
  const eqRe = /(e[_₀-₉])·(e[_₀-₉])=(e[_₀-₉])/g;
  const eqLines = new Set();
  let m;
  while ((m = eqRe.exec(header))) {
    const trip = [octByName[m[1]], octByName[m[2]], octByName[m[3]]];
    assert.ok(trip.every(Boolean), `unknown octonion in header equation ${m[0]}`);
    eqLines.add([...trip].sort().join("|"));
  }
  // Named form: Spark×Forge=Flow.
  const namedRe = /\b(Spark|Forge|Flow|Nexus|Beacon|Grove|Crystal)×(Spark|Forge|Flow|Nexus|Beacon|Grove|Crystal)=(Spark|Forge|Flow|Nexus|Beacon|Grove|Crystal)\b/g;
  const namedLines = new Set();
  while ((m = namedRe.exec(header))) {
    namedLines.add([m[1].toLowerCase(), m[2].toLowerCase(), m[3].toLowerCase()].sort().join("|"));
  }
  const genomeSet = new Set(g.lines.map((L) => L.map((n) => n.toLowerCase()).sort().join("|")));
  assert.equal(eqLines.size, 7, `header e-notation has ${eqLines.size} lines, expected 7`);
  assert.deepEqual([...eqLines].sort(), [...genomeSet].sort(),
    "header e-notation lines != genome supports");
  assert.deepEqual([...namedLines].sort(), [...genomeSet].sort(),
    "header named lines != genome supports");
});

// ── T6: voices basis fields == genome octonion fields (Unicode kept) ──────
test("kagami-voices basis fields equal the genome octonion fields", (t) => {
  const text = readAuthority(COLONIES_PY, t);
  if (!text) return;
  const g = parseGenome(text);
  const { getColony } = loadBrowserLib("lib/kagami-voices.js");
  for (const [name, c] of Object.entries(g.byName)) {
    const v = getColony(name);
    assert.ok(v, `voices has no entry for genome colony ${name}`);
    assert.equal(v.basis, c.octonion, `${name}: voices basis ${v.basis} vs genome octonion ${c.octonion}`);
    assert.equal(v.colony, name[0].toUpperCase() + name.slice(1), `${name}: voices.colony display label`);
  }
});

// ── T7: voices persona table == AGENTS.md Colony→Voice mapping ────────────
test("kagami-voices entries equal the AGENTS.md Colony→Voice table (persona + Cluedo colors)", () => {
  const agents = readFileSync(join(REPO, "AGENTS.md"), "utf8");
  const section = agents.split("## Colony→Voice Mapping")[1];
  assert.ok(section, "AGENTS.md Colony→Voice Mapping section missing");
  const rowRe = /^\| (Spark|Forge|Flow|Nexus|Beacon|Grove|Crystal|Kagami) \| ([^|]+) \| ([^|]+) \| ([^|]+) \| (#[0-9a-f]{6}) \|$/gm;
  const { getColony } = loadBrowserLib("lib/kagami-voices.js");
  let rows = 0, m;
  while ((m = rowRe.exec(section))) {
    const [, name, character, catastrophe, voice, color] = m;
    const v = getColony(name);
    assert.ok(v, `voices missing ${name} (documented in AGENTS.md)`);
    rows++;
    assert.equal(v.character, character.trim(), `${name} character`);
    assert.equal(v.catastrophe, catastrophe.trim(), `${name} catastrophe`);
    assert.equal(v.voice, voice.trim(), `${name} voice`);
    assert.equal(v.color.toLowerCase(), color.toLowerCase(), `${name} color`);
  }
  assert.equal(rows, 8, `parsed ${rows} AGENTS.md voice rows, expected 8 (7 colonies + orchestrator)`);
});

// ── T8: no fork re-declares the colony color mapping ──────────────────────
test("only lib/design-tokens.js may declare a COLONY_COLORS object literal; swept files import it", () => {
  const SKIP_DIRS = new Set(["node_modules", ".git", "medverify"]);
  const jsFiles = [];
  (function walk(dir) {
    for (const e of readdirSync(dir)) {
      if (SKIP_DIRS.has(e)) continue;
      const p = join(dir, e);
      if (statSync(p).isDirectory()) walk(p);
      else if (e.endsWith(".js")) jsFiles.push(p);
    }
  })(REPO);

  const binding = /(?:const|let|var)\s+COLONY_COLORS\s*=\s*\{/;
  const offenders = jsFiles
    .filter((p) => binding.test(readFileSync(p, "utf8")))
    .map((p) => resolve(REPO, p).slice(REPO.length + 1))
    .filter((rel) => rel !== "lib/design-tokens.js");
  assert.deepEqual(offenders, [],
    "COLONY_COLORS literal re-declared outside lib/design-tokens.js — import from there instead (see patent-portfolio/DEBT-design-tokens.md)");

  // The swept fork files must go through the token owner.
  const swept = [
    "patent-portfolio/components/plaque.js",
    "patent-portfolio/lib/materials.js",
    "patent-portfolio/lib/typography.js",
    "patent-portfolio/museum/lighting.js",
    "patent-portfolio/museum/wayfinding.js",
    "patent-portfolio/artworks/artwork-templates.js",
    "patent-portfolio/artworks/p2-artworks.js",
    "patent-portfolio/artworks/p3-artworks.js",
  ];
  for (const rel of swept) {
    const src = readFileSync(join(REPO, rel), "utf8");
    assert.match(src, /from\s+["'][^"']*lib\/design-tokens\.js["']/,
      `${rel} must import the colony colors from lib/design-tokens.js`);
  }
});

// ── T10: steamboat-willie project voice is a Forge derivation ─────────────
// DICT-C handoff 2026-09-29: the page already sends project='steamboat-willie'
// (steamboat-willie.html:276). The registry entry must extend forge and carry
// forge's voice, so the flip to buildVoiceConfig('steamboat-willie') cannot
// silently re-borrow another colony. Deliberately NOT byte-pinned against the
// page's WILLIE_PROMPT: once the flip lands the page-local literal retires,
// and a gate reading a surface it may never see again would rot on success.
test("PROJECT_VOICES['steamboat-willie'] extends forge and uses forge's voice", () => {
  const { PROJECT_VOICES, KAGAMI_VOICES } = loadBrowserLib("lib/kagami-voices.js");
  const w = PROJECT_VOICES["steamboat-willie"];
  assert.ok(w, "steamboat-willie registry entry missing (DICT-C handoff 2026-09-29)");
  assert.equal(w.extends, "forge", "steamboat-willie must extend the genome's forge colony");
  assert.equal(w.voice, KAGAMI_VOICES.forge.voice,
    `voice ${w.voice} != forge voice ${KAGAMI_VOICES.forge.voice}`);
  assert.match(w.additionalInstructions, /Steamboat Willie/, "entry must carry the Willie persona text");
});

// ── T11: derived CSS stays current with the token source ──────────────────
test("lib/colony-tokens.css passes its generator's --check drift gate", () => {
  let out;
  try {
    out = execFileSync(process.execPath, [join(REPO, "scripts", "generate-colony-css.mjs"), "--check"],
      { encoding: "utf8" });
  } catch (e) {
    assert.fail("colony-tokens.css is STALE: " + (e.stderr || e.stdout || e.message)
      + "\nfix: node scripts/generate-colony-css.mjs");
  }
  assert.match(out, /OK: lib\/colony-tokens\.css is current/);
});

// ── T9: retired surfaces stay retired ──────────────────────────────────────
test("retired surfaces do not return", () => {
  const gone = join(REPO, "lib", "kagami-visuals.js");
  assert.ok(!existsSync(gone),
    "lib/kagami-visuals.js is back — it had zero importers and was deleted 2026-09-29 (lane DICT-B); if a second visuals engine is genuinely wanted, re-introduce it with consumers, not as a resurrection");

  const voices = readFileSync(join(REPO, "lib", "kagami-voices.js"), "utf8");
  // Field-declarations only — a naive substring check hits "REFERENCE" (efe).
  assert.ok(!/(^|\s)(efe|leitmotif)\s*:/m.test(voices),
    "voices carries efe:/leitmotif: fields again — removed 2026-09-29 with zero readers (grep art + kagami before re-adding; the creator_micro EFE data lives in the genome, not here)");
});
