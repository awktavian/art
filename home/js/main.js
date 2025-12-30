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

        // Elegant orbs
        const orbs = [
            { x: 0.25, y: 0.35, size: 350, baseHue: 38 },
            { x: 0.75, y: 0.65, size: 300, baseHue: 38 },
            { x: 0.5, y: 0.5, size: 400, baseHue: 35 },
        ];

        const animate = () => {
            time += 0.016;
            ctx.clearRect(0, 0, canvas.width, canvas.height);

            // Scroll affects warmth: top = warm, bottom = cool
            const warmth = Math.max(0, 1 - this.scrollProgress * 1.5);

            orbs.forEach((orb, i) => {
                // Very gentle floating
                const offsetX = Math.sin(time * 0.3 + i * 2) * 30;
                const offsetY = Math.cos(time * 0.2 + i * 2) * 20;

                const x = orb.x * window.innerWidth + offsetX;
                const y = orb.y * window.innerHeight + offsetY;

                // Blend hue with scroll
                const hue = orb.baseHue * warmth + 220 * (1 - warmth);
                const sat = 25 + warmth * 15;
                const light = 55 + warmth * 10;

                const gradient = ctx.createRadialGradient(x, y, 0, x, y, orb.size);
                gradient.addColorStop(0, `hsla(${hue}, ${sat}%, ${light}%, 0.06)`);
                gradient.addColorStop(0.6, `hsla(${hue}, ${sat}%, ${light}%, 0.02)`);
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
       GOODNIGHT EASTER EGG
       ========================================================================== */

    setupGoodnightEasterEgg() {
        const trigger = 'goodnight';
        let buffer = '';
        let lastKeyTime = 0;

        document.addEventListener('keydown', (e) => {
            if (['INPUT', 'TEXTAREA'].includes(document.activeElement.tagName)) return;

            const now = Date.now();
            if (now - lastKeyTime > 2000) buffer = '';
            lastKeyTime = now;

            buffer += e.key.toLowerCase();
            if (buffer.length > trigger.length) {
                buffer = buffer.slice(-trigger.length);
            }

            if (buffer === trigger) {
                this.activateGoodnight();
                buffer = '';
            }
        });
    }

    activateGoodnight() {
        const overlay = document.createElement('div');
        overlay.className = 'goodnight-overlay';
        overlay.innerHTML = `
            <div class="goodnight-content">
                <div class="goodnight-title">"Goodnight"</div>
                <div class="goodnight-sequence"></div>
            </div>
        `;
        document.body.appendChild(overlay);

        requestAnimationFrame(() => {
            overlay.classList.add('active');
        });

        const sequence = overlay.querySelector('.goodnight-sequence');
        const events = [
            { delay: 1000, text: '41 lights fading...' },
            { delay: 2500, text: '11 shades closing...' },
            { delay: 4000, text: '2 locks engaging...' },
            { delay: 5500, text: 'Security armed.' },
            { delay: 6500, text: 'Sleep well.' }
        ];

        events.forEach(({ delay, text }) => {
            setTimeout(() => {
                sequence.style.opacity = '0';
                setTimeout(() => {
                    sequence.textContent = text;
                    sequence.style.opacity = '1';
                }, 200);
            }, delay);
        });

        setTimeout(() => {
            overlay.classList.remove('active');
            setTimeout(() => overlay.remove(), 1000);
        }, 8000);
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
