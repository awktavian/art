#!/usr/bin/env node

/**
 * scripts/build-discovery.mjs — the repository's crawl/LLM entry points.
 *
 * WHY. Before this file existed the repository carried no `sitemap.xml`, no
 * `robots.txt` and no `llms.txt` anywhere: RSI40-1102/R40 grepped all 937
 * tracked files for those four names and got zero hits, and curling the live
 * site returned 404 for `/art/sitemap.xml`, `/art/robots.txt`, `/art/llms.txt`
 * and the host-root equivalents. So 138 published documents had no machine
 * entry point at all. This generator writes the three files; the parity leg in
 * `scripts/check-site.mjs` imports `discoveryFiles()` and fails if a committed
 * file is not byte-identical to what this generator produces from the current
 * tree, which is what keeps a hand-edited or forgotten-regeneration red.
 *
 * The page set and the canonical-URL vocabulary come from
 * `scripts/complete-metadata.mjs` — one owner for both the authoring script and
 * the gate, so a page can never be in the sitemap under one URL and canonical
 * under another.
 *
 * WHAT GOES IN THE SITEMAP. Every tracked HTML page EXCEPT
 *   - a `robots: noindex` page (a sitemap entry would assert the opposite),
 *   - a declared cross-repo mirror (`patent-portfolio/test.html`, NOTES.md
 *     "skipped-mirror"; its head is not this repository's to edit),
 *   - a meta-refresh redirect shell (`get-a-job.html`, `home.html`,
 *     `octoni-on.html`) — each shell canonicalises onto its target's URL, so
 *     its target's entry already IS that URL and a second <loc> would publish
 *     a duplicate-content pair.
 * Deduplicated by canonical URL; `<dir>/index.html` is listed as `/art/<dir>/`.
 *
 * `<lastmod>` is the committer date of the last commit that touched that path
 * (`git log`), never a build timestamp, so regenerating at an unchanged tree
 * reproduces the file byte for byte.
 *
 * Usage:
 *   node scripts/build-discovery.mjs            # write sitemap.xml, robots.txt, llms.txt
 *   node scripts/build-discovery.mjs --check    # exit 1 if any committed file differs
 *   node scripts/build-discovery.mjs --print    # write nothing, print the three files
 */

