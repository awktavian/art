/**
 * Performance Optimizations — 鏡 Kagami
 *
 * 60fps animation pipeline with:
 * - GPU-accelerated compositing
 * - Batched DOM updates
 * - Efficient particle system
 * - Memory-optimized state
 *
 * Target: < 16ms per frame (60fps)
 *
 * Focus:
 */

// ═══════════════════════════════════════════════════════════════
// PERFORMANCE MONITOR
// ═══════════════════════════════════════════════════════════════

class PerformanceMonitor {
    constructor() {
        this.frameTimes = [];
        this.maxSamples = 60;
        this.lastFrameTime = 0;
        this.enabled = true;

        this.metrics = {
            fps: 60,
            frameTime: 16.67,
            jank: 0,
            memory: 0,
        };
    }

    startFrame() {
        this.lastFrameTime = performance.now();
    }

    endFrame() {
        const elapsed = performance.now() - this.lastFrameTime;

        this.frameTimes.push(elapsed);
        if (this.frameTimes.length > this.maxSamples) {
            this.frameTimes.shift();
        }

        // Calculate metrics
        const avgFrameTime = this.frameTimes.reduce((a, b) => a + b, 0) / this.frameTimes.length;
        this.metrics.frameTime = avgFrameTime;
        this.metrics.fps = 1000 / avgFrameTime;
        this.metrics.jank = this.frameTimes.filter(t => t > 16.67).length / this.frameTimes.length;

        // Memory (if available)
        if (performance.memory) {
            this.metrics.memory = performance.memory.usedJSHeapSize / 1024 / 1024;
        }

        // Warn on performance issues
        if (elapsed > 32 && this.enabled) {
            console.warn(`⚠️ Frame took ${elapsed.toFixed(1)}ms (target: 16ms)`);
        }
    }

    getMetrics() {
        return { ...this.metrics };
    }

    log() {
        console.log(`
📊 Performance Metrics:
   FPS: ${this.metrics.fps.toFixed(1)}
   Frame Time: ${this.metrics.frameTime.toFixed(2)}ms
   Jank Rate: ${(this.metrics.jank * 100).toFixed(1)}%
   Memory: ${this.metrics.memory.toFixed(1)}MB
        `);
    }
}

const perfMonitor = new PerformanceMonitor();

// ═══════════════════════════════════════════════════════════════
// BATCHED DOM UPDATES
// ═══════════════════════════════════════════════════════════════

class DOMBatcher {
    constructor() {
        this.readQueue = [];
        this.writeQueue = [];
        this.scheduled = false;
    }

    // Schedule a read operation
    read(fn) {
        this.readQueue.push(fn);
        this.schedule();
        return new Promise(resolve => {
            this.readQueue[this.readQueue.length - 1] = () => resolve(fn());
        });
    }

    // Schedule a write operation
    write(fn) {
        this.writeQueue.push(fn);
        this.schedule();
    }

    schedule() {
        if (!this.scheduled) {
            this.scheduled = true;
            requestAnimationFrame(() => this.flush());
        }
    }

    flush() {
        this.scheduled = false;

        // Reads first (forces layout)
        const reads = this.readQueue.splice(0);
        for (const fn of reads) {
            try { fn(); } catch (e) { console.error('Read error:', e); }
        }

        // Then writes (batched to avoid layout thrashing)
        const writes = this.writeQueue.splice(0);
        for (const fn of writes) {
            try { fn(); } catch (e) { console.error('Write error:', e); }
        }
    }
}

const domBatcher = new DOMBatcher();

// ═══════════════════════════════════════════════════════════════
// GPU-ACCELERATED PARTICLE SYSTEM
// ═══════════════════════════════════════════════════════════════

class OptimizedParticles {
    constructor(container, count = 30) {
        this.container = container;
        this.count = count;
        this.particles = [];
        this.canvas = null;
        this.ctx = null;
        this.useCanvas = this.shouldUseCanvas();

        this.init();
    }

