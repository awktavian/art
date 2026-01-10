/**
 * What About the Weather? — Interactive Celestial System
 * POLISHED TO PERFECTION
 * 
 * Demonstrates:
 * - Sun position calculation (ephemeris)
 * - Window orientation and glare intensity
 * - Shade level optimization
 * - Weather integration
 * 
 * Delight:
 * - Custom cursor with hover states
 * - Floating particles
 * - Count-up animations
 * - Reveal animations
 * - Konami code easter egg
 * - Console API
 * 
 * For engineers building agentic systems.
 */

'use strict';

// ============================================================================
// CONSTANTS
// ============================================================================

const HOME = {
    latitude: 47.6799,
    longitude: -122.3410,
    timezone: 'America/Los_Angeles'
};

const DIRECTIONS = {
    SOUTH: { azimuth: 180, name: 'South (Lake)', color: '#FF9F40' },
    NORTH: { azimuth: 0, name: 'North (Alley)', color: '#64D9FF' },
    EAST: { azimuth: 90, name: 'East', color: '#FFD93D' },
    WEST: { azimuth: 270, name: 'West', color: '#FF6B6B' }
};

const SHADES = [
    { id: 235, name: 'Living South', room: 'Living Room', facing: 'SOUTH' },
    { id: 237, name: 'Living East', room: 'Living Room', facing: 'EAST' },
    { id: 243, name: 'Dining South', room: 'Dining', facing: 'SOUTH' },
    { id: 241, name: 'Dining Slider', room: 'Dining', facing: 'SOUTH', binary: true },
    { id: 229, name: 'Entry', room: 'Entry', facing: 'SOUTH' },
    { id: 66, name: 'Primary North', room: 'Primary Bed', facing: 'NORTH' },
    { id: 68, name: 'Primary West', room: 'Primary Bed', facing: 'WEST' },
    { id: 353, name: 'Primary Bath R', room: 'Primary Bath', facing: 'NORTH' },
    { id: 355, name: 'Primary Bath L', room: 'Primary Bath', facing: 'NORTH' },
    { id: 359, name: 'Bed 4 Right', room: 'Bed 4', facing: 'WEST' },
    { id: 361, name: 'Bed 4 Left', room: 'Bed 4', facing: 'WEST' }
];

// Fibonacci timing (ms)
const TIMING = {
    MICRO: 89,
    SHORT: 144,
    NORMAL: 233,
    MEDIUM: 377,
    LONG: 610,
    SLOW: 987,
    SLOWER: 1597,
    BREATHING: 2584
};

// Konami code
const KONAMI = ['ArrowUp', 'ArrowUp', 'ArrowDown', 'ArrowDown', 'ArrowLeft', 'ArrowRight', 'ArrowLeft', 'ArrowRight', 'b', 'a'];

// ============================================================================
// SECRET LOCATIONS — Easter Egg Destinations
// ============================================================================

const SECRET_LOCATIONS = {
    home: {
        name: 'Green Lake',
        address: '7331 W Green Lake Dr N',
        city: 'Seattle',
        postcode: '98103',
        country: 'USA',
        latitude: 47.6799,
        longitude: -122.3410,
        timezone: 'America/Los_Angeles',
        description: 'Home. Where the heart is. Where the smart home knows your name.',
        trivia: [
            'Green Lake: 2.8 miles around, perfect for morning runs',
            'The Crescent Collection — Farmhouse Elevation',
            'KEF Reference speakers because you hear the difference',
            'Lelit Bianca for morning rituals',
            'Where 41 lights, 11 shades, and 26 audio zones await'
        ],
        emoji: '🏠'
    },
    monmouth: {
        name: 'Monmouth Coffee Company',
        address: '27 Monmouth Street, Covent Garden',
        city: 'London',
        postcode: 'WC2H 9EU',
        country: 'UK',
        latitude: 51.5143,
        longitude: -0.1268,
        timezone: 'Europe/London',
        founded: 1978,
        founders: 'Nicholas Saunders & Anita Le Roy',
        description: 'Pioneer of London\'s specialty coffee scene. Coffee roasted in the basement since 1978.',
        trivia: [
            'Founded in 1978, one of London\'s first specialty coffee roasters',
            'Originally roasted coffee in the basement of 27 Monmouth Street',
            'Helped revitalize the Neal\'s Yard area of Covent Garden',
            'A cornerstone of London\'s third wave coffee movement',
            'The queue outside is legendary — worth every minute'
        ],
        emoji: '☕'
    }
};

// ============================================================================
// ACCESSIBILITY — Reduced Motion Preference
// ============================================================================

const MotionPreference = {
    _prefersReduced: null,
    _listeners: [],

    /**
     * Check if user prefers reduced motion
     * @returns {boolean}
     */
    get prefersReduced() {
        if (this._prefersReduced === null) {
            this._prefersReduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

            // Listen for changes
            window.matchMedia('(prefers-reduced-motion: reduce)').addEventListener('change', (e) => {
                this._prefersReduced = e.matches;
                this._notifyListeners();
                console.log(`%c[A11y] Reduced motion: ${e.matches ? 'enabled' : 'disabled'}`,
                    `color: ${e.matches ? '#FFAB40' : '#4ECB71'};`);
            });
        }
        return this._prefersReduced;
    },

    /**
     * Add listener for motion preference changes
     */
    addListener(callback) {
        this._listeners.push(callback);
    },

    /**
     * Notify all listeners of preference change
     */
    _notifyListeners() {
        this._listeners.forEach(cb => cb(this._prefersReduced));
    },

    /**
     * Run animation only if motion is allowed
     * @param {Function} animateFn - Function to run if motion allowed
     * @param {Function} [fallbackFn] - Optional fallback for reduced motion
     */
    animate(animateFn, fallbackFn = null) {
        if (this.prefersReduced) {
            if (fallbackFn) fallbackFn();
            return false;
        }
        animateFn();
        return true;
    }
};

// WMO Weather Codes (Open-Meteo)
const WMO_CODES = {
    0: 'clear',
    1: 'mostly_clear', 2: 'partly_cloudy', 3: 'overcast',
    45: 'fog', 48: 'fog',
    51: 'drizzle', 53: 'drizzle', 55: 'drizzle',
    56: 'freezing_drizzle', 57: 'freezing_drizzle',
    61: 'rain', 63: 'rain', 65: 'heavy_rain',
    66: 'freezing_rain', 67: 'freezing_rain',
    71: 'snow', 73: 'snow', 75: 'heavy_snow',
    77: 'snow_grains',
    80: 'showers', 81: 'showers', 82: 'heavy_showers',
    85: 'snow_showers', 86: 'snow_showers',
    95: 'thunderstorm', 96: 'thunderstorm', 99: 'thunderstorm'
};

// ============================================================================
// SOUND DESIGN — Subtle audio feedback
// ============================================================================

class SoundDesign {
    constructor() {
        this.context = null;
        this.enabled = false;
        this.masterGain = null;
        this.initialized = false;
        this.frequencyMod = 1; // Modified by WeatherAtmosphere
    }

    async init() {
        if (this.initialized) return;

        // Only initialize on user interaction
        try {
            this.context = new (window.AudioContext || window.webkitAudioContext)();
            this.masterGain = this.context.createGain();
            this.masterGain.gain.value = 0.15; // Subtle volume
            this.masterGain.connect(this.context.destination);
            this.initialized = true;
            this.enabled = true;
        } catch (e) {
            console.log('Audio not supported');
        }
    }

    // Soft click sound for interactions
    playClick() {
        if (!this.enabled || !this.context) return;

        const osc = this.context.createOscillator();
        const gain = this.context.createGain();

        osc.type = 'sine';
        osc.frequency.setValueAtTime(800 * this.frequencyMod, this.context.currentTime);
        osc.frequency.exponentialRampToValueAtTime(400 * this.frequencyMod, this.context.currentTime + 0.05);

        gain.gain.setValueAtTime(0.3, this.context.currentTime);
        gain.gain.exponentialRampToValueAtTime(0.01, this.context.currentTime + 0.05);

        osc.connect(gain);
        gain.connect(this.masterGain);

        osc.start();
        osc.stop(this.context.currentTime + 0.05);
    }

    // Warm hover tone
    playHover() {
        if (!this.enabled || !this.context) return;

        const osc = this.context.createOscillator();
        const gain = this.context.createGain();

        osc.type = 'sine';
        osc.frequency.setValueAtTime(600 * this.frequencyMod, this.context.currentTime);

        gain.gain.setValueAtTime(0.1, this.context.currentTime);
        gain.gain.exponentialRampToValueAtTime(0.01, this.context.currentTime + 0.1);

        osc.connect(gain);
        gain.connect(this.masterGain);

        osc.start();
        osc.stop(this.context.currentTime + 0.1);
    }

    // Slider movement - pitch changes with value
    playSlider(normalizedValue) {
        if (!this.enabled || !this.context) return;

        const osc = this.context.createOscillator();
        const gain = this.context.createGain();

        osc.type = 'sine';
        // Map 0-1 to 300-600 Hz, modified by atmosphere
        const freq = (300 + (normalizedValue * 300)) * this.frequencyMod;
        osc.frequency.setValueAtTime(freq, this.context.currentTime);

        gain.gain.setValueAtTime(0.08, this.context.currentTime);
        gain.gain.exponentialRampToValueAtTime(0.01, this.context.currentTime + 0.03);

        osc.connect(gain);
        gain.connect(this.masterGain);

        osc.start();
        osc.stop(this.context.currentTime + 0.03);
    }

    // Success/unlock chime for Konami
    playSuccess() {
        if (!this.enabled || !this.context) return;

        const notes = [523.25, 659.25, 783.99, 1046.50]; // C5, E5, G5, C6
        const duration = 0.15;

        notes.forEach((freq, i) => {
            const osc = this.context.createOscillator();
            const gain = this.context.createGain();

            osc.type = 'sine';
            osc.frequency.setValueAtTime(freq, this.context.currentTime + i * duration);

            gain.gain.setValueAtTime(0, this.context.currentTime + i * duration);
            gain.gain.linearRampToValueAtTime(0.3, this.context.currentTime + i * duration + 0.02);
            gain.gain.exponentialRampToValueAtTime(0.01, this.context.currentTime + (i + 1) * duration);

            osc.connect(gain);
            gain.connect(this.masterGain);

            osc.start(this.context.currentTime + i * duration);
            osc.stop(this.context.currentTime + (i + 1) * duration);
        });
    }

    toggle() {
        this.enabled = !this.enabled;
        return this.enabled;
    }
}

// Global sound instance
const sound = new SoundDesign();

// ============================================================================
// WEATHER ATMOSPHERE — Adapts to reader's real weather (sneaky!)
// ============================================================================

class WeatherAtmosphere {
    constructor() {
        this.condition = 'clear';
        this.cloudCover = 0;
        this.windSpeed = 0;
        this.temperature = 20;
        this.temperatureHigh = null;
        this.temperatureLow = null;
        this.initialized = false;
        this.refreshInterval = null;
        this.lightningTimeout = null;

        // Atmosphere modifiers
        this.modifiers = {
            hueShift: 0,           // Color temperature shift
            saturation: 1,          // Color saturation multiplier
            brightness: 1,          // Brightness multiplier
            timingScale: 1,         // Animation timing multiplier
            particleDriftX: 0,      // Horizontal particle drift
            particleDriftY: -0.5,   // Vertical particle drift (negative = up)
            particleTurbulence: 0,  // Random motion intensity
            soundFreqMod: 1,        // Sound frequency multiplier
            glowIntensity: 1        // Breathing glow intensity
        };
    }

    async init() {
        if (this.initialized) return;

        try {
            // Use IP-based location by default (no permission prompt)
            const position = await this.getIPLocation();
            this.latitude = position.latitude;
            this.longitude = position.longitude;
            await this.fetchWeather(position.latitude, position.longitude);
            this.applyAtmosphere();
            this.startAutoRefresh();
            this.initialized = true;

            // Sneaky console message
            console.log('%c☁️ The atmosphere adapts to your sky.', 'color: #666; font-size: 10px; font-style: italic;');
        } catch (e) {
            // Silent fallback - no location or API error
            this.applyAtmosphere(); // Apply neutral defaults
        }
    }

    /**
     * Request precise browser geolocation (requires user permission)
     * Call this explicitly if high accuracy is needed
     */
    async requestPreciseLocation() {
        return new Promise((resolve, reject) => {
            if (!navigator.geolocation) {
                reject(new Error('Geolocation not supported'));
                return;
            }

            navigator.geolocation.getCurrentPosition(
                async (pos) => {
                    this.latitude = pos.coords.latitude;
                    this.longitude = pos.coords.longitude;
                    await this.fetchWeather(this.latitude, this.longitude);
                    this.applyAtmosphere();
                    console.log('%c📍 Precise location acquired', 'color: #22c55e;');
                    resolve({ latitude: this.latitude, longitude: this.longitude });
                },
                (err) => reject(err),
                { timeout: 10000, maximumAge: 300000, enableHighAccuracy: true }
            );
        });
    }

    async getIPLocation() {
        // IP-based geolocation - no permission required, city-level accuracy
        // Note: Won't work on file:// protocol due to CORS
        if (window.location.protocol === 'file:') {
            // Default to Seattle for local testing
            return { latitude: HOME.latitude, longitude: HOME.longitude };
        }

        const response = await fetch('https://ipapi.co/json/', { cache: 'force-cache' });
        const data = await response.json();
        return { latitude: data.latitude, longitude: data.longitude };
    }

    async fetchWeather(lat, lon) {
        // Open-Meteo API - free, no key required
        // Include daily forecast for high/low temperatures
        const url = `https://api.open-meteo.com/v1/forecast?latitude=${lat}&longitude=${lon}&current=weather_code,temperature_2m,wind_speed_10m,cloud_cover&daily=temperature_2m_max,temperature_2m_min&timezone=auto&forecast_days=1`;

        const response = await fetch(url);
        const data = await response.json();

        if (data.current) {
            this.condition = WMO_CODES[data.current.weather_code] || 'clear';
            this.cloudCover = data.current.cloud_cover || 0;
            this.windSpeed = data.current.wind_speed_10m || 0;
            this.temperature = data.current.temperature_2m || 20;
        }
        
        // Store daily high/low
        if (data.daily) {
            this.temperatureHigh = data.daily.temperature_2m_max?.[0] ?? null;
            this.temperatureLow = data.daily.temperature_2m_min?.[0] ?? null;
        }
    }

    calculateModifiers() {
        const mods = this.modifiers;

        // Reset to defaults
        Object.assign(mods, {
            hueShift: 0,
            saturation: 1,
            brightness: 1,
            contrast: 1,
            timingScale: 1,
            particleDriftX: 0,
            particleDriftY: -0.5,
            particleTurbulence: 0,
            particleOpacity: 1,
            soundFreqMod: 1,
            glowIntensity: 1,
            vignetteIntensity: 0,
            blurAmount: 0
        });

        switch (this.condition) {
            case 'clear':
            case 'mostly_clear':
                // DRAMATIC: Warm, golden, vibrant energy
                mods.hueShift = 15;             // Warm golden shift
                mods.saturation = 1.3;          // Very vibrant
                mods.brightness = 1.05;         // Bright
                mods.contrast = 1.1;            // Punchy
                mods.timingScale = 0.8;         // Faster, energetic
                mods.particleDriftY = -1.2;     // Strong upward energy
                mods.particleOpacity = 1.3;     // More visible particles
                mods.soundFreqMod = 1.15;       // Bright, sparkly tones
                mods.glowIntensity = 1.8;       // Strong golden glow
                mods.vignetteIntensity = 0.1;   // Subtle warm vignette
                break;

            case 'partly_cloudy':
                // Dynamic interplay
                mods.hueShift = 5;
                mods.saturation = 1.05;
                mods.timingScale = 0.95;
                mods.particleTurbulence = 0.2;
                mods.glowIntensity = 1.1;
                break;

            case 'overcast':
                // DRAMATIC: Heavy, muted, contemplative
                mods.hueShift = -25;            // Strong cool shift
                mods.saturation = 0.55;         // Very desaturated
                mods.brightness = 0.8;          // Noticeably darker
                mods.contrast = 0.9;            // Flatter
                mods.timingScale = 1.4;         // Much slower
                mods.particleDriftY = -0.2;     // Sluggish drift
                mods.particleOpacity = 0.6;     // Faded particles
                mods.soundFreqMod = 0.8;        // Muffled tones
                mods.glowIntensity = 0.4;       // Dim glow
                mods.vignetteIntensity = 0.25;  // Heavy vignette
                mods.blurAmount = 0.5;          // Slight haze
                break;

            case 'fog':
                // DRAMATIC: Ethereal, mysterious, dreamlike
                mods.hueShift = -15;            // Cool ethereal
                mods.saturation = 0.4;          // Very washed out
                mods.brightness = 0.95;         // Bright but flat
                mods.contrast = 0.75;           // Low contrast
                mods.timingScale = 1.6;         // Very slow, dreamlike
                mods.particleDriftY = -0.1;     // Almost still
                mods.particleDriftX = 0.05;     // Gentle sideways
                mods.particleTurbulence = 0.1;
                mods.particleOpacity = 0.4;     // Ghostly particles
                mods.soundFreqMod = 0.7;        // Distant, muffled
                mods.glowIntensity = 0.6;       // Diffuse glow
                mods.vignetteIntensity = 0.4;   // Strong fog vignette
                mods.blurAmount = 2;            // Heavy atmospheric blur
                break;

            case 'drizzle':
            case 'freezing_drizzle':
                // DRAMATIC: Melancholy, introspective
                mods.hueShift = -30;            // Blue-grey
                mods.saturation = 0.65;         // Washed colors
                mods.brightness = 0.85;         // Dim
                mods.contrast = 0.95;
                mods.timingScale = 1.2;         // Slower
                mods.particleDriftY = 0.6;      // Falling
                mods.particleDriftX = 0.1;
                mods.particleTurbulence = 0.25;
                mods.particleOpacity = 0.8;
                mods.soundFreqMod = 0.75;       // Soft, low
                mods.glowIntensity = 0.5;
                mods.vignetteIntensity = 0.3;
                mods.blurAmount = 0.3;
                break;

            case 'rain':
            case 'showers':
            case 'freezing_rain':
                // DRAMATIC: Moody, immersive, cinematic
                mods.hueShift = -40;            // Deep blue shift
                mods.saturation = 0.5;          // Very muted
                mods.brightness = 0.75;         // Dark
                mods.contrast = 1.15;           // High contrast
                mods.timingScale = 1.3;         // Contemplative
                mods.particleDriftY = 1.2;      // Strong falling
                mods.particleDriftX = 0.3;      // Wind-driven
                mods.particleTurbulence = 0.5;
                mods.particleOpacity = 1.2;     // Visible rain
                mods.soundFreqMod = 0.65;       // Deep, resonant
                mods.glowIntensity = 0.3;       // Minimal glow
                mods.vignetteIntensity = 0.35;
                mods.blurAmount = 0.8;
                break;

            case 'heavy_rain':
            case 'heavy_showers':
                // DRAMATIC: Intense, overwhelming, powerful
                mods.hueShift = -50;            // Very blue
                mods.saturation = 0.4;          // Almost monochrome
                mods.brightness = 0.65;         // Very dark
                mods.contrast = 1.25;           // High drama
                mods.timingScale = 1.5;         // Slow motion feel
                mods.particleDriftY = 2.0;      // Torrential
                mods.particleDriftX = 0.5;      // Strong wind
                mods.particleTurbulence = 0.8;  // Chaotic
                mods.particleOpacity = 1.5;     // Dense rain
                mods.soundFreqMod = 0.5;        // Deep rumble
                mods.glowIntensity = 0.2;       // Almost no glow
                mods.vignetteIntensity = 0.5;   // Heavy vignette
                mods.blurAmount = 1.5;          // Rain blur
                break;

            case 'snow':
            case 'snow_grains':
            case 'snow_showers':
                // DRAMATIC: Peaceful, crystalline, magical
                mods.hueShift = -45;            // Cool blue-white
                mods.saturation = 0.5;          // Muted but pure
                mods.brightness = 1.15;         // Bright snow glow
                mods.contrast = 0.9;            // Soft contrast
                mods.timingScale = 1.8;         // Very slow, peaceful
                mods.particleDriftY = 0.4;      // Gentle fall
                mods.particleDriftX = 0.25;     // Drifting
                mods.particleTurbulence = 0.6;  // Swirling
                mods.particleOpacity = 1.4;     // Visible snowflakes
                mods.soundFreqMod = 1.3;        // High, crystalline
                mods.glowIntensity = 1.2;       // Soft white glow
                mods.vignetteIntensity = 0.2;
                mods.blurAmount = 0.3;
                break;

            case 'heavy_snow':
                // DRAMATIC: Blizzard, disorienting, immersive
                mods.hueShift = -55;            // Deep blue-white
                mods.saturation = 0.35;         // Nearly monochrome
                mods.brightness = 1.25;         // Blinding white
                mods.contrast = 0.8;            // Low visibility
                mods.timingScale = 2.0;         // Extremely slow
                mods.particleDriftY = 0.8;      // Heavy fall
                mods.particleDriftX = 0.6;      // Strong wind
                mods.particleTurbulence = 1.0;  // Whiteout chaos
                mods.particleOpacity = 2.0;     // Dense snow
                mods.soundFreqMod = 1.4;        // Howling high tones
                mods.glowIntensity = 1.5;       // Bright diffuse
                mods.vignetteIntensity = 0.4;
                mods.blurAmount = 2.5;          // Blizzard blur
                break;

            case 'thunderstorm':
                // DRAMATIC: Electric, intense, awe-inspiring
                mods.hueShift = -35;            // Electric blue
                mods.saturation = 1.4;          // Hyper-saturated
                mods.brightness = 0.7;          // Dark base
                mods.contrast = 1.4;            // Extreme contrast
                mods.timingScale = 0.7;         // Fast, nervous energy
                mods.particleDriftY = 1.5;      // Heavy rain
                mods.particleDriftX = 0.6;      // Strong wind
                mods.particleTurbulence = 1.2;  // Violent chaos
                mods.particleOpacity = 1.3;
                mods.soundFreqMod = 0.5;        // Deep thunder
                mods.glowIntensity = 2.0;       // Lightning ready

                // More frequent, dramatic lightning
                this.scheduleLightning();
                break;
        }

        // Wind dramatically affects particles
        if (this.windSpeed > 5) {
            mods.particleDriftX += this.windSpeed * 0.025;
            mods.particleTurbulence += this.windSpeed * 0.02;
        }
        if (this.windSpeed > 20) {
            mods.blurAmount += 0.3;  // Wind blur
            mods.timingScale *= 0.9; // Faster in strong wind
        }

        // Cloud cover dramatically affects saturation and brightness
        mods.saturation *= 1 - (this.cloudCover * 0.004);
        mods.brightness *= 1 - (this.cloudCover * 0.002);
        mods.vignetteIntensity += this.cloudCover * 0.002;
    }

    scheduleLightning() {
        if (this.condition !== 'thunderstorm') return;

        // More frequent lightning: 2-8 seconds between flashes
        const delay = 2000 + Math.random() * 6000;

        this.lightningTimeout = setTimeout(() => {
            this.flashLightning();
            this.scheduleLightning();
        }, delay);
    }

    flashLightning() {
        // Skip lightning flash if user prefers reduced motion
        if (MotionPreference.prefersReduced) {
            // Just play thunder sound without visual flash
            if (sound && sound.enabled) {
                setTimeout(() => this.playThunder(), 100);
            }
            return;
        }

        const root = document.documentElement;
        const body = document.body;
        const baseBrightness = this.modifiers.brightness;

        // Add lightning class for CSS effects
        body.classList.add('lightning-flash');

        // DRAMATIC multi-stage flash sequence
        const flashSequence = [
            { brightness: 2.0, saturation: 0.3, duration: 50 },   // Initial blinding flash
            { brightness: baseBrightness, saturation: this.modifiers.saturation, duration: 80 },
            { brightness: 1.6, saturation: 0.5, duration: 40 },   // Secondary flash
            { brightness: baseBrightness, saturation: this.modifiers.saturation, duration: 100 },
        ];

        // Random chance of triple flash (fork lightning)
        if (Math.random() > 0.6) {
            flashSequence.push(
                { brightness: 1.4, saturation: 0.6, duration: 30 },
                { brightness: baseBrightness, saturation: this.modifiers.saturation, duration: 50 }
            );
        }

        // Execute flash sequence
        let totalDelay = 0;
        flashSequence.forEach((flash, i) => {
            setTimeout(() => {
                root.style.setProperty('--atmosphere-brightness', String(flash.brightness));
                root.style.setProperty('--atmosphere-saturation', String(flash.saturation));
            }, totalDelay);
            totalDelay += flash.duration;
        });

        // Remove lightning class and restore
        setTimeout(() => {
            body.classList.remove('lightning-flash');
            root.style.setProperty('--atmosphere-brightness', String(baseBrightness));
            root.style.setProperty('--atmosphere-saturation', String(this.modifiers.saturation));
        }, totalDelay + 100);

        // Play thunder sound if sound is enabled (delayed for realism)
        if (sound && sound.enabled) {
            const thunderDelay = 300 + Math.random() * 2000; // Thunder follows lightning
            setTimeout(() => this.playThunder(), thunderDelay);
        }
    }

    playThunder() {
        if (!sound || !sound.context) return;

        const ctx = sound.context;
        const now = ctx.currentTime;

        // Create thunder rumble using filtered noise
        const duration = 1.5 + Math.random() * 2;
        const bufferSize = ctx.sampleRate * duration;
        const buffer = ctx.createBuffer(1, bufferSize, ctx.sampleRate);
        const data = buffer.getChannelData(0);

        // Generate brownian noise for deep rumble
        let lastOut = 0;
        for (let i = 0; i < bufferSize; i++) {
            const white = Math.random() * 2 - 1;
            data[i] = (lastOut + (0.02 * white)) / 1.02;
            lastOut = data[i];
            data[i] *= 3.5; // Amplify
        }

        const noise = ctx.createBufferSource();
        noise.buffer = buffer;

        // Low-pass filter for deep rumble
        const lowpass = ctx.createBiquadFilter();
        lowpass.type = 'lowpass';
        lowpass.frequency.setValueAtTime(150, now);
        lowpass.frequency.exponentialRampToValueAtTime(60, now + duration);

        // Envelope for thunder shape
        const gain = ctx.createGain();
        gain.gain.setValueAtTime(0, now);
        gain.gain.linearRampToValueAtTime(0.4, now + 0.1);
        gain.gain.exponentialRampToValueAtTime(0.01, now + duration);

        noise.connect(lowpass);
        lowpass.connect(gain);
        gain.connect(sound.masterGain);

        noise.start(now);
        noise.stop(now + duration);
    }

    applyAtmosphere() {
        this.calculateModifiers();
        const mods = this.modifiers;
        const root = document.documentElement;

        // Apply ALL CSS custom properties for dramatic effects
        root.style.setProperty('--atmosphere-hue-shift', `${mods.hueShift}deg`);
        root.style.setProperty('--atmosphere-saturation', String(mods.saturation));
        root.style.setProperty('--atmosphere-brightness', String(mods.brightness));
        root.style.setProperty('--atmosphere-contrast', String(mods.contrast));
        root.style.setProperty('--atmosphere-timing', String(mods.timingScale));
        root.style.setProperty('--atmosphere-particle-drift-x', String(mods.particleDriftX));
        root.style.setProperty('--atmosphere-particle-drift-y', String(mods.particleDriftY));
        root.style.setProperty('--atmosphere-turbulence', String(mods.particleTurbulence));
        root.style.setProperty('--atmosphere-particle-opacity', String(mods.particleOpacity));
        root.style.setProperty('--atmosphere-glow', String(mods.glowIntensity));
        root.style.setProperty('--atmosphere-vignette', String(mods.vignetteIntensity));
        root.style.setProperty('--atmosphere-blur', `${mods.blurAmount}px`);

        // Activate atmosphere overlay
        document.body.classList.add('atmosphere-active');

        // Set weather condition class for targeted styling
        document.body.dataset.weather = this.condition;

        // Update sound frequency modifier
        if (sound && sound.initialized) {
            sound.frequencyMod = mods.soundFreqMod;
        }
    }

    startAutoRefresh() {
        // Refresh weather every 15 minutes
        this.refreshInterval = setInterval(async () => {
            try {
                const position = await this.getIPLocation();
                await this.fetchWeather(position.latitude, position.longitude);
                this.applyAtmosphere();
            } catch (e) {
                // Silent fail on refresh
            }
        }, 15 * 60 * 1000);
    }

    // =========================================================================
    // DEBUG METHODS
    // =========================================================================

