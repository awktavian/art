/**
 * P1-002: 7-Colony Fano Consensus Artwork
 * =======================================
 * 
 * A participatory democracy experience inspired by the Exploratorium.
 * Visitors walk among the 7 colony voting stations, cast votes, and
 * witness Byzantine fault tolerance in action.
 * 
 * Inspired by:
 * - Exploratorium's hands-on civic engagement exhibits
 * - teamLab's collective experience design
 * - Meow Wolf's discovery-driven exploration
 * 
 * Features:
 * - Walk-in voting stations (physically approach to activate)
 * - Real-time click-to-vote interaction
 * - Byzantine node detection and dramatic exclusion
 * - Consensus celebration with light and sound
 * - Message particles following Fano line curves
 * - Colony role visualization (OBSERVER/PARTICIPANT/VALIDATOR)
 * 
 * h(x) ≥ 0 always
 */

import * as THREE from 'three';
import { createPlaque } from '../components/plaque.js';
import { PATENTS } from '../components/info-panel.js';

const PATENT = PATENTS.find(p => p.id === 'P1-002');

const COLONY_DATA = {
    spark:   { hex: 0xFF6B35, name: 'Spark',   role: 'VALIDATOR',   pitch: 523.25 }, // C5
    forge:   { hex: 0xD4AF37, name: 'Forge',   role: 'PARTICIPANT', pitch: 587.33 }, // D5
    flow:    { hex: 0x4ECDC4, name: 'Flow',    role: 'PARTICIPANT', pitch: 659.25 }, // E5
    nexus:   { hex: 0x9B7EBD, name: 'Nexus',   role: 'ORCHESTRATOR',pitch: 698.46 }, // F5
    beacon:  { hex: 0xF59E0B, name: 'Beacon',  role: 'VALIDATOR',   pitch: 783.99 }, // G5
    grove:   { hex: 0x7EB77F, name: 'Grove',   role: 'OBSERVER',    pitch: 880.00 }, // A5
    crystal: { hex: 0x67D4E4, name: 'Crystal', role: 'VALIDATOR',   pitch: 987.77 }  // B5
};

const COLONY_ORDER = ['spark', 'forge', 'flow', 'nexus', 'beacon', 'grove', 'crystal'];

// Fano plane configuration (7 points, 7 lines, each line has 3 collinear points)
const FANO_LINES = [
    [0, 1, 3], // Spark - Forge - Nexus
    [0, 2, 5], // Spark - Flow - Grove
    [0, 4, 6], // Spark - Beacon - Crystal
    [1, 2, 4], // Forge - Flow - Beacon
    [1, 5, 6], // Forge - Grove - Crystal
    [2, 3, 6], // Flow - Nexus - Crystal
    [3, 4, 5]  // Nexus - Beacon - Grove
];

// Consensus state
const VOTE_STATES = {
    PENDING: 'pending',
    APPROVE: 'approve',
    REJECT: 'reject',
    BYZANTINE: 'byzantine'
};

export class FanoConsensusArtwork extends THREE.Group {
    constructor() {
        super();
        this.name = 'artwork-fano-consensus';
        this.time = 0;
        
        // Voting state
        this.nodes = [];
        this.stations = [];
        this.votes = new Array(7).fill(VOTE_STATES.PENDING);
        this.byzantineNodes = new Set();
        this.consensusAchieved = false;
        this.consensusRound = 0;
        this.lastConsensusTime = 0;
        
        // Animation state
        this.messageParticles = [];
        this.celebrationParticles = null;
        this.celebrationActive = false;
        
        // Interaction
        this.hoveredStation = null;
        this.playerVotes = new Set();
        
        // Attack Mode - let visitors try to break consensus
        this.attackMode = false;
        this.attackerNodes = new Set(); // Nodes controlled by attacker
        this.attackAttempts = 0;
        this.attacksBlocked = 0;
        
        // Audio context (will be created on interaction)
        this.audioContext = null;
        
        // Microdelight tracking
        this.microdelights = { byzantineFailTriggered: false, consensusRoundsWatched: 0 };
        
        this.create();
    }
    
    create() {
        // === FOUNDATION ===
        this.createFanoFloor();
        
        // === VOTING INFRASTRUCTURE ===
        this.createVotingStations();
        this.createConnectionLines();
        
        // === CONSENSUS VISUALIZATION ===
        this.createConsensusPillar();
        this.createMessageSystem();
        this.createCelebrationSystem();
        
        // === ATTACK MODE CONTROLS ===
        this.createAttackModePanel();
        
        // === ATMOSPHERIC ===
        this.createAmbientParticles();
        
        // === INFORMATION ===
        this.createPlaque();
        
        // Mark as interactive
        this.userData.interactive = true;
        this.userData.artwork = PATENT;
    }
    
    // ═══════════════════════════════════════════════════════════════════════
    // FANO FLOOR WITH SACRED GEOMETRY
    // ═══════════════════════════════════════════════════════════════════════
    
    createFanoFloor() {
        const group = new THREE.Group();
        group.name = 'fano-floor';
        
        // Main circular floor
        const floorGeo = new THREE.CircleGeometry(8, 64);
        const floorMat = new THREE.MeshPhysicalMaterial({
            color: 0x08080C,
            metalness: 0.9,
            roughness: 0.15,
            clearcoat: 0.8,
            clearcoatRoughness: 0.1
        });
        const floor = new THREE.Mesh(floorGeo, floorMat);
        floor.rotation.x = -Math.PI / 2;
        floor.receiveShadow = true;
        group.add(floor);
        
        // Fano pattern - lines connecting the 7 points
        const lineMat = new THREE.MeshBasicMaterial({
            color: 0x9B7EBD,
            transparent: true,
            opacity: 0.4
        });
        
        FANO_LINES.forEach((line, idx) => {
            const points = line.map(i => {
                const pos = this.getNodePosition(i);
                return new THREE.Vector3(pos.x, 0.02, pos.z);
            });
            
            // Curve through all 3 points
            const curve = new THREE.CatmullRomCurve3(points);
            const tubeGeo = new THREE.TubeGeometry(curve, 48, 0.04, 8, false);
            const tube = new THREE.Mesh(tubeGeo, lineMat.clone());
            group.add(tube);
        });
        
        // Outer glow ring
        const outerRingGeo = new THREE.RingGeometry(7.8, 8, 64);
        const outerRingMat = new THREE.MeshBasicMaterial({
            color: 0x67D4E4,
            transparent: true,
            opacity: 0.3,
            side: THREE.DoubleSide
        });
        const outerRing = new THREE.Mesh(outerRingGeo, outerRingMat);
        outerRing.rotation.x = -Math.PI / 2;
        outerRing.position.y = 0.01;
        group.add(outerRing);
        
        this.add(group);
    }
    
