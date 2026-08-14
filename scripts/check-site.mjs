#!/usr/bin/env node

import { execFileSync } from "node:child_process";
import { readFileSync } from "node:fs";
import { dirname, extname, isAbsolute, relative, resolve, sep } from "node:path";
import { fileURLToPath } from "node:url";

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
let references = 0;

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

if (failures.length > 0) {
  console.error(
    `site integrity: ${failures.length} failure(s) across ${htmlFiles.length} HTML files:`,
  );
  for (const failure of failures) console.error(`  - ${failure}`);
  process.exit(1);
}

console.log(
  `site integrity: ${htmlFiles.length} HTML files, ${manifestFiles.length} manifests, ` +
    `${serviceWorkerFiles.length} service workers, and ${references} local references verified`,
);
