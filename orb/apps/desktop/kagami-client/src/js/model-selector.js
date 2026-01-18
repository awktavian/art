/**
 * Model Selector — User-Facing LLM Model Selection
 *
 * Focus:
 *
 * A compact, expandable selector for choosing which LLM model processes
 * commands. Integrates with quick entry and voice input interfaces.
 *
 * Created: December 30, 2025
 */

// =============================================================================
// MODEL DEFINITIONS (Mirror of kagami/core/services/llm/user_models.py)
// =============================================================================

export const USER_MODELS = [
    {
        key: 'auto',
        displayName: 'Auto',
        icon: '🤖',
        description: 'Let Kagami choose the best model',
        colonyColor: 'crystal',
    },
    {
        key: 'claude',
        displayName: 'Claude',
        icon: '◆',
        description: 'Balanced intelligence and safety',
        colonyColor: 'nexus',
    },
    {
        key: 'gpt4o',
        displayName: 'GPT-4o',
        icon: '◎',
        description: 'Strong reasoning and analysis',
        colonyColor: 'beacon',
    },
    {
        key: 'deepseek',
        displayName: 'DeepSeek',
        icon: '⟠',
        description: 'Best for code and value',
        colonyColor: 'forge',
    },
    {
        key: 'gemini',
        displayName: 'Gemini',
        icon: '◇',
        description: 'Long context and reasoning',
        colonyColor: 'grove',
    },
    {
        key: 'local',
        displayName: 'Local',
        icon: '⊙',
        description: 'Offline, private processing',
        colonyColor: 'flow',
    },
];

// Brand color mapping to CSS variables
const COLONY_COLORS = {
    crystal: 'var(--color-crystal, #5BC0BE)',
    nexus: 'var(--color-nexus, #9B72CF)',
    beacon: 'var(--color-beacon, #FFB347)',
    forge: 'var(--color-forge, #FF6B6B)',
    grove: 'var(--color-grove, #7ED37E)',
    flow: 'var(--color-flow, #6BB5FF)',
    spark: 'var(--color-spark, #FFD93D)',
};

// =============================================================================
// MODEL SELECTOR CLASS
// =============================================================================

export class ModelSelector {
    /**
     * Create a model selector.
     *
     * @param {HTMLElement} container - Container element for the selector
     * @param {Object} options - Configuration options
     * @param {string} options.defaultModel - Default model key (default: 'auto')
     * @param {boolean} options.compact - Use compact mode (default: true)
     * @param {function} options.onChange - Callback when model changes
     */
    constructor(container, options = {}) {
        this.container = container;
        this.options = {
            defaultModel: 'auto',
            compact: true,
            onChange: null,
            ...options,
        };

        this.selectedModel = this._loadSelection() || this.options.defaultModel;
        this.isExpanded = false;

        this._render();
        this._attachEvents();
    }

    /**
     * Get currently selected model key.
     * @returns {string} Model key
     */
    getSelectedModel() {
        return this.selectedModel;
    }

    /**
     * Set selected model.
     * @param {string} key - Model key to select
     */
    setSelectedModel(key) {
        const model = USER_MODELS.find(m => m.key === key);
        if (model) {
            this.selectedModel = key;
            this._saveSelection(key);
            this._updateDisplay();
            if (this.options.onChange) {
                this.options.onChange(key, model);
            }
        }
    }

    /**
     * Expand the selector dropdown.
     */
    expand() {
        this.isExpanded = true;
        this._updateDisplay();
    }

    /**
     * Collapse the selector dropdown.
     */
    collapse() {
        this.isExpanded = false;
        this._updateDisplay();
    }

    /**
     * Toggle expanded state.
     */
    toggle() {
        this.isExpanded ? this.collapse() : this.expand();
    }

    // =========================================================================
    // PRIVATE METHODS
    // =========================================================================

    _render() {
        const model = USER_MODELS.find(m => m.key === this.selectedModel) || USER_MODELS[0];
        const color = COLONY_COLORS[model.colonyColor] || COLONY_COLORS.crystal;

        this.container.innerHTML = `
            <div class="model-selector ${this.options.compact ? 'compact' : ''}" data-expanded="${this.isExpanded}">
                <button class="model-selector-trigger" type="button" title="Select AI model">
                    <span class="model-icon">${model.icon}</span>
                    <span class="model-name">${model.displayName}</span>
                    <span class="model-chevron">▾</span>
                </button>
                <div class="model-selector-dropdown">
                    ${USER_MODELS.map(m => `
                        <button
                            class="model-option ${m.key === this.selectedModel ? 'selected' : ''}"
                            data-model="${m.key}"
                            data-color="${COLONY_COLORS[m.colonyColor]}"
                            type="button"
                        >
                            <span class="model-option-icon">${m.icon}</span>
                            <span class="model-option-content">
                                <span class="model-option-name">${m.displayName}</span>
                                <span class="model-option-desc">${m.description}</span>
                            </span>
                            ${m.key === this.selectedModel ? '<span class="model-check">✓</span>' : ''}
                        </button>
                    `).join('')}
                </div>
            </div>
        `;

        // Apply theme color
        const trigger = this.container.querySelector('.model-selector-trigger');
        if (trigger) {
            trigger.style.setProperty('--model-color', color);
        }
    }

