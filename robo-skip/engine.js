/**
 * Robo-Skip Engine
 * ================
 * Game theory + physics for curling strategy analysis.
 * 
 * Components:
 *   1. WinProbability  — Markov chain, pre-computed lookup
 *   2. Physics         — 2D stone dynamics, curl, collisions
 *   3. PositionEval    — Multi-factor scoring
 *   4. ShotGenerator   — Candidate shot enumeration
 *   5. ShotEvaluator   — Monte Carlo with progressive refinement
 *
 * All distances in meters. Origin = button (center of house).
 * +y = toward hog line (delivery direction). +x = right.
 */

'use strict';

// ═══════════════════════════════════════════════════════════════════════════
// CONSTANTS
// ═══════════════════════════════════════════════════════════════════════════

const CurlingConst = Object.freeze({
    // Stone
    STONE_MASS: 19.1,           // kg
    STONE_RADIUS: 0.145,        // m (diameter ~11.25 in)
    
    // Sheet geometry (meters) — origin at button
    SHEET_WIDTH: 4.572,         // 15 ft
    HOUSE_RADIUS_12: 1.829,     // 6 ft radius (12-ft ring)
    HOUSE_RADIUS_8: 1.219,      // 4 ft radius (8-ft ring)
    HOUSE_RADIUS_4: 0.610,      // 2 ft radius (4-ft ring)
    BUTTON_RADIUS: 0.152,       // ~6 in
    HOG_TO_TEE: 6.401,          // 21 ft
    TEE_TO_BACK: 1.829,         // 6 ft
    BACK_LINE_Y: -1.829,        // behind button
    HOG_LINE_Y: 6.401,          // in front of button
    
    // Physics — calibrated to measured competitive ice (Lozowski et al.)
    MU_FRICTION: 0.012,         // kinematic friction on pebbled ice (measured range 0.006-0.016)
    GRAVITY: 9.81,              // m/s²
    COR: 0.70,                  // coefficient of restitution (granite)
    CURL_K: 0.0032,             // curl strength factor
    OMEGA_DEFAULT: 1.5,         // rad/s typical rotation
    VELOCITY_THRESHOLD: 0.003,  // m/s — below this, stone stops
    
    // Simulation
    SIM_DT: 1 / 240,           // 240 Hz integration
    SIM_MAX_TIME: 12,           // max seconds per simulation
    
    // Monte Carlo
    MC_QUICK_N: 100,            // preview simulations (quick feedback)
    MC_FULL_N: 400,             // full evaluation simulations (more stable convergence)
    NOISE_SPEED_SIGMA: 0.035,   // 3.5% of speed (elite-level execution noise)
    NOISE_ANGLE_SIGMA: 0.008,   // ~0.46 degrees (elite aim noise)
    
    // Game
    ENDS_TOTAL: 10,
    STONES_PER_TEAM: 8,
    FGZ_STONE_COUNT: 5,         // 5-rock free guard zone rule
});

// ═══════════════════════════════════════════════════════════════════════════
// UTILITY
// ═══════════════════════════════════════════════════════════════════════════

function dist(x1, y1, x2, y2) {
    const dx = x2 - x1, dy = y2 - y1;
    return Math.sqrt(dx * dx + dy * dy);
}

function distToButton(x, y) {
    return Math.sqrt(x * x + y * y);
}

function clamp(v, lo, hi) {
    return v < lo ? lo : v > hi ? hi : v;
}

/** Box-Muller transform for Gaussian random */
function gaussRandom(mean, sigma) {
    let u1, u2;
    do { u1 = Math.random(); } while (u1 === 0);
    u2 = Math.random();
    return mean + sigma * Math.sqrt(-2 * Math.log(u1)) * Math.cos(2 * Math.PI * u2);
}

function metersToFeet(m) {
    return m * 3.28084;
}

function feetInchesStr(m) {
    const totalInches = m * 39.3701;
    let ft = Math.floor(totalInches / 12);
    let inches = Math.round(totalInches % 12);
    if (inches === 12) { ft++; inches = 0; }
    if (ft === 0) return `${inches}"`;
    if (inches === 0) return `${ft}'`;
    return `${ft}'${inches}"`;
}

// ═══════════════════════════════════════════════════════════════════════════
// 1. WIN PROBABILITY MODEL — Markov Chain
// ═══════════════════════════════════════════════════════════════════════════

const WinProbability = (() => {
    // Scoring distributions — initialized from Fry et al. model,
    // then updated with live data from Curling IO API via data.js
    let DIST_HAMMER, DIST_NO_HAMMER;
    const MAX_DIFF = 8;
    const MAX_ENDS = CurlingConst.ENDS_TOTAL;
    const EXTRA_END_HAMMER_WP = 0.60;

    // 3D lookup: wp[diff+MAX_DIFF][ends][hammer]
    let wp = new Array(MAX_DIFF * 2 + 1);

    /** Initialize with Fry et al. (2024) constrained geometric model */
    function initDefaultDistributions() {
        // Model parameters calibrated to WCF competitive data (men's + women's):
        //   pWin  = 0.26  — P(non-hammer team scores in an end) [steal rate ~26%]
        //   beta  = 1.00  — hammer advantage (log-odds shift)
        //   mu    = 1.85  — mean score in a scoring end
        //
        // Produces: P(hammer scores)≈49%, P(blank)≈25%, P(steal)≈26%
        // P(Z = n) = theta^n / Sum(theta^k, k=1..8) — constrained geometric
        // P_hammer = e^beta * pWin / (1 - pWin + e^beta * pWin) — logistic model
        const pWin = 0.26;
        const beta = 1.00;
        const mu = 1.85;

        // Fit constrained geometric for mean mu
        let theta = 0.5;
        for (let iter = 0; iter < 100; iter++) {
            let S = 0, K = 0, dS = 0, dK = 0;
            for (let k = 1; k <= 8; k++) {
                const tk = theta ** k;
                S += tk; K += k * tk;
                dS += k * theta ** (k - 1);
                dK += k * k * theta ** (k - 1);
            }
            const f = K / S - mu;
            const df = (dK * S - K * dS) / (S * S);
            if (Math.abs(df) < 1e-15) break;
            theta -= f / df;
            theta = Math.max(0.001, Math.min(0.999, theta));
            if (Math.abs(f) < 1e-12) break;
        }

        let S = 0;
        for (let k = 1; k <= 8; k++) S += theta ** k;
        const scoringDist = new Map();
        for (let k = 1; k <= 8; k++) scoringDist.set(k, theta ** k / S);

        // Logistic hammer advantage
        const pHammerWins = (Math.exp(beta) * pWin) / (1 - pWin + Math.exp(beta) * pWin);
        const pSteal = pWin;
        const pBlank = Math.max(0, 1 - pHammerWins - pSteal);

        // Build P(net_score = k | has_hammer)
        DIST_HAMMER = new Map();
        DIST_HAMMER.set(0, pBlank);
        for (const [k, p] of scoringDist) {
            DIST_HAMMER.set(k, pHammerWins * p);
            DIST_HAMMER.set(-k, pSteal * p);
        }

        // P(net_score = k | no_hammer) is the mirror
        DIST_NO_HAMMER = new Map();
        for (const [k, p] of DIST_HAMMER) {
            DIST_NO_HAMMER.set(-k, p);
        }
    }

    function init() {
        if (!DIST_HAMMER) initDefaultDistributions();

        wp = new Array(MAX_DIFF * 2 + 1);
        for (let d = 0; d <= MAX_DIFF * 2; d++) {
            wp[d] = new Array(MAX_ENDS + 1);
            for (let e = 0; e <= MAX_ENDS; e++) {
                wp[d][e] = new Float64Array(2);
            }
        }

        // Base case: ends = 0
        for (let d = -MAX_DIFF; d <= MAX_DIFF; d++) {
            const idx = d + MAX_DIFF;
            if (d > 0) { wp[idx][0][0] = 1.0; wp[idx][0][1] = 1.0; }
            else if (d < 0) { wp[idx][0][0] = 0.0; wp[idx][0][1] = 0.0; }
            else { wp[idx][0][0] = 1 - EXTRA_END_HAMMER_WP; wp[idx][0][1] = EXTRA_END_HAMMER_WP; }
        }

        // Fill recursively: ends 1..MAX_ENDS
        for (let e = 1; e <= MAX_ENDS; e++) {
            for (let d = -MAX_DIFF; d <= MAX_DIFF; d++) {
                const dIdx = d + MAX_DIFF;
                for (let h = 0; h <= 1; h++) {
                    const scoreDist = h === 1 ? DIST_HAMMER : DIST_NO_HAMMER;
                    let prob = 0;

                    for (const [k, pk] of scoreDist) {
                        const newDiff = clamp(d + k, -MAX_DIFF, MAX_DIFF);
                        const newDIdx = newDiff + MAX_DIFF;

                        // Hammer transition:
                        // h=1 (we have hammer): scored (k>0) → lose hammer; blank/steal → keep
                        // h=0 (opponent has hammer): opponent scored (k<0) → we get hammer; else → they keep
                        const newH = h === 1
                            ? (k > 0 ? 0 : 1)
                            : (k < 0 ? 1 : 0);

                        prob += pk * wp[newDIdx][e - 1][newH];
                    }
                    wp[dIdx][e][h] = prob;
                }
            }
        }
    }

    init();

    return {
        get(scoreDiff, endsRemaining, hasHammer) {
            const d = clamp(Math.round(scoreDiff), -MAX_DIFF, MAX_DIFF) + MAX_DIFF;
            const e = clamp(Math.round(endsRemaining), 0, MAX_ENDS);
            return wp[d][e][hasHammer ? 1 : 0];
        },

        blankingAnalysis(scoreDiff, endsRemaining, hasHammer) {
            if (!hasHammer || endsRemaining <= 0) {
                return { blankWP: 0, score1WP: 0, shouldBlank: false, delta: 0 };
            }
            const blankWP = this.get(scoreDiff, endsRemaining - 1, true);
            const score1WP = this.get(scoreDiff + 1, endsRemaining - 1, false);
            return { blankWP, score1WP, shouldBlank: blankWP > score1WP, delta: blankWP - score1WP };
        },

        getScoringDist(hasHammer) {
            return hasHammer ? DIST_HAMMER : DIST_NO_HAMMER;
        },

        /**
         * Hot-reload distributions from live data (called by data.js pipeline).
         * Replaces distributions and rebuilds the entire WP table.
         */
        updateDistributions(newHammer, newNoHammer) {
            DIST_HAMMER = newHammer;
            DIST_NO_HAMMER = newNoHammer;
            init(); // rebuild WP table with new distributions
        },

        /** Update from a pre-built WP table (from data.js buildWPTable). */
        loadTable(table, maxDiff, maxEnds) {
            for (let d = 0; d <= maxDiff * 2; d++) {
                for (let e = 0; e <= maxEnds; e++) {
                    wp[d][e][0] = table[d][e][0];
                    wp[d][e][1] = table[d][e][1];
                }
            }
        },

        _table: wp,
        _MAX_DIFF: MAX_DIFF,
    };
})();


