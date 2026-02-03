/**
 * Fano Plane Visualization
 * =========================
 * 
 * 7 colony nodes arranged according to Fano plane projective geometry.
 * Each point represents one of the 7 colonies (octonion imaginary units e1-e7).
 * Each line connects 3 collinear points.
 * 
 * h(x) ≥ 0 always
 */

import * as THREE from 'three';
import {
    COLONY_ORDER,
    COLONY_COLORS,
    FANO_POINTS,
    FANO_LINES,
    DURATION_S,
    createColonyMaterial as createColonyMaterialBase
} from '../../lib/design-tokens.js';
import { createGlowMesh, createAnimatedLine, updateGlowMesh } from '../../lib/kagami-visuals.js';

// Helper to get colony color as THREE.Color
function getColonyColor(name) {
    return new THREE.Color(COLONY_COLORS[name].num);
}

// Helper for colony material
function createColonyMaterial(colonyName, options) {
    return createColonyMaterialBase(THREE, colonyName, options);
}

// ═══════════════════════════════════════════════════════════════════════════
// FANO PLANE GROUP
// ═══════════════════════════════════════════════════════════════════════════

export class FanoPlane extends THREE.Group {
    constructor(options = {}) {
        super();
        
        this.options = {
            scale: options.scale || 2,
            nodeSize: options.nodeSize || 0.4,
            lineRadius: options.lineRadius || 0.02,
            animationSpeed: options.animationSpeed || 1.0,
            ...options
        };
        
        // Store references
        this.colonyNodes = [];
        this.colonyGlows = [];
        this.fanoLines = [];
        this.labels = [];
        
        // Animation state
        this.time = 0;
        
        // Build geometry
        this.createNodes();
        this.createLines();
        
        if (options.showLabels) {
            this.createLabels();
        }
        
        this.name = 'FanoPlane';
    }
    
    // ═══════════════════════════════════════════════════════════════════════
    // NODE CREATION
    // ═══════════════════════════════════════════════════════════════════════
    
    createNodes() {
        const { scale, nodeSize } = this.options;
        
        COLONY_ORDER.forEach((colonyName, index) => {
            const pos = FANO_POINTS[index];
            const color = getColonyColor(colonyName);
            
            // Main node geometry (icosahedron for crystalline look)
            const geometry = new THREE.IcosahedronGeometry(nodeSize, 2);
            const material = createColonyMaterial(colonyName, {
                emissiveIntensity: 0.6,
                clearcoat: 1.0,
                clearcoatRoughness: 0.1
            });
            
            const node = new THREE.Mesh(geometry, material);
            node.position.set(pos[0] * scale, pos[1] * scale, pos[2]);
            node.userData = {
                colonyName,
                colonyIndex: index,
                basePosition: node.position.clone(),
                pulsePhase: (index * 0.618) * Math.PI * 2 // Golden ratio offset
            };
            
            // Create outer glow
            const glow = createGlowMesh(node, {
                color: color.clone(),
                intensity: 0.8,
                scale: 1.3
            });
            node.add(glow);
            
            // Inner core (bright emissive center)
            const coreGeometry = new THREE.SphereGeometry(nodeSize * 0.3, 16, 16);
            const coreMaterial = new THREE.MeshBasicMaterial({
                color: color.clone().multiplyScalar(1.5),
                transparent: true,
                opacity: 0.9
            });
            const core = new THREE.Mesh(coreGeometry, coreMaterial);
            node.add(core);
            node.userData.core = core;
            
            this.add(node);
            this.colonyNodes.push(node);
            this.colonyGlows.push(glow);
        });
    }
    
    // ═══════════════════════════════════════════════════════════════════════
    // LINE CREATION
    // ═══════════════════════════════════════════════════════════════════════
    
    createLines() {
        const { scale, lineRadius } = this.options;
        
        FANO_LINES.forEach((lineIndices, lineIndex) => {
            // Get colony colors for this line
            const color1 = getColonyColor(COLONY_ORDER[lineIndices[0]]);
            const color2 = getColonyColor(COLONY_ORDER[lineIndices[2]]);
            
            // Create points for the curve
            const points = lineIndices.map(i => {
                const pos = FANO_POINTS[i];
                return new THREE.Vector3(pos[0] * scale, pos[1] * scale, pos[2]);
            });
            
            // Create animated line with gradient
            const line = createAnimatedLine(points, {
                color1: color1,
                color2: color2,
                radius: lineRadius,
                segments: 32,
                flowSpeed: 0.3,
                opacity: 0.5
            });
            
            line.userData = {
                lineIndex,
                pointIndices: lineIndices
            };
            
            this.add(line);
            this.fanoLines.push(line);
        });
    }
    
    // ═══════════════════════════════════════════════════════════════════════
    // LABEL CREATION
    // ═══════════════════════════════════════════════════════════════════════
    
    createLabels() {
        // Create canvas-based sprite labels
        COLONY_ORDER.forEach((colonyName, index) => {
            const node = this.colonyNodes[index];
            const label = this.createTextSprite(
                COLONY_COLORS[colonyName].name,
                COLONY_COLORS[colonyName].hex
            );
            
            label.position.set(0, this.options.nodeSize * 1.5, 0);
            label.scale.set(0.5, 0.25, 1);
            
            node.add(label);
            this.labels.push(label);
        });
    }
    
