/**
 * 鏡 Kagami Architecture — Interactive Experience
 *
 * Features:
 * - Custom cursor with hover states
 * - Fano plane visualization with data particles
 * - Catastrophe surface rendering
 * - E8 lattice 2D projection
 * - Safety barrier visualization
 * - Sound design for interactions
 * - Easter egg: Kagami⁻¹ story
 *
 * Built with love. craft(x) → ∞ always.
 */

'use strict';

// ═══════════════════════════════════════════════════════════════════
// CONSTANTS
// ═══════════════════════════════════════════════════════════════════

const TIMING = {
    MICRO: 89,
    SHORT: 144,
    NORMAL: 233,
    MEDIUM: 377,
    LONG: 610,
    SLOW: 987,
    SLOWER: 1597,
    BREATHING: 2584
};

// Colony definitions with Fano plane positions
const COLONIES = [
    { id: 'perception', name: 'Perception', catastrophe: 'fold', color: '#FF6B6B', fanoIndex: 0 },
    { id: 'attention', name: 'Attention', catastrophe: 'cusp', color: '#4ECDC4', fanoIndex: 1 },
    { id: 'memory', name: 'Memory', catastrophe: 'swallowtail', color: '#45B7D1', fanoIndex: 2 },
    { id: 'reasoning', name: 'Reasoning', catastrophe: 'butterfly', color: '#96CEB4', fanoIndex: 3 },
    { id: 'planning', name: 'Planning', catastrophe: 'hyperbolic', color: '#FFEAA7', fanoIndex: 4 },
    { id: 'emotion', name: 'Emotion', catastrophe: 'elliptic', color: '#DDA0DD', fanoIndex: 5 },
    { id: 'action', name: 'Action', catastrophe: 'parabolic', color: '#F39C12', fanoIndex: 6 }
];

// Fano plane lines (each connects 3 colonies)
const FANO_LINES = [
    [0, 1, 2], // Perception, Attention, Memory
    [0, 3, 5], // Perception, Reasoning, Emotion
    [1, 3, 4], // Attention, Reasoning, Planning
    [2, 3, 6], // Memory, Reasoning, Action
    [1, 5, 6], // Attention, Emotion, Action
    [2, 4, 5], // Memory, Planning, Emotion
    [0, 4, 6]  // Perception, Planning, Action
];

// ═══════════════════════════════════════════════════════════════════
// ACCESSIBILITY — Reduced Motion
// ═══════════════════════════════════════════════════════════════════

const MotionPreference = {
    _prefersReduced: null,

    get prefersReduced() {
        if (this._prefersReduced === null) {
            this._prefersReduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
            window.matchMedia('(prefers-reduced-motion: reduce)').addEventListener('change', (e) => {
                this._prefersReduced = e.matches;
            });
        }
        return this._prefersReduced;
    },

    animate(animateFn, fallbackFn = null) {
        if (this.prefersReduced) {
            if (fallbackFn) fallbackFn();
            return false;
        }
        animateFn();
        return true;
    }
};

// ═══════════════════════════════════════════════════════════════════
// SOUND DESIGN
// ═══════════════════════════════════════════════════════════════════

class SoundDesign {
    constructor() {
        this.context = null;
        this.enabled = false;
        this.masterGain = null;
        this.initialized = false;
        this.userEnabled = true; // User preference
    }

    async init() {
        if (this.initialized) return;
        try {
            this.context = new (window.AudioContext || window.webkitAudioContext)();
            // Resume context if suspended (browser autoplay policy)
            if (this.context.state === 'suspended') {
                await this.context.resume();
            }
            this.masterGain = this.context.createGain();
            this.masterGain.gain.value = 0.12;
            this.masterGain.connect(this.context.destination);
            this.initialized = true;
            this.enabled = this.userEnabled;
            this.updateToggleUI();
        } catch (e) {
            console.log('Audio not supported');
        }
    }

    toggle() {
        this.userEnabled = !this.userEnabled;
        this.enabled = this.initialized && this.userEnabled;
        this.updateToggleUI();
        // Store preference
        try {
            localStorage.setItem('kagami-sound-enabled', this.userEnabled);
        } catch (e) {}
    }

    loadPreference() {
        try {
            const stored = localStorage.getItem('kagami-sound-enabled');
            if (stored !== null) {
                this.userEnabled = stored === 'true';
            }
        } catch (e) {}
    }

    updateToggleUI() {
        const toggle = document.getElementById('sound-toggle');
        if (toggle) {
            toggle.setAttribute('aria-pressed', this.enabled ? 'true' : 'false');
        }
    }

    playClick() {
        if (!this.enabled || !this.context || MotionPreference.prefersReduced) return;
        const osc = this.context.createOscillator();
        const gain = this.context.createGain();
        osc.type = 'sine';
        osc.frequency.setValueAtTime(800, this.context.currentTime);
        osc.frequency.exponentialRampToValueAtTime(400, this.context.currentTime + 0.05);
        gain.gain.setValueAtTime(0.3, this.context.currentTime);
        gain.gain.exponentialRampToValueAtTime(0.01, this.context.currentTime + 0.05);
        osc.connect(gain);
        gain.connect(this.masterGain);
        osc.start();
        osc.stop(this.context.currentTime + 0.05);
    }

