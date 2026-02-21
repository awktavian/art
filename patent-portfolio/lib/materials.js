/**
 * Museum-Quality Materials Library
 * =================================
 * 
 * AAA-grade physically-based materials for the Patent Museum.
 * All materials optimized for:
 * - Visual quality (Full PBR, clearcoat, iridescence, sheen)
 * - Performance (LOD, instancing, texture atlasing)
 * - Consistency across the museum
 * - IBL (Image-Based Lighting) support
 * - Energy-conserving BRDF
 * 
 * h(x) ≥ 0 always
 */

import * as THREE from 'three';

// ═══════════════════════════════════════════════════════════════════════════
// MATERIAL QUALITY SETTINGS
// ═══════════════════════════════════════════════════════════════════════════

export const MATERIAL_QUALITY = {
    ultra: {
        anisotropy: 16,
        normalMapType: THREE.TangentSpaceNormalMap,
        envMapIntensity: 1.5,
        clearcoat: true,
        iridescence: true,
        sheen: true,
        transmission: true,
        shadowSide: THREE.FrontSide
    },
    high: {
        anisotropy: 8,
        normalMapType: THREE.TangentSpaceNormalMap,
        envMapIntensity: 1.2,
        clearcoat: true,
        iridescence: true,
        sheen: true,
        transmission: true,
        shadowSide: THREE.FrontSide
    },
    medium: {
        anisotropy: 4,
        normalMapType: THREE.TangentSpaceNormalMap,
        envMapIntensity: 0.9,
        clearcoat: true,
        iridescence: false,
        sheen: false,
        transmission: true,
        shadowSide: THREE.FrontSide
    },
    low: {
        anisotropy: 1,
        normalMapType: THREE.ObjectSpaceNormalMap,
        envMapIntensity: 0.6,
        clearcoat: false,
        iridescence: false,
        sheen: false,
        transmission: false,
        shadowSide: THREE.BackSide
    }
};

let currentQuality = MATERIAL_QUALITY.high;

export function setMaterialQuality(level) {
    currentQuality = MATERIAL_QUALITY[level] || MATERIAL_QUALITY.high;
}

export function getMaterialQuality() {
    return currentQuality;
}

// ═══════════════════════════════════════════════════════════════════════════
// COLONY COLORS
// ═══════════════════════════════════════════════════════════════════════════

export const COLONY_COLORS = {
    spark:   0xFF6B35,
    forge:   0xD4AF37,
    flow:    0x4ECDC4,
    nexus:   0x9B7EBD,
    beacon:  0xF59E0B,
    grove:   0x7EB77F,
    crystal: 0x67D4E4
};

export const COLONY_ORDER = ['spark', 'forge', 'flow', 'nexus', 'beacon', 'grove', 'crystal'];

// ═══════════════════════════════════════════════════════════════════════════
// ENVIRONMENT MAP MANAGEMENT (Film-Quality IBL)
// ═══════════════════════════════════════════════════════════════════════════

let globalEnvMap = null;
let pmremGenerator = null;
const colonyEnvMaps = new Map();

export function setGlobalEnvMap(envMap) {
    globalEnvMap = envMap;
}

export function getGlobalEnvMap() {
    return globalEnvMap;
}

export function setColonyEnvMap(colony, envMap) {
    colonyEnvMaps.set(colony, envMap);
}

export function getColonyEnvMap(colony) {
    return colonyEnvMaps.get(colony) || globalEnvMap;
}

/**
 * Initialize PMREM Generator for environment map processing
 * Must be called after renderer is created
 */
export function initPMREMGenerator(renderer) {
    pmremGenerator = new THREE.PMREMGenerator(renderer);
    pmremGenerator.compileEquirectangularShader();
    return pmremGenerator;
}

/**
 * Create a procedural museum environment map for reflections
 * This creates a sophisticated dark museum HDR-like environment
 */
