// ═══════════════════════════════════════════════════════════════════════════
// ROOM I: THE CURRENT
// Where bugs flow to their resolution
// Crystal-verified: Canvas waves, error particles, flow animation
// ═══════════════════════════════════════════════════════════════════════════

import { CONFIG, ERROR_TYPES } from '../config.js';

export class CurrentRoom {
    constructor(container, soundSystem = null) {
        this.container = container;
        this.sound = soundSystem;
        this.canvas = document.getElementById('current-canvas');
        this.ctx = this.canvas ? this.canvas.getContext('2d') : null;
        
        this.particles = [];
        this.waves = [];
        this.errorCount = 0;
        this.fixedCount = 0;
        this.animationId = null;
        this.time = 0;
        
        this.errorCountEl = document.getElementById('error-count');
        this.fixedCountEl = document.getElementById('fixed-count');
        this.flowRateEl = document.getElementById('flow-rate');
        
        this.init();
    }
    
    init() {
        this.resizeCanvas();
        window.addEventListener('resize', () => this.resizeCanvas());
        
        // Initialize waves
        for (let i = 0; i < 5; i++) {
            this.waves.push({
                amplitude: 20 + Math.random() * 30,
                frequency: 0.005 + Math.random() * 0.01,
                phase: Math.random() * Math.PI * 2,
                speed: 0.02 + Math.random() * 0.02,
                y: this.canvas ? this.canvas.height * (0.3 + i * 0.1) : 300,
                color: `rgba(0, ${150 + i * 20}, ${180 + i * 15}, ${0.3 - i * 0.04})`,
            });
        }
        
        // Spawn initial particles
        this.spawnFlowParticles(30);
        
        // Click to spawn errors
        if (this.canvas) {
            this.canvas.addEventListener('click', (e) => {
                const rect = this.canvas.getBoundingClientRect();
                const x = e.clientX - rect.left;
                const y = e.clientY - rect.top;
                this.spawnError(x, y);
            });
        }
        
        // Start animation
        this.startAnimation();
        
        // Auto-spawn errors occasionally
        this.startAutoSpawn();
        
        console.log('🌊 Current room initialized');
    }
    
    resizeCanvas() {
        if (this.canvas) {
            this.canvas.width = window.innerWidth;
            this.canvas.height = window.innerHeight;
        }
    }
    
    spawnFlowParticles(count) {
        for (let i = 0; i < count; i++) {
            this.particles.push({
                x: Math.random() * (this.canvas?.width || 800),
                y: Math.random() * (this.canvas?.height || 600),
                vx: 1 + Math.random() * 2,
                vy: (Math.random() - 0.5) * 0.5,
                size: 2 + Math.random() * 3,
                color: CONFIG.COLORS.CYAN,
                type: 'flow',
                life: Infinity,
            });
        }
    }
    
    spawnError(x, y) {
        const errorType = ERROR_TYPES[Math.floor(Math.random() * ERROR_TYPES.length)];
        
        this.particles.push({
            x: x,
            y: y,
            vx: (Math.random() - 0.5) * 2,
            vy: Math.random() * 2 + 1,
            size: 8 + errorType.severity * 3,
            color: errorType.color,
            type: 'error',
            errorType: errorType.type,
            life: 5000,
            maxLife: 5000,
            healing: false,
        });
        
        this.errorCount++;
        this.updateStats();
        
        if (this.sound && this.sound.initialized) {
            this.sound.playError();
        }
    }
    
    healError(particle) {
        if (particle.healing) return;
        particle.healing = true;
        particle.life = 500;
        particle.color = CONFIG.COLORS.HEALING_GREEN;
        
        this.fixedCount++;
        this.updateStats();
        
        if (this.sound && this.sound.initialized) {
            this.sound.playHeal();
        }
    }
    
