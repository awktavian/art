/**
 * Museum-Quality Post-Processing Stack
 * ====================================
 * 
 * AAA-grade visual effects inspired by:
 * - ARTECHOUSE's cinematic quality
 * - teamLab's ethereal atmospheres
 * - James Turrell's perception-altering light
 * - Uncharted/Naughty Dog cinematography
 * - SIGGRAPH research papers
 * 
 * Effects:
 * - SSAO (Screen Space Ambient Occlusion) for depth perception
 * - SSR (Screen Space Reflections) for polished surfaces
 * - Depth of Field with focal point tracking
 * - TAA (Temporal Anti-Aliasing) for smooth edges
 * - ACES filmic tone mapping
 * - Subtle bloom for glowing elements
 * - Film grain for texture
 * - Chromatic aberration at edges
 * - Vignette for focus
 * - Colony-specific color grading
 * 
 * h(x) ≥ 0 always
 */

import * as THREE from 'three';
import { EffectComposer } from 'three/addons/postprocessing/EffectComposer.js';
import { RenderPass } from 'three/addons/postprocessing/RenderPass.js';
import { UnrealBloomPass } from 'three/addons/postprocessing/UnrealBloomPass.js';
import { ShaderPass } from 'three/addons/postprocessing/ShaderPass.js';
import { OutputPass } from 'three/addons/postprocessing/OutputPass.js';
import { BokehPass } from 'three/addons/postprocessing/BokehPass.js';
import { SMAAPass } from 'three/addons/postprocessing/SMAAPass.js';
import { SSAOPass } from 'three/addons/postprocessing/SSAOPass.js';

// Optional imports - may not be available in all three.js versions
let GTAOPass = null;
let SSRPass = null;

// Attempt dynamic imports for optional passes
async function loadOptionalPasses() {
    try {
        const gtaoModule = await import('three/addons/postprocessing/GTAOPass.js');
        GTAOPass = gtaoModule.GTAOPass;
    } catch (e) {
        console.log('GTAOPass not available, will use SSAOPass fallback');
    }
    
    try {
        const ssrModule = await import('three/addons/postprocessing/SSRPass.js');
        SSRPass = ssrModule.SSRPass;
    } catch (e) {
        console.log('SSRPass not available, will use shader-based fallback');
    }
}

// Initialize optional passes
const optionalPassesReady = loadOptionalPasses();

// ═══════════════════════════════════════════════════════════════════════════
// QUALITY PRESETS
// ═══════════════════════════════════════════════════════════════════════════

export const POST_PROCESSING_QUALITY = {
    // CRISP QUALITY: Clean, sharp visuals - no grunge effects
    ultra: {
        ssao: true,
        ssaoSamples: 16,
        ssaoRadius: 1.2,
        ssaoIntensity: 0.7,
        ssr: true,             // Screen-space reflections on polished surfaces
        ssrMaxDistance: 50,
        dof: false,
        taa: true,             // Anti-aliasing for crisp edges
        bloom: true,
        bloomStrength: 0.45,
        bloomThreshold: 0.7,
        bloomRadius: 0.3,
        grain: 0,              // NO grain
        chromatic: 0,          // NO chromatic aberration
        vignette: 0,           // NO vignette
        exposure: 1.0
    },
    high: {
        ssao: true,
        ssaoSamples: 12,
        ssaoRadius: 1.0,
        ssaoIntensity: 0.6,
        ssr: false,
        ssrMaxDistance: 0,
        dof: false,
        taa: true,
        bloom: true,
        bloomStrength: 0.35,
        bloomThreshold: 0.65,
        bloomRadius: 0.25,
        grain: 0,
        chromatic: 0,
        vignette: 0,
        exposure: 1.0
    },
    medium: {
        ssao: false,
        ssaoSamples: 0,
        ssaoRadius: 0,
        ssr: false,
        ssrMaxDistance: 0,
        dof: false,
        taa: false,
        bloom: true,
        bloomStrength: 0.25,
        bloomThreshold: 0.7,
        bloomRadius: 0.25,
        grain: 0,
        chromatic: 0,
        vignette: 0
    },
    low: {
        ssao: false,
        ssaoSamples: 0,
        ssaoRadius: 0,
        ssr: false,
        ssrMaxDistance: 0,
        dof: false,
        taa: false,
        bloom: false,
        bloomStrength: 0,
        grain: 0,
        chromatic: 0,
        vignette: 0
    },
    emergency: {
        ssao: false,
        ssaoSamples: 0,
        ssaoRadius: 0,
        ssr: false,
        ssrMaxDistance: 0,
        dof: false,
        taa: false,
        bloom: false,
        bloomStrength: 0,
        grain: 0,
        chromatic: 0,
        vignette: 0
    }
};

// ═══════════════════════════════════════════════════════════════════════════
// CUSTOM SHADERS
// ═══════════════════════════════════════════════════════════════════════════