export function createMuseumEnvironmentMap(renderer, scene) {
    if (!pmremGenerator) {
        pmremGenerator = new THREE.PMREMGenerator(renderer);
        pmremGenerator.compileEquirectangularShader();
    }
    
    // Create a render target cube for capturing the environment
    const cubeRenderTarget = new THREE.WebGLCubeRenderTarget(256, {
        format: THREE.RGBAFormat,
        generateMipmaps: true,
        minFilter: THREE.LinearMipmapLinearFilter
    });
    
    // Create a cube camera to capture the environment
    const cubeCamera = new THREE.CubeCamera(0.1, 1000, cubeRenderTarget);
    
    // Position at rotunda center for best overall reflections
    cubeCamera.position.set(0, 5, 0);
    
    // Capture the scene
    cubeCamera.update(renderer, scene);
    
    // Process through PMREM for PBR-compatible reflections
    const envMap = pmremGenerator.fromCubemap(cubeRenderTarget.texture).texture;
    
    // Store globally
    globalEnvMap = envMap;
    
    // Clean up
    cubeRenderTarget.dispose();
    
    return envMap;
}

/**
 * Create a simpler procedural gradient environment map
 * More performant, good for stylized look
 */
export function createGradientEnvironmentMap(renderer) {
    if (!pmremGenerator) {
        pmremGenerator = new THREE.PMREMGenerator(renderer);
        pmremGenerator.compileEquirectangularShader();
    }
    
    // Create gradient scene
    const envScene = new THREE.Scene();
    
    // Create a large sphere with gradient material for HDR-like environment
    const envGeo = new THREE.SphereGeometry(500, 64, 32);
    
    // Create shader for museum-like environment gradient
    const envMat = new THREE.ShaderMaterial({
        side: THREE.BackSide,
        depthWrite: false,
        uniforms: {
            topColor: { value: new THREE.Color(0x8882A0) },
            horizonColor: { value: new THREE.Color(0xA09AB0) },
            bottomColor: { value: new THREE.Color(0x706880) },
            rimColor: { value: new THREE.Color(0x67D4E4) },
            rimIntensity: { value: 1.0 },
            warmColor: { value: new THREE.Color(0xFFE4C4) },
            warmIntensity: { value: 0.15 }
        },
        vertexShader: `
            varying vec3 vWorldPosition;
            varying vec3 vNormal;
            void main() {
                vec4 worldPosition = modelMatrix * vec4(position, 1.0);
                vWorldPosition = worldPosition.xyz;
                vNormal = normalize(normalMatrix * normal);
                gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
            }
        `,
        fragmentShader: `
            uniform vec3 topColor;
            uniform vec3 horizonColor;
            uniform vec3 bottomColor;
            uniform vec3 rimColor;
            uniform float rimIntensity;
            uniform vec3 warmColor;
            uniform float warmIntensity;
            
            varying vec3 vWorldPosition;
            varying vec3 vNormal;
            
            void main() {
                float y = normalize(vWorldPosition).y;
                
                vec3 color;
                if (y > 0.0) {
                    color = mix(horizonColor, topColor, pow(y, 0.8));
                } else {
                    color = mix(horizonColor, bottomColor, pow(-y, 0.5));
                }
                
                float rim = 1.0 - abs(y);
                color += rimColor * rimIntensity * pow(rim, 3.0);
                color += warmColor * warmIntensity * pow(rim, 2.0);
                
                gl_FragColor = vec4(color, 1.0);
            }
        `
    });
    
    const envSphere = new THREE.Mesh(envGeo, envMat);
    envScene.add(envSphere);
    
    // Add subtle accent lights to the environment
    const accentColors = [
        { color: 0xFF6B35, pos: [200, 50, 0] },    // Spark
        { color: 0xD4AF37, pos: [141, 50, 141] },  // Forge
        { color: 0x4ECDC4, pos: [0, 50, 200] },    // Flow
        { color: 0x9B7EBD, pos: [-141, 50, 141] }, // Nexus
        { color: 0xF59E0B, pos: [-200, 50, 0] },   // Beacon
        { color: 0x7EB77F, pos: [-141, 50, -141] }, // Grove
        { color: 0x67D4E4, pos: [0, 50, -200] }    // Crystal
    ];
    
    accentColors.forEach(({ color, pos }) => {
        const lightSphere = new THREE.Mesh(
            new THREE.SphereGeometry(30, 16, 16),
            new THREE.MeshBasicMaterial({ 
                color, 
                transparent: true, 
                opacity: 0.7 
            })
        );
        lightSphere.position.set(...pos);
        envScene.add(lightSphere);
    });
    
    // Render to cube map
    const cubeRenderTarget = new THREE.WebGLCubeRenderTarget(256, {
        format: THREE.RGBAFormat,
        generateMipmaps: true,
        minFilter: THREE.LinearMipmapLinearFilter
    });
    
    const cubeCamera = new THREE.CubeCamera(0.1, 1000, cubeRenderTarget);
    cubeCamera.update(renderer, envScene);
    
    // Process through PMREM
    const envMap = pmremGenerator.fromCubemap(cubeRenderTarget.texture).texture;
    
    // Store globally
    globalEnvMap = envMap;
    
    // Clean up
    envScene.traverse(obj => {
        if (obj.geometry) obj.geometry.dispose();
        if (obj.material) obj.material.dispose();
    });
    cubeRenderTarget.dispose();
    
    console.log('🌍 Museum environment map created');
    
    return envMap;
}

