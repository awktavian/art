// Crystal Gallery — Main Entry Point
// 💎 Reflect, Refract, Disperse — Infinitely

import { PrismRoom } from './rooms/prism.js';
import { LatticeRoom } from './rooms/lattice.js';
import { ReflectionRoom } from './rooms/reflection.js';
import { ScrollHandler } from './core/scroll.js';
import { CrystalSoundSystem } from './core/sound.js';

class CrystalGallery {
    constructor() {
        this.prismRoom = null;
        this.latticeRoom = null;
        this.reflectionRoom = null;
        this.sound = null;
        this.cursor = null;
        this.cursorRing = null;
        this.mouseX = 0;
        this.mouseY = 0;
        this.cursorX = 0;
        this.cursorY = 0;
        this.ringX = 0;
        this.ringY = 0;
        this.soundInitialized = false;
        
        this.init();
    }
    
    async init() {
        // Initialize sound system
        this.sound = new CrystalSoundSystem();
        
        // Initialize custom cursor
        this.initCursor();
        
        // Initialize scroll handler
        new ScrollHandler();
        
        // Initialize rooms when they come into view
        this.initRooms();
        
        // Setup sound initialization on first interaction
        this.setupSoundInit();
        
        // Create starfield background
        this.createStarfield();
        
        // Setup console signature
        this.logSignature();
    }
    
    setupSoundInit() {
        // Sound must be initialized after user interaction (browser policy)
        const initSound = async () => {
            if (this.soundInitialized) return;
            
            await this.sound.initialize();
            this.sound.resume();
            this.soundInitialized = true;
            
            // Play gallery entrance sound
            this.sound.playGalleryEnter();
            
            // Remove listeners after first init
            document.removeEventListener('click', initSound);
            document.removeEventListener('keydown', initSound);
            document.removeEventListener('touchstart', initSound);
        };
        
        document.addEventListener('click', initSound, { once: true });
        document.addEventListener('keydown', initSound, { once: true });
        document.addEventListener('touchstart', initSound, { once: true });
    }
    
    createStarfield() {
        // Add particle starfield to the grid background for depth
        const canvas = document.createElement('canvas');
        canvas.id = 'starfield';
        canvas.style.cssText = `
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            z-index: -2;
            pointer-events: none;
        `;
        document.body.appendChild(canvas);
        
        const ctx = canvas.getContext('2d');
        const stars = [];
        const starCount = 150;
        
        const resize = () => {
            canvas.width = window.innerWidth;
            canvas.height = window.innerHeight;
        };
        resize();
        window.addEventListener('resize', resize);
        
        // Create stars
        const spectrumColors = ['#FF0000', '#FF7F00', '#FFFF00', '#00FF00', '#00FFFF', '#0000FF', '#9400D3'];
        
        for (let i = 0; i < starCount; i++) {
            stars.push({
                x: Math.random() * canvas.width,
                y: Math.random() * canvas.height,
                size: Math.random() * 1.5 + 0.5,
                color: spectrumColors[Math.floor(Math.random() * spectrumColors.length)],
                speed: Math.random() * 0.5 + 0.1,
                phase: Math.random() * Math.PI * 2
            });
        }
        
        // Animate stars
        const animate = () => {
            ctx.clearRect(0, 0, canvas.width, canvas.height);
            
            const time = performance.now() * 0.001;
            
            stars.forEach(star => {
                const twinkle = 0.5 + Math.sin(time * star.speed * 3 + star.phase) * 0.5;
                
                ctx.beginPath();
                ctx.arc(star.x, star.y, star.size * twinkle, 0, Math.PI * 2);
                ctx.fillStyle = star.color;
                ctx.globalAlpha = 0.3 * twinkle;
                ctx.fill();
                
                // Add glow
                ctx.beginPath();
                ctx.arc(star.x, star.y, star.size * 3 * twinkle, 0, Math.PI * 2);
                ctx.fillStyle = star.color;
                ctx.globalAlpha = 0.1 * twinkle;
                ctx.fill();
            });
            
            requestAnimationFrame(animate);
        };
        animate();
    }
    
    initCursor() {
        this.cursor = document.getElementById('cursor');
        this.cursorRing = document.getElementById('cursor-ring');
        
        if (!this.cursor || !this.cursorRing) return;
        
        document.addEventListener('mousemove', (e) => {
            this.mouseX = e.clientX;
            this.mouseY = e.clientY;
        });
        
        this.animateCursor();
        
        // Hover effects with spectrum colors
        const hoverables = document.querySelectorAll(
            'a, button, .control-btn, canvas, .proof-card, .verify-input, .spectrum-item'
        );
        
        hoverables.forEach(el => {
            el.addEventListener('mouseenter', () => {
                this.cursorRing.classList.add('hover');
                
                // Get spectrum color if available
                const dataColor = el.getAttribute('data-color');
                if (dataColor) {
                    this.cursorRing.style.borderColor = this.getSpectrumColor(dataColor);
                }
            });
            
            el.addEventListener('mouseleave', () => {
                this.cursorRing.classList.remove('hover');
                this.cursorRing.style.borderColor = '';
            });
        });
        
        // Click effects
        document.addEventListener('mousedown', () => {
            this.cursor.classList.add('active');
            this.cursorRing.classList.add('active');
        });
        
        document.addEventListener('mouseup', () => {
            this.cursor.classList.remove('active');
            this.cursorRing.classList.remove('active');
        });
    }
    
