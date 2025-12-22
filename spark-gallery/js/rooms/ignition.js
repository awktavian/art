// ═══════════════════════════════════════════════════════════════════════════
// ROOM I: THE IGNITION
// Click to ignite. Watch the universe begin.
// ═══════════════════════════════════════════════════════════════════════════

import { CONFIG } from '../config.js';

export class IgnitionRoom {
    constructor(container, soundSystem = null) {
        this.container = container;
        this.sound = soundSystem;
        this.spark = document.getElementById('the-spark');
        this.voidOverlay = document.getElementById('void-overlay');
        this.content = document.getElementById('ignition-content');
        this.canvas = document.getElementById('explosion-canvas');
        this.ctx = this.canvas ? this.canvas.getContext('2d') : null;
        this.particles = [];
        this.isIgnited = false;
        this.animationId = null;
        
        this.init();
    }
    
    init() {
        this.resizeCanvas();
        window.addEventListener('resize', () => this.resizeCanvas());
        
        // Click spark to ignite
        if (this.spark) {
            this.spark.addEventListener('click', () => this.ignite());
        }
        
        // Also allow clicking anywhere in the room before ignition
        this.container.addEventListener('click', (e) => {
            if (!this.isIgnited && e.target !== this.spark) {
                this.ignite();
            }
        });
        
        // Start ambient particle animation
        this.startAmbientParticles();
    }
    
    resizeCanvas() {
        if (this.canvas) {
            this.canvas.width = window.innerWidth;
            this.canvas.height = window.innerHeight;
        }
    }
    
    ignite() {
        if (this.isIgnited) return;
        this.isIgnited = true;
        
        // Play explosion sound
        if (this.sound) {
            this.sound.playIgnition();
        }
        
        // Create explosion particles
        this.createExplosion(
            this.spark.getBoundingClientRect().left + 50,
            this.spark.getBoundingClientRect().top + 50
        );
        
        // Animate spark exploding
        this.spark.classList.add('ignited');
        
        // Fade void overlay
        setTimeout(() => {
            this.voidOverlay.classList.add('ignited');
        }, 200);
        
        // Reveal content
        setTimeout(() => {
            this.content.classList.add('visible');
        }, 500);
        
        // Start ambient crackle sound
        if (this.sound) {
            setTimeout(() => {
                this.sound.startAmbientCrackle();
            }, 1000);
        }
    }
    
    createExplosion(x, y) {
        const colors = [
            CONFIG.COLORS.FLAME,
            CONFIG.COLORS.EMBER,
            CONFIG.COLORS.GOLD,
            CONFIG.COLORS.YELLOW,
            CONFIG.COLORS.WHITE_HOT,
            CONFIG.COLORS.ELECTRIC,
            CONFIG.COLORS.PLASMA,
        ];
        
        for (let i = 0; i < CONFIG.EXPLOSION.PARTICLE_COUNT; i++) {
            const angle = (Math.PI * 2 * i) / CONFIG.EXPLOSION.PARTICLE_COUNT + Math.random() * 0.5;
            const velocity = CONFIG.EXPLOSION.MIN_VELOCITY + 
                Math.random() * (CONFIG.EXPLOSION.MAX_VELOCITY - CONFIG.EXPLOSION.MIN_VELOCITY);
            
            this.particles.push({
                x: x,
                y: y,
                vx: Math.cos(angle) * velocity,
                vy: Math.sin(angle) * velocity,
                radius: 2 + Math.random() * 6,
                color: colors[Math.floor(Math.random() * colors.length)],
                life: CONFIG.EXPLOSION.PARTICLE_LIFE,
                maxLife: CONFIG.EXPLOSION.PARTICLE_LIFE,
                gravity: CONFIG.EXPLOSION.GRAVITY * (0.5 + Math.random()),
            });
        }
        
        // Secondary burst
        setTimeout(() => {
            for (let i = 0; i < 50; i++) {
                const angle = Math.random() * Math.PI * 2;
                const velocity = 2 + Math.random() * 8;
                
                this.particles.push({
                    x: x + (Math.random() - 0.5) * 100,
                    y: y + (Math.random() - 0.5) * 100,
                    vx: Math.cos(angle) * velocity,
                    vy: Math.sin(angle) * velocity,
                    radius: 1 + Math.random() * 3,
                    color: colors[Math.floor(Math.random() * colors.length)],
                    life: 800,
                    maxLife: 800,
                    gravity: 0.05,
                });
            }
        }, 100);
    }
    
    startAmbientParticles() {
        const animate = () => {
            this.animationId = requestAnimationFrame(animate);
            
            if (!this.ctx) return;
            
            // Clear with fade (creates trails)
            this.ctx.fillStyle = 'rgba(10, 10, 10, 0.1)';
            this.ctx.fillRect(0, 0, this.canvas.width, this.canvas.height);
            
            // Update and draw particles
            for (let i = this.particles.length - 1; i >= 0; i--) {
                const p = this.particles[i];
                
                // Update
                p.x += p.vx;
                p.y += p.vy;
                p.vy += p.gravity;
                p.vx *= 0.99;
                p.life -= 16;
                
                // Remove dead particles
                if (p.life <= 0) {
                    this.particles.splice(i, 1);
                    continue;
                }
                
                // Draw
                const alpha = p.life / p.maxLife;
                this.ctx.beginPath();
                this.ctx.arc(p.x, p.y, p.radius * alpha, 0, Math.PI * 2);
                this.ctx.fillStyle = this.hexToRgba(p.color, alpha);
                this.ctx.fill();
                
                // Add glow
                this.ctx.shadowBlur = 20;
                this.ctx.shadowColor = p.color;
                this.ctx.fill();
                this.ctx.shadowBlur = 0;
            }
            
            // Spawn random ambient sparks after ignition
            if (this.isIgnited && Math.random() < 0.03) {
                const x = Math.random() * this.canvas.width;
                const y = Math.random() * this.canvas.height;
                this.particles.push({
                    x: x,
                    y: y,
                    vx: (Math.random() - 0.5) * 2,
                    vy: -Math.random() * 3,
                    radius: 1 + Math.random() * 2,
                    color: [CONFIG.COLORS.FLAME, CONFIG.COLORS.GOLD, CONFIG.COLORS.EMBER][Math.floor(Math.random() * 3)],
                    life: 500,
                    maxLife: 500,
                    gravity: -0.02,
                });
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

