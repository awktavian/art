/**
 * DRY Mesh Protocol - Interactive JavaScript
 *
 * Features:
 * - Animated mesh background
 * - Interactive identity generation
 * - Encryption/decryption demo (simulated)
 * - Vector clock sync visualization
 * - Network topology animation
 * - Live mesh demo
 * - Sound System (synthesized tech sounds)
 * - Discovery System (DRY-humor easter eggs)
 * - Haptic feedback
 *
 * Don't Repeat Yourself. Or your event listeners.
 * (But we did write them all in one place. That's DRY.)
 */

// ============================================================================
// INITIALIZATION
// ============================================================================

// Check for reduced motion preference
const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

// Track animation frame IDs for cleanup
const animationFrames = {
    meshBackground: null,
    liveMeshDemo: null
};

// Track intervals for cleanup
const intervals = {
    circuitBreaker: null,
    idleHint: null
};

document.addEventListener('DOMContentLoaded', () => {
    // Remove loading state
    setTimeout(() => {
        document.body.classList.remove('loading');
    }, 377);

    // Initialize all modules
    initSoundSystem();
    initHaptics();
    initDiscoverySystem();
    initDRYConsole();
    initFontToggle();
    initSoundToggle();
    initMobileMenu();
    if (!prefersReducedMotion) {
        initMeshBackground();
    }
    initRevealAnimations();
    initStatCounters();
    initIdentityDemo();
    initEncryptionDemo();
    initSyncDemo();
    initTopologyVisualization();
    initLiveMeshDemo();
    initCircuitBreakerAnimation();
    initScrollIndicator();
    initScrollMilestone();
    initIdleHints();
    initCopyButtons();
    initEasterEgg();
    initDRYKeyListener();
    initKonamiCode();
    initTopologyClickTracker();
    initCopyCounter();
});

// Pause animations when tab is not visible
document.addEventListener('visibilitychange', () => {
    if (document.hidden) {
        // Cancel animation frames
        if (animationFrames.meshBackground) {
            cancelAnimationFrame(animationFrames.meshBackground);
        }
        if (animationFrames.liveMeshDemo) {
            cancelAnimationFrame(animationFrames.liveMeshDemo);
        }
        // Clear intervals
        if (intervals.circuitBreaker) {
            clearInterval(intervals.circuitBreaker);
        }
    } else {
        // Restart animations when visible again
        if (!prefersReducedMotion) {
            // Animations will restart on next frame request
        }
    }
});

// ============================================================================
// MOBILE MENU
// ============================================================================

function initMobileMenu() {
    const menuBtn = document.getElementById('mobile-menu-btn');
    const navLinks = document.getElementById('nav-links');

    if (!menuBtn || !navLinks) return;

    menuBtn.addEventListener('click', () => {
        const isExpanded = menuBtn.getAttribute('aria-expanded') === 'true';
        menuBtn.setAttribute('aria-expanded', !isExpanded);
        menuBtn.classList.toggle('active');
        navLinks.classList.toggle('active');

        SoundSystem.blip(isExpanded ? 440 : 523.25);
        Haptics.light();

        announce(isExpanded ? 'Navigation menu closed' : 'Navigation menu opened');
    });

    // Close menu when clicking a link
    navLinks.querySelectorAll('.nav-link').forEach(link => {
        link.addEventListener('click', () => {
            menuBtn.setAttribute('aria-expanded', 'false');
            menuBtn.classList.remove('active');
            navLinks.classList.remove('active');
        });
    });
}

// ============================================================================
// SOUND SYSTEM (Web Audio API - Synthesized Tech Sounds)
// ============================================================================

const SoundSystem = {
    ctx: null,
    enabled: true,
    masterGain: null,

    init() {
        // Lazy initialization on first user interaction
        if (this.ctx) return;

        try {
            this.ctx = new (window.AudioContext || window.webkitAudioContext)();
            this.masterGain = this.ctx.createGain();
            this.masterGain.gain.value = 0.3;
            this.masterGain.connect(this.ctx.destination);
        } catch (e) {
            console.log('Web Audio API not available');
        }
    },

    resume() {
        if (this.ctx && this.ctx.state === 'suspended') {
            this.ctx.resume();
        }
    },

    // Digital blip - like data transmission
    blip(frequency = 880, duration = 0.08) {
        if (!this.enabled || !this.ctx) return;
        this.resume();

        const osc = this.ctx.createOscillator();
        const gain = this.ctx.createGain();

        osc.type = 'sine';
        osc.frequency.setValueAtTime(frequency, this.ctx.currentTime);
        osc.frequency.exponentialRampToValueAtTime(frequency * 1.5, this.ctx.currentTime + duration);

        gain.gain.setValueAtTime(0.4, this.ctx.currentTime);
        gain.gain.exponentialRampToValueAtTime(0.01, this.ctx.currentTime + duration);

        osc.connect(gain);
        gain.connect(this.masterGain);

        osc.start();
        osc.stop(this.ctx.currentTime + duration);
    },

    // Encryption sound - digital scramble
    encrypt() {
        if (!this.enabled || !this.ctx) return;
        this.resume();

        // Series of rapid digital blips
        for (let i = 0; i < 6; i++) {
            setTimeout(() => {
                this.blip(440 + Math.random() * 880, 0.04);
            }, i * 50);
        }
    },

    // Key generation sound - ascending tones
    keyGen() {
        if (!this.enabled || !this.ctx) return;
        this.resume();

        const notes = [261.63, 329.63, 392.00, 523.25]; // C4, E4, G4, C5
        notes.forEach((freq, i) => {
            setTimeout(() => {
                this.blip(freq, 0.1);
            }, i * 89);
        });
    },

    // Sync sound - harmonic convergence
    sync() {
        if (!this.enabled || !this.ctx) return;
        this.resume();

        const osc1 = this.ctx.createOscillator();
        const osc2 = this.ctx.createOscillator();
        const gain = this.ctx.createGain();

        osc1.type = 'sine';
        osc2.type = 'sine';
        osc1.frequency.value = 440;
        osc2.frequency.value = 554.37; // Major third

        gain.gain.setValueAtTime(0.2, this.ctx.currentTime);
        gain.gain.exponentialRampToValueAtTime(0.01, this.ctx.currentTime + 0.3);

        osc1.connect(gain);
        osc2.connect(gain);
        gain.connect(this.masterGain);

        osc1.start();
        osc2.start();
        osc1.stop(this.ctx.currentTime + 0.3);
        osc2.stop(this.ctx.currentTime + 0.3);
    },

    // Circuit breaker - warning tone
    circuitOpen() {
        if (!this.enabled || !this.ctx) return;
        this.resume();

        const osc = this.ctx.createOscillator();
        const gain = this.ctx.createGain();

        osc.type = 'sawtooth';
        osc.frequency.setValueAtTime(220, this.ctx.currentTime);
        osc.frequency.exponentialRampToValueAtTime(110, this.ctx.currentTime + 0.2);

        gain.gain.setValueAtTime(0.3, this.ctx.currentTime);
        gain.gain.exponentialRampToValueAtTime(0.01, this.ctx.currentTime + 0.2);

        osc.connect(gain);
        gain.connect(this.masterGain);

        osc.start();
        osc.stop(this.ctx.currentTime + 0.2);
    },

    // Discovery fanfare - triumphant chord
    discovery() {
        if (!this.enabled || !this.ctx) return;
        this.resume();

        const chord = [523.25, 659.25, 783.99, 1046.50]; // C5, E5, G5, C6
        chord.forEach((freq, i) => {
            setTimeout(() => {
                const osc = this.ctx.createOscillator();
                const gain = this.ctx.createGain();

                osc.type = 'sine';
                osc.frequency.value = freq;

                gain.gain.setValueAtTime(0.25, this.ctx.currentTime);
                gain.gain.exponentialRampToValueAtTime(0.01, this.ctx.currentTime + 0.5);

                osc.connect(gain);
                gain.connect(this.masterGain);

                osc.start();
                osc.stop(this.ctx.currentTime + 0.5);
            }, i * 55);
        });
    },

    // Copy sound - quick confirmation
    copy() {
        if (!this.enabled || !this.ctx) return;
        this.resume();
        this.blip(987.77, 0.06); // B5
    },

    // Error/WET sound - dissonant
    wet() {
        if (!this.enabled || !this.ctx) return;
        this.resume();

        const osc1 = this.ctx.createOscillator();
        const osc2 = this.ctx.createOscillator();
        const gain = this.ctx.createGain();

        osc1.type = 'square';
        osc2.type = 'square';
        osc1.frequency.value = 200;
        osc2.frequency.value = 203; // Beating frequency for dissonance

        gain.gain.setValueAtTime(0.15, this.ctx.currentTime);
        gain.gain.exponentialRampToValueAtTime(0.01, this.ctx.currentTime + 0.3);

        osc1.connect(gain);
        osc2.connect(gain);
        gain.connect(this.masterGain);

        osc1.start();
        osc2.start();
        osc1.stop(this.ctx.currentTime + 0.3);
        osc2.stop(this.ctx.currentTime + 0.3);
    },

    // All discoveries complete - celebration
    allComplete() {
        if (!this.enabled || !this.ctx) return;
        this.resume();

        // Triumphant ascending arpeggio
        const notes = [261.63, 329.63, 392.00, 523.25, 659.25, 783.99, 1046.50];
        notes.forEach((freq, i) => {
            setTimeout(() => {
                this.blip(freq, 0.15);
            }, i * 89);
        });
    }
};

