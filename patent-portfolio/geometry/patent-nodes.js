/**
 * Patent Nodes Visualization
 * ===========================
 * 
 * 54 patentable innovations displayed as interactive 3D cards.
 * Organized by priority (P1 gold, P2 cyan, P3 white) and category.
 * 
 * h(x) ≥ 0 always
 */

import * as THREE from 'three';
import {
    COLONY_COLORS,
    COLONY_ORDER,
    PATENT_CATEGORIES,
    PATENT_PRIORITIES,
    VOID_COLORS,
    TEXT_COLORS,
    DURATION_S,
    getColonyColor as getColonyColorBase
} from '../../lib/design-tokens.js';

// Helper to get colony color as THREE.Color
function getColonyColor(index) {
    return getColonyColorBase(THREE, index);
}

// Helper to get colony THREE.Color by name
function getColonyThreeColor(name) {
    return new THREE.Color(COLONY_COLORS[name]?.num || COLONY_COLORS.crystal.num);
}

// ═══════════════════════════════════════════════════════════════════════════
// PATENT DATA
// ═══════════════════════════════════════════════════════════════════════════

// Full patent list with priority and category
const PATENTS = [
    // Priority 1 - Foundational (6)
    { id: 'P1-001', name: 'EFE-CBF Safety Optimizer', priority: 'P1', category: 'B', desc: 'AI action selection with formal safety guarantees via Control Barrier Functions' },
    { id: 'P1-002', name: '7-Colony Fano Consensus', priority: 'P1', category: 'C', desc: 'Byzantine fault tolerance using Fano plane topology for 7-agent consensus' },
    { id: 'P1-003', name: 'E8 Lattice Semantic Router', priority: 'P1', category: 'A', desc: 'Optimal 8D packing for semantic vector routing' },
    { id: 'P1-004', name: 'S15 Hopf Fibration Encoding', priority: 'P1', category: 'A', desc: 'Octonionic Hopf fibration for neural network state encoding' },
    { id: 'P1-005', name: 'OrganismRSSM Architecture', priority: 'P1', category: 'D', desc: 'Specialized world model with catastrophe prediction' },
    { id: 'P1-006', name: 'Hybrid Quantum-Safe Crypto', priority: 'P1', category: 'E', desc: 'ML-KEM + ML-DSA with classical fallback' },
    
    // Priority 2 - Core Differentiators (18)
    { id: 'P2-001', name: 'Catastrophe KAN Layers', priority: 'P2', category: 'A', desc: 'Kolmogorov-Arnold networks for discontinuity prediction' },
    { id: 'P2-002', name: 'G2 Irrep Tower Attention', priority: 'P2', category: 'A', desc: 'Exceptional Lie group symmetry in attention mechanisms' },
    { id: 'P2-003', name: 'Jordan Algebra F4 Propagation', priority: 'P2', category: 'A', desc: 'Belief propagation using F4 Jordan algebra structure' },
    { id: 'P2-004', name: 'Freudenthal E7 Belief System', priority: 'P2', category: 'A', desc: 'Triple system formulation for uncertainty quantification' },
    { id: 'P2-005', name: 'Search-Augmented Reasoner', priority: 'P2', category: 'J', desc: 'MCTS + CFR + EFE for game-theoretic planning' },
    { id: 'P2-006', name: 'Cross-Hub CRDT Coordination', priority: 'P2', category: 'C', desc: 'Conflict-free replicated data types for multi-hub sync' },
    { id: 'P2-007', name: 'CALM Order Processing', priority: 'P2', category: 'C', desc: 'Monotonic commerce operations without global coordination' },
    { id: 'P2-008', name: 'Context-Bound Encryption', priority: 'P2', category: 'E', desc: 'Encryption keys derived from usage context' },
    { id: 'P2-009', name: 'Active Inference Presence', priority: 'P2', category: 'F', desc: 'Predictive smart home based on expected free energy' },
    { id: 'P2-010', name: 'Music-Reactive Lighting', priority: 'P2', category: 'F', desc: 'Real-time spectrum analysis for ambient lighting' },
    { id: 'P2-011', name: 'Earcon Orchestration Engine', priority: 'P2', category: 'G', desc: 'Spatial audio cues for ambient intelligence' },
    { id: 'P2-012', name: 'Voice Persona Synthesis', priority: 'P2', category: 'G', desc: 'Consistent personality across TTS outputs' },
    { id: 'P2-013', name: 'Freelancer Bidding Agent', priority: 'P2', category: 'H', desc: 'Autonomous job market participation' },
    { id: 'P2-014', name: 'Intent-Based Automation', priority: 'P2', category: 'F', desc: 'Natural language to smart home action translation' },
    { id: 'P2-015', name: 'Weyl Equivariant Convolution', priority: 'P2', category: 'A', desc: 'Root system symmetry preservation in CNNs' },
    { id: 'P2-016', name: 'Octonion Neural Layers', priority: 'P2', category: 'A', desc: '8D non-associative algebra for deep learning' },
    { id: 'P2-017', name: 'Ralph Parallel Audit', priority: 'P2', category: 'B', desc: '6 parallel judges with Byzantine convergence' },
    { id: 'P2-018', name: 'Symbiotic Intent Parser', priority: 'P2', category: 'J', desc: 'Deep context understanding for user intent' },
    
    // Priority 3 - Supporting (30)
    { id: 'P3-001', name: 'Figma-to-Code Pipeline', priority: 'P3', category: 'I', desc: 'Direct Figma design to implementation' },
    { id: 'P3-002', name: 'GenUX Token System', priority: 'P3', category: 'I', desc: 'Generative design token propagation' },
    { id: 'P3-003', name: 'HTML Agent Framework', priority: 'P3', category: 'I', desc: 'Cognitive substrate in HTML documents' },
    { id: 'P3-004', name: 'Composio Integration Layer', priority: 'P3', category: 'I', desc: 'Unified tool composition interface' },
    { id: 'P3-005', name: 'Sensorimotor Bridge', priority: 'P3', category: 'F', desc: 'Perception-action loop for smart home' },
    { id: 'P3-006', name: 'Home Assistant Voice', priority: 'P3', category: 'F', desc: 'Extended voice capabilities for HA' },
    { id: 'P3-007', name: 'Shade Optimization', priority: 'P3', category: 'F', desc: 'Energy-aware window shade control' },
    { id: 'P3-008', name: 'Temperature Scheduling', priority: 'P3', category: 'F', desc: 'Predictive HVAC optimization' },
    { id: 'P3-009', name: 'PBFT State Machine', priority: 'P3', category: 'C', desc: 'Practical Byzantine state replication' },
    { id: 'P3-010', name: 'Curriculum Training', priority: 'P3', category: 'D', desc: 'Progressive difficulty for world model training' },
    { id: 'P3-011', name: 'JAX TPU Pipeline', priority: 'P3', category: 'D', desc: 'Optimized multi-device training' },
    { id: 'P3-012', name: 'RSSM Extensions', priority: 'P3', category: 'D', desc: 'Enhanced recurrent state space model' },
    { id: 'P3-013', name: 'Head Architecture Search', priority: 'P3', category: 'D', desc: 'Automated output head discovery' },
    { id: 'P3-014', name: 'Loss Function Composition', priority: 'P3', category: 'D', desc: 'Multi-objective training optimization' },
    { id: 'P3-015', name: 'Privacy-Preserving Inference', priority: 'P3', category: 'E', desc: 'Secure computation for AI models' },
    { id: 'P3-016', name: 'Key Rotation Protocol', priority: 'P3', category: 'E', desc: 'Seamless cryptographic key updates' },
    { id: 'P3-017', name: 'Voice Cloning Safety', priority: 'P3', category: 'G', desc: 'Consent-aware voice synthesis' },
    { id: 'P3-018', name: 'Spatial Audio Mixing', priority: 'P3', category: 'G', desc: '3D sound field composition' },
    { id: 'P3-019', name: 'Portfolio Optimization', priority: 'P3', category: 'H', desc: 'Risk-adjusted asset allocation' },
    { id: 'P3-020', name: 'Market Signal Detection', priority: 'P3', category: 'H', desc: 'Pattern recognition for trading' },
    { id: 'P3-021', name: 'Invoice Automation', priority: 'P3', category: 'H', desc: 'Intelligent billing workflow' },
    { id: 'P3-022', name: 'Organism Deployment', priority: 'P3', category: 'I', desc: 'Unified agent deployment system' },
    { id: 'P3-023', name: 'Tool Composition Framework', priority: 'P3', category: 'I', desc: 'Skill orchestration runtime' },
    { id: 'P3-024', name: 'Error Recovery System', priority: 'P3', category: 'B', desc: 'Comprehensive fault handling' },
    { id: 'P3-025', name: 'Safety Barrier Verification', priority: 'P3', category: 'B', desc: 'Formal verification of h(x) >= 0' },
    { id: 'P3-026', name: 'Constraint Satisfaction', priority: 'P3', category: 'B', desc: 'Safe action space pruning' },
    { id: 'P3-027', name: 'Domain Adapter System', priority: 'P3', category: 'J', desc: 'Task-specific reasoning adaptation' },
    { id: 'P3-028', name: 'Chess Reasoning Engine', priority: 'P3', category: 'J', desc: 'Specialized game strategy module' },
    { id: 'P3-029', name: 'Catastrophe Visualization', priority: 'P3', category: 'K', desc: 'Interactive discontinuity rendering' },
    { id: 'P3-030', name: 'Patent Portfolio Display', priority: 'P3', category: 'K', desc: '3D WebXR patent visualization' }
];

