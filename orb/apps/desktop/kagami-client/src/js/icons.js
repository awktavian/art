/**
 * Kagami Icon System
 *
 * Typography-first brand with Fano plane secondary mark.
 * Custom SVG icons for all UI elements.
 *
 * Usage:
 *   import { KagamiIcon, getIconSvg, ICON_CATEGORIES } from './icons.js';
 *
 *   // As inline SVG
 *   element.innerHTML = getIconSvg('action-lights', { size: 24, color: 'var(--spark)' });
 *
 *   // Using sprite reference
 *   element.innerHTML = `<svg class="kagami-icon"><use href="assets/icons/sprite.svg#action-lights"></use></svg>`;
 */

// Icon categories for organization
export const ICON_CATEGORIES = {
    brand: ['fano-plane'],
    colonies: ['colony-spark', 'colony-forge', 'colony-flow', 'colony-nexus', 'colony-beacon', 'colony-grove', 'colony-crystal'],
    actions: ['action-lights', 'action-shades', 'action-tv', 'action-fireplace', 'action-lock', 'action-movie-mode', 'action-goodnight', 'action-welcome-home', 'action-away'],
    status: ['status-safe', 'status-caution', 'status-violation', 'status-connected', 'status-offline', 'status-listening'],
    nav: ['nav-home', 'nav-rooms', 'nav-scenes', 'nav-settings', 'nav-voice']
};

// Brand to icon mapping
export const COLONY_ICONS = {
    spark: 'colony-spark',
    forge: 'colony-forge',
    flow: 'colony-flow',
    nexus: 'colony-nexus',
    beacon: 'colony-beacon',
    grove: 'colony-grove',
    crystal: 'colony-crystal'
};

// Action icon states
export const ACTION_ICON_STATES = {
    lights: { on: 'action-lights-on', off: 'action-lights' },
    shades: { open: 'action-shades', closed: 'action-shades-closed' },
    tv: { on: 'action-tv-on', off: 'action-tv' },
    fireplace: { on: 'action-fireplace-on', off: 'action-fireplace' },
    lock: { locked: 'action-lock', unlocked: 'action-lock-unlocked' }
};

// Scene icons mapping (replacing emoji)
export const SCENE_ICONS = {
    'Movie Mode': 'action-movie-mode',
    'Goodnight': 'action-goodnight',
    'Welcome Home': 'action-welcome-home',
    'Away': 'action-away',
    // Legacy mappings
    'movie_mode': 'action-movie-mode',
    'goodnight': 'action-goodnight',
    'welcome_home': 'action-welcome-home',
    'away': 'action-away'
};

// Default icon options
const DEFAULT_OPTIONS = {
    size: 24,
    color: 'currentColor',
    strokeWidth: 2,
    className: 'kagami-icon'
};

/**
 * Get an icon as an inline SVG string using sprite reference
 * @param {string} iconId - Icon identifier (e.g., 'action-lights', 'colony-spark')
 * @param {Object} options - Configuration options
 * @param {number} options.size - Icon size in pixels (default: 24)
 * @param {string} options.color - Icon color (default: 'currentColor')
 * @param {string} options.className - CSS class name
 * @returns {string} SVG HTML string
 */
export function getIconSvg(iconId, options = {}) {
    const opts = { ...DEFAULT_OPTIONS, ...options };
    const spritePath = options.spritePath || 'assets/icons/sprite.svg';

    return `<svg
        class="${opts.className}"
        width="${opts.size}"
        height="${opts.size}"
        style="color: ${opts.color}; --icon-size: ${opts.size}px;"
        aria-hidden="true"
        focusable="false"
    >
        <use href="${spritePath}#${iconId}"></use>
    </svg>`;
}

/**
 * Create an icon element (DOM node)
 * @param {string} iconId - Icon identifier
 * @param {Object} options - Configuration options
 * @returns {SVGElement} SVG DOM element
 */
export function createIconElement(iconId, options = {}) {
    const opts = { ...DEFAULT_OPTIONS, ...options };
    const spritePath = options.spritePath || 'assets/icons/sprite.svg';

    const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    svg.setAttribute('class', opts.className);
    svg.setAttribute('width', opts.size);
    svg.setAttribute('height', opts.size);
    svg.setAttribute('aria-hidden', 'true');
    svg.setAttribute('focusable', 'false');
    svg.style.color = opts.color;
    svg.style.setProperty('--icon-size', `${opts.size}px`);

    const use = document.createElementNS('http://www.w3.org/2000/svg', 'use');
    use.setAttributeNS('http://www.w3.org/1999/xlink', 'href', `${spritePath}#${iconId}`);

    svg.appendChild(use);
    return svg;
}

/**
 * KagamiIcon class for more complex icon management
 */
export class KagamiIcon {
    constructor(iconId, options = {}) {
        this.iconId = iconId;
        this.options = { ...DEFAULT_OPTIONS, ...options };
        this.element = null;
    }

    /**
     * Render the icon and return the element
     * @returns {SVGElement}
     */
    render() {
        this.element = createIconElement(this.iconId, this.options);
        return this.element;
    }

    /**
     * Update the icon (useful for state changes)
     * @param {string} newIconId - New icon identifier
     */
    setIcon(newIconId) {
        this.iconId = newIconId;
        if (this.element) {
            const use = this.element.querySelector('use');
            const spritePath = this.options.spritePath || 'assets/icons/sprite.svg';
            use.setAttributeNS('http://www.w3.org/1999/xlink', 'href', `${spritePath}#${newIconId}`);
        }
    }

