#!/usr/bin/env node
/**
 * Look-dev harness — art's equivalent of awkronos-waddle's
 * `apps/hub/public/snowball/src/lookdev.js`.
 *
 * WHEREFORE
 * ---------
 * RSI40-1102/V10 found art has no way to answer "did this lighting/material
 * change alter the look?" — three different tone-mapping sites, a key light
 * with `castShadow = false`, and zero frame-hash receipts anywhere in the repo.
 * Waddle answers that question with a look-dev harness: a pinned camera rig,
 * named light presets, and a deterministic per-scene frame hash that a fold can
 * diff. This file ports that DISCIPLINE, not the code: art's museum is built
 * from `THREE` importmap modules and `gen/` is a 2D canvas pipeline, so the
 * receipt has two kinds (`lookGraph`, `drawStream`) instead of one.
 *
 * THE GOLDEN RULE (from waddle's theorem-penguin-corpus.golden.test.ts, adapted)
 * ---------------------------------------------------------------------------
 *   The receipt must exercise the pipeline, not paraphrase it.
 * So this harness imports the REAL modules —
 * `patent-portfolio/museum/lighting.js`, `patent-portfolio/museum/architecture.js`,
 * `patent-portfolio/lib/materials.js`, `gen/lib/palette.js`,
 * `gen/algorithms/spark/algo.js` — and digests what they build. Nothing here
 * re-declares a colony hex, a kelvin, a roughness, or a GLSL string; if a pin
 * cannot be derived from a module, it is declared in COVERAGE as a boundary
 * rather than invented as a literal.
 *
 * HOW IT RUNS HEADLESS (zero new dependencies)
 * --------------------------------------------
 * Node 22.15+/26 only. `node:module`'s `registerHooks` redirects the bare
 * specifier `'three'` to a generated `data:text/javascript` shim whose named
 * exports read `globalThis.__LOOKDEV_THREE__` — the bounded test double in
 * `./three-double.mjs`, written against the importmap pin in
 * `patent-portfolio/index.html` (`three@0.160.0`). art has no `node_modules`
 * and no build step, so a double is the only way to run the museum's lighting
 * and material code as Node code. The 2D scenes run against a recording
 * canvas-context instead of a GPU.
 *
 * WHAT A RECEIPT IS — AND IS NOT
 * ------------------------------
 * It is a DRIFT SIGNAL over the look graph: every camera-projected anchor,
 * every light's color/intensity/position/shadow state sampled down a pinned
 * frame timeline, every material's full own-parameter set, texture byte hashes,
 * PMREM/CubeCamera construction events and the dispose tally, plus the
 * recorded 2D draw-op stream for canvas scenes.
 * It is NOT a pixel proof: there is no rasterizer here, so a change that only
 * alters shading math inside three's own shaders is invisible to it. That
 * boundary is stated in COVERAGE and asserted by the test, not hidden.
 *
 * USAGE
 * -----
 *   node tests/lookdev/lookdev.mjs                 # verify corpus vs receipts (exit 1 on drift)
 *   node tests/lookdev/lookdev.mjs --update        # re-stamp receipts.json (the ONLY write mode)
 *   node tests/lookdev/lookdev.mjs --falsify=seed  # perturb a pin constant, prove hashes move
 *   node tests/lookdev/lookdev.mjs --drill         # one-digit edit to a COPY of lighting.js must move the receipt
 *   node tests/lookdev/lookdev.mjs --json          # machine-readable report
 *   node tests/lookdev/lookdev.mjs --list          # scene ids + their surfaces
 *
 * FALSIFIERS (each names the axes a receipt must be sensitive to)
 * --------------------------------------------------------------
 * `--falsify=<axis>` re-runs the corpus with one harness constant perturbed and
 * fails if NO scene hash moves — a receipt that cannot see its own inputs is a
 * description, not a check. Axes: seed | frames | delta | normalMap | quality | canvas
 * | genSeed | atlasSeeds. (`--falsify=all` runs every axis, and an axis PASSES only if
 * the exact declared set of scenes moves — no more, no less.)
 */

