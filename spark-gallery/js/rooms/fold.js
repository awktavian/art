// ═══════════════════════════════════════════════════════════════════════════
// ROOM III: THE FOLD
// A₂ catastrophe visualization: f(x) = x³ + ax
// The simplest catastrophe. Where smooth becomes sudden.
// Crystal-verified: Canvas rendering, slider interaction, bifurcation display
// ═══════════════════════════════════════════════════════════════════════════

import { CONFIG } from '../config.js';

export class FoldRoom {
    constructor(container, soundSystem = null) {
        this.container = container;
        this.sound = soundSystem;
        this.canvas = document.getElementById('fold-canvas');
        this.ctx = this.canvas ? this.canvas.getContext('2d') : null;
        this.slider = document.getElementById('fold-param');
        this.valueDisplay = document.getElementById('fold-param-value');
        
        this.param = -1; // Control parameter 'a'
        this.animationId = null;
        this.time = 0;
        this.lastSoundTime = 0;
        
        this.init();
    }
    
    init() {
        this.resizeCanvas();
        window.addEventListener('resize', () => this.resizeCanvas());
        
        // Slider listener with debounced sound
        if (this.slider) {
            this.slider.addEventListener('input', (e) => {
                this.param = parseFloat(e.target.value);
                if (this.valueDisplay) {
                    this.valueDisplay.textContent = this.param.toFixed(2);
                }
                
                // Play sound on significant change (throttled)
                const now = Date.now();
                if (this.sound && this.sound.initialized && now - this.lastSoundTime > 100) {
                    this.sound.playFoldTransition(this.param);
                    this.lastSoundTime = now;
                }
            });
        }
        
        // Start animation
        this.startAnimation();
        
        console.log('📐 Fold room initialized');
    }
    
    resizeCanvas() {
        if (this.canvas) {
            const container = this.canvas.parentElement;
            this.canvas.width = Math.max(container?.clientWidth || 800, 400);
            this.canvas.height = 400;
        }
    }
    
    // The fold catastrophe: f(x) = x³ + ax
    f(x, a) {
        return x * x * x + a * x;
    }
    
    startAnimation() {
        const animate = () => {
            this.animationId = requestAnimationFrame(animate);
            this.time += 0.02;
            this.draw();
        };
        
        animate();
    }
    
    draw() {
        if (!this.ctx || !this.canvas) return;
        
        const ctx = this.ctx;
        const width = this.canvas.width;
        const height = this.canvas.height;
        const padding = 50;
        
        if (width === 0 || height === 0) return;
        
        // Clear
        ctx.fillStyle = '#050505';
        ctx.fillRect(0, 0, width, height);
        
        // Draw grid
        this.drawGrid(ctx, width, height, padding);
        
        // Draw axes
        this.drawAxes(ctx, width, height, padding);
        
        // Draw the fold curve
        this.drawFoldCurve(ctx, width, height, padding);
        
        // Draw critical points (when a < 0)
        if (this.param < 0) {
            this.drawCriticalPoints(ctx, width, height, padding);
        }
        
        // Draw bifurcation indicator
        this.drawBifurcationIndicator(ctx, width, height);
        
        // Draw animated particle following the curve
        this.drawAnimatedParticle(ctx, width, height, padding);
    }
    
    drawGrid(ctx, width, height, padding) {
        const gridSpacing = 50;
        ctx.strokeStyle = 'rgba(255, 69, 0, 0.08)';
        ctx.lineWidth = 1;
        
        // Vertical lines
        for (let x = padding; x < width - padding; x += gridSpacing) {
            ctx.beginPath();
            ctx.moveTo(x, padding);
            ctx.lineTo(x, height - padding);
            ctx.stroke();
        }
        
        // Horizontal lines
        for (let y = padding; y < height - padding; y += gridSpacing) {
            ctx.beginPath();
            ctx.moveTo(padding, y);
            ctx.lineTo(width - padding, y);
            ctx.stroke();
        }
    }
    