    getNodePosition(index) {
        // True Fano plane PG(2,2): 7 points, 7 lines. Standard layout:
        // Triangle vertices 0, 1, 2; edge midpoints 3=(0,1), 4=(1,2), 5=(0,2); centroid 6.
        // FANO_LINES: [0,1,3], [0,2,5], [0,4,6], [1,2,4], [1,5,6], [2,3,6], [3,4,5]
        const scale = 4.5;
        const h = scale * Math.sqrt(3) / 2;
        const positions = [
            { x: 0,           z: scale },           // 0 - Spark (top vertex)
            { x: -scale,      z: -scale * 0.5 },   // 1 - Forge (left vertex)
            { x: scale,       z: -scale * 0.5 },   // 2 - Flow (right vertex)
            { x: -scale / 2,  z: scale * 0.25 },   // 3 - Nexus (mid 0-1)
            { x: 0,          z: -scale * 0.5 },   // 4 - Beacon (mid 1-2)
            { x: scale / 2,   z: scale * 0.25 },   // 5 - Grove (mid 0-2)
            { x: 0,          z: 0 }               // 6 - Crystal (centroid)
        ];
        return positions[index];
    }
    
    // ═══════════════════════════════════════════════════════════════════════
    // VOTING STATIONS
    // ═══════════════════════════════════════════════════════════════════════
    
    createVotingStations() {
        COLONY_ORDER.forEach((colony, i) => {
            const station = this.createVotingStation(colony, i);
            this.stations.push(station);
            this.add(station);
        });
    }
    
    createVotingStation(colony, index) {
        const group = new THREE.Group();
        group.name = `station-${colony}`;
        
        const pos = this.getNodePosition(index);
        const data = COLONY_DATA[colony];
        const color = data.hex;
        
        // Size based on role
        const roleScale = {
            'ORCHESTRATOR': 1.3,
            'VALIDATOR': 1.1,
            'PARTICIPANT': 1.0,
            'OBSERVER': 0.9
        }[data.role] || 1.0;
        
        // === PLATFORM ===
        const platformGeo = new THREE.CylinderGeometry(0.9 * roleScale, 1.1 * roleScale, 0.2, 32);
        const platformMat = new THREE.MeshPhysicalMaterial({
            color: 0x12101A,
            metalness: 0.7,
            roughness: 0.3,
            clearcoat: 0.5
        });
        const platform = new THREE.Mesh(platformGeo, platformMat);
        platform.position.y = 0.1;
        platform.castShadow = true;
        platform.receiveShadow = true;
        group.add(platform);
        
        // Activation ring (glows when visitor is nearby)
        const activationRingGeo = new THREE.RingGeometry(1.0 * roleScale, 1.2 * roleScale, 32);
        const activationRingMat = new THREE.MeshBasicMaterial({
            color: color,
            transparent: true,
            opacity: 0.3,
            side: THREE.DoubleSide
        });
        const activationRing = new THREE.Mesh(activationRingGeo, activationRingMat);
        activationRing.rotation.x = -Math.PI / 2;
        activationRing.position.y = 0.22;
        activationRing.name = 'activation-ring';
        group.add(activationRing);
        
        // === CENTRAL NODE (floating icosahedron) ===
        const nodeSize = 0.35 * roleScale;
        const nodeGeo = new THREE.IcosahedronGeometry(nodeSize, 2);
        const nodeMat = new THREE.MeshPhysicalMaterial({
            color: color,
            emissive: color,
            emissiveIntensity: 0.4,
            metalness: 0.4,
            roughness: 0.3,
            clearcoat: 0.8
        });
        const node = new THREE.Mesh(nodeGeo, nodeMat);
        node.position.y = 1.5;
        node.name = 'colony-node';
        node.userData = { colony, index, type: 'vote-node', interactive: true };
        group.add(node);
        this.nodes.push(node);
        
        // Node glow
        const glowGeo = new THREE.IcosahedronGeometry(nodeSize * 1.3, 1);
        const glowMat = new THREE.MeshBasicMaterial({
            color: color,
            transparent: true,
            opacity: 0.15,
            side: THREE.BackSide
        });
        const glow = new THREE.Mesh(glowGeo, glowMat);
        glow.position.copy(node.position);
        glow.name = 'node-glow';
        group.add(glow);
        
        // === VOTE INDICATOR (shows current vote) ===
        const voteIndicatorGeo = new THREE.SphereGeometry(0.2, 16, 16);
        const voteIndicatorMat = new THREE.MeshBasicMaterial({
            color: 0x444444,
            transparent: true,
            opacity: 0.5
        });
        const voteIndicator = new THREE.Mesh(voteIndicatorGeo, voteIndicatorMat);
        voteIndicator.position.set(0, 2.0, 0);
        voteIndicator.name = 'vote-indicator';
        group.add(voteIndicator);
        
        // === ROLE BADGE ===
        this.createRoleBadge(group, data.role, color, roleScale);
        
        // === COLONY LABEL ===
        this.createColonyLabel(group, colony, data.role, color);
        
        // === INTERACTION TRIGGER ZONE ===
        const triggerGeo = new THREE.CylinderGeometry(1.5, 1.5, 3, 16);
        const triggerMat = new THREE.MeshBasicMaterial({
            visible: false
        });
        const trigger = new THREE.Mesh(triggerGeo, triggerMat);
        trigger.position.y = 1.5;
        trigger.name = 'trigger-zone';
        trigger.userData = { colony, index, type: 'vote-trigger' };
        group.add(trigger);
        
        // Store reference for interactivity
        group.userData = { colony, index, role: data.role };
        
        // Position the station
        group.position.set(pos.x, 0, pos.z);
        
        return group;
    }
    
