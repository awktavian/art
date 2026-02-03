/**
 * Museum-Quality Materials Library
 * =================================
 * 
 * Professional materials for the Patent Museum.
 * All materials optimized for:
 * - Visual quality (PBR, clearcoat, iridescence)
 * - Performance (LOD, instancing)
 * - Consistency across the museum
 * 
 * h(x) ≥ 0 always
 */

import * as THREE from 'three';

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
// BASE MATERIALS
// ═══════════════════════════════════════════════════════════════════════════

/**
 * Premium glass material with refraction
 */
export function createGlassMaterial(options = {}) {
    const {
        color = 0xFFFFFF,
        opacity = 0.3,
        transmission = 0.95,
        thickness = 0.5,
        roughness = 0,
        ior = 1.5
    } = options;
    
    return new THREE.MeshPhysicalMaterial({
        color,
        metalness: 0,
        roughness,
        transmission,
        thickness,
        transparent: true,
        opacity,
        ior,
        envMapIntensity: 1.0
    });
}

/**
 * Iridescent crystal material
 */
export function createCrystalMaterial(options = {}) {
    const {
        color = 0x67D4E4,
        iridescenceIntensity = 1.0,
        iridescenceIOR = 1.3
    } = options;
    
    return new THREE.MeshPhysicalMaterial({
        color,
        metalness: 0.1,
        roughness: 0.05,
        transmission: 0.7,
        thickness: 1.0,
        iridescence: iridescenceIntensity,
        iridescenceIOR,
        clearcoat: 1.0,
        clearcoatRoughness: 0.1,
        transparent: true,
        opacity: 0.9,
        envMapIntensity: 1.0
    });
}

/**
 * Polished metal material (gold/bronze/steel)
 */
export function createMetalMaterial(options = {}) {
    const {
        color = 0xD4AF37,
        roughness = 0.2,
        clearcoat = 0.5
    } = options;
    
    return new THREE.MeshPhysicalMaterial({
        color,
        metalness: 0.95,
        roughness,
        clearcoat,
        clearcoatRoughness: 0.1,
        envMapIntensity: 1.0
    });
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
 * Museum floor material (polished reflective)
 */
export function createFloorMaterial(options = {}) {
    const {
        color = 0x080810,
        reflectivity = 0.9
    } = options;
    
    return new THREE.MeshPhysicalMaterial({
        color,
        metalness: 0.9,
        roughness: 0.1,
        clearcoat: 1.0,
        clearcoatRoughness: 0.05,
        reflectivity,
        envMapIntensity: 0.8
    });
}

/**
 * Museum wall material (matte with subtle texture)
 */
export function createWallMaterial(options = {}) {
    const {
        color = 0x12101A
    } = options;
    
    return new THREE.MeshStandardMaterial({
        color,
        metalness: 0.1,
        roughness: 0.8
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
