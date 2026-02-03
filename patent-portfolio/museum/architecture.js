/**
 * Patent Museum Architecture
 * ==========================
 * 
 * The Fano Rotunda - a central hall with 7 radiating wings,
 * each representing a colony and containing category galleries.
 * 
 * h(x) ≥ 0 always
 */

import * as THREE from 'three';

// ═══════════════════════════════════════════════════════════════════════════
// COLONY COLORS & WING DATA
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
// MUSEUM DIMENSIONS
// ═══════════════════════════════════════════════════════════════════════════

export const DIMENSIONS = {
    // Central Rotunda
    rotunda: {
        radius: 20,
        height: 25,
        floorY: 0,
        domeStart: 15
    },
    
    // Wing corridors
    wing: {
        width: 12,
        length: 40,
        height: 8,
        entranceWidth: 8
    },
    
    // Gallery rooms (at end of each wing)
    gallery: {
        width: 25,
        depth: 30,
        height: 10
    },
    
    // Entry vestibule
    vestibule: {
        width: 10,
        depth: 15,
        height: 6
    }
};

// ═══════════════════════════════════════════════════════════════════════════
// MATERIALS
// ═══════════════════════════════════════════════════════════════════════════

export function createMuseumMaterials() {
    return {
        // Floor materials
        floor: new THREE.MeshStandardMaterial({
            color: 0x0A0A0F,
            metalness: 0.8,
            roughness: 0.2,
            envMapIntensity: 0.5
        }),
        
        floorReflective: new THREE.MeshPhysicalMaterial({
            color: 0x050510,
            metalness: 0.95,
            roughness: 0.05,
            clearcoat: 1.0,
            clearcoatRoughness: 0.1,
            reflectivity: 1.0
        }),
        
        // Wall materials - enhanced with depth
        wall: new THREE.MeshPhysicalMaterial({
            color: 0x12101A,
            metalness: 0.15,
            roughness: 0.75,
            clearcoat: 0.1,
            clearcoatRoughness: 0.8
        }),
        
        wallAccent: new THREE.MeshPhysicalMaterial({
            color: 0x1A1820,
            metalness: 0.3,
            roughness: 0.6,
            clearcoat: 0.3
        }),
        
        // Baseboard/trim material
        baseboard: new THREE.MeshPhysicalMaterial({
            color: 0x0A080D,
            metalness: 0.4,
            roughness: 0.3,
            clearcoat: 0.5
        }),
        
        // Vertical rib material
        rib: new THREE.MeshStandardMaterial({
            color: 0x0E0C14,
            metalness: 0.2,
            roughness: 0.6
        }),
        
        // Ceiling
        ceiling: new THREE.MeshStandardMaterial({
            color: 0x0D0A0F,
            metalness: 0.2,
            roughness: 0.9,
            side: THREE.BackSide
        }),
        
        // Glass/crystal
        glass: new THREE.MeshPhysicalMaterial({
            color: 0xFFFFFF,
            metalness: 0,
            roughness: 0,
            transmission: 0.95,
            thickness: 0.5,
            transparent: true,
            opacity: 0.3
        }),
        
        // Trim/accent lighting
        trim: new THREE.MeshBasicMaterial({
            color: 0x67D4E4,
            transparent: true,
            opacity: 0.8
        })
    };
}

// ═══════════════════════════════════════════════════════════════════════════
// CENTRAL ROTUNDA
// ═══════════════════════════════════════════════════════════════════════════

export function createRotunda(materials) {
    const group = new THREE.Group();
    group.name = 'rotunda';
    
    const { radius, height, domeStart } = DIMENSIONS.rotunda;
    
    // Floor - reflective black marble
    const floorGeo = new THREE.CircleGeometry(radius, 64);
    const floor = new THREE.Mesh(floorGeo, materials.floorReflective);
    floor.rotation.x = -Math.PI / 2;
    floor.receiveShadow = true;
    floor.name = 'rotunda-floor';
    group.add(floor);
    
    // Floor pattern - E8 lattice hint (concentric rings + radials)
    const patternGroup = createFloorPattern(radius);
    group.add(patternGroup);
    
    // Cylindrical walls (with openings for wings)
    const wallGroup = createRotundaWalls(radius, height, materials);
    group.add(wallGroup);
    
    // Dome ceiling
    const dome = createDome(radius, height, domeStart, materials);
    group.add(dome);
    
    // Central Fano Plane sculpture
    const fanoSculpture = createFanoSculpture();
    fanoSculpture.position.y = 3;
    group.add(fanoSculpture);
    
    // Ambient lighting
    const ambientRing = createAmbientLightRing(radius * 0.8, 12);
    ambientRing.position.y = height - 2;
    group.add(ambientRing);
    
    return group;
}

