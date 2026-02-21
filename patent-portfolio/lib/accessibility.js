/**
 * Accessibility System
 * ====================
 * 
 * WCAG 2.1 AA compliant accessibility features for the Patent Museum.
 * 
 * Features:
 * - High contrast mode
 * - Keyboard-only navigation
 * - Screen reader support (ARIA live regions)
 * - Motion reduction (respects prefers-reduced-motion)
 * - Voice navigation (experimental)
 * - Focus management
 * 
 * h(x) ≥ 0 always
 */

// ═══════════════════════════════════════════════════════════════════════════
// ACCESSIBILITY MANAGER
// ═══════════════════════════════════════════════════════════════════════════

export class AccessibilityManager {
    constructor() {
        this.settings = {
            highContrast: false,
            reducedMotion: false,
            largeText: false,
            screenReaderMode: false,
            keyboardOnly: false,
            voiceNavigation: false
        };
        
        // DOM elements
        this.announcerElement = null;
        this.skipLinkElement = null;
        this.settingsPanelElement = null;
        
        // State
        this.currentFocusIndex = 0;
        this.focusableElements = [];
        this.voiceRecognition = null;
        
        // Bound handlers for cleanup
        this._keyboardHandler = null;
        this._tabHandler = null;
        
        // Detect user preferences
        this.detectPreferences();
    }
    
    init() {
        // Create accessibility infrastructure
        this.createAnnouncer();
        this.createSkipLink();
        this.createSettingsPanel();
        
        // Set up keyboard navigation
        this.setupKeyboardNavigation();
        
        // Set up voice navigation if supported
        this.setupVoiceNavigation();
        
        // Apply initial settings
        this.applySettings();
        
        console.log('♿ Accessibility system initialized');
    }
    
    // ═══════════════════════════════════════════════════════════════════════
    // PREFERENCE DETECTION
    // ═══════════════════════════════════════════════════════════════════════
    
    detectPreferences() {
        // Check for prefers-reduced-motion
        if (window.matchMedia) {
            const motionQuery = window.matchMedia('(prefers-reduced-motion: reduce)');
            this.settings.reducedMotion = motionQuery.matches;
            
            motionQuery.addEventListener('change', (e) => {
                this.settings.reducedMotion = e.matches;
                this.applySettings();
                this.announce(e.matches ? 'Reduced motion enabled' : 'Motion enabled');
            });
            
            // Check for prefers-contrast
            const contrastQuery = window.matchMedia('(prefers-contrast: more)');
            if (contrastQuery.matches) {
                this.settings.highContrast = true;
            }
            
            contrastQuery.addEventListener('change', (e) => {
                this.settings.highContrast = e.matches;
                this.applySettings();
            });
        }
        
        // Check for stored preferences
        try {
            const stored = localStorage.getItem('museum-accessibility');
            if (stored) {
                const parsed = JSON.parse(stored);
                Object.assign(this.settings, parsed);
            }
        } catch (e) {
            // Ignore storage errors
        }
    }
    
    savePreferences() {
        try {
            localStorage.setItem('museum-accessibility', JSON.stringify(this.settings));
        } catch (e) {
            // Ignore storage errors
        }
    }
    
    // ═══════════════════════════════════════════════════════════════════════
    // SCREEN READER SUPPORT
    // ═══════════════════════════════════════════════════════════════════════
    
    createAnnouncer() {
        // Create ARIA live region for announcements
        this.announcerElement = document.createElement('div');
        this.announcerElement.id = 'a11y-announcer';
        this.announcerElement.setAttribute('role', 'status');
        this.announcerElement.setAttribute('aria-live', 'polite');
        this.announcerElement.setAttribute('aria-atomic', 'true');
        this.announcerElement.style.cssText = `
            position: absolute;
            width: 1px;
            height: 1px;
            padding: 0;
            margin: -1px;
            overflow: hidden;
            clip: rect(0, 0, 0, 0);
            white-space: nowrap;
            border: 0;
        `;
        
        document.body.appendChild(this.announcerElement);
        
        // Create assertive announcer for important messages
        this.assertiveAnnouncer = document.createElement('div');
        this.assertiveAnnouncer.id = 'a11y-announcer-assertive';
        this.assertiveAnnouncer.setAttribute('role', 'alert');
        this.assertiveAnnouncer.setAttribute('aria-live', 'assertive');
        this.assertiveAnnouncer.setAttribute('aria-atomic', 'true');
        this.assertiveAnnouncer.style.cssText = this.announcerElement.style.cssText;
        
        document.body.appendChild(this.assertiveAnnouncer);
    }
    
