/**
 * Particles System — Bioluminescent Data Flow
 * 
 * Canvas-based particle system for visualizing data flowing
 * between browser nodes in the swarm.
 * 
 * GPU-accelerated via requestAnimationFrame.
 */

class ParticleSystem {
    constructor(canvasId) {
        this.canvas = document.getElementById(canvasId);
        if (!this.canvas) return;
        
        this.ctx = this.canvas.getContext('2d');
        this.particles = [];
        this.connections = [];
        this.mousePos = { x: 0, y: 0 };
        this.isVisible = true;
        this.animationId = null;
        
        // Colors
        this.colors = {
            cyan: { r: 0, g: 245, b: 212 },
            magenta: { r: 241, g: 91, b: 181 },
            violet: { r: 155, g: 93, b: 229 },
            amber: { r: 254, g: 228, b: 64 }
        };
        
        this.init();
    }
    
    init() {
        this.resize();
        this.createParticles();
        this.bindEvents();
        this.animate();
    }
    
    resize() {
        const dpr = window.devicePixelRatio || 1;
        this.canvas.width = window.innerWidth * dpr;
        this.canvas.height = window.innerHeight * dpr;
        this.canvas.style.width = window.innerWidth + 'px';
        this.canvas.style.height = window.innerHeight + 'px';
        this.ctx.scale(dpr, dpr);
        
        this.width = window.innerWidth;
        this.height = window.innerHeight;
    }
    
    createParticles() {
        const particleCount = Math.min(150, Math.floor((this.width * this.height) / 15000));
        this.particles = [];
        
        for (let i = 0; i < particleCount; i++) {
            this.particles.push(this.createParticle());
        }
    }
    
    createParticle(x, y) {
        const colorKeys = Object.keys(this.colors);
        const colorKey = colorKeys[Math.floor(Math.random() * colorKeys.length)];
        const color = this.colors[colorKey];
        
        return {
            x: x ?? Math.random() * this.width,
            y: y ?? Math.random() * this.height,
            vx: (Math.random() - 0.5) * 0.5,
            vy: (Math.random() - 0.5) * 0.5,
            radius: Math.random() * 2 + 1,
            color: color,
            alpha: Math.random() * 0.5 + 0.2,
            pulsePhase: Math.random() * Math.PI * 2,
            pulseSpeed: 0.02 + Math.random() * 0.02
        };
    }
    