    shouldUseCanvas() {
        // Use canvas for better performance on high-DPI displays
        return window.devicePixelRatio > 1.5;
    }

    init() {
        if (this.useCanvas) {
            this.initCanvas();
        } else {
            this.initDOM();
        }
    }

    initCanvas() {
        this.canvas = document.createElement('canvas');
        this.canvas.style.cssText = `
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            pointer-events: none;
            z-index: -1;
        `;

        this.container.appendChild(this.canvas);
        this.ctx = this.canvas.getContext('2d');

        this.resize();
        window.addEventListener('resize', () => this.resize());

        // Create particle data
        const colors = [
            'rgba(255, 107, 53, 0.4)',   // Spark
            'rgba(212, 175, 55, 0.4)',   // Forge
            'rgba(78, 205, 196, 0.4)',   // Flow
            'rgba(155, 126, 189, 0.4)',  // Nexus
            'rgba(245, 158, 11, 0.4)',   // Beacon
            'rgba(126, 183, 127, 0.4)',  // Grove
            'rgba(103, 212, 228, 0.4)',  // Crystal
        ];

        for (let i = 0; i < this.count; i++) {
            this.particles.push({
                x: Math.random() * this.canvas.width,
                y: Math.random() * this.canvas.height,
                vx: (Math.random() - 0.5) * 0.5,
                vy: -Math.random() * 0.5 - 0.2,
                size: 2 + Math.random() * 2,
                color: colors[i % colors.length],
                alpha: Math.random() * 0.6,
            });
        }
    }

    initDOM() {
        // Fallback to CSS-animated DOM particles
        // Already handled by craft-essential.css
    }

    resize() {
        if (!this.canvas) return;

        const dpr = window.devicePixelRatio || 1;
        this.canvas.width = window.innerWidth * dpr;
        this.canvas.height = window.innerHeight * dpr;
        this.ctx.scale(dpr, dpr);
    }

    update() {
        if (!this.useCanvas || !this.ctx) return;

        this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);

        for (const p of this.particles) {
            // Update position
            p.x += p.vx;
            p.y += p.vy;

            // Wrap around
            if (p.y < -10) {
                p.y = this.canvas.height / window.devicePixelRatio + 10;
                p.x = Math.random() * this.canvas.width / window.devicePixelRatio;
            }
            if (p.x < -10) p.x = this.canvas.width / window.devicePixelRatio + 10;
            if (p.x > this.canvas.width / window.devicePixelRatio + 10) p.x = -10;

            // Draw
            this.ctx.beginPath();
            this.ctx.arc(p.x, p.y, p.size, 0, Math.PI * 2);
            this.ctx.fillStyle = p.color;
            this.ctx.globalAlpha = p.alpha;
            this.ctx.fill();
        }

        this.ctx.globalAlpha = 1;
    }

    // Scatter particles from cursor position
    scatter(x, y, force = 1) {
        for (const p of this.particles) {
            const dx = p.x - x;
            const dy = p.y - y;
            const dist = Math.sqrt(dx * dx + dy * dy);

            if (dist < 100) {
                const angle = Math.atan2(dy, dx);
                const repel = (100 - dist) / 100 * force;
                p.vx += Math.cos(angle) * repel * 2;
                p.vy += Math.sin(angle) * repel * 2;
            }
        }
    }
}

// ═══════════════════════════════════════════════════════════════
// OPTIMIZED ANIMATION LOOP
// ═══════════════════════════════════════════════════════════════

class AnimationLoop {
    constructor() {
        this.running = false;
        this.callbacks = new Set();
        this.particles = null;
    }

    start() {
        if (this.running) return;
        this.running = true;

        // Initialize particles
        const container = document.getElementById('particles') || document.body;
        this.particles = new OptimizedParticles(container, 30);

        this.loop();
    }

    stop() {
        this.running = false;
    }

