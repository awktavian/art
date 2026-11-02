#!/usr/bin/env node
/**
 * determinism.mjs — the falsifier for the CFSG group atlas.
 *
 * The claim being falsified: "the traced image is reproducible from a seed".
 * Two tiers, both run by default, each with its own byte pin:
 *
 *   Tier A — pure CPU. `reference-raster.mjs` rasterises the layout math in
 *     node with no GPU, no DOM and no browser. Run twice in-process and once in
 *     a child process; all three must agree byte-for-byte.
 *   Tier B — GPU. A zero-dependency static server plus headless Chromium
 *     (the repo's existing `@playwright/test` devDependency, ANGLE/SwiftShader,
 *     so the "GPU" is a deterministic software rasteriser). The page's
 *     `window.__atlas.deterministic()` renders N seeded accumulation steps and
 *     hashes the float buffer, the tonemapped canvas bytes and the PNG, twice
 *     inside one page and once in a second browser context.
 *
 * Reduced motion is checked in tier B as its own assertion: with
 * `prefers-reduced-motion: reduce` emulated, the rAF loop must not run, and the
 * static frame must hash the same in two separate contexts.
 *
 * Exit code 0 = every tier that ran agreed. A tier that could not run is
 * reported as a typed absence with its reason, never as a pass; `--require-gpu`
 * makes that absence fatal (it is the default in this lane's receipt).
 *
 *   node tools/determinism.mjs [--frames 8] [--width 320] [--height 200]
 *        [--seed cfsg-atlas] [--require-gpu] [--out PATH]
 *        [--ready-budget-ms 150000] [--playwright PATH]
 */

import { createHash } from "node:crypto";
import { createServer } from "node:http";
import { mkdirSync, readFileSync, writeFileSync, existsSync } from "node:fs";
import { dirname, join, resolve, extname, relative } from "node:path";
import { spawnSync } from "node:child_process";
import { createRequire } from "node:module";
import { fileURLToPath, pathToFileURL } from "node:url";

import { renderReference, loadScene } from "./reference-raster.mjs";

const HERE = dirname(fileURLToPath(import.meta.url));
const SITE = resolve(HERE, "..");
const argv = process.argv.slice(2);
const flag = (name, dflt) => {
  const i = argv.indexOf(`--${name}`);
  return i >= 0 && argv[i + 1] && !argv[i + 1].startsWith("--") ? argv[i + 1] : dflt;
};
const has = (name) => argv.includes(`--${name}`);

const WIDTH = Number(flag("width", 320));
const HEIGHT = Number(flag("height", 200));
const FRAMES = Number(flag("frames", 8));
const SEED = flag("seed", "cfsg-atlas");
const PHASE = Number(flag("phase", 0.09));
const OUT = flag("out", resolve(SITE, "out/determinism-receipt.json"));
const REQUIRE_GPU = has("require-gpu");
// How long a page is allowed to reach `__atlas.ready`. The number is not a
// judgement about the piece: this host runs a software rasteriser (SwiftShader)
// and, on the evening this was measured, more than twenty concurrent agent
// lanes, so a WebGL boot that completes in 5 s idle can exceed 30 s under that
// contention. A tier that times out silently is a false red, so the budget is
// explicit here and the measured wall time goes into the receipt.
const READY_BUDGET_MS = Number(flag("ready-budget-ms", 150000));

const sha = (bytes) => createHash("sha256").update(bytes).digest("hex");
// The receipt is a published artifact. It must say which transport produced the
// bytes without printing the operator's home directory into the site tree.
const HOME = process.env.HOME || "";
const redactPath = (p) => (HOME && typeof p === "string" && p.startsWith(HOME)
  ? `~/${relative(HOME, p)}`
  : p);
const mime = {
  ".html": "text/html; charset=utf-8",
  ".js": "text/javascript; charset=utf-8",
  ".mjs": "text/javascript; charset=utf-8",
  ".json": "application/json; charset=utf-8",
  ".css": "text/css; charset=utf-8",
  ".svg": "image/svg+xml",
  ".png": "image/png",
};

