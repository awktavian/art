/**
 * renderer.js — WebGL2 plumbing for the atlas. Four passes into one float
 * scene target with a depth attachment, temporal accumulation in a ping-pong
 * pair, and a tonemapped blit to the canvas.
 *
 * Runtime policy, stated here because the falsifier depends on it:
 *
 *   • device pixel ratio is clamped to 2, the museum's own idiom
 *     (`Math.min(window.devicePixelRatio || 1, 2)` — patent-portfolio/main.js:2446).
 *   • accumulation runs one sample per pixel per step, so "samples/frame" is
 *     capped by construction at 1 and the frame *budget* is spent on
 *     resolution instead. `u_frame` is the only source of new randomness.
 *   • adaptive resolution drops the render scale in 1/1.25 steps when the
 *     last frames overran the frame budget, and raises it back when they did
 *     not. The current scale and the reason are always on screen — a silent
 *     resolution change would make the piece look worse than it is.
 *   • deterministic mode (`renderDeterministic`) reads no clock, no
 *     `requestAnimationFrame`, and no adaptive policy: camera, scale and frame
 *     count come from the caller, so two runs of it are the same bytes.
 */

import {
  VS_FULL,
  FS_MANIFOLD,
  VS_NODE,
  FS_NODE,
  VS_FILAMENT,
  FS_FILAMENT,
  VS_POINTS,
  FS_POINTS,
  FS_ACCUMULATE,
  FS_DISPLAY,
  FAR,
} from "./shaders.js";
import {
  encodeNodes,
  encodePoints,
  encodeFilaments,
  NODE_STRIDE,
  POINT_STRIDE,
  FILAMENT_STRIDE,
} from "./layout.js";
import { perspective, lookAt } from "./mat4.js";

const QUAD = new Float32Array([
  -1, -1, 1, -1, 1, 1,
  -1, -1, 1, 1, -1, 1,
]);

const MAX_DPR = 2;

/**
 * The manifold pass is a raymarch, so its cost is linear in pixels and the
 * device-pixel count of the accumulation buffer — not the CSS box — is the
 * thing that has to be bounded. 1.25 Mpx is where one path-traced sample per
 * pixel per frame stays interactive at DPR-clamped 2; the browser then upscales
 * the converged buffer into the element. The scale that achieves this is on
 * screen in the HUD, never hidden.
 */
const PIXEL_BUDGET = 1_250_000;

function compile(gl, type, source, label) {
  const shader = gl.createShader(type);
  gl.shaderSource(shader, source);
  gl.compileShader(shader);
  if (!gl.getShaderParameter(shader, gl.COMPILE_STATUS)) {
    const log = gl.getShaderInfoLog(shader) || "no log";
    gl.deleteShader(shader);
    throw new Error(`${label}: shader compile failed — ${log}`);
  }
  return shader;
}

function link(gl, vsSource, fsSource, label) {
  const vs = compile(gl, gl.VERTEX_SHADER, vsSource, `${label}.vert`);
  const fs = compile(gl, gl.FRAGMENT_SHADER, fsSource, `${label}.frag`);
  const program = gl.createProgram();
  gl.attachShader(program, vs);
  gl.attachShader(program, fs);
  gl.linkProgram(program);
  gl.deleteShader(vs);
  gl.deleteShader(fs);
  if (!gl.getProgramParameter(program, gl.LINK_STATUS)) {
    throw new Error(`${label}: link failed — ${gl.getProgramInfoLog(program) || "no log"}`);
  }
  const uniforms = {};
  const count = gl.getProgramParameter(program, gl.ACTIVE_UNIFORMS);
  for (let i = 0; i < count; i += 1) {
    const info = gl.getActiveUniform(program, i);
    if (info) uniforms[info.name] = gl.getUniformLocation(program, info.name);
  }
  const attribs = {};
  const acount = gl.getProgramParameter(program, gl.ACTIVE_ATTRIBUTES);
  for (let i = 0; i < acount; i += 1) {
    const info = gl.getActiveAttrib(program, i);
    if (info) attribs[info.name] = gl.getAttribLocation(program, info.name);
  }
  return { program, uniforms, attribs, label };
}

/**
 * Byte-exact offsets. The instance buffers are a fixed stride, so the layout
 * table has to account for every float in it — the trailing `_pad` entry names
 * an attribute no shader declares, which is skipped for binding but still
 * advances the offset. A stride that does not add up throws instead of
 * silently mis-decoding the scene.
 */
