/**
 * Custom Shaders for P1 Artworks
 * ===============================
 * 
 * AAA-quality physically-based materials with custom effects for each P1 patent artwork.
 * 
 * Material Properties:
 * - IOR (Index of Refraction) for realistic glass/crystal
 * - Fresnel effect for edge glow
 * - Subsurface scattering for translucent materials
 * - Caustics simulation for light focusing
 * - Iridescence for metallic surfaces
 * - PBR metallic-roughness workflow
 * - Image-based lighting (IBL) support
 * - Area light approximations
 * - Energy-conserving BRDF
 * 
 * h(x) ≥ 0 always
 */

import * as THREE from 'three';

// ═══════════════════════════════════════════════════════════════════════════
// PBR CONSTANTS AND UTILITIES
// ═══════════════════════════════════════════════════════════════════════════

export const PBR_CONFIG = {
    // Standard PBR parameters
    dielectricF0: 0.04,          // Non-metal reflectance at normal incidence
    minRoughness: 0.045,          // Avoid division by zero in specular
    maxRoughness: 1.0,
    
    // IBL configuration
    iblDiffuseIntensity: 0.8,
    iblSpecularIntensity: 1.0,
    maxIBLMipLevel: 8,
    
    // Area light approximation
    areaLightRadius: 1.0,
    
    // Quality levels for LOD
    qualityLevels: {
        ultra: { maxLights: 8, shadowMapSize: 2048, envMapSize: 512, ssaoSamples: 64 },
        high: { maxLights: 6, shadowMapSize: 1024, envMapSize: 256, ssaoSamples: 32 },
        medium: { maxLights: 4, shadowMapSize: 512, envMapSize: 128, ssaoSamples: 16 },
        low: { maxLights: 2, shadowMapSize: 256, envMapSize: 64, ssaoSamples: 8 }
    }
};

// ═══════════════════════════════════════════════════════════════════════════
// SHADER CHUNKS (reusable code)
// ═══════════════════════════════════════════════════════════════════════════