// ═══════════════════════════════════════════════════════════════════════════
// 2. PHYSICS ENGINE
// ═══════════════════════════════════════════════════════════════════════════

class Stone {
    constructor(x, y, team, id) {
        this.x = x;
        this.y = y;
        this.vx = 0;
        this.vy = 0;
        this.omega = 0;       // angular velocity (rad/s), positive = clockwise
        this.theta = 0;       // angular position (radians) for visual rotation
        this.team = team;     // 'red' or 'yellow'
        this.id = id;
        this.active = true;   // false = out of play
    }
    
    clone() {
        const s = new Stone(this.x, this.y, this.team, this.id);
        s.vx = this.vx;
        s.vy = this.vy;
        s.omega = this.omega;
        s.theta = this.theta;
        s.active = this.active;
        return s;
    }
    
    speed() {
        return Math.sqrt(this.vx * this.vx + this.vy * this.vy);
    }
    
    distToButton() {
        return Math.sqrt(this.x * this.x + this.y * this.y);
    }
    
    isInHouse() {
        return this.distToButton() <= CurlingConst.HOUSE_RADIUS_12 + CurlingConst.STONE_RADIUS;
    }
    
    isInPlay() {
        return this.active &&
            Math.abs(this.x) <= CurlingConst.SHEET_WIDTH / 2 + CurlingConst.STONE_RADIUS &&
            this.y >= CurlingConst.BACK_LINE_Y - CurlingConst.STONE_RADIUS &&
            this.y <= CurlingConst.HOG_LINE_Y + 3; // some buffer past hog
    }
    
    isMoving() {
        return this.speed() > CurlingConst.VELOCITY_THRESHOLD;
    }
}

