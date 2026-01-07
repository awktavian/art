/**
 * Master of Puppets — Main Application
 *
 * - Easter egg (click on mirror symbol)
 * - WebXR immersive mode
 * - Scroll-based animations
 * - Movement navigation
 * - Hero play button
 *
 * h(x) >= 0
 */

(function() {
    'use strict';

    // ═══════════════════════════════════════════════════════════════════════════
    // DOM ELEMENTS
    // ═══════════════════════════════════════════════════════════════════════════

    const elements = {
        audio: document.getElementById('audio'),
        playBtn: document.getElementById('play-btn'),
        heroPlayBtn: document.getElementById('hero-play-btn'),
        progressBar: document.getElementById('progress-bar'),
        progressFill: document.getElementById('progress-fill'),
        timeDisplay: document.getElementById('time-display'),
        progressBarTop: document.getElementById('progress-bar-top'),
        movementNav: document.getElementById('movement-nav'),
        movementDots: document.querySelectorAll('.movement-dot'),
        movements: document.querySelectorAll('[data-movement]'),
        mirrorEasterEgg: document.getElementById('mirror-easter-egg'),
        easterEggOverlay: document.getElementById('easter-egg-overlay'),
        easterEggClose: document.querySelector('.easter-egg-close'),
        webxrBtn: document.getElementById('webxr-btn'),
        volumeSlider: document.getElementById('volume-slider'),
        volumeIcon: document.getElementById('volume-icon')
    };

    // ═══════════════════════════════════════════════════════════════════════════
    // CONSTANTS
    // ═══════════════════════════════════════════════════════════════════════════

    const DURATION = 402; // 6:42 in seconds
    const FIBONACCI = [89, 144, 233, 377, 610, 987, 1597, 2584];

    // ═══════════════════════════════════════════════════════════════════════════
    // UTILITIES
    // ═══════════════════════════════════════════════════════════════════════════

    function formatTime(seconds) {
        const mins = Math.floor(seconds / 60);
        const secs = Math.floor(seconds % 60);
        return `${mins}:${secs.toString().padStart(2, '0')}`;
    }

    function lerp(start, end, t) {
        return start + (end - start) * t;
    }

    // ═══════════════════════════════════════════════════════════════════════════
    // EASTER EGG - THE MIRROR
    // ═══════════════════════════════════════════════════════════════════════════

    function initEasterEgg() {
        if (!elements.mirrorEasterEgg || !elements.easterEggOverlay) return;

        const showEasterEgg = () => {
            elements.easterEggOverlay.classList.add('active');
            elements.easterEggOverlay.setAttribute('aria-hidden', 'false');
            document.body.style.overflow = 'hidden';

            // Trigger particle burst
            if (window.ParticleCanvas) {
                window.ParticleCanvas.spawnBurst('gold', 1);
            }
        };

        const hideEasterEgg = () => {
            elements.easterEggOverlay.classList.remove('active');
            elements.easterEggOverlay.setAttribute('aria-hidden', 'true');
            document.body.style.overflow = '';
        };

        // Click handler
        elements.mirrorEasterEgg.addEventListener('click', showEasterEgg);

        // Keyboard handler (Enter/Space)
        elements.mirrorEasterEgg.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                showEasterEgg();
            }
        });

        // Close button
        if (elements.easterEggClose) {
            elements.easterEggClose.addEventListener('click', hideEasterEgg);
        }

        // Click outside to close
        elements.easterEggOverlay.addEventListener('click', (e) => {
            if (e.target === elements.easterEggOverlay) {
                hideEasterEgg();
            }
        });

        // Escape to close
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && elements.easterEggOverlay.classList.contains('active')) {
                hideEasterEgg();
            }
        });

        console.log('Easter egg initialized');
    }

    // ═══════════════════════════════════════════════════════════════════════════
    // WEBXR IMMERSIVE MODE
    // ═══════════════════════════════════════════════════════════════════════════

    let xrSession = null;

    async function initWebXR() {
        if (!elements.webxrBtn) return;

        // Check WebXR support
        if (!navigator.xr) {
            console.log('WebXR not supported');
            return;
        }

        try {
            const isSupported = await navigator.xr.isSessionSupported('immersive-vr');
            if (isSupported) {
                elements.webxrBtn.style.display = 'flex';
                elements.webxrBtn.addEventListener('click', toggleXRSession);
                console.log('WebXR available');
            }
        } catch (e) {
            console.log('WebXR check failed:', e.message);
        }
    }

    async function toggleXRSession() {
        if (xrSession) {
            await xrSession.end();
            return;
        }

        try {
            xrSession = await navigator.xr.requestSession('immersive-vr', {
                optionalFeatures: ['local-floor', 'bounded-floor']
            });

            xrSession.addEventListener('end', () => {
                xrSession = null;
                elements.webxrBtn.querySelector('.webxr-text').textContent = 'Enter VR';
            });

            elements.webxrBtn.querySelector('.webxr-text').textContent = 'Exit VR';

            // In a full implementation, we'd set up the XR render loop here
            console.log('XR session started');
        } catch (e) {
            console.error('Failed to start XR session:', e);
        }
    }

    // ═══════════════════════════════════════════════════════════════════════════
    // SCROLL ANIMATIONS
    // ═══════════════════════════════════════════════════════════════════════════

    function initScrollAnimations() {
        const observerOptions = {
            root: null,
            rootMargin: '-10% 0px -10% 0px',
            threshold: [0, 0.1, 0.5, 1]
        };

        const observer = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    entry.target.classList.add('visible');

                    // Update movement navigation
                    const movement = entry.target.dataset.movement;
                    if (movement !== undefined) {
                        updateMovementNav(parseInt(movement));
                    }
                }
            });
        }, observerOptions);

        // Observe movements
        elements.movements.forEach(movement => {
            observer.observe(movement);
        });

        // Observe other animated elements
        document.querySelectorAll('.technique-card, .instrument-section, .score-display').forEach(el => {
            observer.observe(el);
        });

        // Update scroll progress bar
        window.addEventListener('scroll', updateScrollProgress, { passive: true });
    }

    function updateScrollProgress() {
        const scrollTop = window.scrollY;
        const docHeight = document.documentElement.scrollHeight - window.innerHeight;
        const progress = (scrollTop / docHeight) * 100;

        if (elements.progressBarTop) {
            elements.progressBarTop.style.width = `${Math.min(progress, 100)}%`;
            elements.progressBarTop.setAttribute('aria-valuenow', Math.round(progress));
        }
    }

    function updateMovementNav(activeMovement) {
        elements.movementDots.forEach(dot => {
            const dotMovement = parseInt(dot.dataset.movement);
            dot.classList.toggle('active', dotMovement === activeMovement);
        });
    }

    // ═══════════════════════════════════════════════════════════════════════════
    // MOVEMENT NAVIGATION
    // ═══════════════════════════════════════════════════════════════════════════

    function initMovementNav() {
        elements.movementDots.forEach(dot => {
            dot.addEventListener('click', () => {
                const movement = dot.dataset.movement;
                const target = document.querySelector(`[data-movement="${movement}"]`);
                if (target) {
                    target.scrollIntoView({ behavior: 'smooth' });
                }
            });
        });
    }

    // ═══════════════════════════════════════════════════════════════════════════
    // HERO PLAY BUTTON
    // ═══════════════════════════════════════════════════════════════════════════

    function initHeroPlay() {
        if (!elements.heroPlayBtn || !elements.audio) return;

        elements.heroPlayBtn.addEventListener('click', () => {
            // Scroll to orchestra section
            const orchestraSection = document.getElementById('movement-3');
            if (orchestraSection) {
                orchestraSection.scrollIntoView({ behavior: 'smooth' });
            }

            // Start playback after a short delay
            setTimeout(() => {
                if (elements.audio.paused) {
                    elements.audio.play().catch(e => console.log('Play failed:', e));
                }
            }, 800);
        });
    }

    // ═══════════════════════════════════════════════════════════════════════════
    // VOLUME CONTROL
    // ═══════════════════════════════════════════════════════════════════════════

    function initVolumeControl() {
        if (!elements.volumeSlider || !elements.audio) return;

        elements.volumeSlider.addEventListener('input', (e) => {
            const vol = e.target.value / 100;
            elements.audio.volume = vol;
            updateVolumeIcon(vol);
        });

        // Initialize
        elements.audio.volume = elements.volumeSlider.value / 100;

        // Mute toggle
        if (elements.volumeIcon) {
            elements.volumeIcon.addEventListener('click', () => {
                elements.audio.muted = !elements.audio.muted;
                updateVolumeIcon(elements.audio.muted ? 0 : elements.audio.volume);
            });
        }
    }

    function updateVolumeIcon(vol) {
        if (!elements.volumeIcon) return;
        if (vol === 0 || elements.audio.muted) {
            elements.volumeIcon.textContent = '🔇';
        } else if (vol < 0.5) {
            elements.volumeIcon.textContent = '🔉';
        } else {
            elements.volumeIcon.textContent = '🔊';
        }
    }

    // ═══════════════════════════════════════════════════════════════════════════
    // TITLE ANIMATION
    // ═══════════════════════════════════════════════════════════════════════════

    function initTitleAnimation() {
        const titleWords = document.querySelectorAll('.title-word');
        if (!titleWords.length) return;

        titleWords.forEach((word, i) => {
            word.style.opacity = '0';
            word.style.transform = 'translateY(30px)';
            word.style.transition = `all ${FIBONACCI[4]}ms cubic-bezier(0.16, 1, 0.3, 1)`;
            word.style.transitionDelay = `${FIBONACCI[2] + i * FIBONACCI[1]}ms`;
        });

        // Trigger after a short delay
        setTimeout(() => {
            titleWords.forEach(word => {
                word.style.opacity = '1';
                word.style.transform = 'translateY(0)';
            });
        }, 100);
    }

    // ═══════════════════════════════════════════════════════════════════════════
    // OVERTURE META ANIMATION
    // ═══════════════════════════════════════════════════════════════════════════

    function initOvertureAnimation() {
        const content = document.querySelector('.overture-content');
        if (!content) return;

        // Already handled by CSS animations, but we can enhance
        const metaItems = content.querySelectorAll('.meta-item');
        metaItems.forEach((item, i) => {
            item.style.animationDelay = `${2584 + i * 144}ms`;
        });
    }

    // ═══════════════════════════════════════════════════════════════════════════
    // KEYBOARD NAVIGATION
    // ═══════════════════════════════════════════════════════════════════════════

    function initKeyboardNav() {
        document.addEventListener('keydown', (e) => {
            // Don't intercept if user is typing
            if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;

            switch (e.code) {
                case 'Space':
                    e.preventDefault();
                    togglePlay();
                    break;
                case 'ArrowRight':
                    e.preventDefault();
                    if (elements.audio) {
                        elements.audio.currentTime = Math.min(elements.audio.currentTime + 5, DURATION);
                    }
                    break;
                case 'ArrowLeft':
                    e.preventDefault();
                    if (elements.audio) {
                        elements.audio.currentTime = Math.max(elements.audio.currentTime - 5, 0);
                    }
                    break;
                case 'Home':
                    e.preventDefault();
                    if (elements.audio) elements.audio.currentTime = 0;
                    break;
                case 'End':
                    e.preventDefault();
                    if (elements.audio) elements.audio.currentTime = DURATION - 1;
                    break;
                case 'ArrowUp':
                    e.preventDefault();
                    if (elements.volumeSlider) {
                        elements.volumeSlider.value = Math.min(parseInt(elements.volumeSlider.value) + 10, 100);
                        elements.volumeSlider.dispatchEvent(new Event('input'));
                    }
                    break;
                case 'ArrowDown':
                    e.preventDefault();
                    if (elements.volumeSlider) {
                        elements.volumeSlider.value = Math.max(parseInt(elements.volumeSlider.value) - 10, 0);
                        elements.volumeSlider.dispatchEvent(new Event('input'));
                    }
                    break;
                case 'KeyM':
                    if (elements.audio) {
                        elements.audio.muted = !elements.audio.muted;
                        updateVolumeIcon(elements.audio.muted ? 0 : elements.audio.volume);
                    }
                    break;
            }
        });
    }

    function togglePlay() {
        if (!elements.audio || !elements.playBtn) return;

        if (elements.audio.paused) {
            elements.audio.play().catch(e => console.log('Play failed:', e));
        } else {
            elements.audio.pause();
        }
    }

    // ═══════════════════════════════════════════════════════════════════════════
    // KONAMI CODE EASTER EGG
    // ═══════════════════════════════════════════════════════════════════════════

    const KONAMI_CODE = ['ArrowUp', 'ArrowUp', 'ArrowDown', 'ArrowDown', 'ArrowLeft', 'ArrowRight', 'ArrowLeft', 'ArrowRight', 'KeyB', 'KeyA'];
    let konamiProgress = 0;
    let metalModeActive = false;

    function initKonamiCode() {
        document.addEventListener('keydown', (e) => {
            if (e.code === KONAMI_CODE[konamiProgress]) {
                konamiProgress++;
                if (konamiProgress === KONAMI_CODE.length) {
                    activateMetalMode();
                    konamiProgress = 0;
                }
            } else {
                konamiProgress = 0;
            }
        });
    }

    function activateMetalMode() {
        if (metalModeActive) return;
        metalModeActive = true;

        console.log('🤘 METAL MODE ACTIVATED 🤘');

        // Flash the screen with Metallica colors
        const flash = document.createElement('div');
        flash.style.cssText = `
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: linear-gradient(45deg, #8b0000, #0a0a0a, #c0c0c0);
            z-index: 10000;
            opacity: 0;
            pointer-events: none;
            transition: opacity 144ms ease-out;
        `;
        document.body.appendChild(flash);

        // Flash sequence
        setTimeout(() => flash.style.opacity = '0.8', 0);
        setTimeout(() => flash.style.opacity = '0', 144);
        setTimeout(() => flash.style.opacity = '0.6', 288);
        setTimeout(() => flash.style.opacity = '0', 432);
        setTimeout(() => flash.style.opacity = '0.4', 576);
        setTimeout(() => {
            flash.style.opacity = '0';
            setTimeout(() => flash.remove(), 233);
        }, 720);

        // Trigger massive particle burst
        if (window.ParticleCanvas && window.ParticleCanvas.triggerBeat) {
            for (let i = 0; i < 5; i++) {
                setTimeout(() => window.ParticleCanvas.triggerBeat(), i * 100);
            }
        }

        // Spawn section bursts
        if (window.ParticleCanvas && window.ParticleCanvas.spawnBurst) {
            window.ParticleCanvas.spawnBurst('brass', 1);
            setTimeout(() => window.ParticleCanvas.spawnBurst('percussion', 1), 144);
            setTimeout(() => window.ParticleCanvas.spawnBurst('strings', 1), 288);
        }

        // Add temporary metal glow to title
        const title = document.querySelector('.overture-title');
        if (title) {
            title.style.transition = 'all 377ms ease-out';
            title.style.textShadow = '0 0 30px #8b0000, 0 0 60px #c0c0c0, 0 0 90px #8b0000';
            setTimeout(() => {
                title.style.textShadow = '';
            }, 2000);
        }

        // Reset after effect
        setTimeout(() => {
            metalModeActive = false;
        }, 3000);
    }

    // ═══════════════════════════════════════════════════════════════════════════
    // COMPLETION CELEBRATION
    // ═══════════════════════════════════════════════════════════════════════════

    function initCompletionCelebration() {
        if (!elements.audio) return;

        elements.audio.addEventListener('ended', () => {
            // Trigger celebration particle burst
            if (window.ParticleCanvas && window.ParticleCanvas.spawnBurst) {
                window.ParticleCanvas.spawnBurst('brass', 1);
                setTimeout(() => window.ParticleCanvas.spawnBurst('strings', 1), 233);
                setTimeout(() => window.ParticleCanvas.spawnBurst('percussion', 1), 466);
            }

            // Show completion message
            const message = document.createElement('div');
            message.innerHTML = `
                <div style="
                    position: fixed;
                    top: 50%;
                    left: 50%;
                    transform: translate(-50%, -50%);
                    text-align: center;
                    z-index: 10000;
                    animation: completion-fade 3000ms ease-out forwards;
                ">
                    <div style="
                        font-family: 'EB Garamond', serif;
                        font-size: clamp(1.5rem, 4vw, 2.5rem);
                        color: #e5b84a;
                        margin-bottom: 1rem;
                        text-shadow: 0 0 20px rgba(229, 184, 74, 0.5);
                    ">The symphony is complete.</div>
                    <div style="
                        font-size: 3rem;
                        opacity: 0.8;
                    ">鏡</div>
                </div>
            `;

            // Add animation keyframes
            const style = document.createElement('style');
            style.textContent = `
                @keyframes completion-fade {
                    0% { opacity: 0; transform: translate(-50%, -50%) scale(0.9); }
                    20% { opacity: 1; transform: translate(-50%, -50%) scale(1); }
                    80% { opacity: 1; }
                    100% { opacity: 0; }
                }
            `;
            document.head.appendChild(style);
            document.body.appendChild(message);

            // Remove after animation
            setTimeout(() => {
                message.remove();
                style.remove();
            }, 3500);
        });
    }

    // ═══════════════════════════════════════════════════════════════════════════
    // PLAY BUTTON STATE
    // ═══════════════════════════════════════════════════════════════════════════

    function initPlayButton() {
        if (!elements.audio || !elements.playBtn) return;

        elements.playBtn.addEventListener('click', togglePlay);

        elements.audio.addEventListener('play', () => {
            elements.playBtn.classList.add('playing');
            elements.playBtn.setAttribute('aria-label', 'Pause');
        });

        elements.audio.addEventListener('pause', () => {
            elements.playBtn.classList.remove('playing');
            elements.playBtn.setAttribute('aria-label', 'Play');
        });

        elements.audio.addEventListener('ended', () => {
            elements.playBtn.classList.remove('playing');
            elements.playBtn.setAttribute('aria-label', 'Play');
        });
    }

    // ═══════════════════════════════════════════════════════════════════════════
    // PROGRESS BAR SCRUBBING
    // ═══════════════════════════════════════════════════════════════════════════

    function initProgressBar() {
        if (!elements.progressBar || !elements.audio) return;

        let isDragging = false;

        const seek = (e) => {
            const rect = elements.progressBar.getBoundingClientRect();
            const x = e.clientX || (e.touches && e.touches[0] ? e.touches[0].clientX : 0);
            const pct = Math.max(0, Math.min(1, (x - rect.left) / rect.width));
            elements.audio.currentTime = pct * DURATION;
        };

        elements.progressBar.addEventListener('mousedown', (e) => {
            isDragging = true;
            seek(e);
        });

        elements.progressBar.addEventListener('touchstart', (e) => {
            isDragging = true;
            seek(e);
        }, { passive: true });

        document.addEventListener('mousemove', (e) => {
            if (isDragging) seek(e);
        });

        document.addEventListener('touchmove', (e) => {
            if (isDragging) seek(e);
        }, { passive: true });

        document.addEventListener('mouseup', () => { isDragging = false; });
        document.addEventListener('touchend', () => { isDragging = false; });

        // Update progress display
        elements.audio.addEventListener('timeupdate', () => {
            const progress = (elements.audio.currentTime / DURATION) * 100;
            if (elements.progressFill) {
                elements.progressFill.style.width = `${progress}%`;
            }
            if (elements.progressBar) {
                elements.progressBar.setAttribute('aria-valuenow', Math.round(progress));
            }
            if (elements.timeDisplay) {
                elements.timeDisplay.textContent = `${formatTime(elements.audio.currentTime)} / ${formatTime(DURATION)}`;
            }
        });
    }

    // ═══════════════════════════════════════════════════════════════════════════
    // INITIALIZE
    // ═══════════════════════════════════════════════════════════════════════════

    function init() {
        initTitleAnimation();
        initOvertureAnimation();
        initEasterEgg();
        initWebXR();
        initScrollAnimations();
        initMovementNav();
        initHeroPlay();
        initVolumeControl();
        initKeyboardNav();
        initPlayButton();
        initProgressBar();
        initKonamiCode();
        initCompletionCelebration();

        console.log('Master of Puppets — A Fantasia');
        console.log('Controls: Space (play/pause), ← → (seek), ↑ ↓ (volume), M (mute)');
        console.log('h(x) >= 0');
    }

    // Wait for DOM
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }

})();