import { createHash } from 'node:crypto';
import { mkdirSync, readFileSync, rmSync, symlinkSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { registerHooks } from 'node:module';

import { createThreeDouble } from './three-double.mjs';

const HERE = dirname(fileURLToPath(import.meta.url));
const REPO = resolve(HERE, '..', '..');

export const CONTRACT = 'art-lookdev-1';
export const RECEIPT_FILE = join(HERE, 'receipts.json');

// ═══════════════════════════════════════════════════════════════════════════
// PINNED RIG CONSTANTS
// ═══════════════════════════════════════════════════════════════════════════
// These are the harness's OWN inputs — the look-dev contract. Each one is a
// falsifier axis: change it here and the affected receipts move, which is the
// whole point. Values mirror patent-portfolio/main.js's initScene (camera
// PerspectiveCamera(70, aspect, 0.1, 500) at (0,1.7,0) looking at (20,1.7,0),
// background 0x1E1A30, FogExp2(0x1E1A30, 0.004)) and art's Fibonacci timing
// convention (144 frames).
export const RIG = {
  seed: 'kagami',            // canonical art seed (tests/unit/load-browser-lib.mjs)
  fov: 70,
  near: 0.1,
  far: 500,
  eye: [0, 1.7, 0],          // visitor standing height in the rotunda
  look: [20, 1.7, 0],        // straight down the Spark wing axis
  jitter: 0.35,              // metres of seeded camera drift — makes the seed load-bearing
  width: 1920,
  height: 1080,
};
export const STAGE_PIN = {
  background: 0x1e1a30,
  fogColor: 0x1e1a30,
  fogDensity: 0.004,
};
export const TIMELINE = {
  frames: 144,               // Fibonacci
  delta: 1 / 60,             // pinned dt — a look-dev receipt has no wall clock
  sampleEvery: 12,
  shadowMap: 1024,
};
export const GEN_PIN = {
  seed: 'kagami',
  canvas: 1024,              // tests/unit idiom
  atlasSeeds: ['kagami', 'fano', 'octonion'],
};
export const MATERIAL_PIN = {
  quality: 'high',
  normalMapSize: 64,
  normalMapScale: 4,
  cubeRenderTarget: 512,
};

// ═══════════════════════════════════════════════════════════════════════════
// COVERAGE BOUNDARY — declared, never implied
// ═══════════════════════════════════════════════════════════════════════════
/**
 * What the corpus cannot see, stated as data so a fold reads the absence as
 * typed rather than as a green light. `kind: 'boundary'` = structurally out of
 * reach of a headless digest; `kind: 'absent'` = the surface does not exist at
 * this base, with the reason. Both are reported by `--list` and in RESULT.json.
 */
export const COVERAGE = [
  {
    surface: 'patent-portfolio/main.js (tone mapping, renderer, scene assembly)',
    kind: 'boundary',
    why: 'main.js is a browser-entry module (reads window/document/WebGL at import ' +
      'time) and is not a Node-importable API. The tone axis is therefore pinned ' +
      'as a stated contract constant (TONE below), NOT observed from main.js — a ' +
      'lane that changes main.js alone does not flip a receipt here. Closing this ' + 'needs a small extractable `createRenderer()` in art, which is V5/V9 territory.',
  },
  {
    surface: 'patent-portfolio/museum/architecture.js createRotunda/createWing geometry',
    kind: 'boundary',
    why: 'the builders call Math.random() (dust motes, projection-speck placement) ' +
      'and document.createElement("canvas") for labels. The harness traps ' +
      'Math.random during scene execution, so these fail loudly rather than ' +
      'drift silently; DIMENSIONS/COLONY_DATA — the parts that ARE deterministic — ' +
      'are digested as the camera-anchor set.',
  },
  {
    surface: 'patent-portfolio/lib/materials.js createMarbleMaterial / createGradientTexture / createNoiseTexture',
    kind: 'boundary',
    why: 'document.createElement("canvas") + Math.random. Excluded from the material ' +
      'table on purpose; every DOM-free factory is included.',
  },
  {
    surface: 'lib/post-processing.js (bloom / addons)',
    kind: 'boundary',
    why: 'imports "three/addons/*". The double refuses that specifier by name — ' +
      'r160 addon sources are not re-implemented here.',
  },
  {
    surface: 'patent-portfolio/demos/groups/ atlas render',
    kind: 'absent',
    why: 'no patent-portfolio/demos/ directory exists on this branch (re-check: ' +
      'test -d patent-portfolio/demos) — V6 is creating that path in flight and ' +
      'owns it. When it folds, add a `groups-atlas` scene to this corpus and ' +
      're-stamp; the harness should read its module, not copy its code.',
  },
  {
    surface: 'path-traced demo frame hash',
    kind: 'absent',
    why: 'the only path-tracing surface in art at this base lives in V6/V7 write ' +
      '-sets (shaders.js / zke8). Reading a lane-in-flight module to pin it would ' +
      'couple this receipt to un-merged bytes.',
  },
  {
    surface: 'pixel-level shading (GLSL evaluation, AgX curve output)',
    kind: 'boundary',
    why: 'no rasterizer in Node without a heavy dependency (brief forbids one). ' +
      'Shader SOURCES are hashed, so an edited curve flips the receipt; a ' +
      'renderer-version change that alters evaluation without touching source ' +
      'does not. Playwright canaries (npm run test:browser) are the pixel leg.',
  },
];

/** The stated tone contract (see COVERAGE[0] for why this is a pin, not an observation). */
export const TONE = {
  toneMapping: 'LinearToneMapping',
  toneMappingExposure: 1.2,
  outputColorSpace: 'srgb',
};

// ═══════════════════════════════════════════════════════════════════════════
// THREE SHIM INSTALLATION
// ═══════════════════════════════════════════════════════════════════════════
const recorder = { disposes: [], events: [] };
const dbl = createThreeDouble(recorder);
export const THREE = dbl.THREE;

let hooksInstalled = false;
function installThreeShim() {
  if (hooksInstalled) return;
  if (typeof registerHooks !== 'function') {
    throw new Error(
      'lookdev: node:module registerHooks() is unavailable (need Node >=22.15; ' +
      `running ${process.version}). Install a newer node rather than adding a dependency.`,
    );
  }
  const keys = Object.keys(THREE);
  const src =
    `const T = globalThis.__LOOKDEV_THREE__;\n` +
    keys.map((k) => `export const ${k} = T[${JSON.stringify(k)}];`).join('\n') +
    `\nexport default T;\n`;
  const url = 'data:text/javascript;base64,' + Buffer.from(src, 'utf8').toString('base64');
  globalThis.__LOOKDEV_THREE__ = THREE;
  registerHooks({
    resolve(specifier, context, nextResolve) {
      if (specifier === 'three') return { url, shortCircuit: true, format: 'module' };
      if (specifier === 'three/addons' || specifier.startsWith('three/addons/')) {
        throw new Error(
          `lookdev: "${specifier}" is outside the pinned corpus — the double does not ` +
          'implement three\'s addon sources (see COVERAGE in tests/lookdev/lookdev.mjs).',
        );
      }
      return nextResolve(specifier, context);
    },
  });
  hooksInstalled = true;
}

const moduleCache = new Map();
function importArt(relPath) {
  installThreeShim();
  const file = relPath.startsWith('/') ? relPath : join(REPO, relPath);
  const key = file;
  if (!moduleCache.has(key)) moduleCache.set(key, import(pathToFileURL(file).href));
  return moduleCache.get(key);
}

// ═══════════════════════════════════════════════════════════════════════════
// CANONICAL ENCODING — quantized, sorted, fail-closed
// ═══════════════════════════════════════════════════════════════════════════
const QUANT = 1e6;
const sha256 = (bytes) => createHash('sha256').update(bytes).digest('hex');

/**
 * Numbers are quantized to 1e-6 so a receipt survives nothing but a real change.
 * NaN is a HARD failure (it means the double hit a degenerate case), while
 * +/-Infinity is encoded as a named sentinel because three itself ships
 * Infinity defaults (MeshPhysicalMaterial.attenuationDistance).
 */
function quantize(n, where) {
  if (typeof n !== 'number') return n;
  if (Number.isNaN(n)) {
    throw new TypeError(`lookdev: NaN in receipt at ${where} — a NaN means the double hit a ` +
      'degenerate case (zero-length axis, missing field); letting it through would stamp green over a broken scene');
  }
  if (!Number.isFinite(n)) {
    // ±Infinity is a LEGAL three value, not a bug: MeshPhysicalMaterial ships with
    // attenuationDistance = Infinity in r160. JSON cannot carry it, so it is
    // encoded as a named sentinel — still deterministic, still drift-visible.
    return n > 0 ? 'inf' : '-inf';
  }
  if (Object.is(n, -0)) n = 0;
  return Math.round(n * QUANT) / QUANT;
}

const hex = (n) => `0x${Math.floor(n).toString(16).padStart(6, '0')}`;

function encode(value, where = '$', depth = 0, seen = new WeakSet()) {
  if (value === null || value === undefined) return null;
  const t = typeof value;
  if (t === 'number') return quantize(value, where);
  if (t === 'boolean') return value;
  if (t === 'string') {
    // A long string in a look graph is almost always GLSL or a data URI: hash it
    // so an edit flips the receipt without turning receipts.json into a shader dump.
    if (value.length > 256) return { __text: value.length, sha256: sha256(Buffer.from(value, 'utf8')) };
    return value;
  }
  if (t === 'function') return null;
  if (t === 'bigint') return String(value);
  if (ArrayBuffer.isView(value) || value instanceof ArrayBuffer) {
    const bytes = value instanceof ArrayBuffer ? new Uint8Array(value) : new Uint8Array(value.buffer, value.byteOffset, value.byteLength);
    return { __bytes: bytes.length, sha256: sha256(bytes) };
  }
  if (Array.isArray(value)) {
    if (depth > 8) throw new RangeError(`lookdev: encode depth cap at ${where}`);
    return value.map((v, i) => encode(v, `${where}[${i}]`, depth + 1, seen));
  }
  if (seen.has(value)) return { __cyclic: true };
  seen.add(value);

  if (value.isColor) {
    return { hex: hex(value.getHex()), rgb: [quantize(value.r, where), quantize(value.g, where), quantize(value.b, where)] };
  }
  if (value.isVector2 || value.isVector3 || value.isEuler) {
    return ['x', 'y', 'z'].filter((k) => k in value).map((k) => quantize(value[k], where));
  }
  if (value.isMatrix4 && Array.isArray(value.elements)) {
    return value.elements.map((e, i) => quantize(e, `${where}.elements[${i}]`));
  }
  if (value.isTexture) {
    const node = { __texture: value.kind || 'Texture', id: value.id };
    for (const k of ['wrapS', 'wrapT', 'magFilter', 'minFilter', 'anisotropy', 'needsUpdate', 'colorSpace', 'format', 'tag']) {
      if (value[k] !== undefined) node[k] = quantize(value[k], `${where}.${k}`);
    }
    if (value.image && typeof value.image === 'object') {
      if (value.image.data) node.data = encode(value.image, `${where}.image`, depth + 1, seen);
      else node.image = { width: value.image.width ?? null, height: value.image.height ?? null };
    }
    return node;
  }
  if (value.children && value.position) {
    // An Object3D inside a material/light: identity + transform, never its subtree.
    const node = { __object: value.type || 'Object3D', id: value.id, name: value.name || '', position: encode(value.position, `${where}.position`, depth + 1, seen) };
    if (value.rotation) node.rotation = encode(value.rotation, `${where}.rotation`, depth + 1, seen);
    if (value.scale) node.scale = encode(value.scale, `${where}.scale`, depth + 1, seen);
    if (Object.keys(value.userData || {}).length) node.userData = encode(value.userData, `${where}.userData`, depth + 1, seen);
    return node;
  }
  if (depth > 8) throw new RangeError(`lookdev: encode depth cap at ${where}`);
  const out = {};
  for (const k of Object.keys(value).sort()) {
    const v = value[k];
    if (typeof v === 'function') continue;
    if (v === undefined) continue;
    if (k === 'children' || k === 'parent') continue; // handled by traversal, not by value
    out[k] = encode(v, `${where}.${k}`, depth + 1, seen);
  }
  return out;
}

export function canonical(value) {
  return JSON.stringify(encode(value));
}
export function digestOf(value) {
  return sha256(Buffer.from(canonical(value), 'utf8'));
}

// ═══════════════════════════════════════════════════════════════════════════
// RECORDING 2D CONTEXT
// ═══════════════════════════════════════════════════════════════════════════
/**
 * A canvas whose only output is the op stream. Unknown members THROW instead of
 * being skipped: skipping is how a harness ends up pinning a description of the
 * drawing rather than the drawing.
 */
const CTX_SETTERS = new Set([
  'fillStyle', 'strokeStyle', 'lineWidth', 'globalAlpha', 'globalCompositeOperation',
  'shadowColor', 'shadowBlur', 'shadowOffsetX', 'shadowOffsetY', 'shadowOffsetZ',
  'font', 'textAlign', 'textBaseline', 'lineCap', 'lineJoin', 'miterLimit',
  'filter', 'imageSmoothingEnabled', 'imageSmoothingQuality', 'direction', 'letterSpacing', 'wordSpacing',
]);
const CTX_METHODS = new Set([
  'save', 'restore', 'beginPath', 'closePath', 'moveTo', 'lineTo', 'quadraticCurveTo',
  'bezierCurveTo', 'arc', 'arcTo', 'ellipse', 'rect', 'roundRect', 'fillRect', 'strokeRect',
  'clearRect', 'fill', 'stroke', 'clip', 'isPointInPath', 'isPointInStroke',
  'translate', 'rotate', 'scale', 'transform', 'setTransform', 'resetTransform',
  'createLinearGradient', 'createRadialGradient', 'createConicGradient', 'createPattern',
  'fillText', 'strokeText', 'measureText', 'getImageData', 'putImageData', 'drawImage',
  'setLineDash', 'getLineDash', 'getContextAttributes', 'reset',
]);

export function makeRecordingCanvas(width, height) {
  const ops = [];
  let gradSeq = 0;
  const state = {};

  const norm = (v) => {
    if (v === null || v === undefined) return null;
    const t = typeof v;
    if (t === 'number') return quantize(v, 'ctx');
    if (t === 'string' || t === 'boolean') return v;
    if (Array.isArray(v)) return v.map((x) => norm(x));
    if (v.__grad) return { __grad: v.__grad };
    if (v.__pattern) return { __pattern: v.__pattern };
    if (t === 'object') return encode(v, 'ctx.arg');
    return String(v);
  };

  const makeGradient = (kind, args) => {
    const g = {
      __grad: `${kind}#${gradSeq}`,
      stops: [],
      addColorStop(offset, color) {
        const c = { offset: quantize(offset, 'grad'), color: norm(color) };
        g.stops.push(c);
        ops.push([`${kind}.stop`, gradSeq, c.offset, c.color]);
      },
    };
    gradSeq += 1;
    ops.push([kind, ...args.map((a) => norm(a))]);
    return g;
  };

  const impl = {
    createLinearGradient: (x0, y0, x1, y1) => makeGradient('lin', [x0, y0, x1, y1]),
    createRadialGradient: (x0, y0, r0, x1, y1, r1) => makeGradient('rad', [x0, y0, r0, x1, y1, r1]),
    createConicGradient: (a, x, y) => makeGradient('conic', [a, x, y]),
    createPattern: () => ({ __pattern: true, setTransform: () => {} }),
    measureText: (text) => ({ width: norm(String(text)).length * 0.6, actualBoundingBoxAscent: 8, actualBoundingBoxDescent: 2 }),
    getImageData: (x, y, w, h) => ({ width: w, height: h, data: new Uint8ClampedArray(Math.max(0, w * h * 4)) }),
    getLineDash: () => [],
    isPointInPath: () => false,
    isPointInStroke: () => false,
    getContextAttributes: () => ({ alpha: true, desynchronized: false }),
  };

  const canvas = {
    width, height, nodeType: 1, style: {},
    getContext: () => ctx,
    toDataURL: () => `data:,lookdev-canvas:${width}x${height}`,
  };

  const ctx = new Proxy({}, {
    get(_target, prop) {
      if (prop === 'canvas') return canvas;
      if (typeof prop !== 'string') return undefined;
      if (CTX_METHODS.has(prop)) {
        const builtin = impl[prop];
        return (...args) => {
          ops.push([prop, ...args.map((a) => norm(a))]);
          return builtin ? builtin(...args) : undefined;
        };
      }
      if (CTX_SETTERS.has(prop)) return state[prop] ?? null;
      throw new TypeError(`lookdev: unrecorded 2D member read "${String(prop)}" — add it to the recorder or exclude the scene`);
    },
    set(_target, prop, value) {
      if (typeof prop !== 'string' || !CTX_SETTERS.has(prop)) {
        throw new TypeError(`lookdev: unrecorded 2D member write "${String(prop)}" — add it to the recorder or exclude the scene`);
      }
      state[prop] = value;
      ops.push(['set', prop, norm(value)]);
      return true;
    },
    has: (_t, prop) => typeof prop === 'string' && (CTX_METHODS.has(prop) || CTX_SETTERS.has(prop) || prop === 'canvas'),
  });

  return { canvas, ctx, ops };
}

// ═══════════════════════════════════════════════════════════════════════════
// SCENE CONSTRUCTION PRIMITIVES
// ═══════════════════════════════════════════════════════════════════════════
/** Deterministic jitter so the rig's own seed is load-bearing (falsifier: seed). */
function seededJitter(seed, n) {
  // Same construction as art's PRNG (FNV-1a over the seed string) but kept local:
  // it is the harness's rig input, not the subject under test.
  let h1 = 0x811c9dc5, h2 = 0x811c9dc5 ^ 0xdeadbeef, h3 = 0x811c9dc5 ^ 0xcafebabe, h4 = 0x811c9dc5 ^ 0x12345678;
  for (let i = 0; i < seed.length; i += 1) {
    const c = seed.charCodeAt(i);
    h1 = Math.imul(h1 ^ c, 0x01000193); h2 = Math.imul(h2 ^ c, 0x01000193);
    h3 = Math.imul(h3 ^ c, 0x01000193); h4 = Math.imul(h4 ^ c, 0x01000193);
  }
  let s0 = h1 >>> 0, s1 = h2 >>> 0, s2 = h3 >>> 0, s3 = h4 >>> 0;
  const out = [];
  for (let i = 0; i < n; i += 1) {
    const result = (s0 + s3) >>> 0;
    const t = s1 << 9;
    s2 ^= s0; s3 ^= s1; s1 ^= s2; s0 ^= s3; s2 ^= t; s3 = (s3 << 11) | (s3 >>> 21);
    s0 >>>= 0; s1 >>>= 0; s2 >>>= 0; s3 >>>= 0;
    out.push(result / 0xffffffff);
  }
  return out;
}

function makeRigCamera(seed) {
  const j = seededJitter(seed, 6);
  const camera = new THREE.PerspectiveCamera(RIG.fov, RIG.width / RIG.height, RIG.near, RIG.far);
  camera.position.set(
    RIG.eye[0] + (j[0] - 0.5) * 2 * RIG.jitter,
    RIG.eye[1] + (j[1] - 0.5) * 2 * RIG.jitter,
    RIG.eye[2] + (j[2] - 0.5) * 2 * RIG.jitter,
  );
  camera.lookAt(
    RIG.look[0] + (j[3] - 0.5) * 2 * RIG.jitter,
    RIG.look[1] + (j[4] - 0.5) * 2 * RIG.jitter,
    RIG.look[2] + (j[5] - 0.5) * 2 * RIG.jitter,
  );
  camera.updateProjectionMatrix();
  camera.updateMatrixWorld();
  return camera;
}

function makeStage() {
  const stage = new THREE.Scene();
  stage.background = new THREE.Color(STAGE_PIN.background);
  stage.fog = new THREE.FogExp2(STAGE_PIN.fogColor, STAGE_PIN.fogDensity);
  return stage;
}

function makeRenderer() {
  const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false });
  renderer.setPixelRatio(1);
  renderer.setSize(RIG.width, RIG.height);
  renderer.toneMapping = THREE[r160KeyByToneName(TONE.toneMapping)];
  renderer.toneMappingExposure = TONE.toneMappingExposure;
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.shadowMap.enabled = false;
  return renderer;
}
function r160KeyByToneName(name) {
  // The name is the pin; resolve it through the double so a wrong constant is a
  // crash, not a silent zero.
  if (!(name in THREE)) throw new Error(`lookdev: unknown tone-mapping constant "${name}"`);
  return name;
}

