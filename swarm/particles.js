/**
 * Particles System — Bioluminescent Data Flow
 * 
 * Canvas-based particle system for visualizing data flowing
 * between browser nodes in the swarm.
 * 
 * GPU-accelerated via requestAnimationFrame.
 * 
 * FIXES APPLIED:
 * - Particle pool pattern (no unbounded array growth)
 * - Debounced resize handler
 * - Proper cleanup with destroy()
 * - Separated visibility flags
 * - Spatial partitioning for connections
 */

class ParticleSystem {
    constructor(canvasId) {
        this.canvas = document.getElementById(canvasId);
        if (!this.canvas) {
            console.warn(`ParticleSystem: Canvas #${canvasId} not found`);
            return;
        }
        
        this.ctx = this.canvas.getContext('2d');
        this.particles = [];
        this.particlePool = []; // Object pool for recycling
        this.maxParticles = 300; // Hard cap for h(x) >= 0
        this.mousePos = { x: 0, y: 0 };
        this.isTabVisible = true;
        this.isInViewport = true;
        this.animationId = null;
        this.resizeTimeout = null;
        this.lastDpr = window.devicePixelRatio || 1;
        
        // Bound event handlers for cleanup
        this._boundResize = this._debouncedResize.bind(this);
        this._boundMouseMove = this._onMouseMove.bind(this);
        this._boundVisibilityChange = this._onVisibilityChange.bind(this);
        this._boundScroll = this._onScroll.bind(this);
        
        // Intersection observer reference
        this._observer = null;
        
        // Spatial grid for O(1) neighbor lookup
        this.grid = new Map();
        this.gridCellSize = 120;
        
        // Colors
        this.colors = {
            cyan: { r: 0, g: 245, b: 212 },
            magenta: { r: 241, g: 91, b: 181 },
            violet: { r: 155, g: 93, b: 229 },
            amber: { r: 254, g: 228, b: 64 }
        };
        
        this.init();
    }
    
    get isVisible() {
        return this.isTabVisible && this.isInViewport;
    }
    
    init() {
        this.resize();
        this.createParticles();
        this.bindEvents();
        this.animate();
    }
    
    resize() {
        const dpr = window.devicePixelRatio || 1;
        this.lastDpr = dpr;
        
        this.canvas.width = window.innerWidth * dpr;
        this.canvas.height = window.innerHeight * dpr;
        this.canvas.style.width = window.innerWidth + 'px';
        this.canvas.style.height = window.innerHeight + 'px';
        this.ctx.setTransform(1, 0, 0, 1, 0, 0); // Reset transform
        this.ctx.scale(dpr, dpr);
        
        this.width = window.innerWidth;
        this.height = window.innerHeight;
    }
    
    _debouncedResize() {
        if (this.resizeTimeout) {
            clearTimeout(this.resizeTimeout);
        }
        this.resizeTimeout = setTimeout(() => {
            // Check if DPR changed (moved between displays)
            const newDpr = window.devicePixelRatio || 1;
            if (newDpr !== this.lastDpr) {
                this.resize();
            } else {
                this.resize();
            }
            this.createParticles();
        }, 150); // Fibonacci-adjacent debounce
    }
    
    _onMouseMove(e) {
        this.mousePos.x = e.clientX;
        this.mousePos.y = e.clientY;
    }
    
    _onVisibilityChange() {
        this.isTabVisible = !document.hidden;
        if (this.isVisible && !this.animationId) {
            this.animate();
        }
    }
    
    _onScroll() {
        // Emit particles based on scroll velocity
        const now = performance.now();
        if (!this._lastScrollTime) this._lastScrollTime = now;
        if (!this._lastScrollY) this._lastScrollY = window.scrollY;
        
        const dt = now - this._lastScrollTime;
        if (dt > 50) { // Throttle
            const velocity = Math.abs(window.scrollY - this._lastScrollY) / dt * 1000;
            this._lastScrollTime = now;
            this._lastScrollY = window.scrollY;
            
            if (velocity > 500 && this.particles.length < this.maxParticles - 5) {
                const count = Math.min(3, Math.floor(velocity / 500));
                const direction = window.scrollY > this._lastScrollY ? 1 : -1;
                for (let i = 0; i < count; i++) {
                    this.emit(
                        Math.random() * this.width,
                        direction > 0 ? 0 : this.height,
                        2,
                        ['cyan', 'violet'][Math.floor(Math.random() * 2)]
                    );
                }
            }
        }
    }
    
