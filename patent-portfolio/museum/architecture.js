/**
 * Patent Museum Architecture (Redesigned)
 * =======================================
 * 
 * Inspired by:
 * - I.M. Pei: Geometric clarity, triangular forms, clean materials
 * - Frank Lloyd Wright: Compression/release, organic flow
 * - Frank Gehry: Sculptural drama, asymmetric forms
 * 
 * The architecture speaks through geometry, not decoration.
 * 
 * h(x) ≥ 0 always
 */

import * as THREE from 'three';
import { createProceduralNormalMap, createConcreteMaterial, createConcretePolishedMaterial, createBrushedSteelMaterial, createCrystalMaterial, createFlowPoolMaterial } from '../lib/materials.js';

// ═══════════════════════════════════════════════════════════════════════════
// COLONY DATA
// ═══════════════════════════════════════════════════════════════════════════

export const COLONY_DATA = {
    spark:   { hex: 0xFF6B35, name: 'Spark',   categories: ['G', 'K'], wingAngle: 0 },
    forge:   { hex: 0xD4AF37, name: 'Forge',   categories: ['E', 'I'], wingAngle: Math.PI * 2 / 7 },
    flow:    { hex: 0x4ECDC4, name: 'Flow',    categories: ['F'],      wingAngle: Math.PI * 4 / 7 },
    nexus:   { hex: 0x9B7EBD, name: 'Nexus',   categories: ['C', 'J'], wingAngle: Math.PI * 6 / 7 },
    beacon:  { hex: 0xF59E0B, name: 'Beacon',  categories: ['H'],      wingAngle: Math.PI * 8 / 7 },
    grove:   { hex: 0x7EB77F, name: 'Grove',   categories: ['D'],      wingAngle: Math.PI * 10 / 7 },
    crystal: { hex: 0x67D4E4, name: 'Crystal', categories: ['A', 'B'], wingAngle: Math.PI * 12 / 7 }
};

export const COLONY_ORDER = ['spark', 'forge', 'flow', 'nexus', 'beacon', 'grove', 'crystal'];

// ═══════════════════════════════════════════════════════════════════════════
// DIMENSIONS (Wright-inspired compression/release)
// ═══════════════════════════════════════════════════════════════════════════

export const DIMENSIONS = {
    rotunda: {
        radius: 20,
        height: 28,
        floorY: 0,
        domeStart: 18,
        wallSegments: 48,
        apertureRadius: 4,      // Gehry: off-center aperture
        apertureOffset: 3       // Offset from center
    },
    
    // Wright: 3:1 compression — 4m corridor exploding into 16m gallery
    wing: {
        width: 4,               // Narrow corridor (was 12)
        length: 45,
        entranceHeight: 4,     // LOW - compressed entrance
        corridorHeight: 8,     // Start ceiling height
        corridorCeilingMin: 4,  // Taper to 4m mid-corridor
        vestibuleDepth: 6,     // Transition at compression/release boundary
        openingAngle: Math.PI / 8
    },

    gallery: {
        width: 24,
        depth: 30,
        height: 16              // HIGH - release/expansion
    },

    vestibule: {
        width: 10,
        depth: 15,
        height: 6
    },
    
    landmarks: {
        spacing: [8, 13, 21, 34],
        signageInterval: 8
    }
};

// ═══════════════════════════════════════════════════════════════════════════
// BUILDING (floor plan: entrance, spine, circulation)
// Data-driven so layout and wayfinding share one source of truth.
// ═══════════════════════════════════════════════════════════════════════════

export const BUILDING = {
    /** World angle (radians) of main entrance; guest faces this direction on arrival. South = Math.PI. */
    entranceWorldDirection: Math.PI,
    /** World angle (radians) of primary circulation axis through the rotunda (e.g. entrance–center–back). */
    spineDirection: Math.PI,
    /** Optional: world angle for exit / return path (default same as entrance). */
    exitWorldDirection: Math.PI,
    /** Wing layout: use COLONY_DATA[].wingAngle and DIMENSIONS.wing for lengths/widths. */
    wingCount: COLONY_ORDER.length
};

// ═══════════════════════════════════════════════════════════════════════════
// MATERIALS (Pei-inspired: 4 core materials)
// ═══════════════════════════════════════════════════════════════════════════

