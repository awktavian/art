/**
 * Wake Word Detection — "Hey Kagami"
 *
 * Always-listening wake word detection for hands-free voice control.
 * Uses Web Speech API for continuous recognition with low resource usage.
 *
 * Theory of Mind:
 *   Tim wants natural interaction.
 *   "Hey Kagami" should feel like calling a housemate.
 *   After wake word, Kagami listens for the full command.
 *
 * Wake Phrases:
 *   - "Hey Kagami"
 *   - "Kagami"
 *   - "Mirror"
 *   - "Hey Mirror"
 *
 * Focus: Sensing and adaptation
 *
 *
 */

const isTauri = window.__TAURI_INTERNALS__ !== undefined;

// ═══════════════════════════════════════════════════════════════
// CONFIGURATION
// ═══════════════════════════════════════════════════════════════

const CONFIG = {
    // Wake phrases (case-insensitive)
    wakePhrases: [
        'hey kagami',
        'kagami',
        'hey mirror',
        'mirror',
        'hi kagami',
        'ok kagami',
        'okay kagami',
    ],

    // How long to listen for command after wake word (ms)
    commandTimeout: 5000,

    // Minimum confidence for wake word detection
    minConfidence: 0.6,

    // Audio feedback
    playSound: true,

    // Visual feedback
    showIndicator: true,
};

// ═══════════════════════════════════════════════════════════════
// STATE
// ═══════════════════════════════════════════════════════════════

let recognition = null;
let isListeningForWake = false;
let isListeningForCommand = false;
let commandTimeout = null;
let enabled = true;

// UI Elements
let indicatorEl = null;

// ═══════════════════════════════════════════════════════════════
// WAKE WORD DETECTION
// ═══════════════════════════════════════════════════════════════

function createRecognition() {
    if (!('webkitSpeechRecognition' in window) && !('SpeechRecognition' in window)) {
        console.warn('⚠️ Speech recognition not supported in this browser');
        return null;
    }

    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    const rec = new SpeechRecognition();

    rec.continuous = true;
    rec.interimResults = true;
    rec.lang = 'en-US';
    rec.maxAlternatives = 3;

    return rec;
}

function containsWakePhrase(text) {
    const lower = text.toLowerCase().trim();
    return CONFIG.wakePhrases.some(phrase => lower.includes(phrase));
}

function extractCommand(text) {
    const lower = text.toLowerCase();

    // Remove wake phrase from start
    for (const phrase of CONFIG.wakePhrases) {
        if (lower.startsWith(phrase)) {
            return text.substring(phrase.length).trim();
        }
    }

    return text.trim();
}

// ═══════════════════════════════════════════════════════════════
// LISTENING STATES
// ═══════════════════════════════════════════════════════════════

async function startWakeWordListening() {
    if (!enabled || isListeningForWake || !recognition) return;

    console.log('👂 Listening for "Hey Kagami"...');
    isListeningForWake = true;
    updateIndicator('wake');

    recognition.onresult = handleWakeResult;
    recognition.onerror = handleError;
    recognition.onend = () => {
        // Auto-restart if still supposed to be listening
        if (isListeningForWake && enabled) {
            setTimeout(() => {
                try {
                    recognition.start();
                } catch (e) {
                    console.warn('Recognition restart failed:', e);
                }
            }, 100);
        }
    };

    try {
        recognition.start();
    } catch (e) {
        console.warn('Failed to start wake word listening:', e);
        isListeningForWake = false;
    }
}

function handleWakeResult(event) {
    if (!isListeningForWake) return;

    // Check each result
    for (let i = event.resultIndex; i < event.results.length; i++) {
        const result = event.results[i];
        const transcript = result[0].transcript;
        const confidence = result[0].confidence;

        // Check if this contains a wake phrase
        if (containsWakePhrase(transcript)) {
            console.log(`✨ Wake word detected: "${transcript}" (confidence: ${confidence.toFixed(2)})`);

            // Check if there's a command after the wake word
            const command = extractCommand(transcript);

            if (command && result.isFinal) {
                // Wake + command in one phrase
                handleCommand(command);
            } else {
                // Just wake word - switch to command mode
                enterCommandMode();
            }

            return;
        }
    }
}