/**
 * Apply environment map to all PBR materials in a scene
 * This is the key function for film-quality reflections
 */
export function applyEnvironmentMapToScene(scene, envMap = null, intensity = 1.0) {
    const map = envMap || globalEnvMap;
    if (!map) {
        console.warn('No environment map available');
        return 0;
    }
    
    let count = 0;
    
    scene.traverse(object => {
        if (object.isMesh && object.material) {
            const materials = Array.isArray(object.material) ? object.material : [object.material];
            
            materials.forEach(material => {
                // Only apply to PBR materials
                if (material.isMeshStandardMaterial || material.isMeshPhysicalMaterial) {
                    material.envMap = map;
                    material.envMapIntensity = intensity * currentQuality.envMapIntensity;
                    material.needsUpdate = true;
                    count++;
                }
            });
        }
    });
    
    console.log(`🌍 Applied environment map to ${count} materials`);
    return count;
}

/**
 * Update environment map intensity based on quality settings
 */
export function updateEnvironmentMapIntensity(scene, intensity) {
    scene.traverse(object => {
        if (object.isMesh && object.material) {
            const materials = Array.isArray(object.material) ? object.material : [object.material];
            
            materials.forEach(material => {
                if (material.envMap && (material.isMeshStandardMaterial || material.isMeshPhysicalMaterial)) {
                    material.envMapIntensity = intensity;
                    material.needsUpdate = true;
                }
            });
        }
    });
}

// ═══════════════════════════════════════════════════════════════════════════
// PROCEDURAL NORMAL MAP (Perlin-like noise for concrete microsurface)
// ═══════════════════════════════════════════════════════════════════════════

function hash2(x, y) {
    const k = 0.3183099;
    const u = x * k + y * (1 - k);
    return (Math.sin(u * 12.9898 + 78.233) * 43758.5453) % 1;
}

function noise2D(x, y) {
    const ix = Math.floor(x), iy = Math.floor(y);
    const fx = x - ix, fy = y - iy;
    const u = fx * fx * (3 - 2 * fx), v = fy * fy * (3 - 2 * fy);
    const a = hash2(ix, iy), b = hash2(ix + 1, iy);
    const c = hash2(ix, iy + 1), d = hash2(ix + 1, iy + 1);
    return (a * (1 - u) + b * u) * (1 - v) + (c * (1 - u) + d * u) * v;
}

