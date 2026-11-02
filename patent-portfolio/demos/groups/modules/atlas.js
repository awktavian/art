/**
 * atlas.js — the controller. Loads the generated data, builds the layout,
 * mounts the DOM, owns the camera, and exposes the hook the determinism
 * falsifier drives: `window.__atlas.renderDeterministic(...)`.
 *
 * Two camera paths, deliberately separate:
 *
 *   interactive — clock-driven flythrough (one turn per CAMERA_PERIOD_MS, a
 *     Fibonacci 6100 ms), drag to orbit, wheel to dolly, click or keyboard to
 *     focus a group. Adaptive resolution observes frame times and steps the
 *     render scale, announcing every step in the HUD.
 *   deterministic — no clock, no pointer, no adaptive policy. The caller pins
 *     seed, frame count, viewport and camera phase; the renderer mixes one
 *     sample per pixel per step. Two calls with the same arguments are the same
 *     bytes, which is the whole point of `tools/determinism.mjs`.
 *
 * `prefers-reduced-motion` is honoured in both: under it the piece renders a
 * static, converged frame with the camera held at its declared opening phase
 * and no accumulation animation, and nothing in the loop reads a clock.
 */

import { buildLayout, pickNode, cameraPoseAt, LAYOUT_SCHEMA, LIE_FOLD_ANGLE } from "./layout.js";
import { AtlasRenderer } from "./renderer.js";
import { mountUI } from "./ui.js";
import { makeProvenanceReader } from "./describe.js";
import { rayThrough, lookAt, frustum } from "./mat4.js";

const DATA_PATH = "./data/cfsg-families.json";
const PROV_PATH = "./data/provenance.json";

/** Opening phase of the flythrough: the Monster and E8 both in frame. */
export const OPENING_PHASE = 0.09;