function serve(dir) {
  const server = createServer((req, res) => {
    const path = decodeURIComponent((req.url || "/").split("?")[0]);
    const file = resolve(dir, `.${path === "/" ? "/index.html" : path}`);
    if (!file.startsWith(resolve(dir)) || !existsSync(file)) {
      res.writeHead(404).end("not found");
      return;
    }
    res.writeHead(200, { "content-type": mime[extname(file)] || "application/octet-stream", "cache-control": "no-store" });
    res.end(readFileSync(file));
  });
  return new Promise((done) => server.listen(0, "127.0.0.1", () => done({ server, port: server.address().port })));
}

/**
 * Where is Playwright? This seat is a git worktree, and worktrees carry no
 * node_modules of their own. So the primary checkout is asked for it — derived
 * from `git rev-parse --git-common-dir`, never guessed at a path — and the
 * answer is printed in the receipt. A pin whose transport is unknown is not a
 * pin, which is why `--playwright PATH` also exists.
 */
function primaryCheckout() {
  const r = spawnSync("git", ["rev-parse", "--git-common-dir"], { cwd: SITE, encoding: "utf8" });
  if (r.status !== 0) return null;
  const common = resolve(SITE, r.stdout.trim());
  return extname(common) === "" ? dirname(common) : dirname(common);
}

function resolvePlaywright() {
  const named = flag("playwright", null);
  const primary = primaryCheckout();
  const anchors = [];
  if (named) anchors.push({ anchor: "argv", req: createRequire(pathToFileURL(join(resolve(named), "noop.js")).href) });
  if (primary) anchors.push({ anchor: primary, req: createRequire(pathToFileURL(join(primary, "package.json")).href) });
  anchors.push({ anchor: "self", req: createRequire(import.meta.url) });
  for (const { anchor, req } of anchors) {
    for (const specifier of ["playwright", "@playwright/test"]) {
      try {
        const entry = req.resolve(specifier);
        const mod = req(entry);
        if (mod && (mod.chromium || mod.default?.chromium)) {
          return {
            chromium: mod.chromium || mod.default.chromium,
            resolved: entry,
            anchor,
            specifier,
          };
        }
        return { chromium: null, resolved: entry, anchor, reason: `${specifier} resolved at ${entry} but exports no chromium` };
      } catch {
        /* try the next anchor */
      }
    }
  }
  return {
    chromium: null,
    resolved: null,
    reason: `playwright not resolvable from this seat (worktree: ${SITE}) or its primary checkout (${primary ?? "unknown"})`,
  };
}


/* --------------------------------- tier A -------------------------------- */
function cpuTier() {
  const a = renderReference({ width: WIDTH, height: HEIGHT, frames: FRAMES, seed: SEED, phase: PHASE });
  const b = renderReference({ width: WIDTH, height: HEIGHT, frames: FRAMES, seed: SEED, phase: PHASE });
  // A fresh process, so no accidentally shared state between the two calls.
  const child = spawnSync(process.execPath, [
    resolve(HERE, "reference-raster.mjs"),
    "--width", String(WIDTH), "--height", String(HEIGHT),
    "--frames", String(FRAMES), "--seed", SEED, "--phase", String(PHASE),
    "--out", resolve(SITE, "out/reference-child.png"), "--print-sha-only",
  ], { encoding: "utf8" });
  const childSha = (child.stdout || "").trim();
  const different = renderReference({ width: WIDTH, height: HEIGHT, frames: FRAMES, seed: `${SEED}-other`, phase: PHASE });
  return {
    inProcessSha256: a.sha256,
    secondRunSha256: b.sha256,
    childProcessSha256: childSha || null,
    childRc: child.status,
    pixelsSha256: a.pixelsSha256,
    controlDifferentSeedSha256: different.sha256,
    agree: a.sha256 === b.sha256 && a.sha256 === childSha,
    controlDiffers: different.sha256 !== a.sha256,
    stats: a.stats,
  };
}