/** Camera-projected anchors over the museum's deterministic architecture data. */
async function anchorSet(camera) {
  const arch = await importArt('patent-portfolio/museum/architecture.js');
  const { DIMENSIONS, COLONY_DATA, COLONY_ORDER } = arch;
  const rot = DIMENSIONS.rotunda;
  const wing = DIMENSIONS.wing;
  const gal = DIMENSIONS.gallery;
  const galleryOffset = wing.length + (wing.vestibuleDepth ?? 6) + gal.depth / 2;
  const named = [
    ['rotunda-floor', [0, DIMENSIONS.rotunda.floorY, 0]],
    ['rotunda-apex', [0, rot.height, 0]],
    ['dome-seam', [0, rot.domeStart, 0]],
    ['aperture', [rot.apertureOffset, rot.height, rot.apertureOffset * 0.5]],
    ['fano-sculpture', [0, rot.height * 0.45, 0]],
    ['visitor-eye', [0, 1.7, 0]],
    ['spark-wing-mouth', [rot.radius + 0.001, 1.7, 0]],
  ];
  for (const colony of COLONY_ORDER) {
    const angle = COLONY_DATA[colony].wingAngle;
    const cos = Math.cos(angle), sin = Math.sin(angle);
    named.push([`${colony}-wing-center`, [cos * (rot.radius + wing.length / 2), wing.corridorHeight, sin * (rot.radius + wing.length / 2)]]);
    named.push([`${colony}-gallery-center`, [cos * (rot.radius + galleryOffset), gal.height * 0.5, sin * (rot.radius + galleryOffset)]]);
  }
  return named.map(([name, p]) => {
    const v = new THREE.Vector3(p[0], p[1], p[2]);
    v.project(camera);
    return { name, world: p.map((n) => quantize(n, 'anchor')), ndc: [quantize(v.x, 'ndc'), quantize(v.y, 'ndc'), quantize(v.z, 'ndc')] };
  });
}