    createParticles() {
        const particleCount = Math.min(150, Math.floor((this.width * this.height) / 15000));
        this.particles = [];
        this.particlePool = [];
        
        for (let i = 0; i < particleCount; i++) {
            this.particles.push(this.createParticle());
        }
    }
    
    createParticle(x, y, overrides = {}) {
        // Try to reuse from pool
        let particle = this.particlePool.pop();
        
        const colorKeys = Object.keys(this.colors);
        const colorKey = overrides.colorKey || colorKeys[Math.floor(Math.random() * colorKeys.length)];
        const color = this.colors[colorKey];
        
        if (particle) {
            // Recycle existing particle
            particle.x = x ?? Math.random() * this.width;
            particle.y = y ?? Math.random() * this.height;
            particle.vx = overrides.vx ?? (Math.random() - 0.5) * 0.5;
            particle.vy = overrides.vy ?? (Math.random() - 0.5) * 0.5;
            particle.radius = overrides.radius ?? Math.random() * 2 + 1;
            particle.color = color;
            particle.alpha = overrides.alpha ?? Math.random() * 0.5 + 0.2;
            particle.pulsePhase = Math.random() * Math.PI * 2;
            particle.pulseSpeed = 0.02 + Math.random() * 0.02;
            particle.life = overrides.life ?? 1;
            particle.decay = overrides.decay ?? 0;
            particle.isEmitted = !!overrides.isEmitted;
        } else {
            particle = {
                x: x ?? Math.random() * this.width,
                y: y ?? Math.random() * this.height,
                vx: overrides.vx ?? (Math.random() - 0.5) * 0.5,
                vy: overrides.vy ?? (Math.random() - 0.5) * 0.5,
                radius: overrides.radius ?? Math.random() * 2 + 1,
                color: color,
                alpha: overrides.alpha ?? Math.random() * 0.5 + 0.2,
                pulsePhase: Math.random() * Math.PI * 2,
                pulseSpeed: 0.02 + Math.random() * 0.02,
                currentAlpha: 0,
                life: overrides.life ?? 1,
                decay: overrides.decay ?? 0,
                isEmitted: !!overrides.isEmitted
            };
        }
        
        return particle;
    }
    
