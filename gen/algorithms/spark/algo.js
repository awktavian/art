/**
 * Spark Algorithm — Energy bursts and particle explosions
 * Colony: Spark (e1) — Ideation, creative energy, ignition
 *
 * Generates stochastic particle systems with energy bursts,
 * representing the explosive nature of new ideas.
 */

import { PRNG } from '../../lib/prng.js';
import { getPalette, withAlpha } from '../../lib/palette.js';
import {
    drawBreathingBackground,
    drawGlowingCircle,
    drawEnergyBurst,
    drawConnections,
    drawVignette,
    drawSignature
} from '../../lib/genux.js';

/**
 * Main generation function
 * @param {HTMLCanvasElement} canvas
 * @param {string} seed
 * @returns {object} Metadata about the generation
 */
export default function generate(canvas, seed) {
    const ctx = canvas.getContext('2d');
    const rng = new PRNG(seed);
    const palette = getPalette('spark', rng);
    const { width, height } = canvas;

    // Generation parameters (RNG-derived)
    // REFINED: Raised minimums based on 10-seed test (Jan 12, 2026)
    // - burstCount: 3→4 (low burst count felt sparse in 6/10 tests)
    // - particleCount: 80→100 (low particle count felt empty)
    // - energyIntensity: 0.6→0.65 (low energy felt muted)
    // - trailLength: 3→4 (short trails felt abrupt)
    const params = {
        burstCount: rng.int(4, 8),
        particleCount: rng.int(100, 200),
        connectionDensity: rng.range(0.3, 0.7),
        energyIntensity: rng.range(0.65, 1.0),
        trailLength: rng.int(4, 8),
        asymmetry: rng.range(0.2, 0.8)
    };

    // Clear and draw breathing background
    drawBreathingBackground(ctx, palette);

    // Generate burst centers with clustering
    const bursts = generateBurstCenters(rng, width, height, params);

    // Draw connections between nearby bursts
    if (bursts.length > 1 && rng.bool(params.connectionDensity)) {
        drawConnections(ctx, bursts, palette, rng, width * 0.3);
    }

    // Draw energy trails from bursts
    bursts.forEach(burst => {
        drawEnergyTrails(ctx, burst, palette, rng, params);
    });

    // Draw main energy bursts
    bursts.forEach(burst => {
        const rayCount = rng.int(8, 20);
        drawEnergyBurst(ctx, burst.x, burst.y, burst.size, palette, rng, rayCount);
    });

    // Scatter particles
    drawScatteredParticles(ctx, rng, palette, params, width, height);

    // Draw orbital particles around bursts
    bursts.forEach(burst => {
        if (rng.bool(0.6)) {
            drawOrbitalParticles(ctx, burst, palette, rng);
        }
    });

    // Post-processing
    drawVignette(ctx, 0.25);

    // Signature
    drawSignature(ctx, '鏡', width - 40, height - 30, 30, 0.12);

    // Return metadata
    return {
        seed,
        colony: 'spark',
        params,
        burstCount: bursts.length
    };
}

/**
 * Generate burst center points with natural clustering
 */
function generateBurstCenters(rng, width, height, params) {
    const bursts = [];
    const margin = width * 0.15;

    // Primary burst (always present, roughly centered)
    const primaryX = width * rng.range(0.35, 0.65);
    const primaryY = height * rng.range(0.35, 0.65);
    bursts.push({
        x: primaryX,
        y: primaryY,
        size: width * rng.range(0.08, 0.15),
        intensity: params.energyIntensity
    });

    // Secondary bursts
    for (let i = 1; i < params.burstCount; i++) {
        // Cluster around primary or scatter
        let x, y;
        if (rng.bool(0.4)) {
            // Cluster near primary
            const angle = rng.range(0, Math.PI * 2);
            const dist = width * rng.range(0.1, 0.3);
            x = primaryX + Math.cos(angle) * dist;
            y = primaryY + Math.sin(angle) * dist;
        } else {
            // Random position with margin
            x = rng.range(margin, width - margin);
            y = rng.range(margin, height - margin);
        }

        bursts.push({
            x,
            y,
            size: width * rng.range(0.04, 0.1),
            intensity: params.energyIntensity * rng.range(0.5, 1.0)
        });
    }

    return bursts;
}

/**
 * Draw energy trails emanating from burst
 */
function drawEnergyTrails(ctx, burst, palette, rng, params) {
    const trailCount = rng.int(3, 8);

    for (let i = 0; i < trailCount; i++) {
        const angle = rng.range(0, Math.PI * 2);
        const length = burst.size * rng.range(2, 5);

        // Trail is series of fading points
        const steps = params.trailLength;
        for (let s = 0; s < steps; s++) {
            const t = s / steps;
            const dist = length * t;
            const x = burst.x + Math.cos(angle) * dist;
            const y = burst.y + Math.sin(angle) * dist;
            const size = burst.size * 0.1 * (1 - t * 0.8);
            const alpha = 0.4 * (1 - t);

            ctx.beginPath();
            ctx.arc(x, y, size, 0, Math.PI * 2);
            ctx.fillStyle = withAlpha(palette.secondary, alpha);
            ctx.fill();
        }
    }
}

/**
 * Draw scattered ambient particles
 */
function drawScatteredParticles(ctx, rng, palette, params, width, height) {
    const count = params.particleCount;

    for (let i = 0; i < count; i++) {
        const x = rng.range(0, width);
        const y = rng.range(0, height);
        const size = rng.range(0.5, 3);
        const alpha = rng.range(0.1, 0.5);

        // Vary color within palette
        const color = rng.pick(palette.colors || [palette.primary, palette.secondary]);

        ctx.beginPath();
        ctx.arc(x, y, size, 0, Math.PI * 2);
        ctx.fillStyle = withAlpha(color, alpha);
        ctx.fill();

        // Some particles glow
        if (rng.bool(0.15)) {
            ctx.shadowColor = palette.glow;
            ctx.shadowBlur = size * 3;
            ctx.fill();
            ctx.shadowBlur = 0;
        }
    }
}

/**
 * Draw particles orbiting around a burst
 */
function drawOrbitalParticles(ctx, burst, palette, rng) {
    const orbitCount = rng.int(5, 12);
    const orbitRadius = burst.size * rng.range(1.5, 2.5);

    for (let i = 0; i < orbitCount; i++) {
        const angle = (i / orbitCount) * Math.PI * 2 + rng.range(-0.2, 0.2);
        const radiusVar = orbitRadius * rng.range(0.8, 1.2);
        const x = burst.x + Math.cos(angle) * radiusVar;
        const y = burst.y + Math.sin(angle) * radiusVar;
        const size = rng.range(2, 5);

        drawGlowingCircle(ctx, x, y, size, palette.accent, palette.glow);
    }
}