    /**
     * Display current atmosphere state in console
     */
    debug() {
        const styles = {
            header: 'color: #6366f1; font-weight: bold; font-size: 14px;',
            label: 'color: #94a3b8; font-weight: normal;',
            value: 'color: #f8fafc; font-weight: bold;',
            success: 'color: #22c55e;',
            warning: 'color: #eab308;',
            error: 'color: #ef4444;'
        };

        console.log('%c☁️ WeatherAtmosphere Debug', styles.header);
        console.log('%c─────────────────────────────', styles.label);

        // Status
        const status = this.initialized ? '✓ Initialized' : '✗ Not initialized';
        console.log(`%cStatus: %c${status}`, styles.label, this.initialized ? styles.success : styles.warning);

        // Location
        if (this.latitude && this.longitude) {
            console.log(`%cLocation: %c${this.latitude.toFixed(4)}, ${this.longitude.toFixed(4)}`, styles.label, styles.value);
        } else {
            console.log(`%cLocation: %cUnknown`, styles.label, styles.warning);
        }

        // Current weather
        console.log('%c─────────────────────────────', styles.label);
        console.log(`%cCondition: %c${this.condition}`, styles.label, styles.value);
        console.log(`%cCloud Cover: %c${this.cloudCover}%`, styles.label, styles.value);
        console.log(`%cWind Speed: %c${this.windSpeed} km/h`, styles.label, styles.value);
        console.log(`%cTemperature: %c${this.temperature}°C`, styles.label, styles.value);

        // Active modifiers
        console.log('%c─────────────────────────────', styles.label);
        console.log('%cActive Modifiers:', styles.label);
        const mods = this.modifiers;
        console.table({
            'Hue Shift': `${mods.hueShift}deg`,
            'Saturation': mods.saturation.toFixed(3),
            'Brightness': mods.brightness.toFixed(3),
            'Timing Scale': mods.timingScale.toFixed(3),
            'Particle Drift X': mods.particleDriftX.toFixed(3),
            'Particle Drift Y': mods.particleDriftY.toFixed(3),
            'Turbulence': mods.particleTurbulence.toFixed(3),
            'Sound Freq Mod': mods.soundFreqMod.toFixed(3),
            'Glow Intensity': mods.glowIntensity.toFixed(3)
        });

        // CSS Variables
        console.log('%c─────────────────────────────', styles.label);
        console.log('%cCSS Variables Applied:', styles.label);
        const computed = getComputedStyle(document.documentElement);
        console.table({
            '--atmosphere-hue-shift': computed.getPropertyValue('--atmosphere-hue-shift').trim(),
            '--atmosphere-saturation': computed.getPropertyValue('--atmosphere-saturation').trim(),
            '--atmosphere-brightness': computed.getPropertyValue('--atmosphere-brightness').trim(),
            '--atmosphere-timing': computed.getPropertyValue('--atmosphere-timing').trim(),
            '--atmosphere-particle-drift-x': computed.getPropertyValue('--atmosphere-particle-drift-x').trim(),
            '--atmosphere-particle-drift-y': computed.getPropertyValue('--atmosphere-particle-drift-y').trim(),
            '--atmosphere-turbulence': computed.getPropertyValue('--atmosphere-turbulence').trim(),
            '--atmosphere-glow': computed.getPropertyValue('--atmosphere-glow').trim()
        });

        return this;
    }

    /**
     * Simulate a specific weather condition for testing
     * @param {string} condition - Weather condition from WMO_CODES
     * @param {object} options - Optional overrides for cloudCover, windSpeed, temperature
     */
    simulate(condition, options = {}) {
        const validConditions = [...new Set(Object.values(WMO_CODES))];

        if (!validConditions.includes(condition)) {
            console.warn(`%c⚠️ Invalid condition: "${condition}"`, 'color: #eab308;');
            console.log('%cValid conditions:', 'color: #94a3b8;', validConditions.join(', '));
            return this;
        }

        // Store original values for restore
        if (!this._originalState) {
            this._originalState = {
                condition: this.condition,
                cloudCover: this.cloudCover,
                windSpeed: this.windSpeed,
                temperature: this.temperature
            };
        }

        // Clear any existing lightning
        if (this.lightningTimeout) {
            clearTimeout(this.lightningTimeout);
            this.lightningTimeout = null;
        }

        // Apply simulated condition
        this.condition = condition;
        this.cloudCover = options.cloudCover ?? (condition.includes('clear') ? 10 : 70);
        this.windSpeed = options.windSpeed ?? (condition.includes('thunder') ? 25 : 10);
        this.temperature = options.temperature ?? 20;

        this.applyAtmosphere();

        console.log(`%c🎭 Simulating: ${condition}`, 'color: #a855f7; font-weight: bold;');
        console.log('%cUse atmosphere.restore() to return to real weather', 'color: #666; font-style: italic;');

        return this;
    }

    /**
     * Restore original weather state after simulation
     */
    restore() {
        if (!this._originalState) {
            console.log('%c⚠️ No simulation active to restore', 'color: #eab308;');
            return this;
        }

        // Clear lightning if active
        if (this.lightningTimeout) {
            clearTimeout(this.lightningTimeout);
            this.lightningTimeout = null;
        }

        // Restore original state
        Object.assign(this, this._originalState);
        this._originalState = null;

        this.applyAtmosphere();

        console.log('%c✓ Restored to real weather', 'color: #22c55e;');
        return this;
    }

    /**
     * Force refresh weather data now
     */
    async forceRefresh() {
        console.log('%c🔄 Forcing weather refresh...', 'color: #3b82f6;');

        try {
            const position = await this.getIPLocation();
            this.latitude = position.latitude;
            this.longitude = position.longitude;

            await this.fetchWeather(position.latitude, position.longitude);
            this.applyAtmosphere();

            console.log('%c✓ Weather refreshed', 'color: #22c55e;');
            this.debug();
        } catch (e) {
            console.error('%c✗ Refresh failed:', 'color: #ef4444;', e.message);
        }

        return this;
    }

    /**
     * Test lightning flash effect
     * @param {number} count - Number of flashes (default: 1)
     */
    testLightning(count = 1) {
        console.log(`%c⚡ Testing ${count} lightning flash(es)`, 'color: #fbbf24;');

        const flash = (i) => {
            if (i >= count) return;

            setTimeout(() => {
                this.flashLightning();
                flash(i + 1);
            }, i * 800);
        };

        flash(0);
        return this;
    }

    /**
     * List all available weather conditions for simulation
     */
    listConditions() {
        const conditions = [...new Set(Object.values(WMO_CODES))];

        console.log('%c☁️ Available Weather Conditions:', 'color: #6366f1; font-weight: bold;');
        conditions.forEach(c => {
            const isCurrent = c === this.condition;
            console.log(`  ${isCurrent ? '▶' : ' '} %c${c}`, isCurrent ? 'color: #22c55e; font-weight: bold;' : 'color: #f8fafc;');
        });

        return conditions;
    }

    /**
     * Test API connectivity
     */
    async testAPI() {
        console.log('%c🌐 Testing API connectivity...', 'color: #3b82f6;');

        const tests = [];

        // Test IP-based location
        try {
            const start1 = performance.now();
            const ipPos = await this.getIPLocation();
            const time1 = (performance.now() - start1).toFixed(0);
            tests.push({ name: 'IP Location', status: '✓', latency: `${time1}ms`, result: `${ipPos.latitude.toFixed(2)}, ${ipPos.longitude.toFixed(2)}` });
        } catch (e) {
            tests.push({ name: 'IP Location', status: '✗', latency: '-', result: e.message });
        }

        // Test Open-Meteo
        try {
            const lat = this.latitude || 47.6;
            const lon = this.longitude || -122.3;
            const start2 = performance.now();
            const url = `https://api.open-meteo.com/v1/forecast?latitude=${lat}&longitude=${lon}&current=weather_code`;
            const resp = await fetch(url);
            const data = await resp.json();
            const time2 = (performance.now() - start2).toFixed(0);
            tests.push({ name: 'Open-Meteo API', status: '✓', latency: `${time2}ms`, result: `Code: ${data.current?.weather_code}` });
        } catch (e) {
            tests.push({ name: 'Open-Meteo API', status: '✗', latency: '-', result: e.message });
        }

        // Test browser geolocation availability (doesn't trigger prompt)
        const geoAvailable = 'geolocation' in navigator;
        tests.push({ name: 'Browser Geolocation', status: geoAvailable ? '✓' : '✗', latency: '-', result: geoAvailable ? 'Available (use requestPreciseLocation())' : 'Not supported' });

        console.table(tests);

        const criticalPassed = tests.slice(0, 2).every(t => t.status === '✓');
        console.log(criticalPassed ? '%c✓ Core APIs working' : '%c⚠️ Some APIs failed', criticalPassed ? 'color: #22c55e;' : 'color: #eab308;');

        return tests;
    }

    destroy() {
        if (this.refreshInterval) clearInterval(this.refreshInterval);
        if (this.lightningTimeout) clearTimeout(this.lightningTimeout);
    }
}

// Global atmosphere instance
const atmosphere = new WeatherAtmosphere();

// ============================================================================
// ============================================================================
// EPHEMERIS — Astronomical Calculations
// 
// Based on:
// - Jean Meeus, "Astronomical Algorithms" (2nd ed., 1998)
// - NOAA Solar Calculator
// - IAU SOFA (Standards of Fundamental Astronomy)
//
// Accuracy: ±0.01° for sun, ±0.5° for moon (sufficient for visualization)
// Valid range: Years 1900-2100 with high accuracy, 0-4000 CE with ±1° accuracy
// ============================================================================

class Ephemeris {
    // Constants
    static J2000 = 2451545.0;           // Julian Date of J2000.0 epoch
    static DEG_TO_RAD = Math.PI / 180;
    static RAD_TO_DEG = 180 / Math.PI;
    
    /**
     * Calculate Julian Date from JavaScript Date
     * Algorithm: Meeus, Astronomical Algorithms, Ch. 7
     * Valid for all dates in Gregorian calendar (after Oct 15, 1582)
     */
    static julianDate(date) {
        const y = date.getUTCFullYear();
        const m = date.getUTCMonth() + 1;
        const d = date.getUTCDate();
        const h = date.getUTCHours() + date.getUTCMinutes() / 60 + 
                  date.getUTCSeconds() / 3600 + date.getUTCMilliseconds() / 3600000;
        
        let jy = y;
        let jm = m;
        if (m <= 2) {
            jy -= 1;
            jm += 12;
        }
        
        const a = Math.floor(jy / 100);
        const b = 2 - a + Math.floor(a / 4);  // Gregorian correction
        
        return Math.floor(365.25 * (jy + 4716)) + 
               Math.floor(30.6001 * (jm + 1)) + 
               d + h / 24 + b - 1524.5;
    }
    
    /**
     * Calculate obliquity of the ecliptic (Earth's axial tilt)
     * IAU 2006 precession model - accurate for ±10,000 years from J2000
     * @param {number} jd - Julian Date
     * @returns {number} Obliquity in degrees
     */
    static obliquity(jd) {
        const T = (jd - this.J2000) / 36525;  // Julian centuries from J2000
        // IAU 2006 formula (arcseconds)
        const eps0 = 84381.406 - 46.836769 * T - 0.0001831 * T * T + 
                     0.00200340 * T * T * T;
        return eps0 / 3600;  // Convert to degrees
    }
    
    /**
     * Normalize angle to 0-360 range
     */
    static normalizeAngle(angle) {
        return ((angle % 360) + 360) % 360;
    }

    /**
     * Calculate sun position (azimuth and altitude)
     * Algorithm: Low-precision solar coordinates from Astronomical Almanac
     * Accuracy: ±0.01° (sufficient for civil purposes)
     */
    static sunPosition(lat, lon, date = new Date()) {
        const jd = this.julianDate(date);
        const n = jd - this.J2000;  // Days since J2000.0
        const T = n / 36525;        // Julian centuries
        
        // Mean longitude of the Sun (degrees) - IAU
        const L0 = this.normalizeAngle(280.46646 + 36000.76983 * T + 0.0003032 * T * T);
        
        // Mean anomaly of the Sun (degrees) - IAU
        const M = this.normalizeAngle(357.52911 + 35999.05029 * T - 0.0001537 * T * T);
        const Mrad = M * this.DEG_TO_RAD;
        
        // Equation of center (degrees)
        const C = (1.914602 - 0.004817 * T - 0.000014 * T * T) * Math.sin(Mrad) +
                  (0.019993 - 0.000101 * T) * Math.sin(2 * Mrad) +
                  0.000289 * Math.sin(3 * Mrad);
        
        // Sun's true longitude (degrees)
        const sunLon = this.normalizeAngle(L0 + C);
        const sunLonRad = sunLon * this.DEG_TO_RAD;
        
        // Obliquity of ecliptic (with nutation ignored for low precision)
        const epsilon = this.obliquity(jd);
        const epsRad = epsilon * this.DEG_TO_RAD;
        
        // Sun's right ascension and declination
        const alpha = Math.atan2(Math.cos(epsRad) * Math.sin(sunLonRad), Math.cos(sunLonRad));
        const delta = Math.asin(Math.sin(epsRad) * Math.sin(sunLonRad));
        
        // Greenwich Mean Sidereal Time (degrees) - IAU
        const gmst = this.normalizeAngle(280.46061837 + 360.98564736629 * n + 
                     0.000387933 * T * T - T * T * T / 38710000);
        
        // Local Sidereal Time and Hour Angle
        const lst = (gmst + lon) * this.DEG_TO_RAD;
        const ha = lst - alpha;
        
        // Convert to horizontal coordinates
        const latRad = lat * this.DEG_TO_RAD;
        
        const altitude = Math.asin(
            Math.sin(latRad) * Math.sin(delta) + 
            Math.cos(latRad) * Math.cos(delta) * Math.cos(ha)
        ) * this.RAD_TO_DEG;
        
        let azimuth = Math.atan2(
            -Math.sin(ha),
            Math.tan(delta) * Math.cos(latRad) - Math.sin(latRad) * Math.cos(ha)
        ) * this.RAD_TO_DEG;
        
        azimuth = this.normalizeAngle(azimuth);
        
        return {
            altitude: Math.round(altitude * 10) / 10,
            azimuth: Math.round(azimuth * 10) / 10,
            isDay: altitude > -0.833,  // Account for refraction at horizon
            direction: this.azimuthToDirection(azimuth),
            // Debug info
            _sunLon: Math.round(sunLon * 10) / 10,
            _declination: Math.round(delta * this.RAD_TO_DEG * 10) / 10
        };
    }

    /**
     * Convert azimuth to compass direction
     */
    static azimuthToDirection(azimuth) {
        const directions = ['N', 'NNE', 'NE', 'ENE', 'E', 'ESE', 'SE', 'SSE',
                          'S', 'SSW', 'SW', 'WSW', 'W', 'WNW', 'NW', 'NNW'];
        const index = Math.round(azimuth / 22.5) % 16;
        return directions[index];
    }

    /**
     * Calculate moon position (azimuth and altitude)
     * Algorithm: Simplified ELP2000 (Chapront-Touzé & Chapront)
     * Accuracy: ±0.5° for position, sufficient for visualization
     */
    static moonPosition(lat, lon, date = new Date()) {
        const jd = this.julianDate(date);
        const T = (jd - this.J2000) / 36525;  // Julian centuries from J2000
        const T2 = T * T;
        const T3 = T2 * T;
        const T4 = T3 * T;

        // Fundamental arguments (degrees) - IAU 2000
        // Mean longitude of Moon
        const Lp = this.normalizeAngle(218.3164477 + 481267.88123421 * T - 
                   0.0015786 * T2 + T3 / 538841 - T4 / 65194000);
        
        // Mean elongation of Moon from Sun
        const D = this.normalizeAngle(297.8501921 + 445267.1114034 * T - 
                  0.0018819 * T2 + T3 / 545868 - T4 / 113065000);
        
        // Mean anomaly of Sun
        const M = this.normalizeAngle(357.5291092 + 35999.0502909 * T - 
                  0.0001536 * T2 + T3 / 24490000);
        
        // Mean anomaly of Moon
        const Mp = this.normalizeAngle(134.9633964 + 477198.8675055 * T + 
                   0.0087414 * T2 + T3 / 69699 - T4 / 14712000);
        
        // Moon's argument of latitude
        const F = this.normalizeAngle(93.2720950 + 483202.0175233 * T - 
                  0.0036539 * T2 - T3 / 3526000 + T4 / 863310000);

        // Convert to radians
        const toRad = this.DEG_TO_RAD;
        const Drad = D * toRad;
        const Mrad = M * toRad;
        const Mprad = Mp * toRad;
        const Frad = F * toRad;

        // Longitude corrections (main periodic terms)
        // Coefficients from ELP2000-82
        let sumL = 0;
        sumL += 6288774 * Math.sin(Mprad);                           // M'
        sumL += 1274027 * Math.sin(2 * Drad - Mprad);                // 2D - M'
        sumL += 658314 * Math.sin(2 * Drad);                         // 2D
        sumL += 213618 * Math.sin(2 * Mprad);                        // 2M'
        sumL -= 185116 * Math.sin(Mrad);                             // M (solar)
        sumL -= 114332 * Math.sin(2 * Frad);                         // 2F
        sumL += 58793 * Math.sin(2 * Drad - 2 * Mprad);              // 2D - 2M'
        sumL += 57066 * Math.sin(2 * Drad - Mrad - Mprad);           // 2D - M - M'
        sumL += 53322 * Math.sin(2 * Drad + Mprad);                  // 2D + M'
        sumL += 45758 * Math.sin(2 * Drad - Mrad);                   // 2D - M
        sumL -= 40923 * Math.sin(Mrad - Mprad);                      // M - M'
        sumL -= 34720 * Math.sin(Drad);                              // D
        sumL -= 30383 * Math.sin(Mrad + Mprad);                      // M + M'
        
        // Longitude in degrees
        const moonLon = Lp + sumL / 1000000;

        // Latitude corrections (main periodic terms)
        let sumB = 0;
        sumB += 5128122 * Math.sin(Frad);                            // F
        sumB += 280602 * Math.sin(Mprad + Frad);                     // M' + F
        sumB += 277693 * Math.sin(Mprad - Frad);                     // M' - F
        sumB += 173237 * Math.sin(2 * Drad - Frad);                  // 2D - F
        sumB += 55413 * Math.sin(2 * Drad - Mprad + Frad);           // 2D - M' + F
        sumB += 46271 * Math.sin(2 * Drad - Mprad - Frad);           // 2D - M' - F
        sumB += 32573 * Math.sin(2 * Drad + Frad);                   // 2D + F
        sumB += 17198 * Math.sin(2 * Mprad + Frad);                  // 2M' + F
        
        // Latitude in degrees
        const moonLat = sumB / 1000000;

        // Convert ecliptic to equatorial coordinates
        const epsilon = this.obliquity(jd);
        const epsRad = epsilon * toRad;
        const lonRad = moonLon * toRad;
        const latRad = moonLat * toRad;

        // Right ascension
        const alpha = Math.atan2(
            Math.sin(lonRad) * Math.cos(epsRad) - Math.tan(latRad) * Math.sin(epsRad),
            Math.cos(lonRad)
        );

        // Declination
        const delta = Math.asin(
            Math.sin(latRad) * Math.cos(epsRad) +
            Math.cos(latRad) * Math.sin(epsRad) * Math.sin(lonRad)
        );

        // Greenwich Mean Sidereal Time
        const n = jd - this.J2000;
        const gmst = this.normalizeAngle(280.46061837 + 360.98564736629 * n);
        const lst = (gmst + lon) * toRad;
        const ha = lst - alpha;

        // Convert to horizontal coordinates
        const observerLatRad = lat * toRad;

        const altitude = Math.asin(
            Math.sin(observerLatRad) * Math.sin(delta) +
            Math.cos(observerLatRad) * Math.cos(delta) * Math.cos(ha)
        ) * this.RAD_TO_DEG;

        let azimuth = Math.atan2(
            -Math.sin(ha),
            Math.tan(delta) * Math.cos(observerLatRad) - Math.sin(observerLatRad) * Math.cos(ha)
        ) * this.RAD_TO_DEG;

        azimuth = this.normalizeAngle(azimuth);

        // Get phase info
        const phaseInfo = this.moonPhase(date);

        return {
            altitude: Math.round(altitude * 10) / 10,
            azimuth: Math.round(azimuth * 10) / 10,
            isVisible: altitude > -5,
            direction: this.azimuthToDirection(azimuth),
            ...phaseInfo
        };
    }

    /**
     * Calculate moon phase using astronomical algorithm
     * Based on the difference between lunar and solar longitudes
     * Accurate for any date
     */
    static moonPhase(date = new Date()) {
        const jd = this.julianDate(date);
        const T = (jd - this.J2000) / 36525;
        
        // Mean elongation of Moon from Sun (degrees)
        // This is the primary driver of lunar phases
        const D = this.normalizeAngle(297.8501921 + 445267.1114034 * T - 
                  0.0018819 * T * T + T * T * T / 545868);
        
        // Phase as fraction (0 = new, 0.5 = full, 1 = new)
        const phase = D / 360;
        
        // More accurate illumination using phase angle
        const phaseAngle = D;  // degrees
        const illumination = Math.round((1 - Math.cos(phaseAngle * this.DEG_TO_RAD)) / 2 * 100);

        // Phase name and emoji
        let phaseName, phaseEmoji;
        const p = phase;
        
        if (p < 0.025 || p >= 0.975) {
            phaseName = 'New Moon';
            phaseEmoji = '🌑';
        } else if (p < 0.225) {
            phaseName = 'Waxing Crescent';
            phaseEmoji = '🌒';
        } else if (p < 0.275) {
            phaseName = 'First Quarter';
            phaseEmoji = '🌓';
        } else if (p < 0.475) {
            phaseName = 'Waxing Gibbous';
            phaseEmoji = '🌔';
        } else if (p < 0.525) {
            phaseName = 'Full Moon';
            phaseEmoji = '🌕';
        } else if (p < 0.725) {
            phaseName = 'Waning Gibbous';
            phaseEmoji = '🌖';
        } else if (p < 0.775) {
            phaseName = 'Last Quarter';
            phaseEmoji = '🌗';
        } else {
            phaseName = 'Waning Crescent';
            phaseEmoji = '🌘';
        }

        return {
            phase: Math.round(phase * 1000) / 1000,
            illumination,
            phaseName,
            phaseEmoji,
            phaseAngle: Math.round(phaseAngle * 10) / 10,
            isWaxing: phase < 0.5
        };
    }

    /**
     * Calculate sunrise/sunset times
     * Algorithm: NOAA Solar Calculator with corrections
     * Accuracy: ±1 minute for latitudes between 60°N and 60°S
     */
    static sunTimes(lat, lon, date = new Date()) {
        const year = date.getFullYear();
        const month = date.getMonth();
        const day = date.getDate();
        
        // Create date at local noon for calculation stability
        const noonDate = new Date(year, month, day, 12, 0, 0);
        const jd = this.julianDate(noonDate);
        const T = (jd - this.J2000) / 36525;
        
        // Solar coordinates at noon
        const L0 = this.normalizeAngle(280.46646 + 36000.76983 * T);
        const M = this.normalizeAngle(357.52911 + 35999.05029 * T);
        const Mrad = M * this.DEG_TO_RAD;
        
        // Equation of center
        const C = (1.914602 - 0.004817 * T) * Math.sin(Mrad) +
                  (0.019993 - 0.000101 * T) * Math.sin(2 * Mrad) +
                  0.000289 * Math.sin(3 * Mrad);
        
        // Sun's true longitude
        const sunLon = (L0 + C) * this.DEG_TO_RAD;
        
        // Obliquity
        const epsilon = this.obliquity(jd) * this.DEG_TO_RAD;
        
        // Solar declination
        const decl = Math.asin(Math.sin(epsilon) * Math.sin(sunLon));
        
        // Equation of time (minutes)
        const y = Math.tan(epsilon / 2) * Math.tan(epsilon / 2);
        const L0rad = L0 * this.DEG_TO_RAD;
        const eqTime = 4 * this.RAD_TO_DEG * (
            y * Math.sin(2 * L0rad) -
            2 * 0.01671 * Math.sin(Mrad) +
            4 * 0.01671 * y * Math.sin(Mrad) * Math.cos(2 * L0rad) -
            0.5 * y * y * Math.sin(4 * L0rad) -
            1.25 * 0.01671 * 0.01671 * Math.sin(2 * Mrad)
        );
        
        // Hour angle for sunrise/sunset
        const latRad = lat * this.DEG_TO_RAD;
        const zenith = 90.833 * this.DEG_TO_RAD;  // Official sunrise/sunset with refraction
        
        const cosHA = (Math.cos(zenith) - Math.sin(latRad) * Math.sin(decl)) / 
                      (Math.cos(latRad) * Math.cos(decl));
        
        // Check for polar day/night
        if (cosHA > 1) return { sunrise: null, sunset: null, polarNight: true, dayLength: 0 };
        if (cosHA < -1) return { sunrise: null, sunset: null, midnightSun: true, dayLength: 24 };
        
        const HA = Math.acos(cosHA) * this.RAD_TO_DEG;
        
        // Solar noon in minutes from midnight UTC
        const solarNoonUTC = 720 - 4 * lon - eqTime;
        
        // Sunrise/sunset in minutes from midnight UTC
        const sunriseUTC = solarNoonUTC - HA * 4;
        const sunsetUTC = solarNoonUTC + HA * 4;
        
        // Convert to local time
        const tzOffset = date.getTimezoneOffset();
        const sunriseLocal = sunriseUTC - tzOffset;
        const sunsetLocal = sunsetUTC - tzOffset;
        const solarNoonLocal = solarNoonUTC - tzOffset;
        
        // Create date objects
        const baseDate = new Date(year, month, day, 0, 0, 0, 0);
        
        const minutesToDate = (mins) => {
            let m = mins;
            if (m < 0) m += 1440;
            if (m >= 1440) m -= 1440;
            return new Date(baseDate.getTime() + m * 60000);
        };
        
        const dayLength = (sunsetUTC - sunriseUTC) / 60;
        
        return {
            sunrise: minutesToDate(sunriseLocal),
            sunset: minutesToDate(sunsetLocal),
            solarNoon: minutesToDate(solarNoonLocal),
            dayLength: Math.round(dayLength * 100) / 100,
            eqTime: Math.round(eqTime * 10) / 10
        };
    }
    
    /**
     * Format time as HH:MM
     */
    static formatTime(date, includeSeconds = false) {
        if (!date) return '--:--';
        const h = date.getHours().toString().padStart(2, '0');
        const m = date.getMinutes().toString().padStart(2, '0');
        if (includeSeconds) {
            const s = date.getSeconds().toString().padStart(2, '0');
            return `${h}:${m}:${s}`;
        }
        return `${h}:${m}`;
    }
    
    /**
     * Verify algorithm accuracy (for debugging)
     * Call this to test against known values
     */
    static verify() {
        console.group('%c🔬 Ephemeris Verification', 'color: #64D9FF; font-weight: bold;');
        
        // Test 1: J2000.0 epoch
        const j2000 = new Date(Date.UTC(2000, 0, 1, 12, 0, 0));
        const jd = this.julianDate(j2000);
        console.log(`J2000.0 Julian Date: ${jd} (expected: 2451545.0)`);
        console.assert(Math.abs(jd - 2451545.0) < 0.0001, 'Julian Date error');
        
        // Test 2: Obliquity at J2000
        const eps = this.obliquity(2451545.0);
        console.log(`Obliquity at J2000: ${eps.toFixed(4)}° (expected: ~23.4393°)`);
        console.assert(Math.abs(eps - 23.4393) < 0.001, 'Obliquity error');
        
        // Test 3: Sun position at equinox
        const equinox2024 = new Date(Date.UTC(2024, 2, 20, 3, 6, 0)); // March 20, 2024 03:06 UTC
        const sunEq = this.sunPosition(0, 0, equinox2024);
        console.log(`Sun at 2024 equinox: alt=${sunEq.altitude}°, dec=${sunEq._declination}°`);
        console.assert(Math.abs(sunEq._declination) < 1, 'Equinox declination error');
        
        // Test 4: Moon phase - known full moon
        const fullMoon = new Date(Date.UTC(2024, 0, 25, 17, 54, 0)); // Jan 25, 2024 full moon
        const moonFM = this.moonPhase(fullMoon);
        console.log(`Moon phase Jan 25 2024: ${moonFM.phaseName} (${moonFM.illumination}%)`);
        console.assert(moonFM.illumination > 95, 'Full moon illumination error');
        
        console.log('%c✓ Verification complete', 'color: #4CAF50;');
        console.groupEnd();
        
        return { jd, eps, sunEq, moonFM };
    }
}

// ============================================================================
// GEOMETRY — Window Orientation and Glare
// ============================================================================