    bindEvents() {
        window.addEventListener('resize', () => {
            this.resize();
            this.createParticles();
        });
        
        window.addEventListener('mousemove', (e) => {
            this.mousePos.x = e.clientX;
            this.mousePos.y = e.clientY;
        });
        
        // Visibility API - pause when tab is hidden
        document.addEventListener('visibilitychange', () => {
            this.isVisible = !document.hidden;
            if (this.isVisible && !this.animationId) {
                this.animate();
            }
        });
        
        // Intersection Observer for performance
        const observer = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                this.isVisible = entry.isIntersecting;
            });
        });
        
        observer.observe(this.canvas);
    }
    
    updateParticle(particle) {
        // Update position
        particle.x += particle.vx;
        particle.y += particle.vy;
        
        // Wrap around edges
        if (particle.x < 0) particle.x = this.width;
        if (particle.x > this.width) particle.x = 0;
        if (particle.y < 0) particle.y = this.height;
        if (particle.y > this.height) particle.y = 0;
        
        // Mouse interaction - gentle attraction
        const dx = this.mousePos.x - particle.x;
        const dy = this.mousePos.y - particle.y;
        const dist = Math.sqrt(dx * dx + dy * dy);
        
        if (dist < 200 && dist > 0) {
            const force = (200 - dist) / 200 * 0.01;
            particle.vx += (dx / dist) * force;
            particle.vy += (dy / dist) * force;
        }
        
        // Damping
        particle.vx *= 0.99;
        particle.vy *= 0.99;
        
        // Pulse animation
        particle.pulsePhase += particle.pulseSpeed;
        const pulseFactor = 0.5 + Math.sin(particle.pulsePhase) * 0.5;
        particle.currentAlpha = particle.alpha * (0.5 + pulseFactor * 0.5);
    }
    
    drawParticle(particle) {
        const { r, g, b } = particle.color;
        
        // Glow effect
        const gradient = this.ctx.createRadialGradient(
            particle.x, particle.y, 0,
            particle.x, particle.y, particle.radius * 3
        );
        gradient.addColorStop(0, `rgba(${r}, ${g}, ${b}, ${particle.currentAlpha})`);
        gradient.addColorStop(0.5, `rgba(${r}, ${g}, ${b}, ${particle.currentAlpha * 0.3})`);
        gradient.addColorStop(1, `rgba(${r}, ${g}, ${b}, 0)`);
        
        this.ctx.beginPath();
        this.ctx.arc(particle.x, particle.y, particle.radius * 3, 0, Math.PI * 2);
        this.ctx.fillStyle = gradient;
        this.ctx.fill();
        
        // Core
        this.ctx.beginPath();
        this.ctx.arc(particle.x, particle.y, particle.radius, 0, Math.PI * 2);
        this.ctx.fillStyle = `rgba(${r}, ${g}, ${b}, ${particle.currentAlpha})`;
        this.ctx.fill();
    }
    
    drawConnections() {
        const connectionDistance = 120;
        
        for (let i = 0; i < this.particles.length; i++) {
            for (let j = i + 1; j < this.particles.length; j++) {
                const p1 = this.particles[i];
                const p2 = this.particles[j];
                
                const dx = p1.x - p2.x;
                const dy = p1.y - p2.y;
                const dist = Math.sqrt(dx * dx + dy * dy);
                
                if (dist < connectionDistance) {
                    const alpha = (1 - dist / connectionDistance) * 0.15;
                    
                    // Use average color
                    const r = Math.floor((p1.color.r + p2.color.r) / 2);
                    const g = Math.floor((p1.color.g + p2.color.g) / 2);
                    const b = Math.floor((p1.color.b + p2.color.b) / 2);
                    
                    this.ctx.beginPath();
                    this.ctx.moveTo(p1.x, p1.y);
                    this.ctx.lineTo(p2.x, p2.y);
                    this.ctx.strokeStyle = `rgba(${r}, ${g}, ${b}, ${alpha})`;
                    this.ctx.lineWidth = 1;
                    this.ctx.stroke();
                }
            }
        }
    }
    
    animate() {
        if (!this.isVisible) {
            this.animationId = null;
            return;
        }
        
        // Clear canvas
        this.ctx.clearRect(0, 0, this.width, this.height);
        
        // Update and draw particles
        for (const particle of this.particles) {
            this.updateParticle(particle);
            this.drawParticle(particle);
        }
        
        // Draw connections
        this.drawConnections();
        
        this.animationId = requestAnimationFrame(() => this.animate());
    }
    
    // Public method to emit particles from a point
    emit(x, y, count = 10, color = 'cyan') {
        const colorObj = this.colors[color] || this.colors.cyan;
        
        for (let i = 0; i < count; i++) {
            const angle = (Math.PI * 2 / count) * i;
            const speed = 2 + Math.random() * 2;
            
            const particle = {
                x: x,
                y: y,
                vx: Math.cos(angle) * speed,
                vy: Math.sin(angle) * speed,
                radius: Math.random() * 3 + 2,
                color: colorObj,
                alpha: 0.8,
                pulsePhase: 0,
                pulseSpeed: 0.1,
                life: 1,
                decay: 0.02
            };
            
            this.particles.push(particle);
            
            // Remove after animation
            setTimeout(() => {
                const index = this.particles.indexOf(particle);
                if (index > -1) {
                    this.particles.splice(index, 1);
                }
            }, 2000);
        }
    }
    
    destroy() {
        if (this.animationId) {
            cancelAnimationFrame(this.animationId);
        }
    }
}

// Initialize on load
window.particleSystem = null;

document.addEventListener('DOMContentLoaded', () => {
    // Check for reduced motion preference
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
        return;
    }
    
    window.particleSystem = new ParticleSystem('particles');
});
