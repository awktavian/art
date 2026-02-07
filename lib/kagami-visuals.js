/**
 * Kagami Visuals Library for Three.js
 * ====================================
 * 
 * Post-processing effects, particle systems, and visual utilities.
 * Uses design tokens for consistent aesthetics.
 * 
 * h(x) ≥ 0 always
 */

import * as THREE from 'three';
import { EffectComposer } from 'three/addons/postprocessing/EffectComposer.js';
import { RenderPass } from 'three/addons/postprocessing/RenderPass.js';
import { UnrealBloomPass } from 'three/addons/postprocessing/UnrealBloomPass.js';
import { ShaderPass } from 'three/addons/postprocessing/ShaderPass.js';
import { OutputPass } from 'three/addons/postprocessing/OutputPass.js';

import {
    EFFECTS,
    COLONY_COLORS,
    COLONY_ORDER,
    VOID_COLORS,
    DURATION_S,
    getColonyColor as getColonyColorBase
} from './design-tokens.js';

// Helper to get colony color as THREE.Color
function getColonyColor(index) {
    return getColonyColorBase(THREE, index);
}

// ═══════════════════════════════════════════════════════════════════════════
// CUSTOM SHADERS
// ═══════════════════════════════════════════════════════════════════════════

// Chromatic Aberration Shader
export const ChromaticAberrationShader = {
    uniforms: {
        tDiffuse: { value: null },
        amount: { value: EFFECTS.chromaticAberration.offset },
        angle: { value: 0.0 }
    },
    vertexShader: `
        varying vec2 vUv;
        void main() {
            vUv = uv;
            gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
        }
    `,
    fragmentShader: `
        uniform sampler2D tDiffuse;
        uniform float amount;
        uniform float angle;
        varying vec2 vUv;
        
        void main() {
            vec2 offset = amount * vec2(cos(angle), sin(angle));
            
            vec4 cr = texture2D(tDiffuse, vUv + offset);
            vec4 cg = texture2D(tDiffuse, vUv);
            vec4 cb = texture2D(tDiffuse, vUv - offset);
            
            gl_FragColor = vec4(cr.r, cg.g, cb.b, cg.a);
        }
    `
};

// Film Grain Shader
export const FilmGrainShader = {
    uniforms: {
        tDiffuse: { value: null },
        time: { value: 0.0 },
        amount: { value: 0.05 },
        speed: { value: 1.0 }
    },
    vertexShader: `
        varying vec2 vUv;
        void main() {
            vUv = uv;
            gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
        }
    `,
    fragmentShader: `
        uniform sampler2D tDiffuse;
        uniform float time;
        uniform float amount;
        uniform float speed;
        varying vec2 vUv;
        
        float random(vec2 co) {
            return fract(sin(dot(co.xy, vec2(12.9898, 78.233))) * 43758.5453);
        }
        
        void main() {
            vec4 color = texture2D(tDiffuse, vUv);
            float grain = random(vUv + time * speed) * amount;
            color.rgb += grain - amount * 0.5;
            gl_FragColor = color;
        }
    `
};

// Scanline Shader
export const ScanlineShader = {
    uniforms: {
        tDiffuse: { value: null },
        resolution: { value: new THREE.Vector2(1920, 1080) },
        lineCount: { value: 400 },
        lineOpacity: { value: 0.1 },
        time: { value: 0.0 }
    },
    vertexShader: `
        varying vec2 vUv;
        void main() {
            vUv = uv;
            gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
        }
    `,
    fragmentShader: `
        uniform sampler2D tDiffuse;
        uniform vec2 resolution;
        uniform float lineCount;
        uniform float lineOpacity;
        uniform float time;
        varying vec2 vUv;
        
        void main() {
            vec4 color = texture2D(tDiffuse, vUv);
            float scanline = sin(vUv.y * lineCount * 3.14159) * 0.5 + 0.5;
            color.rgb -= scanline * lineOpacity;
            gl_FragColor = color;
        }
    `
};