class HomeGeometry {
    /**
     * Calculate sun intensity on a window (0-1)
     */
    static getSunIntensity(sunAzimuth, sunAltitude, direction) {
        if (sunAltitude <= 0) return 0;
        
        const windowAzimuth = DIRECTIONS[direction].azimuth;
        let diff = Math.abs(sunAzimuth - windowAzimuth);
        if (diff > 180) diff = 360 - diff;
        
        if (diff > 60) return 0;
        
        const alignment = 1.0 - (diff / 60);
        
        let altitudeFactor;
        if (sunAltitude < 15) {
            altitudeFactor = 1.0;
        } else if (sunAltitude < 45) {
            altitudeFactor = 1.0 - ((sunAltitude - 15) / 45);
        } else {
            altitudeFactor = Math.max(0, 0.33 - ((sunAltitude - 45) / 135));
        }
        
        return Math.round(alignment * altitudeFactor * 100) / 100;
    }

    /**
     * Calculate optimal shade level for a window
     */
    static calculateShadeLevel(shade, sunAzimuth, sunAltitude, isDay, weather = null) {
        if (!isDay) {
            return { level: 100, reason: 'Night — open for views' };
        }
        
        if (weather) {
            if (weather.cloudCoverage > 70 || ['rain', 'drizzle', 'thunderstorm'].includes(weather.condition)) {
                return { level: 100, reason: `Weather override (${weather.condition})` };
            }
        }
        
        const intensity = this.getSunIntensity(sunAzimuth, sunAltitude, shade.facing);
        
        if (intensity === 0) {
            return { level: 100, reason: `No sun on ${DIRECTIONS[shade.facing].name}` };
        }
        
        if (shade.binary) {
            if (intensity > 0.7 && sunAltitude < 15) {
                return { level: 0, reason: `Severe glare (${Math.round(intensity * 100)}%)` };
            }
            return { level: 100, reason: 'Open for access' };
        }
        
        const level = Math.max(20, Math.min(100, Math.round(100 - intensity * 80)));
        return { 
            level, 
            reason: `Sun ${Math.round(sunAzimuth)}° → ${DIRECTIONS[shade.facing].name} (${Math.round(intensity * 100)}% glare)` 
        };
    }

    /**
     * Get all shade recommendations
     */
    static getAllRecommendations(sunAzimuth, sunAltitude, isDay, weather = null) {
        return SHADES.map(shade => ({
            ...shade,
            ...this.calculateShadeLevel(shade, sunAzimuth, sunAltitude, isDay, weather),
            intensity: this.getSunIntensity(sunAzimuth, sunAltitude, shade.facing)
        }));
    }
}

// ============================================================================
// WEATHER SERVICE
// ============================================================================

class WeatherService {
    static conditions = {
        clear: { name: 'Clear', icon: '☀️', shadeModifier: 0 },
        clouds: { name: 'Cloudy', icon: '☁️', shadeModifier: 20 },
        rain: { name: 'Rain', icon: '🌧️', shadeModifier: 100 },
        drizzle: { name: 'Drizzle', icon: '🌦️', shadeModifier: 50 },
        thunderstorm: { name: 'Thunderstorm', icon: '⛈️', shadeModifier: 100 },
        snow: { name: 'Snow', icon: '❄️', shadeModifier: 30 },
        fog: { name: 'Fog', icon: '🌫️', shadeModifier: 40 }
    };

    static getSimulatedWeather() {
        const conditions = ['clear', 'clouds', 'rain'];
        const condition = conditions[Math.floor(Math.random() * conditions.length)];
        const cloudCoverage = condition === 'clear' ? Math.random() * 30 :
                             condition === 'clouds' ? 50 + Math.random() * 40 :
                             90 + Math.random() * 10;
        
        return {
            condition,
            cloudCoverage: Math.round(cloudCoverage),
            temperature: Math.round(45 + Math.random() * 25),
            ...this.conditions[condition]
        };
    }
}

// ============================================================================
// CUSTOM CURSOR
// ============================================================================

class CustomCursor {
    constructor() {
        this.cursor = null;
        this.ring = null;
        this.mouseX = 0;
        this.mouseY = 0;
        this.cursorX = 0;
        this.cursorY = 0;
        this.ringX = 0;
        this.ringY = 0;
        this.isHovering = false;
        this.isClicking = false;
        
        this.init();
    }

    init() {
        // Only on devices with fine pointer
        if (!window.matchMedia('(hover: hover) and (pointer: fine)').matches) return;
        
        this.cursor = document.createElement('div');
        this.cursor.className = 'cursor';
        document.body.appendChild(this.cursor);
        
        this.ring = document.createElement('div');
        this.ring.className = 'cursor-ring';
        document.body.appendChild(this.ring);
        
        document.addEventListener('mousemove', (e) => this.onMouseMove(e));
        document.addEventListener('mousedown', () => this.onMouseDown());
        document.addEventListener('mouseup', () => this.onMouseUp());
        
        // Track hoverable elements
        const hoverables = document.querySelectorAll('a, button, [role="button"], input, textarea, select, label, .card, .timeline-item');
        hoverables.forEach(el => {
            el.addEventListener('mouseenter', () => this.onHoverStart());
            el.addEventListener('mouseleave', () => this.onHoverEnd());
        });
        
        this.animate();
    }

    onMouseMove(e) {
        this.mouseX = e.clientX;
        this.mouseY = e.clientY;
    }

    onMouseDown() {
        this.isClicking = true;
        this.cursor?.classList.add('clicking');
    }

    onMouseUp() {
        this.isClicking = false;
        this.cursor?.classList.remove('clicking');
    }

    onHoverStart() {
        this.isHovering = true;
        this.cursor?.classList.add('hovering');
        this.ring?.classList.add('hovering');
    }

    onHoverEnd() {
        this.isHovering = false;
        this.cursor?.classList.remove('hovering');
        this.ring?.classList.remove('hovering');
    }

    animate() {
        // Smooth follow for cursor (fast)
        this.cursorX += (this.mouseX - this.cursorX) * 0.2;
        this.cursorY += (this.mouseY - this.cursorY) * 0.2;
        
        // Slower follow for ring
        this.ringX += (this.mouseX - this.ringX) * 0.1;
        this.ringY += (this.mouseY - this.ringY) * 0.1;
        
        if (this.cursor) {
            this.cursor.style.left = `${this.cursorX}px`;
            this.cursor.style.top = `${this.cursorY}px`;
        }
        
        if (this.ring) {
            this.ring.style.left = `${this.ringX}px`;
            this.ring.style.top = `${this.ringY}px`;
        }
        
        requestAnimationFrame(() => this.animate());
    }
}

// ============================================================================
// PARTICLES — Advanced Canvas-based system with weather effects
// GPU-accelerated with transform/opacity only, 60fps smooth animation
// ============================================================================

class ParticleSystem {
    constructor(container) {
        this.container = container || document.body;
        this.canvas = null;
        this.ctx = null;
        this.particles = [];
        this.weatherParticles = [];
        this.windStreaks = [];
        this.sparkParticles = [];

        // Configuration
        this.baseParticleCount = 40;
        this.weatherParticleCount = 60;
        this.windStreakCount = 15;

        // Mouse tracking
        this.mouseX = window.innerWidth / 2;
        this.mouseY = window.innerHeight / 2;
        this.mouseVelX = 0;
        this.mouseVelY = 0;
        this.lastMouseX = this.mouseX;
        this.lastMouseY = this.mouseY;

        // Interaction settings
        this.mouseRadius = 120;
        this.mouseStrength = 0.08;
        this.particleInteractionRadius = 80;
        this.connectionDistance = 100;
        this.connectionOpacity = 0.15;

        // Weather state (synced with WeatherAtmosphere)
        this.weatherCondition = 'clear';
        this.windSpeed = 0;
        this.temperature = 20;
        this.aqi = 50; // Air quality index

        // Animation state
        this.animationId = null;
        this.lastTime = 0;
        this.deltaTime = 0;

        this.init();
    }

    init() {
        // Create canvas for GPU-accelerated rendering
        this.canvas = document.createElement('canvas');
        this.canvas.className = 'particles-canvas';
        this.canvas.setAttribute('aria-hidden', 'true');
        this.ctx = this.canvas.getContext('2d');
        this.container.appendChild(this.canvas);

        // Size canvas with device pixel ratio for crisp rendering
        this.resize();
        window.addEventListener('resize', () => this.resize(), { passive: true });

        // Track mouse with velocity for flow effects
        document.addEventListener('mousemove', (e) => {
            this.lastMouseX = this.mouseX;
            this.lastMouseY = this.mouseY;
            this.mouseX = e.clientX;
            this.mouseY = e.clientY;
            this.mouseVelX = (this.mouseX - this.lastMouseX) * 0.3;
            this.mouseVelY = (this.mouseY - this.lastMouseY) * 0.3;
        }, { passive: true });

        // Touch support for mobile
        document.addEventListener('touchmove', (e) => {
            if (e.touches.length > 0) {
                const touch = e.touches[0];
                this.lastMouseX = this.mouseX;
                this.lastMouseY = this.mouseY;
                this.mouseX = touch.clientX;
                this.mouseY = touch.clientY;
                this.mouseVelX = (this.mouseX - this.lastMouseX) * 0.3;
                this.mouseVelY = (this.mouseY - this.lastMouseY) * 0.3;
            }
        }, { passive: true });

        // Create base particles (golden dust motes)
        this.createBaseParticles();

        // Start animation loop only if motion is allowed
        if (!MotionPreference.prefersReduced) {
            this.animate();
        } else {
            // Show static particles for reduced motion
            this.drawStaticParticles();
        }

        // Listen for motion preference changes
        MotionPreference.addListener((reduced) => {
            if (reduced) {
                cancelAnimationFrame(this.animationId);
                this.drawStaticParticles();
            } else {
                this.animate();
            }
        });

        // Sync with atmosphere every second
        this.syncWithAtmosphere();
        setInterval(() => this.syncWithAtmosphere(), 1000);
    }

    /**
     * Draw particles without animation for reduced motion preference
     */
    drawStaticParticles() {
        this.ctx.clearRect(0, 0, this.width, this.height);
        // Draw a subset of particles in fixed positions
        this.particles.slice(0, 20).forEach((p, i) => {
            this.ctx.globalAlpha = p.opacity * 0.5;
            this.ctx.fillStyle = `rgb(${parseInt(p.color.slice(1, 3), 16)}, ${parseInt(p.color.slice(3, 5), 16)}, ${parseInt(p.color.slice(5, 7), 16)})`;
            this.ctx.beginPath();
            this.ctx.arc(p.x, p.y, p.size, 0, Math.PI * 2);
            this.ctx.fill();
        });
        this.ctx.globalAlpha = 1;
    }

    resize() {
        const dpr = window.devicePixelRatio || 1;
        this.canvas.width = window.innerWidth * dpr;
        this.canvas.height = window.innerHeight * dpr;
        this.canvas.style.width = `${window.innerWidth}px`;
        this.canvas.style.height = `${window.innerHeight}px`;
        this.ctx.scale(dpr, dpr);
        this.width = window.innerWidth;
        this.height = window.innerHeight;
    }

    syncWithAtmosphere() {
        if (typeof atmosphere !== 'undefined' && atmosphere.initialized) {
            const prevCondition = this.weatherCondition;
            this.weatherCondition = atmosphere.condition;
            this.windSpeed = atmosphere.windSpeed;
            this.temperature = atmosphere.temperature;

            // Recreate weather particles if condition changed
            if (prevCondition !== this.weatherCondition) {
                this.createWeatherParticles();
                this.createWindStreaks();
            }
        }
    }

    // =========================================================================
    // PARTICLE CREATION
    // =========================================================================

    createBaseParticles() {
        this.particles = [];
        for (let i = 0; i < this.baseParticleCount; i++) {
            this.particles.push(this.createDustMote());
        }
    }

    createDustMote() {
        return {
            type: 'dust',
            x: Math.random() * this.width,
            y: Math.random() * this.height,
            vx: (Math.random() - 0.5) * 0.3,
            vy: -0.2 - Math.random() * 0.3, // Float upward
            size: 1.5 + Math.random() * 2.5,
            opacity: 0.3 + Math.random() * 0.4,
            color: { r: 212, g: 175, b: 55 }, // Gold
            life: 1,
            maxLife: 1,
            phase: Math.random() * Math.PI * 2, // For oscillation
            oscillationSpeed: 0.02 + Math.random() * 0.02,
            oscillationAmount: 0.5 + Math.random() * 1
        };
    }

    createWeatherParticles() {
        this.weatherParticles = [];
        this.sparkParticles = [];

        const condition = this.weatherCondition;
        const count = this.weatherParticleCount;

        switch (condition) {
            case 'clear':
            case 'mostly_clear':
                // Extra golden dust motes floating up
                for (let i = 0; i < count / 2; i++) {
                    const p = this.createDustMote();
                    p.size = 2 + Math.random() * 3;
                    p.opacity = 0.4 + Math.random() * 0.3;
                    this.weatherParticles.push(p);
                }
                break;

            case 'rain':
            case 'showers':
            case 'heavy_rain':
            case 'heavy_showers':
            case 'drizzle':
            case 'freezing_rain':
            case 'freezing_drizzle':
                for (let i = 0; i < count; i++) {
                    this.weatherParticles.push(this.createRainDrop(condition.includes('heavy')));
                }
                break;

            case 'snow':
            case 'heavy_snow':
            case 'snow_grains':
            case 'snow_showers':
                for (let i = 0; i < count; i++) {
                    this.weatherParticles.push(this.createSnowflake(condition.includes('heavy')));
                }
                break;

            case 'fog':
                for (let i = 0; i < count * 1.5; i++) {
                    this.weatherParticles.push(this.createFogParticle());
                }
                break;

            case 'thunderstorm':
                // Rain + occasional sparks
                for (let i = 0; i < count; i++) {
                    this.weatherParticles.push(this.createRainDrop(true));
                }
                this.scheduleSparkBurst();
                break;

            case 'overcast':
            case 'partly_cloudy':
                // Subtle grey particles drifting
                for (let i = 0; i < count / 3; i++) {
                    this.weatherParticles.push(this.createCloudParticle());
                }
                break;
        }
    }

    createRainDrop(heavy = false) {
        const windEffect = this.windSpeed * 0.02;
        return {
            type: 'rain',
            x: Math.random() * (this.width + 200) - 100,
            y: -20 - Math.random() * 100,
            vx: windEffect + (Math.random() - 0.5) * 0.5,
            vy: heavy ? 12 + Math.random() * 6 : 8 + Math.random() * 4,
            size: heavy ? 2 : 1.5,
            length: heavy ? 20 + Math.random() * 15 : 12 + Math.random() * 8,
            opacity: heavy ? 0.4 + Math.random() * 0.3 : 0.2 + Math.random() * 0.2,
            color: { r: 110, g: 164, b: 191 }, // Rain blue
            life: 1,
            maxLife: 1
        };
    }

    createSnowflake(heavy = false) {
        return {
            type: 'snow',
            x: Math.random() * this.width,
            y: -10 - Math.random() * 50,
            vx: (Math.random() - 0.5) * 1,
            vy: heavy ? 1.5 + Math.random() * 1.5 : 0.8 + Math.random() * 1,
            size: heavy ? 3 + Math.random() * 4 : 2 + Math.random() * 3,
            opacity: 0.6 + Math.random() * 0.3,
            color: { r: 255, g: 255, b: 255 },
            rotation: Math.random() * Math.PI * 2,
            rotationSpeed: (Math.random() - 0.5) * 0.05,
            phase: Math.random() * Math.PI * 2,
            oscillationSpeed: 0.03 + Math.random() * 0.02,
            oscillationAmount: 1.5 + Math.random() * 2,
            life: 1,
            maxLife: 1
        };
    }

    createFogParticle() {
        return {
            type: 'fog',
            x: Math.random() * this.width,
            y: Math.random() * this.height,
            vx: (Math.random() - 0.5) * 0.3,
            vy: (Math.random() - 0.5) * 0.1,
            size: 40 + Math.random() * 60,
            opacity: 0.02 + Math.random() * 0.04,
            color: { r: 180, g: 180, b: 190 },
            phase: Math.random() * Math.PI * 2,
            pulseSpeed: 0.005 + Math.random() * 0.005,
            life: 1,
            maxLife: 1
        };
    }

    createCloudParticle() {
        return {
            type: 'cloud',
            x: Math.random() * this.width,
            y: Math.random() * this.height,
            vx: (Math.random() - 0.5) * 0.2,
            vy: (Math.random() - 0.5) * 0.1,
            size: 20 + Math.random() * 30,
            opacity: 0.03 + Math.random() * 0.03,
            color: { r: 150, g: 150, b: 160 },
            life: 1,
            maxLife: 1
        };
    }

    createSparkParticle(x, y) {
        const angle = Math.random() * Math.PI * 2;
        const speed = 2 + Math.random() * 4;
        return {
            type: 'spark',
            x: x,
            y: y,
            vx: Math.cos(angle) * speed,
            vy: Math.sin(angle) * speed,
            size: 1 + Math.random() * 2,
            opacity: 0.8 + Math.random() * 0.2,
            color: { r: 255, g: 255, b: 200 }, // Electric yellow-white
            life: 1,
            maxLife: 0.3 + Math.random() * 0.3, // Short-lived
            decay: 0.95
        };
    }

    scheduleSparkBurst() {
        if (this.weatherCondition !== 'thunderstorm') return;

        const delay = 3000 + Math.random() * 8000;
        setTimeout(() => {
            // Create spark burst at random position (upper half of screen)
            const x = Math.random() * this.width;
            const y = Math.random() * this.height * 0.5;
            for (let i = 0; i < 15 + Math.random() * 20; i++) {
                this.sparkParticles.push(this.createSparkParticle(x, y));
            }
            this.scheduleSparkBurst();
        }, delay);
    }

    createWindStreaks() {
        this.windStreaks = [];
        if (this.windSpeed < 5) return;

        const streakCount = Math.min(30, Math.floor(this.windSpeed * 0.8));
        for (let i = 0; i < streakCount; i++) {
            this.windStreaks.push(this.createWindStreak());
        }
    }

    createWindStreak() {
        return {
            type: 'wind',
            x: -50,
            y: Math.random() * this.height,
            vx: 15 + this.windSpeed * 0.5 + Math.random() * 5,
            vy: (Math.random() - 0.5) * 2,
            length: 30 + Math.random() * 50 + this.windSpeed,
            opacity: 0.1 + Math.random() * 0.1,
            color: { r: 255, g: 255, b: 255 },
            life: 1,
            maxLife: 1
        };
    }

    // =========================================================================
    // ANIMATION LOOP (60fps)
    // =========================================================================

    animate(currentTime = 0) {
        this.deltaTime = Math.min((currentTime - this.lastTime) / 16.67, 3); // Cap at 3x normal
        this.lastTime = currentTime;

        // Clear canvas
        this.ctx.clearRect(0, 0, this.width, this.height);

        // Get atmosphere modifiers
        const driftX = parseFloat(getComputedStyle(document.documentElement).getPropertyValue('--atmosphere-particle-drift-x')) || 0;
        const driftY = parseFloat(getComputedStyle(document.documentElement).getPropertyValue('--atmosphere-particle-drift-y')) || -0.5;
        const turbulence = parseFloat(getComputedStyle(document.documentElement).getPropertyValue('--atmosphere-turbulence')) || 0;
        const particleOpacity = parseFloat(getComputedStyle(document.documentElement).getPropertyValue('--atmosphere-particle-opacity')) || 1;

        // Draw AQI haze overlay if air quality is poor
        this.drawAQIOverlay();

        // Draw temperature shimmer for hot days
        this.drawTemperatureShimmer();

        // Update and draw wind streaks
        this.updateWindStreaks();

        // Draw constellation connections between nearby particles
        this.drawConnections(particleOpacity);

        // Update and draw base particles
        this.updateParticles(this.particles, driftX, driftY, turbulence, particleOpacity);

        // Update and draw weather-specific particles
        this.updateWeatherParticles(driftX, turbulence, particleOpacity);

        // Update and draw spark particles (thunderstorm)
        this.updateSparkParticles();

        // Decay mouse velocity
        this.mouseVelX *= 0.95;
        this.mouseVelY *= 0.95;

        this.animationId = requestAnimationFrame((t) => this.animate(t));
    }

    // =========================================================================
    // PARTICLE UPDATES
    // =========================================================================

    updateParticles(particles, driftX, driftY, turbulence, opacityMod) {
        for (let i = 0; i < particles.length; i++) {
            const p = particles[i];

            // Mouse interaction - particles flow around cursor
            const dx = p.x - this.mouseX;
            const dy = p.y - this.mouseY;
            const dist = Math.sqrt(dx * dx + dy * dy);

            if (dist < this.mouseRadius && dist > 0) {
                const force = (this.mouseRadius - dist) / this.mouseRadius;
                const angle = Math.atan2(dy, dx);
                p.vx += Math.cos(angle) * force * this.mouseStrength * this.deltaTime;
                p.vy += Math.sin(angle) * force * this.mouseStrength * this.deltaTime;
                // Add mouse velocity for flow effect
                p.vx += this.mouseVelX * force * 0.1;
                p.vy += this.mouseVelY * force * 0.1;
            }

            // Particle-to-particle interaction (subtle attraction/repulsion)
            for (let j = i + 1; j < particles.length; j++) {
                const p2 = particles[j];
                const pdx = p2.x - p.x;
                const pdy = p2.y - p.y;
                const pdist = Math.sqrt(pdx * pdx + pdy * pdy);

                if (pdist < this.particleInteractionRadius && pdist > 0) {
                    // Soft repulsion when very close, subtle attraction at medium distance
                    let force;
                    if (pdist < 20) {
                        force = -0.01 * (20 - pdist) / 20; // Repulsion
                    } else {
                        force = 0.002 * (pdist - 20) / (this.particleInteractionRadius - 20); // Attraction
                    }

                    const angle = Math.atan2(pdy, pdx);
                    p.vx += Math.cos(angle) * force * this.deltaTime;
                    p.vy += Math.sin(angle) * force * this.deltaTime;
                    p2.vx -= Math.cos(angle) * force * this.deltaTime;
                    p2.vy -= Math.sin(angle) * force * this.deltaTime;
                }
            }

            // Atmospheric drift
            p.vx += driftX * 0.01 * this.deltaTime;
            p.vy += driftY * 0.01 * this.deltaTime;

            // Turbulence
            if (turbulence > 0) {
                p.vx += (Math.random() - 0.5) * turbulence * 0.05 * this.deltaTime;
                p.vy += (Math.random() - 0.5) * turbulence * 0.05 * this.deltaTime;
            }

            // Oscillation for floating effect
            if (p.phase !== undefined) {
                p.phase += p.oscillationSpeed * this.deltaTime;
                p.vx += Math.sin(p.phase) * p.oscillationAmount * 0.01 * this.deltaTime;
            }

            // Apply velocity with damping
            p.x += p.vx * this.deltaTime;
            p.y += p.vy * this.deltaTime;
            p.vx *= 0.98;
            p.vy *= 0.98;

            // Wrap around screen
            if (p.x < -10) p.x = this.width + 10;
            if (p.x > this.width + 10) p.x = -10;
            if (p.y < -10) p.y = this.height + 10;
            if (p.y > this.height + 10) p.y = -10;

            // Draw particle
            this.drawParticle(p, opacityMod);
        }
    }

    updateWeatherParticles(driftX, turbulence, opacityMod) {
        for (let i = this.weatherParticles.length - 1; i >= 0; i--) {
            const p = this.weatherParticles[i];

            switch (p.type) {
                case 'rain':
                    // Rain falls fast, affected by wind
                    p.x += (p.vx + driftX * 0.5) * this.deltaTime;
                    p.y += p.vy * this.deltaTime;

                    // Reset when off screen
                    if (p.y > this.height + 20) {
                        p.x = Math.random() * (this.width + 200) - 100;
                        p.y = -20 - Math.random() * 50;
                    }
                    break;

                case 'snow':
                    // Snowflakes drift and swirl
                    p.phase += p.oscillationSpeed * this.deltaTime;
                    p.x += (p.vx + Math.sin(p.phase) * p.oscillationAmount * 0.5 + driftX * 0.3) * this.deltaTime;
                    p.y += p.vy * this.deltaTime;
                    p.rotation += p.rotationSpeed * this.deltaTime;

                    // Reset when off screen
                    if (p.y > this.height + 20) {
                        p.x = Math.random() * this.width;
                        p.y = -10 - Math.random() * 30;
                    }
                    break;

                case 'fog':
                    // Fog drifts slowly, pulses opacity
                    p.phase += p.pulseSpeed * this.deltaTime;
                    p.x += p.vx * this.deltaTime;
                    p.y += p.vy * this.deltaTime;

                    // Wrap around
                    if (p.x < -p.size) p.x = this.width + p.size;
                    if (p.x > this.width + p.size) p.x = -p.size;
                    if (p.y < -p.size) p.y = this.height + p.size;
                    if (p.y > this.height + p.size) p.y = -p.size;
                    break;

                case 'cloud':
                case 'dust':
                    // Similar to base particles
                    p.x += (p.vx + driftX * 0.02) * this.deltaTime;
                    p.y += (p.vy + (p.type === 'dust' ? -0.3 : 0)) * this.deltaTime;

                    // Wrap around
                    if (p.x < -10) p.x = this.width + 10;
                    if (p.x > this.width + 10) p.x = -10;
                    if (p.y < -10) p.y = this.height + 10;
                    if (p.y > this.height + 10) p.y = -10;
                    break;
            }

            this.drawWeatherParticle(p, opacityMod);
        }
    }

    updateSparkParticles() {
        for (let i = this.sparkParticles.length - 1; i >= 0; i--) {
            const p = this.sparkParticles[i];

            p.x += p.vx * this.deltaTime;
            p.y += p.vy * this.deltaTime;
            p.vy += 0.1 * this.deltaTime; // Gravity
            p.vx *= p.decay;
            p.vy *= p.decay;
            p.life -= 0.02 * this.deltaTime;

            if (p.life <= 0) {
                this.sparkParticles.splice(i, 1);
                continue;
            }

            this.drawSparkParticle(p);
        }
    }

    updateWindStreaks() {
        for (let i = this.windStreaks.length - 1; i >= 0; i--) {
            const s = this.windStreaks[i];

            s.x += s.vx * this.deltaTime;
            s.y += s.vy * this.deltaTime;

            // Reset when off screen
            if (s.x > this.width + s.length) {
                s.x = -s.length;
                s.y = Math.random() * this.height;
            }

            this.drawWindStreak(s);
        }
    }

    // =========================================================================
    // DRAWING (GPU-accelerated via canvas compositing)
    // =========================================================================

    drawParticle(p, opacityMod) {
        const { r, g, b } = p.color;
        const alpha = p.opacity * opacityMod;

        this.ctx.beginPath();
        this.ctx.arc(p.x, p.y, p.size, 0, Math.PI * 2);
        this.ctx.fillStyle = `rgba(${r}, ${g}, ${b}, ${alpha})`;
        this.ctx.fill();

        // Glow effect
        const gradient = this.ctx.createRadialGradient(p.x, p.y, 0, p.x, p.y, p.size * 3);
        gradient.addColorStop(0, `rgba(${r}, ${g}, ${b}, ${alpha * 0.3})`);
        gradient.addColorStop(1, `rgba(${r}, ${g}, ${b}, 0)`);
        this.ctx.fillStyle = gradient;
        this.ctx.beginPath();
        this.ctx.arc(p.x, p.y, p.size * 3, 0, Math.PI * 2);
        this.ctx.fill();
    }

    drawWeatherParticle(p, opacityMod) {
        const { r, g, b } = p.color;

        switch (p.type) {
            case 'rain':
                // Rain as diagonal streaks
                const angle = Math.atan2(p.vy, p.vx);
                this.ctx.strokeStyle = `rgba(${r}, ${g}, ${b}, ${p.opacity * opacityMod})`;
                this.ctx.lineWidth = p.size;
                this.ctx.lineCap = 'round';
                this.ctx.beginPath();
                this.ctx.moveTo(p.x, p.y);
                this.ctx.lineTo(
                    p.x - Math.cos(angle) * p.length,
                    p.y - Math.sin(angle) * p.length
                );
                this.ctx.stroke();
                break;

            case 'snow':
                // Snowflakes as soft circles with rotation effect
                this.ctx.save();
                this.ctx.translate(p.x, p.y);
                this.ctx.rotate(p.rotation);

                const snowGradient = this.ctx.createRadialGradient(0, 0, 0, 0, 0, p.size);
                snowGradient.addColorStop(0, `rgba(255, 255, 255, ${p.opacity * opacityMod})`);
                snowGradient.addColorStop(0.5, `rgba(255, 255, 255, ${p.opacity * opacityMod * 0.5})`);
                snowGradient.addColorStop(1, `rgba(255, 255, 255, 0)`);

                this.ctx.fillStyle = snowGradient;
                this.ctx.beginPath();
                this.ctx.arc(0, 0, p.size, 0, Math.PI * 2);
                this.ctx.fill();

                this.ctx.restore();
                break;

            case 'fog':
                // Fog as large, soft, slowly pulsing circles
                const pulseOpacity = p.opacity * (0.7 + 0.3 * Math.sin(p.phase)) * opacityMod;
                const fogGradient = this.ctx.createRadialGradient(p.x, p.y, 0, p.x, p.y, p.size);
                fogGradient.addColorStop(0, `rgba(${r}, ${g}, ${b}, ${pulseOpacity})`);
                fogGradient.addColorStop(0.5, `rgba(${r}, ${g}, ${b}, ${pulseOpacity * 0.5})`);
                fogGradient.addColorStop(1, `rgba(${r}, ${g}, ${b}, 0)`);

                this.ctx.fillStyle = fogGradient;
                this.ctx.beginPath();
                this.ctx.arc(p.x, p.y, p.size, 0, Math.PI * 2);
                this.ctx.fill();
                break;

            case 'cloud':
            case 'dust':
                // Similar soft circles
                const cloudGradient = this.ctx.createRadialGradient(p.x, p.y, 0, p.x, p.y, p.size);
                cloudGradient.addColorStop(0, `rgba(${r}, ${g}, ${b}, ${p.opacity * opacityMod})`);
                cloudGradient.addColorStop(1, `rgba(${r}, ${g}, ${b}, 0)`);

                this.ctx.fillStyle = cloudGradient;
                this.ctx.beginPath();
                this.ctx.arc(p.x, p.y, p.size, 0, Math.PI * 2);
                this.ctx.fill();
                break;
        }
    }