function createFloorPattern(radius) {
    const group = new THREE.Group();
    group.name = 'floor-pattern';
    
    // Primary lines - more visible (opacity 0.25)
    const lineMaterial = new THREE.LineBasicMaterial({
        color: 0x67D4E4,
        transparent: true,
        opacity: 0.25
    });
    
    // Emissive glow layer (wider, more subtle)
    const glowMaterial = new THREE.LineBasicMaterial({
        color: 0x67D4E4,
        transparent: true,
        opacity: 0.08,
        linewidth: 2
    });
    
    // Concentric circles (8 for E8 reference)
    for (let i = 1; i <= 8; i++) {
        const r = (radius * i) / 9;
        const points = [];
        for (let j = 0; j <= 64; j++) {
            const angle = (j / 64) * Math.PI * 2;
            points.push(new THREE.Vector3(Math.cos(angle) * r, 0.01, Math.sin(angle) * r));
        }
        const geometry = new THREE.BufferGeometry().setFromPoints(points);
        const circle = new THREE.Line(geometry, lineMaterial);
        group.add(circle);
        
        // Add glow layer
        const glowGeometry = new THREE.BufferGeometry().setFromPoints(points.map(p => 
            new THREE.Vector3(p.x, 0.005, p.z)
        ));
        const glowCircle = new THREE.Line(glowGeometry, glowMaterial);
        group.add(glowCircle);
    }
    
    // Radial lines (7 for Fano + 7 more)
    for (let i = 0; i < 14; i++) {
        const angle = (i / 14) * Math.PI * 2;
        const points = [
            new THREE.Vector3(0, 0.01, 0),
            new THREE.Vector3(Math.cos(angle) * radius, 0.01, Math.sin(angle) * radius)
        ];
        const geometry = new THREE.BufferGeometry().setFromPoints(points);
        const line = new THREE.Line(geometry, lineMaterial);
        group.add(line);
        
        // Add glow layer for radial lines
        const glowPoints = [
            new THREE.Vector3(0, 0.005, 0),
            new THREE.Vector3(Math.cos(angle) * radius, 0.005, Math.sin(angle) * radius)
        ];
        const glowGeometry = new THREE.BufferGeometry().setFromPoints(glowPoints);
        const glowLine = new THREE.Line(glowGeometry, glowMaterial);
        group.add(glowLine);
    }
    
    // Add center glow point
    const centerGeo = new THREE.CircleGeometry(0.5, 32);
    const centerMat = new THREE.MeshBasicMaterial({
        color: 0x67D4E4,
        transparent: true,
        opacity: 0.2
    });
    const centerGlow = new THREE.Mesh(centerGeo, centerMat);
    centerGlow.rotation.x = -Math.PI / 2;
    centerGlow.position.y = 0.02;
    group.add(centerGlow);
    
    return group;
}

