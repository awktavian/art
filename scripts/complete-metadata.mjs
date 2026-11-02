#!/usr/bin/env node

/**
 * scripts/complete-metadata.mjs — per-page discovery metadata completion.
 *
 * WHY. `https://awktavian.github.io/art/` is live and its 138 tracked HTML
 * documents all carry a <title>, but the discovery half of their <head> was
 * never written: RSI40-1102/R40 measured `rel="canonical"` on 2 of 138 pages
 * and `og:image` on 5, and the per-page leg of `scripts/check-site.mjs`
 * asserted only lang/title/viewport — so an absent og:image was invisible to
 * CI (the root cause the SL2 board names CS-GATE1). This module is the
 * authoring half of that pair; `check-site.mjs` imports these same functions
 * as the gate half, so the page set and the expected-tag vocabulary have
 * exactly ONE owner and the gate never re-derives them by hand.
 *
 * WHAT IT WRITES, per tracked HTML page, only when the tag is absent:
 *   <meta name="description">        <- existing description, else the page's own <h1>
 *   <meta property="og:url">         <- the page's canonical URL
 *   <meta property="og:title">       <- the page's own <title> text
 *   <meta property="og:description"> <- as above
 *   <meta property="og:image">       <- see IMAGE RULE
 *   <link rel="canonical">           <- see URL RULE
 * plus two repair cases: an og:image that resolves to a tracked file but is
 * written as a relative URL is normalised to its absolute form, and an
 * og:image whose target is NOT tracked is replaced (see rule 3 of IMAGE RULE).
 *
 * URL RULE. GitHub Pages serves this repository as a PROJECT page, so every
 * published URL is prefixed `/art/` (AGENTS.md "Canonical site"; verified
 * live at lane time: `/art/`, `/art/home.html`, `/art/forge.html` -> 200
 * while the host root `awktavian.github.io/` -> 404). `<dir>/index.html`
 * canonicalises to the DIRECTORY form `<origin>/art/<dir>/` and the root
 * `index.html` to `<origin>/art/`, because that is what the only two pages
 * that already carry a canonical do (`blog/smarthome/index.html` and
 * `home/index.html`, measured at this base): the script follows the house
 * precedent instead of inventing a second shape.
 *
 * THREE PAGE CLASSES, each with its own treatment (all three are measured
 * facts about this tree, not hypotheticals):
 *   - noindex   (`robots` meta containing `noindex`; 1 page measured:
 *                 `jail-speech/deep-dive.html`) gets the og tags and the
 *                 description but NO canonical, because a canonical asserts
 *                 indexability and contradicts noindex. Excluded from the
 *                 sitemap by `build-discovery.mjs`.
 *   - redirect shell (`meta http-equiv="refresh"`; 3 pages measured:
 *                 `get-a-job.html`, `home.html`, `octoni-on.html` — the same
 *                 three NOTES.md "skipped-redirects" records) gets exactly
 *                 one tag: a canonical pointing at its TARGET page's canonical
 *                 URL, which is how the duplicate-content pair is collapsed
 *                 for crawlers. It gets no og block (a shell is not the
 *                 document a preview should describe) and no sitemap entry of
 *                 its own — its target's entry already is that URL.
 *   - declared mirror (`patent-portfolio/test.html`, whose in-file PROVENANCE
 *                 comment and NOTES.md "skipped-mirror" row make it a
 *                 byte-identical copy of `awkronos/patents/test.html` with the
 *                 canonical owner in the OTHER repository). Nothing is written
 *                 to it and it is out of the sitemap. The exemption is guarded
 *                 rather than free: `exemptionHolds()` requires the PROVENANCE
 *                 declaration to still be in the file, so a mirror that stops
 *                 declaring itself comes back under the gate.
 *
 * IMAGE RULE, first match wins:
 *   1. the page's existing og:image, if it resolves to a tracked file;
 *   2. the first image the page itself already loads via src=/poster= that
 *      resolves to a tracked file (the page's own hero, in document order);
 *   3. the site-level default card, `favicon.svg` — the 鏡 Kagami gold-on-void
 *      mark that 74 of these 138 pages already link as their icon, and the
 *      only image at the repository root that is site-level rather than one
 *      project's content.
 * Every emitted value is absolute. Rule 3 is what repairs the two pre-existing
 * dangling references measured at this base (`figma/index.html` ->
 * `og-image.png`, `mop/index.html` -> `og-image.jpg`: neither file is tracked,
 * so both 404, and R40's og:image count of 5 includes them). No page is ever
 * given an image URL that does not exist.
 *
 * DISCLOSURE. `favicon.svg` is an SVG and the big scrapers (Facebook, X)
 * render only raster og:image values, so for the majority of pages (the exact
 * count is printed under "og:image by rule") the card is a real-but-generic
 * fallback, not a page-specific 1200x630 preview. Replacing it is a
 * one-constant change to DEFAULT_OG_IMAGE once a raster card exists; re-run
 * this script and the gate re-verifies. The high ratio is the honest shape of
 * a site whose pages are canvas/WebGL scenes with no raster hero to borrow.
 *
 * The work order suggested `generate_app_icons.py` as an image source. That
 * script is NOT part of this repository: `git ls-files` over all 938 tracked
 * paths has no match for it (it lives in the kagami repo, where it renders the
 * lineage-pinned Kagami app-icon set from `assets/brand/app-icon/master-1024.png`
 * and is documented there as untouchable without a Tim turn). Reaching across
 * repositories to raster a new binary into this tree would also break this
 * repository's no-build-step rule, so rule 3 took the order's sanctioned
 * alternative - one of the repo's EXISTING image assets - and discloses it
 * instead of inventing a card that is not there.
 *
 * IDEMPOTENT. Re-running on an unchanged tree writes nothing and prints
 * "0 file(s) would change". `--check` exits 1 when anything would change.
 *
 * Usage:
 *   node scripts/complete-metadata.mjs            # write in place
 *   node scripts/complete-metadata.mjs --dry-run  # report, write nothing
 *   node scripts/complete-metadata.mjs --check    # exit 1 if any file would change
 */

