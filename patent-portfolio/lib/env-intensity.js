/**
 * Environment-map intensity — one authored base, many multipliers.
 * =================================================================
 *
 * Why this file exists (lane V5-ART-ENGINE-MATERIALS-1102, RSI40-1102):
 *
 * `envMapIntensity` is written from four places that do not know about each
 * other, and none of them remembers what the material's author asked for:
 *
 *   lib/materials.js:304        applyEnvironmentMapToScene → `intensity * preset`
 *   lib/materials.js:326        updateEnvironmentMapIntensity → `intensity`
 *   lib/culling-system.js:518   LOD 'high'  → restores a captured snapshot
 *   lib/culling-system.js:524/531 LOD medium/low → `0.3` / `0`
 *   lib/performance.js:636      distant objects → `0`
 *
 * The apply at :304 is a bare assignment of `intensity * preset`, and main.js:852
 * passes `intensity` as the literal 1.0 — so after one apply EVERY env-mapped PBR
 * material in the museum holds the identical number, whatever its author wrote.
 * Measured on the running app (headless chromium over this lane's own served
 * tree, sha256-verified against disk before the reading): 905 env-mapped material
 * slots across 545 distinct materials. What the law in this file now preserves,
 * read back out of the live scene at the Medium preset (0.9):
 *
 *   0.9 x724 · 0.27 x83 · 0.72 x67 · 1.08 x14 · 1.17 x10 · 1.26 x3 · 0.45 x2 · 1.35 x2
 *
 * i.e. eight authored bases — 1.0, 0.3, 0.8, 1.2, 1.3, 1.4, 0.5, 1.5 — each scaled
 * by the preset instead of replaced by it. 29 of those slots sit ABOVE the preset
 * value (p1-e8-lattice.js:236 at 1.5, p1-quantum-safe.js:217 at 1.4, :271 at 1.3);
 * under an absolute write that is not merely unlikely, it is unrepresentable —
 * every one of them was being pulled DOWN to 0.9 while
 * `museum/architecture.js:122` (authored 0.5) and the concrete at
 * `lib/materials.js:419` (authored 0.3) were being pushed UP to it.
 *
 * The authored-ZERO case is real but LATENT, and it is stated as such because
 * the first version of this comment claimed it live and the measurement did not
 * support that: `createWallMaterial` (`lib/materials.js:677`) authors
 * `envMapIntensity: 0`, and the only route to it is the `MATERIAL_PRESETS` table
 * at :1026-1027, which has zero callers on any reachable path. The wall the
 * visitor actually sees is the concrete one at 0.3. So the zero case is proven
 * here by direct invocation rather than by observation: at both 'ultra' (1.5) and
 * 'low' (0.6) an authored 0 measures 0, where the retired write put 1.5 on it.
 *
 * Worse, it cannot be undone. `main.js:513` applies the environment map before
 * `main.js:535` initialises the culling system, so the very first LOD snapshot
 * captured the already-flattened preset value as the "original". And the snapshot
 * line was `a || b`: when an authored 0 is legitimately captured, the next medium
 * step re-evaluates `0 || 0.3` and adopts the degradation's own output as the new
 * baseline, so the material ratchets 0 → 0.3 and 'high' can no longer restore it.
 *
 * The law this file installs instead: **the authored number is the base; the
 * quality preset, the global knob, and an LOD level are multipliers on it.**
 * A base of 0 stays 0 under every multiplier, which is the whole point of
 * authoring it. The base is held in a WeakMap keyed by the material — first
 * touch wins, later writes can never corrupt it, and a disposed material is
 * collected with its entry. It is not stored on `material` or in
 * `userData`, because both travel into `toJSON()` and into cloned materials.
 *
 * Nothing here touches the PMREM generator itself
 * (`lib/materials.js:150-278`) — it is correct: one
 * `PMREMGenerator.fromScene` per environment, `RoundRobinGLES`-safe, disposed
 * render targets. The incoherence was never in the map; it is in the scalar
 * that scales it.
 *
 * h(x) ≥ 0 always
 */