function createRotundaWalls(radius, height, materials) {
    const group = new THREE.Group();
    group.name = 'rotunda-walls';
    
    // Create wall segments between wing openings
    const wingOpeningAngle = Math.PI / 12; // Opening width in radians
    
    COLONY_ORDER.forEach((colony, i) => {
        const data = COLONY_DATA[colony];
        const startAngle = data.wingAngle + wingOpeningAngle;
        const endAngle = data.wingAngle + (Math.PI * 2 / 7) - wingOpeningAngle;
        
        // Wall segment
        const segmentAngle = endAngle - startAngle;
        const wallGeo = new THREE.CylinderGeometry(
            radius, radius, height,
            16, 1, true,
            startAngle, segmentAngle
        );
        const wall = new THREE.Mesh(wallGeo, materials.wall);
        wall.position.y = height / 2;
        group.add(wall);
        
        // Colony accent strip at top of wall - ENLARGED (0.8m height)
        const accentGeo = new THREE.CylinderGeometry(
            radius + 0.08, radius + 0.08, 0.8,
            16, 1, true,
            startAngle, segmentAngle
        );
        const accentMat = new THREE.MeshBasicMaterial({
            color: data.hex,
            transparent: true,
            opacity: 0.7
        });
        const accent = new THREE.Mesh(accentGeo, accentMat);
        accent.position.y = height - 0.6;
        group.add(accent);
        
        // Subtle glow behind accent strip
        const glowGeo = new THREE.CylinderGeometry(
            radius + 0.02, radius + 0.02, 1.2,
            16, 1, true,
            startAngle, segmentAngle
        );
        const glowMat = new THREE.MeshBasicMaterial({
            color: data.hex,
            transparent: true,
            opacity: 0.15,
            side: THREE.BackSide
        });
        const glow = new THREE.Mesh(glowGeo, glowMat);
        glow.position.y = height - 0.6;
        group.add(glow);
        
        // Baseboard at bottom
        const baseboardGeo = new THREE.CylinderGeometry(
            radius + 0.1, radius + 0.1, 0.3,
            16, 1, true,
            startAngle, segmentAngle
        );
        const baseboard = new THREE.Mesh(baseboardGeo, materials.baseboard);
        baseboard.position.y = 0.15;
        group.add(baseboard);
        
        // Vertical ribs/panels (3 per segment)
        const numRibs = 3;
        for (let r = 0; r < numRibs; r++) {
            const ribAngle = startAngle + segmentAngle * ((r + 0.5) / numRibs);
            const ribX = Math.cos(ribAngle) * (radius + 0.05);
            const ribZ = Math.sin(ribAngle) * (radius + 0.05);
            
            const ribGeo = new THREE.BoxGeometry(0.08, height - 1.5, 0.4);
            const rib = new THREE.Mesh(ribGeo, materials.rib);
            rib.position.set(ribX, height / 2 - 0.3, ribZ);
            rib.rotation.y = -ribAngle + Math.PI / 2;
            group.add(rib);
        }
    });
    
    return group;
}

function createDome(radius, height, domeStart, materials) {
    const group = new THREE.Group();
    group.name = 'dome';
    
    // Hemisphere dome
    const domeRadius = radius;
    const domeGeo = new THREE.SphereGeometry(
        domeRadius, 64, 32,
        0, Math.PI * 2,
        0, Math.PI / 2
    );
    const dome = new THREE.Mesh(domeGeo, materials.ceiling);
    dome.position.y = domeStart;
    dome.scale.y = (height - domeStart) / domeRadius;
    group.add(dome);
    
    // Hopf fibration projection on dome (simplified as glowing rings)
    const hopfGroup = createHopfProjection(domeRadius * 0.9, 7);
    hopfGroup.position.y = domeStart + 2;
    group.add(hopfGroup);
    
    return group;
}

function createHopfProjection(radius, numRings) {
    const group = new THREE.Group();
    group.name = 'hopf-projection';
    
    COLONY_ORDER.forEach((colony, i) => {
        const color = COLONY_DATA[colony].hex;
        const material = new THREE.MeshBasicMaterial({
            color: color,
            transparent: true,
            opacity: 0.4,
            side: THREE.DoubleSide
        });
        
        // Tilted torus ring
        const torusGeo = new THREE.TorusGeometry(radius * 0.3, 0.1, 16, 32);
        const torus = new THREE.Mesh(torusGeo, material);
        
        // Position around dome
        const angle = (i / 7) * Math.PI * 2;
        const tilt = Math.PI / 4 + (i * 0.2);
        
        torus.position.set(
            Math.cos(angle) * radius * 0.4,
            radius * 0.2 + Math.sin(i) * 2,
            Math.sin(angle) * radius * 0.4
        );
        torus.rotation.set(tilt, angle, 0);
        
        group.add(torus);
    });
    
    return group;
}

// ═══════════════════════════════════════════════════════════════════════════
// FANO PLANE SCULPTURE
// ═══════════════════════════════════════════════════════════════════════════

