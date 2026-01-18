/**
 * Kagami Orb V3.1 — Post-Processing Pipeline
 * Bloom, anti-aliasing, and tone mapping for premium rendering
 */

import * as THREE from 'three';

// These will be loaded from Three.js examples
let EffectComposer, RenderPass, UnrealBloomPass, SMAAPass, OutputPass;

/**
 * Initialize post-processing dependencies
 * Must be called before createPostProcessing
 */
export async function initPostProcessing(THREE_ADDONS) {
    EffectComposer = THREE_ADDONS.EffectComposer;
    RenderPass = THREE_ADDONS.RenderPass;
    UnrealBloomPass = THREE_ADDONS.UnrealBloomPass;
    SMAAPass = THREE_ADDONS.SMAAPass;
    OutputPass = THREE_ADDONS.OutputPass;
}

/**
 * Post-processing configuration presets
 */
export const PRESETS = {
    // Premium quality for hero shots
    ultra: {
        bloom: { strength: 0.8, radius: 0.6, threshold: 0.2 },
        exposure: 1.0,
        toneMapping: 'ACES',
        smaa: true
    },
    // Balanced for interactive viewing
    high: {
        bloom: { strength: 0.6, radius: 0.5, threshold: 0.3 },
        exposure: 1.0,
        toneMapping: 'ACES',
        smaa: true
    },
    // Performance mode
    medium: {
        bloom: { strength: 0.4, radius: 0.4, threshold: 0.4 },
        exposure: 1.0,
        toneMapping: 'Reinhard',
        smaa: false
    },
    // Mobile fallback
    low: {
        bloom: null,
        exposure: 1.0,
        toneMapping: 'Linear',
        smaa: false
    }
};

/**
 * Create post-processing composer
 * @param {THREE.WebGLRenderer} renderer
 * @param {THREE.Scene} scene
 * @param {THREE.Camera} camera
 * @param {Object} options - Preset name or custom config
 */
export function createPostProcessing(renderer, scene, camera, options = 'high') {
    const config = typeof options === 'string' ? PRESETS[options] : options;
    const size = renderer.getSize(new THREE.Vector2());

    // Configure renderer tone mapping
    renderer.toneMapping = getToneMapping(config.toneMapping);
    renderer.toneMappingExposure = config.exposure;

    // Create composer
    const composer = new EffectComposer(renderer);

    // Base render pass
    const renderPass = new RenderPass(scene, camera);
    composer.addPass(renderPass);

    // Bloom pass (selective for LEDs)
    if (config.bloom) {
        const bloomPass = new UnrealBloomPass(
            new THREE.Vector2(size.x, size.y),
            config.bloom.strength,
            config.bloom.radius,
            config.bloom.threshold
        );
        composer.addPass(bloomPass);
    }

    // SMAA anti-aliasing
    if (config.smaa && SMAAPass) {
        const smaaPass = new SMAAPass(size.x, size.y);
        composer.addPass(smaaPass);
    }

    // Output pass (color space conversion)
    if (OutputPass) {
        const outputPass = new OutputPass();
        composer.addPass(outputPass);
    }

    return composer;
}

/**
 * Get Three.js tone mapping constant from name
 */
function getToneMapping(name) {
    const mappings = {
        'Linear': THREE.LinearToneMapping,
        'Reinhard': THREE.ReinhardToneMapping,
        'ACES': THREE.ACESFilmicToneMapping,
        'Cineon': THREE.CineonToneMapping,
        'AgX': THREE.AgXToneMapping,
        'Neutral': THREE.NeutralToneMapping
    };
    return mappings[name] || THREE.ACESFilmicToneMapping;
}

/**
 * Create selective bloom layer
 * Objects in this layer will glow, others won't
 */
export function createBloomLayer() {
    const BLOOM_LAYER = 1;
    const bloomLayer = new THREE.Layers();
    bloomLayer.set(BLOOM_LAYER);
    return { layer: bloomLayer, id: BLOOM_LAYER };
}

/**
 * Update post-processing on resize
 */
export function updatePostProcessingSize(composer, width, height) {
    composer.setSize(width, height);
}

/**
 * Bloom parameters for different visual states
 */
export const BLOOM_STATES = {
    idle: { strength: 0.4, radius: 0.5 },
    active: { strength: 0.8, radius: 0.6 },
    highlight: { strength: 1.2, radius: 0.7 },
    pulse: { strength: 0.6, radius: 0.55 }
};

/**
 * Animate bloom between states
 * @param {UnrealBloomPass} bloomPass
 * @param {string} targetState
 * @param {number} duration - Animation duration in ms
 */
export function animateBloom(bloomPass, targetState, duration = 500) {
    const target = BLOOM_STATES[targetState] || BLOOM_STATES.idle;
    const start = {
        strength: bloomPass.strength,
        radius: bloomPass.radius
    };
    const startTime = performance.now();

    function animate() {
        const elapsed = performance.now() - startTime;
        const t = Math.min(elapsed / duration, 1);
        const eased = easeOutCubic(t);

        bloomPass.strength = start.strength + (target.strength - start.strength) * eased;
        bloomPass.radius = start.radius + (target.radius - start.radius) * eased;

        if (t < 1) {
            requestAnimationFrame(animate);
        }
    }

    animate();
}

/**
 * Easing function for smooth transitions
 */
function easeOutCubic(t) {
    return 1 - Math.pow(1 - t, 3);
}

/**
 * Create vignette effect (CSS-based for performance)
 */
export function createVignetteOverlay(container) {
    const vignette = document.createElement('div');
    vignette.style.cssText = `
        position: absolute;
        top: 0; left: 0; right: 0; bottom: 0;
        pointer-events: none;
        background: radial-gradient(
            ellipse at center,
            transparent 0%,
            transparent 60%,
            rgba(0,0,0,0.2) 100%
        );
        z-index: 10;
    `;
    container.appendChild(vignette);
    return vignette;
}
