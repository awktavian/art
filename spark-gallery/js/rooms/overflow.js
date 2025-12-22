// ═══════════════════════════════════════════════════════════════════════════
// ROOM IV: THE OVERFLOW
// Interactive spark generator. Click to spawn ideas. Watch chaos unfold.
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
        
        this.init();
    }
    
    init() {
        this.resizeCanvas();
        window.addEventListener('resize', () => this.resizeCanvas());
        
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
                if (Math.random() < 0.3) {
                    const rect = this.canvas.getBoundingClientRect();
                    const x = e.clientX - rect.left;
                    const y = e.clientY - rect.top;
                    this.spawnSpark(x, y, 0.3);
                }
            });
        }
        
        // Start animation
        this.startAnimation();
    }
    
    resizeCanvas() {
        if (this.canvas) {
            const container = this.canvas.parentElement;
            this.canvas.width = container.clientWidth || 800;
            this.canvas.height = 300;
        }
    }
    
    spawnSparkBurst(x, y) {
        const count = 20 + Math.random() * 30;
        
        for (let i = 0; i < count; i++) {
            const angle = (Math.PI * 2 * i) / count + Math.random() * 0.3;
            const speed = 2 + Math.random() * 8;
            
            this.sparks.push({
                x: x,
                y: y,
                vx: Math.cos(angle) * speed,
                vy: Math.sin(angle) * speed,
                radius: 2 + Math.random() * 4,
                color: this.getRandomColor(),
                life: 1000 + Math.random() * 1000,
                maxLife: 2000,
                gravity: 0.05 + Math.random() * 0.1,
            });
        }
        
        // Play sound
        if (this.sound) {
            this.sound.playSpawn();
        }
    }
    
    spawnSpark(x, y, scale = 1) {
        this.sparks.push({
            x: x,
            y: y,
            vx: (Math.random() - 0.5) * 4 * scale,
            vy: -Math.random() * 3 * scale,
            radius: (1 + Math.random() * 2) * scale,
            color: this.getRandomColor(),
            life: 500 * scale,
            maxLife: 500 * scale,
            gravity: 0.02,
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
            
            if (!this.ctx) return;
            
            const ctx = this.ctx;
            const width = this.canvas.width;
            const height = this.canvas.height;
            
            // Clear with fade
            ctx.fillStyle = 'rgba(10, 10, 10, 0.15)';
            ctx.fillRect(0, 0, width, height);
            
            // Draw border glow
            this.drawBorderGlow(ctx, width, height);
            
            // Update and draw sparks
            for (let i = this.sparks.length - 1; i >= 0; i--) {
                const s = this.sparks[i];
                
                // Update
                s.x += s.vx;
                s.y += s.vy;
                s.vy += s.gravity;
                s.vx *= 0.99;
                s.life -= 16;
                
                // Remove dead sparks
                if (s.life <= 0 || s.y > height) {
                    this.sparks.splice(i, 1);
                    continue;
                }
                
                // Bounce off walls
                if (s.x < 0 || s.x > width) {
                    s.vx *= -0.8;
                    s.x = Math.max(0, Math.min(width, s.x));
                }
                
                // Draw
                const alpha = s.life / s.maxLife;
                ctx.beginPath();
                ctx.arc(s.x, s.y, s.radius * alpha, 0, Math.PI * 2);
                ctx.fillStyle = this.hexToRgba(s.color, alpha);
                ctx.shadowBlur = 15;
                ctx.shadowColor = s.color;
                ctx.fill();
                ctx.shadowBlur = 0;
            }
            
            // Spawn random ambient sparks
            if (Math.random() < 0.05) {
                const x = Math.random() * width;
                const y = height;
                this.spawnSpark(x, y, 0.5);
            }
            
            // Draw instruction if few sparks
            if (this.sparks.length < 10) {
                ctx.fillStyle = 'rgba(255, 215, 0, 0.3)';
                ctx.font = '14px "Space Mono", monospace';
                ctx.textAlign = 'center';
                ctx.fillText('CLICK TO SPARK', width / 2, height / 2);
                ctx.textAlign = 'left';
            }
        };
        
        animate();
    }
    
    drawBorderGlow(ctx, width, height) {
        const gradient = ctx.createLinearGradient(0, 0, width, 0);
        gradient.addColorStop(0, 'rgba(255, 69, 0, 0.3)');
        gradient.addColorStop(0.5, 'rgba(255, 215, 0, 0.1)');
        gradient.addColorStop(1, 'rgba(255, 69, 0, 0.3)');
        
        ctx.strokeStyle = gradient;
        ctx.lineWidth = 2;
        ctx.strokeRect(0, 0, width, height);
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