// ═══════════════════════════════════════════════════════════════════════════
// PATENT NODE CLASS
// ═══════════════════════════════════════════════════════════════════════════

class PatentCard extends THREE.Group {
    constructor(patent, options = {}) {
        super();
        
        this.patent = patent;
        this.options = options;
        
        // State
        this.isHovered = false;
        this.isSelected = false;
        
        // Get priority settings
        const priorityConfig = PATENT_PRIORITIES[patent.priority];
        const category = PATENT_CATEGORIES.find(c => c.id === patent.category);
        const colonyColor = getColonyThreeColor(category?.colony || 'crystal');
        
        // Card dimensions
        const width = 1.2;
        const height = 0.8;
        const depth = 0.05;
        
        // Main card body
        const geometry = new THREE.BoxGeometry(width, height, depth);
        const material = new THREE.MeshPhysicalMaterial({
            color: colonyColor.clone().multiplyScalar(0.3),
            emissive: colonyColor.clone().multiplyScalar(0.1),
            emissiveIntensity: 0.3,
            metalness: 0.5,
            roughness: 0.3,
            clearcoat: 1.0,
            clearcoatRoughness: 0.1,
            transparent: true,
            opacity: priorityConfig.opacity
        });
        
        this.cardMesh = new THREE.Mesh(geometry, material);
        this.add(this.cardMesh);
        
        // Priority indicator (top edge glow)
        const edgeGeometry = new THREE.BoxGeometry(width, 0.05, depth + 0.01);
        const edgeMaterial = new THREE.MeshBasicMaterial({
            color: priorityConfig.color,
            transparent: true,
            opacity: 0.9
        });
        const edge = new THREE.Mesh(edgeGeometry, edgeMaterial);
        edge.position.y = height / 2 - 0.025;
        this.add(edge);
        
        // Category icon (colored sphere)
        const iconGeometry = new THREE.SphereGeometry(0.08, 16, 16);
        const iconMaterial = new THREE.MeshBasicMaterial({
            color: colonyColor,
            transparent: true,
            opacity: 0.9
        });
        this.icon = new THREE.Mesh(iconGeometry, iconMaterial);
        this.icon.position.set(-width/2 + 0.15, height/2 - 0.15, depth/2 + 0.01);
        this.add(this.icon);
        
        // Text labels (canvas-based sprites)
        this.createTextLabels(width, height, depth);
        
        // Store for interaction
        this.userData = {
            patent: patent,
            priority: patent.priority,
            category: patent.category,
            isInteractable: true
        };
        
        this.name = `PatentCard_${patent.id}`;
    }
    
