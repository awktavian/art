/**
 * Kagami Onboarding Module
 *
 * Multi-step wizard for desktop client setup with delightful animations.
 * Features:
 * - Progress state management with localStorage persistence
 * - Integration with kagami-api.js for server calls
 * - Smart home discovery and connection verification
 * - Room mapping UI
 * - Desktop notification permission request
 * - First-time user animations
 * - Interactive feature tour with highlights
 * - Skip option with persistence
 *
 * Focus:
 *
 *
 */

// ═══════════════════════════════════════════════════════════════════════════
// CONSTANTS
// ═══════════════════════════════════════════════════════════════════════════

const STORAGE_KEYS = {
    ONBOARDING_COMPLETED: 'hasCompletedOnboarding',
    ONBOARDING_PROGRESS: 'kagami-onboarding-progress',
    SELECTED_ROOMS: 'kagami-selected-rooms',
    PERMISSIONS: 'kagami-permissions',
    SERVER_URL: 'kagami-server-url',
    AUTH_TOKEN: 'kagami-auth-token',
    DEMO_MODE: 'isDemoMode',
    TOUR_COMPLETED: 'kagami-tour-completed',
    TOUR_SKIPPED: 'kagami-tour-skipped'
};

const TOTAL_STEPS = 6;

// ═══════════════════════════════════════════════════════════════════════════
// FEATURE TOUR CONFIGURATION
// ═══════════════════════════════════════════════════════════════════════════

const TOUR_STEPS = [
    {
        id: 'welcome',
        title: 'Welcome to Kagami',
        description: 'Your intelligent home companion. Let me show you around.',
        target: null, // Full screen
        position: 'center',
        animation: 'fade-scale',
    },
    {
        id: 'quick-entry',
        title: 'Quick Entry',
        description: 'Press Cmd+Space (or Ctrl+Space) anywhere to quickly control your home.',
        target: '.quick-entry-demo',
        position: 'bottom',
        animation: 'slide-up',
        highlight: true,
    },
    {
        id: 'voice-control',
        title: 'Voice Control',
        description: 'Hold the microphone button or say "Hey Kagami" to use voice commands.',
        target: '.voice-btn-demo',
        position: 'bottom',
        animation: 'pulse',
        highlight: true,
    },
    {
        id: 'scenes',
        title: 'Smart Scenes',
        description: 'One-tap scenes like "Movie Mode" or "Goodnight" control multiple devices.',
        target: '.scenes-demo',
        position: 'right',
        animation: 'slide-right',
        highlight: true,
    },
    {
        id: 'safety',
        title: 'Safety First',
        description: 'Kagami always prioritizes safety in every action.',
        target: '.safety-demo',
        position: 'left',
        animation: 'glow',
        highlight: true,
    },
    {
        id: 'complete',
        title: 'You\'re All Set!',
        description: 'Explore your smart home with confidence. Type "/" for commands.',
        target: null,
        position: 'center',
        animation: 'confetti',
    },
];

// ═══════════════════════════════════════════════════════════════════════════
// STATE
// ═══════════════════════════════════════════════════════════════════════════

const state = {
    currentStep: 1,
    serverConnected: false,
    integrations: {
        control4: null,
        unifi: null,
        denon: null,
        spotify: null
    },
    rooms: [],
    selectedRooms: new Set(),
    permissions: {
        notifications: true,
        voice: false,
        startup: false
    },
    tourActive: false,
    tourStep: 0,
};

// ═══════════════════════════════════════════════════════════════════════════
// FEATURE TOUR CLASS
// ═══════════════════════════════════════════════════════════════════════════

/**
 * Interactive feature tour with spotlight highlights
 */
class FeatureTour {
    constructor(steps = TOUR_STEPS) {
        this.steps = steps;
        this.currentStep = 0;
        this.active = false;
        this.overlay = null;
        this.tooltip = null;
        this.spotlight = null;
        this.onComplete = null;
        this.onSkip = null;
    }

    /**
     * Start the feature tour
     * @param {Function} onComplete - Callback when tour completes
     * @param {Function} onSkip - Callback when tour is skipped
     */
    start(onComplete, onSkip) {
        if (this.active) return;

        this.active = true;
        this.currentStep = 0;
        this.onComplete = onComplete;
        this.onSkip = onSkip;

        this._createOverlay();
        this._createTooltip();
        this._createSpotlight();
        this._showStep(0);

        // Keyboard navigation
        this._keyHandler = this._handleKeyDown.bind(this);
        document.addEventListener('keydown', this._keyHandler);

        console.log('[Tour] Started feature tour');
    }

    /**
     * Stop and cleanup the tour
     */
    stop() {
        if (!this.active) return;

        this.active = false;
        this._cleanup();
        document.removeEventListener('keydown', this._keyHandler);

        console.log('[Tour] Stopped');
    }

    /**
     * Skip the tour
     */
    skip() {
        localStorage.setItem(STORAGE_KEYS.TOUR_SKIPPED, 'true');
        this.stop();
        if (this.onSkip) this.onSkip();
    }