export function createMuseumMaterials() {
    const normalMap = createProceduralNormalMap(256, 6);
    return {
        // 1. WARM CONCRETE - Walls, dome (procedural normal map, roughness 0.8)
        concrete: createConcreteMaterial({ normalMap, roughness: 0.8 }),
        floor: new THREE.MeshPhysicalMaterial({
            color: 0x0A0A0A,
            roughness: 0.1,
            metalness: 0.3,
            clearcoat: 0.8,
            clearcoatRoughness: 0.1,
            envMapIntensity: 1.0,
            side: THREE.DoubleSide
        }),
        // 3. BRUSHED STEEL - Fano sculpture, accents (anisotropy)
        steel: createBrushedSteelMaterial({ roughness: 0.3 }),
        glass: new THREE.MeshPhysicalMaterial({
            color: 0xFFFFFF,
            transmission: 0.7,
            thickness: 0.5,
            roughness: 0.1,
            metalness: 0,
            ior: 1.5,
            envMapIntensity: 0.5
        }),
        ceiling: new THREE.MeshStandardMaterial({
            color: 0x2D2A28,
            roughness: 0.9,
            metalness: 0.02,
            side: THREE.BackSide
        }),
        concretePolished: createConcretePolishedMaterial(),

        // Legacy compatibility
        wall: null,  // Will point to concrete
        wallAccent: null,
        baseboard: null,
        rib: null,
        floorReflective: null
    };
}

// ═══════════════════════════════════════════════════════════════════════════
// ROTUNDA (Gehry-inspired asymmetric dome)
// ═══════════════════════════════════════════════════════════════════════════

export function createRotunda(materials) {
    const group = new THREE.Group();
    group.name = 'rotunda';
    
    const { radius, height, wallSegments, apertureRadius, apertureOffset } = DIMENSIONS.rotunda;
    
    // === FLOOR (polished black) ===
    const floorGeo = new THREE.CircleGeometry(radius, wallSegments);
    const floor = new THREE.Mesh(floorGeo, materials.floor);
    floor.rotation.x = -Math.PI / 2;
    floor.position.y = 0;
    floor.receiveShadow = true;
    floor.name = 'rotunda-floor';
    group.add(floor);
    
    // Radial lines pointing to wings (use thin planes for better visibility)
    COLONY_ORDER.forEach((colony, i) => {
        const data = COLONY_DATA[colony];
        
        // Create a thin plane instead of a line for better visibility
        const lineLength = radius - 2;  // Don't go all the way to center
        const lineGeo = new THREE.PlaneGeometry(0.08, lineLength);
        const lineMat = new THREE.MeshBasicMaterial({ 
            color: data.hex, 
            opacity: 0.6,
            transparent: true,
            side: THREE.DoubleSide
        });
        const line = new THREE.Mesh(lineGeo, lineMat);
        
        // Position at half the radius, rotated to point outward
        line.rotation.x = -Math.PI / 2;  // Lay flat
        line.rotation.z = -data.wingAngle + Math.PI / 2;  // Point toward wing
        line.position.set(
            Math.cos(data.wingAngle) * (radius / 2 + 1),
            0.01,  // Slightly above floor
            Math.sin(data.wingAngle) * (radius / 2 + 1)
        );
        group.add(line);
    });
    
    // === WALLS (warm concrete, cylindrical) ===
    const wallGeo = new THREE.CylinderGeometry(
        radius, radius * 1.02,  // Slight outward cant (Gehry)
        height * 0.7,
        wallSegments, 1, true
    );
    const walls = new THREE.Mesh(wallGeo, materials.concrete);
    walls.name = 'wall-rotunda';
    walls.userData.occludes = true;
    walls.position.y = height * 0.35;
    walls.receiveShadow = true;
    walls.castShadow = true;
    group.add(walls);
    
    // === DOME (Gehry asymmetric curve) ===
    createGehryDome(group, materials, radius, height, apertureRadius, apertureOffset);
    
    // === FANO SCULPTURE (simplified - just the 7 lines) ===
    const fano = createSimplifiedFano(materials.steel);
    fano.position.y = height * 0.5;
    fano.userData = { interactive: true, type: 'fano-sculpture' };
    group.add(fano);
    
    // === TRIANGULAR PORTALS (Pei-inspired) ===
    COLONY_ORDER.forEach(colony => {
        const data = COLONY_DATA[colony];
        const portal = createTriangularPortal(
            data.wingAngle, 
            radius, 
            DIMENSIONS.wing.entranceHeight,
            data.hex
        );
        group.add(portal);
    });
    
    return group;
}

// ═══════════════════════════════════════════════════════════════════════════
// GEHRY DOME (asymmetric with off-center aperture)
// ═══════════════════════════════════════════════════════════════════════════