    _attachEvents() {
        // Toggle dropdown
        const trigger = this.container.querySelector('.model-selector-trigger');
        if (trigger) {
            trigger.addEventListener('click', (e) => {
                e.stopPropagation();
                this.toggle();
            });
        }

        // Model selection
        const options = this.container.querySelectorAll('.model-option');
        options.forEach(opt => {
            opt.addEventListener('click', (e) => {
                e.stopPropagation();
                const key = opt.dataset.model;
                this.setSelectedModel(key);
                this.collapse();
            });
        });

        // Click outside to close
        document.addEventListener('click', (e) => {
            if (!this.container.contains(e.target)) {
                this.collapse();
            }
        });

        // Keyboard navigation
        this.container.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') {
                this.collapse();
            } else if (e.key === 'ArrowDown' && this.isExpanded) {
                e.preventDefault();
                this._focusNext();
            } else if (e.key === 'ArrowUp' && this.isExpanded) {
                e.preventDefault();
                this._focusPrev();
            }
        });
    }

    _updateDisplay() {
        const selector = this.container.querySelector('.model-selector');
        const model = USER_MODELS.find(m => m.key === this.selectedModel) || USER_MODELS[0];
        const color = COLONY_COLORS[model.colonyColor] || COLONY_COLORS.crystal;

        if (selector) {
            selector.dataset.expanded = this.isExpanded;
        }

        const icon = this.container.querySelector('.model-icon');
        const name = this.container.querySelector('.model-name');
        const trigger = this.container.querySelector('.model-selector-trigger');

        if (icon) icon.textContent = model.icon;
        if (name) name.textContent = model.displayName;
        if (trigger) trigger.style.setProperty('--model-color', color);

        // Update selection state
        const options = this.container.querySelectorAll('.model-option');
        options.forEach(opt => {
            const isSelected = opt.dataset.model === this.selectedModel;
            opt.classList.toggle('selected', isSelected);
            const check = opt.querySelector('.model-check');
            if (isSelected && !check) {
                opt.insertAdjacentHTML('beforeend', '<span class="model-check">✓</span>');
            } else if (!isSelected && check) {
                check.remove();
            }
        });
    }

    _focusNext() {
        const options = Array.from(this.container.querySelectorAll('.model-option'));
        const current = document.activeElement;
        const idx = options.indexOf(current);
        const next = options[(idx + 1) % options.length];
        if (next) next.focus();
    }

    _focusPrev() {
        const options = Array.from(this.container.querySelectorAll('.model-option'));
        const current = document.activeElement;
        const idx = options.indexOf(current);
        const prev = options[(idx - 1 + options.length) % options.length];
        if (prev) prev.focus();
    }

    _loadSelection() {
        try {
            return localStorage.getItem('kagami-model-selection');
        } catch {
            return null;
        }
    }

    _saveSelection(key) {
        try {
            localStorage.setItem('kagami-model-selection', key);
        } catch {
            // Ignore storage errors
        }
    }
}

// =============================================================================
// CSS STYLES (inject into document)
// =============================================================================

const MODEL_SELECTOR_STYLES = `
.model-selector {
    position: relative;
    display: inline-flex;
    font-family: var(--font-sans, system-ui, sans-serif);
}

.model-selector-trigger {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 6px 12px;
    border: 1px solid var(--model-color, var(--color-crystal));
    border-radius: 20px;
    background: rgba(255, 255, 255, 0.05);
    color: var(--model-color, var(--color-crystal));
    font-size: 12px;
    font-weight: 500;
    cursor: pointer;
    transition: all 0.15s ease;
}

.model-selector-trigger:hover {
    background: rgba(255, 255, 255, 0.1);
    border-color: var(--model-color, var(--color-crystal));
}

.model-selector.compact .model-selector-trigger {
    padding: 4px 10px;
    font-size: 11px;
}

.model-icon {
    font-size: 14px;
}

.model-chevron {
    font-size: 10px;
    opacity: 0.6;
    transition: transform 0.15s ease;
}

.model-selector[data-expanded="true"] .model-chevron {
    transform: rotate(180deg);
}

.model-selector-dropdown {
    position: absolute;
    top: calc(100% + 4px);
    left: 0;
    min-width: 220px;
    background: var(--color-void-light, #1a1a2e);
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 12px;
    padding: 4px;
    box-shadow: 0 8px 32px rgba(0, 0, 0, 0.4);
    opacity: 0;
    visibility: hidden;
    transform: translateY(-8px);
    transition: all 0.15s ease;
    z-index: 1000;
}

.model-selector[data-expanded="true"] .model-selector-dropdown {
    opacity: 1;
    visibility: visible;
    transform: translateY(0);
}

.model-option {
    display: flex;
    align-items: center;
    gap: 10px;
    width: 100%;
    padding: 10px 12px;
    border: none;
    border-radius: 8px;
    background: transparent;
    color: rgba(255, 255, 255, 0.8);
    font-size: 13px;
    text-align: left;
    cursor: pointer;
    transition: background 0.1s ease;
}

.model-option:hover {
    background: rgba(255, 255, 255, 0.1);
}

.model-option.selected {
    background: rgba(91, 192, 190, 0.15);
    color: var(--color-crystal, #5BC0BE);
}

.model-option-icon {
    font-size: 18px;
    width: 24px;
    text-align: center;
}

.model-option-content {
    flex: 1;
    display: flex;
    flex-direction: column;
    gap: 2px;
}

.model-option-name {
    font-weight: 500;
}

.model-option-desc {
    font-size: 11px;
    opacity: 0.6;
}

.model-check {
    font-size: 14px;
    color: var(--color-crystal, #5BC0BE);
}
`;

// Inject styles on module load
if (typeof document !== 'undefined') {
    const styleEl = document.createElement('style');
    styleEl.id = 'model-selector-styles';
    styleEl.textContent = MODEL_SELECTOR_STYLES;
    if (!document.getElementById('model-selector-styles')) {
        document.head.appendChild(styleEl);
    }
}

// =============================================================================
// EXPORTS
// =============================================================================

export default ModelSelector;

/*
 * 鏡
 * The model is the lens through which I see.
 * Each brings its own clarity.
 */