    playHover() {
        if (!this.enabled || !this.context || MotionPreference.prefersReduced) return;
        const osc = this.context.createOscillator();
        const gain = this.context.createGain();
        osc.type = 'sine';
        osc.frequency.setValueAtTime(600, this.context.currentTime);
        gain.gain.setValueAtTime(0.08, this.context.currentTime);
        gain.gain.exponentialRampToValueAtTime(0.01, this.context.currentTime + 0.08);
        osc.connect(gain);
        gain.connect(this.masterGain);
        osc.start();
        osc.stop(this.context.currentTime + 0.08);
    }

    playDataFlow(colonyIndex) {
        if (!this.enabled || !this.context || MotionPreference.prefersReduced) return;
        // Each colony has a unique frequency based on golden ratio
        const baseFreq = 220;
        const phi = 1.618;
        const freq = baseFreq * Math.pow(phi, colonyIndex * 0.5);

        const osc = this.context.createOscillator();
        const gain = this.context.createGain();
        osc.type = 'triangle';
        osc.frequency.setValueAtTime(freq, this.context.currentTime);
        osc.frequency.exponentialRampToValueAtTime(freq * 1.5, this.context.currentTime + 0.15);
        gain.gain.setValueAtTime(0.15, this.context.currentTime);
        gain.gain.exponentialRampToValueAtTime(0.01, this.context.currentTime + 0.15);
        osc.connect(gain);
        gain.connect(this.masterGain);
        osc.start();
        osc.stop(this.context.currentTime + 0.15);
    }

    playSafetyWarning() {
        if (!this.enabled || !this.context) return;
        const osc = this.context.createOscillator();
        const gain = this.context.createGain();
        osc.type = 'sawtooth';
        osc.frequency.setValueAtTime(150, this.context.currentTime);
        gain.gain.setValueAtTime(0.2, this.context.currentTime);
        gain.gain.exponentialRampToValueAtTime(0.01, this.context.currentTime + 0.3);
        osc.connect(gain);
        gain.connect(this.masterGain);
        osc.start();
        osc.stop(this.context.currentTime + 0.3);
    }
}

const sound = new SoundDesign();

// ═══════════════════════════════════════════════════════════════════
// CUSTOM CURSOR
// ═══════════════════════════════════════════════════════════════════

class CustomCursor {
    constructor() {
        this.cursor = document.querySelector('.cursor');
        this.ring = document.querySelector('.cursor-ring');
        this.pos = { x: 0, y: 0 };
        this.mouse = { x: 0, y: 0 };
        this.speed = 0.15;

        if (!this.cursor || !this.ring) return;
        if (MotionPreference.prefersReduced) {
            this.cursor.style.display = 'none';
            this.ring.style.display = 'none';
            return;
        }

        this.init();
    }

    init() {
        document.addEventListener('mousemove', (e) => {
            this.mouse.x = e.clientX;
            this.mouse.y = e.clientY;
        });

        // Hover states
        const hoverTargets = document.querySelectorAll('a, button, [role="button"], .colony-card, .package-card, .fano-line, .safety-layer, .platform-badge');
        hoverTargets.forEach(el => {
            el.addEventListener('mouseenter', () => this.setHover(true));
            el.addEventListener('mouseleave', () => this.setHover(false));
        });

        // Click state
        document.addEventListener('mousedown', () => {
            this.cursor.style.transform = 'translate(-50%, -50%) scale(0.8)';
        });
        document.addEventListener('mouseup', () => {
            this.cursor.style.transform = 'translate(-50%, -50%) scale(1)';
        });

        this.animate();
    }

    setHover(isHovering) {
        this.cursor.classList.toggle('hovering', isHovering);
        this.ring.classList.toggle('hovering', isHovering);
    }

    animate() {
        // Smooth follow
        this.pos.x += (this.mouse.x - this.pos.x) * this.speed;
        this.pos.y += (this.mouse.y - this.pos.y) * this.speed;

        this.cursor.style.left = `${this.mouse.x}px`;
        this.cursor.style.top = `${this.mouse.y}px`;
        this.ring.style.left = `${this.pos.x}px`;
        this.ring.style.top = `${this.pos.y}px`;

        requestAnimationFrame(() => this.animate());
    }
}

// ═══════════════════════════════════════════════════════════════════
// PARTICLE SYSTEM — Background Ambiance
// ═══════════════════════════════════════════════════════════════════

class ParticleSystem {
    constructor(canvas) {
        this.canvas = canvas;
        this.ctx = canvas.getContext('2d');
        this.particles = [];
        this.particleCount = 50;
        this.running = true;

        this.resize();
        window.addEventListener('resize', () => this.resize());

        if (!MotionPreference.prefersReduced) {
            this.init();
            this.animate();
        }
    }

    resize() {
        this.canvas.width = window.innerWidth;
        this.canvas.height = window.innerHeight;
    }

    init() {
        this.particles = [];
        for (let i = 0; i < this.particleCount; i++) {
            this.particles.push({
                x: Math.random() * this.canvas.width,
                y: Math.random() * this.canvas.height,
                vx: (Math.random() - 0.5) * 0.3,
                vy: (Math.random() - 0.5) * 0.3 - 0.2, // Slight upward drift
                size: Math.random() * 2 + 1,
                opacity: Math.random() * 0.5 + 0.1,
                hue: Math.random() * 30 + 35 // Gold range
            });
        }
    }

    animate() {
        if (!this.running) return;

        this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);