function createGehryDome(group, materials, radius, height, apertureRadius, apertureOffset) {
    // Custom dome geometry - asymmetric curve
    const segments = 48;
    const rings = 24;
    const positions = [];
    const indices = [];
    const uvs = [];
    
    const domeStart = DIMENSIONS.rotunda.domeStart;
    
    for (let ring = 0; ring <= rings; ring++) {
        const v = ring / rings;
        
        for (let seg = 0; seg <= segments; seg++) {
            const u = seg / segments;
            const theta = u * Math.PI * 2;
            
            // Asymmetric radius (Gehry effect)
            const asymmetry = 1 + 0.08 * Math.sin(theta * 2);
            const ringRadius = radius * (1 - v * 0.7) * asymmetry;
            
            // Height curve (steeper on one side)
            const heightCurve = Math.pow(v, 1.5 + 0.3 * Math.cos(theta));
            const y = domeStart + (height - domeStart) * heightCurve;
            
            // Check if inside aperture (off-center)
            const distFromAperture = Math.sqrt(
                Math.pow(ringRadius * Math.cos(theta) - apertureOffset, 2) +
                Math.pow(ringRadius * Math.sin(theta), 2)
            );
            
            if (v > 0.85 && distFromAperture < apertureRadius) {
                continue; // Skip aperture area
            }
            
            positions.push(
                ringRadius * Math.cos(theta),
                y,
                ringRadius * Math.sin(theta)
            );
            uvs.push(u, v);
        }
    }
    
    // Create indices (simplified for now - use sphere as base)
    const domeGeo = new THREE.SphereGeometry(radius, segments, rings, 0, Math.PI * 2, 0, Math.PI * 0.5);
    
    // Apply asymmetric deformation to sphere
    const pos = domeGeo.attributes.position;
    for (let i = 0; i < pos.count; i++) {
        const x = pos.getX(i);
        const y = pos.getY(i);
        const z = pos.getZ(i);
        
        const theta = Math.atan2(z, x);
        const asymmetry = 1 + 0.1 * Math.sin(theta * 2);
        
        pos.setX(i, x * asymmetry);
        pos.setZ(i, z * asymmetry);
        pos.setY(i, y * 0.6 + domeStart);  // Flatten and raise
    }
    pos.needsUpdate = true;
    domeGeo.computeVertexNormals();
    
    const dome = new THREE.Mesh(domeGeo, materials.ceiling);
    dome.name = 'dome';
    dome.userData.occludes = true;
    group.add(dome);
    
    // Aperture ring (off-center)
    const ringGeo = new THREE.TorusGeometry(apertureRadius, 0.3, 8, 32);
    const ring = new THREE.Mesh(ringGeo, materials.steel);
    ring.position.set(apertureOffset, height - 1, 0);
    ring.rotation.x = Math.PI / 2;
    group.add(ring);
    
    // Sky disc visible through aperture
    const skyGeo = new THREE.CircleGeometry(apertureRadius - 0.1, 32);
    const skyMat = new THREE.MeshBasicMaterial({ 
        color: 0x4488AA, 
        side: THREE.DoubleSide 
    });
    const sky = new THREE.Mesh(skyGeo, skyMat);
    sky.position.set(apertureOffset, height - 0.5, 0);
    sky.rotation.x = Math.PI / 2;
    group.add(sky);
}

// ═══════════════════════════════════════════════════════════════════════════
// SIMPLIFIED FANO SCULPTURE (just 7 lines, no particles)
// ═══════════════════════════════════════════════════════════════════════════

function createSimplifiedFano(steelMaterial) {
    const group = new THREE.Group();
    group.name = 'fano-sculpture';
    
    const scale = 2.5;
    
    // 7 points on a heptagon
    const points = [];
    for (let i = 0; i < 7; i++) {
        const angle = (i / 7) * Math.PI * 2 - Math.PI / 2;
        points.push(new THREE.Vector3(
            Math.cos(angle) * scale,
            0,
            Math.sin(angle) * scale
        ));
    }
    
    // Fano plane connections (each point connects to 3 others)
    const connections = [
        [0, 1], [0, 2], [0, 4],
        [1, 2], [1, 3], [1, 5],
        [2, 3], [2, 6],
        [3, 4], [3, 5],
        [4, 5], [4, 6],
        [5, 6], [6, 0]
    ];
    
    connections.forEach(([a, b]) => {
        const tubeGeo = new THREE.TubeGeometry(
            new THREE.CatmullRomCurve3([points[a], points[b]]),
            8, 0.03, 6, false
        );
        const tube = new THREE.Mesh(tubeGeo, steelMaterial);
        tube.castShadow = true;
        group.add(tube);
    });
    
    // Small spheres at vertices
    points.forEach((point, i) => {
        const sphereGeo = new THREE.SphereGeometry(0.08, 16, 16);
        const sphere = new THREE.Mesh(sphereGeo, steelMaterial);
        sphere.position.copy(point);
        sphere.castShadow = true;
        group.add(sphere);
    });
    
    return group;
}

