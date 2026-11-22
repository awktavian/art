/**
 * accessibility.css ↔ accessibility.js ↔ the pages that ship both — one
 * contract for the domain-wide large-text setting, and the fence that keeps
 * consumers from forking it.
 * Lane ART-RSI-84eb52, campaign ENGINE-COVERAGE-1119, 2026-11-22, on art
 * origin/main 04ecc2f2a8ee15f8028e9b051436daffc7097f84.
 *
 * THE DEFECT. `accessibility.css` applies its type scale to TWO selectors —
 * `html.large-text, body.large-text { font-size: 22px !important; }` (lines
 * 12-15) — because `accessibility.js` stamps `<html>` BEFORE `<body>` exists
 * (the anti-flash path, accessibility.js:22-24) and only reaches `document.body`
 * at DOMContentLoaded. `mesh-dry/index.html` links that stylesheet (line 23)
 * and loads that module (line 946), but kept its own copy of the toggle logic
 * in `mesh-dry/main.js:813-840` and stamped `<body>` only. So on mesh-dry a
 * visitor who arrives with the setting ON (module stamps html + body), clicks
 * the page's own `#font-toggle-btn` and gets: body class removed,
 * `kagami_large_text` written `false`, live region announcing "Normal text
 * size", button showing off — and `<html>` still carrying `large-text`, which
 * the stylesheet's own `!important` rule is keyed to. The page stays at 22px
 * with the setting off, and nothing on the page can turn it back: only a
 * reload clears it. Before this file the shared unit had no gate at all:
 * `git grep -n accessibility.css 04ecc2f2 -- tests scripts` → rc 1 (zero hits),
 * `git grep -l -i accessib 04ecc2f2 -- tests scripts` → one file,
 * tests/unit/museum-engine-motion.test.mjs, which names the museum's
 * patent-portfolio/lib/accessibility.js and not this module, and
 * `git grep -c documentElement 04ecc2f2 -- mesh-dry` → rc 1 (zero lines).
 *
 * THE LAW NOW. A page inside this contract does not keep its own copy of the
 * setting: it loads `accessibility.js` and calls `window.kagamiAccessibility`
 * (mesh-dry/main.js now does), or — if it insists on stamping the class
 * itself — it moves `<html>` and `<body>` together. Leg 5 fences every script
 * reachable from a page that links the shared stylesheet; leg 4 runs the REAL
 * consumer function against the REAL module and grades the page's rendered
 * state after a click.
 *
 * WHAT THIS HARNESS IS. Both halves are plain `<script>` files, not ES
 * modules (the package is "type": "module", so `import`ing them parses them as
 * ESM and their `window.*` exports never materialise). tests/unit/load-browser-lib.mjs
 * already runs `lib/*.js` that way in a vm context with a real `window`; the
 * shared module is loaded through it with a stub `document`/`localStorage`
 * added, so the module's own pre-DOM path and its DOMContentLoaded path both
 * execute. The consumer is `initFontToggle`, sliced out of mesh-dry/main.js by
 * its own declaration and closing brace and run against the SAME document —
 * the shipped source, not a restatement of it. The observable is the pair of
 * class lists the stylesheet keys on, read back after a synthetic click, plus
 * the value the page wrote to `localStorage`.
 *
 * WHAT THE STUB DOES NOT EXERCISE: real layout. Nothing here computes a
 * rendered font-size; the legs assert the class/storage state that
 * accessibility.css translates into a font-size, and the `!important` coupling
 * that makes an orphaned `html.large-text` un-overridable is asserted as a
 * selector fact in leg 2. The Chromium canary (tests/browser/) is that leg and
 * has no large-text spec yet — recommendation R1 in this lane's envelope.
 *
 * POSITIVE CONTROLS (all three run against THIS file before it was committed;
 * rc and the named legs are in the lane's envelope findings). The doctored tree
 * lives in $TMPDIR and is fed in through ART_LARGE_TEXT_OVERLAY — the seat's
 * shipped files were never mutated, and nothing was restored because nothing was
 * written to them. An invariant that cannot go red certifies nothing.
 *   A shipped tree, post-fix                rc=0, 6 green.
 *   B trunk mesh-dry/main.js (blob          rc=1 — leg 4 "the page announced
 *     25b9bb59, pre-fix)"                     'Normal text size' while <html> still
 *                                           carried large-text", leg 5 "2
 *                                           statement(s) … without moving
 *                                           html.large-text", leg 6 "the key is
 *                                           declared by accessibility.js,
 *                                           mesh-dry/main.js". Legs 1/2/3 stayed
 *                                           green: the shared unit was already
 *                                           correct, which is exactly why the
 *                                           fork was the bug.
 *   C accessibility.js with its three       rc=1 — legs 3, 4 AND 5: the module's
 *     documentElement writes deleted        own lockstep is load-bearing, so leg
 *                                           4's green is not a fence over-firing.
 *                                           Leg 6 stayed green (key untouched).
 */
