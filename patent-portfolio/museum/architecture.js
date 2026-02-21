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
            side: THREE.DoubleSide
        }),
        concretePolished: createConcretePolishedMaterial(),

        // Architectural detail materials
        baseboard: new THREE.MeshStandardMaterial({
            color: 0x1A1818,
            roughness: 0.2,
            metalness: 0.3,
            side: THREE.DoubleSide
        }),
        ceilingCove: new THREE.MeshStandardMaterial({
            color: 0x2A2828,
            roughness: 0.95,
            metalness: 0.01,
            side: THREE.DoubleSide
        }),
        threshold: new THREE.MeshStandardMaterial({
            color: 0x3D3835,
            roughness: 0.1,
            metalness: 0.15,
            side: THREE.DoubleSide
        }),

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
    walls.userData.collidable = true;
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
        pos.setY(i, y * 0.75 + domeStart);  // Cathedral dome presence
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
// LIVING FANO CONSTELLATION — The centerpiece of the museum
// 7 colony crystals connected by light bridges, orbited by rings,
// wreathed in constellation dust, pulsing with consensus heartbeats.
// ═══════════════════════════════════════════════════════════════════════════

function createSimplifiedFano(steelMaterial) {
    // Redirects to the full constellation
    return createFanoConstellation(steelMaterial);
}