/**
 * Generate a procedural normal map for concrete (Perlin-like microsurface detail).
 * @param {number} size - Texture size (e.g. 256)
 * @param {number} scale - Noise frequency (higher = finer detail)
 */
export function createProceduralNormalMap(size = 256, scale = 8) {
    const data = new Uint8Array(size * size * 4);
    const stride = 4;
    for (let y = 0; y < size; y++) {
        for (let x = 0; x < size; x++) {
            const u = (x / size) * scale, v = (y / size) * scale;
            const n = noise2D(u, v);
            const nx = (noise2D(u + 0.01, v) - n) * 4;
            const ny = (noise2D(u, v + 0.01) - n) * 4;
            const nz = Math.sqrt(Math.max(0, 1 - nx * nx - ny * ny));
            const i = (y * size + x) * stride;
            data[i] = (nx * 0.5 + 0.5) * 255;
            data[i + 1] = (ny * 0.5 + 0.5) * 255;
            data[i + 2] = (nz * 0.5 + 0.5) * 255;
            data[i + 3] = 255;
        }
    }
    const tex = new THREE.DataTexture(data, size, size, THREE.RGBAFormat);
    tex.wrapS = tex.wrapT = THREE.RepeatWrapping;
    tex.needsUpdate = true;
    return tex;
}

// ═══════════════════════════════════════════════════════════════════════════
// BASE MATERIALS
// ═══════════════════════════════════════════════════════════════════════════

/**
 * Concrete with procedural normal map. Roughness 0.8 for walls.
 */
export function createConcreteMaterial(options = {}) {
    const {
        color = 0x3D3835,
        roughness = 0.8,
        normalMap = null,
        normalScale = 0.4,
        envMap = globalEnvMap
    } = options;
    const material = new THREE.MeshStandardMaterial({
        color,
        roughness,
        metalness: 0.05,
        envMap,
        envMapIntensity: 0.3,
        side: THREE.DoubleSide  // Visible from both sides (critical for rotunda cylinder)
    });
    const nm = normalMap || createProceduralNormalMap(256, 6);
    material.normalMap = nm;
    material.normalScale = new THREE.Vector2(normalScale, normalScale);
    return material;
}

/**
 * Polished concrete for thresholds (roughness 0.1).
 */
export function createConcretePolishedMaterial(options = {}) {
    return createConcreteMaterial({ ...options, roughness: 0.1, normalScale: 0.2 });
}

/**
 * Premium glass material with refraction
 */
export function createGlassMaterial(options = {}) {
    const {
        color = 0xFFFFFF,
        opacity = 0.3,
        transmission = currentQuality.transmission ? 0.95 : 0,
        thickness = 0.5,
        roughness = 0,
        ior = 1.5,
        envMap = globalEnvMap,
        attenuationColor = null,
        attenuationDistance = Infinity
    } = options;
    
    const material = new THREE.MeshPhysicalMaterial({
        color,
        metalness: 0,
        roughness,
        transmission: currentQuality.transmission ? transmission : 0,
        thickness,
        transparent: true,
        opacity: currentQuality.transmission ? 1.0 : opacity,
        ior,
        envMap,
        envMapIntensity: currentQuality.envMapIntensity
    });
    
    // Attenuation for colored glass
    if (attenuationColor) {
        material.attenuationColor = new THREE.Color(attenuationColor);
        material.attenuationDistance = attenuationDistance;
    }
    
    return material;
}

/**
 * Iridescent crystal material with dispersion (chromatic refraction).
 */