// Glow Shader for emissive objects
export const GlowShader = {
    uniforms: {
        tDiffuse: { value: null },
        glowColor: { value: new THREE.Color(0x67D4E4) },
        glowIntensity: { value: 1.0 },
        time: { value: 0.0 }
    },
    vertexShader: `
        varying vec2 vUv;
        varying vec3 vNormal;
        varying vec3 vViewPosition;
        
        void main() {
            vUv = uv;
            vNormal = normalize(normalMatrix * normal);
            vec4 mvPosition = modelViewMatrix * vec4(position, 1.0);
            vViewPosition = -mvPosition.xyz;
            gl_Position = projectionMatrix * mvPosition;
        }
    `,
    fragmentShader: `
        uniform vec3 glowColor;
        uniform float glowIntensity;
        uniform float time;
        varying vec3 vNormal;
        varying vec3 vViewPosition;
        
        void main() {
            vec3 viewDir = normalize(vViewPosition);
            float fresnel = pow(1.0 - dot(vNormal, viewDir), 3.0);
            float pulse = 0.8 + 0.2 * sin(time * 2.0);
            vec3 color = glowColor * fresnel * glowIntensity * pulse;
            gl_FragColor = vec4(color, fresnel * 0.8);
        }
    `
};

// ═══════════════════════════════════════════════════════════════════════════
// POST-PROCESSING SETUP
// ═══════════════════════════════════════════════════════════════════════════

/**
 * Create a fully configured EffectComposer with Kagami visual style
 */
export function createComposer(renderer, scene, camera, options = {}) {
    const composer = new EffectComposer(renderer);
    
    // Base render pass
    const renderPass = new RenderPass(scene, camera);
    composer.addPass(renderPass);
    
    // Bloom pass (UnrealBloom for nice glow)
    if (options.bloom !== false) {
        const bloomPass = new UnrealBloomPass(
            new THREE.Vector2(window.innerWidth, window.innerHeight),
            options.bloomStrength ?? EFFECTS.bloom.strength,
            options.bloomRadius ?? EFFECTS.bloom.radius,
            options.bloomThreshold ?? EFFECTS.bloom.threshold
        );
        composer.addPass(bloomPass);
        composer.bloomPass = bloomPass;
    }
    
    // Chromatic aberration
    if (options.chromaticAberration !== false) {
        const caPass = new ShaderPass(ChromaticAberrationShader);
        caPass.uniforms.amount.value = options.chromaticAmount ?? EFFECTS.chromaticAberration.offset;
        composer.addPass(caPass);
        composer.chromaticPass = caPass;
    }
    
    // Film grain
    if (options.filmGrain !== false) {
        const grainPass = new ShaderPass(FilmGrainShader);
        grainPass.uniforms.amount.value = options.grainAmount ?? 0.03;
        composer.addPass(grainPass);
        composer.grainPass = grainPass;
    }
    
    // Scanlines (optional, more vaporwave)
    if (options.scanlines === true) {
        const scanlinePass = new ShaderPass(ScanlineShader);
        scanlinePass.uniforms.resolution.value.set(window.innerWidth, window.innerHeight);
        composer.addPass(scanlinePass);
        composer.scanlinePass = scanlinePass;
    }
    
    // Output pass for correct color space
    const outputPass = new OutputPass();
    composer.addPass(outputPass);
    
    return composer;
}

/**
 * Update time-based uniforms in composer
 */
export function updateComposerTime(composer, time) {
    if (composer.chromaticPass) {
        composer.chromaticPass.uniforms.angle.value = time * 0.5;
    }
    if (composer.grainPass) {
        composer.grainPass.uniforms.time.value = time;
    }
    if (composer.scanlinePass) {
        composer.scanlinePass.uniforms.time.value = time;
    }
}

// ═══════════════════════════════════════════════════════════════════════════
// PARTICLE SYSTEMS
// ═══════════════════════════════════════════════════════════════════════════

/**
 * Create an instanced particle system for E8 lattice or similar
 */
export function createInstancedParticles(count, options = {}) {
    const geometry = new THREE.IcosahedronGeometry(options.size || 0.08, options.detail || 1);
    const material = new THREE.MeshPhysicalMaterial({
        color: options.color || 0xFFFFFF,
        emissive: options.emissive || options.color || 0xFFFFFF,
        emissiveIntensity: options.emissiveIntensity || 0.3,
        metalness: 0.2,
        roughness: 0.4,
        transparent: true,
        opacity: options.opacity || 0.8
    });
    
    const mesh = new THREE.InstancedMesh(geometry, material, count);
    mesh.instanceMatrix.setUsage(THREE.DynamicDrawUsage);
    
    // Store instance data
    mesh.userData.positions = new Float32Array(count * 3);
    mesh.userData.colors = new Float32Array(count * 3);
    mesh.userData.scales = new Float32Array(count);
    mesh.userData.phases = new Float32Array(count);
    
    // Initialize with random phases for animation
    for (let i = 0; i < count; i++) {
        mesh.userData.phases[i] = Math.random() * Math.PI * 2;
        mesh.userData.scales[i] = 1.0;
    }
    
    return mesh;
}