    updateStats() {
        if (this.errorCountEl) this.errorCountEl.textContent = this.errorCount;
        if (this.fixedCountEl) this.fixedCountEl.textContent = this.fixedCount;
        if (this.flowRateEl) {
            const rate = this.fixedCount > 0 ? (this.fixedCount / Math.max(this.errorCount, 1) * 100).toFixed(0) : '∞';
            this.flowRateEl.textContent = rate === '100' ? '∞' : rate + '%';
        }
    }
    
    startAutoSpawn() {
        setInterval(() => {
            // Auto-heal some errors
            const errors = this.particles.filter(p => p.type === 'error' && !p.healing);
            if (errors.length > 0 && Math.random() < 0.3) {
                this.healError(errors[Math.floor(Math.random() * errors.length)]);
            }
        }, 2000);
    }
    
    startAnimation() {
        const animate = () => {
            this.animationId = requestAnimationFrame(animate);
            this.time += 0.016;
            
            if (!this.ctx || !this.canvas) return;
            
            const ctx = this.ctx;
            const width = this.canvas.width;
            const height = this.canvas.height;
            
            if (width === 0 || height === 0) return;
            
            // Clear
            ctx.fillStyle = 'rgba(10, 10, 15, 0.1)';
            ctx.fillRect(0, 0, width, height);
            
            // Draw waves
            this.waves.forEach(wave => {
                wave.phase += wave.speed;
                ctx.beginPath();
                ctx.moveTo(0, wave.y);
                
                for (let x = 0; x <= width; x += 5) {
                    const y = wave.y + Math.sin(x * wave.frequency + wave.phase) * wave.amplitude;
                    ctx.lineTo(x, y);
                }
                
                ctx.lineTo(width, height);
                ctx.lineTo(0, height);
                ctx.closePath();
                ctx.fillStyle = wave.color;
                ctx.fill();
            });
            
            // Update and draw particles
            for (let i = this.particles.length - 1; i >= 0; i--) {
                const p = this.particles[i];
                
                // Flow physics
                if (p.type === 'flow') {
                    p.x += p.vx;
                    p.y += p.vy + Math.sin(this.time * 2 + p.x * 0.01) * 0.5;
                    
                    // Wrap around
                    if (p.x > width + 10) p.x = -10;
                    if (p.y < 0) p.y = height;
                    if (p.y > height) p.y = 0;
                } else if (p.type === 'error') {
                    p.x += p.vx + Math.sin(this.time * 3) * 0.5;
                    p.y += p.vy;
                    p.vy *= 0.98;
                    p.life -= 16;
                    
                    if (p.life <= 0) {
                        this.particles.splice(i, 1);
                        continue;
                    }
                }
                
                // Draw
                const alpha = p.type === 'flow' ? 0.6 : Math.min(p.life / p.maxLife, 1);
                
                if (p.type === 'error') {
                    // Error glow
                    const gradient = ctx.createRadialGradient(p.x, p.y, 0, p.x, p.y, p.size * 2);
                    gradient.addColorStop(0, this.hexToRgba(p.color, alpha * 0.8));
                    gradient.addColorStop(1, 'transparent');
                    
                    ctx.beginPath();
                    ctx.arc(p.x, p.y, p.size * 2, 0, Math.PI * 2);
                    ctx.fillStyle = gradient;
                    ctx.fill();
                }
                
                ctx.beginPath();
                ctx.arc(p.x, p.y, p.size * alpha, 0, Math.PI * 2);
                ctx.fillStyle = this.hexToRgba(p.color, alpha);
                ctx.fill();
            }
        };
        
        animate();
    }
    
    hexToRgba(hex, alpha) {
        const r = parseInt(hex.slice(1, 3), 16);
        const g = parseInt(hex.slice(3, 5), 16);
        const b = parseInt(hex.slice(5, 7), 16);
        return `rgba(${r}, ${g}, ${b}, ${alpha})`;
    }
    
    destroy() {
        if (this.animationId) {
            cancelAnimationFrame(this.animationId);
        }
    }
}