export function createFanoSculpture(scale = 3) {
    const group = new THREE.Group();
    group.name = 'fano-sculpture';
    
    // Fano plane points (7 points)
    const points = [
        [0, 2, 0],        // 0 - Spark (top)
        [-1.5, 0.5, 0.5], // 1 - Forge
        [1.5, 0.5, 0.5],  // 2 - Flow
        [-2, -1.5, 0],    // 3 - Nexus
        [0, -0.5, 1],     // 4 - Beacon (center front)
        [2, -1.5, 0],     // 5 - Grove
        [0, -2.5, -0.5]   // 6 - Crystal (bottom)
    ].map(p => new THREE.Vector3(p[0] * scale, p[1] * scale, p[2] * scale));
    
    // Fano lines (7 lines, each connecting 3 collinear points)
    const lines = [
        [0, 1, 3], [0, 2, 5], [0, 4, 6],
        [1, 2, 4], [1, 5, 6], [2, 3, 6], [3, 4, 5]
    ];
    
    // Create nodes (icosahedrons)
    COLONY_ORDER.forEach((colony, i) => {
        const color = COLONY_DATA[colony].hex;
        
        // Core
        const coreGeo = new THREE.IcosahedronGeometry(0.5, 2);
        const coreMat = new THREE.MeshPhysicalMaterial({
            color: color,
            emissive: color,
            emissiveIntensity: 0.5,
            metalness: 0.2,
            roughness: 0.3,
            clearcoat: 0.8
        });
        const core = new THREE.Mesh(coreGeo, coreMat);
        core.position.copy(points[i]);
        core.userData = { colony, index: i, type: 'fano-node' };
        group.add(core);
        
        // Glow
        const glowGeo = new THREE.IcosahedronGeometry(0.7, 1);
        const glowMat = new THREE.MeshBasicMaterial({
            color: color,
            transparent: true,
            opacity: 0.2,
            side: THREE.BackSide
        });
        const glow = new THREE.Mesh(glowGeo, glowMat);
        glow.position.copy(points[i]);
        group.add(glow);
    });
    
    // Create connecting lines
    lines.forEach((lineIndices, lineIdx) => {
        // Get colors from endpoints
        const color1 = COLONY_DATA[COLONY_ORDER[lineIndices[0]]].hex;
        const color2 = COLONY_DATA[COLONY_ORDER[lineIndices[2]]].hex;
        
        // Create curved line through 3 points
        const curve = new THREE.CatmullRomCurve3([
            points[lineIndices[0]],
            points[lineIndices[1]],
            points[lineIndices[2]]
        ]);
        
        const tubeGeo = new THREE.TubeGeometry(curve, 32, 0.08, 8, false);
        const tubeMat = new THREE.MeshBasicMaterial({
            color: new THREE.Color(color1).lerp(new THREE.Color(color2), 0.5),
            transparent: true,
            opacity: 0.6
        });
        const tube = new THREE.Mesh(tubeGeo, tubeMat);
        tube.userData = { type: 'fano-line', indices: lineIndices };
        group.add(tube);
    });
    
    // Slow rotation animation data
    group.userData.rotationSpeed = 0.1;
    
    return group;
}

// ═══════════════════════════════════════════════════════════════════════════
// WING CORRIDORS
// ═══════════════════════════════════════════════════════════════════════════