function attributedVAO(gl, prog, buffer, stride, layout) {
  const vao = gl.createVertexArray();
  gl.bindVertexArray(vao);
  const quad = gl.createBuffer();
  gl.bindBuffer(gl.ARRAY_BUFFER, quad);
  gl.bufferData(gl.ARRAY_BUFFER, QUAD, gl.STATIC_DRAW);
  const loc = prog.attribs.a_corner;
  if (loc !== undefined && loc >= 0) {
    gl.enableVertexAttribArray(loc);
    gl.vertexAttribPointer(loc, 2, gl.FLOAT, false, 0, 0);
  }
  gl.bindBuffer(gl.ARRAY_BUFFER, buffer);
  let offset = 0;
  for (const [name, size] of layout) {
    const at = prog.attribs[name];
    if (at !== undefined && at >= 0) {
      gl.enableVertexAttribArray(at);
      gl.vertexAttribPointer(at, size, gl.FLOAT, false, stride * 4, offset * 4);
      gl.vertexAttribDivisor(at, 1);
    }
    offset += size;
  }
  if (offset !== stride) {
    throw new Error(`${prog.label}: attribute layout covers ${offset} floats, buffer stride is ${stride}`);
  }
  gl.bindVertexArray(null);
  return vao;
}

export class AtlasRenderer {
  /**
   * @param {HTMLCanvasElement} canvas
   * @param {object} layout result of buildLayout()
   * @param {object} [opts]
   */
  constructor(canvas, layout, opts = {}) {
    const gl = canvas.getContext("webgl2", {
      antialias: false,
      alpha: false,
      depth: true,
      powerPreference: "high-performance",
      preserveDrawingBuffer: true,
    });
    if (!gl) throw new Error("WebGL2 is unavailable in this browser");
    this.gl = gl;
    this.canvas = canvas;
    this.layout = layout;

    const float = gl.getExtension("EXT_color_buffer_float");
    this.hdr = !!float;
    this.internalFormat = float ? gl.RGBA16F : gl.RGBA8;
    this.readFormat = gl.RGBA;
    this.readType = float ? gl.FLOAT : gl.UNSIGNED_BYTE;

    this.samplesPerPixel = 1;      // per presented frame — the cap the brief asks for
    this.pixelBudget = opts.pixelBudget ?? PIXEL_BUDGET;
    this.dpr = Math.min(window.devicePixelRatio || 1, MAX_DPR);
    this.scale = 1;
    this.scaleFloor = opts.scaleFloor ?? 0.45;
    this.frameBudgetMs = opts.frameBudgetMs ?? 22;
    this.layers = { manifold: true, nodes: true, filaments: true, points: true, ...(opts.layers || {}) };
    this.cssSize = [1, 1];
    this.pixelSize = [1, 1];
    this.frameCount = 0;
    this.lastFrameMs = 0;
    this.moving = false;
    this._camSig = null;
    this.frameEmaMs = null;
    this.observed = 0;
    this.warmupFrames = opts.warmupFrames ?? 12;
    this.warmupAfterStep = opts.warmupAfterStep ?? 3;
    this.warmup = this.warmupFrames;
    this.adaptations = [];
    this.stats = { shaderErrors: 0, hdr: this.hdr, maxDpr: MAX_DPR };

    this.programs = {
      manifold: link(gl, VS_FULL, FS_MANIFOLD, "manifold"),
      nodes: link(gl, VS_NODE, FS_NODE, "nodes"),
      filaments: link(gl, VS_FILAMENT, FS_FILAMENT, "filaments"),
      points: link(gl, VS_POINTS, FS_POINTS, "points"),
      accumulate: link(gl, VS_FULL, FS_ACCUMULATE, "accumulate"),
      display: link(gl, VS_FULL, FS_DISPLAY, "display"),
    };

    this.emptyVAO = gl.createVertexArray();

    this.nodeBuffer = this._instanced(encodeNodes(layout.nodes));
    this.pointBuffer = this._instanced(encodePoints(layout.points));
    this.filamentBuffer = this._instanced(encodeFilaments(layout.filaments));

    this.nodeVAO = attributedVAO(gl, this.programs.nodes, this.nodeBuffer, NODE_STRIDE, [
      ["i_center", 3], ["i_radius", 1], ["i_color", 3], ["i_theta", 1], ["i_kind", 1],
      ["i_m", 1], ["i_rank", 1], ["i_order", 1], ["i_char", 1], ["i_roots", 1], ["i_id", 1], ["_pad", 1],
    ]);
    // i_arm is packed into the buffer (slot 5) but unread by VS_POINTS, so it
    // sits in the padding here: the table has to sum to POINT_STRIDE.
    this.pointVAO = attributedVAO(gl, this.programs.points, this.pointBuffer, POINT_STRIDE, [
      ["i_pos", 3], ["i_kind", 1], ["i_size", 1], ["i_id", 1], ["_pad", 2],
    ]);
    this.filamentVAO = attributedVAO(gl, this.programs.filaments, this.filamentBuffer, FILAMENT_STRIDE, [
      ["i_from", 3], ["i_to", 3], ["i_width", 1], ["i_tone", 1], ["i_id", 1], ["_pad", 1],
    ]);

    this._targets();
  }