/* --------------------------------- tier B -------------------------------- */
async function gpuTier() {
  const pw = resolvePlaywright();
  if (!pw.chromium) {
    return { available: false, reason: pw.reason || "playwright/chromium not resolvable; try --playwright PATH" };
  }
  const { chromium, resolved } = pw;
  const { server, port } = await serve(SITE);
  const base = `http://127.0.0.1:${port}/index.html`;
  const browser = await chromium.launch({
    args: ["--use-gl=angle", "--use-angle=swiftshader", "--disable-lcd-text", "--force-device-scale-factor=1"],
  });
  const result = {
    available: true,
    transport: {
      resolvedFrom: redactPath(pw.anchor),
      specifier: pw.specifier,
      entry: redactPath(resolved),
      module: "chromium",
      gl: "ANGLE/SwiftShader (software, deterministic)",
    },
    // The page follows the repo's font convention — a remote IBM Plex stylesheet
    // (index.html:14). That request is what `load` waits for, so gating the
    // tier on it made the GPU leg fail on a host with no route to the CDN
    // (measured: page.goto Timeout 30000ms on waitUntil "load"). Nothing in the
    // boot path reads fonts — atlas.js never awaits document.fonts — so the
    // tier navigates with domcontentloaded and gates on `__atlas.ready`, which
    // is the thing whose bytes are being pinned. The CSS stack falls back to
    // system faces offline, so the pin is not font-sensitive either.
    navigation: { waitUntil: "domcontentloaded", gate: "window.__atlas.ready === true", remoteFontStylesheet: "index.html:14 (IBM Plex via fonts.googleapis.com)" },
  };
  try {
    // ONE page runner for every leg: a context is opened, navigated, waited
    // for, used, and then closed — the legs of this tier are sequentially
    // dependent on CPU, and a leaked context keeps its requestAnimationFrame
    // loop alive on a software rasteriser, which is how a passing run turns into
    // a timeout three legs later. Each leg records its own page errors, and a
    // failure says WHICH leg it was.
    const legs = [];
    const withPage = async (leg, ctxOptions, fn) => {
      const context = await browser.newContext({
        viewport: { width: WIDTH, height: HEIGHT }, deviceScaleFactor: 1, ...ctxOptions,
      });
      const errors = [];
      const record = { leg, errors, openedAt: new Date().toISOString() };
      legs.push(record);
      try {
        const page = await context.newPage();
        page.on("pageerror", (e) => errors.push(String(e.message || e)));
        page.on("console", (m) => { if (m.type() === "error") errors.push(m.text()); });
        const navStart = Date.now();
        await page.goto(base, { waitUntil: "domcontentloaded", timeout: READY_BUDGET_MS });
        await page.waitForFunction("window.__atlas && window.__atlas.ready === true", null, { timeout: READY_BUDGET_MS });
        record.readyMs = Date.now() - navStart;
        const out = await fn(page, record);
        // stop the loop before tearing the context down, so the next leg starts
        // with the whole software rasteriser to itself
        await page.evaluate(() => { if (window.__atlas && window.__atlas.reduceMotion) window.__atlas.reduceMotion(true); }).catch(() => {});
        return out;
      } catch (error) {
        const why = error && error.message ? error.message : String(error);
        throw new Error(`${leg} — ${why}`
          + (errors.length ? ` | page errors: ${errors.slice(0, 3).join(" / ")}` : " | no page error was reported")
          + ` | legs before this one: ${legs.slice(0, -1).map((l) => l.leg).join(", ") || "(none)"}`);
      } finally {
        record.closedAt = new Date().toISOString();
        await context.close();
      }
    };

    // two calls in the same page, strictly one after the other: `deterministic`
    // reconfigures the renderer (resolution, accumulation, pass set), so
    // overlapping them would measure the interleaving, not the render
    const deterministicLeg = (seed, calls) => async (page) => {
      const out = [];
      for (let i = 0; i < calls; i += 1) {
        // a real function, not a string: Playwright evaluates a *string* first
        // argument as an expression, so "([o]) => …" resolves to a function
        // object, which is not serialisable and comes back as undefined. The
        // tier then compares undefined === undefined and reports byte-identity
        // over nothing — the loudest kind of false green this harness can make.
        const options = { seed, frames: FRAMES, width: WIDTH, height: HEIGHT, phase: PHASE };
        out.push(await page.evaluate((o) => window.__atlas.deterministic(o), options));
      }
      return out;
    };

    const first = await withPage("deterministic-context-1", {}, async (page) => {
      const calls = await deterministicLeg(hashSeed(SEED), 2)(page);
      const info = await page.evaluate(() => ({
        stats: window.__atlas.stats,
        hud: [...document.querySelectorAll(".atlas-hud span")].map((n) => n.textContent),
        webgl: (() => {
          const c = document.createElement("canvas");
          const gl = c.getContext("webgl2");
          if (!gl) return null;
          const ext = gl.getExtension("WEBGL_debug_renderer_info");
          return ext ? `${gl.getParameter(ext.UNMASKED_VENDOR_WEBGL)} / ${gl.getParameter(ext.UNMASKED_RENDERER_WEBGL)}` : "debug info blocked";
        })(),
      }));
      result.layoutStats = info.stats;
      result.hud = info.hud;
      result.renderer = info.webgl;
      return calls;
    });
    const second = await withPage("deterministic-context-2", {}, deterministicLeg(hashSeed(SEED), 2));
    // positive control: a hash that is missing is not a hash that agrees. Every
    // leg must come back with a 64-hex digest and a real mode, or the tier
    // refuses rather than reporting identity over undefined.
    const isSha = (v) => typeof v === "string" && /^[0-9a-f]{64}$/.test(v);
    for (const [leg, calls] of [["context-1", first], ["context-2", second]]) {
      for (const call of calls) {
        if (!call || typeof call !== "object") {
          throw new Error(`${leg}: deterministic() returned ${String(call)} — nothing was measured`);
        }
        if (call.mode !== "gpu-rgba16f" && call.mode !== "gpu-rgba8") {
          throw new Error(`${leg}: unexpected render mode ${String(call.mode)}`);
        }
        for (const field of ["accumSha", "displaySha", "pngSha"]) {
          if (!isSha(call[field])) throw new Error(`${leg}: ${field} is not a 64-hex digest (${String(call[field])})`);
        }
        if (call.frames !== FRAMES) {
          throw new Error(`${leg}: asked for ${FRAMES} accumulation frames, the renderer reports ${call.frames}`);
        }
      }
    }
    result.firstContext = first;
    result.secondContext = second;
    result.mode = first[0].mode;
    result.frames = first[0].frames;
    result.hdr = first[0].mode === "gpu-rgba16f";
    result.inPageAgree = first[0].accumSha === first[1].accumSha
      && first[0].displaySha === first[1].displaySha
      && first[0].pngSha === first[1].pngSha;
    result.acrossContextsAgree = first[0].accumSha === second[0].accumSha
      && first[0].displaySha === second[0].displaySha
      && first[0].pngSha === second[0].pngSha;
    // a different seed must actually change the image, or the pin is vacuous
    const alt = await withPage("control-seed", {}, deterministicLeg(hashSeed(`${SEED}-other`), 1));
    result.controlDifferentSeed = { accumSha: alt[0].accumSha, differs: alt[0].accumSha !== first[0].accumSha };

    // reduced motion: the loop must not run, and the static frame must repeat
    const rm = await withPage("reduced-motion", { reducedMotion: "reduce" }, async (page) => {
      const a = await page.evaluate(() => ({
        reduce: window.__atlas.motion.reduce,
        frames: window.__atlas.renderer() ? window.__atlas.renderer().frameCount : -1,
      }));
      await page.waitForTimeout(400);
      const b = await page.evaluate(() => ({
        frames: window.__atlas.renderer() ? window.__atlas.renderer().frameCount : -1,
      }));
      return { a, b, sha: await canvasSha(page) };
    });
    const rm2 = await withPage("reduced-motion-context-2", { reducedMotion: "reduce" }, canvasSha);
    if (!isSha(rm.sha) || !isSha(rm2)) {
      throw new Error(`reduced motion: the canvas hash is not a digest (${String(rm.sha)} / ${String(rm2)})`);
    }
    result.reducedMotion = {
      mediaQueryHonoured: rm.a.reduce === true,
      frameCountStatic: rm.a.frames === rm.b.frames,
      frames: rm.a.frames,
      canvasSha256: rm.sha,
      secondContextSha256: rm2,
      staticFrameRepeats: rm.sha === rm2,
    };
    // hash the layout geometry in the browser and compare with node: the same
    // modules, two hosts, one answer — this is the cross-tier pin.
    const browserLayoutSha = await withPage("layout-cross-host", {}, (page) => page.evaluate(async () => await window.__atlas.layoutSha()));
    const nodeLayoutSha = sha(layoutBytesFromNode());
    if (!isSha(browserLayoutSha)) {
      throw new Error(`layout cross-host: the browser digest is not 64-hex (${String(browserLayoutSha)})`);
    }
    result.layoutCrossHost = { browser: browserLayoutSha, node: nodeLayoutSha, agree: browserLayoutSha === nodeLayoutSha };
    result.legs = legs.map((l) => ({
      leg: l.leg,
      readyMs: l.readyMs,
      pageErrors: l.errors.length,
      firstPageError: l.errors.length ? String(l.errors[0]).slice(0, 200) : null,
    }));
    result.load = {
      readyBudgetMs: READY_BUDGET_MS,
      slowestLegMs: Math.max(...legs.map((l) => (typeof l.readyMs === "number" ? l.readyMs : 0))),
    };
    result.agree = result.inPageAgree && result.acrossContextsAgree
      && result.controlDifferentSeed.differs
      && result.reducedMotion.mediaQueryHonoured
      && result.reducedMotion.frameCountStatic
      && result.reducedMotion.staticFrameRepeats
      && result.layoutCrossHost.agree;
  } finally {
    await browser.close();
    server.close();
  }
  return result;
}

