#!/usr/bin/env node
/**
 * reference-raster.mjs — the pure-CPU tier of the determinism falsifier.
 *
 * Why this exists: the brief asks for a headless deterministic render that can
 * be run twice and compared byte-for-byte. The GPU path is the piece (and
 * `tools/determinism.mjs` pins it through Chromium/SwiftShader). But a GPU pin
 * is only as good as the browser that happens to be installed, so the layout
 * math gets pinned a second time with no GPU, no DOM and no library: this file
 * imports the SAME `modules/layout.js` and `modules/mat4.js` the browser does
 * and rasterises the scene with hand-written loops.
 *
 * It is a reference rasterizer, not a second renderer. The two tiers are NOT
 * asserted to produce identical pixels — the shader marchs a recursive lattice
 * that this file draws only as a cheap deterministic backdrop. What they do
 * share, exactly, is the geometry: node centres and radii, root-vector
 * positions, filament endpoints, the camera pose and the projection. That is
 * what the byte pin is about.
 *
 * Usage:
 *   node tools/reference-raster.mjs [--width 320] [--height 200]
 *        [--seed cfsg-atlas] [--frames 16] [--phase 0.09] [--out PATH.png]
 *        [--print-sha-only]
 *
 * Exports `renderReference` for `tools/determinism.mjs` and the tests.
 */