/**
 * Update instanced particle positions with animation
 */
export function updateInstancedParticles(mesh, time, options = {}) {
    const matrix = new THREE.Matrix4();
    const position = new THREE.Vector3();
    const quaternion = new THREE.Quaternion();
    const scale = new THREE.Vector3();
    
    const positions = mesh.userData.positions;
    const phases = mesh.userData.phases;
    const scales = mesh.userData.scales;
    
    const pulseSpeed = options.pulseSpeed || 1.0;
    const pulseAmount = options.pulseAmount || 0.1;
    const rotationSpeed = options.rotationSpeed || 0.0;
    
    for (let i = 0; i < mesh.count; i++) {
        const idx = i * 3;
        
        // Base position
        position.set(positions[idx], positions[idx + 1], positions[idx + 2]);
        
        // Optional rotation
        if (rotationSpeed > 0) {
            const angle = time * rotationSpeed;
            const x = position.x;
            const z = position.z;
            position.x = x * Math.cos(angle) - z * Math.sin(angle);
            position.z = x * Math.sin(angle) + z * Math.cos(angle);
        }
        
        // Pulse animation
        const pulse = 1.0 + Math.sin(time * pulseSpeed + phases[i]) * pulseAmount;
        scale.setScalar(scales[i] * pulse);
        
        quaternion.setFromAxisAngle(new THREE.Vector3(0, 1, 0), time + phases[i]);
        
        matrix.compose(position, quaternion, scale);
        mesh.setMatrixAt(i, matrix);
    }
    
    mesh.instanceMatrix.needsUpdate = true;
}

/**
 * Set colors for instanced mesh (colony assignment)
 */
export function setInstancedColors(mesh, colorAssignments) {
    const color = new THREE.Color();
    
    for (let i = 0; i < mesh.count; i++) {
        const colonyIndex = colorAssignments[i] ?? (i % 7);
        color.copy(getColonyColor(colonyIndex));
        mesh.setColorAt(i, color);
    }
    
    if (mesh.instanceColor) {
        mesh.instanceColor.needsUpdate = true;
    }
}

// ═══════════════════════════════════════════════════════════════════════════
// GLOW EFFECTS
// ═══════════════════════════════════════════════════════════════════════════

/**
 * Create a glow mesh wrapper around an existing mesh
 */
export function createGlowMesh(baseMesh, options = {}) {
    const glowGeometry = baseMesh.geometry.clone();
    const glowScale = options.scale || 1.15;
    
    const glowMaterial = new THREE.ShaderMaterial({
        uniforms: {
            glowColor: { value: options.color || COLONY_THREE_COLORS.crystal.clone() },
            glowIntensity: { value: options.intensity || 1.0 },
            time: { value: 0.0 },
            viewVector: { value: new THREE.Vector3() }
        },
        vertexShader: `
            uniform vec3 viewVector;
            varying float intensity;
            void main() {
                vec3 vNormal = normalize(normalMatrix * normal);
                vec3 vNormViewVector = normalize(normalMatrix * viewVector);
                intensity = pow(0.8 - dot(vNormal, vNormViewVector), 2.0);
                gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
            }
        `,
        fragmentShader: `
            uniform vec3 glowColor;
            uniform float glowIntensity;
            uniform float time;
            varying float intensity;
            void main() {
                float pulse = 0.8 + 0.2 * sin(time * 3.0);
                vec3 color = glowColor * intensity * glowIntensity * pulse;
                gl_FragColor = vec4(color, intensity * 0.6);
            }
        `,
        side: THREE.BackSide,
        blending: THREE.AdditiveBlending,
        transparent: true,
        depthWrite: false
    });
    
    const glowMesh = new THREE.Mesh(glowGeometry, glowMaterial);
    glowMesh.scale.multiplyScalar(glowScale);
    
    return glowMesh;
}

/**
 * Update glow mesh uniforms
 */