const Physics = {
    /**
     * Run a full physics simulation until all stones stop.
     * Mutates the stones array in place.
     * @param {Stone[]} stones - All stones on the sheet
     * @param {Object} [opts] - { onStep: fn, recordTrajectory: bool }
     * @returns {{ stones: Stone[], trajectories: Map, collisions: Array }}
     */
    simulate(stones, opts = {}) {
        const dt = CurlingConst.SIM_DT;
        const maxSteps = CurlingConst.SIM_MAX_TIME / dt;
        const R = CurlingConst.STONE_RADIUS;
        const mu = CurlingConst.MU_FRICTION;
        const g = CurlingConst.GRAVITY;
        const curlK = CurlingConst.CURL_K;
        const cor = CurlingConst.COR;
        const vThresh = CurlingConst.VELOCITY_THRESHOLD;
        const halfW = CurlingConst.SHEET_WIDTH / 2;
        const backY = CurlingConst.BACK_LINE_Y - R;
        
        const trajectories = new Map();
        const collisions = [];
        
        if (opts.recordTrajectory) {
            for (const s of stones) {
                if (s.active) trajectories.set(s.id, [{ x: s.x, y: s.y, t: 0 }]);
            }
        }
        
        let step = 0;
        while (step < maxSteps) {
            step++;
            const t = step * dt;
            let anyMoving = false;
            
            // Update velocities and positions
            for (const s of stones) {
                if (!s.active || !s.isMoving()) {
                    if (s.active && s.speed() > 0) {
                        s.vx = 0; s.vy = 0; s.omega = 0;
                    }
                    continue;
                }
                anyMoving = true;
                
                const speed = s.speed();
                if (speed < 0.0001 || !isFinite(speed)) { s.vx = 0; s.vy = 0; s.omega = 0; continue; }
                const ux = s.vx / speed;
                const uy = s.vy / speed;
                
                // Friction deceleration (along velocity direction)
                const frictionDecel = mu * g;
                const speedFactor = 1 + 0.8 / (1 + speed * 8);
                const aFriction = frictionDecel * speedFactor;
                
                // Apply sweeping friction reduction if active
                const sweepFactor = (opts.sweepZone && opts.sweepZone(s)) ? 0.70 : 1.0;
                const effectiveFriction = aFriction * sweepFactor;
                
                // Curl: lateral acceleration perpendicular to velocity
                const curlSign = s.omega > 0 ? 1 : -1;
                const aCurlMag = curlK * Math.abs(s.omega) / Math.max(speed, 0.1);
                
                const perpX = -uy * curlSign;
                const perpY = ux * curlSign;
                
                // Apply accelerations (semi-implicit Euler)
                s.vx += (-ux * effectiveFriction + perpX * aCurlMag) * dt;
                s.vy += (-uy * effectiveFriction + perpY * aCurlMag) * dt;
                
                // NaN safety
                if (!isFinite(s.vx) || !isFinite(s.vy)) { s.vx = 0; s.vy = 0; s.omega = 0; continue; }
                
                // Clamp to zero if deceleration overshoots
                const newSpeed = s.speed();
                if (newSpeed < vThresh || (s.vx * ux + s.vy * uy) < 0) {
                    s.vx = 0; s.vy = 0; s.omega = 0;
                    continue;
                }
                
                // Angular velocity decays
                s.omega *= (1 - 0.02 * dt);
                
                // Integrate angular position for visual rotation
                s.theta += s.omega * dt;
                
                // Update position
                s.x += s.vx * dt;
                s.y += s.vy * dt;
                
                // Record trajectory
                if (opts.recordTrajectory && step % 12 === 0) {
                    const traj = trajectories.get(s.id);
                    if (traj) traj.push({ x: s.x, y: s.y, t, theta: s.theta });
                }
            }
            
            // Collision detection and resolution (iterative for multi-stone pileups)
            const active = stones.filter(s => s.active);
            for (let pass = 0; pass < 3; pass++) {
                for (let i = 0; i < active.length; i++) {
                    for (let j = i + 1; j < active.length; j++) {
                        const a = active[i], b = active[j];
                        const dx = b.x - a.x;
                        const dy = b.y - a.y;
                        const d2 = dx * dx + dy * dy;
                        const minDist = 2 * R;
                        
                        if (d2 < minDist * minDist && d2 > 0.00000001) {
                            const d = Math.sqrt(d2);
                            const nx = dx / d, ny = dy / d;
                            
                            // Separate overlapping stones FIRST (every pass)
                            const overlap = minDist - d;
                            if (overlap > 0) {
                                const sep = overlap * 0.5 + 0.0002;
                                a.x -= nx * sep;
                                a.y -= ny * sep;
                                b.x += nx * sep;
                                b.y += ny * sep;
                            }
                            
                            // Only resolve impulse on first pass
                            if (pass === 0) {
                                const dvx = a.vx - b.vx;
                                const dvy = a.vy - b.vy;
                                const dvn = dvx * nx + dvy * ny;
                                
                                if (dvn > 0) {
                                    const imp = dvn * (1 + cor) / 2;
                                    
                                    a.vx -= imp * nx;
                                    a.vy -= imp * ny;
                                    b.vx += imp * nx;
                                    b.vy += imp * ny;
                                    
                                    // Transfer some angular momentum
                                    const tangent = dvx * (-ny) + dvy * nx;
                                    a.omega += tangent * 0.1;
                                    b.omega -= tangent * 0.1;
                                    
                                    collisions.push({
                                        x: (a.x + b.x) / 2,
                                        y: (a.y + b.y) / 2,
                                        t,
                                        stoneA: a.id,
                                        stoneB: b.id,
                                        force: dvn,
                                    });
                                }
                            }
                        }
                    }
                }
            }
            
            // Out-of-bounds check AFTER collision separation
            for (const s of stones) {
                if (!s.active) continue;
                if (!isFinite(s.x) || !isFinite(s.y)) { s.active = false; s.vx = 0; s.vy = 0; continue; }
                if (Math.abs(s.x) > halfW + R + 0.5 || s.y < backY - 1.0 || s.y > CurlingConst.HOG_LINE_Y + 5) {
                    s.active = false;
                    s.vx = 0; s.vy = 0;
                }
            }
            
            if (!anyMoving) break;
            if (opts.onStep) opts.onStep(stones, t, step);
        }
        
        // Final out-of-play check
        for (const s of stones) {
            if (s.active && !s.isInPlay()) {
                s.active = false;
            }
        }
        
        // Record final positions
        if (opts.recordTrajectory) {
            for (const s of stones) {
                const traj = trajectories.get(s.id);
                if (traj && s.active) {
                    traj.push({ x: s.x, y: s.y, t: step * dt });
                }
            }
        }
        
        return { stones, trajectories, collisions };
    },
    
    /**
     * Advance physics by N sub-steps. Mutates stones in place.
     * Returns { anyMoving, collisions[] } for this batch of steps.
     * sweepZone: (stone) => bool, checked every sub-step.
     */
    stepN(stones, nSteps, opts = {}) {
        const dt = CurlingConst.SIM_DT;
        const R = CurlingConst.STONE_RADIUS;
        const mu = CurlingConst.MU_FRICTION;
        const g = CurlingConst.GRAVITY;
        const curlK = CurlingConst.CURL_K;
        const cor = CurlingConst.COR;
        const vThresh = CurlingConst.VELOCITY_THRESHOLD;
        const halfW = CurlingConst.SHEET_WIDTH / 2;
        const backY = CurlingConst.BACK_LINE_Y - R;
        const collisions = [];
        let anyMoving = false;
        
        for (let step = 0; step < nSteps; step++) {
            let moving = false;
            for (const s of stones) {
                if (!s.active || !s.isMoving()) {
                    if (s.active && s.speed() > 0) { s.vx = 0; s.vy = 0; s.omega = 0; }
                    continue;
                }
                moving = true;
                const speed = s.speed();
                if (speed < 0.0001 || !isFinite(speed)) { s.vx = 0; s.vy = 0; s.omega = 0; continue; }
                const ux = s.vx / speed, uy = s.vy / speed;
                const af = mu * g * (1 + 0.8 / (1 + speed * 8));
                const sf = (opts.sweepZone && opts.sweepZone(s)) ? 0.70 : 1.0;
                const ef = af * sf;
                const cs = s.omega > 0 ? 1 : -1;
                const ac = curlK * Math.abs(s.omega) / Math.max(speed, 0.1);
                s.vx += (-ux * ef + (-uy * cs) * ac) * dt;
                s.vy += (-uy * ef + (ux * cs) * ac) * dt;
                if (!isFinite(s.vx) || !isFinite(s.vy)) { s.vx = 0; s.vy = 0; s.omega = 0; continue; }
                const ns = s.speed();
                if (ns < vThresh || (s.vx * ux + s.vy * uy) < 0) { s.vx = 0; s.vy = 0; s.omega = 0; continue; }
                s.omega *= (1 - 0.02 * dt);
                s.theta += s.omega * dt;
                s.x += s.vx * dt; s.y += s.vy * dt;
            }
            // Collision detection (iterative for multi-stone pileups)
            const active = stones.filter(s => s.active);
            for (let pass = 0; pass < 3; pass++) {
                for (let i = 0; i < active.length; i++) {
                    for (let j = i + 1; j < active.length; j++) {
                        const a = active[i], b = active[j];
                        const dx = b.x - a.x, dy = b.y - a.y;
                        const d2 = dx * dx + dy * dy;
                        const minDist = 2 * R;
                        if (d2 < minDist * minDist && d2 > 0.00000001) {
                            const d = Math.sqrt(d2);
                            const nx = dx / d, ny = dy / d;
                            // Separate FIRST
                            const ol = minDist - d;
                            if (ol > 0) {
                                const sep = ol * 0.5 + 0.0002;
                                a.x -= nx * sep; a.y -= ny * sep;
                                b.x += nx * sep; b.y += ny * sep;
                            }
                            // Impulse on first pass only
                            if (pass === 0) {
                                const dvx = a.vx - b.vx, dvy = a.vy - b.vy;
                                const dvn = dvx * nx + dvy * ny;
                                if (dvn > 0) {
                                    const imp = dvn * (1 + cor) / 2;
                                    a.vx -= imp * nx; a.vy -= imp * ny;
                                    b.vx += imp * nx; b.vy += imp * ny;
                                    const tangent = dvx * (-ny) + dvy * nx;
                                    a.omega += tangent * 0.1; b.omega -= tangent * 0.1;
                                    collisions.push({ x: (a.x + b.x) / 2, y: (a.y + b.y) / 2, stoneA: a.id, stoneB: b.id, force: dvn });
                                }
                            }
                        }
                    }
                }
            }
            // OOB check AFTER collision separation
            for (const s of stones) {
                if (!s.active) continue;
                if (!isFinite(s.x) || !isFinite(s.y)) { s.active = false; s.vx = 0; s.vy = 0; continue; }
                if (Math.abs(s.x) > halfW + R + 0.5 || s.y < backY - 1.0 || s.y > CurlingConst.HOG_LINE_Y + 5) {
                    s.active = false; s.vx = 0; s.vy = 0;
                }
            }
            anyMoving = anyMoving || moving;
        }
        // Out of play check
        for (const s of stones) {
            if (s.active && !s.isInPlay()) s.active = false;
        }
        return { anyMoving, collisions };
    },
    
    /**
     * Create a delivery shot: stone enters from hog line toward the house.
     * @param {Object} params - { targetX, targetY, speed, curl, team, id }
     * @returns {Stone}
     */
    createDelivery(params) {
        const {
            targetX = 0, targetY = 0,
            speed = 2.5,
            curl = 1,  // 1 = clockwise (curls right), -1 = counter-clockwise (curls left)
            team = 'red',
            id = 'delivery'
        } = params;
        
        // Start from above the hog line
        const startY = CurlingConst.HOG_LINE_Y + 2;
        
        // Aim: account for curl by offsetting initial angle
        const dx = targetX - 0; // start centered
        const dy = targetY - startY;
        const targetDist = Math.sqrt(dx * dx + dy * dy);
        
        // Estimate curl displacement and pre-compensate aim
        // CW (curl=1) curls RIGHT → aim LEFT to compensate (negative offset)
        const travelTime = targetDist / speed;
        const curlDisplacement = CurlingConst.CURL_K * Math.abs(CurlingConst.OMEGA_DEFAULT) * travelTime * travelTime * 0.3;
        const curlCompensation = curl > 0 ? -curlDisplacement : curlDisplacement;
        
        const aimX = targetX + curlCompensation;
        const angle = Math.atan2(dy, aimX);
        
        const stone = new Stone(0, startY, team, id);
        stone.vx = Math.cos(angle) * speed;
        stone.vy = Math.sin(angle) * speed; // negative = toward button
        stone.omega = curl * CurlingConst.OMEGA_DEFAULT;
        
        return stone;
    },
    
    /**
     * Check for FGZ (Free Guard Zone) violations.
     * In the first 5 stones of an end, you cannot remove opponent guards
     * that are between the hog line and the house.
     * @param {Stone[]} beforeStones - Stone positions before the shot
     * @param {Stone[]} afterStones - Stone positions after the shot
     * @param {number} turnNumber - Current turn number (0-15)
     * @param {string} deliveryTeam - Team that threw the delivery
     * @returns {{ violation: boolean, restoredStones: Stone[] | null, message: string }}
     */
    checkFGZ(beforeStones, afterStones, turnNumber, deliveryTeam) {
        // FGZ only applies during first 5 stones
        if (turnNumber >= CurlingConst.FGZ_STONE_COUNT) {
            return { violation: false, restoredStones: null, message: '' };
        }
        
        const opponentTeam = deliveryTeam === 'red' ? 'yellow' : 'red';
        
        // Find opponent stones that were in the FGZ before the shot
        const fgzStonesBefore = beforeStones.filter(s =>
            s.active && s.team === opponentTeam &&
            s.y > 0 && s.y < CurlingConst.HOG_LINE_Y &&
            s.distToButton() > CurlingConst.HOUSE_RADIUS_12 + CurlingConst.STONE_RADIUS
        );
        
        // Check if any of those FGZ stones were removed
        for (const before of fgzStonesBefore) {
            const after = afterStones.find(s => s.id === before.id);
            if (!after || !after.active || !after.isInPlay()) {
                // FGZ stone was removed — violation!
                return {
                    violation: true,
                    restoredStones: fgzStonesBefore,
                    message: `FGZ violation: cannot remove opponent guard in first ${CurlingConst.FGZ_STONE_COUNT} stones`
                };
            }
        }
        
        return { violation: false, restoredStones: null, message: '' };
    }
};


