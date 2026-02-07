/**
 * P1-005: OrganismRSSM Architecture Artwork
 * =========================================
 * 
 * Recurrent State Space Model visualization with actual RSSM mathematics:
 * - Deterministic state h_t (hidden state trajectory)
 * - Stochastic state z_t (latent samples)
 * - Prior vs Posterior distributions
 * - Imagination rollouts (future prediction)
 * - 7 colonies with E8 encoding and S7 phase routing
 * 
 * Based on: packages/kagami/core/training/jax/rssm.py
 * 
 * h(x) ≥ 0 always
 */

import * as THREE from 'three';
import { createPlaque } from '../components/plaque.js';
import { PATENTS } from '../components/info-panel.js';

const PATENT = PATENTS.find(p => p.id === 'P1-005');

function softmax(logits) {
    const max = Math.max(...logits);
    const exp = logits.map(x => Math.exp(x - max));
    const sum = exp.reduce((a, b) => a + b, 0);
    return exp.map(x => x / sum);
}

const COLONY_DATA = [
    { name: 'Spark', color: 0xFF6B35, basis: 'e₁' },
    { name: 'Forge', color: 0xD4AF37, basis: 'e₂' },
    { name: 'Flow', color: 0x4ECDC4, basis: 'e₃' },
    { name: 'Nexus', color: 0x9B7EBD, basis: 'e₄' },
    { name: 'Beacon', color: 0xF59E0B, basis: 'e₅' },
    { name: 'Grove', color: 0x7EB77F, basis: 'e₆' },
    { name: 'Crystal', color: 0x67D4E4, basis: 'e₇' }
];

// RSSM architecture constants (from config)
const RSSM_CONFIG = {
    deterDim: 64,      // Hidden state dimension (simplified for viz)
    stochDim: 32,      // Stochastic state dimension
    numColonies: 7,
    discreteClasses: 32,  // Latent classes
    horizons: [1, 4, 16]  // H-JEPA prediction horizons
};

export class OrganismRSSMArtwork extends THREE.Group {
    constructor() {
        super();
        this.name = 'artwork-organism-rssm';
        this.time = 0;
        
        // State visualization
        this.deterStates = [];      // h_t deterministic state nodes
        this.stochStates = [];      // z_t stochastic state nodes
        this.priorPosterior = null; // Distribution visualization
        this.trajectoryLine = null; // State trajectory
        this.imaginationPaths = []; // Future rollouts
        
        // Colony nodes
        this.colonyNodes = [];
        
        // Interaction state
        this.isImagining = false;
        this.imaginationHorizon = 4;
        this.currentStep = 0;
        
        this.create();
    }
    
    create() {
        // Main visualization area
        this.createStateSpace();
        this.createColonyRing();
        this.createPriorPosteriorDisplay();
        this.createTrajectoryVisualization();
        this.createImaginationPanel();
        this.createFormulasDisplay();
        this.createInteractionHints();
        
        // Plaque
        if (PATENT) {
            const plaque = createPlaque(PATENT, { width: 2.8, height: 1.8 });
            plaque.position.set(5, 1.5, 0);
            plaque.rotation.y = -Math.PI / 2;
            this.add(plaque);
        }
        
        this.userData = { patentId: 'P1-005', interactive: true };
    }
    
    // ═══════════════════════════════════════════════════════════════════════
    // STATE SPACE VISUALIZATION
    // ═══════════════════════════════════════════════════════════════════════
    
    createStateSpace() {
        // Central state space sphere representing the latent manifold
        const stateSpaceGeo = new THREE.SphereGeometry(1.5, 64, 64);
        const stateSpaceMat = new THREE.MeshPhysicalMaterial({
            color: 0x1A1A2E,
            transparent: true,
            opacity: 0.3,
            metalness: 0.2,
            roughness: 0.8,
            side: THREE.DoubleSide
        });
        
        this.stateSpace = new THREE.Mesh(stateSpaceGeo, stateSpaceMat);
        this.stateSpace.position.y = 2.5;
        this.add(this.stateSpace);
        
        // Wireframe for latent structure
        const wireGeo = new THREE.IcosahedronGeometry(1.55, 2);
        const wireMat = new THREE.MeshBasicMaterial({
            color: 0x67D4E4,
            wireframe: true,
            transparent: true,
            opacity: 0.15
        });
        const wire = new THREE.Mesh(wireGeo, wireMat);
        wire.position.y = 2.5;
        this.add(wire);
        
        // Create deterministic state visualization (h_t)
        this.createDeterministicState();
        
        // Create stochastic state visualization (z_t)
        this.createStochasticState();
        
        // State space label
        this.createStateSpaceLabel();
    }
    