    createTextLabels(width, height, depth) {
        // ID label
        const idLabel = this.createTextSprite(this.patent.id, {
            fontSize: 18,
            color: '#F5F0E8',
            align: 'left'
        });
        idLabel.position.set(-width/2 + 0.35, height/2 - 0.15, depth/2 + 0.02);
        idLabel.scale.set(0.4, 0.2, 1);
        this.add(idLabel);
        
        // Name label
        const nameLabel = this.createTextSprite(this.patent.name, {
            fontSize: 22,
            color: '#F5F0E8',
            fontWeight: 'bold',
            maxWidth: width * 180
        });
        nameLabel.position.set(0, 0.1, depth/2 + 0.02);
        nameLabel.scale.set(0.8, 0.3, 1);
        this.add(nameLabel);
        
        // Category label
        const category = PATENT_CATEGORIES.find(c => c.id === this.patent.category);
        if (category) {
            const catLabel = this.createTextSprite(category.name, {
                fontSize: 14,
                color: '#C4BFBA'
            });
            catLabel.position.set(0, -0.15, depth/2 + 0.02);
            catLabel.scale.set(0.6, 0.15, 1);
            this.add(catLabel);
        }
    }
    
    createTextSprite(text, options = {}) {
        const canvas = document.createElement('canvas');
        const ctx = canvas.getContext('2d');
        canvas.width = 512;
        canvas.height = 128;
        
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        
        const fontSize = options.fontSize || 24;
        const fontWeight = options.fontWeight || 'normal';
        ctx.font = `${fontWeight} ${fontSize}px 'Orbitron', 'IBM Plex Sans', sans-serif`;
        ctx.textAlign = options.align || 'center';
        ctx.textBaseline = 'middle';
        ctx.fillStyle = options.color || '#FFFFFF';
        
        // Handle text wrapping if needed
        const maxWidth = options.maxWidth || canvas.width - 20;
        const x = options.align === 'left' ? 10 : canvas.width / 2;
        ctx.fillText(text, x, canvas.height / 2, maxWidth);
        
        const texture = new THREE.CanvasTexture(canvas);
        texture.needsUpdate = true;
        
        const material = new THREE.SpriteMaterial({
            map: texture,
            transparent: true,
            depthTest: true,
            depthWrite: false
        });
        
        return new THREE.Sprite(material);
    }
    