// ═══════════════════════════════════════════════════════════════════════════
// TRIANGULAR PORTAL (Pei-inspired wing entrance)
// ═══════════════════════════════════════════════════════════════════════════

function createTriangularPortal(angle, rotundaRadius, height, color) {
    const group = new THREE.Group();
    
    const width = DIMENSIONS.wing.width;
    
    // Triangle shape for portal frame
    const shape = new THREE.Shape();
    shape.moveTo(-width / 2, 0);
    shape.lineTo(0, height * 1.5);  // Peak above entrance
    shape.lineTo(width / 2, 0);
    shape.lineTo(-width / 2, 0);
    
    // Inner cutout (the actual opening)
    const hole = new THREE.Path();
    const inset = 0.8;
    hole.moveTo(-width / 2 * inset, 0.1);
    hole.lineTo(0, height * 1.3);
    hole.lineTo(width / 2 * inset, 0.1);
    hole.lineTo(-width / 2 * inset, 0.1);
    shape.holes.push(hole);
    
    const extrudeSettings = {
        depth: 1,
        bevelEnabled: false
    };
    
    const frameGeo = new THREE.ExtrudeGeometry(shape, extrudeSettings);
    const frameMat = new THREE.MeshStandardMaterial({
        color: color,
        metalness: 0.6,
        roughness: 0.3
    });
    
    const frame = new THREE.Mesh(frameGeo, frameMat);
    
    // Position at rotunda edge
    frame.position.set(
        Math.cos(angle) * rotundaRadius,
        0,
        Math.sin(angle) * rotundaRadius
    );
    frame.rotation.y = -angle + Math.PI / 2;
    frame.castShadow = true;
    
    group.add(frame);
    
    return group;
}

// ═══════════════════════════════════════════════════════════════════════════
// WING CORRIDORS (extreme compression: 4m wide, ceiling taper 8m→4m)
// ═══════════════════════════════════════════════════════════════════════════

export function createWing(colony, materials) {
    const group = new THREE.Group();
    group.name = `wing-${colony}`;
    const data = COLONY_DATA[colony];
    const angle = data.wingAngle;
    const { width, length, corridorHeight, corridorCeilingMin, vestibuleDepth } = DIMENSIONS.wing;
    const rotundaRadius = DIMENSIONS.rotunda.radius;
    const cos = Math.cos(angle), sin = Math.sin(angle);

    // Corridor in 3 segments: ceiling 8m -> 6m -> 4m
    const segLen = length / 3;
    const heights = [corridorHeight, (corridorHeight + (corridorCeilingMin ?? 4)) / 2, corridorCeilingMin ?? 4];

    // === FLOOR (corridor only; vestibule has its own floor) ===
    const floorGeo = new THREE.PlaneGeometry(width, length);
    const floor = new THREE.Mesh(floorGeo, materials.floor);
    floor.rotation.x = -Math.PI / 2;
    floor.rotation.z = angle;
    floor.position.set(
        cos * (rotundaRadius + length / 2),
        0.01,
        sin * (rotundaRadius + length / 2)
    );
    floor.receiveShadow = true;
    floor.name = `wing-floor-${colony}`;
    group.add(floor);

    const centerLineLen = length;
    const lineGeo = new THREE.PlaneGeometry(0.08, centerLineLen);
    const lineMat = new THREE.MeshBasicMaterial({
        color: data.hex,
        opacity: 0.6,
        transparent: true,
        side: THREE.DoubleSide
    });
    const centerLine = new THREE.Mesh(lineGeo, lineMat);
    centerLine.rotation.x = -Math.PI / 2;
    centerLine.rotation.z = angle;
    centerLine.position.set(cos * (rotundaRadius + length / 2), 0.02, sin * (rotundaRadius + length / 2));
    group.add(centerLine);

    // === WALLS + CEILING per segment (taper: rough concrete, last segment polished at threshold) ===
    for (let i = 0; i < 3; i++) {
        const h = heights[i];
        const segStart = i * segLen;
        const mid = segStart + segLen / 2;
        const wallMat = i >= 2 ? materials.concretePolished : materials.concrete;
        const ceilMat = materials.ceiling;

        const leftWall = new THREE.Mesh(new THREE.BoxGeometry(0.4, h, segLen), wallMat);
        leftWall.name = `wall-${colony}-left-${i}`;
        leftWall.userData.occludes = true;
        leftWall.position.set(
            cos * (rotundaRadius + mid) - sin * width / 2,
            h / 2,
            sin * (rotundaRadius + mid) + cos * width / 2
        );
        leftWall.rotation.y = angle;
        leftWall.castShadow = true;
        leftWall.receiveShadow = true;
        group.add(leftWall);

        const rightWall = new THREE.Mesh(new THREE.BoxGeometry(0.4, h, segLen), wallMat);
        rightWall.name = `wall-${colony}-right-${i}`;
        rightWall.userData.occludes = true;
        rightWall.position.set(
            cos * (rotundaRadius + mid) + sin * width / 2,
            h / 2,
            sin * (rotundaRadius + mid) - cos * width / 2
        );
        rightWall.rotation.y = angle;
        rightWall.castShadow = true;
        rightWall.receiveShadow = true;
        group.add(rightWall);

        const ceilingGeo = new THREE.PlaneGeometry(width + 0.1, segLen);
        const ceiling = new THREE.Mesh(ceilingGeo, ceilMat);
        ceiling.userData.occludes = true;
        ceiling.rotation.x = Math.PI / 2;
        ceiling.rotation.z = angle;
        ceiling.position.set(cos * (rotundaRadius + mid), h, sin * (rotundaRadius + mid));
        group.add(ceiling);
    }

    return group;
}

