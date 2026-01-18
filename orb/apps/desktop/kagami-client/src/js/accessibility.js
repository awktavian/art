/**
 * ACCESSIBILITY HELPERS
 * WCAG 2.1 AA Compliant
 *
 * Focus:
 *
 * This module provides:
 * 1. Screen reader announcements (live regions)
 * 2. Focus management utilities
 * 3. Keyboard navigation helpers
 * 4. Roving tabindex for component groups
 * 5. Focus trap for modals
 * 6. Reduced motion detection
 *
 *
 */

// ================================================================
// 1. LIVE REGION ANNOUNCEMENTS
// For screen reader users to hear state changes
// ================================================================

/**
 * Create the live region element if it doesn't exist
 * @returns {HTMLElement} The live region element
 */
function getLiveRegion() {
    let region = document.getElementById('aria-live-announcer');
    if (!region) {
        region = document.createElement('div');
        region.id = 'aria-live-announcer';
        region.className = 'aria-live-region';
        region.setAttribute('aria-live', 'polite');
        region.setAttribute('aria-atomic', 'true');
        region.setAttribute('role', 'status');
        document.body.appendChild(region);
    }
    return region;
}

/**
 * Create an assertive live region for urgent announcements
 * @returns {HTMLElement} The assertive live region element
 */
function getAssertiveLiveRegion() {
    let region = document.getElementById('aria-live-assertive');
    if (!region) {
        region = document.createElement('div');
        region.id = 'aria-live-assertive';
        region.className = 'aria-live-region';
        region.setAttribute('aria-live', 'assertive');
        region.setAttribute('aria-atomic', 'true');
        region.setAttribute('role', 'alert');
        document.body.appendChild(region);
    }
    return region;
}

/**
 * Announce a message to screen readers
 * @param {string} message - The message to announce
 * @param {Object} options - Options for the announcement
 * @param {boolean} options.assertive - Use assertive (interrupting) announcement
 * @param {number} options.clearDelay - Delay before clearing (ms), default 1000
 */
function announce(message, options = {}) {
    const { assertive = false, clearDelay = 1000 } = options;
    const region = assertive ? getAssertiveLiveRegion() : getLiveRegion();

    // Clear first to ensure re-announcement of same message
    region.textContent = '';

    // Use setTimeout to ensure the clear registers before new content
    setTimeout(() => {
        region.textContent = message;

        // Clear after delay to prevent stale content
        setTimeout(() => {
            region.textContent = '';
        }, clearDelay);
    }, 50);
}

/**
 * Announce an error message (uses assertive)
 * @param {string} message - The error message
 */
function announceError(message) {
    announce(message, { assertive: true });
}

/**
 * Announce a status change
 * @param {string} status - The new status
 */
function announceStatus(status) {
    announce(status);
}

/**
 * Announce loading state
 * @param {boolean} isLoading - Whether loading is in progress
 * @param {string} context - What is loading (e.g., "rooms", "status")
 */
function announceLoading(isLoading, context = '') {
    if (isLoading) {
        announce(`Loading ${context}...`);
    } else {
        announce(`${context} loaded.`);
    }
}

// ================================================================
// 2. FOCUS MANAGEMENT
// Utilities for managing focus programmatically
// ================================================================

/**
 * Move focus to an element
 * @param {HTMLElement|string} element - Element or selector to focus
 * @param {Object} options - Focus options
 * @param {boolean} options.preventScroll - Prevent scroll on focus
 */
function focusElement(element, options = {}) {
    const { preventScroll = false } = options;
    const el = typeof element === 'string' ? document.querySelector(element) : element;

    if (el) {
        // Ensure element is focusable
        if (!el.hasAttribute('tabindex') && !isFocusable(el)) {
            el.setAttribute('tabindex', '-1');
        }
        el.focus({ preventScroll });
    }
}

/**
 * Check if an element is focusable
 * @param {HTMLElement} element - Element to check
 * @returns {boolean} Whether the element is focusable
 */
