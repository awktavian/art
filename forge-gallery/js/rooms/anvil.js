// ═══════════════════════════════════════════════════════════════════════════
// ROOM I: THE ANVIL
// Where raw ideas become solid code
// Crystal-verified: Canvas sparks, shake effect, strike counter
// ═══════════════════════════════════════════════════════════════════════════

import { CONFIG } from '../config.js';

export class AnvilRoom {
    constructor(container, soundSystem = null) {
        this.container = container;
        this.sound = soundSystem;
        this.canvas = document.getElementById('anvil-canvas');
        this.ctx = this.canvas ? this.canvas.getContext('2d') : null;
        this.anvilBlock = document.getElementById('anvil-block');
        this.strikeCountEl = document.getElementById('strike-count');
        
        this.sparks = [];
        this.strikeCount = 0;
        this.animationId = null;
        
        this.init();
    }
    
    init() {
        this.resizeCanvas();
        window.addEventListener('resize', () => this.resizeCanvas());
        
        // Click to strike
        if (this.anvilBlock) {
            this.anvilBlock.addEventListener('click', (e) => {
                this.strike(e);
            });
        }
        
        // Start animation
        this.startAnimation();
        
        console.log('🔨 Anvil room initialized');
    }
    
    resizeCanvas() {
        if (this.canvas) {
            this.canvas.width = window.innerWidth;
            this.canvas.height = window.innerHeight;
        }
    }
    
    strike(event) {
        this.strikeCount++;
        if (this.strikeCountEl) {
            this.strikeCountEl.textContent = this.strikeCount;
        }
        
        // Get click position
        const rect = this.anvilBlock.getBoundingClientRect();
        const x = rect.left + rect.width / 2;
        const y = rect.top + rect.height / 2;
        
        // Create sparks
        this.createSparks(x, y);
        
        // Shake effect
        this.shakeAnvil();
        
        // Play sound
        if (this.sound && this.sound.initialized) {
            this.sound.playStrike();
        }
        
        // Metal piece transformation
        this.transformMetal();
    }
    
    createSparks(x, y) {
        const count = CONFIG.ANVIL.SPARK_COUNT;
        const colors = [
            CONFIG.COLORS.WHITE_HOT,
            CONFIG.COLORS.SPARK_YELLOW,
            CONFIG.COLORS.MOLTEN,
            CONFIG.COLORS.FORGE_ORANGE,
        ];
        
        for (let i = 0; i < count; i++) {
            const angle = (Math.PI * 2 * i) / count + (Math.random() - 0.5) * 0.5;
            const speed = 5 + Math.random() * 15;
            
            this.sparks.push({
                x: x,
                y: y,
                vx: Math.cos(angle) * speed,
                vy: Math.sin(angle) * speed - Math.random() * 5,
                size: 1 + Math.random() * 4,
                color: colors[Math.floor(Math.random() * colors.length)],
                life: 800 + Math.random() * 400,
                maxLife: 1200,
                gravity: 0.15,
            });
        }
    }
    
    shakeAnvil() {
        if (!this.anvilBlock) return;
        
        const intensity = CONFIG.ANVIL.SHAKE_INTENSITY;
        this.anvilBlock.style.transform = `translate(${(Math.random() - 0.5) * intensity}px, ${(Math.random() - 0.5) * intensity}px)`;
        
        setTimeout(() => {
            this.anvilBlock.style.transform = 'translate(0, 0)';
        }, 50);
    }
    
    transformMetal() {
        const metal = this.anvilBlock?.querySelector('.metal-piece');
        if (!metal) return;
        
        // Progressive transformation based on strikes
        const progress = Math.min(this.strikeCount / 20, 1);
        const scale = 1 - progress * 0.3;
        const width = 60 + progress * 40;
        
        metal.style.transform = `scaleY(${scale})`;
        metal.style.width = `${width}px`;
        
        // Color change from molten to cooled
        if (this.strikeCount > 15) {
            metal.style.background = `linear-gradient(180deg, ${CONFIG.COLORS.STEEL} 0%, ${CONFIG.COLORS.IRON} 100%)`;
        }
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
            ctx.fillStyle = 'rgba(10, 10, 10, 0.15)';
            ctx.fillRect(0, 0, width, height);
            
            // Update and draw sparks
            for (let i = this.sparks.length - 1; i >= 0; i--) {
                const s = this.sparks[i];
                
                // Physics
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
                
                const alpha = s.life / s.maxLife;
                const size = s.size * alpha;
                
                // Glow
                const gradient = ctx.createRadialGradient(s.x, s.y, 0, s.x, s.y, size * 3);
                gradient.addColorStop(0, this.hexToRgba(s.color, alpha * 0.8));
                gradient.addColorStop(1, 'transparent');
                
                ctx.beginPath();
                ctx.arc(s.x, s.y, size * 3, 0, Math.PI * 2);
                ctx.fillStyle = gradient;
                ctx.fill();
                
                // Core
                ctx.beginPath();
                ctx.arc(s.x, s.y, size, 0, Math.PI * 2);
                ctx.fillStyle = this.hexToRgba(s.color, alpha);
                ctx.fill();
            }
            
            // Ambient forge glow at bottom
            const ambientGradient = ctx.createLinearGradient(0, height - 100, 0, height);
            ambientGradient.addColorStop(0, 'transparent');
            ambientGradient.addColorStop(1, 'rgba(255, 107, 0, 0.1)');
            ctx.fillStyle = ambientGradient;
            ctx.fillRect(0, height - 100, width, 100);
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