// ═══════════════════════════════════════════════════════════════════════════
// WING VESTIBULE (transition at compression/release: 4m→12m width, 4m→10m height)
// ═══════════════════════════════════════════════════════════════════════════

export function createWingVestibule(colony, materials) {
    const group = new THREE.Group();
    group.name = `wing-vestibule-${colony}`;
    const data = COLONY_DATA[colony];
    const angle = data.wingAngle;
    const rotundaRadius = DIMENSIONS.rotunda.radius;
    const wingLength = DIMENSIONS.wing.length;
    const vestibuleDepth = DIMENSIONS.wing.vestibuleDepth ?? 6;
    const cos = Math.cos(angle), sin = Math.sin(angle);
    const centerDist = rotundaRadius + wingLength + vestibuleDepth / 2;
    const centerX = cos * centerDist;
    const centerZ = sin * centerDist;
    const widthStart = DIMENSIONS.wing.width;
    const widthEnd = 12;
    const heightStart = DIMENSIONS.wing.corridorCeilingMin ?? 4;
    const heightEnd = 10;
    const widthMid = (widthStart + widthEnd) / 2;
    const heightMid = (heightStart + heightEnd) / 2;

    const floorGeo = new THREE.PlaneGeometry(widthEnd, vestibuleDepth);
    const floor = new THREE.Mesh(floorGeo, materials.floor);
    floor.rotation.x = -Math.PI / 2;
    floor.position.set(centerX, 0.01, centerZ);
    floor.rotation.z = angle;
    floor.receiveShadow = true;
    group.add(floor);

    const wallMat = materials.concretePolished;
    const leftWall = new THREE.Mesh(
        new THREE.BoxGeometry(0.4, heightMid, vestibuleDepth),
        wallMat
    );
    leftWall.position.set(centerX - sin * widthMid / 2, heightMid / 2, centerZ + cos * widthMid / 2);
    leftWall.rotation.y = angle;
    group.add(leftWall);
    const rightWall = new THREE.Mesh(
        new THREE.BoxGeometry(0.4, heightMid, vestibuleDepth),
        wallMat
    );
    rightWall.position.set(centerX + sin * widthMid / 2, heightMid / 2, centerZ - cos * widthMid / 2);
    rightWall.rotation.y = angle;
    group.add(rightWall);

    const ceilingGeo = new THREE.PlaneGeometry(widthMid, vestibuleDepth);
    const ceiling = new THREE.Mesh(ceilingGeo, materials.ceiling);
    ceiling.userData.occludes = true;
    ceiling.rotation.x = Math.PI / 2;
    ceiling.rotation.z = angle;
    ceiling.position.set(centerX, heightMid, centerZ);
    group.add(ceiling);

    return group;
}

// ═══════════════════════════════════════════════════════════════════════════
// GALLERY ROOM (high ceiling - the "release")
// Each wing has ONE distinct architectural feature
// ═══════════════════════════════════════════════════════════════════════════