    createDeterministicState() {
        // h_t represented as a solid core (deterministic = predictable)
        const hGeo = new THREE.OctahedronGeometry(0.25, 1);
        const hMat = new THREE.MeshPhysicalMaterial({
            color: 0x6FA370,
            emissive: 0x6FA370,
            emissiveIntensity: 0.5,
            metalness: 0.6,
            roughness: 0.3
        });
        
        this.hState = new THREE.Mesh(hGeo, hMat);
        this.hState.position.set(0, 2.5, 0);
        this.add(this.hState);
        
        // Trail showing h_t trajectory
        const trailPoints = [];
        for (let i = 0; i < 50; i++) {
            trailPoints.push(new THREE.Vector3(0, 2.5, 0));
        }
        
        const trailGeo = new THREE.BufferGeometry().setFromPoints(trailPoints);
        const trailMat = new THREE.LineBasicMaterial({
            color: 0x6FA370,
            transparent: true,
            opacity: 0.5
        });
        
        this.hTrail = new THREE.Line(trailGeo, trailMat);
        this.add(this.hTrail);
        this.hTrailPoints = trailPoints;
    }
    
    createStochasticState() {
        // z_t represented as a fuzzy cloud (stochastic = probabilistic)
        const zGroup = new THREE.Group();
        
        // Core
        const zCoreGeo = new THREE.DodecahedronGeometry(0.15, 0);
        const zCoreMat = new THREE.MeshPhysicalMaterial({
            color: 0xFF6B35,
            emissive: 0xFF6B35,
            emissiveIntensity: 0.4,
            metalness: 0.3,
            roughness: 0.5,
            transparent: true,
            opacity: 0.9
        });
        this.zCore = new THREE.Mesh(zCoreGeo, zCoreMat);
        zGroup.add(this.zCore);
        
        // Uncertainty cloud (samples from posterior)
        const cloudCount = 30;
        const cloudGeo = new THREE.BufferGeometry();
        const cloudPositions = new Float32Array(cloudCount * 3);
        const cloudColors = new Float32Array(cloudCount * 3);
        
        for (let i = 0; i < cloudCount; i++) {
            const theta = Math.random() * Math.PI * 2;
            const phi = Math.acos(2 * Math.random() - 1);
            const r = 0.15 + Math.random() * 0.15;
            
            cloudPositions[i * 3] = r * Math.sin(phi) * Math.cos(theta);
            cloudPositions[i * 3 + 1] = r * Math.sin(phi) * Math.sin(theta);
            cloudPositions[i * 3 + 2] = r * Math.cos(phi);
            
            cloudColors[i * 3] = 1;
            cloudColors[i * 3 + 1] = 0.4;
            cloudColors[i * 3 + 2] = 0.2;
        }
        
        cloudGeo.setAttribute('position', new THREE.BufferAttribute(cloudPositions, 3));
        cloudGeo.setAttribute('color', new THREE.BufferAttribute(cloudColors, 3));
        
        const cloudMat = new THREE.PointsMaterial({
            size: 0.05,
            vertexColors: true,
            transparent: true,
            opacity: 0.7,
            blending: THREE.AdditiveBlending
        });
        
        this.zCloud = new THREE.Points(cloudGeo, cloudMat);
        zGroup.add(this.zCloud);
        
        zGroup.position.set(0.3, 2.5, 0.2);
        this.zState = zGroup;
        this.add(zGroup);
    }
    