    loop() {
        if (!this.running) return;

        perfMonitor.startFrame();

        // Update particles
        if (this.particles) {
            this.particles.update();
        }

        // Run registered callbacks
        for (const cb of this.callbacks) {
            try { cb(); } catch (e) { console.error('Animation callback error:', e); }
        }

        perfMonitor.endFrame();

        requestAnimationFrame(() => this.loop());
    }

    register(callback) {
        this.callbacks.add(callback);
        return () => this.callbacks.delete(callback);
    }
}

const animationLoop = new AnimationLoop();

// ═══════════════════════════════════════════════════════════════
// INTERSECTION OBSERVER FOR LAZY ANIMATIONS
// ═══════════════════════════════════════════════════════════════

function setupLazyAnimations() {
    const observer = new IntersectionObserver((entries) => {
        for (const entry of entries) {
            if (entry.isIntersecting) {
                entry.target.classList.add('animate-in');
                // Stop observing after animation
                observer.unobserve(entry.target);
            }
        }
    }, {
        threshold: 0.1,
        rootMargin: '50px',
    });

    // Observe all animatable elements
    document.querySelectorAll('.reveal, .colony, .stat-card').forEach(el => {
        observer.observe(el);
    });
}

// ═══════════════════════════════════════════════════════════════
// CURSOR OPTIMIZATION (requestAnimationFrame instead of mousemove)
// ═══════════════════════════════════════════════════════════════

let mouseX = 0, mouseY = 0;
let cursorX = 0, cursorY = 0;
let ringX = 0, ringY = 0;

function optimizedCursorUpdate() {
    // Smooth interpolation
    cursorX += (mouseX - cursorX) * 0.15;
    cursorY += (mouseY - cursorY) * 0.15;
    ringX += (mouseX - ringX) * 0.08;
    ringY += (mouseY - ringY) * 0.08;

    const cursor = document.getElementById('cursor');
    const ring = document.getElementById('cursor-ring');

    if (cursor) {
        // Use transform for GPU acceleration
        cursor.style.transform = `translate3d(${cursorX}px, ${cursorY}px, 0) translate(-50%, -50%)`;
    }

    if (ring) {
        ring.style.transform = `translate3d(${ringX}px, ${ringY}px, 0) translate(-50%, -50%)`;
    }
}

// Only update mouse position on move
document.addEventListener('mousemove', (e) => {
    mouseX = e.clientX;
    mouseY = e.clientY;
}, { passive: true });

// ═══════════════════════════════════════════════════════════════
// INITIALIZATION
// ═══════════════════════════════════════════════════════════════

function initPerformance() {
    console.log('🚀 Initializing performance optimizations...');

    // Start animation loop
    animationLoop.start();

    // Register cursor update
    animationLoop.register(optimizedCursorUpdate);

    // Setup lazy animations
    setupLazyAnimations();

    // Particle scatter on click
    document.addEventListener('click', (e) => {
        if (animationLoop.particles) {
            animationLoop.particles.scatter(e.clientX, e.clientY, 2);
        }
    });

    console.log('✓ Performance optimizations active');
    console.log('  Try: Performance.getMetrics()');
}

// Auto-init
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initPerformance);
} else {
    initPerformance();
}

// ═══════════════════════════════════════════════════════════════
// EXPORTS
// ═══════════════════════════════════════════════════════════════

export const Performance = {
    monitor: perfMonitor,
    batcher: domBatcher,
    loop: animationLoop,

    getMetrics: () => perfMonitor.getMetrics(),
    log: () => perfMonitor.log(),

    // Batch DOM operations
    read: (fn) => domBatcher.read(fn),
    write: (fn) => domBatcher.write(fn),

    // Register animation callback
    onFrame: (fn) => animationLoop.register(fn),
};

window.Performance = Performance;

/*
 * 鏡
 * Speed is respect. Latency is friction.
 * 60fps is presence.
 */