    /**
     * Set icon color
     * @param {string} color - CSS color value
     */
    setColor(color) {
        this.options.color = color;
        if (this.element) {
            this.element.style.color = color;
        }
    }

    /**
     * Set icon size
     * @param {number} size - Size in pixels
     */
    setSize(size) {
        this.options.size = size;
        if (this.element) {
            this.element.setAttribute('width', size);
            this.element.setAttribute('height', size);
            this.element.style.setProperty('--icon-size', `${size}px`);
        }
    }

    /**
     * Get HTML string representation
     * @returns {string}
     */
    toString() {
        return getIconSvg(this.iconId, this.options);
    }
}

/**
 * Get colony icon by colony name
 * @param {string} colonyName - Colony name (spark, forge, flow, etc.)
 * @param {Object} options - Icon options
 * @returns {string} SVG HTML string
 */
export function getColonyIcon(colonyName, options = {}) {
    const iconId = COLONY_ICONS[colonyName.toLowerCase()];
    if (!iconId) {
        console.warn(`Unknown colony: ${colonyName}`);
        return '';
    }

    // Apply colony color if not specified
    if (!options.color) {
        options.color = `var(--${colonyName.toLowerCase()})`;
    }

    return getIconSvg(iconId, options);
}

/**
 * Get action icon with state
 * @param {string} action - Action name (lights, shades, tv, fireplace, lock)
 * @param {string} state - State (on/off, open/closed, locked/unlocked)
 * @param {Object} options - Icon options
 * @returns {string} SVG HTML string
 */
export function getActionIcon(action, state, options = {}) {
    const states = ACTION_ICON_STATES[action.toLowerCase()];
    if (!states) {
        console.warn(`Unknown action: ${action}`);
        return getIconSvg(`action-${action.toLowerCase()}`, options);
    }

    const iconId = states[state.toLowerCase()] || Object.values(states)[0];
    return getIconSvg(iconId, options);
}

/**
 * Get scene icon
 * @param {string} sceneName - Scene name
 * @param {Object} options - Icon options
 * @returns {string} SVG HTML string
 */
export function getSceneIcon(sceneName, options = {}) {
    const iconId = SCENE_ICONS[sceneName] || SCENE_ICONS[sceneName.toLowerCase().replace(/ /g, '_')];
    if (!iconId) {
        console.warn(`Unknown scene: ${sceneName}, using default`);
        return getIconSvg('nav-scenes', options);
    }
    return getIconSvg(iconId, options);
}

/**
 * Preload the sprite sheet for faster icon rendering
 * @param {string} spritePath - Path to sprite SVG file
 * @returns {Promise<void>}
 */
export async function preloadIconSprite(spritePath = 'assets/icons/sprite.svg') {
    return new Promise((resolve, reject) => {
        const link = document.createElement('link');
        link.rel = 'preload';
        link.as = 'image';
        link.type = 'image/svg+xml';
        link.href = spritePath;
        link.onload = resolve;
        link.onerror = reject;
        document.head.appendChild(link);
    });
}

// CSS styles for icons (inject once)
const iconStyles = `
.kagami-icon {
    display: inline-block;
    vertical-align: middle;
    fill: none;
    stroke: currentColor;
    stroke-width: var(--icon-stroke-default, 2px);
    stroke-linecap: round;
    stroke-linejoin: round;
    width: var(--icon-size, 24px);
    height: var(--icon-size, 24px);
    flex-shrink: 0;
}

.kagami-icon--xs { --icon-size: 12px; }
.kagami-icon--sm { --icon-size: 16px; }
.kagami-icon--md { --icon-size: 24px; }
.kagami-icon--lg { --icon-size: 32px; }
.kagami-icon--xl { --icon-size: 48px; }

/* Animation classes */
.kagami-icon--pulse {
    animation: kagami-icon-pulse 2s ease-in-out infinite;
}

.kagami-icon--shake {
    animation: kagami-icon-shake 0.5s ease-in-out;
}

.kagami-icon--spin {
    animation: kagami-icon-spin 1s linear infinite;
}

@keyframes kagami-icon-pulse {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.5; }
}

@keyframes kagami-icon-shake {
    0%, 100% { transform: translateX(0); }
    25% { transform: translateX(-2px); }
    75% { transform: translateX(2px); }
}

@keyframes kagami-icon-spin {
    from { transform: rotate(0deg); }
    to { transform: rotate(360deg); }
}
`;

// Inject styles once
let stylesInjected = false;
export function injectIconStyles() {
    if (stylesInjected) return;

    const style = document.createElement('style');
    style.textContent = iconStyles;
    document.head.appendChild(style);
    stylesInjected = true;
}

// Auto-inject styles when module loads (in browser context)
if (typeof document !== 'undefined') {
    injectIconStyles();
}

// Export default object for convenience
export default {
    getIconSvg,
    createIconElement,
    KagamiIcon,
    getColonyIcon,
    getActionIcon,
    getSceneIcon,
    preloadIconSprite,
    injectIconStyles,
    ICON_CATEGORIES,
    COLONY_ICONS,
    ACTION_ICON_STATES,
    SCENE_ICONS
};