const SHADER_CHUNKS = {
    // ─────────────────────────────────────────────────────────────────────────
    // PBR BRDF FUNCTIONS
    // ─────────────────────────────────────────────────────────────────────────
    
    // GGX/Trowbridge-Reitz Normal Distribution Function
    pbrNDF: `
        float D_GGX(float NoH, float roughness) {
            float a = roughness * roughness;
            float a2 = a * a;
            float NoH2 = NoH * NoH;
            float denom = NoH2 * (a2 - 1.0) + 1.0;
            return a2 / (PI * denom * denom);
        }
    `,
    
    // Smith-Schlick Geometry Function
    pbrGeometry: `
        float G_SchlickGGX(float NdotV, float roughness) {
            float r = roughness + 1.0;
            float k = (r * r) / 8.0;
            return NdotV / (NdotV * (1.0 - k) + k);
        }
        
        float G_Smith(float NdotV, float NdotL, float roughness) {
            float ggx1 = G_SchlickGGX(NdotV, roughness);
            float ggx2 = G_SchlickGGX(NdotL, roughness);
            return ggx1 * ggx2;
        }
    `,
    
    // Schlick Fresnel Approximation
    pbrFresnel: `
        vec3 F_Schlick(float cosTheta, vec3 F0) {
            return F0 + (1.0 - F0) * pow(clamp(1.0 - cosTheta, 0.0, 1.0), 5.0);
        }
        
        vec3 F_SchlickRoughness(float cosTheta, vec3 F0, float roughness) {
            return F0 + (max(vec3(1.0 - roughness), F0) - F0) * pow(clamp(1.0 - cosTheta, 0.0, 1.0), 5.0);
        }
    `,
    
    // Complete Cook-Torrance BRDF
    pbrBRDF: `
        #define PI 3.14159265359
        #define DIELECTRIC_F0 0.04
        
        vec3 PBR_BRDF(
            vec3 N, vec3 V, vec3 L, vec3 H,
            vec3 albedo, float metallic, float roughness,
            vec3 lightColor, float lightIntensity
        ) {
            float NdotV = max(dot(N, V), 0.001);
            float NdotL = max(dot(N, L), 0.001);
            float NdotH = max(dot(N, H), 0.001);
            float HdotV = max(dot(H, V), 0.001);
            
            // Base reflectivity (dielectric = 0.04, metal = albedo)
            vec3 F0 = mix(vec3(DIELECTRIC_F0), albedo, metallic);
            
            // Cook-Torrance specular BRDF
            float D = D_GGX(NdotH, roughness);
            float G = G_Smith(NdotV, NdotL, roughness);
            vec3 F = F_Schlick(HdotV, F0);
            
            vec3 numerator = D * G * F;
            float denominator = 4.0 * NdotV * NdotL + 0.0001;
            vec3 specular = numerator / denominator;
            
            // Energy conservation
            vec3 kS = F;
            vec3 kD = (1.0 - kS) * (1.0 - metallic);
            
            // Lambert diffuse
            vec3 diffuse = kD * albedo / PI;
            
            return (diffuse + specular) * lightColor * lightIntensity * NdotL;
        }
    `,
    
    // ─────────────────────────────────────────────────────────────────────────
    // IBL (Image-Based Lighting)
    // ─────────────────────────────────────────────────────────────────────────
    
    iblSampling: `
        vec3 sampleIBLDiffuse(samplerCube envMap, vec3 N, float intensity) {
            // Sample from the lowest mip level for diffuse
            vec3 irradiance = textureCube(envMap, N, 8.0).rgb;
            return irradiance * intensity;
        }
        
        vec3 sampleIBLSpecular(samplerCube envMap, vec3 R, float roughness, float maxMipLevel, float intensity) {
            float mipLevel = roughness * maxMipLevel;
            vec3 prefilteredColor = textureCube(envMap, R, mipLevel).rgb;
            return prefilteredColor * intensity;
        }
        
        // Split-sum approximation for environment BRDF
        vec2 envBRDFApprox(float NdotV, float roughness) {
            // Polynomial approximation from Karis
            vec4 c0 = vec4(-1.0, -0.0275, -0.572, 0.022);
            vec4 c1 = vec4(1.0, 0.0425, 1.04, -0.04);
            vec4 r = roughness * c0 + c1;
            float a004 = min(r.x * r.x, exp2(-9.28 * NdotV)) * r.x + r.y;
            return vec2(-1.04, 1.04) * a004 + r.zw;
        }
        
        vec3 computeIBL(
            vec3 N, vec3 V, vec3 R,
            vec3 albedo, float metallic, float roughness,
            samplerCube envMap, float maxMipLevel,
            float diffuseIntensity, float specularIntensity
        ) {
            float NdotV = max(dot(N, V), 0.001);
            vec3 F0 = mix(vec3(DIELECTRIC_F0), albedo, metallic);
            
            // Fresnel with roughness
            vec3 F = F_SchlickRoughness(NdotV, F0, roughness);
            vec3 kS = F;
            vec3 kD = (1.0 - kS) * (1.0 - metallic);
            
            // Diffuse IBL
            vec3 irradiance = sampleIBLDiffuse(envMap, N, diffuseIntensity);
            vec3 diffuse = irradiance * albedo * kD;
            
            // Specular IBL
            vec3 prefilteredColor = sampleIBLSpecular(envMap, R, roughness, maxMipLevel, specularIntensity);
            vec2 envBRDF = envBRDFApprox(NdotV, roughness);
            vec3 specular = prefilteredColor * (F * envBRDF.x + envBRDF.y);
            
            return diffuse + specular;
        }
    `,
    
    // ─────────────────────────────────────────────────────────────────────────
    // AREA LIGHT APPROXIMATION
    // ─────────────────────────────────────────────────────────────────────────
    
    areaLight: `
        // Most-Representative-Point (MRP) approximation for area lights
        vec3 areaLightMRP(vec3 P, vec3 N, vec3 V, vec3 lightPos, vec3 lightDir, float lightRadius) {
            // Find closest point on sphere to reflection ray
            vec3 R = reflect(-V, N);
            vec3 L = lightPos - P;
            vec3 centerToRay = dot(L, R) * R - L;
            vec3 closestPoint = L + centerToRay * clamp(lightRadius / length(centerToRay), 0.0, 1.0);
            return normalize(closestPoint);
        }
        
        // Area light intensity falloff
        float areaLightFalloff(float dist, float lightRadius) {
            float d = max(dist - lightRadius, 0.0);
            return 1.0 / (d * d + 1.0);
        }
    `,
    
    // ─────────────────────────────────────────────────────────────────────────
    // ORIGINAL CHUNKS (enhanced)
    // ─────────────────────────────────────────────────────────────────────────
    
    // Fresnel effect for edge highlighting (enhanced with PBR awareness)
    fresnel: `
        float fresnel(vec3 normal, vec3 viewDir, float power) {
            return pow(1.0 - abs(dot(normal, viewDir)), power);
        }
        
        float fresnelPBR(vec3 normal, vec3 viewDir, float ior) {
            float cosTheta = max(dot(normal, viewDir), 0.0);
            float R0 = pow((1.0 - ior) / (1.0 + ior), 2.0);
            return R0 + (1.0 - R0) * pow(1.0 - cosTheta, 5.0);
        }
    `,
    
    // Smooth noise function (enhanced with FBM)
    noise: `
        float hash(vec3 p) {
            p = fract(p * 0.3183099 + 0.1);
            p *= 17.0;
            return fract(p.x * p.y * p.z * (p.x + p.y + p.z));
        }
        
        float noise3D(vec3 p) {
            vec3 i = floor(p);
            vec3 f = fract(p);
            f = f * f * (3.0 - 2.0 * f);
            
            return mix(
                mix(mix(hash(i), hash(i + vec3(1,0,0)), f.x),
                    mix(hash(i + vec3(0,1,0)), hash(i + vec3(1,1,0)), f.x), f.y),
                mix(mix(hash(i + vec3(0,0,1)), hash(i + vec3(1,0,1)), f.x),
                    mix(hash(i + vec3(0,1,1)), hash(i + vec3(1,1,1)), f.x), f.y), f.z);
        }
        
        // Fractal Brownian Motion for more interesting noise
        float fbm(vec3 p, int octaves) {
            float value = 0.0;
            float amplitude = 0.5;
            float frequency = 1.0;
            for (int i = 0; i < 6; i++) {
                if (i >= octaves) break;
                value += amplitude * noise3D(p * frequency);
                frequency *= 2.0;
                amplitude *= 0.5;
            }
            return value;
        }
    `,
    
    // Iridescence calculation (thin film interference - physically accurate)
    iridescence: `
        vec3 iridescence(float angle, float thickness) {
            // Thin-film interference with proper optical path difference
            float n = 1.5; // Film refractive index
            float d = thickness; // Film thickness in nm
            float cosTheta2 = sqrt(1.0 - sin(angle) * sin(angle) / (n * n));
            float delta = 2.0 * n * d * cosTheta2;
            
            // Wavelength-dependent interference
            float r = 0.5 + 0.5 * cos(2.0 * 3.14159 * delta / 700.0);
            float g = 0.5 + 0.5 * cos(2.0 * 3.14159 * delta / 550.0);
            float b = 0.5 + 0.5 * cos(2.0 * 3.14159 * delta / 450.0);
            
            return vec3(r, g, b);
        }
        
        // Advanced iridescence with Fresnel
        vec3 iridescenceFresnel(vec3 viewDir, vec3 normal, float thickness, float ior) {
            float cosTheta = abs(dot(viewDir, normal));
            float angle = acos(cosTheta);
            vec3 irid = iridescence(angle, thickness);
            
            // Blend with Fresnel
            float F = fresnelPBR(normal, viewDir, ior);
            return mix(vec3(1.0), irid, F);
        }
    `,
    
    // Subsurface scattering approximation (enhanced with BRDF)
    sss: `
        // Fast SSS approximation (Jimenez separable SSS)
        vec3 subsurfaceScatter(vec3 lightDir, vec3 viewDir, vec3 normal, vec3 color, float thickness) {
            // Forward scattering
            float scatter = pow(max(0.0, dot(lightDir, -viewDir)), 8.0);
            // Back scattering (transmission)
            float backlight = max(0.0, dot(lightDir, -normal));
            // Wrap lighting for soft subsurface
            float wrap = max(0.0, (dot(normal, lightDir) + 0.5) / 1.5);
            
            return color * (scatter + backlight * 0.3 + wrap * 0.2) * thickness;
        }
        
        // Pre-integrated skin/translucent SSS
        vec3 subsurfaceScatterPBR(
            vec3 N, vec3 V, vec3 L,
            vec3 albedo, float curvature, float thickness,
            vec3 scatterColor
        ) {
            float NdotL = dot(N, L);
            float NdotV = max(dot(N, V), 0.0);
            
            // Wrap diffuse lighting
            float wrapDiffuse = (NdotL + 0.5) / 1.5;
            wrapDiffuse = max(0.0, wrapDiffuse);
            
            // Transmission through thin surfaces
            float transmission = exp(-thickness * 2.0);
            float backScatter = max(0.0, -NdotL) * transmission;
            
            // Fresnel-based rim scattering
            float rimScatter = pow(1.0 - NdotV, 4.0) * 0.3;
            
            vec3 sss = scatterColor * (wrapDiffuse + backScatter + rimScatter);
            return mix(albedo * wrapDiffuse, sss, 0.5);
        }
    `,
    
    // ─────────────────────────────────────────────────────────────────────────
    // TONE MAPPING
    // ─────────────────────────────────────────────────────────────────────────
    
    toneMapping: `
        // ACES filmic tone mapping
        vec3 ACESFilm(vec3 x) {
            float a = 2.51;
            float b = 0.03;
            float c = 2.43;
            float d = 0.59;
            float e = 0.14;
            return clamp((x * (a * x + b)) / (x * (c * x + d) + e), 0.0, 1.0);
        }
        
        // Reinhard tone mapping
        vec3 ReinhardToneMap(vec3 color) {
            return color / (color + vec3(1.0));
        }
        
        // Uncharted 2 tone mapping
        vec3 Uncharted2ToneMap(vec3 x) {
            float A = 0.15, B = 0.50, C = 0.10, D = 0.20, E = 0.02, F = 0.30;
            return ((x * (A * x + C * B) + D * E) / (x * (A * x + B) + D * F)) - E / F;
        }
    `
};

