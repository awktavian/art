/**
 * 🎬 Kagami Slide Controls — Universal Presentation Navigation
 * 
 * Drop-in navigation for any slide deck in the art portfolio.
 * Mobile-friendly with touch gestures, keyboard shortcuts, and polished UI.
 * 
 * Usage:
 *   <script src="/lib/slide-controls.js"></script>
 *   <script>
 *     initSlideControls({
 *       slideSelector: '.slide',
 *       activeClass: 'active'
 *     });
 *   </script>
 */

(function() {
    'use strict';

    // Default configuration
    const defaults = {
        slideSelector: '.slide',
        activeClass: 'active',
        showCounter: true,
        showProgress: true,
        showKeyboardHints: true,
        autoHide: true,
        autoHideDelay: 3000,
        swipeThreshold: 50,
        theme: 'dark' // 'dark' or 'light'
    };

    // Inject CSS
    function injectStyles(config) {
        const isDark = config.theme === 'dark';
        const bg = isDark ? 'rgba(0,0,0,0.92)' : 'rgba(255,255,255,0.95)';
        const text = isDark ? '#ffffff' : '#1a1a2e';
        const textMuted = isDark ? 'rgba(255,255,255,0.6)' : 'rgba(0,0,0,0.5)';
        const accent = '#4a9eff';
        const accentGlow = 'rgba(74,158,255,0.4)';
        const border = isDark ? 'rgba(74,158,255,0.3)' : 'rgba(74,158,255,0.5)';

        const css = `
/* === KAGAMI SLIDE CONTROLS === */
#kagami-controls {
    position: fixed;
    bottom: 0;
    left: 0;
    right: 0;
    z-index: 99999;
    font-family: 'IBM Plex Sans', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    -webkit-font-smoothing: antialiased;
    transition: transform 400ms cubic-bezier(0.4, 0, 0.2, 1), opacity 400ms ease;
}

#kagami-controls.hidden {
    transform: translateY(100%);
    opacity: 0;
    pointer-events: none;
}

#kagami-controls-inner {
    background: ${bg};
    backdrop-filter: blur(20px);
    -webkit-backdrop-filter: blur(20px);
    border-top: 1px solid ${border};
    padding: 12px 16px;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 12px;
    flex-wrap: wrap;
}

/* Progress bar - full width on top */
#kagami-progress-wrap {
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    height: 3px;
    background: ${isDark ? 'rgba(255,255,255,0.1)' : 'rgba(0,0,0,0.1)'};
    cursor: pointer;
}

#kagami-progress {
    height: 100%;
    background: linear-gradient(90deg, ${accent}, #00f0ff);
    width: 0%;
    transition: width 300ms ease;
    box-shadow: 0 0 10px ${accentGlow};
}

/* Navigation buttons */
.kagami-btn {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 6px;
    background: ${isDark ? 'rgba(74,158,255,0.12)' : 'rgba(74,158,255,0.15)'};
    border: 1px solid ${border};
    color: ${text};
    padding: 10px 18px;
    border-radius: 8px;
    font-size: 14px;
    font-weight: 500;
    cursor: pointer;
    transition: all 200ms cubic-bezier(0.4, 0, 0.2, 1);
    outline: none;
    -webkit-tap-highlight-color: transparent;
    touch-action: manipulation;
}

.kagami-btn:hover, .kagami-btn:focus {
    background: ${isDark ? 'rgba(74,158,255,0.25)' : 'rgba(74,158,255,0.25)'};
    border-color: ${accent};
    transform: translateY(-1px);
    box-shadow: 0 4px 12px ${accentGlow};
}

.kagami-btn:active {
    transform: translateY(0) scale(0.98);
}

.kagami-btn svg {
    width: 18px;
    height: 18px;
    stroke-width: 2.5;
}

/* Slide counter */
#kagami-counter {
    color: ${text};
    font-size: 14px;
    font-weight: 600;
    min-width: 70px;
    text-align: center;
    padding: 0 8px;
}

#kagami-counter span {
    color: ${textMuted};
    font-weight: 400;
}

/* Fullscreen button */
.kagami-btn-icon {
    padding: 10px;
    border-radius: 8px;
}

/* Keyboard hints */
#kagami-hints {
    color: ${textMuted};
    font-size: 11px;
    display: flex;
    align-items: center;
    gap: 8px;
    margin-left: 8px;
}

#kagami-hints kbd {
    background: ${isDark ? 'rgba(255,255,255,0.08)' : 'rgba(0,0,0,0.06)'};
    border: 1px solid ${isDark ? 'rgba(255,255,255,0.15)' : 'rgba(0,0,0,0.1)'};
    border-radius: 4px;
    padding: 2px 6px;
    font-family: 'IBM Plex Mono', 'SF Mono', monospace;
    font-size: 10px;
}

/* Touch indicator */
#kagami-touch-hint {
    display: none;
    color: ${textMuted};
    font-size: 12px;
    align-items: center;
    gap: 6px;
}

/* Mobile styles */
@media (max-width: 768px) {
    #kagami-controls-inner {
        padding: 10px 12px;
        gap: 8px;
    }
    
    .kagami-btn {
        padding: 12px 16px;
        font-size: 13px;
        border-radius: 10px;
    }
    
    .kagami-btn-icon {
        padding: 12px;
    }
    
    #kagami-hints {
        display: none !important;
    }
    
    #kagami-touch-hint {
        display: flex;
    }
    
    #kagami-counter {
        font-size: 13px;
    }
    
    /* Larger touch targets */
    .kagami-btn svg {
        width: 20px;
        height: 20px;
    }
}

@media (max-width: 480px) {
    #kagami-controls-inner {
        padding: 8px;
        gap: 6px;
    }
    
    .kagami-btn {
        padding: 10px 12px;
        font-size: 12px;
    }
    
    .kagami-btn .btn-text {
        display: none;
    }
    
    .kagami-btn svg {
        width: 22px;
        height: 22px;
    }
    
    #kagami-counter {
        font-size: 12px;
        min-width: 60px;
    }
    
    #kagami-touch-hint {
        display: none;
    }
}

/* Fullscreen mode adjustments */
:fullscreen #kagami-controls,
:-webkit-full-screen #kagami-controls {
    position: fixed;
}

/* Safe area for notched phones */
@supports (padding-bottom: env(safe-area-inset-bottom)) {
    #kagami-controls-inner {
        padding-bottom: calc(12px + env(safe-area-inset-bottom));
    }
    
    @media (max-width: 768px) {
        #kagami-controls-inner {
            padding-bottom: calc(10px + env(safe-area-inset-bottom));
        }
    }
}
`;
        const style = document.createElement('style');
        style.id = 'kagami-controls-styles';
        style.textContent = css;
        document.head.appendChild(style);
    }

    // Inject HTML
    function injectHTML(config) {
        const html = `
<div id="kagami-controls">
    <div id="kagami-progress-wrap">
        <div id="kagami-progress"></div>
    </div>
    <div id="kagami-controls-inner">
        <button class="kagami-btn" id="kagami-prev" title="Previous (←)">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
                <path d="M15 18l-6-6 6-6"/>
            </svg>
            <span class="btn-text">Prev</span>
        </button>
        
        <div id="kagami-counter">
            <span id="kagami-current">1</span> <span>/</span> <span id="kagami-total">1</span>
        </div>
        
        <button class="kagami-btn" id="kagami-next" title="Next (→)">
            <span class="btn-text">Next</span>
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
                <path d="M9 18l6-6-6-6"/>
            </svg>
        </button>
        
        <button class="kagami-btn kagami-btn-icon" id="kagami-fullscreen" title="Fullscreen (F)">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" id="kagami-fs-icon">
                <path d="M8 3H5a2 2 0 0 0-2 2v3m18 0V5a2 2 0 0 0-2-2h-3m0 18h3a2 2 0 0 0 2-2v-3M3 16v3a2 2 0 0 0 2 2h3"/>
            </svg>
        </button>
        
        <div id="kagami-hints">
            <kbd>←</kbd><kbd>→</kbd> Navigate
            <kbd>F</kbd> Fullscreen
        </div>
        
        <div id="kagami-touch-hint">
            👆 Swipe to navigate
        </div>
    </div>
</div>`;
        document.body.insertAdjacentHTML('beforeend', html);
    }

    // Main controller
    function initSlideControls(options = {}) {
        const config = { ...defaults, ...options };
        
        // Inject UI
        injectStyles(config);
        injectHTML(config);
        
        // Get elements
        const slides = document.querySelectorAll(config.slideSelector);
        const controls = document.getElementById('kagami-controls');
        const progress = document.getElementById('kagami-progress');
        const progressWrap = document.getElementById('kagami-progress-wrap');
        const currentEl = document.getElementById('kagami-current');
        const totalEl = document.getElementById('kagami-total');
        const prevBtn = document.getElementById('kagami-prev');
        const nextBtn = document.getElementById('kagami-next');
        const fsBtn = document.getElementById('kagami-fullscreen');
        const fsIcon = document.getElementById('kagami-fs-icon');
        
        let currentSlide = 0;
        const totalSlides = slides.length;
        let hideTimeout;
        let touchStartX = 0;
        let touchStartY = 0;
        
        // Update display
        totalEl.textContent = totalSlides;
        
        function showSlide(index) {
            if (index < 0) index = 0;
            if (index >= totalSlides) index = totalSlides - 1;
            
            slides.forEach((s, i) => {
                s.classList.toggle(config.activeClass, i === index);
            });
            
            currentSlide = index;
            currentEl.textContent = index + 1;
            progress.style.width = ((index + 1) / totalSlides * 100) + '%';
            
            // Call external showSlide if exists
            if (window.showSlide && typeof window.showSlide === 'function') {
                window.showSlide(index);
            }
        }
        
        function next() {
            showSlide(currentSlide + 1);
        }
        
        function prev() {
            showSlide(currentSlide - 1);
        }
        
        function goToSlide(index) {
            showSlide(index);
        }
        
        function toggleFullscreen() {
            if (!document.fullscreenElement && !document.webkitFullscreenElement) {
                const el = document.documentElement;
                if (el.requestFullscreen) {
                    el.requestFullscreen();
                } else if (el.webkitRequestFullscreen) {
                    el.webkitRequestFullscreen();
                }
            } else {
                if (document.exitFullscreen) {
                    document.exitFullscreen();
                } else if (document.webkitExitFullscreen) {
                    document.webkitExitFullscreen();
                }
            }
        }
        
        function updateFullscreenIcon() {
            const isFs = document.fullscreenElement || document.webkitFullscreenElement;
            fsIcon.innerHTML = isFs 
                ? '<path d="M8 3v3a2 2 0 0 1-2 2H3m18 0h-3a2 2 0 0 1-2-2V3m0 18v-3a2 2 0 0 1 2-2h3M3 16h3a2 2 0 0 1 2 2v3"/>'
                : '<path d="M8 3H5a2 2 0 0 0-2 2v3m18 0V5a2 2 0 0 0-2-2h-3m0 18h3a2 2 0 0 0 2-2v-3M3 16v3a2 2 0 0 0 2 2h3"/>';
        }
        
        function showControls() {
            controls.classList.remove('hidden');
            if (config.autoHide) {
                clearTimeout(hideTimeout);
                hideTimeout = setTimeout(() => {
                    controls.classList.add('hidden');
                }, config.autoHideDelay);
            }
        }
        
        // Event listeners
        prevBtn.addEventListener('click', prev);
        nextBtn.addEventListener('click', next);
        fsBtn.addEventListener('click', toggleFullscreen);
        
        progressWrap.addEventListener('click', (e) => {
            const rect = progressWrap.getBoundingClientRect();
            const percent = (e.clientX - rect.left) / rect.width;
            goToSlide(Math.floor(percent * totalSlides));
        });
        
        // Keyboard
        document.addEventListener('keydown', (e) => {
            showControls();
            switch(e.key) {
                case 'ArrowRight':
                case 'PageDown':
                case ' ':
                    e.preventDefault();
                    next();
                    break;
                case 'ArrowLeft':
                case 'PageUp':
                    e.preventDefault();
                    prev();
                    break;
                case 'Home':
                    e.preventDefault();
                    goToSlide(0);
                    break;
                case 'End':
                    e.preventDefault();
                    goToSlide(totalSlides - 1);
                    break;
                case 'f':
                case 'F':
                    e.preventDefault();
                    toggleFullscreen();
                    break;
                case 'Escape':
                    if (document.fullscreenElement) {
                        document.exitFullscreen();
                    }
                    break;
            }
        });
        
        // Touch/swipe
        document.addEventListener('touchstart', (e) => {
            touchStartX = e.touches[0].clientX;
            touchStartY = e.touches[0].clientY;
            showControls();
        }, { passive: true });
        
        document.addEventListener('touchend', (e) => {
            const touchEndX = e.changedTouches[0].clientX;
            const touchEndY = e.changedTouches[0].clientY;
            const deltaX = touchEndX - touchStartX;
            const deltaY = touchEndY - touchStartY;
            
            // Only trigger if horizontal swipe is dominant
            if (Math.abs(deltaX) > Math.abs(deltaY) && Math.abs(deltaX) > config.swipeThreshold) {
                if (deltaX > 0) {
                    prev();
                } else {
                    next();
                }
            }
        }, { passive: true });
        
        // Mouse movement shows controls
        document.addEventListener('mousemove', showControls);
        
        // Fullscreen change
        document.addEventListener('fullscreenchange', updateFullscreenIcon);
        document.addEventListener('webkitfullscreenchange', updateFullscreenIcon);
        
        // Initialize
        showSlide(0);
        showControls();
        
        // Export API
        window.kagamiSlides = {
            next,
            prev,
            goToSlide,
            toggleFullscreen,
            getCurrentSlide: () => currentSlide,
            getTotalSlides: () => totalSlides
        };
        
        console.log('🎬 Kagami Slide Controls initialized:', totalSlides, 'slides');
    }
    
    // Export
    window.initSlideControls = initSlideControls;
})();
