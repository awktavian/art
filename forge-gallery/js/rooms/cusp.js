// ═══════════════════════════════════════════════════════════════════════════
// ROOM II: THE CUSP
// A₃ catastrophe visualization: f(x) = x⁴ + ax² + bx
// Crystal-verified: Mathematical accuracy, interactive parameters
// ═══════════════════════════════════════════════════════════════════════════

import { CONFIG } from '../config.js';

export class CuspRoom {
    constructor(container, soundSystem = null) {
        this.container = container;
        this.sound = soundSystem;
        this.canvas = document.getElementById('cusp-canvas');
        this.ctx = this.canvas ? this.canvas.getContext('2d') : null;
        
        this.paramA = -1;
        this.paramB = 0;
        this.animationId = null;
        this.time = 0;
        
        // UI elements
        this.paramASlider = document.getElementById('cusp-param-a');
        this.paramBSlider = document.getElementById('cusp-param-b');
        this.paramAValue = document.getElementById('cusp-a-value');
        this.paramBValue = document.getElementById('cusp-b-value');
        
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
        
        // Start animation
        this.startAnimation();
        
        console.log('📐 Cusp room initialized');
    }
    
    resizeCanvas() {
        if (this.canvas) {
            this.canvas.width = this.canvas.parentElement?.clientWidth || 800;
            this.canvas.height = 400;
        }
    }
    
    onParameterChange() {
        if (this.sound && this.sound.initialized) {
            this.sound.playCuspTransition(this.paramA);
        }
    }
    
    // The cusp potential: V(x) = x⁴ + ax² + bx
    potential(x, a, b) {
        return Math.pow(x, 4) + a * Math.pow(x, 2) + b * x;
    }
    
    // Derivative: V'(x) = 4x³ + 2ax + b (for finding equilibria)
    derivative(x, a, b) {
        return 4 * Math.pow(x, 3) + 2 * a * x + b;
    }
    
    // Find equilibria (where V'(x) = 0)
    findEquilibria(a, b) {
        const equilibria = [];
        
        // Numerical root finding via bisection/scanning
        const xMin = -3;
        const xMax = 3;
        const step = 0.01;
        
        let prevSign = Math.sign(this.derivative(xMin, a, b));
        
        for (let x = xMin + step; x <= xMax; x += step) {
            const currentSign = Math.sign(this.derivative(x, a, b));
            
            if (currentSign !== prevSign && prevSign !== 0) {
                // Root found between x-step and x
                // Refine with bisection
                let lo = x - step;
                let hi = x;
                for (let i = 0; i < 20; i++) {
                    const mid = (lo + hi) / 2;
                    if (Math.sign(this.derivative(mid, a, b)) === prevSign) {
                        lo = mid;
                    } else {
                        hi = mid;
                    }
                }
                equilibria.push((lo + hi) / 2);
            }
            prevSign = currentSign;
        }
        
        return equilibria;
    }
    