  _instanced(data) {
    const gl = this.gl;
    const buffer = gl.createBuffer();
    gl.bindBuffer(gl.ARRAY_BUFFER, buffer);
    gl.bufferData(gl.ARRAY_BUFFER, data, gl.STATIC_DRAW);
    gl.bindBuffer(gl.ARRAY_BUFFER, null);
    return buffer;
  }

  _texture(w, h) {
    const gl = this.gl;
    const tex = gl.createTexture();
    gl.bindTexture(gl.TEXTURE_2D, tex);
    gl.texImage2D(gl.TEXTURE_2D, 0, this.internalFormat, w, h, 0, this.readFormat, this.hdr ? gl.HALF_FLOAT : gl.UNSIGNED_BYTE, null);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.NEAREST);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.NEAREST);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
    gl.bindTexture(gl.TEXTURE_2D, null);
    return tex;
  }

  _targets() {
    const gl = this.gl;
    for (const key of ["scene", "accumA", "accumB"]) {
      if (this[key]) {
        gl.deleteFramebuffer(this[key].fbo);
        gl.deleteTexture(this[key].tex);
        if (this[key].depth) gl.deleteRenderbuffer(this[key].depth);
      }
    }
    const [w, h] = this.pixelSize;
    const mk = (withDepth) => {
      const tex = this._texture(w, h);
      const fbo = gl.createFramebuffer();
      gl.bindFramebuffer(gl.FRAMEBUFFER, fbo);
      gl.framebufferTexture2D(gl.FRAMEBUFFER, gl.COLOR_ATTACHMENT0, gl.TEXTURE_2D, tex, 0);
      let depth = null;
      if (withDepth) {
        depth = gl.createRenderbuffer();
        gl.bindRenderbuffer(gl.RENDERBUFFER, depth);
        gl.renderbufferStorage(gl.RENDERBUFFER, gl.DEPTH_COMPONENT24, w, h);
        gl.framebufferRenderbuffer(gl.FRAMEBUFFER, gl.DEPTH_ATTACHMENT, gl.RENDERBUFFER, depth);
      }
      gl.viewport(0, 0, w, h);
      gl.clearColor(0, 0, 0, 1);
      gl.clear(gl.COLOR_BUFFER_BIT | (withDepth ? gl.DEPTH_BUFFER_BIT : 0));
      gl.bindFramebuffer(gl.FRAMEBUFFER, null);
      return { fbo, tex, depth };
    };
    this.scene = mk(true);
    this.accumA = mk(false);
    this.accumB = mk(false);
    this.accumRead = this.accumA;
    this.accumWrite = this.accumB;
  }

  /**
   * Fit the render scale so the buffer stays inside the pixel budget. Returns
   * the scale it wants; `resize` is the only place that records it, so a silent
   * size change is impossible.
   */
  budgetScale(cssWidth, cssHeight, want) {
    if (!this.pixelBudget) return this.scale;
    const devicePixels = cssWidth * want * cssHeight * want;
    if (devicePixels * this.scale * this.scale <= this.pixelBudget) return this.scale;
    return Math.max(this.scaleFloor, Math.sqrt(this.pixelBudget / devicePixels));
  }

  /** CSS size in, device pixels out, DPR clamped to 2 and scale-adapted. */
  resize(cssWidth, cssHeight, dpr, { budgeted = true } = {}) {
    const want = Math.min(dpr || window.devicePixelRatio || 1, MAX_DPR);
    if (budgeted) {
      const before = this.scale;
      this.scale = this.budgetScale(cssWidth, cssHeight, want);
      if (Math.abs(before - this.scale) > 1e-6) {
        this.adaptations.push({ at: "0.0", from: before, to: this.scale, reason: "pixel budget" });
      }
    }
    const w = Math.max(1, Math.round(cssWidth * want * this.scale));
    const h = Math.max(1, Math.round(cssHeight * want * this.scale));
    const changed = w !== this.pixelSize[0] || h !== this.pixelSize[1] || want !== this.dpr;
    this.cssSize = [cssWidth, cssHeight];
    this.dpr = want;
    this.pixelSize = [w, h];
    if (changed) {
      this.canvas.width = w;
      this.canvas.height = h;
      this._targets();
      this.reset();
    }
    this.lastResize = { css: [cssWidth, cssHeight], budgeted };
    return { w, h, dpr: want, scale: this.scale };
  }

  setRenderScale(next) {
    const clamped = Math.max(this.scaleFloor, Math.min(1, next));
    // a manual step is also a budget statement: never exceed the pixel ceiling
    if (Math.abs(clamped - this.scale) < 1e-6) return false;
    this.scale = clamped;
    this.resize(this.cssSize[0], this.cssSize[1], this.dpr);
    return true;
  }

  reset() { this.frameCount = 0; }

  _common(prog, cam, extra) {
    const gl = this.gl;
    gl.useProgram(prog.program);
    const u = prog.uniforms;
    if (u.u_res) gl.uniform2f(u.u_res, this.pixelSize[0], this.pixelSize[1]);
    if (u.u_far) gl.uniform1f(u.u_far, FAR);
    if (u.u_seed) gl.uniform1ui(u.u_seed, extra.seed >>> 0);
    if (u.u_frame) gl.uniform1i(u.u_frame, extra.frameIndex | 0);
    if (u.u_time) gl.uniform1f(u.u_time, extra.time);
    if (u.u_cam) gl.uniform3f(u.u_cam, cam.pos[0], cam.pos[1], cam.pos[2]);
    if (u.u_view) gl.uniformMatrix4fv(u.u_view, false, cam.view);
    if (u.u_proj) gl.uniformMatrix4fv(u.u_proj, false, cam.proj);
    if (u.u_foldA) gl.uniform1f(u.u_foldA, extra.foldAngle);
    if (u.u_focus) gl.uniform1f(u.u_focus, extra.focus);
    if (u.u_hover) gl.uniform1f(u.u_hover, extra.hover);
    if (u.u_hoverNode) gl.uniform1f(u.u_hoverNode, extra.hover);
    if (u.u_light0) gl.uniform4f(u.u_light0, 9, 12, 7, 1.15);
    if (u.u_light1) gl.uniform4f(u.u_light1, -11, 6, -8, 0.72);
    if (u.u_light2) gl.uniform4f(u.u_light2, 0, 2.2, 0, 0.55);
    if (u.u_pointScale) gl.uniform1f(u.u_pointScale, 0.085);
    if (u.u_frameCount) gl.uniform1i(u.u_frameCount, extra.frameCount);
    return u;
  }

  /**
   * One accumulation step. `camera` is {pos, target, fovYDeg}; `state` carries
   * seed, frameIndex, time, focus, hover, foldAngle.
   */
  renderStep(camera, state) {
    const gl = this.gl;
    const aspect = this.pixelSize[0] / this.pixelSize[1];
    // Temporal averaging only means something while the camera is still: a
    // moving camera would average different viewpoints into one ghost. So the
    // accumulation restarts whenever the pose changes, and the piece converges
    // the moment the flythrough is paused, focused, or reduced-motion.
    const sig = `${camera.pos[0].toFixed(4)},${camera.pos[1].toFixed(4)},${camera.pos[2].toFixed(4)}|${camera.target[0].toFixed(4)},${camera.target[1].toFixed(4)},${camera.target[2].toFixed(4)}`;
    if (sig !== this._camSig) {
      this._camSig = sig;
      this.frameCount = 0;
      this.moving = true;
    } else {
      this.moving = false;
    }
    const cam = {
      pos: camera.pos,
      view: lookAt(camera.pos, camera.target, [0, 1, 0]),
      proj: perspective(((camera.fovYDeg ?? 42) * Math.PI) / 180, aspect, 0.1, FAR),
    };
    const extra = {
      seed: state.seed >>> 0,
      frameIndex: state.frameIndex,
      frameCount: this.frameCount + 1,
      time: state.time,
      focus: state.focus ?? -1,
      hover: state.hover ?? -1,
      foldAngle: state.foldAngle ?? Math.PI / 3,
    };

    // Layer visibility, defaulting to all four. The point of the knob is not
    // the demo switch: it is that a composite of four passes is only
    // debuggable if each pass can be removed from it, and the piece is a
    // composite. `__atlas.setLayers({ filaments: false })`.
    const on = this.layers;
    const count = (key, n) => (on[key] ? n : 0);

    gl.bindFramebuffer(gl.FRAMEBUFFER, this.scene.fbo);
    gl.viewport(0, 0, this.pixelSize[0], this.pixelSize[1]);
    gl.clearColor(0, 0, 0, 1);
    gl.depthMask(true);
    gl.clear(gl.COLOR_BUFFER_BIT | gl.DEPTH_BUFFER_BIT);

    gl.disable(gl.BLEND);
    gl.disable(gl.DEPTH_TEST);
    gl.depthMask(true);

    // 1 — manifold
    gl.bindVertexArray(this.emptyVAO);
    this._common(this.programs.manifold, cam, extra);
    if (on.manifold) gl.drawArrays(gl.TRIANGLES, 0, 3);

    // 2 — nodes, occluded by the manifold through one shared depth encoding
    gl.enable(gl.DEPTH_TEST);
    gl.depthFunc(gl.LESS);
    gl.bindVertexArray(this.nodeVAO);
    this._common(this.programs.nodes, cam, extra);
    gl.drawArraysInstanced(gl.TRIANGLES, 0, 6, count("nodes", this.layout.nodes.length));

    // 3 — filaments, additive over the opaque field
    gl.depthMask(false);
    gl.enable(gl.BLEND);
    gl.blendFunc(gl.SRC_ALPHA, gl.ONE);
    gl.bindVertexArray(this.filamentVAO);
    this._common(this.programs.filaments, cam, extra);
    gl.drawArraysInstanced(gl.TRIANGLES, 0, 6, count("filaments", this.layout.filaments.length));

    // 4 — points
    gl.bindVertexArray(this.pointVAO);
    this._common(this.programs.points, cam, extra);
    gl.drawArraysInstanced(gl.TRIANGLES, 0, 6, count("points", this.layout.points.length));

    gl.disable(gl.BLEND);
    gl.depthMask(true);

    // 5 — accumulate into the ping-pong half not currently sampled
    gl.bindFramebuffer(gl.FRAMEBUFFER, this.accumWrite.fbo);
    gl.viewport(0, 0, this.pixelSize[0], this.pixelSize[1]);
    gl.disable(gl.DEPTH_TEST);
    gl.bindVertexArray(this.emptyVAO);
    const au = this._common(this.programs.accumulate, cam, extra);
    gl.activeTexture(gl.TEXTURE0);
    gl.bindTexture(gl.TEXTURE_2D, this.scene.tex);
    gl.uniform1i(au.u_scene, 0);
    gl.activeTexture(gl.TEXTURE1);
    gl.bindTexture(gl.TEXTURE_2D, this.accumRead.tex);
    gl.uniform1i(au.u_accum, 1);
    gl.drawArrays(gl.TRIANGLES, 0, 3);
    this.frameCount = extra.frameCount;

    // 6 — present the buffer that was just written, then retire the other one
    this._present(cam, extra, this.accumWrite);
    const tmp = this.accumRead;
    this.accumRead = this.accumWrite;
    this.accumWrite = tmp;
    return this.frameCount;
  }

  _present(cam, extra, source) {
    const gl = this.gl;
    gl.bindFramebuffer(gl.FRAMEBUFFER, null);
    gl.viewport(0, 0, this.pixelSize[0], this.pixelSize[1]);
    gl.disable(gl.DEPTH_TEST);
    gl.disable(gl.BLEND);
    gl.bindVertexArray(this.emptyVAO);
    const du = this._common(this.programs.display, cam, extra);
    gl.activeTexture(gl.TEXTURE0);
    gl.bindTexture(gl.TEXTURE_2D, source.tex);
    gl.uniform1i(du.u_accum, 0);
    gl.drawArrays(gl.TRIANGLES, 0, 3);
  }

  /** The converged float buffer, not the tonemapped PNG — this is what gets hashed. */
  readAccumulation(target = this.accumRead) {
    const gl = this.gl;
    gl.bindFramebuffer(gl.FRAMEBUFFER, target.fbo);
    const out = this.hdr
      ? new Float32Array(this.pixelSize[0] * this.pixelSize[1] * 4)
      : new Uint8Array(this.pixelSize[0] * this.pixelSize[1] * 4);
    gl.readPixels(0, 0, this.pixelSize[0], this.pixelSize[1], this.readFormat, this.readType, out);
    gl.bindFramebuffer(gl.FRAMEBUFFER, null);
    return out;
  }

  readCanvasRGBA() {
    const gl = this.gl;
    const out = new Uint8Array(this.pixelSize[0] * this.pixelSize[1] * 4);
    gl.bindFramebuffer(gl.FRAMEBUFFER, null);
    gl.readPixels(0, 0, this.pixelSize[0], this.pixelSize[1], gl.RGBA, gl.UNSIGNED_BYTE, out);
    return out;
  }

  /**
   * Adaptive resolution. `ms` MUST be the wall interval between *presented*
   * frames (the requestAnimationFrame delta), not the time the CPU spent
   * inside renderStep: GL work is queued asynchronously, so a submission timer
   * reads ~0 ms on a machine rendering at one frame a second and the fallback
   * would never fire — measured, not theorised: the first harness logged
   * `ms: 0` on frames that took 1.2 s each.
   *
   * The cadence is smoothed with an EMA and needs `warmup` observations before
   * it decides, so one stalled tab or a resize cannot step the resolution. A
   * frame that is already four times over budget is the exception: at 1.2 s per
   * frame, waiting for twelve observations is twelve seconds of a broken
   * picture, so the first such frame is allowed to act. Every step is recorded
   * with the true scale it came from and the cadence that caused it, and the
   * HUD shows both — the fallback is disclosed, never silent.
   */
  observeFrame(ms) {
    this.lastFrameMs = ms;
    if (!(ms > 0) || !Number.isFinite(ms)) return;
    this.frameEmaMs = this.frameEmaMs === null ? ms : this.frameEmaMs + (ms - this.frameEmaMs) * 0.2;
    this.observed += 1;
    if (this.observed < this.warmup && !(this.observed >= 1 && ms > this.frameBudgetMs * 4)) return;
    const cadence = this.frameEmaMs;
    const ratio = cadence / this.frameBudgetMs;
    const before = this.scale;
    if (ratio > 1 && this.scale > this.scaleFloor) {
      // Decisive, not incremental: 55x over budget is not one 20% step away
      // from interactive, and one step per warm-up window would take the rest
      // of the session to get there.
      const steps = Math.max(1, Math.min(5, Math.round(Math.log(ratio) / Math.log(1.25))));
      const next = Math.max(this.scaleFloor, this.scale / Math.pow(1.25, steps));
      if (this.setRenderScale(next)) {
        this.adaptations.push({ at: cadence.toFixed(1), from: before, to: this.scale, steps, reason: "over budget" });
        this.observed = 0;
        this.frameEmaMs = null;
        this.warmup = this.warmupAfterStep;
      }
    } else if (ratio < 0.45 && this.scale < 1) {
      const next = Math.min(1, this.scale * 1.25);
      if (this.setRenderScale(next)) {
        this.adaptations.push({ at: cadence.toFixed(1), from: before, to: this.scale, steps: 1, reason: "under budget" });
        this.observed = 0;
        this.frameEmaMs = null;
        this.warmup = this.warmupFrames;
      }
    }
    if (this.adaptations.length > 24) this.adaptations.splice(0, this.adaptations.length - 24);
  }

  dispose() {
    const gl = this.gl;
    for (const p of Object.values(this.programs)) gl.deleteProgram(p.program);
    for (const b of [this.nodeBuffer, this.pointBuffer, this.filamentBuffer]) gl.deleteBuffer(b);
    for (const v of [this.emptyVAO, this.nodeVAO, this.pointVAO, this.filamentVAO]) gl.deleteVertexArray(v);
    for (const t of [this.scene, this.accumA, this.accumB]) {
      gl.deleteFramebuffer(t.fbo);
      gl.deleteTexture(t.tex);
      if (t.depth) gl.deleteRenderbuffer(t.depth);
    }
  }
}
