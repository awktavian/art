/**
 * mesh-dry's hint toast has ONE owner.
 *
 * THE SURFACE. `mesh-dry/index.html` ships one celebration channel: the
 * `.dry-hint-toast` node that `styles.css:475-513` styles, keyed on its
 * `.visible` class. Five shipped code paths write through it —
 * `DiscoverySystem.showDiscoveryToast` (3000 ms), `showAllCompleteToast`
 * (5000 ms), `showHint` (2500 ms), `showScrollMilestoneReward` (5000 ms) and
 * `showIdleHint` (4000 ms). On trunk each of the five re-implements the node
 * lookup, the creation, the markup, the `visible` stamp AND its own hiding
 * timer, so one node carries several pending timers at once and nothing cancels
 * an earlier one.
 *
 * THE DEFECT. The page's payoff is deterministic, not a race. `discover()`
 * (main.js:459-487) fires `showDiscoveryToast` on the 8th easter egg and, 1000 ms
 * later, `showAllCompleteToast`. The discovery toast schedules
 * `remove('visible')` at t=3000; the all-complete toast reuses THE SAME NODE,
 * re-stamps `visible` and schedules its own removal at t=6000. At t=3000 the
 * first toast's stale timer fires against the node the second toast is holding,
 * so "You've found all 8 easter eggs!" disappears 2000 ms into the 5000 ms the
 * page promises — mid-sentence, while `SoundSystem.allComplete()` is still
 * playing its arpeggio. The same shape cuts any shorter timer's message under a
 * longer one that follows it.
 *
 * THE LAW NOW. One function owns the node: it cancels the pending removal timer
 * before it takes the node, creates the node at most once, and writes the markup
 * `styles.css` keys on. Call sites pass a title, a body and their own duration —
 * the five durations are pinned leg by leg so a merge cannot quietly shorten what
 * a reader gets to read.
 *
 * HOW IT IS RUN. `mesh-dry/main.js` is a classic `<script>`, not an ESM module
 * (its `const`/`function` declarations never reach `window`), so the shipped file
 * is loaded whole into a vm context with a stub DOM and a virtual clock, and the
 * REAL `discover()` / toast functions are called. `DOMContentLoaded` is never
 * fired, so no canvas, `IntersectionObserver` or `AudioContext` path runs — the
 * sound and haptic units guard themselves on `this.ctx` / `'vibrate' in
 * navigator` and return, exactly as they do in a browser without them. Nothing
 * here restates the page's logic.
 *
 * POSITIVE CONTROLS (both run before this file was committed; rc and legs in the
 * lane's envelope). The doctored tree is fed in through `ART_MESH_DRY_OVERLAY` —
 * the seat's shipped files are never mutated, because nothing is written to them.
 *   A shipped tree, post-fix                  rc=0, 5 green.
 *   B origin/main mesh-dry/main.js (pre-fix)  rc=1 — leg 1 finds the all-complete
 *                                             toast hidden at t=3000, leg 2 counts
 *                                             five `dry-hint-toast` creations.
 * An invariant that cannot go red certifies nothing.
 */