    /**
     * Go to next step
     */
    next() {
        if (this.currentStep < this.steps.length - 1) {
            this.currentStep++;
            this._showStep(this.currentStep);
        } else {
            this._complete();
        }
    }

    /**
     * Go to previous step
     */
    prev() {
        if (this.currentStep > 0) {
            this.currentStep--;
            this._showStep(this.currentStep);
        }
    }

    /**
     * Show specific step
     * @param {number} index
     */
    _showStep(index) {
        const step = this.steps[index];
        if (!step) return;

        // Update tooltip content
        this._updateTooltip(step);

        // Update spotlight
        this._updateSpotlight(step);

        // Play animation
        this._playAnimation(step.animation);

        // Announce to screen readers
        announce(`Tour step ${index + 1} of ${this.steps.length}: ${step.title}`);
    }

    /**
     * Create overlay element
     */
    _createOverlay() {
        this.overlay = document.createElement('div');
        this.overlay.className = 'tour-overlay';
        this.overlay.innerHTML = `
            <div class="tour-overlay-bg"></div>
        `;
        document.body.appendChild(this.overlay);

        // Fade in animation
        requestAnimationFrame(() => {
            this.overlay.classList.add('visible');
        });
    }

    /**
     * Create tooltip element
     */
    _createTooltip() {
        this.tooltip = document.createElement('div');
        this.tooltip.className = 'tour-tooltip';
        this.tooltip.setAttribute('role', 'dialog');
        this.tooltip.setAttribute('aria-modal', 'true');
        this.tooltip.innerHTML = `
            <div class="tour-tooltip-arrow"></div>
            <div class="tour-tooltip-content">
                <h3 class="tour-tooltip-title"></h3>
                <p class="tour-tooltip-description"></p>
                <div class="tour-tooltip-progress">
                    <span class="tour-tooltip-step"></span>
                </div>
                <div class="tour-tooltip-actions">
                    <button type="button" class="tour-btn tour-btn-skip">Skip Tour</button>
                    <div class="tour-tooltip-nav">
                        <button type="button" class="tour-btn tour-btn-prev" disabled>Back</button>
                        <button type="button" class="tour-btn tour-btn-next tour-btn-primary">Next</button>
                    </div>
                </div>
            </div>
        `;
        document.body.appendChild(this.tooltip);

        // Event handlers
        this.tooltip.querySelector('.tour-btn-skip').addEventListener('click', () => this.skip());
        this.tooltip.querySelector('.tour-btn-prev').addEventListener('click', () => this.prev());
        this.tooltip.querySelector('.tour-btn-next').addEventListener('click', () => this.next());
    }

    /**
     * Create spotlight element
     */
    _createSpotlight() {
        this.spotlight = document.createElement('div');
        this.spotlight.className = 'tour-spotlight';
        document.body.appendChild(this.spotlight);
    }

    /**
     * Update tooltip for current step
     * @param {Object} step
     */
    _updateTooltip(step) {
        const title = this.tooltip.querySelector('.tour-tooltip-title');
        const description = this.tooltip.querySelector('.tour-tooltip-description');
        const stepText = this.tooltip.querySelector('.tour-tooltip-step');
        const prevBtn = this.tooltip.querySelector('.tour-btn-prev');
        const nextBtn = this.tooltip.querySelector('.tour-btn-next');

        title.textContent = step.title;
        description.textContent = step.description;
        stepText.textContent = `${this.currentStep + 1} / ${this.steps.length}`;

        // Update navigation buttons
        prevBtn.disabled = this.currentStep === 0;
        nextBtn.textContent = this.currentStep === this.steps.length - 1 ? 'Finish' : 'Next';

        // Position tooltip
        this._positionTooltip(step);

        // Animation
        this.tooltip.classList.remove('visible');
        requestAnimationFrame(() => {
            this.tooltip.classList.add('visible');
        });
    }

    /**
     * Position tooltip relative to target
     * @param {Object} step
     */
    _positionTooltip(step) {
        if (!step.target || step.position === 'center') {
            // Center on screen
            this.tooltip.style.position = 'fixed';
            this.tooltip.style.top = '50%';
            this.tooltip.style.left = '50%';
            this.tooltip.style.transform = 'translate(-50%, -50%)';
            this.tooltip.classList.add('tour-tooltip-center');
            return;
        }

        this.tooltip.classList.remove('tour-tooltip-center');

        const target = document.querySelector(step.target);
        if (!target) {
            // Fallback to center
            this._positionTooltip({ ...step, target: null, position: 'center' });
            return;
        }

        const targetRect = target.getBoundingClientRect();
        const tooltipRect = this.tooltip.getBoundingClientRect();
        const padding = 16;

        let top, left;

        switch (step.position) {
            case 'top':
                top = targetRect.top - tooltipRect.height - padding;
                left = targetRect.left + (targetRect.width - tooltipRect.width) / 2;
                break;
            case 'bottom':
                top = targetRect.bottom + padding;
                left = targetRect.left + (targetRect.width - tooltipRect.width) / 2;
                break;
            case 'left':
                top = targetRect.top + (targetRect.height - tooltipRect.height) / 2;
                left = targetRect.left - tooltipRect.width - padding;
                break;
            case 'right':
                top = targetRect.top + (targetRect.height - tooltipRect.height) / 2;
                left = targetRect.right + padding;
                break;
            default:
                top = targetRect.bottom + padding;
                left = targetRect.left;
        }

        // Clamp to viewport
        top = Math.max(padding, Math.min(top, window.innerHeight - tooltipRect.height - padding));
        left = Math.max(padding, Math.min(left, window.innerWidth - tooltipRect.width - padding));

        this.tooltip.style.position = 'fixed';
        this.tooltip.style.top = `${top}px`;
        this.tooltip.style.left = `${left}px`;
        this.tooltip.style.transform = 'none';
        this.tooltip.setAttribute('data-position', step.position);
    }

