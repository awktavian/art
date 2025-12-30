/*
 * HOME — A House That Thinks With You
 * 
 * Every interaction intentional. Every animation earned.
 */

class HomeExperience {
    constructor() {
        this.scrollProgress = 0;
        this.init();
    }

    init() {
        this.setupAmbientBackground();
        this.setupHeroAnimation();
        this.setupScrollNarrative();
        this.setupNavigation();
        this.setupCardInteractions();
        this.setupGoodnightEasterEgg();
        this.setupSelectionSound();
        this.setupTimelinePulse();
        this.setupSectionTransitions();
        this.setupCategoryAccentColors();
        this.setupSoundDesignInfrastructure();
        this.setupScrollIndicator();
        this.removeLazyLoadingState();
    }

    /* ==========================================================================
       AMBIENT BACKGROUND
       ========================================================================== */

    setupAmbientBackground() {
        const canvas = document.getElementById('background-canvas');
        if (!canvas) return;

        const ctx = canvas.getContext('2d');
        let animationId;
        let time = 0;

        // Mouse tracking with smooth interpolation
        this.mouseX = 0.5;
        this.mouseY = 0.5;
        this.targetMouseX = 0.5;
        this.targetMouseY = 0.5;

        const resize = () => {
            const dpr = Math.min(window.devicePixelRatio || 1, 2);
            canvas.width = window.innerWidth * dpr;
            canvas.height = window.innerHeight * dpr;
            ctx.scale(dpr, dpr);
            canvas.style.width = window.innerWidth + 'px';
            canvas.style.height = window.innerHeight + 'px';
        };

        window.addEventListener('resize', resize);
        resize();

        // Track mouse movement for orb response
        document.addEventListener('mousemove', (e) => {
            this.targetMouseX = e.clientX / window.innerWidth;
            this.targetMouseY = e.clientY / window.innerHeight;
        }, { passive: true });

        // Elegant orbs with enhanced properties
        const orbs = [
            { x: 0.25, y: 0.35, size: 350, baseHue: 38, mouseInfluence: 0.15 },
            { x: 0.75, y: 0.65, size: 300, baseHue: 38, mouseInfluence: 0.12 },
            { x: 0.5, y: 0.5, size: 400, baseHue: 35, mouseInfluence: 0.08 },
        ];

        const animate = () => {
            time += 0.016;
            ctx.clearRect(0, 0, canvas.width, canvas.height);

            // Smooth mouse interpolation (easing)
            const lerp = (a, b, t) => a + (b - a) * t;
            this.mouseX = lerp(this.mouseX, this.targetMouseX, 0.05);
            this.mouseY = lerp(this.mouseY, this.targetMouseY, 0.05);

            // Scroll affects warmth: top = warm, bottom = cool
            const warmth = Math.max(0, 1 - this.scrollProgress * 1.5);

            orbs.forEach((orb, i) => {
                // Combine floating animation with mouse influence
                const floatX = Math.sin(time * 0.3 + i * 2) * 30;
                const floatY = Math.cos(time * 0.2 + i * 2) * 20;

                // Mouse attraction - orbs gently drift toward cursor
                const mouseOffsetX = (this.mouseX - 0.5) * window.innerWidth * orb.mouseInfluence;
                const mouseOffsetY = (this.mouseY - 0.5) * window.innerHeight * orb.mouseInfluence;

                // Scroll parallax - orbs move at different rates
                const scrollOffset = this.scrollProgress * (i + 1) * 50;

                const x = orb.x * window.innerWidth + floatX + mouseOffsetX;
                const y = orb.y * window.innerHeight + floatY + mouseOffsetY - scrollOffset;

                // Mouse proximity affects brightness
                const dx = this.mouseX - orb.x;
                const dy = this.mouseY - orb.y;
                const distance = Math.sqrt(dx * dx + dy * dy);
                const proximity = Math.max(0, 1 - distance * 2);
                const brightnessBoost = proximity * 0.02;

                // Blend hue with scroll
                const hue = orb.baseHue * warmth + 220 * (1 - warmth);
                const sat = 25 + warmth * 15;
                const light = 55 + warmth * 10;

                // Size pulsation based on mouse proximity
                const sizeMultiplier = 1 + proximity * 0.1;
                const dynamicSize = orb.size * sizeMultiplier;

                const gradient = ctx.createRadialGradient(x, y, 0, x, y, dynamicSize);
                gradient.addColorStop(0, `hsla(${hue}, ${sat}%, ${light}%, ${0.06 + brightnessBoost})`);
                gradient.addColorStop(0.6, `hsla(${hue}, ${sat}%, ${light}%, ${0.02 + brightnessBoost * 0.3})`);
                gradient.addColorStop(1, 'transparent');

                ctx.fillStyle = gradient;
                ctx.fillRect(0, 0, canvas.width, canvas.height);
            });

            animationId = requestAnimationFrame(animate);
        };

        // Only animate when visible
        const observer = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    animate();
                } else {
                    cancelAnimationFrame(animationId);
                }
            });
        });

        observer.observe(canvas);
    }

    /* ==========================================================================
       HERO ANIMATION
       ========================================================================== */

    setupHeroAnimation() {
        const hero = document.querySelector('.hero');
        const titleMain = document.querySelector('.title-main');

        if (!hero || !titleMain) return;

        // Add pulse rings
        const pulse = document.createElement('div');
        pulse.className = 'hero-pulse';
        pulse.innerHTML = `
            <div class="pulse-ring pulse-ring-1"></div>
            <div class="pulse-ring pulse-ring-2"></div>
            <div class="pulse-ring pulse-ring-3"></div>
        `;
        hero.insertBefore(pulse, hero.firstChild);

        // Add title glow
        const glow = document.createElement('div');
        glow.className = 'title-glow';
        titleMain.appendChild(glow);

        // Demo items micro-interaction
        document.querySelectorAll('.demo-item').forEach((item, i) => {
            item.style.transitionDelay = `${i * 50}ms`;
        });
    }

    /* ==========================================================================
       SCROLL NARRATIVE
       ========================================================================== */

    setupScrollNarrative() {
        const sections = document.querySelectorAll('.section');
        const navBar = document.getElementById('nav-bar');
        const heroHeight = document.getElementById('hero')?.offsetHeight || window.innerHeight;

        this.createProgressIndicator();

        // Intersection observer for reveals
        const revealObserver = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    entry.target.classList.add('visible');

                    // Stagger cards
                    const cards = entry.target.querySelectorAll('.capability-card');
                    cards.forEach((card, i) => {
                        setTimeout(() => card.classList.add('visible'), i * 80);
                    });

                    // Stagger timeline items
                    const timelineItems = entry.target.querySelectorAll('.timeline-item');
                    timelineItems.forEach((item, i) => {
                        setTimeout(() => item.classList.add('visible'), i * 120);
                    });
                }
            });
        }, {
            threshold: 0.1,
            rootMargin: '-5% 0px -5% 0px'
        });

        sections.forEach(section => revealObserver.observe(section));
        document.querySelectorAll('.section-header, .timeline-item').forEach(el => {
            el.classList.add('reveal-on-scroll');
            revealObserver.observe(el);
        });

        // Scroll handler
        let ticking = false;
        const handleScroll = () => {
            if (!ticking) {
                requestAnimationFrame(() => {
                    const scrollTop = window.pageYOffset;
                    const docHeight = document.documentElement.scrollHeight - window.innerHeight;

                    this.scrollProgress = Math.min(1, scrollTop / docHeight);

                    // Progress indicator
                    this.updateProgressIndicator();

                    // Navbar
                    if (scrollTop > heroHeight * 0.4) {
                        navBar?.classList.add('visible');
                    } else {
                        navBar?.classList.remove('visible');
                    }

                    // Active nav link
                    this.updateActiveNavLink();

                    // Hero parallax
                    const heroContent = document.querySelector('.hero-content');
                    if (heroContent && scrollTop < heroHeight) {
                        const opacity = 1 - (scrollTop / heroHeight) * 1.8;
                        const translateY = scrollTop * 0.4;
                        heroContent.style.opacity = Math.max(0, opacity);
                        heroContent.style.transform = `translateY(${translateY}px)`;
                    }

                    ticking = false;
                });
                ticking = true;
            }
        };

        window.addEventListener('scroll', handleScroll, { passive: true });
        handleScroll();
    }

    createProgressIndicator() {
        const indicator = document.createElement('div');
        indicator.className = 'scroll-progress';
        indicator.innerHTML = `
            <div class="progress-track">
                <div class="progress-fill"></div>
            </div>
            <div class="progress-time">
                <span class="time-current">6:47 AM</span>
            </div>
        `;
        document.body.appendChild(indicator);
    }

    updateProgressIndicator() {
        const fill = document.querySelector('.progress-fill');
        const timeDisplay = document.querySelector('.time-current');

        if (fill) {
            fill.style.height = `${this.scrollProgress * 100}%`;
        }

        if (timeDisplay) {
            const times = [
                '6:47 AM', '7:15 AM', '8:20 AM', '10:00 AM',
                '12:00 PM', '2:30 PM', '4:00 PM', '6:45 PM',
                '8:00 PM', '10:30 PM', '11:30 PM'
            ];
            const index = Math.floor(this.scrollProgress * (times.length - 1));
            const newTime = times[Math.min(index, times.length - 1)];
            
            if (timeDisplay.textContent !== newTime) {
                timeDisplay.style.opacity = '0';
                setTimeout(() => {
                    timeDisplay.textContent = newTime;
                    timeDisplay.style.opacity = '1';
                }, 150);
            }
        }
    }

    updateActiveNavLink() {
        const sections = document.querySelectorAll('section[id]');
        const navLinks = document.querySelectorAll('.nav-link');
        const scrollPos = window.pageYOffset + 150;

        let currentSection = '';

        sections.forEach(section => {
            if (scrollPos >= section.offsetTop && scrollPos < section.offsetTop + section.offsetHeight) {
                currentSection = section.id;
            }
        });

        navLinks.forEach(link => {
            link.classList.toggle('active', link.getAttribute('data-section') === currentSection);
        });
    }

    /* ==========================================================================
       NAVIGATION
       ========================================================================== */

    setupNavigation() {
        document.querySelectorAll('.nav-link').forEach(link => {
            link.addEventListener('click', (e) => {
                e.preventDefault();
                const targetId = link.getAttribute('href').substring(1);
                const target = document.getElementById(targetId);

                if (target) {
                    window.scrollTo({
                        top: target.offsetTop - 80,
                        behavior: 'smooth'
                    });
                }
            });
        });
    }

    /* ==========================================================================
       CARD INTERACTIONS
       ========================================================================== */

    setupCardInteractions() {
        document.querySelectorAll('.capability-card').forEach(card => {
            // Mouse tracking
            card.addEventListener('mousemove', (e) => {
                const rect = card.getBoundingClientRect();
                const x = ((e.clientX - rect.left) / rect.width) * 100;
                const y = ((e.clientY - rect.top) / rect.height) * 100;
                card.style.setProperty('--mouse-x', `${x}%`);
                card.style.setProperty('--mouse-y', `${y}%`);
            });

            // Touch feedback
            card.addEventListener('touchstart', () => {
                card.style.transform = 'scale(0.98)';
            }, { passive: true });

            card.addEventListener('touchend', () => {
                card.style.transform = '';
            }, { passive: true });
        });
    }

    /* ==========================================================================
       EASTER EGGS - Multiple triggers
       ========================================================================== */

    setupGoodnightEasterEgg() {
        // Define all easter egg triggers and their configurations
        this.easterEggs = {
            goodnight: {
                title: '"Goodnight"',
                events: [
                    { delay: 1000, text: '41 lights fading...' },
                    { delay: 2500, text: '11 shades closing...' },
                    { delay: 4000, text: '2 locks engaging...' },
                    { delay: 5500, text: 'Security armed.' },
                    { delay: 6500, text: 'Sleep well.' }
                ],
                duration: 8000,
                theme: 'night' // dark overlay
            },
            morning: {
                title: '"Good morning"',
                events: [
                    { delay: 800, text: 'Eight Sleep detecting movement...' },
                    { delay: 2000, text: 'Bedroom lights: 3000K, 20%...' },
                    { delay: 3200, text: 'Shades opening 30%...' },
                    { delay: 4400, text: 'Kitchen spotlights warming...' },
                    { delay: 5600, text: 'Coffee area ready.' },
                    { delay: 6800, text: 'Good morning, Tim.' }
                ],
                duration: 8500,
                theme: 'morning' // warm sunrise overlay
            },
            moviemode: {
                title: '"Movie mode"',
                events: [
                    { delay: 600, text: 'MantelMount descending...' },
                    { delay: 1600, text: 'Living room lights: 10%...' },
                    { delay: 2600, text: 'Shades closing...' },
                    { delay: 3600, text: 'Denon: Dolby Atmos engaged...' },
                    { delay: 4600, text: 'LG TV: Netflix launching...' },
                    { delay: 5600, text: 'Enjoy the show.' }
                ],
                duration: 7000,
                theme: 'cinema' // dark with accent
            }
        };

        let buffer = '';
        let lastKeyTime = 0;
        const maxTriggerLength = Math.max(...Object.keys(this.easterEggs).map(k => k.length));

        document.addEventListener('keydown', (e) => {
            if (['INPUT', 'TEXTAREA'].includes(document.activeElement.tagName)) return;

            const now = Date.now();
            if (now - lastKeyTime > 2000) buffer = '';
            lastKeyTime = now;

            buffer += e.key.toLowerCase();
            if (buffer.length > maxTriggerLength) {
                buffer = buffer.slice(-maxTriggerLength);
            }

            // Check all triggers
            for (const [trigger, config] of Object.entries(this.easterEggs)) {
                if (buffer.endsWith(trigger)) {
                    this.activateEasterEgg(trigger, config);
                    buffer = '';
                    break;
                }
            }
        });
    }

    activateEasterEgg(trigger, config) {
        const overlay = document.createElement('div');
        overlay.className = `easter-egg-overlay easter-egg-${config.theme}`;
        overlay.innerHTML = `
            <div class="easter-egg-content">
                <div class="easter-egg-title">${config.title}</div>
                <div class="easter-egg-sequence"></div>
            </div>
        `;
        document.body.appendChild(overlay);

        requestAnimationFrame(() => {
            overlay.classList.add('active');
        });

        const sequence = overlay.querySelector('.easter-egg-sequence');

        config.events.forEach(({ delay, text }) => {
            setTimeout(() => {
                sequence.style.opacity = '0';
                setTimeout(() => {
                    sequence.textContent = text;
                    sequence.style.opacity = '1';
                }, 200);
            }, delay);
        });

        // Click to dismiss
        overlay.addEventListener('click', () => {
            overlay.classList.remove('active');
            setTimeout(() => overlay.remove(), 1000);
        });

        setTimeout(() => {
            overlay.classList.remove('active');
            setTimeout(() => overlay.remove(), 1000);
        }, config.duration);
    }

    /* ==========================================================================
       SELECTION SOUND (Visual feedback)
       ========================================================================== */

    setupSelectionSound() {
        // Add subtle visual pulse when clicking cards
        document.querySelectorAll('.capability-card, .demo-item, .timeline-content').forEach(el => {
            el.addEventListener('click', (e) => {
                const pulse = document.createElement('div');
                pulse.style.cssText = `
                    position: absolute;
                    width: 100px;
                    height: 100px;
                    border-radius: 50%;
                    background: radial-gradient(circle, rgba(196, 148, 29, 0.3), transparent 70%);
                    transform: translate(-50%, -50%) scale(0);
                    animation: clickPulse 0.6s ease-out forwards;
                    pointer-events: none;
                    left: ${e.offsetX}px;
                    top: ${e.offsetY}px;
                `;
                
                el.style.position = 'relative';
                el.appendChild(pulse);
                
                setTimeout(() => pulse.remove(), 600);
            });
        });

        // Add click pulse animation if not exists
        if (!document.getElementById('click-pulse-style')) {
            const style = document.createElement('style');
            style.id = 'click-pulse-style';
            style.textContent = `
                @keyframes clickPulse {
                    to { transform: translate(-50%, -50%) scale(3); opacity: 0; }
                }
            `;
            document.head.appendChild(style);
        }
    }

    /* ==========================================================================
       TIMELINE PULSE ANIMATION
       ========================================================================== */

    setupTimelinePulse() {
        const timelineItems = document.querySelectorAll('.timeline-item');
        if (!timelineItems.length) return;

        // Get time from each item
        const parseTime = (timeStr) => {
            const match = timeStr.match(/(\d+):(\d+)\s*(AM|PM)/i);
            if (!match) return 0;
            let hours = parseInt(match[1]);
            const minutes = parseInt(match[2]);
            const isPM = match[3].toUpperCase() === 'PM';
            if (isPM && hours !== 12) hours += 12;
            if (!isPM && hours === 12) hours = 0;
            return hours * 60 + minutes;
        };

        const now = new Date();
        const currentMinutes = now.getHours() * 60 + now.getMinutes();

        // Find the current or most recent timeline item
        let currentItem = null;
        let minDiff = Infinity;

        timelineItems.forEach(item => {
            const timeEl = item.querySelector('.timeline-time');
            if (!timeEl) return;

            const itemMinutes = parseTime(timeEl.textContent);
            const diff = currentMinutes - itemMinutes;

            // Find the most recent past event (smallest positive difference)
            if (diff >= 0 && diff < minDiff) {
                minDiff = diff;
                currentItem = item;
            }
        });

        // Add pulse animation to current item
        if (currentItem) {
            currentItem.classList.add('timeline-current');
        }
    }

    /* ==========================================================================
       SECTION TRANSITIONS
       ========================================================================== */

    setupSectionTransitions() {
        const sections = document.querySelectorAll('.section');

        // Add transition effect between sections
        sections.forEach((section, index) => {
            // Add stagger class for animation timing
            section.style.setProperty('--section-index', index);

            // Enhanced parallax for section backgrounds
            const sectionRect = section.getBoundingClientRect;
        });

        // Smooth section entrance with staggered children
        const staggerObserver = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    const section = entry.target;

                    // Stagger the section header elements
                    const header = section.querySelector('.section-header');
                    if (header) {
                        header.classList.add('animate-in');
                        const meta = header.querySelector('.section-meta');
                        const title = header.querySelector('.section-title');
                        const desc = header.querySelector('.section-description');

                        [meta, title, desc].forEach((el, i) => {
                            if (el) {
                                el.style.animationDelay = `${i * 100}ms`;
                            }
                        });
                    }
                }
            });
        }, {
            threshold: 0.15,
            rootMargin: '-10% 0px'
        });

        sections.forEach(section => staggerObserver.observe(section));
    }

    /* ==========================================================================
       CATEGORY ACCENT COLORS
       ========================================================================== */

    setupCategoryAccentColors() {
        // Define category-specific colors
        const categoryColors = {
            lighting: { hue: 45, color: '#D4A832' },     // Warm gold
            audio: { hue: 280, color: '#9B59B6' },       // Purple
            climate: { hue: 200, color: '#3498DB' },     // Blue
            shades: { hue: 160, color: '#1ABC9C' },      // Teal
            security: { hue: 0, color: '#E74C3C' },      // Red
            entertainment: { hue: 320, color: '#E91E63' }, // Pink
            outdoor: { hue: 120, color: '#27AE60' },     // Green
            music: { hue: 270, color: '#8E44AD' },       // Deep purple
            communication: { hue: 210, color: '#2980B9' }, // Blue
            projects: { hue: 30, color: '#E67E22' },     // Orange
            content: { hue: 180, color: '#00BCD4' },     // Cyan
            schedule: { hue: 45, color: '#F1C40F' },     // Yellow
            development: { hue: 0, color: '#1C1A17' },   // Dark
            creative: { hue: 330, color: '#FF6B9D' },    // Rose
            host: { hue: 220, color: '#5C6BC0' },        // Indigo
            sandbox: { hue: 150, color: '#26A69A' },     // Teal
            multiplatform: { hue: 200, color: '#42A5F5' }, // Light blue
            cli: { hue: 90, color: '#66BB6A' },          // Light green
            actions: { hue: 40, color: '#FFA726' },      // Orange
            triggers: { hue: 60, color: '#FFCA28' },     // Amber
            printing: { hue: 15, color: '#FF7043' },     // Deep orange
            laser: { hue: 350, color: '#EF5350' },       // Red
            finishing: { hue: 300, color: '#AB47BC' },   // Purple
            workflow: { hue: 170, color: '#26C6DA' },    // Cyan
            monitoring: { hue: 190, color: '#29B6F6' },  // Light blue
            materials: { hue: 100, color: '#9CCC65' },   // Light green
            presence: { hue: 35, color: '#FFAB00' },     // Amber
            health: { hue: 340, color: '#EC407A' },      // Pink
            travel: { hue: 260, color: '#7E57C2' },      // Deep purple
            learning: { hue: 75, color: '#C0CA33' },     // Lime
            caching: { hue: 185, color: '#00ACC1' },     // Cyan
            circadian: { hue: 25, color: '#FF8A65' },    // Deep orange
            predictive: { hue: 195, color: '#4DD0E1' },  // Cyan
            visitors: { hue: 355, color: '#F06292' },    // Pink
            guest: { hue: 140, color: '#81C784' },       // Green
            sleep: { hue: 230, color: '#5C6BC0' },       // Indigo
            scenes: { hue: 45, color: '#FFD54F' },       // Amber
            integration: { hue: 205, color: '#64B5F6' }, // Blue
            alerts: { hue: 10, color: '#FF5722' }        // Deep orange
        };

        document.querySelectorAll('.capability-card[data-category]').forEach(card => {
            const category = card.dataset.category;
            const colorInfo = categoryColors[category];

            if (colorInfo) {
                card.style.setProperty('--category-hue', colorInfo.hue);
                card.style.setProperty('--category-color', colorInfo.color);
            }
        });
    }

    /* ==========================================================================
       SOUND DESIGN INFRASTRUCTURE
       ========================================================================== */

    setupSoundDesignInfrastructure() {
        // Sound infrastructure (disabled by default, can be enabled via settings)
        this.soundEnabled = false;
        this.audioContext = null;

        // Sound design registry - frequencies and durations for different interactions
        this.soundDesign = {
            cardHover: { freq: 440, duration: 50, type: 'sine', volume: 0.05 },
            cardClick: { freq: 880, duration: 100, type: 'triangle', volume: 0.08 },
            navClick: { freq: 660, duration: 80, type: 'sine', volume: 0.06 },
            easterEggStart: { freq: 220, duration: 200, type: 'sine', volume: 0.1 },
            sectionEnter: { freq: 330, duration: 150, type: 'sine', volume: 0.04 }
        };

        // Expose toggle method for future settings panel
        this.toggleSound = (enabled) => {
            this.soundEnabled = enabled;
            if (enabled && !this.audioContext) {
                this.audioContext = new (window.AudioContext || window.webkitAudioContext)();
            }
        };

        // Play sound method (for future use)
        this.playSound = (soundName) => {
            if (!this.soundEnabled || !this.audioContext) return;

            const sound = this.soundDesign[soundName];
            if (!sound) return;

            const oscillator = this.audioContext.createOscillator();
            const gainNode = this.audioContext.createGain();

            oscillator.connect(gainNode);
            gainNode.connect(this.audioContext.destination);

            oscillator.type = sound.type;
            oscillator.frequency.setValueAtTime(sound.freq, this.audioContext.currentTime);

            gainNode.gain.setValueAtTime(sound.volume, this.audioContext.currentTime);
            gainNode.gain.exponentialRampToValueAtTime(0.001, this.audioContext.currentTime + sound.duration / 1000);

            oscillator.start(this.audioContext.currentTime);
            oscillator.stop(this.audioContext.currentTime + sound.duration / 1000);
        };
    }

    /* ==========================================================================
       SCROLL INDICATOR
       ========================================================================== */

    setupScrollIndicator() {
        const scrollIndicator = document.querySelector('.scroll-indicator');
        if (!scrollIndicator) return;

        // Make it interactive
        const scrollToContent = () => {
            const firstSection = document.querySelector('.section');
            if (firstSection) {
                window.scrollTo({
                    top: firstSection.offsetTop - 80,
                    behavior: 'smooth'
                });
            }
        };

        // Click handler
        scrollIndicator.addEventListener('click', scrollToContent);

        // Keyboard handler for accessibility
        scrollIndicator.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                scrollToContent();
            }
        });

        // Hide when scrolled past hero
        const hero = document.getElementById('hero');
        if (hero) {
            const hideOnScroll = () => {
                const heroBottom = hero.offsetTop + hero.offsetHeight;
                const scrolled = window.pageYOffset;

                if (scrolled > heroBottom * 0.3) {
                    scrollIndicator.style.opacity = '0';
                    scrollIndicator.style.pointerEvents = 'none';
                } else {
                    scrollIndicator.style.opacity = '';
                    scrollIndicator.style.pointerEvents = '';
                }
            };

            window.addEventListener('scroll', hideOnScroll, { passive: true });
        }
    }

    /* ==========================================================================
       UTILITIES
       ========================================================================== */

    removeLazyLoadingState() {
        requestAnimationFrame(() => {
            document.body.classList.remove('loading');
        });
    }
}

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    new HomeExperience();
});

// Expose for debugging
window.HomeExperience = HomeExperience;
