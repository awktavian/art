/**
 * Kagami Composer Module
 *
 * Shared logic for Quick Entry and Command Palette interfaces.
 * Handles mode selection, model selection, context chips, voice input, and status updates.
 *
 * Focus:
 */

// ============================================================================
// ERROR BOUNDARY
// ============================================================================

/**
 * Safe invoke wrapper with error handling
 * @param {Function} invokeFn - The invoke function
 * @param {string} command - Command name
 * @param {Object} args - Arguments
 * @returns {Promise<any>} Result or null on error
 */
export async function safeInvoke(invokeFn, command, args = {}) {
    if (!invokeFn) return null;
    try {
        return await invokeFn(command, args);
    } catch (error) {
        console.error(`[Kagami] invoke error (${command}):`, error);
        return null;
    }
}

// Global error handler for uncaught promise rejections
if (typeof window !== 'undefined') {
    window.addEventListener('unhandledrejection', (event) => {
        console.error('[Kagami] Unhandled promise rejection:', event.reason);
        event.preventDefault();
    });
}

// ============================================================================
// TAURI INTEGRATION
// ============================================================================

/**
 * Initialize Tauri API bindings
 * @returns {Promise<{invoke: Function, listen: Function, getCurrentWindow: Function}|null>}
 */
export async function initTauri() {
    const isTauri = typeof window !== 'undefined' && window.__TAURI_INTERNALS__ !== undefined;
    if (!isTauri) return null;

    try {
        const core = await import('@tauri-apps/api/core');
        const event = await import('@tauri-apps/api/event');
        const win = await import('@tauri-apps/api/window');
        return {
            invoke: core.invoke,
            listen: event.listen,
            getCurrentWindow: win.getCurrentWindow
        };
    } catch (error) {
        console.error('[Kagami] Failed to load Tauri APIs:', error);
        return null;
    }
}

// ============================================================================
// STATE MANAGEMENT
// ============================================================================

/**
 * Create initial composer state
 * @returns {Object} Initial state object
 */
export function createInitialState() {
    return {
        isConnected: false,
        safetyScore: null,
        context: [],
        mode: localStorage.getItem('kagami_mode') || 'ask',
        model: localStorage.getItem('kagami_model') || 'auto',
    };
}

// ============================================================================
// MODE SELECTOR
// ============================================================================

/**
 * Initialize mode selector buttons
 * @param {HTMLElement} container - Mode pills container
 * @param {Object} state - State object to update
 */
export function initModeSelector(container, state) {
    const pills = container.querySelectorAll('.mode-pill');

    // Set initial state
    pills.forEach(pill => {
        pill.classList.toggle('active', pill.dataset.mode === state.mode);
    });

    // Handle clicks
    pills.forEach(pill => {
        pill.addEventListener('click', () => {
            pills.forEach(p => p.classList.remove('active'));
            pill.classList.add('active');
            state.mode = pill.dataset.mode;
            localStorage.setItem('kagami_mode', state.mode);
        });
    });
}

/**
 * Initialize model selector dropdown
 * @param {HTMLSelectElement} dropdown - Model dropdown element
 * @param {Object} state - State object to update
 */
export function initModelSelector(dropdown, state) {
    dropdown.value = state.model;
    dropdown.addEventListener('change', () => {
        state.model = dropdown.value;
        localStorage.setItem('kagami_model', state.model);
    });
}

// ============================================================================
// CONTEXT CHIPS
// ============================================================================

/**
 * Render context chips
 * @param {HTMLElement} container - Context chips container
 * @param {Object} state - State object with context array
 */
export function renderContextChips(container, state) {
    if (state.context.length === 0) {
        container.classList.remove('visible');
        return;
    }

    container.classList.add('visible');
    container.innerHTML = state.context.map((ctx, i) => `
        <div class="context-chip" data-index="${i}">
            <span class="context-chip-icon">${ctx.icon || '@'}</span>
            <span>${ctx.label}</span>
            <span class="context-chip-remove" data-index="${i}">x</span>
        </div>
    `).join('');

    // Handle remove clicks
    container.querySelectorAll('.context-chip-remove').forEach(btn => {
        btn.addEventListener('click', (e) => {
            e.stopPropagation();
            const index = parseInt(btn.dataset.index, 10);
            state.context.splice(index, 1);
            renderContextChips(container, state);
        });
    });
}