/**
 * Own-field state of an Object3D-derived node (light, camera) — every field the
 * module actually set, minus the scene graph. A new field on a light is a real
 * change to what gets uploaded to the GPU, so it must reach the receipt; this is
 * why there is no allow-list of light parameters here.
 */
const OBJECT_SKIP = new Set(['children', 'parent', 'matrixWorld', 'matrix', 'projectionMatrix', 'matrixWorldInverse', 'id']);
function objectState(o, where) {
  const out = { kind: o.kind ?? o.type ?? o.constructor.name, id: o.id };
  for (const k of Object.keys(o).sort()) {
    if (OBJECT_SKIP.has(k)) continue;
    const v = o[k];
    if (typeof v === 'function' || v === undefined) continue;
    out[k] = encode(v, `${where}.${k}`);
  }
  return out;
}
const lightNode = (o) => objectState(o, '$light');

function fogNode(fog) {
  if (!fog) return null;
  return { fog: fog.isFogExp2 ? 'FogExp2' : fog.isFog ? 'Fog' : 'Unknown', ...encode(fog, '$fog') };
}

function lightLeg(stage) {
  const lights = [];
  stage.traverse((o) => { if (o.isLight) lights.push(lightNode(o)); });
  return lights;
}

function countKind(stage, pred) {
  let n = 0;
  stage.traverse((o) => { if (pred(o)) n += 1; });
  return n;
}

function meshLeg(stage) {
  const meshes = [];
  stage.traverse((o) => {
    if (!o.isMesh) return;
    meshes.push({
      name: o.name || '',
      geometry: o.geometry ? { type: o.geometry.type, params: encode(o.geometry.parameters ?? null, '$geo') } : null,
      material: encode(o.material, '$mat'),
    });
  });
  return meshes;
}