export async function startAtlas(rootEl, opts = {}) {
  const [data, provenance] = await Promise.all([
    fetchJSON(opts.dataPath || DATA_PATH),
    fetchJSON(opts.provPath || PROV_PATH).catch(() => null),
  ]);
  const prov = makeProvenanceReader(provenance);
  const layout = buildLayout(data, prov);

  const api = { hover: -1, focus: -1, seed: hashSeedToUint(opts.seed ?? "cfsg-atlas") };
  let ui = null;
  let renderer = null;
  const motion = {
    reduce: typeof matchMedia === "function"
      ? matchMedia("(prefers-reduced-motion: reduce)").matches
      : false,
  };
  if (typeof matchMedia === "function") {
    const mq = matchMedia("(prefers-reduced-motion: reduce)");
    mq.addEventListener?.("change", (e) => {
      motion.reduce = e.matches;
      if (motion.reduce) stopLoop();
      else startLoop();
      paintHud();
    });
  }

  // One object is both the pointer state and the UI's callback surface: a hover
  // arriving from the keyboard list and a hover arriving from a mouse move then
  // cannot drift apart, and wirePointer's `api.hoverNode(...)` is really there.
  api.focusNode = (index) => {
    api.focus = index;
    ui.showNode(index);
    if (motion.reduce) renderStatic();
    else startConverge();
  };
  api.hoverNode = (index) => {
    if (index === api.hover) return;
    api.hover = index;
    ui.showNode(index);
    if (motion.reduce) renderStatic(24);
    else startConverge();
  };

  ui = mountUI(rootEl, { layout, data, prov, api });

  const camera = {
    phase: OPENING_PHASE,
    yawOffset: 0,
    pitchOffset: 0,
    dolly: 1,
    target: [...layout.camera.target],
    pos: [0, 0, 0],
  };

  try {
    renderer = new AtlasRenderer(ui.canvas, layout, { frameBudgetMs: opts.frameBudgetMs ?? 22 });
  } catch (error) {
    // No context, or a shader that would not compile — either way the traced
    // image is absent and the page says so rather than showing a black box.
    rootEl.prepend(note(`The path-traced view could not start — ${error.message}. The layout, the data and the provenance sidecar are all still here; only the traced image is not.`));
    renderer = null;
  }


  function sizeStage() {
    if (!renderer) return;
    const rect = ui.canvas.getBoundingClientRect();
    const w = Math.max(320, Math.round(rect.width || 900));
    const h = Math.max(240, Math.round((rect.height || (w * 9) / 16) || (w * 9) / 16));
    renderer.resize(w, h);
  }

  function updateCamera() {
    const pose = cameraPoseAt(camera.phase, layout.camera);
    const r = Math.hypot(pose[0], pose[2]) * camera.dolly;
    const yaw = camera.yawOffset;
    const base = Math.atan2(pose[2], pose[0]);
    camera.pos = [
      Math.cos(base + yaw) * r,
      pose[1] + camera.pitchOffset * 6,
      Math.sin(base + yaw) * r,
    ];
    const focus = api.focus >= 0 ? layout.nodes[api.focus].pos : layout.camera.target;
    for (let k = 0; k < 3; k += 1) {
      const d = focus[k] - camera.target[k];
      // Snap the exponential chase once it is inside the pose signature's
      // precision, so "paused" means the camera is genuinely still and the
      // accumulator can converge instead of restarting forever on a 1e-7 wiggle.
      camera.target[k] += Math.abs(d) < 1e-4 ? d : d * 0.06;
    }
  }

  let running = false;
  let raf = 0;
  let lastTs = 0;
  let frameIndex = 0;

  function step(ts) {
    if (!running || !renderer) return;
    // The unclamped interval is the real presented-frame cadence and is what
    // adaptive resolution is judged on; the clamped one only drives the camera,
    // so a 4-second stall in a background tab cannot teleport the flythrough.
    const sincePrev = lastTs ? ts - lastTs : 16;
    const dt = lastTs ? Math.min(0.05, sincePrev / 1000) : 0.016;
    lastTs = ts;
    if (!motion.reduce) camera.phase = (camera.phase + dt / (layout.camera.periodMs / 1000)) % 1;
    updateCamera();
    renderer.renderStep({ pos: camera.pos, target: camera.target, fovYDeg: layout.camera.fovYDeg }, {
      seed: api.seed,
      frameIndex,
      time: ts / 1000,
      focus: api.focus,
      hover: api.hover,
      foldAngle: LIE_FOLD_ANGLE,
    });
    frameIndex += 1;
    renderer.observeFrame(sincePrev);
    paintHud();
    raf = requestAnimationFrame(step);
  }

  /*
   * Pausing the flythrough is not "freeze the canvas" — it is the moment the
   * path tracer gets to denoise. The camera is still, so the accumulator is
   * allowed to build, and the image converges sample by sample in front of you
   * (capped, so a stalled tab is not asked to render forever).
   */
  let convergeRaf = 0;
  function stopConverge() {
    if (convergeRaf) cancelAnimationFrame(convergeRaf);
    convergeRaf = 0;
  }
  function startConverge(cap = 96) {
    if (!renderer || running || motion.reduce) return;
    stopConverge();
    const tick = (ts) => {
      if (running || motion.reduce) { convergeRaf = 0; return; }
      updateCamera();
      renderer.renderStep({ pos: camera.pos, target: camera.target, fovYDeg: layout.camera.fovYDeg }, {
        seed: api.seed,
        frameIndex,
        time: ts / 1000,
        focus: api.focus,
        hover: api.hover,
        foldAngle: LIE_FOLD_ANGLE,
      });
      frameIndex += 1;
      paintHud();
      convergeRaf = renderer.frameCount < cap ? requestAnimationFrame(tick) : 0;
    };
    convergeRaf = requestAnimationFrame(tick);
  }

  function startLoop() {
    if (running || !renderer || motion.reduce) return;
    stopConverge();
    running = true;
    lastTs = 0;
    raf = requestAnimationFrame(step);
    ui.playButton.textContent = "Pause flythrough";
    ui.playButton.setAttribute("aria-pressed", "true");
  }
  function stopLoop() {
    running = false;
    cancelAnimationFrame(raf);
    if (ui) {
      ui.playButton.textContent = "Play flythrough";
      ui.playButton.setAttribute("aria-pressed", "false");
    }
  }

  function paintHud() {
    if (!ui) return;
    if (!renderer) {
      ui.setHud({ buffer: "none (no WebGL2)", motion: motion.reduce ? "reduced" : "full", res: "—", dpr: "—", adapt: "—", frames: 0 });
      return;
    }
    ui.setHud({
      // Under a moving camera the accumulator restarts every frame (averaging
      // different viewpoints would be a ghost, not a denoise), so the sample
      // count says so instead of silently reading "1".
      frames: renderer.moving ? `${renderer.frameCount} (pose resets each frame — pause to converge)` : renderer.frameCount,
      res: `${renderer.pixelSize[0]}×${renderer.pixelSize[1]}`,
      dpr: `${renderer.dpr}`,
      buffer: renderer.hdr ? "RGBA16F" : "RGBA8 (no EXT_color_buffer_float)",
      adapt: `${renderer.scale.toFixed(2)}${renderer.adaptations.length ? ` (${renderer.adaptations.length} step${renderer.adaptations.length === 1 ? "" : "s"})` : ""}`,
      spp: renderer.samplesPerPixel,
      pixelBudget: renderer.pixelBudget,
      motion: motion.reduce ? "reduced (static)" : "full",
    });
  }

  /** One converged frame, no clock, no motion. This is what reduced-motion means. */
  function renderStatic(samples = 48) {
    if (!renderer) return null;
    sizeStage();
    renderer.reset();
    camera.phase = OPENING_PHASE;
    updateCamera();
    for (let i = 0; i < samples; i += 1) {
      renderer.renderStep({ pos: camera.pos, target: camera.target, fovYDeg: layout.camera.fovYDeg }, {
        seed: api.seed,
        frameIndex: i,
        time: 0,
        focus: api.focus,
        hover: api.hover,
        foldAngle: LIE_FOLD_ANGLE,
      });
    }
    paintHud();
    return renderer.frameCount;
  }

  wirePointer(ui.canvas, layout, renderer, camera, api, { motion, renderStatic, paintHud, startConverge });

  ui.playButton.addEventListener("click", () => {
    if (running) { stopLoop(); startConverge(); } else startLoop();
  });
  ui.resetButton.addEventListener("click", () => {
    if (!renderer) return;
    renderer.reset();
    frameIndex = 0;
    if (motion.reduce) renderStatic();
    else if (!running) startConverge();
    paintHud();
  });
  ui.seedButton.addEventListener("click", () => {
    api.seed = (api.seed * 1664525 + 1013904223) >>> 0;
    if (renderer) renderer.reset();
    frameIndex = 0;
    if (motion.reduce) renderStatic();
    else if (!running) startConverge();
    paintHud();
  });

  if (renderer) {
    sizeStage();
    if (motion.reduce) renderStatic();
    else startLoop();
  }
  paintHud();
  ui.showNode(-1);

  /**
   * The falsifier's entry point. Deterministic by construction: fixed viewport,
   * fixed scale, fixed camera phase, no clock, seeded sampler.
   */
  const deterministic = async ({
    seed = api.seed,
    frames = 8,
    width = 480,
    height = 300,
    phase = OPENING_PHASE,
    reduced = false,
  } = {}) => {
    if (!renderer) return { mode: "no-webgl", frames: 0 };
    // A pinned frame is pinned at the size the caller asked for: the pixel
    // budget that reshapes the interactive view is explicitly not applied here,
    // and the stage is put back the moment the bytes are in hand.
    const prevScale = renderer.scale;
    renderer.scale = 1;
    renderer.resize(width, height, 1, { budgeted: false });
    renderer.reset();
    const pose = cameraPoseAt(phase, layout.camera);
    const cam = { pos: pose, target: [...layout.camera.target], fovYDeg: layout.camera.fovYDeg };
    for (let i = 0; i < frames; i += 1) {
      renderer.renderStep(cam, {
        seed: seed >>> 0,
        frameIndex: i,
        time: 0,
        focus: -1,
        hover: -1,
        foldAngle: LIE_FOLD_ANGLE,
      });
    }
    const accum = renderer.readAccumulation();
    const display = renderer.readCanvasRGBA();
    const out = {
      mode: renderer.hdr ? "gpu-rgba16f" : "gpu-rgba8",
      frames: renderer.frameCount,
      reducedMotion: reduced,
      width: renderer.pixelSize[0],
      height: renderer.pixelSize[1],
      seed: seed >>> 0,
      phase,
      layoutSchema: LAYOUT_SCHEMA,
      accumSha: await sha256Hex(accum),
      displaySha: await sha256Hex(display),
      // the tonemapped canvas as a real PNG, for a byte-level second opinion
      pngSha: await pngSha(ui.canvas),
      pinnedSizeUnbudgeted: true,
      nodeCount: layout.nodes.length,
      pointCount: layout.points.length,
      filamentCount: layout.filaments.length,
    };
    // hand the stage back to the interactive policy
    renderer.scale = prevScale;
    sizeStage();
    if (!motion.reduce && !running) startConverge();
    return out;
  };

  const publicApi = {
    ready: true,
    layout,
    stats: layout.stats,
    data,
    provenance: prov,
    renderer: () => renderer,
    deterministic,
    renderStatic,
    motion,
    /**
     * Which of the four passes are in the composite. A path-traced image made
     * of four passes is only debuggable if each one can be taken out of it, so
     * the switch is part of the piece, not a leftover.
     */
    setLayers(next) {
      if (!renderer) return null;
      Object.assign(renderer.layers, next || {});
      renderer.reset();
      if (motion.reduce) renderStatic(16);
      else if (!running) startConverge(16);
      return { ...renderer.layers };
    },
    layers: () => (renderer ? { ...renderer.layers } : null),
    layoutSha: () => sha256Hex(canonicalLayoutBytes(layout)),
    reduceMotion: (on) => {
      motion.reduce = on;
      if (on) stopLoop();
      renderStatic();
      paintHud();
    },
    openingPhase: OPENING_PHASE,
  };
  if (typeof window !== "undefined") window.__atlas = publicApi;
  return publicApi;
}

