/**
 * Kagami Mode Selector
 *
 * Three operational modes for the composer:
 * - Ask: Q&A, information retrieval (Grove colony)
 * - Plan: Strategic thinking, architecture (Beacon colony)
 * - Agent: Autonomous execution (Forge colony)
 *
 * Usage:
 *   const modeSelector = new ModeSelector(containerElement);
 *   modeSelector.onModeChange((mode) => console.log('Mode changed:', mode));
 */

// Mode definitions
export const MODES = {
    ask: {
        id: 'ask',
        label: 'Ask',
        description: 'Get answers',
        colony: 'grove',
        color: 'var(--grove)'
    },
    plan: {
        id: 'plan',
        label: 'Plan',
        description: 'Think it through',
        colony: 'beacon',
        color: 'var(--beacon)'
    },
    agent: {
        id: 'agent',
        label: 'Agent',
        description: 'Make it happen',
        colony: 'forge',
        color: 'var(--forge)'
    }
};

// Mode order for display
export const MODE_ORDER = ['ask', 'plan', 'agent'];

// Storage key
const STORAGE_KEY = 'kagami_mode';

/**
 * ModeSelector class
 */
export class ModeSelector {
    /**
     * @param {HTMLElement} container - Container element to render into
     * @param {Object} options - Configuration options
     * @param {string} options.defaultMode - Default mode ('ask', 'plan', or 'agent')
     * @param {boolean} options.compact - Use compact styling
     * @param {boolean} options.persist - Persist selection to localStorage
     */
    constructor(container, options = {}) {
        this.container = container;
        this.options = {
            defaultMode: 'ask',
            compact: false,
            persist: true,
            ...options
        };

        this.currentMode = this._loadMode();
        this.callbacks = [];

        this._render();
    }

    /**
     * Load persisted mode from localStorage
     * @returns {string}
     */
    _loadMode() {
        if (this.options.persist) {
            const saved = localStorage.getItem(STORAGE_KEY);
            if (saved && MODES[saved]) {
                return saved;
            }
        }
        return this.options.defaultMode;
    }

    /**
     * Save mode to localStorage
     * @param {string} mode
     */
    _saveMode(mode) {
        if (this.options.persist) {
            localStorage.setItem(STORAGE_KEY, mode);
        }
    }

    /**
     * Render the mode selector
     */
    _render() {
        const compactClass = this.options.compact ? ' mode-selector--compact' : '';

        this.container.innerHTML = `
            <div class="mode-selector${compactClass}" role="radiogroup" aria-label="Operation mode">
                ${MODE_ORDER.map(modeId => {
                    const mode = MODES[modeId];
                    const isActive = modeId === this.currentMode;
                    return `
                        <button
                            class="mode-pill${isActive ? ' active' : ''}"
                            data-mode="${modeId}"
                            role="radio"
                            aria-checked="${isActive}"
                            title="${mode.description}"
                        >
                            ${mode.label}
                        </button>
                    `;
                }).join('')}
            </div>
        `;

        // Attach event listeners
        const pills = this.container.querySelectorAll('.mode-pill');
        pills.forEach(pill => {
            pill.addEventListener('click', (e) => {
                const mode = e.currentTarget.dataset.mode;
                this.setMode(mode);
            });
        });
    }

    /**
     * Set the current mode
     * @param {string} mode - Mode identifier
     */
    setMode(mode) {
        if (!MODES[mode] || mode === this.currentMode) {
            return;
        }

        // Update state
        this.currentMode = mode;
        this._saveMode(mode);

        // Update UI
        const pills = this.container.querySelectorAll('.mode-pill');
        pills.forEach(pill => {
            const isActive = pill.dataset.mode === mode;
            pill.classList.toggle('active', isActive);
            pill.setAttribute('aria-checked', isActive.toString());
        });

        // Notify callbacks
        this.callbacks.forEach(cb => cb(mode, MODES[mode]));
    }

    /**
     * Get the current mode
     * @returns {string}
     */
    getMode() {
        return this.currentMode;
    }

    /**
     * Get current mode config
     * @returns {Object}
     */
    getModeConfig() {
        return MODES[this.currentMode];
    }

    /**
     * Register a callback for mode changes
     * @param {Function} callback - Function called with (mode, modeConfig)
     */
    onModeChange(callback) {
        this.callbacks.push(callback);
    }

    /**
     * Remove a callback
     * @param {Function} callback
     */
    offModeChange(callback) {
        this.callbacks = this.callbacks.filter(cb => cb !== callback);
    }

    /**
     * Destroy the mode selector
     */
    destroy() {
        this.callbacks = [];
        this.container.innerHTML = '';
    }
}

/**
 * Create a standalone mode selector
 * @param {HTMLElement} container
 * @param {Object} options
 * @returns {ModeSelector}
 */
export function createModeSelector(container, options = {}) {
    return new ModeSelector(container, options);
}

/**
 * Get the current persisted mode (without creating a selector)
 * @returns {string}
 */
export function getCurrentMode() {
    const saved = localStorage.getItem(STORAGE_KEY);
    return (saved && MODES[saved]) ? saved : 'ask';
}

/**
 * Set the mode programmatically (updates storage)
 * @param {string} mode
 */
export function setPersistedMode(mode) {
    if (MODES[mode]) {
        localStorage.setItem(STORAGE_KEY, mode);
    }
}

// Export default
export default {
    ModeSelector,
    createModeSelector,
    getCurrentMode,
    setPersistedMode,
    MODES,
    MODE_ORDER
};