    drawSparkParticle(p) {
        const { r, g, b } = p.color;
        const alpha = p.opacity * (p.life / p.maxLife);

        // Bright core
        this.ctx.fillStyle = `rgba(${r}, ${g}, ${b}, ${alpha})`;
        this.ctx.beginPath();
        this.ctx.arc(p.x, p.y, p.size, 0, Math.PI * 2);
        this.ctx.fill();

        // Glow
        const gradient = this.ctx.createRadialGradient(p.x, p.y, 0, p.x, p.y, p.size * 4);
        gradient.addColorStop(0, `rgba(${r}, ${g}, ${b}, ${alpha * 0.5})`);
        gradient.addColorStop(1, `rgba(${r}, ${g}, ${b}, 0)`);
        this.ctx.fillStyle = gradient;
        this.ctx.beginPath();
        this.ctx.arc(p.x, p.y, p.size * 4, 0, Math.PI * 2);
        this.ctx.fill();
    }

    drawWindStreak(s) {
        const { r, g, b } = s.color;

        const gradient = this.ctx.createLinearGradient(s.x - s.length, s.y, s.x, s.y);
        gradient.addColorStop(0, `rgba(${r}, ${g}, ${b}, 0)`);
        gradient.addColorStop(0.5, `rgba(${r}, ${g}, ${b}, ${s.opacity})`);
        gradient.addColorStop(1, `rgba(${r}, ${g}, ${b}, 0)`);

        this.ctx.strokeStyle = gradient;
        this.ctx.lineWidth = 1;
        this.ctx.beginPath();
        this.ctx.moveTo(s.x - s.length, s.y);
        this.ctx.lineTo(s.x, s.y);
        this.ctx.stroke();
    }

    drawConnections(opacityMod) {
        // Draw constellation lines between nearby particles
        const allParticles = [...this.particles];

        this.ctx.lineWidth = 0.5;

        for (let i = 0; i < allParticles.length; i++) {
            for (let j = i + 1; j < allParticles.length; j++) {
                const p1 = allParticles[i];
                const p2 = allParticles[j];
                const dx = p2.x - p1.x;
                const dy = p2.y - p1.y;
                const dist = Math.sqrt(dx * dx + dy * dy);

                if (dist < this.connectionDistance) {
                    const alpha = (1 - dist / this.connectionDistance) * this.connectionOpacity * opacityMod;
                    this.ctx.strokeStyle = `rgba(212, 175, 55, ${alpha})`;
                    this.ctx.beginPath();
                    this.ctx.moveTo(p1.x, p1.y);
                    this.ctx.lineTo(p2.x, p2.y);
                    this.ctx.stroke();
                }
            }
        }
    }

    drawAQIOverlay() {
        // AQI overlay - adds haze when air quality is poor
        // Simulated based on weather conditions (fog, overcast = higher perceived AQI)
        let hazeIntensity = 0;

        if (this.weatherCondition === 'fog') {
            hazeIntensity = 0.15;
        } else if (this.weatherCondition === 'overcast') {
            hazeIntensity = 0.05;
        } else if (this.aqi > 100) {
            hazeIntensity = Math.min(0.3, (this.aqi - 100) / 200);
        }

        if (hazeIntensity > 0) {
            const gradient = this.ctx.createRadialGradient(
                this.width / 2, this.height / 2, 0,
                this.width / 2, this.height / 2, Math.max(this.width, this.height) * 0.7
            );
            gradient.addColorStop(0, `rgba(180, 180, 170, 0)`);
            gradient.addColorStop(1, `rgba(180, 180, 170, ${hazeIntensity})`);

            this.ctx.fillStyle = gradient;
            this.ctx.fillRect(0, 0, this.width, this.height);
        }
    }

    drawTemperatureShimmer() {
        // Heat distortion effect for hot days (>30C / 86F)
        if (this.temperature <= 30) return;

        const intensity = Math.min(1, (this.temperature - 30) / 20); // 0-1 from 30-50C
        const time = Date.now() * 0.001;

        // Draw shimmering waves at the bottom of the screen
        const waveHeight = this.height * 0.15;
        const startY = this.height - waveHeight;

        for (let i = 0; i < 5; i++) {
            const waveOffset = Math.sin(time * (0.5 + i * 0.2) + i) * 10;
            const alpha = 0.02 * intensity * (1 - i / 5);

            this.ctx.fillStyle = `rgba(255, 200, 100, ${alpha})`;
            this.ctx.beginPath();
            this.ctx.moveTo(0, startY + waveOffset + i * 20);

            for (let x = 0; x <= this.width; x += 20) {
                const y = startY + waveOffset + i * 20 +
                    Math.sin(x * 0.02 + time + i) * 5 * intensity;
                this.ctx.lineTo(x, y);
            }

            this.ctx.lineTo(this.width, this.height);
            this.ctx.lineTo(0, this.height);
            this.ctx.closePath();
            this.ctx.fill();
        }
    }

    // =========================================================================
    // CLEANUP
    // =========================================================================

    destroy() {
        if (this.animationId) {
            cancelAnimationFrame(this.animationId);
        }
        if (this.canvas && this.canvas.parentNode) {
            this.canvas.parentNode.removeChild(this.canvas);
        }
    }
}

// ============================================================================
// COUNT-UP ANIMATION
// ============================================================================

class CountUp {
    constructor(element, endValue, duration = 2000) {
        this.element = element;
        this.endValue = endValue;
        this.duration = duration;
        this.startValue = 0;
        this.startTime = null;
        this.frameRequest = null;
    }

    start() {
        this.startTime = performance.now();
        this.animate();
    }

    animate(currentTime = performance.now()) {
        const elapsed = currentTime - this.startTime;
        const progress = Math.min(elapsed / this.duration, 1);
        
        // Ease out expo
        const easeProgress = 1 - Math.pow(1 - progress, 3);
        
        const currentValue = Math.round(this.startValue + (this.endValue - this.startValue) * easeProgress);
        
        this.element.textContent = currentValue;
        
        if (progress < 1) {
            this.frameRequest = requestAnimationFrame((t) => this.animate(t));
        }
    }

    cancel() {
        if (this.frameRequest) {
            cancelAnimationFrame(this.frameRequest);
        }
    }
}

// ============================================================================
// SUN VISUALIZATION
// ============================================================================

class SunVisualization {
    constructor(container) {
        this.container = container;
        this.sun = null;
        this.init();
    }

    init() {
        // Create sun element
        this.sun = document.createElement('div');
        this.sun.className = 'sun-marker';
        this.container.appendChild(this.sun);
        
        // Create arc path
        const arc = document.createElement('div');
        arc.style.cssText = `
            position: absolute;
            bottom: 60px;
            left: 15%;
            right: 15%;
            height: 120px;
            border: 2px dashed rgba(212, 175, 55, 0.2);
            border-bottom: none;
            border-radius: 120px 120px 0 0;
            pointer-events: none;
        `;
        this.container.appendChild(arc);
        
        // Create direction labels
        const positions = [
            { dir: 'S', x: '50%', y: 'calc(100% - 20px)', transform: 'translateX(-50%)' },
            { dir: 'W', x: '10px', y: '50%', transform: 'translateY(-50%)' },
            { dir: 'N', x: '50%', y: '20px', transform: 'translateX(-50%)' },
            { dir: 'E', x: 'calc(100% - 10px)', y: '50%', transform: 'translate(-100%, -50%)' }
        ];
        
        positions.forEach(({ dir, x, y, transform }) => {
            const label = document.createElement('span');
            label.className = `direction-label direction-${dir.toLowerCase()}`;
            label.textContent = dir;
            label.style.cssText = `
                position: absolute;
                left: ${x};
                top: ${y};
                transform: ${transform};
            `;
            this.container.appendChild(label);
        });
        
        // Create horizon line
        const horizon = document.createElement('div');
        horizon.style.cssText = `
            position: absolute;
            bottom: 60px;
            left: 10%;
            right: 10%;
            height: 1px;
            background: linear-gradient(90deg, transparent, var(--text-tertiary), transparent);
        `;
        this.container.appendChild(horizon);
    }

    update(azimuth, altitude) {
        if (!this.sun) return;
        
        const centerX = this.container.offsetWidth / 2;
        const centerY = this.container.offsetHeight - 60;
        const radius = Math.min(centerX, centerY) * 0.7;
        
        // Altitude affects vertical position
        const altitudeNorm = Math.max(0, altitude) / 90;
        const r = radius * (1 - altitudeNorm * 0.3);
        
        // Convert azimuth to radians (S is at bottom)
        const theta = (azimuth - 180) * Math.PI / 180;
        
        const x = centerX + r * Math.sin(theta);
        const y = centerY - r * altitudeNorm * 1.5 - (altitude > 0 ? altitude * 1.5 : 0);
        
        this.sun.style.left = `${x}px`;
        this.sun.style.top = `${Math.max(20, y)}px`;
        
        // Color based on altitude
        const hue = altitude < 15 ? 30 : altitude < 45 ? 45 : 50;
        const sat = altitude < 15 ? 100 : 90;
        const light = 50 + altitude * 0.3;
        this.sun.style.background = `hsl(${hue}, ${sat}%, ${light}%)`;
        this.sun.style.boxShadow = `0 0 ${20 + altitude}px hsla(${hue}, ${sat}%, ${light}%, 0.5)`;
        
        // Opacity based on day/night
        this.sun.style.opacity = altitude > 0 ? 1 : 0.3;
    }
}

// ============================================================================
// SHADE TABLE
// ============================================================================

class ShadeTable {
    constructor(container) {
        this.container = container;
        this.init();
    }

    init() {
        this.container.innerHTML = `
            <table class="data-table" role="table" aria-label="Shade level recommendations by window">
                <thead>
                    <tr>
                        <th scope="col">Shade</th>
                        <th scope="col">Room</th>
                        <th scope="col">Facing</th>
                        <th scope="col">Glare</th>
                        <th scope="col">Level</th>
                        <th scope="col">Reason</th>
                    </tr>
                </thead>
                <tbody id="shade-rows"></tbody>
            </table>
        `;
        this.tbody = this.container.querySelector('#shade-rows');
    }

    update(recommendations) {
        this.tbody.innerHTML = recommendations.map(r => `
            <tr>
                <td class="mono" style="color: ${DIRECTIONS[r.facing].color}">${r.name}</td>
                <td>${r.room}</td>
                <td>
                    <span style="display: inline-flex; align-items: center; gap: 6px;">
                        <span style="width: 8px; height: 8px; border-radius: 50%; background: ${DIRECTIONS[r.facing].color}"></span>
                        ${r.facing}
                    </span>
                </td>
                <td>
                    <div class="shade-indicator">
                        <div class="shade-fill" style="width: ${r.intensity * 100}%; background: ${r.intensity > 0.5 ? 'var(--warning)' : 'var(--success)'}"></div>
                    </div>
                </td>
                <td class="mono" style="color: ${r.level < 50 ? 'var(--warning)' : 'var(--success)'}">${r.level}%</td>
                <td style="font-size: var(--text-xs); color: var(--text-tertiary); max-width: 200px;">${r.reason}</td>
            </tr>
        `).join('');
    }
}

// ============================================================================
// KONAMI CODE
// ============================================================================

class KonamiCode {
    constructor(callback) {
        this.callback = callback;
        this.sequence = [];
        this.init();
    }

    init() {
        document.addEventListener('keydown', (e) => {
            this.sequence.push(e.key);
            this.sequence = this.sequence.slice(-KONAMI.length);
            
            if (this.sequence.join(',') === KONAMI.join(',')) {
                this.callback();
                this.sequence = [];
            }
        });
    }
}

// ============================================================================
// SECRET WORD — Type a word anywhere to trigger easter eggs
// ============================================================================

class SecretWord {
    constructor(words, callback) {
        this.words = words.map(w => w.toLowerCase());
        this.callback = callback;
        this.buffer = '';
        this.timeout = null;
        this.init();
        console.log('%c🔑 Secret words activated:', 'color: #666;', this.words.join(', '));
    }

    init() {
        document.addEventListener('keypress', (e) => {
            // Ignore if user is typing in an input/textarea/contenteditable
            const target = e.target;
            if (target.tagName === 'INPUT' || 
                target.tagName === 'TEXTAREA' || 
                target.isContentEditable) return;
            
            // Get the typed character
            const char = e.key.toLowerCase();
            
            // Only track single letters
            if (char.length === 1 && /[a-z]/.test(char)) {
                this.buffer += char;
                
                // Keep buffer to max word length + some slack
                const maxLen = Math.max(...this.words.map(w => w.length)) + 5;
                this.buffer = this.buffer.slice(-maxLen);
                
                // Check if any secret word is at the end of the buffer
                for (const word of this.words) {
                    if (this.buffer.endsWith(word)) {
                        console.log('%c🎉 Secret word detected:', 'color: #D4AF37;', word);
                        this.callback(word);
                        this.buffer = '';
                        break;
                    }
                }
                
                // Clear buffer after 3 seconds of inactivity
                clearTimeout(this.timeout);
                this.timeout = setTimeout(() => {
                    this.buffer = '';
                }, 3000);
            }
        });
    }
}

// ============================================================================
// DEVICE ORIENTATION — Accelerometer & Magnetometer for Compass
// ============================================================================

class DeviceOrientation {
    constructor() {
        this.alpha = 0;       // Compass heading (0-360, 0=North)
        this.beta = 0;        // Front-back tilt (-180 to 180)
        this.gamma = 0;       // Left-right tilt (-90 to 90)
        this.heading = 0;     // Absolute compass heading (if available)
        this.hasPermission = false;
        this.isSupported = false;
        this.isCalibrated = false;
        this.listeners = [];
        this.permissionKey = 'weather_orientation_permission';

        this.checkSupport();
        this.loadStoredPermission();
    }

    /**
     * Check if device orientation APIs are supported
     */
    checkSupport() {
        this.isSupported = 'DeviceOrientationEvent' in window ||
                          'DeviceMotionEvent' in window;

        // Check for absolute orientation (compass)
        this.hasAbsoluteOrientation = 'AbsoluteOrientationSensor' in window ||
            (typeof DeviceOrientationEvent !== 'undefined' &&
             'requestPermission' in DeviceOrientationEvent);
    }

    /**
     * Load permission state from localStorage
     */
    loadStoredPermission() {
        try {
            const stored = localStorage.getItem(this.permissionKey);
            if (stored === 'granted') {
                this.hasPermission = true;
                // Auto-start if permission was previously granted
                this.startListening();
            }
        } catch (e) {
            console.warn('[Orientation] Could not read localStorage:', e);
        }
    }

    /**
     * Store permission state in localStorage
     */
    storePermission(granted) {
        try {
            localStorage.setItem(this.permissionKey, granted ? 'granted' : 'denied');
        } catch (e) {
            console.warn('[Orientation] Could not write localStorage:', e);
        }
    }

    /**
     * Request permission for device orientation (iOS 13+ requires user gesture)
     * @returns {Promise<boolean>} Whether permission was granted
     */
    async requestPermission() {
        if (!this.isSupported) {
            console.log('[Orientation] Device orientation not supported');
            return false;
        }

        // iOS 13+ requires explicit permission request
        if (typeof DeviceOrientationEvent !== 'undefined' &&
            typeof DeviceOrientationEvent.requestPermission === 'function') {
            try {
                const permission = await DeviceOrientationEvent.requestPermission();
                this.hasPermission = permission === 'granted';
                this.storePermission(this.hasPermission);

                if (this.hasPermission) {
                    console.log('%c[Orientation] Permission granted', 'color: #4ECB71;');
                    this.startListening();
                } else {
                    console.log('%c[Orientation] Permission denied', 'color: #FF6B6B;');
                }
                return this.hasPermission;
            } catch (error) {
                console.error('[Orientation] Permission request failed:', error);
                return false;
            }
        }

        // Android and desktop - no permission needed, just start listening
        this.hasPermission = true;
        this.storePermission(true);
        this.startListening();
        return true;
    }

    /**
     * Start listening to device orientation events
     */
    startListening() {
        if (!this.isSupported || !this.hasPermission) return;

        // Try absolute orientation first (gives true compass heading)
        if ('ondeviceorientationabsolute' in window) {
            window.addEventListener('deviceorientationabsolute',
                (e) => this.handleOrientation(e, true), { passive: true });
            console.log('%c[Orientation] Using absolute orientation (compass)', 'color: #64D9FF;');
        } else {
            // Fall back to regular device orientation
            window.addEventListener('deviceorientation',
                (e) => this.handleOrientation(e, false), { passive: true });
            console.log('%c[Orientation] Using relative orientation', 'color: #FFAB40;');
        }

        // Also listen to device motion for better tilt data
        window.addEventListener('devicemotion',
            (e) => this.handleMotion(e), { passive: true });
    }

    /**
     * Handle device orientation event
     */
    handleOrientation(event, isAbsolute) {
        // Alpha: compass direction (0-360), Beta: front-back tilt, Gamma: left-right tilt
        this.alpha = event.alpha || 0;
        this.beta = event.beta || 0;
        this.gamma = event.gamma || 0;

        // For absolute orientation, alpha IS the compass heading
        // 0 = North, 90 = East, 180 = South, 270 = West
        if (isAbsolute && event.absolute) {
            this.heading = this.alpha;
            this.isCalibrated = true;
        } else if (event.webkitCompassHeading !== undefined) {
            // iOS provides compass heading separately
            this.heading = event.webkitCompassHeading;
            this.isCalibrated = true;
        } else {
            // Relative orientation - alpha is arbitrary starting point
            this.heading = this.alpha;
            this.isCalibrated = false;
        }

        // Notify all listeners
        this.notifyListeners();
    }

    /**
     * Handle device motion event (accelerometer data)
     */
    handleMotion(event) {
        // Can be used for more precise tilt calculations
        // or to detect device shake for calibration
        if (event.accelerationIncludingGravity) {
            // Could use for advanced leveling, but orientation is sufficient
        }
    }

    /**
     * Add a listener for orientation updates
     */
    addListener(callback) {
        this.listeners.push(callback);
    }

    /**
     * Remove a listener
     */
    removeListener(callback) {
        this.listeners = this.listeners.filter(l => l !== callback);
    }

    /**
     * Notify all listeners of orientation change
     */
    notifyListeners() {
        const data = {
            alpha: this.alpha,
            beta: this.beta,
            gamma: this.gamma,
            heading: this.heading,
            isCalibrated: this.isCalibrated,
            // Computed values for easy use
            compassHeading: this.heading,
            tiltX: this.gamma,  // Left-right tilt
            tiltY: this.beta,   // Front-back tilt
            isLevel: Math.abs(this.beta) < 10 && Math.abs(this.gamma) < 10
        };

        this.listeners.forEach(callback => callback(data));
    }

    /**
     * Get current orientation data
     */
    getData() {
        return {
            alpha: this.alpha,
            beta: this.beta,
            gamma: this.gamma,
            heading: this.heading,
            isCalibrated: this.isCalibrated,
            hasPermission: this.hasPermission,
            isSupported: this.isSupported
        };
    }
}

// Global device orientation instance
const deviceOrientation = new DeviceOrientation();

// ============================================================================
// CELESTIAL SKY — Sun, Moon, and Sundial
// ============================================================================

class CelestialSky {
    constructor() {
        this.container = null;
        this.sunElement = null;
        this.moonElement = null;
        this.sundialShadow = null;
        this.infoPanel = null;
        this.initialized = false;
    }

    init() {
        // DISABLED: Using compass-sundial in HTML instead
        // The compass-sundial already has sun indicator and shadow
        // This class now only provides update() for time synchronization
        
        // Reference the existing compass-sundial elements
        this.sunElement = document.getElementById('compass-sun-indicator');
        this.sundialShadow = document.getElementById('compass-shadow');
        
        // Hide the old hero-sun if it exists
        const oldHeroSun = document.querySelector('.hero-sun');
        if (oldHeroSun) {
            oldHeroSun.style.display = 'none';
        }
        
        this.initialized = true;
    }

    createHourMarkers() {
        // Simplified: only 4 cardinal marks (12, 3, 6, 9) - cleaner visual
        const markers = [];
        const cardinals = [
            { hour: 0, label: 'XII', angle: -90 },   // 12 at top
            { hour: 3, label: 'III', angle: 0 },     // 3 at right
            { hour: 6, label: 'VI', angle: 90 },     // 6 at bottom
            { hour: 9, label: 'IX', angle: 180 }     // 9 at left
        ];

        for (const c of cardinals) {
            markers.push(`
                <div class="sundial-hour-marker cardinal"
                     style="--angle: ${c.angle}deg">
                    <span class="sundial-numeral">${c.label}</span>
                </div>
            `);
        }

        // Add subtle tick marks for non-cardinal hours (no labels)
        for (let i = 0; i < 12; i++) {
            if (i % 3 !== 0) { // Skip cardinals
                const angle = (i * 30) - 90;
                markers.push(`
                    <div class="sundial-tick-only" style="--angle: ${angle}deg"></div>
                `);
            }
        }

        return markers.join('');
    }

    /**
     * Update celestial positions based on current time
     */
    update(date = new Date()) {
        // DISABLED: CompassSundial class now handles all updates
        // The compass-sundial in the hero section has its own sun indicator and shadow
        return;
    }

    /**
     * Convert azimuth/altitude to screen position in hero section
     */
    celestialToScreen(azimuth, altitude, bodyType = 'sun') {
        const heroRect = this.container.getBoundingClientRect();
        const width = heroRect.width;
        const height = heroRect.height;

        // Map azimuth to horizontal position
        // East (90) = left, South (180) = center, West (270) = right
        // Normalize to 0-1 where East=0, West=1
        let normalizedAz = ((azimuth - 90) % 360) / 180;
        if (normalizedAz < 0) normalizedAz += 2;
        if (normalizedAz > 1) normalizedAz = 2 - normalizedAz; // Mirror for night side

        // X position: 10% to 90% of width
        const x = 0.1 * width + normalizedAz * 0.8 * width;

        // Map altitude to vertical position
        // Higher altitude = higher on screen (lower Y value)
        // Altitude ranges from -90 to 90, but we care about 0-90 mostly
        const normalizedAlt = Math.max(0, Math.min(1, altitude / 90));

        // Y position: 80% at horizon, 15% at zenith
        const horizonY = height * 0.75;
        const zenithY = height * 0.15;
        const y = horizonY - normalizedAlt * (horizonY - zenithY);

        return { x, y, altitude };
    }

    updateSunPosition(sun) {
        if (!this.sunElement) return;

        const pos = this.celestialToScreen(sun.azimuth, sun.altitude, 'sun');

        // Position the sun
        this.sunElement.style.left = `${pos.x}px`;
        this.sunElement.style.top = `${pos.y}px`;

        // Adjust appearance based on altitude
        const isVisible = sun.altitude > -5;
        const isDay = sun.altitude > 0;
        const isTwilight = sun.altitude <= 0 && sun.altitude > -18;

        // Opacity and visibility
        if (sun.altitude > 10) {
            this.sunElement.style.opacity = '1';
        } else if (sun.altitude > 0) {
            this.sunElement.style.opacity = '0.8';
        } else if (isTwilight) {
            this.sunElement.style.opacity = `${0.3 + (sun.altitude + 18) / 18 * 0.4}`;
        } else {
            this.sunElement.style.opacity = '0.1';
        }

        // Color temperature based on altitude (golden hour effect)
        let hue, saturation, lightness;
        if (sun.altitude < 5) {
            // Golden/red at horizon
            hue = 25 + sun.altitude * 2;
            saturation = 100;
            lightness = 50 + sun.altitude;
        } else if (sun.altitude < 20) {
            // Warm yellow
            hue = 45;
            saturation = 95;
            lightness = 55;
        } else {
            // Bright white-yellow
            hue = 50;
            saturation = 90;
            lightness = 60;
        }

        this.sunElement.style.setProperty('--sun-hue', hue);
        this.sunElement.style.setProperty('--sun-saturation', `${saturation}%`);
        this.sunElement.style.setProperty('--sun-lightness', `${lightness}%`);

        // Scale based on altitude (bigger at horizon due to atmospheric lensing)
        const scale = sun.altitude < 10 ? 1.3 - sun.altitude * 0.03 : 1;
        this.sunElement.style.setProperty('--sun-scale', scale);

        // Visibility class
        this.sunElement.classList.toggle('below-horizon', !isDay);
        this.sunElement.classList.toggle('twilight', isTwilight && !isDay);
    }

    updateMoonPosition(moon) {
        if (!this.moonElement) return;

        const pos = this.celestialToScreen(moon.azimuth, moon.altitude, 'moon');

        // Position the moon
        this.moonElement.style.left = `${pos.x}px`;
        this.moonElement.style.top = `${pos.y}px`;

        // Visibility based on altitude
        const isVisible = moon.altitude > -5;
        this.moonElement.style.opacity = isVisible ?
            Math.min(1, 0.5 + moon.altitude / 20) : '0.15';

        // Update phase shadow
        const phaseShadow = this.moonElement.querySelector('.moon-phase-shadow');
        if (phaseShadow) {
            // Calculate shadow position for phase visualization
            // At new moon (phase=0): shadow covers right side
            // At first quarter (phase=0.25): shadow covers left half
            // At full moon (phase=0.5): no shadow
            // At last quarter (phase=0.75): shadow covers right half

            const phase = moon.phase;
            const illumination = moon.illumination;

            // Shadow gradient direction
            if (phase < 0.5) {
                // Waxing: shadow recedes from right
                const shadowPos = (1 - phase * 2) * 100;
                phaseShadow.style.background = `linear-gradient(90deg,
                    transparent ${100 - shadowPos}%,
                    rgba(0,0,0,0.85) ${100 - shadowPos + 10}%
                )`;
            } else {
                // Waning: shadow advances from right
                const shadowPos = ((phase - 0.5) * 2) * 100;
                phaseShadow.style.background = `linear-gradient(270deg,
                    transparent ${100 - shadowPos}%,
                    rgba(0,0,0,0.85) ${100 - shadowPos + 10}%
                )`;
            }
        }

        // Moon glow intensity based on illumination
        this.moonElement.style.setProperty('--moon-glow', moon.illumination / 100);

        // Visibility class
        this.moonElement.classList.toggle('below-horizon', moon.altitude < 0);
        this.moonElement.dataset.phase = moon.phaseName.toLowerCase().replace(' ', '-');
    }

    updateSundial(sun) {
        if (!this.sundialShadow) return;

        // Sundial shadow points opposite to sun direction
        // At solar noon, sun is at azimuth ~180 (south), shadow points north (up on dial)
        // Shadow angle = sun azimuth + 180 (mod 360), then adjust for dial orientation

        // Convert sun azimuth to hour angle style shadow
        // Solar noon (sun at south, az=180) = shadow points to 12 (top)
        // Morning (sun at east, az=90) = shadow points to 6 (left if dial faces north)
        // For a south-facing horizontal sundial in northern hemisphere:
        // Shadow angle = -(hour angle) where hour angle = (solar_time - 12) * 15

        // Simplified: shadow rotates opposite to sun position
        // When sun is at azimuth A, shadow points at A + 180
        const shadowAngle = (sun.azimuth + 180) % 360;

        // Adjust for sundial orientation (12 at top = -90 offset)
        const dialAngle = shadowAngle - 90;

        this.sundialShadow.style.setProperty('--shadow-rotation', `${dialAngle}deg`);

        // Shadow length based on sun altitude
        // Higher sun = shorter shadow
        const shadowLength = sun.altitude > 0 ?
            Math.min(95, 30 + (90 - sun.altitude) * 0.8) : 95;
        this.sundialShadow.style.setProperty('--shadow-length', `${shadowLength}%`);

        // Shadow visibility
        const isDay = sun.altitude > 0;
        this.sundialShadow.style.opacity = isDay ? '1' : '0.15';

        // Sundial face lighting based on sun altitude
        const sundialFace = this.container.querySelector('.sundial-face');
        if (sundialFace) {
            sundialFace.style.setProperty('--ambient-light', isDay ? '1' : '0.3');
        }
    }