function initSoundSystem() {
    SoundSystem.init();

    // Initialize on first user interaction
    document.addEventListener('click', () => SoundSystem.init(), { once: true });
    document.addEventListener('keydown', () => SoundSystem.init(), { once: true });

    // Load saved preference
    const soundPref = localStorage.getItem('kagami_sound_enabled');
    if (soundPref === 'false') {
        SoundSystem.enabled = false;
    }
}

function initSoundToggle() {
    const btn = document.getElementById('sound-toggle-btn');
    if (!btn) return;

    // Set initial state
    if (!SoundSystem.enabled) {
        btn.classList.add('muted');
        btn.querySelector('span').textContent = '🔇';
    }

    btn.addEventListener('click', () => {
        SoundSystem.enabled = !SoundSystem.enabled;
        localStorage.setItem('kagami_sound_enabled', SoundSystem.enabled);

        if (SoundSystem.enabled) {
            btn.classList.remove('muted');
            btn.querySelector('span').textContent = '🔊';
            SoundSystem.blip(); // Confirmation sound
            announce('Sound effects enabled');
        } else {
            btn.classList.add('muted');
            btn.querySelector('span').textContent = '🔇';
            announce('Sound effects disabled');
        }

        Haptics.light();
    });
}

// ============================================================================
// HAPTIC FEEDBACK
// ============================================================================

const Haptics = {
    light() {
        if ('vibrate' in navigator) {
            navigator.vibrate(10);
        }
    },

    medium() {
        if ('vibrate' in navigator) {
            navigator.vibrate(25);
        }
    },

    heavy() {
        if ('vibrate' in navigator) {
            navigator.vibrate(50);
        }
    },

    success() {
        if ('vibrate' in navigator) {
            navigator.vibrate([10, 50, 10, 50, 30]);
        }
    },

    error() {
        if ('vibrate' in navigator) {
            navigator.vibrate([50, 30, 50]);
        }
    },

    discovery() {
        if ('vibrate' in navigator) {
            navigator.vibrate([20, 30, 20, 30, 50, 30, 80]);
        }
    }
};

function initHaptics() {
    // Add haptic feedback to all buttons
    document.querySelectorAll('button, .demo-btn, .sync-btn, .nav-link').forEach(el => {
        el.addEventListener('click', () => Haptics.light());
    });
}

// ============================================================================
// DISCOVERY SYSTEM (DRY-Humor Easter Eggs)
// ============================================================================

const DiscoverySystem = {
    discoveries: {
        'dry-keyword': { found: false, name: 'DRY Devotee', hint: 'Type the magic word...' },
        'wet-keyword': { found: false, name: 'WET Warning', hint: 'What\'s the opposite of DRY?' },
        'konami': { found: false, name: 'Konami Coder', hint: '↑↑↓↓←→←→BA' },
        'kagami-key': { found: false, name: '鏡 Master', hint: 'The mirror has a key...' },
        'all-nodes': { found: false, name: 'Topology Tourist', hint: 'Visit every platform' },
        'triple-copy': { found: false, name: 'Copy Catastrophe', hint: 'DRY violation detected!' },
        'circuit-cycle': { found: false, name: 'Circuit Surfer', hint: 'Ride the state machine' },
        'identity-gen': { found: false, name: 'Identity Crisis', hint: 'Generate 5 identities' }
    },

    totalCount: 8,
    foundCount: 0,

    init() {
        // Load from localStorage
        const saved = localStorage.getItem('kagami_dry_discoveries');
        if (saved) {
            try {
                const parsed = JSON.parse(saved);
                Object.keys(parsed).forEach(key => {
                    if (this.discoveries[key]) {
                        this.discoveries[key].found = parsed[key];
                        if (parsed[key]) this.foundCount++;
                    }
                });
            } catch (e) {
                console.log('Could not load discoveries');
            }
        }
        this.updateCounter();
    },

    discover(id) {
        if (!this.discoveries[id] || this.discoveries[id].found) return false;

        this.discoveries[id].found = true;
        this.foundCount++;

        // Save to localStorage
        const toSave = {};
        Object.keys(this.discoveries).forEach(key => {
            toSave[key] = this.discoveries[key].found;
        });
        localStorage.setItem('kagami_dry_discoveries', JSON.stringify(toSave));

        // Announce
        this.showDiscoveryToast(this.discoveries[id].name);
        SoundSystem.discovery();
        Haptics.discovery();
        this.updateCounter();

        // Check if all complete
        if (this.foundCount === this.totalCount) {
            setTimeout(() => {
                this.showAllCompleteToast();
                SoundSystem.allComplete();
            }, 1000);
        }

        return true;
    },

    updateCounter() {
        const counter = document.getElementById('discovery-counter');
        if (!counter) return;

        const countEl = counter.querySelector('.discovery-count');
        if (countEl) {
            countEl.textContent = `${this.foundCount}/${this.totalCount}`;
        }

        counter.classList.remove('has-discoveries', 'complete');
        if (this.foundCount === this.totalCount) {
            counter.classList.add('complete');
        } else if (this.foundCount > 0) {
            counter.classList.add('has-discoveries');
        }
    },

    showDiscoveryToast(name) {
        let toast = document.querySelector('.dry-hint-toast');
        if (!toast) {
            toast = document.createElement('div');
            toast.className = 'dry-hint-toast';
            document.body.appendChild(toast);
        }

        toast.innerHTML = `
            <div class="hint-title">🔓 Discovery Unlocked!</div>
            <div class="hint-text">${name}</div>
        `;

        toast.classList.add('visible');
        setTimeout(() => toast.classList.remove('visible'), 3000);

        announce(`Discovery unlocked: ${name}`);
    },

    showAllCompleteToast() {
        let toast = document.querySelector('.dry-hint-toast');
        if (!toast) {
            toast = document.createElement('div');
            toast.className = 'dry-hint-toast';
            document.body.appendChild(toast);
        }

        toast.innerHTML = `
            <div class="hint-title">🏆 All Discoveries Complete!</div>
            <div class="hint-text">
                You've found all 8 easter eggs!<br>
                <em>Don't Repeat Yourself... but DO explore everything.</em>
            </div>
        `;

        toast.classList.add('visible');
        setTimeout(() => toast.classList.remove('visible'), 5000);

        announce('Congratulations! All 8 discoveries complete!');
    },

    showHint(id) {
        if (!this.discoveries[id] || this.discoveries[id].found) return;

        let toast = document.querySelector('.dry-hint-toast');
        if (!toast) {
            toast = document.createElement('div');
            toast.className = 'dry-hint-toast';
            document.body.appendChild(toast);
        }

        toast.innerHTML = `
            <div class="hint-title">💡 Hint</div>
            <div class="hint-text">${this.discoveries[id].hint}</div>
        `;

        toast.classList.add('visible');
        setTimeout(() => toast.classList.remove('visible'), 2500);
    }
};