function canonicalLayoutBytes(layout) {
  // Fixed-precision decimal text: the same bytes in node and in Chromium,
  // so the layout pin survives a renderer being unavailable.
  const parts = [];
  for (const n of layout.nodes) {
    parts.push(`N|${n.id}|${n.pos.map(fixed).join(",")}|${fixed(n.radius)}|${n.color.map(fixed).join(",")}|${n.coxeter ? fixed(n.coxeter.theta) : "-"}`);
  }
  for (const p of layout.points) parts.push(`P|${p.pos.map(fixed).join(",")}|${p.kind}`);
  for (const f of layout.filaments) parts.push(`F|${f.from.map(fixed).join(",")}|${f.to.map(fixed).join(",")}|${f.kind}`);
  parts.push(`S|${JSON.stringify(layout.stats)}`);
  return new TextEncoder().encode(parts.join("\n"));
}
function fixed(v) { return (Math.round(v * 1e6) / 1e6).toFixed(6); }

async function sha256Hex(buffer) {
  const bytes = buffer instanceof Uint8Array ? buffer : new Uint8Array(buffer.buffer ?? buffer);
  const digest = await crypto.subtle.digest("SHA-256", bytes);
  return [...new Uint8Array(digest)].map((b) => b.toString(16).padStart(2, "0")).join("");
}

