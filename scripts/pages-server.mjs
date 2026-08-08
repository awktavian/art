#!/usr/bin/env node

import { createReadStream } from "node:fs";
import { access, stat } from "node:fs/promises";
import { createServer } from "node:http";
import { dirname, extname, join, resolve, sep } from "node:path";
import { fileURLToPath } from "node:url";

const repoRoot = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const mountPrefix = "/art";
const host = process.env.PAGES_HOST ?? "127.0.0.1";
const port = Number(process.env.PAGES_PORT ?? 4173);

const mimeTypes = {
  ".css": "text/css; charset=utf-8",
  ".gif": "image/gif",
  ".html": "text/html; charset=utf-8",
  ".ico": "image/x-icon",
  ".jpeg": "image/jpeg",
  ".jpg": "image/jpeg",
  ".js": "text/javascript; charset=utf-8",
  ".json": "application/json; charset=utf-8",
  ".mp3": "audio/mpeg",
  ".mp4": "video/mp4",
  ".png": "image/png",
  ".svg": "image/svg+xml",
  ".txt": "text/plain; charset=utf-8",
  ".wasm": "application/wasm",
  ".webmanifest": "application/manifest+json; charset=utf-8",
  ".woff": "font/woff",
  ".woff2": "font/woff2",
  ".xml": "application/xml; charset=utf-8",
};

async function exists(path) {
  try {
    await access(path);
    return true;
  } catch {
    return false;
  }
}

async function resolvePublishedPath(urlPath) {
  if (urlPath === mountPrefix) {
    urlPath = `${mountPrefix}/`;
  }
  if (!urlPath.startsWith(`${mountPrefix}/`)) {
    return null;
  }

  let relativePath = decodeURIComponent(urlPath.slice(mountPrefix.length));
  if (relativePath.startsWith("/")) relativePath = relativePath.slice(1);
  if (!relativePath) relativePath = "index.html";

  const candidates = [];
  if (relativePath.endsWith("/")) {
    candidates.push(join(repoRoot, relativePath, "index.html"));
  } else if (!extname(relativePath)) {
    candidates.push(join(repoRoot, relativePath));
    candidates.push(join(repoRoot, `${relativePath}.html`));
    candidates.push(join(repoRoot, relativePath, "index.html"));
  } else {
    candidates.push(join(repoRoot, relativePath));
  }

  for (const candidate of candidates) {
    const resolved = resolve(candidate);
    if (resolved !== repoRoot && !resolved.startsWith(`${repoRoot}${sep}`)) {
      continue;
    }
    if (await exists(resolved)) {
      const info = await stat(resolved);
      if (info.isFile()) return resolved;
    }
  }

  return null;
}

const server = createServer(async (request, response) => {
  try {
    const url = new URL(request.url ?? "/", `http://${host}:${port}`);
    const filePath = await resolvePublishedPath(url.pathname);
    if (!filePath) {
      response.writeHead(404, { "Content-Type": "text/plain; charset=utf-8" });
      response.end("Not Found");
      return;
    }

    response.writeHead(200, {
      "Content-Type": mimeTypes[extname(filePath)] ?? "application/octet-stream",
    });
    createReadStream(filePath).pipe(response);
  } catch (error) {
    response.writeHead(500, { "Content-Type": "text/plain; charset=utf-8" });
    response.end(error instanceof Error ? error.message : "Internal Server Error");
  }
});

server.listen(port, host, () => {
  process.stdout.write(`pages-server: http://${host}:${port}${mountPrefix}/\n`);
});