export function createCrystalMaterial(options = {}) {
    const {
        color = 0x67D4E4,
        iridescenceIntensity = 1.0,
        iridescenceIOR = 1.3,
        iridescenceThicknessRange = [100, 400],
        dispersion = 0.1,
        envMap = globalEnvMap
    } = options;

    const material = new THREE.MeshPhysicalMaterial({
        color,
        metalness: 0.1,
        roughness: 0.05,
        transmission: currentQuality.transmission ? 0.7 : 0,
        thickness: 1.0,
        ior: 1.5,
        clearcoat: currentQuality.clearcoat ? 1.0 : 0,
        clearcoatRoughness: 0.1,
        transparent: true,
        opacity: currentQuality.transmission ? 1.0 : 0.9,
        envMap,
        envMapIntensity: currentQuality.envMapIntensity
    });

    if (currentQuality.iridescence) {
        material.iridescence = iridescenceIntensity;
        material.iridescenceIOR = iridescenceIOR;
        material.iridescenceThicknessRange = iridescenceThicknessRange;
    }
    if (typeof material.dispersion !== 'undefined') {
        material.dispersion = dispersion;
    }
    return material;
}

/**
 * Polished metal material (gold/bronze/steel)
 */
export function createMetalMaterial(options = {}) {
    const {
        color = 0xD4AF37,
        roughness = 0.2,
        clearcoat = 0.5,
        anisotropy = 0,
        anisotropyRotation = 0,
        envMap = globalEnvMap
    } = options;
    
    const material = new THREE.MeshPhysicalMaterial({
        color,
        metalness: 0.95,
        roughness,
        clearcoat: currentQuality.clearcoat ? clearcoat : 0,
        clearcoatRoughness: 0.1,
        envMap,
        envMapIntensity: currentQuality.envMapIntensity * 1.2 // Metals reflect more
    });
    
    // Brushed metal anisotropy
    if (anisotropy > 0) {
        material.anisotropy = anisotropy;
        material.anisotropyRotation = anisotropyRotation;
    }
    
    return material;
}

/**
 * Brushed metal / steel with anisotropy for directional highlights.
 */
export function createBrushedMetalMaterial(options = {}) {
    const {
        color = 0xCCCCCC,
        roughness = 0.3,
        direction = 'horizontal',
        anisotropy = 1.0,
        envMap = globalEnvMap
    } = options;

    const anisotropyRotation = direction === 'horizontal' ? 0 :
                              direction === 'vertical' ? Math.PI / 2 : 0;

    return new THREE.MeshPhysicalMaterial({
        color,
        metalness: 0.9,
        roughness,
        anisotropy,
        anisotropyRotation,
        clearcoat: currentQuality.clearcoat ? 0.3 : 0,
        clearcoatRoughness: 0.3,
        envMap,
        envMapIntensity: currentQuality.envMapIntensity * 0.8
    });
}

/** Steel accents (brushed metal). */
export function createBrushedSteelMaterial(options = {}) {
    return createBrushedMetalMaterial({ color: 0xCCCCCC, ...options });
}

/**
 * Glowing emissive material
 */
export function createEmissiveMaterial(options = {}) {
    const {
        color = 0x67D4E4,
        emissiveIntensity = 0.5,
        opacity = 1.0
    } = options;
    
    return new THREE.MeshStandardMaterial({
        color,
        emissive: color,
        emissiveIntensity,
        metalness: 0.2,
        roughness: 0.3,
        transparent: opacity < 1,
        opacity
    });
}

/**
 * Flow pool: water-like surface with dynamic environment map reflection.
 * Call updateFlowPoolEnvMap(material, cubeCamera, renderer) each frame for live reflections.
 */
export function createFlowPoolMaterial(options = {}) {
    const {
        color = 0x4ECDC4,
        roughness = 0.05,
        metalness = 0.1,
        transmission = 0.6,
        thickness = 0.5,
        envMap = globalEnvMap
    } = options;
    const material = new THREE.MeshPhysicalMaterial({
        color,
        metalness,
        roughness,
        transmission,
        thickness,
        transparent: true,
        opacity: 1.0,
        envMap,
        envMapIntensity: 1.0
    });
    material.userData._flowPool = true;
    return material;
}

