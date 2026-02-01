/* ═══════════════════════════════════════════════════════════════════════════
   DESIGN INTELLIGENCE — Interactive Scrollytelling
   
   Features:
   - Animated loading screen with Figma logo assembly
   - Advanced particle canvas with Figma colors
   - Scroll progress tracking
   - Chapter navigation
   - Interactive demos
   - Easter eggs (Konami code, triple-click stars, etc.)
   - Accessibility (reduced motion, keyboard nav)
   
   h(x) ≥ 0
═══════════════════════════════════════════════════════════════════════════ */

(function() {
    'use strict';

    // =========================================================================
    // CONSTANTS
    // =========================================================================
    
    const FIGMA_COLORS = {
        red: '#F24E1E',
        orange: '#FF7262',
        purple: '#A259FF',
        blue: '#1ABCFE',
        green: '#0ACF83'
    };
    
    const PARTICLE_COLORS = [
        'rgba(162, 89, 255, 0.6)',  // purple
        'rgba(26, 188, 254, 0.5)',   // blue
        'rgba(78, 205, 196, 0.5)',   // flow
        'rgba(255, 107, 53, 0.4)',   // spark
        'rgba(10, 207, 131, 0.4)'    // green
    ];
    
    const FIBONACCI = [89, 144, 233, 377, 610, 987, 1597];
    
    // =========================================================================
    // STATE
    // =========================================================================
    
    const state = {
        loaded: false,
        nightMode: false,
        grainMode: true, // On by default for that analog feel
        particles: [],
        mouseX: 0,
        mouseY: 0,
        scrollY: 0,
        prefersReducedMotion: false,
        konamiIndex: 0,
        typedBuffer: '',
        easterEggsFound: new Set()
    };
    
    // Konami code sequence
    const KONAMI_CODE = ['ArrowUp', 'ArrowUp', 'ArrowDown', 'ArrowDown', 
                         'ArrowLeft', 'ArrowRight', 'ArrowLeft', 'ArrowRight', 
                         'b', 'a'];
    
    // =========================================================================
    // LOADING SCREEN
    // =========================================================================
    
    function initLoadingScreen() {
        const loadingScreen = document.getElementById('loading-screen');
        const progressBar = document.getElementById('loading-progress-bar');
        
        if (!loadingScreen || !progressBar) return;
        
        let progress = 0;
        const targetProgress = 100;
        const duration = 1200; // 1.2s loading time
        const startTime = performance.now();
        
        function updateProgress(currentTime) {
            const elapsed = currentTime - startTime;
            progress = Math.min((elapsed / duration) * targetProgress, targetProgress);
            progressBar.style.width = `${progress}%`;
            
            if (progress < targetProgress) {
                requestAnimationFrame(updateProgress);
            } else {
                // Loading complete
                setTimeout(hideLoadingScreen, 300);
            }
        }
        
        requestAnimationFrame(updateProgress);
    }
    
    function hideLoadingScreen() {
        const loadingScreen = document.getElementById('loading-screen');
        const body = document.body;
        
        if (!loadingScreen) return;
        
        // Start fade out
        loadingScreen.classList.add('hidden');
        
        // Small delay before revealing content to prevent flicker
        setTimeout(() => {
            body.classList.remove('loading');
            state.loaded = true;
        }, 100);
        
        // Remove loading screen after animation completes
        setTimeout(() => {
            if (loadingScreen.parentNode) {
                loadingScreen.remove();
            }
        }, 700);
    }
    
    // =========================================================================
    // CANVAS PARTICLE SYSTEM
    // =========================================================================
    
    const canvas = document.getElementById('design-canvas');
    const ctx = canvas ? canvas.getContext('2d') : null;
    let width, height;
    let animationFrame;
    
    function createParticle() {
        const colorIndex = Math.floor(Math.random() * PARTICLE_COLORS.length);
        return {
            x: Math.random() * width,
            y: Math.random() * height,
            vx: (Math.random() - 0.5) * 0.4,
            vy: (Math.random() - 0.5) * 0.4,
            radius: Math.random() * 2.5 + 1,
            color: PARTICLE_COLORS[colorIndex],
            baseColor: PARTICLE_COLORS[colorIndex],
            pulsePhase: Math.random() * Math.PI * 2,
            pulseSpeed: 0.02 + Math.random() * 0.02
        };
    }
    
    function resizeCanvas() {
        if (!canvas) return;
        
        width = canvas.width = window.innerWidth;
        height = canvas.height = window.innerHeight;
        initParticles();
    }
    
    function initParticles() {
        state.particles = [];
        
        // Reduce particle count on mobile or if reduced motion
        const isMobile = window.innerWidth < 768;
        const baseCount = isMobile ? 25 : 50;
        const count = state.prefersReducedMotion ? Math.floor(baseCount / 2) : baseCount;
        
        for (let i = 0; i < count; i++) {
            state.particles.push(createParticle());
        }
    }
    
    function updateParticles() {
        const parallaxFactor = 0.02;
        const scrollFactor = state.scrollY * 0.0001;
        
        state.particles.forEach(p => {
            // Base movement
            p.x += p.vx;
            p.y += p.vy - scrollFactor; // Drift up as user scrolls
            
            // Mouse parallax (subtle)
            const dx = state.mouseX - p.x;
            const dy = state.mouseY - p.y;
            const dist = Math.sqrt(dx * dx + dy * dy);
            
            if (dist < 200 && dist > 0) {
                p.x -= (dx / dist) * parallaxFactor * (200 - dist) / 200;
                p.y -= (dy / dist) * parallaxFactor * (200 - dist) / 200;
            }
            
            // Pulse animation
            p.pulsePhase += p.pulseSpeed;
            
            // Wrap around edges
            if (p.x < -10) p.x = width + 10;
            if (p.x > width + 10) p.x = -10;
            if (p.y < -10) p.y = height + 10;
            if (p.y > height + 10) p.y = -10;
        });
    }
    
    function drawParticles() {
        if (!ctx) return;
        
        ctx.clearRect(0, 0, width, height);
        
        // Night mode: draw stars instead
        if (state.nightMode) {
            drawStars();
            return;
        }
        
        // Draw connections
        ctx.lineWidth = 0.5;
        for (let i = 0; i < state.particles.length; i++) {
            for (let j = i + 1; j < state.particles.length; j++) {
                const p1 = state.particles[i];
                const p2 = state.particles[j];
                const dx = p1.x - p2.x;
                const dy = p1.y - p2.y;
                const dist = Math.sqrt(dx * dx + dy * dy);
                
                if (dist < 150) {
                    const alpha = (1 - dist / 150) * 0.12;
                    ctx.strokeStyle = `rgba(162, 89, 255, ${alpha})`;
                    ctx.beginPath();
                    ctx.moveTo(p1.x, p1.y);
                    ctx.lineTo(p2.x, p2.y);
                    ctx.stroke();
                }
            }
        }
        
        // Draw particles with pulse
        state.particles.forEach(p => {
            const pulse = Math.sin(p.pulsePhase) * 0.3 + 0.7;
            const radius = p.radius * pulse;
            
            ctx.beginPath();
            ctx.arc(p.x, p.y, radius, 0, Math.PI * 2);
            ctx.fillStyle = p.color;
            ctx.fill();
            
            // Glow effect
            const gradient = ctx.createRadialGradient(p.x, p.y, 0, p.x, p.y, radius * 3);
            gradient.addColorStop(0, p.color);
            gradient.addColorStop(1, 'transparent');
            ctx.fillStyle = gradient;
            ctx.fill();
        });
    }
    
    function drawStars() {
        if (!ctx) return;
        
        state.particles.forEach(p => {
            const twinkle = Math.sin(p.pulsePhase * 2) * 0.5 + 0.5;
            
            ctx.beginPath();
            ctx.arc(p.x, p.y, p.radius * 0.8 * twinkle, 0, Math.PI * 2);
            ctx.fillStyle = `rgba(255, 255, 255, ${twinkle * 0.8})`;
            ctx.fill();
        });
    }
    
    function animateCanvas() {
        if (!state.prefersReducedMotion) {
            updateParticles();
        }
        drawParticles();
        animationFrame = requestAnimationFrame(animateCanvas);
    }
    
    // =========================================================================
    // SCROLL PROGRESS
    // =========================================================================
    
    const progressBar = document.getElementById('progress-bar');
    
    function updateProgress() {
        state.scrollY = window.scrollY;
        const docHeight = document.documentElement.scrollHeight - window.innerHeight;
        const progress = (state.scrollY / docHeight) * 100;
        
        if (progressBar) {
            progressBar.style.width = `${progress}%`;
            progressBar.setAttribute('aria-valuenow', Math.round(progress));
        }
        
        // Check for hidden message reveal
        checkHiddenMessage();
    }
    
    // =========================================================================
    // CHAPTER NAVIGATION
    // =========================================================================
    
    const chapterNav = document.getElementById('chapter-nav');
    const chapterDots = chapterNav ? chapterNav.querySelectorAll('.chapter-dot') : [];
    const chapters = document.querySelectorAll('[data-chapter]');
    
    function initChapterObserver() {
        const observer = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    const chapterIndex = entry.target.dataset.chapter;
                    
                    chapterDots.forEach(dot => {
                        const isActive = dot.dataset.chapter === chapterIndex;
                        dot.classList.toggle('active', isActive);
                        dot.setAttribute('aria-current', isActive ? 'step' : 'false');
                    });
                }
            });
        }, {
            rootMargin: '-40% 0px -40% 0px',
            threshold: 0
        });
        
        chapters.forEach(chapter => observer.observe(chapter));
    }
    
    function initChapterClicks() {
        chapterDots.forEach(dot => {
            dot.addEventListener('click', () => {
                const targetChapter = document.querySelector(`[data-chapter="${dot.dataset.chapter}"]`);
                if (targetChapter) {
                    targetChapter.scrollIntoView({ behavior: 'smooth' });
                }
            });
        });
    }
    
    // =========================================================================
    // REVEAL ANIMATIONS
    // =========================================================================
    
    function initRevealAnimations() {
        const revealSelectors = [
            '.chapter-header',
            '.capability-card',
            '.feature-card',
            '.vision-card',
            '.stat-card',
            '.pipeline-stage',
            '.pipeline-connector',
            '.format-card',
            '.response-mock',
            '.detail-item'
        ];
        
        const revealElements = document.querySelectorAll(revealSelectors.join(', '));
        
        const observer = new IntersectionObserver((entries) => {
            entries.forEach((entry) => {
                if (entry.isIntersecting) {
                    const delay = parseInt(entry.target.dataset.delay || 0) * 55;
                    
                    setTimeout(() => {
                        entry.target.classList.add('visible');
                    }, delay);
                    
                    observer.unobserve(entry.target);
                }
            });
        }, {
            rootMargin: '0px 0px -10% 0px',
            threshold: 0.1
        });
        
        revealElements.forEach((el, index) => {
            el.dataset.delay = el.dataset.delay || index % 5;
            observer.observe(el);
        });
    }
    
    // =========================================================================
    // INTERACTIVE DEMOS
    // =========================================================================
    
    function initMagicDemo() {
        const magicDemo = document.querySelector('.magic-demo');
        const responseMock = document.querySelector('.response-mock');
        const scoreRing = document.querySelector('.score-ring');
        
        if (!magicDemo) return;
        
        const observer = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    // Animate response appearing
                    if (responseMock) {
                        responseMock.classList.add('visible');
                    }
                    
                    // Animate score ring with delay
                    if (scoreRing) {
                        setTimeout(() => {
                            scoreRing.classList.add('animated');
                        }, 600);
                    }
                    
                    // Animate detail items
                    const details = magicDemo.querySelectorAll('.detail-item');
                    details.forEach((item, i) => {
                        setTimeout(() => {
                            item.classList.add('visible');
                        }, 800 + i * 200);
                    });
                    
                    observer.unobserve(entry.target);
                }
            });
        }, { threshold: 0.5 });
        
        observer.observe(magicDemo);
    }
    
    function initThresholdSlider() {
        const slider = document.querySelector('.threshold-slider');
        const display = document.querySelector('.threshold-value-display');
        const actionCards = document.querySelectorAll('.action-card');
        
        if (!slider) return;
        
        function updateThreshold(value) {
            if (display) {
                display.textContent = `${value}/100`;
                display.classList.remove('critical', 'warning', 'passing');
                
                if (value < 70) {
                    display.classList.add('critical');
                } else if (value < 80) {
                    display.classList.add('warning');
                } else {
                    display.classList.add('passing');
                }
            }
            
            actionCards.forEach(card => {
                card.classList.remove('active');
                
                if (value < 70 && card.classList.contains('critical-action')) {
                    card.classList.add('active');
                } else if (value >= 70 && value < 80 && card.classList.contains('warning-action')) {
                    card.classList.add('active');
                } else if (value >= 80 && card.classList.contains('passing-action')) {
                    card.classList.add('active');
                }
            });
        }
        
        slider.addEventListener('input', (e) => {
            updateThreshold(parseInt(e.target.value));
        });
        
        // Initialize
        updateThreshold(parseInt(slider.value || 75));
    }
    
    function initSyncButton() {
        const syncButton = document.getElementById('sync-button');
        if (!syncButton) return;
        
        syncButton.addEventListener('click', () => {
            // Animate sync
            syncButton.disabled = true;
            syncButton.textContent = '⟳ Syncing...';
            syncButton.style.animation = 'rotate 1s linear infinite';
            
            // Simulate sync
            setTimeout(() => {
                syncButton.style.animation = '';
                syncButton.textContent = '✓ Synced!';
                showToast('🔄 Design tokens synchronized successfully', 'success');
                
                // Reset after a moment
                setTimeout(() => {
                    syncButton.textContent = '⟳ Sync Now';
                    syncButton.disabled = false;
                }, 2000);
            }, 1500);
        });
    }
    
    // =========================================================================
    // EASTER EGGS
    // =========================================================================
    
    // Konami Code
    function checkKonamiCode(key) {
        if (key === KONAMI_CODE[state.konamiIndex]) {
            state.konamiIndex++;
            
            if (state.konamiIndex === KONAMI_CODE.length) {
                activateGrainMode();
                state.konamiIndex = 0;
                recordEasterEgg('konami');
            }
        } else {
            state.konamiIndex = 0;
        }
    }
    
    function activateGrainMode() {
        state.grainMode = !state.grainMode;
        document.body.classList.toggle('grain-mode', state.grainMode);
        
        if (state.grainMode) {
            showToast('✨ Analog film grain activated', 'info');
            if (!state.easterEggsFound.has('grain')) {
                state.easterEggsFound.add('grain');
                localStorage.setItem('kagami-eggs', JSON.stringify([...state.easterEggsFound]));
            }
        } else {
            showToast('Film grain deactivated', 'info');
        }
    }
    
    // Triple-click title for night mode
    function initTitleTripleClick() {
        const title = document.querySelector('.overture-title');
        let clickCount = 0;
        let clickTimer;
        
        if (!title) return;
        
        title.addEventListener('click', () => {
            clickCount++;
            
            clearTimeout(clickTimer);
            clickTimer = setTimeout(() => {
                clickCount = 0;
            }, 500);
            
            if (clickCount === 3) {
                toggleNightMode();
                clickCount = 0;
                recordEasterEgg('nightMode');
            }
        });
    }
    
    function toggleNightMode() {
        state.nightMode = !state.nightMode;
        document.body.classList.toggle('night-mode', state.nightMode);
        showToast(state.nightMode ? '🌙 Night mode activated' : '☀️ Day mode restored', 'info');
    }
    
    // Type "figma" anywhere
    function checkTypedBuffer(key) {
        if (key.length === 1) {
            state.typedBuffer += key.toLowerCase();
            
            // Keep buffer short
            if (state.typedBuffer.length > 10) {
                state.typedBuffer = state.typedBuffer.slice(-10);
            }
            
            if (state.typedBuffer.includes('figma')) {
                animateFigmaLogo();
                state.typedBuffer = '';
                recordEasterEgg('figmaType');
            }
        }
    }
    
    function animateFigmaLogo() {
        // Brief celebration animation
        showToast('🎨 Figma detected!', 'info');
        triggerConfetti(20);
    }
    
    // Hidden message at footer
    function checkHiddenMessage() {
        const hiddenMessage = document.getElementById('hidden-message');
        if (!hiddenMessage) return;
        
        const scrollBottom = window.innerHeight + window.scrollY;
        const docHeight = document.documentElement.scrollHeight;
        
        if (scrollBottom >= docHeight - 50) {
            hiddenMessage.classList.add('visible');
            recordEasterEgg('hiddenMessage');
        }
    }
    
    // Confetti explosion
    function triggerConfetti(count = 50) {
        const container = document.getElementById('confetti-container');
        if (!container) return;
        
        const colors = Object.values(FIGMA_COLORS);
        
        for (let i = 0; i < count; i++) {
            const confetti = document.createElement('div');
            confetti.className = 'confetti';
            confetti.style.left = `${Math.random() * 100}%`;
            confetti.style.background = colors[Math.floor(Math.random() * colors.length)];
            confetti.style.animationDelay = `${Math.random() * 0.5}s`;
            confetti.style.animationDuration = `${2 + Math.random() * 2}s`;
            
            container.appendChild(confetti);
            
            // Clean up
            setTimeout(() => confetti.remove(), 4000);
        }
    }
    
    function recordEasterEgg(name) {
        if (state.easterEggsFound.has(name)) return;
        
        state.easterEggsFound.add(name);
        
        // Save to localStorage
        try {
            localStorage.setItem('figma-easter-eggs', JSON.stringify([...state.easterEggsFound]));
        } catch (e) {
            // Ignore localStorage errors
        }
        
        // Check if all found
        const allEasterEggs = ['konami', 'nightMode', 'figmaType', 'hiddenMessage'];
        if (allEasterEggs.every(egg => state.easterEggsFound.has(egg))) {
            setTimeout(() => {
                showToast('🏆 You found all Easter eggs!', 'success');
                triggerConfetti(100);
            }, 1000);
        }
    }
    
    function loadEasterEggs() {
        try {
            const saved = localStorage.getItem('figma-easter-eggs');
            if (saved) {
                state.easterEggsFound = new Set(JSON.parse(saved));
            }
        } catch (e) {
            // Ignore localStorage errors
        }
    }
    
    // =========================================================================
    // TOAST NOTIFICATIONS
    // =========================================================================
    
    function showToast(message, type = 'info') {
        const container = document.getElementById('toast-container');
        if (!container) return;
        
        const toast = document.createElement('div');
        toast.className = `toast ${type}`;
        toast.textContent = message;
        
        container.appendChild(toast);
        
        // Auto-dismiss
        setTimeout(() => {
            toast.classList.add('hiding');
            setTimeout(() => toast.remove(), 300);
        }, 3000);
    }
    
    // =========================================================================
    // KEYBOARD NAVIGATION
    // =========================================================================
    
    function initKeyboardNav() {
        document.addEventListener('keydown', (e) => {
            // Chapter navigation
            if (e.key === 'ArrowDown' || e.key === 'j') {
                navigateChapter(1);
            } else if (e.key === 'ArrowUp' || e.key === 'k') {
                navigateChapter(-1);
            }
            
            // Konami code check
            checkKonamiCode(e.key);
            
            // Typed buffer check
            checkTypedBuffer(e.key);
        });
    }
    
    function navigateChapter(direction) {
        const current = [...chapters].find(ch => {
            const rect = ch.getBoundingClientRect();
            return rect.top >= -100 && rect.top < window.innerHeight / 2;
        });
        
        if (current) {
            const currentIndex = parseInt(current.dataset.chapter);
            const targetIndex = currentIndex + direction;
            const targetChapter = document.querySelector(`[data-chapter="${targetIndex}"]`);
            
            if (targetChapter) {
                targetChapter.scrollIntoView({ behavior: 'smooth' });
            }
        }
    }
    
    // =========================================================================
    // MOUSE TRACKING
    // =========================================================================
    
    function initMouseTracking() {
        document.addEventListener('mousemove', (e) => {
            state.mouseX = e.clientX;
            state.mouseY = e.clientY;
        });
    }
    
    // =========================================================================
    // REDUCED MOTION
    // =========================================================================
    
    function checkReducedMotion() {
        const mediaQuery = window.matchMedia('(prefers-reduced-motion: reduce)');
        state.prefersReducedMotion = mediaQuery.matches;
        
        mediaQuery.addEventListener('change', (e) => {
            state.prefersReducedMotion = e.matches;
        });
    }
    
    // =========================================================================
    // CONSOLE EASTER EGG
    // =========================================================================
    
    function printConsoleArt() {
        console.log(`
%c    ╔═══════════════════════════════════════════╗
    ║                                           ║
    ║   ◈ Design Intelligence ◈                 ║
    ║   When Figma Learns to See                ║
    ║                                           ║
    ╠═══════════════════════════════════════════╣
    ║                                           ║
    ║   Built with:                             ║
    ║   • Figma API (14 OAuth scopes)           ║
    ║   • Vision AI (Gemini VLM)                ║
    ║   • Real-time webhooks                    ║
    ║   • Design token sync                     ║
    ║                                           ║
    ║   Type @design-qa on any frame.           ║
    ║                                           ║
    ║   Easter eggs hidden throughout.          ║
    ║   Try: Konami code, triple-click title,   ║
    ║        type "figma", scroll past footer   ║
    ║                                           ║
    ╚═══════════════════════════════════════════╝
    
    h(x) ≥ 0 always.
    `, 'color: #A259FF; font-family: monospace; font-size: 12px;');
    }
    
    // =========================================================================
    // INITIALIZATION
    // =========================================================================
    
    function init() {
        // Check preferences
        checkReducedMotion();
        loadEasterEggs();
        
        // Enable analog grain mode by default
        if (state.grainMode) {
            document.body.classList.add('grain-mode');
        }
        
        // Start loading screen
        initLoadingScreen();
        
        // Initialize canvas
        if (canvas && ctx) {
            window.addEventListener('resize', resizeCanvas);
            resizeCanvas();
            animateCanvas();
        }
        
        // Scroll handling
        window.addEventListener('scroll', updateProgress, { passive: true });
        updateProgress();
        
        // Chapter navigation
        initChapterObserver();
        initChapterClicks();
        
        // Reveal animations
        initRevealAnimations();
        
        // Interactive demos
        initMagicDemo();
        initThresholdSlider();
        initSyncButton();
        
        // Easter eggs
        initTitleTripleClick();
        
        // Keyboard navigation
        initKeyboardNav();
        
        // Mouse tracking
        initMouseTracking();
        
        // Console art
        printConsoleArt();
    }
    
    // =========================================================================
    // SERVICE WORKER REGISTRATION
    // =========================================================================
    
    function registerServiceWorker() {
        if ('serviceWorker' in navigator) {
            window.addEventListener('load', () => {
                navigator.serviceWorker.register('/sw.js')
                    .then((registration) => {
                        console.log('[SW] Registered:', registration.scope);
                    })
                    .catch((error) => {
                        console.log('[SW] Registration failed:', error);
                    });
            });
        }
    }
    
    // =========================================================================
    // START
    // =========================================================================
    
    // Start when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
    
    // Register service worker
    registerServiceWorker();

})();
