/**
 * Museum-Quality Post-Processing Stack
 * ====================================
 * 
 * Professional-grade visual effects inspired by:
 * - ARTECHOUSE's cinematic quality
 * - teamLab's ethereal atmospheres
 * - James Turrell's perception-altering light
 * 
 * Effects:
 * - Subtle bloom for glowing elements
 * - Film grain for texture
 * - Chromatic aberration at edges
 * - Vignette for focus
 * - Color grading per colony
 * 
 * h(x) ≥ 0 always
 */

import * as THREE from 'three';
import { EffectComposer } from 'three/addons/postprocessing/EffectComposer.js';
import { RenderPass } from 'three/addons/postprocessing/RenderPass.js';
import { UnrealBloomPass } from 'three/addons/postprocessing/UnrealBloomPass.js';
import { ShaderPass } from 'three/addons/postprocessing/ShaderPass.js';
import { OutputPass } from 'three/addons/postprocessing/OutputPass.js';

// ═══════════════════════════════════════════════════════════════════════════
// CUSTOM SHADERS
// ═══════════════════════════════════════════════════════════════════════════

/**
 * Film Grain Shader
 * Adds subtle organic texture to the image
 */
const FilmGrainShader = {
    uniforms: {
        tDiffuse: { value: null },
        time: { value: 0 },
        intensity: { value: 0.015 },
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
        uniform float intensity;
        uniform float speed;
        varying vec2 vUv;
        
        // Simple noise function
        float random(vec2 p) {
            return fract(sin(dot(p, vec2(12.9898, 78.233))) * 43758.5453);
        }
        
        void main() {
            vec4 color = texture2D(tDiffuse, vUv);
            
            // Animated film grain
            float grain = random(vUv + fract(time * speed)) * 2.0 - 1.0;
            
            // Apply grain with intensity
            color.rgb += grain * intensity;
            
            gl_FragColor = color;
        }
    `
};

/**
 * Chromatic Aberration Shader
 * Subtle color fringing at edges for cinematic feel
 */
const ChromaticAberrationShader = {
    uniforms: {
        tDiffuse: { value: null },
        amount: { value: 0.003 },
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
            vec2 center = vec2(0.5);
            vec2 dir = vUv - center;
            float dist = length(dir);
            
            // Only apply at edges (radial falloff)
            float edgeFactor = smoothstep(0.2, 0.8, dist);
            float offset = amount * edgeFactor;
            
            vec2 offsetDir = normalize(dir) * offset;
            
            // Sample each color channel with slight offset
            float r = texture2D(tDiffuse, vUv + offsetDir).r;
            float g = texture2D(tDiffuse, vUv).g;
            float b = texture2D(tDiffuse, vUv - offsetDir).b;
            
            gl_FragColor = vec4(r, g, b, 1.0);
        }
    `
};

/**
 * Vignette Shader
 * Darkens edges to focus attention on center
 */
const VignetteShader = {
    uniforms: {
        tDiffuse: { value: null },
        darkness: { value: 0.4 },
        offset: { value: 1.0 }
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
        uniform float darkness;
        uniform float offset;
        varying vec2 vUv;
        
        void main() {
            vec4 color = texture2D(tDiffuse, vUv);
            
            // Calculate distance from center
            vec2 center = vec2(0.5);
            float dist = distance(vUv, center);
            
            // Smooth vignette
            float vignette = smoothstep(0.8, offset * 0.5, dist * (darkness + offset));
            
            color.rgb *= vignette;
            
            gl_FragColor = color;
        }
    `
};

/**
 * Color Grading Shader
 * Warm highlights, cool shadows, colony tinting
 */
const ColorGradingShader = {
    uniforms: {
        tDiffuse: { value: null },
        brightness: { value: 0.0 },
        contrast: { value: 1.05 },
        saturation: { value: 1.1 },
        warmth: { value: 0.05 },
        tint: { value: new THREE.Color(0xFFFFFF) },
        tintStrength: { value: 0.0 }
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
        uniform float brightness;
        uniform float contrast;
        uniform float saturation;
        uniform float warmth;
        uniform vec3 tint;
        uniform float tintStrength;
        varying vec2 vUv;
        
        void main() {
            vec4 color = texture2D(tDiffuse, vUv);
            
            // Brightness
            color.rgb += brightness;
            
            // Contrast
            color.rgb = (color.rgb - 0.5) * contrast + 0.5;
            
            // Saturation
            float luminance = dot(color.rgb, vec3(0.299, 0.587, 0.114));
            color.rgb = mix(vec3(luminance), color.rgb, saturation);
            
            // Warmth (shift toward orange in highlights)
            float highlightMask = smoothstep(0.5, 1.0, luminance);
            color.r += warmth * highlightMask;
            color.b -= warmth * 0.5 * highlightMask;
            
            // Cool shadows
            float shadowMask = 1.0 - smoothstep(0.0, 0.3, luminance);
            color.b += 0.02 * shadowMask;
            
            // Colony tint
            color.rgb = mix(color.rgb, color.rgb * tint, tintStrength);
            
            gl_FragColor = color;
        }
    `
};

// ═══════════════════════════════════════════════════════════════════════════
// POST-PROCESSING MANAGER
// ═══════════════════════════════════════════════════════════════════════════

export class PostProcessingManager {
    constructor(renderer, scene, camera) {
        this.renderer = renderer;
        this.scene = scene;
        this.camera = camera;
        
        this.composer = null;
        this.passes = {};
        this.time = 0;
        this.enabled = true;
        
        // Current zone for color grading
        this.currentZone = 'rotunda';
        
        this.init();
    }
    
    init() {
        this.composer = new EffectComposer(this.renderer);
        
        // Render pass (base scene)
        const renderPass = new RenderPass(this.scene, this.camera);
        this.composer.addPass(renderPass);
        this.passes.render = renderPass;
        
        // Bloom (enhanced for visual impact)
        const bloomPass = new UnrealBloomPass(
            new THREE.Vector2(window.innerWidth, window.innerHeight),
            0.7,   // strength (increased from 0.5)
            0.5,   // radius (increased for softer glow)
            0.75   // threshold (lowered to catch more bright elements)
        );
        this.composer.addPass(bloomPass);
        this.passes.bloom = bloomPass;
        
        // Chromatic aberration (very subtle)
        const chromaticPass = new ShaderPass(ChromaticAberrationShader);
        chromaticPass.uniforms.amount.value = 0.002;
        this.composer.addPass(chromaticPass);
        this.passes.chromatic = chromaticPass;
        
        // Vignette
        const vignettePass = new ShaderPass(VignetteShader);
        vignettePass.uniforms.darkness.value = 0.3;
        vignettePass.uniforms.offset.value = 1.2;
        this.composer.addPass(vignettePass);
        this.passes.vignette = vignettePass;
        
        // Color grading
        const colorGradingPass = new ShaderPass(ColorGradingShader);
        this.composer.addPass(colorGradingPass);
        this.passes.colorGrading = colorGradingPass;
        
        // Film grain (very subtle)
        const grainPass = new ShaderPass(FilmGrainShader);
        grainPass.uniforms.intensity.value = 0.012;
        this.composer.addPass(grainPass);
        this.passes.grain = grainPass;
        
        // Output pass (tone mapping, color space)
        const outputPass = new OutputPass();
        this.composer.addPass(outputPass);
        this.passes.output = outputPass;
    }
    
    // ═══════════════════════════════════════════════════════════════════════
    // ZONE-BASED COLOR GRADING
    // ═══════════════════════════════════════════════════════════════════════
    
    setZone(zone) {
        if (zone === this.currentZone) return;
        this.currentZone = zone;
        
        // Colony-specific color grading
        const colorGrading = this.passes.colorGrading;
        if (!colorGrading) return;
        
        const profiles = {
            rotunda: {
                tint: new THREE.Color(0xFFF8F0),
                tintStrength: 0.03,
                warmth: 0.03,
                saturation: 1.08,
                contrast: 1.05
            },
            spark: {
                tint: new THREE.Color(0xFF7744),
                tintStrength: 0.12,  // Stronger warm wash
                warmth: 0.12,
                saturation: 1.2,
                contrast: 1.08
            },
            forge: {
                tint: new THREE.Color(0xFFD700),
                tintStrength: 0.1,
                warmth: 0.1,
                saturation: 1.15,
                contrast: 1.1
            },
            flow: {
                tint: new THREE.Color(0x66DDDD),
                tintStrength: 0.12,  // Stronger cool wash
                warmth: -0.06,
                saturation: 1.12,
                contrast: 1.02
            },
            nexus: {
                tint: new THREE.Color(0xAA88CC),
                tintStrength: 0.15,  // Mysterious purple desaturation
                warmth: -0.02,
                saturation: 0.95,  // Slight desaturation for mystery
                contrast: 1.05
            },
            beacon: {
                tint: new THREE.Color(0xFFBB33),
                tintStrength: 0.12,
                warmth: 0.1,
                saturation: 1.2,
                contrast: 1.12
            },
            grove: {
                tint: new THREE.Color(0x88DD88),
                tintStrength: 0.12,  // Organic green tint
                warmth: -0.02,
                saturation: 1.1,
                contrast: 1.0
            },
            crystal: {
                tint: new THREE.Color(0x77DDFF),
                tintStrength: 0.14,  // Strong clarity effect
                warmth: -0.08,
                saturation: 1.15,
                contrast: 1.1
            }
        };
        
        const profile = profiles[zone] || profiles.rotunda;
        
        colorGrading.uniforms.tint.value.copy(profile.tint);
        colorGrading.uniforms.tintStrength.value = profile.tintStrength;
        colorGrading.uniforms.warmth.value = profile.warmth;
        colorGrading.uniforms.saturation.value = profile.saturation;
        colorGrading.uniforms.contrast.value = profile.contrast || 1.05;
    }
    
    // ═══════════════════════════════════════════════════════════════════════
    // UPDATE
    // ═══════════════════════════════════════════════════════════════════════
    
    update(deltaTime) {
        this.time += deltaTime;
        
        // Update film grain time
        if (this.passes.grain) {
            this.passes.grain.uniforms.time.value = this.time;
        }
    }
    
    render() {
        if (this.enabled) {
            this.composer.render();
        } else {
            this.renderer.render(this.scene, this.camera);
        }
    }
    
    // ═══════════════════════════════════════════════════════════════════════
    // SETTINGS
    // ═══════════════════════════════════════════════════════════════════════
    
    setBloomIntensity(intensity) {
        if (this.passes.bloom) {
            this.passes.bloom.strength = intensity;
        }
    }
    
    setFilmGrain(intensity) {
        if (this.passes.grain) {
            this.passes.grain.uniforms.intensity.value = intensity;
        }
    }
    
    setChromaticAberration(amount) {
        if (this.passes.chromatic) {
            this.passes.chromatic.uniforms.amount.value = amount;
        }
    }
    
    setVignette(darkness, offset) {
        if (this.passes.vignette) {
            this.passes.vignette.uniforms.darkness.value = darkness;
            this.passes.vignette.uniforms.offset.value = offset;
        }
    }
    
    // VR mode disables some effects
    setVRMode(enabled) {
        if (this.passes.chromatic) {
            this.passes.chromatic.enabled = !enabled;
        }
        if (this.passes.vignette) {
            this.passes.vignette.enabled = !enabled;
        }
        if (this.passes.grain) {
            this.passes.grain.uniforms.intensity.value = enabled ? 0.005 : 0.012;
        }
    }
    
    setSize(width, height) {
        this.composer.setSize(width, height);
        if (this.passes.bloom) {
            this.passes.bloom.setSize(width, height);
        }
    }
    
    toggle() {
        this.enabled = !this.enabled;
        return this.enabled;
    }
}

export { FilmGrainShader, ChromaticAberrationShader, VignetteShader, ColorGradingShader };