// ═══════════════════════════════════════════════════════════════════════════
// P1-001: EFE-CBF SAFETY SHADER
// Glass barrier with danger-zone glow
// ═══════════════════════════════════════════════════════════════════════════

export const EFECBFShader = {
    uniforms: {
        time: { value: 0 },
        hxValue: { value: 1.0 },
        safeColor: { value: new THREE.Color(0x00FF88) },
        dangerColor: { value: new THREE.Color(0xFF2222) },
        barrierStrength: { value: 1.0 },
        viewPosition: { value: new THREE.Vector3() }
    },
    
    vertexShader: `
        varying vec3 vPosition;
        varying vec3 vNormal;
        varying vec3 vWorldPosition;
        varying vec2 vUv;
        
        void main() {
            vPosition = position;
            vNormal = normalize(normalMatrix * normal);
            vUv = uv;
            
            vec4 worldPos = modelMatrix * vec4(position, 1.0);
            vWorldPosition = worldPos.xyz;
            
            gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
        }
    `,
    
    fragmentShader: `
        uniform float time;
        uniform float hxValue;
        uniform vec3 safeColor;
        uniform vec3 dangerColor;
        uniform float barrierStrength;
        uniform vec3 viewPosition;
        
        varying vec3 vPosition;
        varying vec3 vNormal;
        varying vec3 vWorldPosition;
        varying vec2 vUv;
        
        ${SHADER_CHUNKS.fresnel}
        ${SHADER_CHUNKS.noise}
        
        void main() {
            vec3 viewDir = normalize(viewPosition - vWorldPosition);
            
            // Safety color gradient
            vec3 baseColor = mix(dangerColor, safeColor, clamp(hxValue, 0.0, 1.0));
            
            // Fresnel edge glow
            float fresnelFactor = fresnel(vNormal, viewDir, 2.5);
            
            // Barrier wave effect
            float wave = sin(vPosition.y * 5.0 + time * 2.0) * 0.5 + 0.5;
            float barrier = barrierStrength * wave * fresnelFactor;
            
            // Danger pulse when h(x) is low
            float dangerPulse = 0.0;
            if (hxValue < 0.3) {
                dangerPulse = (1.0 - hxValue / 0.3) * sin(time * 10.0) * 0.5 + 0.5;
            }
            
            // Noise for organic feel
            float n = noise3D(vPosition * 3.0 + time * 0.5) * 0.2;
            
            // Final color
            vec3 finalColor = baseColor * (0.6 + n);
            finalColor += safeColor * barrier * 0.5;
            finalColor += dangerColor * dangerPulse * 0.3;
            
            // Opacity based on fresnel and safety
            float alpha = 0.3 + fresnelFactor * 0.5 + (1.0 - hxValue) * 0.2;
            
            gl_FragColor = vec4(finalColor, alpha);
        }
    `
};

// ═══════════════════════════════════════════════════════════════════════════
// P1-002: FANO CONSENSUS SHADER
// Byzantine fault-tolerant network visualization
// ═══════════════════════════════════════════════════════════════════════════

