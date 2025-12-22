// ═══════════════════════════════════════════════════════════════════════════
// ROOM III: THE FOUNDRY
// Molten code visualization
// Crystal-verified: Particle physics, temperature simulation
// ═══════════════════════════════════════════════════════════════════════════

import { CONFIG, METAL_TYPES } from '../config.js';

export class FoundryRoom {
    constructor(container, soundSystem = null) {
        this.container = container;
        this.sound = soundSystem;
        this.canvas = document.getElementById('foundry-canvas');
        this.ctx = this.canvas ? this.canvas.getContext('2d') : null;
        
        this.particles = [];
        this.temperature = 1200;
        this.isPourin = false;
        this.animationId = null;
        this.time = 0;
        
        // UI elements
        this.pourBtn = document.getElementById('pour-btn');
        this.coolBtn = document.getElementById('cool-btn');
        this.tempFill = document.getElementById('temp-fill');
        this.tempValue = document.getElementById('temp-value');
        
        this.init();
    }
    
    init() {
        this.resizeCanvas();
        window.addEventListener('resize', () => this.resizeCanvas());
        
        // Button controls
        if (this.pourBtn) {
            this.pourBtn.addEventListener('click', () => this.pour());
        }
        
        if (this.coolBtn) {
            this.coolBtn.addEventListener('click', () => this.quench());
        }
        
        // Start animation
        this.startAnimation();
        this.updateTemperatureDisplay();
        
        console.log('🔥 Foundry room initialized');
    }
    
    resizeCanvas() {
        if (this.canvas) {
            this.canvas.width = this.canvas.parentElement?.clientWidth || 800;
            this.canvas.height = 400;
        }
    }
    
    pour() {
        this.isPourin = true;
        this.temperature = Math.min(this.temperature + 300, CONFIG.FOUNDRY.MAX_TEMP);
        
        // Create pour stream
        const pourX = (this.canvas?.width || 400) / 2;
        
        for (let i = 0; i < 50; i++) {
            setTimeout(() => {
                this.createMoltenParticle(
                    pourX + (Math.random() - 0.5) * 30,
                    50 + Math.random() * 50
                );
            }, i * 20);
        }
        
        if (this.sound && this.sound.initialized) {
            this.sound.playPour();
        }
        
        setTimeout(() => {
            this.isPourin = false;
        }, 1500);
    }
    
    quench() {
        // Rapid cooling
        const coolingInterval = setInterval(() => {
            this.temperature = Math.max(this.temperature - 50, CONFIG.FOUNDRY.MIN_TEMP);
            this.updateTemperatureDisplay();
            
            if (this.temperature <= CONFIG.FOUNDRY.MIN_TEMP) {
                clearInterval(coolingInterval);
            }
        }, 50);
        
        // Create steam particles
        this.particles.forEach(p => {
            if (p.type === 'molten') {
                p.cooling = true;
            }
        });
        
        // Steam effect
        for (let i = 0; i < 30; i++) {
            setTimeout(() => {
                this.createSteamParticle(
                    Math.random() * (this.canvas?.width || 800),
                    (this.canvas?.height || 400) - 100 + Math.random() * 50
                );
            }, i * 30);
        }
        
        if (this.sound && this.sound.initialized) {
            this.sound.playQuench();
        }
    }
    
    createMoltenParticle(x, y) {
        const metal = METAL_TYPES[Math.floor(Math.random() * METAL_TYPES.length)];
        
        this.particles.push({
            x: x,
            y: y,
            vx: (Math.random() - 0.5) * 2,
            vy: 2 + Math.random() * 3,
            size: 4 + Math.random() * 8,
            color: this.temperatureToColor(this.temperature),
            type: 'molten',
            cooling: false,
            life: 3000,
            maxLife: 3000,
            gravity: 0.15,
            metal: metal,
        });
    }
    
    createSteamParticle(x, y) {
        this.particles.push({
            x: x,
            y: y,
            vx: (Math.random() - 0.5) * 1,
            vy: -2 - Math.random() * 3,
            size: 10 + Math.random() * 20,
            color: '#FFFFFF',
            type: 'steam',
            life: 1500,
            maxLife: 1500,
        });
    }
    
    temperatureToColor(temp) {
        // Physical color temperature mapping
        if (temp > 1300) return '#FFFAF0'; // White hot
        if (temp > 1100) return '#FFD700'; // Yellow
        if (temp > 900) return '#FF8C00'; // Orange
        if (temp > 700) return '#FF4500'; // Red-orange
        if (temp > 500) return '#8B0000'; // Dark red
        return '#434343'; // Cool/grey
    }
    
