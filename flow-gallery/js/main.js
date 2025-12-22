// ═══════════════════════════════════════════════════════════════════════════
// FLOW GALLERY — MAIN ENTRY POINT
// 🌊 e₃ — The Swallowtail Catastrophe — A₄
// Crystal-verified: Room orchestration, sound integration, navigation
// ═══════════════════════════════════════════════════════════════════════════

import { FlowSoundSystem } from './core/sound.js';
import { CurrentRoom } from './rooms/current.js';
import { SwallowtailRoom } from './rooms/swallowtail.js';
import { RecoveryRoom } from './rooms/recovery.js';
import { AdaptationRoom } from './rooms/adaptation.js';

class FlowGallery {
    constructor() {
        this.sound = new FlowSoundSystem();
        this.rooms = {};
        this.currentRoom = null;
        
        this.init();
    }
    
    async init() {
        console.log('🌊 Initializing Flow Gallery...');
        
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
        
        console.log('🌊 Flow Gallery ready!');
    }
    
    initRooms() {
        // Room I: The Current
        const currentContainer = document.getElementById('room-current');
        if (currentContainer) {
            this.rooms.current = new CurrentRoom(currentContainer, this.sound);
        }
        
        // Room II: The Swallowtail
        const swallowtailContainer = document.getElementById('room-swallowtail');
        if (swallowtailContainer) {
            this.rooms.swallowtail = new SwallowtailRoom(swallowtailContainer, this.sound);
        }
        
        // Room III: The Recovery
        const recoveryContainer = document.getElementById('room-recovery');
        if (recoveryContainer) {
            this.rooms.recovery = new RecoveryRoom(recoveryContainer, this.sound);
        }
        
        // Room IV: The Adaptation
        const adaptationContainer = document.getElementById('room-adaptation');
        if (adaptationContainer) {
            this.rooms.adaptation = new AdaptationRoom(adaptationContainer, this.sound);
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
            case 'room-current':
                console.log('🌊 Entering The Current');
                break;
            case 'room-swallowtail':
                console.log('🦋 Entering The Swallowtail');
                break;
            case 'room-recovery':
                console.log('💧 Entering The Recovery');
                break;
            case 'room-adaptation':
                console.log('🧘 Entering The Adaptation');
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
const gallery = new FlowGallery();

// Cleanup on page unload
window.addEventListener('beforeunload', () => {
    gallery.destroy();
});