/** Base per material, first-touch-wins. WeakMap: a disposed material costs nothing. */
const authoredBases = new WeakMap();

/** Multipliers for the LOD ladder, expressed against the authored base (not absolute). */
export const LOD_ENV_SCALE = Object.freeze({
    high: 1.0,
    medium: 0.25,
    low: 0.0
});

/**
 * The quality preset's env scale, mirrored here so the LOD and distance
 * writers can compose against the SAME preset as the scene-wide pass without
 * importing lib/materials.js (which would be a cycle: materials.js imports
 * this file). `setMaterialQuality` keeps it in step.
 */
let presetScale = 1.0;

export function setEnvPresetScale(scale) {
    presetScale = Number.isFinite(scale) && scale > 0 ? scale : 1.0;
    return presetScale;
}

export function getEnvPresetScale() {
    return presetScale;
}

/**
 * @param {object} material  anything with a numeric envMapIntensity
 * @returns {boolean} true when the material participates in IBL at all
 */
export function isEnvironmentScaled(material) {
    if (!material) return false;
    return (material.isMeshStandardMaterial === true || material.isMeshPhysicalMaterial === true)
        && typeof material.envMapIntensity === 'number'
        && Number.isFinite(material.envMapIntensity);
}

/**
 * Record what the material's author asked for, if nobody has yet.
 * Call this at the earliest point a material is reachable — before any
 * scene-wide pass can flatten it. Idempotent: the first value wins forever.
 */
export function rememberAuthored(material) {
    if (!material || !isEnvironmentScaled(material)) return null;
    if (authoredBases.has(material)) return authoredBases.get(material);
    const base = Math.max(0, material.envMapIntensity);
    authoredBases.set(material, base);
    return base;
}

/**
 * The authored base, or `null` when this material has never been seen.
 * Never `||` a captured base against a live value — that is the exact bug
 * this file replaces (an authored 0 is falsy).
 */
export function authoredEnvIntensity(material) {
    if (!material || !authoredBases.has(material)) return null;
    return authoredBases.get(material);
}

/**
 * The value a material should carry right now.
 *
 * @param {object} material
 * @param {number} multiplier  product of every independent scale in play
 *                             (quality preset × global knob × LOD level)
 * @returns {number} authored × multiplier
 */
export function resolveEnvIntensity(material, multiplier = 1) {
    const base = rememberAuthored(material);
    if (base === null) return 0;
    if (!Number.isFinite(multiplier) || multiplier <= 0) return 0;
    const scaled = base * multiplier;
    // No ceiling against the base: the quality preset is legitimately > 1 at
    // 'high' (1.2) and 'ultra' (1.5), so clamping to the base would flatten
    // exactly the highlight materials the law exists to protect. The
    // protection that matters is multiplicative — a base of 0 stays 0 under
    // every multiplier, which is the whole point of authoring it.
    return Number.isFinite(scaled) && scaled > 0 ? scaled : 0;
}

/**
 * Write the resolved value. Returns false when there was nothing to write,
 * so callers can count what they touched (applyEnvironmentMapToScene's `count`).
 */
export function setEnvIntensity(material, multiplier = 1) {
    if (!isEnvironmentScaled(material)) return false;
    const next = resolveEnvIntensity(material, multiplier);
    if (material.envMapIntensity === next) return false;
    material.envMapIntensity = next;
    material.needsUpdate = true;
    return true;
}

/**
 * Capture the authored base across a whole subtree, at construction time.
 * Cheap (one walk) and safe to call repeatedly — first touch wins.
 */
export function registerEnvMaterials(root) {
    if (!root || typeof root.traverse !== 'function') return 0;
    let n = 0;
    root.traverse(obj => {
        if (!obj.isMesh || !obj.material) return;
        const mats = Array.isArray(obj.material) ? obj.material : [obj.material];
        mats.forEach(m => { if (rememberAuthored(m) !== null) n++; });
    });
    return n;
}