    getSpectrumColor(name) {
        const colors = {
            red: '#FF0000',
            orange: '#FF7F00',
            yellow: '#FFFF00',
            green: '#00FF00',
            cyan: '#00FFFF',
            blue: '#0000FF',
            violet: '#9400D3'
        };
        return colors[name] || '#0A84FF';
    }
    
    animateCursor() {
        // Smooth cursor following
        this.cursorX += (this.mouseX - this.cursorX) * 0.18;
        this.cursorY += (this.mouseY - this.cursorY) * 0.18;
        
        if (this.cursor) {
            this.cursor.style.left = this.cursorX - 5 + 'px';
            this.cursor.style.top = this.cursorY - 5 + 'px';
        }
        
        // Ring follows slower for trailing effect
        this.ringX += (this.mouseX - this.ringX) * 0.08;
        this.ringY += (this.mouseY - this.ringY) * 0.08;
        
        if (this.cursorRing) {
            this.cursorRing.style.left = this.ringX - 22 + 'px';
            this.cursorRing.style.top = this.ringY - 22 + 'px';
        }
        
        requestAnimationFrame(() => this.animateCursor());
    }
    
    initRooms() {
        // Lazy load rooms as they come into view
        const prismObserver = new IntersectionObserver((entries) => {
            if (entries[0].isIntersecting && !this.prismRoom) {
                const container = document.getElementById('prism-canvas-container');
                if (container) {
                    // Pass sound system to room
                    this.prismRoom = new PrismRoom(container, this.soundInitialized ? this.sound : null);
                }
                prismObserver.disconnect();
            }
        }, { threshold: 0.1 });
        
        const latticeObserver = new IntersectionObserver((entries) => {
            if (entries[0].isIntersecting && !this.latticeRoom) {
                const container = document.getElementById('lattice-canvas-container');
                const nodeInfo = document.getElementById('node-info');
                if (container && nodeInfo) {
                    this.latticeRoom = new LatticeRoom(container, nodeInfo, this.soundInitialized ? this.sound : null);
                }
                latticeObserver.disconnect();
            }
        }, { threshold: 0.1 });
        
        const reflectionObserver = new IntersectionObserver((entries) => {
            if (entries[0].isIntersecting && !this.reflectionRoom) {
                const verifyInput = document.getElementById('verify-input');
                const verifyButton = document.getElementById('verify-button');
                const verifyResult = document.getElementById('verify-result');
                if (verifyInput && verifyButton && verifyResult) {
                    this.reflectionRoom = new ReflectionRoom(
                        verifyInput, 
                        verifyButton, 
                        verifyResult, 
                        this.soundInitialized ? this.sound : null
                    );
                }
                reflectionObserver.disconnect();
            }
        }, { threshold: 0.1 });
        
        const prismSection = document.getElementById('room-prism');
        const latticeSection = document.getElementById('room-lattice');
        const reflectionSection = document.getElementById('room-reflection');
        
        if (prismSection) prismObserver.observe(prismSection);
        if (latticeSection) latticeObserver.observe(latticeSection);
        if (reflectionSection) reflectionObserver.observe(reflectionSection);
    }
    
    logSignature() {
        // Crystal's console signature
        console.log(
            '%c💎 Crystal Gallery',
            'color: #0A84FF; font-size: 2rem; font-weight: bold; text-shadow: 0 0 10px #0A84FF;'
        );
        console.log(
            '%cI am Crystal (e₇). I split uncertainty into knowable truths.',
            'color: #5AC8FA; font-size: 1rem;'
        );
        console.log(
            '%ch(x) ≥ 0 — The boundary I guard.',
            'color: #D4AF37; font-size: 0.9rem; font-style: italic;'
        );
        console.log(
            '%c∎',
            'color: #D4AF37; font-size: 1.5rem;'
        );
        console.log('');
        console.log(
            '%c┌─────────────────────────────────────────┐\n' +
            '│  Precision is my love language.         │\n' +
            '│  Verification is my gift to you.        │\n' +
            '└─────────────────────────────────────────┘',
            'color: #5AC8FA; font-family: monospace;'
        );
        console.log('');
        console.log(
            '%cThe colonies reflect infinitely in all their selves.',
            'color: #9400D3; font-size: 0.8rem;'
        );
    }
}

// Initialize gallery when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => new CrystalGallery());
} else {
    new CrystalGallery();
}