        this.particles.forEach(p => {
            // Update position
            p.x += p.vx;
            p.y += p.vy;

            // Wrap around
            if (p.x < 0) p.x = this.canvas.width;
            if (p.x > this.canvas.width) p.x = 0;
            if (p.y < 0) p.y = this.canvas.height;
            if (p.y > this.canvas.height) p.y = 0;

            // Draw
            this.ctx.beginPath();
            this.ctx.arc(p.x, p.y, p.size, 0, Math.PI * 2);
            this.ctx.fillStyle = `hsla(${p.hue}, 70%, 55%, ${p.opacity})`;
            this.ctx.fill();
        });

        // Draw connections between nearby particles
        for (let i = 0; i < this.particles.length; i++) {
            for (let j = i + 1; j < this.particles.length; j++) {
                const dx = this.particles[i].x - this.particles[j].x;
                const dy = this.particles[i].y - this.particles[j].y;
                const dist = Math.sqrt(dx * dx + dy * dy);

                if (dist < 120) {
                    this.ctx.beginPath();
                    this.ctx.moveTo(this.particles[i].x, this.particles[i].y);
                    this.ctx.lineTo(this.particles[j].x, this.particles[j].y);
                    this.ctx.strokeStyle = `rgba(212, 175, 55, ${0.1 * (1 - dist / 120)})`;
                    this.ctx.lineWidth = 0.5;
                    this.ctx.stroke();
                }
            }
        }

        requestAnimationFrame(() => this.animate());
    }
}

// ═══════════════════════════════════════════════════════════════════
// FANO PLANE VISUALIZATION
// ═══════════════════════════════════════════════════════════════════

class FanoPlane {
    constructor(canvas, options = {}) {
        this.canvas = canvas;
        this.ctx = canvas.getContext('2d');
        this.options = {
            interactive: true,
            showParticles: true,
            showLabels: true,
            ...options
        };

        this.hoveredColony = null;
        this.hoveredLine = null;
        this.particles = [];
        this.time = 0;

        this.resize();
        window.addEventListener('resize', () => this.resize());

        if (this.options.interactive) {
            this.canvas.addEventListener('mousemove', (e) => this.onMouseMove(e));
            this.canvas.addEventListener('click', (e) => this.onClick(e));
        }

        if (!MotionPreference.prefersReduced) {
            this.initParticles();
            this.animate();
        } else {
            this.draw();
        }
    }

    resize() {
        const rect = this.canvas.getBoundingClientRect();
        this.canvas.width = rect.width * window.devicePixelRatio;
        this.canvas.height = rect.height * window.devicePixelRatio;
        this.ctx.scale(window.devicePixelRatio, window.devicePixelRatio);
        this.width = rect.width;
        this.height = rect.height;
        this.centerX = this.width / 2;
        this.centerY = this.height / 2;
        this.radius = Math.min(this.width, this.height) * 0.35;

        // Calculate colony positions (hexagonal arrangement + center)
        this.colonyPositions = this.calculateColonyPositions();
    }

    calculateColonyPositions() {
        const positions = [];
        // 6 colonies on hexagon vertices, 1 in center
        for (let i = 0; i < 6; i++) {
            const angle = (i * Math.PI / 3) - Math.PI / 2; // Start from top
            positions.push({
                x: this.centerX + Math.cos(angle) * this.radius,
                y: this.centerY + Math.sin(angle) * this.radius
            });
        }
        // Center colony (Reasoning)
        positions.splice(3, 0, { x: this.centerX, y: this.centerY });
        return positions;
    }

    initParticles() {
        // Create particles for each Fano line
        FANO_LINES.forEach((line, lineIndex) => {
            for (let i = 0; i < 3; i++) {
                this.particles.push({
                    lineIndex,
                    progress: Math.random(),
                    speed: 0.002 + Math.random() * 0.002,
                    size: 3 + Math.random() * 2
                });
            }
        });
    }

    onMouseMove(e) {
        const rect = this.canvas.getBoundingClientRect();
        const x = e.clientX - rect.left;
        const y = e.clientY - rect.top;

        // Check colony hover
        this.hoveredColony = null;
        this.colonyPositions.forEach((pos, i) => {
            const dx = x - pos.x;
            const dy = y - pos.y;
            if (Math.sqrt(dx * dx + dy * dy) < 25) {
                this.hoveredColony = i;
            }
        });

        // Check line hover
        this.hoveredLine = null;
        FANO_LINES.forEach((line, i) => {
            // Simple proximity check to line
            const p1 = this.colonyPositions[line[0]];
            const p2 = this.colonyPositions[line[1]];
            const p3 = this.colonyPositions[line[2]];

            // Check distance to each segment
            [[[p1, p2], [p2, p3], [p1, p3]]].forEach(segments => {
                segments.forEach(([a, b]) => {
                    const dist = this.pointToLineDistance(x, y, a.x, a.y, b.x, b.y);
                    if (dist < 10) {
                        this.hoveredLine = i;
                    }
                });
            });
        });
    }

    pointToLineDistance(px, py, x1, y1, x2, y2) {
        const A = px - x1;
        const B = py - y1;
        const C = x2 - x1;
        const D = y2 - y1;
        const dot = A * C + B * D;
        const lenSq = C * C + D * D;
        let param = -1;
        if (lenSq !== 0) param = dot / lenSq;
        let xx, yy;
        if (param < 0) { xx = x1; yy = y1; }
        else if (param > 1) { xx = x2; yy = y2; }
        else { xx = x1 + param * C; yy = y1 + param * D; }
        const dx = px - xx;
        const dy = py - yy;
        return Math.sqrt(dx * dx + dy * dy);
    }

