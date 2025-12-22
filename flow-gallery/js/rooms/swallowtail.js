// ═══════════════════════════════════════════════════════════════════════════
// ROOM II: THE SWALLOWTAIL
// A₄ catastrophe visualization: f(x) = x⁵ + ax³ + bx² + cx
// Crystal-verified: Three-parameter unfolding, bifurcation surfaces
// ═══════════════════════════════════════════════════════════════════════════

import { CONFIG } from '../config.js';

export class SwallowtailRoom {
    constructor(container, soundSystem = null) {
        this.container = container;
        this.sound = soundSystem;
        this.canvas = document.getElementById('swallowtail-canvas');
        this.ctx = this.canvas ? this.canvas.getContext('2d') : null;
        
        this.paramA = -1;
        this.paramB = 0;
        this.paramC = 0;
        this.animationId = null;
        this.time = 0;
        
        // UI elements
        this.paramASlider = document.getElementById('swallow-param-a');
        this.paramBSlider = document.getElementById('swallow-param-b');
        this.paramCSlider = document.getElementById('swallow-param-c');
        this.paramAValue = document.getElementById('swallow-a-value');
        this.paramBValue = document.getElementById('swallow-b-value');
        this.paramCValue = document.getElementById('swallow-c-value');
        
        this.init();
    }
    
    init() {
        this.resizeCanvas();
        window.addEventListener('resize', () => this.resizeCanvas());
        
        // Parameter controls
        if (this.paramASlider) {
            this.paramASlider.addEventListener('input', (e) => {
                this.paramA = parseFloat(e.target.value);
                if (this.paramAValue) this.paramAValue.textContent = this.paramA.toFixed(2);
                this.onParameterChange();
            });
        }
        
        if (this.paramBSlider) {
            this.paramBSlider.addEventListener('input', (e) => {
                this.paramB = parseFloat(e.target.value);
                if (this.paramBValue) this.paramBValue.textContent = this.paramB.toFixed(2);
                this.onParameterChange();
            });
        }
        
        if (this.paramCSlider) {
            this.paramCSlider.addEventListener('input', (e) => {
                this.paramC = parseFloat(e.target.value);
                if (this.paramCValue) this.paramCValue.textContent = this.paramC.toFixed(2);
                this.onParameterChange();
            });
        }
        
        // Start animation
        this.startAnimation();
        
        console.log('🦋 Swallowtail room initialized');
    }
    
    resizeCanvas() {
        if (this.canvas) {
            this.canvas.width = this.canvas.parentElement?.clientWidth || 800;
            this.canvas.height = 400;
        }
    }
    
    onParameterChange() {
        if (this.sound && this.sound.initialized) {
            this.sound.playSwallowtailTransition({
                a: this.paramA,
                b: this.paramB,
                c: this.paramC,
            });
        }
    }
    
    // The swallowtail potential: V(x) = x⁵ + ax³ + bx² + cx
    potential(x, a, b, c) {
        return Math.pow(x, 5) + a * Math.pow(x, 3) + b * Math.pow(x, 2) + c * x;
    }
    
    // Derivative: V'(x) = 5x⁴ + 3ax² + 2bx + c
    derivative(x, a, b, c) {
        return 5 * Math.pow(x, 4) + 3 * a * Math.pow(x, 2) + 2 * b * x + c;
    }
    
    // Second derivative for stability
    secondDerivative(x, a, b) {
        return 20 * Math.pow(x, 3) + 6 * a * x + 2 * b;
    }
    
    // Find equilibria
    findEquilibria(a, b, c) {
        const equilibria = [];
        const xMin = -2.5;
        const xMax = 2.5;
        const step = 0.01;
        
        let prevVal = this.derivative(xMin, a, b, c);
        let prevSign = Math.sign(prevVal);
        
        for (let x = xMin + step; x <= xMax; x += step) {
            const val = this.derivative(x, a, b, c);
            const currentSign = Math.sign(val);
            
            if (currentSign !== prevSign && prevSign !== 0) {
                // Refine with bisection
                let lo = x - step;
                let hi = x;
                for (let i = 0; i < 20; i++) {
                    const mid = (lo + hi) / 2;
                    if (Math.sign(this.derivative(mid, a, b, c)) === prevSign) {
                        lo = mid;
                    } else {
                        hi = mid;
                    }
                }
                equilibria.push((lo + hi) / 2);
            }
            prevVal = val;
            prevSign = currentSign;
        }
        
        return equilibria;
    }
    