import { execFileSync } from "node:child_process";
import { readFileSync, writeFileSync } from "node:fs";
import { dirname, extname, resolve, sep } from "node:path";
import { fileURLToPath } from "node:url";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");

/** Canonical deployment: the GitHub Pages project page for repository `art`. */
export const SITE_ORIGIN = "https://awktavian.github.io";
export const SITE_BASE = "/art";
/** Repository-relative path of the site-level fallback card. */
export const DEFAULT_OG_IMAGE = "favicon.svg";
/** Paths whose <head> another owner holds; see the declared-mirror note above. */
export const DECLARED_MIRRORS = Object.freeze(["patent-portfolio/test.html"]);

const IMAGE_EXTENSIONS = new Set([".png", ".jpg", ".jpeg", ".webp", ".gif", ".svg"]);
const MARKER = "discovery-metadata: generated by scripts/complete-metadata.mjs";
/** og:description is meant to be a sentence or two; 200 keeps the card honest. */
const DESCRIPTION_LIMIT = 200;

export function trackedFiles(cwd = root) {
  return execFileSync("git", ["ls-files", "-z"], { cwd, encoding: "utf8" })
    .split("\0")
    .filter(Boolean);
}

/**
 * The page set, with the same two exclusions as `check-site.mjs`: `medverify/`
 * is a separate repository that is not published here (AGENTS.md) and
 * `playwright-report/` output is not a document.
 */
export function htmlPages(files) {
  return files
    .filter((file) => file.endsWith(".html"))
    .filter((file) => !file.startsWith("medverify/"))
    .filter((file) => !file.includes("/playwright-report/"))
    .sort();
}

/** `<origin>/art/...` for a repository-relative page path (directory form for index.html). */
export function urlForPath(file) {
  const segments = file.split("/");
  if (segments.at(-1) !== "index.html") {
    return `${SITE_ORIGIN}${SITE_BASE}/${encodePath(segments.join("/"))}`;
  }
  segments.pop();
  return segments.length === 0
    ? `${SITE_ORIGIN}${SITE_BASE}/`
    : `${SITE_ORIGIN}${SITE_BASE}/${encodePath(segments.join("/"))}/`;
}

