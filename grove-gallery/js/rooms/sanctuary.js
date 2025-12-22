// Grove's Sanctuary - Enhanced Elliptic Vortex with Depth, Avatar, Swarm, and Sound

/**
 * Simple Perlin noise generator for organic motion
 */
class SimplexNoise {
    constructor() {
        this.perm = this.generatePermutation();
    }

    generatePermutation() {
        const p = [];
        for (let i = 0; i < 256; i++) p[i] = i;
        for (let i = 255; i > 0; i--) {
            const j = Math.floor(Math.random() * (i + 1));
            [p[i], p[j]] = [p[j], p[i]];
        }
        return p.concat(p);
    }

    fade(t) {
        return t * t * t * (t * (t * 6 - 15) + 10);
    }

    lerp(a, b, t) {
        return a + t * (b - a);
    }

    grad(hash, x, y) {
        const h = hash & 3;
        return ((h & 1) === 0 ? x : -x) + ((h & 2) === 0 ? y : -y);
    }

    noise(x, y) {
        const X = Math.floor(x) & 255;
        const Y = Math.floor(y) & 255;

        x -= Math.floor(x);
        y -= Math.floor(y);

        const u = this.fade(x);
        const v = this.fade(y);

        const a = this.perm[X] + Y;
        const b = this.perm[X + 1] + Y;

        return this.lerp(
            this.lerp(this.grad(this.perm[a], x, y), this.grad(this.perm[b], x - 1, y), u),
            this.lerp(this.grad(this.perm[a + 1], x, y - 1), this.grad(this.perm[b + 1], x - 1, y - 1), u),
            v
        );
    }
}

/**
 * Message Typewriter Effect
 */
class MessageRevealer {
    constructor(element) {
        this.element = element;
        this.originalText = element.textContent;
        this.currentIndex = 0;
        this.element.textContent = '';
    }

    async reveal(speed = 30, onCharacter = null) {
        return new Promise(resolve => {
            const interval = setInterval(() => {
                if (this.currentIndex < this.originalText.length) {
                    this.element.textContent += this.originalText[this.currentIndex];

                    if (onCharacter && this.originalText[this.currentIndex] !== ' ') {
                        onCharacter();
                    }

                    this.currentIndex++;
                } else {
                    clearInterval(interval);
                    resolve();
                }
            }, speed);
        });
    }
}

export class Sanctuary {
    constructor(soundSystem = null) {
        this.canvas = document.getElementById('elliptic-canvas');
        this.ctx = this.canvas?.getContext('2d');
        this.soundSystem = soundSystem;

        this.particles = [];
        this.particleCount = 100;
        this.time = 0;
        this.noise = new SimplexNoise();

        // Avatar (Grove's tracking orb)
        this.avatar = {
            x: 0,
            y: 0,
            targetX: 0,
            targetY: 0,
            size: 20,
            glow: 0,
        };

        // Mouse tracking
        this.mouse = {
            x: 0,
            y: 0,
            inVortex: false,
            clicking: false,
        };

        // State
        this.mode = 'orbit'; // 'orbit', 'swarm', 'burst', 'reform'
        this.burstTime = 0;
        this.rustlingSound = null;
        this.messageRevealed = false;

        this.init();
    }

