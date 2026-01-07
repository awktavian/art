/**
 * Master of Puppets — Orchestra Visualization
 * 
 * Millisecond-accurate note visualization synced to audio playback
 * Supports scrubbing, seeking, and paused state updates
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
    const progressBar = document.getElementById('progress-bar');
    const progressFill = document.getElementById('progress-fill');
    const timeDisplay = document.getElementById('time-display');
    const volumeSlider = document.getElementById('volume-slider');
    const volumeIcon = document.getElementById('volume-icon');
    const instruments = document.querySelectorAll('.instrument');
    const sectionMeters = document.querySelectorAll('.section-meter');

    // Fallback if elements don't exist
    if (!audio || !playBtn) {
        console.warn('Orchestra visualization: Required elements not found');
        return;
    }

    // =========================================================================
    // STATE
    // =========================================================================
    
    const DURATION = 402; // 6:42 in seconds
    const NOTES = window.ORCHESTRA_NOTES || {};
    const SECTIONS = window.INSTRUMENT_SECTIONS || {};
    
    // Track note indices for each instrument (for efficient lookup)
    const noteIndices = {};
    Object.keys(NOTES).forEach(id => noteIndices[id] = 0);

    // Section activity tracking
    const sectionActivity = { strings: 0, woodwinds: 0, brass: 0, percussion: 0 };

    let isPlaying = false;
    let animationId = null;

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
            playBtn.innerHTML = '▶';
            playBtn.setAttribute('aria-label', 'Play');
            cancelAnimationFrame(animationId);
        } else {
            audio.play().catch(e => {
                console.log('Audio play failed:', e);
                // Show error state
                playBtn.innerHTML = '⚠';
            });
            playBtn.classList.add('playing');
            playBtn.innerHTML = '⏸';
            playBtn.setAttribute('aria-label', 'Pause');
            updateVisualization();
        }
        isPlaying = !isPlaying;
    }

    playBtn.addEventListener('click', togglePlay);

    // Volume control
    if (volumeSlider) {
        volumeSlider.addEventListener('input', (e) => {
            const vol = e.target.value / 100;
            audio.volume = vol;
            if (volumeIcon) {
                volumeIcon.textContent = vol === 0 ? '🔇' : vol < 0.5 ? '🔉' : '🔊';
            }
        });
        audio.volume = volumeSlider.value / 100;
    }

    if (volumeIcon) {
        volumeIcon.addEventListener('click', () => {
            audio.muted = !audio.muted;
            volumeIcon.textContent = audio.muted ? '🔇' : '🔊';
        });
    }

    // =========================================================================
    // SEEKING
    // =========================================================================
    
    function seekTo(timeMs) {
        // Recalculate all note indices for the new position
        Object.keys(NOTES).forEach(id => {
            const notes = NOTES[id];
            if (!notes) return;
            let idx = 0;
            for (let i = 0; i < notes.length; i++) {
                if (notes[i][0] <= timeMs) {
                    idx = i;
                } else {
                    break;
                }
            }
            noteIndices[id] = idx;
        });
        
        // Update visualization immediately
        updateVisualizationFrame();
    }

    // Progress bar click
    if (progressBar) {
        progressBar.addEventListener('click', (e) => {
            const rect = progressBar.getBoundingClientRect();
            const pct = (e.clientX - rect.left) / rect.width;
            const newTime = pct * DURATION;
            audio.currentTime = newTime;
            seekTo(newTime * 1000);
        });
    }

    // Handle seeking from any source
    audio.addEventListener('seeked', () => {
        seekTo(audio.currentTime * 1000);
    });

    // =========================================================================
    // VISUALIZATION
    // =========================================================================
    
    function updateVisualizationFrame() {
        const currentTimeMs = audio.currentTime * 1000;
        const currentTimeSec = audio.currentTime;

        // Update progress
        const progress = (currentTimeSec / DURATION) * 100;
        if (progressFill) {
            progressFill.style.width = `${Math.min(progress, 100)}%`;
        }
        if (timeDisplay) {
            timeDisplay.textContent = `${formatTime(currentTimeSec)} / ${formatTime(DURATION)}`;
        }

        // Reset section activity
        Object.keys(sectionActivity).forEach(k => sectionActivity[k] = 0);

        // Check each instrument for note hits
        Object.keys(NOTES).forEach(instId => {
            const notes = NOTES[instId];
            const inst = document.querySelector(`[data-id="${instId}"]`);
            if (!inst || !notes) return;

            // Find notes that should be playing now
            let isCurrentlyPlaying = false;
            
            // Search around current index for active notes
            const searchStart = Math.max(0, noteIndices[instId] - 5);
            const searchEnd = Math.min(notes.length, noteIndices[instId] + 20);
            
            for (let i = searchStart; i < searchEnd; i++) {
                const [start, dur, vel] = notes[i];
                
                // Note is currently playing (with small tolerance)
                if (currentTimeMs >= start - 10 && currentTimeMs <= start + dur + 50) {
                    isCurrentlyPlaying = true;
                    // Update section activity based on velocity
                    const section = SECTIONS[instId];
                    if (section) {
                        sectionActivity[section] = Math.max(sectionActivity[section], vel / 127);
                    }
                }
            }

            // Apply playing state
            if (isCurrentlyPlaying) {
                if (!inst.classList.contains('playing')) {
                    inst.classList.add('playing');
                }
            } else {
                inst.classList.remove('playing');
            }
        });

        // Update section meters
        sectionMeters.forEach(meter => {
            const section = meter.dataset.section;
            const fill = meter.querySelector('.section-meter-fill');
            if (fill) {
                const activity = sectionActivity[section] || 0;
                fill.style.width = `${activity * 100}%`;
            }
        });
    }

    function updateVisualization() {
        updateVisualizationFrame();
        
        // Advance note indices during playback
        const currentTimeMs = audio.currentTime * 1000;
        Object.keys(NOTES).forEach(instId => {
            const notes = NOTES[instId];
            if (!notes) return;
            while (noteIndices[instId] < notes.length - 1 && 
                   notes[noteIndices[instId]][0] + notes[noteIndices[instId]][1] < currentTimeMs - 100) {
                noteIndices[instId]++;
            }
        });

        // Continue animation if playing
        if (!audio.paused) {
            animationId = requestAnimationFrame(updateVisualization);
        }
    }
    
    // Update on timeupdate (for scrubbing while paused)
    audio.addEventListener('timeupdate', () => {
        if (audio.paused) {
            updateVisualizationFrame();
        }
    });

    // =========================================================================
    // AUDIO EVENTS
    // =========================================================================
    
    audio.addEventListener('ended', () => {
        isPlaying = false;
        playBtn.classList.remove('playing');
        playBtn.innerHTML = '▶';
        playBtn.setAttribute('aria-label', 'Play');
        cancelAnimationFrame(animationId);
        // Reset indices
        Object.keys(noteIndices).forEach(id => noteIndices[id] = 0);
        if (progressFill) progressFill.style.width = '0%';
    });

    audio.addEventListener('loadedmetadata', () => {
        const dur = audio.duration || DURATION;
        if (timeDisplay) {
            timeDisplay.textContent = `0:00 / ${formatTime(dur)}`;
        }
        console.log('✓ Audio loaded:', formatTime(dur));
    });

    audio.addEventListener('canplaythrough', () => {
        console.log('✓ Audio ready to play');
        playBtn.style.opacity = '1';
    });

    audio.addEventListener('error', (e) => {
        console.error('✗ Audio error:', e);
        if (timeDisplay) timeDisplay.textContent = 'Audio load error';
        playBtn.innerHTML = '⚠';
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
    });

    // =========================================================================
    // INITIALIZATION
    // =========================================================================
    
    playBtn.style.opacity = '0.5';
    if (timeDisplay) {
        timeDisplay.textContent = `0:00 / ${formatTime(DURATION)}`;
    }
    
    // Preload audio
    audio.load();
    
    console.log('🎻 Master of Puppets — Orchestra Visualization');
    console.log('   Instruments:', Object.keys(NOTES).length);
    console.log('   Total notes:', Object.values(NOTES).reduce((a, b) => a + b.length, 0));
    console.log('   Duration:', formatTime(DURATION));
    console.log('   Controls: Space (play/pause), ← → (scrub ±5s)');
    console.log('   h(x) ≥ 0');

})();