    drawAxes(ctx, width, height, padding) {
        const centerX = width / 2;
        const centerY = height / 2;
        
        ctx.strokeStyle = 'rgba(255, 215, 0, 0.4)';
        ctx.lineWidth = 2;
        
        // X axis
        ctx.beginPath();
        ctx.moveTo(padding, centerY);
        ctx.lineTo(width - padding, centerY);
        ctx.stroke();
        
        // Y axis
        ctx.beginPath();
        ctx.moveTo(centerX, padding);
        ctx.lineTo(centerX, height - padding);
        ctx.stroke();
        
        // Arrow heads
        ctx.fillStyle = 'rgba(255, 215, 0, 0.4)';
        
        // X arrow
        ctx.beginPath();
        ctx.moveTo(width - padding, centerY);
        ctx.lineTo(width - padding - 10, centerY - 5);
        ctx.lineTo(width - padding - 10, centerY + 5);
        ctx.fill();
        
        // Y arrow
        ctx.beginPath();
        ctx.moveTo(centerX, padding);
        ctx.lineTo(centerX - 5, padding + 10);
        ctx.lineTo(centerX + 5, padding + 10);
        ctx.fill();
        
        // Labels
        ctx.fillStyle = CONFIG.COLORS.GOLD;
        ctx.font = 'bold 14px "Space Mono", monospace';
        ctx.fillText('x', width - padding - 15, centerY - 12);
        ctx.fillText('f(x)', centerX + 12, padding + 18);
    }
    
    drawFoldCurve(ctx, width, height, padding) {
        const centerX = width / 2;
        const centerY = height / 2;
        const scaleX = (width - 2 * padding) / 4;
        const scaleY = (height - 2 * padding) / 6;
        
        // Main curve with glow
        ctx.shadowBlur = 20;
        ctx.shadowColor = CONFIG.COLORS.FLAME;
        
        ctx.beginPath();
        ctx.strokeStyle = CONFIG.COLORS.FLAME;
        ctx.lineWidth = 3;
        
        let started = false;
        for (let px = padding; px < width - padding; px++) {
            const x = (px - centerX) / scaleX;
            const y = this.f(x, this.param);
            const py = centerY - y * scaleY;
            
            if (py > padding && py < height - padding) {
                if (!started) {
                    ctx.moveTo(px, py);
                    started = true;
                } else {
                    ctx.lineTo(px, py);
                }
            }
        }
        
        ctx.stroke();
        ctx.shadowBlur = 0;
        
        // Gradient overlay for depth
        const gradient = ctx.createLinearGradient(padding, 0, width - padding, 0);
        gradient.addColorStop(0, 'rgba(255, 69, 0, 0.3)');
        gradient.addColorStop(0.5, 'rgba(255, 215, 0, 0.5)');
        gradient.addColorStop(1, 'rgba(255, 69, 0, 0.3)');
        
        ctx.beginPath();
        ctx.strokeStyle = gradient;
        ctx.lineWidth = 1.5;
        started = false;
        
        for (let px = padding; px < width - padding; px++) {
            const x = (px - centerX) / scaleX;
            const y = this.f(x, this.param);
            const py = centerY - y * scaleY;
            
            if (py > padding && py < height - padding) {
                if (!started) {
                    ctx.moveTo(px, py);
                    started = true;
                } else {
                    ctx.lineTo(px, py);
                }
            }
        }
        
        ctx.stroke();
    }
    