    init() {
        if (!this.canvas || !this.ctx) return;

        this.resize();
        window.addEventListener('resize', this.resize.bind(this));

        // Initialize particles in elliptic pattern with z-depth
        for (let i = 0; i < this.particleCount; i++) {
            this.particles.push({
                angle: (i / this.particleCount) * Math.PI * 2,
                radius: 0.3 + Math.random() * 0.4,
                speed: 0.5 + Math.random() * 0.5,
                size: 2 + Math.random() * 3,
                offset: Math.random() * Math.PI * 2,
                z: Math.random() * 100 - 50, // -50 to +50 (depth)
                vx: 0,
                vy: 0,
                trail: [],
            });
        }

        // Mouse events
        this.canvas.addEventListener('mousemove', this.onMouseMove.bind(this));
        this.canvas.addEventListener('mousedown', this.onMouseDown.bind(this));
        this.canvas.addEventListener('mouseup', this.onMouseUp.bind(this));
        this.canvas.addEventListener('mouseenter', this.onMouseEnter.bind(this));
        this.canvas.addEventListener('mouseleave', this.onMouseLeave.bind(this));

        // Initialize avatar position
        this.avatar.x = this.canvas.width / 2;
        this.avatar.y = this.canvas.height / 2;
        this.avatar.targetX = this.avatar.x;
        this.avatar.targetY = this.avatar.y;

        // Message typewriter effect (trigger when visible)
        this.setupMessageReveal();

        this.animate();
    }

    resize() {
        const size = Math.min(this.canvas.parentElement.clientWidth, this.canvas.parentElement.clientHeight);
        this.canvas.width = size;
        this.canvas.height = size;

        // Update avatar center
        this.avatar.targetX = size / 2;
        this.avatar.targetY = size / 2;
    }

    setupMessageReveal() {
        const messageElement = document.querySelector('.grove-message .message-content');
        if (!messageElement || this.messageRevealed) return;

        const observer = new IntersectionObserver(entries => {
            entries.forEach(entry => {
                if (entry.isIntersecting && !this.messageRevealed) {
                    this.messageRevealed = true;

                    // Get all paragraphs
                    const paragraphs = messageElement.querySelectorAll('p');
                    let delay = 0;

                    paragraphs.forEach((p, i) => {
                        setTimeout(() => {
                            const revealer = new MessageRevealer(p);
                            revealer.reveal(30, () => {
                                if (this.soundSystem) {
                                    // Typewriter: Random pentatonic note, slight pan variation
                                    const pan = (Math.random() - 0.5) * 0.4; // Subtle stereo spread
                                    this.soundSystem.playParticleSpawn(pan);
                                }
                            });
                        }, delay);
                        delay += p.textContent.length * 30 + 500; // Delay between paragraphs
                    });
                }
            });
        }, { threshold: 0.3 });

        observer.observe(messageElement);
    }

    onMouseMove(e) {
        const rect = this.canvas.getBoundingClientRect();
        this.mouse.x = e.clientX - rect.left;
        this.mouse.y = e.clientY - rect.top;
    }

    onMouseDown(e) {
        this.mouse.clicking = true;
        if (this.mouse.inVortex) {
            this.mode = 'burst';
            this.burstTime = this.time;
            this.burstFromCursor();
        }
    }

    onMouseUp(e) {
        this.mouse.clicking = false;
    }

    onMouseEnter(e) {
        if (this.soundSystem && !this.rustlingSound) {
            this.rustlingSound = this.soundSystem.playRustlingLeaves();
            if (this.rustlingSound) {
                // Fade in over 2 seconds
                this.rustlingSound.gain.gain.exponentialRampToValueAtTime(
                    0.15,
                    this.soundSystem.context.currentTime + 2.0
                );
            }
        }
    }

    onMouseLeave(e) {
        this.mouse.inVortex = false;
        this.mode = 'orbit';

        if (this.soundSystem && this.rustlingSound) {
            // Fade out
            this.rustlingSound.gain.gain.exponentialRampToValueAtTime(
                0.001,
                this.soundSystem.context.currentTime + 1.0
            );
            setTimeout(() => {
                if (this.rustlingSound) {
                    this.rustlingSound.source.stop();
                    this.rustlingSound = null;
                }
            }, 1000);
        }
    }

