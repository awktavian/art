/**
 * amelie/script.js — the gallery's category list is the CONTENT SOURCE's.
 * Lane ART-RSI-b56437, campaign ENGINE-COVERAGE-1119, 2026-11-22, on art
 * origin/main d6c69a7e57727898da10002774dc7f1a04182927.
 *
 * THE DEFECT. `renderProducts()` opened with
 *     const categories = ['les-pantalons', 'le-style-parisien',
 *                         'lartisanat-japonais', 'les-accessoires'];
 * — a fourth copy of a list that already lives in three places:
 * `amelie/data/gallery.json` `categories` (the content source the curation
 * pipeline writes; see amelie/scripts/curate_amelie.py), the four
 * `.products-grid[data-category=…]` divs in amelie/index.html, and the nav's
 * four `data-category` links. The literal made the least-authoritative copy
 * the authority: a fifth category added to the data (and to the page) would
 * render NOTHING, because the loop never visited it, and the `if (!grid)
 * return;` guard turned every such drop into silence. The Studio code map
 * ranked this file T0/cleanup for exactly that reason ("static-site generator
 * or content source"); before this lane, `git grep -l amelie <tip> -- tests
 * scripts` returned ZERO files, so none of it was covered by any gate.
 *
 * THE LAW NOW: the render set is `gallery.json.categories` in source order,
 * unioned with the grids the page itself declares; a piece whose category has
 * no grid is REPORTED (console.warn naming the id and the category) instead
 * of vanishing.
 *
 * WHAT THIS HARNESS IS. amelie/script.js is a plain <script>, not an ES
 * module (the package is "type": "module", so `import`ing it would parse it
 * as ESM and its top-level `let galleryData` would never be reachable). Like
 * tests/unit/load-browser-lib.mjs does for lib/*.js, the script is run in a
 * vm context with a stub `document`, then the SHIPPED entry path
 * (`loadGalleryData` → `initializeGallery`, the two calls the DOMContentLoaded
 * handler makes before any interaction wiring) is driven. Product cards are
 * real output: `grid.innerHTML` is the string the browser would parse, and
 * ids are read back out of the `data-product-id` attribute that
 * createProductCard() mints.
 *
 * WHAT THE STUB DOES NOT EXERCISE: the interaction initializers
 * (IntersectionObserver, modal, parallax, touch) and the network. `fetch` is
 * a stub that resolves the fixture data, exactly the shape loadGalleryData
 * consumes. Nothing here claims to be the Chromium canary — tests/browser/
 * is that, and it has no amelie spec yet (recommendation R1).
 *
 * POSITIVE CONTROLS, all four run before this file was committed (rc and the
 * failing legs are in the lane's RESULT.json findings). The doctored inputs
 * live in $TMPDIR and are fed through the path overrides below — the seat's
 * shipped files were never mutated, and each leg restored nothing because
 * nothing was written to them. An invariant that cannot go red certifies
 * nothing; all six legs do, in at least one control.
 *   A shipped bytes, untouched        rc=0, 6 green        (harness is faithful)
 *   B pre-fix script.js at d6c69a7    rc=1 — C3 "the new category's piece never
 *                                       rendered", C5 "no console.warn: a stranded
 *                                       piece fell silent again", C6 "a literal
 *                                       category list is back in renderProducts".
 *                                       C1/C2/C4 stayed GREEN, which is the point:
 *                                       the shipped data happens to agree with the
 *                                       old literal, so a census alone could never
 *                                       have caught this defect.
 *   C content source with one product's category renamed to a category the page
 *     has no grid for                 rc=1 — C1 "page rendered 13 of 14 pieces",
 *                                       C5 green (the warning names the strand),
 *                                       C3/C4 red as collateral: they read the
 *                                       same doctored source.
 *   D markup with one grid div emptied (data-category dropped)
 *                                       rc=1 — C1, C2 ("grids in index.html !=
 *                                       categories in gallery.json"), C3, C4 red.
 *   The pair B+C together is why this file needs both a behaviour leg (C3/C5)
 *   and a shape leg (C2/C6): C alone cannot tell a data defect from a script
 *   defect, B alone certifies the shipped tree.
 *
 * PATH OVERRIDES (same convention as museum-navigation-mirror.test.mjs's
 * ARTNAV_MIRROR_PATH), for controls and for host-local runs:
 *   AMELIE_SCRIPT_PATH  default amelie/script.js
 *   AMELIE_MARKUP_PATH  default amelie/index.html
 *   AMELIE_DATA_PATH    default amelie/data/gallery.json
 */
import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import vm from "node:vm";

const here = dirname(fileURLToPath(import.meta.url));
const repo = resolve(here, "..", "..");
const envPath = (name, fallback) =>
  process.env[name] ? resolve(repo, process.env[name]) : join(repo, fallback);