    /**
     * Update spotlight for current step
     * @param {Object} step
     */
    _updateSpotlight(step) {
        if (!step.target || !step.highlight) {
            this.spotlight.classList.remove('visible');
            return;
        }

        const target = document.querySelector(step.target);
        if (!target) {
            this.spotlight.classList.remove('visible');
            return;
        }

        const rect = target.getBoundingClientRect();
        const padding = 8;

        this.spotlight.style.top = `${rect.top - padding}px`;
        this.spotlight.style.left = `${rect.left - padding}px`;
        this.spotlight.style.width = `${rect.width + padding * 2}px`;
        this.spotlight.style.height = `${rect.height + padding * 2}px`;
        this.spotlight.classList.add('visible');
    }

    /**
     * Play step animation
     * @param {string} animation
     */
    _playAnimation(animation) {
        // Remove previous animation classes
        this.tooltip.classList.remove(
            'tour-anim-fade-scale',
            'tour-anim-slide-up',
            'tour-anim-slide-right',
            'tour-anim-pulse',
            'tour-anim-glow',
            'tour-anim-confetti'
        );

        if (animation) {
            this.tooltip.classList.add(`tour-anim-${animation}`);
        }

        // Special confetti animation
        if (animation === 'confetti') {
            this._showConfetti();
        }
    }

    /**
     * Show confetti celebration
     */
    _showConfetti() {
        const colors = ['#FF4136', '#FFDC00', '#2ECC40', '#00D4FF', '#B10DC9'];
        const container = document.createElement('div');
        container.className = 'tour-confetti-container';
        document.body.appendChild(container);

        for (let i = 0; i < 50; i++) {
            const piece = document.createElement('div');
            piece.className = 'confetti-piece';
            piece.style.left = `${Math.random() * 100}%`;
            piece.style.backgroundColor = colors[Math.floor(Math.random() * colors.length)];
            piece.style.animationDelay = `${Math.random() * 0.5}s`;
            piece.style.animationDuration = `${2 + Math.random() * 2}s`;
            container.appendChild(piece);
        }

        // Remove after animation
        setTimeout(() => {
            container.remove();
        }, 4000);
    }

    /**
     * Handle keyboard navigation
     * @param {KeyboardEvent} e
     */
    _handleKeyDown(e) {
        switch (e.key) {
            case 'ArrowRight':
            case 'Enter':
                e.preventDefault();
                this.next();
                break;
            case 'ArrowLeft':
                e.preventDefault();
                this.prev();
                break;
            case 'Escape':
                e.preventDefault();
                this.skip();
                break;
        }
    }

    /**
     * Complete the tour
     */
    _complete() {
        localStorage.setItem(STORAGE_KEYS.TOUR_COMPLETED, 'true');
        this.stop();
        if (this.onComplete) this.onComplete();
    }

    /**
     * Cleanup tour elements
     */
    _cleanup() {
        // Use standard timing: 233ms (normal exit animation)
        if (this.overlay) {
            this.overlay.classList.remove('visible');
            setTimeout(() => this.overlay.remove(), 233);
        }
        if (this.tooltip) {
            this.tooltip.classList.remove('visible');
            setTimeout(() => this.tooltip.remove(), 233);
        }
        if (this.spotlight) {
            this.spotlight.classList.remove('visible');
            setTimeout(() => this.spotlight.remove(), 233);
        }
    }
}

// Global tour instance
let featureTour = null;

// ═══════════════════════════════════════════════════════════════════════════
// INITIALIZATION
// ═══════════════════════════════════════════════════════════════════════════

/**
 * Initialize the onboarding module
 */
async function init() {
    console.log('[Onboarding] Initializing...');

    // Check if already onboarded
    if (localStorage.getItem(STORAGE_KEYS.ONBOARDING_COMPLETED) === 'true') {
        console.log('[Onboarding] Already completed, redirecting to dashboard...');
        redirectToDashboard();
        return;
    }

    // Check for auth token - if missing, redirect to login
    const authToken = localStorage.getItem(STORAGE_KEYS.AUTH_TOKEN);
    if (!authToken) {
        console.log('[Onboarding] No auth token, redirecting to login...');
        window.location.href = 'login.html';
        return;
    }

    // Restore progress if any
    restoreProgress();

    // Load server URL from login
    loadServerUrl();

    // Setup event listeners
    setupEventListeners();

    // Setup keyboard navigation
    setupKeyboardNavigation();

    console.log('[Onboarding] Ready');
}

