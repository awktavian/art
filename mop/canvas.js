/**
 * Master of Puppets — Audio-Reactive Canvas
 * 
 * Winamp-style visualization with Web Audio API
 * 
 * h(x) ≥ 0
 */

(function() {
    'use strict';

    const canvas = document.getElementById('fantasia-canvas');
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    const audio = document.getElementById('audio');
    
    let width, height;
    let particles = [];
    let time = 0;
    let currentMovement = 0;
    
    // Audio analysis
    let audioCtx = null;
    let analyser = null;
    let dataArray = null;
    let audioConnected = false;
    
    // Movement colors
    const MOVEMENT_HUES = [45, 0, 35, 280, 200];
    const MOVEMENT_NAMES = ['Overture', 'Score', 'Transform', 'Orchestra', 'Code'];

    // =========================================================================
    // AUDIO SETUP
    // =========================================================================
    
    function connectAudio() {
        if (audioConnected || !audio) return;
        
        try {
            audioCtx = new (window.AudioContext || window.webkitAudioContext)();
            analyser = audioCtx.createAnalyser();
            analyser.fftSize = 256;
            analyser.smoothingTimeConstant = 0.8;
            
            const source = audioCtx.createMediaElementSource(audio);
            source.connect(analyser);
            analyser.connect(audioCtx.destination);
            
            dataArray = new Uint8Array(analyser.frequencyBinCount);
            audioConnected = true;
            console.log('🎵 Audio visualization connected');
        } catch (e) {
            console.warn('Audio visualization not available:', e);
        }
    }

    // Connect on first user interaction
    document.addEventListener('click', () => {
        if (!audioConnected) connectAudio();
    }, { once: true });
    
    if (audio) {
        audio.addEventListener('play', () => {
            if (!audioConnected) connectAudio();
            if (audioCtx && audioCtx.state === 'suspended') {
                audioCtx.resume();
            }
        });
    }

    // =========================================================================
    // GET AUDIO DATA
    // =========================================================================
    
    function getAudioData() {
        if (!analyser || !dataArray) {
            return { bass: 0, mid: 0, high: 0, overall: 0 };
        }
        
        analyser.getByteFrequencyData(dataArray);
        
        const len = dataArray.length;
        let bass = 0, mid = 0, high = 0;
        
        // Bass: 0-10% of frequencies
        for (let i = 0; i < len * 0.1; i++) {
            bass += dataArray[i];
        }
        bass = bass / (len * 0.1) / 255;
        
        // Mid: 10-50% of frequencies
        for (let i = Math.floor(len * 0.1); i < len * 0.5; i++) {
            mid += dataArray[i];
        }
        mid = mid / (len * 0.4) / 255;
        
        // High: 50-100% of frequencies
        for (let i = Math.floor(len * 0.5); i < len; i++) {
            high += dataArray[i];
        }
        high = high / (len * 0.5) / 255;
        
        const overall = (bass * 0.5 + mid * 0.3 + high * 0.2);
        
        return { bass, mid, high, overall };
    }

    // =========================================================================
    // RESIZE
    // =========================================================================
    
    function resize() {
        width = canvas.width = window.innerWidth;
        height = canvas.height = window.innerHeight;
        initParticles();
    }

    // =========================================================================
    // PARTICLE CLASS
    // =========================================================================
    
    class Particle {
        constructor() {
            this.reset();
        }

        reset() {
            this.x = Math.random() * width;
            this.y = Math.random() * height;
            this.baseSize = Math.random() * 2 + 0.5;
            this.size = this.baseSize;
            this.baseSpeedX = (Math.random() - 0.5) * 0.5;
            this.baseSpeedY = (Math.random() - 0.5) * 0.5;
            this.speedX = this.baseSpeedX;
            this.speedY = this.baseSpeedY;
            this.opacity = Math.random() * 0.5 + 0.1;
            this.pulseOffset = Math.random() * Math.PI * 2;
            this.type = Math.random(); // 0-0.33: bass, 0.33-0.66: mid, 0.66-1: high
        }

        update(audioData) {
            // React to audio based on particle type
            let boost = 0;
            if (this.type < 0.33) {
                boost = audioData.bass * 3;
            } else if (this.type < 0.66) {
                boost = audioData.mid * 2;
            } else {
                boost = audioData.high * 1.5;
            }
            
            // Size reacts to audio
            this.size = this.baseSize * (1 + boost * 2);
            
            // Speed reacts to audio
            const speedMult = 1 + audioData.overall * 3;
            this.speedX = this.baseSpeedX * speedMult;
            this.speedY = this.baseSpeedY * speedMult;
            
            this.x += this.speedX;
            this.y += this.speedY;

            // Wrap around
            if (this.x < -10) this.x = width + 10;
            if (this.x > width + 10) this.x = -10;
            if (this.y < -10) this.y = height + 10;
            if (this.y > height + 10) this.y = -10;
        }

        draw(audioData) {
            const pulse = Math.sin(time * 0.03 + this.pulseOffset) * 0.3 + 0.7;
            const hue = MOVEMENT_HUES[currentMovement] || 45;
            
            // Brightness reacts to audio
            const brightness = 50 + audioData.overall * 30;
            const alpha = this.opacity * pulse * (0.5 + audioData.overall * 0.5);

            ctx.beginPath();
            ctx.arc(this.x, this.y, this.size * pulse, 0, Math.PI * 2);
            ctx.fillStyle = `hsla(${hue}, 70%, ${brightness}%, ${alpha})`;
            ctx.fill();
            
            // Glow effect on bass hits
            if (audioData.bass > 0.5 && this.type < 0.33) {
                ctx.beginPath();
                ctx.arc(this.x, this.y, this.size * pulse * 3, 0, Math.PI * 2);
                ctx.fillStyle = `hsla(${hue}, 80%, 60%, ${alpha * 0.3})`;
                ctx.fill();
            }
        }
    }

    // =========================================================================
    // INIT PARTICLES
    // =========================================================================
    
    function initParticles() {
        particles = [];
        const count = Math.min(150, Math.floor((width * height) / 15000));
        for (let i = 0; i < count; i++) {
            particles.push(new Particle());
        }
    }

    // =========================================================================
    // DRAW FREQUENCY BARS (Winamp style)
    // =========================================================================
    
    function drawFrequencyBars(audioData) {
        if (!analyser || !dataArray || !audio || audio.paused) return;
        
        analyser.getByteFrequencyData(dataArray);
        
        const barCount = 64;
        const barWidth = width / barCount;
        const hue = MOVEMENT_HUES[currentMovement] || 45;
        
        ctx.save();
        ctx.globalAlpha = 0.3;
        
        for (let i = 0; i < barCount; i++) {
            const dataIndex = Math.floor(i * dataArray.length / barCount);
            const value = dataArray[dataIndex] / 255;
            const barHeight = value * height * 0.3;
            
            // Gradient from bottom
            const gradient = ctx.createLinearGradient(0, height, 0, height - barHeight);
            gradient.addColorStop(0, `hsla(${hue}, 80%, 50%, 0.8)`);
            gradient.addColorStop(1, `hsla(${hue + 30}, 70%, 70%, 0.2)`);
            
            ctx.fillStyle = gradient;
            ctx.fillRect(i * barWidth, height - barHeight, barWidth - 1, barHeight);
        }
        
        ctx.restore();
    }

    // =========================================================================
    // DRAW CENTER WAVEFORM (Oscilloscope style)
    // =========================================================================
    
    function drawWaveform(audioData) {
        if (!analyser || !audio || audio.paused) return;
        
        const timeData = new Uint8Array(analyser.fftSize);
        analyser.getByteTimeDomainData(timeData);
        
        const hue = MOVEMENT_HUES[currentMovement] || 45;
        const intensity = audioData.overall;
        
        ctx.save();
        
        // Glow effect layer
        ctx.shadowBlur = 20 + intensity * 30;
        ctx.shadowColor = `hsla(${hue}, 80%, 60%, 0.8)`;
        ctx.strokeStyle = `hsla(${hue}, 80%, 70%, ${0.6 + intensity * 0.4})`;
        ctx.lineWidth = 3 + intensity * 4;
        ctx.lineCap = 'round';
        ctx.lineJoin = 'round';
        
        ctx.beginPath();
        
        const sliceWidth = width / timeData.length;
        let x = 0;
        
        for (let i = 0; i < timeData.length; i++) {
            const v = timeData[i] / 128.0;
            // Bigger amplitude - fills more of screen
            const amplitude = height * 0.35 * (1 + intensity * 0.5);
            const y = (v - 1) * amplitude + height / 2;
            
            if (i === 0) {
                ctx.moveTo(x, y);
            } else {
                ctx.lineTo(x, y);
            }
            x += sliceWidth;
        }
        
        ctx.stroke();
        
        // Second brighter line on top
        ctx.shadowBlur = 0;
        ctx.strokeStyle = `hsla(${hue}, 60%, 90%, ${0.4 + intensity * 0.3})`;
        ctx.lineWidth = 1.5;
        ctx.stroke();
        
        ctx.restore();
    }
    
    // =========================================================================
    // DRAW CIRCULAR VISUALIZER (Center)
    // =========================================================================
    
    function drawCircularVisualizer(audioData) {
        if (!analyser || !dataArray || !audio || audio.paused) return;
        
        analyser.getByteFrequencyData(dataArray);
        
        const hue = MOVEMENT_HUES[currentMovement] || 45;
        const centerX = width / 2;
        const centerY = height / 2;
        const baseRadius = Math.min(width, height) * 0.15;
        
        ctx.save();
        
        // Draw circular bars
        const barCount = 64;
        for (let i = 0; i < barCount; i++) {
            const dataIndex = Math.floor(i * dataArray.length / barCount);
            const value = dataArray[dataIndex] / 255;
            
            const angle = (i / barCount) * Math.PI * 2 - Math.PI / 2;
            const barLength = value * baseRadius * 1.5;
            
            const x1 = centerX + Math.cos(angle) * baseRadius;
            const y1 = centerY + Math.sin(angle) * baseRadius;
            const x2 = centerX + Math.cos(angle) * (baseRadius + barLength);
            const y2 = centerY + Math.sin(angle) * (baseRadius + barLength);
            
            ctx.beginPath();
            ctx.moveTo(x1, y1);
            ctx.lineTo(x2, y2);
            
            const gradient = ctx.createLinearGradient(x1, y1, x2, y2);
            gradient.addColorStop(0, `hsla(${hue}, 70%, 50%, 0.3)`);
            gradient.addColorStop(1, `hsla(${hue + 30}, 80%, 70%, ${0.5 + value * 0.5})`);
            
            ctx.strokeStyle = gradient;
            ctx.lineWidth = 3;
            ctx.lineCap = 'round';
            ctx.stroke();
        }
        
        // Inner circle glow
        ctx.beginPath();
        ctx.arc(centerX, centerY, baseRadius * 0.8, 0, Math.PI * 2);
        ctx.strokeStyle = `hsla(${hue}, 60%, 60%, ${0.2 + audioData.bass * 0.5})`;
        ctx.lineWidth = 2;
        ctx.shadowBlur = 20 + audioData.bass * 30;
        ctx.shadowColor = `hsla(${hue}, 80%, 50%, 0.6)`;
        ctx.stroke();
        
        ctx.restore();
    }

    // =========================================================================
    // ANIMATION LOOP
    // =========================================================================
    
    function animate() {
        const audioData = getAudioData();
        
        // Clear with fade effect
        ctx.fillStyle = 'rgba(3, 3, 5, 0.15)';
        ctx.fillRect(0, 0, width, height);

        // Draw frequency bars (behind particles)
        drawFrequencyBars(audioData);
        
        // Draw circular visualizer in center
        drawCircularVisualizer(audioData);
        
        // Draw waveform (oscilloscope)
        drawWaveform(audioData);

        // Update and draw particles
        particles.forEach(p => {
            p.update(audioData);
            p.draw(audioData);
        });

        // Draw connections between nearby particles on beats
        if (audioData.bass > 0.6) {
            drawConnections(audioData);
        }

        time++;
        requestAnimationFrame(animate);
    }

    // =========================================================================
    // DRAW CONNECTIONS
    // =========================================================================
    
    function drawConnections(audioData) {
        const hue = MOVEMENT_HUES[currentMovement] || 45;
        ctx.save();
        ctx.strokeStyle = `hsla(${hue}, 60%, 50%, ${audioData.bass * 0.3})`;
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
        ctx.restore();
    }

    // =========================================================================
    // TRACK CURRENT MOVEMENT
    // =========================================================================
    
    function updateMovement() {
        const movements = document.querySelectorAll('.movement, .overture');
        let newMovement = 0;

        movements.forEach((m, i) => {
            const rect = m.getBoundingClientRect();
            if (rect.top < window.innerHeight * 0.5) {
                newMovement = i;
            }
        });

        currentMovement = newMovement;
    }

    window.addEventListener('scroll', updateMovement, { passive: true });

    // =========================================================================
    // INIT
    // =========================================================================
    
    resize();
    window.addEventListener('resize', resize);

    if (!window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
        animate();
    }

    console.log('✨ Audio-reactive canvas initialized');
    console.log('   Click anywhere to enable audio visualization');

})();