    createStateSpaceLabel() {
        const canvas = document.createElement('canvas');
        canvas.width = 512;
        canvas.height = 256;
        const ctx = canvas.getContext('2d');
        
        ctx.fillStyle = 'rgba(0,0,0,0.8)';
        ctx.fillRect(0, 0, 512, 256);
        
        // Title
        ctx.fillStyle = '#67D4E4';
        ctx.font = 'bold 28px "IBM Plex Mono", monospace';
        ctx.textAlign = 'center';
        ctx.fillText('State Space', 256, 40);
        
        // h_t description
        ctx.fillStyle = '#6FA370';
        ctx.font = '20px "IBM Plex Mono", monospace';
        ctx.textAlign = 'left';
        ctx.fillText('h_t = Deterministic State', 30, 90);
        ctx.fillStyle = '#9E9994';
        ctx.font = '14px "IBM Plex Sans", sans-serif';
        ctx.fillText('BlockGRU hidden state [B, 7, 64]', 30, 115);
        ctx.fillText('Captures temporal dynamics', 30, 135);
        
        // z_t description
        ctx.fillStyle = '#FF6B35';
        ctx.font = '20px "IBM Plex Mono", monospace';
        ctx.fillText('z_t = Stochastic State', 30, 175);
        ctx.fillStyle = '#9E9994';
        ctx.font = '14px "IBM Plex Sans", sans-serif';
        ctx.fillText('Categorical + embedded [B, 7, 32]', 30, 200);
        ctx.fillText('Captures uncertainty', 30, 220);
        
        const texture = new THREE.CanvasTexture(canvas);
        const labelGeo = new THREE.PlaneGeometry(2.5, 1.25);
        const labelMat = new THREE.MeshBasicMaterial({
            map: texture,
            transparent: true,
            side: THREE.DoubleSide
        });
        const label = new THREE.Mesh(labelGeo, labelMat);
        label.position.set(-2.5, 3.5, 0);
        label.rotation.y = Math.PI / 6;
        this.add(label);
    }
    
    // ═══════════════════════════════════════════════════════════════════════
    // COLONY RING (7 Colonies)
    // ═══════════════════════════════════════════════════════════════════════
    
    createColonyRing() {
        const radius = 2.5;
        
        COLONY_DATA.forEach((colony, i) => {
            const angle = (i / 7) * Math.PI * 2 - Math.PI / 2;
            const x = Math.cos(angle) * radius;
            const z = Math.sin(angle) * radius;
            
            // Colony node
            const nodeGeo = new THREE.IcosahedronGeometry(0.2, 1);
            const nodeMat = new THREE.MeshPhysicalMaterial({
                color: colony.color,
                emissive: colony.color,
                emissiveIntensity: 0.3,
                metalness: 0.4,
                roughness: 0.4
            });
            
            const node = new THREE.Mesh(nodeGeo, nodeMat);
            node.position.set(x, 2.5, z);
            node.userData = { colonyIndex: i, colonyName: colony.name };
            this.colonyNodes.push(node);
            this.add(node);
            
            // Connection to center (E8 projection)
            const connectionGeo = new THREE.BufferGeometry().setFromPoints([
                new THREE.Vector3(x, 2.5, z),
                new THREE.Vector3(0, 2.5, 0)
            ]);
            const connectionMat = new THREE.LineBasicMaterial({
                color: colony.color,
                transparent: true,
                opacity: 0.2
            });
            const connection = new THREE.Line(connectionGeo, connectionMat);
            this.add(connection);
            
            // Colony label
            const labelCanvas = document.createElement('canvas');
            labelCanvas.width = 128;
            labelCanvas.height = 64;
            const ctx = labelCanvas.getContext('2d');
            
            ctx.fillStyle = '#' + colony.color.toString(16).padStart(6, '0');
            ctx.font = 'bold 14px "IBM Plex Mono", monospace';
            ctx.textAlign = 'center';
            ctx.fillText(colony.name, 64, 25);
            ctx.font = '12px "IBM Plex Mono", monospace';
            ctx.fillText(colony.basis, 64, 45);
            
            const labelTex = new THREE.CanvasTexture(labelCanvas);
            const labelGeo = new THREE.PlaneGeometry(0.6, 0.3);
            const labelMat = new THREE.MeshBasicMaterial({
                map: labelTex,
                transparent: true,
                side: THREE.DoubleSide
            });
            const label = new THREE.Mesh(labelGeo, labelMat);
            label.position.set(x * 1.3, 2.5 + 0.4, z * 1.3);
            label.lookAt(0, 2.5, 0);
            label.rotation.y += Math.PI;
            this.add(label);
        });
    }
    