/**
 * Restore saved progress from localStorage
 */
function restoreProgress() {
    const savedProgress = localStorage.getItem(STORAGE_KEYS.ONBOARDING_PROGRESS);
    if (savedProgress) {
        try {
            const progress = JSON.parse(savedProgress);
            state.currentStep = Math.min(progress.step || 1, TOTAL_STEPS);
            state.selectedRooms = new Set(progress.selectedRooms || []);
            state.permissions = { ...state.permissions, ...progress.permissions };

            // Show the restored step
            if (state.currentStep > 1) {
                goToStep(state.currentStep);
            }

            console.log('[Onboarding] Restored progress to step', state.currentStep);
        } catch (e) {
            console.warn('[Onboarding] Failed to restore progress:', e);
        }
    }
}

/**
 * Save current progress to localStorage
 */
function saveProgress() {
    const progress = {
        step: state.currentStep,
        selectedRooms: Array.from(state.selectedRooms),
        permissions: state.permissions,
        timestamp: Date.now()
    };
    localStorage.setItem(STORAGE_KEYS.ONBOARDING_PROGRESS, JSON.stringify(progress));
}

/**
 * Load server URL from login
 */
function loadServerUrl() {
    const serverUrl = localStorage.getItem(STORAGE_KEYS.SERVER_URL) || 'http://kagami.local:8001';
    const serverUrlInput = document.getElementById('server-url');
    if (serverUrlInput) {
        serverUrlInput.value = serverUrl;
    }
}

// ═══════════════════════════════════════════════════════════════════════════
// EVENT LISTENERS
// ═══════════════════════════════════════════════════════════════════════════

/**
 * Setup all event listeners
 */
function setupEventListeners() {
    // Step 1: Welcome
    document.getElementById('start-btn')?.addEventListener('click', () => goToStep(2));

    // Step 2: Server
    document.getElementById('back-to-welcome')?.addEventListener('click', () => goToStep(1));
    document.getElementById('verify-server')?.addEventListener('click', handleVerifyServer);

    // Step 3: Integrations
    document.getElementById('back-to-server')?.addEventListener('click', () => goToStep(2));
    document.getElementById('continue-integrations')?.addEventListener('click', () => goToStep(4));

    // Step 4: Rooms
    document.getElementById('back-to-integrations')?.addEventListener('click', () => goToStep(3));
    document.getElementById('continue-rooms')?.addEventListener('click', () => goToStep(5));
    document.getElementById('skip-rooms')?.addEventListener('click', () => goToStep(5));
    document.getElementById('select-all-rooms')?.addEventListener('click', selectAllRooms);
    document.getElementById('deselect-all-rooms')?.addEventListener('click', deselectAllRooms);

    // Step 5: Permissions
    document.getElementById('back-to-rooms')?.addEventListener('click', () => goToStep(4));
    document.getElementById('continue-permissions')?.addEventListener('click', handleCompleteSetup);
    document.getElementById('skip-permissions')?.addEventListener('click', handleCompleteSetup);

    // Step 6: Complete
    document.getElementById('go-to-dashboard')?.addEventListener('click', handleGoToDashboard);

    // Permission toggles
    document.getElementById('perm-notifications')?.addEventListener('change', (e) => {
        state.permissions.notifications = e.target.checked;
        saveProgress();
    });
    document.getElementById('perm-voice')?.addEventListener('change', (e) => {
        state.permissions.voice = e.target.checked;
        saveProgress();
    });
    document.getElementById('perm-startup')?.addEventListener('change', (e) => {
        state.permissions.startup = e.target.checked;
        saveProgress();
    });
}

/**
 * Setup keyboard navigation
 */
function setupKeyboardNavigation() {
    document.addEventListener('keydown', (e) => {
        // Escape key to go back
        if (e.key === 'Escape' && state.currentStep > 1 && state.currentStep < 6) {
            goToStep(state.currentStep - 1);
        }

        // Enter key on room items toggles selection
        if (e.key === 'Enter' || e.key === ' ') {
            const activeElement = document.activeElement;
            if (activeElement?.classList.contains('room-item')) {
                e.preventDefault();
                const checkbox = activeElement.querySelector('input[type="checkbox"]');
                if (checkbox) {
                    checkbox.checked = !checkbox.checked;
                    checkbox.dispatchEvent(new Event('change', { bubbles: true }));
                }
            }
        }
    });
}

// ═══════════════════════════════════════════════════════════════════════════
// STEP NAVIGATION
// ═══════════════════════════════════════════════════════════════════════════

/**
 * Navigate to a specific step
 * @param {number} step - Step number (1-6)
 */