/**
 * Update Flow pool (or any mesh) with a freshly captured env map from cube camera.
 */
export function updateFlowPoolEnvMap(material, cubeCamera, renderer, pmremGen = null) {
    if (!material || !cubeCamera || !renderer) return;
    const pmrem = pmremGen || pmremGenerator;
    if (!pmrem) return;
    cubeCamera.update(renderer, cubeCamera.parent || new THREE.Scene());
    const envMap = pmrem.fromCubemap(cubeCamera.renderTarget.texture).texture;
    material.envMap = envMap;
    material.needsUpdate = true;
}

/**
 * Museum floor material (polished reflective)
 */
export function createFloorMaterial(options = {}) {
    const {
        color = 0x080810,
        reflectivity = 0.9,
        envMap = globalEnvMap,
        normalMap = null,
        normalScale = 0.5
    } = options;
    
    const material = new THREE.MeshPhysicalMaterial({
        color,
        metalness: 0.6,
        roughness: 0.25,
        clearcoat: currentQuality.clearcoat ? 1.0 : 0,
        clearcoatRoughness: 0.05,
        reflectivity,
        envMap,
        envMapIntensity: currentQuality.envMapIntensity * 0.8
    });
    
    if (normalMap) {
        material.normalMap = normalMap;
        material.normalScale = new THREE.Vector2(normalScale, normalScale);
    }
    
    return material;
}

/**
 * Museum wall material (matte with subtle texture)
 */
export function createWallMaterial(options = {}) {
    const {
        color = 0x12101A,
        roughnessMap = null,
        normalMap = null,
        aoMap = null
    } = options;
    
    const material = new THREE.MeshStandardMaterial({
        color,
        metalness: 0.1,
        roughness: 0.8
    });
    
    if (roughnessMap) material.roughnessMap = roughnessMap;
    if (normalMap) {
        material.normalMap = normalMap;
        material.normalScale = new THREE.Vector2(0.3, 0.3);
    }
    if (aoMap) {
        material.aoMap = aoMap;
        material.aoMapIntensity = 1.0;
    }
    
    return material;
}

/**
 * Velvet/fabric material with sheen
 */
export function createVelvetMaterial(options = {}) {
    const {
        color = 0x220022,
        sheenColor = 0x440044,
        roughness = 0.8
    } = options;
    
    const material = new THREE.MeshPhysicalMaterial({
        color,
        metalness: 0,
        roughness
    });
    
    if (currentQuality.sheen) {
        material.sheen = 1.0;
        material.sheenColor = new THREE.Color(sheenColor);
        material.sheenRoughness = 0.5;
    }
    
    return material;
}

/**
 * Marble material with subsurface scattering
 */
export function createMarbleMaterial(options = {}) {
    const {
        color = 0xF5F5F0,
        veinColor = 0x333333,
        roughness = 0.15,
        envMap = globalEnvMap
    } = options;
    
    // Create procedural marble texture
    const canvas = document.createElement('canvas');
    canvas.width = 512;
    canvas.height = 512;
    const ctx = canvas.getContext('2d');
    
    // Base color
    ctx.fillStyle = '#' + new THREE.Color(color).getHexString();
    ctx.fillRect(0, 0, 512, 512);
    
    // Add veins using noise pattern
    ctx.strokeStyle = '#' + new THREE.Color(veinColor).getHexString();
    ctx.lineWidth = 2;
    ctx.globalAlpha = 0.3;
    
    for (let i = 0; i < 20; i++) {
        ctx.beginPath();
        let x = Math.random() * 512;
        let y = Math.random() * 512;
        ctx.moveTo(x, y);
        for (let j = 0; j < 10; j++) {
            x += (Math.random() - 0.5) * 100;
            y += (Math.random() - 0.3) * 80;
            ctx.lineTo(x, y);
        }
        ctx.stroke();
    }
    
    const texture = new THREE.CanvasTexture(canvas);
    texture.wrapS = THREE.RepeatWrapping;
    texture.wrapT = THREE.RepeatWrapping;
    
    return new THREE.MeshPhysicalMaterial({
        map: texture,
        metalness: 0,
        roughness,
        clearcoat: currentQuality.clearcoat ? 0.5 : 0,
        clearcoatRoughness: 0.1,
        envMap,
        envMapIntensity: currentQuality.envMapIntensity * 0.5
    });
}