/**
 * ACES Tone Mapping Shader
 * Industry-standard filmic tone mapping
 */
const ACESToneMappingShader = {
    uniforms: {
        tDiffuse: { value: null },
        exposure: { value: 1.0 },
        whitePoint: { value: 11.2 }
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
        uniform float exposure;
        uniform float whitePoint;
        varying vec2 vUv;
        
        // ACES sRGB fitted
        vec3 ACESFilm(vec3 x) {
            float a = 2.51;
            float b = 0.03;
            float c = 2.43;
            float d = 0.59;
            float e = 0.14;
            return clamp((x * (a * x + b)) / (x * (c * x + d) + e), 0.0, 1.0);
        }
        
        void main() {
            vec4 texColor = texture2D(tDiffuse, vUv);
            vec3 color = texColor.rgb * exposure;
            
            // ACES tone mapping
            color = ACESFilm(color);
            
            // Gamma correction (if needed)
            // color = pow(color, vec3(1.0 / 2.2));
            
            gl_FragColor = vec4(color, texColor.a);
        }
    `
};

/**
 * Depth of Field Shader (Bokeh)
 * Focus-based blur with artistic bokeh shapes
 */
const DepthOfFieldShader = {
    uniforms: {
        tDiffuse: { value: null },
        tDepth: { value: null },
        focus: { value: 10.0 },
        aperture: { value: 0.025 },
        maxblur: { value: 0.01 },
        nearClip: { value: 0.1 },
        farClip: { value: 1000.0 }
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
        uniform sampler2D tDepth;
        uniform float focus;
        uniform float aperture;
        uniform float maxblur;
        uniform float nearClip;
        uniform float farClip;
        varying vec2 vUv;
        
        float getDepth(vec2 uv) {
            float depth = texture2D(tDepth, uv).x;
            float z = (nearClip * farClip) / (farClip - depth * (farClip - nearClip));
            return z;
        }
        
        void main() {
            float depth = getDepth(vUv);
            float factor = clamp(abs(depth - focus) * aperture, 0.0, maxblur);
            
            vec4 color = vec4(0.0);
            float total = 0.0;
            
            // Circular bokeh kernel (9 samples for performance)
            for (float i = -2.0; i <= 2.0; i += 1.0) {
                for (float j = -2.0; j <= 2.0; j += 1.0) {
                    float weight = 1.0 - length(vec2(i, j)) / 4.0;
                    if (weight > 0.0) {
                        vec2 offset = vec2(i, j) * factor;
                        color += texture2D(tDiffuse, vUv + offset) * weight;
                        total += weight;
                    }
                }
            }
            
            gl_FragColor = color / total;
        }
    `
};

/**
 * TAA (Temporal Anti-Aliasing) Shader
 * Jitter-based temporal accumulation for smooth edges
 */
const TAAShader = {
    uniforms: {
        tDiffuse: { value: null },
        tPrevious: { value: null },
        tVelocity: { value: null },
        blend: { value: 0.9 },
        resolution: { value: new THREE.Vector2() }
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
        uniform sampler2D tPrevious;
        uniform float blend;
        uniform vec2 resolution;
        varying vec2 vUv;
        
        // Simple neighborhood clamping
        vec3 clipAABB(vec3 aabbMin, vec3 aabbMax, vec3 p) {
            vec3 center = 0.5 * (aabbMax + aabbMin);
            vec3 halfSize = 0.5 * (aabbMax - aabbMin);
            vec3 clip = (p - center) / halfSize;
            vec3 clipAbs = abs(clip);
            float maxComponent = max(max(clipAbs.x, clipAbs.y), clipAbs.z);
            if (maxComponent > 1.0) {
                return center + clip / maxComponent * halfSize;
            }
            return p;
        }
        
        void main() {
            vec3 current = texture2D(tDiffuse, vUv).rgb;
            vec3 previous = texture2D(tPrevious, vUv).rgb;
            
            // Sample neighborhood for AABB clipping
            vec2 texelSize = 1.0 / resolution;
            vec3 neighborhood[9];
            int idx = 0;
            for (int x = -1; x <= 1; x++) {
                for (int y = -1; y <= 1; y++) {
                    neighborhood[idx++] = texture2D(tDiffuse, vUv + vec2(float(x), float(y)) * texelSize).rgb;
                }
            }
            
            vec3 aabbMin = min(min(min(min(min(min(min(min(
                neighborhood[0], neighborhood[1]), neighborhood[2]),
                neighborhood[3]), neighborhood[4]), neighborhood[5]),
                neighborhood[6]), neighborhood[7]), neighborhood[8]);
            vec3 aabbMax = max(max(max(max(max(max(max(max(
                neighborhood[0], neighborhood[1]), neighborhood[2]),
                neighborhood[3]), neighborhood[4]), neighborhood[5]),
                neighborhood[6]), neighborhood[7]), neighborhood[8]);
            
            // Clip history to neighborhood AABB
            previous = clipAABB(aabbMin, aabbMax, previous);
            
            // Blend
            vec3 result = mix(current, previous, blend);
            
            gl_FragColor = vec4(result, 1.0);
        }
    `
};

// SSAOShaderSimple REMOVED — tDepth/tNormal never bound, produced broken output.
// SSAO uses Three.js built-in SSAOPass only.
const _REMOVED_SSAOShaderSimple = {
    uniforms: {
        tDiffuse: { value: null },
        tDepth: { value: null },
        tNormal: { value: null },
        resolution: { value: new THREE.Vector2() },
        cameraNear: { value: 0.1 },
        cameraFar: { value: 1000.0 },
        radius: { value: 1.0 },
        intensity: { value: 1.0 },
        bias: { value: 0.025 },
        kernelSize: { value: 16 }
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
        uniform sampler2D tDepth;
        uniform vec2 resolution;
        uniform float cameraNear;
        uniform float cameraFar;
        uniform float radius;
        uniform float intensity;
        uniform float bias;
        varying vec2 vUv;
        
        float getLinearDepth(float depth) {
            return cameraNear * cameraFar / (cameraFar - depth * (cameraFar - cameraNear));
        }
        
        // Simple pseudo-random
        float random(vec2 co) {
            return fract(sin(dot(co, vec2(12.9898, 78.233))) * 43758.5453);
        }
        
        void main() {
            vec4 color = texture2D(tDiffuse, vUv);
            float depth = texture2D(tDepth, vUv).x;
            float linearDepth = getLinearDepth(depth);
            
            // Skip far fragments
            if (depth >= 1.0) {
                gl_FragColor = color;
                return;
            }
            
            float occlusion = 0.0;
            float sampleRadius = radius / linearDepth;
            
            // Deterministic Poisson disk pattern (pre-computed, stable)
            // These offsets create a well-distributed sample pattern without per-frame noise
            const vec2 poissonDisk[16] = vec2[](
                vec2(-0.94201624, -0.39906216),
                vec2(0.94558609, -0.76890725),
                vec2(-0.094184101, -0.92938870),
                vec2(0.34495938, 0.29387760),
                vec2(-0.91588581, 0.45771432),
                vec2(-0.81544232, -0.87912464),
                vec2(-0.38277543, 0.27676845),
                vec2(0.97484398, 0.75648379),
                vec2(0.44323325, -0.97511554),
                vec2(0.53742981, -0.47373420),
                vec2(-0.26496911, -0.41893023),
                vec2(0.79197514, 0.19090188),
                vec2(-0.24188840, 0.99706507),
                vec2(-0.81409955, 0.91437590),
                vec2(0.19984126, 0.78641367),
                vec2(0.14383161, -0.14100790)
            );
            
            // 16 sample kernel using stable Poisson disk
            for (int i = 0; i < 16; i++) {
                vec2 sampleOffset = poissonDisk[i] * sampleRadius;
                
                vec2 sampleUv = vUv + sampleOffset;
                float sampleDepth = texture2D(tDepth, sampleUv).x;
                float sampleLinearDepth = getLinearDepth(sampleDepth);
                
                // Range check with smooth falloff
                float rangeCheck = smoothstep(0.0, 1.0, radius / abs(linearDepth - sampleLinearDepth));
                occlusion += (sampleLinearDepth <= linearDepth - bias ? 1.0 : 0.0) * rangeCheck;
            }
            
            occlusion = 1.0 - (occlusion / 16.0) * intensity * 0.8;  // Slightly reduced intensity
            
            gl_FragColor = vec4(color.rgb * occlusion, color.a);
        }
    `
};

// SSRShaderSimple REMOVED — tDepth/tNormal never bound, corrupted frame buffer.
const _REMOVED_SSRShaderSimple = {
    uniforms: {
        tDiffuse: { value: null },
        tDepth: { value: null },
        tNormal: { value: null },
        resolution: { value: new THREE.Vector2() },
        cameraProjectionMatrix: { value: new THREE.Matrix4() },
        cameraInverseProjectionMatrix: { value: new THREE.Matrix4() },
        cameraNear: { value: 0.1 },
        cameraFar: { value: 1000.0 },
        maxDistance: { value: 50.0 },
        thickness: { value: 0.5 },
        intensity: { value: 0.5 }
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
        uniform sampler2D tDepth;
        uniform sampler2D tNormal;
        uniform vec2 resolution;
        uniform mat4 cameraProjectionMatrix;
        uniform mat4 cameraInverseProjectionMatrix;
        uniform float cameraNear;
        uniform float cameraFar;
        uniform float maxDistance;
        uniform float thickness;
        uniform float intensity;
        varying vec2 vUv;
        
        vec3 getViewPosition(vec2 uv, float depth) {
            vec4 ndc = vec4(uv * 2.0 - 1.0, depth * 2.0 - 1.0, 1.0);
            vec4 view = cameraInverseProjectionMatrix * ndc;
            return view.xyz / view.w;
        }
        
        void main() {
            vec4 color = texture2D(tDiffuse, vUv);
            float depth = texture2D(tDepth, vUv).x;
            
            // Skip background
            if (depth >= 1.0) {
                gl_FragColor = color;
                return;
            }
            
            vec3 normal = texture2D(tNormal, vUv).xyz * 2.0 - 1.0;
            vec3 viewPos = getViewPosition(vUv, depth);
            vec3 viewDir = normalize(viewPos);
            vec3 reflectDir = reflect(viewDir, normal);
            
            // Simple ray march (8 steps for performance)
            vec3 reflection = vec3(0.0);
            float hit = 0.0;
            
            for (int i = 1; i <= 8; i++) {
                vec3 rayPos = viewPos + reflectDir * (float(i) / 8.0 * maxDistance);
                vec4 projPos = cameraProjectionMatrix * vec4(rayPos, 1.0);
                projPos.xyz /= projPos.w;
                vec2 sampleUv = projPos.xy * 0.5 + 0.5;
                
                if (sampleUv.x < 0.0 || sampleUv.x > 1.0 || sampleUv.y < 0.0 || sampleUv.y > 1.0) break;
                
                float sampleDepth = texture2D(tDepth, sampleUv).x;
                vec3 sampleViewPos = getViewPosition(sampleUv, sampleDepth);
                
                if (abs(rayPos.z - sampleViewPos.z) < thickness) {
                    reflection = texture2D(tDiffuse, sampleUv).rgb;
                    hit = 1.0;
                    break;
                }
            }
            
            // Fresnel-based reflection intensity
            float fresnel = pow(1.0 - abs(dot(viewDir, normal)), 5.0);
            
            gl_FragColor = vec4(mix(color.rgb, reflection, hit * fresnel * intensity), color.a);
        }
    `
};

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
            
            // Stable temporal film grain - changes only every few frames
            // Floor the UV to create pixel blocks, floor time to reduce flicker
            vec2 stableUv = floor(vUv * 400.0) / 400.0;
            float stableTime = floor(time * 8.0);  // Update 8x per second, not every frame
            float grain = random(stableUv + stableTime * 0.1) * 2.0 - 1.0;
            
            // Softer grain application
            color.rgb += grain * intensity * 0.7;
            
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
        contrast: { value: 1.08 },
        saturation: { value: 1.15 },
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
    constructor(renderer, scene, camera, options = {}) {
        this.renderer = renderer;
        this.scene = scene;
        this.camera = camera;
        
        this.composer = null;
        this.passes = {};
        this.time = 0;
        this.enabled = true;
        
        // Quality preset
        this.qualityLevel = options.quality || 'high';
        this.quality = POST_PROCESSING_QUALITY[this.qualityLevel];
        
        // Current zone for color grading
        this.currentZone = 'rotunda';
        
        // Focal point tracking
        this.focusTarget = null;
        this.currentFocus = 10.0;
        this.focusSmoothing = 0.1;
        
        // TAA history buffer
        this.historyBuffer = null;
        this.jitterIndex = 0;
        this.jitterPattern = this.generateHaltonSequence(16);
        
        // Depth buffer for SSAO/SSR
        this.depthRenderTarget = null;
        this.normalRenderTarget = null;
        
        this.init();
    }
    
    /**
     * Generate Halton sequence for TAA jitter
     */
    generateHaltonSequence(count) {
        const sequence = [];
        for (let i = 0; i < count; i++) {
            sequence.push({
                x: this.halton(i, 2) - 0.5,
                y: this.halton(i, 3) - 0.5
            });
        }
        return sequence;
    }
    
    halton(index, base) {
        let result = 0;
        let f = 1 / base;
        let i = index;
        while (i > 0) {
            result += f * (i % base);
            i = Math.floor(i / base);
            f /= base;
        }
        return result;
    }
    
    init() {
        const width = window.innerWidth;
        const height = window.innerHeight;
        
        // Create render targets for deferred effects
        this.setupRenderTargets(width, height);
        
        this.composer = new EffectComposer(this.renderer);
        
        // ─────────────────────────────────────────────────────────────────────
        // BASE RENDER PASS
        // ─────────────────────────────────────────────────────────────────────
        const renderPass = new RenderPass(this.scene, this.camera);
        this.composer.addPass(renderPass);
        this.passes.render = renderPass;
        
        // ─────────────────────────────────────────────────────────────────────
        // SSAO (Screen Space Ambient Occlusion)
        // Uses SSAOPass which is reliably available
        // ─────────────────────────────────────────────────────────────────────
        if (this.quality.ssao) {
            try {
                // Try the built-in SSAOPass first (available in three.js 0.160)
                const ssaoPass = new SSAOPass(this.scene, this.camera, width, height);
                ssaoPass.kernelRadius = this.quality.ssaoRadius;
                ssaoPass.minDistance = 0.005;
                ssaoPass.maxDistance = 0.1;
                ssaoPass.output = SSAOPass.OUTPUT.Default;
                this.composer.addPass(ssaoPass);
                this.passes.ssao = ssaoPass;
            } catch (e) {
                console.warn('SSAOPass not available, skipping SSAO:', e);
            }
        }
        
        // ─────────────────────────────────────────────────────────────────────
        // SSR (Screen Space Reflections) - Custom Implementation
        // SSRPass may not be available in all versions, so we use our custom shader
        // ─────────────────────────────────────────────────────────────────────
        // SSR disabled — custom shader had unbound depth/normal textures.
        // Re-enable when Three.js SSRPass is wired with proper render targets.
        
        // ─────────────────────────────────────────────────────────────────────
        // BLOOM
        // ─────────────────────────────────────────────────────────────────────
        if (this.quality.bloom) {
            // Bloom tuned for emissive materials:
            //   threshold 0.6–0.8  →  catches MeshStandardMaterial with emissiveIntensity > 0
            //   strength  0.3–0.5  →  visible glow without washing out the scene
            //   radius    0.25–0.4 →  soft falloff, not a hard halo
            const bloomPass = new UnrealBloomPass(
                new THREE.Vector2(width, height),
                this.quality.bloomStrength,    // strength (per-preset)
                this.quality.bloomRadius || 0.3,  // radius (per-preset, fallback 0.3)
                this.quality.bloomThreshold ?? 0.7 // threshold (per-preset, fallback 0.7)
            );
            this.composer.addPass(bloomPass);
            this.passes.bloom = bloomPass;
        }
        
        // ─────────────────────────────────────────────────────────────────────
        // DEPTH OF FIELD
        // ─────────────────────────────────────────────────────────────────────
        if (this.quality.dof) {
            try {
                const bokehPass = new BokehPass(this.scene, this.camera, {
                    focus: 10.0,
                    aperture: 0.00025,
                    maxblur: 0.01
                });
                bokehPass.enabled = false; // Enable dynamically when needed
                this.composer.addPass(bokehPass);
                this.passes.dof = bokehPass;
            } catch (e) {
                console.warn('BokehPass not available:', e);
            }
        }
        
        // ─────────────────────────────────────────────────────────────────────
        // ACES TONE MAPPING (all presets — 1 draw call, critical for correct output)
        // ─────────────────────────────────────────────────────────────────────
        {
            const acesPass = new ShaderPass(ACESToneMappingShader);
            acesPass.uniforms.exposure.value = 1.0;
            this.composer.addPass(acesPass);
            this.passes.aces = acesPass;
            if (this.renderer) {
                this.renderer.toneMapping = THREE.NoToneMapping;
            }
        }
        
        // ─────────────────────────────────────────────────────────────────────
        // CHROMATIC ABERRATION
        // ─────────────────────────────────────────────────────────────────────
        if (this.quality.chromatic > 0) {
            const chromaticPass = new ShaderPass(ChromaticAberrationShader);
            chromaticPass.uniforms.amount.value = this.quality.chromatic;
            this.composer.addPass(chromaticPass);
            this.passes.chromatic = chromaticPass;
        }
        
        // ─────────────────────────────────────────────────────────────────────
        // VIGNETTE (disabled by default for clean look)
        // ─────────────────────────────────────────────────────────────────────
        if (this.quality.vignette > 0) {
            const vignettePass = new ShaderPass(VignetteShader);
            vignettePass.uniforms.darkness.value = this.quality.vignette;
            vignettePass.uniforms.offset.value = 1.4;
            this.composer.addPass(vignettePass);
            this.passes.vignette = vignettePass;
        }
        
        // ─────────────────────────────────────────────────────────────────────
        // COLOR GRADING (high/ultra only)
        // ─────────────────────────────────────────────────────────────────────
        if (this.qualityLevel === 'high' || this.qualityLevel === 'ultra') {
            const colorGradingPass = new ShaderPass(ColorGradingShader);
            this.composer.addPass(colorGradingPass);
            this.passes.colorGrading = colorGradingPass;
        }
        
        // ─────────────────────────────────────────────────────────────────────
        // FILM GRAIN
        // ─────────────────────────────────────────────────────────────────────
        if (this.quality.grain > 0) {
            const grainPass = new ShaderPass(FilmGrainShader);
            grainPass.uniforms.intensity.value = this.quality.grain;
            this.composer.addPass(grainPass);
            this.passes.grain = grainPass;
        }
        
        // ─────────────────────────────────────────────────────────────────────
        // SMAA (Anti-aliasing fallback when TAA is disabled)
        // ─────────────────────────────────────────────────────────────────────
        if (!this.quality.taa) {
            try {
                const smaaPass = new SMAAPass(width, height);
                this.composer.addPass(smaaPass);
                this.passes.smaa = smaaPass;
            } catch (e) {
                console.warn('SMAAPass not available:', e);
            }
        }
        
        // ─────────────────────────────────────────────────────────────────────
        // OUTPUT PASS
        // ─────────────────────────────────────────────────────────────────────
        const outputPass = new OutputPass();
        this.composer.addPass(outputPass);
        this.passes.output = outputPass;
    }
    
    /**
     * Setup render targets for deferred effects
     */
    setupRenderTargets(width, height) {
        // Render targets removed — depth/normal/history were never bound to any
        // shader uniform. SSAOPass creates its own internal targets.
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
                contrast: 1.05,
                exposure: 1.0
            },
            spark: {
                tint: new THREE.Color(0xFF7744),
                tintStrength: 0.12,  // Stronger warm wash
                warmth: 0.12,
                saturation: 1.2,
                contrast: 1.08,
                exposure: 1.1
            },
            forge: {
                tint: new THREE.Color(0xFFD700),
                tintStrength: 0.1,
                warmth: 0.1,
                saturation: 1.15,
                contrast: 1.1,
                exposure: 1.05
            },
            flow: {
                tint: new THREE.Color(0x66DDDD),
                tintStrength: 0.12,  // Stronger cool wash
                warmth: -0.06,
                saturation: 1.12,
                contrast: 1.02,
                exposure: 0.95
            },
            nexus: {
                tint: new THREE.Color(0xAA88CC),
                tintStrength: 0.15,  // Mysterious purple desaturation
                warmth: -0.02,
                saturation: 0.95,  // Slight desaturation for mystery
                contrast: 1.05,
                exposure: 0.9
            },
            beacon: {
                tint: new THREE.Color(0xFFBB33),
                tintStrength: 0.12,
                warmth: 0.1,
                saturation: 1.2,
                contrast: 1.12,
                exposure: 1.15
            },
            grove: {
                tint: new THREE.Color(0x88DD88),
                tintStrength: 0.12,  // Organic green tint
                warmth: -0.02,
                saturation: 1.1,
                contrast: 1.0,
                exposure: 1.0
            },
            crystal: {
                tint: new THREE.Color(0x77DDFF),
                tintStrength: 0.14,  // Strong clarity effect
                warmth: -0.08,
                saturation: 1.15,
                contrast: 1.1,
                exposure: 1.05
            }
        };
        
        const profile = profiles[zone] || profiles.rotunda;
        
        colorGrading.uniforms.tint.value.copy(profile.tint);
        colorGrading.uniforms.tintStrength.value = profile.tintStrength;
        colorGrading.uniforms.warmth.value = profile.warmth;
        colorGrading.uniforms.saturation.value = profile.saturation;
        colorGrading.uniforms.contrast.value = profile.contrast || 1.05;
        
        // Update ACES exposure per zone
        if (this.passes.aces) {
            this.passes.aces.uniforms.exposure.value = profile.exposure || 1.0;
        }
    }
    
    // ═══════════════════════════════════════════════════════════════════════
    // FOCUS CONTROL (for DoF)
    // ═══════════════════════════════════════════════════════════════════════
    
    /**
     * Set focus target for depth of field
     * @param {THREE.Object3D|THREE.Vector3|null} target - Object or position to focus on
     */
    setFocusTarget(target) {
        this.focusTarget = target;
        if (target && this.passes.dof) {
            this.passes.dof.enabled = true;
        }
    }
    
    /**
     * Clear focus target (disable DoF)
     */
    clearFocusTarget() {
        this.focusTarget = null;
        if (this.passes.dof) {
            this.passes.dof.enabled = false;
        }
    }
    
    /**
     * Update focus distance based on target
     */
    updateFocus() {
        if (!this.focusTarget || !this.passes.dof) return;
        
        let targetPosition;
        if (this.focusTarget.position) {
            targetPosition = this.focusTarget.position;
        } else if (this.focusTarget instanceof THREE.Vector3) {
            targetPosition = this.focusTarget;
        } else {
            return;
        }
        
        const distance = this.camera.position.distanceTo(targetPosition);
        this.currentFocus += (distance - this.currentFocus) * this.focusSmoothing;
        
        if (this.passes.dof.uniforms && this.passes.dof.uniforms.focus) {
            this.passes.dof.uniforms.focus.value = this.currentFocus;
        }
    }
    
    /**
     * Auto-focus DoF by raycasting from camera center into the scene.
     * Call each frame (or throttled) to keep BokehPass focus tracking
     * whatever the camera is looking at.
     * 
     * @param {THREE.Raycaster} raycaster - Raycaster to reuse (avoids allocation)
     * @param {THREE.Camera} camera - Camera whose forward direction defines the ray
     * @param {number} [defaultDistance=10] - Fallback focus distance when nothing is hit
     */
    updateFocalPoint(raycaster, camera, defaultDistance = 10) {
        if (!this.passes.dof) return;
        
        // Cast from camera center (0,0 in NDC) along the forward axis
        raycaster.setFromCamera({ x: 0, y: 0 }, camera);
        const hits = raycaster.intersectObjects(this.scene.children, true);
        
        const targetDistance = hits.length > 0 ? hits[0].distance : defaultDistance;
        
        // Smooth toward target to avoid jarring focus pops
        this.currentFocus += (targetDistance - this.currentFocus) * this.focusSmoothing;
        
        if (this.passes.dof.uniforms && this.passes.dof.uniforms.focus) {
            this.passes.dof.uniforms.focus.value = this.currentFocus;
        }
    }
    
    // ═══════════════════════════════════════════════════════════════════════
    // TAA JITTER
    // ═══════════════════════════════════════════════════════════════════════
    
    /**
     * Apply TAA jitter to camera projection matrix
     */
    applyJitter() {
        if (!this.quality.taa) return;
        
        const jitter = this.jitterPattern[this.jitterIndex];
        this.jitterIndex = (this.jitterIndex + 1) % this.jitterPattern.length;
        
        const pixelWidth = 1.0 / window.innerWidth;
        const pixelHeight = 1.0 / window.innerHeight;
        
        this.camera.projectionMatrix.elements[8] = jitter.x * pixelWidth * 2;
        this.camera.projectionMatrix.elements[9] = jitter.y * pixelHeight * 2;
    }
    
    /**
     * Remove TAA jitter from camera
     */
    removeJitter() {
        if (!this.quality.taa) return;
        this.camera.projectionMatrix.elements[8] = 0;
        this.camera.projectionMatrix.elements[9] = 0;
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
        
        // Update focus for DoF
        this.updateFocus();
        
        // Update SSAO camera matrices if using fallback shader
        if (this.passes.ssao && this.passes.ssao.uniforms) {
            this.passes.ssao.uniforms.cameraNear.value = this.camera.near;
            this.passes.ssao.uniforms.cameraFar.value = this.camera.far;
        }
        
        // Update SSR matrices if using fallback shader
        if (this.passes.ssr && this.passes.ssr.uniforms && this.passes.ssr.uniforms.cameraProjectionMatrix) {
            this.passes.ssr.uniforms.cameraProjectionMatrix.value.copy(this.camera.projectionMatrix);
            this.passes.ssr.uniforms.cameraInverseProjectionMatrix.value.copy(this.camera.projectionMatrixInverse);
            this.passes.ssr.uniforms.cameraNear.value = this.camera.near;
            this.passes.ssr.uniforms.cameraFar.value = this.camera.far;
        }
    }
    
    render() {
        if (this.enabled) {
            // Apply TAA jitter before render
            if (this.quality.taa) {
                this.applyJitter();
            }
            
            this.composer.render();
            
            // Remove jitter after render
            if (this.quality.taa) {
                this.removeJitter();
            }
        } else {
            this.renderer.render(this.scene, this.camera);
        }
    }
    
    // ═══════════════════════════════════════════════════════════════════════
    // SETTINGS
    // ═══════════════════════════════════════════════════════════════════════
    
    /**
     * Set quality preset
     */
    setQuality(level) {
        if (!POST_PROCESSING_QUALITY[level]) {
            console.warn(`Unknown quality level: ${level}`);
            return;
        }
        
        this.qualityLevel = level;
        this.quality = POST_PROCESSING_QUALITY[level];
        
        // Update pass settings
        if (this.passes.gtao) {
            this.passes.gtao.enabled = this.quality.ssao;
        }
        if (this.passes.ssao) {
            this.passes.ssao.enabled = this.quality.ssao;
            if (this.passes.ssao.uniforms) {
                this.passes.ssao.uniforms.radius.value = this.quality.ssaoRadius;
            }
        }
        if (this.passes.ssr) {
            this.passes.ssr.enabled = this.quality.ssr;
        }
        if (this.passes.bloom) {
            this.passes.bloom.enabled = this.quality.bloom;
            this.passes.bloom.strength = this.quality.bloomStrength;
        }
        if (this.passes.dof) {
            // DoF is controlled by focus target, but respect quality setting
            if (!this.quality.dof) {
                this.passes.dof.enabled = false;
            }
        }
        if (this.passes.grain) {
            this.passes.grain.uniforms.intensity.value = this.quality.grain;
        }
        if (this.passes.chromatic) {
            this.passes.chromatic.uniforms.amount.value = this.quality.chromatic;
        }
    }
    
    /**
     * Temporary bloom pulse for artwork discovery moments.
     * Ramps bloom up then back to baseline over ~1s.
     */
    triggerDiscoveryBloom(peakStrength = 0.8) {
        if (!this.passes.bloom) return;
        const base = this.quality.bloomStrength;
        this.passes.bloom.strength = peakStrength;
        const start = performance.now();
        const duration = 1000;
        const tick = () => {
            const t = Math.min(1, (performance.now() - start) / duration);
            this.passes.bloom.strength = base + (peakStrength - base) * (1 - t) * (1 - t);
            if (t < 1) requestAnimationFrame(tick);
        };
        requestAnimationFrame(tick);
    }
    
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
    
    setExposure(value) {
        if (this.passes.aces) {
            this.passes.aces.uniforms.exposure.value = value;
        }
    }
    
    setSSAOIntensity(intensity) {
        if (this.passes.gtao) {
            this.passes.gtao.blendIntensity = intensity;
        }
        if (this.passes.ssao && this.passes.ssao.uniforms) {
            this.passes.ssao.uniforms.intensity.value = intensity;
        }
    }
    
    setSSRIntensity(intensity) {
        if (this.passes.ssr) {
            if (this.passes.ssr.opacity !== undefined) {
                this.passes.ssr.opacity = intensity;
            } else if (this.passes.ssr.uniforms && this.passes.ssr.uniforms.intensity) {
                this.passes.ssr.uniforms.intensity.value = intensity;
            }
        }
    }
    
    // VR mode disables some effects
    setVRMode(enabled) {
        // Disable screen-space effects in VR (they don't work well with stereo rendering)
        if (this.passes.ssao) this.passes.ssao.enabled = !enabled && this.quality.ssao;
        if (this.passes.gtao) this.passes.gtao.enabled = !enabled && this.quality.ssao;
        if (this.passes.ssr) this.passes.ssr.enabled = !enabled && this.quality.ssr;
        if (this.passes.dof) this.passes.dof.enabled = false;
        if (this.passes.chromatic) this.passes.chromatic.enabled = !enabled;
        if (this.passes.vignette) this.passes.vignette.enabled = !enabled;
        
        // Reduce grain in VR
        if (this.passes.grain) {
            this.passes.grain.uniforms.intensity.value = enabled ? 0.003 : this.quality.grain;
        }
        
        // Disable TAA jitter in VR
        if (enabled) {
            this.removeJitter();
        }
    }
    
    setSize(width, height) {
        this.composer.setSize(width, height);
        
        if (this.passes.bloom) {
            this.passes.bloom.setSize(width, height);
        }
        if (this.passes.gtao) {
            this.passes.gtao.setSize(width, height);
        }
        if (this.passes.ssr && this.passes.ssr.setSize) {
            this.passes.ssr.setSize(width, height);
        }
        if (this.passes.dof && this.passes.dof.setSize) {
            this.passes.dof.setSize(width, height);
        }
        if (this.passes.smaa && this.passes.smaa.setSize) {
            this.passes.smaa.setSize(width, height);
        }
        
        // Update render targets
        if (this.depthRenderTarget) {
            this.depthRenderTarget.setSize(width, height);
        }
        if (this.normalRenderTarget) {
            this.normalRenderTarget.setSize(width, height);
        }
        if (this.historyBuffer) {
            this.historyBuffer.setSize(width, height);
        }
        
        // Update resolution uniforms
        if (this.passes.ssao && this.passes.ssao.uniforms) {
            this.passes.ssao.uniforms.resolution.value.set(width, height);
        }
        if (this.passes.ssr && this.passes.ssr.uniforms && this.passes.ssr.uniforms.resolution) {
            this.passes.ssr.uniforms.resolution.value.set(width, height);
        }
        
        // Regenerate jitter pattern for new resolution
        this.jitterPattern = this.generateHaltonSequence(16);
    }
    
    toggle() {
        this.enabled = !this.enabled;
        return this.enabled;
    }
    
    /**
     * Toggle specific pass
     */
    togglePass(passName, enabled = undefined) {
        const pass = this.passes[passName];
        if (pass) {
            pass.enabled = enabled !== undefined ? enabled : !pass.enabled;
            return pass.enabled;
        }
        return false;
    }
    
    /**
     * Get current quality level
     */
    getQuality() {
        return this.qualityLevel;
    }
    
    /**
     * Get all available passes
     */
    getPasses() {
        return Object.keys(this.passes);
    }
    
    /**
     * Dispose all resources
     */
    dispose() {
        if (this.depthRenderTarget) {
            this.depthRenderTarget.dispose();
        }
        if (this.normalRenderTarget) {
            this.normalRenderTarget.dispose();
        }
        if (this.historyBuffer) {
            this.historyBuffer.dispose();
        }
        if (this.composer) {
            this.composer.dispose();
        }
    }
}

export {
    ACESToneMappingShader,
    DepthOfFieldShader,
    TAAShader,
    FilmGrainShader,
    ChromaticAberrationShader,
    VignetteShader,
    ColorGradingShader
};