    onClick(e) {
        if (this.hoveredColony !== null) {
            sound.playClick();
            // Scroll to colony card
            const colonyCard = document.querySelector(`[data-colony="${COLONIES[this.hoveredColony].id}"]`);
            if (colonyCard) {
                colonyCard.scrollIntoView({ behavior: 'smooth', block: 'center' });
            }
        }
    }

    animate() {
        this.time += 0.01;
        this.draw();

        // Update particles
        this.particles.forEach(p => {
            p.progress += p.speed;
            if (p.progress > 1) {
                p.progress = 0;
                if (this.options.showParticles && Math.random() > 0.95) {
                    sound.playDataFlow(FANO_LINES[p.lineIndex][0]);
                }
            }
        });

        requestAnimationFrame(() => this.animate());
    }

    draw() {
        this.ctx.clearRect(0, 0, this.width, this.height);

        // Draw Fano lines (curved Bezier for the inscribed circle)
        FANO_LINES.forEach((line, lineIndex) => {
            const isHovered = this.hoveredLine === lineIndex;
            const p1 = this.colonyPositions[line[0]];
            const p2 = this.colonyPositions[line[1]];
            const p3 = this.colonyPositions[line[2]];

            this.ctx.beginPath();
            this.ctx.moveTo(p1.x, p1.y);

            // Draw through all three points
            // For the central point (index 3), draw straight lines
            // For peripheral points, use curves
            if (line.includes(3)) {
                // Lines through center
                this.ctx.lineTo(p2.x, p2.y);
                this.ctx.lineTo(p3.x, p3.y);
            } else {
                // Curved lines (arc through inscribed circle)
                const midX = (p1.x + p2.x + p3.x) / 3;
                const midY = (p1.y + p2.y + p3.y) / 3;
                this.ctx.quadraticCurveTo(midX, midY, p2.x, p2.y);
                this.ctx.quadraticCurveTo(midX, midY, p3.x, p3.y);
            }

            this.ctx.strokeStyle = isHovered
                ? 'rgba(212, 175, 55, 0.8)'
                : 'rgba(212, 175, 55, 0.25)';
            this.ctx.lineWidth = isHovered ? 3 : 1.5;
            this.ctx.stroke();
        });

        // Draw data flow particles
        if (this.options.showParticles) {
            this.particles.forEach(p => {
                const line = FANO_LINES[p.lineIndex];
                const pos = this.getPointOnLine(line, p.progress);

                // Glow effect
                const gradient = this.ctx.createRadialGradient(pos.x, pos.y, 0, pos.x, pos.y, p.size * 2);
                gradient.addColorStop(0, 'rgba(212, 175, 55, 0.8)');
                gradient.addColorStop(1, 'rgba(212, 175, 55, 0)');

                this.ctx.beginPath();
                this.ctx.arc(pos.x, pos.y, p.size * 2, 0, Math.PI * 2);
                this.ctx.fillStyle = gradient;
                this.ctx.fill();

                // Core
                this.ctx.beginPath();
                this.ctx.arc(pos.x, pos.y, p.size * 0.5, 0, Math.PI * 2);
                this.ctx.fillStyle = '#FFD700';
                this.ctx.fill();
            });
        }

        // Draw colony nodes
        this.colonyPositions.forEach((pos, i) => {
            const colony = COLONIES[i];
            const isHovered = this.hoveredColony === i;
            const baseSize = 20;
            const size = isHovered ? baseSize * 1.3 : baseSize;

            // Glow
            if (isHovered) {
                const gradient = this.ctx.createRadialGradient(pos.x, pos.y, 0, pos.x, pos.y, size * 2);
                gradient.addColorStop(0, `${colony.color}80`);
                gradient.addColorStop(1, 'transparent');
                this.ctx.beginPath();
                this.ctx.arc(pos.x, pos.y, size * 2, 0, Math.PI * 2);
                this.ctx.fillStyle = gradient;
                this.ctx.fill();
            }

            // Node
            this.ctx.beginPath();
            this.ctx.arc(pos.x, pos.y, size, 0, Math.PI * 2);
            this.ctx.fillStyle = colony.color;
            this.ctx.fill();

            // Border
            this.ctx.strokeStyle = isHovered ? '#fff' : 'rgba(255,255,255,0.3)';
            this.ctx.lineWidth = isHovered ? 3 : 2;
            this.ctx.stroke();

            // Label
            if (this.options.showLabels) {
                this.ctx.font = `${isHovered ? '600' : '500'} 11px "IBM Plex Mono", monospace`;
                this.ctx.fillStyle = isHovered ? '#fff' : 'rgba(255,255,255,0.7)';
                this.ctx.textAlign = 'center';
                this.ctx.textBaseline = 'middle';

                // Position label outside node
                const labelAngle = Math.atan2(pos.y - this.centerY, pos.x - this.centerX);
                const labelDist = size + 20;
                const labelX = pos.x + Math.cos(labelAngle) * labelDist;
                const labelY = pos.y + Math.sin(labelAngle) * labelDist;

                this.ctx.fillText(colony.name, labelX, labelY);
            }
        });
    }

    getPointOnLine(line, progress) {
        const p1 = this.colonyPositions[line[0]];
        const p2 = this.colonyPositions[line[1]];
        const p3 = this.colonyPositions[line[2]];

        // Interpolate along the line segments
        const totalProgress = progress * 2; // 0-2 range
        if (totalProgress < 1) {
            return {
                x: p1.x + (p2.x - p1.x) * totalProgress,
                y: p1.y + (p2.y - p1.y) * totalProgress
            };
        } else {
            const t = totalProgress - 1;
            return {
                x: p2.x + (p3.x - p2.x) * t,
                y: p2.y + (p3.y - p2.y) * t
            };
        }
    }
}