    bindEvents() {
        window.addEventListener('resize', this._boundResize);
        window.addEventListener('mousemove', this._boundMouseMove, { passive: true });
        document.addEventListener('visibilitychange', this._boundVisibilityChange);
        window.addEventListener('scroll', this._boundScroll, { passive: true });
        
        // Intersection Observer for performance
        this._observer = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                this.isInViewport = entry.isIntersecting;
                if (this.isVisible && !this.animationId) {
                    this.animate();
                }
            });
        });
        
        this._observer.observe(this.canvas);
    }
    
    // Spatial grid helpers
    _getCellKey(x, y) {
        const cellX = Math.floor(x / this.gridCellSize);
        const cellY = Math.floor(y / this.gridCellSize);
        return `${cellX},${cellY}`;
    }
    
    _updateGrid() {
        this.grid.clear();
        for (let i = 0; i < this.particles.length; i++) {
            const p = this.particles[i];
            const key = this._getCellKey(p.x, p.y);
            if (!this.grid.has(key)) {
                this.grid.set(key, []);
            }
            this.grid.get(key).push(i);
        }
    }
    
    _getNeighborIndices(x, y) {
        const neighbors = [];
        const cellX = Math.floor(x / this.gridCellSize);
        const cellY = Math.floor(y / this.gridCellSize);
        
        // Check 3x3 cells around the particle
        for (let dx = -1; dx <= 1; dx++) {
            for (let dy = -1; dy <= 1; dy++) {
                const key = `${cellX + dx},${cellY + dy}`;
                const cell = this.grid.get(key);
                if (cell) {
                    neighbors.push(...cell);
                }
            }
        }
        
        return neighbors;
    }
    
    updateParticle(particle, index) {
        // Update position
        particle.x += particle.vx;
        particle.y += particle.vy;
        
        // Handle emitted particles (decay and die)
        if (particle.isEmitted) {
            particle.life -= particle.decay;
            if (particle.life <= 0) {
                return false; // Mark for removal
            }
        }
        
        // Wrap around edges (only for non-emitted)
        if (!particle.isEmitted) {
            if (particle.x < 0) particle.x = this.width;
            if (particle.x > this.width) particle.x = 0;
            if (particle.y < 0) particle.y = this.height;
            if (particle.y > this.height) particle.y = 0;
        }
        
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
        particle.currentAlpha = particle.alpha * (0.5 + pulseFactor * 0.5) * particle.life;
        
        return true; // Keep particle
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
        
        // Use spatial grid for O(n) instead of O(n^2)
        this._updateGrid();
        const drawn = new Set();
        
        for (let i = 0; i < this.particles.length; i++) {
            const p1 = this.particles[i];
            if (p1.isEmitted) continue; // Don't connect emitted particles
            
            const neighbors = this._getNeighborIndices(p1.x, p1.y);
            
            for (const j of neighbors) {
                if (j <= i) continue; // Avoid duplicates
                
                const p2 = this.particles[j];
                if (p2.isEmitted) continue;
                
                const pairKey = `${i}-${j}`;
                if (drawn.has(pairKey)) continue;
                drawn.add(pairKey);
                
                const dx = p1.x - p2.x;
                const dy = p1.y - p2.y;
                const dist = Math.sqrt(dx * dx + dy * dy);
                
                if (dist < connectionDistance) {
                    const alpha = (1 - dist / connectionDistance) * 0.15;
                    
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
        
        // Update and draw particles, removing dead ones
        const aliveParticles = [];
        for (let i = 0; i < this.particles.length; i++) {
            const particle = this.particles[i];
            const alive = this.updateParticle(particle, i);
            
            if (alive) {
                this.drawParticle(particle);
                aliveParticles.push(particle);
            } else {
                // Return to pool for recycling
                this.particlePool.push(particle);
            }
        }
        this.particles = aliveParticles;
        
        // Draw connections
        this.drawConnections();
        
        this.animationId = requestAnimationFrame(() => this.animate());
    }
    
    // Public method to emit particles from a point
    emit(x, y, count = 10, color = 'cyan') {
        // Enforce cap
        const available = this.maxParticles - this.particles.length;
        const actualCount = Math.min(count, available);
        
        if (actualCount <= 0) return;
        
        const colorObj = this.colors[color] || this.colors.cyan;
        
        for (let i = 0; i < actualCount; i++) {
            const angle = (Math.PI * 2 / actualCount) * i + Math.random() * 0.5;
            const speed = 2 + Math.random() * 2;
            
            const particle = this.createParticle(x, y, {
                vx: Math.cos(angle) * speed,
                vy: Math.sin(angle) * speed,
                radius: Math.random() * 3 + 2,
                colorKey: color,
                alpha: 0.8,
                life: 1,
                decay: 0.015,
                isEmitted: true
            });
            
            this.particles.push(particle);
        }
    }
    
    destroy() {
        // Cancel animation
        if (this.animationId) {
            cancelAnimationFrame(this.animationId);
            this.animationId = null;
        }
        
        // Clear resize timeout
        if (this.resizeTimeout) {
            clearTimeout(this.resizeTimeout);
        }
        
        // Remove event listeners
        window.removeEventListener('resize', this._boundResize);
        window.removeEventListener('mousemove', this._boundMouseMove);
        document.removeEventListener('visibilitychange', this._boundVisibilityChange);
        window.removeEventListener('scroll', this._boundScroll);
        
        // Disconnect observer
        if (this._observer) {
            this._observer.disconnect();
            this._observer = null;
        }
        
        // Clear particles
        this.particles = [];
        this.particlePool = [];
        this.grid.clear();
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