function goToStep(step) {
    if (step < 1 || step > TOTAL_STEPS) return;

    // Hide all steps
    document.querySelectorAll('.step-content').forEach(el => {
        el.classList.remove('active');
    });

    // Show target step
    const targetStep = document.querySelector(`.step-content[data-step="${step}"]`);
    if (targetStep) {
        targetStep.classList.add('active');
    }

    // Update progress segments
    document.querySelectorAll('.progress-segment').forEach(segment => {
        const segmentStep = parseInt(segment.dataset.step);
        segment.classList.remove('active', 'completed');
        segment.removeAttribute('aria-current');

        if (segmentStep < step) {
            segment.classList.add('completed');
        } else if (segmentStep === step) {
            segment.classList.add('active');
            segment.setAttribute('aria-current', 'step');
        }
    });

    state.currentStep = step;
    saveProgress();

    // Announce step change to screen readers
    announce(`Step ${step} of ${TOTAL_STEPS}`);

    // Focus management
    setTimeout(() => {
        const firstFocusable = targetStep?.querySelector('button, input, [tabindex="0"]');
        if (firstFocusable) {
            firstFocusable.focus();
        }
    }, 100);

    // Step-specific initialization
    switch (step) {
        case 2:
            verifyServerConnection();
            break;
        case 3:
            checkIntegrations();
            break;
        case 4:
            loadRooms();
            break;
        case 5:
            loadPermissionStates();
            break;
    }
}

// ═══════════════════════════════════════════════════════════════════════════
// STEP 2: SERVER CONNECTION
// ═══════════════════════════════════════════════════════════════════════════

/**
 * Handle verify server button click
 */
async function handleVerifyServer() {
    const isConnected = await verifyServerConnection();
    if (isConnected) {
        goToStep(3);
    }
}

/**
 * Verify connection to the server
 * @returns {Promise<boolean>}
 */
async function verifyServerConnection() {
    const serverUrl = localStorage.getItem(STORAGE_KEYS.SERVER_URL);
    const authToken = localStorage.getItem(STORAGE_KEYS.AUTH_TOKEN);
    const statusEl = document.getElementById('server-status');
    const errorEl = document.getElementById('server-error');
    const errorMsg = document.getElementById('server-error-message');

    // Reset UI
    statusEl?.classList.remove('visible');
    errorEl?.classList.remove('visible');

    if (!serverUrl || !authToken) {
        showServerError('No server connection. Please login again.');
        return false;
    }

    try {
        const response = await fetch(`${serverUrl}/health`, {
            headers: {
                'Authorization': `Bearer ${authToken}`
            },
            signal: AbortSignal.timeout(5000)
        });

        if (response.ok) {
            state.serverConnected = true;
            statusEl?.classList.add('visible');
            announce('Server connection verified');
            return true;
        } else {
            throw new Error(`Server returned ${response.status}`);
        }
    } catch (e) {
        console.error('[Onboarding] Server verification failed:', e);
        showServerError(e.message || 'Connection failed. Check your network.');
        return false;
    }
}

/**
 * Show server error message
 * @param {string} message
 */
function showServerError(message) {
    const errorEl = document.getElementById('server-error');
    const errorMsg = document.getElementById('server-error-message');
    const statusEl = document.getElementById('server-status');

    statusEl?.classList.remove('visible');

    if (errorMsg) {
        errorMsg.textContent = message;
    }
    errorEl?.classList.add('visible');
    announce(message, true);
}

// ═══════════════════════════════════════════════════════════════════════════
// STEP 3: INTEGRATIONS
// ═══════════════════════════════════════════════════════════════════════════

/**
 * Check integration statuses
 */
async function checkIntegrations() {
    const serverUrl = localStorage.getItem(STORAGE_KEYS.SERVER_URL);
    const authToken = localStorage.getItem(STORAGE_KEYS.AUTH_TOKEN);

    // Set all to checking
    setIntegrationStatus('control4', 'checking');
    setIntegrationStatus('unifi', 'checking');
    setIntegrationStatus('denon', 'checking');
    setIntegrationStatus('spotify', 'checking');

    try {
        const response = await fetch(`${serverUrl}/api/home/status`, {
            headers: {
                'Authorization': `Bearer ${authToken}`,
                'Content-Type': 'application/json'
            },
            signal: AbortSignal.timeout(10000)
        });

        if (response.ok) {
            const data = await response.json();
            const integrations = data.integrations || {};

            // Update each integration status
            state.integrations.control4 = integrations.control4;
            state.integrations.unifi = integrations.unifi;
            state.integrations.denon = integrations.denon;
            state.integrations.spotify = integrations.spotify;

            setIntegrationStatus('control4', integrations.control4 ? 'connected' : 'disconnected');
            setIntegrationStatus('unifi', integrations.unifi ? 'connected' : 'disconnected');
            setIntegrationStatus('denon', integrations.denon ? 'connected' : 'disconnected');
            setIntegrationStatus('spotify', integrations.spotify ? 'connected' : 'disconnected');

            const connectedCount = Object.values(integrations).filter(Boolean).length;
            announce(`${connectedCount} integrations connected`);
        } else {
            throw new Error('Failed to fetch integrations');
        }
    } catch (e) {
        console.error('[Onboarding] Integration check failed:', e);
        // Show as disconnected on error
        setIntegrationStatus('control4', 'disconnected');
        setIntegrationStatus('unifi', 'disconnected');
        setIntegrationStatus('denon', 'disconnected');
        setIntegrationStatus('spotify', 'disconnected');
    }
}

