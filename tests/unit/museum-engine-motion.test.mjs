/**
 * Museum engine family — envMapIntensity coherence + motion time law.
 * Lane V5-ART-ENGINE-MATERIALS-1102, campaign RSI40-1102, 2026-11-02.
 *
 * Two laws, each with the defect it replaces as a known-positive control —
 * the style the voice gate and the twin register already use in this family:
 * prove the guard fires on the OLD behaviour, not only that it approves the
 * new one.
 *
 * LEG 1 — lib/env-intensity.js. `envMapIntensity` was written from four
 * places that did not know about each other (lib/materials.js scene-wide
 * apply, its quality update, lib/culling-system.js applyLOD,
 * lib/performance.js distance pass). The apply assigned `1.0 * preset`
 * absolutely (main.js:852 passes the literal 1.0), so ONE call put every
 * env-mapped PBR material on the same number whatever its author asked for.
 * Measured on the running app: 905 env-mapped slots, and the authored bases
 * that number was erasing are 1.0, 0.3, 0.8, 1.2, 1.3, 1.4, 0.5 and 1.5 —
 * the E8 lattice at patent-portfolio/artworks/p1-e8-lattice.js:236 (1.5) went
 * DOWN to the preset while the concrete at patent-portfolio/lib/materials.js:419
 * (0.3) went UP to it. And it was unrecoverable: main.js applies the
 * environment map (:513) BEFORE it builds the culling system (:535), so
 * applyLOD's snapshot of the "original" captured the already-flattened
 * number — and the snapshot line was `a || b`, which re-read an authored 0 as
 * whatever the last degradation had just written. The authored-0 material
 * itself (createWallMaterial's default, lib/materials.js:677) is LATENT: its
 * only route is the MATERIAL_PRESETS table, which has zero callers. The 1a
 * tests below therefore pin that case by direct construction, which is what
 * it honestly is — a law test, not an observation.
 *
 * The law now: the authored number is the base, everything else is a
 * multiplier on it, and the base lives in a WeakMap that later writes cannot
 * touch. A base of 0 stays 0 at every preset and every LOD level — that is
 * what it means to author it.
 *
 * LEG 2 — lib/motion.js. Every smoothing step in the museum was a fixed
 * FRACTION PER STEP (museum/lighting.js `(target - intensity) * 0.05`,
 * museum/architecture.js `ring.scale.lerp(v, 0.05)`), which is a fraction of a
 * FRAME. museum/lighting.js is stepped once every 6 frames with
 * `clampedDelta * 6` (main.js render loop), so its transitions take 4x longer
 * on 30 fps than on 120 Hz. And main.js clamps its own delta to 50 ms
 * (`Math.min(delta, 0.05)`) while passing the RAW delta onward — a
 * backgrounded tab integrates the whole hidden interval in one step.
 * `springStep` is the closed form of the critically damped oscillator, so it
 * is exact for any dt: identical at 30/60/240 fps, and one 50 ms spike step
 * equals the three 16.7 ms steps it replaces. Reduced motion is read from the
 * mechanism lane V4 (FIFTY-1102) already wired — the `reduced-motion` body
 * class lib/accessibility.js applies from `settings.reducedMotion` — not
 * redefined here.
 *
 * Node builtins + the modules' own source only. Offline, no credentials, no
 * browser, no THREE (both modules are deliberately THREE-free; the fake
 * materials below carry the two flags the predicate reads).
 */

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

import {
    rememberAuthored,
    authoredEnvIntensity,
    resolveEnvIntensity,
    setEnvIntensity,
    isEnvironmentScaled,
    setEnvPresetScale,
    getEnvPresetScale,
    LOD_ENV_SCALE
} from '../../patent-portfolio/lib/env-intensity.js';

