/**
 * Kagami Orb V3.1 — Lighting & Environment
 * Studio-quality lighting setup for product visualization
 */

import * as THREE from 'three';

/**
 * Lighting presets for different moods
 */
export const LIGHTING_PRESETS = {
    // Clean studio lighting for product shots
    studio: {
        ambient: { color: 0xffffff, intensity: 0.3 },
        key: { color: 0xffffff, intensity: 1.5, position: [5, 8, 5] },
        fill: { color: 0x8888ff, intensity: 0.6, position: [-5, 3, -2] },
        rim: { color: 0xffffcc, intensity: 0.8, position: [0, -3, -5] },
        top: { color: 0xffffff, intensity: 0.5, position: [0, 10, 0] }
    },
    // Dramatic hero shot
    dramatic: {
        ambient: { color: 0x111122, intensity: 0.1 },
        key: { color: 0xff9900, intensity: 2.0, position: [4, 5, 3] },
        fill: { color: 0x0066ff, intensity: 0.4, position: [-4, 2, -2] },
        rim: { color: 0xff00ff, intensity: 1.0, position: [0, -2, -4] },
        top: null
    },
    // Warm evening ambiance
    evening: {
        ambient: { color: 0x221111, intensity: 0.2 },
        key: { color: 0xffcc88, intensity: 1.2, position: [4, 6, 4] },
        fill: { color: 0x6644ff, intensity: 0.3, position: [-3, 2, -3] },
        rim: { color: 0xff8844, intensity: 0.6, position: [0, -2, -4] },
        top: { color: 0xffaa66, intensity: 0.3, position: [0, 8, 0] }
    },
    // Cool tech aesthetic
    tech: {
        ambient: { color: 0x001122, intensity: 0.15 },
        key: { color: 0x00ccff, intensity: 1.5, position: [5, 7, 5] },
        fill: { color: 0x0044ff, intensity: 0.5, position: [-4, 3, -3] },
        rim: { color: 0x00ff88, intensity: 0.7, position: [0, -2, -5] },
        top: { color: 0x0088ff, intensity: 0.4, position: [0, 10, 0] }
    }
};

/**
 * Create complete lighting setup
 * @param {THREE.Scene} scene
 * @param {string} preset - Preset name
 * @returns {Object} Light references for animation
 */
export function createLighting(scene, preset = 'studio') {
    const config = LIGHTING_PRESETS[preset];
    const lights = {};

    // Ambient light
    lights.ambient = new THREE.AmbientLight(
        config.ambient.color,
        config.ambient.intensity
    );
    scene.add(lights.ambient);

    // Key light (main light source)
    lights.key = new THREE.DirectionalLight(
        config.key.color,
        config.key.intensity
    );
    lights.key.position.set(...config.key.position);
    lights.key.castShadow = true;
    lights.key.shadow.mapSize.width = 2048;
    lights.key.shadow.mapSize.height = 2048;
    lights.key.shadow.camera.near = 0.1;
    lights.key.shadow.camera.far = 50;
    lights.key.shadow.bias = -0.001;
    scene.add(lights.key);

    // Fill light (softens shadows)
    lights.fill = new THREE.DirectionalLight(
        config.fill.color,
        config.fill.intensity
    );
    lights.fill.position.set(...config.fill.position);
    scene.add(lights.fill);

    // Rim light (edge highlight)
    lights.rim = new THREE.DirectionalLight(
        config.rim.color,
        config.rim.intensity
    );
    lights.rim.position.set(...config.rim.position);
    scene.add(lights.rim);

    // Top light (optional)
    if (config.top) {
        lights.top = new THREE.PointLight(
            config.top.color,
            config.top.intensity
        );
        lights.top.position.set(...config.top.position);
        scene.add(lights.top);
    }

    return lights;
}

/**
 * Create HDRI environment map
 * @param {THREE.WebGLRenderer} renderer
 * @param {string} url - HDRI URL
 */
export async function createEnvironment(renderer, url) {
    const { RGBELoader } = await import('three/addons/loaders/RGBELoader.js');
    const loader = new RGBELoader();

    return new Promise((resolve, reject) => {
        loader.load(url, (texture) => {
            texture.mapping = THREE.EquirectangularReflectionMapping;
            resolve(texture);
        }, undefined, reject);
    });
}

/**
 * Create procedural studio environment (no external HDR needed)
 * @param {THREE.WebGLRenderer} renderer
 */
export function createProceduralEnvironment(renderer) {
    const pmremGenerator = new THREE.PMREMGenerator(renderer);
    pmremGenerator.compileEquirectangularShader();

    // Create gradient sky
    const scene = new THREE.Scene();

    // Soft gradient background
    const canvas = document.createElement('canvas');
    canvas.width = 512;
    canvas.height = 512;
    const ctx = canvas.getContext('2d');

    const gradient = ctx.createRadialGradient(256, 256, 0, 256, 256, 256);
    gradient.addColorStop(0, '#2a3a4a');
    gradient.addColorStop(0.5, '#1a2a3a');
    gradient.addColorStop(1, '#0a1a2a');
    ctx.fillStyle = gradient;
    ctx.fillRect(0, 0, 512, 512);

    const texture = new THREE.CanvasTexture(canvas);
    texture.mapping = THREE.EquirectangularReflectionMapping;

    const envMap = pmremGenerator.fromEquirectangular(texture).texture;
    pmremGenerator.dispose();

    return envMap;
}

/**
 * Create soft box lights (for studio setup)
 * @param {THREE.Scene} scene
 * @param {Object} options
 */
export function createSoftBoxLights(scene, options = {}) {
    const {
        count = 4,
        radius = 15,
        height = 10,
        color = 0xffffff,
        intensity = 0.4
    } = options;

    const lights = [];

    for (let i = 0; i < count; i++) {
        const angle = (i / count) * Math.PI * 2;
        const light = new THREE.RectAreaLight(color, intensity, 5, 5);
        light.position.set(
            Math.cos(angle) * radius,
            height,
            Math.sin(angle) * radius
        );
        light.lookAt(0, 0, 0);
        scene.add(light);
        lights.push(light);
    }

    return lights;
}

/**
 * Animate light color for mood transitions
 * @param {THREE.Light} light
 * @param {number} targetColor - Target color hex
 * @param {number} duration - Animation duration in ms
 */
export function animateLightColor(light, targetColor, duration = 1000) {
    const startColor = light.color.clone();
    const endColor = new THREE.Color(targetColor);
    const startTime = performance.now();

    function animate() {
        const elapsed = performance.now() - startTime;
        const t = Math.min(elapsed / duration, 1);
        const eased = t * t * (3 - 2 * t); // smoothstep

        light.color.lerpColors(startColor, endColor, eased);

        if (t < 1) {
            requestAnimationFrame(animate);
        }
    }

    animate();
}

/**
 * Create spotlight for dramatic component highlight
 * @param {THREE.Vector3} target - Point to illuminate
 */
export function createSpotlight(target) {
    const spotlight = new THREE.SpotLight(0xffffff, 2);
    spotlight.position.set(0, 20, 10);
    spotlight.angle = Math.PI / 8;
    spotlight.penumbra = 0.3;
    spotlight.decay = 2;
    spotlight.distance = 50;
    spotlight.target.position.copy(target);
    spotlight.castShadow = true;
    spotlight.shadow.mapSize.width = 1024;
    spotlight.shadow.mapSize.height = 1024;

    return spotlight;
}
