// ═══════════════════════════════════════════════════════════════════════════
// ROOM IV: THE ADAPTATION
// Flow's psychology and the art of debugging
// Crystal-verified: Psychological profile, water ripple effect
// ═══════════════════════════════════════════════════════════════════════════

import { CONFIG } from '../config.js';

export class AdaptationRoom {
    constructor(container, soundSystem = null) {
        this.container = container;
        this.sound = soundSystem;
        this.canvas = null;
        this.ctx = null;
        this.animationId = null;
        this.time = 0;
        this.ripples = [];
        
        this.init();
    }
    
    init() {
        // Animate psychology cards on scroll
        this.setupScrollAnimations();
        
        // Trait hover effects
        this.setupTraitEffects();
        
        // Start water ripple background
        this.startWaterEffect();
        
        console.log('🧘 Adaptation room initialized');
    }
    
    setupScrollAnimations() {
        const cards = this.container?.querySelectorAll('.psych-card');
        
        if (!cards || cards.length === 0) return;
        
        const observer = new IntersectionObserver((entries) => {
            entries.forEach((entry, index) => {
                if (entry.isIntersecting) {
                    setTimeout(() => {
                        entry.target.classList.add('visible');
                    }, index * 150);
                }
            });
        }, { threshold: 0.2 });
        
        cards.forEach(card => observer.observe(card));
    }
    
    setupTraitEffects() {
        const traits = this.container?.querySelectorAll('.trait');
        
        if (!traits || traits.length === 0) return;
        
        traits.forEach(trait => {
            trait.addEventListener('mouseenter', (e) => {
                const rect = trait.getBoundingClientRect();
                const containerRect = this.container.getBoundingClientRect();
                
                this.createRipple(
                    rect.left - containerRect.left + rect.width / 2,
                    rect.top - containerRect.top + rect.height / 2
                );
                
                if (this.sound && this.sound.initialized) {
                    this.sound.playDroplet();
                }
            });
        });
    }
    
    createRipple(x, y) {
        this.ripples.push({
            x: x,
            y: y,
            radius: 0,
            maxRadius: 150,
            alpha: 0.5,
        });
    }
    
    startWaterEffect() {
        const container = this.container?.querySelector('.adaptation-content');
        if (!container) return;
        
        // Create canvas for water effect
        this.canvas = document.createElement('canvas');
        this.canvas.className = 'water-effect-canvas';
        this.canvas.style.cssText = `
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            pointer-events: none;
            opacity: 0.2;
        `;
        container.style.position = 'relative';
        container.insertBefore(this.canvas, container.firstChild);
        
        this.ctx = this.canvas.getContext('2d');
        
        const resize = () => {
            this.canvas.width = container.clientWidth;
            this.canvas.height = container.clientHeight;
        };
        resize();
        window.addEventListener('resize', resize);
        
        // Click to create ripples
        container.addEventListener('click', (e) => {
            const rect = container.getBoundingClientRect();
            this.createRipple(e.clientX - rect.left, e.clientY - rect.top);
            
            if (this.sound && this.sound.initialized) {
                this.sound.playDroplet();
            }
        });
        
        const animate = () => {
            this.animationId = requestAnimationFrame(animate);
            this.time += 0.016;
            
            if (!this.ctx || this.canvas.width === 0) return;
            
            const ctx = this.ctx;
            const width = this.canvas.width;
            const height = this.canvas.height;
            
            // Clear
            ctx.clearRect(0, 0, width, height);
            
            // Draw subtle wave pattern
            ctx.strokeStyle = CONFIG.COLORS.TEAL;
            ctx.lineWidth = 1;
            
            for (let i = 0; i < 15; i++) {
                ctx.beginPath();
                ctx.globalAlpha = 0.1 - i * 0.006;
                
                const y = (i / 15) * height;
                const amplitude = 5 + Math.sin(this.time + i * 0.5) * 3;
                const frequency = 0.02 + i * 0.001;
                
                ctx.moveTo(0, y);
                for (let x = 0; x <= width; x += 10) {
                    const dy = Math.sin(x * frequency + this.time * 2 + i) * amplitude;
                    ctx.lineTo(x, y + dy);
                }
                ctx.stroke();
            }
            
            ctx.globalAlpha = 1;
            
            // Draw ripples
            for (let i = this.ripples.length - 1; i >= 0; i--) {
                const r = this.ripples[i];
                r.radius += 2;
                r.alpha = 0.5 * (1 - r.radius / r.maxRadius);
                
                if (r.radius >= r.maxRadius) {
                    this.ripples.splice(i, 1);
                    continue;
                }
                
                ctx.beginPath();
                ctx.arc(r.x, r.y, r.radius, 0, Math.PI * 2);
                ctx.strokeStyle = `rgba(0, 206, 209, ${r.alpha})`;
                ctx.lineWidth = 2;
                ctx.stroke();
                
                // Inner ring
                ctx.beginPath();
                ctx.arc(r.x, r.y, r.radius * 0.7, 0, Math.PI * 2);
                ctx.strokeStyle = `rgba(0, 255, 255, ${r.alpha * 0.5})`;
                ctx.lineWidth = 1;
                ctx.stroke();
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