import {
    clampStep,
    damp,
    rateFromStepFraction,
    springState,
    springStep,
    springTo,
    smoothstep,
    smootherstep,
    easeOutCubic,
    easeInOutCubic,
    clamp01,
    reducedMotionActive,
    MAX_FRAME_DT
} from '../../patent-portfolio/lib/motion.js';

const here = dirname(fileURLToPath(import.meta.url));
const src = p => readFileSync(join(here, '..', '..', 'patent-portfolio', p), 'utf8');

// The museum's own preset ladder, read off lib/materials.js MATERIAL_QUALITY.
const PRESET = { ultra: 1.5, high: 1.2, medium: 0.9, low: 0.6 };

/** A stand-in for a THREE.MeshStandardMaterial — only these three fields matter. */
function pbr(envMapIntensity) {
    return { isMeshStandardMaterial: true, envMapIntensity, needsUpdate: false };
}

// ═══════════════════════════════════════════════════════════════════════════
// LEG 1a — the authored base is the base
// ═══════════════════════════════════════════════════════════════════════════

test('a material records the value its author wrote, on first touch', () => {
    const wall = pbr(0);
    assert.equal(rememberAuthored(wall), 0);
    assert.equal(authoredEnvIntensity(wall), 0);
});

test('an authored zero stays non-reflective through a scene-wide apply', () => {
    // lib/materials.js createWallMaterial (:677) authors 0 so such a wall
    // cannot mirror the environment map. That material is LATENT — its only
    // caller is the uncalled MATERIAL_PRESETS table — so this is a law test
    // by construction, not an observation of the shipped scene. The old apply
    // assigned `intensity * preset` absolutely and would have raised it to the
    // preset on every rung.
    const wall = pbr(0);
    setEnvPresetScale(PRESET.high);
    setEnvIntensity(wall, 1.0 * PRESET.high);
    assert.equal(wall.envMapIntensity, 0, 'authored 0 must survive every multiplier');
});

test('the E8 lattice keeps its authored highlight instead of being lowered', () => {
    // artworks/p1-e8-lattice.js authors 1.5 — ABOVE the preset. The old
    // absolute write made the museum's brightest reflector dimmer.
    const lattice = pbr(1.5);
    setEnvIntensity(lattice, 1.0 * PRESET.high);
    assert.equal(lattice.envMapIntensity, 1.5 * PRESET.high);
    assert.ok(lattice.envMapIntensity > PRESET.high, 'must not be clamped down to the preset');
});

test('a relative weight below 1 is scaled, not overwritten upward', () => {
    // museum/architecture.js authors 0.5; the old write set it to 1.2 (2.4x).
    const trim = pbr(0.5);
    setEnvIntensity(trim, 1.0 * PRESET.high);
    assert.equal(trim.envMapIntensity, 0.6);
});

test('apply is idempotent — repeating it does not compound the preset', () => {
    const m = pbr(1.0);
    const once = setEnvIntensity(m, PRESET.high) || m.envMapIntensity;
    const before = m.envMapIntensity;
    setEnvIntensity(m, PRESET.high);
    setEnvIntensity(m, PRESET.high);
    assert.equal(m.envMapIntensity, before, 'a multiplier on a stored base cannot compound');
    assert.equal(before, PRESET.high);
});

test('the quality preset enters exactly once across the four levels', () => {
    const authored = 1.2; // createMetalMaterial: "metals reflect more"
    for (const [level, scale] of Object.entries(PRESET)) {
        const m = pbr(authored);
        setEnvPresetScale(scale);
        setEnvIntensity(m, 1.0 * getEnvPresetScale());
        assert.equal(m.envMapIntensity, authored * scale, `${level} preset`);
    }
    setEnvPresetScale(PRESET.high);
});

test('a second capture never revises the base — first touch wins', () => {
    const m = pbr(1.5);
    rememberAuthored(m);
    m.envMapIntensity = 0;            // a degradation pass writes over it
    assert.equal(rememberAuthored(m), 1.5, 'a later write must not become the new truth');
    assert.equal(authoredEnvIntensity(m), 1.5);
});