function isFocusable(element) {
    if (element.disabled || element.hidden || element.getAttribute('aria-hidden') === 'true') {
        return false;
    }

    const focusableTags = ['A', 'BUTTON', 'INPUT', 'TEXTAREA', 'SELECT', 'DETAILS'];
    if (focusableTags.includes(element.tagName)) {
        return true;
    }

    const tabindex = element.getAttribute('tabindex');
    return tabindex !== null && tabindex !== '-1';
}

/**
 * Get all focusable elements within a container
 * @param {HTMLElement} container - Container element
 * @returns {HTMLElement[]} Array of focusable elements
 */
function getFocusableElements(container) {
    const selector = [
        'a[href]',
        'button:not([disabled])',
        'input:not([disabled])',
        'select:not([disabled])',
        'textarea:not([disabled])',
        '[tabindex]:not([tabindex="-1"])',
        '[contenteditable="true"]',
    ].join(', ');

    return Array.from(container.querySelectorAll(selector)).filter(
        el => !el.closest('[hidden]') && !el.closest('[aria-hidden="true"]')
    );
}

/**
 * Save current focus to restore later
 * @returns {HTMLElement|null} The currently focused element
 */
function saveFocus() {
    return document.activeElement;
}

/**
 * Restore focus to a previously saved element
 * @param {HTMLElement} element - Element to restore focus to
 */
function restoreFocus(element) {
    if (element && document.body.contains(element)) {
        element.focus();
    }
}

// ================================================================
// 3. KEYBOARD NAVIGATION HELPERS
// Detect keyboard navigation mode and handle key events
// ================================================================

let isKeyboardNav = false;

/**
 * Initialize keyboard navigation detection
 * Adds 'keyboard-nav' class to body when using keyboard
 */
function initKeyboardNavigation() {
    // Detect keyboard navigation
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Tab') {
            isKeyboardNav = true;
            document.body.classList.add('keyboard-nav');
        }
    });

    // Detect mouse usage
    document.addEventListener('mousedown', () => {
        isKeyboardNav = false;
        document.body.classList.remove('keyboard-nav');
    });
}

/**
 * Check if user is navigating via keyboard
 * @returns {boolean} Whether keyboard navigation is active
 */
function isKeyboardNavigation() {
    return isKeyboardNav;
}

/**
 * Handle arrow key navigation within a group
 * @param {KeyboardEvent} event - The keyboard event
 * @param {HTMLElement[]} items - Array of navigable items
 * @param {Object} options - Navigation options
 * @param {boolean} options.horizontal - Use left/right arrows (default: true)
 * @param {boolean} options.vertical - Use up/down arrows (default: true)
 * @param {boolean} options.wrap - Wrap around at ends (default: true)
 */
function handleArrowNavigation(event, items, options = {}) {
    const { horizontal = true, vertical = true, wrap = true } = options;

    const currentIndex = items.indexOf(document.activeElement);
    if (currentIndex === -1) return;

    let nextIndex = currentIndex;
    const key = event.key;

    if ((horizontal && key === 'ArrowRight') || (vertical && key === 'ArrowDown')) {
        event.preventDefault();
        nextIndex = currentIndex + 1;
        if (nextIndex >= items.length) {
            nextIndex = wrap ? 0 : items.length - 1;
        }
    } else if ((horizontal && key === 'ArrowLeft') || (vertical && key === 'ArrowUp')) {
        event.preventDefault();
        nextIndex = currentIndex - 1;
        if (nextIndex < 0) {
            nextIndex = wrap ? items.length - 1 : 0;
        }
    } else if (key === 'Home') {
        event.preventDefault();
        nextIndex = 0;
    } else if (key === 'End') {
        event.preventDefault();
        nextIndex = items.length - 1;
    }

    if (nextIndex !== currentIndex) {
        items[nextIndex].focus();
    }
}

// ================================================================
// 4. ROVING TABINDEX
// For keyboard navigation within component groups
// ================================================================

/**
 * Initialize roving tabindex for a group of elements
 * @param {HTMLElement} container - Container element
 * @param {string} itemSelector - Selector for items within container
 * @param {Object} options - Options for roving tabindex
 */