/**
 * Set integration badge status
 * @param {string} integration - Integration name
 * @param {string} status - 'checking', 'connected', or 'disconnected'
 */
function setIntegrationStatus(integration, status) {
    const badge = document.getElementById(`int-${integration}`);
    if (!badge) return;

    badge.className = `integration-badge ${status}`;

    switch (status) {
        case 'checking':
            badge.textContent = 'Checking...';
            break;
        case 'connected':
            badge.textContent = 'Connected';
            break;
        case 'disconnected':
            badge.textContent = 'Not Found';
            break;
    }
}

// ═══════════════════════════════════════════════════════════════════════════
// STEP 4: ROOMS
// ═══════════════════════════════════════════════════════════════════════════

/**
 * Load rooms from API
 */
async function loadRooms() {
    const roomsList = document.getElementById('rooms-list');
    if (!roomsList) return;

    const serverUrl = localStorage.getItem(STORAGE_KEYS.SERVER_URL);
    const authToken = localStorage.getItem(STORAGE_KEYS.AUTH_TOKEN);

    // Show loading
    roomsList.innerHTML = '<div class="loading-spinner" aria-label="Loading rooms"></div>';

    try {
        const response = await fetch(`${serverUrl}/api/home/rooms`, {
            headers: {
                'Authorization': `Bearer ${authToken}`,
                'Content-Type': 'application/json'
            },
            signal: AbortSignal.timeout(10000)
        });

        if (response.ok) {
            const data = await response.json();
            state.rooms = data.rooms || [];

            // Load previously selected rooms
            const savedRooms = localStorage.getItem(STORAGE_KEYS.SELECTED_ROOMS);
            if (savedRooms) {
                try {
                    state.selectedRooms = new Set(JSON.parse(savedRooms));
                } catch (e) {
                    // Select all by default
                    state.selectedRooms = new Set(state.rooms.map(r => r.id));
                }
            } else {
                // Select all by default
                state.selectedRooms = new Set(state.rooms.map(r => r.id));
            }

            renderRooms();
            announce(`${state.rooms.length} rooms found`);
        } else {
            throw new Error('Failed to fetch rooms');
        }
    } catch (e) {
        console.error('[Onboarding] Room loading failed:', e);
        roomsList.innerHTML = `
            <div style="text-align: center; color: var(--prism-text-tertiary); padding: var(--prism-space-4);">
                <p>Could not load rooms.</p>
                <button type="button" class="skip-btn" onclick="loadRooms()">Retry</button>
            </div>
        `;
    }
}

/**
 * Render rooms list
 */
function renderRooms() {
    const roomsList = document.getElementById('rooms-list');
    if (!roomsList || state.rooms.length === 0) return;

    roomsList.innerHTML = state.rooms.map((room, index) => {
        const isSelected = state.selectedRooms.has(room.id);
        return `
            <div class="room-item ${isSelected ? 'selected' : ''}"
                 data-room-id="${room.id}"
                 tabindex="${index === 0 ? '0' : '-1'}"
                 role="checkbox"
                 aria-checked="${isSelected}">
                <input type="checkbox"
                       id="room-${room.id}"
                       ${isSelected ? 'checked' : ''}
                       aria-label="${room.name}">
                <label for="room-${room.id}">${escapeHtml(room.name)}</label>
            </div>
        `;
    }).join('');

    // Add event listeners
    roomsList.querySelectorAll('.room-item').forEach(item => {
        const checkbox = item.querySelector('input[type="checkbox"]');

        item.addEventListener('click', (e) => {
            if (e.target !== checkbox) {
                checkbox.checked = !checkbox.checked;
                checkbox.dispatchEvent(new Event('change', { bubbles: true }));
            }
        });

        checkbox.addEventListener('change', () => {
            const roomId = item.dataset.roomId;
            if (checkbox.checked) {
                state.selectedRooms.add(roomId);
                item.classList.add('selected');
                item.setAttribute('aria-checked', 'true');
            } else {
                state.selectedRooms.delete(roomId);
                item.classList.remove('selected');
                item.setAttribute('aria-checked', 'false');
            }
            saveRoomSelection();
        });
    });

    // Keyboard navigation within rooms list
    setupRoomListKeyboardNav(roomsList);
}

/**
 * Setup keyboard navigation for room list
 * @param {HTMLElement} roomsList
 */