    // Info panel removed - clicking sun/moon logs to console for details

    showSunDetails() {
        if (!sound.initialized) sound.init();
        sound.playClick();

        const lat = atmosphere.latitude || HOME.latitude;
        const lon = atmosphere.longitude || HOME.longitude;
        const sun = Ephemeris.sunPosition(lat, lon);
        const times = Ephemeris.sunTimes(lat, lon);

        console.log('%c\u2600\uFE0F Sun Position', 'color: #FFD700; font-weight: bold; font-size: 14px;');
        console.table({
            'Azimuth': `${sun.azimuth}°`,
            'Altitude': `${sun.altitude}°`,
            'Direction': sun.direction,
            'Is Day': sun.isDay ? 'Yes' : 'No',
            'Sunrise': times.sunrise?.toLocaleTimeString() || 'N/A',
            'Sunset': times.sunset?.toLocaleTimeString() || 'N/A',
            'Solar Noon': times.solarNoon?.toLocaleTimeString() || 'N/A'
        });
    }

    showMoonDetails() {
        if (!sound.initialized) sound.init();
        sound.playClick();

        const lat = atmosphere.latitude || HOME.latitude;
        const lon = atmosphere.longitude || HOME.longitude;
        const moon = Ephemeris.moonPosition(lat, lon);

        console.log('%c\uD83C\uDF19 Moon Position', 'color: #C0C0C0; font-weight: bold; font-size: 14px;');
        console.table({
            'Azimuth': `${moon.azimuth}°`,
            'Altitude': `${moon.altitude}°`,
            'Phase': moon.phaseName,
            'Illumination': `${moon.illumination}%`,
            'Is Visible': moon.isVisible ? 'Yes' : 'No',
            'Is Waxing': moon.isWaxing ? 'Yes' : 'No'
        });
    }

    // =========================================================================
    // DEVICE ORIENTATION INTEGRATION
    // =========================================================================

    /**
     * Request orientation permission when user taps sundial
     */
    async requestOrientationPermission() {
        if (!sound.initialized) sound.init();

        if (deviceOrientation.hasPermission) {
            // Already have permission - show debug info
            sound.playClick();
            this.showOrientationDebug();
            return;
        }

        if (!deviceOrientation.isSupported) {
            sound.playClick();
            console.log('%c[Compass] Device orientation not supported on this device', 'color: #FF6B6B;');
            return;
        }

        // Request permission (requires user gesture - this tap counts)
        const granted = await deviceOrientation.requestPermission();

        if (granted) {
            sound.playSuccess();
            this.orientationEnabled = true;
            this.updateOrientationIndicator(true);
            console.log('%c[Compass] Orientation enabled! Dial will now level and track compass heading.', 'color: #4ECB71;');
        } else {
            sound.playClick();
            console.log('%c[Compass] Permission denied', 'color: #FF6B6B;');
        }
    }

    /**
     * Handle orientation data updates
     */
    handleOrientationUpdate(data) {
        if (!this.orientationEnabled) return;

        this.deviceHeading = data.compassHeading;
        this.deviceTiltX = data.tiltX;
        this.deviceTiltY = data.tiltY;

        // Apply leveling transform to sundial
        this.applyLeveling(data);

        // Adjust celestial positions based on device heading
        this.adjustCelestialForCompass(data);
    }

    /**
     * Apply leveling transform to keep dial level regardless of device tilt
     */
    applyLeveling(data) {
        if (!this.sundialElement) return;

        // Counter-rotate the dial to compensate for device tilt
        // Beta = front-back tilt (pitch)
        // Gamma = left-right tilt (roll)
        const beta = data.beta || 0;
        const gamma = data.gamma || 0;

        // Clamp values for safety
        const clampedBeta = Math.max(-60, Math.min(60, beta));
        const clampedGamma = Math.max(-60, Math.min(60, gamma));

        // Apply 3D transform to level the dial
        const sundialFace = this.sundialElement.querySelector('.sundial-face');
        if (sundialFace) {
            sundialFace.style.transform = `
                rotateX(${-clampedBeta}deg)
                rotateY(${clampedGamma}deg)
            `;
            sundialFace.style.transition = 'transform 100ms ease-out';
        }

        // Show level indicator
        const isLevel = Math.abs(beta) < 5 && Math.abs(gamma) < 5;
        this.sundialElement.classList.toggle('is-level', isLevel);
    }

    /**
     * Adjust sun and moon positions based on compass heading
     * This makes them point to their true direction in the real world
     */
    adjustCelestialForCompass(data) {
        if (!data.isCalibrated) return;

        const heading = data.compassHeading;

        // The container needs to rotate based on device heading
        // When device points north (heading=0), north should be up
        // When device points east (heading=90), we need to rotate container -90deg
        // so that the north marker still points to real-world north

        if (this.container) {
            // Rotate the entire celestial container to match compass
            this.container.style.setProperty('--compass-rotation', `${-heading}deg`);
        }

        // Also update sun/moon absolute positions if desired
        // This would make them appear at their real-world azimuth
        // relative to the device's current orientation
    }

    /**
     * Update visual indicator showing orientation is active
     */
    updateOrientationIndicator(enabled) {
        if (!this.sundialElement) return;

        if (enabled) {
            this.sundialElement.classList.add('orientation-enabled');
            this.sundialElement.setAttribute('aria-label', 'Compass orientation active - dial is leveled');

            // Add a small compass indicator
            let indicator = this.sundialElement.querySelector('.orientation-indicator');
            if (!indicator) {
                indicator = document.createElement('div');
                indicator.className = 'orientation-indicator';
                indicator.innerHTML = `
                    <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2">
                        <circle cx="12" cy="12" r="10"/>
                        <polygon points="12,2 14,10 12,8 10,10" fill="currentColor"/>
                    </svg>
                `;
                this.sundialElement.appendChild(indicator);
            }
        } else {
            this.sundialElement.classList.remove('orientation-enabled');
        }
    }

    /**
     * Show orientation debug information
     */
    showOrientationDebug() {
        const data = deviceOrientation.getData();
        console.log('%c🧭 Device Orientation', 'color: #64D9FF; font-weight: bold; font-size: 14px;');
        console.table({
            'Compass Heading': `${data.heading.toFixed(1)}°`,
            'Tilt X (Gamma)': `${data.gamma.toFixed(1)}°`,
            'Tilt Y (Beta)': `${data.beta.toFixed(1)}°`,
            'Alpha': `${data.alpha.toFixed(1)}°`,
            'Calibrated': data.isCalibrated ? 'Yes' : 'No',
            'Permission': data.hasPermission ? 'Granted' : 'Denied'
        });
    }
}

// Global celestial sky instance
const celestialSky = new CelestialSky();

// ============================================================================
// CELESTIAL VOICE — Expressive spoken weather narration
// ============================================================================

class CelestialVoice {
    constructor() {
        this.synth = window.speechSynthesis;
        this.voice = null;
        this.lastSpoken = 0;
        this.cooldown = 3000; // Prevent spam clicks
        this.speaking = false;

        // Response templates organized by mood
        this.templates = {
            // CLEAR conditions
            clear: {
                freezing: [
                    "{temp} degrees. Crystal clear and absolutely freezing. The stars must be incredible tonight.",
                    "A brilliant {temp}. The cold has made the sky impossibly sharp.",
                    "{temp} degrees under a flawless sky. Winter at its most honest.",
                ],
                cold: [
                    "{temp} degrees. The cold has a clarity to it today.",
                    "A crisp {temp}. The kind of cold that wakes you up.",
                    "{temp} degrees and clear. Wrap yourself in something warm.",
                ],
                cool: [
                    "{temp} degrees. Fresh and invigorating.",
                    "A lovely {temp} today. Jacket weather, but the good kind.",
                    "{temp} degrees of autumn energy. Perfect for a walk.",
                ],
                mild: [
                    "{temp} degrees... rather pleasant, actually.",
                    "A gentle {temp}. The air itself feels kind today.",
                    "{temp} degrees. Neither here nor there. Just... nice.",
                ],
                warm: [
                    "{temp} degrees... a perfect day. The kind where everything feels possible.",
                    "A beautiful {temp}. What are you going to do with all this sunshine?",
                    "{temp} degrees of pure invitation. The world is offering itself to you.",
                ],
                hot: [
                    "{temp}... the air itself feels heavy. Find some shade.",
                    "{temp} degrees of summer pressing down. Stay hydrated.",
                    "It's {temp} out there. The sun means business today.",
                ],
                scorching: [
                    "{temp} degrees. Seriously. Stay inside if you can.",
                    "A brutal {temp}. The heat is not playing around.",
                    "{temp} degrees of raw solar intensity. Respect the sun today.",
                ],
            },

            // CLOUDY conditions
            cloudy: {
                freezing: [
                    "{temp} degrees under heavy clouds. A grey blanket over winter.",
                    "A muted {temp}. The clouds are hoarding all the light.",
                    "{temp} degrees. Cold and contemplative.",
                ],
                cold: [
                    "{temp} degrees. The grey sky feels close today.",
                    "A soft {temp} under cloud cover. Cozy weather.",
                    "{temp} degrees. The clouds are thinking about something.",
                ],
                cool: [
                    "{temp} degrees under grey skies. Contemplative weather.",
                    "A thoughtful {temp}. Good day for introspection.",
                    "{temp} degrees. The sky is keeping its secrets.",
                ],
                mild: [
                    "{temp} degrees. Neutral. The weather is noncommittal today.",
                    "A quiet {temp}. The clouds soften everything.",
                    "{temp} degrees. An in-between kind of day.",
                ],
                warm: [
                    "{temp} degrees with cloud cover. Warm but not harsh.",
                    "A gentle {temp}. The clouds are doing you a favor.",
                    "{temp} degrees. Comfortable warmth without the glare.",
                ],
                hot: [
                    "{temp} degrees, even with clouds. The heat finds a way.",
                    "A muggy {temp}. The clouds trap the warmth like a lid.",
                    "{temp} degrees of humid heaviness. The air is thick.",
                ],
                scorching: [
                    "{temp} degrees despite the clouds. Oppressive.",
                    "A suffocating {temp}. No relief from the grey.",
                    "{temp} degrees. The heat wins, clouds or not.",
                ],
            },

            // RAIN conditions
            rain: {
                freezing: [
                    "{temp} degrees of freezing rain. Ice is forming. Be careful.",
                    "A treacherous {temp}. The rain is turning to ice.",
                    "{temp} degrees. The rain stings today.",
                ],
                cold: [
                    "{temp} degrees, with rain washing the world clean.",
                    "A wet {temp}. The rain has its own music today.",
                    "{temp} degrees. Wet, grey, and honestly? Kind of perfect for staying in.",
                ],
                cool: [
                    "{temp} degrees of Seattle authenticity. Let it rain.",
                    "A rainy {temp}. The pavement is singing.",
                    "{temp} degrees. The clouds are finally letting go.",
                ],
                mild: [
                    "{temp} degrees with rain. Warm enough to enjoy it.",
                    "A soft {temp}. This is the good kind of rain.",
                    "{temp} degrees. The rain feels almost gentle.",
                ],
                warm: [
                    "{temp} degrees of warm rain. Almost tropical.",
                    "A balmy {temp}. The rain is refreshing, not punishing.",
                    "{temp} degrees. Dancing in this rain would be appropriate.",
                ],
                hot: [
                    "{temp} degrees with rain. Steam rising from the streets.",
                    "A steamy {temp}. The rain evaporates before it lands.",
                    "{temp} degrees. The rain brings no relief.",
                ],
                scorching: [
                    "{temp} degrees even with rain. How is this possible?",
                    "A monsoon {temp}. Hot and wet and relentless.",
                    "{temp} degrees. The rain is warm as bathwater.",
                ],
            },

            // SNOW conditions
            snow: {
                freezing: [
                    "{temp} degrees. The world is wrapped in white silence.",
                    "A frozen {temp}. Snow falling like a secret.",
                    "{temp} degrees. Everything sounds softer under snow.",
                ],
                cold: [
                    "{temp} degrees of winter magic. Snow is falling.",
                    "A snowy {temp}. The world is being rewritten in white.",
                    "{temp} degrees. Each flake a tiny miracle.",
                ],
                cool: [
                    "{temp} degrees with wet snow. Almost magical.",
                    "A slushy {temp}. The snow can't quite commit.",
                    "{temp} degrees. Snow and rain can't decide.",
                ],
                mild: [
                    "{temp} degrees... snow? Really? Nature is confused.",
                    "An unusual {temp}. Snow that probably won't stick.",
                    "{temp} degrees. The warmest snow you'll ever see.",
                ],
                warm: [
                    "{temp} degrees and... snowing? Check the sensors.",
                    "A very confused {temp}. This snow is a rebel.",
                    "{temp} degrees. Either the thermometer or the sky is wrong.",
                ],
            },

            // FOG conditions
            fog: {
                freezing: [
                    "{temp} degrees in freezing fog. The world has dissolved.",
                    "A spectral {temp}. Ice crystals hang in the air.",
                    "{temp} degrees. The fog bites.",
                ],
                cold: [
                    "{temp} degrees. The fog holds everything in mystery.",
                    "A muffled {temp}. The world ends at your doorstep.",
                    "{temp} degrees, shrouded. The city has disappeared.",
                ],
                cool: [
                    "{temp} degrees in the mist. Atmospheric.",
                    "A dreamy {temp}. The fog softens all the edges.",
                    "{temp} degrees. Some days the sky comes down to meet you.",
                ],
                mild: [
                    "{temp} degrees wrapped in fog. Gentle and strange.",
                    "A mysterious {temp}. What lies beyond the grey?",
                    "{temp} degrees. The fog makes everything intimate.",
                ],
                warm: [
                    "{temp} degrees in warm fog. Almost tropical.",
                    "A humid {temp}. The fog clings to everything.",
                    "{temp} degrees. The air is thick with moisture.",
                ],
            },

            // THUNDERSTORM conditions
            thunderstorm: {
                freezing: [
                    "{temp} degrees with thunder. A winter storm of legends.",
                    "A violent {temp}. Thunder and ice together.",
                    "{temp} degrees. The storm doesn't care about the cold.",
                ],
                cold: [
                    "{temp} degrees of chaos. Lightning writes across the sky.",
                    "A dramatic {temp}. The sky is having feelings.",
                    "{temp} degrees. Thunder echoes through the cold.",
                ],
                cool: [
                    "{temp} degrees with thunderstorms. Electric.",
                    "A charged {temp}. The air itself is nervous.",
                    "{temp} degrees. Stay safe, stay awed.",
                ],
                mild: [
                    "{temp} degrees of storm energy. Beautiful and dangerous.",
                    "A powerful {temp}. Nature is putting on a show.",
                    "{temp} degrees. The thunder has stories to tell.",
                ],
                warm: [
                    "{temp} degrees of summer storm. Magnificent.",
                    "A wild {temp}. The heat has summoned the thunder.",
                    "{temp} degrees. This is the good kind of drama.",
                ],
                hot: [
                    "{temp} degrees with thunderstorms. Primal energy.",
                    "A fierce {temp}. The heat and the storm are fighting.",
                    "{temp} degrees. Lightning and humidity. Classic summer.",
                ],
            },
        };

        // Time of day prefixes
        this.timePrefixes = {
            morning: [
                "Good morning. ",
                "Dawn breaks at ",
                "The morning brings ",
                "",  // No prefix sometimes
            ],
            afternoon: [
                "Right now, it's ",
                "The afternoon holds ",
                "",
                "",
            ],
            evening: [
                "As evening settles in... ",
                "The day winds down at ",
                "Evening brings ",
                "",
            ],
            night: [
                "The night air holds ",
                "Under the stars, ",
                "In the quiet of night... ",
                "",
            ],
        };

        // Number words for natural speech
        this.ones = ['', 'one', 'two', 'three', 'four', 'five', 'six', 'seven', 'eight', 'nine',
                     'ten', 'eleven', 'twelve', 'thirteen', 'fourteen', 'fifteen', 'sixteen',
                     'seventeen', 'eighteen', 'nineteen'];
        this.tens = ['', '', 'twenty', 'thirty', 'forty', 'fifty', 'sixty', 'seventy', 'eighty', 'ninety'];

        this.init();
    }

    init() {
        if (!this.synth) {
            console.warn('Speech synthesis not supported');
            return;
        }

        // Voices load asynchronously
        this.synth.onvoiceschanged = () => this.selectVoice();
        this.selectVoice();
    }

    selectVoice() {
        const voices = this.synth.getVoices();
        if (!voices.length) return;

        // Prefer natural-sounding voices
        this.voice =
            voices.find(v => v.name.includes('Samantha')) ||
            voices.find(v => v.name.includes('Karen')) ||
            voices.find(v => v.name.includes('Daniel') && v.lang.includes('en-GB')) ||
            voices.find(v => v.name.includes('Google UK English Female')) ||
            voices.find(v => v.lang.startsWith('en-GB')) ||
            voices.find(v => v.lang.startsWith('en-US')) ||
            voices[0];
    }

    numberToWords(n) {
        if (n === 0) return 'zero';
        if (n < 0) return 'negative ' + this.numberToWords(-n);

        n = Math.round(n);

        if (n < 20) return this.ones[n];
        if (n < 100) {
            const ten = Math.floor(n / 10);
            const one = n % 10;
            return this.tens[ten] + (one ? '-' + this.ones[one] : '');
        }
        if (n < 1000) {
            const hundred = Math.floor(n / 100);
            const remainder = n % 100;
            return this.ones[hundred] + ' hundred' + (remainder ? ' ' + this.numberToWords(remainder) : '');
        }

        return String(n); // Fallback for very large numbers
    }

    celsiusToFahrenheit(c) {
        return Math.round((c * 9/5) + 32);
    }

    getTimeOfDay() {
        const hour = new Date().getHours();
        if (hour >= 5 && hour < 12) return 'morning';
        if (hour >= 12 && hour < 17) return 'afternoon';
        if (hour >= 17 && hour < 21) return 'evening';
        return 'night';
    }

    getTemperatureCategory(tempF) {
        if (tempF < 32) return 'freezing';
        if (tempF < 50) return 'cold';
        if (tempF < 60) return 'cool';
        if (tempF < 70) return 'mild';
        if (tempF < 80) return 'warm';
        if (tempF < 95) return 'hot';
        return 'scorching';
    }

    getConditionCategory(condition) {
        // Map WMO conditions to our template categories
        if (['thunderstorm'].includes(condition)) return 'thunderstorm';
        if (['snow', 'heavy_snow', 'snow_grains', 'snow_showers'].includes(condition)) return 'snow';
        if (['fog'].includes(condition)) return 'fog';
        if (['rain', 'heavy_rain', 'showers', 'heavy_showers', 'drizzle', 'freezing_drizzle', 'freezing_rain'].includes(condition)) return 'rain';
        if (['overcast', 'partly_cloudy'].includes(condition)) return 'cloudy';
        return 'clear'; // clear, mostly_clear
    }

    pickRandom(arr) {
        return arr[Math.floor(Math.random() * arr.length)];
    }

    generateResponse() {
        // Get weather data from atmosphere
        const tempC = atmosphere.temperature || 15;
        const tempF = this.celsiusToFahrenheit(tempC);
        const condition = atmosphere.condition || 'clear';

        const tempWords = this.numberToWords(tempF);
        const timeOfDay = this.getTimeOfDay();
        const tempCategory = this.getTemperatureCategory(tempF);
        const conditionCategory = this.getConditionCategory(condition);

        // Get templates for this condition
        let templates = this.templates[conditionCategory]?.[tempCategory];

        // Fallback to clear if no specific template
        if (!templates || !templates.length) {
            templates = this.templates.clear[tempCategory] || this.templates.clear.mild;
        }

        // Pick random template and prefix
        const template = this.pickRandom(templates);
        const prefix = this.pickRandom(this.timePrefixes[timeOfDay]);

        // Build response
        let response = template.replace('{temp}', tempWords);

        // Add prefix (only if template doesn't start with temp words already)
        if (prefix && !response.toLowerCase().startsWith(tempWords)) {
            response = prefix + response;
        }

        return response;
    }

    getVoiceSettings() {
        const condition = atmosphere.condition || 'clear';
        const conditionCategory = this.getConditionCategory(condition);

        // Adjust rate and pitch based on mood
        const settings = {
            rate: 0.9,  // Slightly slower than normal for contemplative feel
            pitch: 1.0,
        };

        switch (conditionCategory) {
            case 'thunderstorm':
                settings.rate = 0.95;  // Slightly more urgent
                settings.pitch = 0.95;
                break;
            case 'snow':
                settings.rate = 0.85;  // Slow and peaceful
                settings.pitch = 1.05;
                break;
            case 'fog':
                settings.rate = 0.8;   // Very slow, mysterious
                settings.pitch = 0.98;
                break;
            case 'rain':
                settings.rate = 0.88;  // Contemplative
                settings.pitch = 0.95;
                break;
            case 'cloudy':
                settings.rate = 0.9;
                settings.pitch = 0.98;
                break;
            case 'clear':
                const tempC = atmosphere.temperature || 15;
                const tempF = this.celsiusToFahrenheit(tempC);
                if (tempF > 80) {
                    settings.rate = 0.85;  // Slow in the heat
                    settings.pitch = 0.92;
                } else if (tempF < 40) {
                    settings.rate = 0.88;
                    settings.pitch = 0.95;
                } else {
                    settings.rate = 0.92;  // Upbeat for nice weather
                    settings.pitch = 1.02;
                }
                break;
        }

        return settings;
    }

    async playPreSpeechTone() {
        if (!sound.enabled || !sound.context) return;

        // Ethereal rising tone
        const osc = sound.context.createOscillator();
        const gain = sound.context.createGain();

        osc.type = 'sine';
        osc.frequency.setValueAtTime(400, sound.context.currentTime);
        osc.frequency.exponentialRampToValueAtTime(600, sound.context.currentTime + 0.3);

        gain.gain.setValueAtTime(0, sound.context.currentTime);
        gain.gain.linearRampToValueAtTime(0.1, sound.context.currentTime + 0.1);
        gain.gain.exponentialRampToValueAtTime(0.01, sound.context.currentTime + 0.3);

        osc.connect(gain);
        gain.connect(sound.masterGain);

        osc.start();
        osc.stop(sound.context.currentTime + 0.3);

        // Wait for tone to complete
        return new Promise(resolve => setTimeout(resolve, 350));
    }

    playPostSpeechTone() {
        if (!sound.enabled || !sound.context) return;

        // Gentle falling tone
        const osc = sound.context.createOscillator();
        const gain = sound.context.createGain();

        osc.type = 'sine';
        osc.frequency.setValueAtTime(500, sound.context.currentTime);
        osc.frequency.exponentialRampToValueAtTime(300, sound.context.currentTime + 0.4);

        gain.gain.setValueAtTime(0.08, sound.context.currentTime);
        gain.gain.exponentialRampToValueAtTime(0.01, sound.context.currentTime + 0.4);

        osc.connect(gain);
        gain.connect(sound.masterGain);

        osc.start();
        osc.stop(sound.context.currentTime + 0.4);
    }

    async speak() {
        // Prevent spam and overlapping speech
        if (!this.synth || this.speaking) return;
        if (Date.now() - this.lastSpoken < this.cooldown) return;

        this.speaking = true;
        this.lastSpoken = Date.now();

        // Cancel any existing speech
        this.synth.cancel();

        // Initialize audio on first interaction
        await sound.init();

        // Play pre-speech tone
        await this.playPreSpeechTone();

        // Generate response
        const response = this.generateResponse();

        // Create utterance
        const utterance = new SpeechSynthesisUtterance(response);

        if (this.voice) {
            utterance.voice = this.voice;
        }

        const settings = this.getVoiceSettings();
        utterance.rate = settings.rate;
        utterance.pitch = settings.pitch;
        utterance.volume = 0.9;

        // Handle completion
        utterance.onend = () => {
            this.playPostSpeechTone();
            this.speaking = false;
        };

        utterance.onerror = () => {
            this.speaking = false;
        };

        // Speak
        this.synth.speak(utterance);

        // Log to console for debugging
        console.log('%c' + response, 'color: #D4AF37; font-style: italic;');
    }

    // Manual trigger for console API
    say(text) {
        if (!this.synth) return;

        this.synth.cancel();
        const utterance = new SpeechSynthesisUtterance(text);
        if (this.voice) utterance.voice = this.voice;
        utterance.rate = 0.9;
        this.synth.speak(utterance);
    }
}

// Global voice instance
const celestialVoice = new CelestialVoice();

// ============================================================================
// CELESTIAL XR — Immersive WebXR Sun/Moon Simulation
// ============================================================================

class CelestialXR {
    constructor() {
        this.xrSupported = false;
        this.xrSession = null;
        this.renderer = null;
        this.scene = null;
        this.camera = null;
        this.xrButton = null;
        this.animationId = null;
        this.celestialBodies = {};
        this.stars = null;
        this.initialized = false;
    }

    async init() {
        if (this.initialized) return;

        // Check WebXR support
        if (navigator.xr) {
            try {
                this.xrSupported = await navigator.xr.isSessionSupported('immersive-vr');
            } catch (e) {
                console.log('WebXR check failed:', e);
                this.xrSupported = false;
            }
        }

        if (this.xrSupported) {
            this.createVRButton();
            await this.loadThreeJS();
            console.log('%c🥽 WebXR available. Enter VR for immersive celestial view.', 'color: #9F7AEA;');
        } else {
            console.log('%c🥽 WebXR not available on this device/browser.', 'color: #666;');
        }

        this.initialized = true;
    }

    async loadThreeJS() {
        // Load Three.js from CDN if not already loaded
        if (window.THREE) return;

        return new Promise((resolve, reject) => {
            const script = document.createElement('script');
            script.src = 'https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js';
            script.onload = resolve;
            script.onerror = reject;
            document.head.appendChild(script);
        });
    }

    createVRButton() {
        // Create "Enter VR" button in the hero section
        const heroSection = document.querySelector('.hero');
        if (!heroSection) return;

        this.xrButton = document.createElement('button');
        this.xrButton.className = 'vr-enter-btn';
        this.xrButton.innerHTML = `
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M3 6h18v12H3z"/>
                <circle cx="7" cy="12" r="2"/>
                <circle cx="17" cy="12" r="2"/>
                <path d="M10 12h4"/>
            </svg>
            <span>Enter VR</span>
        `;
        this.xrButton.setAttribute('aria-label', 'Enter immersive VR mode to view celestial bodies');

        // Style the button
        const style = document.createElement('style');
        style.textContent = `
            .vr-enter-btn {
                position: absolute;
                bottom: 20px;
                right: 20px;
                display: flex;
                align-items: center;
                gap: 8px;
                padding: 12px 20px;
                background: linear-gradient(135deg, rgba(159, 122, 234, 0.9), rgba(99, 102, 241, 0.9));
                border: none;
                border-radius: 12px;
                color: white;
                font-family: inherit;
                font-size: 14px;
                font-weight: 600;
                cursor: pointer;
                transition: all 0.233s ease;
                backdrop-filter: blur(8px);
                box-shadow: 0 4px 20px rgba(159, 122, 234, 0.3);
                z-index: 100;
            }
            .vr-enter-btn:hover {
                transform: translateY(-2px);
                box-shadow: 0 6px 25px rgba(159, 122, 234, 0.5);
            }
            .vr-enter-btn:active {
                transform: translateY(0);
            }
            .vr-enter-btn svg {
                opacity: 0.9;
            }
            .vr-enter-btn.active {
                background: linear-gradient(135deg, rgba(239, 68, 68, 0.9), rgba(220, 38, 38, 0.9));
                box-shadow: 0 4px 20px rgba(239, 68, 68, 0.3);
            }
            .vr-enter-btn.active span::after {
                content: 'Exit VR';
            }
            .vr-enter-btn.active span {
                font-size: 0;
            }
        `;
        document.head.appendChild(style);

        this.xrButton.addEventListener('click', () => this.toggleXR());
        heroSection.appendChild(this.xrButton);
    }

    async toggleXR() {
        if (this.xrSession) {
            await this.endXRSession();
        } else {
            await this.startXRSession();
        }
    }

    async startXRSession() {
        if (!this.xrSupported || !window.THREE) {
            console.warn('WebXR or Three.js not available');
            return;
        }

        try {
            // Request XR session
            this.xrSession = await navigator.xr.requestSession('immersive-vr', {
                requiredFeatures: ['local-floor']
            });

            this.xrButton.classList.add('active');

            // Initialize Three.js scene
            this.initThreeScene();

            // Set up XR rendering
            await this.renderer.xr.setSession(this.xrSession);

            // Handle session end
            this.xrSession.addEventListener('end', () => this.onXRSessionEnd());

            // Start render loop
            this.renderer.setAnimationLoop((time, frame) => this.renderXR(time, frame));

            console.log('%c🌌 Entered immersive celestial view', 'color: #9F7AEA;');
        } catch (e) {
            console.error('Failed to start XR session:', e);
            this.xrButton.classList.remove('active');
        }
    }