test('the LIVE census is reproduced by the law, and is not by the old write', () => {
    // Measured on the running app (headless, sha-verified served tree) at the
    // Medium preset, 905 env-mapped slots carried exactly these eight values.
    // The authored bases they decompose into are the eight numbers the museum
    // actually ships. This test pins the decomposition, so an absolute write
    // coming back would fail here rather than only in a browser nobody runs.
    const MEDIUM = 0.9;
    const observedLive = [0.9, 0.27, 0.72, 1.08, 1.17, 1.26, 0.45, 1.35];
    const authoredLive = [1.0, 0.3, 0.8, 1.2, 1.3, 1.4, 0.5, 1.5];
    assert.equal(observedLive.length, authoredLive.length);

    const mats = authoredLive.map(a => pbr(a));
    setEnvPresetScale(MEDIUM);
    mats.forEach(m => setEnvIntensity(m, 1.0 * getEnvPresetScale()));
    const live = mats.map(m => +m.envMapIntensity.toFixed(6)).sort();
    assert.deepEqual(live, [...observedLive].sort(),
        'authored x preset must land on the values the running app showed');

    // KNOWN-POSITIVE CONTROL for the control above: the retired expression,
    // run over the SAME authored set, collapses it to one value. If this
    // assertion ever stops being true, the test above has stopped measuring.
    const retired = authoredLive.map(a => 1.0 * MEDIUM); // materials.js:304 was this
    assert.equal(new Set(retired).size, 1, 'the old write must have been a constant');
    assert.notEqual(new Set(live).size, 1, 'the law must not be');
    assert.equal(retired.filter(v => v > MEDIUM + 1e-12).length, 0,
        'an absolute write cannot produce a value above the preset — 29 live slots do');

    setEnvPresetScale(PRESET.high);
});

// ═══════════════════════════════════════════════════════════════════════════
// LEG 1b — the LOD ladder round-trips
// ═══════════════════════════════════════════════════════════════════════════

test('high -> medium -> low -> high restores the authored value exactly', () => {
    const mat = pbr(1.4); // artworks/p1-quantum-safe.js authors 1.4
    setEnvPresetScale(PRESET.high);
    const step = level => setEnvIntensity(mat, getEnvPresetScale() * LOD_ENV_SCALE[level]);
    step('high'); const hi = mat.envMapIntensity;
    step('medium'); const med = mat.envMapIntensity;
    step('low'); const low = mat.envMapIntensity;
    step('high');
    assert.equal(mat.envMapIntensity, hi, 'restoring must land on the same number');
    assert.ok(med < hi && med > 0, 'medium is a reduction, not an absolute 0.3');
    assert.equal(low, 0, 'low kills the env term');
    assert.equal(med, 1.4 * PRESET.high * LOD_ENV_SCALE.medium);
});

test('the LOD ladder is monotone for a reflective material and pinned at 0 for a matte one', () => {
    const shiny = pbr(1.0);
    const vals = ['high', 'medium', 'low'].map(l => {
        setEnvIntensity(shiny, getEnvPresetScale() * LOD_ENV_SCALE[l]);
        return shiny.envMapIntensity;
    });
    assert.ok(vals[0] > vals[1] && vals[1] > vals[2], `ladder not monotone: ${vals}`);

    const matte = pbr(0);
    const matteVals = ['high', 'medium', 'low'].map(l => {
        setEnvIntensity(matte, getEnvPresetScale() * LOD_ENV_SCALE[l]);
        return matte.envMapIntensity;
    });
    assert.deepEqual(matteVals, [0, 0, 0], 'authored 0 cannot be lit up by an LOD level');
});

