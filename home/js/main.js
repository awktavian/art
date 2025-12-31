/**
 * HOME — A House That Thinks With You
 *
 * Interactive experience powered by GENUX design principles:
 * - Custom cursor with trailing ring
 * - Breathing backgrounds that respond to mouse
 * - Floating particles
 * - Scroll reveal animations
 * - Easter egg keyboard sequences
 * - Reading progress tracking
 *
 * 鏡
 */

class HomeExperience {
    constructor() {
        // State
        this.mouseX = 0;
        this.mouseY = 0;
        this.cursorX = 0;
        this.cursorY = 0;
        this.ringX = 0;
        this.ringY = 0;
        this.scrollY = 0;
        this.ticking = false;
        this.heroHeight = 0;
        this.keyBuffer = '';
        this.keyTimeout = null;
        this.animationFrameId = null;
        this.isAnimating = false;
        this.easterEggTimeouts = [];
        this.sectionPositions = [];

        // Elements
        this.cursor = null;
        this.cursorRing = null;
        this.progressBar = null;
        this.readingProgress = null;
        this.navBar = null;
        this.canvas = null;
        this.ctx = null;
        this.scrollRevealObserver = null;

        // Preferences
        this.prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
        this.isTouchDevice = 'ontouchstart' in window || navigator.maxTouchPoints > 0;

        // Bound handlers for cleanup
        this.boundHandlers = {
            mousemove: this.handleMouseMove.bind(this),
            mousedown: this.handleMouseDown.bind(this),
            mouseup: this.handleMouseUp.bind(this),
            scroll: this.handleScroll.bind(this),
            resize: this.handleResize.bind(this),
            keydown: this.handleKeyDown.bind(this),
            visibilitychange: this.handleVisibilityChange.bind(this),
            breathingMousemove: null, // Set in setupBreathingResponse
            scrollIndicatorScroll: null, // Set in setupScrollIndicator
            scrollIndicatorClick: null, // Set in setupScrollIndicator
            scrollIndicatorKeydown: null // Set in setupScrollIndicator
        };

        // Element references for cleanup
        this.scrollIndicator = null;

        // Initialize
        this.init();
    }