    /**
     * Announce a message to screen readers
     * @param {string} message - Message to announce
     * @param {boolean} assertive - If true, interrupts current speech
     */
    announce(message, assertive = false) {
        const element = assertive ? this.assertiveAnnouncer : this.announcerElement;
        if (!element) return;
        
        // Clear and re-add to trigger announcement
        element.textContent = '';
        
        // Small delay to ensure change is detected
        setTimeout(() => {
            element.textContent = message;
        }, 50);
        
        console.log(`📢 Announced: ${message}`);
    }
    
    /**
     * Announce current location in museum
     */
    announceLocation(locationName, description = '') {
        let message = `You are now in ${locationName}.`;
        if (description) {
            message += ` ${description}`;
        }
        this.announce(message);
    }
    
    /**
     * Announce artwork details
     */
    announceArtwork(artwork) {
        if (!artwork) return;
        
        const message = `
            Artwork: ${artwork.name || 'Untitled'}.
            ${artwork.description || ''}.
            ${artwork.keyFeatures ? 'Key features: ' + artwork.keyFeatures.join(', ') : ''}
        `.replace(/\s+/g, ' ').trim();
        
        this.announce(message);
        
        if (this.settings.screenReaderMode) {
            this.speakTTS(message);
        }
    }
    
    /**
     * Speak text aloud using Web Speech Synthesis API.
     * Falls back silently if unsupported.
     */
    speakTTS(text) {
        if (!('speechSynthesis' in window)) return;
        
        window.speechSynthesis.cancel();
        const utterance = new SpeechSynthesisUtterance(text);
        utterance.rate = 0.9;
        utterance.pitch = 1.0;
        utterance.volume = 0.8;
        utterance.lang = 'en-US';
        window.speechSynthesis.speak(utterance);
    }
    
    // ═══════════════════════════════════════════════════════════════════════
    // SKIP LINK
    // ═══════════════════════════════════════════════════════════════════════
    
    createSkipLink() {
        this.skipLinkElement = document.createElement('a');
        this.skipLinkElement.id = 'skip-link';
        this.skipLinkElement.href = '#museum-content';
        this.skipLinkElement.textContent = 'Skip to museum content';
        this.skipLinkElement.style.cssText = `
            position: absolute;
            top: -100px;
            left: 50%;
            transform: translateX(-50%);
            padding: 12px 24px;
            background: #1A1A1A;
            color: #67D4E4;
            text-decoration: none;
            font-family: 'IBM Plex Sans', sans-serif;
            font-size: 16px;
            border-radius: 0 0 8px 8px;
            z-index: 10000;
            transition: top 0.2s ease;
        `;
        
        this.skipLinkElement.addEventListener('focus', () => {
            this.skipLinkElement.style.top = '0';
        });
        
        this.skipLinkElement.addEventListener('blur', () => {
            this.skipLinkElement.style.top = '-100px';
        });
        
        document.body.insertBefore(this.skipLinkElement, document.body.firstChild);
    }
    
    // ═══════════════════════════════════════════════════════════════════════
    // SETTINGS PANEL
    // ═══════════════════════════════════════════════════════════════════════
    