    startAnimation() {
        const animate = () => {
            this.animationId = requestAnimationFrame(animate);
            this.time += CONFIG.CUSP.ANIMATION_SPEED;
            
            if (!this.ctx || !this.canvas) return;
            
            const ctx = this.ctx;
            const width = this.canvas.width;
            const height = this.canvas.height;
            
            if (width === 0 || height === 0) return;
            
            // Clear
            ctx.fillStyle = 'rgba(10, 10, 10, 1)';
            ctx.fillRect(0, 0, width, height);
            
            const padding = CONFIG.CUSP.CANVAS_PADDING;
            const plotWidth = width - padding * 2;
            const plotHeight = height - padding * 2;
            const centerY = padding + plotHeight / 2;
            
            // Draw grid
            ctx.strokeStyle = 'rgba(113, 121, 126, 0.2)';
            ctx.lineWidth = 1;
            
            // Vertical lines
            for (let i = 0; i <= 10; i++) {
                const x = padding + (plotWidth / 10) * i;
                ctx.beginPath();
                ctx.moveTo(x, padding);
                ctx.lineTo(x, height - padding);
                ctx.stroke();
            }
            
            // Horizontal lines
            for (let i = 0; i <= 6; i++) {
                const y = padding + (plotHeight / 6) * i;
                ctx.beginPath();
                ctx.moveTo(padding, y);
                ctx.lineTo(width - padding, y);
                ctx.stroke();
            }
            
            // Draw axes
            ctx.strokeStyle = CONFIG.COLORS.STEEL_LIGHT;
            ctx.lineWidth = 2;
            
            // X-axis
            ctx.beginPath();
            ctx.moveTo(padding, centerY);
            ctx.lineTo(width - padding, centerY);
            ctx.stroke();
            
            // Y-axis
            ctx.beginPath();
            ctx.moveTo(width / 2, padding);
            ctx.lineTo(width / 2, height - padding);
            ctx.stroke();
            
            // Draw the potential curve V(x)
            const xMin = -2.5;
            const xMax = 2.5;
            const yMin = -3;
            const yMax = 6;
            
            const xScale = plotWidth / (xMax - xMin);
            const yScale = plotHeight / (yMax - yMin);
            
            const toCanvasX = (x) => padding + (x - xMin) * xScale;
            const toCanvasY = (y) => centerY - y * (plotHeight / 10);
            
            // Draw potential
            ctx.beginPath();
            ctx.strokeStyle = CONFIG.COLORS.MOLTEN;
            ctx.lineWidth = CONFIG.CUSP.LINE_WIDTH;
            
            let first = true;
            for (let px = 0; px <= plotWidth; px++) {
                const x = xMin + (px / plotWidth) * (xMax - xMin);
                const y = this.potential(x, this.paramA, this.paramB);
                
                // Clamp y
                const canvasY = toCanvasY(y);
                
                if (canvasY > padding - 20 && canvasY < height - padding + 20) {
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
            
            // Draw glow for the curve
            ctx.save();
            ctx.shadowColor = CONFIG.COLORS.MOLTEN;
            ctx.shadowBlur = 15;
            ctx.stroke();
            ctx.restore();
            
            // Find and draw equilibria
            const equilibria = this.findEquilibria(this.paramA, this.paramB);
            
            equilibria.forEach((x, i) => {
                const y = this.potential(x, this.paramA, this.paramB);
                const canvasX = toCanvasX(x);
                const canvasY = toCanvasY(y);
                
                // Second derivative to determine stability
                const secondDeriv = 12 * x * x + 2 * this.paramA;
                const isStable = secondDeriv > 0;
                
                // Draw equilibrium point
                const radius = 8 + Math.sin(this.time * 3 + i) * 2;
                
                if (isStable) {
                    // Stable: filled circle
                    ctx.beginPath();
                    ctx.arc(canvasX, canvasY, radius, 0, Math.PI * 2);
                    ctx.fillStyle = CONFIG.COLORS.SPARK_YELLOW;
                    ctx.fill();
                    
                    // Glow
                    const gradient = ctx.createRadialGradient(canvasX, canvasY, 0, canvasX, canvasY, radius * 2);
                    gradient.addColorStop(0, 'rgba(255, 215, 0, 0.5)');
                    gradient.addColorStop(1, 'transparent');
                    ctx.fillStyle = gradient;
                    ctx.beginPath();
                    ctx.arc(canvasX, canvasY, radius * 2, 0, Math.PI * 2);
                    ctx.fill();
                } else {
                    // Unstable: hollow circle
                    ctx.beginPath();
                    ctx.arc(canvasX, canvasY, radius, 0, Math.PI * 2);
                    ctx.strokeStyle = CONFIG.COLORS.EMBER;
                    ctx.lineWidth = 2;
                    ctx.stroke();
                }
            });
            
            // Draw cusp label
            ctx.fillStyle = CONFIG.COLORS.STEEL_LIGHT;
            ctx.font = '14px "JetBrains Mono", monospace';
            ctx.fillText(`V(x) = x⁴ + (${this.paramA.toFixed(2)})x² + (${this.paramB.toFixed(2)})x`, padding, height - 15);
            
            // Bifurcation indicator
            const discriminant = 8 * Math.pow(this.paramA, 3) + 27 * Math.pow(this.paramB, 2);
            if (this.paramA < 0 && Math.abs(discriminant) < 5) {
                ctx.fillStyle = CONFIG.COLORS.EMBER;
                ctx.fillText('⚠ NEAR BIFURCATION', width - 200, height - 15);
            }
        };
        
        animate();
    }
    
    destroy() {
        if (this.animationId) {
            cancelAnimationFrame(this.animationId);
        }
    }
}