function setupRoomListKeyboardNav(roomsList) {
    roomsList.addEventListener('keydown', (e) => {
        const items = Array.from(roomsList.querySelectorAll('.room-item'));
        const currentIndex = items.findIndex(item => item === document.activeElement);

        switch (e.key) {
            case 'ArrowRight':
            case 'ArrowDown':
                e.preventDefault();
                if (currentIndex < items.length - 1) {
                    items[currentIndex + 1].focus();
                }
                break;
            case 'ArrowLeft':
            case 'ArrowUp':
                e.preventDefault();
                if (currentIndex > 0) {
                    items[currentIndex - 1].focus();
                }
                break;
            case 'Home':
                e.preventDefault();
                items[0]?.focus();
                break;
            case 'End':
                e.preventDefault();
                items[items.length - 1]?.focus();
                break;
        }
    });
}

/**
 * Select all rooms
 */
function selectAllRooms() {
    state.selectedRooms = new Set(state.rooms.map(r => r.id));
    renderRooms();
    saveRoomSelection();
    announce('All rooms selected');
}

/**
 * Deselect all rooms
 */
function deselectAllRooms() {
    state.selectedRooms.clear();
    renderRooms();
    saveRoomSelection();
    announce('All rooms deselected');
}

/**
 * Save room selection to localStorage
 */
function saveRoomSelection() {
    localStorage.setItem(STORAGE_KEYS.SELECTED_ROOMS, JSON.stringify(Array.from(state.selectedRooms)));
    saveProgress();
}

// ═══════════════════════════════════════════════════════════════════════════
// STEP 5: PERMISSIONS
// ═══════════════════════════════════════════════════════════════════════════

/**
 * Load permission states from saved preferences
 */
function loadPermissionStates() {
    const notificationsToggle = document.getElementById('perm-notifications');
    const voiceToggle = document.getElementById('perm-voice');
    const startupToggle = document.getElementById('perm-startup');

    if (notificationsToggle) {
        notificationsToggle.checked = state.permissions.notifications;
    }
    if (voiceToggle) {
        voiceToggle.checked = state.permissions.voice;
    }
    if (startupToggle) {
        startupToggle.checked = state.permissions.startup;
    }
}

/**
 * Handle complete setup button
 */
async function handleCompleteSetup() {
    // Save permissions
    localStorage.setItem(STORAGE_KEYS.PERMISSIONS, JSON.stringify(state.permissions));

    // Request notification permission if enabled
    if (state.permissions.notifications && 'Notification' in window) {
        try {
            const permission = await Notification.requestPermission();
            state.permissions.notifications = permission === 'granted';
            localStorage.setItem(STORAGE_KEYS.PERMISSIONS, JSON.stringify(state.permissions));
        } catch (e) {
            console.warn('[Onboarding] Notification permission request failed:', e);
        }
    }

    // Request microphone permission if voice is enabled
    if (state.permissions.voice && navigator.mediaDevices) {
        try {
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            stream.getTracks().forEach(track => track.stop());
        } catch (e) {
            console.warn('[Onboarding] Microphone permission request failed:', e);
            state.permissions.voice = false;
            localStorage.setItem(STORAGE_KEYS.PERMISSIONS, JSON.stringify(state.permissions));
        }
    }

    // Handle startup permission (Tauri-specific)
    if (state.permissions.startup && window.__TAURI_INTERNALS__) {
        try {
            const { invoke } = await import('@tauri-apps/api/core');
            await invoke('enable_autostart');
        } catch (e) {
            console.warn('[Onboarding] Autostart setup failed:', e);
        }
    }

    // Go to complete step
    goToStep(6);
}

// ═══════════════════════════════════════════════════════════════════════════
// STEP 6: COMPLETE
// ═══════════════════════════════════════════════════════════════════════════

/**
 * Handle go to dashboard button
 */
function handleGoToDashboard() {
    // Mark onboarding as complete
    localStorage.setItem(STORAGE_KEYS.ONBOARDING_COMPLETED, 'true');

    // Clear progress (no longer needed)
    localStorage.removeItem(STORAGE_KEYS.ONBOARDING_PROGRESS);

    // Redirect to dashboard
    redirectToDashboard();
}

/**
 * Redirect to dashboard
 */
function redirectToDashboard() {
    window.location.href = 'index.html';
}

// ═══════════════════════════════════════════════════════════════════════════
// UTILITIES
// ═══════════════════════════════════════════════════════════════════════════

/**
 * Escape HTML to prevent XSS
 * @param {string} str
 * @returns {string}
 */
function escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}

/**
 * Announce message to screen readers
 * @param {string} message
 * @param {boolean} isError
 */
function announce(message, isError = false) {
    const liveRegion = document.getElementById('live-region');
    if (liveRegion) {
        liveRegion.setAttribute('aria-live', isError ? 'assertive' : 'polite');
        liveRegion.textContent = message;

        // Clear after announcement
        setTimeout(() => {
            liveRegion.textContent = '';
        }, 1000);
    }
}

// ═══════════════════════════════════════════════════════════════════════════
// FEATURE TOUR PUBLIC API
// ═══════════════════════════════════════════════════════════════════════════

/**
 * Start the feature tour for first-time users
 * @param {Object} options - Tour options
 * @param {Function} options.onComplete - Callback when tour completes
 * @param {Function} options.onSkip - Callback when tour is skipped
 * @param {boolean} options.force - Force show even if previously completed
 */