    // ═══════════════════════════════════════════════════════════════════════
    // PRIOR / POSTERIOR VISUALIZATION
    // ═══════════════════════════════════════════════════════════════════════
    
    createPriorPosteriorDisplay() {
        const panelGroup = new THREE.Group();
        panelGroup.position.set(3.5, 2.5, -2);
        panelGroup.rotation.y = -Math.PI / 4;
        
        // Background panel
        const bgGeo = new THREE.PlaneGeometry(2.5, 2);
        const bgMat = new THREE.MeshBasicMaterial({
            color: 0x0A0A0F,
            transparent: true,
            opacity: 0.9,
            side: THREE.DoubleSide
        });
        const bg = new THREE.Mesh(bgGeo, bgMat);
        panelGroup.add(bg);
        
        // Dynamic canvas for distributions
        this.priorPosteriorCanvas = document.createElement('canvas');
        this.priorPosteriorCanvas.width = 512;
        this.priorPosteriorCanvas.height = 400;
        
        this.priorPosteriorTexture = new THREE.CanvasTexture(this.priorPosteriorCanvas);
        const displayGeo = new THREE.PlaneGeometry(2.4, 1.9);
        const displayMat = new THREE.MeshBasicMaterial({
            map: this.priorPosteriorTexture,
            transparent: true,
            side: THREE.DoubleSide
        });
        const display = new THREE.Mesh(displayGeo, displayMat);
        display.position.z = 0.01;
        panelGroup.add(display);
        
        this.priorPosteriorPanel = panelGroup;
        this.add(panelGroup);
        
        this.updatePriorPosteriorDisplay();
    }
    
    updatePriorPosteriorDisplay() {
        const ctx = this.priorPosteriorCanvas.getContext('2d');
        const w = this.priorPosteriorCanvas.width;
        const h = this.priorPosteriorCanvas.height;
        const K = RSSM_CONFIG.discreteClasses;

        ctx.fillStyle = 'rgba(10, 10, 15, 0.95)';
        ctx.fillRect(0, 0, w, h);

        ctx.fillStyle = '#67D4E4';
        ctx.font = 'bold 24px "IBM Plex Mono", monospace';
        ctx.textAlign = 'center';
        ctx.fillText('Prior vs Posterior (categorical)', w/2, 35);

        // Categorical: p and q are probability vectors over K classes
        const priorProbs = softmax(new Array(K).fill(0).map((_, i) => (Math.sin(this.time * 0.5 + i * 0.3) * 0.5)));
        const postProbs = softmax(new Array(K).fill(0).map((_, i) => (Math.sin(this.time * 0.7 + 1 + i * 0.2) * 0.6)));

        const drawCategorical = (probs, color, label, yOffset) => {
            ctx.fillStyle = color;
            ctx.font = '16px "IBM Plex Mono", monospace';
            ctx.textAlign = 'left';
            ctx.fillText(label, 30, yOffset);
            const barW = (w - 60) / K;
            const maxH = 70;
            for (let i = 0; i < K; i++) {
                const x = 30 + i * barW;
                const barH = probs[i] * maxH;
                ctx.fillStyle = color;
                ctx.fillRect(x, yOffset + 25 - barH, Math.max(1, barW - 1), barH);
            }
        };

        drawCategorical(priorProbs, 'rgb(155, 126, 189)', 'Prior p(z_t | h_t)', 100);
        drawCategorical(postProbs, 'rgb(0, 255, 136)', 'Posterior q(z_t | h_t, o_t)', 230);

        // Real KL(q || p) for categorical: sum_k q_k log(q_k / p_k)
        let kl = 0;
        for (let k = 0; k < K; k++) {
            const qk = Math.max(1e-10, postProbs[k]);
            const pk = Math.max(1e-10, priorProbs[k]);
            kl += qk * (Math.log(qk) - Math.log(pk));
        }
        ctx.fillStyle = '#FF6B35';
        ctx.font = '18px "IBM Plex Mono", monospace';
        ctx.textAlign = 'center';
        ctx.fillText(`KL(q‖p) = ${kl.toFixed(4)} nats`, w/2, 350);

        ctx.fillStyle = '#9E9994';
        ctx.font = '12px "IBM Plex Sans", sans-serif';
        ctx.fillText('KL(q‖p) = Σ q_k log(q_k/p_k)  — categorical', w/2, 380);

        this.priorPosteriorTexture.needsUpdate = true;
    }
    