function initDiscoverySystem() {
    DiscoverySystem.init();
}

// ============================================================================
// DRY/WET KEYWORD DETECTION
// ============================================================================

let keyBuffer = '';

function initDRYKeyListener() {
    document.addEventListener('keydown', (e) => {
        // Don't capture if in input field
        if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;

        keyBuffer += e.key.toLowerCase();
        keyBuffer = keyBuffer.slice(-10); // Keep last 10 chars

        // Check for "dry"
        if (keyBuffer.includes('dry')) {
            if (DiscoverySystem.discover('dry-keyword')) {
                showDRYMessage();
            }
            keyBuffer = '';
        }

        // Check for "wet"
        if (keyBuffer.includes('wet')) {
            if (DiscoverySystem.discover('wet-keyword')) {
                showWETMessage();
            } else {
                // Already discovered, just show the message for fun
                showWETMessage();
            }
            keyBuffer = '';
        }
    });
}

function showDRYMessage() {
    const modal = document.createElement('div');
    modal.className = 'easter-egg-modal visible';
    modal.innerHTML = `
        <div class="easter-egg-content">
            <div class="kanji" style="font-size: 4rem;">💧🚫</div>
            <h3 style="color: var(--accent);">Don't Repeat Yourself</h3>
            <p>
                You typed "DRY" — the sacred principle!<br><br>
                <em>Write once. Sync everywhere.</em><br>
                <em>One implementation. Six platforms.</em><br>
                <em>Zero duplicated bugs.</em><br><br>
                <code style="color: var(--success);">// Good code is code you only write once</code>
            </p>
            <div class="dismiss">Press any key to close</div>
        </div>
    `;
    document.body.appendChild(modal);

    const close = () => {
        modal.classList.remove('visible');
        setTimeout(() => modal.remove(), 377);
        document.removeEventListener('keydown', close);
        modal.removeEventListener('click', close);
    };

    setTimeout(() => {
        document.addEventListener('keydown', close, { once: true });
        modal.addEventListener('click', close);
    }, 100);
}

function showWETMessage() {
    SoundSystem.wet();

    const modal = document.createElement('div');
    modal.className = 'easter-egg-modal visible';
    modal.style.setProperty('--accent', '#ef4444');
    modal.innerHTML = `
        <div class="easter-egg-content">
            <div class="kanji" style="font-size: 4rem;">💧💧</div>
            <h3 style="color: #ef4444;">Write Everything Twice?!</h3>
            <p style="color: var(--text-secondary);">
                You typed "WET" — the anti-pattern!<br><br>
                <em style="color: #ef4444;">WET = Write Everything Twice</em><br>
                <em style="color: #ef4444;">WET = We Enjoy Typing</em><br>
                <em style="color: #ef4444;">WET = Waste Everyone's Time</em><br><br>
                <code style="color: #ef4444;">// This is why we can't have nice things</code><br><br>
                <span style="color: var(--success);">Stay DRY, friend. Stay DRY.</span>
            </p>
            <div class="dismiss">Press any key to escape this horror</div>
        </div>
    `;
    document.body.appendChild(modal);

    const close = () => {
        modal.classList.remove('visible');
        setTimeout(() => modal.remove(), 377);
        document.removeEventListener('keydown', close);
        modal.removeEventListener('click', close);
    };

    setTimeout(() => {
        document.addEventListener('keydown', close, { once: true });
        modal.addEventListener('click', close);
    }, 100);
}

// ============================================================================
// KONAMI CODE
// ============================================================================

const konamiSequence = ['ArrowUp', 'ArrowUp', 'ArrowDown', 'ArrowDown', 'ArrowLeft', 'ArrowRight', 'ArrowLeft', 'ArrowRight', 'b', 'a'];
let konamiIndex = 0;

function initKonamiCode() {
    document.addEventListener('keydown', (e) => {
        if (e.key === konamiSequence[konamiIndex] || e.key.toLowerCase() === konamiSequence[konamiIndex]) {
            konamiIndex++;
            if (konamiIndex === konamiSequence.length) {
                konamiIndex = 0;
                if (DiscoverySystem.discover('konami')) {
                    showKonamiMessage();
                }
            }
        } else {
            konamiIndex = 0;
        }
    });
}

function showKonamiMessage() {
    const modal = document.createElement('div');
    modal.className = 'easter-egg-modal visible';
    modal.innerHTML = `
        <div class="easter-egg-content">
            <div class="kanji" style="font-size: 4rem;">🎮</div>
            <h3 style="color: var(--secondary);">↑↑↓↓←→←→BA</h3>
            <p>
                The Konami Code! A classic.<br><br>
                <em>Some things are worth repeating...</em><br>
                <em>...but only input sequences, not code.</em><br><br>
                <code>30 extra lives granted to your mesh network</code>
            </p>
            <div class="dismiss">Press any key to close</div>
        </div>
    `;
    document.body.appendChild(modal);

    const close = () => {
        modal.classList.remove('visible');
        setTimeout(() => modal.remove(), 377);
    };

    setTimeout(() => {
        document.addEventListener('keydown', close, { once: true });
        modal.addEventListener('click', close);
    }, 100);
}

// ============================================================================
// TOPOLOGY CLICK TRACKER
// ============================================================================

const clickedNodes = new Set();

function initTopologyClickTracker() {
    const nodes = document.querySelectorAll('.topology-node');
    nodes.forEach(node => {
        node.addEventListener('click', () => {
            const nodeId = node.id;
            clickedNodes.add(nodeId);
            SoundSystem.blip(440 + clickedNodes.size * 100);
            Haptics.light();

            if (clickedNodes.size === 6) {
                DiscoverySystem.discover('all-nodes');
            }
        });
    });
}

// ============================================================================
// COPY COUNTER (Triple copy = DRY violation!)
// ============================================================================

let copyCount = 0;
let lastCopyTime = 0;

function initCopyCounter() {
    // This will be triggered by the copy button handler
}

