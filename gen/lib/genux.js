/**
 * GENUX Primitives — Core visual elements for generative art
 * Breathing backgrounds, particles, micro-delights.
 */

import { withAlpha } from './palette.js';

/**
 * Draw breathing gradient background
 */
export function drawBreathingBackground(ctx, palette, phase = 0) {
    const { width, height } = ctx.canvas;

    // Base void
    ctx.fillStyle = palette.bg || '#07060B';
    ctx.fillRect(0, 0, width, height);

    // Breathing layers with phase offset
    const breathAlpha = 0.03 + Math.sin(phase) * 0.02;

    // Primary breath — colony color
    const grad1 = ctx.createRadialGradient(
        width * 0.5, height * 0.5, 0,
        width * 0.5, height * 0.5, width * 0.6
    );
    grad1.addColorStop(0, withAlpha(palette.primary, breathAlpha));
    grad1.addColorStop(1, 'transparent');
    ctx.fillStyle = grad1;
    ctx.fillRect(0, 0, width, height);

    // Secondary breath — accent, offset
    const grad2 = ctx.createRadialGradient(
        width * 0.3, height * 0.7, 0,
        width * 0.3, height * 0.7, width * 0.5
    );
    grad2.addColorStop(0, withAlpha(palette.accent, breathAlpha * 0.7));
    grad2.addColorStop(1, 'transparent');
    ctx.fillStyle = grad2;
    ctx.fillRect(0, 0, width, height);
}

/**
 * Draw floating particles
 */
export function drawParticles(ctx, palette, rng, count = 50) {
    const { width, height } = ctx.canvas;

    for (let i = 0; i < count; i++) {
        const x = rng.range(0, width);
        const y = rng.range(0, height);
        const size = rng.range(1, 4);
        const alpha = rng.range(0.1, 0.5);

        ctx.beginPath();
        ctx.arc(x, y, size, 0, Math.PI * 2);
        ctx.fillStyle = withAlpha(palette.primary, alpha);
        ctx.fill();

        // Glow
        if (rng.bool(0.3)) {
            ctx.shadowColor = palette.glow;
            ctx.shadowBlur = size * 4;
            ctx.fill();
            ctx.shadowBlur = 0;
        }
    }
}

/**
 * Draw connecting lines between points
 */
export function drawConnections(ctx, points, palette, rng, maxDist = 100) {
    ctx.strokeStyle = withAlpha(palette.secondary, 0.15);
    ctx.lineWidth = 1;

    for (let i = 0; i < points.length; i++) {
        for (let j = i + 1; j < points.length; j++) {
            const dx = points[j].x - points[i].x;
            const dy = points[j].y - points[i].y;
            const dist = Math.sqrt(dx * dx + dy * dy);

            if (dist < maxDist) {
                const alpha = 1 - (dist / maxDist);
                ctx.strokeStyle = withAlpha(palette.secondary, alpha * 0.2);
                ctx.beginPath();
                ctx.moveTo(points[i].x, points[i].y);
                ctx.lineTo(points[j].x, points[j].y);
                ctx.stroke();
            }
        }
    }
}

/**
 * Draw glowing circle
 */
export function drawGlowingCircle(ctx, x, y, radius, color, glowColor) {
    // Outer glow
    const gradient = ctx.createRadialGradient(x, y, 0, x, y, radius * 2);
    gradient.addColorStop(0, glowColor || withAlpha(color, 0.5));
    gradient.addColorStop(0.5, withAlpha(color, 0.1));
    gradient.addColorStop(1, 'transparent');

    ctx.fillStyle = gradient;
    ctx.beginPath();
    ctx.arc(x, y, radius * 2, 0, Math.PI * 2);
    ctx.fill();

    // Core
    ctx.fillStyle = color;
    ctx.beginPath();
    ctx.arc(x, y, radius, 0, Math.PI * 2);
    ctx.fill();
}

/**
 * Draw energy burst (spark pattern)
 */