/**
 * Holographic display material
 */
export function createHologramMaterial(options = {}) {
    const {
        color = 0x67D4E4,
        opacity = 0.8
    } = options;
    
    return new THREE.MeshBasicMaterial({
        color,
        transparent: true,
        opacity,
        side: THREE.DoubleSide,
        blending: THREE.AdditiveBlending,
        depthWrite: false
    });
}

// ═══════════════════════════════════════════════════════════════════════════
// COLONY-SPECIFIC MATERIALS
// ═══════════════════════════════════════════════════════════════════════════

/**
 * Get colony-themed material
 */
export function getColonyMaterial(colony, type = 'standard') {
    const color = COLONY_COLORS[colony] || 0x67D4E4;
    
    switch (type) {
        case 'emissive':
            return createEmissiveMaterial({ color, emissiveIntensity: 0.5 });
        
        case 'crystal':
            return createCrystalMaterial({ color });
        
        case 'metal':
            return createMetalMaterial({ color });
        
        case 'glass':
            return createGlassMaterial({ color, transmission: 0.8 });
        
        case 'hologram':
            return createHologramMaterial({ color });
        
        case 'glow':
            return new THREE.MeshBasicMaterial({
                color,
                transparent: true,
                opacity: 0.3,
                side: THREE.BackSide,
                blending: THREE.AdditiveBlending
            });
        
        case 'standard':
        default:
            return new THREE.MeshPhysicalMaterial({
                color,
                emissive: color,
                emissiveIntensity: 0.3,
                metalness: 0.3,
                roughness: 0.4,
                clearcoat: 0.5
            });
    }
}

// ═══════════════════════════════════════════════════════════════════════════
// SPECIAL EFFECT MATERIALS
// ═══════════════════════════════════════════════════════════════════════════

/**
 * Particle material with additive blending
 */
export function createParticleMaterial(options = {}) {
    const {
        color = 0xFFFFFF,
        size = 0.1,
        opacity = 0.8,
        vertexColors = true
    } = options;
    
    return new THREE.PointsMaterial({
        color: vertexColors ? 0xFFFFFF : color,
        size,
        transparent: true,
        opacity,
        vertexColors,
        blending: THREE.AdditiveBlending,
        depthWrite: false,
        sizeAttenuation: true
    });
}

/**
 * Line/connection material
 */
export function createLineMaterial(options = {}) {
    const {
        color = 0x67D4E4,
        opacity = 0.5
    } = options;
    
    return new THREE.LineBasicMaterial({
        color,
        transparent: true,
        opacity,
        blending: THREE.AdditiveBlending
    });
}

/**
 * Safety barrier material (shader-based)
 */
