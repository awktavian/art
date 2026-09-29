#!/usr/bin/env node
/**
 * Generate lib/colony-tokens.css from lib/design-tokens.js.
 *
 * One-way derivation: design-tokens.js is the SSOT (and is itself machine-pinned
 * to the waddle master + the genome by tests/unit/identity-coherence.test.mjs).
 * CSS pages consume the derived custom properties instead of re-typing hexes;
 * DICT-C measured ~50 inline hex declaration sites that become mechanical once
 * this file lands.
 *
 * Interface precedent: kagami `packages/kagami-design-tokens/generate.py`
 * `--check` ("Drift gate: regenerate in-memory and diff against generated
 * output; exit 1 on any mismatch"). No timestamps in the output: the only
 * inputs are the token values and the sha256 of the source file, so the result
 * is byte-stable and --check is exact.
 *
 *   node scripts/generate-colony-css.mjs            # write (atomic)
 *   node scripts/generate-colony-css.mjs --check    # drift gate, no writes
 *
 * Writes are transactional (temp file + rename), mirroring the precedent's
 * mkstemp/os.replace discipline.
 */
import { readFileSync, writeFileSync, renameSync, existsSync } from "node:fs";
import { createHash } from "node:crypto";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

import {
  COLONY_ORDER, COLONY_COLORS, HIGH_CONTRAST,
  VOID_COLORS, STATUS_COLORS, SAFETY_COLORS, TEXT_COLORS,
} from "../lib/design-tokens.js";

const REPO = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const SRC = join(REPO, "lib", "design-tokens.js");
const OUT = join(REPO, "lib", "colony-tokens.css");

const hex = (n) => "#" + n.toString(16).padStart(6, "0").toUpperCase();
const camel = (s) => s.replace(/[A-Z]/g, (c) => "-" + c.toLowerCase());

function render() {
  const srcSha = createHash("sha256").update(readFileSync(SRC)).digest("hex");
  const L = [];
  L.push("/* GENERATED — DO NOT EDIT.");
  L.push(` * Derived from lib/design-tokens.js (sha256 ${srcSha})`);
  L.push(" * Regenerate:  node scripts/generate-colony-css.mjs");
  L.push(" * Drift gate:  node scripts/generate-colony-css.mjs --check  (exit 1 = stale)");
  L.push(" * Machine-checked by tests/unit/identity-coherence.test.mjs via --check.");
  L.push(" */");
  L.push(":root {");

  L.push("  /* Colony palette — Fano points, genome octonion order */");
  for (const c of COLONY_ORDER) {
    const t = COLONY_COLORS[c];
    L.push(`  --colony-${c}: ${t.hex.toUpperCase()};  /* basis ${t.basis} · ${t.name} */`);
    L.push(`  --colony-${c}-rgb: ${t.rgb.join(", ")};`);
    L.push(`  --colony-${c}-hc: ${hex(HIGH_CONTRAST.colony[c])};`);
  }

  L.push("");
  L.push("  /* High-contrast overrides for the base surfaces */");
  L.push(`  --bg-hc: ${hex(HIGH_CONTRAST.background)};`);
  L.push(`  --surface-hc: ${hex(HIGH_CONTRAST.surface)};`);
  L.push(`  --text-hc: ${hex(HIGH_CONTRAST.text)};`);
  L.push(`  --text-secondary-hc: ${hex(HIGH_CONTRAST.textSecondary)};`);
  L.push(`  --accent-hc: ${hex(HIGH_CONTRAST.accent)};`);
  L.push(`  --border-hc: ${hex(HIGH_CONTRAST.border)};`);

  L.push("");
  L.push("  /* Dark void palette */");
  for (const [k, v] of Object.entries(VOID_COLORS)) L.push(`  --void-${camel(k)}: ${hex(v)};`);

  L.push("");
  L.push("  /* Status + safety (h(x) band) */");
  for (const [k, v] of Object.entries(STATUS_COLORS)) L.push(`  --status-${camel(k)}: ${hex(v)};`);
  for (const [k, v] of Object.entries(SAFETY_COLORS)) L.push(`  --safety-${camel(k)}: ${hex(v)};  /* ${k === "ok" ? "h(x) >= 0.5" : k === "caution" ? "0 <= h(x) < 0.5" : "h(x) < 0"} */`);

  L.push("");
  L.push("  /* Text ramp */");
  for (const [k, v] of Object.entries(TEXT_COLORS)) L.push(`  --text-${camel(k)}: ${hex(v)};`);

  L.push("}");
  L.push("");
  return L.join("\n");
}

const want = render();

if (process.argv.includes("--check")) {
  if (!existsSync(OUT)) {
    console.error(`STALE: ${OUT} missing — run node scripts/generate-colony-css.mjs`);
    process.exit(1);
  }
  const have = readFileSync(OUT, "utf8");
  if (have !== want) {
    console.error(`STALE: ${OUT} does not match a fresh derivation from lib/design-tokens.js`);
    const a = have.split("\n"), b = want.split("\n");
    for (let i = 0; i < Math.max(a.length, b.length); i++) {
      if (a[i] !== b[i]) { console.error(`  first diff line ${i + 1}:\n    on disk: ${a[i]}\n    derived: ${b[i]}`); break; }
    }
    process.exit(1);
  }
  console.log("OK: lib/colony-tokens.css is current with lib/design-tokens.js");
  process.exit(0);
}

const tmp = OUT + ".tmp-" + process.pid;
writeFileSync(tmp, want);
renameSync(tmp, OUT);
console.log(`wrote ${OUT} (${Buffer.byteLength(want)} bytes)`);