    checkCursorInVortex() {
        const { width, height } = this.canvas;
        const centerX = width / 2;
        const centerY = height / 2;
        const maxRadius = Math.min(width, height) * 0.4;

        const dx = this.mouse.x - centerX;
        const dy = this.mouse.y - centerY;
        const dist = Math.sqrt(dx * dx + dy * dy);

        const wasInVortex = this.mouse.inVortex;
        this.mouse.inVortex = dist < maxRadius;

        // Trigger swarm mode when entering vortex
        if (!wasInVortex && this.mouse.inVortex && this.mode === 'orbit') {
            this.mode = 'swarm';
            if (this.soundSystem) {
                this.soundSystem.playSoftChime();
            }
        }

        // Return to orbit when leaving vortex
        if (wasInVortex && !this.mouse.inVortex && this.mode === 'swarm') {
            this.mode = 'orbit';
        }
    }

    swarmToCursor() {
        this.particles.forEach(p => {
            const dx = this.mouse.x - p.x;
            const dy = this.mouse.y - p.y;
            const dist = Math.sqrt(dx * dx + dy * dy) + 1;

            // Force toward cursor (inverse square law)
            const force = Math.min(100 / dist, 5);
            p.vx += (dx / dist) * force * 0.01;
            p.vy += (dy / dist) * force * 0.01;

            // Add orbital component (spiral)
            const angle = Math.atan2(dy, dx);
            p.vx += -Math.sin(angle) * force * 0.005;
            p.vy += Math.cos(angle) * force * 0.005;

            // Update position
            p.x += p.vx;
            p.y += p.vy;

            // Damping
            p.vx *= 0.95;
            p.vy *= 0.95;
        });
    }

    burstFromCursor() {
        this.particles.forEach(p => {
            const dx = p.x - this.mouse.x;
            const dy = p.y - this.mouse.y;
            const dist = Math.sqrt(dx * dx + dy * dy) + 1;

            // Explosive force outward
            const force = 10;
            p.vx = (dx / dist) * force;
            p.vy = (dy / dist) * force;

            // Initialize trail
            p.trail = [{ x: p.x, y: p.y, alpha: 1.0 }];
        });

        if (this.soundSystem) {
            // Spatial audio based on cursor position (normalized to -1...1)
            const pan = (this.mouse.x / this.canvas.width) * 2 - 1;
            this.soundSystem.playParticleSpawn(pan);
        }
    }

    updateAvatar() {
        // Smooth follow cursor with elastic easing
        const dx = this.avatar.targetX - this.avatar.x;
        const dy = this.avatar.targetY - this.avatar.y;
        this.avatar.x += dx * 0.1;
        this.avatar.y += dy * 0.1;

        // When cursor is near, avatar moves toward it
        const distToCursor = Math.sqrt(
            Math.pow(this.mouse.x - this.avatar.x, 2) +
            Math.pow(this.mouse.y - this.avatar.y, 2)
        );

        if (distToCursor < 200) {
            const centerX = this.canvas.width / 2;
            const centerY = this.canvas.height / 2;
            this.avatar.targetX = centerX + (this.mouse.x - centerX) * 0.3;
            this.avatar.targetY = centerY + (this.mouse.y - centerY) * 0.3;
            this.avatar.glow = Math.min(1, this.avatar.glow + 0.05);
        } else {
            this.avatar.targetX = this.canvas.width / 2;
            this.avatar.targetY = this.canvas.height / 2;
            this.avatar.glow = Math.max(0, this.avatar.glow - 0.02);
        }
    }

    drawAvatar() {
        // Outer glow
        const gradient = this.ctx.createRadialGradient(
            this.avatar.x, this.avatar.y, 0,
            this.avatar.x, this.avatar.y, this.avatar.size * 3
        );
        gradient.addColorStop(0, `rgba(48, 209, 88, ${0.6 * this.avatar.glow})`);
        gradient.addColorStop(0.5, `rgba(48, 209, 88, ${0.2 * this.avatar.glow})`);
        gradient.addColorStop(1, 'rgba(48, 209, 88, 0)');

        this.ctx.fillStyle = gradient;
        this.ctx.beginPath();
        this.ctx.arc(this.avatar.x, this.avatar.y, this.avatar.size * 3, 0, Math.PI * 2);
        this.ctx.fill();

        // Core orb
        this.ctx.fillStyle = '#30D158';
        this.ctx.shadowBlur = 20 * this.avatar.glow;
        this.ctx.shadowColor = '#30D158';
        this.ctx.beginPath();
        this.ctx.arc(this.avatar.x, this.avatar.y, this.avatar.size, 0, Math.PI * 2);
        this.ctx.fill();
        this.ctx.shadowBlur = 0;
    }

