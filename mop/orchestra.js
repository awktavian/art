/**
 * Master of Puppets — Orchestra Visualization
 * 
 * ONLY handles visual animation - player controls are in app.js
 * 
 * h(x) ≥ 0
 */

(function() {
    'use strict';

    const audio = document.getElementById('audio');
    const sectionMeters = document.querySelectorAll('.section-meter');

    if (!audio) {
        console.warn('Orchestra visualization: audio element not found');
        return;
    }

    // =========================================================================
    // STATE
    // =========================================================================
    
    const NOTES = window.ORCHESTRA_NOTES || {};
    const SECTIONS = window.INSTRUMENT_SECTIONS || {};
    
    // Track note indices for efficient lookup
    const noteIndices = {};
    Object.keys(NOTES).forEach(id => noteIndices[id] = 0);

    // Section activity tracking
    const sectionActivity = { strings: 0, woodwinds: 0, brass: 0, percussion: 0 };

    let animationId = null;

    // =========================================================================
    // SEEKING - Reset indices when audio seeks
    // =========================================================================
    
    function seekTo(timeMs) {
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
    }

    audio.addEventListener('seeked', () => {
        seekTo(audio.currentTime * 1000);
        updateVisualizationFrame();
    });

    // =========================================================================
    // VISUALIZATION
    // =========================================================================
    
    function updateVisualizationFrame() {
        const currentTimeMs = audio.currentTime * 1000;

        // Reset section activity
        Object.keys(sectionActivity).forEach(k => sectionActivity[k] = 0);

        // Check each instrument
        Object.keys(NOTES).forEach(instId => {
            const notes = NOTES[instId];
            const inst = document.querySelector(`[data-id="${instId}"]`);
            if (!inst || !notes) return;

            let isCurrentlyPlaying = false;
            
            // Search around current index
            const searchStart = Math.max(0, noteIndices[instId] - 5);
            const searchEnd = Math.min(notes.length, noteIndices[instId] + 20);
            
            for (let i = searchStart; i < searchEnd; i++) {
                const [start, dur, vel] = notes[i];
                
                if (currentTimeMs >= start - 10 && currentTimeMs <= start + dur + 50) {
                    isCurrentlyPlaying = true;
                    const section = SECTIONS[instId];
                    if (section) {
                        sectionActivity[section] = Math.max(sectionActivity[section], vel / 127);
                    }
                }
            }

            // Apply playing state
            if (isCurrentlyPlaying) {
                inst.classList.add('playing');
            } else {
                inst.classList.remove('playing');
            }
        });

        // Update section meters
        sectionMeters.forEach(meter => {
            const section = meter.dataset.section;
            const fill = meter.querySelector('.section-meter-fill');
            if (fill) {
                fill.style.width = `${(sectionActivity[section] || 0) * 100}%`;
            }
        });
    }

    function updateVisualization() {
        updateVisualizationFrame();
        
        // Advance note indices
        const currentTimeMs = audio.currentTime * 1000;
        Object.keys(NOTES).forEach(instId => {
            const notes = NOTES[instId];
            if (!notes) return;
            while (noteIndices[instId] < notes.length - 1 && 
                   notes[noteIndices[instId]][0] + notes[noteIndices[instId]][1] < currentTimeMs - 100) {
                noteIndices[instId]++;
            }
        });

        if (!audio.paused) {
            animationId = requestAnimationFrame(updateVisualization);
        }
    }

    // =========================================================================
    // AUDIO EVENTS - Start/stop animation
    // =========================================================================
    
    audio.addEventListener('play', () => {
        console.log('🎻 Visualization: playing');
        updateVisualization();
    });

    audio.addEventListener('pause', () => {
        console.log('🎻 Visualization: paused');
        cancelAnimationFrame(animationId);
    });

    audio.addEventListener('ended', () => {
        cancelAnimationFrame(animationId);
        Object.keys(noteIndices).forEach(id => noteIndices[id] = 0);
        // Clear all playing states
        document.querySelectorAll('.instrument.playing').forEach(el => {
            el.classList.remove('playing');
        });
        sectionMeters.forEach(meter => {
            const fill = meter.querySelector('.section-meter-fill');
            if (fill) fill.style.width = '0%';
        });
    });

    // Update visualization when scrubbing while paused
    audio.addEventListener('timeupdate', () => {
        if (audio.paused) {
            updateVisualizationFrame();
        }
    });

    // =========================================================================
    // INIT
    // =========================================================================
    
    console.log('🎻 Orchestra Visualization initialized');
    console.log('   Instruments:', Object.keys(NOTES).length);
    console.log('   Notes:', Object.values(NOTES).reduce((a, b) => a + b.length, 0));

})();