import assert from "node:assert/strict";
import test from "node:test";
import { execFileSync } from "node:child_process";
import { existsSync, readFileSync } from "node:fs";
import { dirname, relative, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import vm from "node:vm";
import { loadBrowserLib } from "./load-browser-lib.mjs";

const HERE = dirname(fileURLToPath(import.meta.url));
const ROOT = resolve(HERE, "..", "..");

/**
 * A control feeds a doctored copy of one of these files in through this
 * overlay; reads prefer the overlay, and anything the overlay does not carry
 * still comes from the shipped tree. The page census always comes from the
 * seat's git index, so a control cannot shrink what is covered.
 */
const OVERLAY = process.env.ART_LARGE_TEXT_OVERLAY
  ? resolve(process.env.ART_LARGE_TEXT_OVERLAY)
  : null;

function pathFor(rel) {
  if (OVERLAY) {
    const p = resolve(OVERLAY, rel);
    if (existsSync(p)) return p;
  }
  return resolve(ROOT, rel);
}
const read = (rel) => readFileSync(pathFor(rel), "utf8");

const SHARED_CSS = "accessibility.css";
const SHARED_JS = "accessibility.js";
const KEY = "kagami_large_text";
const CLASS = "large-text";

/** Tracked HTML, the way scripts/check-site.mjs enumerates the fleet. */
function trackedHtml() {
  return execFileSync("git", ["ls-files", "-z", "*.html"], {
    cwd: ROOT,
    encoding: "utf8",
  })
    .split("\0")
    .filter(Boolean)
    .filter((f) => !f.startsWith("medverify/"));
}

/**
 * The contract's reach: every page that links the shared stylesheet, with the
 * first-party scripts it loads (resolved against the page's directory) and its
 * own inline script bodies. A page that links the CSS inherits the CSS's
 * selectors; that is the whole reason the class pairing is a fleet property.
 */
function contractFleet() {
  const pages = [];
  for (const page of trackedHtml()) {
    const source = read(page);
    if (!new RegExp(`href="[^"]*${SHARED_CSS}"`).test(source)) continue;

    const dir = dirname(page);
    const scripts = [];
    for (const m of source.matchAll(/<script\b[^>]*\bsrc="([^"]+)"[^>]*><\/script>/gi)) {
      const src = m[1].split(/[?#]/)[0];
      if (/^(https?:)?\/\//.test(src)) continue; // third-party (three.js on robert)
      // A page's src is relative to the PAGE, and the fleet is addressed in
      // repo-relative paths, so resolve through ROOT and come back down.
      scripts.push(relative(ROOT, resolve(ROOT, dir, src)));
    }
    // Inline bodies: a page's own <script> without src is its own code.
    const inline = [...source.matchAll(/<script\b(?![^>]*\bsrc=)[^>]*>([\s\S]*?)<\/script>/gi)]
      .map((m) => m[1])
      .filter((body) => body.includes(CLASS));
    pages.push({ page, scripts, inline });
  }
  return pages;
}

/** Minimal classList with the real two-argument toggle() semantics. */
function makeClassList() {
  const tokens = new Set();
  return {
    add: (...names) => names.forEach((n) => tokens.add(n)),
    remove: (...names) => names.forEach((n) => tokens.delete(n)),
    toggle: (name, force) => {
      const shouldAdd = force === undefined ? !tokens.has(name) : Boolean(force);
      if (shouldAdd) tokens.add(name);
      else tokens.delete(name);
      return shouldAdd;
    },
    contains: (name) => tokens.has(name),
  };
}

function makeElement(id, extra = {}) {
  return {
    id,
    classList: makeClassList(),
    _listeners: {},
    addEventListener(type, fn) {
      (this._listeners[type] ??= []).push(fn);
    },
    click() {
      (this._listeners.click ?? []).forEach((fn) => fn({ type: "click" }));
    },
    ...extra,
  };
}

function makeDocument(ids = []) {
  const listeners = {};
  return {
    documentElement: makeElement("html"),
    body: makeElement("body"),
    getElementById: (id) => ids.find((e) => e.id === id) ?? null,
    addEventListener: (type, fn) => {
      (listeners[type] ??= []).push(fn);
    },
    /** Fire a document-level event the way the browser would. */
    fire: (type) => (listeners[type] ?? []).forEach((fn) => fn({ type })),
    _registered: () => Object.keys(listeners),
  };
}

function makeStore(initial = {}) {
  const map = new Map(Object.entries(initial));
  return {
    getItem: (k) => (map.has(k) ? map.get(k) : null),
    setItem: (k, v) => map.set(k, String(v)),
    removeItem: (k) => map.delete(k),
  };
}

class FakeCustomEvent {
  constructor(type, init = {}) {
    this.type = type;
    this.detail = init.detail;
  }
}

/** Load the shared module against a fresh page whose setting is `stored`. */
function loadShared({ stored = null, ids = [] } = {}) {
  const document = makeDocument(ids);
  const store = makeStore(stored === null ? {} : { [KEY]: String(stored) });
  const dispatched = [];
  const win = loadBrowserLib(pathFor(SHARED_JS), {
    document,
    localStorage: store,
    CustomEvent: FakeCustomEvent,
  });
  win.dispatchEvent = (event) => dispatched.push(event);
  return { document, store, win, dispatched };
}

/**
 * Slice one top-level `function NAME(...) { ... }` out of a browser script and
 * run it in a vm, so a consumer leg grades the shipped code rather than a copy
 * of its logic. The file's style (4-space bodies, closing brace at column 0)
 * is what the pattern matches; a miss is a typed failure, never a silent pass.
 */
function runConsumerFunction(sourceRel, name, globals) {
  const source = read(sourceRel);
  const match = source.match(
    new RegExp(`\\nfunction ${name}\\s*\\([\\s\\S]*?\\n\\}`),
  );
  assert.ok(
    match,
    `${sourceRel} no longer declares \`${name}\` as a top-level function — ` +
      `this leg's slice pattern is stale, so the consumer it pins is unpinned`,
  );
  const context = vm.createContext({ window: {}, ...globals });
  context.globalThis = context;
  vm.runInContext(match[0], context, { filename: `${sourceRel}:${name}` });
  assert.equal(typeof context[name], "function", `${name} did not materialise`);
  return context;
}

/** Selector blocks of the shared stylesheet, comments stripped. */
function cssBlocks(source) {
  return source
    .replace(/\/\*[\s\S]*?\*\//g, "")
    .split("}")
    .map((chunk) => {
      const at = chunk.indexOf("{");
      if (at < 0) return null;
      return {
        selectors: chunk
          .slice(0, at)
          .split(",")
          .map((s) => s.replace(/\s+/g, " ").trim())
          .filter(Boolean),
        body: chunk.slice(at + 1).replace(/\s+/g, " ").trim(),
      };
    })
    .filter(Boolean);
}

/**
 * The sources the contract binds, deduplicated: every first-party script any
 * reaching page loads (a shared file loaded by six pages is one unit) plus each
 * page's own inline bodies that name the class. `where` is the reader-visible
 * locator — the page that pulls the file in, and the file itself.
 */
function contractSources() {
  const units = new Map();
  for (const { page, scripts, inline } of contractFleet()) {
    for (const rel of scripts) {
      const source = safeRead(rel);
      if (source === null) continue;
      const key = rel;
      if (!units.has(key)) units.set(key, { where: `${page} -> ${rel}`, source });
    }
    inline.forEach((body, i) =>
      units.set(`${page}#inline${i}`, { where: `${page} <script> #${i + 1}`, source: body }),
    );
  }
  return [...units.values()];
}

// ─────────────────────────────────────────────────────────────────────────────

test("the two halves of the shared unit ship together", () => {
  // accessibility.css's class pair and accessibility.js's storage key are one
  // feature. A page that ships one half alone gets an unwired button (CSS) or
  // unstyled large text (JS), which is how the fork in mesh-dry started.
  const cssPages = new Set();
  const jsPages = new Set();
  for (const page of trackedHtml()) {
    const source = read(page);
    if (new RegExp(`href="[^"]*${SHARED_CSS}"`).test(source)) cssPages.add(page);
    if (new RegExp(`src="[^"]*${SHARED_JS}"`).test(source)) jsPages.add(page);
  }
  assert.ok(cssPages.size >= 5, `only ${cssPages.size} pages link ${SHARED_CSS}`);
  assert.deepEqual(
    [...cssPages].sort(),
    [...jsPages].sort(),
    `pages linking ${SHARED_CSS} without loading ${SHARED_JS}: ` +
      `${[...cssPages].filter((p) => !jsPages.has(p)).join(", ") || "none"}; ` +
      `loading ${SHARED_JS} without linking ${SHARED_CSS}: ` +
      `${[...jsPages].filter((p) => !cssPages.has(p)).join(", ") || "none"}`,
  );
  assert.ok(cssPages.has("mesh-dry/index.html"), "the specimen page left the contract");
  process.stdout.write(
    `census: ${cssPages.size} pages ship the shared unit — ${[...cssPages].sort().join(", ")}\n`,
  );
});

test("accessibility.css keys its type scale on both halves of the class pair", () => {
  // The pin that makes the pairing load-bearing: the stylesheet's own font-size
  // rule is anchored to `html.large-text` as well as `body.large-text`, and it
  // is `!important`, so a consumer that clears only one half cannot be
  // overridden by its own stylesheet. If this leg ever goes green with the
  // html selector gone, leg 4's guarantee weakens to a convention.
  const blocks = cssBlocks(read(SHARED_CSS));
  const fontRules = blocks.filter((b) => /font-size/.test(b.body));
  const htmlRule = fontRules.find((b) => b.selectors.includes(`html.${CLASS}`));
  const bodyRule = fontRules.find((b) => b.selectors.includes(`body.${CLASS}`));
  assert.ok(htmlRule, `no rule sets font-size on html.${CLASS} — the anti-flash half is gone`);
  assert.ok(bodyRule, `no rule sets font-size on body.${CLASS}`);
  assert.ok(
    /!important/.test(htmlRule.body),
    `the html.${CLASS} font-size lost its !important: ${htmlRule.body}`,
  );
  assert.equal(
    htmlRule.selectors.includes(`body.${CLASS}`),
    true,
    `html.${CLASS} and body.${CLASS} are no longer one selector list, so a ` +
      `consumer can satisfy one and not the other`,
  );
});

test("the shared module moves <html> and <body> together", () => {
  // accessibility.js is the authority. This leg pins its contract so a consumer
  // that delegates to it (the fix below) is guaranteed to be correct, and so
  // control C — the same file with its documentElement writes deleted — turns
  // this leg red instead of silently approving the delegation.
  const { document, store, win } = loadShared({ stored: "true" });

  // Pre-DOM: the module runs from a <script> tag and stamps <html> at once,
  // before document.body is styled — that is the whole flash fix.
  assert.equal(document.documentElement.classList.contains(CLASS), true);
  document.fire("DOMContentLoaded");
  assert.equal(document.body.classList.contains(CLASS), true);

  assert.equal(typeof win.kagamiAccessibility, "object", "the public API is gone");
  assert.equal(win.kagamiAccessibility.isLargeText(), true);

  win.kagamiAccessibility.setLargeText(false);
  assert.equal(store.getItem(KEY), "false");
  assert.equal(
    document.body.classList.contains(CLASS),
    false,
    `setLargeText(false) left body.${CLASS} on`,
  );
  assert.equal(
    document.documentElement.classList.contains(CLASS),
    false,
    `setLargeText(false) left html.${CLASS} on — accessibility.css applies ` +
      `font-size: 22px !important to it, so the page would still render large`,
  );

  win.kagamiAccessibility.toggle();
  assert.deepEqual(
    [document.documentElement.classList.contains(CLASS), document.body.classList.contains(CLASS)],
    [true, true],
    "toggle() does not move both halves together",
  );
});

test("mesh-dry's own toggle leaves the page and the setting in agreement", () => {
  // THE DEFECT LEG. mesh-dry/index.html links the shared stylesheet and loads
  // the shared module one line before main.js, then drives its own
  // #font-toggle-btn. Run that shipped function on a page that arrives with
  // the setting on, click it, and demand that what the visitor SEES (the two
  // class lists the stylesheet keys on) agrees with what the page SAYS
  // (localStorage, the announcement, the button's own state).
  const btn = makeElement("font-toggle-btn", { });
  const { document, store, win } = loadShared({ stored: "true", ids: [btn] });
  document.fire("DOMContentLoaded");
  assert.equal(document.documentElement.classList.contains(CLASS), true);
  assert.equal(document.body.classList.contains(CLASS), true);

  const announced = [];
  const context = runConsumerFunction("mesh-dry/main.js", "initFontToggle", {
    document,
    window: win,
    localStorage: store,
    announce: (message) => announced.push(message),
    Haptics: { light() {} },
    SoundSystem: { blip() {} },
  });
  context.initFontToggle();

  assert.equal(btn.classList.contains("active"), true, "the button did not reflect the on state");

  btn.click(); // visitor turns large text OFF
  const saysNormal = announced.at(-1) === "Normal text size";
  assert.equal(store.getItem(KEY), "false", "the click did not record the setting");
  assert.equal(saysNormal, true, `the live region said ${JSON.stringify(announced.at(-1))}`);
  assert.equal(
    document.body.classList.contains(CLASS),
    false,
    `the page announced "Normal text size" while body.${CLASS} was still on`,
  );
  assert.equal(
    document.documentElement.classList.contains(CLASS),
    false,
    `the page announced "Normal text size", wrote ${KEY}=false and cleared ` +
      `body.${CLASS}, but <html> still carries ${CLASS} — accessibility.css:12-15 ` +
      `applies font-size: 22px !important to html.${CLASS}, so mesh-dry keeps ` +
      `rendering large text with the setting off and no control that turns it back`,
  );

  btn.click(); // and back on
  assert.equal(store.getItem(KEY), "true");
  assert.deepEqual(
    [document.documentElement.classList.contains(CLASS), document.body.classList.contains(CLASS)],
    [true, true],
    "turning the setting back on did not restore both halves",
  );
});

test("no consumer inside the contract stamps body.large-text without <html>", () => {
  // The fleet fence: a NEW page may fork the toggle only if it keeps both
  // halves in step or delegates to window.kagamiAccessibility. This is the leg
  // that would have caught mesh-dry when it was written.
  const offenders = [];
  let touched = 0;
  for (const { where, source } of contractSources()) {
    const lines = source.split("\n");
    lines.forEach((line, i) => {
      const stampsBody = new RegExp(
        `(document\\.body|document\\s*\\.\\s*getElementsByTagName\\(["']body["'])\\)?\\.classList\\.(add|remove|toggle)\\(\\s*['"\`]${CLASS}`,
      ).test(line);
      if (!stampsBody) return;
      touched += 1;
      const window = lines.slice(Math.max(0, i - 14), i + 15).join("\n");
      const movesHtml =
        /documentElement\s*\.\s*classList\s*\.\s*(?:add|remove|toggle)\s*\([^)]*['"`]large-text/.test(
          window,
        );
      const delegates = window.includes("kagamiAccessibility");
      if (!movesHtml && !delegates) {
        offenders.push(`${where}:${i + 1} — ${line.trim()}`);
      }
    });
  }
  // Non-vacuity: the scan must actually find the class pair being moved in
  // reach (the shared module's own three writes), or the fence is grading an
  // empty set and certifies nothing.
  assert.ok(
    touched >= 1,
    `no body.${CLASS} mutation found in the contract's reach — the fleet scan ` +
      `is empty, so this leg cannot catch a fork`,
  );
  assert.deepEqual(
    offenders,
    [],
    `${offenders.length} statement(s) inside the contract mutate body.${CLASS} ` +
      `without moving html.${CLASS} in the same block or delegating to ` +
      `window.kagamiAccessibility:\n  ${offenders.join("\n  ")}`,
  );
  process.stdout.write(
    `census: ${touched} body.${CLASS} mutation(s) fenced, ${offenders.length} unfenced\n`,
  );
});

test("the setting's storage key has exactly one owner", () => {
  // `kagami_large_text` is the domain-wide setting; two files holding the
  // literal is two settings, which is how a visitor gets large text on one page
  // and normal on the next. Before this lane TWO files declared it as their own
  // — the shared module, and mesh-dry/main.js:818/827 reading and writing it
  // directly. Now only the module owns the literal; every consumer reaches it
  // through window.kagamiAccessibility. The census is over the tracked JS fleet,
  // so a NEW page forking the key goes red here, not just mesh-dry.
  // patent-portfolio/ has its own separate accessibility setting under a
  // different key ('museum-accessibility'); its page does not link
  // accessibility.css, so it is outside this contract and must not be caught.
  const KEY_LITERAL = new RegExp(`['"\`]${KEY}['"\`]`);
  const owners = [];
  const allJs = execFileSync("git", ["ls-files", "-z", "*.js"], {
    cwd: ROOT,
    encoding: "utf8",
  })
    .split("\0")
    .filter(Boolean);
  for (const rel of allJs) {
    let source;
    try {
      source = read(rel);
    } catch {
      continue;
    }
    if (KEY_LITERAL.test(source)) owners.push(rel);
  }
  assert.deepEqual(
    owners,
    [SHARED_JS],
    `'${KEY}' is declared by ${owners.length === 0 ? "no file" : owners.join(", ")} — ` +
      `the shared module (${SHARED_JS}) must be its only owner, and every page ` +
      `must reach it through window.kagamiAccessibility`,
  );

  // Inside the contract's reach, any localStorage access that brackets a
  // large-text mutation must name that one key (a page may hold unrelated
  // settings, so the check is scoped to the mutations, not the whole file).
  const strays = [];
  let seen = 0;
  for (const { where, source } of contractSources()) {
    const lines = source.split("\n");
    lines.forEach((line, i) => {
      if (!new RegExp(`classList\\.[a-z]+\\([^)]*['"\`]${CLASS}`).test(line)) return;
      const bracket = lines.slice(Math.max(0, i - 10), i + 11).join("\n");
      for (const m of bracket.matchAll(/localStorage\.(?:get|set)Item\(\s*['"`]([^'"`]+)['"`]/g)) {
        seen += 1;
        if (m[1] !== KEY) strays.push(`${where}:${i + 1} uses '${m[1]}'`);
      }
    });
  }
  assert.deepEqual(strays, [], `a second key for the same setting: ${strays.join(", ")}`);
  process.stdout.write(
    `census: '${KEY}' owned by ${owners.length} file (${owners.join(", ")}); ` +
      `${seen} bracketed localStorage access(es) in reach\n`,
  );
});

function safeRead(rel) {
  try {
    return read(rel);
  } catch {
    return null; // an untracked/absolute target is not part of the fleet scan
  }
}