export function createGalleryRoom(colony, categoryId, materials) {
    const group = new THREE.Group();
    group.name = `gallery-${colony}-${categoryId}`;
    
    const data = COLONY_DATA[colony];
    const angle = data.wingAngle;
    const { width, depth, height } = DIMENSIONS.gallery;
    const rotundaRadius = DIMENSIONS.rotunda.radius;
    const wingLength = DIMENSIONS.wing.length;
    const vestibuleDepth = DIMENSIONS.wing.vestibuleDepth ?? 6;
    // Gallery position after corridor + vestibule
    const centerDist = rotundaRadius + wingLength + vestibuleDepth + depth / 2;
    const centerX = Math.cos(angle) * centerDist;
    const centerZ = Math.sin(angle) * centerDist;
    
    // === FLOOR ===
    const floorGeo = new THREE.PlaneGeometry(width, depth);
    const floor = new THREE.Mesh(floorGeo, materials.floor);
    floor.rotation.x = -Math.PI / 2;
    floor.position.set(centerX, 0.01, centerZ);
    floor.rotation.z = angle;
    floor.receiveShadow = true;
    group.add(floor);
    
    // === SIDE WALLS (concrete) ===
    const wallThickness = 0.5;
    const sideWallGeo = new THREE.BoxGeometry(wallThickness, height, depth);
    
    const leftWall = new THREE.Mesh(sideWallGeo, materials.concrete);
    leftWall.name = `wall-gallery-${colony}-left`;
    leftWall.userData.occludes = true;
    leftWall.position.set(
        centerX - Math.sin(angle) * width / 2,
        height / 2,
        centerZ + Math.cos(angle) * width / 2
    );
    leftWall.rotation.y = angle;
    group.add(leftWall);
    
    const rightWall = new THREE.Mesh(sideWallGeo, materials.concrete);
    rightWall.name = `wall-gallery-${colony}-right`;
    rightWall.userData.occludes = true;
    rightWall.position.set(
        centerX + Math.sin(angle) * width / 2,
        height / 2,
        centerZ - Math.cos(angle) * width / 2
    );
    rightWall.rotation.y = angle;
    group.add(rightWall);
    
    // === CEILING ===
    const ceilingGeo = new THREE.PlaneGeometry(width, depth);
    const ceiling = new THREE.Mesh(ceilingGeo, materials.ceiling);
    ceiling.userData.occludes = true;
    ceiling.rotation.x = Math.PI / 2;
    ceiling.rotation.z = angle;
    ceiling.position.set(centerX, height, centerZ);
    group.add(ceiling);
    
    // === WING-SPECIFIC ACCENT (the differentiator) ===
    const backWallPos = {
        x: centerX + Math.cos(angle) * depth / 2,
        z: centerZ + Math.sin(angle) * depth / 2
    };
    
    switch (colony) {
        case 'spark': {
            // COPPER-CLAD ACCENT WALL (warm reflections)
            const copperMat = new THREE.MeshStandardMaterial({
                color: 0xB87333,
                metalness: 0.9,
                roughness: 0.25
            });
            const copperWall = new THREE.Mesh(
                new THREE.BoxGeometry(width, height, wallThickness),
                copperMat
            );
            copperWall.position.set(backWallPos.x, height / 2, backWallPos.z);
            copperWall.rotation.y = angle;
            group.add(copperWall);
            break;
        }
        
        case 'forge': {
            // BRASS INLAY FLOOR + warm metal wall
            const brassMat = new THREE.MeshStandardMaterial({
                color: 0xD4AF37,
                metalness: 0.85,
                roughness: 0.2
            });
            
            // Brass threshold inlay
            const inlayGeo = new THREE.RingGeometry(2, 4, 6);
            const inlay = new THREE.Mesh(inlayGeo, brassMat);
            inlay.rotation.x = -Math.PI / 2;
            inlay.position.set(centerX, 0.02, centerZ);
            group.add(inlay);
            
            // Brass accent wall
            const brassWall = new THREE.Mesh(
                new THREE.BoxGeometry(width, height, wallThickness),
                brassMat
            );
            brassWall.position.set(backWallPos.x, height / 2, backWallPos.z);
            brassWall.rotation.y = angle;
            group.add(brassWall);
            break;
        }
        
        case 'flow': {
            // REFLECTION POOL (dynamic env map reflection)
            const waterMat = createFlowPoolMaterial({ color: 0x4ECDC4 });
            const poolGeo = new THREE.CircleGeometry(6, 32);
            const pool = new THREE.Mesh(poolGeo, waterMat);
            pool.rotation.x = -Math.PI / 2;
            pool.position.set(centerX, 0.02, centerZ);
            group.add(pool);
            
            // Glass back wall
            const glassWall = materials.glass.clone();
            glassWall.color = new THREE.Color(0x4ECDC4);
            const backWall = new THREE.Mesh(
                new THREE.BoxGeometry(width, height, wallThickness),
                glassWall
            );
            backWall.position.set(backWallPos.x, height / 2, backWallPos.z);
            backWall.rotation.y = angle;
            group.add(backWall);
            break;
        }
        
        case 'nexus': {
            // PERFORATED WALL (network pattern, light passes through)
            const perfMat = new THREE.MeshStandardMaterial({
                color: 0x9B7EBD,
                metalness: 0.5,
                roughness: 0.4
            });
            
            // Create perforated effect with multiple boxes
            const gridSize = 8;
            const cellSize = width / gridSize;
            for (let x = 0; x < gridSize; x++) {
                for (let y = 0; y < gridSize; y++) {
                    // Skip some cells to create perforation pattern
                    if ((x + y) % 3 === 0) continue;
                    
                    const cell = new THREE.Mesh(
                        new THREE.BoxGeometry(cellSize * 0.8, (height / gridSize) * 0.8, wallThickness),
                        perfMat
                    );
                    const offsetX = (x - gridSize / 2 + 0.5) * cellSize;
                    const offsetY = (y + 0.5) * (height / gridSize);
                    
                    cell.position.set(
                        backWallPos.x - Math.sin(angle) * offsetX,
                        offsetY,
                        backWallPos.z + Math.cos(angle) * offsetX
                    );
                    cell.rotation.y = angle;
                    group.add(cell);
                }
            }
            break;
        }
        
        case 'beacon': {
            // VERTICAL WINDOW SLOT (lighthouse reference)
            const backWallMat = materials.concrete.clone();
            const backWall = new THREE.Mesh(
                new THREE.BoxGeometry(width, height, wallThickness),
                backWallMat
            );
            backWall.position.set(backWallPos.x, height / 2, backWallPos.z);
            backWall.rotation.y = angle;
            group.add(backWall);
            
            // Vertical light slot
            const slotMat = new THREE.MeshBasicMaterial({
                color: 0xF59E0B,
                transparent: true,
                opacity: 0.8
            });
            const slot = new THREE.Mesh(
                new THREE.BoxGeometry(1, height * 0.9, 0.1),
                slotMat
            );
            slot.position.set(backWallPos.x, height / 2, backWallPos.z);
            slot.rotation.y = angle;
            group.add(slot);
            break;
        }
        
        case 'grove': {
            // GREEN TEXTURED WALL (living wall reference)
            const greenMat = new THREE.MeshStandardMaterial({
                color: 0x4A7A4C,
                roughness: 0.9,
                metalness: 0.0
            });
            const greenWall = new THREE.Mesh(
                new THREE.BoxGeometry(width, height, wallThickness),
                greenMat
            );
            greenWall.position.set(backWallPos.x, height / 2, backWallPos.z);
            greenWall.rotation.y = angle;
            group.add(greenWall);
            
            // Subtle vine pattern (vertical lines)
            const vineMat = new THREE.MeshBasicMaterial({
                color: 0x7EB77F,
                transparent: true,
                opacity: 0.3
            });
            for (let i = 0; i < 5; i++) {
                const vine = new THREE.Mesh(
                    new THREE.BoxGeometry(0.2, height, 0.1),
                    vineMat
                );
                const offset = (i - 2) * (width / 5);
                vine.position.set(
                    backWallPos.x - Math.sin(angle) * offset,
                    height / 2,
                    backWallPos.z + Math.cos(angle) * offset
                );
                vine.rotation.y = angle;
                group.add(vine);
            }
            break;
        }
        
        case 'crystal': {
            const crystalMat = createCrystalMaterial({
                color: 0x67D4E4,
                transmission: 0.7,
                thickness: 1,
                roughness: 0.05,
                dispersion: 0.12,
                iridescenceIntensity: 0.5
            });
            for (let i = 0; i < 7; i++) {
                const facet = new THREE.Mesh(
                    new THREE.BoxGeometry(width / 7, height, wallThickness),
                    crystalMat.clone()
                );
                const offset = (i - 3) * (width / 7);
                const angleOffset = (i - 3) * 0.1;  // Slight angle variation
                
                facet.position.set(
                    backWallPos.x - Math.sin(angle) * offset,
                    height / 2,
                    backWallPos.z + Math.cos(angle) * offset
                );
                facet.rotation.y = angle + angleOffset;
                group.add(facet);
            }
            break;
        }
    }
    
    // === TRIANGULAR SKYLIGHT (Pei touch - all galleries) ===
    const skylightSize = Math.min(width, depth) * 0.3;
    const skylightGeo = new THREE.ConeGeometry(skylightSize, 2, 3, 1, true);
    const skylightMat = new THREE.MeshBasicMaterial({
        color: 0x88AACC,
        side: THREE.DoubleSide,
        transparent: true,
        opacity: 0.3
    });
    const skylight = new THREE.Mesh(skylightGeo, skylightMat);
    skylight.position.set(centerX, height + 1, centerZ);
    skylight.rotation.x = Math.PI;
    group.add(skylight);
    
    return group;
}

