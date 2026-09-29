/**
 * Persona integrity gate — static, offline, no browser, no server.
 * =================================================================
 * WHY: realtime-proxy/server.js (lines 227-246) closes every WebSocket that
 * omits either the `project` or `colony` query parameter with 4400, and the
 * browser canary's page list drifted behind the actual set of voice-connecting
 * pages (steamboat-willie connected with no `colony` and a hardcoded
 * `voice:'echo'`, invisible to the gate). Source: the GROVE-DICT baseline,
 * measured 2026-09-29.
 *
 * This gate scans the PAGES (root HTML and directory index HTML files, plus the project's
 * own sibling wiring JS) for realtime voice call sites and asserts, per site:
 *
 *   1. every resolveRealtimeEndpoint('voice', …) call carries BOTH a
 *      `project:` and a `colony:` key in its params object;
 *   2. every `new RealtimeVoice({ … })` takes its voice from the dictionary
 *      (an expression like `config.voice` / `persona.voice`), never a page-side
 *      string literal;
 *   3. every VoiceOverlay.init / direct project label that claims a
 *      PROJECT_VOICES key resolves a real persona via buildVoiceConfig;
 *   4. every wiring file references the shared dictionary surface
 *      (buildVoiceConfig / KAGAMI_VOICES / PROJECT_VOICES) — a page talking to
 *      the proxy without any dictionary linkage is the bypass this gate kills;
 *   5. the dictionary itself: all 6 PROJECT_VOICES keys (post-DICT-B: dead
 *      pair deleted, steamboat-willie added) resolve a persona and every
 *      persona voice is one of the KAGAMI_VOICES colony voices (6/6),
 *      and all 8 KAGAMI_VOICES entries carry colony + voice.
 *
 * The checkers run against embedded fixtures too (rule 6): a known-positive
 * broken snippet must produce violations and a repaired snippet must be clean,
 * so a regex that silently stopped matching cannot turn this gate green by
 * going blind. `node --test`, offline, zero credentials.
 */