// ============================================================================
// VOICE INPUT
// ============================================================================

/**
 * Voice input controller
 */
export class VoiceController {
    constructor(inputElement, statusElement) {
        this.input = inputElement;
        this.statusElement = statusElement;
        this.recognition = null;
        this.isRecording = false;
        this.isWarmedUp = false;

        this._initSpeechRecognition();
    }

    /**
     * Warmup the voice pipeline (call on window load)
     * This pre-initializes the speech recognition for faster response
     */
    async warmup() {
        if (this.isWarmedUp || !this.recognition) {
            return;
        }

        try {
            // Request microphone permission early
            if (navigator.mediaDevices && navigator.mediaDevices.getUserMedia) {
                const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
                // Stop immediately - we just want the permission
                stream.getTracks().forEach(track => track.stop());
            }

            // Mark as warmed up
            this.isWarmedUp = true;
            console.log('[Kagami Voice] Pipeline warmed up - ready for instant activation');

            // Dispatch event for UI to show "Voice ready" indicator
            if (this.input) {
                this.input.dispatchEvent(new CustomEvent('voice-ready'));
            }

            return true;
        } catch (error) {
            console.warn('[Kagami Voice] Warmup failed (mic permission may be denied):', error);
            return false;
        }
    }

    /**
     * Check if voice is warmed up and ready
     */
    get isReady() {
        return this.isWarmedUp && this.recognition !== null;
    }

    _initSpeechRecognition() {
        if (!('webkitSpeechRecognition' in window || 'SpeechRecognition' in window)) {
            return;
        }

        const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
        this.recognition = new SpeechRecognition();
        this.recognition.continuous = false;
        this.recognition.interimResults = true;
        this.recognition.lang = 'en-US';

        this.recognition.onstart = () => {
            this.isRecording = true;
            if (this.statusElement) {
                this.statusElement.textContent = 'Listening...';
            }
            this._dispatchEvent('recording-start');
        };

        this.recognition.onresult = (event) => {
            let finalTranscript = '';
            for (let i = event.resultIndex; i < event.results.length; i++) {
                if (event.results[i].isFinal) {
                    finalTranscript += event.results[i][0].transcript;
                } else if (this.input) {
                    this.input.value = event.results[i][0].transcript;
                }
            }

            if (finalTranscript && this.input) {
                this.input.value = finalTranscript;
                this.input.dispatchEvent(new Event('input', { bubbles: true }));
            }
        };

        this.recognition.onerror = (event) => {
            if (this.statusElement) {
                this.statusElement.textContent = event.error === 'no-speech'
                    ? 'No speech detected'
                    : `Error: ${event.error}`;
                setTimeout(() => {
                    if (this.statusElement) this.statusElement.textContent = 'Ready';
                }, 2000);
            }
            this.stop();
        };

        this.recognition.onend = () => this.stop();
    }

    start() {
        if (this.recognition) {
            try {
                this.recognition.start();
            } catch (e) {
                // Already started
            }
        }
    }

    stop() {
        this.isRecording = false;
        this._dispatchEvent('recording-stop');
        if (this.recognition) {
            try {
                this.recognition.stop();
            } catch (e) {
                // Already stopped
            }
        }
    }

    _dispatchEvent(type) {
        if (this.input) {
            this.input.dispatchEvent(new CustomEvent(`voice-${type}`));
        }
    }

    /**
     * Attach voice button event handlers
     * @param {HTMLElement} button - Voice button element
     */
    attachButton(button) {
        button.addEventListener('mousedown', () => this.start());
        button.addEventListener('mouseup', () => this.stop());
        button.addEventListener('mouseleave', () => {
            if (this.isRecording) this.stop();
        });
        button.addEventListener('touchstart', (e) => {
            e.preventDefault();
            this.start();
        });
        button.addEventListener('touchend', (e) => {
            e.preventDefault();
            this.stop();
        });

        // Update button styling based on recording state
        if (this.input) {
            this.input.addEventListener('voice-recording-start', () => {
                button.classList.add('recording');
            });
            this.input.addEventListener('voice-recording-stop', () => {
                button.classList.remove('recording');
            });
        }
    }
}