import { createHash } from "node:crypto";
import { mkdirSync, writeFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import { deflateSync } from "node:zlib";

import { PRNG } from "../../../../gen/lib/prng.js";
import { buildLayout, cameraPoseAt, LIE_FOLD_ANGLE, LAYOUT_SCHEMA, rgbForKind } from "../modules/layout.js";
import { lookAt, frustum, project, rayThrough, FAR } from "../modules/mat4.js";
import { makeProvenanceReader } from "../modules/describe.js";

const HERE = dirname(fileURLToPath(import.meta.url));
const DATA = resolve(HERE, "../data/cfsg-families.json");
const PROV = resolve(HERE, "../data/provenance.json");

/** Matches the GLSL `lights()` triple, so shading means the same thing twice. */
const LIGHTS = [
  { p: [9, 12, 7], i: 1.15 },
  { p: [-11, 6, -8], i: 0.72 },
  { p: [0, 2.2, 0], i: 0.55 },
];
const POINT_SCALE = 0.085;
/**
 * The CPU tier's three lights are the same three as the shader's, so without an
 * exposure the reference image blows out where they stack. This number belongs
 * to the reference rasterizer alone; it is not the GPU's tonemap.
 */
const EXPOSURE = 0.55;

export function loadScene() {
  /* eslint-disable no-console */
  const data = JSON.parse(readFileSyncSafe(DATA));
  let provenance = null;
  try { provenance = JSON.parse(readFileSyncSafe(PROV)); } catch { provenance = null; }
  const prov = makeProvenanceReader(provenance);
  return { layout: buildLayout(data, prov), data, prov };
}

function readFileSyncSafe(path) {
  // Kept out of the top-level import so `--print-sha-only` still works from a
  // shell without fs-side effects.
  return new TextDecoder().decode(readFileBytes(path));
}
import { readFileSync } from "node:fs";
function readFileBytes(path) { return readFileSync(path); }

/**
 * Ray/sphere against every node bounding sphere; nearest hit or null.
 * Shared logic with `pickNode` in layout.js by construction — same radii.
 */
function traceNodes(origin, direction, nodes) {
  let best = null;
  for (let i = 0; i < nodes.length; i += 1) {
    const n = nodes[i];
    const ox = origin[0] - n.pos[0];
    const oy = origin[1] - n.pos[1];
    const oz = origin[2] - n.pos[2];
    const b = ox * direction[0] + oy * direction[1] + oz * direction[2];
    const c = ox * ox + oy * oy + oz * oz - n.radius * n.radius;
    const disc = b * b - c;
    if (disc <= 0) continue;
    const t = -b - Math.sqrt(disc);
    if (t <= 1e-4 || t >= FAR) continue;
    if (!best || t < best.t) best = { t, node: n, index: i };
  }
  return best;
}

/**
 * CPU mirror of `foldWedge` in shaders.js: reflect a 2-vector out of a wedge
 * of half-angle a. Used only for the deterministic backdrop, and labelled as
 * a mirror rather than a match.
 */
function foldWedge(x, z, a) {
  const twoA = 2 * a;
  let px = x;
  let pz = z;
  for (let i = 0; i < 4; i += 1) {
    const cos = Math.cos(twoA * (i + 1));
    const sin = Math.sin(twoA * (i + 1));
    const d = px * sin - pz * cos;
    if (d < 0) {
      const nx = 2 * d * sin;
      const nz = -2 * d * cos;
      px -= nx;
      pz -= nz;
    }
  }
  return [px, pz];
}

/** Procedural manifold backdrop — a folded pillar field, no raymarching. */
function backdrop(direction, foldAngle) {
  const y = direction[1];
  const horiz = Math.hypot(direction[0], direction[2]) || 1e-6;
  const [fx, fz] = foldWedge(direction[0] / horiz, direction[2] / horiz, foldAngle);
  const az = Math.atan2(fz, fx);
  const pillar = Math.pow(Math.abs(Math.cos(az * 4.0)), 8.0);
  const ring = Math.pow(Math.abs(Math.sin(horiz * 6.0 + y * 3.0)), 12.0);
  const sky = Math.max(0, 0.06 + y * 0.16);
  const gold = Math.max(0, Math.cos(az * 2.0)) * pillar * 0.16;
  const ice = ring * 0.1 * (0.4 + 0.6 * Math.max(0, -y));
  return [
    sky * 0.34 + ice * 0.30 + gold * 0.90,
    sky * 0.40 + ice * 0.92 + gold * 0.62,
    sky * 0.62 + ice * 1.00 + gold * 0.20,
  ];
}

function shade(hit, origin, direction, node) {
  const p = [
    origin[0] + direction[0] * hit.t,
    origin[1] + direction[1] * hit.t,
    origin[2] + direction[2] * hit.t,
  ];
  const nx = (p[0] - node.pos[0]) / node.radius;
  const ny = (p[1] - node.pos[1]) / node.radius;
  const nz = (p[2] - node.pos[2]) / node.radius;
  let r = 0;
  let g = 0;
  let b = 0;
  for (const light of LIGHTS) {
    const lx = light.p[0] - p[0];
    const ly = light.p[1] - p[1];
    const lz = light.p[2] - p[2];
    const ll = Math.hypot(lx, ly, lz) || 1e-6;
    const ndl = Math.max(0, (nx * lx + ny * ly + nz * lz) / ll);
    // the facet pattern: the Coxeter residue carves meridians into the shading
    let facet = 1;
    if (node.coxeter) {
      const theta = Math.atan2(nz, nx);
      const wedges = Math.max(2, node.coxeter.m);
      facet = 0.55 + 0.45 * Math.pow(Math.abs(Math.cos(theta * wedges)), 0.6);
    }
    r += node.color[0] * ndl * light.i * facet;
    g += node.color[1] * ndl * light.i * facet;
    b += node.color[2] * ndl * light.i * facet;
    const vx = -direction[0];
    const vy = -direction[1];
    const vz = -direction[2];
    const spec = Math.pow(Math.max(0, (nx * lx + ny * ly + nz * lz) / ll * 0.5 + vx * 0.5), 24);
    r += spec * light.i * 0.6;
    g += spec * light.i * 0.6;
    b += spec * light.i * 0.6;
  }
  const fres = Math.pow(1 - Math.max(0, -(nx * direction[0] + ny * direction[1] + nz * direction[2])), 3);
  r += fres * node.color[0] * 0.5;
  g += fres * node.color[1] * 0.55;
  b += fres * node.color[2] * 0.7;
  return [r, g, b];
}

/**
 * The render. Deterministic: everything is driven by `seed`, `frames`,
 * `width`, `height` and `phase`, and the PRNG is the repo's own xorshift128+.
 *
 * @returns {{rgba: Uint8Array, width:number, height:number, sha256:string, stats:object}}
 */
export function renderReference(options = {}) {
  const {
    width = 320,
    height = 200,
    seed = "cfsg-atlas",
    frames = 16,
    phase = 0.09,
    layout,
  } = options;
  const scene = layout ? { layout } : loadScene();
  const L = scene.layout;
  const aspect = width / height;
  const pose = cameraPoseAt(phase, L.camera);
  const view = lookAt(pose, L.camera.target, [0, 1, 0]);
  const proj = frustum(L.camera.fovYDeg, aspect);

  const acc = new Float32Array(width * height * 3);
  const depth = new Float32Array(width * height);
  const rng = new PRNG(`${seed}|cpu|${width}x${height}|${phase}`);

  let sphereHits = 0;
  let pointDots = 0;
  let filamentCells = 0;

  for (let frame = 0; frame < frames; frame += 1) {
    depth.fill(Infinity);
    for (let py = 0; py < height; py += 1) {
      for (let px = 0; px < width; px += 1) {
        // one jittered sample per pixel per frame: progressive, convergent
        const jx = (px + rng.next()) / width;
        const jy = (py + rng.next()) / height;
        const ndc = [jx * 2 - 1, -(jy * 2 - 1)];
        const ray = rayThrough(ndc, pose, view, proj);
        const hit = traceNodes(ray.origin, ray.direction, L.nodes);
        const i3 = (py * width + px) * 3;
        let col;
        if (hit) {
          col = shade(hit, ray.origin, ray.direction, hit.node);
          depth[py * width + px] = hit.t;
          sphereHits += 1;
        } else {
          col = backdrop(ray.direction, LIE_FOLD_ANGLE);
        }
        acc[i3] += col[0];
        acc[i3 + 1] += col[1];
        acc[i3 + 2] += col[2];
      }
    }

    // points and filaments are projected, not traced: they are additive and
    // depth-tested against the spheres the ray pass just filled.
    for (const p of L.points) {
      const s = project(p.pos, view, proj, [0, 0, width, height]);
      if (!s) continue;
      const camZ = viewZ(p.pos, view);
      const rgb = rgbForKind(p.kind);
      const radius = Math.max(0.6, (POINT_SCALE / Math.max(0.2, camZ)) * height * 0.5);
      const x0 = Math.max(0, Math.floor(s.x - radius));
      const x1 = Math.min(width - 1, Math.ceil(s.x + radius));
      const y0 = Math.max(0, Math.floor(s.y - radius));
      const y1 = Math.min(height - 1, Math.ceil(s.y + radius));
      for (let y = y0; y <= y1; y += 1) {
        for (let x = x0; x <= x1; x += 1) {
          const dx = (x + 0.5 - s.x) / radius;
          const dy = (y + 0.5 - s.y) / radius;
          const d2 = dx * dx + dy * dy;
          if (d2 > 1) continue;
          if (camZ > depth[y * width + x]) continue;
          const glow = (1 - d2) * (1 - d2);
          const i3 = (y * width + x) * 3;
          acc[i3] += rgb[0] * glow * 0.5;
          acc[i3 + 1] += rgb[1] * glow * 0.5;
          acc[i3 + 2] += rgb[2] * glow * 0.5;
          pointDots += 1;
        }
      }
    }

    for (const f of L.filaments) {
      const a = project(f.from, view, proj, [0, 0, width, height]);
      const b = project(f.to, view, proj, [0, 0, width, height]);
      if (!a || !b) continue;
      const rgb = rgbForKind(f.kind);
      const zA = viewZ(f.from, view);
      const zB = viewZ(f.to, view);
      drawLine(acc, depth, width, height, a, b, zA, zB, rgb);
      filamentCells += 1;
    }
  }

  // tonemap + ordered dither, then to 8-bit RGBA
  const rgba = new Uint8Array(width * height * 4);
  for (let py = 0; py < height; py += 1) {
    for (let px = 0; px < width; px += 1) {
      const i = py * width + px;
      const i3 = i * 3;
      const inv = EXPOSURE / frames;
      let r = acc[i3] * inv;
      let g = acc[i3 + 1] * inv;
      let b = acc[i3 + 2] * inv;
      // ACES-ish shoulder, the same shape the display pass uses
      const tonemap = (v) => (v * (2.51 * v + 0.03)) / (v * (2.43 * v + 0.59) + 0.14);
      r = tonemap(Math.max(0, r));
      g = tonemap(Math.max(0, g));
      b = tonemap(Math.max(0, b));
      const bayer = BAYER4[(py & 3) * 4 + (px & 3)] / 16 - 0.5;
      rgba[i * 4] = to8(r + bayer * 0.012);
      rgba[i * 4 + 1] = to8(g + bayer * 0.012);
      rgba[i * 4 + 2] = to8(b + bayer * 0.012);
      rgba[i * 4 + 3] = 255;
    }
  }

  const png = encodePNG(rgba, width, height);
  const stats = {
    tier: "cpu-reference-rasterizer",
    layoutSchema: LAYOUT_SCHEMA,
    width,
    height,
    frames,
    phase,
    seed: String(seed),
    nodes: L.nodes.length,
    points: L.points.length,
    filaments: L.filaments.length,
    sphereHits,
    pointDots,
    filamentCells,
  };
  return { rgba, png, stats, sha256: sha256Hex(png), pixelsSha256: sha256Hex(rgba) };
}

const BAYER4 = [
  0, 8, 2, 10,
  12, 4, 14, 6,
  3, 11, 1, 9,
  15, 7, 13, 5,
];
function to8(v) {
  const s = Math.round(Math.max(0, Math.min(1, v)) * 255);
  return s === 0 ? 0 : s === 255 ? 255 : s;
}
function viewZ(point, view) {
  return -(view[2] * point[0] + view[6] * point[1] + view[10] * point[2] + view[14]);
}

/** Bresenham-ish thick line with a linear depth ramp and additive glow. */
function drawLine(acc, depth, width, height, a, b, zA, zB, color) {
  const dx = b.x - a.x;
  const dy = b.y - a.y;
  const len = Math.hypot(dx, dy);
  if (!(len > 0.5)) return;
  const steps = Math.ceil(len);
  for (let s = 0; s <= steps; s += 1) {
    const u = s / steps;
    const x = Math.round(a.x + dx * u);
    const y = Math.round(a.y + dy * u);
    if (x < 0 || y < 0 || x >= width || y >= height) continue;
    const z = zA + (zB - zA) * u;
    if (z > depth[y * width + x]) continue;
    const i3 = (y * width + x) * 3;
    const w = 0.35;
    acc[i3] += color[0] * w;
    acc[i3 + 1] += color[1] * w;
    acc[i3 + 2] += color[2] * w;
  }
}

function sha256Hex(bytes) {
  return createHash("sha256").update(bytes).digest("hex");
}

/** Minimal, dependency-free PNG: one IDAT, filter 0 per scanline. */
export function encodePNG(rgba, width, height) {
  const raw = Buffer.alloc((width * 4 + 1) * height);
  for (let y = 0; y < height; y += 1) {
    const rowStart = y * (width * 4 + 1);
    raw[rowStart] = 0;
    rgba.subarray(y * width * 4, (y + 1) * width * 4).forEach((v, i) => {
      raw[rowStart + 1 + i] = v;
    });
  }
  const chunks = [];
  const push = (type, data) => {
    const len = Buffer.alloc(4);
    len.writeUInt32BE(data.length, 0);
    const body = Buffer.concat([Buffer.from(type, "latin1"), data]);
    const crc = Buffer.alloc(4);
    crc.writeUInt32BE(crc32(body) >>> 0, 0);
    chunks.push(len, body, crc);
  };
  const ihdr = Buffer.alloc(13);
  ihdr.writeUInt32BE(width, 0);
  ihdr.writeUInt32BE(height, 4);
  ihdr[8] = 8;   // bit depth
  ihdr[9] = 6;   // RGBA
  ihdr[10] = 0;  // deflate
  ihdr[11] = 0;  // adaptive filtering off (we only ever emit filter 0)
  ihdr[12] = 0;  // interlace
  push("IHDR", ihdr);
  push("IDAT", deflateSync(raw, { level: 9 }));
  push("IEND", Buffer.alloc(0));
  return Buffer.concat([Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]), ...chunks]);
}