    async endXRSession() {
        if (this.xrSession) {
            await this.xrSession.end();
        }
    }

    onXRSessionEnd() {
        this.xrSession = null;
        this.xrButton.classList.remove('active');
        if (this.renderer) {
            this.renderer.setAnimationLoop(null);
        }
        console.log('%c🌌 Exited immersive view', 'color: #666;');
    }

    initThreeScene() {
        const THREE = window.THREE;

        // Create renderer
        this.renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
        this.renderer.setPixelRatio(window.devicePixelRatio);
        this.renderer.setSize(window.innerWidth, window.innerHeight);
        this.renderer.xr.enabled = true;
        this.renderer.outputEncoding = THREE.sRGBEncoding;
        this.renderer.toneMapping = THREE.ACESFilmicToneMapping;
        this.renderer.toneMappingExposure = 1;

        // Create scene
        this.scene = new THREE.Scene();

        // Create camera
        this.camera = new THREE.PerspectiveCamera(75, window.innerWidth / window.innerHeight, 0.1, 2000);
        this.camera.position.set(0, 1.6, 0); // Standing height

        // Create celestial elements
        this.createSkybox();
        this.createStars();
        this.createSun();
        this.createMoon();

        // Add ambient light
        const ambientLight = new THREE.AmbientLight(0x404040, 0.5);
        this.scene.add(ambientLight);
    }

    createSkybox() {
        const THREE = window.THREE;

        // Create gradient sky sphere
        const skyGeometry = new THREE.SphereGeometry(1000, 32, 32);

        // Custom shader for gradient sky
        const skyMaterial = new THREE.ShaderMaterial({
            uniforms: {
                topColor: { value: new THREE.Color(0x0a0a20) },
                bottomColor: { value: new THREE.Color(0x1a1a3e) },
                horizonColor: { value: new THREE.Color(0x2a2a5e) },
                offset: { value: 33 },
                exponent: { value: 0.6 }
            },
            vertexShader: `
                varying vec3 vWorldPosition;
                void main() {
                    vec4 worldPosition = modelMatrix * vec4(position, 1.0);
                    vWorldPosition = worldPosition.xyz;
                    gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
                }
            `,
            fragmentShader: `
                uniform vec3 topColor;
                uniform vec3 bottomColor;
                uniform vec3 horizonColor;
                uniform float offset;
                uniform float exponent;
                varying vec3 vWorldPosition;
                void main() {
                    float h = normalize(vWorldPosition + offset).y;
                    float t = max(pow(max(h, 0.0), exponent), 0.0);
                    vec3 color = mix(horizonColor, topColor, t);
                    if (h < 0.0) {
                        color = mix(horizonColor, bottomColor, min(-h * 2.0, 1.0));
                    }
                    gl_FragColor = vec4(color, 1.0);
                }
            `,
            side: THREE.BackSide
        });

        const sky = new THREE.Mesh(skyGeometry, skyMaterial);
        this.scene.add(sky);
        this.celestialBodies.sky = sky;
    }

    createStars() {
        const THREE = window.THREE;

        // Create starfield
        const starsGeometry = new THREE.BufferGeometry();
        const starCount = 3000;
        const positions = new Float32Array(starCount * 3);
        const sizes = new Float32Array(starCount);
        const colors = new Float32Array(starCount * 3);

        for (let i = 0; i < starCount; i++) {
            // Random position on sphere
            const theta = Math.random() * Math.PI * 2;
            const phi = Math.acos(2 * Math.random() - 1);
            const radius = 800 + Math.random() * 100;

            positions[i * 3] = radius * Math.sin(phi) * Math.cos(theta);
            positions[i * 3 + 1] = radius * Math.sin(phi) * Math.sin(theta);
            positions[i * 3 + 2] = radius * Math.cos(phi);

            sizes[i] = Math.random() * 2 + 0.5;

            // Slight color variation (white to blue-white)
            const temp = 0.8 + Math.random() * 0.2;
            colors[i * 3] = temp;
            colors[i * 3 + 1] = temp;
            colors[i * 3 + 2] = 1.0;
        }

        starsGeometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));
        starsGeometry.setAttribute('size', new THREE.BufferAttribute(sizes, 1));
        starsGeometry.setAttribute('color', new THREE.BufferAttribute(colors, 3));

        const starsMaterial = new THREE.ShaderMaterial({
            uniforms: {
                time: { value: 0 }
            },
            vertexShader: `
                attribute float size;
                attribute vec3 color;
                varying vec3 vColor;
                uniform float time;
                void main() {
                    vColor = color;
                    vec4 mvPosition = modelViewMatrix * vec4(position, 1.0);
                    float twinkle = 0.8 + 0.2 * sin(time * 2.0 + position.x * 0.1);
                    gl_PointSize = size * twinkle * (300.0 / -mvPosition.z);
                    gl_Position = projectionMatrix * mvPosition;
                }
            `,
            fragmentShader: `
                varying vec3 vColor;
                void main() {
                    float dist = length(gl_PointCoord - vec2(0.5));
                    if (dist > 0.5) discard;
                    float alpha = 1.0 - smoothstep(0.0, 0.5, dist);
                    gl_FragColor = vec4(vColor, alpha);
                }
            `,
            transparent: true,
            blending: THREE.AdditiveBlending
        });

        this.stars = new THREE.Points(starsGeometry, starsMaterial);
        this.scene.add(this.stars);
    }

    createSun() {
        const THREE = window.THREE;

        // Sun group
        const sunGroup = new THREE.Group();

        // Sun core
        const coreGeometry = new THREE.SphereGeometry(20, 32, 32);
        const coreMaterial = new THREE.MeshBasicMaterial({
            color: 0xffdd44,
            transparent: true,
            opacity: 1.0
        });
        const core = new THREE.Mesh(coreGeometry, coreMaterial);
        sunGroup.add(core);

        // Sun glow (corona)
        const coronaGeometry = new THREE.SphereGeometry(30, 32, 32);
        const coronaMaterial = new THREE.ShaderMaterial({
            uniforms: {
                time: { value: 0 },
                glowColor: { value: new THREE.Color(0xffaa00) }
            },
            vertexShader: `
                varying vec3 vNormal;
                void main() {
                    vNormal = normalize(normalMatrix * normal);
                    gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
                }
            `,
            fragmentShader: `
                uniform vec3 glowColor;
                uniform float time;
                varying vec3 vNormal;
                void main() {
                    float intensity = pow(0.7 - dot(vNormal, vec3(0.0, 0.0, 1.0)), 2.0);
                    float pulse = 0.9 + 0.1 * sin(time * 2.0);
                    gl_FragColor = vec4(glowColor, intensity * pulse * 0.6);
                }
            `,
            transparent: true,
            blending: THREE.AdditiveBlending,
            side: THREE.BackSide
        });
        const corona = new THREE.Mesh(coronaGeometry, coronaMaterial);
        sunGroup.add(corona);

        // Outer glow
        const outerGlowGeometry = new THREE.SphereGeometry(50, 32, 32);
        const outerGlowMaterial = new THREE.ShaderMaterial({
            uniforms: {
                glowColor: { value: new THREE.Color(0xff6600) }
            },
            vertexShader: `
                varying vec3 vNormal;
                void main() {
                    vNormal = normalize(normalMatrix * normal);
                    gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
                }
            `,
            fragmentShader: `
                uniform vec3 glowColor;
                varying vec3 vNormal;
                void main() {
                    float intensity = pow(0.5 - dot(vNormal, vec3(0.0, 0.0, 1.0)), 3.0);
                    gl_FragColor = vec4(glowColor, intensity * 0.3);
                }
            `,
            transparent: true,
            blending: THREE.AdditiveBlending,
            side: THREE.BackSide
        });
        const outerGlow = new THREE.Mesh(outerGlowGeometry, outerGlowMaterial);
        sunGroup.add(outerGlow);

        // Add point light from sun
        const sunLight = new THREE.PointLight(0xffdd88, 2, 500);
        sunGroup.add(sunLight);

        this.scene.add(sunGroup);
        this.celestialBodies.sun = sunGroup;
        this.celestialBodies.sunCorona = corona;
    }

    createMoon() {
        const THREE = window.THREE;

        // Moon group
        const moonGroup = new THREE.Group();

        // Moon surface
        const moonGeometry = new THREE.SphereGeometry(8, 32, 32);
        const moonMaterial = new THREE.MeshStandardMaterial({
            color: 0xe8e8e8,
            roughness: 0.8,
            metalness: 0.1,
            emissive: 0x222222,
            emissiveIntensity: 0.3
        });
        const moonSurface = new THREE.Mesh(moonGeometry, moonMaterial);
        moonGroup.add(moonSurface);

        // Phase shadow (dark hemisphere)
        const shadowGeometry = new THREE.SphereGeometry(8.1, 32, 32);
        const shadowMaterial = new THREE.ShaderMaterial({
            uniforms: {
                phase: { value: 0.0 }, // 0 = new moon, 0.5 = full moon, 1 = new moon
                shadowColor: { value: new THREE.Color(0x0a0a15) }
            },
            vertexShader: `
                varying vec3 vPosition;
                varying vec3 vNormal;
                void main() {
                    vPosition = position;
                    vNormal = normal;
                    gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
                }
            `,
            fragmentShader: `
                uniform float phase;
                uniform vec3 shadowColor;
                varying vec3 vPosition;
                varying vec3 vNormal;
                void main() {
                    // Calculate illumination based on phase
                    float phaseAngle = phase * 2.0 * 3.14159;
                    vec3 sunDir = vec3(sin(phaseAngle), 0.0, cos(phaseAngle));
                    float illumination = dot(normalize(vNormal), sunDir);

                    // Shadow on unilluminated side
                    float shadow = 1.0 - smoothstep(-0.1, 0.3, illumination);
                    gl_FragColor = vec4(shadowColor, shadow * 0.85);
                }
            `,
            transparent: true,
            side: THREE.FrontSide
        });
        const phaseShadow = new THREE.Mesh(shadowGeometry, shadowMaterial);
        moonGroup.add(phaseShadow);

        // Moon glow
        const glowGeometry = new THREE.SphereGeometry(12, 32, 32);
        const glowMaterial = new THREE.ShaderMaterial({
            uniforms: {
                glowColor: { value: new THREE.Color(0x8888aa) }
            },
            vertexShader: `
                varying vec3 vNormal;
                void main() {
                    vNormal = normalize(normalMatrix * normal);
                    gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
                }
            `,
            fragmentShader: `
                uniform vec3 glowColor;
                varying vec3 vNormal;
                void main() {
                    float intensity = pow(0.6 - dot(vNormal, vec3(0.0, 0.0, 1.0)), 2.0);
                    gl_FragColor = vec4(glowColor, intensity * 0.3);
                }
            `,
            transparent: true,
            blending: THREE.AdditiveBlending,
            side: THREE.BackSide
        });
        const moonGlow = new THREE.Mesh(glowGeometry, glowMaterial);
        moonGroup.add(moonGlow);

        this.scene.add(moonGroup);
        this.celestialBodies.moon = moonGroup;
        this.celestialBodies.moonPhaseShadow = phaseShadow;
    }

    /**
     * Convert azimuth/altitude to 3D position
     * azimuth: 0 = North, 90 = East, 180 = South, 270 = West
     * altitude: 0 = horizon, 90 = zenith
     */
    celestialToCartesian(azimuth, altitude, distance = 500) {
        // Convert to radians
        const azRad = (azimuth - 90) * Math.PI / 180; // Adjust so 0 = North
        const altRad = altitude * Math.PI / 180;

        // Spherical to Cartesian
        const x = distance * Math.cos(altRad) * Math.sin(azRad);
        const y = distance * Math.sin(altRad);
        const z = -distance * Math.cos(altRad) * Math.cos(azRad);

        return { x, y, z };
    }

    updateCelestialPositions(date = new Date()) {
        if (!this.celestialBodies.sun || !this.celestialBodies.moon) return;

        // Get real astronomical positions
        const sunPos = Ephemeris.sunPosition(HOME.latitude, HOME.longitude, date);
        const moonPos = Ephemeris.moonPosition(HOME.latitude, HOME.longitude, date);

        // Position sun
        const sunCartesian = this.celestialToCartesian(sunPos.azimuth, sunPos.altitude, 500);
        this.celestialBodies.sun.position.set(sunCartesian.x, sunCartesian.y, sunCartesian.z);

        // Position moon
        const moonCartesian = this.celestialToCartesian(moonPos.azimuth, moonPos.altitude, 400);
        this.celestialBodies.moon.position.set(moonCartesian.x, moonCartesian.y, moonCartesian.z);

        // Update moon phase
        if (this.celestialBodies.moonPhaseShadow) {
            const phaseMaterial = this.celestialBodies.moonPhaseShadow.material;
            if (phaseMaterial.uniforms && phaseMaterial.uniforms.phase) {
                // moonPhase returns phase 0-1, we need to adjust for shader
                const phase = moonPos.phase !== undefined ? moonPos.phase : 0.5;
                phaseMaterial.uniforms.phase.value = phase;
            }
        }

        // Update sky color based on sun altitude
        if (this.celestialBodies.sky) {
            const skyMaterial = this.celestialBodies.sky.material;
            if (skyMaterial.uniforms) {
                const THREE = window.THREE;

                if (sunPos.altitude > 10) {
                    // Daytime - blue sky
                    skyMaterial.uniforms.topColor.value = new THREE.Color(0x0077be);
                    skyMaterial.uniforms.horizonColor.value = new THREE.Color(0x87ceeb);
                    skyMaterial.uniforms.bottomColor.value = new THREE.Color(0x4a7c59);
                } else if (sunPos.altitude > -6) {
                    // Twilight - orange/purple
                    const t = (sunPos.altitude + 6) / 16; // 0 at -6°, 1 at 10°
                    skyMaterial.uniforms.topColor.value = new THREE.Color(0x1a0a30).lerp(new THREE.Color(0x0077be), t);
                    skyMaterial.uniforms.horizonColor.value = new THREE.Color(0xff6b35).lerp(new THREE.Color(0x87ceeb), t);
                    skyMaterial.uniforms.bottomColor.value = new THREE.Color(0x2a1a4a).lerp(new THREE.Color(0x4a7c59), t);
                } else {
                    // Night
                    skyMaterial.uniforms.topColor.value = new THREE.Color(0x0a0a20);
                    skyMaterial.uniforms.horizonColor.value = new THREE.Color(0x1a1a3e);
                    skyMaterial.uniforms.bottomColor.value = new THREE.Color(0x0a0a15);
                }
            }
        }

        // Hide sun if below horizon
        this.celestialBodies.sun.visible = sunPos.altitude > -10;

        // Dim stars during day
        if (this.stars && this.stars.material) {
            const dayFactor = Math.max(0, Math.min(1, sunPos.altitude / 20));
            this.stars.material.opacity = 1 - dayFactor * 0.9;
        }
    }

    renderXR(time, frame) {
        if (!this.xrSession || !this.renderer) return;

        const seconds = time * 0.001;

        // Update star twinkle
        if (this.stars && this.stars.material.uniforms) {
            this.stars.material.uniforms.time.value = seconds;
        }

        // Update sun corona pulse
        if (this.celestialBodies.sunCorona && this.celestialBodies.sunCorona.material.uniforms) {
            this.celestialBodies.sunCorona.material.uniforms.time.value = seconds;
        }

        // Update celestial positions (use current app time if available)
        const currentTime = window.celestialDemo?.currentTime || new Date();
        this.updateCelestialPositions(currentTime);

        // Render
        this.renderer.render(this.scene, this.camera);
    }

    // Public method to update from external time control
    update(date) {
        if (this.xrSession) {
            this.updateCelestialPositions(date);
        }
    }

    // Check if VR is currently active
    isActive() {
        return this.xrSession !== null;
    }
}

// Global XR instance
const celestialXR = new CelestialXR();

// ============================================================================
// MAIN APPLICATION
// ============================================================================

class CelestialDemo {
    constructor() {
        this.currentTime = new Date();
        this.weather = null;
        this.elements = {};
        this.visualization = null;
        this.shadeTable = null;
        this.cursor = null;
        this.particles = null;
        
        this.init();
    }

    init() {
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', () => this.setup());
        } else {
            this.setup();
        }
    }

    setup() {
        this.cacheElements();
        this.setupLoading();
        this.setupNavigation();
        this.setupRevealAnimations();
        this.setupTimeControls();
        this.setupVisualization();
        this.setupCelestialSky();
        this.setupCelestialXR();
        this.setupDelight();
        this.setupAtmosphere();
        this.update();
        this.startAutoUpdate();
        this.setupConsole();
    }

    setupCelestialSky() {
        // Initialize the celestial sky visualization
        celestialSky.init();
    }

    setupCelestialXR() {
        // Initialize WebXR immersive view (shows button only if supported)
        celestialXR.init();
    }

    setupAtmosphere() {
        // Initialize weather-based atmosphere adaptation
        // This sneakily adjusts all animations based on reader's real weather
        atmosphere.init();
    }

    cacheElements() {
        this.elements = {
            timeSlider: document.getElementById('time-slider'),
            timeDisplay: document.getElementById('time-display'),
            weatherToggle: document.getElementById('weather-toggle'),
            sunViz: document.getElementById('sun-visualization'),
            shadeTable: document.getElementById('shade-table'),
            sunAzimuth: document.getElementById('sun-azimuth'),
            sunAltitude: document.getElementById('sun-altitude'),
            sunDirection: document.getElementById('sun-direction'),
            isDay: document.getElementById('is-day'),
            weatherCondition: document.getElementById('weather-condition'),
            cloudCoverage: document.getElementById('cloud-coverage'),
            nav: document.querySelector('.nav'),
            revealElements: document.querySelectorAll('[data-reveal]'),
            statValues: document.querySelectorAll('.stat-value[data-count]')
        };
    }

    setupLoading() {
        // Remove loading state after brief delay
        setTimeout(() => {
            document.body.classList.remove('loading');
        }, 100);
        
        // Animate stat counts when visible
        const statsObserver = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    const el = entry.target;
                    const value = parseInt(el.dataset.count, 10);
                    if (!isNaN(value)) {
                        new CountUp(el, value, 1500).start();
                    }
                    statsObserver.unobserve(el);
                }
            });
        }, { threshold: 0.5 });
        
        this.elements.statValues.forEach(el => statsObserver.observe(el));
    }

    setupNavigation() {
        const nav = this.elements.nav;
        if (!nav) return;

        // Mobile hamburger menu
        const navToggle = nav.querySelector('.nav-toggle');
        const navLinks = nav.querySelector('.nav-links');

        if (navToggle && navLinks) {
            navToggle.addEventListener('click', () => {
                const isExpanded = navToggle.getAttribute('aria-expanded') === 'true';
                navToggle.setAttribute('aria-expanded', !isExpanded);
                navLinks.classList.toggle('open');
                document.body.style.overflow = isExpanded ? '' : 'hidden';
            });

            // Close menu when link clicked
            navLinks.querySelectorAll('.nav-link').forEach(link => {
                link.addEventListener('click', () => {
                    navToggle.setAttribute('aria-expanded', 'false');
                    navLinks.classList.remove('open');
                    document.body.style.overflow = '';
                });
            });

            // Close on escape key
            document.addEventListener('keydown', (e) => {
                if (e.key === 'Escape' && navLinks.classList.contains('open')) {
                    navToggle.setAttribute('aria-expanded', 'false');
                    navLinks.classList.remove('open');
                    document.body.style.overflow = '';
                    navToggle.focus();
                }
            });
        }

        let lastScroll = 0;

        window.addEventListener('scroll', () => {
            const currentScroll = window.scrollY;

            if (currentScroll > 100) {
                nav.classList.add('visible');
            } else {
                nav.classList.remove('visible');
            }

            // Update active nav link
            const sections = document.querySelectorAll('.section[id]');
            sections.forEach(section => {
                const rect = section.getBoundingClientRect();
                const link = nav.querySelector(`[href="#${section.id}"]`);
                if (link) {
                    if (rect.top < 200 && rect.bottom > 200) {
                        link.classList.add('active');
                    } else {
                        link.classList.remove('active');
                    }
                }
            });

            lastScroll = currentScroll;
        }, { passive: true });

        // Smooth scroll
        document.querySelectorAll('a[href^="#"]').forEach(link => {
            link.addEventListener('click', (e) => {
                const href = link.getAttribute('href');
                if (href.startsWith('#')) {
                    e.preventDefault();
                    const target = document.querySelector(href);
                    if (target) {
                        target.scrollIntoView({ behavior: 'smooth' });
                    }
                }
            });
        });
    }

    setupRevealAnimations() {
        const observer = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    entry.target.classList.add('visible');
                }
            });
        }, {
            threshold: 0.1,
            rootMargin: '-50px'
        });

        this.elements.revealElements.forEach(el => observer.observe(el));
    }

    setupTimeControls() {
        const slider = this.elements.timeSlider;
        if (!slider) return;

        slider.value = this.currentTime.getHours() + this.currentTime.getMinutes() / 60;

        // Initialize audio on first slider interaction
        let audioInitialized = false;
        let lastSliderSoundTime = 0;

        slider.addEventListener('input', () => {
            const hours = parseFloat(slider.value);
            const h = Math.floor(hours);
            const m = Math.round((hours - h) * 60);

            this.currentTime = new Date();
            this.currentTime.setHours(h, m, 0, 0);

            // Initialize audio on first interaction
            if (!audioInitialized) {
                sound.init();
                audioInitialized = true;
            }

            // Throttle slider sound to avoid rapid-fire
            const now = Date.now();
            if (now - lastSliderSoundTime > 50) {
                sound.playSlider(hours / 24);
                lastSliderSoundTime = now;
            }

            this.update();
        });

        const weatherToggle = this.elements.weatherToggle;
        if (weatherToggle) {
            weatherToggle.addEventListener('change', () => {
                // Initialize audio on toggle
                sound.init().then(() => sound.playClick());

                if (weatherToggle.checked) {
                    this.weather = WeatherService.getSimulatedWeather();
                } else {
                    this.weather = null;
                }
                this.update();
            });
        }
    }

    setupVisualization() {
        if (this.elements.sunViz) {
            this.visualization = new SunVisualization(this.elements.sunViz);
        }
        
        if (this.elements.shadeTable) {
            this.shadeTable = new ShadeTable(this.elements.shadeTable);
        }
    }

    setupDelight() {
        // Custom cursor
        this.cursor = new CustomCursor();

        // Particles
        this.particles = new ParticleSystem();

        // Breathing glow
        const glow = document.createElement('div');
        glow.className = 'breathing-glow';
        glow.style.cssText = 'top: 30%; left: 70%;';
        document.body.appendChild(glow);

        // Celestial Voice — click sun to hear the weather spoken
        this.setupCelestialVoice();

        // Konami code
        new KonamiCode(() => {
            document.body.classList.add('konami-unlocked');
            console.log('%c🌈 KONAMI UNLOCKED!', 'font-size: 24px; color: #FFD700;');
            console.log('%cYou found the easter egg! The sun is now extra shiny.', 'color: #888;');

            // Play success chime
            sound.init().then(() => sound.playSuccess());

            // Rainbow sun
            const heroSun = document.querySelector('.hero-sun');
            if (heroSun) {
                heroSun.style.animation = 'sun-pulse 1s ease-in-out infinite, sun-float 4s ease-in-out infinite';
                heroSun.style.filter = 'hue-rotate(0deg)';
                let hue = 0;
                const rainbowInterval = setInterval(() => {
                    hue = (hue + 2) % 360;
                    heroSun.style.filter = `hue-rotate(${hue}deg)`;
                }, 50);

                // Store interval for cleanup
                window._konamiRainbow = rainbowInterval;
            }

            setTimeout(() => {
                document.body.classList.remove('konami-unlocked');
            }, 500);
        });

        // Secret words: "monmouth" and "home" — Teleport to secret locations (10 second preview)
        this.secretLocationTimeout = null;
        this.originalLocation = null;
        
        new SecretWord(['monmouth', 'home'], (word) => {
            const location = SECRET_LOCATIONS[word];
            if (!location) return;

            // Style based on location
            const isHome = word === 'home';
            const titleColor = isHome ? '#22c55e' : '#8B4513';
            const nameColor = isHome ? '#4ade80' : '#D2691E';

            console.log(`%c${location.emoji} ${isHome ? 'WELCOME HOME!' : 'SECRET LOCATION UNLOCKED!'}`, `font-size: 24px; color: ${titleColor};`);
            console.log(`%c${location.name}`, `font-size: 16px; color: ${nameColor}; font-weight: bold;`);
            console.log(`%c${location.address}, ${location.city}`, 'color: #888;');
            console.log(`%c${location.description}`, 'color: #666; font-style: italic;');
            console.log(`%c⏱️ Location preview for 10 seconds...`, 'color: #888; font-style: italic;');
            
            // Random trivia
            const trivia = location.trivia[Math.floor(Math.random() * location.trivia.length)];
            console.log(`%c💡 ${trivia}`, 'color: #D4AF37;');

            // Play success sound
            sound.init().then(() => sound.playSuccess());

            // Update the demo location temporarily
            if (window.celestialDemo) {
                // Store original location (from IP geolocation) if not already stored
                if (!this.originalLocation && typeof atmosphere !== 'undefined') {
                    this.originalLocation = {
                        latitude: atmosphere.latitude,
                        longitude: atmosphere.longitude
                    };
                }
                
                // Clear any existing revert timeout
                if (this.secretLocationTimeout) {
                    clearTimeout(this.secretLocationTimeout);
                }
                
                // Apply the secret location
                window.celestialDemo.latitude = location.latitude;
                window.celestialDemo.longitude = location.longitude;
                
                // Show fancy toast
                this.showLocationToast(location, word);
                
                // Force compass to update globe and celestial positions
                if (window.compassSundial) {
                    // Pass the location directly so it updates immediately
                    window.compassSundial.updateGlobeLocation(location.latitude, location.longitude);
                    window.compassSundial.updateCelestialBodies(location.latitude, location.longitude);
                }
                
                // Update location-specific CSS classes
                document.body.classList.remove('monmouth-mode', 'home-mode');
                document.body.classList.add(`${word}-mode`);
                
                // Update any location displays
                this.updateLocationDisplays(location);
                
                // FETCH NEW WEATHER for the location!
                this.updateWeatherForLocation(location);
                
                // Revert to original location after 10 seconds
                this.secretLocationTimeout = setTimeout(() => {
                    this.revertToOriginalLocation();
                }, 10000);
            }
        });
    }
    
    async updateWeatherForLocation(location) {
        // Update atmosphere with new location's weather
        if (typeof atmosphere !== 'undefined' && atmosphere.fetchWeather) {
            console.log(`%c🌤️ Fetching weather for ${location.city}...`, 'color: #64B5F6;');
            
            try {
                atmosphere.latitude = location.latitude;
                atmosphere.longitude = location.longitude;
                await atmosphere.fetchWeather(location.latitude, location.longitude);
                atmosphere.applyAtmosphere();
                
                console.log(`%c✓ Weather updated: ${atmosphere.condition}, ${atmosphere.temperature}°C`, 'color: #4CAF50;');
            } catch (e) {
                console.log('%c⚠️ Weather fetch failed', 'color: #FFA726;', e);
            }
        }
    }
    
    async revertToOriginalLocation() {
        if (!this.originalLocation) return;
        
        console.log('%c🔄 Reverting to your location...', 'color: #64B5F6;');
        
        // Restore original coordinates
        const orig = this.originalLocation;
        
        if (window.celestialDemo) {
            window.celestialDemo.latitude = orig.latitude;
            window.celestialDemo.longitude = orig.longitude;
        }
        
        // Restore atmosphere location and fetch weather
        if (typeof atmosphere !== 'undefined') {
            atmosphere.latitude = orig.latitude;
            atmosphere.longitude = orig.longitude;
            
            try {
                await atmosphere.fetchWeather(orig.latitude, orig.longitude);
                atmosphere.applyAtmosphere();
                console.log(`%c✓ Back to your weather: ${atmosphere.condition}, ${atmosphere.temperature}°C`, 'color: #4CAF50;');
            } catch (e) {
                console.log('%c⚠️ Weather revert failed', 'color: #FFA726;', e);
            }
        }
        
        // Update compass/globe with original coordinates
        if (window.compassSundial) {
            window.compassSundial.updateGlobeLocation(orig.latitude, orig.longitude);
            window.compassSundial.updateCelestialBodies(orig.latitude, orig.longitude);
        }
        
        // Remove location-specific CSS classes
        document.body.classList.remove('monmouth-mode', 'home-mode');
        
        // Show revert toast
        this.showRevertToast();
        
        // Clear the stored original location
        this.originalLocation = null;
        this.secretLocationTimeout = null;
    }
    
    showRevertToast() {
        // Remove existing toasts
        const existing = document.querySelector('.secret-toast');
        if (existing) existing.remove();
        
        const toast = document.createElement('div');
        toast.className = 'secret-toast revert-toast';
        toast.innerHTML = `
            <div class="toast-emoji">📍</div>
            <div class="toast-content">
                <div class="toast-title">Back to Your Location</div>
                <div class="toast-subtitle">Weather and globe updated</div>
            </div>
        `;
        document.body.appendChild(toast);
        
        // Animate in
        requestAnimationFrame(() => {
            toast.classList.add('show');
        });
        
        // Remove after 3 seconds
        setTimeout(() => {
            toast.classList.remove('show');
            setTimeout(() => toast.remove(), 500);
        }, 3000);
    }

    showLocationToast(location, word) {
        // Remove existing toast
        const existing = document.querySelector('.secret-toast');
        if (existing) existing.remove();

        const isHome = word === 'home';
        const title = isHome ? `Welcome Home` : `Teleported to ${location.name}`;
        const foundedLine = location.founded 
            ? `<div class="toast-founded">Est. ${location.founded}</div>` 
            : '';

        const toast = document.createElement('div');
        toast.className = `secret-toast ${word}-toast`;
        toast.innerHTML = `
            <div class="toast-emoji">${location.emoji}</div>
            <div class="toast-content">
                <div class="toast-title">${title}</div>
                <div class="toast-subtitle">${location.address}, ${location.city}</div>
                <div class="toast-trivia">"${location.trivia[Math.floor(Math.random() * location.trivia.length)]}"</div>
                ${foundedLine}
            </div>
        `;
        document.body.appendChild(toast);

        // Animate in
        requestAnimationFrame(() => {
            toast.classList.add('show');
        });

        // Remove after 6 seconds
        setTimeout(() => {
            toast.classList.remove('show');
            setTimeout(() => toast.remove(), 400);
        }, 6000);
    }

    updateLocationDisplays(location) {
        // Update any elements showing coordinates
        const coordElements = document.querySelectorAll('[data-location]');
        coordElements.forEach(el => {
            el.textContent = `${location.city} • ${location.latitude.toFixed(4)}°N, ${Math.abs(location.longitude).toFixed(4)}°W`;
        });
    }

    setupCelestialVoice() {
        // Make sun elements clickable to speak the weather
        const sunElements = [
            document.querySelector('.hero-sun'),
            document.querySelector('.sun-marker'),
            document.querySelector('.celestial-sun')  // From CelestialSky
        ].filter(Boolean);

        sunElements.forEach(el => {
            // Make visually interactive
            el.style.cursor = 'pointer';
            el.setAttribute('role', 'button');
            el.setAttribute('tabindex', '0');
            el.setAttribute('aria-label', 'Click to hear the weather');

            // Click handler
            el.addEventListener('click', (e) => {
                e.stopPropagation();
                celestialVoice.speak();
            });

            // Keyboard support
            el.addEventListener('keydown', (e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault();
                    celestialVoice.speak();
                }
            });

            // Visual feedback on hover
            el.addEventListener('mouseenter', () => {
                el.style.transform = (el.style.transform || '') + ' scale(1.05)';
                el.style.transition = 'transform 0.3s ease';
            });

            el.addEventListener('mouseleave', () => {
                el.style.transform = el.style.transform.replace(' scale(1.05)', '');
            });
        });

        // Also make the moon clickable for moon facts (if available)
        const moonEl = document.querySelector('.celestial-moon');
        if (moonEl) {
            moonEl.style.cursor = 'pointer';
            moonEl.setAttribute('role', 'button');
            moonEl.setAttribute('tabindex', '0');
            moonEl.setAttribute('aria-label', 'Click to hear about the moon');

            moonEl.addEventListener('click', (e) => {
                e.stopPropagation();
                this.speakMoonFacts();
            });

            moonEl.addEventListener('keydown', (e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault();
                    this.speakMoonFacts();
                }
            });
        }
    }

    speakMoonFacts() {
        const moon = Ephemeris.moonPhase();
        const phrases = [
            `The moon is ${moon.illumination}% illuminated. ${moon.phaseName}.`,
            `${moon.phaseName}. ${moon.illumination}% of its face catches the light.`,
            `Tonight we have a ${moon.phaseName.toLowerCase()}. ${moon.illumination}% visible.`,
            `The moon shows ${moon.illumination}% tonight. A ${moon.phaseName.toLowerCase()}.`,
        ];
        const phrase = phrases[Math.floor(Math.random() * phrases.length)];
        celestialVoice.say(phrase);
        console.log('%c' + phrase, 'color: #94a3b8; font-style: italic;');
    }

    update() {
        const sun = Ephemeris.sunPosition(HOME.latitude, HOME.longitude, this.currentTime);

        if (this.visualization) {
            this.visualization.update(sun.azimuth, sun.altitude);
        }

        // Update celestial sky with current time
        celestialSky.update(this.currentTime);

        // Update XR view if active
        celestialXR.update(this.currentTime);

        const recommendations = HomeGeometry.getAllRecommendations(
            sun.azimuth, sun.altitude, sun.isDay, this.weather
        );

        if (this.shadeTable) {
            this.shadeTable.update(recommendations);
        }

        this.updateDisplays(sun);
    }

    updateDisplays(sun) {
        const { timeDisplay, sunAzimuth, sunAltitude, sunDirection, isDay, weatherCondition, cloudCoverage } = this.elements;
        
        if (timeDisplay) {
            timeDisplay.textContent = this.currentTime.toLocaleTimeString('en-US', {
                hour: '2-digit',
                minute: '2-digit',
                hour12: true
            });
        }
        
        if (sunAzimuth) sunAzimuth.textContent = `${sun.azimuth}°`;
        if (sunAltitude) sunAltitude.textContent = `${sun.altitude}°`;
        if (sunDirection) sunDirection.textContent = sun.direction;
        if (isDay) {
            isDay.textContent = sun.isDay ? 'Yes' : 'No';
            isDay.className = `output-value ${sun.isDay ? 'good' : ''}`;
        }
        
        if (this.weather) {
            if (weatherCondition) weatherCondition.textContent = `${this.weather.icon} ${this.weather.name}`;
            if (cloudCoverage) cloudCoverage.textContent = `${this.weather.cloudCoverage}%`;
        } else {
            if (weatherCondition) weatherCondition.textContent = '—';
            if (cloudCoverage) cloudCoverage.textContent = '—';
        }
    }

    startAutoUpdate() {
        setInterval(() => {
            if (!this.elements.timeSlider || this.elements.timeSlider.value == this.elements.timeSlider.defaultValue) {
                this.currentTime = new Date();
                if (this.elements.timeSlider) {
                    this.elements.timeSlider.value = this.currentTime.getHours() + this.currentTime.getMinutes() / 60;
                }
                this.update();
            }
        }, 60000);
    }

    setupConsole() {
        console.log('%c☀️', 'font-size: 64px');
        console.log('%cWhat About the Weather?', 'font-size: 18px; font-family: Georgia, serif; color: #D4AF37; font-weight: bold;');
        console.log('%cCelestial Shades System — Technical Deep Dive', 'font-size: 12px; color: #888;');
        console.log('%c─────────────────────────────────────', 'color: #333;');
        console.log('%cwindow.celestial API:', 'color: #64D9FF; font-weight: bold;');
        console.log('%c  .ephemeris     — Sun position calculations', 'color: #888;');
        console.log('%c  .geometry      — Window glare calculations', 'color: #888;');
        console.log('%c  .getSunPosition()  — Current sun position', 'color: #888;');
        console.log('%c  .getRecommendations()  — Current shade levels', 'color: #888;');
        console.log('%c─────────────────────────────────────', 'color: #333;');
        console.log('%c☁️ Atmosphere Debug:', 'color: #a855f7; font-weight: bold;');
        console.log('%c  .atmosphere.debug()        — Show current state', 'color: #888;');
        console.log('%c  .atmosphere.simulate(cond) — Test a condition', 'color: #888;');
        console.log('%c  .atmosphere.restore()      — Restore real weather', 'color: #888;');
        console.log('%c  .atmosphere.testAPI()      — Test API connectivity', 'color: #888;');
        console.log('%c  .atmosphere.testLightning()— Flash lightning', 'color: #888;');
        console.log('%c  .atmosphere.listConditions()— List all conditions', 'color: #888;');
        console.log('%c─────────────────────────────────────', 'color: #333;');
        console.log('%c🗣️ Voice (click sun to trigger):', 'color: #D4AF37; font-weight: bold;');
        console.log('%c  .speak()                   — Speak the weather', 'color: #888;');
        console.log('%c  .say("text")               — Speak custom text', 'color: #888;');
        console.log('%c─────────────────────────────────────', 'color: #333;');
        console.log('%c🥽 WebXR (if supported):', 'color: #9F7AEA; font-weight: bold;');
        console.log('%c  .xr.isActive()             — Check if VR is active', 'color: #888;');
        console.log('%c  .xr.toggleXR()             — Enter/exit VR mode', 'color: #888;');
        console.log('%c─────────────────────────────────────', 'color: #333;');
        console.log('%c🧭 Device Orientation (tap sundial):', 'color: #64D9FF; font-weight: bold;');
        console.log('%c  .enableCompass()           — Request orientation permission', 'color: #888;');
        console.log('%c  .getOrientation()          — Get current device orientation', 'color: #888;');
        console.log('%c  .orientation.getData()     — Full orientation data', 'color: #888;');
        console.log('%c─────────────────────────────────────', 'color: #333;');
        console.log('%c↑↑↓↓←→←→BA for a surprise 🌈', 'color: #666; font-size: 10px;');
        console.log('%c☀️ Click the sun to hear the weather!', 'color: #D4AF37; font-style: italic; font-size: 10px;');
        console.log('%c🧭 Tap the sundial to enable compass leveling!', 'color: #64D9FF; font-style: italic; font-size: 10px;');

        window.celestial = {
            ephemeris: Ephemeris,
            geometry: HomeGeometry,
            weather: WeatherService,
            atmosphere: atmosphere,
            voice: celestialVoice,
            sky: celestialSky,
            xr: celestialXR,
            home: HOME,
            shades: SHADES,
            demo: this,
            getSunPosition: () => Ephemeris.sunPosition(HOME.latitude, HOME.longitude),
            getMoonPosition: () => Ephemeris.moonPosition(HOME.latitude, HOME.longitude),
            getRecommendations: () => {
                const sun = Ephemeris.sunPosition(HOME.latitude, HOME.longitude);
                return HomeGeometry.getAllRecommendations(sun.azimuth, sun.altitude, sun.isDay);
            },
            getAtmosphere: () => ({
                condition: atmosphere.condition,
                cloudCover: atmosphere.cloudCover,
                windSpeed: atmosphere.windSpeed,
                temperature: atmosphere.temperature,
                modifiers: { ...atmosphere.modifiers }
            }),
            // Debug shortcuts
            debugAtmosphere: () => atmosphere.debug(),
            simulateWeather: (condition, options) => atmosphere.simulate(condition, options),
            restoreWeather: () => atmosphere.restore(),
            testLightning: (count) => atmosphere.testLightning(count),
            // Voice shortcuts
            speak: () => celestialVoice.speak(),
            say: (text) => celestialVoice.say(text),
            // Device orientation
            orientation: deviceOrientation,
            enableCompass: () => celestialSky.requestOrientationPermission(),
            getOrientation: () => deviceOrientation.getData()
        };
    }
}

