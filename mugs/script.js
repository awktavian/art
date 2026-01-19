/**
 * Jill's Mug Gallery
 * Mobile-optimized interactions for iPhone
 * 
 * No particles. No hidden messages. No cleverness.
 * Just warmth, gentle motion, and tactile delight.
 */

(function() {
    'use strict';

    // ═══════════════════════════════════════════════════════════════
    // SCROLL REVEAL — Intersection Observer
    // ═══════════════════════════════════════════════════════════════
    
    const revealObserver = new IntersectionObserver(
        (entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    entry.target.classList.add('visible');
                }
            });
        },
        {
            root: null,
            rootMargin: '0px 0px -60px 0px',
            threshold: 0.1
        }
    );

    function initScrollReveal() {
        const revealElements = document.querySelectorAll('.reveal, .reveal-stagger');
        revealElements.forEach(el => revealObserver.observe(el));
    }

    // ═══════════════════════════════════════════════════════════════
    // CATEGORY FILTERING — With smooth transitions
    // ═══════════════════════════════════════════════════════════════
    
    function initCategoryFilter() {
        const pills = document.querySelectorAll('.category-pill');
        const cards = document.querySelectorAll('.mug-card');
        
        if (!pills.length || !cards.length) return;
        
        pills.forEach(pill => {
            pill.addEventListener('click', () => {
                const filter = pill.dataset.filter;
                
                // Update active pill and ARIA
                pills.forEach(p => {
                    p.classList.remove('active');
                    p.setAttribute('aria-selected', 'false');
                });
                pill.classList.add('active');
                pill.setAttribute('aria-selected', 'true');
                
                // Haptic feedback on iOS
                if ('vibrate' in navigator) {
                    navigator.vibrate(10);
                }
                
                // Filter cards with staggered animation
                let visibleIndex = 0;
                cards.forEach((card) => {
                    const category = card.dataset.category;
                    const shouldShow = filter === 'all' || category === filter;
                    
                    if (shouldShow) {
                        card.style.display = '';
                        card.style.opacity = '0';
                        card.style.transform = 'translateY(20px) scale(0.98)';
                        
                        // Stagger the reveal
                        setTimeout(() => {
                            card.style.transition = 'opacity 0.4s ease, transform 0.4s ease';
                            card.style.opacity = '1';
                            card.style.transform = 'translateY(0) scale(1)';
                        }, visibleIndex * 80);
                        
                        visibleIndex++;
                    } else {
                        card.style.opacity = '0';
                        card.style.transform = 'scale(0.95)';
                        setTimeout(() => {
                            card.style.display = 'none';
                        }, 250);
                    }
                });
            });
        });
    }

    // ═══════════════════════════════════════════════════════════════
    // AUDIO PLAYER — JFK Inaugural Address
    // ═══════════════════════════════════════════════════════════════
    
    function initAudioPlayer() {
        const playerContainer = document.getElementById('jfk-audio');
        if (!playerContainer) return;
        
        const button = playerContainer.querySelector('.audio-player__button');
        const audio = playerContainer.querySelector('audio');
        const icon = playerContainer.querySelector('.audio-player__icon');
        const label = playerContainer.querySelector('.audio-player__label');
        
        if (!button || !audio) return;
        
        let isPlaying = false;
        
        button.addEventListener('click', () => {
            if (isPlaying) {
                audio.pause();
                button.classList.remove('playing');
                button.setAttribute('aria-pressed', 'false');
                button.setAttribute('aria-label', 'Play JFK inaugural address');
                icon.textContent = '▶';
                label.textContent = 'Listen to JFK';
                isPlaying = false;
            } else {
                audio.play().then(() => {
                    button.classList.add('playing');
                    button.setAttribute('aria-pressed', 'true');
                    button.setAttribute('aria-label', 'Pause JFK inaugural address');
                    icon.textContent = '❚❚';
                    label.textContent = 'Playing...';
                    isPlaying = true;
                }).catch(err => {
                    console.log('Audio playback failed:', err);
                    label.textContent = 'Tap to play';
                });
            }

            // Haptic feedback
            if ('vibrate' in navigator) {
                navigator.vibrate(15);
            }
        });
        
        audio.addEventListener('ended', () => {
            button.classList.remove('playing');
            icon.textContent = '▶';
            label.textContent = 'Play again';
            isPlaying = false;
        });
        
        audio.addEventListener('error', () => {
            const errorCode = audio.error ? audio.error.code : 0;
            const messages = {
                1: 'Loading stopped',
                2: 'Network error',
                3: 'Decoding failed',
                4: 'Format not supported'
            };
            label.textContent = messages[errorCode] || 'Audio unavailable';
            button.disabled = false;
            button.style.opacity = '0.7';
            // Allow retry on click
        });
    }

    // ═══════════════════════════════════════════════════════════════
    // SMOOTH ANCHOR SCROLLING
    // ═══════════════════════════════════════════════════════════════
    
    function initSmoothScroll() {
        document.querySelectorAll('a[href^="#"]').forEach(anchor => {
            anchor.addEventListener('click', (e) => {
                const target = document.querySelector(anchor.getAttribute('href'));
                if (target) {
                    e.preventDefault();
                    target.scrollIntoView({
                        behavior: 'smooth',
                        block: 'start'
                    });
                }
            });
        });
    }

    // ═══════════════════════════════════════════════════════════════
    // EXTERNAL LINK HANDLING
    // ═══════════════════════════════════════════════════════════════
    
    function initExternalLinks() {
        document.querySelectorAll('a[href^="http"]').forEach(link => {
            if (!link.hasAttribute('target')) {
                link.setAttribute('target', '_blank');
            }
            if (!link.hasAttribute('rel')) {
                link.setAttribute('rel', 'noopener noreferrer');
            }
        });
    }

    // ═══════════════════════════════════════════════════════════════
    // KEYBOARD NAVIGATION
    // ═══════════════════════════════════════════════════════════════
    
    function initKeyboardNav() {
        const pills = document.querySelectorAll('.category-pill');
        
        pills.forEach((pill, index) => {
            pill.addEventListener('keydown', (e) => {
                let targetIndex = index;
                
                if (e.key === 'ArrowRight' || e.key === 'ArrowDown') {
                    e.preventDefault();
                    targetIndex = (index + 1) % pills.length;
                } else if (e.key === 'ArrowLeft' || e.key === 'ArrowUp') {
                    e.preventDefault();
                    targetIndex = (index - 1 + pills.length) % pills.length;
                } else if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault();
                    pill.click();
                    return;
                } else {
                    return;
                }
                
                pills[targetIndex].focus();
            });
        });
    }

    // ═══════════════════════════════════════════════════════════════
    // MOBILE TOUCH INTERACTIONS
    // ═══════════════════════════════════════════════════════════════
    
    function initTouchInteractions() {
        // Add active states for touch devices
        const cards = document.querySelectorAll('.mug-card');
        
        cards.forEach(card => {
            card.addEventListener('touchstart', () => {
                card.style.transform = 'scale(0.98)';
            }, { passive: true });
            
            card.addEventListener('touchend', () => {
                card.style.transform = '';
            }, { passive: true });
            
            card.addEventListener('touchcancel', () => {
                card.style.transform = '';
            }, { passive: true });
        });
        
        // Horizontal scroll snap for categories on mobile
        const categoriesNav = document.querySelector('.collection__categories');
        if (categoriesNav && window.innerWidth <= 600) {
            categoriesNav.style.scrollSnapType = 'x mandatory';
            document.querySelectorAll('.category-pill').forEach(pill => {
                pill.style.scrollSnapAlign = 'center';
            });
        }
    }

    // ═══════════════════════════════════════════════════════════════
    // IMAGE LAZY LOADING WITH FADE
    // ═══════════════════════════════════════════════════════════════
    
    function initImageLazyLoad() {
        const images = document.querySelectorAll('.mug-card__image img');
        
        images.forEach(img => {
            // Add loading class
            img.style.opacity = '0';
            img.style.transition = 'opacity 0.4s ease';
            
            if (img.complete) {
                img.style.opacity = '1';
            } else {
                img.addEventListener('load', () => {
                    img.style.opacity = '1';
                });
                
                img.addEventListener('error', () => {
                    // Replace with placeholder on error
                    const parent = img.parentElement;
                    if (parent) {
                        parent.innerHTML = '<div class="mug-card__placeholder">☕</div>';
                    }
                });
            }
        });
    }

    // ═══════════════════════════════════════════════════════════════
    // VIEWPORT HEIGHT FIX FOR MOBILE BROWSERS
    // ═══════════════════════════════════════════════════════════════
    
    function initViewportFix() {
        // Fix for iOS Safari 100vh issue
        const setVH = () => {
            const vh = window.innerHeight * 0.01;
            document.documentElement.style.setProperty('--vh', `${vh}px`);
        };
        
        setVH();
        window.addEventListener('resize', setVH);
        window.addEventListener('orientationchange', () => {
            setTimeout(setVH, 100);
        });
    }

    // ═══════════════════════════════════════════════════════════════
    // PULL TO REFRESH PREVENTION (for app-like feel)
    // ═══════════════════════════════════════════════════════════════
    
    function initPullToRefreshPrevention() {
        // Only on iOS
        if (!(/iPad|iPhone|iPod/.test(navigator.userAgent))) return;
        
        let lastY = 0;
        
        document.addEventListener('touchstart', (e) => {
            lastY = e.touches[0].clientY;
        }, { passive: true });
        
        document.addEventListener('touchmove', (e) => {
            const y = e.touches[0].clientY;
            const scrollTop = window.pageYOffset || document.documentElement.scrollTop;
            
            // Prevent pull-to-refresh when at top and pulling down
            if (scrollTop === 0 && y > lastY) {
                // Let it scroll normally - don't prevent
            }
        }, { passive: true });
    }

    // ═══════════════════════════════════════════════════════════════
    // SCROLL PROGRESS INDICATOR
    // ═══════════════════════════════════════════════════════════════

    function initScrollProgress() {
        const progressBar = document.createElement('div');
        progressBar.className = 'scroll-progress';
        document.body.appendChild(progressBar);

        window.addEventListener('scroll', () => {
            const scrollHeight = document.documentElement.scrollHeight - window.innerHeight;
            const scrolled = (window.scrollY / scrollHeight) * 100;
            progressBar.style.width = scrolled + '%';
        }, { passive: true });
    }

    // ═══════════════════════════════════════════════════════════════
    // INITIALIZATION
    // ═══════════════════════════════════════════════════════════════

    function init() {
        initViewportFix();
        initScrollReveal();
        initCategoryFilter();
        initSmoothScroll();
        initExternalLinks();
        initKeyboardNav();
        initAudioPlayer();
        initTouchInteractions();
        initImageLazyLoad();
        initPullToRefreshPrevention();
        initScrollProgress();
        
        // Small console message
        console.log(
            '%c☕ For Jill',
            'font-family: Georgia, serif; font-size: 14px; color: #4A3C2F;'
        );
        console.log(
            '%c"The cup is small. The history is not."',
            'font-family: Georgia, serif; font-size: 11px; font-style: italic; color: #888;'
        );
    }

    // Run on DOM ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