async function pngSha(canvas) {
  const blob = await new Promise((res) => canvas.toBlob(res, "image/png"));
  if (!blob) return null;
  return sha256Hex(new Uint8Array(await blob.arrayBuffer()));
}

function hashSeedToUint(seed) {
  let h = 0x811c9dc5;
  const s = String(seed);
  for (let i = 0; i < s.length; i += 1) {
    h ^= s.charCodeAt(i);
    h = Math.imul(h, 0x01000193);
  }
  return h >>> 0;
}

async function fetchJSON(path) {
  const response = await fetch(path);
  if (!response.ok) throw new Error(`${path}: HTTP ${response.status}`);
  return response.json();
}

function note(text) {
  const p = document.createElement("p");
  p.className = "atlas-note";
  p.textContent = text;
  return p;
}

/**
 * Self-boot. `index.html` loads this module with no inline starter so the page
 * has exactly one entry point, and so the falsifier can import the same file
 * the browser does. A hash seed (`#seed=…`) reproduces any image, per the house
 * convention that every piece is reproducible from its seed.
 */
function seedFromLocation() {
  if (typeof location === "undefined" || !location.hash) return null;
  const match = /seed=([^&]+)/.exec(location.hash.slice(1));
  return match ? decodeURIComponent(match[1]) : null;
}