export function createWing(colony, materials) {
    const group = new THREE.Group();
    group.name = `wing-${colony}`;
    
    const data = COLONY_DATA[colony];
    const { width, length, height } = DIMENSIONS.wing;
    const { radius: rotundaRadius } = DIMENSIONS.rotunda;
    
    // Position wing radiating from rotunda
    const angle = data.wingAngle;
    
    // Floor
    const floorGeo = new THREE.PlaneGeometry(width, length);
    const floor = new THREE.Mesh(floorGeo, materials.floor);
    floor.rotation.x = -Math.PI / 2;
    floor.position.set(0, 0, length / 2);
    floor.receiveShadow = true;
    group.add(floor);
    
    // Floor accent line (colony color)
    const accentLineGeo = new THREE.PlaneGeometry(0.2, length);
    const accentLineMat = new THREE.MeshBasicMaterial({
        color: data.hex,
        transparent: true,
        opacity: 0.4
    });
    const accentLine = new THREE.Mesh(accentLineGeo, accentLineMat);
    accentLine.rotation.x = -Math.PI / 2;
    accentLine.position.set(0, 0.01, length / 2);
    group.add(accentLine);
    
    // Left wall
    const leftWallGeo = new THREE.BoxGeometry(0.3, height, length);
    const leftWall = new THREE.Mesh(leftWallGeo, materials.wall);
    leftWall.position.set(-width / 2, height / 2, length / 2);
    group.add(leftWall);
    
    // Right wall
    const rightWall = leftWall.clone();
    rightWall.position.set(width / 2, height / 2, length / 2);
    group.add(rightWall);
    
    // Ceiling
    const ceilingGeo = new THREE.PlaneGeometry(width, length);
    const ceiling = new THREE.Mesh(ceilingGeo, materials.ceiling);
    ceiling.rotation.x = Math.PI / 2;
    ceiling.position.set(0, height, length / 2);
    group.add(ceiling);
    
    // Accent lighting strips along ceiling edges
    const lightStripGeo = new THREE.BoxGeometry(0.1, 0.1, length);
    const lightStripMat = new THREE.MeshBasicMaterial({
        color: data.hex,
        transparent: true,
        opacity: 0.7
    });
    
    const leftStrip = new THREE.Mesh(lightStripGeo, lightStripMat);
    leftStrip.position.set(-width / 2 + 0.5, height - 0.1, length / 2);
    group.add(leftStrip);
    
    const rightStrip = leftStrip.clone();
    rightStrip.position.set(width / 2 - 0.5, height - 0.1, length / 2);
    group.add(rightStrip);
    
    // Wing label at entrance
    const labelGroup = createWingLabel(data.name, data.hex, width);
    labelGroup.position.set(0, height - 1, 2);
    group.add(labelGroup);
    
    // Position and rotate entire wing
    group.position.set(
        Math.cos(angle) * rotundaRadius,
        0,
        Math.sin(angle) * rotundaRadius
    );
    group.rotation.y = -angle + Math.PI / 2;
    
    // Store colony reference
    group.userData = { colony, categories: data.categories };
    
    return group;
}

function createWingLabel(name, color, width) {
    const group = new THREE.Group();
    
    // Create text using canvas texture
    const canvas = document.createElement('canvas');
    canvas.width = 512;
    canvas.height = 128;
    const ctx = canvas.getContext('2d');
    
    // Background
    ctx.fillStyle = 'rgba(18, 16, 26, 0.9)';
    ctx.fillRect(0, 0, 512, 128);
    
    // Border
    ctx.strokeStyle = `#${color.toString(16).padStart(6, '0')}`;
    ctx.lineWidth = 4;
    ctx.strokeRect(4, 4, 504, 120);
    
    // Text
    ctx.fillStyle = '#F5F0E8';
    ctx.font = '600 48px "IBM Plex Sans", sans-serif';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillText(`${name.toUpperCase()} WING`, 256, 64);
    
    const texture = new THREE.CanvasTexture(canvas);
    texture.needsUpdate = true;
    
    const planeGeo = new THREE.PlaneGeometry(width * 0.8, width * 0.2);
    const planeMat = new THREE.MeshBasicMaterial({
        map: texture,
        transparent: true
    });
    const plane = new THREE.Mesh(planeGeo, planeMat);
    group.add(plane);
    
    return group;
}

// ═══════════════════════════════════════════════════════════════════════════
// GALLERY ROOMS
// ═══════════════════════════════════════════════════════════════════════════

