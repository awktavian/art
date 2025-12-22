// ═══════════════════════════════════════════════════════════════════════════
// ROOM IV: THE OVERFLOW
// Interactive spark generator. Click to spawn ideas. Watch chaos unfold.
// Crystal-verified: Canvas interaction, particle physics, visual polish
// ═══════════════════════════════════════════════════════════════════════════

import { CONFIG } from '../config.js';

export class OverflowRoom {
    constructor(container, soundSystem = null) {
        this.container = container;
        this.sound = soundSystem;
        this.canvas = document.getElementById('generator-canvas');
        this.ctx = this.canvas ? this.canvas.getContext('2d') : null;
        
        this.sparks = [];
        this.animationId = null;
        this.isVisible = false;
        
        this.init();
    }
    
    init() {
        this.resizeCanvas();
        window.addEventListener('resize', () => this.resizeCanvas());
        
        // IntersectionObserver for visibility
        const observer = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                this.isVisible = entry.isIntersecting;
            });
        }, { threshold: 0.2 });
        
        if (this.container) {
            observer.observe(this.container);
        }
        
        // Click to spawn sparks
        if (this.canvas) {
            this.canvas.addEventListener('click', (e) => {
                const rect = this.canvas.getBoundingClientRect();
                const x = e.clientX - rect.left;
                const y = e.clientY - rect.top;
                this.spawnSparkBurst(x, y);
            });
            
            // Mouse move creates trailing sparks
            this.canvas.addEventListener('mousemove', (e) => {
                if (Math.random() < 0.4) {
                    const rect = this.canvas.getBoundingClientRect();
                    const x = e.clientX - rect.left;
                    const y = e.clientY - rect.top;
                    this.spawnSpark(x, y, 0.4);
                }
            });
            
            // Touch support
            this.canvas.addEventListener('touchmove', (e) => {
                e.preventDefault();
                const touch = e.touches[0];
                const rect = this.canvas.getBoundingClientRect();
                const x = touch.clientX - rect.left;
                const y = touch.clientY - rect.top;
                this.spawnSpark(x, y, 0.3);
            }, { passive: false });
        }
        
        // Start animation
        this.startAnimation();
        
        console.log('💥 Overflow room initialized');
    }
    
    resizeCanvas() {
        if (this.canvas) {
            const container = this.canvas.parentElement;
            this.canvas.width = Math.max(container?.clientWidth || 800, 400);
            this.canvas.height = 300;
        }
    }
    
    spawnSparkBurst(x, y) {
        const count = 30 + Math.random() * 25;
        
        for (let i = 0; i < count; i++) {
            const angle = (Math.PI * 2 * i) / count + (Math.random() - 0.5) * 0.4;
            const speed = 3 + Math.random() * 10;
            
            this.sparks.push({
                x: x,
                y: y,
                vx: Math.cos(angle) * speed,
                vy: Math.sin(angle) * speed,
                radius: 2 + Math.random() * 5,
                color: this.getRandomColor(),
                life: 1200 + Math.random() * 800,
                maxLife: 2000,
                gravity: 0.06 + Math.random() * 0.08,
            });
        }
        
        // Play sound
        if (this.sound && this.sound.initialized) {
            this.sound.playSpawn();
        }
    }
    
    spawnSpark(x, y, scale = 1) {
        this.sparks.push({
            x: x,
            y: y,
            vx: (Math.random() - 0.5) * 5 * scale,
            vy: -Math.random() * 4 * scale - 1,
            radius: (1.5 + Math.random() * 2.5) * scale,
            color: this.getRandomColor(),
            life: 700 * scale,
            maxLife: 700 * scale,
            gravity: 0.03,
        });
    }
    
    getRandomColor() {
        const colors = [
            CONFIG.COLORS.FLAME,
            CONFIG.COLORS.EMBER,
            CONFIG.COLORS.GOLD,
            CONFIG.COLORS.YELLOW,
            CONFIG.COLORS.WHITE_HOT,
            CONFIG.COLORS.ELECTRIC,
            CONFIG.COLORS.PLASMA,
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
            
            // Clear with fade
            ctx.fillStyle = 'rgba(5, 5, 5, 0.18)';
            ctx.fillRect(0, 0, width, height);
            
            // Draw border glow
            this.drawBorderGlow(ctx, width, height);
            
            // Update and draw sparks
            for (let i = this.sparks.length - 1; i >= 0; i--) {
                const s = this.sparks[i];
                
                // Update physics
                s.x += s.vx;
                s.y += s.vy;
                s.vy += s.gravity;
                s.vx *= 0.99;
                s.life -= 16;
                
                // Remove dead sparks
                if (s.life <= 0 || s.y > height + 20) {
                    this.sparks.splice(i, 1);
                    continue;
                }
                
                // Bounce off walls
                if (s.x < 0 || s.x > width) {
                    s.vx *= -0.7;
                    s.x = Math.max(0, Math.min(width, s.x));
                }
                
                // Draw spark with glow
                const alpha = Math.pow(s.life / s.maxLife, 0.6);
                const radius = s.radius * alpha;
                
                // Glow layer
                const gradient = ctx.createRadialGradient(s.x, s.y, 0, s.x, s.y, radius * 4);
                gradient.addColorStop(0, this.hexToRgba(s.color, alpha * 0.7));
                gradient.addColorStop(0.5, this.hexToRgba(s.color, alpha * 0.2));
                gradient.addColorStop(1, 'transparent');
                
                ctx.beginPath();
                ctx.arc(s.x, s.y, radius * 4, 0, Math.PI * 2);
                ctx.fillStyle = gradient;
                ctx.fill();
                
                // Core
                ctx.beginPath();
                ctx.arc(s.x, s.y, radius, 0, Math.PI * 2);
                ctx.fillStyle = this.hexToRgba(s.color, alpha);
                ctx.fill();
            }
            
            // Spawn ambient sparks from bottom
            if (this.isVisible && Math.random() < 0.08) {
                const x = Math.random() * width;
                const y = height + 10;
                this.sparks.push({
                    x, y,
                    vx: (Math.random() - 0.5) * 2,
                    vy: -Math.random() * 6 - 3,
                    radius: 1 + Math.random() * 2,
                    color: this.getRandomColor(),
                    life: 800 + Math.random() * 400,
                    maxLife: 1200,
                    gravity: 0.01,
                });
            }
            
            // Draw instruction if few sparks
            if (this.sparks.length < 5) {
                ctx.fillStyle = 'rgba(255, 215, 0, 0.25)';
                ctx.font = '16px "Space Mono", monospace';
                ctx.textAlign = 'center';
                ctx.fillText('CLICK TO SPARK', width / 2, height / 2);
                ctx.fillText('🔥', width / 2, height / 2 + 30);
                ctx.textAlign = 'left';
            }
        };
        
        animate();
    }
    
    drawBorderGlow(ctx, width, height) {
        // Animated gradient border
        const time = Date.now() / 1000;
        const gradient = ctx.createLinearGradient(0, 0, width, 0);
        
        const offset = (Math.sin(time) + 1) / 2;
        gradient.addColorStop(0, `rgba(255, 69, 0, ${0.2 + offset * 0.2})`);
        gradient.addColorStop(0.5, `rgba(255, 215, 0, ${0.1 + offset * 0.1})`);
        gradient.addColorStop(1, `rgba(255, 69, 0, ${0.2 + offset * 0.2})`);
        
        ctx.strokeStyle = gradient;
        ctx.lineWidth = 2;
        
        // Rounded rectangle
        const r = 15;
        ctx.beginPath();
        ctx.moveTo(r, 0);
        ctx.lineTo(width - r, 0);
        ctx.quadraticCurveTo(width, 0, width, r);
        ctx.lineTo(width, height - r);
        ctx.quadraticCurveTo(width, height, width - r, height);
        ctx.lineTo(r, height);
        ctx.quadraticCurveTo(0, height, 0, height - r);
        ctx.lineTo(0, r);
        ctx.quadraticCurveTo(0, 0, r, 0);
        ctx.stroke();
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