function startFeatureTour(options = {}) {
    const { onComplete, onSkip, force = false } = options;

    // Check if tour should be shown
    if (!force) {
        const completed = localStorage.getItem(STORAGE_KEYS.TOUR_COMPLETED) === 'true';
        const skipped = localStorage.getItem(STORAGE_KEYS.TOUR_SKIPPED) === 'true';
        if (completed || skipped) {
            console.log('[Tour] Already completed or skipped');
            return false;
        }
    }

    // Create and start tour
    featureTour = new FeatureTour(TOUR_STEPS);
    featureTour.start(
        () => {
            console.log('[Tour] Completed');
            if (onComplete) onComplete();
        },
        () => {
            console.log('[Tour] Skipped');
            if (onSkip) onSkip();
        }
    );

    return true;
}

/**
 * Check if tour should be shown for first-time users
 * @returns {boolean}
 */
function shouldShowTour() {
    const completed = localStorage.getItem(STORAGE_KEYS.TOUR_COMPLETED) === 'true';
    const skipped = localStorage.getItem(STORAGE_KEYS.TOUR_SKIPPED) === 'true';
    const onboardingDone = localStorage.getItem(STORAGE_KEYS.ONBOARDING_COMPLETED) === 'true';

    // Show tour after onboarding is complete, but only once
    return onboardingDone && !completed && !skipped;
}

/**
 * Reset tour state (for testing or re-enabling)
 */
function resetTourState() {
    localStorage.removeItem(STORAGE_KEYS.TOUR_COMPLETED);
    localStorage.removeItem(STORAGE_KEYS.TOUR_SKIPPED);
    console.log('[Tour] State reset');
}

/**
 * Get current tour instance
 * @returns {FeatureTour|null}
 */
function getTourInstance() {
    return featureTour;
}

// ═══════════════════════════════════════════════════════════════════════════
// FIRST-TIME USER WELCOME ANIMATION
// ═══════════════════════════════════════════════════════════════════════════

/**
 * Show welcome animation for first-time users
 */
function showWelcomeAnimation() {
    const container = document.createElement('div');
    container.className = 'welcome-animation-container';
    container.innerHTML = `
        <div class="welcome-animation">
            <div class="welcome-logo" aria-hidden="true">
                <svg viewBox="0 0 100 100" class="kagami-logo-animated">
                    <path class="logo-outer" d="M50 5 L95 50 L50 95 L5 50 Z"
                          fill="none" stroke="currentColor" stroke-width="2"/>
                    <path class="logo-inner" d="M50 20 L80 50 L50 80 L20 50 Z"
                          fill="none" stroke="currentColor" stroke-width="1.5"/>
                    <circle class="logo-center" cx="50" cy="50" r="8"
                            fill="currentColor"/>
                </svg>
            </div>
            <h1 class="welcome-title">Welcome to Kagami</h1>
            <p class="welcome-subtitle">Your intelligent home companion</p>
            <div class="welcome-dots">
                <span class="dot dot-1"></span>
                <span class="dot dot-2"></span>
                <span class="dot dot-3"></span>
            </div>
        </div>
    `;

    document.body.appendChild(container);

    // Animate in
    requestAnimationFrame(() => {
        container.classList.add('visible');
    });

    // Auto-dismiss after animation
    setTimeout(() => {
        container.classList.add('fade-out');
        setTimeout(() => {
            container.remove();
        }, 500);
    }, 2500);
}

/**
 * Check and show welcome animation for first-time users
 * @returns {boolean} Whether animation was shown
 */
function maybeShowWelcome() {
    const hasSeenWelcome = localStorage.getItem('kagami-welcome-shown') === 'true';
    const isFirstVisit = !localStorage.getItem(STORAGE_KEYS.ONBOARDING_COMPLETED);

    if (isFirstVisit && !hasSeenWelcome) {
        showWelcomeAnimation();
        localStorage.setItem('kagami-welcome-shown', 'true');
        return true;
    }
    return false;
}

// ═══════════════════════════════════════════════════════════════════════════
// EXPORTS
// ═══════════════════════════════════════════════════════════════════════════

// Export for external use
window.KagamiOnboarding = {
    goToStep,
    getState: () => ({ ...state }),
    isComplete: () => localStorage.getItem(STORAGE_KEYS.ONBOARDING_COMPLETED) === 'true',
    // Tour API
    startTour: startFeatureTour,
    shouldShowTour,
    resetTourState,
    getTour: getTourInstance,
    // Welcome animation
    showWelcome: showWelcomeAnimation,
    maybeShowWelcome,
    // Tour class for custom tours
    FeatureTour,
};

// Initialize on DOM ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
} else {
    init();
}

// Auto-start tour if appropriate (after a brief delay)
setTimeout(() => {
    if (shouldShowTour()) {
        console.log('[Onboarding] Starting feature tour for returning user');
        startFeatureTour();
    }
}, 1000);

/*
 * Beacon guides. Beacon welcomes. Beacon illuminates.
 *
 */