export function updateGlowMesh(glowMesh, camera, time) {
    if (glowMesh.material.uniforms) {
        glowMesh.material.uniforms.viewVector.value = new THREE.Vector3().subVectors(
            camera.position,
            glowMesh.position
        );
        glowMesh.material.uniforms.time.value = time;
    }
}

// ═══════════════════════════════════════════════════════════════════════════
// LINE EFFECTS
// ═══════════════════════════════════════════════════════════════════════════

/**
 * Create an animated line with gradient color
 */
export function createAnimatedLine(points, options = {}) {
    const curve = new THREE.CatmullRomCurve3(points);
    const geometry = new THREE.TubeGeometry(
        curve,
        options.segments || 64,
        options.radius || 0.02,
        options.radialSegments || 8,
        false
    );
    
    const material = new THREE.ShaderMaterial({
        uniforms: {
            color1: { value: options.color1 || COLONY_THREE_COLORS.spark.clone() },
            color2: { value: options.color2 || COLONY_THREE_COLORS.crystal.clone() },
            time: { value: 0.0 },
            flowSpeed: { value: options.flowSpeed || 1.0 },
            opacity: { value: options.opacity || 0.6 }
        },
        vertexShader: `
            varying vec2 vUv;
            void main() {
                vUv = uv;
                gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
            }
        `,
        fragmentShader: `
            uniform vec3 color1;
            uniform vec3 color2;
            uniform float time;
            uniform float flowSpeed;
            uniform float opacity;
            varying vec2 vUv;
            
            void main() {
                float flow = fract(vUv.x - time * flowSpeed);
                float pulse = 0.5 + 0.5 * sin(flow * 6.28318);
                vec3 color = mix(color1, color2, flow) * (0.7 + pulse * 0.3);
                float alpha = opacity * (0.5 + pulse * 0.5);
                gl_FragColor = vec4(color, alpha);
            }
        `,
        transparent: true,
        side: THREE.DoubleSide,
        depthWrite: false,
        blending: THREE.AdditiveBlending
    });
    
    return new THREE.Mesh(geometry, material);
}

/**
 * Update animated line time
 */
export function updateAnimatedLine(line, time) {
    if (line.material.uniforms) {
        line.material.uniforms.time.value = time;
    }
}

// ═══════════════════════════════════════════════════════════════════════════
// BACKGROUND EFFECTS
// ═══════════════════════════════════════════════════════════════════════════

/**
 * Create a starfield background
 */
export function createStarfield(count = 2000, radius = 100) {
    const geometry = new THREE.BufferGeometry();
    const positions = new Float32Array(count * 3);
    const colors = new Float32Array(count * 3);
    const sizes = new Float32Array(count);
    
    for (let i = 0; i < count; i++) {
        const theta = Math.random() * Math.PI * 2;
        const phi = Math.acos(2 * Math.random() - 1);
        const r = radius * (0.5 + Math.random() * 0.5);
        
        positions[i * 3] = r * Math.sin(phi) * Math.cos(theta);
        positions[i * 3 + 1] = r * Math.sin(phi) * Math.sin(theta);
        positions[i * 3 + 2] = r * Math.cos(phi);
        
        // Mostly white with occasional colony colors
        if (Math.random() < 0.1) {
            const colonyColor = getColonyColor(Math.floor(Math.random() * 7));
            colors[i * 3] = colonyColor.r;
            colors[i * 3 + 1] = colonyColor.g;
            colors[i * 3 + 2] = colonyColor.b;
        } else {
            colors[i * 3] = 0.8 + Math.random() * 0.2;
            colors[i * 3 + 1] = 0.8 + Math.random() * 0.2;
            colors[i * 3 + 2] = 0.9 + Math.random() * 0.1;
        }
        
        sizes[i] = 0.5 + Math.random() * 1.5;
    }
    
    geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));
    geometry.setAttribute('color', new THREE.BufferAttribute(colors, 3));
    geometry.setAttribute('size', new THREE.BufferAttribute(sizes, 1));
    
    const material = new THREE.PointsMaterial({
        size: 0.5,
        vertexColors: true,
        transparent: true,
        opacity: 0.8,
        sizeAttenuation: true,
        blending: THREE.AdditiveBlending
    });
    
    return new THREE.Points(geometry, material);
}

/**
 * Create a grid floor with vaporwave aesthetic
 */