export function createGalleryRoom(colony, categoryId, materials) {
    const group = new THREE.Group();
    group.name = `gallery-${colony}-${categoryId}`;
    
    const { width, depth, height } = DIMENSIONS.gallery;
    const data = COLONY_DATA[colony];
    
    // Floor
    const floorGeo = new THREE.PlaneGeometry(width, depth);
    const floor = new THREE.Mesh(floorGeo, materials.floorReflective);
    floor.rotation.x = -Math.PI / 2;
    floor.receiveShadow = true;
    group.add(floor);
    
    // Walls
    const wallGeo = new THREE.BoxGeometry(0.3, height, depth);
    
    // Left wall
    const leftWall = new THREE.Mesh(wallGeo, materials.wall);
    leftWall.position.set(-width / 2, height / 2, 0);
    group.add(leftWall);
    
    // Right wall
    const rightWall = new THREE.Mesh(wallGeo, materials.wall);
    rightWall.position.set(width / 2, height / 2, 0);
    group.add(rightWall);
    
    // Back wall
    const backWallGeo = new THREE.BoxGeometry(width, height, 0.3);
    const backWall = new THREE.Mesh(backWallGeo, materials.wall);
    backWall.position.set(0, height / 2, depth / 2);
    group.add(backWall);
    
    // Ceiling
    const ceilingGeo = new THREE.PlaneGeometry(width, depth);
    const ceiling = new THREE.Mesh(ceilingGeo, materials.ceiling);
    ceiling.rotation.x = Math.PI / 2;
    ceiling.position.y = height;
    group.add(ceiling);
    
    // Accent lighting
    const accentHeight = height - 0.5;
    const accentMat = new THREE.MeshBasicMaterial({
        color: data.hex,
        transparent: true,
        opacity: 0.5
    });
    
    // Perimeter accent line
    const accentPoints = [
        new THREE.Vector3(-width/2 + 0.5, accentHeight, -depth/2 + 0.5),
        new THREE.Vector3(-width/2 + 0.5, accentHeight, depth/2 - 0.5),
        new THREE.Vector3(width/2 - 0.5, accentHeight, depth/2 - 0.5),
        new THREE.Vector3(width/2 - 0.5, accentHeight, -depth/2 + 0.5),
        new THREE.Vector3(-width/2 + 0.5, accentHeight, -depth/2 + 0.5)
    ];
    
    const accentLineGeo = new THREE.BufferGeometry().setFromPoints(accentPoints);
    const accentLine = new THREE.Line(accentLineGeo, new THREE.LineBasicMaterial({
        color: data.hex,
        transparent: true,
        opacity: 0.6
    }));
    group.add(accentLine);
    
    // Store data
    group.userData = { colony, categoryId, artworkSlots: [] };
    
    return group;
}

// ═══════════════════════════════════════════════════════════════════════════
// ENTRY VESTIBULE
// ═══════════════════════════════════════════════════════════════════════════

export function createVestibule(materials) {
    const group = new THREE.Group();
    group.name = 'vestibule';
    
    const { width, depth, height } = DIMENSIONS.vestibule;
    const { radius: rotundaRadius } = DIMENSIONS.rotunda;
    
    // Floor
    const floorGeo = new THREE.PlaneGeometry(width, depth);
    const floor = new THREE.Mesh(floorGeo, materials.floor);
    floor.rotation.x = -Math.PI / 2;
    floor.receiveShadow = true;
    group.add(floor);
    
    // Walls (left and right)
    const wallGeo = new THREE.BoxGeometry(0.3, height, depth);
    
    const leftWall = new THREE.Mesh(wallGeo, materials.wall);
    leftWall.position.set(-width / 2, height / 2, 0);
    group.add(leftWall);
    
    const rightWall = new THREE.Mesh(wallGeo, materials.wall);
    rightWall.position.set(width / 2, height / 2, 0);
    group.add(rightWall);
    
    // Entry archway (back of vestibule)
    const archGroup = createArchway(width, height, 0x67D4E4);
    archGroup.position.set(0, 0, -depth / 2);
    group.add(archGroup);
    
    // Ceiling
    const ceilingGeo = new THREE.PlaneGeometry(width, depth);
    const ceiling = new THREE.Mesh(ceilingGeo, materials.ceiling);
    ceiling.rotation.x = Math.PI / 2;
    ceiling.position.y = height;
    group.add(ceiling);
    
    // Title plaque
    const titlePlaque = createTitlePlaque();
    titlePlaque.position.set(0, height * 0.6, -depth / 2 + 1);
    group.add(titlePlaque);
    
    // Position vestibule outside rotunda
    group.position.set(0, 0, -rotundaRadius - depth / 2);
    
    return group;
}

function createArchway(width, height, color) {
    const group = new THREE.Group();
    
    // Arch shape using CatmullRomCurve
    const archPoints = [];
    for (let i = 0; i <= 20; i++) {
        const t = i / 20;
        const angle = Math.PI * t;
        archPoints.push(new THREE.Vector3(
            Math.cos(angle) * (width / 2 - 0.5),
            Math.sin(angle) * (height - 1) + 1,
            0
        ));
    }
    
    const archCurve = new THREE.CatmullRomCurve3(archPoints);
    const tubeGeo = new THREE.TubeGeometry(archCurve, 32, 0.15, 8, false);
    const tubeMat = new THREE.MeshBasicMaterial({
        color: color,
        transparent: true,
        opacity: 0.8
    });
    const arch = new THREE.Mesh(tubeGeo, tubeMat);
    group.add(arch);
    
    return group;
}