// ═══════════════════════════════════════════════════════════════════════════
// VESTIBULE
// ═══════════════════════════════════════════════════════════════════════════

export function createVestibule(materials) {
    const group = new THREE.Group();
    group.name = 'vestibule';
    
    const { width, depth, height } = DIMENSIONS.vestibule;
    const rotundaRadius = DIMENSIONS.rotunda.radius;
    
    // Position outside rotunda at main entrance (BUILDING.entranceWorldDirection)
    const angle = BUILDING.entranceWorldDirection;
    const centerX = Math.cos(angle) * (rotundaRadius + depth / 2 + 2);
    const centerZ = Math.sin(angle) * (rotundaRadius + depth / 2 + 2);
    
    // Floor
    const floorGeo = new THREE.PlaneGeometry(width, depth);
    const floor = new THREE.Mesh(floorGeo, materials.floor);
    floor.rotation.x = -Math.PI / 2;
    floor.position.set(centerX, 0.01, centerZ);
    floor.receiveShadow = true;
    group.add(floor);
    
    // Walls
    const wallGeo = new THREE.BoxGeometry(width, height, 0.5);
    const backWall = new THREE.Mesh(wallGeo, materials.concrete);
    backWall.name = 'wall-vestibule-back';
    backWall.userData.occludes = true;
    backWall.position.set(centerX, height / 2, centerZ - depth / 2);
    group.add(backWall);
    
    // Side walls
    const sideGeo = new THREE.BoxGeometry(0.5, height, depth);
    const leftWall = new THREE.Mesh(sideGeo, materials.concrete);
    leftWall.name = 'wall-vestibule-left';
    leftWall.userData.occludes = true;
    leftWall.position.set(centerX - width / 2, height / 2, centerZ);
    group.add(leftWall);
    
    const rightWall = new THREE.Mesh(sideGeo, materials.concrete);
    rightWall.name = 'wall-vestibule-right';
    rightWall.userData.occludes = true;
    rightWall.position.set(centerX + width / 2, height / 2, centerZ);
    group.add(rightWall);
    
    // Ceiling
    const ceilingGeo = new THREE.PlaneGeometry(width, depth);
    const ceiling = new THREE.Mesh(ceilingGeo, materials.ceiling);
    ceiling.userData.occludes = true;
    ceiling.rotation.x = Math.PI / 2;
    ceiling.position.set(centerX, height, centerZ);
    group.add(ceiling);
    
    return group;
}

