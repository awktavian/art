// Main Entry Point - Grove's Gallery

import { CustomCursor } from './core/cursor.js';
import { ParticleSystem } from './rendering/particles.js';
import { ScrollManager } from './core/scroll.js';
import { SoundSystem } from './core/sound.js';
import { EntranceExperience } from './rooms/entrance.js';
import { ColoniesHall } from './rooms/colonies-hall.js';
import { FanoVisualization } from './rooms/fano-visualization.js';
import { Sanctuary } from './rooms/sanctuary.js';

class GalleryApp {
    constructor() {
        this.cursor = null;
        this.particles = null;
        this.scroll = null;
        this.sound = null;
        this.entrance = null;
        this.coloniesHall = null;
        this.fanoViz = null;
        this.sanctuary = null;

        this.init();
    }

    init() {
        // Wait for DOM ready
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', () => this.setup());
        } else {
            this.setup();
        }
    }

    async setup() {
        console.log('🌿 Grove\'s Gallery initializing...');

        // Core systems
        this.cursor = new CustomCursor();
        this.particles = new ParticleSystem(this.cursor);
        this.scroll = new ScrollManager();
        this.sound = new SoundSystem();

        // Initialize sound on first user interaction
        document.addEventListener('click', () => {
            this.sound.initialize();
        }, { once: true });

        // Room-specific modules
        this.entrance = new EntranceExperience(this.sound, this.particles);
        this.sanctuary = new Sanctuary(this.sound);
        this.coloniesHall = new ColoniesHall();
        this.fanoViz = new FanoVisualization();

        // XR support
        this.setupXR();

        // Accessibility
        this.setupAccessibility();

        // Mobile navigation
        this.setupMobileNav();

        console.log('✅ Gallery ready');
    }

    setupXR() {
        const xrButton = document.getElementById('xr-toggle');
        if (!xrButton) return;

        // Check XR support
        if (navigator.xr) {
            navigator.xr.isSessionSupported('immersive-vr').then(supported => {
                if (supported) {
                    xrButton.addEventListener('click', this.enterXR.bind(this));
                } else {
                    xrButton.style.display = 'none';
                }
            });
        } else {
            xrButton.style.display = 'none';
        }
    }

    async enterXR() {
        try {
            const session = await navigator.xr.requestSession('immersive-vr');
            console.log('XR session started');
            // TODO: Full XR implementation
            // This would require WebXR-specific rendering loop
        } catch (error) {
            console.error('XR session failed:', error);
        }
    }

    setupAccessibility() {
        // Keyboard navigation
        document.addEventListener('keydown', (e) => {
            // Tab navigation is handled natively
            // ESC to close modals/details
            if (e.key === 'Escape') {
                // Clear active colony
                document.querySelectorAll('.colony-node.active').forEach(node => {
                    node.classList.remove('active');
                });
            }
        });

        // Reduced motion check
        if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
            console.log('Reduced motion preference detected');
            // Most animations respect prefers-reduced-motion via CSS
        }

        // Focus management
        document.addEventListener('focusin', (e) => {
            // Show focus outlines for keyboard navigation
            e.target.classList.add('keyboard-focus');
        });

        document.addEventListener('focusout', (e) => {
            e.target.classList.remove('keyboard-focus');
        });
    }

    setupMobileNav() {
        const navToggle = document.querySelector('.nav-toggle');
        const navLinks = document.querySelector('.nav-links');

        if (!navToggle || !navLinks) return;

        // Toggle menu
        navToggle.addEventListener('click', () => {
            const isOpen = navToggle.classList.toggle('open');
            navLinks.classList.toggle('open');
            navToggle.setAttribute('aria-expanded', isOpen);

            // Prevent body scroll when menu is open
            document.body.style.overflow = isOpen ? 'hidden' : '';
        });

        // Close menu on link click
        navLinks.querySelectorAll('a').forEach(link => {
            link.addEventListener('click', () => {
                navToggle.classList.remove('open');
                navLinks.classList.remove('open');
                navToggle.setAttribute('aria-expanded', 'false');
                document.body.style.overflow = '';
            });
        });

        // Close menu on escape key
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && navToggle.classList.contains('open')) {
                navToggle.classList.remove('open');
                navLinks.classList.remove('open');
                navToggle.setAttribute('aria-expanded', 'false');
                document.body.style.overflow = '';
            }
        });

        // Close menu on outside click
        document.addEventListener('click', (e) => {
            if (navToggle.classList.contains('open') &&
                !navLinks.contains(e.target) &&
                !navToggle.contains(e.target)) {
                navToggle.classList.remove('open');
                navLinks.classList.remove('open');
                navToggle.setAttribute('aria-expanded', 'false');
                document.body.style.overflow = '';
            }
        });
    }
}

// Initialize app
new GalleryApp();