function createTitlePlaque() {
    const group = new THREE.Group();
    
    // Create canvas texture
    const canvas = document.createElement('canvas');
    canvas.width = 1024;
    canvas.height = 512;
    const ctx = canvas.getContext('2d');
    
    // Background
    ctx.fillStyle = 'rgba(7, 6, 11, 0.95)';
    ctx.fillRect(0, 0, 1024, 512);
    
    // Border
    ctx.strokeStyle = '#67D4E4';
    ctx.lineWidth = 4;
    ctx.strokeRect(20, 20, 984, 472);
    
    // Title
    ctx.fillStyle = '#F5F0E8';
    ctx.font = '700 72px "Orbitron", sans-serif';
    ctx.textAlign = 'center';
    ctx.fillText('鏡', 512, 120);
    
    ctx.font = '500 48px "IBM Plex Sans", sans-serif';
    ctx.fillText('PATENT PORTFOLIO', 512, 200);
    
    // Subtitle
    ctx.fillStyle = '#9E9994';
    ctx.font = '400 28px "IBM Plex Sans", sans-serif';
    ctx.fillText('54 Patentable Innovations', 512, 280);
    
    // h(x) >= 0
    ctx.fillStyle = '#67D4E4';
    ctx.font = '500 36px "IBM Plex Mono", monospace';
    ctx.fillText('h(x) ≥ 0 always', 512, 380);
    
    const texture = new THREE.CanvasTexture(canvas);
    
    const planeGeo = new THREE.PlaneGeometry(6, 3);
    const planeMat = new THREE.MeshBasicMaterial({
        map: texture,
        transparent: true
    });
    const plane = new THREE.Mesh(planeGeo, planeMat);
    group.add(plane);
    
    return group;
}

// ═══════════════════════════════════════════════════════════════════════════
// AMBIENT LIGHTING
// ═══════════════════════════════════════════════════════════════════════════

function createAmbientLightRing(radius, numLights) {
    const group = new THREE.Group();
    group.name = 'ambient-light-ring';
    
    for (let i = 0; i < numLights; i++) {
        const angle = (i / numLights) * Math.PI * 2;
        const x = Math.cos(angle) * radius;
        const z = Math.sin(angle) * radius;
        
        // Point light
        const light = new THREE.PointLight(0xF5F0E8, 0.5, 30, 2);
        light.position.set(x, 0, z);
        group.add(light);
        
        // Visual indicator (small glowing sphere)
        const sphereGeo = new THREE.SphereGeometry(0.2, 16, 16);
        const sphereMat = new THREE.MeshBasicMaterial({
            color: 0xF5F0E8,
            transparent: true,
            opacity: 0.6
        });
        const sphere = new THREE.Mesh(sphereGeo, sphereMat);
        sphere.position.set(x, 0, z);
        group.add(sphere);
    }
    
    return group;
}

// ═══════════════════════════════════════════════════════════════════════════
// COMPLETE MUSEUM ASSEMBLY
// ═══════════════════════════════════════════════════════════════════════════

export function createMuseum() {
    const museum = new THREE.Group();
    museum.name = 'patent-museum';
    
    // Create materials
    const materials = createMuseumMaterials();
    
    // Central rotunda
    const rotunda = createRotunda(materials);
    museum.add(rotunda);
    
    // Entry vestibule
    const vestibule = createVestibule(materials);
    museum.add(vestibule);
    
    // Wing corridors
    const wings = {};
    COLONY_ORDER.forEach(colony => {
        const wing = createWing(colony, materials);
        wings[colony] = wing;
        museum.add(wing);
    });
    
    // Gallery rooms at the end of each wing
    const galleries = {};
    COLONY_ORDER.forEach(colony => {
        const data = COLONY_DATA[colony];
        const galleryGroup = new THREE.Group();
        galleryGroup.name = `galleries-${colony}`;
        
        // Create gallery for each category in this wing
        data.categories.forEach((categoryId, idx) => {
            const gallery = createGalleryRoom(colony, categoryId, materials);
            
            // Position gallery at end of wing
            const { radius } = DIMENSIONS.rotunda;
            const { length } = DIMENSIONS.wing;
            const { depth } = DIMENSIONS.gallery;
            
            // Gallery position: at end of wing corridor
            const distance = radius + length + depth / 2 + 2; // Extra 2m for archway
            const angle = data.wingAngle;
            
            gallery.position.set(
                Math.cos(angle) * distance,
                0,
                Math.sin(angle) * distance
            );
            
            // Rotate gallery to face wing
            gallery.rotation.y = -angle + Math.PI / 2;
            
            // Offset multiple galleries laterally
            if (data.categories.length > 1) {
                const lateralOffset = (idx - (data.categories.length - 1) / 2) * (DIMENSIONS.gallery.width + 4);
                const perpAngle = angle + Math.PI / 2;
                gallery.position.x += Math.cos(perpAngle) * lateralOffset;
                gallery.position.z += Math.sin(perpAngle) * lateralOffset;
            }
            
            galleryGroup.add(gallery);
        });
        
        // Create archway transition from wing to gallery
        const archway = createGalleryArchway(colony, materials);
        galleryGroup.add(archway);
        
        galleries[colony] = galleryGroup;
        museum.add(galleryGroup);
    });
    
    // Store references
    museum.userData = {
        materials,
        rotunda,
        vestibule,
        wings,
        galleries
    };
    
    return museum;
}

