#!/usr/bin/env node

import { execFileSync } from "node:child_process";
import { readFileSync } from "node:fs";
import { dirname, extname, isAbsolute, relative, resolve, sep } from "node:path";
import { fileURLToPath } from "node:url";

// The discovery-metadata vocabulary has ONE owner: the two generator scripts
// that write it. The gate below imports their predicates instead of restating
// them, so a page can never be green in the sitemap and red in its own
// <link rel="canonical">, and so the checker's idea of "indexable" is the
// generator's idea by construction. (RSI40-1102/CS1: this leg used to assert
// only lang/title/viewport, which is how 136/138 missing canonicals and
// 133/138 missing og:image stayed invisible to CI.)
import {
  SITE_BASE,
  SITE_ORIGIN,
  canonicalFor,
  exemptionHolds,
  pathForUrl,
  redirectTarget,
  resolveRelative,
} from "./complete-metadata.mjs";
import {
  LLMS_PATH,
  ROBOTS_PATH,
  SITEMAP_PATH,
  discoveryFiles,
  sitemapEntries,
} from "./build-discovery.mjs";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const trackedFiles = execFileSync("git", ["ls-files", "-z"], {
  cwd: root,
  encoding: "utf8",
})
  .split("\0")
  .filter(Boolean);
const trackedFileSet = new Set(trackedFiles);
const htmlFiles = trackedFiles
  .filter((file) => file.endsWith(".html"))
  .filter((file) => !file.startsWith("medverify/"))
  .filter((file) => !file.includes("/playwright-report/"));
const manifestFiles = trackedFiles.filter(
  (file) => file.endsWith(".webmanifest") || file.endsWith("/manifest.json"),
);
const serviceWorkerFiles = trackedFiles.filter((file) => file.endsWith("/sw.js"));

const failures = [];
/** <loc> URLs the committed sitemap.xml actually publishes, for the per-page leg. */
let sitemapLocs = new Set();
let references = 0;

/**
 * What the discovery legs actually covered, counted while they check rather than
 * reported from the generator's own bookkeeping. Printed on green as well as red,
 * because a pass that does not name its own coverage is the failure mode this lane
 * was cut to cure: the old per-page leg passed over 138 pages while asserting only
 * lang/title/viewport, so 133 missing og:image and 136 missing canonical were
 * invisible to CI. A silent green is not a census.
 */
const discoveryCensus = {
  pagesFull: 0, // held to the whole contract
  pagesShell: 0, // canonicalised onto a target page
  pagesNoindex: 0, // og block, no canonical, no sitemap entry
  pagesMirror: 0, // exempt while the in-file PROVENANCE declaration holds
  pagesOgComplete: 0, // all four required og tags, non-empty
  pagesCanonicalOk: 0, // canonical equals the page's published URL
  pagesInSitemap: 0, // its published URL appears as a <loc>
  sitemapLocs: 0,
  sitemapStamps: 0,
  bytePinnedOk: 0, // of robots.txt + llms.txt
};

function fail(file, message) {
  failures.push(`${file}: ${message}`);
}

function decodeHtml(value) {
  return value
    .replaceAll("&amp;", "&")
    .replaceAll("&#38;", "&")
    .replaceAll("&#x2F;", "/")
    .replaceAll("&#47;", "/");
}

function isExternal(value) {
  return (
    /^[a-z][a-z0-9+.-]*:/i.test(value) ||
    value.startsWith("//") ||
    value.startsWith("#") ||
    value.startsWith("?") ||
    value.includes("{{") ||
    value.includes("${")
  );
}

function insideRoot(path) {
  const rel = relative(root, path);
  return rel === "" || (!rel.startsWith(`..${sep}`) && rel !== ".." && !isAbsolute(rel));
}

function candidatesFor(pathname, attr) {
  if (attr !== "href" || extname(pathname)) return [pathname];
  if (pathname.endsWith(sep)) return [resolve(pathname, "index.html")];
  return [pathname, `${pathname}.html`, resolve(pathname, "index.html")];
}

