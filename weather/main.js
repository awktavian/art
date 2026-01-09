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
// EPHEMERIS — Sun Position Calculations
// ============================================================================

class Ephemeris {
    /**
     * Calculate Julian Date from JavaScript Date
     */
    static julianDate(date) {
        const y = date.getUTCFullYear();
        const m = date.getUTCMonth() + 1;
        const d = date.getUTCDate();
        const h = date.getUTCHours() + date.getUTCMinutes() / 60 + date.getUTCSeconds() / 3600;
        
        let jy = y;
        let jm = m;
        if (m <= 2) {
            jy -= 1;
            jm += 12;
        }
        
        const a = Math.floor(jy / 100);
        const b = 2 - a + Math.floor(a / 4);
        
        return Math.floor(365.25 * (jy + 4716)) + 
               Math.floor(30.6001 * (jm + 1)) + 
               d + h / 24 + b - 1524.5;
    }

    /**
     * Calculate sun position (azimuth and altitude)
     */
    static sunPosition(lat, lon, date = new Date()) {
        const jd = this.julianDate(date);
        const n = jd - 2451545.0;
        
        const L = (280.460 + 0.9856474 * n) % 360;
        const g = ((357.528 + 0.9856003 * n) % 360) * Math.PI / 180;
        const lambda = (L + 1.915 * Math.sin(g) + 0.020 * Math.sin(2 * g)) * Math.PI / 180;
        const epsilon = 23.439 * Math.PI / 180;
        
        const alpha = Math.atan2(Math.cos(epsilon) * Math.sin(lambda), Math.cos(lambda));
        const delta = Math.asin(Math.sin(epsilon) * Math.sin(lambda));
        
        const gmst = (280.46061837 + 360.98564736629 * n) % 360;
        const lst = (gmst + lon) * Math.PI / 180;
        const ha = lst - alpha;
        
        const latRad = lat * Math.PI / 180;
        
        const altitude = Math.asin(
            Math.sin(latRad) * Math.sin(delta) + 
            Math.cos(latRad) * Math.cos(delta) * Math.cos(ha)
        ) * 180 / Math.PI;
        
        let azimuth = Math.atan2(
            -Math.sin(ha),
            Math.tan(delta) * Math.cos(latRad) - Math.sin(latRad) * Math.cos(ha)
        ) * 180 / Math.PI;
        
        azimuth = (azimuth + 360) % 360;
        
        return {
            altitude: Math.round(altitude * 10) / 10,
            azimuth: Math.round(azimuth * 10) / 10,
            isDay: altitude > 0,
            direction: this.azimuthToDirection(azimuth)
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
     * Calculate sunrise/sunset times (simplified)
     */
    static sunTimes(lat, lon, date = new Date()) {
        const jd = this.julianDate(date);
        const n = Math.floor(jd - 2451545.0 + 0.0008);
        
        const jStar = n - lon / 360;
        const M = (357.5291 + 0.98560028 * jStar) % 360;
        const C = 1.9148 * Math.sin(M * Math.PI / 180) + 
                  0.02 * Math.sin(2 * M * Math.PI / 180);
        const lambda = (M + C + 180 + 102.9372) % 360;
        
        const delta = Math.asin(Math.sin(lambda * Math.PI / 180) * Math.sin(23.44 * Math.PI / 180));
        
        const cosOmega = (Math.sin(-0.83 * Math.PI / 180) - Math.sin(lat * Math.PI / 180) * Math.sin(delta)) /
                         (Math.cos(lat * Math.PI / 180) * Math.cos(delta));
        
        if (cosOmega > 1) return { sunrise: null, sunset: null, polarNight: true };
        if (cosOmega < -1) return { sunrise: null, sunset: null, midnightSun: true };
        
        const omega = Math.acos(cosOmega) * 180 / Math.PI;
        
        const noon = 12 - lon / 15;
        const rise = noon - omega / 15;
        const set = noon + omega / 15;
        
        const baseDate = new Date(date);
        baseDate.setUTCHours(0, 0, 0, 0);
        
        return {
            sunrise: new Date(baseDate.getTime() + rise * 3600000),
            sunset: new Date(baseDate.getTime() + set * 3600000),
            solarNoon: new Date(baseDate.getTime() + noon * 3600000)
        };
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
// PARTICLES
// ============================================================================

class ParticleSystem {
    constructor(container) {
        this.container = container || document.body;
        this.particles = [];
        this.maxParticles = 20;
        
        this.init();
    }

    init() {
        const particleContainer = document.createElement('div');
        particleContainer.className = 'particles-container';
        this.container.appendChild(particleContainer);
        this.particleContainer = particleContainer;
        
        // Create initial particles
        for (let i = 0; i < this.maxParticles; i++) {
            this.createParticle(i);
        }
    }

    createParticle(index) {
        const particle = document.createElement('div');
        particle.className = 'particle';
        
        // Random position and timing
        const left = Math.random() * 100;
        const delay = Math.random() * 8;
        const duration = 6 + Math.random() * 4;
        const size = 2 + Math.random() * 3;
        
        particle.style.cssText = `
            left: ${left}%;
            width: ${size}px;
            height: ${size}px;
            animation-delay: ${delay}s;
            animation-duration: ${duration}s;
            opacity: ${0.3 + Math.random() * 0.4};
        `;
        
        this.particleContainer.appendChild(particle);
        this.particles.push(particle);
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
            <table class="data-table">
                <thead>
                    <tr>
                        <th>Shade</th>
                        <th>Room</th>
                        <th>Facing</th>
                        <th>Glare</th>
                        <th>Level</th>
                        <th>Reason</th>
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
        this.setupDelight();
        this.update();
        this.startAutoUpdate();
        this.setupConsole();
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
        
        slider.addEventListener('input', () => {
            const hours = parseFloat(slider.value);
            const h = Math.floor(hours);
            const m = Math.round((hours - h) * 60);
            
            this.currentTime = new Date();
            this.currentTime.setHours(h, m, 0, 0);
            
            this.update();
        });
        
        const weatherToggle = this.elements.weatherToggle;
        if (weatherToggle) {
            weatherToggle.addEventListener('change', () => {
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
        
        // Konami code
        new KonamiCode(() => {
            document.body.classList.add('konami-unlocked');
            console.log('%c🌈 KONAMI UNLOCKED!', 'font-size: 24px; color: #FFD700;');
            console.log('%cYou found the easter egg! The sun is now extra shiny.', 'color: #888;');
            
            // Rainbow sun
            const heroSun = document.querySelector('.hero-sun');
            if (heroSun) {
                heroSun.style.animation = 'sun-pulse 1s ease-in-out infinite, sun-float 4s ease-in-out infinite';
                heroSun.style.filter = 'hue-rotate(0deg)';
                let hue = 0;
                setInterval(() => {
                    hue = (hue + 2) % 360;
                    heroSun.style.filter = `hue-rotate(${hue}deg)`;
                }, 50);
            }
            
            setTimeout(() => {
                document.body.classList.remove('konami-unlocked');
            }, 500);
        });
    }

    update() {
        const sun = Ephemeris.sunPosition(HOME.latitude, HOME.longitude, this.currentTime);
        
        if (this.visualization) {
            this.visualization.update(sun.azimuth, sun.altitude);
        }
        
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
        console.log('%c↑↑↓↓←→←→BA for a surprise 🌈', 'color: #666; font-size: 10px;');
        
        window.celestial = {
            ephemeris: Ephemeris,
            geometry: HomeGeometry,
            weather: WeatherService,
            home: HOME,
            shades: SHADES,
            demo: this,
            getSunPosition: () => Ephemeris.sunPosition(HOME.latitude, HOME.longitude),
            getRecommendations: () => {
                const sun = Ephemeris.sunPosition(HOME.latitude, HOME.longitude);
                return HomeGeometry.getAllRecommendations(sun.azimuth, sun.altitude, sun.isDay);
            }
        };
    }
}

// ============================================================================
// INITIALIZE
// ============================================================================

const celestialDemo = new CelestialDemo();

// Scroll indicator click
document.querySelector('.scroll-indicator')?.addEventListener('click', () => {
    document.querySelector('#ephemeris')?.scrollIntoView({ behavior: 'smooth' });
});