// ═══════════════════════════════════════════════════════════════════════════
// MUSEUM ASSEMBLY
// ═══════════════════════════════════════════════════════════════════════════

export function createMuseum() {
    const group = new THREE.Group();
    group.name = 'museum';
    
    // Create materials
    const materials = createMuseumMaterials();
    
    // Aliases for compatibility
    materials.wall = materials.concrete;
    materials.wallAccent = materials.concrete;
    materials.baseboard = materials.steel;
    materials.rib = materials.concrete;
    materials.floorReflective = materials.floor;
    
    // Central rotunda
    const rotunda = createRotunda(materials);
    group.add(rotunda);
    
    // Store references for animation
    group.userData.rotunda = rotunda;
    group.userData.materials = materials;
    
    // 7 wings (corridor + vestibule + gallery each)
    COLONY_ORDER.forEach(colony => {
        const wing = createWing(colony, materials);
        group.add(wing);
        const vestibule = createWingVestibule(colony, materials);
        group.add(vestibule);
        const data = COLONY_DATA[colony];
        data.categories.forEach(cat => {
            const gallery = createGalleryRoom(colony, cat, materials);
            group.add(gallery);
        });
    });
    
    // Vestibule
    const vestibule = createVestibule(materials);
    group.add(vestibule);
    
    console.log('Museum created: Pei/Wright/Gehry architecture');
    
    return group;
}

// ═══════════════════════════════════════════════════════════════════════════
// ANIMATION (minimal - just Fano rotation)
// ═══════════════════════════════════════════════════════════════════════════

export function animateFanoSculpture(sculpture, time) {
    if (!sculpture) return;
    // Slow rotation: 1 revolution per 7 minutes (420 seconds)
    sculpture.rotation.y = (time / 420) * Math.PI * 2;
}

// Legacy compatibility stubs
export function createFanoSculpture(scale) {
    const materials = createMuseumMaterials();
    return createSimplifiedFano(materials.steel);
}

export function animateHopfProjection() {}