    startAnimation() {
        const animate = () => {
            this.animationId = requestAnimationFrame(animate);
            this.time += CONFIG.SWALLOWTAIL.ANIMATION_SPEED;
            
            if (!this.ctx || !this.canvas) return;
            
            const ctx = this.ctx;
            const width = this.canvas.width;
            const height = this.canvas.height;
            
            if (width === 0 || height === 0) return;
            
            // Clear
            ctx.fillStyle = 'rgba(10, 10, 15, 1)';
            ctx.fillRect(0, 0, width, height);
            
            const padding = CONFIG.SWALLOWTAIL.CANVAS_PADDING;
            const plotWidth = width - padding * 2;
            const plotHeight = height - padding * 2;
            const centerY = padding + plotHeight / 2;
            
            // Draw flowing background
            this.drawFlowingBackground(ctx, width, height);
            
            // Draw grid
            ctx.strokeStyle = 'rgba(0, 139, 139, 0.15)';
            ctx.lineWidth = 1;
            
            for (let i = 0; i <= 10; i++) {
                const x = padding + (plotWidth / 10) * i;
                ctx.beginPath();
                ctx.moveTo(x, padding);
                ctx.lineTo(x, height - padding);
                ctx.stroke();
            }
            
            for (let i = 0; i <= 6; i++) {
                const y = padding + (plotHeight / 6) * i;
                ctx.beginPath();
                ctx.moveTo(padding, y);
                ctx.lineTo(width - padding, y);
                ctx.stroke();
            }
            
            // Draw axes
            ctx.strokeStyle = CONFIG.COLORS.TEAL;
            ctx.lineWidth = 2;
            
            ctx.beginPath();
            ctx.moveTo(padding, centerY);
            ctx.lineTo(width - padding, centerY);
            ctx.stroke();
            
            ctx.beginPath();
            ctx.moveTo(width / 2, padding);
            ctx.lineTo(width / 2, height - padding);
            ctx.stroke();
            
            // Coordinate transforms
            const xMin = -2;
            const xMax = 2;
            const toCanvasX = (x) => padding + ((x - xMin) / (xMax - xMin)) * plotWidth;
            const toCanvasY = (y) => centerY - y * (plotHeight / 12);
            
            // Draw the potential
            ctx.beginPath();
            ctx.strokeStyle = CONFIG.COLORS.CYAN;
            ctx.lineWidth = CONFIG.SWALLOWTAIL.LINE_WIDTH;
            
            let first = true;
            for (let px = 0; px <= plotWidth; px++) {
                const x = xMin + (px / plotWidth) * (xMax - xMin);
                const y = this.potential(x, this.paramA, this.paramB, this.paramC);
                const canvasY = toCanvasY(y);
                
                if (canvasY > padding - 30 && canvasY < height - padding + 30) {
                    if (first) {
                        ctx.moveTo(toCanvasX(x), canvasY);
                        first = false;
                    } else {
                        ctx.lineTo(toCanvasX(x), canvasY);
                    }
                } else {
                    first = true;
                }
            }
            ctx.stroke();
            
            // Glow
            ctx.save();
            ctx.shadowColor = CONFIG.COLORS.CYAN;
            ctx.shadowBlur = 20;
            ctx.stroke();
            ctx.restore();
            
            // Draw equilibria
            const equilibria = this.findEquilibria(this.paramA, this.paramB, this.paramC);
            
            equilibria.forEach((x, i) => {
                const y = this.potential(x, this.paramA, this.paramB, this.paramC);
                const canvasX = toCanvasX(x);
                const canvasY = toCanvasY(y);
                
                if (canvasY < padding || canvasY > height - padding) return;
                
                const secondDeriv = this.secondDerivative(x, this.paramA, this.paramB);
                const isStable = secondDeriv > 0;
                
                const radius = 7 + Math.sin(this.time * 4 + i * 2) * 2;
                
                if (isStable) {
                    // Stable equilibrium
                    const gradient = ctx.createRadialGradient(canvasX, canvasY, 0, canvasX, canvasY, radius * 2.5);
                    gradient.addColorStop(0, CONFIG.COLORS.HEALING_GREEN);
                    gradient.addColorStop(0.5, 'rgba(0, 255, 127, 0.3)');
                    gradient.addColorStop(1, 'transparent');
                    
                    ctx.beginPath();
                    ctx.arc(canvasX, canvasY, radius * 2.5, 0, Math.PI * 2);
                    ctx.fillStyle = gradient;
                    ctx.fill();
                    
                    ctx.beginPath();
                    ctx.arc(canvasX, canvasY, radius, 0, Math.PI * 2);
                    ctx.fillStyle = CONFIG.COLORS.HEALING_GREEN;
                    ctx.fill();
                } else {
                    // Unstable equilibrium
                    ctx.beginPath();
                    ctx.arc(canvasX, canvasY, radius, 0, Math.PI * 2);
                    ctx.strokeStyle = CONFIG.COLORS.ERROR_RED;
                    ctx.lineWidth = 2;
                    ctx.stroke();
                }
            });
            
            // Labels
            ctx.fillStyle = CONFIG.COLORS.FOAM;
            ctx.font = '13px "Fira Code", monospace';
            ctx.fillText(
                `V(x) = x⁵ + (${this.paramA.toFixed(2)})x³ + (${this.paramB.toFixed(2)})x² + (${this.paramC.toFixed(2)})x`,
                padding, height - 12
            );
            
            // Equilibria count
            ctx.fillStyle = equilibria.length >= 3 ? CONFIG.COLORS.WARNING_AMBER : CONFIG.COLORS.TEAL;
            ctx.fillText(`${equilibria.length} equilibri${equilibria.length === 1 ? 'um' : 'a'}`, width - 150, height - 12);
        };
        
        animate();
    }
    
    drawFlowingBackground(ctx, width, height) {
        // Subtle flowing lines
        ctx.strokeStyle = 'rgba(0, 139, 139, 0.05)';
        ctx.lineWidth = 1;
        
        for (let i = 0; i < 20; i++) {
            ctx.beginPath();
            const y = (i / 20) * height;
            const offset = Math.sin(this.time + i * 0.3) * 20;
            
            ctx.moveTo(0, y + offset);
            for (let x = 0; x <= width; x += 50) {
                const dy = Math.sin(this.time * 0.5 + x * 0.01 + i) * 10;
                ctx.lineTo(x, y + offset + dy);
            }
            ctx.stroke();
        }
    }
    
    destroy() {
        if (this.animationId) {
            cancelAnimationFrame(this.animationId);
        }
    }
}