    createRoleBadge(group, role, color, scale) {
        // Small badge showing the colony's role
        const canvas = document.createElement('canvas');
        canvas.width = 256;
        canvas.height = 64;
        const ctx = canvas.getContext('2d');
        
        // Background
        ctx.fillStyle = 'rgba(0, 0, 0, 0.7)';
        ctx.roundRect(8, 8, 240, 48, 8);
        ctx.fill();
        
        // Role icon and text
        const icons = {
            'ORCHESTRATOR': '🎭',
            'VALIDATOR': '✓',
            'PARTICIPANT': '●',
            'OBSERVER': '👁'
        };
        
        ctx.fillStyle = '#' + color.toString(16).padStart(6, '0');
        ctx.font = 'bold 24px "IBM Plex Sans", sans-serif';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.fillText(`${icons[role] || ''} ${role}`, 128, 32);
        
        const texture = new THREE.CanvasTexture(canvas);
        const badgeGeo = new THREE.PlaneGeometry(1.2 * scale, 0.3 * scale);
        const badgeMat = new THREE.MeshBasicMaterial({
            map: texture,
            transparent: true,
            side: THREE.DoubleSide
        });
        const badge = new THREE.Mesh(badgeGeo, badgeMat);
        badge.position.set(0, 0.8, 0);
        badge.rotation.x = -0.3;
        group.add(badge);
    }
    
    createColonyLabel(group, colony, role, color) {
        const canvas = document.createElement('canvas');
        canvas.width = 256;
        canvas.height = 96;
        const ctx = canvas.getContext('2d');
        
        ctx.fillStyle = '#' + color.toString(16).padStart(6, '0');
        ctx.font = 'bold 36px "IBM Plex Sans", sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText(colony.toUpperCase(), 128, 50);
        
        const texture = new THREE.CanvasTexture(canvas);
        const labelGeo = new THREE.PlaneGeometry(1.5, 0.6);
        const labelMat = new THREE.MeshBasicMaterial({
            map: texture,
            transparent: true,
            side: THREE.DoubleSide
        });
        const label = new THREE.Mesh(labelGeo, labelMat);
        label.position.set(0, 2.3, 0);
        group.add(label);
    }
    
    // ═══════════════════════════════════════════════════════════════════════
    // CONNECTION LINES (3D Fano lines)
    // ═══════════════════════════════════════════════════════════════════════
    
    createConnectionLines() {
        this.connectionLines = [];
        
        FANO_LINES.forEach((line, idx) => {
            const positions = line.map(i => {
                const pos = this.getNodePosition(i);
                return new THREE.Vector3(pos.x, 1.5, pos.z);
            });
            
            // Create smooth curve through all 3 points
            const curve = new THREE.CatmullRomCurve3(positions);
            const tubeGeo = new THREE.TubeGeometry(curve, 48, 0.025, 8, false);
            
            const tubeMat = new THREE.MeshBasicMaterial({
                color: 0x9B7EBD,
                transparent: true,
                opacity: 0.4
            });
            
            const tube = new THREE.Mesh(tubeGeo, tubeMat);
            tube.userData = { lineIndex: idx, nodes: line };
            this.add(tube);
            this.connectionLines.push(tube);
        });
    }
    
    // ═══════════════════════════════════════════════════════════════════════
    // CONSENSUS PILLAR
    // ═══════════════════════════════════════════════════════════════════════
    
    createConsensusPillar() {
        const group = new THREE.Group();
        group.name = 'consensus-pillar';
        
        // Central pillar
        const pillarGeo = new THREE.CylinderGeometry(0.25, 0.35, 4, 32);
        const pillarMat = new THREE.MeshPhysicalMaterial({
            color: 0x1A1820,
            metalness: 0.6,
            roughness: 0.4,
            clearcoat: 0.5
        });
        const pillar = new THREE.Mesh(pillarGeo, pillarMat);
        pillar.position.y = 2;
        group.add(pillar);
        
        // Consensus progress rings (7 rings for 7 nodes)
        this.consensusRings = [];
        for (let i = 0; i < 7; i++) {
            const ringGeo = new THREE.TorusGeometry(0.4, 0.03, 8, 32);
            const ringMat = new THREE.MeshBasicMaterial({
                color: 0x444444,
                transparent: true,
                opacity: 0.5
            });
            const ring = new THREE.Mesh(ringGeo, ringMat);
            ring.rotation.x = Math.PI / 2;
            ring.position.y = 0.5 + i * 0.5;
            group.add(ring);
            this.consensusRings.push(ring);
        }
        
        // Status display
        this.createStatusDisplay(group);
        
        // Top indicator (shows consensus state)
        const indicatorGeo = new THREE.OctahedronGeometry(0.3, 0);
        const indicatorMat = new THREE.MeshPhysicalMaterial({
            color: 0x67D4E4,
            emissive: 0x67D4E4,
            emissiveIntensity: 0.5,
            metalness: 0.5,
            roughness: 0.3
        });
        this.consensusIndicator = new THREE.Mesh(indicatorGeo, indicatorMat);
        this.consensusIndicator.position.y = 4.5;
        group.add(this.consensusIndicator);
        
        // Position at Nexus (center, orchestrator)
        const nexusPos = this.getNodePosition(3);
        group.position.set(nexusPos.x, 0, nexusPos.z);
        
        this.consensusPillar = group;
        this.add(group);
    }
    
    createStatusDisplay(group) {
        // Canvas texture for status
        const canvas = document.createElement('canvas');
        canvas.width = 512;
        canvas.height = 256;
        this.statusCanvas = canvas;
        this.statusCtx = canvas.getContext('2d');
        
        this.updateStatusDisplay();
        
        const texture = new THREE.CanvasTexture(canvas);
        this.statusTexture = texture;
        
        const displayGeo = new THREE.PlaneGeometry(1.5, 0.75);
        const displayMat = new THREE.MeshBasicMaterial({
            map: texture,
            transparent: true,
            side: THREE.DoubleSide
        });
        const display = new THREE.Mesh(displayGeo, displayMat);
        display.position.set(0, 3.5, 0.3);
        group.add(display);
    }
    