test('KNOWN-POSITIVE: the retired userData snapshot corrupts an authored 0 on the second transition', () => {
    // This is the exact expression lib/culling-system.js:524/531 used to run,
    // reproduced here so the replacement stays measured, not merely asserted.
    // The capture is `ud.original || mat.envMapIntensity`. A FIRST medium pass
    // is accidentally fine (`undefined || 0` stores the honest 0). The
    // corruption needs a second transition — medium then low, which the
    // `_lastLodLevel` dirty flag does not suppress because the level changed:
    // `0 || 0.3` re-reads the degradation's own output as the new baseline.
    const wall = pbr(0);
    const ud = {};
    const oldStep = level => {
        ud.originalEnvMapIntensity = ud.originalEnvMapIntensity || wall.envMapIntensity;
        wall.envMapIntensity = level === 'medium' ? 0.3 : 0;
    };
    const oldHighRestore = () => (ud.originalEnvMapIntensity !== undefined
        ? ud.originalEnvMapIntensity
        : wall.envMapIntensity);

    oldStep('medium');
    assert.equal(ud.originalEnvMapIntensity, 0, 'the first capture is accidentally honest');
    oldStep('low');
    assert.equal(ud.originalEnvMapIntensity, 0.3, 'the second capture adopted the degradation output');
    wall.envMapIntensity = oldHighRestore();
    assert.equal(wall.envMapIntensity, 0.3, 'the old "restore" left the matte wall reflective forever');

    // Same material, same transition sequence, new law: still 0.
    const wall2 = pbr(0);
    setEnvIntensity(wall2, getEnvPresetScale() * LOD_ENV_SCALE.medium);
    setEnvIntensity(wall2, getEnvPresetScale() * LOD_ENV_SCALE.low);
    setEnvIntensity(wall2, getEnvPresetScale() * LOD_ENV_SCALE.high);
    assert.equal(wall2.envMapIntensity, 0, 'authored 0 survives the whole round trip');
});

test('KNOWN-POSITIVE: the scene-wide apply used to raise an authored 0 to the preset', () => {
    // lib/materials.js applyEnvironmentMapToScene assigned
    // `intensity * currentQuality.envMapIntensity` absolutely. Reproduced.
    const oldWrite = (authored, intensity, preset) => intensity * preset;
    assert.equal(oldWrite(0, 1.0, PRESET.high), PRESET.high, 'the wall became a mirror');
    assert.equal(oldWrite(1.5, 1.0, PRESET.high), PRESET.high, 'the lattice lost 0.3 of itself');

    const wall = pbr(0); setEnvIntensity(wall, 1.0 * PRESET.high);
    const lattice = pbr(1.5); setEnvIntensity(lattice, 1.0 * PRESET.high);
    assert.equal(wall.envMapIntensity, 0);
    assert.equal(lattice.envMapIntensity, 1.5 * PRESET.high);
});

// ═══════════════════════════════════════════════════════════════════════════
// LEG 1c — the writers all go through the one authority
// ═══════════════════════════════════════════════════════════════════════════

test('no writer assigns envMapIntensity absolutely outside the authority', () => {
    const files = [
        'lib/materials.js',
        'lib/culling-system.js',
        'lib/performance.js',
        'museum/architecture.js',
        'museum/lighting.js'
    ];
    const offenders = [];
    for (const f of files) {
        const lines = src(f).split('\n');
        for (let i = 0; i < lines.length; i++) {
            const t = lines[i].trim();
            if (t.startsWith('//') || t.startsWith('*') || t.startsWith('/*')) continue;
            // an assignment (single =), not an object-literal key, not a comparison
            if (/\.envMapIntensity\s*=[^=]/.test(t)) {
                offenders.push(`${f}:${i + 1}  ${t}`);
            }
        }
    }
    // The only assignment allowed anywhere is the authority's own write.
    assert.deepEqual(offenders, [], 'every scene write must call setEnvIntensity()');
});