// ============================================================================
// STATUS UPDATES
// ============================================================================

/**
 * Update connection and safety status indicators
 * @param {Object} elements - Status elements (statusDot, safetyScore)
 * @param {Object} state - Current state
 */
export function updateStatus(elements, state) {
    const { statusDot, safetyScore, safetyDot } = elements;

    if (statusDot) {
        statusDot.classList.toggle('connected', state.isConnected);
        statusDot.classList.toggle('disconnected', !state.isConnected);
    }

    // Safety score display for detailed view
    if (safetyScore && state.safetyScore !== null) {
        safetyScore.textContent = `Safety: ${(state.safetyScore * 100).toFixed(0)}%`;
    }

    // Semantic safety indicator (dot)
    if (safetyDot && state.safetyScore !== null) {
        safetyDot.classList.remove('good', 'caution', 'alert');
        if (state.safetyScore >= 0.5) {
            safetyDot.classList.add('good');
        } else if (state.safetyScore >= 0) {
            safetyDot.classList.add('caution');
        } else {
            safetyDot.classList.add('alert');
        }
    }
}

// ============================================================================
// WINDOW MANAGEMENT
// ============================================================================

/**
 * Hide the quick entry window
 * @param {Object} tauri - Tauri API bindings
 */
export async function hideWindow(tauri) {
    if (!tauri) return;

    const result = await safeInvoke(tauri.invoke, 'hide_quick_entry');
    if (result === null) {
        try {
            const win = tauri.getCurrentWindow();
            await win.hide();
        } catch (error) {
            console.error('[Kagami] Failed to hide window:', error);
        }
    }
}

/**
 * Setup keyboard shortcut handlers
 * @param {Object} tauri - Tauri API bindings
 */
export function setupKeyboardShortcuts(tauri) {
    document.addEventListener('keydown', async (e) => {
        if (e.key === 'Escape') {
            e.preventDefault();
            await hideWindow(tauri);
        }
    });
}

/**
 * Setup visibility change handler to reset input on show
 * @param {HTMLInputElement} input - Input element
 * @param {HTMLElement} statusElement - Status text element
 */
export function setupVisibilityHandler(input, statusElement) {
    document.addEventListener('visibilitychange', () => {
        if (!document.hidden) {
            if (input) {
                input.value = '';
                input.focus();
            }
            if (statusElement) {
                statusElement.textContent = 'Ready';
            }
        }
    });
}

// ============================================================================
// REALTIME STATE LISTENER
// ============================================================================

/**
 * Setup real-time state listener
 * @param {Object} tauri - Tauri API bindings
 * @param {Object} state - State object to update
 * @param {Function} onUpdate - Callback when state updates
 */
export async function setupStateListener(tauri, state, onUpdate) {
    if (!tauri) return;

    try {
        await tauri.listen('kagami-state', (event) => {
            state.isConnected = event.payload.connected;
            state.safetyScore = event.payload.safety_score;
            onUpdate();
        });
    } catch (error) {
        console.error('[Kagami] Failed to set up state listener:', error);
    }

    // Initial fetch
    const ctxState = await safeInvoke(tauri.invoke, 'get_context_state');
    if (ctxState) {
        state.isConnected = ctxState.is_connected;
        state.safetyScore = ctxState.safety_score;
        onUpdate();
    }

    // Check API status
    const apiStatus = await safeInvoke(tauri.invoke, 'get_api_status');
    if (apiStatus) {
        state.isConnected = apiStatus.running;
        onUpdate();
    }
}

// ============================================================================
// CONSOLE BANNER
// ============================================================================

/**
 * Print console banner
 */
export function printBanner() {
    console.log(`%cKagami Composer
%c--------------------
%cType / for commands
%cType @ for context
%c
%c`,
        'color: #10B981; font-size: 14px; font-weight: bold;',
        'color: #10B981;',
        'color: #888;',
        'color: #888;',
        '',
        'color: #00BFA5;'
    );
}