let CRC_TABLE = null;
function crc32(buf) {
  if (!CRC_TABLE) {
    CRC_TABLE = new Int32Array(256);
    for (let n = 0; n < 256; n += 1) {
      let c = n;
      for (let k = 0; k < 8; k += 1) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1;
      CRC_TABLE[n] = c;
    }
  }
  let c = 0xffffffff;
  for (let i = 0; i < buf.length; i += 1) c = CRC_TABLE[(c ^ buf[i]) & 0xff] ^ (c >>> 8);
  return c ^ 0xffffffff;
}

/* ---------------------------------- CLI --------------------------------- */
if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  const argv = process.argv.slice(2);
  const get = (name, dflt) => {
    const i = argv.indexOf(`--${name}`);
    return i >= 0 && argv[i + 1] && !argv[i + 1].startsWith("--") ? argv[i + 1] : dflt;
  };
  const width = Number(get("width", 320));
  const height = Number(get("height", 200));
  const frames = Number(get("frames", 16));
  const phase = Number(get("phase", 0.09));
  const seed = get("seed", "cfsg-atlas");
  const out = get("out", resolve(HERE, `../out/reference-${width}x${height}-f${frames}.png`));
  const t0 = Date.now();
  const result = renderReference({ width, height, frames, phase, seed });
  mkdirSync(dirname(out), { recursive: true });
  writeFileSync(out, result.png);
  writeFileSync(`${out}.json`, `${JSON.stringify({ ...result.stats, png: out, pngSha256: result.sha256, ms: Date.now() - t0 }, null, 2)}\n`);
  if (argv.includes("--print-sha-only")) console.log(result.sha256);
  else console.log(JSON.stringify({ ...result.stats, png: out, pngSha256: result.sha256, pixelsSha256: result.pixelsSha256, ms: Date.now() - t0 }, null, 2));
}