    updateStatusDisplay() {
        const ctx = this.statusCtx;
        ctx.clearRect(0, 0, 512, 256);
        
        // Background
        ctx.fillStyle = 'rgba(0, 0, 0, 0.8)';
        ctx.roundRect(10, 10, 492, 236, 10);
        ctx.fill();
        
        // Count votes
        const approves = this.votes.filter(v => v === VOTE_STATES.APPROVE).length;
        const rejects = this.votes.filter(v => v === VOTE_STATES.REJECT).length;
        const pending = this.votes.filter(v => v === VOTE_STATES.PENDING).length;
        const byzantine = this.byzantineNodes.size;
        
        // Title
        ctx.fillStyle = '#67D4E4';
        ctx.font = 'bold 32px "IBM Plex Sans", sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText('CONSENSUS STATUS', 256, 50);
        
        // Vote count - using colony-based status colors
        const consensusThreshold = Math.ceil(7 * 2 / 3); // 5 of 7
        ctx.fillStyle = approves >= consensusThreshold ? '#6FA370' : '#F5F0E8';  // Grove green
        ctx.font = 'bold 48px "IBM Plex Mono", monospace';
        ctx.fillText(`${approves}/7 AGREE`, 256, 120);
        
        // Threshold indicator
        ctx.fillStyle = '#9E9994';
        ctx.font = '24px "IBM Plex Sans", sans-serif';
        ctx.fillText(`(Need ${consensusThreshold} for consensus)`, 256, 160);
        
        // Status - film-quality colony colors
        if (this.consensusAchieved) {
            ctx.fillStyle = '#6FA370';  // Grove green
            ctx.font = 'bold 28px "IBM Plex Sans", sans-serif';
            ctx.fillText('✓ CONSENSUS ACHIEVED', 256, 210);
        } else if (byzantine > 0) {
            ctx.fillStyle = '#E85A2F';  // Spark red
            ctx.font = 'bold 28px "IBM Plex Sans", sans-serif';
            ctx.fillText(`⚠ ${byzantine} BYZANTINE DETECTED`, 256, 210);
        } else if (pending > 0) {
            ctx.fillStyle = '#E8940A';  // Beacon amber
            ctx.font = '24px "IBM Plex Sans", sans-serif';
            ctx.fillText(`${pending} votes pending...`, 256, 210);
        }
        
        if (this.statusTexture) {
            this.statusTexture.needsUpdate = true;
        }
    }
    
    // ═══════════════════════════════════════════════════════════════════════
    // MESSAGE PASSING SYSTEM
    // ═══════════════════════════════════════════════════════════════════════
    
    createMessageSystem() {
        // Pool of message particles
        this.messageParticles = [];
        
        const particleGeo = new THREE.SphereGeometry(0.1, 8, 8);
        
        for (let i = 0; i < 100; i++) {
            const particleMat = new THREE.MeshBasicMaterial({
                color: 0xF5F0E8,
                transparent: true,
                opacity: 0
            });
            
            const particle = new THREE.Mesh(particleGeo, particleMat);
            particle.visible = false;
            particle.userData = {
                active: false,
                progress: 0,
                speed: 0,
                fromNode: 0,
                toNode: 0,
                lineIndex: -1,
                voteValue: null
            };
            this.add(particle);
            this.messageParticles.push(particle);
        }
    }
    
    sendVoteMessage(fromNode, toNode, voteValue) {
        // Find an available particle
        const particle = this.messageParticles.find(p => !p.userData.active);
        if (!particle) return;
        
        // Find which Fano line connects these nodes
        let lineIndex = -1;
        FANO_LINES.forEach((line, idx) => {
            if (line.includes(fromNode) && line.includes(toNode)) {
                lineIndex = idx;
            }
        });
        
        particle.userData = {
            active: true,
            progress: 0,
            speed: 0.4 + Math.random() * 0.2,
            fromNode,
            toNode,
            lineIndex,
            voteValue
        };
        
        // Set color based on vote
        particle.material.color.setHex(voteValue === VOTE_STATES.APPROVE ? 0x6FA370 : 0xE85A2F);
        particle.material.opacity = 1;
        particle.visible = true;
        
        // Set starting position
        const fromPos = this.getNodePosition(fromNode);
        particle.position.set(fromPos.x, 1.5, fromPos.z);
    }
    
    broadcastVote(nodeIndex, voteValue) {
        // Find all nodes connected to this one via Fano lines
        const connectedNodes = new Set();
        FANO_LINES.forEach(line => {
            if (line.includes(nodeIndex)) {
                line.forEach(node => {
                    if (node !== nodeIndex) connectedNodes.add(node);
                });
            }
        });
        
        // Send message to each connected node
        connectedNodes.forEach(toNode => {
            // Stagger the messages slightly
            setTimeout(() => {
                this.sendVoteMessage(nodeIndex, toNode, voteValue);
            }, Math.random() * 300);
        });
    }
    
    // ═══════════════════════════════════════════════════════════════════════
    // CELEBRATION SYSTEM
    // ═══════════════════════════════════════════════════════════════════════
    