// ═══════════════════════════════════════════════════════════════════════════
// 3. POSITION EVALUATION
// ═══════════════════════════════════════════════════════════════════════════

const PositionEval = {
    /**
     * Count stones and determine who's scoring.
     * @param {Stone[]} stones - Active stones on sheet
     * @returns {{ team: string|null, count: number, distances: Array }}
     */
    countingStones(stones) {
        const active = stones.filter(s => s.active && s.isInHouse());
        if (active.length === 0) return { team: null, count: 0, distances: [] };
        
        // Sort by distance to button
        const sorted = active.map(s => ({
            stone: s,
            dist: s.distToButton(),
        })).sort((a, b) => a.dist - b.dist);
        
        const closestTeam = sorted[0].stone.team;
        let count = 0;
        
        for (const entry of sorted) {
            if (entry.stone.team === closestTeam) {
                count++;
            } else {
                break; // opponent stone is closer than remaining
            }
        }
        
        return {
            team: closestTeam,
            count,
            distances: sorted.map(e => ({
                team: e.stone.team,
                id: e.stone.id,
                dist: e.dist,
                distStr: feetInchesStr(e.dist),
                counting: e.stone.team === closestTeam && sorted.indexOf(e) < count,
            })),
        };
    },
    
    /**
     * Evaluate a position for a team.
     * Higher = better for that team. Range roughly [-60, +60].
     */
    evaluate(stones, team) {
        const active = stones.filter(s => s.active);
        const counting = this.countingStones(active);
        
        let score = 0;
        
        // 1. Counting stones
        if (counting.team === team) {
            score += counting.count * 10;
        } else if (counting.team !== null) {
            score -= counting.count * 10;
        }
        
        // 2. Button control
        const onButton = active.find(s => s.team === team && s.distToButton() < CurlingConst.BUTTON_RADIUS + CurlingConst.STONE_RADIUS);
        if (onButton) score += 8;
        
        // 3. Guards and protection
        const ourStones = active.filter(s => s.team === team);
        const theirStones = active.filter(s => s.team !== team);
        const houseStones = ourStones.filter(s => s.isInHouse());
        
        for (const hs of houseStones) {
            // Check if there's a guard in front (between hog and this stone, roughly on the same line)
            const hasGuard = ourStones.some(gs => {
                if (gs === hs) return false;
                if (gs.y <= hs.y) return false; // guard must be in front (higher y)
                if (!this._isInFGZ(gs)) return false; // must be in free guard zone area
                // Check if guard is roughly on line between button and house stone
                const dx = Math.abs(gs.x - hs.x);
                return dx < CurlingConst.STONE_RADIUS * 4; // within ~4 stone widths
            });
            
            if (hasGuard) {
                score += 5; // guard premium
            } else {
                // Check if exposed (no guard, opponents can take it out)
                const exposed = theirStones.length > 0; // simplified: if opponents exist, it's exposed
                if (exposed) score -= 3;
            }
        }
        
        // 4. Freeze bonus
        for (const os of ourStones) {
            const frozen = theirStones.some(ts => {
                const d = dist(os.x, os.y, ts.x, ts.y);
                return d < CurlingConst.STONE_RADIUS * 2.3; // just touching
            });
            if (frozen && os.isInHouse()) score += 4;
        }
        
        // 5. FGZ guards (protected early in end)
        const fgzGuards = ourStones.filter(s => this._isInFGZ(s));
        score += fgzGuards.length * 2;
        
        // 6. Back of house coverage
        const backStones = ourStones.filter(s => s.isInHouse() && s.y < 0);
        score += backStones.length * 1.5;
        
        // 7. Opponent threats
        for (const ts of theirStones) {
            if (ts.isInHouse()) {
                // Opponent stone in the house is a threat
                if (ts.distToButton() < CurlingConst.HOUSE_RADIUS_4) {
                    score -= 4; // close to button = big threat
                } else if (ts.distToButton() < CurlingConst.HOUSE_RADIUS_8) {
                    score -= 2;
                }
            }
        }
        
        return score;
    },
    
    /**
     * Convert position evaluation to expected scoring.
     * Returns expected score for the team (positive = they score, negative = steal).
     */
    expectedScore(stones, team, hasHammer) {
        const evalScore = this.evaluate(stones, team);
        const normalized = Math.tanh(evalScore / 30); // sigmoid-ish mapping to [-1, 1]
        
        if (hasHammer) {
            // With hammer, positive eval → score 2-3, negative → forced or steal
            return 1.5 + normalized * 1.5; // range [0, 3]
        } else {
            // Without hammer, we're typically getting stolen from or forcing
            return normalized * 1.5; // range [-1.5, 1.5]
        }
    },
    
    /**
     * Get detailed strategic breakdown.
     */
    getStrategicFactors(stones, team) {
        const active = stones.filter(s => s.active);
        const counting = this.countingStones(active);
        const ourStones = active.filter(s => s.team === team);
        const theirStones = active.filter(s => s.team !== team);
        
        return {
            counting: counting.team === team ? counting.count : 0,
            opponentCounting: counting.team !== team && counting.team !== null ? counting.count : 0,
            ourInHouse: ourStones.filter(s => s.isInHouse()).length,
            theirInHouse: theirStones.filter(s => s.isInHouse()).length,
            ourGuards: ourStones.filter(s => this._isInFGZ(s)).length,
            theirGuards: theirStones.filter(s => this._isInFGZ(s)).length,
            totalStones: active.length,
            evaluation: this.evaluate(stones, team),
        };
    },
    
    _isInFGZ(stone) {
        return stone.y > 0 && stone.y < CurlingConst.HOG_LINE_Y &&
               !stone.isInHouse() &&
               Math.abs(stone.x) < CurlingConst.SHEET_WIDTH / 2;
    }
};