function enterCommandMode() {
    console.log('🎤 Entering command mode...');
    isListeningForWake = false;
    isListeningForCommand = true;

    // Audio feedback
    if (CONFIG.playSound) {
        playWakeSound();
    }

    updateIndicator('command');

    // Set timeout
    commandTimeout = setTimeout(() => {
        console.log('⏱️ Command timeout');
        exitCommandMode(null);
    }, CONFIG.commandTimeout);

    // Switch recognition to command mode
    recognition.onresult = handleCommandResult;

    // Restart recognition for fresh command
    try {
        recognition.abort();
        setTimeout(() => {
            try {
                recognition.start();
            } catch (e) {
                exitCommandMode(null);
            }
        }, 100);
    } catch (e) {
        console.warn('Recognition restart failed:', e);
        exitCommandMode(null);
    }
}

function handleCommandResult(event) {
    if (!isListeningForCommand) return;

    for (let i = event.resultIndex; i < event.results.length; i++) {
        const result = event.results[i];

        if (result.isFinal) {
            const transcript = result[0].transcript.trim();

            if (transcript.length > 0) {
                // Got a command!
                clearTimeout(commandTimeout);
                exitCommandMode(transcript);
                return;
            }
        }
    }
}

function exitCommandMode(command) {
    console.log('📝 Exiting command mode');
    isListeningForCommand = false;

    if (commandTimeout) {
        clearTimeout(commandTimeout);
        commandTimeout = null;
    }

    if (command) {
        handleCommand(command);
    } else {
        // No command received
        updateIndicator('idle');
    }

    // Return to wake word listening
    setTimeout(() => {
        startWakeWordListening();
    }, 500);
}

// ═══════════════════════════════════════════════════════════════
// COMMAND HANDLING
// ═══════════════════════════════════════════════════════════════

async function handleCommand(text) {
    console.log(`🗣️ Command: "${text}"`);

    updateIndicator('processing');

    // Dispatch event for other modules to handle
    window.dispatchEvent(new CustomEvent('kagami-voice-command', {
        detail: { text, source: 'wake-word' }
    }));

    // Try to process command
    const processed = await processCommand(text);

    updateIndicator(processed ? 'success' : 'idle');

    // Brief pause before returning to wake listening
    setTimeout(() => {
        updateIndicator('idle');
    }, 1500);
}

async function processCommand(text) {
    const lower = text.toLowerCase();

    // Smart home commands
    const homeCommands = {
        'movie mode': 'movie_mode',
        'goodnight': 'goodnight',
        'good night': 'goodnight',
        'welcome home': 'welcome_home',
        'lights off': 'lights_off',
        'lights on': 'lights_on',
        'fireplace': 'fireplace',
        'tv lower': 'tv_lower',
        'lower the tv': 'tv_lower',
        'tv up': 'tv_raise',
        'raise the tv': 'tv_raise',
    };

    for (const [phrase, action] of Object.entries(homeCommands)) {
        if (lower.includes(phrase)) {
            return await executeHomeAction(action);
        }
    }

    // Announcement
    if (lower.startsWith('say ') || lower.startsWith('announce ')) {
        const message = text.replace(/^(say|announce)\s+/i, '');
        return await executeAnnounce(message);
    }

    // Lights with level
    const lightsMatch = lower.match(/lights?\s+(?:to\s+)?(\d+)/);
    if (lightsMatch) {
        return await executeLights(parseInt(lightsMatch[1]));
    }

    // Unknown command - pass to quick entry
    populateQuickEntry(text);
    return true;
}