/** SHA-256 of the presented canvas, computed inside the page. */
async function canvasSha(page) {
  return page.evaluate(async () => {
    const r = window.__atlas.renderer();
    if (!r) return null;
    const bytes = r.readCanvasRGBA();
    const digest = await crypto.subtle.digest("SHA-256", bytes);
    return [...new Uint8Array(digest)].map((b) => b.toString(16).padStart(2, "0")).join("");
  });
}

function layoutBytesFromNode() {
  const { layout } = loadScene();
  const parts = [];
  const fixed = (v) => (Math.round(v * 1e6) / 1e6).toFixed(6);
  for (const n of layout.nodes) {
    parts.push(`N|${n.id}|${n.pos.map(fixed).join(",")}|${fixed(n.radius)}|${n.color.map(fixed).join(",")}|${n.coxeter ? fixed(n.coxeter.theta) : "-"}`);
  }
  for (const p of layout.points) parts.push(`P|${p.pos.map(fixed).join(",")}|${p.kind}`);
  for (const f of layout.filaments) parts.push(`F|${f.from.map(fixed).join(",")}|${f.to.map(fixed).join(",")}|${f.kind}`);
  parts.push(`S|${JSON.stringify(layout.stats)}`);
  return Buffer.from(parts.join("\n"), "utf8");
}