const SCRIPT_PATH = envPath("AMELIE_SCRIPT_PATH", "amelie/script.js");
const MARKUP_PATH = envPath("AMELIE_MARKUP_PATH", "amelie/index.html");
const DATA_PATH = envPath("AMELIE_DATA_PATH", "amelie/data/gallery.json");

/** The categories the PAGE declares as product grids, read off real markup. */
function gridsInMarkup(markup) {
  const found = [];
  for (const tag of markup.match(/<div\b[^>]*>/g) ?? []) {
    if (!/class="[^"]*\bproducts-grid\b[^"]*"/.test(tag)) continue;
    const category = tag.match(/data-category="([^"]*)"/);
    if (category && category[1]) found.push(category[1]);
  }
  return found;
}

function elementStub(extra = {}) {
  const classes = new Set();
  return {
    innerHTML: "",
    textContent: "",
    dataset: {},
    style: {},
    classList: {
      add: (c) => classes.add(c),
      remove: (c) => classes.delete(c),
      toggle: (c, on) => (on ? classes.add(c) : classes.delete(c)),
      contains: (c) => classes.has(c),
    },
    addEventListener() {},
    removeEventListener() {},
    appendChild() {},
    remove() {},
    scrollIntoView() {},
    getBoundingClientRect: () => ({ left: 0, top: 0, width: 100, height: 100 }),
    querySelector: () => elementStub(),
    querySelectorAll: () => [],
    closest: () => null,
    ...extra,
  };
}

/**
 * Run the shipped script in a vm over `data` and the grids `categories`
 * declares, drive loadGalleryData() + initializeGallery(), and return the
 * per-category innerHTML the script wrote plus every console.warn it emitted.
 */
async function renderGallery({ data, categories }) {
  const grids = new Map(categories.map((c) => [c, elementStub({ dataset: { category: c } })]));
  const warnings = [];
  const page = {
    innerHTML: "",
    textContent: "",
    dataset: {},
    style: {},
    classList: { add() {}, remove() {}, toggle() {}, contains: () => false },
    addEventListener() {},
    appendChild() {},
    remove() {},
    scrollIntoView() {},
    querySelector: (sel) => {
      const explicit = sel.match(/^\.products-grid\[data-category="([^"]+)"\]$/);
      if (explicit) return grids.get(explicit[1]) ?? null;
      return elementStub();
    },
    querySelectorAll: (sel) => {
      if (sel === ".products-grid[data-category]") return [...grids.values()];
      return [];
    },
  };
  const documentStub = {
    readyState: "complete",
    addEventListener() {},
    createElement: () => elementStub(),
    getElementById: () => elementStub(),
    body: elementStub(),
    head: elementStub(),
    documentElement: elementStub(),
    querySelector: page.querySelector,
    querySelectorAll: page.querySelectorAll,
  };

  const sandbox = {
    console: { log() {}, warn: (...args) => warnings.push(args.join(" ")), error() {} },
    document: documentStub,
    window: {},
    navigator: { doNotTrack: "", sendBeacon: () => false, userAgent: "node" },
    localStorage: { getItem: () => null, setItem() {}, removeItem() {}, clear() {} },
    fetch: async () => ({ ok: true, json: async () => structuredClone(data) }),
    IntersectionObserver: class { observe() {} unobserve() {} disconnect() {} },
    ResizeObserver: class { observe() {} disconnect() {} },
    setTimeout: (fn) => 0,
    clearTimeout() {},
    setInterval: () => 0,
    clearInterval() {},
    requestAnimationFrame: () => 0,
    cancelAnimationFrame() {},
    getComputedStyle: () => ({ getPropertyValue: () => "" }),
    matchMedia: () => ({ matches: false, addEventListener() {}, addListener() {} }),
    URL,
    URLSearchParams,
    structuredClone,
    location: { hostname: "localhost", pathname: "/art/amelie/", href: "http://localhost/art/amelie/" },
  };
  sandbox.globalThis = sandbox;
  sandbox.window = sandbox;
  const context = vm.createContext(sandbox);
  vm.runInContext(readFileSync(SCRIPT_PATH, "utf8"), context, {
    filename: "amelie/script.js",
  });

  // The shipped entry path, in the shipped order: the DOMContentLoaded
  // handler calls exactly these two before any interaction wiring.
  await sandbox.loadGalleryData();
  sandbox.initializeGallery();

  const rendered = {};
  for (const [category, grid] of grids) rendered[category] = grid.innerHTML;
  return { rendered, warnings, sandbox };
}

/** Product ids a rendered grid HTML carries, in order. */
function idsIn(html) {
  return [...html.matchAll(/data-product-id="([^"]+)"/g)].map((m) => m[1]);
}