import assert from "node:assert/strict";
import test from "node:test";
import { existsSync, readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import vm from "node:vm";

const HERE = dirname(fileURLToPath(import.meta.url));
const ROOT = resolve(HERE, "..", "..");

/** Reads prefer the overlay a control feeds in; anything absent comes from the tree. */
const OVERLAY = process.env.ART_MESH_DRY_OVERLAY
  ? resolve(process.env.ART_MESH_DRY_OVERLAY)
  : null;

function pathFor(rel) {
  if (OVERLAY) {
    const p = resolve(OVERLAY, rel);
    if (existsSync(p)) return p;
  }
  return resolve(ROOT, rel);
}

const JS = "mesh-dry/main.js";
const CSS = "mesh-dry/styles.css";

/** The five durations the page has always given a reader. */
const DURATIONS = {
  discovery: 3000,
  allComplete: 5000,
  hint: 2500,
  scroll: 5000,
  idle: 4000,
};

const ALL_EGGS = [
  "dry-keyword", "wet-keyword", "konami", "kagami-key",
  "all-nodes", "triple-copy", "circuit-cycle", "identity-gen",
];

// ---------------------------------------------------------------------------
// The stub world: a DOM tree, a storage area, and a clock only `advance` moves.
// ---------------------------------------------------------------------------

function makeWorld() {
  let clock = 0;
  let seq = 0;
  const timers = new Map();
  const stored = new Map();
  const bodyNodes = [];

  function makeNode(tag) {
    const node = {
      tagName: String(tag).toUpperCase(),
      id: "",
      children: [],
      parentNode: null,
      style: { cssText: "", setProperty() {} },
      _listeners: {},
      _html: "",
      textContent: "",
    };
    const classes = new Set();
    node.classList = {
      add: (...cs) => cs.forEach((c) => classes.add(c)),
      remove: (...cs) => cs.forEach((c) => classes.delete(c)),
      contains: (c) => classes.has(c),
      toggle: (c) => (classes.has(c) ? classes.delete(c) : classes.add(c)),
    };
    Object.defineProperty(node, "className", {
      get() { return [...classes].join(" "); },
      set(v) {
        classes.clear();
        String(v).split(/\s+/).filter(Boolean).forEach((c) => classes.add(c));
      },
    });
    Object.defineProperty(node, "innerHTML", {
      get() { return node._html; },
      set(v) {
        node._html = String(v);
        // A reader hears the text inside the markup, so keep a plain-text view.
        node.textContent = node._html.replace(/<[^>]*>/g, " ").replace(/\s+/g, " ").trim();
      },
    });
    node.appendChild = (child) => {
      node.children.push(child);
      child.parentNode = node;
      return child;
    };
    node.remove = () => {
      if (node.parentNode) {
        node.parentNode.children = node.parentNode.children.filter((c) => c !== node);
        node.parentNode = null;
      }
    };
    node.addEventListener = (type, fn) => {
      (node._listeners[type] ??= []).push(fn);
    };
    node.removeEventListener = () => {};
    node.click = () => (node._listeners.click ?? []).forEach((fn) => fn({ type: "click" }));
    node.querySelector = (sel) => queryDescendants(node, sel)[0] ?? null;
    node.querySelectorAll = (sel) => queryDescendants(node, sel);
    bodyNodes.push(node);
    return node;
  }

  function matches(node, sel) {
    if (sel.startsWith(".")) return node.classList.contains(sel.slice(1));
    if (sel.startsWith("#")) return node.id === sel.slice(1);
    return node.tagName === sel.toUpperCase();
  }

  function queryDescendants(root, sel) {
    const out = [];
    const walk = (n) => {
      for (const c of n.children) {
        if (matches(c, sel)) out.push(c);
        walk(c);
      }
    };
    walk(root);
    return out;
  }

  const body = makeNode("body");
  const documentElement = makeNode("html");
  const head = makeNode("head");
  const byId = new Map();

  const document = {
    body,
    head,
    documentElement,
    createElement: (tag) => makeNode(tag),
    getElementById: (id) => byId.get(id) ?? null,
    querySelector: (sel) => queryDescendants(body, sel)[0] ?? null,
    querySelectorAll: (sel) => queryDescendants(body, sel),
    _listeners: {},
    addEventListener: (type, fn) => {
      (document._listeners[type] ??= []).push(fn);
    },
    removeEventListener: () => {},
    cookie: "",
  };

  const window = {
    matchMedia: () => ({ matches: true, addEventListener() {}, addListener() {} }),
    addEventListener() {},
    removeEventListener() {},
    requestAnimationFrame: () => 0,
    // Undefined on purpose: SoundSystem.init() never runs, and every sound unit
    // returns early on `!this.ctx`, as it does in a browser with no Web Audio.
    AudioContext: undefined,
    location: { hostname: "localhost", pathname: "/mesh-dry/" },
    document,
  };

  const localStorage = {
    getItem: (k) => (stored.has(k) ? stored.get(k) : null),
    setItem: (k, v) => stored.set(k, String(v)),
    removeItem: (k) => stored.delete(k),
  };

  function setTimeoutStub(fn, ms = 0) {
    const id = ++seq;
    timers.set(id, { at: clock + Number(ms), fn });
    return id;
  }

  /** Move to an absolute instant, firing every timer due on the way, in order. */
  function advance(to) {
    for (;;) {
      const due = [...timers.entries()]
        .filter(([, t]) => t.at <= to)
        .sort((a, b) => a[1].at - b[1].at || a[0] - b[0])[0];
      if (!due) break;
      const [id, t] = due;
      timers.delete(id);
      clock = Math.max(clock, t.at);
      t.fn();
    }
    clock = Math.max(clock, to);
  }

  const world = {
    document,
    window,
    localStorage,
    makeNode,
    /** Put a node on the page under an id, the way index.html ships it. */
    mount(id, node) {
      node.id = id;
      byId.set(id, node);
      body.appendChild(node);
      return node;
    },
    advance,
    after: (ms) => advance(clock + ms),
    now: () => clock,
    /** Every live `.dry-hint-toast` node in the body subtree. */
    toastNodes: () => queryDescendants(body, ".dry-hint-toast"),
    pendingTimers: () => [...timers.values()].map((t) => t.at - clock).filter((d) => d >= 0),
    stored,
  };

  const context = vm.createContext({
    window,
    document,
    localStorage,
    navigator: {},
    console: { log() {} },
    setTimeout: setTimeoutStub,
    clearTimeout: (id) => timers.delete(id),
    setInterval: () => 0,
    clearInterval: () => {},
    requestAnimationFrame: window.requestAnimationFrame,
    Date,
    Math,
    JSON,
    Set,
    Map,
    Object,
    Array,
    String,
    Number,
    RegExp,
    Boolean,
    Error,
    isNaN,
    parseInt,
    parseFloat,
  });
  context.globalThis = context;
  world.context = context;
  return world;
}

/**
 * Load the shipped `mesh-dry/main.js` whole, then hand the legs the objects and
 * functions the page actually runs. Top-level `const`/`let` in a vm script are
 * lexical, not context properties, so the tail exports them from inside the
 * shipped file's own scope rather than re-declaring anything here.
 */
function loadPage() {
  const world = makeWorld();
  const source = readFileSync(pathFor(JS), "utf8");
  const tail =
    "\n;globalThis.__shipped = {" +
    "DiscoverySystem, showScrollMilestoneReward, showIdleHint, announce};";
  vm.runInContext(source + tail, world.context, { filename: JS });
  world.shipped = world.context.__shipped;
  assert.equal(
    typeof world.shipped?.DiscoverySystem?.discover,
    "function",
    "mesh-dry/main.js no longer ships DiscoverySystem.discover — this harness is stale",
  );
  return world;
}

/** The two nodes every toast path writes to: the live region and the counter. */
function mountLiveNodes(world) {
  const announcer = world.mount("live-announcer", world.makeNode("div"));
  announcer.classList.add("visually-hidden");
  const counter = world.mount("discovery-counter", world.makeNode("div"));
  counter.classList.add("discovery-counter");
  const count = world.makeNode("span");
  count.classList.add("discovery-count");
  counter.appendChild(count);
  return { announcer, counter, count };
}

/** Unlock eggs 1..7 so the 8th `discover()` is the page's real completion path. */
function primeSevenNearCompletion(world) {
  const D = world.shipped.DiscoverySystem;
  for (const id of ALL_EGGS.slice(0, 7)) D.discover(id);
  assert.equal(D.foundCount, 7, "harness did not leave the page one egg short");
  return D;
}

// ---------------------------------------------------------------------------
// Leg 1 — the payoff toast keeps the whole 5000 ms the page promises.
// ---------------------------------------------------------------------------

test("the all-complete toast survives the discovery toast that preceded it", () => {
  const world = loadPage();
  mountLiveNodes(world);
  const D = primeSevenNearCompletion(world);

  // The visitor unlocks the 8th egg. discover() shows its own toast now and the
  // completion toast 1000 ms later, on the same node.
  assert.equal(D.discover("identity-gen"), true);
  const toasts = world.toastNodes();
  assert.equal(toasts.length, 1, `the page built ${toasts.length} toast nodes on one unlock`);
  const toast = toasts[0];
  assert.equal(toast.classList.contains("visible"), true, "the discovery toast never showed");

  world.advance(1000); // the completion toast takes the node
  assert.match(toast.innerHTML, /All Discoveries Complete/, "the payoff message never arrived");
  assert.equal(toast.classList.contains("visible"), true, "the payoff toast never showed");

  world.advance(3000); // t=3000: the DISCOVERY toast's timer was due here
  assert.equal(
    toast.classList.contains("visible"),
    true,
    "the 8th discovery's own 3000 ms timer is still armed when the all-complete toast " +
      "takes the node at t=1000, so it strips .visible at t=3000 and the reader loses " +
      '"You\'ve found all 8 easter eggs!" 2000 ms into a 5000 ms message while ' +
      "SoundSystem.allComplete() is still playing. One owner must cancel the pending " +
      "removal timer before it takes the shared node.",
  );

  world.advance(5999);
  assert.equal(toast.classList.contains("visible"), true, "the payoff toast ended early");

  world.advance(6000); // 1000 + 5000: its OWN deadline
  assert.equal(
    toast.classList.contains("visible"),
    false,
    "the payoff toast never hides — a cancel-on-takeover fix that leaks the timer " +
      "leaves the celebration pinned over the page",
  );
});

// ---------------------------------------------------------------------------
// Leg 2 — one node, one owner: the five forks are gone from the shipped source.
// ---------------------------------------------------------------------------

test("the toast node has exactly one owner in the shipped source", () => {
  const source = readFileSync(pathFor(JS), "utf8");
  const creations = [
    ...source.matchAll(/className\s*=\s*["'`]dry-hint-toast["'`]/g),
  ];
  assert.equal(
    creations.length,
    1,
    `mesh-dry/main.js creates the toast in ${creations.length} places — each copy also ` +
      "re-implements the show and its hide, which is how an older timer learned to " +
      "dismiss a newer message. All five call sites must go through one owner.",
  );

  const lookups = [...source.matchAll(/querySelector\(\s*["']\.dry-hint-toast["']\s*\)/g)];
  assert.equal(lookups.length, 1, `the node is looked up in ${lookups.length} places, expected 1`);

  // And the runtime agrees: driving every path leaves ONE node, not a stack.
  const world = loadPage();
  mountLiveNodes(world);
  const D = world.shipped.DiscoverySystem;
  D.showDiscoveryToast("Topology Tourist");
  D.showAllCompleteToast();
  D.showHint("konami");
  world.shipped.showScrollMilestoneReward();
  world.shipped.showIdleHint();
  assert.equal(
    world.toastNodes().length,
    1,
    `five toast paths built ${world.toastNodes().length} nodes; the page styles one channel`,
  );
});

// ---------------------------------------------------------------------------
// Leg 3 — every path still gets the duration the page has always given it.
// ---------------------------------------------------------------------------

test("each toast keeps its own published duration", () => {
  const world = loadPage();
  mountLiveNodes(world);
  const D = world.shipped.DiscoverySystem;

  const cases = [
    ["discovery", DURATIONS.discovery, () => D.showDiscoveryToast("WET Warning")],
    ["allComplete", DURATIONS.allComplete, () => D.showAllCompleteToast()],
    ["hint", DURATIONS.hint, () => D.showHint("triple-copy")],
    ["scroll", DURATIONS.scroll, () => world.shipped.showScrollMilestoneReward()],
    ["idle", DURATIONS.idle, () => world.shipped.showIdleHint()],
  ];

  for (const [name, ms, show] of cases) {
    world.after(10000); // drain whatever the previous case left running
    show();
    const toast = world.toastNodes()[0];
    assert.ok(toast, `${name}: the page built no toast node`);
    assert.equal(toast.classList.contains("visible"), true, `${name}: nothing shown`);

    world.after(ms - 1);
    assert.equal(
      toast.classList.contains("visible"),
      true,
      `${name} hid after ${ms - 1} ms of its own ${ms} ms — merging the five copies ` +
        "must not shorten what a reader gets to read",
    );

    world.after(1);
    assert.equal(
      toast.classList.contains("visible"),
      false,
      `${name} outstayed its ${ms} ms, so the merge left a timer running`,
    );
    assert.deepEqual(
      world.pendingTimers(),
      [],
      `${name} left a timer pending after it hid`,
    );
  }
});

// ---------------------------------------------------------------------------
// Leg 4 — the markup contract with styles.css survives the merge.
// ---------------------------------------------------------------------------

test("the merged owner writes the markup the stylesheet keys on", () => {
  const css = readFileSync(pathFor(CSS), "utf8");
  for (const selector of [
    ".dry-hint-toast {",
    ".dry-hint-toast.visible {",
    ".dry-hint-toast .hint-title {",
    ".dry-hint-toast .hint-text {",
  ]) {
    assert.ok(css.includes(selector), `mesh-dry/styles.css no longer carries ${selector}`);
  }

  const world = loadPage();
  mountLiveNodes(world);
  world.shipped.DiscoverySystem.showDiscoveryToast("Identity Crisis");
  const toast = world.toastNodes()[0];
  assert.match(toast.innerHTML, /class="hint-title"/, "the title lost its hook");
  assert.match(toast.innerHTML, /class="hint-text"/, "the body lost its hook");
  assert.match(toast.innerHTML, /Identity Crisis/, "the message did not reach the node");
});

// ---------------------------------------------------------------------------
// Leg 5 — the live region still carries what the toast says (WCAG 2.1 AA).
// ---------------------------------------------------------------------------

test("the announcing toast paths still announce", () => {
  const world = loadPage();
  const { announcer, count } = mountLiveNodes(world);
  const seen = [];
  const grab = () => { if (announcer.textContent) seen.push(announcer.textContent); };

  const D = primeSevenNearCompletion(world);
  D.discover("identity-gen");
  grab();
  assert.match(
    seen.join(" "),
    /Discovery unlocked: Identity Crisis/,
    "the discovery announcement is gone from the page",
  );

  world.advance(1000);
  grab();
  assert.match(
    seen.join(" "),
    /All 8 discoveries complete/,
    "the completion announcement is gone from the page",
  );

  world.advance(1001); // announce() clears the region 1000 ms after each write
  world.shipped.showScrollMilestoneReward();
  grab();
  assert.match(
    seen.join(" "),
    /reached the end of the page/,
    "the scroll-milestone announcement is gone from the page",
  );

  // The counter the reader watches still agrees with the discoveries.
  assert.equal(D.foundCount, 8);
  assert.match(count.textContent, /8\/8/, "the discovery counter no longer reads 8/8");
});
