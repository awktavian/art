// ═══════════════════════════════════════════════════════════════════════════
// FORGE GALLERY — MAIN ENTRY POINT
// ⚒️ e₂ — The Cusp Catastrophe — A₃
// Crystal-verified: Room orchestration, sound integration, navigation
// ═══════════════════════════════════════════════════════════════════════════

import { ForgeSoundSystem } from './core/sound.js';
import { AnvilRoom } from './rooms/anvil.js';
import { CuspRoom } from './rooms/cusp.js';
import { FoundryRoom } from './rooms/foundry.js';
import { ConstructRoom } from './rooms/construct.js';

class ForgeGallery {
    constructor() {
        this.sound = new ForgeSoundSystem();
        this.rooms = {};
        this.currentRoom = null;
        
        this.init();
    }
    
    async init() {
        console.log('⚒️ Initializing Forge Gallery...');
        
        // Wait for DOM
        if (document.readyState === 'loading') {
            await new Promise(resolve => {
                document.addEventListener('DOMContentLoaded', resolve);
            });
        }
        
        // Initialize sound on first interaction
        document.addEventListener('click', async () => {
            if (!this.sound.initialized) {
                await this.sound.init();
            }
        }, { once: true });
        
        // Sound toggle
        const soundToggle = document.getElementById('sound-toggle');
        if (soundToggle) {
            soundToggle.addEventListener('click', (e) => {
                e.stopPropagation();
                const enabled = this.sound.toggle();
                const onIcon = soundToggle.querySelector('.sound-on');
                const offIcon = soundToggle.querySelector('.sound-off');
                if (onIcon) onIcon.style.display = enabled ? 'inline' : 'none';
                if (offIcon) offIcon.style.display = enabled ? 'none' : 'inline';
            });
        }
        
        // Initialize rooms
        this.initRooms();
        
        // Setup navigation
        this.setupNavigation();
        
        // Intersection observer for room activation
        this.setupRoomObserver();
        
        console.log('⚒️ Forge Gallery ready!');
    }
    
    initRooms() {
        // Room I: The Anvil
        const anvilContainer = document.getElementById('room-anvil');
        if (anvilContainer) {
            this.rooms.anvil = new AnvilRoom(anvilContainer, this.sound);
        }
        
        // Room II: The Cusp
        const cuspContainer = document.getElementById('room-cusp');
        if (cuspContainer) {
            this.rooms.cusp = new CuspRoom(cuspContainer, this.sound);
        }
        
        // Room III: The Foundry
        const foundryContainer = document.getElementById('room-foundry');
        if (foundryContainer) {
            this.rooms.foundry = new FoundryRoom(foundryContainer, this.sound);
        }
        
        // Room IV: The Construct
        const constructContainer = document.getElementById('room-construct');
        if (constructContainer) {
            this.rooms.construct = new ConstructRoom(constructContainer, this.sound);
        }
    }
    
    setupNavigation() {
        // Smooth scroll for nav links
        document.querySelectorAll('.nav-links a').forEach(link => {
            link.addEventListener('click', (e) => {
                e.preventDefault();
                const targetId = link.getAttribute('href');
                const target = document.querySelector(targetId);
                if (target) {
                    target.scrollIntoView({ behavior: 'smooth' });
                }
            });
        });
        
        // Update active nav link on scroll
        const sections = document.querySelectorAll('.room');
        const navLinks = document.querySelectorAll('.nav-links a');
        
        window.addEventListener('scroll', () => {
            let current = '';
            
            sections.forEach(section => {
                const sectionTop = section.offsetTop;
                const sectionHeight = section.clientHeight;
                
                if (window.scrollY >= sectionTop - sectionHeight / 3) {
                    current = section.getAttribute('id');
                }
            });
            
            navLinks.forEach(link => {
                link.classList.remove('active');
                if (link.getAttribute('href') === `#${current}`) {
                    link.classList.add('active');
                }
            });
        });
    }
    
    setupRoomObserver() {
        const observer = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    const roomId = entry.target.getAttribute('id');
                    this.onRoomEnter(roomId);
                }
            });
        }, { threshold: 0.3 });
        
        document.querySelectorAll('.room').forEach(room => {
            observer.observe(room);
        });
    }
    
    onRoomEnter(roomId) {
        this.currentRoom = roomId;
        
        // Room-specific entrance effects
        switch (roomId) {
            case 'room-anvil':
                console.log('⚒️ Entering The Anvil');
                break;
            case 'room-cusp':
                console.log('📐 Entering The Cusp');
                break;
            case 'room-foundry':
                console.log('🔥 Entering The Foundry');
                break;
            case 'room-construct':
                console.log('🏗️ Entering The Construct');
                break;
        }
    }
    
    destroy() {
        Object.values(this.rooms).forEach(room => {
            if (room && typeof room.destroy === 'function') {
                room.destroy();
            }
        });
    }
}

// Initialize
const gallery = new ForgeGallery();

// Cleanup on page unload
window.addEventListener('beforeunload', () => {
    gallery.destroy();
});

