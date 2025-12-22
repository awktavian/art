// ═══════════════════════════════════════════════════════════════════════════
// ROOM I: IGNITION
// The first spark. From void to fire.
// Crystal-verified: Canvas explosion, particle physics, content reveal
// ═══════════════════════════════════════════════════════════════════════════

import { CONFIG } from '../config.js';

export class IgnitionRoom {
    constructor(container, soundSystem = null) {
        this.container = container;
        this.sound = soundSystem;
        this.canvas = document.getElementById('ignition-canvas');
        this.ctx = this.canvas ? this.canvas.getContext('2d') : null;
        
        this.particles = [];
        this.isIgnited = false;
        this.animationId = null;
        
        this.voidOverlay = document.getElementById('void-overlay');
        this.sparkTrigger = document.getElementById('spark-trigger');
        this.ignitionReveal = document.getElementById('ignition-reveal');
        
        this.init();
    }
    
    init() {
        this.resizeCanvas();
        window.addEventListener('resize', () => this.resizeCanvas());
        
        // Click to ignite
        if (this.sparkTrigger) {
            this.sparkTrigger.addEventListener('click', (e) => {
                if (!this.isIgnited) {
                    const rect = this.canvas.getBoundingClientRect();
                    const x = e.clientX - rect.left;
                    const y = e.clientY - rect.top;
                    this.ignite(x, y);
                }
            });
        }
        
        // Start render loop
        this.startAnimation();
        
        console.log('✨ Ignition room initialized');
    }
    
    resizeCanvas() {
        if (this.canvas) {
            this.canvas.width = window.innerWidth;
            this.canvas.height = window.innerHeight;
        }
    }
    
    async ignite(clickX, clickY) {
        if (this.isIgnited) return;
        this.isIgnited = true;
        
        // Play ignition sound
        if (this.sound) {
            await this.sound.init();
            this.sound.playIgnition();
        }
        
        // Create explosion at click point
        const centerX = clickX || this.canvas.width / 2;
        const centerY = clickY || this.canvas.height / 2;
        
        // Multi-wave explosion
        this.createExplosion(centerX, centerY, 150, 0);
        setTimeout(() => this.createExplosion(centerX, centerY, 100, 1), 80);
        setTimeout(() => this.createExplosion(centerX, centerY, 80, 2), 160);
        setTimeout(() => this.createExplosion(centerX, centerY, 50, 3), 250);
        
        // Fade out void overlay
        if (this.voidOverlay) {
            this.voidOverlay.style.transition = 'opacity 1.5s ease-out';
            this.voidOverlay.style.opacity = '0';
            setTimeout(() => {
                this.voidOverlay.style.display = 'none';
            }, 1500);
        }
        
        // Hide spark trigger
        if (this.sparkTrigger) {
            this.sparkTrigger.style.transition = 'opacity 0.3s ease-out';
            this.sparkTrigger.style.opacity = '0';
            setTimeout(() => {
                this.sparkTrigger.style.display = 'none';
            }, 300);
        }
        
        // Reveal content after explosion settles
        setTimeout(() => {
            if (this.ignitionReveal) {
                this.ignitionReveal.classList.add('revealed');
            }
            // Start ambient particles
            this.startAmbientParticles();
        }, 800);
    }
    
    createExplosion(x, y, count, wave) {
        const colors = [
            CONFIG.COLORS.WHITE_HOT,
            CONFIG.COLORS.YELLOW,
            CONFIG.COLORS.GOLD,
            CONFIG.COLORS.FLAME,
            CONFIG.COLORS.EMBER,
        ];
        
        for (let i = 0; i < count; i++) {
            const angle = (Math.PI * 2 * i) / count + Math.random() * 0.3;
            const speed = 8 + Math.random() * 18 - wave * 2;
            const size = 2 + Math.random() * 8 - wave * 0.5;
            
            this.particles.push({
                x: x,
                y: y,
                vx: Math.cos(angle) * speed,
                vy: Math.sin(angle) * speed,
                size: Math.max(1, size),
                color: colors[Math.floor(Math.random() * colors.length)],
                life: 1600 + Math.random() * 800 - wave * 200,
                maxLife: 2400 - wave * 200,
                gravity: 0.08 + wave * 0.02,
                drag: 0.985,
                wave: wave,
            });
        }
    }
    