export function createVaporwaveGrid(size = 100, divisions = 50, options = {}) {
    const gridGroup = new THREE.Group();
    
    // Main grid
    const gridHelper = new THREE.GridHelper(
        size,
        divisions,
        options.color1 || 0xFF6AD5,
        options.color2 || 0xFF6AD5
    );
    gridHelper.material.opacity = options.opacity || 0.3;
    gridHelper.material.transparent = true;
    gridHelper.position.y = options.y || -5;
    gridGroup.add(gridHelper);
    
    // Glow plane under grid
    const planeGeometry = new THREE.PlaneGeometry(size, size);
    const planeMaterial = new THREE.ShaderMaterial({
        uniforms: {
            color: { value: new THREE.Color(options.glowColor || 0xFF6AD5) },
            time: { value: 0.0 }
        },
        vertexShader: `
            varying vec2 vUv;
            void main() {
                vUv = uv;
                gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
            }
        `,
        fragmentShader: `
            uniform vec3 color;
            uniform float time;
            varying vec2 vUv;
            
            void main() {
                float dist = distance(vUv, vec2(0.5));
                float glow = 1.0 - smoothstep(0.0, 0.7, dist);
                glow *= 0.3 + 0.1 * sin(time * 0.5);
                gl_FragColor = vec4(color * glow, glow * 0.5);
            }
        `,
        transparent: true,
        side: THREE.DoubleSide,
        depthWrite: false
    });
    
    const plane = new THREE.Mesh(planeGeometry, planeMaterial);
    plane.rotation.x = -Math.PI / 2;
    plane.position.y = (options.y || -5) - 0.01;
    gridGroup.add(plane);
    
    gridGroup.userData.update = (time) => {
        planeMaterial.uniforms.time.value = time;
    };
    
    return gridGroup;
}

// ═══════════════════════════════════════════════════════════════════════════
// LIGHTING PRESETS
// ═══════════════════════════════════════════════════════════════════════════

/**
 * Create standard Kagami lighting setup
 */
export function createKagamiLighting() {
    const group = new THREE.Group();
    
    // Ambient light (subtle)
    const ambient = new THREE.AmbientLight(0x1a1a2e, 0.3);
    group.add(ambient);
    
    // Main directional light
    const mainLight = new THREE.DirectionalLight(0xffffff, 0.8);
    mainLight.position.set(10, 20, 10);
    mainLight.castShadow = true;
    group.add(mainLight);
    
    // Colony-colored point lights
    const colonyLights = COLONY_ORDER.map((colony, i) => {
        const light = new THREE.PointLight(
            COLONY_THREE_COLORS[colony],
            0.5,
            30,
            2
        );
        const angle = (i / 7) * Math.PI * 2;
        light.position.set(
            Math.cos(angle) * 15,
            5,
            Math.sin(angle) * 15
        );
        return light;
    });
    
    colonyLights.forEach(light => group.add(light));
    group.userData.colonyLights = colonyLights;
    
    // Hemisphere light for nice ambient
    const hemiLight = new THREE.HemisphereLight(0x67D4E4, 0xFF6B35, 0.2);
    group.add(hemiLight);
    
    return group;
}

/**
 * Animate colony lights in a subtle pulsing pattern
 */
export function animateColonyLights(lightGroup, time) {
    const lights = lightGroup.userData.colonyLights;
    if (!lights) return;
    
    lights.forEach((light, i) => {
        // Fibonacci-based pulse offset
        const phase = (i * 0.618) * Math.PI * 2; // Golden ratio offset
        const pulse = 0.3 + 0.2 * Math.sin(time * 1.5 + phase);
        light.intensity = pulse;
    });
}

// ═══════════════════════════════════════════════════════════════════════════
// EXPORT
// ═══════════════════════════════════════════════════════════════════════════

export default {
    // Shaders
    ChromaticAberrationShader,
    FilmGrainShader,
    ScanlineShader,
    GlowShader,
    
    // Composer
    createComposer,
    updateComposerTime,
    
    // Particles
    createInstancedParticles,
    updateInstancedParticles,
    setInstancedColors,
    
    // Glow
    createGlowMesh,
    updateGlowMesh,
    
    // Lines
    createAnimatedLine,
    updateAnimatedLine,
    
    // Background
    createStarfield,
    createVaporwaveGrid,
    
    // Lighting
    createKagamiLighting,
    animateColonyLights
};