/**
 * Runs `fn` with Math.random trapped and console silenced.
 * Math.random is the drift this harness exists to refuse: a pinned scene that
 * reaches for it is a bug, so it throws (naming the caller) instead of stamping
 * a different hash every run. console is silenced because the museum's own
 * `console.log` banners would make terminal output noisy, not wrong — they are
 * captured, not digested.
 */
export async function inDeterministicContext(fn) {
  const realRandom = Math.random;
  const realLog = console.log;
  const realWarn = console.warn;
  const logs = [];
  Math.random = () => { throw new Error('lookdev: Math.random() reached a pinned scene — the surface is not deterministic; exclude it (see COVERAGE)'); };
  console.log = (...a) => { logs.push(a.map(String).join(' ')); };
  console.warn = (...a) => { logs.push(`warn: ${a.map(String).join(' ')}`); };
  try {
    return { result: await fn(), logs };
  } finally {
    Math.random = realRandom;
    console.log = realLog;
    console.warn = realWarn;
  }
}

// ═══════════════════════════════════════════════════════════════════════════
// PINNED SCENES
// ═══════════════════════════════════════════════════════════════════════════
// A scene returns { kind, surfaces, graph } — the digest is taken over `graph`.
// `surfaces` names the real art modules the receipt exercises, so a reader can
// see what a flip implicates without opening the harness.

/** Museum lighting, zone-scripted over a pinned frame timeline. */
async function museumLightScene(id, { title, zoneScript, shadows, rigSeed, frames, delta, lightingModule }) {
  const { TurrellLighting } = await importArt(lightingModule ?? 'patent-portfolio/museum/lighting.js');
  const arch = await importArt('patent-portfolio/museum/architecture.js');
  return {
    id,
    kind: 'lookGraph',
    title,
    surfaces: [
      lightingModule ?? 'patent-portfolio/museum/lighting.js',
      'patent-portfolio/museum/architecture.js',
      'lib/design-tokens.js',
    ],
    run: async () => {
      dbl.reset();
      const stage = makeStage();
      const camera = makeRigCamera(rigSeed);
      const { result } = await inDeterministicContext(async () => {
        const lighting = new TurrellLighting(stage, camera);
        if (shadows) lighting.enableShadows(TIMELINE.shadowMap);
        let applied = null;
        const timeline = [];
        for (let f = 0; f < frames; f += 1) {
          const zone = zoneScript[f];
          if (zone !== undefined && zone !== applied) { lighting.setZone(zone); applied = zone; }
          const p = (f / Math.max(1, frames - 1)) * Math.PI * 2;
          const r = arch.DIMENSIONS.rotunda.radius * 0.3;
          lighting.update(delta, new THREE.Vector3(Math.cos(p) * r, 1.7, Math.sin(p) * r));
          if (f % TIMELINE.sampleEvery === 0) {
            timeline.push({
              frame: f,
              zone: lighting.currentZone ?? null,
              targetZone: lighting._targetZone ?? null,
              transition: quantize(lighting._zoneTransition ?? 0, 'transition'),
              time: quantize(lighting._time ?? 0, 'time'),
              fog: fogNode(stage.fog),
              sun: lighting.sunlight ? lightNode(lighting.sunlight) : null,
              wing: Object.fromEntries(Object.entries(lighting.wingLights || {}).map(([k, v]) => [k, {
                spotlight: lightNode(v.spotlight), hemi: lightNode(v.hemi), profile: encode(v.profile, '$profile'),
              }])),
              lights: lightLeg(stage),
            });
          }
        }
        // The dispose owner: after teardown the stage must hold no lights and no
        // strip meshes. This is V10's "one dispose owner" ask made load-bearing —
        // a lighting.js that leaks a light on dispose flips this receipt.
        const lightsBefore = countKind(stage, (o) => o.isLight);
        lighting.dispose();
        const lightsAfter = countKind(stage, (o) => o.isLight);
        const leaked = [...stage.children]
          .filter((o) => o.isLight || o.isMesh)
          .map((o) => o.kind ?? o.type ?? o.constructor.name);
        return { lighting, timeline, teardown: { lightsBefore, lightsAfter, leaked } };
      });
      const anchors = await anchorSet(camera);
      const renderer = makeRenderer();
      return {
        rig: {
          seed: rigSeed,
          frame: [RIG.width, RIG.height],
          camera: { ...objectState(camera, '$camera'), projectionMatrix: encode(camera.projectionMatrix, '$proj') },
          anchors,
        },
        tone: {
          ...TONE,
          resolvedToneMapping: renderer.toneMapping,
          exposure: renderer.toneMappingExposure,
          outputColorSpace: renderer.outputColorSpace,
          // Enum identity, so a three-version bump that renumbers the tone
          // curves (or moves AgX into the museum) is visible in the receipt.
          curveConstants: {
            NoToneMapping: THREE.NoToneMapping,
            LinearToneMapping: THREE.LinearToneMapping,
            ACESFilmicToneMapping: THREE.ACESFilmicToneMapping,
            AgXToneMapping: THREE.AgXToneMapping,
          },
        },
        background: encode(stage.background, '$bg'),
        timeline: result.timeline,
        teardown: result.teardown,
        tally: { events: [...recorder.events], disposes: [...recorder.disposes].sort() },
      };
    },
  };
}