/** Repository-relative page path a `<origin>/art/...` URL maps back to, or null. */
export function pathForUrl(url) {
  const prefix = `${SITE_ORIGIN}${SITE_BASE}/`;
  if (!url.startsWith(prefix)) return null;
  const rest = decodeURIComponent(url.slice(prefix.length));
  if (rest === "") return "index.html";
  if (url.endsWith("/")) return `${rest}index.html`;
  return rest;
}

function encodePath(path) {
  return path
    .split("/")
    .map((segment) => encodeURIComponent(segment))
    .join("/");
}

export function isNoIndex(source) {
  return /<meta\b[^>]*name=["']robots["'][^>]*content=["'][^"']*\bnoindex\b[^"']*["']/i.test(
    source,
  );
}

/** The page a meta-refresh shell forwards to, as a tracked path, or null. */
export function redirectTarget(file, source, fileSet) {
  const tag = metaTags(source).find((candidate) => /\bhttp-equiv=["']refresh["']/i.test(candidate));
  if (!tag) return null;
  const url = attributeOf(tag, "content")?.match(/url\s*=\s*(["']?)([^\s"'<>]+)\1/i)?.[2];
  if (!url) return null;
  const resolved = resolveRelative(url, file, fileSet);
  if (!resolved) return null;
  return fileSet.has(resolved) ? resolved : null;
}

export function isRedirectShell(file, source, fileSet) {
  return redirectTarget(file, source, fileSet) !== null;
}

/** True while the file still carries its cross-repo mirror declaration. */
export function exemptionHolds(file, source) {
  return DECLARED_MIRRORS.includes(file) && /PROVENANCE/.test(source);
}

/**
 * Canonical URL a page should carry, or null when it should carry none
 * (noindex pages). Redirect shells resolve to their target's canonical.
 */
export function canonicalFor(file, source, fileSet) {
  if (isNoIndex(source) || exemptionHolds(file, source)) return null;
  const target = redirectTarget(file, source, fileSet);
  return target ? urlForPath(target) : urlForPath(file);
}

/**
 * The pages the sitemap describes: every tracked page except a noindex page,
 * a declared mirror, and a redirect shell (whose canonical URL is already
 * present as its target's entry). Deduplicated by canonical URL.
 */
export function sitemapPages(pages, readSource, fileSet) {
  const seen = new Map();
  const skipped = { noindex: [], mirror: [], shell: [] };
  for (const file of pages) {
    const source = readSource(file);
    if (exemptionHolds(file, source)) {
      skipped.mirror.push(file);
      continue;
    }
    if (isNoIndex(source)) {
      skipped.noindex.push(file);
      continue;
    }
    const canonical = canonicalFor(file, source, fileSet);
    if (redirectTarget(file, source, fileSet)) {
      skipped.shell.push(file);
      // Still keep the target's own entry; the shell adds nothing.
      continue;
    }
    if (canonical && !seen.has(canonical)) seen.set(canonical, file);
  }
  return { entries: [...seen].map(([url, file]) => ({ url, file })), skipped };
}

function metaTags(source) {
  return [...source.matchAll(/<meta\b[\s\S]*?(?:\/>|>)/gi)].map((match) => match[0]);
}

function attributeOf(tag, name) {
  const match = tag.match(new RegExp(`\\b${name}=["']([\\s\\S]*?)["']`, "i"));
  return match ? match[1] : null;
}

/** Raw attribute text of a <meta> tag matched by `predicate(name, content)`. */
function findMeta(source, predicate) {
  for (const tag of metaTags(source)) {
    const name = attributeOf(tag, "name") ?? attributeOf(tag, "property") ?? attributeOf(tag, "http-equiv");
    if (!name) continue;
    const content = attributeOf(tag, "content");
    if (content !== null && predicate(name, content, tag)) return { name, content, tag };
  }
  return null;
}

export function pageTitle(source) {
  const raw = source.match(/<title\b[^>]*>([\s\S]*?)<\/title>/i)?.[1] ?? null;
  return raw === null ? null : collapse(raw);
}

export function pageDescription(source) {
  return findMeta(source, (name) => name.toLowerCase() === "description")?.content ?? null;
}

export function existingOgImageTag(source) {
  return findMeta(source, (name) => name.toLowerCase() === "og:image");
}

/**
 * Description text for a page with no meta description: its own <h1>, tags
 * stripped. A quote from the document, not a sentence invented about it.
 */
export function pageHeading(source) {
  const raw = source.match(/<h1\b[^>]*>([\s\S]*?)<\/h1>/i)?.[1];
  if (!raw) return null;
  return collapse(raw.replace(/<[^>]+>/g, " "));
}

/** Absolute image URL for a page, plus which IMAGE RULE clause fired. */
export function ogImageFor(file, source, fileSet) {
  const declared = existingOgImageTag(source);
  const declaredRelative = declared
    ? resolveRelative(declared.content, file, fileSet)
    : null;
  if (declared && declaredRelative) {
    return {
      url: assetUrl(declaredRelative),
      relative: declaredRelative,
      rule: "1-existing",
      dangling: false,
      needsNormalise: declared.content.trim() !== assetUrl(declaredRelative),
    };
  }
  const own = firstOwnImage(file, source, fileSet);
  if (own) {
    return {
      url: assetUrl(own),
      relative: own,
      rule: "2-page-hero",
      dangling: Boolean(declared),
      needsNormalise: Boolean(declared),
    };
  }
  return {
    url: assetUrl(DEFAULT_OG_IMAGE),
    relative: DEFAULT_OG_IMAGE,
    rule: "3-site-default-card",
    dangling: Boolean(declared),
    needsNormalise: Boolean(declared),
  };
}

/** Repository-relative path a reference resolves to, only when it is tracked. */
export function resolveRelative(value, file, fileSet) {
  const trimmed = String(value).trim();
  if (!trimmed) return null;
  const prefix = `${SITE_ORIGIN}${SITE_BASE}/`;
  let path;
  if (/^https?:/i.test(trimmed)) {
    if (!trimmed.startsWith(prefix)) return null;
    path = decodeURIComponent(trimmed.slice(prefix.length)).replace(/^\/+/, "");
    if (path === "") return null;
  } else if (trimmed.startsWith("/")) {
    return null;
  } else {
    const decoded = safeDecodeURIComponent(trimmed.split(/[?#]/, 1)[0]);
    if (decoded === null) return null;
    path = resolve(dirname(resolve(root, file)), decoded)
      .slice(root.length + 1)
      .split(sep)
      .join("/");
  }
  return fileSet.has(path) ? path : null;
}

function safeDecodeURIComponent(value) {
  try {
    return decodeURIComponent(value);
  } catch {
    return null;
  }
}

export function assetUrl(relativePath) {
  return `${SITE_ORIGIN}${SITE_BASE}/${encodePath(relativePath)}`;
}

/** First image the page itself loads, in document order, that is tracked. */
export function firstOwnImage(file, source, fileSet) {
  const published = source.replace(/<!--[\s\S]*?-->/g, "");
  for (const match of published.matchAll(/(?:^|[\s<])(?:src|poster)=["']([^"'<>]+)["']/gi)) {
    const value = match[1].trim();
    if (!IMAGE_EXTENSIONS.has(extname(value.split(/[?#]/, 1)[0]).toLowerCase())) continue;
    const resolved = resolveRelative(value, file, fileSet);
    if (resolved) return resolved;
  }
  return null;
}

function collapse(value) {
  return value.replace(/\s+/g, " ").trim();
}

/** Escape for an HTML attribute value, leaving existing character references alone. */
export function escapeAttribute(value) {
  return String(value)
    .replace(/&(?!#[0-9]{1,7};|#x[0-9a-fA-F]{1,6};|[a-zA-Z][a-zA-Z0-9]*;)/g, "&amp;")
    .replace(/"/g, "&quot;");
}

function truncate(value) {
  if (value.length <= DESCRIPTION_LIMIT) return value;
  const window = value.slice(0, DESCRIPTION_LIMIT + 1);
  const boundary = window.lastIndexOf(" ");
  const cut = boundary > 80 ? window.slice(0, boundary) : window.slice(0, DESCRIPTION_LIMIT);
  return `${cut.trimEnd()}…`;
}

/**
 * The tags a page is missing. Returns `{ lines, added, image, descriptionSource }`
 * where `added` names each action for the report and `image.rule` says which
 * IMAGE RULE clause supplied the card.
 */
export function missingTags({ file, source, fileSet }) {
  if (exemptionHolds(file, source)) {
    return { lines: [], added: [], image: null, descriptionSource: "exempt-mirror" };
  }

  const canonical = canonicalFor(file, source, fileSet);
  const shell = redirectTarget(file, source, fileSet) !== null;

  if (shell) {
    // A meta-refresh shell gets one thing only: a canonical that collapses it
    // onto its target. No og block, because the shell is not the document.
    if (canonical && /<link\b[^>]*rel=["']canonical["']/i.test(source)) {
      return { lines: [], added: [], image: null, descriptionSource: "redirect-shell" };
    }
    const lines = canonical ? [`<link rel="canonical" href="${canonical}">`] : [];
    return {
      lines,
      added: canonical ? ["canonical(redirect-shell)"] : [],
      image: null,
      descriptionSource: "redirect-shell",
    };
  }

  const image = ogImageFor(file, source, fileSet);
  const title = pageTitle(source);
  const declaredDescription = pageDescription(source);
  const heading = declaredDescription ? null : pageHeading(source);
  const description = declaredDescription ?? (heading ? truncate(escapeAttribute(heading)) : null);

  const lines = [];
  const added = [];

  if (!declaredDescription && description) {
    lines.push(`<meta name="description" content="${description}">`);
    added.push("meta:description");
  }
  if (!findMeta(source, (name) => name.toLowerCase() === "og:url")) {
    lines.push(`<meta property="og:url" content="${canonical ?? urlForPath(file)}">`);
    added.push("og:url");
  }
  if (!findMeta(source, (name) => name.toLowerCase() === "og:title")) {
    lines.push(`<meta property="og:title" content="${escapeAttribute(title ?? "")}">`);
    added.push(title ? "og:title" : "og:title(NO-TITLE)");
  }
  if (!findMeta(source, (name) => name.toLowerCase() === "og:description")) {
    if (description) {
      lines.push(`<meta property="og:description" content="${description}">`);
      added.push("og:description");
    } else {
      added.push("og:description(NO-SOURCE-TEXT)");
    }
  }
  const declaredImage = existingOgImageTag(source);
  if (!declaredImage) {
    lines.push(`<meta property="og:image" content="${image.url}">`);
    added.push("og:image");
  } else if (declaredImage.content.trim() !== image.url) {
    added.push(image.dangling ? "og:image(repair-dangling)" : "og:image(normalise-absolute)");
  }
  if (!canonical) {
    if (isNoIndex(source) && /<link\b[^>]*rel=["']canonical["']/i.test(source)) {
      added.push("canonical(REMOVE:page-is-noindex)");
    }
  } else if (!/<link\b[^>]*rel=["']canonical["']/i.test(source)) {
    lines.push(`<link rel="canonical" href="${canonical}">`);
    added.push("canonical");
  }

  return {
    lines,
    added,
    image,
    descriptionSource: declaredDescription ? "meta" : heading ? "h1" : "none",
    imageRepair: declaredImage && declaredImage.content.trim() !== image.url ? declaredImage : null,
  };
}

/**
 * Where the generated block is spliced in: after the last <meta> line already
 * in the <head> (so the block joins the existing metadata cluster), falling
 * back to after the <title> line, then to just before </head>.
 */
function insertionOffset(source) {
  const headEnd = source.search(/<\/head>/i);
  const region = headEnd === -1 ? source : source.slice(0, headEnd);
  const metas = [...region.matchAll(/<meta\b[\s\S]*?(?:\/>|>)/gi)];
  let anchor = metas.length ? metas.at(-1).index + metas.at(-1)[0].length : -1;
  if (anchor === -1) {
    const title = region.match(/<title\b[^>]*>[\s\S]*?<\/title>/i);
    anchor = title ? title.index + title[0].length : -1;
  }
  if (anchor === -1) return headEnd === -1 ? source.length : region.lastIndexOf("\n", headEnd);
  const lineEnd = source.indexOf("\n", anchor);
  return lineEnd === -1 ? source.length : lineEnd;
}

/** Apply every completion for one page. Never writes; the caller decides. */
export function completeSource({ file, source, fileSet }) {
  const { lines, added, image, descriptionSource, imageRepair } = missingTags({
    file,
    source,
    fileSet,
  });
  if (lines.length === 0 && !imageRepair) {
    return { source, changed: false, added, image, descriptionSource };
  }

  let next = source;
  if (imageRepair) {
    // Rewrite the content attribute of the matched og:image tag in place.
    const tagText = imageRepair.tag;
    const index = next.indexOf(tagText);
    if (index !== -1) {
      const rewritten = tagText.replace(/content=(["'])[\s\S]*?\1/i, `content="${image.url}"`);
      next = `${next.slice(0, index)}${rewritten}${next.slice(index + tagText.length)}`;
    }
  }

  if (lines.length > 0) {
    const lineEnd = insertionOffset(next);
    const lineStart = next.lastIndexOf("\n", lineEnd - 1) + 1;
    const indent = next.slice(lineStart).match(/^[ \t]*/)?.[0] ?? "";
    const block = [
      "",
      ...lines.map((line) => `${indent}${line}`),
      `${indent}<!-- ${MARKER} -->`,
    ].join("\n");
    next = `${next.slice(0, lineEnd)}${block}${next.slice(lineEnd)}`;
  }

  return { source: next, changed: true, added, image, descriptionSource };
}

function run({ write }) {
  const files = trackedFiles();
  const fileSet = new Set(files);
  const pages = htmlPages(files);
  const report = {
    pages: pages.length,
    changedFiles: 0,
    added: new Map(),
    imageRules: new Map(),
    repairs: [],
    unwritten: [],
  };

  for (const file of pages) {
    const source = readFileSync(resolve(root, file), "utf8");
    const result = completeSource({ file, source, fileSet });
    for (const tag of result.added) report.added.set(tag, (report.added.get(tag) ?? 0) + 1);
    if (result.image) {
      report.imageRules.set(result.image.rule, (report.imageRules.get(result.image.rule) ?? 0) + 1);
    }
    for (const tag of result.added) {
      if (tag.includes("NO-") || tag.startsWith("canonical(REMOVE")) {
        report.unwritten.push(`${file}: ${tag}`);
      }
    }
    if (result.added.some((tag) => tag.startsWith("og:image("))) {
      report.repairs.push(`${file}: ${result.added.find((tag) => tag.startsWith("og:image("))} -> ${result.image?.url}`);
    }
    if (result.changed) {
      report.changedFiles += 1;
      if (write) writeFileSync(resolve(root, file), result.source, "utf8");
    }
  }

  return report;
}

function bucket(map) {
  return (
    [...map.entries()]
      .sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]))
      .map(([key, value]) => `${key}=${value}`)
      .join(" ") || "none"
  );
}

function printReport(report, mode) {
  console.log(
    [
      `complete-metadata (${mode}): ${report.pages} tracked HTML pages, ${report.changedFiles} file(s) ${
        mode === "write" ? "written" : "would change"
      }`,
      `  tags: ${bucket(report.added)}`,
      `  og:image by rule: ${bucket(report.imageRules)}`,
    ].join("\n"),
  );
  if (report.repairs.length) {
    console.log(`  og:image repairs (${report.repairs.length}):`);
    for (const line of report.repairs) console.log(`    - ${line}`);
  }
  if (report.unwritten.length) {
    console.log(`  UNWRITABLE (no source text / contradictory state — the gate will stay red here):`);
    for (const line of report.unwritten) console.log(`    - ${line}`);
  }
}

const invokedDirectly =
  process.argv[1] && resolve(process.argv[1]) === resolve(fileURLToPath(import.meta.url));

if (invokedDirectly) {
  const args = new Set(process.argv.slice(2));
  const mode = args.has("--check") ? "check" : args.has("--dry-run") ? "dry-run" : "write";
  const report = run({ write: mode === "write" });
  printReport(report, mode);
  if (mode === "check" && report.changedFiles > 0) {
    console.error(`fix: node scripts/complete-metadata.mjs`);
    process.exit(1);
  }
}
