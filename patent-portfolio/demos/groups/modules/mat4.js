/**
 * mat4.js — the four functions this atlas needs from linear algebra, and no
 * more. Written here rather than borrowed because the reference rasterizer
 * (tools/reference-raster.mjs) runs in bare node with no DOM and no library,
 * and the determinism claim only holds if the browser's camera transform and
 * the pinned CPU transform are literally the same code.
 *
 * Column-major Float32Array, matching what WebGL2 wants; `perspective` and
 * `lookAt` follow the OpenGL convention (clip z in [-1, 1]) because that is
 * what the shaders' `depthOf()` reconstruction assumes.
 */

export const NEAR = 0.1;
/** Marching ceiling: the whole atlas (the arm helices sit at r ≈ 13.2). */
export const FAR = 140.0;

export function mat4() {
  const m = new Float32Array(16);
  m[0] = 1;
  m[5] = 1;
  m[10] = 1;
  m[15] = 1;
  return m;
}

/**
 * The one frustum this atlas uses: `NEAR`/`FAR` and the vertical field, given
 * an aspect. Every consumer — the GPU passes, the CPU picker, the reference
 * rasterizer — builds its projection through here, so a pick and a pixel
 * cannot disagree about where a node is.
 */
export function frustum(fovYDeg, aspect) {
  return perspective(((fovYDeg ?? 42) * Math.PI) / 180, aspect, NEAR, FAR);
}

export function perspective(fovYRad, aspect, near, far) {
  const f = 1 / Math.tan(fovYRad / 2);
  const nf = 1 / (near - far);
  const m = new Float32Array(16);
  m[0] = f / aspect;
  m[5] = f;
  m[10] = (far + near) * nf;
  m[11] = -1;
  m[14] = 2 * far * near * nf;
  return m;
}

export function lookAt(eye, target, up) {
  const z = norm3([eye[0] - target[0], eye[1] - target[1], eye[2] - target[2]]);
  const x = norm3(cross3(up, z));
  const y = cross3(z, x);
  const m = mat4();
  m[0] = x[0]; m[1] = y[0]; m[2] = z[0];
  m[4] = x[1]; m[5] = y[1]; m[6] = z[1];
  m[8] = x[2]; m[9] = y[2]; m[10] = z[2];
  m[12] = -dot3(x, eye);
  m[13] = -dot3(y, eye);
  m[14] = -dot3(z, eye);
  return m;
}

/**
 * Camera basis in world space — needed on the CPU side for picking and for
 * the reference rasterizer, where there is no shader to ask.
 */
export function cameraBasis(eye, target, up) {
  const z = norm3([eye[0] - target[0], eye[1] - target[1], eye[2] - target[2]]);
  const x = norm3(cross3(up, z));
  const y = cross3(z, x);
  return { right: x, upVec: y, back: z };
}

/**
 * World ray through a pixel. ndc is (x, y) in [-1, 1] with y up, matching
 * `gl_FragCoord` conventions after the usual flip.
 */
export function rayThrough(ndc, eye, view, proj) {
  const inv = invertPerspective(proj);
  const vx = ndc[0] * inv[0];
  const vy = ndc[1] * inv[5];
  const vz = -1;
  const dirView = [vx, vy, vz];
  const r = 1 / Math.max(1e-12, Math.hypot(dirView[0], dirView[1], dirView[2]));
  // view's 3x3 is orthonormal, so its inverse is its transpose. In
  // column-major storage R^T·v reads down the COLUMNS of `view`:
  //   world_i = Σ_j R_{j,i} · dirView_j
  const dir = [
    (view[0] * dirView[0] + view[1] * dirView[1] + view[2] * dirView[2]) * r,
    (view[4] * dirView[0] + view[5] * dirView[1] + view[6] * dirView[2]) * r,
    (view[8] * dirView[0] + view[9] * dirView[1] + view[10] * dirView[2]) * r,
  ];
  return { origin: [eye[0], eye[1], eye[2]], direction: dir };
}

/** Column-major 4x4 inverse restricted to the perspective form above. */
function invertPerspective(p) {
  return { 0: 1 / p[0], 5: 1 / p[5] };
}

/**
 * Project a world point to normalised device coordinates. Returns null behind
 * the camera, which the rasterizer treats as "do not draw" and the HUD uses to
 * place labels without a DOM layout pass.
 */
export function project(point, view, proj, viewport) {
  const vx = view[0] * point[0] + view[4] * point[1] + view[8] * point[2] + view[12];
  const vy = view[1] * point[0] + view[5] * point[1] + view[9] * point[2] + view[13];
  const vz = view[2] * point[0] + view[6] * point[1] + view[10] * point[2] + view[14];
  const cw = view[3] * point[0] + view[7] * point[1] + view[11] * point[2] + view[15];
  const cx = proj[0] * vx + proj[4] * vy + proj[8] * vz + proj[12] * cw;
  const cy = proj[1] * vx + proj[5] * vy + proj[9] * vz + proj[13] * cw;
  const cz = proj[2] * vx + proj[6] * vy + proj[10] * vz + proj[14] * cw;
  const w = proj[3] * vx + proj[7] * vy + proj[11] * vz + proj[15] * cw;
  if (!(w > 1e-6)) return null;
  return {
    x: (cx / w * 0.5 + 0.5) * viewport[2] + viewport[0],
    y: (1 - (cy / w * 0.5 + 0.5)) * viewport[3] + viewport[1],
    depth: cz / w,
    scale: 1 / w,
  };
}

function cross3(a, b) {
  return [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]];
}
function dot3(a, b) { return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]; }
function norm3(v) {
  const l = Math.hypot(v[0], v[1], v[2]);
  return l > 1e-12 ? [v[0] / l, v[1] / l, v[2] / l] : [0, 0, 0];
}
