/**
 * tests/lookdev/three-double.mjs — a bounded THREE test double for the look-dev
 * harness, faithful to `three@0.160.0` (the version patent-portfolio/index.html
 * pins in its import map).
 *
 * WHY A DOUBLE AT ALL. `patent-portfolio/**` resolves `three` through a browser
 * import map to the jsdelivr CDN build, so there is no `node_modules/three` and
 * Node cannot import `museum/lighting.js` or `lib/materials.js` as written. The
 * alternative — paraphrasing those modules' numbers into the harness — would pin
 * a description of the look instead of the look, which is exactly what the
 * waddle golden-test discipline refuses ("the golden check exercises the
 * pipeline, not a paraphrase of it"). So the harness installs this double in
 * place of the bare specifier `three` via `module.registerHooks`, and art's own
 * lighting/material code runs verbatim under Node. Nothing in `patent-portfolio/`
 * imports or knows about this file; it is resolved only while a lookdev scene is
 * being built.
 *
 * WHAT IS IN SCOPE. Only the API surface the pinned scenes actually reach:
 * Color (with r160's sRGB↔linear transfer), Vector2/3, the four light classes
 * plus AmbientLight, Object3D/Scene/Group with add/remove/traverse, FogExp2,
 * Mesh, the geometry classes that appear as constructor calls, the material
 * classes, DataTexture/CanvasTexture, CubeCamera + WebGLCubeRenderTarget,
 * PMREMGenerator, PerspectiveCamera with r160's projection matrix, and the
 * numeric constants. Everything is recorded against a per-scene `recorder` so
 * construction ORDER is part of the receipt.
 *
 * WHAT IS NOT, and what that means for the digest:
 *   - No GPU, no rasteriser. `PMREMGenerator.fromScene/fromCubemap` and
 *     `CubeCamera.update` are recorded (the arguments are the look decision) and
 *     return an opaque texture stub. A scene receipt is therefore a LOOK-GRAPH
 *     digest — camera-projected anchors, light state, material fields, texture
 *     bytes — not a pixel hash. It is a drift signal, and it is sensitive to
 *     exactly the axes a look-dev review cares about.
 *   - `MeshPhysicalMaterial` deliberately has NO `dispersion` property: three
 *     r160 does not define it (`grep -c dispersion` over the r160 build = 0,
 *     read 2026-11-02), which is why `createCrystalMaterial`'s
 *     `typeof material.dispersion !== 'undefined'` guard skips it in the browser
 *     too. Adding it here would make the double disagree with production.
 *   - `Material.needsUpdate` is a plain writable field (in three it is a setter
 *     that bumps a version counter; nothing read by these scenes depends on the
 *     difference).
 *
 * FAITHFULNESS TESTS live in tests/unit/lookdev.test.mjs: the color transform,
 * the perspective projection, and the near/far depth mapping are checked against
 * hand-computable values, so a double that drifts from three fails loudly
 * instead of quietly stamping a wrong receipt.
 */

// ── r160 constants (values read out of the pinned build, not remembered) ─────
const NoToneMapping = 0;
const LinearToneMapping = 1;
const ReinhardToneMapping = 2;
const CineonToneMapping = 3;
const ACESFilmicToneMapping = 4;
const CustomToneMapping = 5;
const AgXToneMapping = 6;

const BasicShadowMap = 0;
const PCFShadowMap = 1;
const PCFSoftShadowMap = 2;
const VSMShadowMap = 3;

const FrontSide = 0;
const BackSide = 1;
const DoubleSide = 2;

const NormalBlending = 1;
const AdditiveBlending = 2;

const RepeatWrapping = 1000;
const ClampToEdgeWrapping = 1001;
const MirroredRepeatWrapping = 1002;
const NearestFilter = 1003;
const LinearFilter = 1006;
const LinearMipmapLinearFilter = 1008;
const RGBAFormat = 1023;

const TangentSpaceNormalMap = 0;
const ObjectSpaceNormalMap = 1;

const SRGBColorSpace = "srgb";
const LinearSRGBColorSpace = "srgb-linear";
const NoColorSpace = "";