/** The material + environment contract: one PMREM owner, one dispose owner. */
async function materialContractScene(id, { title, rigSeed, quality, normalMapSize, normalMapScale }) {
  const {
    createGradientEnvironmentMap, applyEnvironmentMapToScene, createProceduralNormalMap,
    disposeMaterial, MATERIAL_PRESETS, MATERIAL_QUALITY, setMaterialQuality, getColonyMaterial, COLONY_ORDER,
    initPMREMGenerator, setGlobalEnvMap, getGlobalEnvMap,
  } = await importArt('patent-portfolio/lib/materials.js');
  const { createMuseumMaterials } = await importArt('patent-portfolio/museum/architecture.js');
  return {
    id,
    kind: 'lookGraph',
    title,
    surfaces: [
      'patent-portfolio/lib/materials.js',
      'patent-portfolio/museum/architecture.js (createMuseumMaterials)',
      'lib/design-tokens.js',
    ],
    run: async () => {
      dbl.reset();
      const stage = makeStage();
      const renderer = makeRenderer();
      const camera = makeRigCamera(rigSeed);
      const { result, logs } = await inDeterministicContext(async () => {
        // materials.js carries three module-level singletons — currentQuality,
        // pmremGenerator and globalEnvMap. A scene whose inputs include leftovers
        // from a previous run is not a pinned scene, so each is reset through the
        // module's OWN exported setter before anything is built. (Finding for the
        // ledger: in the browser the same singletons mean a second museum init
        // silently reuses the first run's PMREM texture, even after its target was
        // disposed — which is exactly the drift this harness is meant to reveal.)
        setGlobalEnvMap(null);
        setMaterialQuality(quality);
        // materials.js keeps its PMREMGenerator in a module-level singleton, so a
        // second run in the same process would skip construction and change the
        // event tally — i.e. the receipt would depend on run history. Re-mint
        // through the module's OWN exported owner before asking it for an env map.
        initPMREMGenerator(renderer);
        if (getGlobalEnvMap()) {
          throw new Error('lookdev: globalEnvMap is non-null after setGlobalEnvMap(null) — the ' +
            'material table would digest a previous run\'s environment; refusing to stamp');
        }
        const table = createMuseumMaterials();
        const normalMap = createProceduralNormalMap(normalMapSize, normalMapScale);
        const colonyMaterials = {};
        for (const colony of COLONY_ORDER) {
          colonyMaterials[colony] = {
            standard: encode(getColonyMaterial(colony, 'standard'), '$m'),
            crystal: encode(MATERIAL_PRESETS.COLONY_CRYSTAL(colony), '$m'),
            emissive: encode(MATERIAL_PRESETS.COLONY_EMISSIVE(colony), '$m'),
            hologram: encode(MATERIAL_PRESETS.COLONY_HOLOGRAM(colony), '$m'),
          };
        }
        const surfaces = [
          { name: 'floor', factory: MATERIAL_PRESETS.FLOOR_POLISHED },
          { name: 'floorMatte', factory: MATERIAL_PRESETS.FLOOR_MATTE },
          { name: 'wall', factory: MATERIAL_PRESETS.WALL_DARK },
          { name: 'wallLight', factory: MATERIAL_PRESETS.WALL_LIGHT },
        ];
        const presets = {};
        surfaces.forEach(({ name, factory }, i) => {
          const m = factory();
          const mesh = new THREE.Mesh(new THREE.BoxGeometry(10, 0.2, 10 + i), m);
          mesh.name = `probe-${name}`;
          mesh.position.set(i * 3 - 6, 0, 0);
          stage.add(mesh);
          presets[name] = encode(m, '$m');
        });
        // The PMREM owner: exactly one generator, one cube target, one fromCubemap.
        const envMap = createGradientEnvironmentMap(renderer);
        const appliedCount = applyEnvironmentMapToScene(stage, envMap, 1.0);
        const afterApply = meshLeg(stage);
        // The dispose owner: everything this scene built must be released.
        stage.traverse((o) => { if (o.isMesh) { o.geometry.dispose(); disposeMaterial(o.material); } });
        Object.values(table).forEach((m) => disposeMaterial(m));
        normalMap.dispose();
        envMap.dispose?.();
        renderer.dispose?.();
        return {
          table: Object.fromEntries(Object.entries(table).map(([k, m]) => [k, encode(m, '$table')])),
          normalMap: encode(normalMap, '$normal'),
          colonyMaterials, presets, afterApply, appliedCount,
          envMap: encode(envMap, '$env'),
        };
      });
      const anchors = await anchorSet(camera);
      return {
        rig: {
          seed: rigSeed,
          frame: [RIG.width, RIG.height],
          camera: { ...objectState(camera, '$camera'), projectionMatrix: encode(camera.projectionMatrix, '$proj') },
          anchors,
        },
        quality: { requested: quality, active: encode(MATERIAL_QUALITY[quality], '$q') },
        pmrem: { owner: 'createGradientEnvironmentMap', events: [...recorder.events], disposes: [...recorder.disposes].sort() },
        materialTable: result.table,
        proceduralNormalMap: { size: normalMapSize, scale: normalMapScale, node: result.normalMap },
        colonyMaterials: result.colonyMaterials,
        presets: result.presets,
        envApplication: { applied: result.appliedCount, map: result.envMap, meshes: result.afterApply },
        announcements: { count: logs.length },
      };
    },
  };
}

/** Colony palette atlas — art's deterministic "atlas render" surface at this base. */
async function colonyAtlasScene(id, { title, seeds }) {
  const { getPalette, getColonies, COLONY_PALETTES } = await importArt('gen/lib/palette.js');
  const { PRNG } = await importArt('gen/lib/prng.js');
  const { COLONY_COLORS } = await importArt('lib/design-tokens.js');
  return {
    id,
    kind: 'lookGraph',
    title,
    surfaces: ['gen/lib/palette.js', 'gen/lib/prng.js', 'lib/design-tokens.js'],
    run: async () => {
      const { result, logs } = await inDeterministicContext(() => {
        const colonies = getColonies();
        const cells = [];
        seeds.forEach((seed, si) => {
          colonies.forEach((colony, ci) => {
            const rng = new PRNG(`${seed}:${colony}`);
            const p = getPalette(colony, rng);
            cells.push({
              cell: [si, ci],
              seed, colony,
              base: encode(COLONY_PALETTES[colony], '$base'),
              token: COLONY_COLORS && COLONY_COLORS[colony] ? encode(COLONY_COLORS[colony], '$token') : null,
              palette: encode(p, '$palette'),
              shifted: encode(getPalette(colony, rng), '$shifted'),
            });
          });
        });
        return { grid: { seeds, colonies, cells: [seeds.length, colonies.length] }, cells };
      });
      return { ...result, announcements: logs.length };
    },
  };
}

/** The real 2D generative pipeline, recorded as an op stream. */
async function sparkFrameScene(id, { title, seed, canvasSize }) {
  const spark = await importArt('gen/algorithms/spark/algo.js');
  return {
    id,
    kind: 'drawStream',
    title,
    surfaces: ['gen/algorithms/spark/algo.js', 'gen/lib/genux.js', 'gen/lib/palette.js', 'gen/lib/prng.js'],
    run: async () => {
      const { result } = await inDeterministicContext(() => {
        const { canvas, ops } = makeRecordingCanvas(canvasSize, canvasSize);
        const meta = spark.default(canvas, seed);
        return {
          seed,
          canvas: [canvasSize, canvasSize],
          meta: encode(meta, '$meta'),
          ops: { count: ops.length, stream: ops.map((o) => encode(o, '$op')) },
        };
      });
      return result;
    },
  };
}

// ═══════════════════════════════════════════════════════════════════════════
// CORPUS
// ═══════════════════════════════════════════════════════════════════════════
/** The zone script: rotunda the whole walk (hero view) — one pinned entry beat. */
const HERO_ZONES = {};
/** Enter at the rotunda, commit to the Forge wing at frame 72 (mid-timeline). */
const WING_ZONES = { 0: 'rotunda', 72: 'forge' };

export async function corpus(pins = {}) {
  const p = { ...defaultPins(), ...pins };
  return [
    await museumLightScene('museum.rotunda-hero', {
      title: 'Museum rotunda hero view — TurrellLighting entry state + god-ray breathing',
      zoneScript: p.zoneHero, shadows: false, rigSeed: p.rigSeed, frames: p.frames, delta: p.delta,
    }),
    await museumLightScene('museum.wing-forge', {
      title: 'Rotunda→Forge wing zone commit — per-wing profile, ganzfeld density, shadowed key',
      zoneScript: p.zoneWing, shadows: true, rigSeed: p.rigSeed, frames: p.frames, delta: p.delta,
    }),
    await materialContractScene('museum.material-and-env-contract', {
      title: 'One PMREM owner, one dispose owner — museum material table + colony presets + procedural normal bytes',
      rigSeed: p.rigSeed, quality: p.quality, normalMapSize: p.normalMapSize, normalMapScale: p.normalMapScale,
    }),
    await colonyAtlasScene('gen.colony-atlas', {
      title: 'Colony palette atlas — 7 colonies × 3 seeds through the real PRNG/palette pair',
      seeds: p.atlasSeeds,
    }),
    await sparkFrameScene('gen.spark-frame-1024', {
      title: 'Spark generative frame — full 2D draw-op stream for the canonical seed',
      seed: p.genSeed, canvasSize: p.genCanvas,
    }),
  ];
}