function trackCopy() {
    const now = Date.now();
    if (now - lastCopyTime > 5000) {
        copyCount = 0;
    }
    copyCount++;
    lastCopyTime = now;

    if (copyCount >= 3) {
        DiscoverySystem.discover('triple-copy');
        copyCount = 0;
    }
}

// ============================================================================
// DRY CONSOLE MESSAGES
// ============================================================================

function initDRYConsole() {
    const styles = {
        title: 'font-size: 24px; font-weight: bold; color: #00d4ff; text-shadow: 0 0 10px #00d4ff;',
        subtitle: 'font-size: 14px; color: #a855f7; font-style: italic;',
        text: 'font-size: 12px; color: #f0f0f5;',
        code: 'font-size: 12px; color: #22c55e; font-family: monospace; background: #1a1a25; padding: 2px 6px; border-radius: 3px;',
        warning: 'font-size: 12px; color: #f59e0b;',
        joke: 'font-size: 12px; color: #ec4899; font-style: italic;'
    };

    console.log('%c鏡 DRY Mesh Protocol', styles.title);
    console.log('%cDon\'t Repeat Yourself. Or your packets. Or your bugs.', styles.subtitle);
    console.log('');
    console.log('%c📡 Protocol Status:', styles.text);
    console.log('%c  • Ed25519 identity: READY', styles.code);
    console.log('%c  • X25519 key exchange: READY', styles.code);
    console.log('%c  • XChaCha20-Poly1305: READY', styles.code);
    console.log('%c  • Vector Clocks: SYNCHRONIZED', styles.code);
    console.log('%c  • CRDTs: CONFLICT-FREE', styles.code);
    console.log('%c  • Circuit Breaker: CLOSED', styles.code);
    console.log('');
    console.log('%c💡 DRY Wisdom:', styles.text);
    console.log('%c  "Copy-paste is the root of all evil." — Every Senior Dev Ever', styles.joke);
    console.log('%c  "Write once, debug everywhere... wait, that\'s Java." — Anonymous', styles.joke);
    console.log('%c  "The best code is no code. The second best is code you only write once."', styles.joke);
    console.log('');
    console.log('%c🔍 Looking for secrets? There are 8 discoveries hidden in this page.', styles.warning);
    console.log('%c   Hint: Try typing certain keywords, clicking things, or using classic cheat codes...', styles.text);
    console.log('');
    console.log('%c// h(x) ≥ 0. Always.', styles.code);
}

// ============================================================================
// FONT TOGGLE
// ============================================================================

function initFontToggle() {
    const btn = document.getElementById('font-toggle-btn');
    if (!btn) return;

    // Check for existing large text setting
    const isLarge = localStorage.getItem('kagami_large_text') === 'true';
    if (isLarge) {
        document.body.classList.add('large-text');
        btn.classList.add('active');
    }

    btn.addEventListener('click', () => {
        document.body.classList.toggle('large-text');
        const isNowLarge = document.body.classList.contains('large-text');
        localStorage.setItem('kagami_large_text', isNowLarge);

        if (isNowLarge) {
            btn.classList.add('active');
            announce('Large text enabled');
        } else {
            btn.classList.remove('active');
            announce('Normal text size');
        }

        Haptics.light();
        SoundSystem.blip();
    });
}

// ============================================================================
// LIVE REGION ANNOUNCER
// ============================================================================

function announce(message) {
    const announcer = document.getElementById('live-announcer');
    if (announcer) {
        announcer.textContent = message;
        // Clear after announcement
        setTimeout(() => {
            announcer.textContent = '';
        }, 1000);
    }
}

// ============================================================================
// MESH BACKGROUND CANVAS
// ============================================================================

function initMeshBackground() {
    const canvas = document.getElementById('mesh-canvas');
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    let animationId;
    let nodes = [];
    let mouseX = 0;
    let mouseY = 0;

    function resize() {
        canvas.width = window.innerWidth;
        canvas.height = window.innerHeight;
        initNodes();
    }

    function initNodes() {
        nodes = [];
        const nodeCount = Math.floor((canvas.width * canvas.height) / 25000);

        for (let i = 0; i < nodeCount; i++) {
            nodes.push({
                x: Math.random() * canvas.width,
                y: Math.random() * canvas.height,
                vx: (Math.random() - 0.5) * 0.3,
                vy: (Math.random() - 0.5) * 0.3,
                radius: Math.random() * 2 + 1,
                pulse: Math.random() * Math.PI * 2
            });
        }
    }

    function draw() {
        ctx.clearRect(0, 0, canvas.width, canvas.height);

        // Update and draw nodes
        nodes.forEach((node, i) => {
            // Update position
            node.x += node.vx;
            node.y += node.vy;
            node.pulse += 0.02;

            // Bounce off edges
            if (node.x < 0 || node.x > canvas.width) node.vx *= -1;
            if (node.y < 0 || node.y > canvas.height) node.vy *= -1;

            // Keep in bounds
            node.x = Math.max(0, Math.min(canvas.width, node.x));
            node.y = Math.max(0, Math.min(canvas.height, node.y));

            // Mouse attraction (subtle)
            const dx = mouseX - node.x;
            const dy = mouseY - node.y;
            const dist = Math.sqrt(dx * dx + dy * dy);
            if (dist < 200 && dist > 0) {
                node.vx += dx / dist * 0.01;
                node.vy += dy / dist * 0.01;
            }

            // Draw connections
            nodes.forEach((other, j) => {
                if (i >= j) return;
                const dx = other.x - node.x;
                const dy = other.y - node.y;
                const dist = Math.sqrt(dx * dx + dy * dy);

                if (dist < 150) {
                    const alpha = (1 - dist / 150) * 0.15;
                    ctx.beginPath();
                    ctx.strokeStyle = `rgba(0, 212, 255, ${alpha})`;
                    ctx.lineWidth = 1;
                    ctx.moveTo(node.x, node.y);
                    ctx.lineTo(other.x, other.y);
                    ctx.stroke();
                }
            });

            // Draw node
            const pulseSize = 1 + Math.sin(node.pulse) * 0.3;
            ctx.beginPath();
            ctx.fillStyle = `rgba(0, 212, 255, ${0.4 + Math.sin(node.pulse) * 0.2})`;
            ctx.arc(node.x, node.y, node.radius * pulseSize, 0, Math.PI * 2);
            ctx.fill();
        });

        animationFrames.meshBackground = requestAnimationFrame(draw);
    }

    // Event listeners
    window.addEventListener('resize', resize);
    document.addEventListener('mousemove', (e) => {
        mouseX = e.clientX;
        mouseY = e.clientY;
    });

    // Start
    resize();
    draw();
}

// ============================================================================
// SCROLL MILESTONE (Secret at page bottom)
// ============================================================================

let scrollMilestoneReached = false;

function initScrollMilestone() {
    const footer = document.querySelector('.footer');
    if (!footer) return;

    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting && !scrollMilestoneReached) {
                scrollMilestoneReached = true;
                showScrollMilestoneReward();
            }
        });
    }, { threshold: 0.8 });

    observer.observe(footer);
}