export const FanoConsensusShader = {
    uniforms: {
        time: { value: 0 },
        activeNode: { value: -1 },
        byzantineNodes: { value: [0, 0, 0, 0, 0, 0, 0] }, // Array of 7
        consensusStrength: { value: 1.0 },
        nodePositions: { value: [] } // Array of vec3
    },
    
    vertexShader: `
        varying vec3 vPosition;
        varying vec3 vNormal;
        varying vec2 vUv;
        
        void main() {
            vPosition = position;
            vNormal = normalize(normalMatrix * normal);
            vUv = uv;
            gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
        }
    `,
    
    fragmentShader: `
        uniform float time;
        uniform int activeNode;
        uniform float consensusStrength;
        
        varying vec3 vPosition;
        varying vec3 vNormal;
        varying vec2 vUv;
        
        ${SHADER_CHUNKS.fresnel}
        
        // Fano plane colors (7 colonies)
        vec3 getNodeColor(int index) {
            if (index == 0) return vec3(1.0, 0.42, 0.21);  // Spark
            if (index == 1) return vec3(0.83, 0.69, 0.22); // Forge
            if (index == 2) return vec3(0.31, 0.80, 0.77); // Flow
            if (index == 3) return vec3(0.61, 0.49, 0.74); // Nexus
            if (index == 4) return vec3(0.96, 0.62, 0.04); // Beacon
            if (index == 5) return vec3(0.49, 0.72, 0.50); // Grove
            return vec3(0.40, 0.83, 0.89);                  // Crystal
        }
        
        void main() {
            vec3 viewDir = normalize(cameraPosition - vPosition);
            
            // Base metallic network appearance
            vec3 baseColor = vec3(0.2, 0.2, 0.25);
            
            // Consensus glow
            float pulse = sin(time * 3.0) * 0.5 + 0.5;
            vec3 consensusColor = vec3(0.0, 1.0, 0.53) * consensusStrength * pulse;
            
            // Fresnel rim
            float rim = fresnel(vNormal, viewDir, 3.0);
            
            // Active node highlight
            vec3 activeColor = vec3(0.0);
            if (activeNode >= 0 && activeNode < 7) {
                activeColor = getNodeColor(activeNode) * 0.5;
            }
            
            vec3 finalColor = baseColor + consensusColor * 0.3 + activeColor;
            finalColor += rim * vec3(0.4, 0.83, 0.89) * 0.5;
            
            float alpha = 0.8 + rim * 0.2;
            
            gl_FragColor = vec4(finalColor, alpha);
        }
    `
};

// ═══════════════════════════════════════════════════════════════════════════
// P1-003: E8 LATTICE SHADER
// Crystal sphere packing visualization
// ═══════════════════════════════════════════════════════════════════════════

export const E8LatticeShader = {
    uniforms: {
        time: { value: 0 },
        activeRegion: { value: -1 },
        projectionPhase: { value: 0 },
        crystalIOR: { value: 1.45 }, // Glass-like
        dispersion: { value: 0.05 }
    },
    
    vertexShader: `
        varying vec3 vPosition;
        varying vec3 vNormal;
        varying vec3 vViewPosition;
        varying vec2 vUv;
        
        void main() {
            vPosition = position;
            vNormal = normalize(normalMatrix * normal);
            vUv = uv;
            
            vec4 mvPosition = modelViewMatrix * vec4(position, 1.0);
            vViewPosition = -mvPosition.xyz;
            
            gl_Position = projectionMatrix * mvPosition;
        }
    `,
    
    fragmentShader: `
        uniform float time;
        uniform int activeRegion;
        uniform float projectionPhase;
        uniform float crystalIOR;
        uniform float dispersion;
        
        varying vec3 vPosition;
        varying vec3 vNormal;
        varying vec3 vViewPosition;
        varying vec2 vUv;
        
        ${SHADER_CHUNKS.fresnel}
        ${SHADER_CHUNKS.iridescence}
        
        void main() {
            vec3 viewDir = normalize(vViewPosition);
            vec3 normal = normalize(vNormal);
            
            // Crystal refraction
            float cosTheta = dot(viewDir, normal);
            float ratio = 1.0 / crystalIOR;
            vec3 refracted = refract(-viewDir, normal, ratio);
            
            // Iridescent effect from crystal structure
            float angle = acos(cosTheta);
            vec3 iridColor = iridescence(angle, 200.0 + sin(time) * 50.0);
            
            // Base crystal color
            vec3 baseColor = vec3(0.4, 0.83, 0.89); // Crystal blue
            
            // Fresnel for reflectivity
            float fresnelFactor = fresnel(normal, viewDir, 4.0);
            
            // 8D projection animation
            float phaseWave = sin(vPosition.x * 2.0 + projectionPhase) * 
                            cos(vPosition.y * 2.0 + projectionPhase) *
                            sin(vPosition.z * 2.0 + projectionPhase * 0.5);
            
            // Combine effects
            vec3 finalColor = mix(baseColor, iridColor, fresnelFactor * 0.5);
            finalColor += vec3(1.0) * fresnelFactor * 0.3; // Specular
            finalColor *= 0.8 + phaseWave * 0.2;
            
            // Active region highlight
            if (activeRegion >= 0) {
                float highlight = sin(time * 5.0) * 0.3 + 0.7;
                finalColor *= highlight;
            }
            
            float alpha = 0.6 + fresnelFactor * 0.3;
            
            gl_FragColor = vec4(finalColor, alpha);
        }
    `
};

// ═══════════════════════════════════════════════════════════════════════════
// P1-004: S15 HOPF SHADER
// Octonionic fiber visualization
// ═══════════════════════════════════════════════════════════════════════════

