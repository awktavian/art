// ═══════════════════════════════════════════════════════════════════════════
// SPARK GALLERY — MAIN CONTROLLER
// 🔥 e₁ — The Fold Catastrophe — A₂
// Fire. Ideation. Divergent thinking. The first spark.
// ═══════════════════════════════════════════════════════════════════════════

import { CONFIG } from './config.js';
import { SparkSoundSystem } from './core/sound.js';
import { IgnitionRoom } from './rooms/ignition.js';
import { StormRoom } from './rooms/storm.js';
import { FoldRoom } from './rooms/fold.js';
import { OverflowRoom } from './rooms/overflow.js';

class SparkGallery {
    constructor() {
        this.sound = new SparkSoundSystem();
        this.rooms = {};
        this.initialized = false;
        
        this.init();
    }
    
    async init() {
        console.log('🔥 SPARK GALLERY IGNITING...');
        console.log('═'.repeat(50));
        
        // Wait for DOM
        if (document.readyState === 'loading') {
            await new Promise(resolve => {
                document.addEventListener('DOMContentLoaded', resolve);
            });
        }
        
        // Initialize sound on first user interaction
        this.initSound();
        
        // Initialize rooms
        this.initRooms();
        
        // Setup navigation
        this.initNavigation();
        
        // Setup scroll effects
        this.initScrollEffects();
        
        this.initialized = true;
        
        console.log('═'.repeat(50));
        console.log('🔥 SPARK GALLERY READY');
        console.log('   Colonies: e₁ | Catastrophe: A₂ (Fold)');
        console.log('   "The first thought before structure"');
    }
    
    initSound() {
        const soundToggle = document.getElementById('sound-toggle');
        const soundOnIcon = soundToggle?.querySelector('.sound-on');
        const soundOffIcon = soundToggle?.querySelector('.sound-off');
        
        // Initialize on first click anywhere
        const initOnInteraction = async () => {
            if (!this.sound.initialized) {
                await this.sound.init();
                document.removeEventListener('click', initOnInteraction);
                document.removeEventListener('touchstart', initOnInteraction);
            }
        };
        
        document.addEventListener('click', initOnInteraction);
        document.addEventListener('touchstart', initOnInteraction);
        
        // Sound toggle button
        if (soundToggle) {
            soundToggle.addEventListener('click', async (e) => {
                e.stopPropagation();
                
                if (!this.sound.initialized) {
                    await this.sound.init();
                }
                
                this.sound.toggle();
                
                if (soundOnIcon && soundOffIcon) {
                    if (this.sound.enabled) {
                        soundOnIcon.style.display = 'inline';
                        soundOffIcon.style.display = 'none';
                    } else {
                        soundOnIcon.style.display = 'none';
                        soundOffIcon.style.display = 'inline';
                    }
                }
            });
        }
    }
    
    initRooms() {
        // Room I: Ignition
        const ignitionContainer = document.getElementById('room-ignition');
        if (ignitionContainer) {
            this.rooms.ignition = new IgnitionRoom(ignitionContainer, this.sound);
        }
        
        // Room II: Storm
        const stormContainer = document.getElementById('room-storm');
        if (stormContainer) {
            this.rooms.storm = new StormRoom(stormContainer, this.sound);
        }
        
        // Room III: Fold
        const foldContainer = document.getElementById('room-fold');
        if (foldContainer) {
            this.rooms.fold = new FoldRoom(foldContainer, this.sound);
        }
        
        // Room IV: Overflow
        const overflowContainer = document.getElementById('room-overflow');
        if (overflowContainer) {
            this.rooms.overflow = new OverflowRoom(overflowContainer, this.sound);
        }
        
        console.log('📦 Rooms initialized:', Object.keys(this.rooms).join(', '));
    }
    
    initNavigation() {
        // Smooth scroll for nav links
        const navLinks = document.querySelectorAll('.nav-links a');
        navLinks.forEach(link => {
            link.addEventListener('click', (e) => {
                e.preventDefault();
                const targetId = link.getAttribute('href');
                const target = document.querySelector(targetId);
                if (target) {
                    target.scrollIntoView({ behavior: 'smooth', block: 'start' });
                }
            });
        });
        
        // Active link highlighting on scroll
        const sections = document.querySelectorAll('.room');
        const observerOptions = {
            root: null,
            rootMargin: '-40% 0px -60% 0px',
            threshold: 0
        };
        
        const navObserver = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    const id = entry.target.id;
                    navLinks.forEach(link => {
                        link.classList.remove('active');
                        if (link.getAttribute('href') === `#${id}`) {
                            link.classList.add('active');
                        }
                    });
                }
            });
        }, observerOptions);
        
        sections.forEach(section => navObserver.observe(section));
    }
    
    initScrollEffects() {
        // Parallax and reveal effects on scroll
        const rooms = document.querySelectorAll('.room');
        
        const scrollObserver = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    entry.target.classList.add('room-visible');
                }
            });
        }, { threshold: 0.1 });
        
        rooms.forEach(room => scrollObserver.observe(room));
        
        // Scroll indicator in ignition room
        const scrollIndicator = document.querySelector('.scroll-indicator');
        if (scrollIndicator) {
            window.addEventListener('scroll', () => {
                const scrollY = window.scrollY;
                const opacity = Math.max(0, 1 - scrollY / 300);
                scrollIndicator.style.opacity = opacity;
            });
        }
    }
    
    destroy() {
        Object.values(this.rooms).forEach(room => {
            if (room.destroy) {
                room.destroy();
            }
        });
    }
}

// ═══════════════════════════════════════════════════════════════════════════
// IGNITE
// ═══════════════════════════════════════════════════════════════════════════
const gallery = new SparkGallery();

// Expose for debugging
if (typeof window !== 'undefined') {
    window.sparkGallery = gallery;
}