    createTextSprite(text, color) {
        const canvas = document.createElement('canvas');
        const ctx = canvas.getContext('2d');
        canvas.width = 256;
        canvas.height = 128;
        
        // Background (transparent)
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        
        // Text
        ctx.font = 'bold 32px "Orbitron", sans-serif';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.fillStyle = color;
        ctx.fillText(text, canvas.width / 2, canvas.height / 2);
        
        const texture = new THREE.CanvasTexture(canvas);
        texture.needsUpdate = true;
        
        const material = new THREE.SpriteMaterial({
            map: texture,
            transparent: true,
            depthTest: false
        });
        
        return new THREE.Sprite(material);
    }
    
    // ═══════════════════════════════════════════════════════════════════════
    // ANIMATION UPDATE
    // ═══════════════════════════════════════════════════════════════════════
    
    update(deltaTime, camera) {
        this.time += deltaTime * this.options.animationSpeed;
        
        // Animate nodes
        this.colonyNodes.forEach((node, index) => {
            const { pulsePhase, basePosition } = node.userData;
            
            // Fibonacci-timed pulse (233ms cycle)
            const pulse = Math.sin(this.time * (1000 / 233) + pulsePhase);
            const scale = 1.0 + pulse * 0.1;
            node.scale.setScalar(scale);
            
            // Gentle floating motion
            const floatY = Math.sin(this.time * 0.5 + pulsePhase) * 0.1;
            node.position.y = basePosition.y + floatY;
            
            // Core brightness pulse
            if (node.userData.core) {
                node.userData.core.material.opacity = 0.7 + pulse * 0.3;
            }
            
            // Update glow
            const glow = this.colonyGlows[index];
            if (glow && camera) {
                updateGlowMesh(glow, camera, this.time);
            }
        });
        
        // Animate lines
        this.fanoLines.forEach((line, index) => {
            if (line.material.uniforms) {
                line.material.uniforms.time.value = this.time;
            }
        });
        
        // Gentle rotation of entire structure
        this.rotation.y = Math.sin(this.time * 0.1) * 0.1;
    }
    
    // ═══════════════════════════════════════════════════════════════════════
    // INTERACTION
    // ═══════════════════════════════════════════════════════════════════════
    
    /**
     * Get interactable nodes for raycasting
     */
    getInteractables() {
        return this.colonyNodes;
    }
    
    /**
     * Highlight a specific colony node
     */
    highlightNode(index, highlight = true) {
        const node = this.colonyNodes[index];
        if (!node) return;
        
        const targetScale = highlight ? 1.3 : 1.0;
        const targetEmissive = highlight ? 1.0 : 0.6;
        
        // Animate scale
        const currentScale = node.scale.x;
        const newScale = THREE.MathUtils.lerp(currentScale, targetScale, 0.1);
        node.scale.setScalar(newScale);
        
        // Animate emissive
        if (node.material.emissiveIntensity !== undefined) {
            node.material.emissiveIntensity = THREE.MathUtils.lerp(
                node.material.emissiveIntensity,
                targetEmissive,
                0.1
            );
        }
    }
    
    /**
     * Highlight lines connected to a node
     */
    highlightConnectedLines(nodeIndex, highlight = true) {
        const targetOpacity = highlight ? 0.9 : 0.5;
        
        FANO_LINES.forEach((lineIndices, lineIndex) => {
            if (lineIndices.includes(nodeIndex)) {
                const line = this.fanoLines[lineIndex];
                if (line.material.uniforms) {
                    line.material.uniforms.opacity.value = THREE.MathUtils.lerp(
                        line.material.uniforms.opacity.value,
                        targetOpacity,
                        0.1
                    );
                }
            }
        });
    }
    
    /**
     * Get colony info by node
     */
    getColonyInfo(node) {
        if (!node?.userData?.colonyName) return null;
        
        const name = node.userData.colonyName;
        return {
            name,
            index: node.userData.colonyIndex,
            displayName: COLONY_COLORS[name].name,
            color: COLONY_COLORS[name].hex,
            basis: COLONY_COLORS[name].basis
        };
    }
    
    // ═══════════════════════════════════════════════════════════════════════
    // DISPOSAL
    // ═══════════════════════════════════════════════════════════════════════
    
    dispose() {
        // Dispose nodes
        this.colonyNodes.forEach(node => {
            if (node.geometry) node.geometry.dispose();
            if (node.material) node.material.dispose();
        });
        
        // Dispose lines
        this.fanoLines.forEach(line => {
            if (line.geometry) line.geometry.dispose();
            if (line.material) line.material.dispose();
        });
        
        // Dispose labels
        this.labels.forEach(label => {
            if (label.material.map) label.material.map.dispose();
            if (label.material) label.material.dispose();
        });
        
        // Clear arrays
        this.colonyNodes = [];
        this.colonyGlows = [];
        this.fanoLines = [];
        this.labels = [];
    }
}

// ═══════════════════════════════════════════════════════════════════════════
// FACTORY FUNCTION
// ═══════════════════════════════════════════════════════════════════════════

export function createFanoPlane(options = {}) {
    return new FanoPlane(options);
}

export default FanoPlane;