if (typeof document !== "undefined") {
  const boot = () => {
    const rootEl = document.getElementById("atlas-root");
    if (!rootEl) return;
    startAtlas(rootEl, { seed: seedFromLocation() ?? "cfsg-atlas" })
      .then(() => { rootEl.setAttribute("aria-busy", "false"); })
      .catch((error) => {
        rootEl.setAttribute("aria-busy", "false");
        rootEl.prepend(note(`Atlas failed to start: ${error && error.message ? error.message : String(error)}`));
      });
  };
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", boot, { once: true });
  else boot();
}

function wirePointer(canvas, layout, renderer, camera, api, ctx) {
  if (!canvas) return;
  let dragging = null;

  const pickAt = (clientX, clientY) => {
    const rect = canvas.getBoundingClientRect();
    if (!rect.width || !rect.height) return -1;
    const ndc = [
      ((clientX - rect.left) / rect.width) * 2 - 1,
      -(((clientY - rect.top) / rect.height) * 2 - 1),
    ];
    // One aspect source: the GPU's own pixel box when it exists, so a pick is
    // made against the projection that actually drew the pixel.
    const aspect = renderer ? renderer.pixelSize[0] / renderer.pixelSize[1] : rect.width / rect.height;
    const view = lookAt(camera.pos, camera.target, [0, 1, 0]);
    const proj = frustum(layout.camera.fovYDeg, aspect);
    const ray = rayThrough(ndc, camera.pos, view, proj);
    return pickNode(layout.nodes, ray.origin, ray.direction);
  };

  canvas.addEventListener("pointermove", (event) => {
    if (dragging) {
      camera.yawOffset += (event.clientX - dragging.x) * 0.005;
      camera.pitchOffset = Math.max(-0.6, Math.min(0.6, camera.pitchOffset + (event.clientY - dragging.y) * 0.0035));
      dragging = { x: event.clientX, y: event.clientY };
      // A dragged pose is a new pose: converge it (a no-op while the flythrough
      // itself is animating, a fresh denoise while the viewer is holding still).
      if (ctx.motion.reduce) ctx.renderStatic(32);
      else ctx.startConverge(48);
      return;
    }
    const hit = pickAt(event.clientX, event.clientY);
    canvas.style.cursor = hit >= 0 ? "pointer" : "grab";
    if (hit !== api.hover) api.hoverNode(hit);
  });
  canvas.addEventListener("pointerdown", (event) => {
    dragging = { x: event.clientX, y: event.clientY };
    canvas.setPointerCapture?.(event.pointerId);
  });
  canvas.addEventListener("pointerup", (event) => {
    if (dragging && Math.abs(event.clientX - dragging.x) < 3 && Math.abs(event.clientY - dragging.y) < 3) {
      const hit = pickAt(event.clientX, event.clientY);
      if (hit >= 0) api.focusNode(hit);
    }
    dragging = null;
  });
  canvas.addEventListener("wheel", (event) => {
    event.preventDefault();
    camera.dolly = Math.max(0.45, Math.min(2.4, camera.dolly * (event.deltaY > 0 ? 1.08 : 0.92)));
    if (ctx.motion.reduce) ctx.renderStatic(32);
    else ctx.startConverge(48);
  }, { passive: false });
  canvas.addEventListener("pointerleave", () => {
    dragging = null;
    api.hoverNode(-1);
  });
}
