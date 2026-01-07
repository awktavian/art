/**
 * Master of Puppets — Audio-Reactive Particle Canvas
 *
 * Particles that respond to:
 * - Audio frequency data (bass, mid, treble)
 * - Note events from the orchestra
 * - Mouse/touch interaction
 * - Scroll position
 *
 * h(x) >= 0
 */

(function() {
    'use strict';

    const canvas = document.getElementById('fantasia-canvas');
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    const audio = document.getElementById('audio');

    // Audio analysis
    let audioContext = null;
    let analyser = null;
    let frequencyData = null;
    let audioConnected = false;

    // Particle system
    const particles = [];
    const MAX_PARTICLES = 150;

    // Color palette
    const COLORS = {
        void: [3, 3, 5],
        gold: [229, 184, 74],
        copper: [184, 115, 51],
        red: [139, 0, 0],
        flow: [0, 229, 204],
        strings: [193, 154, 107],
        brass: [255, 215, 0],
        woodwinds: [46, 139, 87],
        percussion: [139, 69, 19]
    };

    // State
    let width = window.innerWidth;
    let height = window.innerHeight;
    let mouseX = width / 2;
    let mouseY = height / 2;
    let scrollProgress = 0;
    let bassLevel = 0;
    let midLevel = 0;
    let trebleLevel = 0;
    let isPlaying = false;
    let activeSection = null;

    // ═══════════════════════════════════════════════════════════════════════════
    // AUDIO SETUP
    // ═══════════════════════════════════════════════════════════════════════════

    function initAudio() {
        if (audioConnected || !audio) return;

        try {
            audioContext = new (window.AudioContext || window.webkitAudioContext)();
            analyser = audioContext.createAnalyser();
            analyser.fftSize = 256;
            analyser.smoothingTimeConstant = 0.8;

            const source = audioContext.createMediaElementSource(audio);
            source.connect(analyser);
            analyser.connect(audioContext.destination);

            frequencyData = new Uint8Array(analyser.frequencyBinCount);
            audioConnected = true;

            console.log('Audio analysis connected');
        } catch (e) {
            console.warn('Audio analysis not available:', e.message);
        }
    }

    function analyzeAudio() {
        if (!analyser || !frequencyData) return;

        analyser.getByteFrequencyData(frequencyData);

        const binCount = frequencyData.length;
        const bassEnd = Math.floor(binCount * 0.15);
        const midEnd = Math.floor(binCount * 0.5);

        // Calculate levels
        let bassSum = 0, midSum = 0, trebleSum = 0;

        for (let i = 0; i < bassEnd; i++) {
            bassSum += frequencyData[i];
        }
        for (let i = bassEnd; i < midEnd; i++) {
            midSum += frequencyData[i];
        }
        for (let i = midEnd; i < binCount; i++) {
            trebleSum += frequencyData[i];
        }

        bassLevel = bassSum / (bassEnd * 255);
        midLevel = midSum / ((midEnd - bassEnd) * 255);
        trebleLevel = trebleSum / ((binCount - midEnd) * 255);
    }

    // ═══════════════════════════════════════════════════════════════════════════
    // PARTICLE CLASS
    // ═══════════════════════════════════════════════════════════════════════════

    class Particle {
        constructor(x, y, options = {}) {
            this.x = x ?? Math.random() * width;
            this.y = y ?? Math.random() * height;
            this.size = options.size ?? 1 + Math.random() * 2;
            this.baseSize = this.size;
            this.vx = (Math.random() - 0.5) * 0.5;
            this.vy = (Math.random() - 0.5) * 0.5;
            this.life = 1;
            this.decay = options.decay ?? 0.001 + Math.random() * 0.002;
            this.color = options.color ?? COLORS.gold;
            this.alpha = options.alpha ?? 0.3 + Math.random() * 0.4;
            this.pulsePhase = Math.random() * Math.PI * 2;
            this.pulseSpeed = 0.02 + Math.random() * 0.02;
            this.section = options.section ?? null;
        }

        update(dt) {
            // Fibonacci-based pulse
            this.pulsePhase += this.pulseSpeed;
            const pulse = Math.sin(this.pulsePhase) * 0.3 + 1;

            // Audio reactivity
            let audioBoost = 1;
            if (isPlaying) {
                if (this.section === 'percussion' || !this.section) {
                    audioBoost += bassLevel * 2;
                } else if (this.section === 'brass') {
                    audioBoost += midLevel * 1.5;
                } else if (this.section === 'strings' || this.section === 'woodwinds') {
                    audioBoost += trebleLevel * 1.2;
                } else {
                    audioBoost += (bassLevel + midLevel + trebleLevel) / 3 * 1.5;
                }
            }

            this.size = this.baseSize * pulse * audioBoost;

            // Movement with audio influence
            const audioMovement = isPlaying ? (bassLevel * 0.5 + 0.5) : 0.5;
            this.x += this.vx * audioMovement;
            this.y += this.vy * audioMovement;

            // Gentle drift toward center when music plays
            if (isPlaying && bassLevel > 0.3) {
                const dx = width / 2 - this.x;
                const dy = height / 2 - this.y;
                const dist = Math.sqrt(dx * dx + dy * dy);
                if (dist > 100) {
                    this.vx += (dx / dist) * 0.01 * bassLevel;
                    this.vy += (dy / dist) * 0.01 * bassLevel;
                }
            }

            // Mouse attraction
            const mdx = mouseX - this.x;
            const mdy = mouseY - this.y;
            const mdist = Math.sqrt(mdx * mdx + mdy * mdy);
            if (mdist < 200 && mdist > 10) {
                this.vx += (mdx / mdist) * 0.02;
                this.vy += (mdy / mdist) * 0.02;
            }

            // Velocity damping
            this.vx *= 0.99;
            this.vy *= 0.99;

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
            const alpha = this.alpha * this.life;
            const [r, g, b] = this.color;

            ctx.beginPath();
            ctx.arc(this.x, this.y, this.size, 0, Math.PI * 2);
            ctx.fillStyle = `rgba(${r}, ${g}, ${b}, ${alpha})`;
            ctx.fill();

            // Glow effect when audio is loud
            if (isPlaying && (bassLevel > 0.4 || this.section === activeSection)) {
                ctx.beginPath();
                ctx.arc(this.x, this.y, this.size * 2, 0, Math.PI * 2);
                ctx.fillStyle = `rgba(${r}, ${g}, ${b}, ${alpha * 0.3})`;
                ctx.fill();
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
        const count = Math.floor(3 + intensity * 5);

        for (let i = 0; i < count; i++) {
            spawnParticle({
                x: width * (0.3 + Math.random() * 0.4),
                y: height * (0.3 + Math.random() * 0.4),
                color: sectionColor,
                size: 2 + Math.random() * 3,
                alpha: 0.5 + intensity * 0.3,
                decay: 0.005 + Math.random() * 0.005,
                section: section
            });
        }

        activeSection = section;
        setTimeout(() => {
            if (activeSection === section) activeSection = null;
        }, 300);
    }

    function initParticles() {
        for (let i = 0; i < MAX_PARTICLES * 0.6; i++) {
            const colorKeys = ['gold', 'copper', 'strings', 'brass'];
            const color = COLORS[colorKeys[Math.floor(Math.random() * colorKeys.length)]];
            spawnParticle({ color });
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
        // Analyze audio if playing
        if (isPlaying) {
            analyzeAudio();
        }

        // Clear with trail effect
        ctx.fillStyle = `rgba(3, 3, 5, ${isPlaying ? 0.15 : 0.1})`;
        ctx.fillRect(0, 0, width, height);

        // Update and draw particles
        for (let i = particles.length - 1; i >= 0; i--) {
            if (!particles[i].update()) {
                particles.splice(i, 1);
            } else {
                particles[i].draw();
            }
        }

        // Spawn new particles to maintain count
        while (particles.length < MAX_PARTICLES * 0.5) {
            const colorKeys = ['gold', 'copper', 'strings', 'brass'];
            const color = COLORS[colorKeys[Math.floor(Math.random() * colorKeys.length)]];
            spawnParticle({ color });
        }

        // Draw connections when audio is loud
        if (isPlaying && bassLevel > 0.3) {
            drawConnections();
        }

        requestAnimationFrame(render);
    }

    function drawConnections() {
        ctx.strokeStyle = `rgba(229, 184, 74, ${bassLevel * 0.15})`;
        ctx.lineWidth = 0.5;

        for (let i = 0; i < particles.length; i++) {
            for (let j = i + 1; j < particles.length; j++) {
                const dx = particles[i].x - particles[j].x;
                const dy = particles[i].y - particles[j].y;
                const dist = Math.sqrt(dx * dx + dy * dy);

                if (dist < 100) {
                    ctx.beginPath();
                    ctx.moveTo(particles[i].x, particles[i].y);
                    ctx.lineTo(particles[j].x, particles[j].y);
                    ctx.stroke();
                }
            }
        }
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

    document.addEventListener('scroll', () => {
        const maxScroll = document.documentElement.scrollHeight - window.innerHeight;
        scrollProgress = window.scrollY / maxScroll;
    });

    // Listen for play/pause
    if (audio) {
        audio.addEventListener('play', () => {
            isPlaying = true;
            initAudio();
            if (audioContext && audioContext.state === 'suspended') {
                audioContext.resume();
            }
        });

        audio.addEventListener('pause', () => {
            isPlaying = false;
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
        getAudioLevels: () => ({ bass: bassLevel, mid: midLevel, treble: trebleLevel })
    };

    // ═══════════════════════════════════════════════════════════════════════════
    // INITIALIZE
    // ═══════════════════════════════════════════════════════════════════════════

    resize();
    initParticles();
    render();

    console.log('Particle canvas initialized');

})();