    init() {
        // Wait for DOM
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', () => this.setup(), { once: true });
        } else {
            this.setup();
        }
    }

    setup() {
        try {
            // Cache elements
            this.cursor = document.querySelector('.cursor');
            this.cursorRing = document.querySelector('.cursor-ring');
            this.progressBar = document.querySelector('.reading-progress-bar');
            this.readingProgress = document.querySelector('.reading-progress');
            this.navBar = document.querySelector('.nav-bar');
            this.canvas = document.querySelector('#background-canvas');

            // Cache section positions
            this.cacheSectionPositions();

            // Setup features with individual error handling
            const features = [
                () => this.setupCustomCursor(),
                () => this.setupCanvas(),
                () => this.setupParticles(),
                () => this.setupBreathingResponse(),
                () => this.setupScrollEffects(),
                () => this.setupScrollReveal(),
                () => this.setupCardInteractions(),
                () => this.setupScrollIndicator(),
                () => this.setupEasterEggs(),
                () => this.setupSmoothScroll(),
                () => this.setupVisibilityHandling()
            ];

            features.forEach(fn => {
                try {
                    fn();
                } catch (e) {
                    console.warn('Feature setup failed:', e);
                }
            });

            // Remove loading state
            requestAnimationFrame(() => {
                document.body.classList.remove('loading');
            });

            // Start animation loop
            this.startAnimation();
        } catch (e) {
            console.error('HomeExperience initialization failed:', e);
        }
    }

    cacheSectionPositions() {
        const hero = document.querySelector('.hero');
        this.heroHeight = hero ? hero.offsetHeight : window.innerHeight;

        const sections = document.querySelectorAll('[data-section]');
        this.sectionPositions = Array.from(sections).map(section => ({
            element: section,
            top: section.offsetTop - 150,
            name: section.getAttribute('data-section')
        }));
    }

    // ========================================================================
    // VISIBILITY HANDLING
    // ========================================================================

    setupVisibilityHandling() {
        document.addEventListener('visibilitychange', this.boundHandlers.visibilitychange);
    }

    handleVisibilityChange() {
        if (document.hidden) {
            this.pauseAnimation();
        } else {
            this.resumeAnimation();
        }
    }

    startAnimation() {
        if (!this.isAnimating) {
            this.isAnimating = true;
            this.animate();
        }
    }

    pauseAnimation() {
        this.isAnimating = false;
        if (this.animationFrameId) {
            cancelAnimationFrame(this.animationFrameId);
            this.animationFrameId = null;
        }
    }

    resumeAnimation() {
        if (!this.isAnimating && !document.hidden) {
            this.startAnimation();
        }
    }

    // ========================================================================
    // CUSTOM CURSOR
    // ========================================================================

    setupCustomCursor() {
        if (!this.cursor || !this.cursorRing) return;

        // Disable custom cursor on touch devices
        if (this.isTouchDevice) {
            this.cursor.style.display = 'none';
            this.cursorRing.style.display = 'none';
            document.body.style.cursor = 'auto';
            return;
        }

        // Track mouse position
        document.addEventListener('mousemove', this.boundHandlers.mousemove, { passive: true });

        // Hover states for interactive elements
        const interactiveElements = document.querySelectorAll('a, button, [role="button"], .capability-card, .stat-card, .tier-card, .lesson-card, .timeline-content, .arch-box');

        interactiveElements.forEach(el => {
            el.addEventListener('mouseenter', () => {
                this.cursorRing.classList.add('hover');
            });
            el.addEventListener('mouseleave', () => {
                this.cursorRing.classList.remove('hover');
            });
        });

        // Click feedback
        document.addEventListener('mousedown', this.boundHandlers.mousedown);
        document.addEventListener('mouseup', this.boundHandlers.mouseup);
    }

    handleMouseMove(e) {
        this.mouseX = e.clientX;
        this.mouseY = e.clientY;
    }

    handleMouseDown() {
        if (this.cursorRing) {
            this.cursorRing.classList.add('clicking');
        }
    }

    handleMouseUp() {
        if (this.cursorRing) {
            this.cursorRing.classList.remove('clicking');
        }
    }

    updateCursor() {
        if (!this.cursor || !this.cursorRing || this.isTouchDevice) return;

        // Smooth follow with different speeds
        this.cursorX += (this.mouseX - this.cursorX) * 0.18;
        this.cursorY += (this.mouseY - this.cursorY) * 0.18;
        this.ringX += (this.mouseX - this.ringX) * 0.08;
        this.ringY += (this.mouseY - this.ringY) * 0.08;

        this.cursor.style.left = `${this.cursorX}px`;
        this.cursor.style.top = `${this.cursorY}px`;
        this.cursorRing.style.left = `${this.ringX}px`;
        this.cursorRing.style.top = `${this.ringY}px`;
    }

    // ========================================================================
    // AMBIENT CANVAS
    // ========================================================================

    setupCanvas() {
        if (!this.canvas) return;

        this.ctx = this.canvas.getContext('2d');
        this.resizeCanvas();

        window.addEventListener('resize', this.boundHandlers.resize, { passive: true });
    }

    handleResize() {
        this.resizeCanvas();
        this.cacheSectionPositions();
    }

    resizeCanvas() {
        if (!this.canvas || !this.ctx) return;

        const dpr = window.devicePixelRatio || 1;
        this.canvas.width = window.innerWidth * dpr;
        this.canvas.height = window.innerHeight * dpr;
        this.ctx.scale(dpr, dpr);
    }

    drawCanvas() {
        // Skip if reduced motion is preferred
        if (this.prefersReducedMotion) return;
        if (!this.ctx || !this.canvas) return;

        const w = window.innerWidth;
        const h = window.innerHeight;

        // Clear
        this.ctx.clearRect(0, 0, w, h);

        // Draw subtle orbs based on mouse position
        const time = Date.now() * 0.001;

        // Primary orb (amber)
        const orb1X = w * 0.3 + Math.sin(time * 0.5) * 100 + (this.mouseX - w / 2) * 0.05;
        const orb1Y = h * 0.4 + Math.cos(time * 0.3) * 80 + (this.mouseY - h / 2) * 0.05;
        this.drawOrb(orb1X, orb1Y, 200, 'rgba(245, 158, 11, 0.03)');

        // Secondary orb (cyan)
        const orb2X = w * 0.7 + Math.cos(time * 0.4) * 120 - (this.mouseX - w / 2) * 0.03;
        const orb2Y = h * 0.6 + Math.sin(time * 0.35) * 100 - (this.mouseY - h / 2) * 0.03;
        this.drawOrb(orb2X, orb2Y, 180, 'rgba(6, 182, 212, 0.02)');

        // Tertiary orb (emerald)
        const orb3X = w * 0.5 + Math.sin(time * 0.25) * 150;
        const orb3Y = h * 0.3 + Math.cos(time * 0.45) * 90;
        this.drawOrb(orb3X, orb3Y, 150, 'rgba(16, 185, 129, 0.015)');
    }

    drawOrb(x, y, radius, color) {
        const gradient = this.ctx.createRadialGradient(x, y, 0, x, y, radius);
        gradient.addColorStop(0, color);
        gradient.addColorStop(1, 'transparent');

        this.ctx.beginPath();
        this.ctx.arc(x, y, radius, 0, Math.PI * 2);
        this.ctx.fillStyle = gradient;
        this.ctx.fill();
    }

    // ========================================================================
    // FLOATING PARTICLES
    // ========================================================================

    setupParticles() {
        // Skip if reduced motion preferred
        if (this.prefersReducedMotion) return;

        const container = document.querySelector('.particles-container');
        if (!container) return;

        // Create 12 particles with random positions and delays
        const particleCount = 12;

        for (let i = 0; i < particleCount; i++) {
            const particle = document.createElement('div');
            particle.className = 'particle';
            particle.setAttribute('aria-hidden', 'true');
            particle.style.left = `${Math.random() * 100}%`;
            particle.style.animationDelay = `${Math.random() * 15}s`;
            particle.style.animationDuration = `${12 + Math.random() * 8}s`;
            container.appendChild(particle);
        }
    }

    // ========================================================================
    // BREATHING RESPONSE
    // ========================================================================

    setupBreathingResponse() {
        // Skip if reduced motion preferred
        if (this.prefersReducedMotion) return;

        const breathLayers = document.querySelectorAll('.breath-layer');
        if (breathLayers.length === 0) return;

        // Create bound handler for cleanup
        this.boundHandlers.breathingMousemove = (e) => {
            const x = (e.clientX / window.innerWidth - 0.5) * 20;
            const y = (e.clientY / window.innerHeight - 0.5) * 20;

            breathLayers.forEach((layer, i) => {
                const factor = (i + 1) * 0.5;
                layer.style.transform = `translate(${x * factor}px, ${y * factor}px)`;
            });
        };

        document.addEventListener('mousemove', this.boundHandlers.breathingMousemove, { passive: true });
    }

    // ========================================================================
    // SCROLL EFFECTS
    // ========================================================================

    setupScrollEffects() {
        window.addEventListener('scroll', this.boundHandlers.scroll, { passive: true });

        // Initial call
        this.onScroll();
    }

    handleScroll() {
        if (!this.ticking) {
            requestAnimationFrame(() => {
                this.onScroll();
                this.ticking = false;
            });
            this.ticking = true;
        }
    }

    onScroll() {
        this.scrollY = window.scrollY;

        // Update reading progress
        this.updateReadingProgress();

        // Update nav visibility
        this.updateNavVisibility();

        // Update active nav link
        this.updateActiveNavLink();
    }

    updateReadingProgress() {
        if (!this.progressBar || !this.readingProgress) return;

        const docHeight = document.documentElement.scrollHeight - window.innerHeight;
        // Guard against division by zero on short pages
        if (docHeight <= 0) return;
        const progress = Math.min((this.scrollY / docHeight) * 100, 100);

        this.progressBar.style.transform = `scaleX(${progress / 100})`;
        this.readingProgress.setAttribute('aria-valuenow', Math.round(progress));

        // Show progress bar after scrolling past hero
        if (this.scrollY > 200) {
            this.readingProgress.classList.add('visible');
        } else {
            this.readingProgress.classList.remove('visible');
        }
    }

    updateNavVisibility() {
        if (!this.navBar) return;

        if (this.scrollY > this.heroHeight * 0.6) {
            this.navBar.classList.add('visible');
        } else {
            this.navBar.classList.remove('visible');
        }
    }

    updateActiveNavLink() {
        if (!this.sectionPositions.length) return;

        const navLinks = document.querySelectorAll('.nav-link');
        let currentSection = '';

        for (const section of this.sectionPositions) {
            if (this.scrollY >= section.top) {
                currentSection = section.name;
            }
        }

        navLinks.forEach(link => {
            const linkSection = link.getAttribute('data-section');
            if (linkSection === currentSection) {
                link.classList.add('active');
            } else {
                link.classList.remove('active');
            }
        });
    }

    // ========================================================================
    // SCROLL REVEAL
    // ========================================================================

    setupScrollReveal() {
        const revealElements = document.querySelectorAll('[data-reveal]');
        if (!revealElements.length) return;

        // Guard for browsers without IntersectionObserver support
        if (typeof IntersectionObserver === 'undefined') {
            // Fallback: make all elements visible immediately
            revealElements.forEach(el => el.classList.add('visible'));
            return;
        }

        this.scrollRevealObserver = new IntersectionObserver((entries) => {
            const newlyVisible = entries.filter(
                e => e.isIntersecting && !e.target.classList.contains('visible')
            );

            newlyVisible.forEach((entry, index) => {
                setTimeout(() => {
                    entry.target.classList.add('visible');
                }, index * 80);
            });
        }, {
            threshold: 0.1,
            rootMargin: '-50px'
        });

        revealElements.forEach(el => this.scrollRevealObserver.observe(el));
    }

    // ========================================================================
    // CARD INTERACTIONS
    // ========================================================================

    setupCardInteractions() {
        const cards = document.querySelectorAll('.capability-card');

        cards.forEach(card => {
            // Mouse events
            card.addEventListener('mousemove', (e) => {
                this.updateCardPosition(card, e.clientX, e.clientY);
            });

            // Touch events for mobile
            card.addEventListener('touchmove', (e) => {
                if (e.touches.length === 1) {
                    const touch = e.touches[0];
                    this.updateCardPosition(card, touch.clientX, touch.clientY);
                }
            }, { passive: true });
        });
    }

    updateCardPosition(card, clientX, clientY) {
        const rect = card.getBoundingClientRect();
        const x = ((clientX - rect.left) / rect.width) * 100;
        const y = ((clientY - rect.top) / rect.height) * 100;

        card.style.setProperty('--mouse-x', `${x}%`);
        card.style.setProperty('--mouse-y', `${y}%`);
    }

    // ========================================================================
    // SCROLL INDICATOR
    // ========================================================================

    setupScrollIndicator() {
        const indicator = document.querySelector('.scroll-indicator');
        if (!indicator) return;

        // Store reference for cleanup
        this.scrollIndicator = indicator;

        // Ensure accessibility attributes
        if (!indicator.hasAttribute('tabindex')) {
            indicator.setAttribute('tabindex', '0');
        }
        if (!indicator.hasAttribute('role')) {
            indicator.setAttribute('role', 'button');
        }
        if (!indicator.hasAttribute('aria-label')) {
            indicator.setAttribute('aria-label', 'Scroll to content');
        }

        // Create bound handlers for cleanup
        this.boundHandlers.scrollIndicatorClick = () => {
            const firstSection = document.querySelector('.stats-section, .section');
            if (firstSection) {
                firstSection.scrollIntoView({ behavior: 'smooth' });
            }
        };

        this.boundHandlers.scrollIndicatorKeydown = (e) => {
            if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                this.boundHandlers.scrollIndicatorClick();
            }
        };

        this.boundHandlers.scrollIndicatorScroll = () => {
            if (window.scrollY > this.heroHeight * 0.3) {
                indicator.style.opacity = '0';
                indicator.style.pointerEvents = 'none';
            } else {
                indicator.style.opacity = '';
                indicator.style.pointerEvents = '';
            }
        };

        // Attach event listeners
        indicator.addEventListener('click', this.boundHandlers.scrollIndicatorClick);
        indicator.addEventListener('keydown', this.boundHandlers.scrollIndicatorKeydown);

        // Touch support for mobile devices
        indicator.addEventListener('touchend', this.boundHandlers.scrollIndicatorClick, { passive: true });

        // Hide after scrolling
        window.addEventListener('scroll', this.boundHandlers.scrollIndicatorScroll, { passive: true });
    }

    // ========================================================================
    // SMOOTH SCROLL FOR NAV LINKS
    // ========================================================================

    setupSmoothScroll() {
        const navLinks = document.querySelectorAll('.nav-link, a[href^="#"]');

        navLinks.forEach(link => {
            link.addEventListener('click', (e) => {
                const href = link.getAttribute('href');
                if (href && href.startsWith('#')) {
                    const target = document.querySelector(href);
                    if (target) {
                        e.preventDefault();
                        target.scrollIntoView({ behavior: 'smooth' });
                    }
                }
            });
        });
    }

    // ========================================================================
    // EASTER EGGS
    // ========================================================================

    setupEasterEggs() {
        const easterEggs = {
            'goodnight': {
                type: 'night',
                title: 'Goodnight',
                sequence: [
                    '41 lights fading...',
                    '11 shades closing...',
                    '2 locks engaging...',
                    'Security armed.',
                    'Sleep well.'
                ],
                duration: 8000
            },
            'morning': {
                type: 'morning',
                title: 'Good Morning',
                sequence: [
                    'Shades opening...',
                    'Coffee area illuminated.',
                    'Morning playlist starting...',
                    'Temperature optimizing.',
                    'Have a great day.'
                ],
                duration: 8500
            },
            'moviemode': {
                type: 'cinema',
                title: 'Movie Mode',
                sequence: [
                    'TV descending...',
                    'Lights dimming to 5%...',
                    'Shades closing...',
                    'Atmos engaged.',
                    'Enjoy the show.'
                ],
                duration: 7000
            }
        };

        document.addEventListener('keydown', this.boundHandlers.keydown);
        this.easterEggs = easterEggs;
    }

    handleKeyDown(e) {
        // Don't capture if typing in an input
        if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;

        // Clear timeout and reset buffer after 2 seconds of inactivity
        if (this.keyTimeout) {
            clearTimeout(this.keyTimeout);
        }

        this.keyBuffer += e.key.toLowerCase();
        this.keyTimeout = setTimeout(() => {
            this.keyBuffer = '';
        }, 2000);

        // Check for matches
        for (const [trigger, config] of Object.entries(this.easterEggs || {})) {
            if (this.keyBuffer.includes(trigger)) {
                this.keyBuffer = '';
                this.triggerEasterEgg(config);
                break;
            }
        }
    }

    triggerEasterEgg(config) {
        const container = document.getElementById('easter-egg-container');
        if (!container) return;

        // Remove any existing overlays first
        const existingOverlay = container.querySelector('.easter-egg-overlay');
        if (existingOverlay) {
            existingOverlay.remove();
        }

        // Clear any pending timeouts
        if (this.easterEggTimeouts.length) {
            this.easterEggTimeouts.forEach(t => clearTimeout(t));
            this.easterEggTimeouts = [];
        }

        // Update aria-hidden on container
        container.setAttribute('aria-hidden', 'false');

        // Create overlay
        const overlay = document.createElement('div');
        overlay.className = `easter-egg-overlay easter-egg-${config.type}`;
        overlay.setAttribute('role', 'dialog');
        overlay.setAttribute('aria-label', config.title);
        overlay.innerHTML = `
            <div class="easter-egg-content">
                <div class="easter-egg-title">${config.title}</div>
                <div class="easter-egg-sequence" aria-live="polite"></div>
            </div>
        `;

        container.appendChild(overlay);

        // Activate after a frame
        requestAnimationFrame(() => {
            overlay.classList.add('active');
        });

        // Animate sequence
        const sequenceEl = overlay.querySelector('.easter-egg-sequence');
        let currentIndex = 0;

        const showNextItem = () => {
            if (currentIndex < config.sequence.length) {
                sequenceEl.textContent = config.sequence[currentIndex];
                sequenceEl.style.opacity = '0';
                requestAnimationFrame(() => {
                    sequenceEl.style.opacity = '1';
                });
                currentIndex++;
                const timeout = setTimeout(showNextItem, config.duration / (config.sequence.length + 1));
                this.easterEggTimeouts.push(timeout);
            }
        };

        const sequenceTimeout = setTimeout(showNextItem, 800);
        this.easterEggTimeouts.push(sequenceTimeout);

        // Dismiss on click
        const dismissHandler = () => {
            overlay.classList.remove('active');
            setTimeout(() => {
                overlay.remove();
                container.setAttribute('aria-hidden', 'true');
            }, 500);
        };

        overlay.addEventListener('click', dismissHandler);

        // Auto-dismiss
        const dismissTimeout = setTimeout(() => {
            overlay.classList.remove('active');
            setTimeout(() => {
                overlay.remove();
                container.setAttribute('aria-hidden', 'true');
            }, 500);
        }, config.duration);
        this.easterEggTimeouts.push(dismissTimeout);
    }

    // ========================================================================
    // ANIMATION LOOP
    // ========================================================================

    animate() {
        if (!this.isAnimating) return;

        this.updateCursor();
        this.drawCanvas();

        this.animationFrameId = requestAnimationFrame(() => this.animate());
    }

    // ========================================================================
    // CLEANUP
    // ========================================================================

    destroy() {
        // Stop animation
        this.pauseAnimation();

        // Remove document event listeners
        document.removeEventListener('mousemove', this.boundHandlers.mousemove);
        document.removeEventListener('mousedown', this.boundHandlers.mousedown);
        document.removeEventListener('mouseup', this.boundHandlers.mouseup);
        document.removeEventListener('keydown', this.boundHandlers.keydown);
        document.removeEventListener('visibilitychange', this.boundHandlers.visibilitychange);

        // Remove breathing response listener
        if (this.boundHandlers.breathingMousemove) {
            document.removeEventListener('mousemove', this.boundHandlers.breathingMousemove);
        }

        // Remove window event listeners
        window.removeEventListener('scroll', this.boundHandlers.scroll);
        window.removeEventListener('resize', this.boundHandlers.resize);

        // Remove scroll indicator listeners
        if (this.boundHandlers.scrollIndicatorScroll) {
            window.removeEventListener('scroll', this.boundHandlers.scrollIndicatorScroll);
        }
        if (this.scrollIndicator) {
            if (this.boundHandlers.scrollIndicatorClick) {
                this.scrollIndicator.removeEventListener('click', this.boundHandlers.scrollIndicatorClick);
                this.scrollIndicator.removeEventListener('touchend', this.boundHandlers.scrollIndicatorClick);
            }
            if (this.boundHandlers.scrollIndicatorKeydown) {
                this.scrollIndicator.removeEventListener('keydown', this.boundHandlers.scrollIndicatorKeydown);
            }
        }

        // Clear timeouts
        if (this.keyTimeout) {
            clearTimeout(this.keyTimeout);
        }
        if (this.easterEggTimeouts.length) {
            this.easterEggTimeouts.forEach(t => clearTimeout(t));
        }

        // Disconnect observer
        if (this.scrollRevealObserver) {
            this.scrollRevealObserver.disconnect();
        }

        // Clear references
        this.scrollIndicator = null;
    }
}

// Initialize
const experience = new HomeExperience();

// Expose to window for debugging
window.Home = experience;