    // Interaction methods
    setHovered(hovered) {
        this.isHovered = hovered;
        const targetScale = hovered ? 1.1 : 1.0;
        const targetEmissive = hovered ? 0.6 : 0.3;
        
        // Animate scale
        this.scale.setScalar(THREE.MathUtils.lerp(this.scale.x, targetScale, 0.2));
        
        // Animate emissive
        if (this.cardMesh.material.emissiveIntensity !== undefined) {
            this.cardMesh.material.emissiveIntensity = THREE.MathUtils.lerp(
                this.cardMesh.material.emissiveIntensity,
                targetEmissive,
                0.2
            );
        }
    }
    
    setSelected(selected) {
        this.isSelected = selected;
        // Could trigger detail panel
    }
    
    update(time) {
        // Gentle floating animation
        const phase = this.patent.id.charCodeAt(3) * 0.1;
        this.position.y += Math.sin(time * 0.5 + phase) * 0.0005;
        
        // Icon pulse
        if (this.icon) {
            const pulse = 1.0 + Math.sin(time * 2 + phase) * 0.1;
            this.icon.scale.setScalar(pulse);
        }
    }
    
    dispose() {
        this.traverse(child => {
            if (child.geometry) child.geometry.dispose();
            if (child.material) {
                if (child.material.map) child.material.map.dispose();
                child.material.dispose();
            }
        });
    }
}

// ═══════════════════════════════════════════════════════════════════════════
// PATENT NODES GROUP
// ═══════════════════════════════════════════════════════════════════════════

export class PatentNodes extends THREE.Group {
    constructor(options = {}) {
        super();
        
        this.options = {
            baseDistance: options.baseDistance || 12,
            layerSpacing: options.layerSpacing || 4,
            cardsPerRing: options.cardsPerRing || 12,
            ...options
        };
        
        // Store cards
        this.cards = [];
        this.hoveredCard = null;
        this.selectedCard = null;
        
        // Animation state
        this.time = 0;
        
        // Build
        this.createCards();
        
        this.name = 'PatentNodes';
    }
    
    createCards() {
        // Sort patents by priority
        const p1Patents = PATENTS.filter(p => p.priority === 'P1');
        const p2Patents = PATENTS.filter(p => p.priority === 'P2');
        const p3Patents = PATENTS.filter(p => p.priority === 'P3');
        
        // Place P1 patents (inner ring)
        this.placePatentsInRing(p1Patents, PATENT_PRIORITIES.P1.distance, 0);
        
        // Place P2 patents (middle ring)
        this.placePatentsInRing(p2Patents, PATENT_PRIORITIES.P2.distance, 0.5);
        
        // Place P3 patents (outer ring, multiple layers)
        this.placePatentsInRing(p3Patents.slice(0, 15), PATENT_PRIORITIES.P3.distance, 1);
        this.placePatentsInRing(p3Patents.slice(15), PATENT_PRIORITIES.P3.distance + 4, 1.5);
    }
    
