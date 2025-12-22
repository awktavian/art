// Entrance Experience - Gasp Moment #1

import { COLORS } from '../config.js';

export class EntranceExperience {
    constructor(soundSystem, particleSystem) {
        this.sound = soundSystem;
        this.particles = particleSystem;
        this.hasPlayed = false;
        
        this.elements = {
            glyph: null,
            title: null,
            subtitle: null,
            dedication: null,
        };
        
        this.init();
    }

    init() {
        // Cache DOM elements
        this.elements.glyph = document.querySelector('.entrance-glyph');
        this.elements.title = document.querySelector('.entrance-title');
        this.elements.subtitle = document.querySelector('.entrance-subtitle');
        this.elements.dedication = document.querySelector('.entrance-dedication');
        
        // Trigger sequence on first scroll or after delay
        this.setupTriggers();
    }

    setupTriggers() {
        // Auto-play after 1 second
        setTimeout(() => {
            if (!this.hasPlayed) {
                this.playEntranceSequence();
            }
        }, 1000);
        
        // Also trigger on first scroll
        const observer = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting && !this.hasPlayed) {
                    this.playEntranceSequence();
                }
            });
        }, { threshold: 0.5 });
        
        const entranceSection = document.getElementById('entrance');
        if (entranceSection) {
            observer.observe(entranceSection);
        }
    }

    /**
     * Main entrance animation sequence
     */
    async playEntranceSequence() {
        if (this.hasPlayed) return;
        this.hasPlayed = true;
        
        // Initialize sound (requires user gesture)
        await this.sound.initialize();
        this.sound.resume();
        
        console.log('🌟 Entrance sequence starting...');
        
        // Phase 0: Void (0-1s)
        await this.wait(1000);
        
        // Phase 1: Glyph assembles (1-2s)
        await this.assembleGlyph();
        
        // Phase 2: Light burst (2-2.5s)
        await this.lightBurst();
        
        // Phase 3: Title cascade (2.5-4s)
        await this.cascadeTitle();
        
        // Phase 4: Subtitle fade (4-4.5s)
        await this.fadeInSubtitle();
        
        // Phase 5: Dedication typewriter (4.5-6s)
        await this.typewriterDedication();
        
        // Phase 6: Particles spiral inward (6s+)
        this.startSpiralParticles();
        
        console.log('✨ Entrance sequence complete');
    }

    /**
     * Glyph assembly from seven fragments
     */
    async assembleGlyph() {
        const glyph = this.elements.glyph;
        if (!glyph) return;
        
        // Play bell chime
        this.sound.playBellChime(1.5);
        
        // Reveal glyph with fragment animation
        glyph.classList.add('assembling');
        
        await this.wait(1000);
    }

    /**
     * Light burst from center
     */
    async lightBurst() {
        const glyph = this.elements.glyph;
        if (!glyph) return;
        
        // Play wind whoosh
        this.sound.playWindWhoosh(1.5);
        
        glyph.classList.add('bursting');
        
        // Spawn particles from center
        const rect = glyph.getBoundingClientRect();
        const centerX = rect.left + rect.width / 2;
        const centerY = rect.top + rect.height / 2;
        
        for (let i = 0; i < 20; i++) {
            setTimeout(() => {
                this.particles.spawnParticle(centerX, centerY, COLORS.gold);
            }, i * 25);
        }
        
        await this.wait(500);
    }

    /**
     * Title cascade letter-by-letter
     */
    async cascadeTitle() {
        const title = this.elements.title;
        if (!title) return;
        
        // Split title into letters
        const lines = title.querySelectorAll('.title-line');
        
        for (const line of lines) {
            const text = line.textContent;
            line.textContent = '';
            line.style.opacity = '1';
            
            const letters = text.split('');
            for (let i = 0; i < letters.length; i++) {
                const span = document.createElement('span');
                span.textContent = letters[i];
                span.className = 'letter';
                span.style.animationDelay = `${i * 0.05}s`;
                line.appendChild(span);
                
                // Text chime every 5 letters
                if (i % 5 === 0) {
                    this.sound.playTextChime();
                }
            }
        }
        
        await this.wait(1500);
    }

    /**
     * Fade in subtitle
     */
    async fadeInSubtitle() {
        const subtitle = this.elements.subtitle;
        if (!subtitle) return;
        
        subtitle.classList.add('visible');
        await this.wait(500);
    }

    /**
     * Typewriter effect for dedication
     */
    async typewriterDedication() {
        const dedication = this.elements.dedication;
        if (!dedication) return;
        
        const texts = dedication.querySelectorAll('p');
        
        for (const p of texts) {
            const text = p.textContent;
            p.textContent = '';
            p.style.opacity = '1';
            
            for (let i = 0; i < text.length; i++) {
                p.textContent += text[i];
                
                // Sound every 3 characters
                if (i % 3 === 0) {
                    this.sound.playTextChime();
                }
                
                await this.wait(30);
            }
            
            await this.wait(200);
        }
        
        await this.wait(500);
    }

    /**
     * Spiral particles inward (continuous)
     */
    startSpiralParticles() {
        // Switch particle system to spiral mode
        this.particles.setMode('spiral-inward');
        
        // Spawn particles around screen edges
        this.spawnSpiralParticles();
    }

    /**
     * Spawn particles in spiral pattern
     */
    spawnSpiralParticles() {
        const width = window.innerWidth;
        const height = window.innerHeight;
        const centerX = width / 2;
        const centerY = height / 2;
        
        // Spawn 8 particles around perimeter
        for (let i = 0; i < 8; i++) {
            const angle = (i / 8) * Math.PI * 2;
            const radius = Math.max(width, height) * 0.6;
            const x = centerX + Math.cos(angle) * radius;
            const y = centerY + Math.sin(angle) * radius;
            
            this.particles.spawnParticle(x, y, COLORS.grove);
        }
        
        // Repeat every 2 seconds
        setTimeout(() => this.spawnSpiralParticles(), 2000);
    }

    /**
     * Utility: wait for duration
     * @param {number} ms - Milliseconds to wait
     * @returns {Promise<void>}
     */
    wait(ms) {
        return new Promise(resolve => setTimeout(resolve, ms));
    }
}