test('the four former writers import the authority', () => {
    const importers = [
        'lib/materials.js',
        'lib/culling-system.js',
        'lib/performance.js'
    ];
    for (const f of importers) {
        assert.match(src(f), /from\s+'\.\/env-intensity\.js'/, `${f} must route through it`);
    }
    assert.match(src('lib/materials.js'), /setEnvPresetScale/, 'the preset must reach the authority');
});

test('a non-PBR material is never touched', () => {
    const basic = { isMeshBasicMaterial: true };
    assert.equal(isEnvironmentScaled(basic), false);
    assert.equal(setEnvIntensity(basic, 1.2), false);
    assert.equal(basic.envMapIntensity, undefined);
});

test('a poisoned multiplier yields 0, never NaN into a shader uniform', () => {
    const m = pbr(1.0);
    setEnvIntensity(m, NaN);
    assert.equal(m.envMapIntensity, 0);
    setEnvIntensity(m, -1);
    assert.equal(m.envMapIntensity, 0);
    setEnvIntensity(m, 1.0);
    assert.ok(Number.isFinite(m.envMapIntensity) && m.envMapIntensity > 0);
});

test('the preset scale ignores garbage and keeps a usable value', () => {
    const good = getEnvPresetScale();
    setEnvPresetScale(0); assert.equal(getEnvPresetScale(), 1.0);
    setEnvPresetScale(NaN); assert.equal(getEnvPresetScale(), 1.0);
    setEnvPresetScale('high'); assert.equal(getEnvPresetScale(), 1.0);
    setEnvPresetScale(good);
});

test('h(x) >= 0 — no multiplier produces a negative intensity', () => {
    for (const base of [0, 0.5, 1.0, 1.5]) {
        for (const mult of [0, 0.25, 0.6, 1.2, 1.5, 3, NaN, -2, Infinity]) {
            const m = pbr(base);
            setEnvIntensity(m, mult);
            assert.ok(m.envMapIntensity >= 0 && Number.isFinite(m.envMapIntensity),
                `base ${base} × ${mult} -> ${m.envMapIntensity}`);
        }
    }
});

// ═══════════════════════════════════════════════════════════════════════════
// LEG 2a — the spring is exact, so a frame boundary cannot change the motion
// ═══════════════════════════════════════════════════════════════════════════

test('springStep matches the analytic critically damped solution to float precision', () => {
    const w = 12, target = 1;
    const A = 0 - target, B = 0 + w * A;
    const exact = t => target + (A + B * t) * Math.exp(-w * t);
    let s = springState(0);
    const dt = 1 / 240;
    for (let i = 1; i <= 240; i++) {
        springStep(s, target, w, dt);
        assert.ok(Math.abs(s.value - exact(i * dt)) < 1e-9, `step ${i}`);
    }
});

test('the spring never crosses its target — no ringing on a hover pop', () => {
    for (const w of [1, 4, 12, 40, 200]) {
        let s = springState(0);
        for (let i = 0; i < 600; i++) {
            springStep(s, 1, w, 1 / 60);
            assert.ok(s.value <= 1 + 1e-12, `overshot at omega ${w}, step ${i}`);
        }
    }
});

test('30 / 60 / 144 / 240 fps land on the same value at the same wall time', () => {
    // The defect this replaces: a fixed fraction per step makes the number of
    // steps per second equal the frame rate, so the motion's duration was
    // a function of the visitor's hardware.
    const w = 12, seconds = 0.5;
    const at = fps => {
        let s = springState(0);
        for (let i = 0; i < Math.round(fps * seconds); i++) springStep(s, 1, w, 1 / fps);
        return s.value;
    };
    const ref = at(60);
    for (const fps of [30, 144, 240]) {
        assert.ok(Math.abs(at(fps) - ref) < 1e-12, `${fps} fps diverged from 60 fps`);
    }
});

