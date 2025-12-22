// Particle System - Canvas-based

import { CONFIG, COLORS } from '../config.js';

export class ParticleSystem {
    constructor(cursor) {
        this.cursor = cursor;
        this.canvas = document.getElementById('particle-canvas');
        this.ctx = this.canvas?.getContext('2d');

        this.particles = [];
        this.particlePool = [];
        this.lastSpawnTime = 0;
        this.mode = 'normal'; // 'normal' or 'spiral-inward'

        this.init();
    }

    init() {
        if (!this.canvas || !this.ctx) return;

        this.resize();
        window.addEventListener('resize', this.resize.bind(this));

        // Start animation loop
        this.animate();
    }

    resize() {
        this.canvas.width = window.innerWidth;
        this.canvas.height = window.innerHeight;
    }

    createParticle(x, y, color = COLORS.gold) {
        const angle = Math.random() * Math.PI * 2;
        const speed = CONFIG.PARTICLE_SPEED + Math.random() * 2;

        return {
            x,
            y,
            vx: Math.cos(angle) * speed,
            vy: Math.sin(angle) * speed,
            life: 1.0,
            maxLife: CONFIG.PARTICLE_LIFETIME,
            color,
            size: CONFIG.PARTICLE_SIZE,
            birthTime: Date.now()
        };
    }

    spawnParticle(x, y, color) {
        if (this.particles.length >= CONFIG.PARTICLE_LIMIT) {
            this.particles.shift(); // Remove oldest
        }

        const particle = this.particlePool.pop() || this.createParticle(x, y, color);
        particle.x = x;
        particle.y = y;
        particle.life = 1.0;
        particle.birthTime = Date.now();
        particle.color = color;

        const angle = Math.random() * Math.PI * 2;
        const speed = CONFIG.PARTICLE_SPEED + Math.random() * 2;
        particle.vx = Math.cos(angle) * speed;
        particle.vy = Math.sin(angle) * speed;

        this.particles.push(particle);
    }

    update(deltaTime) {
        const cursorPos = this.cursor.getPosition();
        const centerX = window.innerWidth / 2;
        const centerY = window.innerHeight / 2;

        for (let i = this.particles.length - 1; i >= 0; i--) {
            const p = this.particles[i];

            // Update lifetime
            const age = Date.now() - p.birthTime;
            p.life = 1.0 - (age / p.maxLife);

            if (p.life <= 0) {
                this.particlePool.push(this.particles.splice(i, 1)[0]);
                continue;
            }

            if (this.mode === 'spiral-inward') {
                // Spiral inward mode: pull toward screen center
                const dx = centerX - p.x;
                const dy = centerY - p.y;
                const dist = Math.sqrt(dx * dx + dy * dy);

                if (dist > 10) {
                    const angle = Math.atan2(dy, dx);
                    // Add radial component (toward center)
                    p.vx = Math.cos(angle) * 2.5;
                    p.vy = Math.sin(angle) * 2.5;
                    // Add tangential component (spiral)
                    p.vx += -Math.sin(angle) * 0.8;
                    p.vy += Math.cos(angle) * 0.8;
                } else {
                    // Near center: fade out
                    p.life = 0;
                }
            } else {
                // Normal mode: gravitational pull toward cursor
                const dx = cursorPos.x - p.x;
                const dy = cursorPos.y - p.y;
                const distSq = dx * dx + dy * dy;

                if (distSq < CONFIG.CURSOR_INFLUENCE_RADIUS * CONFIG.CURSOR_INFLUENCE_RADIUS) {
                    const dist = Math.sqrt(distSq);
                    const force = (1.0 - dist / CONFIG.CURSOR_INFLUENCE_RADIUS) * 0.5;
                    p.vx += (dx / dist) * force;
                    p.vy += (dy / dist) * force;
                }
            }

            // Apply friction
            p.vx *= 0.98;
            p.vy *= 0.98;

            // Update position
            p.x += p.vx;
            p.y += p.vy;
        }
    }

    render() {
        if (!this.ctx) return;

        this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);

        for (const p of this.particles) {
            const alpha = p.life;

            // Glow
            this.ctx.beginPath();
            this.ctx.arc(p.x, p.y, CONFIG.PARTICLE_GLOW_SIZE, 0, Math.PI * 2);
            const gradient = this.ctx.createRadialGradient(p.x, p.y, 0, p.x, p.y, CONFIG.PARTICLE_GLOW_SIZE);
            gradient.addColorStop(0, this.hexToRgba(p.color, alpha * 0.6));
            gradient.addColorStop(1, this.hexToRgba(p.color, 0));
            this.ctx.fillStyle = gradient;
            this.ctx.fill();

            // Core
            this.ctx.beginPath();
            this.ctx.arc(p.x, p.y, p.size, 0, Math.PI * 2);
            this.ctx.fillStyle = this.hexToRgba(p.color, alpha);
            this.ctx.fill();
        }
    }

    hexToRgba(hex, alpha) {
        const r = parseInt(hex.slice(1, 3), 16);
        const g = parseInt(hex.slice(3, 5), 16);
        const b = parseInt(hex.slice(5, 7), 16);
        return `rgba(${r}, ${g}, ${b}, ${alpha})`;
    }

    /**
     * Set particle mode
     * @param {string} mode - 'normal' or 'spiral-inward'
     */
    setMode(mode) {
        this.mode = mode;
        console.log(`Particle mode: ${mode}`);
    }

    animate() {
        const now = Date.now();

        // Spawn particles periodically if cursor is moving (normal mode only)
        if (this.mode === 'normal') {
            const velocity = this.cursor.getVelocity();
            const speed = Math.sqrt(velocity.x * velocity.x + velocity.y * velocity.y);

            if (speed > 0.5 && now - this.lastSpawnTime > 1000 / CONFIG.PARTICLE_SPAWN_RATE) {
                const pos = this.cursor.getPosition();
                this.spawnParticle(pos.x, pos.y, COLORS.gold);
                this.lastSpawnTime = now;
            }
        }

        this.update(16); // Assume ~60fps
        this.render();

        requestAnimationFrame(this.animate.bind(this));
    }
}