    createSettingsPanel() {
        this.settingsPanelElement = document.createElement('div');
        this.settingsPanelElement.id = 'a11y-settings';
        this.settingsPanelElement.setAttribute('role', 'dialog');
        this.settingsPanelElement.setAttribute('aria-labelledby', 'a11y-settings-title');
        this.settingsPanelElement.setAttribute('aria-modal', 'true');
        this.settingsPanelElement.style.cssText = `
            position: fixed;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            width: 90%;
            max-width: 400px;
            background: #1A1A1A;
            border: 2px solid #67D4E4;
            border-radius: 12px;
            padding: 24px;
            z-index: 10001;
            display: none;
            font-family: 'IBM Plex Sans', sans-serif;
        `;
        
        this.settingsPanelElement.innerHTML = `
            <h2 id="a11y-settings-title" style="margin: 0 0 20px 0; color: #67D4E4; font-size: 20px;">
                Accessibility Settings
            </h2>
            
            <div style="display: flex; flex-direction: column; gap: 16px;">
                <label style="display: flex; align-items: center; gap: 12px; color: #E0E0E0; cursor: pointer;">
                    <input type="checkbox" id="a11y-high-contrast" 
                           style="width: 20px; height: 20px; accent-color: #67D4E4;">
                    <span>High Contrast Mode</span>
                </label>
                
                <label style="display: flex; align-items: center; gap: 12px; color: #E0E0E0; cursor: pointer;">
                    <input type="checkbox" id="a11y-reduced-motion"
                           style="width: 20px; height: 20px; accent-color: #67D4E4;">
                    <span>Reduced Motion</span>
                </label>
                
                <label style="display: flex; align-items: center; gap: 12px; color: #E0E0E0; cursor: pointer;">
                    <input type="checkbox" id="a11y-large-text"
                           style="width: 20px; height: 20px; accent-color: #67D4E4;">
                    <span>Large Text</span>
                </label>
                
                <label style="display: flex; align-items: center; gap: 12px; color: #E0E0E0; cursor: pointer;">
                    <input type="checkbox" id="a11y-screen-reader"
                           style="width: 20px; height: 20px; accent-color: #67D4E4;">
                    <span>Screen Reader Mode</span>
                </label>
                
                <label style="display: flex; align-items: center; gap: 12px; color: #E0E0E0; cursor: pointer;">
                    <input type="checkbox" id="a11y-voice-nav"
                           style="width: 20px; height: 20px; accent-color: #67D4E4;">
                    <span>Voice Navigation (Experimental)</span>
                </label>
            </div>
            
            <div style="margin-top: 24px; display: flex; gap: 12px; justify-content: flex-end;">
                <button id="a11y-close" style="
                    padding: 10px 20px;
                    background: transparent;
                    border: 1px solid #666;
                    color: #E0E0E0;
                    border-radius: 6px;
                    cursor: pointer;
                    font-size: 14px;
                ">Close</button>
                <button id="a11y-save" style="
                    padding: 10px 20px;
                    background: #67D4E4;
                    border: none;
                    color: #1A1A1A;
                    border-radius: 6px;
                    cursor: pointer;
                    font-size: 14px;
                    font-weight: 500;
                ">Save</button>
            </div>
        `;
        
        document.body.appendChild(this.settingsPanelElement);
        
        // Bind events
        this.settingsPanelElement.querySelector('#a11y-close').addEventListener('click', () => {
            this.hideSettings();
        });
        
        this.settingsPanelElement.querySelector('#a11y-save').addEventListener('click', () => {
            this.saveSettingsFromPanel();
            this.hideSettings();
        });
        
        // Initialize checkboxes with current values
        this.updateSettingsPanel();
    }
    
    updateSettingsPanel() {
        const panel = this.settingsPanelElement;
        if (!panel) return;
        
        panel.querySelector('#a11y-high-contrast').checked = this.settings.highContrast;
        panel.querySelector('#a11y-reduced-motion').checked = this.settings.reducedMotion;
        panel.querySelector('#a11y-large-text').checked = this.settings.largeText;
        panel.querySelector('#a11y-screen-reader').checked = this.settings.screenReaderMode;
        panel.querySelector('#a11y-voice-nav').checked = this.settings.voiceNavigation;
    }
    
    saveSettingsFromPanel() {
        const panel = this.settingsPanelElement;
        
        this.settings.highContrast = panel.querySelector('#a11y-high-contrast').checked;
        this.settings.reducedMotion = panel.querySelector('#a11y-reduced-motion').checked;
        this.settings.largeText = panel.querySelector('#a11y-large-text').checked;
        this.settings.screenReaderMode = panel.querySelector('#a11y-screen-reader').checked;
        this.settings.voiceNavigation = panel.querySelector('#a11y-voice-nav').checked;
        
        this.applySettings();
        this.savePreferences();
        this.announce('Settings saved');
    }
    
    showSettings() {
        this.updateSettingsPanel();
        this.settingsPanelElement.style.display = 'block';
        
        // Focus first input
        this.settingsPanelElement.querySelector('input').focus();
        
        // Trap focus
        this.trapFocus(this.settingsPanelElement);
    }
    
    hideSettings() {
        this.settingsPanelElement.style.display = 'none';
        this.releaseFocus();
    }
    