// Create archway transition between wing and gallery
function createGalleryArchway(colony, materials) {
    const group = new THREE.Group();
    group.name = `archway-${colony}`;
    
    const data = COLONY_DATA[colony];
    const { radius } = DIMENSIONS.rotunda;
    const { length, width, height } = DIMENSIONS.wing;
    
    // Position at end of wing
    const distance = radius + length;
    const angle = data.wingAngle;
    
    group.position.set(
        Math.cos(angle) * distance,
        0,
        Math.sin(angle) * distance
    );
    group.rotation.y = -angle + Math.PI / 2;
    
    // Archway frame
    const archWidth = width * 0.8;
    const archHeight = height * 0.9;
    const archDepth = 2;
    
    // Left pillar
    const pillarGeo = new THREE.BoxGeometry(0.5, archHeight, archDepth);
    const pillarMat = materials.wallAccent;
    
    const leftPillar = new THREE.Mesh(pillarGeo, pillarMat);
    leftPillar.position.set(-archWidth / 2, archHeight / 2, 0);
    group.add(leftPillar);
    
    // Right pillar
    const rightPillar = new THREE.Mesh(pillarGeo, pillarMat);
    rightPillar.position.set(archWidth / 2, archHeight / 2, 0);
    group.add(rightPillar);
    
    // Top arch
    const archGeo = new THREE.BoxGeometry(archWidth + 1, 0.5, archDepth);
    const arch = new THREE.Mesh(archGeo, pillarMat);
    arch.position.set(0, archHeight, 0);
    group.add(arch);
    
    // Colony-colored accent
    const accentGeo = new THREE.BoxGeometry(archWidth + 1.2, 0.15, archDepth + 0.2);
    const accentMat = new THREE.MeshBasicMaterial({
        color: data.hex,
        transparent: true,
        opacity: 0.6
    });
    const accent = new THREE.Mesh(accentGeo, accentMat);
    accent.position.set(0, archHeight + 0.3, 0);
    group.add(accent);
    
    // Floor connection
    const floorGeo = new THREE.PlaneGeometry(archWidth, archDepth);
    const floor = new THREE.Mesh(floorGeo, materials.floorReflective);
    floor.rotation.x = -Math.PI / 2;
    floor.position.y = 0.01;
    group.add(floor);
    
    return group;
}

// ═══════════════════════════════════════════════════════════════════════════
// ANIMATION HELPERS
// ═══════════════════════════════════════════════════════════════════════════

export function animateFanoSculpture(sculpture, time) {
    if (!sculpture) return;
    
    // Slow rotation
    sculpture.rotation.y = time * 0.1;
    
    // Pulse the nodes
    sculpture.children.forEach((child, i) => {
        if (child.userData?.type === 'fano-node') {
            const pulse = 1 + Math.sin(time * 2 + i * 0.9) * 0.1;
            child.scale.setScalar(pulse);
        }
    });
}

export function animateHopfProjection(projection, time) {
    if (!projection) return;
    
    projection.children.forEach((ring, i) => {
        ring.rotation.z = time * 0.3 + i * 0.5;
        ring.rotation.x = Math.sin(time * 0.2 + i) * 0.3 + Math.PI / 4;
    });
}