    // ═══════════════════════════════════════════════════════════════════════
    // TRAJECTORY VISUALIZATION
    // ═══════════════════════════════════════════════════════════════════════
    
    createTrajectoryVisualization() {
        // Show actual trajectory through state space
        const trajectoryGroup = new THREE.Group();
        
        // Generate sample trajectory points
        this.trajectoryPoints = [];
        for (let t = 0; t < 30; t++) {
            const angle = t * 0.3;
            const r = 0.5 + Math.sin(t * 0.2) * 0.3;
            const y = Math.sin(t * 0.15) * 0.5;
            
            this.trajectoryPoints.push(new THREE.Vector3(
                Math.cos(angle) * r,
                2.5 + y,
                Math.sin(angle) * r
            ));
        }
        
        // Trajectory curve
        const trajCurve = new THREE.CatmullRomCurve3(this.trajectoryPoints);
        const trajGeo = new THREE.TubeGeometry(trajCurve, 100, 0.02, 8, false);
        const trajMat = new THREE.MeshBasicMaterial({
            color: 0x67D4E4,
            transparent: true,
            opacity: 0.6
        });
        this.trajectoryMesh = new THREE.Mesh(trajGeo, trajMat);
        trajectoryGroup.add(this.trajectoryMesh);
        
        // Observation markers along trajectory
        for (let t = 0; t < 30; t += 5) {
            const point = this.trajectoryPoints[t];
            const obsGeo = new THREE.SphereGeometry(0.03, 8, 8);
            const obsMat = new THREE.MeshBasicMaterial({
                color: 0xF5F0E8,
                transparent: true,
                opacity: 0.8
            });
            const obs = new THREE.Mesh(obsGeo, obsMat);
            obs.position.copy(point);
            trajectoryGroup.add(obs);
        }
        
        this.add(trajectoryGroup);
    }
    
    // ═══════════════════════════════════════════════════════════════════════
    // IMAGINATION (FUTURE PREDICTION)
    // ═══════════════════════════════════════════════════════════════════════
    
    createImaginationPanel() {
        // Panel showing imagination/rollout capability
        const panelGroup = new THREE.Group();
        panelGroup.position.set(-3.5, 2.5, -2);
        panelGroup.rotation.y = Math.PI / 4;
        
        // Background
        const bgGeo = new THREE.PlaneGeometry(2.5, 2);
        const bgMat = new THREE.MeshBasicMaterial({
            color: 0x0A0A0F,
            transparent: true,
            opacity: 0.9,
            side: THREE.DoubleSide
        });
        const bg = new THREE.Mesh(bgGeo, bgMat);
        panelGroup.add(bg);
        
        // Dynamic canvas
        this.imaginationCanvas = document.createElement('canvas');
        this.imaginationCanvas.width = 512;
        this.imaginationCanvas.height = 400;
        
        this.imaginationTexture = new THREE.CanvasTexture(this.imaginationCanvas);
        const displayGeo = new THREE.PlaneGeometry(2.4, 1.9);
        const displayMat = new THREE.MeshBasicMaterial({
            map: this.imaginationTexture,
            transparent: true,
            side: THREE.DoubleSide
        });
        const display = new THREE.Mesh(displayGeo, displayMat);
        display.position.z = 0.01;
        panelGroup.add(display);
        
        this.imaginationPanel = panelGroup;
        this.add(panelGroup);
        
        this.updateImaginationDisplay();
    }
    