function initRovingTabindex(container, itemSelector, options = {}) {
    const { horizontal = true, vertical = false, wrap = true } = options;
    const items = Array.from(container.querySelectorAll(itemSelector));

    if (items.length === 0) return;

    // Set initial tabindex values
    items.forEach((item, index) => {
        item.setAttribute('tabindex', index === 0 ? '0' : '-1');
    });

    // Handle keyboard navigation
    container.addEventListener('keydown', (event) => {
        handleArrowNavigation(event, items, { horizontal, vertical, wrap });

        // Update tabindex on focus change
        const newFocused = items.find(item => item === document.activeElement);
        if (newFocused) {
            items.forEach(item => {
                item.setAttribute('tabindex', item === newFocused ? '0' : '-1');
            });
        }
    });

    // Update tabindex on click
    container.addEventListener('click', (event) => {
        const clickedItem = items.find(item => item.contains(event.target));
        if (clickedItem) {
            items.forEach(item => {
                item.setAttribute('tabindex', item === clickedItem ? '0' : '-1');
            });
        }
    });
}

// ================================================================
// 5. FOCUS TRAP
// For modal dialogs and overlays
// ================================================================

let activeFocusTrap = null;
let previouslyFocused = null;

/**
 * Create a focus trap within a container
 * @param {HTMLElement} container - Container to trap focus within
 * @returns {Object} Focus trap controller with activate/deactivate methods
 */
function createFocusTrap(container) {
    const focusableElements = getFocusableElements(container);
    const firstFocusable = focusableElements[0];
    const lastFocusable = focusableElements[focusableElements.length - 1];

    function handleKeydown(event) {
        if (event.key !== 'Tab') return;

        if (event.shiftKey) {
            // Shift + Tab: moving backwards
            if (document.activeElement === firstFocusable) {
                event.preventDefault();
                lastFocusable.focus();
            }
        } else {
            // Tab: moving forwards
            if (document.activeElement === lastFocusable) {
                event.preventDefault();
                firstFocusable.focus();
            }
        }
    }

    function handleEscape(event) {
        if (event.key === 'Escape') {
            deactivate();
        }
    }

    function activate() {
        if (activeFocusTrap) {
            activeFocusTrap.deactivate();
        }

        previouslyFocused = document.activeElement;
        activeFocusTrap = trapController;

        container.setAttribute('data-focus-trap', 'active');
        document.addEventListener('keydown', handleKeydown);
        document.addEventListener('keydown', handleEscape);

        // Focus first focusable element
        if (firstFocusable) {
            firstFocusable.focus();
        }

        // Make other content inert
        document.querySelectorAll('body > *:not(script):not(style)').forEach(el => {
            if (!container.contains(el) && el !== container) {
                el.setAttribute('inert', '');
            }
        });
    }

    function deactivate() {
        container.removeAttribute('data-focus-trap');
        document.removeEventListener('keydown', handleKeydown);
        document.removeEventListener('keydown', handleEscape);

        // Remove inert from other content
        document.querySelectorAll('[inert]').forEach(el => {
            el.removeAttribute('inert');
        });

        // Restore focus
        if (previouslyFocused) {
            previouslyFocused.focus();
            previouslyFocused = null;
        }

        if (activeFocusTrap === trapController) {
            activeFocusTrap = null;
        }
    }

    const trapController = { activate, deactivate };
    return trapController;
}

// ================================================================
// 6. REDUCED MOTION DETECTION
// Detect and respond to user's motion preferences
// ================================================================

/**
 * Check if user prefers reduced motion
 * @returns {boolean} Whether reduced motion is preferred
 */
function prefersReducedMotion() {
    return window.matchMedia('(prefers-reduced-motion: reduce)').matches;
}

/**
 * Listen for changes to reduced motion preference
 * @param {Function} callback - Callback when preference changes
 * @returns {Function} Cleanup function to remove listener
 */
function onReducedMotionChange(callback) {
    const mediaQuery = window.matchMedia('(prefers-reduced-motion: reduce)');

    const handler = (event) => {
        callback(event.matches);
    };

    mediaQuery.addEventListener('change', handler);
    return () => mediaQuery.removeEventListener('change', handler);
}

