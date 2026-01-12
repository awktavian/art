/**
 * Kagami Orb V3.1 — Geometry Factory
 * Procedural mesh generation for all component types
 */

import * as THREE from 'three';

/**
 * Create hemisphere geometry
 * @param {number} radius - Sphere radius
 * @param {boolean} top - True for top half, false for bottom
 */
export function createHemisphere(radius, top = true) {
    const geometry = new THREE.SphereGeometry(
        radius,
        64, 64,
        0, Math.PI * 2,
        top ? 0 : Math.PI / 2,
        Math.PI / 2
    );
    return geometry;
}

/**
 * Create box geometry with optional rounding
 * @param {number} w - Width (X)
 * @param {number} d - Depth (Z)
 * @param {number} h - Height (Y)
 * @param {number} radius - Edge radius (0 for sharp)
 */
export function createBox(w, d, h, radius = 0) {
    if (radius > 0 && typeof THREE.RoundedBoxGeometry !== 'undefined') {
        return new THREE.RoundedBoxGeometry(w, h, d, 4, radius);
    }
    return new THREE.BoxGeometry(w, h, d);
}

/**
 * Create cylinder geometry
 * @param {number} radius - Cylinder radius
 * @param {number} height - Cylinder height
 * @param {number} segments - Radial segments
 */
export function createCylinder(radius, height, segments = 64) {
    return new THREE.CylinderGeometry(radius, radius, height, segments);
}

/**
 * Create disc (flat cylinder)
 * @param {number} radius - Disc radius
 * @param {number} height - Disc thickness
 */
export function createDisc(radius, height) {
    return createCylinder(radius, height, 64);
}

/**
 * Create ring geometry (hollow cylinder)
 * @param {number} outerRadius - Outer radius
 * @param {number} innerRadius - Inner radius
 * @param {number} height - Ring thickness
 */
export function createRing(outerRadius, innerRadius, height) {
    const shape = new THREE.Shape();
    shape.absarc(0, 0, outerRadius, 0, Math.PI * 2, false);
    const hole = new THREE.Path();
    hole.absarc(0, 0, innerRadius, 0, Math.PI * 2, true);
    shape.holes.push(hole);

    const extrudeSettings = {
        steps: 1,
        depth: height,
        bevelEnabled: false
    };

    const geometry = new THREE.ExtrudeGeometry(shape, extrudeSettings);
    geometry.rotateX(-Math.PI / 2);
    geometry.translate(0, height / 2, 0);
    return geometry;
}

/**
 * Create torus geometry for coils
 * @param {number} majorRadius - Ring radius
 * @param {number} minorRadius - Tube radius
 * @param {number} turns - Number of visible turns (aesthetic)
 */
export function createTorus(majorRadius, minorRadius, turns = 12) {
    return new THREE.TorusGeometry(majorRadius, minorRadius, 16, turns * 8);
}

/**
 * Create LED array as instanced mesh
 * @param {number} count - Number of LEDs
 * @param {number} radius - Ring radius
 * @param {number} y - Y position
 * @param {THREE.Material} material - LED material
 */
export function createLEDArray(count, radius, y, material) {
    const ledGeometry = new THREE.BoxGeometry(3, 1.6, 3);
    const instancedMesh = new THREE.InstancedMesh(ledGeometry, material, count);

    const matrix = new THREE.Matrix4();
    for (let i = 0; i < count; i++) {
        const angle = (i / count) * Math.PI * 2;
        const x = Math.cos(angle) * radius;
        const z = Math.sin(angle) * radius;
        matrix.setPosition(x, y, z);
        instancedMesh.setMatrixAt(i, matrix);
    }

    instancedMesh.instanceMatrix.needsUpdate = true;
    return instancedMesh;
}

/**
 * Create microphone array
 * @param {number} count - Number of mics (4 for quad array)
 * @param {number} radius - Ring radius
 * @param {number} y - Y position
 * @param {THREE.Material} material - Mic material
 */
export function createMicArray(count, radius, y, material) {
    const micGeometry = new THREE.CylinderGeometry(1.5, 1.5, 2.47, 16);
    const instancedMesh = new THREE.InstancedMesh(micGeometry, material, count);

    const matrix = new THREE.Matrix4();
    for (let i = 0; i < count; i++) {
        const angle = (i / count) * Math.PI * 2 + Math.PI / 4; // Offset 45°
        const x = Math.cos(angle) * radius;
        const z = Math.sin(angle) * radius;
        matrix.setPosition(x, y, z);
        instancedMesh.setMatrixAt(i, matrix);
    }

    instancedMesh.instanceMatrix.needsUpdate = true;
    return instancedMesh;
}

/**
 * Create copper wire coil with realistic spiral
 * @param {number} majorRadius - Coil radius
 * @param {number} wireRadius - Wire thickness
 * @param {number} turns - Number of turns
 * @param {number} pitch - Vertical pitch per turn
 */
export function createCoilSpiral(majorRadius, wireRadius, turns, pitch = 0) {
    const points = [];
    const segments = turns * 64;

    for (let i = 0; i <= segments; i++) {
        const t = i / segments;
        const angle = t * Math.PI * 2 * turns;
        const x = Math.cos(angle) * majorRadius;
        const z = Math.sin(angle) * majorRadius;
        const y = t * pitch * turns;
        points.push(new THREE.Vector3(x, y, z));
    }

    const curve = new THREE.CatmullRomCurve3(points);
    return new THREE.TubeGeometry(curve, segments, wireRadius, 8, false);
}

/**
 * Factory function to create geometry for a component
 * @param {Object} component - Component definition from components.js
 * @returns {THREE.BufferGeometry}
 */
export function createGeometryForComponent(component) {
    const geo = component.geo;

    switch (geo) {
        case 'hemi_top':
            return createHemisphere(component.r, true);
        case 'hemi_bot':
            return createHemisphere(component.r, false);
        case 'box':
            return createBox(component.w, component.d, component.h);
        case 'cyl':
            return createCylinder(component.r, component.h);
        case 'disc':
            return createDisc(component.r, component.h);
        case 'ring':
            return createRing(component.ro, component.ri, component.h);
        case 'torus':
            return createTorus(component.R, component.r);
        case 'leds':
        case 'mics':
            // These need special handling with materials
            return null;
        default:
            console.warn(`Unknown geometry type: ${geo}`);
            return createBox(10, 10, 5);
    }
}

/**
 * Create sphere outline wireframe (for collision visualization)
 * @param {number} radius - Sphere radius
 * @param {number} color - Line color
 */
export function createSphereOutline(radius, color = 0x00ff00) {
    const geometry = new THREE.SphereGeometry(radius, 32, 32);
    const wireframe = new THREE.WireframeGeometry(geometry);
    const material = new THREE.LineBasicMaterial({
        color,
        opacity: 0.2,
        transparent: true
    });
    return new THREE.LineSegments(wireframe, material);
}

/**
 * Create cross-section plane for internal view
 * @param {number} size - Plane size
 * @param {number} opacity - Plane opacity
 */
export function createCrossSectionPlane(size = 100, opacity = 0.1) {
    const geometry = new THREE.PlaneGeometry(size, size);
    const material = new THREE.MeshBasicMaterial({
        color: 0xffffff,
        transparent: true,
        opacity,
        side: THREE.DoubleSide,
        depthWrite: false
    });
    return new THREE.Mesh(geometry, material);
}