    toggleSettings() {
        if (this.settingsPanelElement.style.display === 'none') {
            this.showSettings();
        } else {
            this.hideSettings();
        }
    }
    
    // ═══════════════════════════════════════════════════════════════════════
    // KEYBOARD NAVIGATION
    // ═══════════════════════════════════════════════════════════════════════
    
    setupKeyboardNavigation() {
        // Main keyboard handler (store reference for cleanup)
        this._keyboardHandler = (e) => {
            // Accessibility settings shortcut (Ctrl+Shift+A)
            if (e.ctrlKey && e.shiftKey && e.key.toLowerCase() === 'a') {
                e.preventDefault();
                this.toggleSettings();
            }
            
            // Quick toggle high contrast (Ctrl+Shift+H)
            if (e.ctrlKey && e.shiftKey && e.key.toLowerCase() === 'h') {
                e.preventDefault();
                this.settings.highContrast = !this.settings.highContrast;
                this.applySettings();
                this.announce(this.settings.highContrast ? 'High contrast enabled' : 'High contrast disabled');
            }
            
            // Quick toggle reduced motion (Ctrl+Shift+M)
            if (e.ctrlKey && e.shiftKey && e.key.toLowerCase() === 'm') {
                e.preventDefault();
                this.settings.reducedMotion = !this.settings.reducedMotion;
                this.applySettings();
                this.announce(this.settings.reducedMotion ? 'Reduced motion enabled' : 'Motion enabled');
            }
            
            // Read current location (Ctrl+L)
            if (e.ctrlKey && e.key.toLowerCase() === 'l') {
                e.preventDefault();
                document.dispatchEvent(new CustomEvent('a11y-read-location'));
            }
            
            // Help (?)
            if (e.key === '?' && !e.ctrlKey && !e.altKey) {
                this.showHelp();
            }
        };
        document.addEventListener('keydown', this._keyboardHandler);
        
        // Tab key handling for museum navigation (store reference for cleanup)
        this._tabHandler = (e) => {
            if (e.key === 'Tab' && !this.isInDialog()) {
                // Custom tab navigation for museum elements
                this.handleTabNavigation(e);
            }
        };
        document.addEventListener('keydown', this._tabHandler);
    }
    
    handleTabNavigation(e) {
        // Get focusable elements in museum
        this.updateFocusableElements();
        
        if (this.focusableElements.length === 0) return;
        
        if (e.shiftKey) {
            // Shift+Tab: previous
            this.currentFocusIndex--;
            if (this.currentFocusIndex < 0) {
                this.currentFocusIndex = this.focusableElements.length - 1;
            }
        } else {
            // Tab: next
            this.currentFocusIndex++;
            if (this.currentFocusIndex >= this.focusableElements.length) {
                this.currentFocusIndex = 0;
            }
        }
        
        // Focus the element
        const element = this.focusableElements[this.currentFocusIndex];
        if (element) {
            e.preventDefault();
            element.focus();
            
            // Announce element
            if (element.getAttribute('aria-label')) {
                this.announce(element.getAttribute('aria-label'));
            }
        }
    }
    
    updateFocusableElements() {
        // Query all focusable elements in the museum
        this.focusableElements = Array.from(document.querySelectorAll(
            '#museum-content button, #museum-content [tabindex="0"], ' +
            '#museum-content a[href], #museum-content input, ' +
            '.artwork-interactive, .wing-sign, .info-kiosk'
        ));
    }
    
    // ═══════════════════════════════════════════════════════════════════════
    // FOCUS TRAP (for dialogs)
    // ═══════════════════════════════════════════════════════════════════════
    
    trapFocus(element) {
        this.focusTrapElement = element;
        this.focusTrapHandler = (e) => {
            if (e.key !== 'Tab') return;
            
            const focusable = element.querySelectorAll(
                'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
            );
            const first = focusable[0];
            const last = focusable[focusable.length - 1];
            
            if (e.shiftKey && document.activeElement === first) {
                e.preventDefault();
                last.focus();
            } else if (!e.shiftKey && document.activeElement === last) {
                e.preventDefault();
                first.focus();
            }
        };
        
        document.addEventListener('keydown', this.focusTrapHandler);
    }
    
    releaseFocus() {
        if (this.focusTrapHandler) {
            document.removeEventListener('keydown', this.focusTrapHandler);
            this.focusTrapHandler = null;
        }
    }
    