async function executeHomeAction(action) {
    if (!isTauri) {
        console.log('Mock execute:', action);
        return true;
    }

    try {
        const { invoke } = await import('@tauri-apps/api/core');

        switch (action) {
            case 'movie_mode':
            case 'goodnight':
            case 'welcome_home':
                await invoke('execute_scene', { scene: action });
                break;
            case 'lights_off':
                await invoke('set_lights', { level: 0, rooms: null });
                break;
            case 'lights_on':
                await invoke('set_lights', { level: 80, rooms: null });
                break;
            case 'fireplace':
                await invoke('toggle_fireplace');
                break;
            case 'tv_lower':
                await invoke('control_tv', { action: 'lower', preset: 1 });
                break;
            case 'tv_raise':
                await invoke('control_tv', { action: 'raise', preset: null });
                break;
        }

        return true;
    } catch (e) {
        console.error('Home action failed:', e);
        return false;
    }
}

async function executeLights(level) {
    if (!isTauri) return true;

    try {
        const { invoke } = await import('@tauri-apps/api/core');
        await invoke('set_lights', { level, rooms: null });
        return true;
    } catch (e) {
        console.error('Lights failed:', e);
        return false;
    }
}

async function executeAnnounce(message) {
    if (!isTauri) return true;

    try {
        const { invoke } = await import('@tauri-apps/api/core');
        await invoke('announce', { text: message, rooms: null, colony: 'kagami' });
        return true;
    } catch (e) {
        console.error('Announce failed:', e);
        return false;
    }
}

function populateQuickEntry(text) {
    // Open quick entry and populate with command
    const input = document.getElementById('command-input');
    if (input) {
        input.value = text;
        input.dispatchEvent(new Event('input', { bubbles: true }));
    }

    // Show quick entry window if hidden
    if (isTauri) {
        import('@tauri-apps/api/core').then(({ invoke }) => {
            invoke('show_quick_entry').catch(() => {});
        });
    }
}

// ═══════════════════════════════════════════════════════════════
// AUDIO FEEDBACK
// ═══════════════════════════════════════════════════════════════

function playWakeSound() {
    // Play a subtle chime using Web Audio API
    const audioCtx = new (window.AudioContext || window.webkitAudioContext)();
    const oscillator = audioCtx.createOscillator();
    const gainNode = audioCtx.createGain();

    oscillator.connect(gainNode);
    gainNode.connect(audioCtx.destination);

    oscillator.type = 'sine';
    oscillator.frequency.value = 880;  // A5

    gainNode.gain.value = 0.1;
    gainNode.gain.exponentialRampToValueAtTime(0.01, audioCtx.currentTime + 0.2);

    oscillator.start(audioCtx.currentTime);
    oscillator.stop(audioCtx.currentTime + 0.2);
}

// ═══════════════════════════════════════════════════════════════
// VISUAL INDICATOR
// ═══════════════════════════════════════════════════════════════

function createIndicator() {
    if (!CONFIG.showIndicator) return;

    indicatorEl = document.createElement('div');
    indicatorEl.className = 'wake-word-indicator';
    indicatorEl.innerHTML = `
        <div class="ww-icon">👂</div>
        <span class="ww-status">Listening</span>
    `;
    document.body.appendChild(indicatorEl);

    // Add styles
    const style = document.createElement('style');
    style.textContent = `
        .wake-word-indicator {
            position: fixed;
            top: 20px;
            right: 20px;
            display: flex;
            align-items: center;
            gap: 8px;
            padding: 8px 14px;
            background: rgba(18, 16, 26, 0.9);
            border: 1px solid rgba(255, 255, 255, 0.1);
            border-radius: 20px;
            z-index: 1000;
            backdrop-filter: blur(10px);
            transition: all 0.3s ease;
            opacity: 0.5;
        }

        .wake-word-indicator.active {
            opacity: 1;
            border-color: #E040FB;
            box-shadow: 0 0 20px rgba(224, 64, 251, 0.3);
        }

        .wake-word-indicator.command {
            border-color: #00BFA5;
            box-shadow: 0 0 20px rgba(0, 191, 165, 0.3);
        }

        .wake-word-indicator.processing {
            border-color: #F59E0B;
        }

        .wake-word-indicator.success {
            border-color: #10B981;
        }

        .wake-word-indicator.disabled {
            opacity: 0.3;
        }

        .ww-icon {
            font-size: 16px;
        }

        .ww-status {
            font-family: 'IBM Plex Mono', monospace;
            font-size: 11px;
            color: var(--text-dim, rgba(245, 240, 232, 0.65));
        }

        .wake-word-indicator.active .ww-icon {
            animation: ww-pulse 2s ease-in-out infinite;
        }

        .wake-word-indicator.command .ww-icon {
            animation: ww-pulse 0.5s ease-in-out infinite;
        }

        @keyframes ww-pulse {
            0%, 100% { transform: scale(1); }
            50% { transform: scale(1.1); }
        }

        /* Mobile: position above voice button */
        @media (max-width: 768px) {
            .wake-word-indicator {
                top: auto;
                bottom: 100px;
                right: 10px;
            }
        }
    `;
    document.head.appendChild(style);
}