function targetExists(pathname, attr) {
  for (const candidate of candidatesFor(pathname, attr)) {
    const candidateRelative = relative(root, candidate).split(sep).join("/");
    if (trackedFileSet.has(candidateRelative)) return true;
    const indexRelative = relative(root, resolve(candidate, "index.html"))
      .split(sep)
      .join("/");
    if (trackedFileSet.has(indexRelative)) return true;
  }
  return false;
}

function verifyPublishedPath(file, value, label, attr = "href") {
  if (typeof value !== "string" || !value) {
    fail(file, `${label} is missing or empty`);
    return;
  }
  if (isExternal(value)) return;
  if (value.startsWith("/")) {
    fail(file, `${label}="${value}" escapes the /art/ GitHub Pages base`);
    return;
  }

  const pathname = value.split(/[?#]/, 1)[0];
  let decodedPath;
  try {
    decodedPath = decodeURIComponent(pathname);
  } catch {
    fail(file, `${label}="${value}" contains invalid URL encoding`);
    return;
  }
  const target = resolve(dirname(resolve(root, file)), decodedPath || ".");
  if (!insideRoot(target)) {
    fail(file, `${label}="${value}" resolves outside the published repository`);
  } else if (!targetExists(target, attr)) {
    fail(file, `${label}="${value}" has no tracked static target`);
  }
}

/**
 * Discovery-metadata legs (RSI40-1102/CS1). Three page classes, decided by the
 * generator's own predicates: a `robots: noindex` page must carry no canonical
 * and stay out of the sitemap; a meta-refresh redirect shell must carry a
 * canonical that lands on a tracked target and gets no og block of its own; a
 * declared cross-repo mirror is exempt entirely, but only while the in-file
 * PROVENANCE declaration still holds (`exemptionHolds`). Everything else is
 * held to the full contract.
 */
const REQUIRED_OG_TAGS = ["og:title", "og:description", "og:image", "og:url"];

function readTracked(file) {
  return readFileSync(resolve(root, file), "utf8");
}

function metaContentOf(source, name) {
  const namePattern = new RegExp(`(?:name|property)=["']${name}["']`, "i");
  for (const tag of source.match(/<meta\b[\s\S]*?(?:\/>|>)/gi) ?? []) {
    if (!namePattern.test(tag)) continue;
    const content = tag.match(/content=(["'])([\s\S]*?)\1/i)?.[2];
    if (content !== undefined) return content;
  }
  return null;
}
function canonicalHrefOf(source) {
  const link = (source.match(/<link\b[\s\S]*?(?:\/>|>)/gi) ?? []).find((tag) =>
    /\brel=["']canonical["']/i.test(tag),
  );
  return link ? (link.match(/href=["']([^"']*)["']/i)?.[1] ?? "") : null;
}

function verifyDiscoveryMetadata(file, source) {
  if (exemptionHolds(file, source)) {
    discoveryCensus.pagesMirror += 1;
    return;
  }

  if (redirectTarget(file, source, trackedFileSet) !== null) {
    discoveryCensus.pagesShell += 1;
    const href = canonicalHrefOf(source);
    const expected = canonicalFor(file, source, trackedFileSet);
    if (href === null) {
      fail(file, "meta-refresh redirect shell carries no rel=canonical onto its target page");
    } else if (href !== expected) {
      fail(
        file,
        `redirect shell canonical="${href}" does not collapse onto its target's canonical="${expected}"`,
      );
    }
    return;
  }

  discoveryCensus.pagesFull += 1;
  let ogPresent = 0;
  for (const name of REQUIRED_OG_TAGS) {
    const found = metaContentOf(source, name);
    if (found && found.trim()) ogPresent += 1;
    if (!found) {
      fail(file, `missing <meta property="${name}"> (fix: node scripts/complete-metadata.mjs)`);
    } else if (!found.trim()) {
      fail(file, `<meta property="${name}"> is empty`);
    }
  }

  const description = metaContentOf(source, "description");
  if (!description) {
    fail(file, 'missing <meta name="description"> (fix: node scripts/complete-metadata.mjs)');
  } else if (!description.trim()) {
    fail(file, '<meta name="description"> is empty');
  }

  if (ogPresent === REQUIRED_OG_TAGS.length) discoveryCensus.pagesOgComplete += 1;

  const image = metaContentOf(source, "og:image");
  if (image) {
    const value = image.trim();
    if (!value.startsWith(`${SITE_ORIGIN}${SITE_BASE}/`)) {
      fail(file, `og:image="${value}" is not an absolute ${SITE_BASE}/ URL, which scrapers require`);
    } else if (!resolveRelative(value, file, trackedFileSet)) {
      fail(file, `og:image="${value}" resolves to no tracked file (it would 404)`);
    }
  }

  const href = canonicalHrefOf(source);
  const expected = canonicalFor(file, source, trackedFileSet);
  if (expected === null) {
    discoveryCensus.pagesNoindex += 1;
    if (href !== null) {
      fail(
        file,
        `noindex page must not publish rel=canonical="${href}" — a canonical asserts indexability`,
      );
    }
    return;
  }
  if (href === null) {
    fail(file, `missing rel=canonical="${expected}" (fix: node scripts/complete-metadata.mjs)`);
  } else if (href !== expected) {
    fail(file, `rel=canonical="${href}" is not the page's published URL "${expected}"`);
  } else {
    discoveryCensus.pagesCanonicalOk += 1;
  }

  if (sitemapLocs.has(expected)) discoveryCensus.pagesInSitemap += 1;
  if (!sitemapLocs.has(expected)) {
    fail(file, `has no ${SITEMAP_PATH} entry (fix: node scripts/build-discovery.mjs)`);
  }
}

/**
 * Root discovery documents: sitemap.xml, robots.txt, llms.txt. Two independent
 * legs — the committed bytes must equal what `build-discovery.mjs` produces
 * from this tree (staleness), and the committed `<loc>` set must agree with the
 * page set (parity), stated by parsing the file rather than by trusting the
 * generator's own bookkeeping.
 */
function verifyDiscoveryDocuments() {
  let generated;
  try {
    generated = discoveryFiles({ pages: htmlFiles, fileSet: trackedFileSet, read: readTracked });
  } catch (error) {
    fail(SITEMAP_PATH, `generator failed: ${error.message}`);
    return new Set();
  }

  // robots.txt and llms.txt are functions of the page set and the inventory file only,
  // so they are pinned byte-for-byte. sitemap.xml is NOT: its <lastmod> values come from
  // git history, and the commit that changes a page cannot also record its own date, so a
  // byte-pinned sitemap is stale by construction one commit before it can be written. Its
  // real invariant is the <loc> SET, swept against the page set below and per page above.
  for (const path of [ROBOTS_PATH, LLMS_PATH]) {
    const contents = generated.get(path);
    let committed = null;
    try {
      committed = readTracked(path);
    } catch {
      committed = null;
    }
    if (committed === null) {
      fail(path, `is missing (fix: node scripts/build-discovery.mjs)`);
    } else if (committed !== contents) {
      fail(
        path,
        `is stale — it does not match regeneration from this tree (fix: node scripts/build-discovery.mjs)`,
      );
    }
  }

  if (!generated.has(SITEMAP_PATH)) fail(SITEMAP_PATH, "the generator does not produce it");

  let sitemapSource;
  try {
    sitemapSource = readTracked(SITEMAP_PATH);
  } catch {
    return new Set();
  }

  const locs = [...sitemapSource.matchAll(/<loc>([\s\S]*?)<\/loc>/g)].map((match) => match[1].trim());
  const stamps = [...sitemapSource.matchAll(/<lastmod>([^<]*)<\/lastmod>/g)].map((m) => m[1].trim());
  for (const stamp of stamps) {
    if (!/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}[+-]\d{2}:\d{2}$/.test(stamp)) {
      fail(SITEMAP_PATH, `<lastmod>${stamp}</lastmod> is not an ISO-8601 offset date`);
    }
  }
  const locSet = new Set(locs);
  if (locSet.size !== locs.length) {
    fail(SITEMAP_PATH, `lists ${locs.length - locSet.size} duplicate <loc> entry(ies)`);
  }

  for (const loc of locs) {
    const page = pathForUrl(loc);
    if (page === null) {
      fail(SITEMAP_PATH, `<loc>${loc}</loc> is not under ${SITE_ORIGIN}${SITE_BASE}/`);
    } else if (!trackedFileSet.has(page)) {
      fail(SITEMAP_PATH, `<loc>${loc}</loc> maps to ${page}, which is not a tracked file`);
    }
  }

  const expected = new Set(sitemapEntries({ pages: htmlFiles, fileSet: trackedFileSet, read: readTracked }).entries.map((entry) => entry.url));
  for (const url of expected) {
    if (!locSet.has(url)) fail(SITEMAP_PATH, `indexable page ${url} has no sitemap entry`);
  }
  for (const loc of locSet) {
    if (!expected.has(loc)) fail(SITEMAP_PATH, `<loc>${loc}</loc> is not an indexable page of this tree`);
  }

  if (!sitemapSource.includes("<urlset") || !sitemapSource.includes("<url>")) {
    fail(SITEMAP_PATH, "is not a urlset with entries");
  }

  let robots;
  try {
    robots = readTracked(ROBOTS_PATH);
  } catch {
    robots = null;
  }
  if (robots !== null) {
    const declared = (robots.match(/^Sitemap:\s*(\S+)\s*$/im)?.[1] ?? "").trim();
    const declaredIsOurs =
      declared === `${SITE_ORIGIN}${SITE_BASE}/${SITEMAP_PATH}` ||
      declared === `${SITE_ORIGIN}/${SITEMAP_PATH}`;
    if (!declaredIsOurs) {
      fail(ROBOTS_PATH, `Sitemap: line points at "${declared || "(none)"}" — robots.txt must publish this site's own sitemap`);
    }
  }

  try {
    const llms = readTracked(LLMS_PATH);
    if (!llms.includes("/patent-portfolio/")) {
      fail(LLMS_PATH, "does not point at the Patent Museum (/patent-portfolio/)");
    }
    if (!/^- `P/m.test(llms)) {
      fail(LLMS_PATH, "carries no patent inventory entries");
    }
  } catch {
    /* absence already failed above */
  }

  discoveryCensus.sitemapLocs = locs.length;
  discoveryCensus.sitemapStamps = stamps.length;
  discoveryCensus.bytePinnedOk = [ROBOTS_PATH, LLMS_PATH].filter(
    (path) => !failures.some((f) => f.startsWith(`${path}: `)),
  ).length;

  return locSet;
}

function verifyDirectoryCounts(file, source) {
  const jumpCounts = new Map(
    [...source.matchAll(/href=["']#([^"']+)["'][^>]*>[\s\S]*?<span class=["']jn["']>(\d+)<\/span>/g)].map(
      (match) => [match[1], Number(match[2])],
    ),
  );
  let total = 0;

  for (const match of source.matchAll(
    /<section id=["']([^"']+)["'][\s\S]*?<span class=["']cnt["']>(\d+)<\/span>[\s\S]*?<ul class=["']grid["'][^>]*>([\s\S]*?)<\/ul>\s*<\/section>/g,
  )) {
    const [, id, displayedCount, cards] = match;
    const actualCount = (cards.match(/<li\b/g) ?? []).length;
    total += actualCount;
    if (Number(displayedCount) !== actualCount) {
      fail(file, `${id} heading says ${displayedCount}, but contains ${actualCount} cards`);
    }
    if (jumpCounts.get(id) !== actualCount) {
      fail(
        file,
        `${id} jump says ${jumpCounts.get(id) ?? "missing"}, but contains ${actualCount} cards`,
      );
    }
  }

  const totalClaims = [
    ["description", /directory of (\d+) small interactive works/i],
    ["filter status", /<p id=["']count["'][^>]*>(\d+) apps<\/p>/i],
    ["footer", /<div class=["']wrap["']>\s*(\d+) works\b/i],
  ];
  for (const [label, pattern] of totalClaims) {
    const claimed = source.match(pattern)?.[1];
    if (Number(claimed) !== total) {
      fail(file, `${label} says ${claimed ?? "missing"}, but the directory contains ${total} cards`);
    }
  }
}

// Root discovery documents are verified before the page loop: the per-page leg below
// asks the committed sitemap which pages it publishes, so that set must exist first.
sitemapLocs = verifyDiscoveryDocuments();

for (const file of htmlFiles) {
  const absoluteFile = resolve(root, file);
  const source = readFileSync(absoluteFile, "utf8");
  const publishedSource = source.replace(/<!--[\s\S]*?-->/g, "");

  if (!/<html\b[^>]*\blang=["'][^"']+["']/i.test(source)) {
    fail(file, "missing an explicit html lang attribute");
  }
  if (!/<title>[^<]+<\/title>/i.test(source)) {
    fail(file, "missing a non-empty title");
  }
  if (!/<meta\b[^>]*\bname=["']viewport["']/i.test(source)) {
    fail(file, "missing the responsive viewport meta tag");
  }
  verifyDiscoveryMetadata(file, source);
  if (file === "index.html") {
    verifyDirectoryCounts(file, publishedSource);
    const hasSkipLink = [...publishedSource.matchAll(/<a\b[^>]*>/gi)].some(
      ([tag]) =>
        /\bclass=["'][^"']*\bskip\b[^"']*["']/i.test(tag) &&
        /\bhref=["']#[^"']+["']/i.test(tag),
    );
    if (!hasSkipLink) {
      fail(file, "missing a skip link to in-page content");
    }
    if (!/<main\b/i.test(publishedSource)) {
      fail(file, "missing a main landmark");
    }
    for (const match of publishedSource.matchAll(/<a\b[^>]*\bclass=["'][^"']*\bcard\b[^"']*["'][^>]*>/gi)) {
      const tag = match[0];
      if (!/\bhref=["'][^"']+["']/.test(tag)) {
        fail(file, "directory card is missing an href");
      }
      if (!/\bdata-s=["'][^"']+["']/.test(tag)) {
        fail(file, "directory card is missing a searchable data-s attribute");
      }
    }
  }

  for (const match of publishedSource.matchAll(
    /(?:^|[\s<])(href|src|poster|action)=["']([^"'<>]+)["']/gi,
  )) {
    const attr = match[1].toLowerCase();
    const value = decodeHtml(match[2].trim());
    if (!value || isExternal(value)) continue;
    references += 1;

    if (value.startsWith("/")) {
      fail(
        file,
        `${attr}="${value}" escapes the /art/ GitHub Pages base; use a document-relative URL`,
      );
      continue;
    }

    const pathname = value.split(/[?#]/, 1)[0];
    let decodedPath;
    try {
      decodedPath = decodeURIComponent(pathname);
    } catch {
      fail(file, `${attr}="${value}" contains invalid URL encoding`);
      continue;
    }
    const target = resolve(dirname(absoluteFile), decodedPath || ".");
    if (!insideRoot(target)) {
      fail(file, `${attr}="${value}" resolves outside the published repository`);
      continue;
    }
    if (!targetExists(target, attr)) {
      fail(file, `${attr}="${value}" has no tracked static target`);
    }
  }
}

for (const file of manifestFiles) {
  let manifest;
  try {
    manifest = JSON.parse(readFileSync(resolve(root, file), "utf8"));
  } catch (error) {
    fail(file, `invalid JSON: ${error.message}`);
    continue;
  }

  verifyPublishedPath(file, manifest.start_url, "start_url");
  if (manifest.scope !== undefined) verifyPublishedPath(file, manifest.scope, "scope");
  for (const [index, icon] of (manifest.icons ?? []).entries()) {
    verifyPublishedPath(file, icon.src, `icons[${index}].src`, "src");
  }
  for (const [index, screenshot] of (manifest.screenshots ?? []).entries()) {
    verifyPublishedPath(file, screenshot.src, `screenshots[${index}].src`, "src");
  }
  for (const [index, shortcut] of (manifest.shortcuts ?? []).entries()) {
    verifyPublishedPath(file, shortcut.url, `shortcuts[${index}].url`);
    for (const [iconIndex, icon] of (shortcut.icons ?? []).entries()) {
      verifyPublishedPath(
        file,
        icon.src,
        `shortcuts[${index}].icons[${iconIndex}].src`,
        "src",
      );
    }
  }
}

for (const file of serviceWorkerFiles) {
  const source = readFileSync(resolve(root, file), "utf8").replace(/\/\*[\s\S]*?\*\//g, "");
  if (/(["'])\/(?!\/)/.test(source)) {
    fail(file, "contains a root-relative URL that escapes its GitHub Pages app scope");
  }
  if (
    /\.filter\(\s*([A-Za-z_$][\w$]*)\s*=>\s*\1\s*!==\s*(?:CACHE|CACHE_NAME)\s*\)/.test(
      source,
    )
  ) {
    fail(file, "cache activation can delete caches owned by sibling apps");
  }
  for (const match of source.matchAll(/(["'])(\.\.?\/[^"']*)\1/g)) {
    verifyPublishedPath(file, match[2], `service-worker asset`, "src");
  }
}

// Corpus statistics gate. `wiles/index.html` published four hand-typed
// numbers about the hong Lean corpus and all four had drifted, including a
// "13 sorry" tile over a corpus that is sorry-free with 45 open scientific
// goals. The numbers are generated now; this makes the page unable to
// disagree with the compiler without failing the build. Where no proof report
// exists (CI, fresh clone) the child prints SKIPPED and exits 0 — an absence
// of evidence, which reads as such in the log, not as a pass. Where the report
// exists but carries no number for a tile (schema-v4 rows may omit theorem and
// open-goal counts while the native inventory resolves), the child prints
// UNMEASURED, leaves that tile alone, and gates only the measured tiles — a
// missing count never becomes a published NaN or a fabricated "0 sorry".
{
  const { spawnSync } = await import("node:child_process");
  const gate = spawnSync(
    process.execPath,
    [new URL("./sync-corpus-stats.mjs", import.meta.url).pathname, "--check"],
    { encoding: "utf8" },
  );
  if (gate.stdout) process.stdout.write(gate.stdout);
  if (gate.status !== 0) {
    if (gate.stderr) process.stderr.write(gate.stderr);
    failures.push(
      "wiles/index.html: corpus statistics disagree with /tmp/proof-report.json " +
        "(fix: node scripts/sync-corpus-stats.mjs)",
    );
  }
}

const discoveryLine =
  `discovery: ${htmlFiles.length} tracked pages - ` +
  `${discoveryCensus.pagesFull} held to the full contract ` +
  `(${discoveryCensus.pagesOgComplete} with all ${REQUIRED_OG_TAGS.length} og tags, ` +
  `${discoveryCensus.pagesCanonicalOk} with a matching rel=canonical, ` +
  `${discoveryCensus.pagesInSitemap} with a sitemap entry), ` +
  `${discoveryCensus.pagesShell} redirect shell(s) canonicalised onto a target, ` +
  `${discoveryCensus.pagesNoindex} noindex page(s) with no canonical, ` +
  `${discoveryCensus.pagesMirror} declared mirror(s) exempt; ` +
  `${SITEMAP_PATH} publishes ${discoveryCensus.sitemapLocs} <loc> and ` +
  `${discoveryCensus.sitemapStamps} <lastmod>; ` +
  `${discoveryCensus.bytePinnedOk}/2 of robots.txt + llms.txt byte-identical to regeneration`;

if (failures.length > 0) {
  console.error(discoveryLine);
  console.error(
    `site integrity: ${failures.length} failure(s) across ${htmlFiles.length} HTML files:`,
  );
  for (const failure of failures) console.error(`  - ${failure}`);
  process.exit(1);
}

console.log(discoveryLine);
console.log(
  `site integrity: ${htmlFiles.length} HTML files, ${manifestFiles.length} manifests, ` +
    `${serviceWorkerFiles.length} service workers, and ${references} local references verified`,
);