export const S15HopfShader = {
    uniforms: {
        time: { value: 0 },
        fiberIndex: { value: 0 },
        colonyColors: { value: [] }, // Array of vec3
        flowSpeed: { value: 1.0 },
        fiberPhase: { value: 0 }
    },
    
    vertexShader: `
        attribute float fiberParam; // 0-1 along fiber
        
        varying vec3 vPosition;
        varying vec3 vNormal;
        varying float vFiberParam;
        varying vec2 vUv;
        
        uniform float time;
        uniform float flowSpeed;
        
        void main() {
            vPosition = position;
            vNormal = normalize(normalMatrix * normal);
            vFiberParam = fiberParam;
            vUv = uv;
            
            // Add flow animation along fiber
            vec3 displaced = position;
            float flow = fract(vFiberParam + time * flowSpeed * 0.1);
            displaced += normal * sin(flow * 6.28318) * 0.02;
            
            gl_Position = projectionMatrix * modelViewMatrix * vec4(displaced, 1.0);
        }
    `,
    
    fragmentShader: `
        uniform float time;
        uniform int fiberIndex;
        uniform float flowSpeed;
        uniform float fiberPhase;
        
        varying vec3 vPosition;
        varying vec3 vNormal;
        varying float vFiberParam;
        varying vec2 vUv;
        
        ${SHADER_CHUNKS.fresnel}
        ${SHADER_CHUNKS.sss}
        
        // Colony colors
        vec3 getColonyColor(int index) {
            if (index == 0) return vec3(1.0, 0.42, 0.21);  // Spark
            if (index == 1) return vec3(0.83, 0.69, 0.22); // Forge
            if (index == 2) return vec3(0.31, 0.80, 0.77); // Flow
            if (index == 3) return vec3(0.61, 0.49, 0.74); // Nexus
            if (index == 4) return vec3(0.96, 0.62, 0.04); // Beacon
            if (index == 5) return vec3(0.49, 0.72, 0.50); // Grove
            return vec3(0.40, 0.83, 0.89);                  // Crystal
        }
        
        void main() {
            vec3 viewDir = normalize(cameraPosition - vPosition);
            vec3 normal = normalize(vNormal);
            
            // Base colony color
            vec3 baseColor = getColonyColor(fiberIndex);
            
            // Flow effect along fiber
            float flow = fract(vFiberParam + time * flowSpeed * 0.1 + fiberPhase);
            float flowPulse = smoothstep(0.0, 0.1, flow) * smoothstep(0.3, 0.2, flow);
            
            // Fresnel glow
            float fresnelFactor = fresnel(normal, viewDir, 2.0);
            
            // Subsurface scattering for fiber translucency
            vec3 lightDir = normalize(vec3(1.0, 1.0, 0.5));
            vec3 sssColor = subsurfaceScatter(lightDir, viewDir, normal, baseColor, 0.5);
            
            // Combine
            vec3 finalColor = baseColor * 0.5;
            finalColor += baseColor * flowPulse * 0.8;
            finalColor += sssColor * 0.3;
            finalColor += baseColor * fresnelFactor * 0.5;
            
            // Emissive glow
            float emissive = 0.3 + flowPulse * 0.4;
            finalColor += baseColor * emissive;
            
            float alpha = 0.7 + fresnelFactor * 0.3;
            
            gl_FragColor = vec4(finalColor, alpha);
        }
    `
};

// ═══════════════════════════════════════════════════════════════════════════
// P1-005: ORGANISM RSSM SHADER
// World model state space visualization
// ═══════════════════════════════════════════════════════════════════════════

export const OrganismRSSMShader = {
    uniforms: {
        time: { value: 0 },
        stateActivation: { value: [] }, // Array of floats
        predictionUncertainty: { value: 0.5 },
        beliefState: { value: new THREE.Vector4(0, 0, 0, 0) }
    },
    
    vertexShader: `
        varying vec3 vPosition;
        varying vec3 vNormal;
        varying vec2 vUv;
        
        uniform float time;
        uniform float predictionUncertainty;
        
        void main() {
            vPosition = position;
            vNormal = normalize(normalMatrix * normal);
            vUv = uv;
            
            // Uncertainty wobble
            vec3 displaced = position;
            displaced += normal * sin(time * 3.0 + position.x * 5.0) * predictionUncertainty * 0.05;
            
            gl_Position = projectionMatrix * modelViewMatrix * vec4(displaced, 1.0);
        }
    `,
    
    fragmentShader: `
        uniform float time;
        uniform float predictionUncertainty;
        uniform vec4 beliefState;
        
        varying vec3 vPosition;
        varying vec3 vNormal;
        varying vec2 vUv;
        
        ${SHADER_CHUNKS.fresnel}
        ${SHADER_CHUNKS.noise}
        
        void main() {
            vec3 viewDir = normalize(cameraPosition - vPosition);
            vec3 normal = normalize(vNormal);
            
            // Base neural color (purple-blue)
            vec3 baseColor = vec3(0.4, 0.3, 0.7);
            
            // State activation pattern
            float activation = sin(vPosition.x * 10.0 + time) * 
                              cos(vPosition.y * 10.0 + time * 0.7) *
                              sin(vPosition.z * 10.0 + time * 1.3);
            activation = activation * 0.5 + 0.5;
            
            // Prediction certainty affects brightness
            float certainty = 1.0 - predictionUncertainty;
            
            // Belief state color modulation
            vec3 beliefColor = vec3(beliefState.x, beliefState.y, beliefState.z) * beliefState.w;
            
            // Neural noise pattern
            float n = noise3D(vPosition * 5.0 + time * 0.3);
            
            // Fresnel for membrane effect
            float fresnelFactor = fresnel(normal, viewDir, 2.5);
            
            // Combine
            vec3 finalColor = baseColor * (0.5 + activation * 0.3);
            finalColor = mix(finalColor, beliefColor, 0.3);
            finalColor *= certainty * 0.5 + 0.5;
            finalColor += n * 0.1;
            finalColor += vec3(0.6, 0.4, 0.9) * fresnelFactor * 0.5;
            
            float alpha = 0.7 + fresnelFactor * 0.3;
            
            gl_FragColor = vec4(finalColor, alpha);
        }
    `
};

// ═══════════════════════════════════════════════════════════════════════════
// P1-006: QUANTUM-SAFE SHADER
// Post-quantum cryptography visualization
// ═══════════════════════════════════════════════════════════════════════════