function showScrollMilestoneReward() {
    // Create celebratory particles
    createConfetti();

    // Show special message
    let toast = document.querySelector('.dry-hint-toast');
    if (!toast) {
        toast = document.createElement('div');
        toast.className = 'dry-hint-toast';
        document.body.appendChild(toast);
    }

    toast.innerHTML = `
        <div class="hint-title">🎉 You Made It!</div>
        <div class="hint-text">
            You read the whole page.<br>
            <em>That's dedication. Unlike copy-paste, this was worth repeating.</em>
        </div>
    `;

    toast.classList.add('visible');
    SoundSystem.allComplete();
    Haptics.success();

    setTimeout(() => toast.classList.remove('visible'), 5000);

    announce('Congratulations! You reached the end of the page.');
}

function createConfetti() {
    const colors = ['#00d4ff', '#a855f7', '#22c55e', '#f59e0b', '#ec4899'];
    const container = document.createElement('div');
    container.className = 'confetti-container';
    container.style.cssText = 'position: fixed; inset: 0; pointer-events: none; z-index: 9999; overflow: hidden;';
    document.body.appendChild(container);

    for (let i = 0; i < 50; i++) {
        const particle = document.createElement('div');
        particle.style.cssText = `
            position: absolute;
            width: ${Math.random() * 10 + 5}px;
            height: ${Math.random() * 10 + 5}px;
            background: ${colors[Math.floor(Math.random() * colors.length)]};
            left: ${Math.random() * 100}%;
            top: -20px;
            border-radius: ${Math.random() > 0.5 ? '50%' : '2px'};
            animation: confettiFall ${Math.random() * 2 + 2}s ease-out forwards;
            animation-delay: ${Math.random() * 0.5}s;
        `;
        container.appendChild(particle);
    }

    // Add confetti animation if not exists
    if (!document.querySelector('#confetti-styles')) {
        const style = document.createElement('style');
        style.id = 'confetti-styles';
        style.textContent = `
            @keyframes confettiFall {
                0% { transform: translateY(0) rotate(0deg); opacity: 1; }
                100% { transform: translateY(100vh) rotate(720deg); opacity: 0; }
            }
        `;
        document.head.appendChild(style);
    }

    setTimeout(() => container.remove(), 4000);
}

// ============================================================================
// IDLE HINTS (Help users discover easter eggs)
// ============================================================================

let lastInteractionTime = Date.now();
let idleHintShown = false;

function initIdleHints() {
    // Track user interactions
    ['click', 'keydown', 'mousemove', 'touchstart'].forEach(event => {
        document.addEventListener(event, () => {
            lastInteractionTime = Date.now();
        }, { passive: true });
    });

    // Check for idle state periodically
    intervals.idleHint = setInterval(() => {
        const idleTime = Date.now() - lastInteractionTime;
        const discoveryCount = DiscoverySystem.foundCount;

        // Show hint after 90 seconds of idle if not all discoveries found
        if (idleTime > 90000 && !idleHintShown && discoveryCount < 8) {
            showIdleHint();
            idleHintShown = true;
        }

        // Reset hint flag after activity
        if (idleTime < 5000) {
            idleHintShown = false;
        }
    }, 10000);
}

function showIdleHint() {
    const undiscovered = Object.entries(DiscoverySystem.discoveries)
        .filter(([key, val]) => !val.found);

    if (undiscovered.length === 0) return;

    // Pick a random undiscovered hint
    const [key, discovery] = undiscovered[Math.floor(Math.random() * undiscovered.length)];

    let toast = document.querySelector('.dry-hint-toast');
    if (!toast) {
        toast = document.createElement('div');
        toast.className = 'dry-hint-toast';
        document.body.appendChild(toast);
    }

    toast.innerHTML = `
        <div class="hint-title">💡 Psst...</div>
        <div class="hint-text">${discovery.hint}</div>
    `;

    toast.classList.add('visible');
    SoundSystem.blip(330);

    setTimeout(() => toast.classList.remove('visible'), 4000);
}

// ============================================================================
// REVEAL ANIMATIONS
// ============================================================================

function initRevealAnimations() {
    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.classList.add('revealed');
            }
        });
    }, {
        threshold: 0.1,
        rootMargin: '0px 0px -50px 0px'
    });

    document.querySelectorAll('[data-reveal]').forEach(el => {
        observer.observe(el);
    });
}

// ============================================================================
// STAT COUNTERS
// ============================================================================

function initStatCounters() {
    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                animateCounter(entry.target);
                observer.unobserve(entry.target);
            }
        });
    }, { threshold: 0.5 });

    document.querySelectorAll('.stat-value[data-count]').forEach(el => {
        observer.observe(el);
    });
}

function animateCounter(element) {
    const target = parseInt(element.dataset.count);
    const duration = 1597; // Fibonacci
    const start = performance.now();

    function update(currentTime) {
        const elapsed = currentTime - start;
        const progress = Math.min(elapsed / duration, 1);

        // Ease out expo
        const eased = 1 - Math.pow(2, -10 * progress);
        const current = Math.floor(eased * target);

        element.textContent = current;

        if (progress < 1) {
            requestAnimationFrame(update);
        } else {
            element.textContent = target;
        }
    }

    requestAnimationFrame(update);
}

// ============================================================================
// IDENTITY DEMO
// ============================================================================

let identityGenCount = 0;

function initIdentityDemo() {
    const btn = document.getElementById('generate-identity-btn');
    const display = document.getElementById('peer-id-display');

    if (!btn || !display) return;

    btn.addEventListener('click', () => {
        // Generate a fake Ed25519 public key (64 hex chars = 32 bytes)
        const peerId = generateRandomHex(64);
        display.textContent = peerId;

        // Track identity generation for discovery
        identityGenCount++;
        if (identityGenCount >= 5) {
            DiscoverySystem.discover('identity-gen');
        }

        // Sound and haptics
        SoundSystem.keyGen();
        Haptics.medium();

        // Animation
        display.style.animation = 'none';
        display.offsetHeight; // Trigger reflow
        display.style.animation = 'fadeInUp 377ms ease-out';

        announce(`New identity generated. ${5 - identityGenCount > 0 ? (5 - identityGenCount) + ' more for discovery.' : 'Identity Crisis unlocked!'}`);
    });
}

function generateRandomHex(length) {
    const chars = '0123456789abcdef';
    let result = '';
    for (let i = 0; i < length; i++) {
        result += chars[Math.floor(Math.random() * 16)];
    }
    return result;
}

// ============================================================================
// ENCRYPTION DEMO
// ============================================================================

let encryptionKey = null;
let lastCiphertext = null;