const WebGLCoordinateSystem = 2000;
const DEG2RAD = Math.PI / 180;

/** three r160 SRGBToLinear / LinearToSRGB, constants copied from the build. */
function SRGBToLinear(c) {
  return c < 0.04045 ? c * 0.0773993808 : Math.pow(c * 0.9478672986 + 0.0521327014, 2.4);
}
function LinearToSRGB(c) {
  // r160 clamps into [0,1] FIRST. Without the clamp, an out-of-gamut channel
  // (Math.pow of a negative) returns NaN and the NaN silently poisons every
  // downstream hex digest — measured against three's Color.js, not assumed.
  c = Math.max(0, Math.min(1, c));
  return c < 0.0031308 ? c * 12.92 : 1.055 * Math.pow(c, 0.41666) - 0.055;
}
function clamp(v, min, max) {
  return Math.max(min, Math.min(max, v));
}

/**
 * The double is created per scene so ids, dispose tallies and construction
 * order never leak between receipts.
 * @param {{disposes: string[], events: string[]}} recorder
 */
export function createThreeDouble(recorder) {
  const state = { nextId: 1 };
  /**
   * Ids and the recorder are process-wide, but a scene receipt must not depend
   * on which scenes ran before it — `withScene()` calls reset() first, so
   * construction ids and dispose tallies are scene-local.
   */
  const reset = () => { state.nextId = 1; recorder.disposes.length = 0; recorder.events.length = 0; };
  const id = (prefix) => `${prefix}:${(state.nextId++).toString(16).padStart(3, "0")}`;
  const dispose = (what) => recorder.disposes.push(what);
  const event = (what) => recorder.events.push(what);

  // ── Color ────────────────────────────────────────────────────────────────
  class Color {
    constructor(r, g, b) {
      this.r = 1; this.g = 1; this.b = 1;
      if (r !== undefined) this.set(r, g, b);
    }
    set(value, g, b) {
      if (value && value.isColor) return this.copy(value);
      if (typeof value === "number") {
        if (g === undefined && b === undefined) return this.setHex(value);
        return this.setRGB(value, g, b);
      }
      if (typeof value === "string") return this.setStyle(value);
      return this;
    }
    setHex(hex, colorSpace = SRGBColorSpace) {
      hex = Math.floor(hex);
      this.r = ((hex >> 16) & 255) / 255;
      this.g = ((hex >> 8) & 255) / 255;
      this.b = (hex & 255) / 255;
      if (colorSpace === SRGBColorSpace) {
        this.r = SRGBToLinear(this.r);
        this.g = SRGBToLinear(this.g);
        this.b = SRGBToLinear(this.b);
      }
      return this;
    }
    setRGB(r, g, b) { this.r = r; this.g = g; this.b = b; return this; }
    setScalar(s) { this.r = s; this.g = s; this.b = s; return this; }
    setStyle(str) {
      const m = /^#?([0-9a-f]{6})$/i.exec(str || "");
      if (m) return this.setHex(parseInt(m[1], 16));
      return this.setHex(0xffffff);
    }
    copy(c) { this.r = c.r; this.g = c.g; this.b = c.b; return this; }
    clone() { return new Color().copy(this); }
    addScalar(s) { this.r += s; this.g += s; this.b += s; return this; }
    multiplyScalar(s) { this.r *= s; this.g *= s; this.b *= s; return this; }
    lerp(color, alpha) {
      this.r += (color.r - this.r) * alpha;
      this.g += (color.g - this.g) * alpha;
      this.b += (color.b - this.b) * alpha;
      return this;
    }
    lerpColors(c1, c2, alpha) {
      this.r = c1.r + (c2.r - c1.r) * alpha;
      this.g = c1.g + (c2.g - c1.g) * alpha;
      this.b = c1.b + (c2.b - c1.b) * alpha;
      return this;
    }
    getHex(colorSpace = SRGBColorSpace) {
      const c = new Color().copy(this);
      if (colorSpace === SRGBColorSpace) {
        c.r = LinearToSRGB(c.r); c.g = LinearToSRGB(c.g); c.b = LinearToSRGB(c.b);
      }
      return (
        Math.round(clamp(c.r * 255, 0, 255)) * 65536 +
        Math.round(clamp(c.g * 255, 0, 255)) * 256 +
        Math.round(clamp(c.b * 255, 0, 255))
      );
    }
    // r160 verbatim: (getHex() + 0x1000000).toString(16).substring(1) — exactly
    // six digits. Measured while testing this double: an earlier hand-rolled
    // "000000" + slice(-6) returned twelve digits, which would have made
    // materials.js's '#'+getHexString() CSS colors impossible to compare by eye.
    getHexString(colorSpace = SRGBColorSpace) {
      return (this.getHex(colorSpace) + 0x1000000).toString(16).substring(1);
    }
    equals(c) { return this.r === c.r && this.g === c.g && this.b === c.b; }
  }
  Color.prototype.isColor = true;

  // ── Vectors / matrices ───────────────────────────────────────────────────
  class Vector2 {
    constructor(x = 0, y = 0) { this.x = x; this.y = y; }
    set(x, y) { this.x = x; this.y = y; return this; }
    copy(v) { this.x = v.x; this.y = v.y; return this; }
    clone() { return new Vector2(this.x, this.y); }
  }

  class Matrix4 {
    constructor() { this.elements = [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1]; }
    identity() { this.elements = [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1]; return this; }
    /** column-major, matching three's `te[]` indexing */
    setRowVector(r, x, y, z, w) {
      const e = this.elements;
      e[0 * 4 + r] = x; e[1 * 4 + r] = y; e[2 * 4 + r] = z; e[3 * 4 + r] = w;
      return this;
    }
    makePerspective(left, right, top, bottom, near, far) {
      const e = this.elements;
      const x = (2 * near) / (right - left);
      const y = (2 * near) / (top - bottom);
      const a = (right + left) / (right - left);
      const b = (top + bottom) / (top - bottom);
      const c = -(far + near) / (far - near);
      const d = (-2 * far * near) / (far - near);
      e[0] = x; e[4] = 0; e[8] = a; e[12] = 0;
      e[1] = 0; e[5] = y; e[9] = b; e[13] = 0;
      e[2] = 0; e[6] = 0; e[10] = c; e[14] = d;
      e[3] = 0; e[7] = 0; e[11] = -1; e[15] = 0;
      return this;
    }
    multiplyVector3(v) {
      const e = this.elements;
      const { x, y, z } = v;
      return {
        x: e[0] * x + e[4] * y + e[8] * z + e[12],
        y: e[1] * x + e[5] * y + e[9] * z + e[13],
        z: e[2] * x + e[6] * y + e[10] * z + e[14],
        w: e[3] * x + e[7] * y + e[11] * z + e[15],
      };
    }
  }

  class Vector3 {
    constructor(x = 0, y = 0, z = 0) { this.x = x; this.y = y; this.z = z; }
    set(x, y, z) { this.x = x; this.y = y; this.z = z; return this; }
    copy(v) { this.x = v.x; this.y = v.y; this.z = v.z; return this; }
    clone() { return new Vector3(this.x, this.y, this.z); }
    setScalar(s) { this.x = s; this.y = s; this.z = s; return this; }
    add(v) { this.x += v.x; this.y += v.y; this.z += v.z; return this; }
    sub(v) { this.x -= v.x; this.y -= v.y; this.z -= v.z; return this; }
    subVectors(a, b) { this.x = a.x - b.x; this.y = a.y - b.y; this.z = a.z - b.z; return this; }
    addScaledVector(v, s) { this.x += v.x * s; this.y += v.y * s; this.z += v.z * s; return this; }
    multiplyScalar(s) { this.x *= s; this.y *= s; this.z *= s; return this; }
    dot(v) { return this.x * v.x + this.y * v.y + this.z * v.z; }
    crossVectors(a, b) {
      this.x = a.y * b.z - a.z * b.y;
      this.y = a.z * b.x - a.x * b.z;
      this.z = a.x * b.y - a.y * b.x;
      return this;
    }
    length() { return Math.hypot(this.x, this.y, this.z); }
    normalize() { const l = this.length() || 1; return this.multiplyScalar(1 / l); }
    lerp(v, a) { this.x += (v.x - this.x) * a; this.y += (v.y - this.y) * a; this.z += (v.z - this.z) * a; return this; }
    applyMatrix4(m) {
      const c = m.multiplyVector3(this);
      this.x = c.x / c.w; this.y = c.y / c.w; this.z = c.z / c.w;
      return this;
    }
    project(camera) {
      return this.applyMatrix4(camera.matrixWorldInverse).applyMatrix4(camera.projectionMatrix);
    }
    toArray() { return [this.x, this.y, this.z]; }
  }

  class Euler {
    constructor(x = 0, y = 0, z = 0) { this._x = x; this._y = y; this._z = z; this.order = "XYZ"; }
    get x() { return this._x; }
    set x(v) { this._x = v; }
    get y() { return this._y; }
    set y(v) { this._y = v; }
    get z() { return this._z; }
    set z(v) { this._z = v; }
    set(x, y, z) { this._x = x; this._y = y; this._z = z; return this; }
    copy(e) { this._x = e.x; this._y = e.y; this._z = e.z; return this; }
  }

  // ── Object graph ─────────────────────────────────────────────────────────
  class Object3D {
    constructor() {
      this.id = id("o");
      this.name = "";
      this.children = [];
      this.parent = null;
      this.userData = {};
      this.position = new Vector3();
      this.rotation = new Euler();
      this.scale = new Vector3(1, 1, 1);
      this.up = new Vector3(0, 1, 0);
      this.visible = true;
      this.matrixWorld = new Matrix4();
      this.frustumCulled = true;
    }
    add(o) { if (o && o !== this) { o.parent = this; this.children.push(o); } return this; }
    remove(o) {
      const i = this.children.indexOf(o);
      if (i >= 0) { this.children.splice(i, 1); o.parent = null; }
      return this;
    }
    traverse(cb) { cb(this); for (const c of [...this.children]) c.traverse(cb); return this; }
    lookAt(x, y, z) {
      const t = x instanceof Vector3 ? x : new Vector3(x, y, z);
      this._lookTarget = t.clone();
      return this;
    }
  }

  class Scene extends Object3D {
    constructor() { super(); this.isScene = true; this.background = null; this.environment = null; this.fog = null; }
  }
  class Group extends Object3D { constructor() { super(); this.isGroup = true; } }

  // ── Fog ──────────────────────────────────────────────────────────────────
  class FogExp2 {
    constructor(color, density = 0.00025) {
      this.isFogExp2 = true;
      this.color = color instanceof Color ? color : new Color(color);
      this.density = density;
    }
  }
  class Fog {
    constructor(color, near = 1, far = 1000) {
      this.isFog = true;
      this.color = color instanceof Color ? color : new Color(color);
      this.near = near; this.far = far;
    }
  }

  // ── Lights ───────────────────────────────────────────────────────────────
  class Light extends Object3D {
    constructor(color = 0xffffff, intensity = 1) {
      super();
      this.isLight = true;
      this.color = color instanceof Color ? color : new Color(color);
      this.intensity = intensity;
      this.castShadow = false;
      this.shadow = {
        mapSize: new Vector2(512, 512),
        bias: 0, radius: 1, blurSamples: 8,
        camera: { near: 0.5, far: 500, left: -5, right: 5, top: 5, bottom: -5, updateProjectionMatrix() {} },
      };
    }
    dispose() { dispose(`${this.kind ?? "Light"}.shadow`); }
  }
  class AmbientLight extends Light {
    constructor(color, intensity) { super(color, intensity); this.kind = "AmbientLight"; this.isAmbientLight = true; }
  }
  class HemisphereLight extends Light {
    constructor(skyColor = 0xffffff, groundColor = 0xffffff, intensity = 1) {
      super(skyColor, intensity);
      this.kind = "HemisphereLight"; this.isHemisphereLight = true;
      this.groundColor = groundColor instanceof Color ? groundColor : new Color(groundColor);
    }
  }
  class DirectionalLight extends Light {
    constructor(color, intensity) {
      super(color, intensity);
      this.kind = "DirectionalLight"; this.isDirectionalLight = true;
      this.target = new Object3D();
    }
  }
  class PointLight extends Light {
    constructor(color, intensity, distance = 0, decay = 2) {
      super(color, intensity);
      this.kind = "PointLight"; this.isPointLight = true;
      this.distance = distance; this.decay = decay;
    }
  }
  class SpotLight extends Light {
    constructor(color, intensity, distance = 0, angle = Math.PI / 3, penumbra = 0, decay = 2) {
      super(color, intensity);
      this.kind = "SpotLight"; this.isSpotLight = true;
      this.distance = distance; this.angle = angle; this.penumbra = penumbra; this.decay = decay;
      this.target = new Object3D();
    }
  }

  // ── Geometry / material ──────────────────────────────────────────────────
  class BufferGeometry {
    constructor() { this.type = "BufferGeometry"; this.attributes = {}; }
    setAttribute(name, a) { this.attributes[name] = a; return this; }
    dispose() { dispose(`geometry:${this.type}`); }
  }
  const geometryClass = (name) => class extends BufferGeometry {
    constructor(...args) { super(); this.type = name; this.parameters = args.slice(); }
  };

  class Material {
    constructor(params = {}) {
      this.id = id("m");
      // r160 identity flags that art branches on. An isX flag the double
      // omits silently reroutes real code: measured, applyEnvironmentMapToScene
      // applied to 0 materials until isMeshStandardMaterial existed here.
      this.isMaterial = true;
      // `new.target` is the leaf class here — subclass fields land after
      // super(), so defaults must be applied through a prototype hook that runs
      // BEFORE setValues(), or a constructor argument would be overwritten by
      // its own class default.
      this.type = new.target.name;
      this.visible = true;
      this.transparent = false;
      this.opacity = 1;
      this.side = FrontSide;
      this.blending = NormalBlending;
      this.depthWrite = true;
      this.depthTest = true;
      this.color = new Color(0xffffff);
      this.envMap = null;
      this.envMapIntensity = 1;
      this.defaults();
      this.setValues(params);
    }
    defaults() {}
    setValues(params) {
      for (const [k, v] of Object.entries(params)) {
        if ((k === "color" || k === "emissive") && !(this[k] instanceof Color)) this[k] = new Color();
        if (k === "color" || k === "emissive") {
          if (v instanceof Color) this[k].copy(v);
          else if (typeof v === "number") this[k].setHex(v);
          else if (typeof v === "string") this[k].setStyle(v);
        } else {
          this[k] = v;
        }
      }
      return this;
    }
    clone() {
      const c = new this.constructor();
      for (const [k, v] of Object.entries(this)) {
        c[k] = v && v.clone ? v.clone() : (v instanceof Color ? v.clone() : v);
      }
      c.id = id("m");
      return c;
    }
    dispose() { dispose(`material:${this.type}`); }
  }
  class MeshBasicMaterial extends Material {
    defaults() { this.isMeshBasicMaterial = true; this.map = null; this.alphaMap = null; }
  }
  class MeshStandardMaterial extends Material {
    defaults() {
      this.roughness = 1;
      this.metalness = 0;
      this.emissive = new Color(0x000000);
      this.emissiveIntensity = 1;
      this.map = null; this.alphaMap = null; this.normalMap = null;
      this.normalScale = new Vector2(1, 1);
      this.roughnessMap = null; this.metalnessMap = null;
      this.aoMap = null; this.emissiveMap = null;
      this.normalMapType = TangentSpaceNormalMap;
      this.isMeshStandardMaterial = true;
    }
  }
  class MeshPhysicalMaterial extends MeshStandardMaterial {
    defaults() {
      super.defaults();
      this.clearcoat = 0; this.clearcoatRoughness = 0; this.clearcoatMap = null;
      this.iridescence = 0; this.iridescenceIOR = 1; this.iridescenceThicknessRange = [100, 1];
      this.sheen = 0; this.sheenRoughness = 1; this.sheenColor = new Color(0xffffff);
      this.transmission = 0; this.thickness = 0; this.ior = 1.5;
      this.attenuationDistance = Infinity; this.attenuationColor = new Color(1, 1, 1);
      this.specularIntensity = 1; this.specularColor = new Color(1, 1, 1);
      this.reflectivity = 0.5; this.roughness = 1;
      this.isMeshPhysicalMaterial = true;
      // NOTE: no `dispersion` — three r160 does not define it.
    }
  }
  class ShaderMaterial extends Material {
    defaults() { this.isShaderMaterial = true; this.uniforms = {}; this.vertexShader = ""; this.fragmentShader = ""; this.glslVersion = null; }
  }
  class PointsMaterial extends Material { defaults() { this.isPointsMaterial = true; this.size = 1; this.sizeAttenuation = true; this.map = null; } }
  class LineBasicMaterial extends Material { defaults() { this.isLineBasicMaterial = true; this.linewidth = 1; this.linecap = "round"; this.linejoin = "round"; } }
  class SpriteMaterial extends Material { defaults() { this.isSpriteMaterial = true; this.map = null; this.rotation = 0; this.sizeAttenuation = true; } }

  class Texture {
    constructor() {
      this.id = id("t");
      this.isTexture = true;
      this.wrapS = ClampToEdgeWrapping; this.wrapT = ClampToEdgeWrapping;
      this.magFilter = LinearFilter; this.minFilter = LinearMipmapLinearFilter;
      this.anisotropy = 1; this.needsUpdate = false; this.colorSpace = NoColorSpace;
    }
    dispose() { dispose(`texture:${this.kind ?? "Texture"}`); }
  }
  class DataTexture extends Texture {
    constructor(data, width, height, format) {
      super();
      this.kind = "DataTexture"; this.isDataTexture = true;
      this.image = { data, width, height };
      this.format = format;
    }
  }
  class CanvasTexture extends Texture {
    constructor(canvas) { super(); this.kind = "CanvasTexture"; this.isCanvasTexture = true; this.image = canvas; }
  }

  class Mesh extends Object3D {
    constructor(geometry, material) {
      super();
      this.isMesh = true;
      this.geometry = geometry ?? new BufferGeometry();
      this.material = material ?? new MeshBasicMaterial();
    }
  }
  class Points extends Object3D {
    constructor(geometry, material) { super(); this.isPoints = true; this.geometry = geometry; this.material = material; }
  }
  class Sprite extends Object3D {
    constructor(material) { super(); this.isSprite = true; this.material = material; }
  }

  // ── Camera ───────────────────────────────────────────────────────────────
  class Camera extends Object3D {
    constructor() { super(); this.isCamera = true; this.projectionMatrix = new Matrix4(); this.matrixWorldInverse = new Matrix4(); }
  }
  class PerspectiveCamera extends Camera {
    constructor(fov = 50, aspect = 1, near = 0.1, far = 2000) {
      super();
      this.isPerspectiveCamera = true;
      this.fov = fov; this.aspect = aspect; this.near = near; this.far = far;
      this.zoom = 1; this.filmOffset = 0;
      this.updateProjectionMatrix();
    }
    updateProjectionMatrix() {
      const near = this.near;
      const top = (near * Math.tan(DEG2RAD * 0.5 * this.fov)) / this.zoom;
      const height = 2 * top;
      const width = this.aspect * height;
      const left = -0.5 * width;
      this.projectionMatrix.makePerspective(left, left + width, top, top - height, near, this.far);
    }
    /**
     * Build world + view matrices from position, `lookAt` target (or Euler
     * rotation) and `up`. For the look-dev rigs the target is always off-axis,
     * so the degenerate up/forward case cannot happen — if it does, throw rather
     * than silently emit NaNs into a receipt.
     */
    updateMatrixWorld() {
      const eye = this.position;
      const target = this._lookTarget ? new Vector3().copy(this._lookTarget) : new Vector3(eye.x, eye.y, eye.z - 1);
      const zAxis = new Vector3(eye.x - target.x, eye.y - target.y, eye.z - target.z);
      if (zAxis.length() < 1e-9) throw new Error("lookdev double: zero-length camera forward axis");
      zAxis.normalize();
      const xAxis = new Vector3().crossVectors(this.up, zAxis);
      if (xAxis.length() < 1e-9) throw new Error("lookdev double: camera up is parallel to forward axis");
      xAxis.normalize();
      const yAxis = new Vector3().crossVectors(zAxis, xAxis);
      const dot = (v) => v.x * eye.x + v.y * eye.y + v.z * eye.z;
      this.matrixWorldInverse
        .setRowVector(0, xAxis.x, xAxis.y, xAxis.z, -dot(xAxis))
        .setRowVector(1, yAxis.x, yAxis.y, yAxis.z, -dot(yAxis))
        .setRowVector(2, zAxis.x, zAxis.y, zAxis.z, -dot(zAxis))
        .setRowVector(3, 0, 0, 0, 1);
      return this;
    }
  }

  // ── Render targets / PMREM ───────────────────────────────────────────────
  class WebGLRenderTarget {
    constructor(width, height, options = {}) {
      this.id = id("rt");
      this.width = width; this.height = height;
      this.options = options;
      this.texture = new Texture();
      this.texture.kind = "RenderTargetTexture";
    }
    setSize(w, h) { this.width = w; this.height = h; }
    dispose() { dispose(`renderTarget:${this.width}x${this.height}`); }
  }
  class WebGLCubeRenderTarget extends WebGLRenderTarget {
    constructor(size = 256, options = {}) {
      super(size, size, options);
      this.isWebGLCubeRenderTarget = true;
      this.texture.kind = "CubeRenderTargetTexture";
    }
    fromEquirectangularTexture() { return this.texture; }
    clear() { return this; }
  }
  class CubeCamera extends Object3D {
    constructor(near = 0.1, far = 100, renderTarget = null) {
      super();
      this.isCubeCamera = true;
      this.near = near; this.far = far;
      this.renderTarget = renderTarget;
    }
    update(renderer, scene) {
      event(`CubeCamera.update(near=${this.near},far=${this.far},rt=${this.renderTarget?.width ?? "?"})`);
      if (renderer && typeof renderer.__observeCube === "function") renderer.__observeCube(this, scene);
    }
  }
  class PMREMGenerator {
    constructor(renderer) { this.renderer = renderer; this.autoFinish = true; }
    compileCubemapShader() { event("PMREM.compileCubemapShader"); }
    compileEquirectangularShader() { event("PMREM.compileEquirectangularShader"); }
    fromScene(scene, sigma = 0, near = 0.1, far = 100) {
      event(`PMREM.fromScene(sigma=${sigma},near=${near},far=${far})`);
      return { texture: makePmremTexture(`fromScene:${sigma}:${near}:${far}`), dispose: () => dispose("pmremTarget") };
    }
    fromCubemap(cubemap) {
      event(`PMREM.fromCubemap(${cubemap?.kind ?? "?"})`);
      return { texture: makePmremTexture(`fromCubemap:${cubemap?.kind ?? "?"}`), dispose: () => dispose("pmremTarget") };
    }
    fromEquirectangular(equirect) {
      event(`PMREM.fromEquirectangular(${equirect?.kind ?? "?"})`);
      return { texture: makePmremTexture(`fromEquirectangular:${equirect?.kind ?? "?"}`), dispose: () => dispose("pmremTarget") };
    }
    dispose() { dispose("PMREMGenerator"); }
  }
  const makePmremTexture = (tag) => {
    const t = new Texture();
    t.kind = "PMREM"; t.tag = tag;
    return t;
  };

  class WebGLRenderer {
    constructor(params = {}) {
      this.params = params;
      this.domElement = { width: 0, height: 0, style: {} };
      this.toneMapping = NoToneMapping;
      this.toneMappingExposure = 1;
      this.outputColorSpace = SRGBColorSpace;
      this.shadowMap = { enabled: false, type: PCFShadowMap, autoUpdate: true, needsUpdate: false };
      this.info = { render: { calls: 0, triangles: 0 }, memory: { geometries: 0, textures: 0 } };
      this.pixelRatio = 1;
      this.extensions = { get: () => null };
      this.capabilities = {
        isWebGL2: true, maxTextureSize: 8192, maxAnisotropy: 16,
        getMaxAnisotropy: () => 16, precision: "highp",
      };
      this._cubeUpdates = [];
      const self = this;
      this.__observeCube = (cam, scene) => { self._cubeUpdates.push({ near: cam.near, far: cam.far, children: countScene(scene) }); };
    }
    setPixelRatio(r) { this.pixelRatio = r; }
    setSize(w, h) { this.domElement.width = w; this.domElement.height = h; }
    getContext() { return null; }
    getRenderTarget() { return null; }
    setRenderTarget() { return this; }
    render() { return this; }
    compile() { return this; }
    dispose() { dispose("WebGLRenderer"); }
  }
  const countScene = (scene) => { let n = 0; scene?.traverse?.(() => { n++; }); return n; };

  class BufferAttribute {
    constructor(array, itemSize) { this.array = array; this.itemSize = itemSize; this.count = array.length / itemSize; }
    setUsage() { return this; }
    needsUpdateValue() { return this; }
  }

  class Shape {
    moveTo() { return this; }
    lineTo() { return this; }
    quadraticCurveTo() { return this; }
    bezierCurveTo() { return this; }
    absarc() { return this; }
  }
  class Path extends Shape {}
  class QuadraticBezierCurve3 { constructor(...a) { this.points = a; } }

  const THREE = {
    REVISION: "160-double",
    Color, Vector2, Vector3, Euler, Matrix4,
    Object3D, Scene, Group, Fog, FogExp2,
    AmbientLight, HemisphereLight, DirectionalLight, PointLight, SpotLight,
    BufferGeometry, BufferAttribute,
    BoxGeometry: geometryClass("BoxGeometry"),
    PlaneGeometry: geometryClass("PlaneGeometry"),
    SphereGeometry: geometryClass("SphereGeometry"),
    CircleGeometry: geometryClass("CircleGeometry"),
    RingGeometry: geometryClass("RingGeometry"),
    ConeGeometry: geometryClass("ConeGeometry"),
    CylinderGeometry: geometryClass("CylinderGeometry"),
    TorusGeometry: geometryClass("TorusGeometry"),
    IcosahedronGeometry: geometryClass("IcosahedronGeometry"),
    ExtrudeGeometry: geometryClass("ExtrudeGeometry"),
    TubeGeometry: geometryClass("TubeGeometry"),
    Shape, Path, QuadraticBezierCurve3,
    Mesh, Points, Sprite,
    MeshBasicMaterial, MeshStandardMaterial, MeshPhysicalMaterial,
    ShaderMaterial, PointsMaterial, LineBasicMaterial, SpriteMaterial,
    Texture, DataTexture, CanvasTexture,
    Camera, PerspectiveCamera,
    WebGLRenderer, WebGLRenderTarget, WebGLCubeRenderTarget, CubeCamera, PMREMGenerator,
    NoToneMapping, LinearToneMapping, ReinhardToneMapping, CineonToneMapping,
    ACESFilmicToneMapping, CustomToneMapping, AgXToneMapping,
    BasicShadowMap, PCFShadowMap, PCFSoftShadowMap, VSMShadowMap,
    FrontSide, BackSide, DoubleSide,
    NormalBlending, AdditiveBlending,
    RepeatWrapping, ClampToEdgeWrapping, MirroredRepeatWrapping,
    NearestFilter, LinearFilter, LinearMipmapLinearFilter,
    RGBAFormat, TangentSpaceNormalMap, ObjectSpaceNormalMap,
    SRGBColorSpace, LinearSRGBColorSpace, NoColorSpace,
    WebGLCoordinateSystem,
    MathUtils: {
      DEG2RAD, RAD2DEG: 1 / DEG2RAD,
      clamp, lerp: (x, y, a) => x + (y - x) * a,
      smoothstep: (x, min, max) => { const t = clamp((x - min) / (max - min), 0, 1); return t * t * (3 - 2 * t); },
      randFloat: () => { throw new Error("lookdev double: Math.random() is not allowed in a pinned scene"); },
    },
    SRGBToLinear, LinearToSRGB,
    DoublePrecision: true,
  };
  return { THREE, recorder, reset };
}

export const r160 = { SRGBToLinear, LinearToSRGB, LinearToneMapping, AgXToneMapping, ACESFilmicToneMapping };