const shippedData = JSON.parse(readFileSync(DATA_PATH, "utf8"));
const shippedGrids = gridsInMarkup(readFileSync(MARKUP_PATH, "utf8"));
const product = (id, category) => ({
  id,
  name: `Piece ${id}`,
  brand: "Atelier",
  category,
  price_display: "$1",
  description: "d",
  local_image: null,
  product_url: "https://example.test/" + id,
});

// ═══════════════════════════════════════════════════════════════════════════
// C1 — the shipped three surfaces agree: every piece in the content source
// renders, exactly once, in the grid of its own category.
// ═══════════════════════════════════════════════════════════════════════════

test("C1 every product in the shipped content source renders exactly once", async () => {
  const { rendered, warnings } = await renderGallery({
    data: shippedData,
    categories: shippedGrids,
  });
  const seen = [];
  for (const html of Object.values(rendered)) seen.push(...idsIn(html));
  assert.equal(
    seen.length,
    shippedData.products.length,
    `page rendered ${seen.length} of ${shippedData.products.length} pieces`,
  );
  assert.equal(new Set(seen).size, seen.length, "a piece rendered twice");
  for (const p of shippedData.products) {
    assert.ok(
      idsIn(rendered[p.category] ?? "").includes(p.id),
      `${p.id} (${p.category}) is not in its own category grid`,
    );
  }
  assert.deepEqual(warnings, [], "the shipped collection strands no piece");
});

test("C2 the markup's grid census and the content source's category list are the same set", async () => {
  // Both are inputs to C1, so this names WHICH surface drifted when C1 goes
  // red on one side only. It is a consistency pin, not the law.
  assert.deepEqual(
    [...shippedGrids].sort(),
    [...shippedData.categories].sort(),
    `grids in ${MARKUP_PATH} != categories in ${DATA_PATH}`,
  );
});

// ═══════════════════════════════════════════════════════════════════════════
// C3 — the content source is the authority: a category the script has never
// heard of still renders. RED on the pre-fix bytes (positive control).
// ═══════════════════════════════════════════════════════════════════════════

test("C3 a fifth category added to the content source renders, with no edit to script.js", async () => {
  const data = {
    ...structuredClone(shippedData),
    categories: [...shippedData.categories, "les-chaussures"],
    products: [...structuredClone(shippedData.products), product("repetto-new", "les-chaussures")],
  };
  const { rendered, warnings } = await renderGallery({
    data,
    categories: [...shippedGrids, "les-chaussures"],
  });
  assert.ok(
    idsIn(rendered["les-chaussures"] ?? "").includes("repetto-new"),
    "the new category's piece never rendered",
  );
  assert.deepEqual(warnings, [], "a source-declared, page-declared category must not warn");
});

test("C4 with no `categories` key in the data the page's own grids are the fallback", async () => {
  const data = { ...structuredClone(shippedData) };
  delete data.categories;
  const { rendered } = await renderGallery({ data, categories: shippedGrids });
  const seen = Object.values(rendered).flatMap(idsIn);
  assert.equal(
    seen.length,
    shippedData.products.length,
    `no categories key: rendered ${seen.length} of ${shippedData.products.length} pieces`,
  );
});

// ═══════════════════════════════════════════════════════════════════════════
// C5 — silence is the failure mode, so the drop must be REPORTED.
// ═══════════════════════════════════════════════════════════════════════════

test("C5 a piece whose category has no grid on the page is reported, not swallowed", async () => {
  const data = {
    ...structuredClone(shippedData),
    categories: [...shippedData.categories, "les-chapeaux"],
    products: [...structuredClone(shippedData.products), product("maison-kitsune-hat", "les-chapeaux")],
  };
  const { rendered, warnings } = await renderGallery({ data, categories: shippedGrids });
  const seen = Object.values(rendered).flatMap(idsIn);
  assert.ok(!seen.includes("maison-kitsune-hat"), "a stranded piece must not be shown");
  const line = warnings.find((w) => w.includes("maison-kitsune-hat"));
  assert.ok(line, "no console.warn: a stranded piece fell silent again");
  assert.match(line, /les-chapeaux/, "the warning must name the category to fix");
});

// ═══════════════════════════════════════════════════════════════════════════
// C6 — the merged duplicate stays merged: no fourth copy of the list may
// come back into the renderer. RED on the pre-fix bytes (positive control).
// ═══════════════════════════════════════════════════════════════════════════

test("C6 renderProducts carries no literal category list", () => {
  const source = readFileSync(SCRIPT_PATH, "utf8");
  const renderer = source.slice(
    source.indexOf("function renderProducts"),
    source.indexOf("function createProductCard"),
  );
  assert.ok(renderer.length > 0, "renderProducts() moved — update this pin's slice");
  assert.doesNotMatch(
    renderer,
    /const\s+categories\s*=\s*\[/,
    "a literal category list is back in renderProducts — the content source owns it",
  );
});