// ═══════════════════════════════════════════════════════════════════════════
// 4. SHOT GENERATOR
// ═══════════════════════════════════════════════════════════════════════════

const ShotGenerator = {
    /**
     * Generate candidate shots for analysis.
     * @param {Stone[]} stones - Current position
     * @param {string} team - Team making the shot
     * @param {Object} [opts] - { turnNumber: number }
     * @returns {Array<{ type, name, params, targetX, targetY }>}
     */
    generate(stones, team, opts = {}) {
        const candidates = [];
        const active = stones.filter(s => s.active);
        const opponents = active.filter(s => s.team !== team);
        const ours = active.filter(s => s.team === team);
        const R = CurlingConst.STONE_RADIUS;
        const turnNumber = opts.turnNumber || 0;
        const fgzActive = turnNumber < CurlingConst.FGZ_STONE_COUNT;
        
        // === DRAW SHOTS ===
        // Draw to button (calibrated: μ=0.020, ~8.4m travel)
        candidates.push({
            type: 'draw', name: 'Draw to Button',
            icon: '🎯',
            targetX: 0, targetY: 0,
            speed: 1.90, curl: 1,
        });
        
        // Draw to 4-foot
        for (const side of [-1, 1]) {
            candidates.push({
                type: 'draw',
                name: `Draw to 4ft ${side > 0 ? 'R' : 'L'}`,
                icon: '🎯',
                targetX: side * 0.45, targetY: 0.15,
                speed: 1.90, curl: side,
            });
        }
        
        // Draw to 8-foot
        for (const angle of [0, Math.PI / 4, -Math.PI / 4, Math.PI / 2, -Math.PI / 2]) {
            const tx = Math.sin(angle) * CurlingConst.HOUSE_RADIUS_8 * 0.7;
            const ty = -Math.cos(angle) * CurlingConst.HOUSE_RADIUS_8 * 0.5;
            candidates.push({
                type: 'draw',
                name: `Draw to 8ft`,
                icon: '🎯',
                targetX: tx, targetY: ty,
                speed: 1.95, curl: tx > 0 ? 1 : -1,
            });
        }
        
        // Draw behind guards (come-around)
        for (const guard of active.filter(s => PositionEval._isInFGZ(s) && s.team === team)) {
            for (const side of [-1, 1]) {
                candidates.push({
                    type: 'draw',
                    name: `Come Around`,
                    icon: '↩️',
                    targetX: guard.x + side * R * 2,
                    targetY: guard.y - 1.5,
                    speed: 1.80, curl: -side,
                });
            }
        }
        
        // === GUARD SHOTS ===
        // Center guard (lighter weight — stone stops in FGZ ~3-4m from button)
        candidates.push({
            type: 'guard', name: 'Center Guard',
            icon: '🛡️',
            targetX: 0, targetY: 3.5,
            speed: 1.45, curl: 1,
        });
        candidates.push({
            type: 'guard', name: 'Center Guard (close)',
            icon: '🛡️',
            targetX: 0, targetY: 2.5,
            speed: 1.30, curl: -1,
        });
        
        // Corner guards
        for (const side of [-1, 1]) {
            candidates.push({
                type: 'guard',
                name: `Corner Guard ${side > 0 ? 'R' : 'L'}`,
                icon: '🛡️',
                targetX: side * 1.2, targetY: 3.0,
                speed: 1.50, curl: side,
            });
        }
        
        // === TAKEOUT SHOTS ===
        for (const opp of opponents) {
            // FGZ: skip takeouts on FGZ guards during first 5 stones
            if (fgzActive && PositionEval._isInFGZ(opp)) continue;
            
            // Nose hit — needs enough speed to reach target AND remove it
            // Higher speed for stones closer to hack (larger y = farther from button = less travel)
            const distFromHog = CurlingConst.HOG_LINE_Y - opp.y;
            const takeoutSpeed = 2.4 + distFromHog * 0.08; // ~2.4 for button, ~2.9 for hog
            candidates.push({
                type: 'takeout',
                name: `Takeout`,
                icon: '💥',
                targetX: opp.x, targetY: opp.y,
                speed: clamp(takeoutSpeed, 2.4, 3.5),
                curl: opp.x > 0 ? 1 : -1,
                targetStone: opp.id,
            });
            
            // Hit and roll (offset aim to roll to a good position)
            for (const rollDir of [-1, 1]) {
                const offset = rollDir * R * 1.5;
                candidates.push({
                    type: 'hit-and-roll',
                    name: `Hit & Roll`,
                    icon: '🔄',
                    targetX: opp.x + offset,
                    targetY: opp.y,
                    speed: clamp(takeoutSpeed * 0.92, 2.2, 3.2),
                    curl: rollDir,
                    targetStone: opp.id,
                });
            }
        }
        
        // === PEEL SHOTS ===
        for (const opp of opponents.filter(s => PositionEval._isInFGZ(s))) {
            // FGZ: skip peels on FGZ guards during first 5 stones
            if (fgzActive) continue;
            
            candidates.push({
                type: 'peel',
                name: `Peel Guard`,
                icon: '🧹',
                targetX: opp.x, targetY: opp.y,
                speed: 3.3,
                curl: opp.x > 0 ? 1 : -1,
                targetStone: opp.id,
            });
        }
        
        // === FREEZE SHOTS ===
        for (const opp of opponents.filter(s => s.isInHouse())) {
            candidates.push({
                type: 'freeze',
                name: `Freeze`,
                icon: '❄️',
                targetX: opp.x, targetY: opp.y + R * 2.05,
                speed: 1.75,
                curl: opp.x > 0 ? 1 : -1,
                targetStone: opp.id,
            });
        }
        
        // === RAISE SHOTS ===
        for (const own of ours.filter(s => s.isInHouse() && s.distToButton() > CurlingConst.HOUSE_RADIUS_4)) {
            candidates.push({
                type: 'raise',
                name: `Raise`,
                icon: '⬆️',
                targetX: own.x, targetY: own.y + R * 2,
                speed: 2.4,
                curl: own.x > 0 ? 1 : -1,
                targetStone: own.id,
            });
        }
        
        // === DOUBLE TAKEOUT ===
        // Look for pairs of opponent stones close together
        for (let i = 0; i < opponents.length; i++) {
            for (let j = i + 1; j < opponents.length; j++) {
                const a = opponents[i], b = opponents[j];
                if (fgzActive && (PositionEval._isInFGZ(a) || PositionEval._isInFGZ(b))) continue;
                const gap = dist(a.x, a.y, b.x, b.y);
                if (gap < R * 6) {
                    // Aim between them with enough weight
                    const midX = (a.x + b.x) / 2;
                    const midY = (a.y + b.y) / 2;
                    candidates.push({
                        type: 'double-takeout',
                        name: `Double Takeout`,
                        icon: '💥💥',
                        targetX: midX, targetY: midY,
                        speed: clamp(3.0 + midY * 0.03, 2.8, 3.5),
                        curl: midX > 0 ? 1 : -1,
                    });
                }
            }
        }
        
        // === TICK SHOT ===
        // Move opponent guard slightly off-center without removing it
        for (const opp of opponents.filter(s => PositionEval._isInFGZ(s))) {
            if (fgzActive) continue; // FGZ protects them
            for (const side of [-1, 1]) {
                candidates.push({
                    type: 'tick',
                    name: `Tick ${side > 0 ? 'R' : 'L'}`,
                    icon: '👆',
                    targetX: opp.x + side * R * 0.8,
                    targetY: opp.y,
                    speed: 2.3,
                    curl: side,
                    targetStone: opp.id,
                });
            }
        }
        
        // === RUNBACK ===
        // Hit own stone to push it into opponent behind it
        for (const own of ours) {
            for (const opp of opponents) {
                // Check if opponent is roughly behind our stone (closer to button)
                if (opp.y < own.y && dist(own.x, own.y, opp.x, opp.y) < R * 8) {
                    if (fgzActive && PositionEval._isInFGZ(opp)) continue;
                    candidates.push({
                        type: 'runback',
                        name: `Runback`,
                        icon: '🔙',
                        targetX: own.x, targetY: own.y,
                        speed: clamp(2.6 + own.y * 0.03, 2.4, 3.2),
                        curl: own.x > 0 ? 1 : -1,
                        targetStone: own.id,
                    });
                    break; // one runback per own stone
                }
            }
        }
        
        // === DRAW-SPECIFIC NAMES ===
        // Top-4 draw (draw to the 4-foot, top of house)
        candidates.push({
            type: 'draw', name: 'Top-4 Draw',
            icon: '🎯',
            targetX: 0, targetY: -CurlingConst.HOUSE_RADIUS_4 * 0.5,
            speed: 1.85, curl: 1,
        });
        
        // Corner freeze (freeze behind opponent in the corner of the 8-foot)
        for (const opp of opponents.filter(s => s.isInHouse() && Math.abs(s.x) > CurlingConst.HOUSE_RADIUS_4)) {
            candidates.push({
                type: 'freeze',
                name: `Corner Freeze`,
                icon: '❄️',
                targetX: opp.x, targetY: opp.y + R * 2.05,
                speed: 1.70,
                curl: opp.x > 0 ? 1 : -1,
                targetStone: opp.id,
            });
        }
        
        // Assign unique IDs
        candidates.forEach((c, i) => { c.id = i; });
        
        return candidates;
    }
};