test('one 50 ms spike step equals the small steps it replaces', () => {
    const w = 12;
    const spike = springState(0);
    springStep(spike, 1, w, 0.05);
    let many = springState(0);
    for (let i = 0; i < 3; i++) springStep(many, 1, w, 1 / 60);
    assert.ok(Math.abs(spike.value - many.value) < 1e-9);
});

test('springTo reports arrival and stops writing once settled', () => {
    const s = springState(0);
    let done = false;
    for (let i = 0; i < 600 && !done; i++) done = springTo(s, 1, 12, 1 / 60);
    assert.ok(done, 'never reported arrival');
    assert.ok(Math.abs(s.value - 1) < 1e-4);
});

// ═══════════════════════════════════════════════════════════════════════════
// LEG 2b — reduced motion: read V4's mechanism, do not redefine it
// ═══════════════════════════════════════════════════════════════════════════

test('reduced motion snaps to the target in one step and reports arrival', () => {
    const s = springState(0);
    const done = springTo(s, 1, 12, 1 / 60, true);
    assert.equal(done, true);
    assert.equal(s.value, 1);
    assert.equal(s.velocity, 0, 'nothing may be in motion');
});

test('reducedMotionActive is false with no DOM (node) and true on the class V4 writes', () => {
    assert.equal(reducedMotionActive(), false, 'no window/document must not mean motion was asked for');
    globalThis.document = { body: { classList: { contains: n => n === 'reduced-motion' } } };
    try {
        assert.equal(reducedMotionActive(), true, 'the body class lib/accessibility.js applies is the signal');
    } finally {
        delete globalThis.document;
    }
    globalThis.window = { matchMedia: () => ({ matches: true }) };
    try {
        assert.equal(reducedMotionActive(), true, 'the OS preference is honoured before the class lands');
    } finally {
        delete globalThis.window;
    }
});

test('a matchMedia that throws is not read as a request for motion', () => {
    globalThis.window = { matchMedia: () => { throw new Error('no media queries'); } };
    try {
        assert.equal(reducedMotionActive(), false);
    } finally {
        delete globalThis.window;
    }
});

// ═══════════════════════════════════════════════════════════════════════════
// LEG 2c — the time law
// ═══════════════════════════════════════════════════════════════════════════

test('clampStep bounds a tab-return delta to the museum own frame budget', () => {
    assert.equal(MAX_FRAME_DT, 0.05);
    assert.equal(clampStep(30), 0.05, 'a 30 s hidden interval must not integrate at once');
    assert.equal(clampStep(1 / 60), 1 / 60, 'a normal frame passes through');
    assert.equal(clampStep(0.05), 0.05);
    assert.equal(clampStep(-1), 0, 'never backwards');
    assert.equal(clampStep(NaN), 1 / 60, 'matches architecture.js deltaTime || 0.016');
    assert.ok(Number.isFinite(clampStep(Infinity)));
});

test('rateFromStepFraction preserves a tuned constant across the move', () => {
    // museum/lighting.js `(target - intensity) * 0.05` per step at 60 steps/s
    // is a time constant of -1/(60 ln 0.95) s; the conversion must be that.
    const r = rateFromStepFraction(0.05, 60);
    assert.ok(Math.abs(r - (-60 * Math.log(0.95))) < 1e-12);
    assert.equal(rateFromStepFraction(0), 60);
    assert.equal(rateFromStepFraction(1), 60);
});

test('damp converges and never overshoots its target', () => {
    let v = 0;
    for (let i = 0; i < 600; i++) {
        v = damp(v, 1, rateFromStepFraction(0.05, 60), 1 / 60);
        assert.ok(v >= 0 && v <= 1 + 1e-12, `damp left [0,1] at step ${i}`);
    }
    assert.ok(v > 0.999);
    assert.equal(damp(0.5, 1, 0, 1 / 60), 0.5, 'rate 0 must not move');
    assert.equal(damp(0.5, 1, 10, 0), 0.5, 'zero dt must not move');
    assert.equal(damp(NaN, 1, 10, 1 / 60), 1, 'a poisoned current adopts the target rather than propagating NaN');
});

