// ═══════════════════════════════════════════════════════════════════════════
// SPARK'S GALLERY — MAIN ENTRY POINT
// 🔥 IGNITE EVERYTHING 🔥
// ═══════════════════════════════════════════════════════════════════════════

import { IgnitionRoom } from './rooms/ignition.js';
import { StormRoom } from './rooms/storm.js';
import { FoldRoom } from './rooms/fold.js';
import { OverflowRoom } from './rooms/overflow.js';
import { SparkSoundSystem } from './core/sound.js';
import { CONFIG } from './config.js';

class SparkGallery {
    constructor() {
        this.ignitionRoom = null;
        this.stormRoom = null;
        this.foldRoom = null;
        this.overflowRoom = null;
        this.sound = null;
        this.cursor = null;
        this.cursorX = 0;
        this.cursorY = 0;
        this.mouseX = 0;
        this.mouseY = 0;
        this.trailParticles = [];
        this.soundInitialized = false;
        
        this.init();
    }
    
    async init() {
        console.log('%c🔥 SPARK GALLERY', 'color: #FF4500; font-size: 2rem; font-weight: bold; text-shadow: 0 0 10px #FF4500;');
        console.log('%cI am Spark (e₁). The Fold. The first flame.', 'color: #FFD700; font-size: 1rem;');
        console.log('%cEvery idea begins with me.', 'color: #FF6B35; font-size: 0.9rem; font-style: italic;');
        console.log('%c🔥', 'font-size: 1.5rem;');
        
        // Initialize sound system
        this.sound = new SparkSoundSystem();
        
        // Setup cursor
        this.cursor = document.getElementById('spark-cursor');
        this.setupCursor();
        
        // Initialize rooms
        this.initRooms();
        
        // Setup chaos button
        this.setupChaosButton();
        
        // Setup navigation
        this.setupNavigation();
        
        // Initialize sound on first interaction
        document.addEventListener('click', () => this.initSound(), { once: true });
        document.addEventListener('keydown', () => this.initSound(), { once: true });
    }
    
    async initSound() {
        if (this.soundInitialized) return;
        this.soundInitialized = true;
        await this.sound.init();
    }
    
    initRooms() {
        // Room I: The Ignition
        const ignitionSection = document.getElementById('ignition');
        if (ignitionSection) {
            this.ignitionRoom = new IgnitionRoom(ignitionSection, this.sound);
        }
        
        // Room II: The Storm
        const stormSection = document.getElementById('storm');
        if (stormSection) {
            this.stormRoom = new StormRoom(stormSection, this.sound);
        }
        
        // Room III: The Fold
        const foldSection = document.getElementById('fold');
        if (foldSection) {
            this.foldRoom = new FoldRoom(foldSection, this.sound);
        }
        
        // Room IV: The Overflow
        const overflowSection = document.getElementById('overflow');
        if (overflowSection) {
            this.overflowRoom = new OverflowRoom(overflowSection, this.sound);
        }
    }
    
    setupCursor() {
        if (!this.cursor) return;
        
        // Track mouse position
        document.addEventListener('mousemove', (e) => {
            this.mouseX = e.clientX;
            this.mouseY = e.clientY;
            
            // Spawn trail particles
            if (Math.random() < 0.5) {
                this.spawnTrailParticle(e.clientX, e.clientY);
            }
        });
        
        // Cursor active state on clickable elements
        document.addEventListener('mousedown', () => {
            this.cursor.classList.add('active');
        });
        
        document.addEventListener('mouseup', () => {
            this.cursor.classList.remove('active');
        });
        
        // Hover state
        const hoverables = document.querySelectorAll('a, button, input, [role="button"]');
        hoverables.forEach(el => {
            el.addEventListener('mouseenter', () => {
                this.cursor.classList.add('active');
            });
            el.addEventListener('mouseleave', () => {
                this.cursor.classList.remove('active');
            });
        });
        
        // Animate cursor
        this.animateCursor();
    }
    