// ================================================================
// 7. ARIA ATTRIBUTE HELPERS
// Utilities for managing ARIA attributes
// ================================================================

/**
 * Set aria-expanded on an element
 * @param {HTMLElement} element - The element
 * @param {boolean} expanded - Whether expanded
 */
function setExpanded(element, expanded) {
    element.setAttribute('aria-expanded', String(expanded));
}

/**
 * Set aria-pressed on a toggle button
 * @param {HTMLElement} element - The button element
 * @param {boolean} pressed - Whether pressed
 */
function setPressed(element, pressed) {
    element.setAttribute('aria-pressed', String(pressed));
}

/**
 * Set aria-selected on an option
 * @param {HTMLElement} element - The option element
 * @param {boolean} selected - Whether selected
 */
function setSelected(element, selected) {
    element.setAttribute('aria-selected', String(selected));
}

/**
 * Set aria-busy on an element
 * @param {HTMLElement} element - The element
 * @param {boolean} busy - Whether busy/loading
 */
function setBusy(element, busy) {
    element.setAttribute('aria-busy', String(busy));
}

/**
 * Set aria-disabled on an element
 * @param {HTMLElement} element - The element
 * @param {boolean} disabled - Whether disabled
 */
function setAriaDisabled(element, disabled) {
    element.setAttribute('aria-disabled', String(disabled));
}

/**
 * Update aria-describedby
 * @param {HTMLElement} element - The element
 * @param {string} descriptionId - ID of the describing element
 */
function setDescribedBy(element, descriptionId) {
    element.setAttribute('aria-describedby', descriptionId);
}

// ================================================================
// 8. INITIALIZATION
// Set up accessibility features on page load
// ================================================================

function initAccessibility() {
    // Initialize keyboard navigation detection
    initKeyboardNavigation();

    // Create live regions
    getLiveRegion();
    getAssertiveLiveRegion();

    // Initialize roving tabindex for action grid
    const actionGrid = document.querySelector('.action-grid');
    if (actionGrid) {
        initRovingTabindex(actionGrid, '.action-btn', { horizontal: true, wrap: true });
    }

    // Initialize roving tabindex for status grid
    const statusGrid = document.querySelector('.status-grid');
    if (statusGrid) {
        initRovingTabindex(statusGrid, '.stat-card', { horizontal: true, wrap: true });
    }

    // Initialize roving tabindex for rooms grid
    const roomsGrid = document.getElementById('rooms-grid');
    if (roomsGrid) {
        // Re-initialize when rooms are loaded
        const observer = new MutationObserver(() => {
            initRovingTabindex(roomsGrid, '.room-card', { horizontal: true, wrap: true });
        });
        observer.observe(roomsGrid, { childList: true });
    }

    // Initialize roving tabindex for mode selector
    const modeSelector = document.querySelector('.mode-selector');
    if (modeSelector) {
        initRovingTabindex(modeSelector, '.mode-pill', { horizontal: true, wrap: true });
    }

    console.log('%c[Accessibility] Initialized', 'color: #67d4e4;');
}

// Initialize on DOM ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initAccessibility);
} else {
    initAccessibility();
}

// ================================================================
// EXPORTS
// ================================================================

export const Accessibility = {
    // Announcements
    announce,
    announceError,
    announceStatus,
    announceLoading,

    // Focus management
    focusElement,
    saveFocus,
    restoreFocus,
    isFocusable,
    getFocusableElements,

    // Keyboard navigation
    isKeyboardNavigation,
    handleArrowNavigation,
    initRovingTabindex,

    // Focus trap
    createFocusTrap,

    // Reduced motion
    prefersReducedMotion,
    onReducedMotionChange,

    // ARIA helpers
    setExpanded,
    setPressed,
    setSelected,
    setBusy,
    setAriaDisabled,
    setDescribedBy,
};

// Also expose globally for non-module usage
window.Accessibility = Accessibility;

/*
 * Accessibility is not optional. It is essential.
 *
 */