    isInDialog() {
        return document.activeElement?.closest('[role="dialog"]') !== null;
    }
    
    // ═══════════════════════════════════════════════════════════════════════
    // VOICE NAVIGATION
    // ═══════════════════════════════════════════════════════════════════════
    
    setupVoiceNavigation() {
        if (!('webkitSpeechRecognition' in window) && !('SpeechRecognition' in window)) {
            console.log('Voice navigation not supported');
            return;
        }
        
        const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
        this.voiceRecognition = new SpeechRecognition();
        this.voiceRecognition.continuous = true;
        this.voiceRecognition.interimResults = false;
        this.voiceRecognition.lang = 'en-US';
        
        this.voiceRecognition.onresult = (event) => {
            const command = event.results[event.results.length - 1][0].transcript.toLowerCase().trim();
            this.handleVoiceCommand(command);
        };
        
        this.voiceRecognition.onerror = (event) => {
            if (event.error !== 'no-speech') {
                console.warn('Voice recognition error:', event.error);
            }
        };
    }
    
    startVoiceNavigation() {
        if (!this.voiceRecognition) return;
        
        try {
            this.voiceRecognition.start();
            this.announce('Voice navigation started. Say "help" for commands.');
        } catch (e) {
            console.warn('Could not start voice recognition:', e);
        }
    }
    
    stopVoiceNavigation() {
        if (!this.voiceRecognition) return;
        
        this.voiceRecognition.stop();
        this.announce('Voice navigation stopped.');
    }
    
    handleVoiceCommand(command) {
        console.log('Voice command:', command);
        
        // Navigation commands
        if (command.includes('go to') || command.includes('navigate to')) {
            const wings = ['spark', 'forge', 'flow', 'nexus', 'beacon', 'grove', 'crystal'];
            for (const wing of wings) {
                if (command.includes(wing)) {
                    document.dispatchEvent(new CustomEvent('voice-navigate', { detail: { wing } }));
                    this.announce(`Navigating to ${wing} wing`);
                    return;
                }
            }
            
            if (command.includes('rotunda') || command.includes('center')) {
                document.dispatchEvent(new CustomEvent('voice-navigate', { detail: { location: 'rotunda' } }));
                this.announce('Navigating to rotunda');
            }
        }
        
        // Movement commands
        if (command.includes('forward') || command.includes('ahead')) {
            document.dispatchEvent(new CustomEvent('voice-move', { detail: { direction: 'forward' } }));
        } else if (command.includes('back') || command.includes('backward')) {
            document.dispatchEvent(new CustomEvent('voice-move', { detail: { direction: 'back' } }));
        } else if (command.includes('left')) {
            document.dispatchEvent(new CustomEvent('voice-move', { detail: { direction: 'left' } }));
        } else if (command.includes('right')) {
            document.dispatchEvent(new CustomEvent('voice-move', { detail: { direction: 'right' } }));
        }
        
        // Information commands
        if (command.includes('where am i') || command.includes('my location')) {
            document.dispatchEvent(new CustomEvent('a11y-read-location'));
        }
        
        if (command.includes('describe') || command.includes('what is this')) {
            document.dispatchEvent(new CustomEvent('a11y-describe-artwork'));
        }
        
        // Help
        if (command.includes('help')) {
            this.announceVoiceCommands();
        }
        
        // Stop
        if (command.includes('stop listening') || command.includes('voice off')) {
            this.stopVoiceNavigation();
        }
    }
    
    announceVoiceCommands() {
        this.announce(`
            Voice commands available:
            Go to spark, forge, flow, nexus, beacon, grove, or crystal wing.
            Forward, backward, left, or right to move.
            Where am I to hear your location.
            Describe to learn about the current artwork.
            Stop listening to disable voice navigation.
        `);
    }
    
    // ═══════════════════════════════════════════════════════════════════════
    // APPLY SETTINGS
    // ═══════════════════════════════════════════════════════════════════════
    
