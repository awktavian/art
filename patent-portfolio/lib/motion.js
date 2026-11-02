/**
 * Museum motion primitives — pure math, no THREE, no DOM at module scope.
 * ==========================================================
 *
 * Why this file exists (lane V5-ART-ENGINE-MATERIALS-1102, RSI40-1102):
 * the museum's motion is good — sinusoidal phase driven by the shared clock,
 * Fibonacci rhythms (Fibonacci in CLAUDE.md: 89/144/233/377/610/987 ms),
 * and reset-from-origin writes that cannot drift. What was missing was a
 * *time law*: every smoothing step in the museum is written as a fixed
 * fraction per step —
 *
 *   museum/lighting.js:238,240   intensity += (target - intensity) * 0.05
 *   museum/lighting.js:264       density   += (target - density)   * 0.02
 *   museum/architecture.js:1616  ring.scale.lerp(v, 0.05)
 *   museum/architecture.js:1621  rotation += (target - rotation)   * 0.02
 *
 * — and a fixed fraction per *step* is a fixed fraction of a frame, not of a
 * second. The lighting subsystem is stepped once every 6 frames with
 * `clampedDelta * 6` (main.js:2289-2292), so the number of smoothing steps
 * per second is fps/6: the same zone transition takes 4x longer on a 30 fps
 * machine than on a 120 Hz one. And a spike is not a slow frame: main.js:2191
 * clamps the delta to 50 ms for exactly that reason, while the value the Fano
 * animator receives (main.js:2305) is the raw one.
 *
 * So: `damp()` below is frame-rate independent by construction (the closed
 * form of "fraction f at 60 Hz" is recovered with `rate = -60*ln(1-f)`), and
 * `springTo()` is critically damped — the shape that reaches a target without
 * overshooting it, which is what a hover response and a settle want.
 *
 * Reduced motion is first-class here, not bolted on: lane V4 (FIFTY-1102)
 * wired the setting into the render loop (main.js:2207 `const still = ...`)
 * and its D3 contract is that the canvas answers too. `reducedMotionActive()`
 * reads the SAME mechanism V4's manager writes — the `reduced-motion` class
 * lib/accessibility.js:658-662 applies from `settings.reducedMotion`, which
 * itself is seeded from `prefers-reduced-motion` and live-listened (D2) — so
 * a component that never touches the manager still honours the visitor,
 * whether the setting came from the OS or from the museum's own toggle.
 * Nothing in this file redefines that setting; it only reads its output.
 *
 * h(x) >= 0 always
 */

/** The museum's own frame budget: main.js:2191 `Math.min(delta, 0.05)`. */
export const MAX_FRAME_DT = 0.05;

/**
 * Clamp an integration step to the museum's frame budget.
 * A backgrounded tab hands THREE.Clock the whole hidden interval, so an
 * accumulating transform would integrate it in one go. Returns `dt` unchanged
 * when it is already sane; non-finite input becomes one 60 Hz frame, matching
 * architecture.js:1745's `deltaTime || 0.016` default.
 */
export function clampStep(dt, max = MAX_FRAME_DT) {
    if (!Number.isFinite(dt)) return 1 / 60;
    if (dt <= 0) return 0;
    return dt > max ? max : dt;
}

/**
 * Frame-rate independent exponential smoothing, in seconds.
 *
 * @param {number} current
 * @param {number} target
 * @param {number} rate    1/time-constant. Bigger settles faster.
 * @param {number} dt      seconds since the last step (already clamped)
 * @returns {number}
 */
export function damp(current, target, rate, dt) {
    if (!Number.isFinite(current)) return target;
    if (!(rate > 0) || !(dt > 0)) return current;
    return current + (target - current) * (1 - Math.exp(-rate * dt));
}

/**
 * Convert the museum's legacy per-step fraction into a `damp()` rate so a
 * tuned constant survives the move: "0.05 per step at 60 steps/s" is the same
 * time constant as rate = -60*ln(0.95) = 3.076 s^-1.
 */
export function rateFromStepFraction(fraction, stepsPerSecond = 60) {
    if (!(fraction > 0) || fraction >= 1) return stepsPerSecond;
    return -stepsPerSecond * Math.log(1 - fraction);
}