import { execFileSync } from "node:child_process";
import { readFileSync, writeFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

import {
  SITE_ORIGIN,
  SITE_BASE,
  canonicalFor,
  exemptionHolds,
  htmlPages,
  redirectTarget,
  trackedFiles,
  urlForPath,
} from "./complete-metadata.mjs";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");

export const SITEMAP_PATH = "sitemap.xml";
export const ROBOTS_PATH = "robots.txt";
export const LLMS_PATH = "llms.txt";
/** Read-only input for llms.txt. This generator never writes into it. */
export const PATENT_INVENTORY_PATH = "patent-portfolio/data/patent-inventory.json";

export const SITEMAP_URL = `${SITE_ORIGIN}${SITE_BASE}/${SITEMAP_PATH}`;

function gitArgs(args, cwd = root) {
  return execFileSync("git", args, { cwd, encoding: "utf8", maxBuffer: 64 * 1024 * 1024 });
}

/**
 * Path -> ISO-8601 committer date of the last commit that touched it, in one
 * `git log` walk over HTML paths (newest first, first sighting wins). A path
 * with no commit yet yields no entry, and the caller then omits `<lastmod>`
 * rather than inventing a date.
 */
export function lastmodsFor(paths) {
  const wanted = new Set(paths);
  const found = new Map();
  if (wanted.size === 0) return found;
  const out = gitArgs([
    "log",
    "--format=committer-date:%cI",
    "--name-only",
    "--",
    "*.html",
  ]);
  let stamp = null;
  for (const line of out.split("\n")) {
    if (line.startsWith("committer-date:")) {
      stamp = line.slice("committer-date:".length);
      continue;
    }
    const path = line.trim();
    if (path && stamp && wanted.has(path) && !found.has(path)) found.set(path, stamp);
  }
  return found;
}

export function readSource(file) {
  return readFileSync(resolve(root, file), "utf8");
}

/** The sitemap's page list: [{file, url}] sorted by URL. */
export function sitemapEntries({ pages, fileSet, read }) {
  const seen = new Map();
  const excluded = { noindex: [], mirror: [], shell: [] };
  for (const file of pages) {
    const source = read(file);
    if (exemptionHolds(file, source)) {
      excluded.mirror.push(file);
      continue;
    }
    const url = canonicalFor(file, source, fileSet);
    if (url === null) {
      excluded.noindex.push(file);
      continue;
    }
    if (redirectTarget(file, source, fileSet) !== null) {
      excluded.shell.push(file);
      continue;
    }
    if (!seen.has(url)) seen.set(url, file);
  }
  return {
    entries: [...seen.entries()]
      .map(([url, file]) => ({ url, file }))
      .sort((a, b) => (a.url < b.url ? -1 : a.url > b.url ? 1 : 0)),
    excluded,
  };
}

export function buildSitemap({ pages, fileSet, read }) {
  const { entries } = sitemapEntries({ pages, fileSet, read });
  const stamps = lastmodsFor(entries.map((entry) => entry.file));
  const body = entries.map(({ url, file }) => {
    const stamp = stamps.get(file);
    return [
      "  <url>",
      `    <loc>${url}</loc>`,
      ...(stamp ? [`    <lastmod>${stamp}</lastmod>`] : []),
      "  </url>",
    ].join("\n");
  });

  return [
    '<?xml version="1.0" encoding="UTF-8"?>',
    "<!--",
    "  Generated by scripts/build-discovery.mjs - do not edit by hand.",
    "  Regenerate with: node scripts/build-discovery.mjs",
    "",
    `  Covers every tracked, indexable HTML page of this GitHub Pages site`,
    `  (${SITE_ORIGIN}${SITE_BASE}/). Excluded, and why: a robots "noindex" page (an`,
    "  entry would contradict it), a declared cross-repo mirror whose head another",
    "  repository owns (patent-portfolio/test.html), and meta-refresh redirect shells,",
    "  each of which canonicalises onto the target page's own entry.",
    "  Every lastmod element is the committer date of the last commit touching that path.",
    `  Indexable pages listed: ${entries.length}.`,
    "  -->",
    '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
    body.join("\n"),
    "</urlset>",
    "",
  ].join("\n");
}

export function buildRobots() {
  return [
    "# Generated by scripts/build-discovery.mjs - do not edit by hand.",
    "# Regenerate with: node scripts/build-discovery.mjs",
    "#",
    "# This repository is a GitHub Pages PROJECT page, so the repository root is",
    `# the document root of ${SITE_ORIGIN}${SITE_BASE}/ and this file is served at`,
    `# ${SITE_ORIGIN}${SITE_BASE}/robots.txt. The host root (awktavian.github.io/robots.txt)`,
    "# is owned by the awktavian.github.io repository and is not this file.",
    "",
    "User-agent: *",
    "Allow: /",
    "",
    `Sitemap: ${SITEMAP_URL}`,
    "",
  ].join("\n");
}

function readInventory(fileSet) {
  if (!fileSet.has(PATENT_INVENTORY_PATH)) {
    return {
      available: false,
      note: "patent-portfolio/data/patent-inventory.json is not tracked at this revision",
    };
  }
  const parsed = JSON.parse(readFileSync(resolve(root, PATENT_INVENTORY_PATH), "utf8"));
  const patents = Array.isArray(parsed.patents) ? parsed.patents : [];
  return {
    available: true,
    source: parsed.source ?? "unknown",
    updated: parsed.updated ?? "unknown",
    declaredTotal: parsed.total ?? null,
    patents,
  };
}

/** Directory -> pages, for the llms.txt section list. */
function pagesByDirectory(pages) {
  const groups = new Map();
  for (const file of pages) {
    const dir = file.includes("/") ? file.slice(0, file.lastIndexOf("/")) : "";
    if (!groups.has(dir)) groups.set(dir, []);
    groups.get(dir).push(file);
  }
  return groups;
}

const SECTION_LIST_LIMIT = 6;

/** One line per directory that holds at least one page. */
function sectionLines({ pages }) {
  const lines = [];
  for (const [dir, files] of [...pagesByDirectory(pages).entries()].sort()) {
    const indexPath = dir === "" ? "index.html" : `${dir}/index.html`;
    const label = dir === "" ? "site root" : `${dir}/`;
    const hasIndex = files.includes(indexPath);
    const extras = files.filter((file) => file !== indexPath);
    const tail =
      extras.length === 0
        ? ""
        : extras.length <= SECTION_LIST_LIMIT
          ? `; other pages: ${extras.join(", ")}`
          : `; ${extras.length} other pages`;
    const count = `${files.length} page${files.length === 1 ? "" : "s"}`;
    lines.push(
      hasIndex
        ? `- [${label}](${urlForPath(indexPath)}) — ${count}${tail}`
        : `- \`${label}\` — ${count}, no index page${tail}`,
    );
  }
  return lines;
}

export function buildLlms({ pages, fileSet, read }) {
  const { entries, excluded } = sitemapEntries({ pages, fileSet, read });
  const inventory = readInventory(fileSet);
  const lines = [];

  lines.push("# 鏡 Kagami — Tim Jacoby: Art, Tools, and the Patent Museum");
  lines.push("");
  lines.push(
    `> A static portfolio of ${entries.length} published HTML documents, served by GitHub Pages at `,
  );
  lines.push(
    `> ${SITE_ORIGIN}${SITE_BASE}/ from the branch tree (no build step). It holds interactive works, `,
  );
  lines.push(
    "> essays and technical briefs, curated galleries, and one 3D experience: the Patent Museum, ",
  );
  lines.push("> which exhibits the 54 inventions listed at the end of this file.");
  lines.push("");
  lines.push("## Discovery");
  lines.push("");
  lines.push(
    `- [sitemap.xml](${SITEMAP_URL}): all ${entries.length} indexable pages, with the last commit date of each.`,
  );
  lines.push(
    `- [robots.txt](${SITE_ORIGIN}${SITE_BASE}/robots.txt): allows every crawler; nothing is disallowed.`,
  );
  lines.push(
    `- [This site's directory](${SITE_ORIGIN}${SITE_BASE}/): a human index of the works, grouped and searchable.`,
  );
  lines.push("");
  lines.push("## Sections");
  lines.push("");
  lines.push(...sectionLines({ pages }));
  lines.push("");
  lines.push("## Patent Museum");
  lines.push("");
  lines.push(
    `Location: [/art/patent-portfolio/](${SITE_ORIGIN}${SITE_BASE}/patent-portfolio/) —`,
  );
  lines.push(
    "a Three.js gallery that walks the visitor through the inventions below as sculptural exhibits. ",
  );
  lines.push(
    "The museum is one document: the exhibits are rendered by its JavaScript from the inventory data ",
  );
  lines.push(
    `file \`${PATENT_INVENTORY_PATH}\`, which is machine-readable JSON.`,
  );
  lines.push("");
  if (inventory.available) {
    lines.push(
      `Inventory: ${inventory.patents.length} entries (the file declares total=${inventory.declaredTotal}), source \`${inventory.source}\`, last updated ${inventory.updated}.`,
    );
  } else {
    lines.push(`Inventory: UNAVAILABLE — ${inventory.note}.`);
  }
  lines.push("");
  lines.push(
    "### Reading note — there is no per-patent URL on this site",
  );
  lines.push("");
  lines.push(
    "No page of the form `/art/patent-portfolio/patent-<id>.html` exists, and the museum does not route ",
  );
  lines.push(
    "by hash or history state, so an individual patent cannot be deep-linked or quoted from a crawl. ",
  );
  lines.push(
    "The list below is the citable text for each patent. If you need a per-patent document, ask for one; ",
  );
  lines.push(
    "do not invent a URL — none of the entries below resolve outside this list.",
  );
  lines.push("");
  lines.push(`### Patents (${inventory.available ? inventory.patents.length : 0})`);
  lines.push("");
  if (inventory.available) {
    for (const patent of inventory.patents) {
      lines.push(
        `- \`${patent.id}\` **${patent.title}** — category ${patent.category}, priority ${patent.priority}, colony ${patent.colony}, status ${patent.status}, filing: ${patent.filing}.`,
      );
    }
  }
  lines.push("");
  lines.push("## Caveats for language models");
  lines.push("");
  lines.push(
    `- ${count(excluded.noindex.length, "page")} of this repository carr${excluded.noindex.length === 1 ? "ies" : "y"} a \`robots\` meta of \`noindex\` (${excluded.noindex.join(", ") || "none"}) and ${excluded.noindex.length === 1 ? "is" : "are"} deliberately not in the sitemap.`,
  );
  lines.push(
    `- ${count(excluded.shell.length, "page")} (${excluded.shell.join(", ") || "none"}) ${excluded.shell.length === 1 ? "is" : "are"} meta-refresh redirect shells kept only so older links keep working; each canonicalises onto its target, so treat the target as the document.`,
  );
  lines.push(
    `- ${count(excluded.mirror.length, "page")} (${excluded.mirror.join(", ") || "none"}) ${excluded.mirror.length === 1 ? "is" : "are"} declared byte-identical mirror${excluded.mirror.length === 1 ? "" : "s"} of a file in another repository; the other repository owns the canonical copy.`,
  );
  lines.push(
    "- Every page's own `<link rel=\"canonical\">` is the `/art/`-prefixed URL on this host; there is no custom domain.",
  );
  lines.push(
    "- Statistics quoted inside pages (patent counts, corpus sizes) are generated from the tree by `scripts/sync-corpus-stats.mjs` and checked in CI; if a number here and a number on a page disagree, the page is the stale one.",
  );
  lines.push("");
  lines.push("## Meta");
  lines.push("");
  lines.push(
    "Generated by `scripts/build-discovery.mjs` from the tracked tree; re-run after adding or removing a page.",
  );
  lines.push(
    "`scripts/check-site.mjs` fails CI if this file is not byte-identical to that regeneration.",
  );
  lines.push("");

  return `${lines.map((line) => line.replace(/[ \t]+$/, "")).join("\n")}`;
}

function count(n, noun) {
  return `${n} ${noun}${n === 1 ? "" : "s"}`;
}

/** Every discovery file this generator owns: path -> contents. */
export function discoveryFiles({ pages, fileSet, read = readSource } = {}) {
  const list = pages ?? htmlPages(trackedFiles());
  const set = fileSet ?? new Set(trackedFiles());
  return new Map([
    [SITEMAP_PATH, buildSitemap({ pages: list, fileSet: set, read })],
    [ROBOTS_PATH, buildRobots()],
    [LLMS_PATH, buildLlms({ pages: list, fileSet: set, read })],
  ]);
}

const invokedDirectly =
  process.argv[1] && resolve(process.argv[1]) === resolve(fileURLToPath(import.meta.url));

if (invokedDirectly) {
  const args = new Set(process.argv.slice(2));
  const mode = args.has("--check") ? "check" : args.has("--print") ? "print" : "write";
  const files = discoveryFiles();
  let stale = [];

  for (const [path, contents] of files) {
    if (mode === "print") {
      console.log(`\n===== ${path} =====\n${contents}`);
      continue;
    }
    let current = null;
    try {
      current = readFileSync(resolve(root, path), "utf8");
    } catch {
      current = null;
    }
    if (current === contents) continue;
    stale.push(path);
    if (mode === "write") {
      writeFileSync(resolve(root, path), contents, "utf8");
      console.log(`${path}: ${current === null ? "created" : "rewritten"} (${contents.length} bytes)`);
    } else {
      console.log(`${path}: STALE (${current === null ? "absent" : "differs from regeneration"})`);
    }
  }

  const entryCount = sitemapEntries({
    pages: htmlPages(trackedFiles()),
    fileSet: new Set(trackedFiles()),
    read: readSource,
  }).entries.length;
  console.log(
    `build-discovery (${mode}): ${files.size} files, ${entryCount} <loc> entries, ` +
      `${stale.length} needing regeneration`,
  );
  if (mode === "check" && stale.length > 0) {
    console.error(`fix: node scripts/build-discovery.mjs  (${stale.join(", ")})`);
    process.exit(1);
  }
}