export function drawEnergyBurst(ctx, x, y, radius, palette, rng, rayCount = 12) {
    const angleStep = (Math.PI * 2) / rayCount;

    for (let i = 0; i < rayCount; i++) {
        const angle = i * angleStep + rng.range(-0.2, 0.2);
        const length = radius * rng.range(0.5, 1.5);
        const thickness = rng.range(1, 3);

        const endX = x + Math.cos(angle) * length;
        const endY = y + Math.sin(angle) * length;

        // Gradient along ray
        const grad = ctx.createLinearGradient(x, y, endX, endY);
        grad.addColorStop(0, palette.primary);
        grad.addColorStop(0.5, withAlpha(palette.secondary, 0.5));
        grad.addColorStop(1, 'transparent');

        ctx.strokeStyle = grad;
        ctx.lineWidth = thickness;
        ctx.lineCap = 'round';
        ctx.beginPath();
        ctx.moveTo(x, y);
        ctx.lineTo(endX, endY);
        ctx.stroke();
    }

    // Central glow
    drawGlowingCircle(ctx, x, y, radius * 0.2, palette.primary, palette.glow);
}

/**
 * Draw organic blob shape
 */
export function drawBlob(ctx, x, y, size, palette, rng, points = 8) {
    ctx.beginPath();

    for (let i = 0; i <= points; i++) {
        const angle = (i / points) * Math.PI * 2;
        const variation = rng.range(0.7, 1.3);
        const r = size * variation;

        const px = x + Math.cos(angle) * r;
        const py = y + Math.sin(angle) * r;

        if (i === 0) {
            ctx.moveTo(px, py);
        } else {
            // Smooth curve through points
            const prevAngle = ((i - 1) / points) * Math.PI * 2;
            const cpDist = size * 0.5;
            const cp1x = x + Math.cos(prevAngle + 0.3) * cpDist;
            const cp1y = y + Math.sin(prevAngle + 0.3) * cpDist;
            ctx.quadraticCurveTo(cp1x, cp1y, px, py);
        }
    }

    ctx.closePath();
    ctx.fillStyle = withAlpha(palette.primary, 0.3);
    ctx.fill();
    ctx.strokeStyle = withAlpha(palette.secondary, 0.5);
    ctx.lineWidth = 2;
    ctx.stroke();
}

/**
 * Add film grain texture overlay
 */
export function drawGrain(ctx, intensity = 0.05) {
    const { width, height } = ctx.canvas;
    const imageData = ctx.getImageData(0, 0, width, height);
    const data = imageData.data;

    for (let i = 0; i < data.length; i += 4) {
        const noise = (Math.random() - 0.5) * intensity * 255;
        data[i] += noise;     // R
        data[i + 1] += noise; // G
        data[i + 2] += noise; // B
    }

    ctx.putImageData(imageData, 0, 0);
}

/**
 * Draw vignette effect
 */
export function drawVignette(ctx, intensity = 0.3) {
    const { width, height } = ctx.canvas;
    const cx = width / 2;
    const cy = height / 2;
    const radius = Math.max(width, height) * 0.7;

    const gradient = ctx.createRadialGradient(cx, cy, 0, cx, cy, radius);
    gradient.addColorStop(0, 'transparent');
    gradient.addColorStop(0.5, 'transparent');
    gradient.addColorStop(1, `rgba(0, 0, 0, ${intensity})`);

    ctx.fillStyle = gradient;
    ctx.fillRect(0, 0, width, height);
}

/**
 * Draw signature kanji watermark
 */
export function drawSignature(ctx, text = '鏡', x, y, size = 40, alpha = 0.15) {
    ctx.font = `${size}px "Noto Sans JP", serif`;
    ctx.fillStyle = `rgba(245, 240, 232, ${alpha})`;
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillText(text, x, y);
}

export default {
    drawBreathingBackground,
    drawParticles,
    drawConnections,
    drawGlowingCircle,
    drawEnergyBurst,
    drawBlob,
    drawGrain,
    drawVignette,
    drawSignature
};
