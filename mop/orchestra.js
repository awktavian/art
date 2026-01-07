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
    // PLAYBACK CONTROL (handled by app.js, we just listen to events)
    // =========================================================================

    audio.addEventListener('play', () => {
        console.log('▶ Audio playing');
        updateVisualization();
    });

    audio.addEventListener('pause', () => {
        console.log('⏸ Audio paused');
        cancelAnimationFrame(animationId);
    });

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
        // Binary search to find correct position for each instrument
        Object.keys(NOTES).forEach(id => {
            const notes = NOTES[id];
            if (!notes || notes.length === 0) {
                noteIndices[id] = 0;
                return;
            }
            
            // Binary search for first note that might be playing
            let lo = 0, hi = notes.length - 1;
            while (lo < hi) {
                const mid = Math.floor((lo + hi) / 2);
                // Find first note whose end time is >= current time
                if (notes[mid][0] + notes[mid][1] < timeMs - 200) {
                    lo = mid + 1;
                } else {
                    hi = mid;
                }
            }
            noteIndices[id] = lo;
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

        // Reset section activity
        Object.keys(sectionActivity).forEach(k => sectionActivity[k] = 0);

        // Check each instrument for note hits
        Object.keys(NOTES).forEach(instId => {
            const notes = NOTES[instId];
            const inst = document.querySelector(`[data-id="${instId}"]`);
            if (!inst || !notes || notes.length === 0) return;

            // Binary search to find starting point
            let lo = 0, hi = notes.length - 1;
            while (lo < hi) {
                const mid = Math.floor((lo + hi) / 2);
                if (notes[mid][0] + notes[mid][1] < currentTimeMs - 200) {
                    lo = mid + 1;
                } else {
                    hi = mid;
                }
            }
            noteIndices[instId] = lo;

            // Find notes that should be playing now
            let isCurrentlyPlaying = false;
            let maxVelocity = 0;
            
            // Search from binary search result forward
            for (let i = lo; i < notes.length && i < lo + 30; i++) {
                const [start, dur, vel] = notes[i];
                
                // If note starts after current time + tolerance, stop searching
                if (start > currentTimeMs + 100) break;
                
                // Note is currently playing (with tolerance for attack/release)
                const noteEnd = start + dur;
                if (currentTimeMs >= start - 30 && currentTimeMs <= noteEnd + 80) {
                    isCurrentlyPlaying = true;
                    maxVelocity = Math.max(maxVelocity, vel);
                }
            }

            // Update section activity based on max velocity
            if (isCurrentlyPlaying) {
                const section = SECTIONS[instId];
                if (section) {
                    sectionActivity[section] = Math.max(sectionActivity[section], maxVelocity / 127);
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
        cancelAnimationFrame(animationId);
        // Reset indices
        Object.keys(noteIndices).forEach(id => noteIndices[id] = 0);
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