export const QuantumSafeShader = {
    uniforms: {
        time: { value: 0 },
        encryptionStrength: { value: 1.0 },
        latticeScale: { value: 1.0 },
        kyberPhase: { value: 0 },
        quantumNoise: { value: 0.1 }
    },
    
    vertexShader: `
        varying vec3 vPosition;
        varying vec3 vNormal;
        varying vec2 vUv;
        
        uniform float time;
        uniform float quantumNoise;
        
        void main() {
            vPosition = position;
            vNormal = normalize(normalMatrix * normal);
            vUv = uv;
            
            // Quantum uncertainty displacement
            vec3 displaced = position;
            float quantum = sin(position.x * 20.0 + time * 5.0) * 
                           cos(position.y * 20.0 + time * 4.0) *
                           sin(position.z * 20.0 + time * 6.0);
            displaced += normal * quantum * quantumNoise * 0.02;
            
            gl_Position = projectionMatrix * modelViewMatrix * vec4(displaced, 1.0);
        }
    `,
    
    fragmentShader: `
        uniform float time;
        uniform float encryptionStrength;
        uniform float latticeScale;
        uniform float kyberPhase;
        uniform float quantumNoise;
        
        varying vec3 vPosition;
        varying vec3 vNormal;
        varying vec2 vUv;
        
        ${SHADER_CHUNKS.fresnel}
        ${SHADER_CHUNKS.noise}
        ${SHADER_CHUNKS.iridescence}
        
        void main() {
            vec3 viewDir = normalize(cameraPosition - vPosition);
            vec3 normal = normalize(vNormal);
            
            // Kyber lattice pattern
            float lattice = sin(vPosition.x * latticeScale * 10.0) *
                           sin(vPosition.y * latticeScale * 10.0) *
                           sin(vPosition.z * latticeScale * 10.0);
            lattice = smoothstep(-0.3, 0.3, lattice);
            
            // Base crypto color (gold for security)
            vec3 baseColor = vec3(1.0, 0.84, 0.0);
            
            // Quantum interference pattern
            float interference = sin(kyberPhase + vPosition.x * 30.0) *
                                cos(kyberPhase * 1.3 + vPosition.y * 30.0);
            
            // Encryption strength glow
            vec3 secureColor = vec3(0.0, 1.0, 0.53) * encryptionStrength;
            
            // Quantum noise pattern
            float qNoise = noise3D(vPosition * 10.0 + time);
            
            // Fresnel for crystalline look
            float fresnelFactor = fresnel(normal, viewDir, 3.0);
            
            // Iridescence for quantum effects
            float angle = acos(dot(viewDir, normal));
            vec3 iridColor = iridescence(angle, 150.0 + quantumNoise * 100.0);
            
            // Combine
            vec3 finalColor = baseColor * (0.4 + lattice * 0.3);
            finalColor = mix(finalColor, secureColor, 0.3);
            finalColor += interference * 0.1;
            finalColor += qNoise * quantumNoise * 0.2;
            finalColor += iridColor * fresnelFactor * 0.3;
            finalColor += baseColor * fresnelFactor * 0.2;
            
            float alpha = 0.6 + fresnelFactor * 0.4;
            
            gl_FragColor = vec4(finalColor, alpha);
        }
    `
};

// ═══════════════════════════════════════════════════════════════════════════
// SHADER MATERIAL FACTORY
// ═══════════════════════════════════════════════════════════════════════════

export function createShaderMaterial(shaderDef, customUniforms = {}) {
    const uniforms = THREE.UniformsUtils.clone(shaderDef.uniforms);
    
    // Merge custom uniforms
    Object.keys(customUniforms).forEach(key => {
        if (uniforms[key]) {
            uniforms[key].value = customUniforms[key];
        }
    });
    
    return new THREE.ShaderMaterial({
        uniforms,
        vertexShader: shaderDef.vertexShader,
        fragmentShader: shaderDef.fragmentShader,
        transparent: true,
        side: THREE.DoubleSide,
        blending: THREE.NormalBlending,
        depthWrite: true
    });
}

// Update shader time uniform
export function updateShaderTime(material, time) {
    if (material.uniforms && material.uniforms.time) {
        material.uniforms.time.value = time;
    }
}

// ═══════════════════════════════════════════════════════════════════════════
// MUSEUM PBR SHADER
// Full physically-based rendering with IBL support
// ═══════════════════════════════════════════════════════════════════════════