// ═══════════════════════════════════════════════════════════════════════════
// 5. SHOT EVALUATOR — Monte Carlo
// ═══════════════════════════════════════════════════════════════════════════

const ShotEvaluator = {
    /**
     * Evaluate a single candidate shot with Monte Carlo.
     * @param {Stone[]} currentStones - Current position (will be cloned)
     * @param {Object} candidate - Shot candidate from ShotGenerator
     * @param {Object} gameState - { scoreDiff, endsRemaining, hammerTeam }
     * @param {string} team - Team making the shot
     * @param {number} numSims - Number of simulations
     * @returns {{ wpDelta, avgWP, successRate, results }}
     */
    evaluateShot(currentStones, candidate, gameState, team, numSims) {
        const baseWP = WinProbability.get(
            gameState.scoreDiff,
            gameState.endsRemaining,
            gameState.hammerTeam === team
        );
        
        let totalWP = 0;
        let successCount = 0;
        const wpSamples = [];
        
        for (let i = 0; i < numSims; i++) {
            // Clone stones
            const simStones = currentStones.filter(s => s.active).map(s => s.clone());
            
            // Create noisy delivery — zero-centered Gaussian perturbation
            const noisySpeed = gaussRandom(candidate.speed, candidate.speed * CurlingConst.NOISE_SPEED_SIGMA);
            // Lateral noise (perpendicular to aim line): ~3cm sigma at elite level
            const lateralNoise = gaussRandom(0, 0.030);
            // Depth noise (along aim line): ~2cm sigma
            const depthNoise = gaussRandom(0, 0.020);
            
            const delivery = Physics.createDelivery({
                targetX: candidate.targetX + lateralNoise,
                targetY: candidate.targetY + depthNoise,
                speed: Math.max(noisySpeed, 0.5),
                curl: candidate.curl,
                team: team,
                id: `delivery_${i}`,
            });
            
            simStones.push(delivery);
            
            // Run simulation twice: once without sweep, once with sweep on delivery
            // The team sweeps optimally (whichever result is better)
            const simNoSweep = simStones.map(s => s.clone());
            Physics.simulate(simNoSweep);
            
            const simSwept = simStones.map(s => s.clone());
            Physics.simulate(simSwept, { sweepZone: (s) => s.id === `delivery_${i}` });
            
            // Evaluate both and pick the better outcome for the team
            function evalPos(stones) {
                const active = stones.filter(s => s.active);
                const c = PositionEval.countingStones(active);
                if (c.team === team) return c.count;
                if (c.team === null) return 0;
                return -c.count;
            }
            const scoreNoSweep = evalPos(simNoSweep);
            const scoreSwept = evalPos(simSwept);
            const bestSim = scoreSwept >= scoreNoSweep ? simSwept : simNoSweep;
            const expectedEndScore = Math.max(scoreSwept, scoreNoSweep);
            
            // Use the best result
            const resultActive = bestSim.filter(s => s.active);
            
            // Convert to WP (expectedEndScore already computed above)
            // Hammer transition: if we score (>0), opponent gets hammer next.
            // If blank (0), hammer stays. If opponent steals (<0), we get hammer.
            const newDiff = gameState.scoreDiff + expectedEndScore;
            let hasHammerNext;
            if (expectedEndScore > 0) {
                hasHammerNext = gameState.hammerTeam !== team; // we scored → lose hammer
            } else if (expectedEndScore < 0) {
                hasHammerNext = gameState.hammerTeam === team; // opponent stole → they lose hammer, we get it
            } else {
                hasHammerNext = gameState.hammerTeam === team; // blank → hammer stays
            }
            const newWP = WinProbability.get(
                newDiff,
                Math.max(0, gameState.endsRemaining - 1),
                hasHammerNext
            );
            
            totalWP += newWP;
            wpSamples.push(newWP);
            
            // Success = shot achieved its primary goal (use bestSim which includes optimal sweep)
            const deliveredStone = bestSim.find(s => s.id === `delivery_${i}` && s.active);
            if (candidate.type === 'takeout' || candidate.type === 'peel' || candidate.type === 'hit-and-roll') {
                const targetGone = !bestSim.find(s => s.id === candidate.targetStone && s.active && s.isInHouse());
                if (targetGone) successCount++;
            } else if (candidate.type === 'double') {
                // Double takeout: both targets removed
                const t1 = candidate.targetStone;
                const t2 = candidate.targetStone2;
                const gone1 = !bestSim.find(s => s.id === t1 && s.active && s.isInHouse());
                const gone2 = !t2 || !bestSim.find(s => s.id === t2 && s.active && s.isInHouse());
                if (gone1 && gone2) successCount++;
            } else if (candidate.type === 'freeze') {
                const targetStone = bestSim.find(s => s.id === candidate.targetStone && s.active);
                if (deliveredStone && targetStone) {
                    const d = dist(deliveredStone.x, deliveredStone.y, targetStone.x, targetStone.y);
                    if (d < CurlingConst.STONE_RADIUS * 3) successCount++;
                }
            } else if (candidate.type === 'raise' || candidate.type === 'tick' || candidate.type === 'runback') {
                // Raise/tick/runback: target stone moved significantly from original position
                const targetStone = bestSim.find(s => s.id === candidate.targetStone && s.active);
                if (candidate.type === 'raise' && targetStone) {
                    // Raise success: own stone moved closer to button
                    if (targetStone.distToButton() < dist(candidate.targetX, candidate.targetY, 0, 0)) successCount++;
                } else if (candidate.type === 'tick') {
                    // Tick success: guard moved laterally
                    if (!targetStone || dist(targetStone.x, targetStone.y, candidate.targetX, candidate.targetY) > CurlingConst.STONE_RADIUS * 2) successCount++;
                } else {
                    // Runback: opponent stone behind ours removed
                    if (deliveredStone) successCount++;
                }
            } else if (candidate.type === 'draw' || candidate.type === 'guard' || candidate.type === 'come-around') {
                if (deliveredStone) {
                    const distToTarget = dist(deliveredStone.x, deliveredStone.y, candidate.targetX, candidate.targetY);
                    if (distToTarget < CurlingConst.STONE_RADIUS * 5) successCount++;
                }
            } else {
                // Manual throws and unknown types — check if delivery stayed in play
                if (deliveredStone) successCount++;
            }
        }
        
        const avgWP = totalWP / numSims;
        const wpDelta = avgWP - baseWP;
        const successRate = successCount / numSims;
        
        // Standard error
        let variance = 0;
        for (const wp of wpSamples) {
            variance += (wp - avgWP) ** 2;
        }
        variance /= numSims;
        const stdError = Math.sqrt(variance / numSims);
        
        // Record trial endpoints for visualization (delivery final positions)
        // Only record for display — keep last N trial positions
        const trialEndpoints = [];
        // Re-run a small batch to collect endpoints (if numSims was large, 
        // we already ran them but didn't record positions — so collect a fast sample)
        const vizSims = Math.min(numSims, 24);
        for (let i = 0; i < vizSims; i++) {
            const vizStones = currentStones.filter(s => s.active).map(s => s.clone());
            const latN = gaussRandom(0, 0.030);
            const depN = gaussRandom(0, 0.020);
            const nSpeed = gaussRandom(candidate.speed, candidate.speed * CurlingConst.NOISE_SPEED_SIGMA);
            const del = Physics.createDelivery({
                targetX: candidate.targetX + latN,
                targetY: candidate.targetY + depN,
                speed: Math.max(nSpeed, 0.5),
                curl: candidate.curl,
                team: team,
                id: `viz_${i}`,
            });
            vizStones.push(del);
            const { trajectories } = Physics.simulate(vizStones, { recordTrajectory: true });
            
            // Record the delivery stone's trajectory and final position
            const traj = trajectories?.get(`viz_${i}`);
            const finalDel = vizStones.find(s => s.id === `viz_${i}`);
            trialEndpoints.push({
                x: finalDel?.x ?? candidate.targetX,
                y: finalDel?.y ?? candidate.targetY,
                active: finalDel?.active ?? false,
                trajectory: traj ? traj.map(p => ({ x: p.x, y: p.y })) : [],
            });
        }
        
        return {
            candidate,
            wpDelta,
            avgWP,
            baseWP,
            successRate,
            stdError,
            numSims,
            trialEndpoints,
        };
    },
    
    /**
     * Evaluate all candidates and return ranked results.
     * @param {Stone[]} stones - Current position
     * @param {Object} gameState - { scoreDiff, endsRemaining, hammerTeam }
     * @param {string} team - Team making the shot
     * @param {number} numSims - Simulations per candidate
     * @param {Function} [onProgress] - Progress callback
     * @returns {Array} Ranked shot evaluations
     */
    evaluateAll(stones, gameState, team, numSims = CurlingConst.MC_QUICK_N, onProgress, opts = {}) {
        const candidates = ShotGenerator.generate(stones, team, { turnNumber: opts.turnNumber || 0 });
        const results = [];
        
        for (let i = 0; i < candidates.length; i++) {
            const result = this.evaluateShot(stones, candidates[i], gameState, team, numSims);
            results.push(result);
            
            if (onProgress) {
                onProgress({
                    done: i + 1,
                    total: candidates.length,
                    best: results.sort((a, b) => b.wpDelta - a.wpDelta).slice(0, 5),
                });
            }
        }
        
        // Sort by WP delta (best first)
        results.sort((a, b) => b.wpDelta - a.wpDelta);
        
        return results;
    },
};