    placePatentsInRing(patents, distance, yOffset) {
        const count = patents.length;
        
        patents.forEach((patent, index) => {
            const card = new PatentCard(patent, this.options);
            
            // Position in ring
            const angle = (index / count) * Math.PI * 2;
            const x = Math.cos(angle) * distance;
            const z = Math.sin(angle) * distance;
            const y = yOffset * this.options.layerSpacing - 2;
            
            card.position.set(x, y, z);
            
            // Face center
            card.lookAt(0, y, 0);
            card.rotateY(Math.PI);
            
            // Scale by priority
            const priorityConfig = PATENT_PRIORITIES[patent.priority];
            card.scale.setScalar(priorityConfig.scale);
            
            this.add(card);
            this.cards.push(card);
        });
    }
    
    // ═══════════════════════════════════════════════════════════════════════
    // ANIMATION UPDATE
    // ═══════════════════════════════════════════════════════════════════════
    
    update(deltaTime) {
        this.time += deltaTime;
        
        // Update all cards
        this.cards.forEach(card => {
            card.update(this.time);
        });
        
        // Slow rotation of the entire group
        this.rotation.y += deltaTime * 0.02;
    }
    
    // ═══════════════════════════════════════════════════════════════════════
    // INTERACTION
    // ═══════════════════════════════════════════════════════════════════════
    
    /**
     * Get all interactable objects for raycasting
     */
    getInteractables() {
        return this.cards.map(card => card.cardMesh);
    }
    
    /**
     * Handle hover
     */
    setHoveredCard(cardMesh) {
        // Clear previous hover
        if (this.hoveredCard) {
            this.hoveredCard.setHovered(false);
        }
        
        // Find parent card
        if (cardMesh) {
            const card = this.cards.find(c => c.cardMesh === cardMesh);
            if (card) {
                card.setHovered(true);
                this.hoveredCard = card;
                return card.patent;
            }
        }
        
        this.hoveredCard = null;
        return null;
    }
    
    /**
     * Handle selection
     */
    selectCard(cardMesh) {
        // Clear previous selection
        if (this.selectedCard) {
            this.selectedCard.setSelected(false);
        }
        
        // Find parent card
        if (cardMesh) {
            const card = this.cards.find(c => c.cardMesh === cardMesh);
            if (card) {
                card.setSelected(true);
                this.selectedCard = card;
                return card.patent;
            }
        }
        
        this.selectedCard = null;
        return null;
    }
    
    /**
     * Filter cards by priority
     */
    filterByPriority(priority) {
        this.cards.forEach(card => {
            const match = !priority || card.patent.priority === priority;
            card.visible = match;
        });
    }
    
    /**
     * Filter cards by category
     */
    filterByCategory(categoryId) {
        this.cards.forEach(card => {
            const match = !categoryId || card.patent.category === categoryId;
            card.visible = match;
        });
    }
    
    /**
     * Reset filters
     */
    resetFilters() {
        this.cards.forEach(card => {
            card.visible = true;
        });
    }
    
    /**
     * Get patent info by card
     */
    getPatentInfo(card) {
        if (!card?.patent) return null;
        
        const patent = card.patent;
        const category = PATENT_CATEGORIES.find(c => c.id === patent.category);
        
        return {
            ...patent,
            categoryName: category?.name,
            categoryIcon: category?.icon,
            colonyName: category?.colony,
            priorityConfig: PATENT_PRIORITIES[patent.priority]
        };
    }
    
    // ═══════════════════════════════════════════════════════════════════════
    // DISPOSAL
    // ═══════════════════════════════════════════════════════════════════════
    
    dispose() {
        this.cards.forEach(card => card.dispose());
        this.cards = [];
    }
}

// ═══════════════════════════════════════════════════════════════════════════
// FACTORY FUNCTION
// ═══════════════════════════════════════════════════════════════════════════

export function createPatentNodes(options = {}) {
    return new PatentNodes(options);
}

// Export patent data for external use
export { PATENTS, PATENT_CATEGORIES };

export default PatentNodes;