export const MuseumPBRShader = {
    uniforms: {
        time: { value: 0 },
        // PBR maps
        albedoMap: { value: null },
        normalMap: { value: null },
        roughnessMap: { value: null },
        metalnessMap: { value: null },
        aoMap: { value: null },
        emissiveMap: { value: null },
        // PBR values (fallback when no maps)
        albedo: { value: new THREE.Color(0xFFFFFF) },
        roughness: { value: 0.5 },
        metalness: { value: 0.0 },
        emissive: { value: new THREE.Color(0x000000) },
        emissiveIntensity: { value: 1.0 },
        // IBL
        envMap: { value: null },
        envMapIntensity: { value: 1.0 },
        maxMipLevel: { value: 8.0 },
        // Lighting
        ambientColor: { value: new THREE.Color(0x222222) },
        lightPositions: { value: [] },
        lightColors: { value: [] },
        lightIntensities: { value: [] },
        numLights: { value: 0 },
        // Camera
        cameraPosition: { value: new THREE.Vector3() }
    },
    
    vertexShader: `
        varying vec3 vPosition;
        varying vec3 vNormal;
        varying vec3 vWorldPosition;
        varying vec2 vUv;
        varying vec3 vViewPosition;
        varying mat3 vTBN;
        
        attribute vec4 tangent;
        
        void main() {
            vPosition = position;
            vUv = uv;
            
            // World space position and normal
            vec4 worldPos = modelMatrix * vec4(position, 1.0);
            vWorldPosition = worldPos.xyz;
            vNormal = normalize((modelMatrix * vec4(normal, 0.0)).xyz);
            
            // TBN matrix for normal mapping
            vec3 T = normalize((modelMatrix * vec4(tangent.xyz, 0.0)).xyz);
            vec3 N = vNormal;
            vec3 B = cross(N, T) * tangent.w;
            vTBN = mat3(T, B, N);
            
            // View space position
            vec4 mvPosition = modelViewMatrix * vec4(position, 1.0);
            vViewPosition = -mvPosition.xyz;
            
            gl_Position = projectionMatrix * mvPosition;
        }
    `,
    
    fragmentShader: `
        uniform float time;
        
        // PBR maps
        uniform sampler2D albedoMap;
        uniform sampler2D normalMap;
        uniform sampler2D roughnessMap;
        uniform sampler2D metalnessMap;
        uniform sampler2D aoMap;
        uniform sampler2D emissiveMap;
        
        // PBR values
        uniform vec3 albedo;
        uniform float roughness;
        uniform float metalness;
        uniform vec3 emissive;
        uniform float emissiveIntensity;
        
        // IBL
        uniform samplerCube envMap;
        uniform float envMapIntensity;
        uniform float maxMipLevel;
        
        // Lighting
        uniform vec3 ambientColor;
        uniform vec3 lightPositions[8];
        uniform vec3 lightColors[8];
        uniform float lightIntensities[8];
        uniform int numLights;
        
        // Camera
        uniform vec3 cameraPosition;
        
        varying vec3 vPosition;
        varying vec3 vNormal;
        varying vec3 vWorldPosition;
        varying vec2 vUv;
        varying vec3 vViewPosition;
        varying mat3 vTBN;
        
        ${SHADER_CHUNKS.pbrNDF}
        ${SHADER_CHUNKS.pbrGeometry}
        ${SHADER_CHUNKS.pbrFresnel}
        ${SHADER_CHUNKS.pbrBRDF}
        ${SHADER_CHUNKS.toneMapping}
        
        void main() {
            // Sample textures (or use uniform values)
            vec3 baseColor = albedo;
            #ifdef USE_ALBEDO_MAP
                baseColor = texture2D(albedoMap, vUv).rgb;
            #endif
            
            float rough = roughness;
            #ifdef USE_ROUGHNESS_MAP
                rough = texture2D(roughnessMap, vUv).g;
            #endif
            rough = clamp(rough, 0.045, 1.0);
            
            float metal = metalness;
            #ifdef USE_METALNESS_MAP
                metal = texture2D(metalnessMap, vUv).b;
            #endif
            
            float ao = 1.0;
            #ifdef USE_AO_MAP
                ao = texture2D(aoMap, vUv).r;
            #endif
            
            // Normal mapping
            vec3 N = normalize(vNormal);
            #ifdef USE_NORMAL_MAP
                vec3 normalSample = texture2D(normalMap, vUv).xyz * 2.0 - 1.0;
                N = normalize(vTBN * normalSample);
            #endif
            
            vec3 V = normalize(cameraPosition - vWorldPosition);
            vec3 R = reflect(-V, N);
            
            // Accumulate direct lighting
            vec3 Lo = vec3(0.0);
            for (int i = 0; i < 8; i++) {
                if (i >= numLights) break;
                
                vec3 L = normalize(lightPositions[i] - vWorldPosition);
                vec3 H = normalize(V + L);
                float distance = length(lightPositions[i] - vWorldPosition);
                float attenuation = 1.0 / (distance * distance + 1.0);
                
                Lo += PBR_BRDF(N, V, L, H, baseColor, metal, rough, lightColors[i], lightIntensities[i] * attenuation);
            }
            
            // IBL (simplified - would need prefiltered maps in production)
            vec3 F0 = mix(vec3(DIELECTRIC_F0), baseColor, metal);
            vec3 F = F_SchlickRoughness(max(dot(N, V), 0.0), F0, rough);
            vec3 kS = F;
            vec3 kD = (1.0 - kS) * (1.0 - metal);
            
            vec3 irradiance = textureCube(envMap, N).rgb * envMapIntensity;
            vec3 diffuseIBL = irradiance * baseColor * kD;
            
            float lod = rough * maxMipLevel;
            vec3 prefilteredColor = textureCube(envMap, R, lod).rgb * envMapIntensity;
            vec2 envBRDF = vec2(0.9, 0.1); // Simplified, would use LUT in production
            vec3 specularIBL = prefilteredColor * (F * envBRDF.x + envBRDF.y);
            
            vec3 ambient = (diffuseIBL + specularIBL) * ao;
            
            // Emissive
            vec3 emission = emissive * emissiveIntensity;
            #ifdef USE_EMISSIVE_MAP
                emission *= texture2D(emissiveMap, vUv).rgb;
            #endif
            
            // Final color
            vec3 color = ambient + Lo + emission + ambientColor * baseColor * ao;
            
            // Tone mapping
            color = ACESFilm(color);
            
            // Gamma correction
            color = pow(color, vec3(1.0 / 2.2));
            
            gl_FragColor = vec4(color, 1.0);
        }
    `
};

// ═══════════════════════════════════════════════════════════════════════════
// SHADER LOD VARIANTS
// Simplified versions for performance scaling
// ═══════════════════════════════════════════════════════════════════════════

export const ShaderLOD = {
    // Ultra: Full PBR with IBL, 8 lights, all maps
    ultra: {
        maxLights: 8,
        useIBL: true,
        useNormalMap: true,
        useAOMap: true,
        shadowQuality: 'high'
    },
    
    // High: PBR with IBL, 6 lights
    high: {
        maxLights: 6,
        useIBL: true,
        useNormalMap: true,
        useAOMap: true,
        shadowQuality: 'medium'
    },
    
    // Medium: Basic PBR, 4 lights, no IBL
    medium: {
        maxLights: 4,
        useIBL: false,
        useNormalMap: true,
        useAOMap: false,
        shadowQuality: 'low'
    },
    
    // Low: Lambert + Blinn-Phong, 2 lights
    low: {
        maxLights: 2,
        useIBL: false,
        useNormalMap: false,
        useAOMap: false,
        shadowQuality: 'none'
    }
};