    startAmbientParticles() {
        // Continuously spawn ambient sparks
        const spawnAmbient = () => {
            if (!this.isIgnited) return;
            
            // Random sparks from edges and bottom
            if (Math.random() < 0.12) {
                const edge = Math.floor(Math.random() * 3);
                let x, y;
                
                if (edge === 0) { // Bottom
                    x = Math.random() * this.canvas.width;
                    y = this.canvas.height + 10;
                } else if (edge === 1) { // Left
                    x = -10;
                    y = Math.random() * this.canvas.height;
                } else { // Right
                    x = this.canvas.width + 10;
                    y = Math.random() * this.canvas.height;
                }
                
                const angle = Math.atan2(this.canvas.height / 2 - y, this.canvas.width / 2 - x);
                const speed = 1 + Math.random() * 3;
                
                this.particles.push({
                    x: x,
                    y: y,
                    vx: Math.cos(angle) * speed + (Math.random() - 0.5) * 2,
                    vy: Math.sin(angle) * speed + (Math.random() - 0.5) * 2,
                    size: 1 + Math.random() * 3,
                    color: this.getRandomColor(),
                    life: 500 + Math.random() * 800,
                    maxLife: 1300,
                    gravity: -0.02,
                    drag: 0.995,
                    ambient: true,
                });
            }
            
            requestAnimationFrame(spawnAmbient);
        };
        
        spawnAmbient();
    }
    
    getRandomColor() {
        const colors = [
            CONFIG.COLORS.FLAME,
            CONFIG.COLORS.EMBER,
            CONFIG.COLORS.GOLD,
            CONFIG.COLORS.YELLOW,
        ];
        return colors[Math.floor(Math.random() * colors.length)];
    }
    
    startAnimation() {
        const animate = () => {
            this.animationId = requestAnimationFrame(animate);
            
            if (!this.ctx || !this.canvas) return;
            
            const ctx = this.ctx;
            const width = this.canvas.width;
            const height = this.canvas.height;
            
            if (width === 0 || height === 0) return;
            
            // Clear with fade trail
            ctx.fillStyle = this.isIgnited ? 'rgba(5, 5, 5, 0.12)' : 'rgba(5, 5, 5, 1)';
            ctx.fillRect(0, 0, width, height);
            
            // Update and draw particles
            for (let i = this.particles.length - 1; i >= 0; i--) {
                const p = this.particles[i];
                
                // Physics
                p.x += p.vx;
                p.y += p.vy;
                p.vy += p.gravity;
                p.vx *= p.drag;
                p.vy *= p.drag;
                p.life -= 16;
                
                // Remove dead particles
                if (p.life <= 0) {
                    this.particles.splice(i, 1);
                    continue;
                }
                
                // Calculate alpha based on life
                const lifeRatio = p.life / p.maxLife;
                const alpha = Math.pow(lifeRatio, 0.5);
                const size = p.size * lifeRatio;
                
                // Draw glow
                const gradient = ctx.createRadialGradient(p.x, p.y, 0, p.x, p.y, size * 4);
                gradient.addColorStop(0, this.hexToRgba(p.color, alpha * 0.8));
                gradient.addColorStop(0.4, this.hexToRgba(p.color, alpha * 0.3));
                gradient.addColorStop(1, 'transparent');
                
                ctx.beginPath();
                ctx.arc(p.x, p.y, size * 4, 0, Math.PI * 2);
                ctx.fillStyle = gradient;
                ctx.fill();
                
                // Draw core
                ctx.beginPath();
                ctx.arc(p.x, p.y, size, 0, Math.PI * 2);
                ctx.fillStyle = this.hexToRgba(p.color, alpha);
                ctx.fill();
                
                // Bright inner core for fresh particles
                if (lifeRatio > 0.7) {
                    ctx.beginPath();
                    ctx.arc(p.x, p.y, size * 0.4, 0, Math.PI * 2);
                    ctx.fillStyle = this.hexToRgba(CONFIG.COLORS.WHITE_HOT, alpha * 0.8);
                    ctx.fill();
                }
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