    createCelebrationSystem() {
        const particleCount = 500;
        const positions = new Float32Array(particleCount * 3);
        const colors = new Float32Array(particleCount * 3);
        const velocities = new Float32Array(particleCount * 3);
        
        for (let i = 0; i < particleCount; i++) {
            positions[i * 3] = 0;
            positions[i * 3 + 1] = 2;
            positions[i * 3 + 2] = 0;
            
            // Colony colors
            const colonyIdx = i % 7;
            const colony = COLONY_ORDER[colonyIdx];
            const color = new THREE.Color(COLONY_DATA[colony].hex);
            colors[i * 3] = color.r;
            colors[i * 3 + 1] = color.g;
            colors[i * 3 + 2] = color.b;
            
            velocities[i * 3] = 0;
            velocities[i * 3 + 1] = 0;
            velocities[i * 3 + 2] = 0;
        }
        
        const geometry = new THREE.BufferGeometry();
        geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));
        geometry.setAttribute('color', new THREE.BufferAttribute(colors, 3));
        
        this.celebrationVelocities = velocities;
        
        const material = new THREE.PointsMaterial({
            size: 0.12,
            vertexColors: true,
            transparent: true,
            opacity: 0,
            blending: THREE.AdditiveBlending,
            depthWrite: false
        });
        
        this.celebrationParticles = new THREE.Points(geometry, material);
        this.add(this.celebrationParticles);
    }
    
    triggerCelebration() {
        if (this.celebrationActive) return;
        
        this.celebrationActive = true;
        console.log('🎉 CONSENSUS ACHIEVED!');
        
        // Reset and launch particles
        const positions = this.celebrationParticles.geometry.attributes.position.array;
        const velocities = this.celebrationVelocities;
        const nexusPos = this.getNodePosition(3);
        
        for (let i = 0; i < positions.length; i += 3) {
            // Start at consensus pillar
            positions[i] = nexusPos.x;
            positions[i + 1] = 4;
            positions[i + 2] = nexusPos.z;
            
            // Random explosion velocity
            const theta = Math.random() * Math.PI * 2;
            const phi = Math.random() * Math.PI;
            const speed = 3 + Math.random() * 5;
            
            velocities[i] = Math.sin(phi) * Math.cos(theta) * speed;
            velocities[i + 1] = Math.abs(Math.cos(phi)) * speed + 2;
            velocities[i + 2] = Math.sin(phi) * Math.sin(theta) * speed;
        }
        
        this.celebrationParticles.material.opacity = 1;
        this.celebrationParticles.geometry.attributes.position.needsUpdate = true;
        
        // Play celebration sound
        this.playConsensusChord();
        
        // Pulse all connection lines
        this.connectionLines.forEach(line => {
            line.material.opacity = 1;
        });
    }
    
    // ═══════════════════════════════════════════════════════════════════════
    // AMBIENT PARTICLES
    // ═══════════════════════════════════════════════════════════════════════
    
    createAmbientParticles() {
        const particleCount = 200;
        const positions = new Float32Array(particleCount * 3);
        const colors = new Float32Array(particleCount * 3);
        
        for (let i = 0; i < particleCount; i++) {
            const angle = Math.random() * Math.PI * 2;
            const radius = Math.random() * 7;
            
            positions[i * 3] = Math.cos(angle) * radius;
            positions[i * 3 + 1] = Math.random() * 4;
            positions[i * 3 + 2] = Math.sin(angle) * radius;
            
            colors[i * 3] = 0.5;
            colors[i * 3 + 1] = 0.4;
            colors[i * 3 + 2] = 0.74; // Nexus purple
        }
        
        const geometry = new THREE.BufferGeometry();
        geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));
        geometry.setAttribute('color', new THREE.BufferAttribute(colors, 3));
        
        const material = new THREE.PointsMaterial({
            size: 0.04,
            vertexColors: true,
            transparent: true,
            opacity: 0.4,
            blending: THREE.AdditiveBlending
        });
        
        this.ambientParticles = new THREE.Points(geometry, material);
        this.add(this.ambientParticles);
    }
    
    // ═══════════════════════════════════════════════════════════════════════
    // ATTACK MODE - "Try to Break It" Feature
    // ═══════════════════════════════════════════════════════════════════════
    
    createAttackModePanel() {
        // Control panel for attack mode
        const canvas = document.createElement('canvas');
        canvas.width = 512;
        canvas.height = 384;
        this.attackCanvas = canvas;
        this.attackCtx = canvas.getContext('2d');
        
        this.updateAttackPanel();
        
        const texture = new THREE.CanvasTexture(canvas);
        this.attackTexture = texture;
        
        const geo = new THREE.PlaneGeometry(2.2, 1.65);
        const mat = new THREE.MeshBasicMaterial({
            map: texture,
            transparent: true,
            side: THREE.DoubleSide
        });
        
        const panel = new THREE.Mesh(geo, mat);
        panel.position.set(-6.5, 2.5, 0);
        panel.rotation.y = Math.PI / 5;
        panel.name = 'attack-panel';
        panel.userData = { type: 'attack-toggle' };
        this.attackPanel = panel;
        this.add(panel);
        
        // Attack mode toggle button
        const btnGeo = new THREE.BoxGeometry(0.8, 0.3, 0.1);
        const btnMat = new THREE.MeshPhysicalMaterial({
            color: 0xE85A2F,
            emissive: 0xE85A2F,
            emissiveIntensity: 0.3,
            metalness: 0.6,
            roughness: 0.3
        });
        
        const btn = new THREE.Mesh(btnGeo, btnMat);
        btn.position.set(-6.5, 1.5, 0.3);
        btn.rotation.y = Math.PI / 5;
        btn.name = 'attack-button';
        btn.userData = { type: 'attack-toggle', interactive: true };
        this.attackButton = btn;
        this.add(btn);
    }
    
    updateAttackPanel() {
        if (!this.attackCtx) return;
        const ctx = this.attackCtx;
        
        ctx.clearRect(0, 0, 512, 384);
        
        // Background
        ctx.fillStyle = this.attackMode ? 'rgba(100, 20, 20, 0.9)' : 'rgba(20, 20, 30, 0.9)';
        if (ctx.roundRect) {
            ctx.beginPath();
            ctx.roundRect(10, 10, 492, 364, 10);
            ctx.fill();
        } else {
            ctx.fillRect(10, 10, 492, 364);
        }
        
        // Title
        ctx.fillStyle = this.attackMode ? '#FF4444' : '#67D4E4';
        ctx.font = 'bold 28px "IBM Plex Sans", sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText(this.attackMode ? '⚔️ ATTACK MODE' : 'Try to Break It', 256, 55);
        
        // Explanation
        ctx.fillStyle = '#AAAAAA';
        ctx.font = '16px "IBM Plex Sans", sans-serif';
        ctx.textAlign = 'center';
        
        if (this.attackMode) {
            ctx.fillText('Control 2 Byzantine nodes to try', 256, 100);
            ctx.fillText('fooling the network!', 256, 125);
            
            // Attack stats
            ctx.fillStyle = '#FF6666';
            ctx.font = 'bold 20px "IBM Plex Mono", monospace';
            ctx.fillText(`Attacks: ${this.attackAttempts}`, 256, 175);
            
            ctx.fillStyle = '#66FF66';
            ctx.fillText(`Blocked: ${this.attacksBlocked}`, 256, 210);
            
            // Success rate
            const blockRate = this.attackAttempts > 0 
                ? Math.round((this.attacksBlocked / this.attackAttempts) * 100) 
                : 0;
            ctx.fillStyle = '#FFCC00';
            ctx.font = 'bold 24px "IBM Plex Mono", monospace';
            ctx.fillText(`Block Rate: ${blockRate}%`, 256, 260);
            
            // Explanation
            ctx.fillStyle = '#888888';
            ctx.font = '14px "IBM Plex Sans", sans-serif';
            ctx.fillText('Byzantine Fault Tolerance: Need 5/7', 256, 310);
            ctx.fillText('agreement for consensus', 256, 330);
            ctx.fillText('2 Byzantine faults tolerated (5 honest nodes suffice)', 256, 355);
        } else {
            ctx.fillText('Click button below to become a', 256, 100);
            ctx.fillText('Byzantine attacker!', 256, 125);
            
            ctx.fillStyle = '#666666';
            ctx.font = '14px "IBM Plex Sans", sans-serif';
            ctx.fillText('In BFT, malicious actors try to disrupt', 256, 180);
            ctx.fillText('consensus by sending conflicting messages.', 256, 205);
            
            ctx.fillStyle = '#67D4E4';
            ctx.fillText('The Fano plane structure (3 per line)', 256, 260);
            ctx.fillText('guarantees detection of up to 2 liars!', 256, 285);
            
            ctx.fillStyle = '#888888';
            ctx.font = '12px "IBM Plex Mono", monospace';
            ctx.fillText('f < n/3 → safe consensus', 256, 330);
            ctx.fillText('(f=faults, n=nodes)', 256, 350);
        }
        
        if (this.attackTexture) {
            this.attackTexture.needsUpdate = true;
        }
    }
    
    toggleAttackMode() {
        this.attackMode = !this.attackMode;
        
        if (this.attackMode) {
            // Randomly select 2 nodes for attacker to control
            this.attackerNodes.clear();
            const available = [0, 1, 2, 3, 4, 5, 6];
            for (let i = 0; i < 2; i++) {
                const idx = Math.floor(Math.random() * available.length);
                this.attackerNodes.add(available[idx]);
                available.splice(idx, 1);
            }
            
            // Mark attacker nodes visually
            this.attackerNodes.forEach(nodeIdx => {
                const station = this.stations[nodeIdx];
                const node = station?.getObjectByName('colony-node');
                if (node) {
                    node.material.color.setHex(0xFF0000);
                    node.material.emissive.setHex(0xFF0000);
                }
            });
            
            // Update button color
            if (this.attackButton) {
                this.attackButton.material.color.setHex(0x66FF66);
                this.attackButton.material.emissive.setHex(0x66FF66);
            }
        } else {
            // Reset attacker nodes
            this.attackerNodes.forEach(nodeIdx => {
                const colony = COLONY_ORDER[nodeIdx];
                const data = COLONY_DATA[colony];
                const station = this.stations[nodeIdx];
                const node = station?.getObjectByName('colony-node');
                if (node && data) {
                    node.material.color.setHex(data.hex);
                    node.material.emissive.setHex(data.hex);
                }
            });
            this.attackerNodes.clear();
            
            // Update button color
            if (this.attackButton) {
                this.attackButton.material.color.setHex(0xE85A2F);
                this.attackButton.material.emissive.setHex(0xE85A2F);
            }
            
            // Reset consensus
            this.resetConsensus();
        }
        
        this.updateAttackPanel();
    }
    
    executeAttack() {
        if (!this.attackMode || this.attackerNodes.size !== 2) return;
        
        this.attackAttempts++;
        
        // Attacker tries to send conflicting votes
        // In a real Byzantine attack, they would send APPROVE to some and REJECT to others
        const attackerArray = Array.from(this.attackerNodes);
        
        // First attacker node: vote APPROVE
        this.votes[attackerArray[0]] = VOTE_STATES.APPROVE;
        this.broadcastVote(attackerArray[0], VOTE_STATES.APPROVE);
        
        // Second attacker node: vote REJECT (conflicting!)
        this.votes[attackerArray[1]] = VOTE_STATES.REJECT;
        this.broadcastVote(attackerArray[1], VOTE_STATES.REJECT);
        
        // Update visuals
        this.updateNodeVisual(attackerArray[0], VOTE_STATES.APPROVE);
        this.updateNodeVisual(attackerArray[1], VOTE_STATES.REJECT);
        
        // The other 5 nodes detect the conflict via Fano lines
        // (each line has 3 points, so conflicting votes are detected)
        setTimeout(() => {
            // Mark Byzantine nodes as detected
            attackerArray.forEach(idx => this.markByzantine(idx));
            this.attacksBlocked++;
            this.updateAttackPanel();
            this.updateStatusDisplay();
        }, 1500);
    }
    
    updateNodeVisual(nodeIndex, voteState) {
        const station = this.stations[nodeIndex];
        if (!station) return;
        
        const ring = this.consensusRings?.[nodeIndex];
        if (ring) {
            if (voteState === VOTE_STATES.APPROVE) {
                ring.material.color.setHex(0x6FA370);
            } else if (voteState === VOTE_STATES.REJECT) {
                ring.material.color.setHex(0xE85A2F);
            }
            ring.material.opacity = 1;
        }
    }
    
    // ═══════════════════════════════════════════════════════════════════════
    // PLAQUE
    // ═══════════════════════════════════════════════════════════════════════
    
    createPlaque() {
        if (PATENT) {
            const plaque = createPlaque(PATENT, { width: 3, height: 2 });
            plaque.position.set(6, 1.2, 0);
            plaque.rotation.y = -Math.PI / 2;
            this.add(plaque);
        }
    }
    
    // ═══════════════════════════════════════════════════════════════════════
    // INTERACTION
    // ═══════════════════════════════════════════════════════════════════════
    
    onClick(intersection) {
        const object = intersection?.object;
        if (!object || !object.userData) return;
        
        // Handle attack mode toggle
        if (object.userData.type === 'attack-toggle') {
            this.toggleAttackMode();
            return;
        }
        
        // Handle voting nodes
        if (object.userData.type === 'vote-node') {
            const index = object.userData.index;
            const colony = object.userData.colony;
            
            // In attack mode, clicking attacker nodes executes attack
            if (this.attackMode && this.attackerNodes.has(index)) {
                this.executeAttack();
                return;
            }
            
            // Normal voting
            if (this.votes[index] === VOTE_STATES.PENDING || this.votes[index] === VOTE_STATES.REJECT) {
                this.castVote(index, VOTE_STATES.APPROVE);
            } else if (this.votes[index] === VOTE_STATES.APPROVE) {
                this.castVote(index, VOTE_STATES.REJECT);
            }
            
            // Play note
            this.playColonyNote(colony);
        }
    }
    
    // Alias for backward compatibility
    handleClick(point, object) {
        this.onClick({ point, object });
    }
    
    castVote(nodeIndex, voteValue) {
        this.votes[nodeIndex] = voteValue;
        this.playerVotes.add(nodeIndex);
        
        // Update visual indicator
        const station = this.stations[nodeIndex];
        const voteIndicator = station.getObjectByName('vote-indicator');
        if (voteIndicator) {
            voteIndicator.material.color.setHex(
                voteValue === VOTE_STATES.APPROVE ? 0x6FA370 : 0xE85A2F
            );
            voteIndicator.material.opacity = 1;
        }
        
        // Update consensus ring
        if (this.consensusRings[nodeIndex]) {
            this.consensusRings[nodeIndex].material.color.setHex(
                voteValue === VOTE_STATES.APPROVE ? 0x6FA370 : 0xE85A2F
            );
            this.consensusRings[nodeIndex].material.opacity = 1;
        }
        
        // Broadcast vote to connected nodes
        this.broadcastVote(nodeIndex, voteValue);
        
        // Check for consensus
        this.checkConsensus();
        
        // Update status display
        this.updateStatusDisplay();
    }
    
    checkConsensus() {
        const approves = this.votes.filter(v => v === VOTE_STATES.APPROVE).length;
        const threshold = Math.ceil(7 * 2 / 3); // 5 of 7
        
        if (approves >= threshold && !this.consensusAchieved) {
            this.consensusAchieved = true;
            this.triggerCelebration();
        }
    }
    
    markByzantine(nodeIndex) {
        this.byzantineNodes.add(nodeIndex);
        this.votes[nodeIndex] = VOTE_STATES.BYZANTINE;
        
        // Visual indication
        const station = this.stations[nodeIndex];
        const node = station.getObjectByName('colony-node');
        if (node) {
            node.material.emissive.setHex(0xFF0000);
            node.material.emissiveIntensity = 1.0;
        }
        
        // Update status
        this.updateStatusDisplay();
    }
    
    // ═══════════════════════════════════════════════════════════════════════
    // AUDIO
    // ═══════════════════════════════════════════════════════════════════════
    
    initAudio() {
        if (!this.audioContext) {
            this.audioContext = new (window.AudioContext || window.webkitAudioContext)();
        }
    }
    
    playColonyNote(colony) {
        this.initAudio();
        if (!this.audioContext) return;
        
        const data = COLONY_DATA[colony];
        if (!data) return;
        
        const oscillator = this.audioContext.createOscillator();
        const gainNode = this.audioContext.createGain();
        
        oscillator.type = 'sine';
        oscillator.frequency.setValueAtTime(data.pitch, this.audioContext.currentTime);
        
        gainNode.gain.setValueAtTime(0.2, this.audioContext.currentTime);
        gainNode.gain.exponentialRampToValueAtTime(0.01, this.audioContext.currentTime + 0.5);
        
        oscillator.connect(gainNode);
        gainNode.connect(this.audioContext.destination);
        
        oscillator.start();
        oscillator.stop(this.audioContext.currentTime + 0.5);
    }
    
    playConsensusChord() {
        this.initAudio();
        if (!this.audioContext) return;
        
        // Play all colony notes as a chord
        COLONY_ORDER.forEach((colony, i) => {
            setTimeout(() => {
                this.playColonyNote(colony);
            }, i * 50); // Slight arpeggio effect
        });
    }
    
    // ═══════════════════════════════════════════════════════════════════════
    // AUTOMATIC CONSENSUS SIMULATION
    // ═══════════════════════════════════════════════════════════════════════
    
    simulateConsensusRound() {
        // Only simulate for nodes the player hasn't voted on
        COLONY_ORDER.forEach((colony, i) => {
            if (!this.playerVotes.has(i) && this.votes[i] === VOTE_STATES.PENDING) {
                // Random vote with slight bias toward approval
                const vote = Math.random() > 0.2 ? VOTE_STATES.APPROVE : VOTE_STATES.REJECT;
                
                // Small chance of Byzantine behavior
                if (Math.random() < 0.1) {
                    this.markByzantine(i);
                } else {
                    this.castVote(i, vote);
                }
            }
        });
    }
    
    resetConsensus() {
        this.votes = new Array(7).fill(VOTE_STATES.PENDING);
        this.byzantineNodes.clear();
        this.consensusAchieved = false;
        this.playerVotes.clear();
        this.celebrationActive = false;
        
        // Reset visuals
        this.stations.forEach((station, i) => {
            const voteIndicator = station.getObjectByName('vote-indicator');
            if (voteIndicator) {
                voteIndicator.material.color.setHex(0x444444);
                voteIndicator.material.opacity = 0.5;
            }
            
            const node = station.getObjectByName('colony-node');
            if (node) {
                const color = COLONY_DATA[COLONY_ORDER[i]].hex;
                node.material.emissive.setHex(color);
                node.material.emissiveIntensity = 0.4;
            }
        });
        
        this.consensusRings.forEach(ring => {
            ring.material.color.setHex(0x444444);
            ring.material.opacity = 0.5;
        });
        
        this.updateStatusDisplay();
    }
    
    // ═══════════════════════════════════════════════════════════════════════
    // ANIMATION
    // ═══════════════════════════════════════════════════════════════════════
    
    update(deltaTime) {
        this.time += deltaTime;
        
        // Animate nodes
        this.nodes.forEach((node, i) => {
            node.position.y = 1.5 + Math.sin(this.time * 2 + i * 0.8) * 0.15;
            node.rotation.y += deltaTime * 0.5;
            node.rotation.x = Math.sin(this.time + i) * 0.1;
        });
        
        // Animate message particles
        this.animateMessages(deltaTime);
        
        // Animate celebration
        if (this.celebrationActive) {
            this.animateCelebration(deltaTime);
        }
        
        // Animate ambient particles
        if (this.ambientParticles) {
            this.ambientParticles.rotation.y += deltaTime * 0.05;
        }
        
        // Animate consensus indicator
        if (this.consensusIndicator) {
            this.consensusIndicator.rotation.y += deltaTime;
            this.consensusIndicator.position.y = 4.5 + Math.sin(this.time * 2) * 0.2;
            
            // Color based on consensus state
            const approves = this.votes.filter(v => v === VOTE_STATES.APPROVE).length;
            const t = approves / 7;
            this.consensusIndicator.material.color.setHex(
                this.consensusAchieved ? 0x6FA370 : 
                (approves >= 3 ? 0xFFAA00 : 0x67D4E4)
            );
        }
        
        // Pulse connection lines - brighten when messages are traveling
        this.connectionLines.forEach((line, i) => {
            const baseOpacity = this.consensusAchieved ? 0.7 : 0.4;
            let messageBoost = 0;
            
            // Check if any message is traveling on this line
            this.messageParticles.forEach(particle => {
                if (particle.userData.active) {
                    const lineNodes = [Math.floor(i / 3), (Math.floor(i / 3) + 1 + i % 3) % 7];
                    const from = particle.userData.fromNode;
                    const to = particle.userData.toNode;
                    if ((lineNodes.includes(from) && lineNodes.includes(to))) {
                        messageBoost = Math.max(messageBoost, 0.3);
                    }
                }
            });
            
            line.material.opacity = baseOpacity + Math.sin(this.time * 2 + i * 0.5) * 0.1 + messageBoost;
        });
        
        // Sequential ring lighting on consensus
        if (this.consensusAchieved && this.consensusRings) {
            this.consensusRings.forEach((ring, i) => {
                const delay = i * 0.15;
                const lightUp = Math.max(0, Math.sin((this.time - this.lastConsensusTime - delay) * 4));
                ring.material.opacity = 0.3 + lightUp * 0.5;
                ring.material.emissiveIntensity = lightUp;
            });
        }
        
        // Hover glow intensification for nodes
        this.nodes.forEach((node, i) => {
            const isHovered = this.hoveredStation === i;
            const targetEmissive = isHovered ? 1.5 : 0.5;
            if (node.material && node.material.emissiveIntensity !== undefined) {
                node.material.emissiveIntensity += (targetEmissive - node.material.emissiveIntensity) * 0.1;
            }
        });
        
        // Auto-simulation (if player is idle)
        if (this.time - this.lastConsensusTime > 8 && !this.consensusAchieved) {
            this.lastConsensusTime = this.time;
            this.simulateConsensusRound();
            
            // Microdelight: track consensus rounds watched
            this.microdelights.consensusRoundsWatched++;
            if (this.microdelights.consensusRoundsWatched >= 7) {
                this._dispatchMicrodelight('achievement', { name: 'consensus-observer' });
                this.microdelights.consensusRoundsWatched = -Infinity; // Only fire once
            }
        }
        
        // Reset after celebration
        if (this.consensusAchieved && this.time - this.lastConsensusTime > 12) {
            this.lastConsensusTime = this.time;
            this.resetConsensus();
        }
    }
    
    animateMessages(deltaTime) {
        this.messageParticles.forEach(particle => {
            if (!particle.userData.active) return;
            
            particle.userData.progress += deltaTime * particle.userData.speed;
            
            if (particle.userData.progress >= 1) {
                particle.visible = false;
                particle.userData.active = false;
                particle.material.opacity = 0;
                return;
            }
            
            // Interpolate position along Fano line curve
            const fromPos = this.getNodePosition(particle.userData.fromNode);
            const toPos = this.getNodePosition(particle.userData.toNode);
            const t = particle.userData.progress;
            
            // Arc trajectory
            particle.position.x = fromPos.x + (toPos.x - fromPos.x) * t;
            particle.position.z = fromPos.z + (toPos.z - fromPos.z) * t;
            particle.position.y = 1.5 + Math.sin(t * Math.PI) * 1.2;
            
            // Fade
            particle.material.opacity = Math.min(1, (1 - t) * 2);
        });
    }
    
    animateCelebration(deltaTime) {
        if (!this.celebrationParticles) return;
        
        const positions = this.celebrationParticles.geometry.attributes.position.array;
        const velocities = this.celebrationVelocities;
        
        let activeCount = 0;
        
        for (let i = 0; i < positions.length; i += 3) {
            // Apply gravity
            velocities[i + 1] -= 9.8 * deltaTime;
            
            // Apply velocity
            positions[i] += velocities[i] * deltaTime;
            positions[i + 1] += velocities[i + 1] * deltaTime;
            positions[i + 2] += velocities[i + 2] * deltaTime;
            
            // Track active particles
            if (positions[i + 1] > 0) activeCount++;
        }
        
        this.celebrationParticles.geometry.attributes.position.needsUpdate = true;
        
        // Fade out when particles have fallen
        if (activeCount < 50) {
            this.celebrationParticles.material.opacity *= 0.95;
        }
    }
    
    // ═══════════════════════════════════════════════════════════════════════
    // MICRODELIGHTS
    // ═══════════════════════════════════════════════════════════════════════
    
    _dispatchMicrodelight(type, detail = {}) {
        window.dispatchEvent(new CustomEvent('artwork-microdelight', {
            detail: { patentId: 'P1-002', type, ...detail }
        }));
    }
    
    // ═══════════════════════════════════════════════════════════════════════
    // CLEANUP
    // ═══════════════════════════════════════════════════════════════════════
    
    dispose() {
        if (this.audioContext) {
            this.audioContext.close();
        }
        
        this.traverse((obj) => {
            if (obj.geometry) obj.geometry.dispose();
            if (obj.material) {
                if (Array.isArray(obj.material)) {
                    obj.material.forEach(m => m.dispose());
                } else {
                    obj.material.dispose();
                }
            }
        });
    }
}

export function createFanoConsensusArtwork() {
    return new FanoConsensusArtwork();
}

export default FanoConsensusArtwork;