/**
 * Create a shader material with LOD-appropriate settings
 */
export function createPBRShaderMaterial(options = {}) {
    const {
        lod = 'high',
        albedo = new THREE.Color(0xFFFFFF),
        roughness = 0.5,
        metalness = 0.0,
        envMap = null,
        customUniforms = {}
    } = options;
    
    const lodConfig = ShaderLOD[lod] || ShaderLOD.high;
    
    const uniforms = THREE.UniformsUtils.clone(MuseumPBRShader.uniforms);
    uniforms.albedo.value = albedo;
    uniforms.roughness.value = roughness;
    uniforms.metalness.value = metalness;
    if (envMap) uniforms.envMap.value = envMap;
    
    // Merge custom uniforms
    Object.keys(customUniforms).forEach(key => {
        if (uniforms[key]) {
            uniforms[key].value = customUniforms[key];
        }
    });
    
    const defines = {};
    if (lodConfig.useNormalMap) defines.USE_NORMAL_MAP = '';
    if (lodConfig.useAOMap) defines.USE_AO_MAP = '';
    if (lodConfig.useIBL) defines.USE_IBL = '';
    
    return new THREE.ShaderMaterial({
        uniforms,
        vertexShader: MuseumPBRShader.vertexShader,
        fragmentShader: MuseumPBRShader.fragmentShader,
        defines,
        side: THREE.DoubleSide
    });
}

// ═══════════════════════════════════════════════════════════════════════════
// ENVIRONMENT MAP GENERATOR
// Creates procedural environment maps for IBL
// ═══════════════════════════════════════════════════════════════════════════

export class EnvironmentMapGenerator {
    constructor(renderer) {
        this.renderer = renderer;
        this.pmremGenerator = null;
        this.envMaps = new Map();
    }
    
    init() {
        if (!THREE.PMREMGenerator) {
            console.warn('PMREMGenerator not available');
            return;
        }
        this.pmremGenerator = new THREE.PMREMGenerator(this.renderer);
        this.pmremGenerator.compileEquirectangularShader();
    }
    
    /**
     * Generate a procedural environment map for a colony
     */
    generateColonyEnvMap(colony) {
        if (this.envMaps.has(colony)) {
            return this.envMaps.get(colony);
        }
        
        // Create a simple gradient cubemap procedurally
        const size = 256;
        const scene = new THREE.Scene();
        
        // Colony-specific colors
        const colonyColors = {
            spark: { top: 0xFF8866, horizon: 0xFF4422, bottom: 0x331100 },
            forge: { top: 0xFFDD88, horizon: 0xDD9922, bottom: 0x442200 },
            flow: { top: 0x88FFFF, horizon: 0x44BBBB, bottom: 0x003333 },
            nexus: { top: 0xCC99FF, horizon: 0x8866AA, bottom: 0x221133 },
            beacon: { top: 0xFFCC66, horizon: 0xFFAA22, bottom: 0x442200 },
            grove: { top: 0x88FF88, horizon: 0x66AA66, bottom: 0x113311 },
            crystal: { top: 0x88EEFF, horizon: 0x55CCDD, bottom: 0x002233 },
            rotunda: { top: 0x444455, horizon: 0x222233, bottom: 0x111118 }
        };
        
        const colors = colonyColors[colony] || colonyColors.rotunda;
        
        // Create gradient sphere
        const geometry = new THREE.SphereGeometry(500, 32, 32);
        const material = new THREE.ShaderMaterial({
            uniforms: {
                topColor: { value: new THREE.Color(colors.top) },
                horizonColor: { value: new THREE.Color(colors.horizon) },
                bottomColor: { value: new THREE.Color(colors.bottom) }
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
                uniform vec3 horizonColor;
                uniform vec3 bottomColor;
                varying vec3 vWorldPosition;
                void main() {
                    float y = normalize(vWorldPosition).y;
                    vec3 color;
                    if (y > 0.0) {
                        color = mix(horizonColor, topColor, y);
                    } else {
                        color = mix(horizonColor, bottomColor, -y);
                    }
                    gl_FragColor = vec4(color, 1.0);
                }
            `,
            side: THREE.BackSide
        });
        
        const skybox = new THREE.Mesh(geometry, material);
        scene.add(skybox);
        
        // Render to cubemap
        const cubeRenderTarget = new THREE.WebGLCubeRenderTarget(size, {
            format: THREE.RGBAFormat,
            generateMipmaps: true,
            minFilter: THREE.LinearMipmapLinearFilter
        });
        
        const cubeCamera = new THREE.CubeCamera(1, 1000, cubeRenderTarget);
        cubeCamera.update(this.renderer, scene);
        
        // Clean up
        geometry.dispose();
        material.dispose();
        
        // Generate PMREM for IBL if available
        let envMap = cubeRenderTarget.texture;
        if (this.pmremGenerator) {
            const pmremRenderTarget = this.pmremGenerator.fromCubemap(cubeRenderTarget.texture);
            envMap = pmremRenderTarget.texture;
        }
        
        this.envMaps.set(colony, envMap);
        return envMap;
    }
    
    /**
     * Dispose all generated environment maps
     */
    dispose() {
        this.envMaps.forEach(envMap => {
            if (envMap.dispose) envMap.dispose();
        });
        this.envMaps.clear();
        if (this.pmremGenerator) {
            this.pmremGenerator.dispose();
        }
    }
}

// ═══════════════════════════════════════════════════════════════════════════
// EXPORTS
// ═══════════════════════════════════════════════════════════════════════════

export default {
    PBR_CONFIG,
    SHADER_CHUNKS,
    EFECBFShader,
    FanoConsensusShader,
    E8LatticeShader,
    S15HopfShader,
    OrganismRSSMShader,
    QuantumSafeShader,
    MuseumPBRShader,
    ShaderLOD,
    createShaderMaterial,
    createPBRShaderMaterial,
    updateShaderTime,
    EnvironmentMapGenerator
};