// ═══════════════════════════════════════════════════════════════════
// CATASTROPHE SURFACE RENDERER
// ═══════════════════════════════════════════════════════════════════

class CatastropheSurface {
    constructor(canvas, type) {
        this.canvas = canvas;
        this.ctx = canvas.getContext('2d');
        this.type = type;
        this.time = 0;
        this.hovered = false;

        this.resize();

        if (!MotionPreference.prefersReduced) {
            this.animate();
        } else {
            this.draw();
        }

        // Hover interaction
        const card = canvas.closest('.colony-card');
        if (card) {
            card.addEventListener('mouseenter', () => { this.hovered = true; });
            card.addEventListener('mouseleave', () => { this.hovered = false; });
        }
    }

    resize() {
        const rect = this.canvas.getBoundingClientRect();
        this.canvas.width = rect.width * window.devicePixelRatio;
        this.canvas.height = rect.height * window.devicePixelRatio;
        this.ctx.scale(window.devicePixelRatio, window.devicePixelRatio);
        this.width = rect.width;
        this.height = rect.height;
    }

    animate() {
        this.time += this.hovered ? 0.03 : 0.01;
        this.draw();
        requestAnimationFrame(() => this.animate());
    }

    draw() {
        this.ctx.clearRect(0, 0, this.width, this.height);

        const centerX = this.width / 2;
        const centerY = this.height / 2;
        const scale = Math.min(this.width, this.height) * 0.3;

        // Get the catastrophe function
        const fn = this.getCatastropheFunction();

        // Draw the surface as a contour plot
        const resolution = 80;
        const imageData = this.ctx.createImageData(this.width, this.height);

        for (let py = 0; py < this.height; py++) {
            for (let px = 0; px < this.width; px++) {
                const x = (px - centerX) / scale;
                const y = (py - centerY) / scale;
                const z = fn(x, y, this.time);

                // Map z to color
                const normalized = (Math.tanh(z * 0.5) + 1) / 2;
                const colony = COLONIES.find(c => c.catastrophe === this.type);
                const color = this.hexToRgb(colony ? colony.color : '#D4AF37');

                const idx = (py * this.width + px) * 4;
                imageData.data[idx] = color.r * normalized * 0.5;
                imageData.data[idx + 1] = color.g * normalized * 0.5;
                imageData.data[idx + 2] = color.b * normalized * 0.5;
                imageData.data[idx + 3] = 180;
            }
        }

        this.ctx.putImageData(imageData, 0, 0);

        // Draw contour lines
        this.ctx.strokeStyle = 'rgba(255, 255, 255, 0.15)';
        this.ctx.lineWidth = 1;

        for (let level = -2; level <= 2; level += 0.5) {
            this.ctx.beginPath();
            let started = false;

            for (let angle = 0; angle < Math.PI * 2; angle += 0.05) {
                for (let r = 0.1; r < 2; r += 0.1) {
                    const x = Math.cos(angle) * r;
                    const y = Math.sin(angle) * r;
                    const z = fn(x, y, this.time);

                    if (Math.abs(z - level) < 0.1) {
                        const px = centerX + x * scale;
                        const py = centerY + y * scale;
                        if (!started) {
                            this.ctx.moveTo(px, py);
                            started = true;
                        } else {
                            this.ctx.lineTo(px, py);
                        }
                    }
                }
            }
            this.ctx.stroke();
        }
    }

    getCatastropheFunction() {
        switch (this.type) {
            case 'fold':
                return (x, y, t) => Math.pow(x, 3) + Math.sin(t) * x;

            case 'cusp':
                return (x, y, t) => Math.pow(x, 4) + Math.sin(t) * x * x + Math.cos(t * 0.7) * x;

            case 'swallowtail':
                return (x, y, t) => Math.pow(x, 5) + Math.sin(t) * Math.pow(x, 3) + Math.cos(t * 0.5) * x * x + Math.sin(t * 0.3) * x;

            case 'butterfly':
                return (x, y, t) => Math.pow(x, 6) + Math.sin(t) * Math.pow(x, 4) + Math.cos(t * 0.7) * Math.pow(x, 3) + Math.sin(t * 0.5) * x * x;

            case 'hyperbolic':
                return (x, y, t) => Math.pow(x, 3) + Math.pow(y, 3) + Math.sin(t) * x * y + Math.cos(t * 0.5) * x + Math.sin(t * 0.3) * y;

            case 'elliptic':
                return (x, y, t) => Math.pow(x, 3) - 3 * x * y * y + Math.sin(t) * (x * x + y * y) + Math.cos(t * 0.5) * x;

            case 'parabolic':
                return (x, y, t) => x * x * y + Math.pow(y, 4) + Math.sin(t) * x * x + Math.cos(t * 0.5) * y * y;

            default:
                return (x, y, t) => x * x + y * y;
        }
    }

    hexToRgb(hex) {
        const result = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(hex);
        return result ? {
            r: parseInt(result[1], 16),
            g: parseInt(result[2], 16),
            b: parseInt(result[3], 16)
        } : { r: 212, g: 175, b: 55 };
    }
}

// ═══════════════════════════════════════════════════════════════════
// E8 LATTICE VISUALIZATION (2D Projection)
// ═══════════════════════════════════════════════════════════════════