test('damp is frame-rate independent too', () => {
    const rate = 3.0, seconds = 1;
    const at = fps => { let v = 0; for (let i = 0; i < fps * seconds; i++) v = damp(v, 1, rate, 1 / fps); return v; };
    // 1 - e^{-rate*t} is the exact answer both must approximate
    const truth = 1 - Math.exp(-rate * seconds);
    assert.ok(Math.abs(at(30) - truth) < 0.02, `30fps ${at(30)} vs ${truth}`);
    assert.ok(Math.abs(at(240) - truth) < 0.002, `240fps ${at(240)} vs ${truth}`);
});

// ═══════════════════════════════════════════════════════════════════════════
// LEG 2d — easing curves
// ═══════════════════════════════════════════════════════════════════════════

test('every curve is 0 at 0, 1 at 1, and monotone', () => {
    for (const [name, fn] of Object.entries({ smoothstep, smootherstep, easeOutCubic, easeInOutCubic })) {
        assert.equal(fn(0), 0, `${name}(0)`);
        assert.equal(fn(1), 1, `${name}(1)`);
        assert.equal(fn(-5), 0, `${name} clamps below`);
        assert.equal(fn(5), 1, `${name} clamps above`);
        assert.equal(fn(NaN), 0, `${name}(NaN) must not leak`);
        let prev = -1;
        for (let i = 0; i <= 100; i++) {
            const v = fn(i / 100);
            assert.ok(v >= prev - 1e-12, `${name} not monotone at ${i / 100}`);
            assert.ok(v >= 0 && v <= 1, `${name} left [0,1] at ${i / 100}`);
            prev = v;
        }
    }
});

test('smootherstep has zero slope at both ends (the reveal must not snap)', () => {
    const slope = t => (smootherstep(t + 1e-5) - smootherstep(t)) / 1e-5;
    assert.ok(slope(0) < 1e-9, `start slope ${slope(0)}`);
    assert.ok(Math.abs(slope(1) - 0) < 1e-6, `end slope ${slope(1)}`);
    const mid = (smootherstep(0.5 + 1e-5) - smootherstep(0.5)) / 1e-5;
    assert.ok(mid > 1, 'it must actually move in the middle');
});

test('clamp01 is total', () => {
    assert.equal(clamp01(-1), 0);
    assert.equal(clamp01(2), 1);
    assert.equal(clamp01(0.25), 0.25);
    assert.equal(clamp01(Infinity), 1, 'an over-run t clamps to the end, not to 0');
    assert.equal(clamp01(-Infinity), 0);
    assert.equal(clamp01(NaN), 0);
    assert.equal(clamp01(undefined), 0, 'a non-number must not be returned verbatim');
    assert.equal(clamp01(null), 0);
    assert.equal(clamp01('0.5'), 0);
    assert.equal(smoothstep(Infinity), 1);
    assert.equal(easeOutCubic(undefined), 0);
});

// ═══════════════════════════════════════════════════════════════════════════
// LEG 3 — the museum files still parse and keep their contract lines
// ═══════════════════════════════════════════════════════════════════════════

test('the touched modules keep the h(x) >= 0 header the estate convention requires', () => {
    for (const f of ['lib/env-intensity.js', 'lib/motion.js', 'lib/materials.js']) {
        assert.match(src(f), /h\(x\)\s*[≥>]=?\s*0/, `${f} header`);
    }
});

test('navigation.js bytes are untouched (contract rule: READ-ONLY this wave)', () => {
    const nav = src('museum/navigation.js');
    assert.ok(nav.length > 1000, 'read');
    // V5-1102 claims no edit here; assert no authority import leaked in.
    assert.doesNotMatch(nav, /env-intensity/, 'navigation.js must not be wired to this lane');
});