    updateParticles() {
        const { width, height } = this.canvas;
        const centerX = width / 2;
        const centerY = height / 2;
        const maxRadius = Math.min(width, height) * 0.4;

        this.particles.forEach((p, i) => {
            if (this.mode === 'burst') {
                // Update trail
                if (p.trail.length > 0) {
                    p.trail.forEach(t => t.alpha *= 0.9);
                    p.trail = p.trail.filter(t => t.alpha > 0.05);
                    p.trail.unshift({ x: p.x, y: p.y, alpha: 1.0 });
                    if (p.trail.length > 5) p.trail.pop();
                }

                // Continue burst momentum
                p.x += p.vx;
                p.y += p.vy;
                p.vx *= 0.95;
                p.vy *= 0.95;

                // Check if burst is done (particles slowed down)
                if (this.time - this.burstTime > 2.0) {
                    this.mode = 'reform';
                }
            } else if (this.mode === 'reform') {
                // Return to orbit positions
                const targetAngle = p.angle + this.time * p.speed;
                const spiralFactor = Math.sin(this.time * p.speed + p.offset) * 0.2;
                const currentRadius = maxRadius * (p.radius + spiralFactor);
                const a = currentRadius;
                const b = currentRadius * 0.7;

                const targetX = centerX + a * Math.cos(targetAngle);
                const targetY = centerY + b * Math.sin(targetAngle);

                // Smooth return
                const dx = targetX - p.x;
                const dy = targetY - p.y;
                p.vx = dx * 0.05;
                p.vy = dy * 0.05;

                p.x += p.vx;
                p.y += p.vy;

                // Clear trails
                p.trail = [];

                // Check if reformed
                const dist = Math.sqrt(dx * dx + dy * dy);
                if (dist < 5) {
                    this.mode = 'orbit';
                }
            } else if (this.mode === 'swarm') {
                this.swarmToCursor();
            } else {
                // Orbit mode (elliptic motion)
                const spiralFactor = Math.sin(this.time * p.speed + p.offset) * 0.2;
                const currentRadius = maxRadius * (p.radius + spiralFactor);

                const a = currentRadius;
                const b = currentRadius * 0.7;
                const angle = p.angle + this.time * p.speed;

                p.x = centerX + a * Math.cos(angle);
                p.y = centerY + b * Math.sin(angle);

                // Add Perlin noise turbulence for organic wobble
                const noiseVal = this.noise.noise(p.x * 0.01, p.y * 0.01);
                p.x += noiseVal * 0.5;
                p.y += noiseVal * 0.5;

                // Reset velocities
                p.vx = 0;
                p.vy = 0;
            }

            // Update z-depth (slow oscillation)
            p.z = Math.sin(this.time * 0.5 + p.offset) * 50;
        });
    }

    drawParticles() {
        this.particles.forEach((p, i) => {
            // Calculate depth-based properties
            const depth = (p.z + 50) / 100; // 0 to 1
            const alpha = 0.3 + depth * 0.7;
            const size = p.size * (0.5 + depth * 0.5);

            // Draw trail (burst mode only)
            if (p.trail && p.trail.length > 1) {
                this.ctx.strokeStyle = `rgba(48, 209, 88, 0.5)`;
                this.ctx.lineWidth = 1;
                this.ctx.beginPath();
                this.ctx.moveTo(p.trail[0].x, p.trail[0].y);
                for (let i = 1; i < p.trail.length; i++) {
                    this.ctx.lineTo(p.trail[i].x, p.trail[i].y);
                }
                this.ctx.stroke();
            }

            // Draw particle glow
            const gradient = this.ctx.createRadialGradient(p.x, p.y, 0, p.x, p.y, size * 3);
            gradient.addColorStop(0, `rgba(48, 209, 88, ${alpha * 0.8})`);
            gradient.addColorStop(1, 'rgba(48, 209, 88, 0)');
            this.ctx.fillStyle = gradient;
            this.ctx.beginPath();
            this.ctx.arc(p.x, p.y, size * 3, 0, Math.PI * 2);
            this.ctx.fill();

            // Draw particle core
            this.ctx.fillStyle = `rgba(48, 209, 88, ${alpha})`;
            this.ctx.beginPath();
            this.ctx.arc(p.x, p.y, size, 0, Math.PI * 2);
            this.ctx.fill();
        });
    }