function initEncryptionDemo() {
    const encryptBtn = document.getElementById('encrypt-btn');
    const decryptBtn = document.getElementById('decrypt-btn');
    const plaintext = document.getElementById('plaintext-input');
    const cipherOutput = document.getElementById('ciphertext-output');
    const keyDisplay = document.getElementById('shared-key-display');

    if (!encryptBtn || !decryptBtn) return;

    // Generate initial key
    encryptionKey = generateRandomHex(64);
    keyDisplay.textContent = encryptionKey.substring(0, 16) + '...';

    encryptBtn.addEventListener('click', async () => {
        const text = plaintext.value || 'Hello, Mesh!';

        // Disable buttons during animation
        encryptBtn.disabled = true;
        decryptBtn.disabled = true;
        encryptBtn.style.opacity = '0.6';
        decryptBtn.style.opacity = '0.6';

        // Simulate XChaCha20-Poly1305 encryption with visual effect
        const nonce = generateRandomHex(48);
        const fakeTag = generateRandomHex(32);
        const textHex = stringToHex(text);
        lastCiphertext = nonce + textHex + fakeTag;

        // Sound and haptics
        SoundSystem.encrypt();
        Haptics.medium();

        // Scrambling animation - show random hex that converges to final
        const finalLength = lastCiphertext.length;
        const scrambleDuration = 610; // Fibonacci
        const steps = 12;

        for (let i = 0; i < steps; i++) {
            await new Promise(resolve => setTimeout(resolve, scrambleDuration / steps));

            // Gradually reveal more of the real ciphertext
            const revealRatio = i / (steps - 1);
            const revealChars = Math.floor(finalLength * revealRatio);
            const scrambled = lastCiphertext.substring(0, revealChars) +
                              generateRandomHex(finalLength - revealChars);

            cipherOutput.textContent = scrambled;
            cipherOutput.style.color = 'var(--warning)';
        }

        // Final reveal
        cipherOutput.textContent = lastCiphertext;
        cipherOutput.style.color = 'var(--success)';

        // Re-enable buttons
        encryptBtn.disabled = false;
        decryptBtn.disabled = false;
        encryptBtn.style.opacity = '1';
        decryptBtn.style.opacity = '1';

        announce('Message encrypted with XChaCha20-Poly1305');
    });

    decryptBtn.addEventListener('click', () => {
        if (!lastCiphertext) {
            cipherOutput.textContent = 'Nothing to decrypt!';
            cipherOutput.style.color = 'var(--error)';
            SoundSystem.wet();
            Haptics.error();
            return;
        }

        // "Decrypt" by extracting the middle part
        const nonce = lastCiphertext.substring(0, 48);
        const tag = lastCiphertext.substring(lastCiphertext.length - 32);
        const cipherHex = lastCiphertext.substring(48, lastCiphertext.length - 32);

        const decrypted = hexToString(cipherHex);
        plaintext.value = decrypted;
        cipherOutput.textContent = `Decrypted: "${decrypted}"`;
        cipherOutput.style.color = 'var(--accent)';

        // Sound and haptics
        SoundSystem.blip(523.25); // C5 - success tone
        Haptics.success();
        announce(`Decrypted: ${decrypted}`);
    });
}

function stringToHex(str) {
    return Array.from(str)
        .map(c => c.charCodeAt(0).toString(16).padStart(2, '0'))
        .join('');
}

function hexToString(hex) {
    let result = '';
    for (let i = 0; i < hex.length; i += 2) {
        result += String.fromCharCode(parseInt(hex.substr(i, 2), 16));
    }
    return result;
}

// ============================================================================
// SYNC DEMO (VECTOR CLOCKS)
// ============================================================================

let vectorClocks = {
    phone: 0,
    hub: 0
};

function initSyncDemo() {
    const phoneClock = document.getElementById('phone-clock');
    const hubClock = document.getElementById('hub-clock');
    const mergedClock = document.getElementById('merged-clock');
    const syncStatus = document.getElementById('sync-status');
    const syncArrow = document.getElementById('sync-arrow');
    const container = document.querySelector('.sync-demo-container');

    document.querySelectorAll('.sync-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            const node = btn.dataset.node;
            const prevValue = vectorClocks[node];
            vectorClocks[node]++;

            updateClockDisplay(node);
            animateSync(node);
            animateDataPacket(node, container);

            // Sound and haptics
            SoundSystem.sync();
            Haptics.light();
        });
    });

    function updateClockDisplay(changedNode) {
        // Highlight the changed value
        const phoneEl = phoneClock;
        const hubEl = hubClock;

        phoneEl.textContent = vectorClocks.phone;
        hubEl.textContent = vectorClocks.hub;

        // Flash the changed node
        const changedEl = changedNode === 'phone' ? phoneEl : hubEl;
        changedEl.style.color = 'var(--success)';
        changedEl.style.textShadow = '0 0 10px var(--success)';
        setTimeout(() => {
            changedEl.style.color = '';
            changedEl.style.textShadow = '';
        }, 377);

        // Update merged with highlighting
        const mergedStr = `{ "phone": ${vectorClocks.phone}, "hub": ${vectorClocks.hub} }`;
        mergedClock.innerHTML = mergedStr.replace(
            new RegExp(`"${changedNode}": ${vectorClocks[changedNode]}`),
            `<span style="color: var(--success); text-shadow: 0 0 8px var(--success);">"${changedNode}": ${vectorClocks[changedNode]}</span>`
        );

        // Clear highlight after delay
        setTimeout(() => {
            mergedClock.textContent = mergedStr;
        }, 987);
    }

    function animateSync(sourceNode) {
        syncStatus.textContent = 'Syncing...';
        syncStatus.style.color = 'var(--warning)';
        syncArrow.style.animation = 'none';
        syncArrow.offsetHeight;
        syncArrow.style.animation = 'pulse 233ms ease-out 3';

        setTimeout(() => {
            syncStatus.textContent = 'Synced';
            syncStatus.style.color = 'var(--success)';
        }, 699);
    }

    function animateDataPacket(sourceNode, container) {
        // Create floating data packet
        const packet = document.createElement('div');
        packet.style.cssText = `
            position: absolute;
            width: 12px;
            height: 12px;
            background: var(--accent);
            border-radius: 50%;
            box-shadow: 0 0 15px var(--accent);
            pointer-events: none;
            z-index: 10;
        `;

        const containerRect = container.getBoundingClientRect();
        const sourceNode1 = document.getElementById('sync-node-1');
        const sourceNode2 = document.getElementById('sync-node-2');
        const mergedEl = document.querySelector('.sync-merged');

        const sourceEl = sourceNode === 'phone' ? sourceNode1 : sourceNode2;
        const sourceRect = sourceEl.getBoundingClientRect();
        const targetRect = mergedEl.getBoundingClientRect();

        // Calculate positions relative to container
        const startX = sourceRect.left + sourceRect.width / 2 - containerRect.left;
        const startY = sourceRect.bottom - containerRect.top;
        const endX = targetRect.left + targetRect.width / 2 - containerRect.left;
        const endY = targetRect.top - containerRect.top;

        packet.style.left = `${startX}px`;
        packet.style.top = `${startY}px`;

        container.style.position = 'relative';
        container.appendChild(packet);

        // Animate to merged clock
        packet.animate([
            { left: `${startX}px`, top: `${startY}px`, opacity: 1 },
            { left: `${endX}px`, top: `${endY}px`, opacity: 1 }
        ], {
            duration: 377,
            easing: 'ease-out',
            fill: 'forwards'
        }).onfinish = () => {
            // Burst effect
            packet.animate([
                { transform: 'scale(1)', opacity: 1 },
                { transform: 'scale(2)', opacity: 0 }
            ], {
                duration: 233,
                easing: 'ease-out'
            }).onfinish = () => packet.remove();
        };
    }
}

// ============================================================================
// TOPOLOGY VISUALIZATION
// ============================================================================

function initTopologyVisualization() {
    const diagram = document.querySelector('.topology-diagram');
    if (!diagram) return;

    // Draw SVG lines between nodes
    drawTopologyLines();

    // Add hover effects with data packets
    const nodes = diagram.querySelectorAll('.topology-node');
    nodes.forEach(node => {
        node.addEventListener('mouseenter', () => {
            if (node.classList.contains('topology-hub')) {
                // Pulse all connections
                pulseAllConnections();
            }
        });
    });
}