class E8Visualization {
    constructor(canvas) {
        this.canvas = canvas;
        this.ctx = canvas.getContext('2d');
        this.time = 0;
        this.points = [];
        this.hovered = false;

        this.resize();
        window.addEventListener('resize', () => this.resize());

        // Generate E8 root system (simplified 2D projection)
        this.generateRoots();

        if (!MotionPreference.prefersReduced) {
            this.animate();
        } else {
            this.draw();
        }

        canvas.addEventListener('mouseenter', () => { this.hovered = true; });
        canvas.addEventListener('mouseleave', () => { this.hovered = false; });
    }

    resize() {
        const rect = this.canvas.getBoundingClientRect();
        this.canvas.width = rect.width * window.devicePixelRatio;
        this.canvas.height = rect.height * window.devicePixelRatio;
        this.ctx.scale(window.devicePixelRatio, window.devicePixelRatio);
        this.width = rect.width;
        this.height = rect.height;
    }

    generateRoots() {
        // Generate 240 root vectors of E8 (simplified 2D projection using Coxeter plane)
        this.points = [];
        const n = 240;

        for (let i = 0; i < n; i++) {
            // Use golden ratio based projection
            const phi = (1 + Math.sqrt(5)) / 2;
            const angle1 = (i / n) * Math.PI * 2;
            const angle2 = (i * phi) * Math.PI * 2;

            // Project to 2D using combination of angles
            const r = 0.7 + 0.3 * Math.sin(i * 0.1);
            const x = Math.cos(angle1) * r + Math.cos(angle2) * 0.3;
            const y = Math.sin(angle1) * r + Math.sin(angle2) * 0.3;

            this.points.push({ x, y, phase: i / n });
        }
    }

    animate() {
        this.time += this.hovered ? 0.008 : 0.003;
        this.draw();
        requestAnimationFrame(() => this.animate());
    }

    draw() {
        this.ctx.clearRect(0, 0, this.width, this.height);

        const centerX = this.width / 2;
        const centerY = this.height / 2;
        const scale = Math.min(this.width, this.height) * 0.4;

        // Draw connections between nearby points
        this.ctx.strokeStyle = 'rgba(212, 175, 55, 0.08)';
        this.ctx.lineWidth = 0.5;

        for (let i = 0; i < this.points.length; i++) {
            for (let j = i + 1; j < this.points.length; j++) {
                const p1 = this.points[i];
                const p2 = this.points[j];
                const dx = p1.x - p2.x;
                const dy = p1.y - p2.y;
                const dist = Math.sqrt(dx * dx + dy * dy);

                if (dist < 0.25) {
                    const x1 = centerX + p1.x * scale;
                    const y1 = centerY + p1.y * scale;
                    const x2 = centerX + p2.x * scale;
                    const y2 = centerY + p2.y * scale;

                    this.ctx.beginPath();
                    this.ctx.moveTo(x1, y1);
                    this.ctx.lineTo(x2, y2);
                    this.ctx.stroke();
                }
            }
        }

        // Draw points with pulsing animation
        this.points.forEach((p, i) => {
            const pulse = Math.sin(this.time * 2 + p.phase * Math.PI * 2) * 0.5 + 0.5;
            const size = 1.5 + pulse * 1.5;
            const opacity = 0.3 + pulse * 0.5;

            const x = centerX + p.x * scale;
            const y = centerY + p.y * scale;

            // Glow
            const gradient = this.ctx.createRadialGradient(x, y, 0, x, y, size * 3);
            gradient.addColorStop(0, `rgba(212, 175, 55, ${opacity * 0.5})`);
            gradient.addColorStop(1, 'transparent');
            this.ctx.beginPath();
            this.ctx.arc(x, y, size * 3, 0, Math.PI * 2);
            this.ctx.fillStyle = gradient;
            this.ctx.fill();

            // Core
            this.ctx.beginPath();
            this.ctx.arc(x, y, size, 0, Math.PI * 2);
            this.ctx.fillStyle = `rgba(255, 215, 0, ${opacity})`;
            this.ctx.fill();
        });
    }
}

// ═══════════════════════════════════════════════════════════════════
// SAFETY BARRIER VISUALIZATION
// ═══════════════════════════════════════════════════════════════════

class SafetyVisualization {
    constructor(canvas) {
        this.canvas = canvas;
        this.ctx = canvas.getContext('2d');
        this.time = 0;
        this.hValue = 1.0; // Safety barrier value, 0 = boundary

        this.resize();
        window.addEventListener('resize', () => this.resize());

        if (!MotionPreference.prefersReduced) {
            this.animate();
        } else {
            this.draw();
        }

        // Make h(x) interactive
        canvas.addEventListener('mousemove', (e) => this.onMouseMove(e));
        canvas.addEventListener('mouseleave', () => {
            this.hValue = 1.0;
            document.querySelector('.safety-barrier-overlay')?.classList.remove('warning');
        });
    }

    resize() {
        const rect = this.canvas.getBoundingClientRect();
        this.canvas.width = rect.width * window.devicePixelRatio;
        this.canvas.height = rect.height * window.devicePixelRatio;
        this.ctx.scale(window.devicePixelRatio, window.devicePixelRatio);
        this.width = rect.width;
        this.height = rect.height;
    }