import { test } from "node:test";
import assert from "node:assert/strict";
import { existsSync, readFileSync, readdirSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

import { loadBrowserLib } from "./load-browser-lib.mjs";

const REPO = resolve(dirname(fileURLToPath(import.meta.url)), "..", "..");

const SKIP_DIRS = new Set([
  "node_modules",
  ".git",
  "lib", // lib/** is the DICT-B-owned library surface, not pages
  "tests",
  "scripts",
  "medverify", // separate repository, ignored here
]);

// ── extraction helpers ────────────────────────────────────────────────────

/** Balanced `{…}` block whose opening brace is at or after `startIndex`. */
function braceBlock(text, startIndex) {
  const open = text.indexOf("{", startIndex);
  if (open === -1) return null;
  let depth = 0;
  let inStr = null;
  for (let i = open; i < text.length; i++) {
    const ch = text[i];
    if (inStr) {
      if (ch === "\\") i++;
      else if (ch === inStr) inStr = null;
      continue;
    }
    if (ch === "'" || ch === '"' || ch === "`") inStr = ch;
    else if (ch === "{") depth++;
    else if (ch === "}") {
      depth--;
      if (depth === 0) return text.slice(open, i + 1);
    }
  }
  return null;
}

/** All option-object literals passed to `name(...)`, as source text. */
function callOptionObjects(text, name, preludeRe) {
  const out = [];
  const re = new RegExp(name, "g");
  let m;
  while ((m = re.exec(text)) !== null) {
    const tail = text.slice(m.index, m.index + 200);
    if (preludeRe && !preludeRe.test(tail)) continue;
    const block = braceBlock(text, m.index);
    if (block) out.push({ block, index: m.index });
  }
  return out;
}

function lineOf(text, index) {
  return text.slice(0, index).split("\n").length;
}

// ── the rules (shared by page scan and known-positive fixtures) ───────────

/**
 * @returns violation strings for one wiring file's source text.
 * @param resolveProject  key => persona|null (buildVoiceConfig)
 */
export function scanWiringFile(source, { resolveProject, fileName }) {
  const violations = [];
  const tag = (idx) => `${fileName}:${lineOf(source, idx)}`;

  const hasVoiceCall = /resolveRealtimeEndpoint\(\s*['"]voice['"]/.test(source);
  const hasOverlayInit = /VoiceOverlay\.init\s*\(/.test(source);
  const hasRealtimeVoice = /new\s+RealtimeVoice\s*\(/.test(source);

  // Rule 4: a page wiring the proxy by hand (no VoiceOverlay) must still link
  // to the shared dictionary — VoiceOverlay.init is dictionary-bound by
  // construction (voice-overlay.js throws without a persona).
  if ((hasVoiceCall || hasRealtimeVoice) && !hasOverlayInit) {
    if (!/\b(buildVoiceConfig|KAGAMI_VOICES|PROJECT_VOICES)\b/.test(source)) {
      violations.push(
        `${tag(0)}: hand-wired voice page references neither buildVoiceConfig ` +
          `nor KAGAMI_VOICES/PROJECT_VOICES — it bypasses the persona dictionary.`,
      );
    }
  }

  // Rule 1: direct voice endpoint calls must carry project AND colony.
  for (const { block, index } of callOptionObjects(
    source,
    "resolveRealtimeEndpoint\\(",
    /['"]voice['"]/,
  )) {
    const paramsIdx = block.search(/params\s*:/);
    const params = paramsIdx === -1 ? null : braceBlock(block, paramsIdx);
    const missing = [];
    if (!params || !/project\s*:/.test(params)) missing.push("project");
    if (!params || !/colony\s*:/.test(params)) missing.push("colony");
    if (missing.length) {
      violations.push(
        `${tag(index)}: resolveRealtimeEndpoint('voice') params omit ${missing.join(" + ")} ` +
          `— realtime-proxy/server.js closes such sessions with 4400.`,
      );
    }
  }

  // Rule 2: RealtimeVoice options may not hardcode a voice string literal.
  for (const { block, index } of callOptionObjects(source, "new\\s+RealtimeVoice\\s*\\(")) {
    const voiceLit = block.match(/\bvoice\s*:\s*(['"`])([^'"`]*)\1/);
    if (voiceLit) {
      violations.push(
        `${tag(index)}: new RealtimeVoice sets voice:'${voiceLit[2]}' as a page-side ` +
          `literal — route it through the shared dictionary (config.voice / ` +
          `KAGAMI_VOICES[key].voice) instead of a string the gate cannot check.`,
      );
    }
  }

  // Rule 3: overlay project labels must resolve a persona.
  for (const { block, index } of callOptionObjects(source, "VoiceOverlay\\.init\\s*\\(")) {
    for (const pm of block.matchAll(/\bproject\s*:\s*(['"])([\w-]+)\1/g)) {
      if (!resolveProject(pm[2])) {
        violations.push(
          `${tag(index)}: VoiceOverlay.init project:'${pm[2]}' has no PROJECT_VOICES ` +
            `persona — voice-overlay.js refuses to substitute a generic assistant, ` +
            `so this page fails at connect time.`,
        );
      }
    }
  }

  return violations;
}

// ── page discovery ─────────────────────────────────────────────────────────

function scanTargets() {
  const targets = []; // { file (repo-relative), source }
  const entries = readdirSync(REPO, { withFileTypes: true });
  for (const e of entries) {
    if (SKIP_DIRS.has(e.name)) continue;
    if (e.isFile() && e.name.endsWith(".html")) {
      targets.push(e.name);
    } else if (e.isDirectory()) {
      if (existsSync(join(REPO, e.name, "index.html"))) targets.push(`${e.name}/index.html`);
      // project-owned wiring JS at depth 1 (e.g. robo-skip/voice-coach.js)
      for (const f of readdirSync(join(REPO, e.name), { withFileTypes: true })) {
        if (f.isFile() && f.name.endsWith(".js")) targets.push(`${e.name}/${f.name}`);
      }
    }
  }
  return targets.map((file) => ({ file, source: readFileSync(join(REPO, file), "utf8") }));
}

const VOICE_MARKERS = /resolveRealtimeEndpoint\(\s*['"]voice['"]|VoiceOverlay\.init\s*\(|new\s+RealtimeVoice\s*\(/;

// ── dictionary under test ──────────────────────────────────────────────────

const voiceLib = loadBrowserLib("lib/kagami-voices.js");
const { KAGAMI_VOICES, PROJECT_VOICES, buildVoiceConfig } = voiceLib;

// ── tests ──────────────────────────────────────────────────────────────────

test("voice-connecting pages pass project AND colony and never hardcode a voice literal", () => {
  const offenders = [];
  let connecting = 0;
  for (const { file, source } of scanTargets()) {
    if (!VOICE_MARKERS.test(source)) continue;
    connecting++;
    const v = scanWiringFile(source, {
      fileName: file,
      resolveProject: (k) => (buildVoiceConfig ? buildVoiceConfig(k) : null),
    });
    offenders.push(...v);
  }
  assert.deepEqual(offenders, [], `persona-integrity violations:\n${offenders.join("\n")}`);
  // A scan that found no voice pages is a broken scan, not a clean estate.
  assert.ok(
    connecting >= 6,
    `expected ≥6 voice-connecting pages (baseline 2026-09-29: clue, skippy, collapse, orb, ` +
      `robo-skip, steamboat-willie); scan found ${connecting} — the marker regex or the ` +
      `file discovery is blind.`,
  );
});

test("all 6 PROJECT_VOICES keys resolve a persona whose voice is a colony voice (6/6)", () => {
  const colonyVoices = new Set(Object.values(KAGAMI_VOICES).map((c) => c.voice));
  for (const key of Object.keys(PROJECT_VOICES)) {
    const persona = buildVoiceConfig(key);
    assert.ok(persona, `PROJECT_VOICES['${key}'] → buildVoiceConfig returned null`);
    assert.ok(persona.voice, `PROJECT_VOICES['${key}'] has no voice`);
    assert.ok(persona.instructions, `PROJECT_VOICES['${key}'] has no instructions`);
    assert.ok(
      colonyVoices.has(persona.voice),
      `PROJECT_VOICES['${key}'].voice='${persona.voice}' is not a KAGAMI_VOICES colony voice`,
    );
  }
  // 6 = the pre-DICT-B seven minus the deleted dead pair (catastrophes,
  // minimize-surprise) plus 'steamboat-willie' (extends forge, voice 'echo').
  // Each key is a PROJECT persona that extends a colony; the loop's per-key
  // assertions are the real gate; the count only catches silent additions.
  assert.equal(Object.keys(PROJECT_VOICES).length, 6, "PROJECT_VOICES key count changed — update the gate brief");
});

test("all 8 KAGAMI_VOICES entries carry colony + voice identity fields", () => {
  for (const [key, c] of Object.entries(KAGAMI_VOICES)) {
    assert.ok(c.colony, `KAGAMI_VOICES['${key}'] missing colony`);
    assert.ok(c.voice, `KAGAMI_VOICES['${key}'] missing voice`);
    assert.ok(c.personality, `KAGAMI_VOICES['${key}'] missing personality`);
  }
  assert.equal(Object.keys(KAGAMI_VOICES).length, 8, "KAGAMI_VOICES entry count changed");
});

test("the gate fires on a page omitting colony or hardcoding voice (known-positive)", () => {
  const broken = [
    `const PROXY_URL = resolveRealtimeEndpoint('voice', { params: { project: 'demo' } });`,
    `const v = new RealtimeVoice({ proxyUrl: PROXY_URL, voice: 'echo', instructions: 'x' });`,
  ].join("\n");
  const v1 = scanWiringFile(broken, { fileName: "fixture-broken.html", resolveProject: () => null });
  assert.ok(v1.some((m) => /omit colony/.test(m)), "known-positive: missing colony must fire");
  assert.ok(v1.some((m) => /voice:'echo'/.test(m)), "known-positive: hardcoded voice must fire");
  assert.ok(v1.some((m) => /bypasses the persona dictionary/.test(m)), "known-positive: no dictionary reference must fire");

  const repaired = [
    `const persona = window.KAGAMI_VOICES['forge'];`,
    `const PROXY_URL = resolveRealtimeEndpoint('voice', {`,
    `  params: { project: 'demo', colony: persona.colony.toLowerCase() },`,
    `});`,
    `const v = new RealtimeVoice({ proxyUrl: PROXY_URL, voice: persona.voice, instructions: persona.personality });`,
  ].join("\n");
  const v2 = scanWiringFile(repaired, { fileName: "fixture-repaired.html", resolveProject: () => null });
  assert.deepEqual(v2, [], `repaired fixture must be clean, got:\n${v2.join("\n")}`);

  const overlayMissingPersona =
    `VoiceOverlay.init({ project: 'no-such-key' });`;
  const v3 = scanWiringFile(overlayMissingPersona, { fileName: "fixture-overlay.html", resolveProject: () => null });
  assert.ok(v3.some((m) => /no PROJECT_VOICES persona/.test(m)), "known-positive: overlay missing persona must fire");
});

test("dictionary keys without a wired page are empty", () => {
  // The former dead pair (catastrophes, minimize-surprise) was DELETED
  // 2026-09-29 (lane DICT-B, DICT-C dead-key handoff) after zero-consumer
  // verification. steamboat-willie is wired by its own page
  // (buildVoiceConfig flip, same fold). The gate stays: any PROJECT_VOICES
  // key that lands without a wired page fires here instead of rotting
  // silently, and a deliberate unwiring clears it by editing this allowlist
  // with a reason.
  const targets = scanTargets();
  const wired = new Set();
  for (const { source } of targets) {
    for (const m of source.matchAll(/\bproject\s*:\s*(['"])([\w-]+)\1/g)) wired.add(m[2]);
    for (const m of source.matchAll(/buildVoiceConfig\(\s*(['"])([\w-]+)\1/g)) wired.add(m[2]);
  }
  const unwired = Object.keys(PROJECT_VOICES).filter((k) => !wired.has(k)).sort();
  assert.deepEqual(
    unwired,
    [],
    `PROJECT_VOICES keys with no wired page changed: ${unwired.join(", ")} — wire them, ` +
      `delete them deliberately (report to the lib owner), or update this allowlist ` +
      `with a reason.`,
  );
});

test("proxy contract parity: server.js still requires both params", () => {
  // The gate's premise is the proxy's 4400 branch. If server.js changes its
  // mind, this scan must say so rather than silently enforce a dead contract.
  const server = readFileSync(join(REPO, "realtime-proxy", "server.js"), "utf8");
  assert.match(server, /close\(4400/, "server.js no longer closes with 4400 — update this gate's premise");
  assert.match(server, /searchParams\.get\('project'\)/, "server.js no longer reads the project param");
  assert.match(server, /searchParams\.get\('colony'\)/, "server.js no longer reads the colony param");
});