function drawTopologyLines() {
    // This would draw SVG lines between the hub and other nodes
    // For simplicity, we'll add a visual indicator using CSS animations
    const diagram = document.querySelector('.topology-diagram');
    if (!diagram) return;

    // Create SVG overlay
    const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    svg.style.cssText = 'position: absolute; inset: 0; width: 100%; height: 100%; pointer-events: none;';
    diagram.insertBefore(svg, diagram.firstChild);

    // Get node positions (approximated for demo)
    const connections = [
        { from: 'hub', to: 'ios', color: '#a855f7' },
        { from: 'hub', to: 'android', color: '#22c55e' },
        { from: 'hub', to: 'desktop', color: '#f59e0b' },
        { from: 'hub', to: 'watch', color: '#ec4899' },
        { from: 'hub', to: 'vision', color: '#8b5cf6' }
    ];

    // Draw animated dashed lines
    const hubX = 50, hubY = 50; // percentages

    const nodePositions = {
        ios: { x: 20, y: 15 },
        android: { x: 80, y: 15 },
        desktop: { x: 50, y: 85 },
        watch: { x: 15, y: 75 },
        vision: { x: 85, y: 75 }
    };

    connections.forEach((conn, i) => {
        const line = document.createElementNS('http://www.w3.org/2000/svg', 'line');
        const toPos = nodePositions[conn.to];

        line.setAttribute('x1', `${hubX}%`);
        line.setAttribute('y1', `${hubY}%`);
        line.setAttribute('x2', `${toPos.x}%`);
        line.setAttribute('y2', `${toPos.y}%`);
        line.setAttribute('stroke', conn.color);
        line.setAttribute('stroke-width', '2');
        line.setAttribute('stroke-dasharray', '5,5');
        line.setAttribute('opacity', '0.4');
        line.style.animation = `dashMove ${1597 + i * 144}ms linear infinite`;

        svg.appendChild(line);
    });

    // Add dash animation
    const style = document.createElement('style');
    style.textContent = `
        @keyframes dashMove {
            from { stroke-dashoffset: 0; }
            to { stroke-dashoffset: -20; }
        }
    `;
    document.head.appendChild(style);
}

function pulseAllConnections() {
    const lines = document.querySelectorAll('.topology-diagram line');
    lines.forEach(line => {
        line.style.opacity = '0.8';
        setTimeout(() => {
            line.style.opacity = '0.4';
        }, 377);
    });
}

// ============================================================================
// LIVE MESH DEMO
// ============================================================================

let meshNodes = [];
let meshMessages = [];
let meshLog = [];

function initLiveMeshDemo() {
    const canvas = document.getElementById('demo-mesh-canvas');
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    const logContainer = document.getElementById('demo-log');

    // Set canvas size
    function resizeCanvas() {
        const rect = canvas.parentElement.getBoundingClientRect();
        canvas.width = rect.width - 32; // Account for padding
        canvas.height = 400;
    }

    resizeCanvas();
    window.addEventListener('resize', resizeCanvas);

    // Initialize with hub node
    meshNodes = [{
        id: 'hub',
        x: canvas.width / 2,
        y: canvas.height / 2,
        color: '#00d4ff',
        label: 'Hub',
        status: 'online'
    }];

    addLog('Mesh initialized. Hub online.');

    // Button handlers
    document.getElementById('add-node-btn')?.addEventListener('click', () => {
        const nodeTypes = ['ios', 'android', 'desktop', 'watch', 'vision'];
        const colors = ['#a855f7', '#22c55e', '#f59e0b', '#ec4899', '#8b5cf6'];
        const labels = ['iPhone', 'Android', 'Desktop', 'Watch', 'Vision'];

        const index = meshNodes.length - 1;
        if (index >= nodeTypes.length) {
            addLog('Maximum nodes reached.');
            return;
        }

        const angle = (index / nodeTypes.length) * Math.PI * 2 - Math.PI / 2;
        const radius = 150;

        meshNodes.push({
            id: nodeTypes[index],
            x: canvas.width / 2 + Math.cos(angle) * radius,
            y: canvas.height / 2 + Math.sin(angle) * radius,
            color: colors[index],
            label: labels[index],
            status: 'connecting'
        });

        addLog(`${labels[index]} joining mesh...`);

        setTimeout(() => {
            meshNodes[meshNodes.length - 1].status = 'online';
            addLog(`${labels[index]} connected. Ed25519 handshake complete.`);
        }, 610);
    });

    document.getElementById('send-message-btn')?.addEventListener('click', () => {
        if (meshNodes.length < 2) {
            addLog('Add more nodes to send messages.');
            return;
        }

        // Send message from random node to hub
        const sender = meshNodes[Math.floor(Math.random() * (meshNodes.length - 1)) + 1];
        const receiver = meshNodes[0]; // hub

        meshMessages.push({
            from: { x: sender.x, y: sender.y },
            to: { x: receiver.x, y: receiver.y },
            progress: 0,
            color: sender.color
        });

        addLog(`${sender.label} → Hub: [encrypted] XChaCha20-Poly1305`);
    });

    document.getElementById('simulate-failure-btn')?.addEventListener('click', () => {
        if (meshNodes.length < 2) {
            addLog('No nodes to fail.');
            return;
        }

        const node = meshNodes[meshNodes.length - 1];
        node.status = 'failed';
        addLog(`Circuit breaker OPEN: ${node.label} connection lost.`);

        setTimeout(() => {
            node.status = 'recovering';
            addLog(`Circuit breaker HALF-OPEN: Testing ${node.label}...`);
        }, 1597);

        setTimeout(() => {
            node.status = 'online';
            addLog(`Circuit breaker CLOSED: ${node.label} recovered.`);
        }, 2584);
    });

    document.getElementById('reset-mesh-btn')?.addEventListener('click', () => {
        meshNodes = [{
            id: 'hub',
            x: canvas.width / 2,
            y: canvas.height / 2,
            color: '#00d4ff',
            label: 'Hub',
            status: 'online'
        }];
        meshMessages = [];
        meshLog = [];
        logContainer.innerHTML = '';
        addLog('Mesh reset. Hub online.');
    });

    function addLog(message) {
        const time = new Date().toLocaleTimeString('en-US', {
            hour12: false,
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit'
        });

        const entry = document.createElement('div');
        entry.className = 'log-entry';
        entry.innerHTML = `
            <span class="log-time">${time}</span>
            <span class="log-message">${message}</span>
        `;

        logContainer.appendChild(entry);
        logContainer.scrollTop = logContainer.scrollHeight;
    }

    // Animation loop
    function animate() {
        ctx.clearRect(0, 0, canvas.width, canvas.height);

        // Draw connections
        meshNodes.forEach((node, i) => {
            if (i === 0) return; // Skip hub

            ctx.beginPath();
            ctx.strokeStyle = node.status === 'online' ? 'rgba(0, 212, 255, 0.3)' :
                              node.status === 'failed' ? 'rgba(239, 68, 68, 0.3)' :
                              'rgba(245, 158, 11, 0.3)';
            ctx.setLineDash([5, 5]);
            ctx.moveTo(meshNodes[0].x, meshNodes[0].y);
            ctx.lineTo(node.x, node.y);
            ctx.stroke();
            ctx.setLineDash([]);
        });

        // Draw nodes
        meshNodes.forEach(node => {
            // Glow
            const gradient = ctx.createRadialGradient(
                node.x, node.y, 0,
                node.x, node.y, 30
            );
            gradient.addColorStop(0, node.status === 'online' ? node.color + '40' :
                                       node.status === 'failed' ? '#ef444440' : '#f59e0b40');
            gradient.addColorStop(1, 'transparent');
            ctx.fillStyle = gradient;
            ctx.beginPath();
            ctx.arc(node.x, node.y, 30, 0, Math.PI * 2);
            ctx.fill();

            // Node circle
            ctx.beginPath();
            ctx.fillStyle = node.status === 'online' ? node.color :
                           node.status === 'failed' ? '#ef4444' : '#f59e0b';
            ctx.arc(node.x, node.y, 15, 0, Math.PI * 2);
            ctx.fill();

            // Border
            ctx.strokeStyle = node.status === 'online' ? node.color :
                             node.status === 'failed' ? '#ef4444' : '#f59e0b';
            ctx.lineWidth = 2;
            ctx.stroke();

            // Label
            ctx.fillStyle = '#f0f0f5';
            ctx.font = '12px JetBrains Mono, monospace';
            ctx.textAlign = 'center';
            ctx.fillText(node.label, node.x, node.y + 35);
        });

        // Draw and update messages
        meshMessages = meshMessages.filter(msg => {
            msg.progress += 0.02;

            if (msg.progress >= 1) return false;

            const x = msg.from.x + (msg.to.x - msg.from.x) * msg.progress;
            const y = msg.from.y + (msg.to.y - msg.from.y) * msg.progress;

            // Packet glow
            const gradient = ctx.createRadialGradient(x, y, 0, x, y, 8);
            gradient.addColorStop(0, msg.color);
            gradient.addColorStop(1, 'transparent');
            ctx.fillStyle = gradient;
            ctx.beginPath();
            ctx.arc(x, y, 8, 0, Math.PI * 2);
            ctx.fill();

            // Packet
            ctx.beginPath();
            ctx.fillStyle = msg.color;
            ctx.arc(x, y, 4, 0, Math.PI * 2);
            ctx.fill();

            return true;
        });

        requestAnimationFrame(animate);
    }

    animate();
}