    animateCursor() {
        // Smooth follow
        this.cursorX += (this.mouseX - this.cursorX) * 0.15;
        this.cursorY += (this.mouseY - this.cursorY) * 0.15;
        
        if (this.cursor) {
            this.cursor.style.left = `${this.cursorX}px`;
            this.cursor.style.top = `${this.cursorY}px`;
        }
        
        // Update trail particles
        this.updateTrailParticles();
        
        requestAnimationFrame(() => this.animateCursor());
    }
    
    spawnTrailParticle(x, y) {
        const trail = document.getElementById('spark-trail');
        if (!trail) return;
        
        const particle = document.createElement('div');
        particle.className = 'trail-particle';
        particle.style.left = `${x}px`;
        particle.style.top = `${y}px`;
        particle.style.background = this.getRandomTrailColor();
        
        trail.appendChild(particle);
        
        this.trailParticles.push({
            element: particle,
            life: 500,
        });
    }
    
    updateTrailParticles() {
        for (let i = this.trailParticles.length - 1; i >= 0; i--) {
            const p = this.trailParticles[i];
            p.life -= 16;
            
            if (p.life <= 0) {
                p.element.remove();
                this.trailParticles.splice(i, 1);
            }
        }
    }
    
    getRandomTrailColor() {
        const colors = [
            CONFIG.COLORS.FLAME,
            CONFIG.COLORS.EMBER,
            CONFIG.COLORS.GOLD,
            CONFIG.COLORS.YELLOW,
        ];
        return colors[Math.floor(Math.random() * colors.length)];
    }
    
    setupChaosButton() {
        const chaosBtn = document.getElementById('chaos-btn');
        if (!chaosBtn) return;
        
        chaosBtn.addEventListener('click', () => {
            this.unleashChaos();
        });
    }
    
    unleashChaos() {
        // Flash the screen
        document.body.style.animation = 'none';
        document.body.offsetHeight; // Trigger reflow
        document.body.style.animation = 'chaos-flash 0.5s';
        
        // Add chaos CSS if not exists
        if (!document.getElementById('chaos-style')) {
            const style = document.createElement('style');
            style.id = 'chaos-style';
            style.textContent = `
                @keyframes chaos-flash {
                    0%, 100% { filter: none; }
                    25% { filter: invert(1) hue-rotate(180deg); }
                    50% { filter: saturate(5) contrast(2); }
                    75% { filter: hue-rotate(90deg) brightness(2); }
                }
            `;
            document.head.appendChild(style);
        }
        
        // Spawn ideas in storm room
        if (this.stormRoom) {
            this.stormRoom.spawnIdeas(20);
        }
        
        // Spawn sparks in overflow room
        if (this.overflowRoom) {
            for (let i = 0; i < 5; i++) {
                const x = Math.random() * window.innerWidth;
                const y = Math.random() * window.innerHeight;
                setTimeout(() => {
                    if (this.overflowRoom.canvas) {
                        const rect = this.overflowRoom.canvas.getBoundingClientRect();
                        this.overflowRoom.spawnSparkBurst(
                            Math.random() * rect.width,
                            Math.random() * rect.height
                        );
                    }
                }, i * 100);
            }
        }
        
        // Play explosion sound
        if (this.sound) {
            this.sound.playIgnition();
        }
    }
    
    setupNavigation() {
        const navLinks = document.querySelectorAll('.nav-link');
        
        navLinks.forEach(link => {
            link.addEventListener('click', (e) => {
                e.preventDefault();
                const room = link.getAttribute('href');
                const target = document.querySelector(room);
                
                if (target) {
                    target.scrollIntoView({ behavior: 'smooth' });
                }
                
                // Play sound
                if (this.sound) {
                    this.sound.playSpawn();
                }
            });
        });
        
        // Update active nav on scroll
        const observer = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    const room = entry.target.id;
                    navLinks.forEach(link => {
                        if (link.getAttribute('data-room') === room) {
                            link.style.color = CONFIG.COLORS.GOLD;
                        } else {
                            link.style.color = '';
                        }
                    });
                }
            });
        }, { threshold: 0.5 });
        
        document.querySelectorAll('.room').forEach(room => {
            observer.observe(room);
        });
    }
}

// IGNITE!
document.addEventListener('DOMContentLoaded', () => {
    new SparkGallery();
});