    onMouseMove(e) {
        const rect = this.canvas.getBoundingClientRect();
        const x = (e.clientX - rect.left) / rect.width;
        const y = (e.clientY - rect.top) / rect.height;

        // Calculate distance from center (safety zone)
        const dx = x - 0.5;
        const dy = y - 0.5;
        const dist = Math.sqrt(dx * dx + dy * dy);

        // h(x) decreases as we approach boundary
        this.hValue = Math.max(0.05, 1 - dist * 2.5);

        // Show warning overlay when approaching boundary
        const overlay = document.querySelector('.safety-barrier-overlay');
        if (this.hValue < 0.3) {
            overlay?.classList.add('warning');
            if (this.hValue < 0.15) {
                sound.playSafetyWarning();
            }
        } else {
            overlay?.classList.remove('warning');
        }
    }

    animate() {
        this.time += 0.01;
        this.draw();
        requestAnimationFrame(() => this.animate());
    }

    draw() {
        this.ctx.clearRect(0, 0, this.width, this.height);

        const centerX = this.width / 2;
        const centerY = this.height / 2;
        const maxRadius = Math.min(this.width, this.height) * 0.45;

        // Draw concentric safety zones
        const zones = [
            { radius: 0.3, color: 'rgba(78, 203, 113, 0.3)', label: 'Safe' },
            { radius: 0.6, color: 'rgba(255, 171, 64, 0.2)', label: 'Caution' },
            { radius: 0.9, color: 'rgba(255, 107, 107, 0.15)', label: 'Warning' },
            { radius: 1.0, color: 'rgba(255, 107, 107, 0.3)', label: 'Boundary' }
        ];

        zones.forEach((zone, i) => {
            const gradient = this.ctx.createRadialGradient(
                centerX, centerY, maxRadius * (zone.radius - 0.2),
                centerX, centerY, maxRadius * zone.radius
            );
            gradient.addColorStop(0, 'transparent');
            gradient.addColorStop(1, zone.color);

            this.ctx.beginPath();
            this.ctx.arc(centerX, centerY, maxRadius * zone.radius, 0, Math.PI * 2);
            this.ctx.fillStyle = gradient;
            this.ctx.fill();
        });

        // Draw boundary line (animated)
        this.ctx.beginPath();
        this.ctx.arc(centerX, centerY, maxRadius, 0, Math.PI * 2);
        this.ctx.strokeStyle = `rgba(255, 107, 107, ${0.5 + Math.sin(this.time * 3) * 0.3})`;
        this.ctx.lineWidth = 3;
        this.ctx.setLineDash([10, 5]);
        this.ctx.stroke();
        this.ctx.setLineDash([]);

        // Draw current h(x) indicator
        const indicatorRadius = maxRadius * (1 - this.hValue);
        const indicatorColor = this.hValue > 0.5 ? '#4ECB71' : this.hValue > 0.2 ? '#FFAB40' : '#FF6B6B';

        this.ctx.beginPath();
        this.ctx.arc(centerX, centerY, indicatorRadius, 0, Math.PI * 2);
        this.ctx.strokeStyle = indicatorColor;
        this.ctx.lineWidth = 4;
        this.ctx.stroke();

        // Draw h(x) value
        this.ctx.font = '600 24px "IBM Plex Mono", monospace';
        this.ctx.fillStyle = indicatorColor;
        this.ctx.textAlign = 'center';
        this.ctx.textBaseline = 'middle';
        this.ctx.fillText(`h(x) = ${this.hValue.toFixed(2)}`, centerX, centerY - 20);

        // Safety message
        this.ctx.font = '400 14px "IBM Plex Sans", sans-serif';
        this.ctx.fillStyle = 'rgba(255, 255, 255, 0.7)';
        this.ctx.fillText(
            this.hValue >= 0.5 ? 'Safe operating region' :
            this.hValue >= 0.2 ? 'Approaching boundary' :
            'DANGER: Near safety limit',
            centerX, centerY + 20
        );

        // Draw center point (current state)
        this.ctx.beginPath();
        this.ctx.arc(centerX, centerY + indicatorRadius * 0.7, 8, 0, Math.PI * 2);
        this.ctx.fillStyle = indicatorColor;
        this.ctx.fill();
        this.ctx.strokeStyle = '#fff';
        this.ctx.lineWidth = 2;
        this.ctx.stroke();
    }
}

// ═══════════════════════════════════════════════════════════════════
// SCROLL ANIMATIONS
// ═══════════════════════════════════════════════════════════════════

class ScrollAnimations {
    constructor() {
        this.observer = new IntersectionObserver(
            (entries) => this.handleIntersect(entries),
            { threshold: 0.1, rootMargin: '0px 0px -10% 0px' }
        );

        // Observe animatable elements
        document.querySelectorAll('.colony-card, .package-card, .section-header, .e8-stat, .house-stat, .pipeline-stage').forEach(el => {
            el.style.opacity = '0';
            el.style.transform = 'translateY(30px)';
            this.observer.observe(el);
        });
    }

    handleIntersect(entries) {
        entries.forEach((entry, index) => {
            if (entry.isIntersecting) {
                setTimeout(() => {
                    entry.target.style.transition = `opacity ${TIMING.LONG}ms ease-out, transform ${TIMING.LONG}ms ease-out`;
                    entry.target.style.opacity = '1';
                    entry.target.style.transform = 'translateY(0)';
                }, index * 50);
                this.observer.unobserve(entry.target);
            }
        });
    }
}

// ═══════════════════════════════════════════════════════════════════
// EASTER EGG — Kagami⁻¹ Modal
// ═══════════════════════════════════════════════════════════════════