    updateImaginationDisplay() {
        const ctx = this.imaginationCanvas.getContext('2d');
        const w = this.imaginationCanvas.width;
        const h = this.imaginationCanvas.height;
        
        ctx.fillStyle = 'rgba(10, 10, 15, 0.95)';
        ctx.fillRect(0, 0, w, h);
        
        // Title
        ctx.fillStyle = '#FF6B35';
        ctx.font = 'bold 24px "IBM Plex Mono", monospace';
        ctx.textAlign = 'center';
        ctx.fillText('Imagination Rollout', w/2, 35);
        
        // Explanation
        ctx.fillStyle = '#9E9994';
        ctx.font = '14px "IBM Plex Sans", sans-serif';
        ctx.fillText('Pure latent dynamics (no observations)', w/2, 60);
        
        // Draw imagination timeline
        const horizons = RSSM_CONFIG.horizons;
        const startX = 60;
        const endX = w - 60;
        const y = 120;
        
        // Timeline
        ctx.strokeStyle = '#333';
        ctx.lineWidth = 2;
        ctx.beginPath();
        ctx.moveTo(startX, y);
        ctx.lineTo(endX, y);
        ctx.stroke();
        
        // Current state
        ctx.fillStyle = '#6FA370';
        ctx.beginPath();
        ctx.arc(startX, y, 10, 0, Math.PI * 2);
        ctx.fill();
        ctx.fillStyle = '#67D4E4';
        ctx.font = '12px "IBM Plex Mono", monospace';
        ctx.textAlign = 'center';
        ctx.fillText('t', startX, y + 25);
        
        // Predicted states at horizons
        horizons.forEach((horizon, i) => {
            const x = startX + (horizon / 20) * (endX - startX);
            const confidence = 1 - horizon * 0.04;
            
            ctx.fillStyle = `rgba(255, 107, 53, ${confidence})`;
            ctx.beginPath();
            ctx.arc(x, y, 8, 0, Math.PI * 2);
            ctx.fill();
            
            // Uncertainty cone
            ctx.strokeStyle = `rgba(255, 107, 53, ${confidence * 0.3})`;
            ctx.lineWidth = 1;
            ctx.beginPath();
            ctx.moveTo(startX, y);
            ctx.lineTo(x, y - horizon * 2);
            ctx.lineTo(x, y + horizon * 2);
            ctx.closePath();
            ctx.stroke();
            
            ctx.fillStyle = '#FF6B35';
            ctx.font = '12px "IBM Plex Mono", monospace';
            ctx.fillText(`t+${horizon}`, x, y + 25);
        });
        
        // H-JEPA label
        ctx.fillStyle = '#67D4E4';
        ctx.font = '16px "IBM Plex Mono", monospace';
        ctx.textAlign = 'center';
        ctx.fillText('H-JEPA Multi-Horizon Prediction', w/2, 180);
        
        // State equations
        ctx.fillStyle = '#9B7EBD';
        ctx.font = '14px "IBM Plex Mono", monospace';
        ctx.textAlign = 'left';
        
        const equations = [
            'h\'_t = GRU(h_{t-1}, z_{t-1}, a_{t-1})',
            'z_t ~ p(z_t | h_t)  [prior]',
            'ô_t = decoder(h_t, z_t)',
            'r̂_t, v̂_t = heads(h_t, z_t)'
        ];
        
        equations.forEach((eq, i) => {
            ctx.fillText(eq, 50, 220 + i * 25);
        });
        
        // Imagination status
        const status = this.isImagining ? 'IMAGINING...' : 'Click to imagine';
        ctx.fillStyle = this.isImagining ? '#6FA370' : '#9E9994';
        ctx.font = '16px "IBM Plex Mono", monospace';
        ctx.textAlign = 'center';
        ctx.fillText(status, w/2, 360);
        
        this.imaginationTexture.needsUpdate = true;
    }
    
    // ═══════════════════════════════════════════════════════════════════════
    // FORMULAS DISPLAY
    // ═══════════════════════════════════════════════════════════════════════
    