// ============================================================================
// CIRCUIT BREAKER ANIMATION
// ============================================================================

let circuitCycleCount = 0;

function initCircuitBreakerAnimation() {
    const states = document.querySelectorAll('.circuit-state');
    if (states.length === 0) return;

    let currentState = 0;

    function highlightState(index) {
        states.forEach((state, i) => {
            if (i === index) {
                state.style.transform = 'scale(1.1)';
                state.style.boxShadow = '0 0 20px ' + getComputedStyle(state).borderColor;
            } else {
                state.style.transform = 'scale(1)';
                state.style.boxShadow = 'none';
            }
        });
    }

    // Make states clickable for manual cycling
    states.forEach((state, i) => {
        state.style.cursor = 'pointer';
        state.addEventListener('click', () => {
            currentState = i;
            highlightState(currentState);

            // Track full cycles for discovery
            if (i === 0) {
                circuitCycleCount++;
                if (circuitCycleCount >= 3) {
                    DiscoverySystem.discover('circuit-cycle');
                }
            }

            // Sound based on state
            if (i === 0) {
                SoundSystem.blip(523.25); // Success tone for Closed
            } else if (i === 1) {
                SoundSystem.circuitOpen();
            } else {
                SoundSystem.blip(440); // Warning tone for HalfOpen
            }
            Haptics.light();
        });
    });

    // Auto-cycle through states (only if not preferring reduced motion)
    if (!prefersReducedMotion) {
        intervals.circuitBreaker = setInterval(() => {
            currentState = (currentState + 1) % 3;
            highlightState(currentState);

            // Track auto cycles too
            if (currentState === 0) {
                circuitCycleCount++;
                if (circuitCycleCount >= 3) {
                    DiscoverySystem.discover('circuit-cycle');
                }
            }
        }, 2584);
    }
}

// ============================================================================
// SCROLL INDICATOR
// ============================================================================

function initScrollIndicator() {
    const indicator = document.querySelector('.scroll-indicator');
    if (!indicator) return;

    indicator.addEventListener('click', () => {
        const firstSection = document.querySelector('.section');
        if (firstSection) {
            firstSection.scrollIntoView({ behavior: 'smooth' });
        }
    });

    // Hide on scroll
    let hidden = false;
    window.addEventListener('scroll', () => {
        if (window.scrollY > 100 && !hidden) {
            indicator.style.opacity = '0';
            hidden = true;
        } else if (window.scrollY <= 100 && hidden) {
            indicator.style.opacity = '1';
            hidden = false;
        }
    });
}

// ============================================================================
// UTILITY: Smooth scroll for nav links
// ============================================================================

document.querySelectorAll('a[href^="#"]').forEach(anchor => {
    anchor.addEventListener('click', function(e) {
        e.preventDefault();
        const target = document.querySelector(this.getAttribute('href'));
        if (target) {
            target.scrollIntoView({
                behavior: 'smooth',
                block: 'start'
            });
        }
    });
});

// ============================================================================
// COPY TO CLIPBOARD
// ============================================================================

function initCopyButtons() {
    document.querySelectorAll('.copy-btn').forEach(btn => {
        btn.addEventListener('click', async () => {
            // Find the associated value element
            let valueElement;
            if (btn.id === 'copy-peer-id') {
                valueElement = document.getElementById('peer-id-display');
            } else if (btn.id === 'copy-shared-key') {
                valueElement = document.getElementById('shared-key-display');
            }

            if (!valueElement) return;

            const text = valueElement.textContent;
            if (text === 'Click to generate...' || text === 'Not generated') {
                announce('Nothing to copy yet. Generate a value first.');
                SoundSystem.wet();
                Haptics.error();
                return;
            }

            try {
                await navigator.clipboard.writeText(text);
                btn.classList.add('copied');

                // Track copies for DRY violation discovery
                trackCopy();

                // Sound and haptics
                SoundSystem.copy();
                Haptics.light();

                announce('Copied to clipboard');

                // Reset after animation
                setTimeout(() => {
                    btn.classList.remove('copied');
                }, 1597);
            } catch (err) {
                console.error('Failed to copy:', err);
                announce('Failed to copy to clipboard');
                SoundSystem.wet();
                Haptics.error();
            }
        });
    });
}

// ============================================================================
// EASTER EGG
// ============================================================================

function initEasterEgg() {
    // Create modal
    const modal = document.createElement('div');
    modal.className = 'easter-egg-modal';
    modal.innerHTML = `
        <div class="easter-egg-content">
            <div class="kanji">鏡</div>
            <h3>Kagami</h3>
            <p>
                The mirror reflects truth. The mesh connects all.<br>
                One protocol. Every device. Zero redundancy.<br><br>
                <em>Don't Repeat Yourself.</em><br>
                <em>Let the mesh remember.</em>
            </p>
            <div class="dismiss">Press any key to close</div>
        </div>
    `;
    document.body.appendChild(modal);

    // Key listener for 'k'
    document.addEventListener('keydown', (e) => {
        if (e.key === 'k' && !modal.classList.contains('visible')) {
            modal.classList.add('visible');

            // Trigger discovery
            DiscoverySystem.discover('kagami-key');

            announce('Easter egg revealed: Kagami, the mirror');
        } else if (modal.classList.contains('visible')) {
            modal.classList.remove('visible');
        }
    });

    // Click to close
    modal.addEventListener('click', () => {
        modal.classList.remove('visible');
    });
}

/*
 * 鏡
 * DRY Mesh Protocol: Don't Repeat Yourself. Or your JavaScript.
 * h(x) >= 0. Always.
 */