class EasterEgg {
    constructor() {
        this.modal = document.getElementById('shadow-modal');
        this.trigger = document.querySelector('.shadow-trigger');
        this.closeBtn = this.modal?.querySelector('.modal-close');

        if (!this.trigger || !this.modal) return;

        this.trigger.addEventListener('click', () => this.show());
        this.trigger.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                this.show();
            }
        });

        this.closeBtn?.addEventListener('click', () => this.hide());
        this.modal.addEventListener('click', (e) => {
            if (e.target === this.modal) this.hide();
        });

        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && this.modal.classList.contains('active')) {
                this.hide();
            }
        });
    }

    show() {
        sound.playSafetyWarning();
        this.modal.classList.add('active');
        this.modal.setAttribute('aria-hidden', 'false');
        this.closeBtn?.focus();
        document.body.style.overflow = 'hidden';
    }

    hide() {
        this.modal.classList.remove('active');
        this.modal.setAttribute('aria-hidden', 'true');
        document.body.style.overflow = '';
        this.trigger?.focus();
    }
}

// ═══════════════════════════════════════════════════════════════════
// COUNT-UP ANIMATION
// ═══════════════════════════════════════════════════════════════════

class CountUp {
    constructor() {
        this.observer = new IntersectionObserver(
            (entries) => this.handleIntersect(entries),
            { threshold: 0.5 }
        );

        document.querySelectorAll('[data-count]').forEach(el => {
            this.observer.observe(el);
        });
    }

    handleIntersect(entries) {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                this.animateCount(entry.target);
                this.observer.unobserve(entry.target);
            }
        });
    }

    animateCount(el) {
        const target = parseInt(el.dataset.count, 10);
        const duration = TIMING.SLOW;
        const start = performance.now();

        const update = (now) => {
            const elapsed = now - start;
            const progress = Math.min(elapsed / duration, 1);
            const eased = 1 - Math.pow(1 - progress, 3); // Ease out cubic
            const current = Math.floor(eased * target);

            el.textContent = current.toLocaleString();

            if (progress < 1) {
                requestAnimationFrame(update);
            } else {
                el.textContent = target.toLocaleString();
            }
        };

        requestAnimationFrame(update);
    }
}

// ═══════════════════════════════════════════════════════════════════
// INITIALIZATION
// ═══════════════════════════════════════════════════════════════════

document.addEventListener('DOMContentLoaded', () => {
    // Load sound preference
    sound.loadPreference();

    // Initialize sound on first interaction
    document.addEventListener('click', () => sound.init(), { once: true });
    document.addEventListener('keydown', () => sound.init(), { once: true });

    // Sound toggle button
    const soundToggle = document.getElementById('sound-toggle');
    if (soundToggle) {
        soundToggle.addEventListener('click', () => {
            sound.init().then(() => sound.toggle());
        });
    }

    // Initialize cursor
    new CustomCursor();

    // Initialize background particles
    const particlesCanvas = document.querySelector('.particles-canvas');
    if (particlesCanvas) {
        new ParticleSystem(particlesCanvas);
    }

    // Initialize hero Fano plane
    const fanoHero = document.getElementById('fano-hero');
    if (fanoHero) {
        new FanoPlane(fanoHero, { interactive: true, showParticles: true, showLabels: true });
    }

    // Initialize detailed Fano plane
    const fanoDetailed = document.getElementById('fano-detailed');
    if (fanoDetailed) {
        new FanoPlane(fanoDetailed, { interactive: true, showParticles: true, showLabels: true });
    }

    // Initialize catastrophe surfaces
    document.querySelectorAll('.catastrophe-canvas').forEach(canvas => {
        const type = canvas.dataset.type;
        if (type) {
            new CatastropheSurface(canvas, type);
        }
    });

    // Initialize E8 visualization
    const e8Canvas = document.getElementById('e8-canvas');
    if (e8Canvas) {
        new E8Visualization(e8Canvas);
    }

    // Initialize safety visualization
    const safetyCanvas = document.getElementById('safety-canvas');
    if (safetyCanvas) {
        new SafetyVisualization(safetyCanvas);
    }

    // Initialize scroll animations
    if (!MotionPreference.prefersReduced) {
        new ScrollAnimations();
    }

    // Initialize count-up animations
    new CountUp();

    // Initialize easter egg
    new EasterEgg();

    // Explore button scroll
    const exploreBtn = document.getElementById('btn-explore');
    if (exploreBtn) {
        exploreBtn.addEventListener('click', () => {
            sound.playClick();
            document.querySelector('.colonies-section')?.scrollIntoView({ behavior: 'smooth' });
        });
    }

    // Scroll indicator click + keyboard (accessibility)
    const scrollIndicator = document.querySelector('.scroll-indicator');
    if (scrollIndicator) {
        const scrollToColonies = () => {
            sound.playClick();
            document.querySelector('.colonies-section')?.scrollIntoView({ behavior: 'smooth' });
        };
        scrollIndicator.addEventListener('click', scrollToColonies);
        scrollIndicator.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                scrollToColonies();
            }
        });
    }

    // Fano line hover interactions
    document.querySelectorAll('.fano-line').forEach(el => {
        el.addEventListener('mouseenter', () => {
            sound.playHover();
        });
    });

    // Console easter egg
    console.log('%c鏡 Kagami Architecture', 'color: #D4AF37; font-size: 24px; font-weight: bold;');
    console.log('%cSeven colonies. One mind. Infinite craft.', 'color: #888; font-size: 12px;');
    console.log('%ch(x) ≥ 0 always', 'color: #4ECB71; font-size: 14px;');
    console.log('%ccraft(x) → ∞ always', 'color: #D4AF37; font-size: 14px;');
});