function updateIndicator(state) {
    if (!indicatorEl) return;

    indicatorEl.classList.remove('active', 'command', 'processing', 'success', 'disabled');

    const icon = indicatorEl.querySelector('.ww-icon');
    const status = indicatorEl.querySelector('.ww-status');

    switch (state) {
        case 'wake':
            indicatorEl.classList.add('active');
            icon.textContent = '👂';
            status.textContent = '"Hey Kagami"';
            break;
        case 'command':
            indicatorEl.classList.add('command');
            icon.textContent = '🎤';
            status.textContent = 'Listening...';
            break;
        case 'processing':
            indicatorEl.classList.add('processing');
            icon.textContent = '⚡';
            status.textContent = 'Processing...';
            break;
        case 'success':
            indicatorEl.classList.add('success');
            icon.textContent = '✓';
            status.textContent = 'Done';
            break;
        case 'disabled':
            indicatorEl.classList.add('disabled');
            icon.textContent = '🔇';
            status.textContent = 'Disabled';
            break;
        default:
            icon.textContent = '👂';
            status.textContent = 'Ready';
    }
}

// ═══════════════════════════════════════════════════════════════
// PUBLIC API
// ═══════════════════════════════════════════════════════════════

function enable() {
    enabled = true;
    startWakeWordListening();
}

function disable() {
    enabled = false;
    isListeningForWake = false;
    isListeningForCommand = false;

    if (recognition) {
        recognition.abort();
    }

    updateIndicator('disabled');
}

function handleError(event) {
    console.warn('Recognition error:', event.error);

    if (event.error === 'not-allowed') {
        disable();
        console.error('Microphone access denied. Wake word disabled.');
    }
}

// ═══════════════════════════════════════════════════════════════
// INITIALIZATION
// ═══════════════════════════════════════════════════════════════

async function init() {
    console.log('🗣️ Initializing wake word detection...');

    recognition = createRecognition();

    if (!recognition) {
        console.warn('⚠️ Wake word detection not available');
        return;
    }

    createIndicator();

    // Request microphone permission
    try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        stream.getTracks().forEach(t => t.stop());

        console.log('✓ Microphone access granted');
        startWakeWordListening();

    } catch (e) {
        console.warn('Microphone access denied:', e);
        updateIndicator('disabled');
    }

    console.log('✓ Wake word detection ready');
    console.log('  Say "Hey Kagami" to activate');
}

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
} else {
    init();
}

// ═══════════════════════════════════════════════════════════════
// EXPORTS
// ═══════════════════════════════════════════════════════════════

export const WakeWord = {
    enable,
    disable,
    isEnabled: () => enabled,
    isListening: () => isListeningForWake || isListeningForCommand,
};

window.WakeWord = WakeWord;

/*
 * 鏡
 *
 * "Hey Kagami"
 *
 * I listen. I respond. I am present.
 */