    createFormulasDisplay() {
        const canvas = document.createElement('canvas');
        canvas.width = 600;
        canvas.height = 300;
        const ctx = canvas.getContext('2d');
        
        ctx.fillStyle = 'rgba(0,0,0,0.85)';
        ctx.fillRect(0, 0, 600, 300);
        
        // Border
        ctx.strokeStyle = '#67D4E4';
        ctx.lineWidth = 2;
        ctx.strokeRect(5, 5, 590, 290);
        
        // Title
        ctx.fillStyle = '#67D4E4';
        ctx.font = 'bold 22px "IBM Plex Mono", monospace';
        ctx.textAlign = 'center';
        ctx.fillText('OrganismRSSM Architecture', 300, 35);
        
        // Core equations
        ctx.fillStyle = '#F5F0E8';
        ctx.font = '14px "IBM Plex Mono", monospace';
        ctx.textAlign = 'left';
        
        const formulas = [
            { label: 'Encoding:', formula: '(e8, s7) = encode(o_t)' },
            { label: 'Colony Project:', formula: 'o_col = E8ToColony(e8, s7)' },
            { label: 'Prior Dynamics:', formula: 'h\'_t = BlockGRU(z_{t-1} ⊕ a_{t-1}, h_{t-1})' },
            { label: 'Posterior:', formula: 'h_t = SimNorm(FanoAttn(MLP(h\'_t ⊕ o_col)))' },
            { label: 'Stochastic:', formula: 'z_t ~ Categorical(softmax(W_post · h_t))' },
            { label: 'KL Loss:', formula: 'L_kl = α_dyn · KL(sg(q)||p) + α_rep · KL(q||sg(p))' }
        ];
        
        formulas.forEach((f, i) => {
            ctx.fillStyle = '#9B7EBD';
            ctx.fillText(f.label, 30, 75 + i * 35);
            ctx.fillStyle = '#F5F0E8';
            ctx.fillText(f.formula, 180, 75 + i * 35);
        });
        
        const texture = new THREE.CanvasTexture(canvas);
        const geo = new THREE.PlaneGeometry(3.5, 1.75);
        const mat = new THREE.MeshBasicMaterial({
            map: texture,
            transparent: true,
            side: THREE.DoubleSide
        });
        const display = new THREE.Mesh(geo, mat);
        display.position.set(0, 0.8, 3.5);
        this.add(display);
    }
    
    // ═══════════════════════════════════════════════════════════════════════
    // INTERACTION HINTS
    // ═══════════════════════════════════════════════════════════════════════
    
    createInteractionHints() {
        const canvas = document.createElement('canvas');
        canvas.width = 400;
        canvas.height = 100;
        const ctx = canvas.getContext('2d');
        
        ctx.fillStyle = 'rgba(0,0,0,0.7)';
        ctx.fillRect(0, 0, 400, 100);
        
        ctx.fillStyle = '#9E9994';
        ctx.font = '14px "IBM Plex Sans", sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText('💡 Click colonies to see their hidden states', 200, 30);
        ctx.fillText('🔮 Watch h_t and z_t evolve in real-time', 200, 55);
        ctx.fillText('🌀 Imagination shows pure latent prediction', 200, 80);
        
        const texture = new THREE.CanvasTexture(canvas);
        const geo = new THREE.PlaneGeometry(2, 0.5);
        const mat = new THREE.MeshBasicMaterial({
            map: texture,
            transparent: true,
            side: THREE.DoubleSide
        });
        const hints = new THREE.Mesh(geo, mat);
        hints.position.set(0, 0.3, 0);
        hints.rotation.x = -Math.PI / 2;
        this.add(hints);
    }
    
    // ═══════════════════════════════════════════════════════════════════════
    // ANIMATION
    // ═══════════════════════════════════════════════════════════════════════
    