    drawCriticalPoints(ctx, width, height, padding) {
        const centerX = width / 2;
        const centerY = height / 2;
        const scaleX = (width - 2 * padding) / 4;
        const scaleY = (height - 2 * padding) / 6;
        
        // Critical points: x = ±√(-a/3) when a < 0
        const critX = Math.sqrt(-this.param / 3);
        
        // Draw critical points
        [critX, -critX].forEach((x, i) => {
            const y = this.f(x, this.param);
            const px = centerX + x * scaleX;
            const py = centerY - y * scaleY;
            
            // Pulse animation
            const pulse = 1 + 0.25 * Math.sin(this.time * 4 + i * Math.PI);
            
            // Glow
            const gradient = ctx.createRadialGradient(px, py, 0, px, py, 25 * pulse);
            gradient.addColorStop(0, i === 0 ? 'rgba(255, 215, 0, 0.6)' : 'rgba(0, 255, 255, 0.6)');
            gradient.addColorStop(1, 'transparent');
            
            ctx.beginPath();
            ctx.arc(px, py, 25 * pulse, 0, Math.PI * 2);
            ctx.fillStyle = gradient;
            ctx.fill();
            
            // Core
            ctx.beginPath();
            ctx.arc(px, py, 8 * pulse, 0, Math.PI * 2);
            ctx.fillStyle = i === 0 ? CONFIG.COLORS.GOLD : CONFIG.COLORS.ELECTRIC;
            ctx.fill();
            
            // Label
            ctx.fillStyle = '#FFFFFF';
            ctx.font = '11px "Space Mono", monospace';
            ctx.fillText(i === 0 ? 'min' : 'max', px + 15, py + 4);
        });
    }
    
    drawBifurcationIndicator(ctx, width, height) {
        // Show bifurcation status
        const atBifurcation = Math.abs(this.param) < 0.1;
        const status = this.param < -0.1 ? 'TWO STABLE STATES' : 
                      (atBifurcation ? '⚡ BIFURCATION ⚡' : 'ONE STABLE STATE');
        const color = atBifurcation ? CONFIG.COLORS.WHITE_HOT : 
                      (this.param < 0 ? CONFIG.COLORS.GOLD : CONFIG.COLORS.FLAME);
        
        ctx.fillStyle = color;
        ctx.font = 'bold 14px "Bebas Neue", sans-serif';
        ctx.textAlign = 'right';
        ctx.letterSpacing = '0.1em';
        
        if (atBifurcation) {
            ctx.shadowBlur = 15;
            ctx.shadowColor = CONFIG.COLORS.WHITE_HOT;
        }
        
        ctx.fillText(status, width - 25, height - 25);
        ctx.textAlign = 'left';
        ctx.shadowBlur = 0;
        
        // Flash at bifurcation
        if (atBifurcation) {
            const flash = Math.abs(Math.sin(this.time * 8)) * 0.15;
            ctx.fillStyle = `rgba(255, 250, 240, ${flash})`;
            ctx.fillRect(0, 0, width, height);
        }
    }
    
    drawAnimatedParticle(ctx, width, height, padding) {
        const centerX = width / 2;
        const centerY = height / 2;
        const scaleX = (width - 2 * padding) / 4;
        const scaleY = (height - 2 * padding) / 6;
        
        // Particle oscillates along x
        const x = 1.8 * Math.sin(this.time * 0.4);
        const y = this.f(x, this.param);
        const px = centerX + x * scaleX;
        const py = centerY - y * scaleY;
        
        // Trail
        for (let i = 1; i < 12; i++) {
            const trailX = 1.8 * Math.sin((this.time - i * 0.04) * 0.4);
            const trailY = this.f(trailX, this.param);
            const tpx = centerX + trailX * scaleX;
            const tpy = centerY - trailY * scaleY;
            
            const alpha = 0.5 * (1 - i / 12);
            ctx.beginPath();
            ctx.arc(tpx, tpy, 4 * (1 - i / 12), 0, Math.PI * 2);
            ctx.fillStyle = `rgba(255, 0, 255, ${alpha})`;
            ctx.fill();
        }
        
        // Draw particle with glow
        ctx.shadowBlur = 20;
        ctx.shadowColor = CONFIG.COLORS.PLASMA;
        
        ctx.beginPath();
        ctx.arc(px, py, 7, 0, Math.PI * 2);
        ctx.fillStyle = CONFIG.COLORS.PLASMA;
        ctx.fill();
        
        ctx.shadowBlur = 0;
    }
    
    destroy() {
        if (this.animationId) {
            cancelAnimationFrame(this.animationId);
        }
    }
}