function createFanoConstellation(steelMaterial) {
    const group = new THREE.Group();
    group.name = 'fano-sculpture';
    
    const R = 4.0; // 4m radius — dramatic presence
    
    // === 3D VERTEX POSITIONS (not flat — reveal incidence structure) ===
    // Place vertices on a sphere with vertical spread for 3D depth
    const vertexPositions = [];
    for (let i = 0; i < 7; i++) {
        const angle = (i / 7) * Math.PI * 2 - Math.PI / 2;
        const elevation = Math.sin(i * 1.35) * R * 0.35; // vertical spread
        vertexPositions.push(new THREE.Vector3(
            Math.cos(angle) * R * 0.85,
            elevation,
            Math.sin(angle) * R * 0.85
        ));
    }
    
    // === FANO LINES (7 lines, each through 3 points) ===
    const fanoLines = [
        [0, 1, 3], [1, 2, 4], [2, 3, 5], [3, 4, 6],
        [4, 5, 0], [5, 6, 1], [6, 0, 2]
    ];
    
    // === CENTRAL NEXUS SPHERE — Kagami's core ===
    const nexusGeo = new THREE.IcosahedronGeometry(0.35, 2);
    const nexusMat = new THREE.MeshPhysicalMaterial({
        color: 0xFFFFFF, emissive: 0x67D4E4, emissiveIntensity: 0.6,
        metalness: 0.3, roughness: 0.1, transmission: 0.3,
        thickness: 0.5, clearcoat: 1.0
    });
    const nexus = new THREE.Mesh(nexusGeo, nexusMat);
    nexus.name = 'constellation-nexus';
    nexus.userData = { interactive: true, type: 'fano-nexus' };
    group.add(nexus);
    
    // Nexus inner glow
    const nexusGlowGeo = new THREE.IcosahedronGeometry(0.2, 1);
    const nexusGlow = new THREE.Mesh(nexusGlowGeo, new THREE.MeshBasicMaterial({
        color: 0xFFFFFF, transparent: true, opacity: 0.8
    }));
    nexusGlow.name = 'nexus-glow';
    group.add(nexusGlow);
    
    // Nexus wireframe halo
    const nexusHaloGeo = new THREE.IcosahedronGeometry(0.5, 1);
    const nexusHalo = new THREE.Mesh(nexusHaloGeo, new THREE.MeshBasicMaterial({
        color: 0x67D4E4, wireframe: true, transparent: true, opacity: 0.15
    }));
    nexusHalo.name = 'nexus-halo';
    group.add(nexusHalo);
    
    // === 7 COLONY CRYSTALS ===
    const colonyColors = [];
    COLONY_ORDER.forEach((colony, i) => {
        const data = COLONY_DATA[colony];
        const color = data.hex;
        colonyColors.push(color);
        
        const crystalGeo = new THREE.IcosahedronGeometry(0.25, 1);
        const crystalMat = new THREE.MeshPhysicalMaterial({
            color: color, emissive: color, emissiveIntensity: 0.4,
            metalness: 0.5, roughness: 0.15, clearcoat: 0.8,
            transmission: 0.2, thickness: 0.3
        });
        const crystal = new THREE.Mesh(crystalGeo, crystalMat);
        crystal.position.copy(vertexPositions[i]);
        crystal.name = `crystal-${colony}`;
        crystal.userData = { interactive: true, type: 'fano-node', colony: colony, idx: i };
        crystal.castShadow = true;
        group.add(crystal);
        
        // Crystal outer shell (wireframe)
        const shellGeo = new THREE.IcosahedronGeometry(0.35, 1);
        const shell = new THREE.Mesh(shellGeo, new THREE.MeshBasicMaterial({
            color: color, wireframe: true, transparent: true, opacity: 0.2
        }));
        shell.position.copy(vertexPositions[i]);
        shell.name = `crystal-shell-${colony}`;
        group.add(shell);
        
        // Colony name label (canvas sprite)
        const labelCanvas = document.createElement('canvas');
        const dpr = Math.min(window.devicePixelRatio || 1, 2);
        labelCanvas.width = 256 * dpr;
        labelCanvas.height = 48 * dpr;
        const lctx = labelCanvas.getContext('2d');
        lctx.scale(dpr, dpr);
        lctx.fillStyle = 'rgba(0,0,0,0)';
        lctx.fillRect(0, 0, 256, 48);
        lctx.fillStyle = `#${color.toString(16).padStart(6, '0')}`;
        lctx.font = "18px 'IBM Plex Sans', sans-serif";
        lctx.textAlign = 'center';
        lctx.textBaseline = 'middle';
        lctx.fillText(data.name, 128, 24);
        const labelTex = new THREE.CanvasTexture(labelCanvas);
        labelTex.minFilter = THREE.LinearFilter;
        const label = new THREE.Sprite(new THREE.SpriteMaterial({
            map: labelTex, transparent: true, depthWrite: false
        }));
        label.position.copy(vertexPositions[i]);
        label.position.y += 0.55;
        label.scale.set(1.2, 0.25, 1);
        group.add(label);
    });
    
    // === LIGHT BRIDGES (7 Fano lines as glowing tubes) ===
    fanoLines.forEach((line, lineIdx) => {
        // Each Fano line passes through 3 colony vertices
        // Draw curved bridge through all 3 points, arcing through center
        for (let seg = 0; seg < 2; seg++) {
            const a = vertexPositions[line[seg]];
            const b = vertexPositions[line[seg + 1]];
            const mid = a.clone().add(b).multiplyScalar(0.5);
            // Arc toward center for visual depth
            mid.multiplyScalar(0.6);
            mid.y += 0.3;
            
            const curve = new THREE.QuadraticBezierCurve3(a, mid, b);
            const tubeGeo = new THREE.TubeGeometry(curve, 24, 0.02, 8, false);
            
            // Blend colors of the two endpoint colonies
            const colorA = colonyColors[line[seg]];
            const colorB = colonyColors[line[seg + 1]];
            const blendColor = new THREE.Color(colorA).lerp(new THREE.Color(colorB), 0.5);
            
            const tubeMat = new THREE.MeshPhysicalMaterial({
                color: blendColor, emissive: blendColor, emissiveIntensity: 0.25,
                transparent: true, opacity: 0.6, metalness: 0.7, roughness: 0.2
            });
            const tube = new THREE.Mesh(tubeGeo, tubeMat);
            tube.name = `bridge-${lineIdx}-${seg}`;
            tube.castShadow = true;
            group.add(tube);
        }
    });
    
    // === 7 ORBITAL RINGS (orrery-style, different tilts) ===
    const fibonacciAngles = [0.38, 0.62, 1.0, 1.62, 2.62, 4.24, 6.85];
    COLONY_ORDER.forEach((colony, i) => {
        const data = COLONY_DATA[colony];
        const ringRadius = 2.8 + i * 0.25;
        const ringGeo = new THREE.TorusGeometry(ringRadius, 0.012, 8, 96);
        const ringMat = new THREE.MeshBasicMaterial({
            color: data.hex, transparent: true, opacity: 0.18
        });
        const ring = new THREE.Mesh(ringGeo, ringMat);
        ring.rotation.x = fibonacciAngles[i] * 0.4;
        ring.rotation.z = fibonacciAngles[i] * 0.25;
        ring.name = `orbital-ring-${colony}`;
        ring.userData = { colony, orbitSpeed: 0.02 + i * 0.005, tiltBase: ring.rotation.x };
        group.add(ring);
    });
    
    // === CONSTELLATION DUST (600 particles in nebula cloud) ===
    const dustCount = 600;
    const dustPositions = new Float32Array(dustCount * 3);
    const dustColors = new Float32Array(dustCount * 3);
    const dustSizes = new Float32Array(dustCount);
    
    for (let i = 0; i < dustCount; i++) {
        // Spherical distribution with bias toward orbital plane
        const theta = Math.random() * Math.PI * 2;
        const phi = (Math.random() - 0.5) * Math.PI * 0.7; // flattened
        const r = 1.5 + Math.random() * 3.5;
        dustPositions[i * 3] = Math.cos(theta) * Math.cos(phi) * r;
        dustPositions[i * 3 + 1] = Math.sin(phi) * r * 0.5; // compressed vertical
        dustPositions[i * 3 + 2] = Math.sin(theta) * Math.cos(phi) * r;
        
        // Color: blend of nearest colony colors
        const nearestColony = Math.floor(Math.random() * 7);
        const col = new THREE.Color(colonyColors[nearestColony]);
        dustColors[i * 3] = col.r;
        dustColors[i * 3 + 1] = col.g;
        dustColors[i * 3 + 2] = col.b;
        
        dustSizes[i] = 0.02 + Math.random() * 0.04;
    }
    
    const dustGeo = new THREE.BufferGeometry();
    dustGeo.setAttribute('position', new THREE.BufferAttribute(dustPositions, 3));
    dustGeo.setAttribute('color', new THREE.BufferAttribute(dustColors, 3));
    dustGeo.setAttribute('size', new THREE.BufferAttribute(dustSizes, 1));
    
    const dust = new THREE.Points(dustGeo, new THREE.PointsMaterial({
        size: 0.04, vertexColors: true, transparent: true, opacity: 0.4,
        blending: THREE.AdditiveBlending, depthWrite: false, sizeAttenuation: true
    }));
    dust.name = 'constellation-dust';
    group.add(dust);
    
    // === FLOOR PROJECTION (Fano plane diagram beneath sculpture) ===
    const projCanvas = document.createElement('canvas');
    projCanvas.width = 1024;
    projCanvas.height = 1024;
    const pctx = projCanvas.getContext('2d');
    
    // Draw Fano plane diagram
    pctx.fillStyle = 'rgba(0, 0, 0, 0)';
    pctx.fillRect(0, 0, 1024, 1024);
    
    const pc = 512; // center
    const pr = 350; // radius
    
    // Draw lines first (behind nodes)
    pctx.lineWidth = 2;
    fanoLines.forEach((line) => {
        const pts = line.map(idx => ({
            x: pc + Math.cos((idx / 7) * Math.PI * 2 - Math.PI / 2) * pr,
            y: pc + Math.sin((idx / 7) * Math.PI * 2 - Math.PI / 2) * pr
        }));
        
        const blendCol = new THREE.Color(colonyColors[line[0]]).lerp(new THREE.Color(colonyColors[line[2]]), 0.5);
        const r = Math.floor(blendCol.r * 255);
        const g = Math.floor(blendCol.g * 255);
        const b = Math.floor(blendCol.b * 255);
        pctx.strokeStyle = `rgba(${r}, ${g}, ${b}, 0.25)`;
        
        pctx.beginPath();
        pctx.moveTo(pts[0].x, pts[0].y);
        pctx.quadraticCurveTo(pc, pc, pts[1].x, pts[1].y);
        pctx.stroke();
        pctx.beginPath();
        pctx.moveTo(pts[1].x, pts[1].y);
        pctx.quadraticCurveTo(pc, pc, pts[2].x, pts[2].y);
        pctx.stroke();
    });
    
    // Draw nodes
    COLONY_ORDER.forEach((colony, i) => {
        const data = COLONY_DATA[colony];
        const nx = pc + Math.cos((i / 7) * Math.PI * 2 - Math.PI / 2) * pr;
        const ny = pc + Math.sin((i / 7) * Math.PI * 2 - Math.PI / 2) * pr;
        const hexStr = `#${data.hex.toString(16).padStart(6, '0')}`;
        
        pctx.beginPath();
        pctx.arc(nx, ny, 18, 0, Math.PI * 2);
        pctx.fillStyle = hexStr;
        pctx.globalAlpha = 0.4;
        pctx.fill();
        pctx.globalAlpha = 1;
        
        pctx.fillStyle = hexStr;
        pctx.font = "16px 'IBM Plex Sans', sans-serif";
        pctx.textAlign = 'center';
        pctx.textBaseline = 'middle';
        pctx.fillText(data.name, nx, ny + 30);
    });
    
    // Center label
    pctx.fillStyle = 'rgba(103, 212, 228, 0.3)';
    pctx.font = "14px 'IBM Plex Mono', monospace";
    pctx.textAlign = 'center';
    pctx.fillText('7 points · 7 lines · perfect symmetry', pc, pc);
    
    const projTex = new THREE.CanvasTexture(projCanvas);
    projTex.minFilter = THREE.LinearFilter;
    const projGeo = new THREE.CircleGeometry(5, 64);
    const projMat = new THREE.MeshBasicMaterial({
        map: projTex, transparent: true, opacity: 0.2,
        side: THREE.DoubleSide, depthWrite: false,
        blending: THREE.AdditiveBlending
    });
    const projection = new THREE.Mesh(projGeo, projMat);
    projection.rotation.x = -Math.PI / 2;
    projection.position.y = -0.05; // just above floor
    projection.name = 'floor-projection';
    group.add(projection);
    
    // === MESSAGE PARTICLE POOL (for consensus heartbeat) ===
    const msgGeo = new THREE.SphereGeometry(0.04, 6, 6);
    for (let i = 0; i < 21; i++) { // 3 per line × 7 lines
        const msg = new THREE.Mesh(msgGeo, new THREE.MeshBasicMaterial({
            color: 0xFFFFFF, transparent: true, opacity: 0
        }));
        msg.name = `msg-particle-${i}`;
        msg.userData = { active: false, progress: 0, lineIdx: Math.floor(i / 3), speed: 0.4 + Math.random() * 0.3 };
        msg.visible = false;
        group.add(msg);
    }
    
    // Store vertex positions and line data for animation
    group.userData.vertexPositions = vertexPositions;
    group.userData.fanoLines = fanoLines;
    group.userData.colonyColors = colonyColors;
    group.userData.constellationData = {
        lastConsensusTime: 0,
        consensusInterval: 7, // every 7 seconds
        auroraPhase: 0,
        lastAuroraTime: 0,
        auroraInterval: 300, // every 5 minutes
        discoveryPlayed: false,
        celebrationPlayed: false
    };
    
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

    // === WALLS + CEILING + BASEBOARDS per segment ===
    const wallThick = 0.6;  // Substantial walls (was 0.4)
    const baseboardH = 0.15;
    
    for (let i = 0; i < 3; i++) {
        const h = heights[i];
        const segStart = i * segLen;
        const mid = segStart + segLen / 2;
        const wallMat = i >= 2 ? materials.concretePolished : materials.concrete;
        const ceilMat = materials.ceiling;

        // Left wall
        const leftWall = new THREE.Mesh(new THREE.BoxGeometry(wallThick, h, segLen), wallMat);
        leftWall.name = `wall-${colony}-left-${i}`;
        leftWall.userData.occludes = true;
        leftWall.userData.collidable = true;
        leftWall.position.set(
            cos * (rotundaRadius + mid) - sin * (width / 2 + wallThick / 2),
            h / 2,
            sin * (rotundaRadius + mid) + cos * (width / 2 + wallThick / 2)
        );
        leftWall.rotation.y = angle;
        leftWall.castShadow = true;
        leftWall.receiveShadow = true;
        group.add(leftWall);

        // Right wall
        const rightWall = new THREE.Mesh(new THREE.BoxGeometry(wallThick, h, segLen), wallMat);
        rightWall.name = `wall-${colony}-right-${i}`;
        rightWall.userData.occludes = true;
        rightWall.userData.collidable = true;
        rightWall.position.set(
            cos * (rotundaRadius + mid) + sin * (width / 2 + wallThick / 2),
            h / 2,
            sin * (rotundaRadius + mid) - cos * (width / 2 + wallThick / 2)
        );
        rightWall.rotation.y = angle;
        rightWall.castShadow = true;
        rightWall.receiveShadow = true;
        group.add(rightWall);

        // Ceiling
        const ceilingGeo = new THREE.PlaneGeometry(width + wallThick * 2 + 0.1, segLen);
        const ceiling = new THREE.Mesh(ceilingGeo, ceilMat);
        ceiling.userData.occludes = true;
        ceiling.rotation.x = Math.PI / 2;
        ceiling.rotation.z = angle;
        ceiling.position.set(cos * (rotundaRadius + mid), h, sin * (rotundaRadius + mid));
        group.add(ceiling);

        // Baseboards (dark polished strip at floor level)
        if (materials.baseboard) {
            const bbGeo = new THREE.BoxGeometry(wallThick + 0.05, baseboardH, segLen);
            
            const leftBB = new THREE.Mesh(bbGeo, materials.baseboard);
            leftBB.position.set(
                cos * (rotundaRadius + mid) - sin * (width / 2 + wallThick / 2),
                baseboardH / 2,
                sin * (rotundaRadius + mid) + cos * (width / 2 + wallThick / 2)
            );
            leftBB.rotation.y = angle;
            group.add(leftBB);
            
            const rightBB = new THREE.Mesh(bbGeo, materials.baseboard);
            rightBB.position.set(
                cos * (rotundaRadius + mid) + sin * (width / 2 + wallThick / 2),
                baseboardH / 2,
                sin * (rotundaRadius + mid) - cos * (width / 2 + wallThick / 2)
            );
            rightBB.rotation.y = angle;
            group.add(rightBB);
        }
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
    const vestWallThick = 0.6;
    const leftWall = new THREE.Mesh(
        new THREE.BoxGeometry(vestWallThick, heightMid, vestibuleDepth),
        wallMat
    );
    leftWall.name = `wall-vestibule-${colony}-left`;
    leftWall.userData.occludes = true;
    leftWall.userData.collidable = true;
    leftWall.position.set(centerX - sin * (widthMid / 2 + vestWallThick / 2), heightMid / 2, centerZ + cos * (widthMid / 2 + vestWallThick / 2));
    leftWall.rotation.y = angle;
    leftWall.castShadow = true;
    leftWall.receiveShadow = true;
    group.add(leftWall);
    const rightWall = new THREE.Mesh(
        new THREE.BoxGeometry(vestWallThick, heightMid, vestibuleDepth),
        wallMat
    );
    rightWall.name = `wall-vestibule-${colony}-right`;
    rightWall.userData.occludes = true;
    rightWall.userData.collidable = true;
    rightWall.position.set(centerX + sin * (widthMid / 2 + vestWallThick / 2), heightMid / 2, centerZ - cos * (widthMid / 2 + vestWallThick / 2));
    rightWall.rotation.y = angle;
    rightWall.castShadow = true;
    rightWall.receiveShadow = true;
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
    
    // === SIDE WALLS (concrete, thick for real museum feel) ===
    const wallThickness = 0.8;  // Substantial gallery walls (was 0.5)
    const sideWallGeo = new THREE.BoxGeometry(wallThickness, height, depth);
    
    const leftWall = new THREE.Mesh(sideWallGeo, materials.concrete);
    leftWall.name = `wall-gallery-${colony}-left`;
    leftWall.userData.occludes = true;
    leftWall.userData.collidable = true;
    leftWall.position.set(
        centerX - Math.sin(angle) * (width / 2 + wallThickness / 2),
        height / 2,
        centerZ + Math.cos(angle) * (width / 2 + wallThickness / 2)
    );
    leftWall.rotation.y = angle;
    leftWall.castShadow = true;
    leftWall.receiveShadow = true;
    group.add(leftWall);
    
    const rightWall = new THREE.Mesh(sideWallGeo, materials.concrete);
    rightWall.name = `wall-gallery-${colony}-right`;
    rightWall.userData.occludes = true;
    rightWall.userData.collidable = true;
    rightWall.position.set(
        centerX + Math.sin(angle) * (width / 2 + wallThickness / 2),
        height / 2,
        centerZ - Math.cos(angle) * (width / 2 + wallThickness / 2)
    );
    rightWall.rotation.y = angle;
    rightWall.castShadow = true;
    rightWall.receiveShadow = true;
    group.add(rightWall);
    
    // Gallery baseboards
    if (materials.baseboard) {
        const bbH = 0.15;
        const bbGeo = new THREE.BoxGeometry(wallThickness + 0.05, bbH, depth);
        
        const leftBB = new THREE.Mesh(bbGeo, materials.baseboard);
        leftBB.position.copy(leftWall.position);
        leftBB.position.y = bbH / 2;
        leftBB.rotation.y = angle;
        group.add(leftBB);
        
        const rightBB = new THREE.Mesh(bbGeo, materials.baseboard);
        rightBB.position.copy(rightWall.position);
        rightBB.position.y = bbH / 2;
        rightBB.rotation.y = angle;
        group.add(rightBB);
    }
    
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
    const wallThick = 0.6;
    const baseboardH = 0.15;
    
    // Position outside rotunda at main entrance — angle-aligned
    const angle = BUILDING.entranceWorldDirection;
    const cos = Math.cos(angle), sin = Math.sin(angle);
    const centerX = cos * (rotundaRadius + depth / 2 + 2);
    const centerZ = sin * (rotundaRadius + depth / 2 + 2);
    
    // Floor
    const floorGeo = new THREE.PlaneGeometry(width, depth);
    const floor = new THREE.Mesh(floorGeo, materials.floor);
    floor.rotation.x = -Math.PI / 2;
    floor.rotation.z = angle;
    floor.position.set(centerX, 0.01, centerZ);
    floor.receiveShadow = true;
    group.add(floor);
    
    // Back wall (furthest from rotunda)
    const backDist = depth / 2;
    const backWall = new THREE.Mesh(
        new THREE.BoxGeometry(width, height, wallThick),
        materials.concrete
    );
    backWall.name = 'wall-vestibule-back';
    backWall.userData.occludes = true;
    backWall.userData.collidable = true;
    backWall.position.set(
        centerX + cos * backDist,
        height / 2,
        centerZ + sin * backDist
    );
    backWall.rotation.y = angle;
    backWall.castShadow = true;
    backWall.receiveShadow = true;
    group.add(backWall);
    
    // Side walls
    const sideGeo = new THREE.BoxGeometry(wallThick, height, depth);
    
    const leftWall = new THREE.Mesh(sideGeo, materials.concrete);
    leftWall.name = 'wall-vestibule-left';
    leftWall.userData.occludes = true;
    leftWall.userData.collidable = true;
    leftWall.position.set(
        centerX - sin * width / 2,
        height / 2,
        centerZ + cos * width / 2
    );
    leftWall.rotation.y = angle;
    leftWall.castShadow = true;
    leftWall.receiveShadow = true;
    group.add(leftWall);
    
    const rightWall = new THREE.Mesh(sideGeo, materials.concrete);
    rightWall.name = 'wall-vestibule-right';
    rightWall.userData.occludes = true;
    rightWall.userData.collidable = true;
    rightWall.position.set(
        centerX + sin * width / 2,
        height / 2,
        centerZ - cos * width / 2
    );
    rightWall.rotation.y = angle;
    rightWall.castShadow = true;
    rightWall.receiveShadow = true;
    group.add(rightWall);
    
    // Ceiling
    const ceilingGeo = new THREE.PlaneGeometry(width, depth);
    const ceiling = new THREE.Mesh(ceilingGeo, materials.ceiling);
    ceiling.userData.occludes = true;
    ceiling.rotation.x = Math.PI / 2;
    ceiling.rotation.z = angle;
    ceiling.position.set(centerX, height, centerZ);
    group.add(ceiling);
    
    // Baseboards
    if (materials.baseboard) {
        const bbGeo = new THREE.BoxGeometry(wallThick + 0.05, baseboardH, depth);
        
        const leftBB = new THREE.Mesh(bbGeo, materials.baseboard);
        leftBB.position.copy(leftWall.position);
        leftBB.position.y = baseboardH / 2;
        leftBB.rotation.y = angle;
        group.add(leftBB);
        
        const rightBB = new THREE.Mesh(bbGeo, materials.baseboard);
        rightBB.position.copy(rightWall.position);
        rightBB.position.y = baseboardH / 2;
        rightBB.rotation.y = angle;
        group.add(rightBB);
    }
    
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
// FANO CONSTELLATION ANIMATOR — The beating heart of the museum
// ═══════════════════════════════════════════════════════════════════════════

export class FanoConstellationAnimator {
    constructor(sculpture) {
        this.sculpture = sculpture;
        this.time = 0;
        this.data = sculpture?.userData?.constellationData || {};
        this.vertexPositions = sculpture?.userData?.vertexPositions || [];
        this.fanoLines = sculpture?.userData?.fanoLines || [];
        this.colonyColors = sculpture?.userData?.colonyColors || [];
        this.consensusPhase = 'idle'; // idle, propagating, voting, resolved
        this.consensusTimer = 0;
        this.nearestVisitor = null;
        this.visitedWings = new Set();
    }
    
    update(time, deltaTime, playerPosition) {
        if (!this.sculpture) return;
        this.time = time;
        
        // Slow base rotation (1 rev / 7 min)
        this.sculpture.rotation.y = (time / 420) * Math.PI * 2;
        
        this._animateCrystals(time, deltaTime);
        this._animateOrbitalRings(time, deltaTime);
        this._animateConstellationDust(time, deltaTime);
        this._animateNexus(time, deltaTime);
        this._runConsensusHeartbeat(time, deltaTime);
        this._animateMessageParticles(time, deltaTime);
        this._respondToVisitor(playerPosition);
        this._checkAurora(time, deltaTime);
        this._animateFloorProjection(time);
    }
    
    _animateCrystals(time, dt) {
        // Fibonacci-spaced breathing for each colony
        const fibRhythms = [2.33, 3.77, 6.1, 9.87, 15.97, 25.84, 41.81];
        
        COLONY_ORDER.forEach((colony, i) => {
            const crystal = this.sculpture.getObjectByName(`crystal-${colony}`);
            const shell = this.sculpture.getObjectByName(`crystal-shell-${colony}`);
            if (!crystal) return;
            
            const breathPhase = Math.sin(time / fibRhythms[i] * Math.PI * 2);
            const breathScale = 1 + breathPhase * 0.08;
            crystal.scale.setScalar(breathScale);
            
            if (crystal.material) {
                crystal.material.emissiveIntensity = 0.3 + breathPhase * 0.2;
            }
            
            if (shell) {
                shell.scale.setScalar(1 + breathPhase * 0.12);
                shell.rotation.y += dt * 0.3;
                shell.rotation.x += dt * 0.15;
                if (shell.material) shell.material.opacity = 0.12 + breathPhase * 0.08;
            }
            
            // Gentle hover
            crystal.position.y = this.vertexPositions[i].y + Math.sin(time * 0.5 + i * 0.9) * 0.05;
        });
    }
    
    _animateOrbitalRings(time, dt) {
        COLONY_ORDER.forEach((colony) => {
            const ring = this.sculpture.getObjectByName(`orbital-ring-${colony}`);
            if (!ring) return;
            const { orbitSpeed, tiltBase } = ring.userData;
            ring.rotation.y += dt * orbitSpeed;
            ring.rotation.x = tiltBase + Math.sin(time * 0.1 + ring.rotation.z) * 0.05;
        });
    }
    
    _animateConstellationDust(time, dt) {
        const dust = this.sculpture.getObjectByName('constellation-dust');
        if (!dust?.geometry) return;
        
        const positions = dust.geometry.attributes.position;
        if (!positions) return;
        
        for (let i = 0; i < positions.count; i++) {
            const x = positions.getX(i);
            const y = positions.getY(i);
            const z = positions.getZ(i);
            
            // Slow swirl
            const angle = dt * 0.01;
            const cos = Math.cos(angle);
            const sin = Math.sin(angle);
            positions.setX(i, x * cos - z * sin);
            positions.setZ(i, x * sin + z * cos);
            
            // Gentle vertical bob
            positions.setY(i, y + Math.sin(time * 0.2 + i * 0.1) * 0.001);
        }
        positions.needsUpdate = true;
    }
    
    _animateNexus(time, dt) {
        const nexus = this.sculpture.getObjectByName('constellation-nexus');
        const glow = this.sculpture.getObjectByName('nexus-glow');
        const halo = this.sculpture.getObjectByName('nexus-halo');
        
        if (nexus) {
            nexus.rotation.y += dt * 0.2;
            nexus.rotation.x = Math.sin(time * 0.3) * 0.1;
            const pulse = 0.8 + Math.sin(time * 1.5) * 0.15;
            nexus.scale.setScalar(pulse);
            if (nexus.material) nexus.material.emissiveIntensity = 0.4 + Math.sin(time * 2) * 0.2;
        }
        if (glow) {
            glow.rotation.y -= dt * 0.4;
            glow.scale.setScalar(0.8 + Math.sin(time * 2.5) * 0.15);
            if (glow.material) glow.material.opacity = 0.5 + Math.sin(time * 2) * 0.3;
        }
        if (halo) {
            halo.rotation.y += dt * 0.1;
            halo.rotation.z += dt * 0.05;
        }
    }
    
    _runConsensusHeartbeat(time, dt) {
        const interval = this.data.consensusInterval || 7;
        const timeSinceLast = time - (this.data.lastConsensusTime || 0);
        
        if (this.consensusPhase === 'idle' && timeSinceLast >= interval) {
            this.consensusPhase = 'propagating';
            this.consensusTimer = 0;
            this.data.lastConsensusTime = time;
            
            // Activate message particles
            this.sculpture.traverse(obj => {
                if (obj.name.startsWith('msg-particle-')) {
                    obj.visible = true;
                    obj.userData.active = true;
                    obj.userData.progress = 0;
                }
            });
        }
        
        if (this.consensusPhase === 'propagating') {
            this.consensusTimer += dt;
            if (this.consensusTimer > 2) {
                this.consensusPhase = 'voting';
                this.consensusTimer = 0;
            }
        }
        
        if (this.consensusPhase === 'voting') {
            this.consensusTimer += dt;
            // Pulse nexus brightly during voting
            const nexus = this.sculpture.getObjectByName('constellation-nexus');
            if (nexus?.material) {
                nexus.material.emissiveIntensity = 0.8 + Math.sin(this.consensusTimer * 8) * 0.4;
            }
            if (this.consensusTimer > 1.5) {
                this.consensusPhase = 'resolved';
                this.consensusTimer = 0;
            }
        }
        
        if (this.consensusPhase === 'resolved') {
            this.consensusTimer += dt;
            // Flash all crystals in agreement
            COLONY_ORDER.forEach((colony) => {
                const crystal = this.sculpture.getObjectByName(`crystal-${colony}`);
                if (crystal?.material) {
                    crystal.material.emissiveIntensity = 1.0 * Math.max(0, 1 - this.consensusTimer * 0.7);
                }
            });
            if (this.consensusTimer > 1.5) {
                this.consensusPhase = 'idle';
                // Deactivate particles
                this.sculpture.traverse(obj => {
                    if (obj.name.startsWith('msg-particle-')) {
                        obj.visible = false;
                        obj.userData.active = false;
                    }
                });
            }
        }
    }
    
    _animateMessageParticles(time, dt) {
        this.sculpture.traverse(obj => {
            if (!obj.name.startsWith('msg-particle-') || !obj.userData.active) return;
            
            obj.userData.progress += dt * obj.userData.speed;
            const p = Math.min(obj.userData.progress, 1);
            
            const lineIdx = obj.userData.lineIdx;
            if (lineIdx >= this.fanoLines.length) return;
            
            const line = this.fanoLines[lineIdx];
            const segIdx = Math.floor(parseInt(obj.name.split('-')[2]) % 3);
            const fromIdx = line[Math.min(segIdx, line.length - 1)];
            const toIdx = line[Math.min(segIdx + 1, line.length - 1)];
            
            const from = this.vertexPositions[fromIdx];
            const to = this.vertexPositions[toIdx] || this.vertexPositions[fromIdx];
            
            if (from && to) {
                // Arc through center
                const mid = from.clone().add(to).multiplyScalar(0.3);
                mid.y += 0.5;
                
                const t = p;
                const mt = 1 - t;
                obj.position.set(
                    mt * mt * from.x + 2 * mt * t * mid.x + t * t * to.x,
                    mt * mt * from.y + 2 * mt * t * mid.y + t * t * to.y,
                    mt * mt * from.z + 2 * mt * t * mid.z + t * t * to.z
                );
            }
            
            // Fade in/out
            if (obj.material) {
                obj.material.opacity = p < 0.1 ? p * 10 : (p > 0.9 ? (1 - p) * 10 : 0.8);
                obj.material.color.setHex(this.colonyColors[fromIdx] || 0xFFFFFF);
            }
        });
    }
    
    _respondToVisitor(playerPosition) {
        if (!playerPosition) return;
        
        // Find nearest colony crystal and brighten it
        let minDist = Infinity;
        let nearestColony = null;
        
        // We need sculpture's world position
        const sculptureWorldPos = new THREE.Vector3();
        this.sculpture.getWorldPosition(sculptureWorldPos);
        
        COLONY_ORDER.forEach((colony, i) => {
            const crystal = this.sculpture.getObjectByName(`crystal-${colony}`);
            if (!crystal) return;
            
            const crystalWorld = new THREE.Vector3();
            crystal.getWorldPosition(crystalWorld);
            const dist = playerPosition.distanceTo(crystalWorld);
            
            if (dist < minDist) {
                minDist = dist;
                nearestColony = colony;
            }
            
            // Proximity brightness
            const brightness = Math.max(0, 1 - dist / 15);
            if (crystal.material) {
                crystal.material.emissiveIntensity = Math.max(crystal.material.emissiveIntensity, 0.3 + brightness * 0.5);
            }
            
            // Widen orbital ring on proximity
            const ring = this.sculpture.getObjectByName(`orbital-ring-${colony}`);
            if (ring) {
                const targetScale = 1 + brightness * 0.15;
                ring.scale.lerp(new THREE.Vector3(targetScale, targetScale, targetScale), 0.05);
            }
        });
        
        // Subtle tilt toward visitor
        if (minDist < 20) {
            const dx = playerPosition.x - sculptureWorldPos.x;
            const dz = playerPosition.z - sculptureWorldPos.z;
            const targetTiltX = Math.atan2(dz, Math.sqrt(dx * dx + dz * dz)) * 0.03;
            const targetTiltZ = Math.atan2(-dx, Math.sqrt(dx * dx + dz * dz)) * 0.03;
            this.sculpture.rotation.x += (targetTiltX - this.sculpture.rotation.x) * 0.02;
            this.sculpture.rotation.z += (targetTiltZ - this.sculpture.rotation.z) * 0.02;
        }
    }
    
    _checkAurora(time, dt) {
        const interval = this.data.auroraInterval || 300;
        const timeSinceLast = time - (this.data.lastAuroraTime || 0);
        
        if (timeSinceLast >= interval) {
            this.data.lastAuroraTime = time;
            this.data.auroraPhase = 1; // Start aurora
        }
        
        if (this.data.auroraPhase > 0) {
            this.data.auroraPhase -= dt * 0.15; // Fades over ~7 seconds
            
            const dust = this.sculpture.getObjectByName('constellation-dust');
            if (dust?.geometry?.attributes?.color) {
                const colors = dust.geometry.attributes.color;
                for (let i = 0; i < colors.count; i++) {
                    const phase = this.data.auroraPhase;
                    const wave = Math.sin(i * 0.03 + time * 2) * 0.5 + 0.5;
                    // Cascade rainbow through the dust
                    const hue = (i / colors.count + time * 0.1) % 1;
                    const col = new THREE.Color().setHSL(hue, 0.8, 0.5 + wave * 0.3);
                    colors.setXYZ(i, 
                        colors.getX(i) * (1 - phase * 0.5) + col.r * phase * 0.5,
                        colors.getY(i) * (1 - phase * 0.5) + col.g * phase * 0.5,
                        colors.getZ(i) * (1 - phase * 0.5) + col.b * phase * 0.5
                    );
                }
                colors.needsUpdate = true;
            }
            
            if (this.data.auroraPhase <= 0) this.data.auroraPhase = 0;
        }
    }
    
    _animateFloorProjection(time) {
        const proj = this.sculpture.getObjectByName('floor-projection');
        if (!proj?.material) return;
        
        // Gentle pulse
        proj.material.opacity = 0.15 + Math.sin(time * 0.5) * 0.05;
        proj.rotation.z = time * 0.005; // Very slow rotation
    }
    
    // === Interactive triggers ===
    
    triggerCelebration() {
        if (this.data.celebrationPlayed) return;
        this.data.celebrationPlayed = true;
        
        // All rings align
        COLONY_ORDER.forEach((colony) => {
            const ring = this.sculpture.getObjectByName(`orbital-ring-${colony}`);
            if (ring) {
                ring.userData._savedRotation = { x: ring.rotation.x, z: ring.rotation.z };
                ring.rotation.x = 0;
                ring.rotation.z = 0;
            }
        });
        
        // Flash all crystals
        COLONY_ORDER.forEach((colony) => {
            const crystal = this.sculpture.getObjectByName(`crystal-${colony}`);
            if (crystal?.material) crystal.material.emissiveIntensity = 2.0;
        });
        
        // Restore after 5 seconds
        setTimeout(() => {
            COLONY_ORDER.forEach((colony) => {
                const ring = this.sculpture.getObjectByName(`orbital-ring-${colony}`);
                const crystal = this.sculpture.getObjectByName(`crystal-${colony}`);
                if (ring?.userData._savedRotation) {
                    ring.rotation.x = ring.userData._savedRotation.x;
                    ring.rotation.z = ring.userData._savedRotation.z;
                }
                if (crystal?.material) crystal.material.emissiveIntensity = 0.4;
            });
        }, 5000);
    }
    
    setVisitedWings(wings) {
        this.visitedWings = new Set(wings);
        if (this.visitedWings.size >= 7) {
            this.triggerCelebration();
        }
    }
    
    triggerNexusConsensus() {
        // Force immediate consensus round
        this.data.lastConsensusTime = 0;
        this.consensusPhase = 'idle';
    }
    
    highlightColonyBeam(colony) {
        const crystal = this.sculpture.getObjectByName(`crystal-${colony}`);
        if (!crystal) return;
        
        if (crystal.material) crystal.material.emissiveIntensity = 1.5;
        setTimeout(() => {
            if (crystal.material) crystal.material.emissiveIntensity = 0.4;
        }, 3000);
    }
}

export function animateFanoSculpture(sculpture, time, deltaTime, playerPosition) {
    if (!sculpture) return;
    
    // Initialize animator on first call
    if (!sculpture.userData._animator) {
        sculpture.userData._animator = new FanoConstellationAnimator(sculpture);
    }
    
    sculpture.userData._animator.update(time, deltaTime || 0.016, playerPosition);
}

// Legacy compatibility stubs
export function createFanoSculpture(scale) {
    const materials = createMuseumMaterials();
    return createSimplifiedFano(materials.steel);
}

export function animateHopfProjection() {}