// ============================================================================
// 3D GLOBE — Real WebGL Earth with Three.js
// ============================================================================

class MiniGlobe {
    constructor(canvas, options = {}) {
        this.canvas = canvas;
        
        // Location to center on - REQUIRED, no hardcoded defaults
        this.targetLat = options.latitude;
        this.targetLon = options.longitude;
        
        if (this.targetLat == null || this.targetLon == null) {
            console.warn('MiniGlobe: No location provided, waiting for geolocation...');
            this.targetLat = 0;
            this.targetLon = 0;
        }
        
        // ═══════════════════════════════════════════════════════════════════
        // QUATERNION-BASED ORIENTATION (Fano-inspired: proper composition)
        // ═══════════════════════════════════════════════════════════════════
        // 
        // We use quaternions for all rotations because:
        // 1. They compose correctly (q1 * q2 gives proper combined rotation)
        // 2. They interpolate smoothly (slerp avoids gimbal lock)
        // 3. They're the natural representation for 3D orientation
        //
        // The "home" quaternion represents: globe rotated so target lat/lon faces camera
        // The "drag" quaternion represents: temporary user rotation (springs back)
        // Final orientation = drag * home (drag applied after home)
        // ═══════════════════════════════════════════════════════════════════
        
        this.homeQuat = null;      // Quaternion to center target location
        this.dragQuat = null;      // Quaternion for user drag interaction
        this.currentQuat = null;   // Current interpolated orientation
        this.dragVelocity = null;  // Angular velocity for momentum
        
        // Auto rotation (gentle drift around Y axis)
        this.autoRotateAngle = 0;
        this.autoRotateSpeed = 0.3; // degrees per second
        
        // Drag interaction state
        this.isDragging = false;
        this.dragStartX = 0;
        this.dragStartY = 0;
        this.lastDragTime = 0;
        
        // Three.js components
        this.scene = null;
        this.camera = null;
        this.renderer = null;
        this.globe = null;
        this.atmosphere = null;
        this.marker = null;
        this.markerGlow = null;
        this.clouds = null;
        this.nightLights = null;
        
        this.animationId = null;
        this.lastTime = performance.now();
        
        this.init();
    }
    
    init() {
        if (typeof THREE === 'undefined') {
            console.warn('Three.js not loaded, globe disabled');
            return;
        }
        
        const width = this.canvas.clientWidth || 300;
        const height = this.canvas.clientHeight || 300;
        
        // Scene
        this.scene = new THREE.Scene();
        
        // Camera - positioned to look at globe
        this.camera = new THREE.PerspectiveCamera(45, width / height, 0.1, 1000);
        this.camera.position.set(0, 0, 2.5);
        this.camera.lookAt(0, 0, 0);
        
        // Renderer
        this.renderer = new THREE.WebGLRenderer({
            canvas: this.canvas,
            alpha: true,
            antialias: true
        });
        this.renderer.setSize(width, height);
        this.renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
        this.renderer.setClearColor(0x000000, 0);
        
        // Initialize quaternions
        this.homeQuat = new THREE.Quaternion();
        this.dragQuat = new THREE.Quaternion(); // Identity = no drag
        this.currentQuat = new THREE.Quaternion();
        this.dragVelocity = new THREE.Quaternion(); // Identity = no velocity
        
        // Create globe
        this.createGlobe();
        this.createAtmosphere();
        this.createMarker();
        this.createLights();
        
        // Compute initial home quaternion and apply immediately
        this.computeHomeQuaternion();
        this.currentQuat.copy(this.homeQuat);
        this.applyQuaternion();
        
        // Setup drag interaction
        this.setupDragInteraction();
        
        // Start animation
        this.animate();
        
        console.log('%c🌍 3D Globe initialized (Quaternion mode)', 'color: #64B5F6;');
        console.log(`   Target: ${this.targetLat.toFixed(2)}°, ${this.targetLon.toFixed(2)}°`);
    }
    
    // ═══════════════════════════════════════════════════════════════════════
    // QUATERNION MATH (Fano plane composition principle)
    // ═══════════════════════════════════════════════════════════════════════
    
    computeHomeQuaternion() {
        // Goal: Rotate globe so that (targetLat, targetLon) faces the camera (+Z)
        //
        // EMPIRICAL CALIBRATION (from testing with Blue Marble texture):
        // - When rotation.y = 0°, Asia (~+130°E) faces camera
        // - To show Seattle (-122°): rotation = 160 + (-122) = 38°
        // - Formula: rotation_y = (160 + targetLon)° in radians
        //
        // For latitude, we tilt around X axis
        //
        // Quaternion composition: Y rotation (longitude), then X rotation (latitude)
        
        // Longitude rotation (empirically calibrated for Blue Marble texture)
        const lonRotation = (160 + this.targetLon) * Math.PI / 180;
        const qY = new THREE.Quaternion();
        qY.setFromAxisAngle(new THREE.Vector3(0, 1, 0), lonRotation);
        
        // Latitude tilt (small tilt based on latitude for viewing perspective)
        // Not a full lat rotation - just subtle camera perspective
        const latTilt = this.targetLat * 0.3 * Math.PI / 180;
        const qX = new THREE.Quaternion();
        qX.setFromAxisAngle(new THREE.Vector3(1, 0, 0), latTilt);
        
        // Compose: apply qY first (rotate to longitude), then qX (tilt for latitude)
        this.homeQuat.multiplyQuaternions(qX, qY);
    }
    
    applyQuaternion() {
        if (!this.globe) return;
        
        // Apply auto-rotation (gentle drift around world Y axis)
        const autoRotRad = this.autoRotateAngle * Math.PI / 180;
        const qAuto = new THREE.Quaternion();
        qAuto.setFromAxisAngle(new THREE.Vector3(0, 1, 0), autoRotRad);
        
        // Final quaternion: auto * current
        // (auto-rotation is in world space, applied first)
        const finalQuat = new THREE.Quaternion();
        finalQuat.multiplyQuaternions(qAuto, this.currentQuat);
        
        // Apply to globe and all layers
        this.globe.quaternion.copy(finalQuat);
        
        if (this.clouds) {
            this.clouds.quaternion.copy(finalQuat);
        }
        
        if (this.nightLights) {
            this.nightLights.quaternion.copy(finalQuat);
        }
    }
    
    createGlobe() {
        // High-detail Earth sphere
        const geometry = new THREE.SphereGeometry(1, 64, 64);
        
        // Use NASA Blue Marble texture from reliable CDN
        const textureLoader = new THREE.TextureLoader();
        
        // Earth day texture (Blue Marble)
        const earthTexture = textureLoader.load(
            'https://unpkg.com/three-globe@2.24.13/example/img/earth-blue-marble.jpg',
            () => console.log('%c🌍 Earth texture loaded', 'color: #4CAF50;'),
            undefined,
            () => {
                console.warn('Earth texture failed, using fallback');
                this.createFallbackTexture();
            }
        );
        earthTexture.anisotropy = 16;
        
        // Earth bump map for terrain
        const bumpTexture = textureLoader.load(
            'https://unpkg.com/three-globe@2.24.13/example/img/earth-topology.png'
        );
        
        // Earth specular map (water shine)
        const specTexture = textureLoader.load(
            'https://unpkg.com/three-globe@2.24.13/example/img/earth-water.png'
        );
        
        const material = new THREE.MeshPhongMaterial({
            map: earthTexture,
            bumpMap: bumpTexture,
            bumpScale: 0.015,
            specularMap: specTexture,
            specular: new THREE.Color(0x333333),
            shininess: 15
        });
        
        this.globe = new THREE.Mesh(geometry, material);
        this.scene.add(this.globe);
        
        // Night lights layer
        const nightTexture = textureLoader.load(
            'https://unpkg.com/three-globe@2.24.13/example/img/earth-night.jpg'
        );
        
        const nightGeometry = new THREE.SphereGeometry(1.001, 64, 64);
        const nightMaterial = new THREE.MeshBasicMaterial({
            map: nightTexture,
            transparent: true,
            opacity: 0.5,
            blending: THREE.AdditiveBlending,
            depthWrite: false
        });
        
        this.nightLights = new THREE.Mesh(nightGeometry, nightMaterial);
        this.scene.add(this.nightLights);
        
        // Cloud layer
        const cloudTexture = textureLoader.load(
            'https://unpkg.com/three-globe@2.24.13/example/img/earth-clouds.png'
        );
        
        const cloudGeometry = new THREE.SphereGeometry(1.01, 64, 64);
        const cloudMaterial = new THREE.MeshPhongMaterial({
            map: cloudTexture,
            transparent: true,
            opacity: 0.4,
            depthWrite: false
        });
        
        this.clouds = new THREE.Mesh(cloudGeometry, cloudMaterial);
        this.scene.add(this.clouds);
    }
    
    createFallbackTexture() {
        // Simple fallback if NASA textures fail to load
        const canvas = document.createElement('canvas');
        canvas.width = 512;
        canvas.height = 256;
        const ctx = canvas.getContext('2d');
        
        // Ocean
        ctx.fillStyle = '#1a4a7a';
        ctx.fillRect(0, 0, 512, 256);
        
        // Simple continents
        ctx.fillStyle = '#2d5a3d';
        ctx.fillRect(60, 40, 120, 80);   // North America
        ctx.fillRect(80, 140, 60, 80);   // South America  
        ctx.fillRect(220, 50, 80, 100);  // Europe/Africa
        ctx.fillRect(320, 40, 150, 120); // Asia
        ctx.fillRect(380, 160, 60, 50);  // Australia
        
        const texture = new THREE.CanvasTexture(canvas);
        if (this.globe) {
            this.globe.material.map = texture;
            this.globe.material.needsUpdate = true;
        }
    }
    
    createAtmosphere() {
        // Atmospheric glow (fresnel effect simulation)
        const atmosGeometry = new THREE.SphereGeometry(1.15, 32, 32);
        const atmosMaterial = new THREE.ShaderMaterial({
            uniforms: {
                glowColor: { value: new THREE.Color(0x4488ff) }
            },
            vertexShader: `
                varying vec3 vNormal;
                void main() {
                    vNormal = normalize(normalMatrix * normal);
                    gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
                }
            `,
            fragmentShader: `
                uniform vec3 glowColor;
                varying vec3 vNormal;
                void main() {
                    float intensity = pow(0.65 - dot(vNormal, vec3(0.0, 0.0, 1.0)), 2.0);
                    gl_FragColor = vec4(glowColor, intensity * 0.4);
                }
            `,
            side: THREE.BackSide,
            blending: THREE.AdditiveBlending,
            transparent: true,
            depthWrite: false
        });
        
        this.atmosphere = new THREE.Mesh(atmosGeometry, atmosMaterial);
        this.scene.add(this.atmosphere);
    }
    
    createMarker() {
        // Location marker as a glowing point
        const markerGeometry = new THREE.SphereGeometry(0.03, 16, 16);
        const markerMaterial = new THREE.MeshBasicMaterial({
            color: 0xd4af37,
            transparent: true,
            opacity: 1
        });
        this.marker = new THREE.Mesh(markerGeometry, markerMaterial);
        // Add marker as child of globe so it rotates with it
        this.globe.add(this.marker);
        
        // Marker glow
        const glowGeometry = new THREE.SphereGeometry(0.06, 16, 16);
        const glowMaterial = new THREE.MeshBasicMaterial({
            color: 0xd4af37,
            transparent: true,
            opacity: 0.3
        });
        this.markerGlow = new THREE.Mesh(glowGeometry, glowMaterial);
        this.globe.add(this.markerGlow);
        
        this.updateMarkerPosition();
    }
    
    createLights() {
        // Ambient light
        const ambient = new THREE.AmbientLight(0x404040, 0.5);
        this.scene.add(ambient);
        
        // Main light (simulates sun)
        const mainLight = new THREE.DirectionalLight(0xffffff, 1);
        mainLight.position.set(5, 3, 5);
        this.scene.add(mainLight);
        
        // Fill light
        const fillLight = new THREE.DirectionalLight(0x4488ff, 0.3);
        fillLight.position.set(-5, -2, 2);
        this.scene.add(fillLight);
        
        // Rim light for atmosphere
        const rimLight = new THREE.DirectionalLight(0x88aaff, 0.2);
        rimLight.position.set(0, 0, -5);
        this.scene.add(rimLight);
    }
    
    setupDragInteraction() {
        const canvas = this.canvas;
        
        // Mouse events
        canvas.addEventListener('mousedown', (e) => this.onDragStart(e.clientX, e.clientY));
        canvas.addEventListener('mousemove', (e) => this.onDragMove(e.clientX, e.clientY));
        canvas.addEventListener('mouseup', () => this.onDragEnd());
        canvas.addEventListener('mouseleave', () => this.onDragEnd());
        
        // Touch events
        canvas.addEventListener('touchstart', (e) => {
            e.preventDefault();
            const touch = e.touches[0];
            this.onDragStart(touch.clientX, touch.clientY);
        }, { passive: false });
        
        canvas.addEventListener('touchmove', (e) => {
            e.preventDefault();
            const touch = e.touches[0];
            this.onDragMove(touch.clientX, touch.clientY);
        }, { passive: false });
        
        canvas.addEventListener('touchend', () => this.onDragEnd());
        canvas.addEventListener('touchcancel', () => this.onDragEnd());
        
        // Cursor style
        canvas.style.cursor = 'grab';
    }
    
    onDragStart(x, y) {
        this.isDragging = true;
        this.dragStartX = x;
        this.dragStartY = y;
        this.lastDragX = x;
        this.lastDragY = y;
        this.lastDragTime = performance.now();
        
        // Reset velocity when starting new drag
        if (this.dragVelocity) {
            this.dragVelocity.identity();
        }
        
        this.canvas.style.cursor = 'grabbing';
    }
    
    onDragMove(x, y) {
        if (!this.isDragging) return;
        
        // Calculate delta from last position (not start position)
        const deltaX = x - this.lastDragX;
        const deltaY = y - this.lastDragY;
        
        // Apply incremental drag rotation
        this.applyDragDelta(deltaX, deltaY);
        
        // Update last position
        this.lastDragX = x;
        this.lastDragY = y;
        this.lastDragTime = performance.now();
    }
    
    onDragEnd() {
        if (!this.isDragging) return;
        this.isDragging = false;
        this.canvas.style.cursor = 'grab';
        // Momentum and spring-back handled in animate()
    }
    
    setLocation(lat, lon) {
        console.log(`%c🌍 Globe setLocation: ${lat.toFixed(2)}°, ${lon.toFixed(2)}°`, 'color: #64B5F6;');
        this.targetLat = lat;
        this.targetLon = lon;
        
        // Recompute home quaternion for new location
        this.computeHomeQuaternion();
        
        // Reset auto-rotate and drag state
        this.autoRotateAngle = 0;
        this.dragQuat.identity();
        this.dragVelocity.identity();
    }
    
    updateMarkerPosition() {
        if (!this.marker || !this.globe) return;
        
        // The marker is a child of the globe, positioned in local coordinates
        // In globe's local space, the target location should be at the front (+Z)
        // since we rotated the globe to center it
        
        // Position marker at front of globe (where target location is centered)
        const r = 1.03; // Slightly above surface
        this.marker.position.set(0, 0, r);
        this.markerGlow.position.copy(this.marker.position);
    }
    
    // ═══════════════════════════════════════════════════════════════════════
    // DRAG HANDLING (Quaternion-based with spring physics)
    // ═══════════════════════════════════════════════════════════════════════
    
    applyDragDelta(deltaX, deltaY) {
        // Convert pixel drag to rotation angles
        const sensitivity = 0.005; // radians per pixel
        const angleX = -deltaY * sensitivity; // Vertical drag → X rotation
        const angleY = deltaX * sensitivity;  // Horizontal drag → Y rotation
        
        // Create incremental rotation quaternions
        const qX = new THREE.Quaternion();
        const qY = new THREE.Quaternion();
        qX.setFromAxisAngle(new THREE.Vector3(1, 0, 0), angleX);
        qY.setFromAxisAngle(new THREE.Vector3(0, 1, 0), angleY);
        
        // Compose with existing drag: newDrag = qY * qX * oldDrag
        const incrementalDrag = new THREE.Quaternion();
        incrementalDrag.multiplyQuaternions(qY, qX);
        this.dragQuat.premultiply(incrementalDrag);
        
        // Store velocity for momentum
        this.dragVelocity.copy(incrementalDrag);
    }
    
    updateOrientation() {
        if (!this.homeQuat) return;
        
        // Compose: current = drag * home
        // This applies the home rotation first, then drag on top
        this.currentQuat.multiplyQuaternions(this.dragQuat, this.homeQuat);
        
        // Apply to globe
        this.applyQuaternion();
    }
    
    springBackDrag() {
        // Spring the drag quaternion back to identity (no drag)
        // Using slerp for smooth interpolation
        const springStrength = 0.08;
        const damping = 0.85;
        
        // Apply momentum first (if we have velocity)
        if (!this.dragVelocity.equals(new THREE.Quaternion())) {
            // Slerp velocity towards identity (decay)
            this.dragVelocity.slerp(new THREE.Quaternion(), 1 - damping);
            
            // Apply velocity to drag
            this.dragQuat.premultiply(this.dragVelocity);
        }
        
        // Spring force pulls drag towards identity
        this.dragQuat.slerp(new THREE.Quaternion(), springStrength);
        
        // Snap to identity when very close
        const identity = new THREE.Quaternion();
        if (Math.abs(this.dragQuat.dot(identity) - 1) < 0.0001) {
            this.dragQuat.identity();
            this.dragVelocity.identity();
        }
    }
    
