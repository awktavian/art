/**
 * Master of Puppets — Audio-Reactive Particle Canvas
 *
 * WORLD-CLASS visualization synced to audio:
 * - Real-time FFT analysis with bass/mid/treble separation
 * - Waveform visualization
 * - Beat detection with burst spawning
 * - Dramatic particle behaviors tied to frequency data
 * - Orchestra section integration
 *
 * h(x) >= 0
 */

(function() {
    'use strict';

    const canvas = document.getElementById('fantasia-canvas');
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    const audio = document.getElementById('audio');

    // ═══════════════════════════════════════════════════════════════════════════
    // AUDIO ANALYSIS (Enhanced)
    // ═══════════════════════════════════════════════════════════════════════════

    let audioContext = null;
    let analyser = null;
    let analyserWaveform = null;
    let frequencyData = null;
    let waveformData = null;
    let audioConnected = false;

    // Audio levels with smoothing
    let bassLevel = 0;
    let midLevel = 0;
    let trebleLevel = 0;
    let bassSmooth = 0;
    let midSmooth = 0;
    let trebleSmooth = 0;
    let overallLevel = 0;
    let beatDetected = false;
    let lastBeatTime = 0;
    let beatThreshold = 0.35; // Lower threshold catches more beats
    let previousBass = 0;

    // ═══════════════════════════════════════════════════════════════════════════
    // PARTICLE SYSTEM (Enhanced)
    // ═══════════════════════════════════════════════════════════════════════════

    const particles = [];
    const MAX_PARTICLES = 300;
    const waveParticles = [];
    const MAX_WAVE_PARTICLES = 100;

    // Color palette
    const COLORS = {
        void: [3, 3, 5],
        gold: [229, 184, 74],
        copper: [184, 115, 51],
        red: [139, 0, 0],
        deepRed: [100, 0, 0],
        flow: [0, 229, 204],
        strings: [193, 154, 107],
        brass: [255, 215, 0],
        woodwinds: [46, 139, 87],
        percussion: [139, 69, 19],
        white: [248, 246, 242],
        purple: [102, 51, 153]
    };

    // State
    let width = window.innerWidth;
    let height = window.innerHeight;
    let mouseX = width / 2;
    let mouseY = height / 2;
    let isPlaying = false;
    let activeSection = null;
    let frameCount = 0;

    // ═══════════════════════════════════════════════════════════════════════════
    // AUDIO SETUP
    // ═══════════════════════════════════════════════════════════════════════════

    function initAudio() {
        if (audioConnected || !audio) return;

        try {
            audioContext = new (window.AudioContext || window.webkitAudioContext)();

            // Main frequency analyser - lower smoothing for punchier response
            analyser = audioContext.createAnalyser();
            analyser.fftSize = 1024;
            analyser.smoothingTimeConstant = 0.4; // Faster response

            // Waveform analyser - very responsive
            analyserWaveform = audioContext.createAnalyser();
            analyserWaveform.fftSize = 2048;
            analyserWaveform.smoothingTimeConstant = 0.1; // Near-instant

            const source = audioContext.createMediaElementSource(audio);
            source.connect(analyser);
            source.connect(analyserWaveform);
            analyser.connect(audioContext.destination);

            frequencyData = new Uint8Array(analyser.frequencyBinCount);
            waveformData = new Uint8Array(analyserWaveform.frequencyBinCount);
            audioConnected = true;

            console.log('🎵 Audio analysis connected - FFT size:', analyser.fftSize);
        } catch (e) {
            console.warn('Audio analysis not available:', e.message);
        }
    }

    function analyzeAudio() {
        if (!analyser || !frequencyData) return;

        analyser.getByteFrequencyData(frequencyData);
        if (analyserWaveform && waveformData) {
            analyserWaveform.getByteTimeDomainData(waveformData);
        }

        const binCount = frequencyData.length;
        const bassEnd = Math.floor(binCount * 0.1);     // 0-10% = sub bass + bass
        const lowMidEnd = Math.floor(binCount * 0.25);  // 10-25% = low mids
        const midEnd = Math.floor(binCount * 0.5);      // 25-50% = mids
        const trebleStart = Math.floor(binCount * 0.5); // 50-100% = treble

        // Calculate levels with better weighting
        let bassSum = 0, midSum = 0, trebleSum = 0;

        // Bass (weighted toward sub-bass)
        for (let i = 0; i < bassEnd; i++) {
            const weight = 1 + (bassEnd - i) / bassEnd; // More weight to lower frequencies
            bassSum += frequencyData[i] * weight;
        }

        // Mids
        for (let i = bassEnd; i < midEnd; i++) {
            midSum += frequencyData[i];
        }

        // Treble
        for (let i = trebleStart; i < binCount; i++) {
            trebleSum += frequencyData[i];
        }

        // Normalize to 0-1 range
        bassLevel = Math.min(1, bassSum / (bassEnd * 255 * 1.5));
        midLevel = Math.min(1, midSum / ((midEnd - bassEnd) * 255));
        trebleLevel = Math.min(1, trebleSum / ((binCount - trebleStart) * 255));

        // Smooth the levels - fast attack, slower release (Winamp style)
        const attackSmoothing = 0.4;  // Fast rise
        const releaseSmoothing = 0.1; // Slower fall

        // Attack/release smoothing for punchier visuals
        bassSmooth += (bassLevel - bassSmooth) * (bassLevel > bassSmooth ? attackSmoothing : releaseSmoothing);
        midSmooth += (midLevel - midSmooth) * (midLevel > midSmooth ? attackSmoothing : releaseSmoothing);
        trebleSmooth += (trebleLevel - trebleSmooth) * (trebleLevel > trebleSmooth ? attackSmoothing : releaseSmoothing);

        overallLevel = (bassSmooth + midSmooth + trebleSmooth) / 3;

        // Beat detection (look for sudden bass increases) - more sensitive
        const bassJump = bassLevel - previousBass;
        const now = performance.now();
        if (bassJump > 0.08 && bassLevel > beatThreshold && now - lastBeatTime > 100) {
            beatDetected = true;
            lastBeatTime = now;
            onBeat(bassLevel);
        } else {
            beatDetected = false;
        }
        previousBass = bassLevel;
    }

    function onBeat(intensity) {
        // Spawn burst of particles on beat
        const count = Math.floor(5 + intensity * 15);
        const colors = [COLORS.gold, COLORS.copper, COLORS.brass, COLORS.red];

        for (let i = 0; i < count; i++) {
            const angle = Math.random() * Math.PI * 2;
            const speed = 2 + intensity * 5;
            const color = colors[Math.floor(Math.random() * colors.length)];

            spawnParticle({
                x: width / 2 + (Math.random() - 0.5) * 200,
                y: height / 2 + (Math.random() - 0.5) * 200,
                vx: Math.cos(angle) * speed,
                vy: Math.sin(angle) * speed,
                color: color,
                size: 2 + intensity * 4,
                alpha: 0.8,
                decay: 0.008 + Math.random() * 0.005,
                glow: true
            });
        }

        // Also spawn wave particles from edges
        if (intensity > 0.5) {
            spawnWaveFromEdge(intensity);
        }
    }

    // ═══════════════════════════════════════════════════════════════════════════
    // PARTICLE CLASS (Enhanced)
    // ═══════════════════════════════════════════════════════════════════════════

    class Particle {
        constructor(x, y, options = {}) {
            this.x = x ?? Math.random() * width;
            this.y = y ?? Math.random() * height;
            this.size = options.size ?? 1 + Math.random() * 2;
            this.baseSize = this.size;
            this.vx = options.vx ?? (Math.random() - 0.5) * 0.5;
            this.vy = options.vy ?? (Math.random() - 0.5) * 0.5;
            this.life = 1;
            this.decay = options.decay ?? 0.001 + Math.random() * 0.002;
            this.color = options.color ?? COLORS.gold;
            this.alpha = options.alpha ?? 0.3 + Math.random() * 0.4;
            this.baseAlpha = this.alpha;
            this.pulsePhase = Math.random() * Math.PI * 2;
            this.pulseSpeed = 0.03 + Math.random() * 0.03;
            this.section = options.section ?? null;
            this.glow = options.glow ?? false;
            this.trail = [];
            this.maxTrail = options.glow ? 8 : 3;
        }

        update() {
            // Store trail position
            if (this.trail.length >= this.maxTrail) {
                this.trail.shift();
            }
            this.trail.push({ x: this.x, y: this.y, size: this.size });

            // Fibonacci-based pulse
            this.pulsePhase += this.pulseSpeed;
            const pulse = Math.sin(this.pulsePhase) * 0.4 + 1;

            // Audio reactivity
            let audioBoost = 1;
            if (isPlaying) {
                if (this.section === 'percussion' || this.glow) {
                    audioBoost += bassSmooth * 3;
                } else if (this.section === 'brass') {
                    audioBoost += midSmooth * 2.5;
                } else if (this.section === 'strings' || this.section === 'woodwinds') {
                    audioBoost += trebleSmooth * 2;
                } else {
                    audioBoost += overallLevel * 2;
                }
            }

            this.size = this.baseSize * pulse * audioBoost;
            this.alpha = this.baseAlpha * (0.5 + overallLevel * 0.5) * this.life;

            // Movement with audio influence
            const audioSpeed = isPlaying ? (1 + bassSmooth * 2) : 1;
            this.x += this.vx * audioSpeed;
            this.y += this.vy * audioSpeed;

            // Dramatic movement during loud parts
            if (isPlaying && bassSmooth > 0.4) {
                const dx = width / 2 - this.x;
                const dy = height / 2 - this.y;
                const dist = Math.sqrt(dx * dx + dy * dy);
                if (dist > 50) {
                    // Spiral toward center on bass hits
                    const perpX = -dy / dist;
                    const perpY = dx / dist;
                    this.vx += (dx / dist * 0.03 + perpX * 0.02) * bassSmooth;
                    this.vy += (dy / dist * 0.03 + perpY * 0.02) * bassSmooth;
                }
            }

            // Mouse interaction
            const mdx = mouseX - this.x;
            const mdy = mouseY - this.y;
            const mdist = Math.sqrt(mdx * mdx + mdy * mdy);
            if (mdist < 200 && mdist > 10) {
                this.vx += (mdx / mdist) * 0.03;
                this.vy += (mdy / mdist) * 0.03;
            }

            // Velocity damping
            this.vx *= 0.98;
            this.vy *= 0.98;

            // Wrap around edges
            if (this.x < -50) this.x = width + 50;
            if (this.x > width + 50) this.x = -50;
            if (this.y < -50) this.y = height + 50;
            if (this.y > height + 50) this.y = -50;

            // Decay
            this.life -= this.decay;

            return this.life > 0;
        }

        draw() {
            const [r, g, b] = this.color;

            // Draw trail
            if (this.trail.length > 1 && isPlaying) {
                ctx.beginPath();
                ctx.moveTo(this.trail[0].x, this.trail[0].y);
                for (let i = 1; i < this.trail.length; i++) {
                    ctx.lineTo(this.trail[i].x, this.trail[i].y);
                }
                ctx.strokeStyle = `rgba(${r}, ${g}, ${b}, ${this.alpha * 0.3})`;
                ctx.lineWidth = this.size * 0.5;
                ctx.stroke();
            }

            // Main particle
            ctx.beginPath();
            ctx.arc(this.x, this.y, this.size, 0, Math.PI * 2);
            ctx.fillStyle = `rgba(${r}, ${g}, ${b}, ${this.alpha})`;
            ctx.fill();

            // Glow effect
            if (this.glow || (isPlaying && (bassSmooth > 0.5 || this.section === activeSection))) {
                const glowSize = this.size * (2 + bassSmooth * 2);
                const gradient = ctx.createRadialGradient(
                    this.x, this.y, 0,
                    this.x, this.y, glowSize
                );
                gradient.addColorStop(0, `rgba(${r}, ${g}, ${b}, ${this.alpha * 0.5})`);
                gradient.addColorStop(1, `rgba(${r}, ${g}, ${b}, 0)`);
                ctx.beginPath();
                ctx.arc(this.x, this.y, glowSize, 0, Math.PI * 2);
                ctx.fillStyle = gradient;
                ctx.fill();
            }
        }
    }

    // ═══════════════════════════════════════════════════════════════════════════
    // WAVE PARTICLE (for dramatic moments)
    // ═══════════════════════════════════════════════════════════════════════════

    class WaveParticle {
        constructor(x, y, angle, speed, color) {
            this.x = x;
            this.y = y;
            this.vx = Math.cos(angle) * speed;
            this.vy = Math.sin(angle) * speed;
            this.size = 3 + Math.random() * 2;
            this.life = 1;
            this.color = color;
            this.alpha = 0.8;
        }

        update() {
            this.x += this.vx * (1 + bassSmooth);
            this.y += this.vy * (1 + bassSmooth);
            this.vx *= 0.99;
            this.vy *= 0.99;
            this.life -= 0.015;
            this.size *= 0.98;
            return this.life > 0;
        }

        draw() {
            const [r, g, b] = this.color;
            const a = this.alpha * this.life;

            // Core
            ctx.beginPath();
            ctx.arc(this.x, this.y, this.size, 0, Math.PI * 2);
            ctx.fillStyle = `rgba(${r}, ${g}, ${b}, ${a})`;
            ctx.fill();

            // Glow
            const gradient = ctx.createRadialGradient(
                this.x, this.y, 0,
                this.x, this.y, this.size * 3
            );
            gradient.addColorStop(0, `rgba(${r}, ${g}, ${b}, ${a * 0.5})`);
            gradient.addColorStop(1, `rgba(${r}, ${g}, ${b}, 0)`);
            ctx.beginPath();
            ctx.arc(this.x, this.y, this.size * 3, 0, Math.PI * 2);
            ctx.fillStyle = gradient;
            ctx.fill();
        }
    }

    function spawnWaveFromEdge(intensity) {
        const edge = Math.floor(Math.random() * 4);
        const count = Math.floor(10 + intensity * 20);
        const color = Math.random() > 0.5 ? COLORS.gold : COLORS.copper;

        for (let i = 0; i < count; i++) {
            let x, y, angle;
            switch (edge) {
                case 0: // Top
                    x = Math.random() * width;
                    y = 0;
                    angle = Math.PI / 2 + (Math.random() - 0.5) * 0.5;
                    break;
                case 1: // Right
                    x = width;
                    y = Math.random() * height;
                    angle = Math.PI + (Math.random() - 0.5) * 0.5;
                    break;
                case 2: // Bottom
                    x = Math.random() * width;
                    y = height;
                    angle = -Math.PI / 2 + (Math.random() - 0.5) * 0.5;
                    break;
                case 3: // Left
                    x = 0;
                    y = Math.random() * height;
                    angle = (Math.random() - 0.5) * 0.5;
                    break;
            }

            if (waveParticles.length < MAX_WAVE_PARTICLES) {
                waveParticles.push(new WaveParticle(x, y, angle, 3 + intensity * 5, color));
            }
        }
    }

    // ═══════════════════════════════════════════════════════════════════════════
    // PARTICLE MANAGEMENT
    // ═══════════════════════════════════════════════════════════════════════════

    function spawnParticle(options = {}) {
        if (particles.length < MAX_PARTICLES) {
            particles.push(new Particle(options.x, options.y, options));
        }
    }

    function spawnSectionBurst(section, intensity = 1) {
        const sectionColor = COLORS[section] || COLORS.gold;
        const count = Math.floor(5 + intensity * 10);

        for (let i = 0; i < count; i++) {
            const angle = Math.random() * Math.PI * 2;
            const speed = 1 + intensity * 3;

            spawnParticle({
                x: width / 2 + (Math.random() - 0.5) * 300,
                y: height / 2 + (Math.random() - 0.5) * 300,
                vx: Math.cos(angle) * speed,
                vy: Math.sin(angle) * speed,
                color: sectionColor,
                size: 2 + Math.random() * 4,
                alpha: 0.6 + intensity * 0.3,
                decay: 0.004 + Math.random() * 0.004,
                section: section,
                glow: true
            });
        }

        activeSection = section;
        setTimeout(() => {
            if (activeSection === section) activeSection = null;
        }, 500);
    }

    function initParticles() {
        for (let i = 0; i < MAX_PARTICLES * 0.4; i++) {
            const colorKeys = ['gold', 'copper', 'strings', 'brass'];
            const color = COLORS[colorKeys[Math.floor(Math.random() * colorKeys.length)]];
            spawnParticle({ color });
        }
    }

    // ═══════════════════════════════════════════════════════════════════════════
    // WAVEFORM VISUALIZATION
    // ═══════════════════════════════════════════════════════════════════════════

    function drawWaveform() {
        if (!waveformData || !isPlaying) return;

        const sliceWidth = width / waveformData.length;
        const centerY = height / 2;

        // Draw filled waveform (more dramatic)
        ctx.beginPath();
        ctx.moveTo(0, centerY);

        for (let i = 0; i < waveformData.length; i++) {
            const v = (waveformData[i] - 128) / 128.0; // -1 to 1
            const amplitude = height * 0.35 * (0.5 + bassSmooth * 0.5);
            const y = centerY + v * amplitude;

            if (i === 0) {
                ctx.moveTo(0, y);
            } else {
                ctx.lineTo(i * sliceWidth, y);
            }
        }

        // Close the shape for fill
        ctx.lineTo(width, centerY);
        ctx.lineTo(0, centerY);
        ctx.closePath();

        // Gradient fill
        const waveGradient = ctx.createLinearGradient(0, centerY - height * 0.3, 0, centerY + height * 0.3);
        waveGradient.addColorStop(0, `rgba(229, 184, 74, ${0.15 + overallLevel * 0.2})`);
        waveGradient.addColorStop(0.5, `rgba(229, 184, 74, ${0.05 + overallLevel * 0.1})`);
        waveGradient.addColorStop(1, `rgba(139, 0, 0, ${0.1 + bassSmooth * 0.15})`);
        ctx.fillStyle = waveGradient;
        ctx.fill();

        // Stroke the waveform line
        ctx.beginPath();
        for (let i = 0; i < waveformData.length; i++) {
            const v = (waveformData[i] - 128) / 128.0;
            const amplitude = height * 0.35 * (0.5 + bassSmooth * 0.5);
            const y = centerY + v * amplitude;

            if (i === 0) {
                ctx.moveTo(0, y);
            } else {
                ctx.lineTo(i * sliceWidth, y);
            }
        }

        ctx.strokeStyle = `rgba(229, 184, 74, ${0.3 + overallLevel * 0.4})`;
        ctx.lineWidth = 1.5 + bassSmooth * 3;
        ctx.stroke();
    }

    // ═══════════════════════════════════════════════════════════════════════════
    // FREQUENCY BARS
    // ═══════════════════════════════════════════════════════════════════════════

    function drawFrequencyBars() {
        if (!frequencyData || !isPlaying) return;

        const barCount = 128; // More bars for detail
        const barWidth = width / barCount;
        const maxHeight = height * 0.5; // Taller bars

        // Mirror effect - draw from both top and bottom
        for (let i = 0; i < barCount; i++) {
            const dataIndex = Math.floor(i * (frequencyData.length / barCount));
            const value = frequencyData[dataIndex] / 255;
            const barHeight = value * maxHeight;

            // Bottom bars - hot colors
            const gradient = ctx.createLinearGradient(0, height, 0, height - barHeight);
            gradient.addColorStop(0, `rgba(139, 0, 0, ${value * 0.7})`);
            gradient.addColorStop(0.3, `rgba(229, 184, 74, ${value * 0.6})`);
            gradient.addColorStop(0.7, `rgba(229, 184, 74, ${value * 0.4})`);
            gradient.addColorStop(1, `rgba(229, 184, 74, 0)`);

            ctx.fillStyle = gradient;
            ctx.fillRect(
                i * barWidth,
                height - barHeight,
                barWidth - 1,
                barHeight
            );

            // Top bars (mirrored, fainter) for symmetry
            const topGradient = ctx.createLinearGradient(0, 0, 0, barHeight * 0.4);
            topGradient.addColorStop(0, `rgba(139, 0, 0, ${value * 0.4})`);
            topGradient.addColorStop(1, `rgba(139, 0, 0, 0)`);

            ctx.fillStyle = topGradient;
            ctx.fillRect(
                i * barWidth,
                0,
                barWidth - 1,
                barHeight * 0.4
            );
        }
    }

    // ═══════════════════════════════════════════════════════════════════════════
    // CENTRAL ORB (responsive to audio)
    // ═══════════════════════════════════════════════════════════════════════════

    function drawCentralOrb() {
        const centerX = width / 2;
        const centerY = height / 2;
        const baseRadius = 50;

        // Idle state - gentle breathing orb
        if (!isPlaying) {
            const breathe = Math.sin(frameCount * 0.02) * 0.2 + 1;
            const idleRadius = baseRadius * breathe;

            // Subtle idle glow
            const idleGlow = ctx.createRadialGradient(
                centerX, centerY, 0,
                centerX, centerY, idleRadius * 1.5
            );
            idleGlow.addColorStop(0, 'rgba(229, 184, 74, 0.15)');
            idleGlow.addColorStop(0.5, 'rgba(229, 184, 74, 0.05)');
            idleGlow.addColorStop(1, 'rgba(0, 0, 0, 0)');

            ctx.beginPath();
            ctx.arc(centerX, centerY, idleRadius * 1.5, 0, Math.PI * 2);
            ctx.fillStyle = idleGlow;
            ctx.fill();

            // Inner idle core
            const innerIdle = ctx.createRadialGradient(
                centerX, centerY, 0,
                centerX, centerY, idleRadius
            );
            innerIdle.addColorStop(0, 'rgba(248, 246, 242, 0.1)');
            innerIdle.addColorStop(0.5, 'rgba(229, 184, 74, 0.08)');
            innerIdle.addColorStop(1, 'rgba(229, 184, 74, 0)');

            ctx.beginPath();
            ctx.arc(centerX, centerY, idleRadius, 0, Math.PI * 2);
            ctx.fillStyle = innerIdle;
            ctx.fill();

            return;
        }

        const audioRadius = baseRadius + bassSmooth * 100;

        // Outer glow
        const outerGlow = ctx.createRadialGradient(
            centerX, centerY, 0,
            centerX, centerY, audioRadius * 2
        );
        outerGlow.addColorStop(0, `rgba(229, 184, 74, ${0.1 + bassSmooth * 0.2})`);
        outerGlow.addColorStop(0.5, `rgba(139, 0, 0, ${0.05 + bassSmooth * 0.1})`);
        outerGlow.addColorStop(1, 'rgba(0, 0, 0, 0)');

        ctx.beginPath();
        ctx.arc(centerX, centerY, audioRadius * 2, 0, Math.PI * 2);
        ctx.fillStyle = outerGlow;
        ctx.fill();

        // Inner core
        const innerGlow = ctx.createRadialGradient(
            centerX, centerY, 0,
            centerX, centerY, audioRadius
        );
        innerGlow.addColorStop(0, `rgba(255, 255, 255, ${0.1 + overallLevel * 0.3})`);
        innerGlow.addColorStop(0.3, `rgba(229, 184, 74, ${0.1 + midSmooth * 0.2})`);
        innerGlow.addColorStop(1, 'rgba(229, 184, 74, 0)');

        ctx.beginPath();
        ctx.arc(centerX, centerY, audioRadius, 0, Math.PI * 2);
        ctx.fillStyle = innerGlow;
        ctx.fill();

        // Pulsing ring on beats
        if (beatDetected) {
            ctx.beginPath();
            ctx.arc(centerX, centerY, audioRadius * 1.5, 0, Math.PI * 2);
            ctx.strokeStyle = `rgba(229, 184, 74, 0.5)`;
            ctx.lineWidth = 3;
            ctx.stroke();
        }
    }

    // ═══════════════════════════════════════════════════════════════════════════
    // CONNECTION LINES
    // ═══════════════════════════════════════════════════════════════════════════

    function drawConnections() {
        // Idle state - subtle ambient connections
        if (!isPlaying) {
            const connectionDistance = 100;
            ctx.lineWidth = 0.5;

            for (let i = 0; i < Math.min(particles.length, 50); i++) {
                for (let j = i + 1; j < Math.min(particles.length, i + 10); j++) {
                    const dx = particles[i].x - particles[j].x;
                    const dy = particles[i].y - particles[j].y;
                    const dist = Math.sqrt(dx * dx + dy * dy);

                    if (dist < connectionDistance) {
                        const alpha = (1 - dist / connectionDistance) * 0.1;
                        ctx.beginPath();
                        ctx.moveTo(particles[i].x, particles[i].y);
                        ctx.lineTo(particles[j].x, particles[j].y);
                        ctx.strokeStyle = `rgba(229, 184, 74, ${alpha})`;
                        ctx.stroke();
                    }
                }
            }
            return;
        }

        if (bassSmooth < 0.2) return;

        const connectionDistance = 80 + bassSmooth * 60;
        ctx.strokeStyle = `rgba(229, 184, 74, ${bassSmooth * 0.2})`;
        ctx.lineWidth = 0.5 + bassSmooth;

        for (let i = 0; i < particles.length; i++) {
            for (let j = i + 1; j < Math.min(particles.length, i + 20); j++) {
                const dx = particles[i].x - particles[j].x;
                const dy = particles[i].y - particles[j].y;
                const dist = Math.sqrt(dx * dx + dy * dy);

                if (dist < connectionDistance) {
                    const alpha = (1 - dist / connectionDistance) * bassSmooth * 0.3;
                    ctx.beginPath();
                    ctx.moveTo(particles[i].x, particles[i].y);
                    ctx.lineTo(particles[j].x, particles[j].y);
                    ctx.strokeStyle = `rgba(229, 184, 74, ${alpha})`;
                    ctx.stroke();
                }
            }
        }
    }

    // ═══════════════════════════════════════════════════════════════════════════
    // RENDER LOOP
    // ═══════════════════════════════════════════════════════════════════════════

    function resize() {
        width = window.innerWidth;
        height = window.innerHeight;
        canvas.width = width * window.devicePixelRatio;
        canvas.height = height * window.devicePixelRatio;
        canvas.style.width = width + 'px';
        canvas.style.height = height + 'px';
        ctx.scale(window.devicePixelRatio, window.devicePixelRatio);
    }

    function render() {
        frameCount++;

        // Analyze audio if playing
        if (isPlaying) {
            analyzeAudio();
        }

        // Clear with dynamic trail effect - faster clear during playback for punchy response
        const trailOpacity = isPlaying ? (0.2 + overallLevel * 0.3) : 0.08;
        ctx.fillStyle = `rgba(3, 3, 5, ${trailOpacity})`;
        ctx.fillRect(0, 0, width, height);

        // Draw layers (back to front)
        drawFrequencyBars();
        drawWaveform();
        drawCentralOrb();
        drawConnections();

        // Update and draw main particles
        for (let i = particles.length - 1; i >= 0; i--) {
            if (!particles[i].update()) {
                particles.splice(i, 1);
            } else {
                particles[i].draw();
            }
        }

        // Update and draw wave particles
        for (let i = waveParticles.length - 1; i >= 0; i--) {
            if (!waveParticles[i].update()) {
                waveParticles.splice(i, 1);
            } else {
                waveParticles[i].draw();
            }
        }

        // Spawn new particles to maintain count
        if (particles.length < MAX_PARTICLES * 0.3) {
            const colorKeys = ['gold', 'copper', 'strings', 'brass'];
            const color = COLORS[colorKeys[Math.floor(Math.random() * colorKeys.length)]];
            spawnParticle({ color });
        }

        // Periodic spawning during playback
        if (isPlaying && frameCount % 5 === 0 && particles.length < MAX_PARTICLES * 0.7) {
            const colors = [COLORS.gold, COLORS.copper];
            spawnParticle({
                color: colors[Math.floor(Math.random() * colors.length)],
                alpha: 0.2 + overallLevel * 0.3
            });
        }

        requestAnimationFrame(render);
    }

    // ═══════════════════════════════════════════════════════════════════════════
    // EVENT LISTENERS
    // ═══════════════════════════════════════════════════════════════════════════

    window.addEventListener('resize', resize);

    document.addEventListener('mousemove', (e) => {
        mouseX = e.clientX;
        mouseY = e.clientY;
    });

    document.addEventListener('touchmove', (e) => {
        if (e.touches[0]) {
            mouseX = e.touches[0].clientX;
            mouseY = e.touches[0].clientY;
        }
    });

    // Listen for play/pause
    if (audio) {
        audio.addEventListener('play', () => {
            isPlaying = true;
            initAudio();
            if (audioContext && audioContext.state === 'suspended') {
                audioContext.resume();
            }
            console.log('▶ Visualization active');
        });

        audio.addEventListener('pause', () => {
            isPlaying = false;
            console.log('⏸ Visualization paused');
        });

        audio.addEventListener('ended', () => {
            isPlaying = false;
        });
    }

    // ═══════════════════════════════════════════════════════════════════════════
    // PUBLIC API
    // ═══════════════════════════════════════════════════════════════════════════

    window.ParticleCanvas = {
        spawnBurst: spawnSectionBurst,
        setActiveSection: (section) => { activeSection = section; },
        getAudioLevels: () => ({
            bass: bassSmooth,
            mid: midSmooth,
            treble: trebleSmooth,
            overall: overallLevel,
            beat: beatDetected
        }),
        triggerBeat: () => onBeat(0.8)
    };

    // ═══════════════════════════════════════════════════════════════════════════
    // INITIALIZE
    // ═══════════════════════════════════════════════════════════════════════════

    resize();
    initParticles();
    render();

    console.log('🎨 Audio-reactive particle canvas initialized');
    console.log('   Features: FFT analysis, beat detection, waveform, frequency bars');

})();
