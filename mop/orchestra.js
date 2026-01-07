/**
 * Master of Puppets — Orchestra Visualization
 * 
 * Millisecond-accurate note visualization synced to audio
 * 
 * h(x) ≥ 0
 */

(function() {
    'use strict';

    const audio = document.getElementById('audio');
    const sectionMeters = document.querySelectorAll('.section-meter');
    const instruments = document.querySelectorAll('.instrument');

    if (!audio) {
        console.warn('Orchestra: audio element not found');
        return;
    }

    // =========================================================================
    // STATE
    // =========================================================================
    
    const NOTES = window.ORCHESTRA_NOTES || {};
    const SECTIONS = window.INSTRUMENT_SECTIONS || {};
    
    const noteIndices = {};
    Object.keys(NOTES).forEach(id => noteIndices[id] = 0);

    const sectionActivity = { strings: 0, woodwinds: 0, brass: 0, percussion: 0 };
    const instrumentActivity = {};
    Object.keys(NOTES).forEach(id => instrumentActivity[id] = 0);

    let animationId = null;
    let lastTime = 0;

    // =========================================================================
    // SEEK - Reset indices when audio seeks
    // =========================================================================
    
    function seekTo(timeMs) {
        Object.keys(NOTES).forEach(id => {
            const notes = NOTES[id];
            if (!notes || notes.length === 0) {
                noteIndices[id] = 0;
                return;
            }
            
            // Binary search for efficiency
            let lo = 0, hi = notes.length - 1;
            while (lo < hi) {
                const mid = Math.floor((lo + hi) / 2);
                if (notes[mid][0] < timeMs) {
                    lo = mid + 1;
                } else {
                    hi = mid;
                }
            }
            // Back up a bit to catch notes that started before but are still playing
            noteIndices[id] = Math.max(0, lo - 10);
        });
        console.log('🎻 Seeked to', Math.floor(timeMs), 'ms');
    }

    audio.addEventListener('seeked', () => {
        seekTo(audio.currentTime * 1000);
        updateVisualizationFrame();
    });

    // =========================================================================
    // VISUALIZATION FRAME
    // =========================================================================
    
    function updateVisualizationFrame() {
        const currentTimeMs = audio.currentTime * 1000;

        // Reset activity
        Object.keys(sectionActivity).forEach(k => sectionActivity[k] = 0);
        Object.keys(instrumentActivity).forEach(k => instrumentActivity[k] = 0);

        // Check each instrument
        Object.keys(NOTES).forEach(instId => {
            const notes = NOTES[instId];
            if (!notes || notes.length === 0) return;

            let maxVel = 0;
            const idx = noteIndices[instId];
            
            // Search forward from current index
            for (let i = Math.max(0, idx - 5); i < notes.length && i < idx + 50; i++) {
                const [start, dur, vel] = notes[i];
                const end = start + dur;
                
                // Note is playing if current time is within its duration
                // Add tolerance for attack/release
                if (currentTimeMs >= start - 20 && currentTimeMs <= end + 100) {
                    maxVel = Math.max(maxVel, vel);
                }
                
                // Stop searching if we're past current time
                if (start > currentTimeMs + 500) break;
            }

            instrumentActivity[instId] = maxVel / 127;

            // Update section activity
            const section = SECTIONS[instId];
            if (section && maxVel > 0) {
                sectionActivity[section] = Math.max(sectionActivity[section], maxVel / 127);
            }
        });

        // Apply visual states
        instruments.forEach(inst => {
            const id = inst.dataset.id;
            const activity = instrumentActivity[id] || 0;
            
            if (activity > 0.1) {
                inst.classList.add('playing');
                // Set intensity via CSS variable
                inst.style.setProperty('--intensity', activity);
            } else {
                inst.classList.remove('playing');
                inst.style.removeProperty('--intensity');
            }
        });

        // Update section meters
        sectionMeters.forEach(meter => {
            const section = meter.dataset.section;
            const fill = meter.querySelector('.section-meter-fill');
            if (fill) {
                const activity = sectionActivity[section] || 0;
                fill.style.width = `${activity * 100}%`;
                fill.style.opacity = 0.5 + activity * 0.5;
            }
        });
    }

    // =========================================================================
    // ANIMATION LOOP
    // =========================================================================
    
    function updateVisualization() {
        const currentTimeMs = audio.currentTime * 1000;
        
        // Only update if time changed significantly
        if (Math.abs(currentTimeMs - lastTime) > 10) {
            updateVisualizationFrame();
            lastTime = currentTimeMs;
            
            // Advance note indices
            Object.keys(NOTES).forEach(instId => {
                const notes = NOTES[instId];
                if (!notes) return;
                
                // Move index forward past notes that have ended
                while (noteIndices[instId] < notes.length - 1) {
                    const [start, dur] = notes[noteIndices[instId]];
                    if (start + dur < currentTimeMs - 200) {
                        noteIndices[instId]++;
                    } else {
                        break;
                    }
                }
            });
        }

        if (!audio.paused) {
            animationId = requestAnimationFrame(updateVisualization);
        }
    }

    // =========================================================================
    // AUDIO EVENTS
    // =========================================================================
    
    audio.addEventListener('play', () => {
        console.log('🎻 Orchestra: playing');
        lastTime = audio.currentTime * 1000;
        seekTo(lastTime);
        updateVisualization();
    });

    audio.addEventListener('pause', () => {
        console.log('🎻 Orchestra: paused');
        cancelAnimationFrame(animationId);
    });

    audio.addEventListener('ended', () => {
        cancelAnimationFrame(animationId);
        // Reset everything
        Object.keys(noteIndices).forEach(id => noteIndices[id] = 0);
        instruments.forEach(inst => {
            inst.classList.remove('playing');
            inst.style.removeProperty('--intensity');
        });
        sectionMeters.forEach(meter => {
            const fill = meter.querySelector('.section-meter-fill');
            if (fill) {
                fill.style.width = '0%';
                fill.style.opacity = '0.5';
            }
        });
    });

    // Update on scrub while paused
    audio.addEventListener('timeupdate', () => {
        if (audio.paused) {
            updateVisualizationFrame();
        }
    });

    // =========================================================================
    // DEBUG: Log note activity
    // =========================================================================
    
    window.debugOrchestra = () => {
        const currentTimeMs = audio.currentTime * 1000;
        console.log('Time:', currentTimeMs.toFixed(0), 'ms');
        Object.keys(NOTES).forEach(id => {
            const notes = NOTES[id];
            if (!notes) return;
            const idx = noteIndices[id];
            const nearby = notes.slice(Math.max(0, idx - 2), idx + 5);
            const active = nearby.filter(([s, d]) => currentTimeMs >= s - 20 && currentTimeMs <= s + d + 100);
            if (active.length > 0) {
                console.log(`  ${id}: ${active.length} notes playing`);
            }
        });
    };

    // =========================================================================
    // INIT
    // =========================================================================
    
    const totalNotes = Object.values(NOTES).reduce((a, b) => a + b.length, 0);
    console.log('🎻 Orchestra Visualization');
    console.log('   Instruments:', Object.keys(NOTES).length);
    console.log('   Total notes:', totalNotes);
    console.log('   Debug: window.debugOrchestra()');

})();