    animate() {
        const now = performance.now();
        const delta = now - this.lastTime;
        this.lastTime = now;
        
        // Auto-rotation (gentle drift) - pause while dragging
        const identity = new THREE.Quaternion();
        const dragIsActive = this.dragQuat && Math.abs(this.dragQuat.dot(identity) - 1) > 0.001;
        
        if (!this.isDragging && !dragIsActive) {
            this.autoRotateAngle += this.autoRotateSpeed * delta / 1000;
            if (this.autoRotateAngle > 360) this.autoRotateAngle -= 360;
        }
        
        // Spring physics for drag (when not dragging)
        if (!this.isDragging && this.dragQuat) {
            this.springBackDrag();
        }
        
        // Update globe orientation
        this.updateOrientation();
        this.updateMarkerPosition();
        
        // Pulse marker
        if (this.markerGlow) {
            const pulse = 1 + 0.3 * Math.sin(now / 400);
            this.markerGlow.scale.setScalar(pulse);
        }
        
        // Twinkle city lights
        if (this.nightLights && this.nightLights.material) {
            const twinkle = 0.6 + 0.15 * Math.sin(now / 800);
            this.nightLights.material.opacity = twinkle;
        }
        
        // Render
        if (this.renderer && this.scene && this.camera) {
            this.renderer.render(this.scene, this.camera);
        }
        
        this.animationId = requestAnimationFrame(() => this.animate());
    }
    
    stop() {
        if (this.animationId) {
            cancelAnimationFrame(this.animationId);
        }
    }
    
    dispose() {
        this.stop();
        if (this.renderer) {
            this.renderer.dispose();
        }
    }
}

// ============================================================================
// COMPASS SUNDIAL — Isometric 3D with device orientation
// ============================================================================

class CompassSundial {
    constructor() {
        this.element = document.getElementById('compass-sundial');
        this.shadow = document.getElementById('compass-shadow');
        this.sunIndicator = document.getElementById('compass-sun-indicator');
        this.moonIndicator = document.getElementById('compass-moon-indicator');
        this.hint = document.getElementById('compass-hint');
        this.body = this.element?.querySelector('.compass-body');
        this.globeCanvas = document.getElementById('compass-globe');
        this.globeBg = document.getElementById('compass-globe-bg');
        this.globe = null;
        
        this.orientationEnabled = false;
        this.tiltX = 55; // Default isometric tilt
        this.tiltY = 0;
        this.rotation = 0;
        this.globeInitialized = false;
        
        if (this.element) {
            this.init();
        }
    }
    
    // Get viewer's location - ALWAYS from IP geolocation (atmosphere)
    getLocation() {
        // Primary: atmosphere has the IP-based geolocation
        if (typeof atmosphere !== 'undefined' && atmosphere.latitude != null && atmosphere.longitude != null) {
            return {
                latitude: atmosphere.latitude,
                longitude: atmosphere.longitude
            };
        }
        // Fallback: use HOME constant (defined at top of file)
        // This should only happen before atmosphere initializes
        return {
            latitude: HOME.latitude,
            longitude: HOME.longitude
        };
    }
    
    init() {
        // Click handlers for sun and moon (they talk!)
        if (this.sunIndicator) {
            this.sunIndicator.addEventListener('click', (e) => {
                e.stopPropagation();
                this.sunSpeak();
            });
        }
        
        if (this.moonIndicator) {
            this.moonIndicator.addEventListener('click', (e) => {
                e.stopPropagation();
                this.moonSpeak();
            });
        }
        
        // Compass click for orientation
        this.element.addEventListener('click', () => this.requestOrientation());
        
        // Listen for orientation updates
        deviceOrientation.addListener((data) => this.handleOrientation(data));
        
        // Check if already enabled
        if (deviceOrientation.hasPermission) {
            this.orientationEnabled = true;
            this.element.classList.add('orientation-active');
        }
        
        // Initialize globe when location is ready
        this.initGlobe();
        
        // Initial update
        this.updateCelestialBodies();
        
        // Update every 30 seconds
        setInterval(() => this.updateCelestialBodies(), 30000);
        
        // Retry globe init if location updates
        setTimeout(() => this.initGlobe(), 2000);
    }
    
    initGlobe() {
        if (this.globeInitialized || !this.globeCanvas) return;
        
        // Get location from IP geolocation (atmosphere)
        const loc = this.getLocation();
        if (loc.latitude == null || loc.longitude == null) {
            console.log('%c🌍 Globe waiting for geolocation...', 'color: #FFA500;');
            return; // Will retry
        }
        
        console.log(`%c🌍 Initializing globe at ${loc.latitude.toFixed(2)}°, ${loc.longitude.toFixed(2)}°`, 'color: #64B5F6;');
        
        this.globe = new MiniGlobe(this.globeCanvas, {
            latitude: loc.latitude,
            longitude: loc.longitude
        });
        
        this.globeInitialized = true;
        console.log('%c🌍 Globe initialized', 'color: #64B5F6;');
    }
    
    updateGlobeLocation(lat = null, lon = null) {
        if (!this.globe) return;
        // Use provided coordinates or fall back to getLocation()
        if (lat !== null && lon !== null) {
            this.globe.setLocation(lat, lon);
        } else {
            const loc = this.getLocation();
            this.globe.setLocation(loc.latitude, loc.longitude);
        }
    }
    
    getTemperatureString() {
        // Get current temperature from atmosphere if available
        // atmosphere is the global WeatherAtmosphere instance
        if (typeof atmosphere === 'undefined' || !atmosphere.temperature) {
            return null;
        }
        
        const temp = atmosphere.temperature;
        const useCelsius = localStorage.getItem('weather_temp_unit') === 'celsius';
        
        if (useCelsius) {
            return `${temp.toFixed(0)}°C`;
        } else {
            const fahrenheit = (temp * 9/5) + 32;
            return `${fahrenheit.toFixed(0)}°F`;
        }
    }
    
    sunSpeak() {
        const now = window.celestialDemo?.currentTime || new Date();
        const loc = this.getLocation();
        const sun = Ephemeris.sunPosition(loc.latitude, loc.longitude, now);
        const times = Ephemeris.sunTimes(loc.latitude, loc.longitude, now);
        
        const isDay = sun.altitude > 0;
        
        // Get weather data
        const weather = this.getWeatherData();
        
        // Console logging
        console.log(`%c${isDay ? '☀️ Sun Report' : '🌅 Sun Report'}`, 'color: #FFD700; font-size: 16px; font-weight: bold;');
        console.log(`%cAltitude: ${sun.altitude.toFixed(1)}° | Direction: ${sun.direction}`, 'color: #FFA500;');
        if (weather.current) console.log(`%cTemperature: ${weather.current}`, 'color: #888;');
        if (weather.high && weather.low) console.log(`%cHigh: ${weather.high} | Low: ${weather.low}`, 'color: #888;');
        
        // Show beautiful forecast toast
        this.showWeatherToast(weather, times, isDay);
    }
    
    getWeatherData() {
        const useCelsius = localStorage.getItem('weather_temp_unit') === 'celsius';
        const data = { current: null, high: null, low: null, condition: null, unit: useCelsius ? '°C' : '°F' };
        
        if (typeof atmosphere === 'undefined') return data;
        
        // Current temperature
        if (atmosphere.temperature != null) {
            const temp = useCelsius ? atmosphere.temperature : (atmosphere.temperature * 9/5) + 32;
            data.current = Math.round(temp);
        }
        
        // High/Low
        if (atmosphere.temperatureHigh != null) {
            const high = useCelsius ? atmosphere.temperatureHigh : (atmosphere.temperatureHigh * 9/5) + 32;
            data.high = Math.round(high);
        }
        if (atmosphere.temperatureLow != null) {
            const low = useCelsius ? atmosphere.temperatureLow : (atmosphere.temperatureLow * 9/5) + 32;
            data.low = Math.round(low);
        }
        
        // Condition
        data.condition = atmosphere.condition || 'clear';
        data.cloudCover = atmosphere.cloudCover || 0;
        
        return data;
    }
    
    getConditionIcon(condition) {
        const icons = {
            'clear': '☀️',
            'partly-cloudy': '⛅',
            'cloudy': '☁️',
            'overcast': '☁️',
            'fog': '🌫️',
            'drizzle': '🌧️',
            'rain': '🌧️',
            'heavy-rain': '⛈️',
            'thunderstorm': '⛈️',
            'snow': '❄️',
            'sleet': '🌨️'
        };
        return icons[condition] || '🌤️';
    }
    
    showWeatherToast(weather, times, isDay) {
        // Remove existing toast
        const existing = document.querySelector('.weather-forecast-toast');
        if (existing) existing.remove();
        
        const sunrise = times.sunrise ? times.sunrise.toLocaleTimeString([], {hour: 'numeric', minute:'2-digit'}) : '--';
        const sunset = times.sunset ? times.sunset.toLocaleTimeString([], {hour: 'numeric', minute:'2-digit'}) : '--';
        const conditionIcon = this.getConditionIcon(weather.condition);
        const conditionName = weather.condition ? weather.condition.replace('-', ' ').replace(/\b\w/g, l => l.toUpperCase()) : 'Unknown';
        
        const toast = document.createElement('div');
        toast.className = 'weather-forecast-toast';
        toast.innerHTML = `
            <div class="wft-header">
                <span class="wft-icon">${conditionIcon}</span>
                <span class="wft-condition">${conditionName}</span>
            </div>
            <div class="wft-temp-main">
                ${weather.current != null ? `<span class="wft-current">${weather.current}</span><span class="wft-unit">${weather.unit}</span>` : '<span class="wft-current">--</span>'}
            </div>
            <div class="wft-highlow">
                ${weather.high != null ? `<span class="wft-high">↑ ${weather.high}°</span>` : ''}
                ${weather.low != null ? `<span class="wft-low">↓ ${weather.low}°</span>` : ''}
            </div>
            <div class="wft-sun-times">
                <span class="wft-sunrise">🌅 ${sunrise}</span>
                <span class="wft-sunset">🌇 ${sunset}</span>
            </div>
        `;
        
        document.body.appendChild(toast);
        
        // Animate in
        requestAnimationFrame(() => {
            toast.classList.add('show');
        });
        
        // Remove after 5 seconds
        setTimeout(() => {
            toast.classList.remove('show');
            setTimeout(() => toast.remove(), 400);
        }, 5000);
    }
    
    getHighLowString() {
        // atmosphere is the global WeatherAtmosphere instance
        if (typeof atmosphere === 'undefined' || atmosphere.temperatureHigh === null || atmosphere.temperatureLow === null) {
            return null;
        }
        const atmos = atmosphere;
        
        const useCelsius = localStorage.getItem('weather_temp_unit') === 'celsius';
        
        if (useCelsius) {
            return `↑${atmos.temperatureHigh.toFixed(0)}° ↓${atmos.temperatureLow.toFixed(0)}°C`;
        } else {
            const highF = (atmos.temperatureHigh * 9/5) + 32;
            const lowF = (atmos.temperatureLow * 9/5) + 32;
            return `↑${highF.toFixed(0)}° ↓${lowF.toFixed(0)}°F`;
        }
    }
    
    moonSpeak() {
        const now = window.celestialDemo?.currentTime || new Date();
        const loc = this.getLocation();
        const moon = Ephemeris.moonPosition(loc.latitude, loc.longitude, now);
        
        const moonUp = moon.altitude > 0;
        const phaseEmoji = this.getMoonEmoji(moon.phase);
        const tempStr = this.getTemperatureString();
        
        let greeting = moonUp ? `${phaseEmoji} Hello from above!` : `${phaseEmoji} I'm below the horizon...`;
        if (tempStr) {
            greeting = moonUp 
                ? `${phaseEmoji} Hello! ${tempStr} tonight.` 
                : `${phaseEmoji} It's ${tempStr} while I rest.`;
        }
        
        const status = moonUp
            ? `I'm ${moon.altitude.toFixed(1)}° up, ${moon.illumination.toFixed(0)}% illuminated.`
            : `Currently ${Math.abs(moon.altitude).toFixed(1)}° below, ${moon.illumination.toFixed(0)}% illuminated.`;
        
        console.log(`%c${greeting}`, 'color: #C0C0C0; font-size: 16px; font-weight: bold;');
        console.log(`%c${status}`, 'color: #A0A0A0;');
        console.log(`%cPhase: ${moon.phaseName}`, 'color: #888;');
        
        // Show toast
        this.showToast(`${greeting} ${status}`);
    }
    
    getMoonEmoji(phase) {
        if (phase < 0.03) return '🌑';
        if (phase < 0.22) return '🌒';
        if (phase < 0.28) return '🌓';
        if (phase < 0.47) return '🌔';
        if (phase < 0.53) return '🌕';
        if (phase < 0.72) return '🌖';
        if (phase < 0.78) return '🌗';
        if (phase < 0.97) return '🌘';
        return '🌑';
    }
    
    showToast(message) {
        // Remove existing toast
        const existing = document.querySelector('.celestial-toast');
        if (existing) existing.remove();
        
        const toast = document.createElement('div');
        toast.className = 'celestial-toast';
        toast.textContent = message;
        document.body.appendChild(toast);
        
        // Animate in
        requestAnimationFrame(() => {
            toast.classList.add('show');
        });
        
        // Remove after 4 seconds
        setTimeout(() => {
            toast.classList.remove('show');
            setTimeout(() => toast.remove(), 300);
        }, 4000);
    }
    
    async requestOrientation() {
        if (this.orientationEnabled) return;
        
        const granted = await deviceOrientation.requestPermission();
        if (granted) {
            this.orientationEnabled = true;
            this.element.classList.add('orientation-active');
            
            // Feedback
            if (this.hint) {
                this.hint.innerHTML = '<span class="compass-hint-icon">✓</span><span>Orientation enabled</span>';
                setTimeout(() => {
                    this.hint.style.opacity = '0';
                }, 2000);
            }
        }
    }
    
    handleOrientation(data) {
        if (!this.orientationEnabled || !this.body) return;
        
        // Use device tilt to control compass perspective
        // Beta: front-back tilt (-180 to 180)
        // Gamma: left-right tilt (-90 to 90)
        
        const beta = data.beta || 0;
        const gamma = data.gamma || 0;
        const heading = data.compassHeading || data.alpha || 0;
        
        // Map device tilt to compass tilt
        // When device is flat (beta ~0), show more top-down
        // When device is tilted toward user (beta ~45), show more isometric
        this.tiltX = Math.max(30, Math.min(70, 55 + (beta - 45) * 0.5));
        this.tiltY = Math.max(-20, Math.min(20, gamma * 0.4));
        
        // Use compass heading to rotate the dial
        this.rotation = -heading;
        
        this.updateTransform();
    }
    
    updateTransform() {
        if (!this.body) return;
        // Flat compass - only rotate, no tilt (keeps sun/moon clickable)
        this.body.style.transform = `rotate(${this.rotation}deg)`;
    }
    
    updateCelestialBodies(lat = null, lon = null) {
        const now = window.celestialDemo?.currentTime || new Date();
        
        // Use provided coordinates or fall back to getLocation()
        let useLat, useLon;
        if (lat !== null && lon !== null) {
            useLat = lat;
            useLon = lon;
        } else {
            const loc = this.getLocation();
            useLat = loc.latitude;
            useLon = loc.longitude;
        }
        
        const sun = Ephemeris.sunPosition(useLat, useLon, now);
        const moon = Ephemeris.moonPosition(useLat, useLon, now);
        
        // Update sun position - radius 38 keeps it inside the face
        if (this.sunIndicator) {
            const radius = 38;
            const angleRad = (sun.azimuth - 90) * Math.PI / 180;
            const x = 50 + radius * Math.cos(angleRad);
            const y = 50 + radius * Math.sin(angleRad);
            
            this.sunIndicator.style.left = `${x}%`;
            this.sunIndicator.style.top = `${y}%`;
            
            const isDay = sun.altitude > 0;
            const scale = isDay ? 1 + (sun.altitude / 150) : 0.75;
            this.sunIndicator.style.opacity = isDay ? '1' : '0.4';
            this.sunIndicator.style.transform = `translate(-50%, -50%) scale(${scale})`;
        }
        
        // Update moon position
        if (this.moonIndicator && moon) {
            const radius = 38;
            const angleRad = (moon.azimuth - 90) * Math.PI / 180;
            const x = 50 + radius * Math.cos(angleRad);
            const y = 50 + radius * Math.sin(angleRad);
            
            this.moonIndicator.style.left = `${x}%`;
            this.moonIndicator.style.top = `${y}%`;
            
            const moonUp = moon.altitude > 0;
            const scale = moonUp ? 0.9 + (moon.altitude / 150) : 0.65;
            this.moonIndicator.style.opacity = moonUp ? '1' : '0.35';
            this.moonIndicator.style.transform = `translate(-50%, -50%) scale(${scale})`;
        }
        
        // Update sundial shadow — points OPPOSITE to the sun (180° offset)
        // The shadow is cast by the gnomon, falling away from the sun
        if (this.shadow) {
            const isDay = sun.altitude > -6; // Include civil twilight
            // Shadow points opposite to sun direction
            // Sun azimuth = where sun IS, shadow points opposite
            const shadowAngle = sun.azimuth + 180;
            
            this.shadow.style.setProperty('--shadow-angle', `${shadowAngle}deg`);
            
            // Remove previous state classes
            this.shadow.classList.remove('night', 'below-horizon');
            
            if (sun.altitude > 0) {
                // Daytime - full shadow
                this.shadow.style.opacity = '1';
            } else if (sun.altitude > -6) {
                // Twilight - faded shadow
                this.shadow.classList.add('night');
                this.shadow.style.opacity = '0.4';
            } else {
                // Night - very faint
                this.shadow.classList.add('below-horizon');
                this.shadow.style.opacity = '0.15';
            }
        }
    }
}

// ============================================================================
// INITIALIZE
// ============================================================================

const celestialDemo = new CelestialDemo();
const compassSundial = new CompassSundial();

// Expose to window for easter egg access
window.celestialDemo = celestialDemo;
window.compassSundial = compassSundial;

// Debug: Log celestial calculations on page load
(() => {
    const now = new Date();
    const sun = Ephemeris.sunPosition(HOME.latitude, HOME.longitude, now);
    const moon = Ephemeris.moonPosition(HOME.latitude, HOME.longitude, now);
    const times = Ephemeris.sunTimes(HOME.latitude, HOME.longitude, now);
    
    console.group('%c🌌 Celestial Ephemeris', 'color: #FFD700; font-weight: bold; font-size: 14px;');
    console.log('%cAlgorithms: Meeus "Astronomical Algorithms" + IAU 2000/2006', 'color: #666; font-style: italic;');
    console.log('%cAccuracy: Sun ±0.01°, Moon ±0.5°, Times ±1min', 'color: #666; font-style: italic;');
    console.log('%cValid: 1900-2100 (high), 0-4000 CE (±1°)', 'color: #666; font-style: italic;');
    console.log('');
    console.log(`%c📍 Location`, 'color: #4CAF50; font-weight: bold;');
    console.log(`   ${HOME.latitude.toFixed(4)}°N, ${Math.abs(HOME.longitude).toFixed(4)}°W`);
    console.log(`   Green Lake, Seattle, WA`);
    console.log(`   Local: ${now.toLocaleString()}`);
    console.log(`   TZ: UTC${now.getTimezoneOffset() > 0 ? '-' : '+'}${Math.abs(now.getTimezoneOffset() / 60)}`);
    console.log('');
    console.log(`%c☀️ Sun`, 'color: #FFA500; font-weight: bold;');
    console.log(`   Position: ${sun.altitude}° alt, ${sun.azimuth}° az (${sun.direction})`);
    console.log(`   Declination: ${sun._declination}°`);
    console.log(`   Status: ${sun.isDay ? '☀️ Day' : '🌙 Night'}`);
    console.log(`   Rise: ${Ephemeris.formatTime(times.sunrise)} → Noon: ${Ephemeris.formatTime(times.solarNoon)} → Set: ${Ephemeris.formatTime(times.sunset)}`);
    console.log(`   Day Length: ${times.dayLength} hours`);
    console.log('');
    console.log(`%c🌙 Moon`, 'color: #B0C4FF; font-weight: bold;');
    console.log(`   Position: ${moon.altitude}° alt, ${moon.azimuth}° az (${moon.direction})`);
    console.log(`   Phase: ${moon.phaseName} ${moon.phaseEmoji} (${moon.illumination}% illuminated)`);
    console.log(`   Phase Angle: ${moon.phaseAngle}°`);
    console.log(`   Visibility: ${moon.isVisible ? 'Above horizon' : 'Below horizon'}`);
    console.groupEnd();
    
    // Run verification in development
    if (location.hostname === 'localhost' || location.hostname === '127.0.0.1') {
        Ephemeris.verify();
    }
})();

// ============================================================================
// LOCATION MAP — Google Maps with dark styling
// ============================================================================

class LocationMap {
    constructor() {
        this.map = null;
        this.marker = null;
        this.mapElement = document.getElementById('location-map');
        this.coordsElement = document.getElementById('map-coords');
        
        if (this.mapElement) {
            this.init();
        }
    }
    
    init() {
        // Wait for Google Maps to load
        if (window.googleMapsLoaded) {
            this.createMap();
        } else {
            window.addEventListener('googlemaps-loaded', () => this.createMap());
        }
    }
    
    createMap() {
        const location = { lat: HOME.latitude, lng: HOME.longitude };
        
        // Dark map style
        const darkStyle = [
            { elementType: 'geometry', stylers: [{ color: '#1a1a18' }] },
            { elementType: 'labels.text.stroke', stylers: [{ color: '#1a1a18' }] },
            { elementType: 'labels.text.fill', stylers: [{ color: '#8a8a78' }] },
            {
                featureType: 'administrative',
                elementType: 'geometry.stroke',
                stylers: [{ color: '#3a3a28' }]
            },
            {
                featureType: 'road',
                elementType: 'geometry',
                stylers: [{ color: '#2a2a20' }]
            },
            {
                featureType: 'road',
                elementType: 'geometry.stroke',
                stylers: [{ color: '#1a1a10' }]
            },
            {
                featureType: 'road.highway',
                elementType: 'geometry',
                stylers: [{ color: '#3a3a28' }]
            },
            {
                featureType: 'water',
                elementType: 'geometry',
                stylers: [{ color: '#0d0d0a' }]
            },
            {
                featureType: 'water',
                elementType: 'labels.text.fill',
                stylers: [{ color: '#4a4a38' }]
            },
            {
                featureType: 'poi',
                elementType: 'geometry',
                stylers: [{ color: '#1a1a14' }]
            },
            {
                featureType: 'poi.park',
                elementType: 'geometry',
                stylers: [{ color: '#1a2018' }]
            },
            {
                featureType: 'transit',
                stylers: [{ visibility: 'off' }]
            }
        ];
        
        this.map = new google.maps.Map(this.mapElement, {
            center: location,
            zoom: 15,
            styles: darkStyle,
            disableDefaultUI: true,
            gestureHandling: 'greedy', // Enable panning
            draggable: true,
            scrollwheel: false,
            zoomControl: false,
            mapTypeControl: false,
            streetViewControl: false,
            fullscreenControl: false
        });
        
        // Custom marker (gold dot)
        this.marker = new google.maps.Marker({
            position: location,
            map: this.map,
            icon: {
                path: google.maps.SymbolPath.CIRCLE,
                fillColor: '#d4af37',
                fillOpacity: 1,
                strokeColor: '#fff',
                strokeWeight: 2,
                scale: 8
            },
            title: 'Home Location'
        });
        
        // Pulsing effect via CSS
        this.addPulsingMarker(location);
        
        // Update coords display on pan
        this.map.addListener('center_changed', () => {
            const center = this.map.getCenter();
            if (this.coordsElement) {
                const lat = center.lat().toFixed(4);
                const lng = Math.abs(center.lng()).toFixed(4);
                const latDir = center.lat() >= 0 ? 'N' : 'S';
                const lngDir = center.lng() >= 0 ? 'E' : 'W';
                this.coordsElement.textContent = `${Math.abs(lat)}° ${latDir}, ${lng}° ${lngDir}`;
            }
        });
        
        // Double-click to reset
        this.map.addListener('dblclick', () => {
            this.map.panTo(location);
            this.map.setZoom(15);
        });
    }
    
    addPulsingMarker(location) {
        // Add a pulsing overlay
        const pulseDiv = document.createElement('div');
        pulseDiv.className = 'map-pulse-marker';
        pulseDiv.innerHTML = `
            <div class="pulse-ring"></div>
            <div class="pulse-ring pulse-ring-2"></div>
        `;
        
        // Create overlay
        class PulseOverlay extends google.maps.OverlayView {
            constructor(position, div) {
                super();
                this.position = position;
                this.div = div;
            }
            onAdd() {
                this.getPanes().overlayLayer.appendChild(this.div);
            }
            draw() {
                const projection = this.getProjection();
                const pos = projection.fromLatLngToDivPixel(this.position);
                this.div.style.left = (pos.x - 20) + 'px';
                this.div.style.top = (pos.y - 20) + 'px';
            }
            onRemove() {
                this.div.parentNode.removeChild(this.div);
            }
        }
        
        new PulseOverlay(new google.maps.LatLng(location.lat, location.lng), pulseDiv).setMap(this.map);
    }
}

const locationMap = new LocationMap();

// ============================================================================
// TEMPERATURE UNIT TOGGLE — Celsius/Fahrenheit
// ============================================================================

class UnitToggle {
    constructor() {
        this.container = document.getElementById('unit-toggle');
        this.buttons = this.container?.querySelectorAll('.unit-btn');
        this.currentUnit = localStorage.getItem('tempUnit') || 'C';
        
        if (this.container) {
            this.init();
        }
    }
    
    init() {
        // Set initial state
        this.setUnit(this.currentUnit, false);
        
        // Add click handlers
        this.buttons.forEach(btn => {
            btn.addEventListener('click', () => {
                const unit = btn.dataset.unit;
                this.setUnit(unit, true);
            });
        });
    }
    
    setUnit(unit, notify = true) {
        this.currentUnit = unit;
        localStorage.setItem('tempUnit', unit);
        
        // Update button states
        this.buttons.forEach(btn => {
            btn.classList.toggle('active', btn.dataset.unit === unit);
        });
        
        // Dispatch event for other components
        if (notify) {
            window.dispatchEvent(new CustomEvent('unitChanged', { 
                detail: { unit } 
            }));
            
            // Show feedback
            const label = unit === 'C' ? 'Celsius' : 'Fahrenheit';
            console.log(`🌡️ Temperature unit: ${label}`);
        }
    }
    
    // Convert temperature
    static convert(celsius, toUnit) {
        if (toUnit === 'F') {
            return (celsius * 9/5) + 32;
        }
        return celsius;
    }
    
    // Format temperature with unit
    static format(celsius, unit) {
        const value = UnitToggle.convert(celsius, unit);
        return `${Math.round(value)}°${unit}`;
    }
    
    get unit() {
        return this.currentUnit;
    }
}

const unitToggle = new UnitToggle();

// Expose globally for use in other components
window.tempUnit = () => unitToggle.unit;
window.formatTemp = (celsius) => UnitToggle.format(celsius, unitToggle.unit);

// Expose for XR time sync
window.celestialDemo = celestialDemo;

// Scroll indicator click + keyboard support
const scrollIndicator = document.querySelector('.scroll-indicator');
if (scrollIndicator) {
    const scrollToEphemeris = () => {
        document.querySelector('#ephemeris')?.scrollIntoView({ behavior: 'smooth' });
    };
    scrollIndicator.addEventListener('click', scrollToEphemeris);
    scrollIndicator.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault();
            scrollToEphemeris();
        }
    });
}

// ============================================================================
// SERVICE WORKER REGISTRATION
// ============================================================================

if ('serviceWorker' in navigator) {
    window.addEventListener('load', () => {
        navigator.serviceWorker.register('/sw.js')
            .then((registration) => {
                console.log('%c[PWA] Service worker registered', 'color: #4ECB71;', registration.scope);

                // Listen for updates
                registration.addEventListener('updatefound', () => {
                    const newWorker = registration.installing;
                    console.log('%c[PWA] New service worker installing...', 'color: #FFAB40;');

                    newWorker.addEventListener('statechange', () => {
                        if (newWorker.state === 'installed' && navigator.serviceWorker.controller) {
                            console.log('%c[PWA] New content available, refresh to update', 'color: #64D9FF;');
                        }
                    });
                });
            })
            .catch((error) => {
                console.warn('[PWA] Service worker registration failed:', error);
            });

        // Listen for sync completion messages from SW
        navigator.serviceWorker.addEventListener('message', (event) => {
            if (event.data.type === 'SYNC_COMPLETE') {
                console.log('%c[PWA] Background sync complete', 'color: #4ECB71;');
                // Optionally refresh weather data
                if (atmosphere && atmosphere.weather) {
                    atmosphere.fetchWeather(atmosphere.latitude, atmosphere.longitude);
                }
            }
        });
    });
}
