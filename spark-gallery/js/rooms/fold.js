// ═══════════════════════════════════════════════════════════════════════════
// ROOM III: THE FOLD
// A₂ catastrophe visualization: f(x) = x³ + ax
// The simplest catastrophe. Where smooth becomes sudden.
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
        
        this.init();
    }
    
    init() {
        this.resizeCanvas();
        window.addEventListener('resize', () => this.resizeCanvas());
        
        // Slider listener
        if (this.slider) {
            this.slider.addEventListener('input', (e) => {
                this.param = parseFloat(e.target.value);
                if (this.valueDisplay) {
                    this.valueDisplay.textContent = this.param.toFixed(2);
                }
                
                // Play sound on significant change
                if (this.sound) {
                    this.sound.playFoldTransition(this.param);
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
            this.canvas.height = 400;
        }
    }
    
    // The fold catastrophe: f(x) = x³ + ax
    // Critical points where f'(x) = 0: 3x² + a = 0
    // Only exists when a < 0
    f(x, a) {
        return x * x * x + a * x;
    }
    
    // Derivative: f'(x) = 3x² + a
    fPrime(x, a) {
        return 3 * x * x + a;
    }
    
    startAnimation() {
        const animate = () => {
            this.animationId = requestAnimationFrame(animate);
            this.time += CONFIG.FOLD.ANIMATION_SPEED;
            this.draw();
        };
        
        animate();
    }
    
    draw() {
        if (!this.ctx) return;
        
        const ctx = this.ctx;
        const width = this.canvas.width;
        const height = this.canvas.height;
        const padding = CONFIG.FOLD.CANVAS_PADDING;
        
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
        ctx.strokeStyle = 'rgba(255, 69, 0, 0.1)';
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
        
        ctx.strokeStyle = 'rgba(255, 215, 0, 0.5)';
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
        
        // Labels
        ctx.fillStyle = CONFIG.COLORS.GOLD;
        ctx.font = '12px "Space Mono", monospace';
        ctx.fillText('x', width - padding - 15, centerY - 10);
        ctx.fillText('f(x)', centerX + 10, padding + 15);
    }
    
    drawFoldCurve(ctx, width, height, padding) {
        const centerX = width / 2;
        const centerY = height / 2;
        const scaleX = (width - 2 * padding) / 4; // x range: -2 to 2
        const scaleY = (height - 2 * padding) / 8; // y range scaled for visibility
        
        ctx.beginPath();
        ctx.strokeStyle = CONFIG.COLORS.FLAME;
        ctx.lineWidth = CONFIG.FOLD.LINE_WIDTH;
        ctx.shadowBlur = 15;
        ctx.shadowColor = CONFIG.COLORS.FLAME;
        
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
        
        // Draw second branch when a < 0 (the fold creates two stable states)
        if (this.param < 0) {
            ctx.beginPath();
            ctx.setLineDash([5, 5]);
            ctx.strokeStyle = CONFIG.COLORS.ELECTRIC;
            ctx.lineWidth = 2;
            
            // Unstable branch (dashed)
            const critX = Math.sqrt(-this.param / 3);
            for (let px = padding; px < width - padding; px++) {
                const x = (px - centerX) / scaleX;
                if (Math.abs(x) < critX) {
                    const y = this.f(x, this.param);
                    const py = centerY - y * scaleY;
                    if (py > padding && py < height - padding) {
                        ctx.lineTo(px, py);
                    }
                }
            }
            ctx.stroke();
            ctx.setLineDash([]);
        }
    }
    
    drawCriticalPoints(ctx, width, height, padding) {
        const centerX = width / 2;
        const centerY = height / 2;
        const scaleX = (width - 2 * padding) / 4;
        const scaleY = (height - 2 * padding) / 8;
        
        // Critical points: x = ±√(-a/3) when a < 0
        const critX = Math.sqrt(-this.param / 3);
        
        // Draw critical points
        [critX, -critX].forEach((x, i) => {
            const y = this.f(x, this.param);
            const px = centerX + x * scaleX;
            const py = centerY - y * scaleY;
            
            // Pulse animation
            const pulse = 1 + 0.2 * Math.sin(this.time * 5 + i);
            
            ctx.beginPath();
            ctx.arc(px, py, 8 * pulse, 0, Math.PI * 2);
            ctx.fillStyle = i === 0 ? CONFIG.COLORS.GOLD : CONFIG.COLORS.ELECTRIC;
            ctx.shadowBlur = 20;
            ctx.shadowColor = ctx.fillStyle;
            ctx.fill();
            ctx.shadowBlur = 0;
            
            // Label
            ctx.fillStyle = CONFIG.COLORS.WHITE_HOT;
            ctx.font = '10px "Space Mono", monospace';
            ctx.fillText(i === 0 ? 'local min' : 'local max', px + 12, py);
        });
    }
    
    drawBifurcationIndicator(ctx, width, height) {
        // Show bifurcation status
        const status = this.param < 0 ? 'TWO STATES' : (this.param === 0 ? 'BIFURCATION!' : 'ONE STATE');
        const color = this.param === 0 ? CONFIG.COLORS.WHITE_HOT : 
                      (this.param < 0 ? CONFIG.COLORS.GOLD : CONFIG.COLORS.FLAME);
        
        ctx.fillStyle = color;
        ctx.font = 'bold 16px "Bebas Neue", sans-serif';
        ctx.textAlign = 'right';
        ctx.fillText(status, width - 20, height - 20);
        ctx.textAlign = 'left';
        
        // Flash at bifurcation
        if (Math.abs(this.param) < 0.1) {
            ctx.fillStyle = `rgba(255, 250, 240, ${0.3 * Math.sin(this.time * 10)})`;
            ctx.fillRect(0, 0, width, height);
        }
    }
    
    drawAnimatedParticle(ctx, width, height, padding) {
        const centerX = width / 2;
        const centerY = height / 2;
        const scaleX = (width - 2 * padding) / 4;
        const scaleY = (height - 2 * padding) / 8;
        
        // Particle oscillates along x
        const x = 1.8 * Math.sin(this.time * 0.5);
        const y = this.f(x, this.param);
        const px = centerX + x * scaleX;
        const py = centerY - y * scaleY;
        
        // Draw particle
        ctx.beginPath();
        ctx.arc(px, py, 6, 0, Math.PI * 2);
        ctx.fillStyle = CONFIG.COLORS.PLASMA;
        ctx.shadowBlur = 25;
        ctx.shadowColor = CONFIG.COLORS.PLASMA;
        ctx.fill();
        ctx.shadowBlur = 0;
        
        // Trail
        for (let i = 1; i < 10; i++) {
            const trailX = 1.8 * Math.sin((this.time - i * 0.05) * 0.5);
            const trailY = this.f(trailX, this.param);
            const tpx = centerX + trailX * scaleX;
            const tpy = centerY - trailY * scaleY;
            
            ctx.beginPath();
            ctx.arc(tpx, tpy, 3 * (1 - i / 10), 0, Math.PI * 2);
            ctx.fillStyle = `rgba(255, 0, 255, ${0.5 * (1 - i / 10)})`;
            ctx.fill();
        }
    }
    
    destroy() {
        if (this.animationId) {
            cancelAnimationFrame(this.animationId);
        }
    }
}

