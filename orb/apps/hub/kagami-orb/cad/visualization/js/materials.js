/**
 * Kagami Orb V3.1 — PBR Materials Library
 * Premium materials with physically accurate properties
 */

import * as THREE from 'three';

/**
 * Create premium clear acrylic material with glass-like properties
 * Used for shell hemispheres
 */
export function createAcrylicMaterial(options = {}) {
    return new THREE.MeshPhysicalMaterial({
        color: options.color ?? 0xffffff,
        metalness: 0.0,
        roughness: options.roughness ?? 0.05,
        transmission: options.transmission ?? 0.92,
        thickness: options.thickness ?? 3.5,
        ior: 1.49, // Acrylic IOR
        clearcoat: 1.0,
        clearcoatRoughness: 0.05,
        envMapIntensity: options.envMapIntensity ?? 1.2,
        transparent: true,
        side: THREE.DoubleSide,
        // Subtle blue tint for infinity mirror effect
        attenuationColor: new THREE.Color(0xccddff),
        attenuationDistance: 5,
    });
}

/**
 * Create polished copper material for coils
 */
export function createCopperMaterial() {
    return new THREE.MeshStandardMaterial({
        color: 0xB87333,
        metalness: 1.0,
        roughness: 0.25,
        envMapIntensity: 1.3,
    });
}

/**
 * Create walnut wood material
 */
export function createWalnutMaterial() {
    return new THREE.MeshStandardMaterial({
        color: 0x5d4037,
        metalness: 0.0,
        roughness: 0.55,
        envMapIntensity: 0.4,
    });
}

/**
 * Create PCB material with green solder mask
 */
export function createPCBMaterial() {
    return new THREE.MeshPhysicalMaterial({
        color: 0x1D5C37,
        metalness: 0.0,
        roughness: 0.4,
        clearcoat: 0.3,
        clearcoatRoughness: 0.2,
    });
}

/**
 * Create LED emissive material
 * @param {number} color - Emissive color (hex)
 * @param {number} intensity - Emissive intensity
 */
export function createLEDMaterial(color = 0xff6600, intensity = 5.0) {
    return new THREE.MeshStandardMaterial({
        color: 0x222222,
        emissive: new THREE.Color(color),
        emissiveIntensity: intensity,
        toneMapped: false, // Critical for bloom
    });
}

/**
 * Create display/screen material
 */
export function createDisplayMaterial() {
    return new THREE.MeshStandardMaterial({
        color: 0x111120,
        metalness: 0.0,
        roughness: 0.1,
        emissive: new THREE.Color(0x000022),
        emissiveIntensity: 0.3,
    });
}

/**
 * Create camera lens material
 */
export function createCameraLensMaterial() {
    return new THREE.MeshPhysicalMaterial({
        color: 0x1a1a2a,
        metalness: 0.0,
        roughness: 0.05,
        transmission: 0.3,
        thickness: 2,
        ior: 1.52,
        clearcoat: 1.0,
    });
}

/**
 * Create generic component material based on color
 */
export function createComponentMaterial(color, options = {}) {
    return new THREE.MeshStandardMaterial({
        color: color,
        metalness: options.metalness ?? 0.1,
        roughness: options.roughness ?? 0.7,
        transparent: options.opacity !== undefined,
        opacity: options.opacity ?? 1.0,
        side: options.opacity ? THREE.DoubleSide : THREE.FrontSide,
    });
}

/**
 * Create battery material (blue cell color)
 */
export function createBatteryMaterial() {
    return new THREE.MeshStandardMaterial({
        color: 0x0055aa,
        metalness: 0.3,
        roughness: 0.6,
    });
}

/**
 * Create heatsink material (brushed aluminum)
 */
export function createHeatsinkMaterial() {
    return new THREE.MeshStandardMaterial({
        color: 0x3a3a3a,
        metalness: 0.8,
        roughness: 0.35,
    });
}

/**
 * Create diffuser material (frosted plastic)
 */
export function createDiffuserMaterial() {
    return new THREE.MeshPhysicalMaterial({
        color: 0xffffff,
        metalness: 0.0,
        roughness: 0.7,
        transmission: 0.5,
        thickness: 1.5,
        ior: 1.4,
        transparent: true,
        opacity: 0.7,
        side: THREE.DoubleSide,
    });
}

/**
 * Create ferrite material (dark magnetic material)
 */
export function createFerriteMaterial() {
    return new THREE.MeshStandardMaterial({
        color: 0x1a1a1a,
        metalness: 0.0,
        roughness: 0.9,
    });
}

/**
 * Create maglev module material
 */
export function createMaglevMaterial() {
    return new THREE.MeshStandardMaterial({
        color: 0x2a3a4a,
        metalness: 0.4,
        roughness: 0.5,
    });
}

/**
 * Material factory - get material by component type
 */
export function getMaterialForComponent(component) {
    const id = component.id;
    const color = component.clr;
    const opacity = component.op;

    // Special material assignments
    if (id.includes('shell')) {
        return createAcrylicMaterial({ transmission: 0.88 });
    }
    if (id.includes('coil')) {
        return createCopperMaterial();
    }
    if (id === 'base_enc') {
        return createWalnutMaterial();
    }
    if (id.includes('pcb') || id === 'led_ring') {
        return createPCBMaterial();
    }
    if (id === 'leds' || id === 'base_leds') {
        return createLEDMaterial(color);
    }
    if (id === 'display') {
        return createDisplayMaterial();
    }
    if (id === 'camera') {
        return createCameraLensMaterial();
    }
    if (id === 'battery') {
        return createBatteryMaterial();
    }
    if (id === 'heatsink') {
        return createHeatsinkMaterial();
    }
    if (id === 'diffuser') {
        return createDiffuserMaterial();
    }
    if (id === 'ferrite') {
        return createFerriteMaterial();
    }
    if (id === 'maglev') {
        return createMaglevMaterial();
    }

    // Default material
    return createComponentMaterial(color, { opacity });
}