/** Must match `hashSeedToUint` in modules/atlas.js — the pin is the seed word. */
function hashSeed(str) {
  let h = 0x811c9dc5;
  for (let i = 0; i < str.length; i += 1) {
    h ^= str.charCodeAt(i);
    h = Math.imul(h, 0x01000193);
  }
  return h >>> 0;
}

/* ---------------------------------- main ---------------------------------- */
const receipt = {
  tool: "v6.determinism.1",
  ranAt: new Date().toISOString().replace(/\.\d+Z$/, "Z"),
  subject: { site: "patent-portfolio/demos/groups", seed: SEED, frames: FRAMES, width: WIDTH, height: HEIGHT, phase: PHASE },
  tierA_cpu: null,
  tierB_gpu: null,
};

receipt.tierA_cpu = cpuTier();
try {
  receipt.tierB_gpu = await gpuTier();
} catch (error) {
  receipt.tierB_gpu = { available: false, reason: `gpu tier threw: ${error && error.message ? error.message : String(error)}` };
}

const cpuOk = receipt.tierA_cpu.agree && receipt.tierA_cpu.controlDiffers;
const gpuRan = receipt.tierB_gpu.available === true;
const gpuOk = gpuRan && receipt.tierB_gpu.agree === true;
receipt.verdict = {
  tierA_cpu: cpuOk ? "byte-identical across three runs (two in-process, one child)" : "MISMATCH",
  tierB_gpu: gpuRan ? (gpuOk ? "byte-identical across two calls in one context and a second context" : "MISMATCH") : `not run: ${receipt.tierB_gpu.reason}`,
  mode: gpuRan ? `both: GPU path-trace (${receipt.tierB_gpu.mode}) + pure-CPU reference rasterizer` : "CPU reference rasterizer only (disclosed: no GPU tier available)",
};
receipt.pass = cpuOk && (gpuOk || !REQUIRE_GPU);

mkdirSync(dirname(OUT), { recursive: true });
writeFileSync(OUT, `${JSON.stringify(receipt, null, 2)}\n`);
process.stdout.write(`${JSON.stringify(receipt, null, 2)}\n`);
process.exit(receipt.pass ? 0 : 1);