// ═══════════════════════════════════════════════════════════════════════════
// 6. WEB WORKER FOR PARALLEL MONTE CARLO
// ═══════════════════════════════════════════════════════════════════════════

const WorkerPool = (() => {
    const WORKER_CODE = `
'use strict';

const C = {
    STONE_RADIUS: 0.145,
    SHEET_WIDTH: 4.572,
    HOUSE_RADIUS_12: 1.829,
    BUTTON_RADIUS: 0.152,
    HOG_LINE_Y: 6.401,
    BACK_LINE_Y: -1.829,
    MU_FRICTION: 0.012,
    GRAVITY: 9.81,
    COR: 0.70,
    CURL_K: 0.0032,
    OMEGA_DEFAULT: 1.5,
    VELOCITY_THRESHOLD: 0.003,
    SIM_DT: 1/240,
    SIM_MAX_TIME: 12,
    NOISE_SPEED_SIGMA: 0.035,
    NOISE_LATERAL_SIGMA: 0.030,
    NOISE_DEPTH_SIGMA: 0.020,
};

function gaussRandom(mean, sigma) {
    let u1; do { u1 = Math.random(); } while (u1 === 0);
    return mean + sigma * Math.sqrt(-2 * Math.log(u1)) * Math.cos(2 * Math.PI * Math.random());
}
function clamp(v, lo, hi) { return v < lo ? lo : v > hi ? hi : v; }
function dist(x1,y1,x2,y2) { const dx=x2-x1,dy=y2-y1; return Math.sqrt(dx*dx+dy*dy); }

function simulate(stones, sweepId) {
    const dt=C.SIM_DT, maxSteps=C.SIM_MAX_TIME/dt, R=C.STONE_RADIUS;
    const mu=C.MU_FRICTION, g=C.GRAVITY, curlK=C.CURL_K, cor=C.COR;
    const vThresh=C.VELOCITY_THRESHOLD, halfW=C.SHEET_WIDTH/2;
    
    for (let step=0; step<maxSteps; step++) {
        let anyMoving = false;
        for (const s of stones) {
            if (!s.a) continue;
            const spd = Math.sqrt(s.vx*s.vx+s.vy*s.vy);
            if (spd < vThresh || spd < 0.0001 || !isFinite(spd)) { s.vx=0; s.vy=0; s.w=0; continue; }
            anyMoving = true;
            const ux=s.vx/spd, uy=s.vy/spd;
            const af = mu*g*(1+0.8/(1+spd*8));
            const sf = (sweepId && s.id===sweepId) ? 0.70 : 1.0;
            const cs = s.w>0?1:-1;
            const ac = curlK*Math.abs(s.w)/Math.max(spd,0.1);
            s.vx += (-ux*af*sf + (-uy*cs)*ac)*dt;
            s.vy += (-uy*af*sf + (ux*cs)*ac)*dt;
            if (!isFinite(s.vx)||!isFinite(s.vy)) { s.vx=0;s.vy=0;s.w=0;continue; }
            const ns = Math.sqrt(s.vx*s.vx+s.vy*s.vy);
            if (ns<vThresh||(s.vx*ux+s.vy*uy)<0) { s.vx=0;s.vy=0;s.w=0;continue; }
            s.w *= (1-0.02*dt);
            s.x += s.vx*dt; s.y += s.vy*dt;
        }
        // Collisions (iterative — separate FIRST, then impulse)
        const act = stones.filter(s=>s.a);
        for (let pass=0;pass<3;pass++) {
            for (let i=0;i<act.length;i++) for (let j=i+1;j<act.length;j++) {
                const a=act[i],b=act[j];
                const dx=b.x-a.x,dy=b.y-a.y,d2=dx*dx+dy*dy;
                if (d2<(2*R)*(2*R)&&d2>0.00000001) {
                    const d=Math.sqrt(d2);
                    const nx=dx/d,ny=dy/d;
                    const ol=2*R-d;
                    if (ol>0) { const sep=ol*0.5+0.0002; a.x-=nx*sep;a.y-=ny*sep;b.x+=nx*sep;b.y+=ny*sep; }
                    if (pass===0) {
                        const dvn=(a.vx-b.vx)*nx+(a.vy-b.vy)*ny;
                        if (dvn>0) {
                            const imp=dvn*(1+cor)/2;
                            a.vx-=imp*nx;a.vy-=imp*ny;b.vx+=imp*nx;b.vy+=imp*ny;
                        }
                    }
                }
            }
        }
        // OOB after separation
        for (const s of stones) {
            if (!s.a) continue;
            if (!isFinite(s.x)||!isFinite(s.y)) { s.a=false;s.vx=0;s.vy=0;continue; }
            if (Math.abs(s.x)>halfW+R+0.5||s.y<C.BACK_LINE_Y-R-1.0||s.y>C.HOG_LINE_Y+5) { s.a=false;s.vx=0;s.vy=0; }
        }
        if (!anyMoving) break;
    }
}

function createDelivery(p) {
    const startY=C.HOG_LINE_Y+2;
    const dx=p.tx, dy=p.ty-startY;
    const td=Math.sqrt(dx*dx+dy*dy);
    const tt=td/p.spd;
    const cd=C.CURL_K*Math.abs(C.OMEGA_DEFAULT)*tt*tt*0.3;
    const cc=p.curl>0?-cd:cd;
    const ang=Math.atan2(dy,p.tx+cc);
    return {x:0,y:startY,vx:Math.cos(ang)*p.spd,vy:Math.sin(ang)*p.spd,w:p.curl*C.OMEGA_DEFAULT,t:p.team,id:p.id,a:true};
}

function countStones(stones) {
    const house = stones.filter(s=>s.a&&Math.sqrt(s.x*s.x+s.y*s.y)<=C.HOUSE_RADIUS_12+C.STONE_RADIUS);
    if (!house.length) return {team:null,count:0};
    house.sort((a,b)=>Math.sqrt(a.x*a.x+a.y*a.y)-Math.sqrt(b.x*b.x+b.y*b.y));
    const ct=house[0].t;
    let c=0;
    for (const s of house) { if(s.t===ct)c++; else break; }
    return {team:ct,count:c};
}

self.onmessage = function(e) {
    const { candidates, stones, gameState, team, numSims, wpTable, batchId } = e.data;
    const results = [];
    
    for (const cand of candidates) {
        let totalWP=0, succCount=0;
        const wpSamples=[];
        
        for (let i=0; i<numSims; i++) {
            const sim = stones.filter(s=>s.a).map(s=>({x:s.x,y:s.y,vx:0,vy:0,w:0,t:s.t,id:s.id,a:true}));
            const ns = gaussRandom(cand.speed, cand.speed*C.NOISE_SPEED_SIGMA);
            const latN = gaussRandom(0, C.NOISE_LATERAL_SIGMA);
            const depN = gaussRandom(0, C.NOISE_DEPTH_SIGMA);
            const del = createDelivery({
                tx:cand.targetX+latN,
                ty:cand.targetY+depN,
                spd:Math.max(ns,0.5), curl:cand.curl, team:team, id:'d'+i
            });
            sim.push(del);
            
            // Simulate both without and with sweep; pick best outcome (optimal sweep strategy)
            const simNS = sim.map(s=>({...s}));
            simulate(simNS);
            const simSW = sim.map(s=>({...s}));
            simulate(simSW, 'd'+i);
            
            function evalCnt(ss) {
                const c=countStones(ss);
                if(c.team===team) return c.count;
                if(c.team!==null) return -c.count;
                return 0;
            }
            const esNS=evalCnt(simNS), esSW=evalCnt(simSW);
            const es = Math.max(esNS, esSW);
            const bestSim = esSW>=esNS ? simSW : simNS;
            
            const nd = gameState.scoreDiff + es;
            // Hammer transition: scored → lose hammer; stolen → gain hammer; blank → stays
            const nh = es>0?(gameState.hammerTeam!==team):(es<0?(gameState.hammerTeam===team):(gameState.hammerTeam===team));
            
            // WP lookup from pre-computed table
            const di = clamp(Math.round(nd),-8,8)+8;
            const ei = clamp(Math.max(0,gameState.endsRemaining-1),0,10);
            const wp = wpTable[di][ei][nh?1:0];
            
            totalWP += wp;
            wpSamples.push(wp);
            
            // Success check (using optimal-sweep result)
            const deliv = bestSim.find(s=>s.id==='d'+i&&s.a);
            if (cand.type==='takeout'||cand.type==='peel'||cand.type==='hit-and-roll') {
                if (!bestSim.find(s=>s.id===cand.targetStone&&s.a&&Math.sqrt(s.x*s.x+s.y*s.y)<=C.HOUSE_RADIUS_12+C.STONE_RADIUS)) succCount++;
            } else if (cand.type==='double') {
                const g1=!bestSim.find(s=>s.id===cand.targetStone&&s.a&&Math.sqrt(s.x*s.x+s.y*s.y)<=C.HOUSE_RADIUS_12+C.STONE_RADIUS);
                const g2=!cand.targetStone2||!bestSim.find(s=>s.id===cand.targetStone2&&s.a&&Math.sqrt(s.x*s.x+s.y*s.y)<=C.HOUSE_RADIUS_12+C.STONE_RADIUS);
                if (g1&&g2) succCount++;
            } else if (cand.type==='freeze') {
                const ts=bestSim.find(s=>s.id===cand.targetStone&&s.a);
                if (deliv&&ts) { const fd=dist(deliv.x,deliv.y,ts.x,ts.y); if(fd<C.STONE_RADIUS*3) succCount++; }
            } else if (cand.type==='draw'||cand.type==='guard'||cand.type==='come-around') {
                if (deliv) { const dt2=dist(deliv.x,deliv.y,cand.targetX,cand.targetY); if(dt2<C.STONE_RADIUS*5) succCount++; }
            } else {
                if (deliv) succCount++;
            }
        }
        
        const avg=totalWP/numSims;
        let variance=0;
        for (const w of wpSamples) variance+=(w-avg)**2;
        variance/=numSims;
        
        results.push({
            candidate: cand,
            wpDelta: avg - wpTable[clamp(Math.round(gameState.scoreDiff),-8,8)+8][clamp(gameState.endsRemaining,0,10)][gameState.hammerTeam===team?1:0],
            avgWP: avg,
            successRate: succCount/numSims,
            stdError: Math.sqrt(variance/numSims),
            numSims,
        });
    }
    
    self.postMessage({ results, batchId });
};
`;
    
    let workers = [];
    let workerBlob = null;
    const POOL_SIZE = Math.min(navigator.hardwareConcurrency || 4, 4);
    
    function init() {
        if (workers.length > 0) return;
        workerBlob = new Blob([WORKER_CODE], { type: 'application/javascript' });
        const url = URL.createObjectURL(workerBlob);
        for (let i = 0; i < POOL_SIZE; i++) {
            workers.push(new Worker(url));
        }
    }
    
    /**
     * Serialize WP table for worker transfer.
     */
    function serializeWPTable() {
        const table = [];
        for (let d = 0; d <= 16; d++) {
            table[d] = [];
            for (let e = 0; e <= 10; e++) {
                table[d][e] = [
                    WinProbability._table[d][e][0],
                    WinProbability._table[d][e][1]
                ];
            }
        }
        return table;
    }
    
    /**
     * Run parallel Monte Carlo evaluation.
     * @returns {Promise<Array>} Ranked results
     */
    function evaluateParallel(stones, gameState, team, numSims, onProgress, opts = {}) {
        init();
        
        const candidates = ShotGenerator.generate(stones, team, { turnNumber: opts.turnNumber || 0 });
        if (candidates.length === 0) return Promise.resolve([]);
        
        const wpTable = serializeWPTable();
        const serializedStones = stones.filter(s => s.active).map(s => ({
            x: s.x, y: s.y, t: s.team, id: s.id, a: true
        }));
        
        // Split candidates across workers
        const chunks = [];
        const chunkSize = Math.ceil(candidates.length / POOL_SIZE);
        for (let i = 0; i < candidates.length; i += chunkSize) {
            chunks.push(candidates.slice(i, i + chunkSize));
        }
        
        return new Promise((resolve) => {
            const allResults = [];
            let completed = 0;
            
            chunks.forEach((chunk, idx) => {
                const worker = workers[idx % workers.length];
                const batchId = idx;
                
                const handler = (e) => {
                    if (e.data.batchId === batchId) {
                        worker.removeEventListener('message', handler);
                        allResults.push(...e.data.results);
                        completed++;
                        
                        if (onProgress) {
                            onProgress({
                                done: completed,
                                total: chunks.length,
                                partial: allResults.sort((a, b) => b.wpDelta - a.wpDelta).slice(0, 5),
                            });
                        }
                        
                        if (completed === chunks.length) {
                            allResults.sort((a, b) => b.wpDelta - a.wpDelta);
                            resolve(allResults);
                        }
                    }
                };
                
                worker.addEventListener('message', handler);
                worker.postMessage({
                    candidates: chunk,
                    stones: serializedStones,
                    gameState,
                    team,
                    numSims,
                    wpTable,
                    batchId,
                });
            });
        });
    }
    
    return { init, evaluateParallel };
})();


// ═══════════════════════════════════════════════════════════════════════════
// 7. PRESETS — Empty placeholder; real games loaded from data.js via API
// ═══════════════════════════════════════════════════════════════════════════

const Presets = {
    empty: { stones: [], description: 'Empty sheet' },
};


// ═══════════════════════════════════════════════════════════════════════════
// EXPORTS (global namespace for vanilla JS)
// ═══════════════════════════════════════════════════════════════════════════

window.CurlingEngine = {
    CurlingConst,
    WinProbability,
    Physics,
    PositionEval,
    ShotGenerator,
    ShotEvaluator,
    WorkerPool,
    Presets,
    Stone,
    dist,
    distToButton,
    feetInchesStr,
    metersToFeet,
    clamp,
    gaussRandom,
};