function defaultPins() {
  return {
    rigSeed: RIG.seed,
    frames: TIMELINE.frames,
    delta: TIMELINE.delta,
    zoneHero: HERO_ZONES,
    zoneWing: WING_ZONES,
    quality: MATERIAL_PIN.quality,
    normalMapSize: MATERIAL_PIN.normalMapSize,
    normalMapScale: MATERIAL_PIN.normalMapScale,
    atlasSeeds: GEN_PIN.atlasSeeds,
    genSeed: GEN_PIN.seed,
    genCanvas: GEN_PIN.canvas,
  };
}

/** Sensitivity table: which axis is REQUIRED to move which scene. */
export const SENSITIVITY = {
  // Every museum scene carries the pinned rig, so the rig seed reaches all three.
  seed: ['museum.rotunda-hero', 'museum.wing-forge', 'museum.material-and-env-contract'],
  frames: ['museum.rotunda-hero', 'museum.wing-forge'],
  delta: ['museum.rotunda-hero', 'museum.wing-forge'],
  normalMap: ['museum.material-and-env-contract'],
  quality: ['museum.material-and-env-contract'],
  genSeed: ['gen.spark-frame-1024'],
  canvas: ['gen.spark-frame-1024'],
  atlasSeeds: ['gen.colony-atlas'],
};

export const PERTURB = {
  seed: { rigSeed: `${RIG.seed}-perturbed` },
  frames: { frames: TIMELINE.frames + 1 },
  delta: { delta: TIMELINE.delta * (1 + 1 / 1024) },
  normalMap: { normalMapSize: MATERIAL_PIN.normalMapSize + 2 },
  quality: { quality: MATERIAL_PIN.quality === 'ultra' ? 'low' : 'ultra' },
  canvas: { genCanvas: GEN_PIN.canvas + 1 },
  genSeed: { genSeed: `${GEN_PIN.seed}-perturbed` },
  atlasSeeds: { atlasSeeds: [GEN_PIN.atlasSeeds[0], GEN_PIN.atlasSeeds[1], `${GEN_PIN.atlasSeeds[2]}-x`] },
};

/**
 * @returns {{scenes: Array, byId: Object, contract: string}}
 */
export async function runAll(pins = {}) {
  const merged = { ...defaultPins(), ...pins };
  const scenes = [];
  for (const spec of await corpus(merged)) {
    const started = Date.now();
    const graph = await spec.run();
    const receipt = {
      id: spec.id,
      kind: spec.kind,
      title: spec.title,
      surfaces: spec.surfaces,
      graph,
      hash: digestOf(graph),
      bytes: canonical(graph).length,
      ms: Date.now() - started,
    };
    scenes.push(receipt);
  }
  return { contract: CONTRACT, scenes, byId: Object.fromEntries(scenes.map((s) => [s.id, s])) };
}

export function readReceipts(file = RECEIPT_FILE) {
  try {
    return JSON.parse(readFileSync(file, 'utf8'));
  } catch (err) {
    if (err.code === 'ENOENT') return null;
    throw new Error(`lookdev: receipts file ${file} is unreadable (${err.message}) — re-stamp with --update`);
  }
}

export function writeReceipts(report, file = RECEIPT_FILE) {
  const payload = {
    contract: CONTRACT,
    pinnedAtBase: process.env.LOOKDEV_BASE || 'unknown',
    note: 'Drift signal over the look graph of the pinned scenes, NOT a pixel proof. ' +
      'Generated by tests/lookdev/lookdev.mjs --update; never hand-edit. A flip means ' +
      'a lighting/material/palette surface moved — inspect the diff before re-stamping.',
    scenes: Object.fromEntries(report.scenes.map((s) => [s.id, {
      kind: s.kind, hash: s.hash, bytes: s.bytes, surfaces: s.surfaces, title: s.title,
    }])),
  };
  writeFileSync(file, `${JSON.stringify(payload, null, 2)}\n`, 'utf8');
  return payload;
}

// ═══════════════════════════════════════════════════════════════════════════
// SOURCE DRILL — the falsifier that needs no write to a lane's file
// ═══════════════════════════════════════════════════════════════════════════
/**
 * The harness constants prove the receipts see their own inputs. This proves the
 * receipts see the SUBJECT's source: it copies patent-portfolio/museum/lighting.js
 * into a scratch tree under the temp dir, changes ONE digit of one constant
 * there, and runs the pinned wing scene against (a) the untouched copy and (b) the
 * edited copy. The untouched copy MUST reproduce the stamped hash — otherwise the
 * scratch path/shim machinery, not the edit, is what moved the number. The edited
 * copy MUST differ — otherwise a lighting edit could fold with every receipt
 * still green, which is the failure V10 is about.
 *
 * Nothing in the repo is written: the in-flight lanes own those files, so the
 * drill operates on a copy and Node resolves its `./architecture.js` /
 * `../../lib/design-tokens.js` imports back to the real modules by realpath.
 */
export const DRILL = {
  subject: 'patent-portfolio/museum/lighting.js',
  pattern: 'kelvin: 2700',
  replacement: 'kelvin: 2701',
  scene: 'museum.wing-forge',
};

async function drillSceneSpec(id, lightingModule) {
  const pins = defaultPins();
  return museumLightScene(id, {
    title: 'drill',
    zoneScript: pins.zoneWing,
    shadows: true,
    rigSeed: pins.rigSeed,
    frames: pins.frames,
    delta: pins.delta,
    lightingModule,
  });
}

export async function runDrill() {
  const root = join(tmpdir(), `art-lookdev-drill-${process.pid}`);
  const museum = join(root, 'patent-portfolio/museum');
  rmSync(root, { recursive: true, force: true });
  mkdirSync(museum, { recursive: true });
  try {
    symlinkSync(join(REPO, 'patent-portfolio', 'lib'), join(root, 'patent-portfolio', 'lib'), 'dir');
    // The subject's own imports resolve back into the repo by realpath, so the
    // drill swaps exactly one module and inherits every other byte of the tree.
    symlinkSync(join(REPO, 'patent-portfolio', 'museum', 'architecture.js'), join(museum, 'architecture.js'), 'file');
    symlinkSync(join(REPO, 'lib'), join(root, 'lib'), 'dir');

    const source = readFileSync(join(REPO, DRILL.subject), 'utf8');
    const control = join(museum, 'lighting-control.js');
    const edited = join(museum, 'lighting-edited.js');
    writeFileSync(control, source, 'utf8');
    const hits = source.split(DRILL.pattern).length - 1;
    if (hits < 1) {
      throw new Error(`lookdev drill: precondition failed — "${DRILL.pattern}" not found in ${DRILL.subject} ` +
        '(the subject constant moved; update DRILL.pattern — a drill that edits nothing proves nothing)');
    }
    writeFileSync(edited, source.split(DRILL.pattern).join(DRILL.replacement), 'utf8');

    const controlHash = digestOf(await (await drillSceneSpec('drill.control', control)).run());
    const editedHash = digestOf(await (await drillSceneSpec('drill.edited', edited)).run());
    const pinned = readReceipts()?.scenes?.[DRILL.scene]?.hash ?? null;
    return {
      root, hits, controlHash, editedHash, pinnedHash: pinned,
      controlMatchesPinned: pinned !== null && controlHash === pinned,
      editedDiffers: editedHash !== controlHash && editedHash !== pinned,
    };
  } finally {
    rmSync(root, { recursive: true, force: true });
  }
}