export function createBarrierMaterial(options = {}) {
    const {
        safeColor = 0x00FF88,
        dangerColor = 0xFF4444
    } = options;
    
    return new THREE.ShaderMaterial({
        uniforms: {
            time: { value: 0 },
            hxValue: { value: 1.0 },
            safeColor: { value: new THREE.Color(safeColor) },
            dangerColor: { value: new THREE.Color(dangerColor) }
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
            uniform float time;
            uniform float hxValue;
            uniform vec3 safeColor;
            uniform vec3 dangerColor;
            
            varying vec3 vPosition;
            varying vec3 vNormal;
            
            void main() {
                vec3 color = mix(dangerColor, safeColor, hxValue);
                
                float fresnel = pow(1.0 - abs(dot(normalize(vNormal), vec3(0.0, 1.0, 0.0))), 2.0);
                float pulse = sin(time * 2.0 + vPosition.y * 3.0) * 0.5 + 0.5;
                
                float alpha = fresnel * 0.4 + pulse * 0.1;
                
                gl_FragColor = vec4(color, alpha * (1.0 - hxValue * 0.5));
            }
        `,
        transparent: true,
        side: THREE.DoubleSide,
        depthWrite: false
    });
}

// ═══════════════════════════════════════════════════════════════════════════
// MATERIAL UTILITIES
// ═══════════════════════════════════════════════════════════════════════════

/**
 * Create gradient texture
 */
export function createGradientTexture(color1, color2, size = 256) {
    const canvas = document.createElement('canvas');
    canvas.width = size;
    canvas.height = size;
    const ctx = canvas.getContext('2d');
    
    const gradient = ctx.createLinearGradient(0, 0, 0, size);
    gradient.addColorStop(0, '#' + new THREE.Color(color1).getHexString());
    gradient.addColorStop(1, '#' + new THREE.Color(color2).getHexString());
    
    ctx.fillStyle = gradient;
    ctx.fillRect(0, 0, size, size);
    
    const texture = new THREE.CanvasTexture(canvas);
    texture.needsUpdate = true;
    return texture;
}

/**
 * Create noise texture
 */
export function createNoiseTexture(size = 256) {
    const canvas = document.createElement('canvas');
    canvas.width = size;
    canvas.height = size;
    const ctx = canvas.getContext('2d');
    const imageData = ctx.createImageData(size, size);
    
    for (let i = 0; i < imageData.data.length; i += 4) {
        const value = Math.random() * 255;
        imageData.data[i] = value;
        imageData.data[i + 1] = value;
        imageData.data[i + 2] = value;
        imageData.data[i + 3] = 255;
    }
    
    ctx.putImageData(imageData, 0, 0);
    
    const texture = new THREE.CanvasTexture(canvas);
    texture.wrapS = THREE.RepeatWrapping;
    texture.wrapT = THREE.RepeatWrapping;
    texture.needsUpdate = true;
    return texture;
}

/**
 * Dispose material and its textures
 */
export function disposeMaterial(material) {
    if (!material) return;
    
    // Dispose textures
    const textureProps = ['map', 'normalMap', 'roughnessMap', 'metalnessMap', 'emissiveMap', 'envMap'];
    textureProps.forEach(prop => {
        if (material[prop]) {
            material[prop].dispose();
        }
    });
    
    material.dispose();
}

// ═══════════════════════════════════════════════════════════════════════════
// MATERIAL PRESETS
// ═══════════════════════════════════════════════════════════════════════════

export const MATERIAL_PRESETS = {
    // Floor types
    FLOOR_POLISHED: () => createFloorMaterial({ reflectivity: 0.95 }),
    FLOOR_MATTE: () => createFloorMaterial({ color: 0x0A0A0F, reflectivity: 0.3 }),
    
    // Wall types
    WALL_DARK: () => createWallMaterial({ color: 0x12101A }),
    WALL_LIGHT: () => createWallMaterial({ color: 0x1A1820 }),
    
    // Interactive elements
    INTERACTIVE_HOVER: (color) => createEmissiveMaterial({ color, emissiveIntensity: 0.8 }),
    INTERACTIVE_ACTIVE: (color) => createEmissiveMaterial({ color, emissiveIntensity: 1.2 }),
    
    // Colony crystals
    COLONY_CRYSTAL: (colony) => getColonyMaterial(colony, 'crystal'),
    COLONY_EMISSIVE: (colony) => getColonyMaterial(colony, 'emissive'),
    COLONY_HOLOGRAM: (colony) => getColonyMaterial(colony, 'hologram')
};