/**
 * One step of a critically damped (zeta = 1) spring toward `target`.
 *
 * Closed form, not Euler: the critically damped solution
 *   x(t) = target - (A + B t) e^{-w t},  A = x0 - target, B = v0 + w A
 * is exact for any t, so a long frame cannot overshoot what a short one
 * undershoots, and the state never crosses the target (no ringing on a hover
 * pop). `velocity` is carried by the caller so a moving object continues to
 * move instead of losing its momentum at each retarget.
 *
 * @param {{value:number, velocity:number}} state   mutated in place (no alloc per step)
 * @param {number} target
 * @param {number} omega  natural frequency, rad/s. ~2PI/0.35 s for a brisk hover.
 * @param {number} dt     seconds
 * @returns {{value:number, velocity:number}} the same `state` object
 */
export function springStep(state, target, omega, dt) {
    if (!Number.isFinite(state.value)) {
        state.value = target;
        state.velocity = 0;
        return state;
    }
    if (!(omega > 0) || !(dt > 0)) return state;
    const A = state.value - target;          // displacement from target
    const B = state.velocity + omega * A;    // critically damped slope constant
    const e = Math.exp(-omega * dt);
    const At = A + B * dt;
    state.value = target + At * e;
    state.velocity = (B - omega * At) * e;   // d/dt[(A + Bt)e^{-wt}]
    return state;
}

/** A spring state object; allocate once at construction, never per frame. */
export function springState(value = 0) {
    return { value, velocity: 0 };
}

/**
 * Drive `state` to `target` and report whether it is done. With reduced motion
 * the spring is not run at all — the value is set to the target immediately,
 * which is V4's settle-then-hold shape: the pose is reached, nothing moves.
 */
export function springTo(state, target, omega, dt, reducedMotion = false) {
    if (reducedMotion) {
        state.value = target;
        state.velocity = 0;
        return true;
    }
    springStep(state, target, omega, dt);
    return Math.abs(state.value - target) < 1e-4 && Math.abs(state.velocity) < 1e-4;
}

// ═══════════════════════════════════════════════════════════════════════════
// EASED CURVES — the museum's own shapes, named
// ═══════════════════════════════════════════════════════════════════════════

/**
 * The smoothstep already in use at museum/lighting.js:223
 * (`t * t * (3 - 2 * t)`), lifted out so it is one definition.
 */
export function smoothstep(t) {
    const x = clamp01(t);
    return x * x * (3 - 2 * x);
}

/** Ken Perlin's smootherstep — zero first AND second derivative at both ends. */
export function smootherstep(t) {
    const x = clamp01(t);
    return x * x * x * (x * (x * 6 - 15) + 10);
}

/** Ease-out cubic: fast departure, soft arrival — the hover/reveal idiom. */
export function easeOutCubic(t) {
    const x = clamp01(t);
    const i = 1 - x;
    return 1 - i * i * i;
}

/** Ease-in-out cubic, symmetric. */
export function easeInOutCubic(t) {
    const x = clamp01(t);
    return x < 0.5 ? 4 * x * x * x : 1 - Math.pow(-2 * x + 2, 3) / 2;
}

export function clamp01(t) {
    // NaN is the only number that is not ordered, so it is the only number
    // that collapses to 0. +/-Infinity ARE ordered: an over-run t must clamp
    // to 1, not be mistaken for "no progress". Anything that is not a number
    // at all (undefined, a string, null) collapses to 0 rather than falling
    // through both comparisons and being returned verbatim.
    if (typeof t !== 'number' || Number.isNaN(t)) return 0;
    if (t >= 1) return 1;
    if (t <= 0) return 0;
    return t;
}

// ═══════════════════════════════════════════════════════════════════════════
// REDUCED MOTION — read V4's mechanism, do not redefine it
// ═══════════════════════════════════════════════════════════════════════════

/**
 * True when the visitor has asked for stillness, by either route:
 *  - the museum's setting (lib/accessibility.js writes the `reduced-motion`
 *    class from `settings.reducedMotion` at :658-662 — this is the SAME signal
 *    main.js:2207 reads for the render loop), or
 *  - the OS preference, when the DOM is not there yet (a component built
 *    before the manager has applied its settings).
 * Safe off-browser: returns false when there is no window/document.
 */
export function reducedMotionActive() {
    if (typeof document !== 'undefined' && document.body) {
        if (document.body.classList && document.body.classList.contains('reduced-motion')) {
            return true;
        }
    }
    if (typeof window !== 'undefined' && typeof window.matchMedia === 'function') {
        try {
            return window.matchMedia('(prefers-reduced-motion: reduce)').matches === true;
        } catch {
            /* a matchMedia that throws is not a request for motion */
        }
    }
    return false;
}