    drawConnections() {
        this.particles.forEach((p1, i) => {
            this.particles.slice(i + 1).forEach(p2 => {
                const dx = p2.x - p1.x;
                const dy = p2.y - p1.y;
                const dist = Math.sqrt(dx * dx + dy * dy);

                if (dist < 50) {
                    // Fade opacity based on distance
                    const opacity = 1 - (dist / 50);

                    // Depth-based alpha
                    const depth1 = (p1.z + 50) / 100;
                    const depth2 = (p2.z + 50) / 100;
                    const avgDepth = (depth1 + depth2) / 2;
                    const depthAlpha = 0.3 + avgDepth * 0.7;

                    // Gradient line
                    const gradient = this.ctx.createLinearGradient(p1.x, p1.y, p2.x, p2.y);
                    gradient.addColorStop(0, `rgba(48, 209, 88, ${depthAlpha * opacity * 0.3})`);
                    gradient.addColorStop(1, `rgba(48, 209, 88, ${depthAlpha * opacity * 0.3})`);
                    this.ctx.strokeStyle = gradient;
                    this.ctx.lineWidth = opacity * 2;

                    this.ctx.beginPath();
                    this.ctx.moveTo(p1.x, p1.y);
                    this.ctx.lineTo(p2.x, p2.y);
                    this.ctx.stroke();
                }
            });
        });
    }

    animate() {
        requestAnimationFrame(this.animate.bind(this));

        if (!this.ctx) return;

        const { width, height } = this.canvas;
        const centerX = width / 2;
        const centerY = height / 2;

        this.time += 0.01;

        // Clear with fade effect
        this.ctx.fillStyle = 'rgba(10, 10, 12, 0.05)';
        this.ctx.fillRect(0, 0, width, height);

        // Check cursor position
        this.checkCursorInVortex();

        // Update avatar
        this.updateAvatar();

        // Update particles
        this.updateParticles();

        // Sort particles by z-depth (back to front)
        const sortedParticles = [...this.particles].sort((a, b) => a.z - b.z);

        // Draw connections (only in orbit/swarm modes)
        if (this.mode === 'orbit' || this.mode === 'swarm') {
            this.drawConnections();
        }

        // Draw particles
        this.drawParticles();

        // Draw avatar
        this.drawAvatar();

        // Draw center convergence point (only in orbit mode)
        if (this.mode === 'orbit') {
            const pulseSize = 5 + Math.sin(this.time * 2) * 3;
            const gradient = this.ctx.createRadialGradient(centerX, centerY, 0, centerX, centerY, pulseSize * 3);
            gradient.addColorStop(0, 'rgba(48, 209, 88, 0.8)');
            gradient.addColorStop(1, 'rgba(48, 209, 88, 0)');
            this.ctx.fillStyle = gradient;
            this.ctx.beginPath();
            this.ctx.arc(centerX, centerY, pulseSize * 3, 0, Math.PI * 2);
            this.ctx.fill();

            this.ctx.fillStyle = 'rgba(48, 209, 88, 1)';
            this.ctx.beginPath();
            this.ctx.arc(centerX, centerY, pulseSize, 0, Math.PI * 2);
            this.ctx.fill();
        }
    }
}