    update(deltaTime) {
        this.time += deltaTime;
        
        // Update h_t position (deterministic trajectory)
        const hAngle = this.time * 0.5;
        const hRadius = 0.3 + Math.sin(this.time * 0.3) * 0.2;
        const hY = 2.5 + Math.sin(this.time * 0.4) * 0.3;
        
        this.hState.position.set(
            Math.cos(hAngle) * hRadius,
            hY,
            Math.sin(hAngle) * hRadius
        );
        this.hState.rotation.y = this.time;
        
        // Update h trail
        this.hTrailPoints.pop();
        this.hTrailPoints.unshift(this.hState.position.clone());
        this.hTrail.geometry.setFromPoints(this.hTrailPoints);
        
        // Update z_t position (follows h_t with stochastic offset)
        const zOffset = new THREE.Vector3(
            Math.sin(this.time * 3) * 0.15,
            Math.cos(this.time * 2.5) * 0.1,
            Math.sin(this.time * 2.8) * 0.15
        );
        this.zState.position.copy(this.hState.position).add(zOffset);
        this.zCore.rotation.x = this.time * 2;
        this.zCore.rotation.z = this.time * 1.5;
        
        // Update z cloud (uncertainty samples)
        const cloudPositions = this.zCloud.geometry.attributes.position.array;
        for (let i = 0; i < cloudPositions.length / 3; i++) {
            const theta = Math.random() * Math.PI * 2;
            const phi = Math.acos(2 * Math.random() - 1);
            const uncertainty = 0.15 + Math.sin(this.time + i) * 0.05;
            const r = uncertainty + Math.random() * 0.1;
            
            cloudPositions[i * 3] = r * Math.sin(phi) * Math.cos(theta);
            cloudPositions[i * 3 + 1] = r * Math.sin(phi) * Math.sin(theta);
            cloudPositions[i * 3 + 2] = r * Math.cos(phi);
        }
        this.zCloud.geometry.attributes.position.needsUpdate = true;
        
        // Update colony nodes (activity based on proximity to h_t)
        this.colonyNodes.forEach((node, i) => {
            const dist = node.position.distanceTo(this.hState.position);
            const activity = Math.max(0, 1 - dist / 3);
            node.material.emissiveIntensity = 0.2 + activity * 0.6;
            
            // Subtle float
            node.position.y = 2.5 + Math.sin(this.time * 2 + i * 0.9) * 0.05;
        });
        
        // Update state space wireframe rotation
        if (this.stateSpace) {
            this.stateSpace.rotation.y = this.time * 0.1;
        }
        
        // Update prior/posterior display
        if (Math.floor(this.time * 5) % 3 === 0) {
            this.updatePriorPosteriorDisplay();
        }
        
        // Update imagination display
        if (Math.floor(this.time * 3) % 2 === 0) {
            this.updateImaginationDisplay();
        }
    }
    
    // ═══════════════════════════════════════════════════════════════════════
    // INTERACTION
    // ═══════════════════════════════════════════════════════════════════════
    
    onClick(intersection) {
        // Check if clicked on imagination panel
        if (intersection?.object === this.imaginationPanel?.children[0]) {
            this.toggleImagination();
        }
        
        // Check if clicked on colony
        const colonyIndex = intersection?.object?.userData?.colonyIndex;
        if (colonyIndex !== undefined) {
            this.highlightColony(colonyIndex);
        }
    }
    
    toggleImagination() {
        this.isImagining = !this.isImagining;
        console.log('🔮 Imagination mode:', this.isImagining ? 'ON' : 'OFF');
        this.updateImaginationDisplay();
    }
    
    highlightColony(index) {
        const colony = COLONY_DATA[index];
        console.log(`🔬 Colony ${colony.name} (${colony.basis}) selected`);
        
        // Pulse the selected colony
        const node = this.colonyNodes[index];
        const originalIntensity = node.material.emissiveIntensity;
        node.material.emissiveIntensity = 1.0;
        
        setTimeout(() => {
            node.material.emissiveIntensity = originalIntensity;
        }, 500);
    }
    
    dispose() {
        this.traverse((obj) => {
            if (obj.geometry) obj.geometry.dispose();
            if (obj.material) obj.material.dispose();
            if (obj.material?.map) obj.material.map.dispose();
        });
    }
}

export function createOrganismRSSMArtwork() {
    return new OrganismRSSMArtwork();
}

export default OrganismRSSMArtwork;