    applySettings() {
        // High contrast
        if (this.settings.highContrast) {
            document.body.classList.add('high-contrast');
        } else {
            document.body.classList.remove('high-contrast');
        }
        
        // Reduced motion
        if (this.settings.reducedMotion) {
            document.body.classList.add('reduced-motion');
        } else {
            document.body.classList.remove('reduced-motion');
        }
        
        // Large text
        if (this.settings.largeText) {
            document.body.classList.add('large-text');
        } else {
            document.body.classList.remove('large-text');
        }
        
        // Screen reader mode
        if (this.settings.screenReaderMode) {
            document.body.classList.add('screen-reader-mode');
        } else {
            document.body.classList.remove('screen-reader-mode');
        }
        
        // Voice navigation
        if (this.settings.voiceNavigation) {
            this.startVoiceNavigation();
        } else {
            this.stopVoiceNavigation();
        }
        
        // Dispatch event for other systems
        document.dispatchEvent(new CustomEvent('accessibility-changed', {
            detail: this.settings
        }));
    }
    
    // ═══════════════════════════════════════════════════════════════════════
    // HELP
    // ═══════════════════════════════════════════════════════════════════════
    
    showHelp() {
        this.announce(`
            Keyboard shortcuts:
            W A S D or Arrow keys to move.
            Click and drag to look around.
            M to toggle minimap.
            I for information.
            Control Shift A for accessibility settings.
            Control Shift H for high contrast.
            Control Shift M for reduced motion.
            Control L to hear your location.
            Question mark for this help.
        `);
    }
    
    // ═══════════════════════════════════════════════════════════════════════
    // CLEANUP
    // ═══════════════════════════════════════════════════════════════════════
    
    dispose() {
        // Remove keyboard event listeners
        if (this._keyboardHandler) {
            document.removeEventListener('keydown', this._keyboardHandler);
            this._keyboardHandler = null;
        }
        if (this._tabHandler) {
            document.removeEventListener('keydown', this._tabHandler);
            this._tabHandler = null;
        }
        
        // Release any active focus trap
        this.releaseFocus();
        
        if (this.announcerElement) {
            this.announcerElement.remove();
        }
        if (this.assertiveAnnouncer) {
            this.assertiveAnnouncer.remove();
        }
        if (this.skipLinkElement) {
            this.skipLinkElement.remove();
        }
        if (this.settingsPanelElement) {
            this.settingsPanelElement.remove();
        }
        if (this.voiceRecognition) {
            this.voiceRecognition.stop();
        }
    }
}

// ═══════════════════════════════════════════════════════════════════════════
// ACCESSIBILITY CSS (injected)
// ═══════════════════════════════════════════════════════════════════════════

export function injectAccessibilityStyles() {
    // Prevent duplicate injection
    if (document.getElementById('accessibility-styles')) {
        return;
    }
    
    const style = document.createElement('style');
    style.id = 'accessibility-styles';
    style.textContent = `
        /* High Contrast Mode */
        body.high-contrast {
            --bg-primary: #000000 !important;
            --text-primary: #FFFFFF !important;
            --accent: #FFFF00 !important;
        }
        
        body.high-contrast canvas {
            filter: contrast(1.5) saturate(1.3);
        }
        
        body.high-contrast #minimap {
            background: #000000 !important;
            border-color: #FFFF00 !important;
        }
        
        body.high-contrast .plaque,
        body.high-contrast .info-panel {
            background: #000000 !important;
            border: 2px solid #FFFF00 !important;
            color: #FFFFFF !important;
        }
        
        /* Reduced Motion */
        body.reduced-motion *,
        body.reduced-motion *::before,
        body.reduced-motion *::after {
            animation-duration: 0.01ms !important;
            animation-iteration-count: 1 !important;
            transition-duration: 0.01ms !important;
        }
        
        /* Large Text */
        body.large-text {
            font-size: 120% !important;
        }
        
        body.large-text .plaque,
        body.large-text .info-panel {
            font-size: 1.2em !important;
        }
        
        /* Screen Reader Mode - Enhanced focus indicators */
        body.screen-reader-mode *:focus {
            outline: 3px solid #FFFF00 !important;
            outline-offset: 2px !important;
        }
        
        body.screen-reader-mode .artwork-interactive:focus {
            box-shadow: 0 0 0 4px #FFFF00 !important;
        }
        
        /* Focus visible polyfill */
        :focus:not(:focus-visible) {
            outline: none;
        }
        
        :focus-visible {
            outline: 2px solid #67D4E4;
            outline-offset: 2px;
        }
    `;
    
    document.head.appendChild(style);
}

export default AccessibilityManager;