    updateTemperatureDisplay() {
        if (this.tempValue) {
            this.tempValue.textContent = Math.round(this.temperature);
        }
        
        if (this.tempFill) {
            const percentage = ((this.temperature - CONFIG.FOUNDRY.MIN_TEMP) / 
                (CONFIG.FOUNDRY.MAX_TEMP - CONFIG.FOUNDRY.MIN_TEMP)) * 100;
            this.tempFill.style.width = `${percentage}%`;
            this.tempFill.style.background = `linear-gradient(90deg, 
                ${this.temperatureToColor(CONFIG.FOUNDRY.MIN_TEMP)} 0%, 
                ${this.temperatureToColor(this.temperature)} 100%)`;
        }
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
            
            // Clear with fade
            ctx.fillStyle = 'rgba(10, 10, 10, 0.1)';
            ctx.fillRect(0, 0, width, height);
            
            // Draw crucible/pool at bottom
            const poolHeight = 80;
            const poolGradient = ctx.createLinearGradient(0, height - poolHeight, 0, height);
            poolGradient.addColorStop(0, this.temperatureToColor(this.temperature));
            poolGradient.addColorStop(0.3, this.temperatureToColor(this.temperature * 0.8));
            poolGradient.addColorStop(1, this.temperatureToColor(this.temperature * 0.5));
            
            ctx.fillStyle = poolGradient;
            ctx.beginPath();
            ctx.ellipse(width / 2, height - poolHeight / 2, width / 2 - 50, poolHeight / 2, 0, 0, Math.PI * 2);
            ctx.fill();
            
            // Pool glow
            if (this.temperature > 500) {
                const glowGradient = ctx.createRadialGradient(
                    width / 2, height - poolHeight / 2, 0,
                    width / 2, height - poolHeight / 2, width / 2
                );
                glowGradient.addColorStop(0, `rgba(255, 107, 0, ${(this.temperature - 500) / 1000 * 0.5})`);
                glowGradient.addColorStop(1, 'transparent');
                ctx.fillStyle = glowGradient;
                ctx.fillRect(0, height - 200, width, 200);
            }
            
            // Heat shimmer
            if (this.temperature > 700) {
                ctx.save();
                ctx.globalAlpha = 0.05;
                for (let i = 0; i < 5; i++) {
                    const shimmerY = height - poolHeight - 50 - i * 30;
                    const shimmerOffset = Math.sin(this.time * 3 + i) * 5;
                    
                    ctx.beginPath();
                    ctx.moveTo(100, shimmerY);
                    for (let x = 100; x < width - 100; x += 10) {
                        ctx.lineTo(x, shimmerY + Math.sin(x * 0.05 + this.time * 5) * 3 + shimmerOffset);
                    }
                    ctx.strokeStyle = this.temperatureToColor(this.temperature);
                    ctx.lineWidth = 2;
                    ctx.stroke();
                }
                ctx.restore();
            }
            
            // Update and draw particles
            for (let i = this.particles.length - 1; i >= 0; i--) {
                const p = this.particles[i];
                
                if (p.type === 'molten') {
                    p.x += p.vx;
                    p.y += p.vy;
                    p.vy += p.gravity;
                    
                    // Bounce off pool
                    if (p.y > height - 80) {
                        p.vy *= -0.3;
                        p.y = height - 80;
                        p.vx *= 0.8;
                    }
                    
                    // Cooling
                    if (p.cooling) {
                        p.life -= 50;
                        p.color = this.temperatureToColor(this.temperature * (p.life / p.maxLife));
                    } else {
                        p.life -= 16;
                    }
                } else if (p.type === 'steam') {
                    p.x += p.vx + Math.sin(this.time * 5 + p.y * 0.1) * 0.5;
                    p.y += p.vy;
                    p.vy *= 0.99;
                    p.life -= 16;
                    p.size *= 1.01; // Expand
                }
                
                if (p.life <= 0) {
                    this.particles.splice(i, 1);
                    continue;
                }
                
                const alpha = p.life / p.maxLife;
                
                if (p.type === 'molten') {
                    // Glow
                    const gradient = ctx.createRadialGradient(p.x, p.y, 0, p.x, p.y, p.size * 2);
                    gradient.addColorStop(0, this.hexToRgba(p.color, alpha * 0.8));
                    gradient.addColorStop(1, 'transparent');
                    
                    ctx.beginPath();
                    ctx.arc(p.x, p.y, p.size * 2, 0, Math.PI * 2);
                    ctx.fillStyle = gradient;
                    ctx.fill();
                    
                    ctx.beginPath();
                    ctx.arc(p.x, p.y, p.size, 0, Math.PI * 2);
                    ctx.fillStyle = this.hexToRgba(p.color, alpha);
                    ctx.fill();
                } else if (p.type === 'steam') {
                    ctx.beginPath();
                    ctx.arc(p.x, p.y, p.size, 0, Math.PI * 2);
                    ctx.fillStyle = `rgba(255, 255, 255, ${alpha * 0.3})`;
                    ctx.fill();
                }
            }
            
            // Gradual cooling
            if (!this.isPourin && this.temperature > CONFIG.FOUNDRY.MIN_TEMP) {
                this.temperature = Math.max(this.temperature - 0.5, CONFIG.FOUNDRY.MIN_TEMP);
                this.updateTemperatureDisplay();
            }
        };
        
        animate();
    }
    
    hexToRgba(hex, alpha) {
        if (hex.startsWith('rgba')) return hex;
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