// ═══════════════════════════════════════════════════════════════════════════
// CLI
// ═══════════════════════════════════════════════════════════════════════════
async function main(argv) {
  const flags = new Set(argv.filter((a) => a.startsWith('--') && !a.includes('=')));
  const kv = Object.fromEntries(argv
    .filter((a) => a.startsWith('--') && a.includes('='))
    .map((a) => { const i = a.indexOf('='); return [a.slice(2, i), a.slice(i + 1)]; }));

  if (flags.has('--list')) {
    const report = await runAll();
    for (const s of report.scenes) {
      console.log(`${s.id}  [${s.kind}]  ${s.bytes} bytes  hash ${s.hash.slice(0, 16)}…`);
      for (const surf of s.surfaces) console.log(`    ↳ ${surf}`);
    }
    console.log('\nDeclared coverage boundary:');
    for (const c of COVERAGE) console.log(`    (${c.kind}) ${c.surface}`);
    return 0;
  }

  if (flags.has('--drill')) {
    const d = await runDrill();
    const ok = d.controlMatchesPinned && d.editedDiffers;
    console.log(`${ok ? 'PASS' : 'FAIL'} source drill on ${DRILL.subject} (${d.hits} occurrence(s) of "${DRILL.pattern}")`);
    console.log(`  control (untouched copy)  ${d.controlHash.slice(0, 32)}  -> pinned ${DRILL.scene}: ${d.controlMatchesPinned ? 'MATCH' : 'MISMATCH'}`);
    console.log(`  edited  ("${DRILL.replacement}")        ${d.editedHash.slice(0, 32)}  -> ${d.editedDiffers ? 'DIFFERS (receipt is source-sensitive)' : 'IDENTICAL (receipt cannot see a lighting edit!)'}`);
    if (!d.controlMatchesPinned) console.log('  the scratch run does not reproduce the stamped receipt, so the edit result is untrustworthy');
    return ok ? 0 : 1;
  }

  if (kv.falsify) {
    const axes = kv.falsify === 'all' ? Object.keys(PERTURB) : [kv.falsify];
    const baseline = await runAll();
    let rc = 0;
    for (const axis of axes) {
      const pins = PERTURB[axis];
      if (!pins) { console.error(`lookdev: unknown falsifier axis "${axis}" (${Object.keys(PERTURB).join('|')})`); rc = 1; continue; }
      const moved = await runAll(pins);
      const required = SENSITIVITY[axis] || [];
      const changes = [];
      for (const s of moved.scenes) {
        const before = baseline.byId[s.id].hash;
        if (before !== s.hash) changes.push(s.id);
      }
      const missing = required.filter((id) => !changes.includes(id));
      const unexpected = changes.filter((id) => !required.includes(id));
      // Exact set, not "at least": an axis that moves surfaces it has no
      // business moving is the same blindness wearing a different hat.
      const ok = changes.length > 0 && missing.length === 0 && unexpected.length === 0;
      if (!ok) rc = 1;
      console.log(`${ok ? 'PASS' : 'FAIL'} falsify ${axis}: ${changes.length}/${moved.scenes.length} scene hashes moved` +
        (changes.length ? `\n    moved: ${changes.join(', ')}` : '') +
        (missing.length ? `\n    REQUIRED but unchanged: ${missing.join(', ')} — the receipt cannot see this axis` : '') +
        (unexpected.length ? `\n    MOVED but not declared: ${unexpected.join(', ')} — the axis leaks into surfaces it should not reach` : '') +
        (changes.length === 0 ? '\n    the corpus is blind to this axis' : ''));
    }
    return rc;
  }

  const report = await runAll();
  if (flags.has('--update')) {
    writeReceipts(report);
    console.log(`stamped ${report.scenes.length} scene receipts -> ${RECEIPT_FILE}`);
    for (const s of report.scenes) console.log(`  ${s.id}\t${s.hash}`);
    return 0;
  }

  const stamped = readReceipts();
  if (!stamped) {
    console.error('lookdev: no receipts.json — stamp the corpus with --update first.');
    return 1;
  }
  let drift = 0;
  const rows = [];
  for (const s of report.scenes) {
    const prior = stamped.scenes?.[s.id];
    const status = !prior ? 'NEW' : prior.hash === s.hash ? 'same' : 'DRIFT';
    if (status !== 'same') drift += 1;
    rows.push({ id: s.id, kind: s.kind, hash: s.hash, status, prior: prior?.hash ?? null, bytes: s.bytes });
  }
  for (const id of Object.keys(stamped.scenes ?? {})) {
    if (!report.byId[id]) { rows.push({ id, status: 'REMOVED', hash: null, prior: stamped.scenes[id].hash }); drift += 1; }
  }
  if (stamped.contract && stamped.contract !== CONTRACT) {
    console.error(`lookdev: contract mismatch — receipts stamped under "${stamped.contract}", harness is "${CONTRACT}"`);
    drift += 1;
  }

  if (flags.has('--json')) {
    console.log(JSON.stringify({ contract: CONTRACT, drift, rows, coverage: COVERAGE }, null, 2));
  } else {
    for (const r of rows) {
      const tag = r.status === 'same' ? 'same ' : r.status === 'DRIFT' ? 'DRIFT' : r.status === 'NEW' ? 'NEW ' : 'GONE';
      console.log(`${tag}  ${r.id}  ${r.hash ? r.hash.slice(0, 16) : '—'}`);
      if (r.status === 'DRIFT') console.log(`         was ${String(r.prior).slice(0, 16)}`);
    }
    console.log(drift === 0
      ? `\nlook: ${report.scenes.length} pinned scenes, 0 drift — the corpus matches receipts.json.`
      : `\nlook: ${drift} of ${report.scenes.length} pinned scenes DRIFTED from receipts.json.`);
    if (drift > 0) {
      console.log('Inspect the lighting/material/palette diff before re-stamping:');
      console.log('  node tests/lookdev/lookdev.mjs --update');
    }
  }
  return drift === 0 ? 0 : 1;
}

const invokedDirectly = process.argv[1] && resolve(process.argv[1]) === resolve(fileURLToPath(import.meta.url));
if (invokedDirectly) {
  try {
    process.exitCode = await main(process.argv.slice(2));
  } catch (err) {
    console.error(`lookdev: FAILED — ${err && err.stack ? err.stack : err}`);
    process.exitCode = 1;
  }
}
