/**
 * Master of Puppets — Main Application
 * 
 * Audio player controls, keyboard shortcuts, scroll handling
 * 
 * h(x) ≥ 0
 */

(function() {
    'use strict';

    // =========================================================================
    // DOM ELEMENTS
    // =========================================================================
    
    const audio = document.getElementById('audio');
    const playBtn = document.getElementById('play-btn');
    const heroPlayBtn = document.getElementById('hero-play-btn');
    const progressBar = document.getElementById('progress-bar');
    const progressFill = document.getElementById('progress-fill');
    const timeDisplay = document.getElementById('time-display');
    const volumeSlider = document.getElementById('volume-slider');
    const volumeIcon = document.getElementById('volume-icon');
    const progressBarTop = document.getElementById('progress-bar-top');
    const movementDots = document.querySelectorAll('.movement-dot');
    const movements = document.querySelectorAll('.movement, .overture');
    const easterEggOverlay = document.getElementById('easter-egg-overlay');
    const mirrorSymbol = document.getElementById('mirror-easter-egg');

    if (!audio || !playBtn) {
        console.warn('App: Required elements not found');
        return;
    }

    // =========================================================================
    // STATE
    // =========================================================================
    
    const DURATION = 402; // 6:42 in seconds
    let isPlaying = false;
    let currentMovement = 0;

    // =========================================================================
    // UTILITIES
    // =========================================================================
    
    function formatTime(seconds) {
        const mins = Math.floor(seconds / 60);
        const secs = Math.floor(seconds % 60);
        return `${mins}:${secs.toString().padStart(2, '0')}`;
    }

    // =========================================================================
    // PLAYBACK CONTROL
    // =========================================================================
    
    function togglePlay() {
        if (isPlaying) {
            audio.pause();
            playBtn.classList.remove('playing');
            playBtn.setAttribute('aria-label', 'Play');
        } else {
            audio.play().catch(e => {
                console.error('Audio play failed:', e);
            });
            playBtn.classList.add('playing');
            playBtn.setAttribute('aria-label', 'Pause');
        }
        isPlaying = !isPlaying;
    }

    // Play button
    playBtn.addEventListener('click', togglePlay);

    // Hero play button
    if (heroPlayBtn) {
        heroPlayBtn.addEventListener('click', () => {
            if (!isPlaying) {
                togglePlay();
            }
            // Scroll to orchestra section
            const orchestraSection = document.getElementById('movement-3');
            if (orchestraSection) {
                orchestraSection.scrollIntoView({ behavior: 'smooth' });
            }
        });
    }

    // =========================================================================
    // PROGRESS BAR
    // =========================================================================
    
    if (progressBar) {
        progressBar.addEventListener('click', (e) => {
            const rect = progressBar.getBoundingClientRect();
            const pct = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width));
            audio.currentTime = pct * DURATION;
        });

        // Drag support
        let isDragging = false;

        progressBar.addEventListener('mousedown', (e) => {
            isDragging = true;
            const rect = progressBar.getBoundingClientRect();
            const pct = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width));
            audio.currentTime = pct * DURATION;
        });

        document.addEventListener('mousemove', (e) => {
            if (!isDragging) return;
            const rect = progressBar.getBoundingClientRect();
            const pct = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width));
            audio.currentTime = pct * DURATION;
        });

        document.addEventListener('mouseup', () => {
            isDragging = false;
        });
    }

    // =========================================================================
    // VOLUME CONTROL
    // =========================================================================
    
    if (volumeSlider) {
        volumeSlider.addEventListener('input', (e) => {
            const vol = e.target.value / 100;
            audio.volume = vol;
            updateVolumeIcon(vol, audio.muted);
        });
        audio.volume = volumeSlider.value / 100;
    }

    if (volumeIcon) {
        volumeIcon.addEventListener('click', () => {
            audio.muted = !audio.muted;
            updateVolumeIcon(audio.volume, audio.muted);
        });
    }

    function updateVolumeIcon(vol, muted) {
        if (!volumeIcon) return;
        if (muted || vol === 0) {
            volumeIcon.textContent = '🔇';
        } else if (vol < 0.5) {
            volumeIcon.textContent = '🔉';
        } else {
            volumeIcon.textContent = '🔊';
        }
    }

    // =========================================================================
    // AUDIO EVENTS
    // =========================================================================
    
    audio.addEventListener('timeupdate', () => {
        const currentTimeSec = audio.currentTime;
        const progress = (currentTimeSec / DURATION) * 100;
        
        if (progressFill) {
            progressFill.style.width = `${Math.min(progress, 100)}%`;
        }
        if (timeDisplay) {
            timeDisplay.textContent = `${formatTime(currentTimeSec)} / ${formatTime(DURATION)}`;
        }
    });

    audio.addEventListener('ended', () => {
        isPlaying = false;
        playBtn.classList.remove('playing');
        playBtn.setAttribute('aria-label', 'Play');
        if (progressFill) progressFill.style.width = '0%';
    });

    audio.addEventListener('loadedmetadata', () => {
        const dur = audio.duration || DURATION;
        if (timeDisplay) {
            timeDisplay.textContent = `0:00 / ${formatTime(dur)}`;
        }
        playBtn.style.opacity = '1';
        console.log('✓ Audio metadata loaded:', formatTime(dur));
    });

    audio.addEventListener('canplaythrough', () => {
        console.log('✓ Audio ready to play');
    });

    audio.addEventListener('error', (e) => {
        console.error('✗ Audio error:', e);
        if (timeDisplay) timeDisplay.textContent = 'Audio load error';
    });

    // =========================================================================
    // KEYBOARD CONTROLS
    // =========================================================================
    
    document.addEventListener('keydown', (e) => {
        // Don't intercept if user is typing in an input
        if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;
        
        if (e.code === 'Space') {
            e.preventDefault();
            togglePlay();
        }
        if (e.code === 'ArrowRight') {
            e.preventDefault();
            audio.currentTime = Math.min(audio.currentTime + 5, DURATION);
        }
        if (e.code === 'ArrowLeft') {
            e.preventDefault();
            audio.currentTime = Math.max(audio.currentTime - 5, 0);
        }
        if (e.code === 'ArrowUp') {
            e.preventDefault();
            const newVol = Math.min(1, audio.volume + 0.1);
            audio.volume = newVol;
            if (volumeSlider) volumeSlider.value = newVol * 100;
            updateVolumeIcon(newVol, audio.muted);
        }
        if (e.code === 'ArrowDown') {
            e.preventDefault();
            const newVol = Math.max(0, audio.volume - 0.1);
            audio.volume = newVol;
            if (volumeSlider) volumeSlider.value = newVol * 100;
            updateVolumeIcon(newVol, audio.muted);
        }
        if (e.code === 'KeyM') {
            audio.muted = !audio.muted;
            updateVolumeIcon(audio.volume, audio.muted);
        }
    });

    // =========================================================================
    // SCROLL HANDLING
    // =========================================================================
    
    function updateScroll() {
        const scrollTop = window.pageYOffset;
        const docHeight = document.documentElement.scrollHeight - window.innerHeight;
        const progress = docHeight > 0 ? scrollTop / docHeight : 0;
        
        if (progressBarTop) {
            progressBarTop.style.width = `${progress * 100}%`;
        }

        // Update current movement
        let newMovement = 0;
        movements.forEach((m, i) => {
            const rect = m.getBoundingClientRect();
            if (rect.top < window.innerHeight * 0.5) {
                newMovement = i;
            }
        });

        if (newMovement !== currentMovement) {
            currentMovement = newMovement;
            movementDots.forEach((d, i) => {
                d.classList.toggle('active', i === currentMovement);
            });
        }
    }

    // Movement dot navigation
    movementDots.forEach((dot, i) => {
        dot.addEventListener('click', () => {
            if (movements[i]) {
                movements[i].scrollIntoView({ behavior: 'smooth' });
            }
        });
    });

    window.addEventListener('scroll', updateScroll, { passive: true });

    // =========================================================================
    // INTERSECTION OBSERVER FOR ANIMATIONS
    // =========================================================================
    
    const observerOptions = { threshold: 0.1, rootMargin: '0px 0px -10% 0px' };
    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.classList.add('visible');
            }
        });
    }, observerOptions);

    document.querySelectorAll('.movement, .technique-card, .instrument-section, .transformation-card').forEach(el => {
        observer.observe(el);
    });

    // =========================================================================
    // TITLE ANIMATION
    // =========================================================================
    
    const titleWords = document.querySelectorAll('.title-word');
    titleWords.forEach((word, i) => {
        word.style.animation = `title-emerge 1s ease-out ${0.3 + i * 0.15}s forwards`;
    });

    // =========================================================================
    // EASTER EGG
    // =========================================================================
    
    if (mirrorSymbol && easterEggOverlay) {
        const closeBtn = easterEggOverlay.querySelector('.easter-egg-close');

        function showEasterEgg() {
            easterEggOverlay.classList.add('active');
            easterEggOverlay.setAttribute('aria-hidden', 'false');
        }

        function hideEasterEgg() {
            easterEggOverlay.classList.remove('active');
            easterEggOverlay.setAttribute('aria-hidden', 'true');
        }

        mirrorSymbol.addEventListener('click', showEasterEgg);
        mirrorSymbol.addEventListener('keydown', (e) => {
            if (e.code === 'Enter' || e.code === 'Space') {
                e.preventDefault();
                showEasterEgg();
            }
        });

        if (closeBtn) {
            closeBtn.addEventListener('click', hideEasterEgg);
        }

        easterEggOverlay.addEventListener('click', (e) => {
            if (e.target === easterEggOverlay) {
                hideEasterEgg();
            }
        });

        document.addEventListener('keydown', (e) => {
            if (e.code === 'Escape' && easterEggOverlay.classList.contains('active')) {
                hideEasterEgg();
            }
        });
    }

    // =========================================================================
    // INIT
    // =========================================================================
    
    playBtn.style.opacity = '0.5';
    audio.load();
    updateScroll();

    console.log('🎼 Master of Puppets — A Fantasia');
    console.log('   Controls: Space (play/pause), ← → (scrub), ↑ ↓ (volume), M (mute)');
    console.log('   h(x) ≥ 0');

})();
