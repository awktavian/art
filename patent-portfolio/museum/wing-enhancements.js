/**
 * Wing Visual Enhancements (Simplified)
 * =====================================
 * 
 * Pei-inspired: Clean architecture, no clutter
 * Each wing has ONE subtle differentiator:
 * 
 * - SPARK: Copper accent wall
 * - FORGE: Brass floor inlay
 * - FLOW: Reflection pool
 * - NEXUS: Perforated wall
 * - BEACON: Vertical window slot
 * - GROVE: Green textured wall
 * - CRYSTAL: Faceted glass wall
 * 
 * NO particles. Let architecture speak.
 * 
 * h(x) ≥ 0 always
 */

import * as THREE from 'three';
import { COLONY_DATA, COLONY_ORDER, DIMENSIONS } from './architecture.js';

// ═══════════════════════════════════════════════════════════════════════════
// SIMPLIFIED WING ENHANCEMENT MANAGER
// ═══════════════════════════════════════════════════════════════════════════

export class WingEnhancementManager {
    constructor(scene) {
        this.scene = scene;
        this.enhancements = new Map();
        this.time = 0;
    }
    
    init() {
        // Create architectural enhancements for each wing
        COLONY_ORDER.forEach(colony => {
            const data = COLONY_DATA[colony];
            const enhancement = this._createWingEnhancement(colony, data);
            if (enhancement) {
                this.enhancements.set(colony, enhancement);
                this.scene.add(enhancement.group);
            }
        });
        console.log('Wing enhancements: 7 architectural accents active');
    }
    
    _createWingEnhancement(colony, data) {
        const angle = data.wingAngle;
        const wingLength = 28;
        const corridorWidth = 4;
        const group = new THREE.Group();
        group.name = `wing-enhancement-${colony}`;
        
        // Position at wing entrance
        const entranceX = Math.cos(angle) * 12;
        const entranceZ = Math.sin(angle) * 12;
        group.position.set(entranceX, 0, entranceZ);
        group.rotation.y = -angle + Math.PI;
        
        const color = data.hex;
        
        switch (colony) {
            case 'spark': {
                // Animated copper patina wall — color shifts over time
                const wallGeo = new THREE.PlaneGeometry(corridorWidth * 0.8, 4);
                const wallMat = new THREE.MeshPhysicalMaterial({
                    color: 0xB87333, emissive: 0xFF6B35, emissiveIntensity: 0.05,
                    metalness: 0.9, roughness: 0.35
                });
                const wall = new THREE.Mesh(wallGeo, wallMat);
                wall.position.set(0, 2.5, 2);
                wall.name = 'spark-copper-wall';
                group.add(wall);
                return { group, type: 'spark', wall };
            }
            case 'forge': {
                // Brass floor inlay pattern (reflective geometric pattern)
                const inlayGeo = new THREE.PlaneGeometry(corridorWidth * 0.6, 8);
                const inlayMat = new THREE.MeshPhysicalMaterial({
                    color: 0xD4AF37, metalness: 0.95, roughness: 0.1,
                    clearcoat: 0.8, clearcoatRoughness: 0.1
                });
                const inlay = new THREE.Mesh(inlayGeo, inlayMat);
                inlay.rotation.x = -Math.PI / 2;
                inlay.position.set(0, 0.02, 5);
                inlay.name = 'forge-brass-inlay';
                group.add(inlay);
                
                // Geometric pattern overlay (wireframe grid)
                const patternGeo = new THREE.PlaneGeometry(corridorWidth * 0.6, 8, 6, 12);
                const pattern = new THREE.Mesh(patternGeo, new THREE.MeshBasicMaterial({
                    color: 0xD4AF37, wireframe: true, transparent: true, opacity: 0.3
                }));
                pattern.rotation.x = -Math.PI / 2;
                pattern.position.set(0, 0.025, 5);
                group.add(pattern);
                return { group, type: 'forge' };
            }
            case 'flow': {
                // Reflection pool — a mirror-like water surface
                const poolGeo = new THREE.CircleGeometry(1.5, 32);
                const poolMat = new THREE.MeshPhysicalMaterial({
                    color: 0x1A3A4A, metalness: 0.1, roughness: 0.05,
                    transmission: 0.3, thickness: 0.5
                });
                const pool = new THREE.Mesh(poolGeo, poolMat);
                pool.rotation.x = -Math.PI / 2;
                pool.position.set(0, 0.01, 6);
                pool.name = 'flow-reflection-pool';
                group.add(pool);
                
                // Subtle ripple ring
                const rippleGeo = new THREE.TorusGeometry(1.0, 0.01, 8, 64);
                const ripple = new THREE.Mesh(rippleGeo, new THREE.MeshBasicMaterial({
                    color: 0x4ECDC4, transparent: true, opacity: 0.15
                }));
                ripple.rotation.x = Math.PI / 2;
                ripple.position.set(0, 0.02, 6);
                ripple.name = 'flow-ripple';
                group.add(ripple);
                return { group, type: 'flow', ripple };
            }
            case 'nexus': {
                // Perforated wall with light penetration
                const wallGroup = new THREE.Group();
                wallGroup.position.set(corridorWidth * 0.4, 0, 3);
                
                // Base wall
                const baseGeo = new THREE.PlaneGeometry(0.5, 4);
                const base = new THREE.Mesh(baseGeo, new THREE.MeshPhysicalMaterial({
                    color: 0x2A2A3A, metalness: 0.3, roughness: 0.7
                }));
                base.position.y = 2.5;
                wallGroup.add(base);
                
                // Perforation holes (small lit circles)
                for (let row = 0; row < 6; row++) {
                    for (let col = 0; col < 3; col++) {
                        const holeGeo = new THREE.CircleGeometry(0.03, 8);
                        const hole = new THREE.Mesh(holeGeo, new THREE.MeshBasicMaterial({
                            color: 0x9B7EBD, transparent: true, opacity: 0.4
                        }));
                        hole.position.set(
                            (col - 1) * 0.1,
                            1.0 + row * 0.5,
                            0.01
                        );
                        wallGroup.add(hole);
                    }
                }
                group.add(wallGroup);
                return { group, type: 'nexus' };
            }
            case 'beacon': {
                // Vertical light slot with animated beam
                const slotGeo = new THREE.PlaneGeometry(0.15, 4.5);
                const slotMat = new THREE.MeshBasicMaterial({
                    color: 0xF59E0B, transparent: true, opacity: 0.2
                });
                const slot = new THREE.Mesh(slotGeo, slotMat);
                slot.position.set(corridorWidth * 0.35, 2.5, 4);
                slot.name = 'beacon-light-slot';
                group.add(slot);
                
                // Light beam
                const beamGeo = new THREE.CylinderGeometry(0.05, 0.3, 4, 8, 1, true);
                const beamMat = new THREE.MeshBasicMaterial({
                    color: 0xF59E0B, transparent: true, opacity: 0.06,
                    side: THREE.DoubleSide
                });
                const beam = new THREE.Mesh(beamGeo, beamMat);
                beam.position.set(corridorWidth * 0.35, 2.5, 4);
                beam.rotation.z = Math.PI / 2;
                beam.name = 'beacon-beam';
                group.add(beam);
                return { group, type: 'beacon', beam };
            }
            case 'grove': {
                // Green textured wall with vine-like growth
                const wallGeo = new THREE.PlaneGeometry(corridorWidth * 0.5, 3);
                const wallMat = new THREE.MeshPhysicalMaterial({
                    color: 0x2D4A2E, emissive: 0x7EB77F, emissiveIntensity: 0.03,
                    roughness: 0.9, metalness: 0.0
                });
                const wall = new THREE.Mesh(wallGeo, wallMat);
                wall.position.set(-corridorWidth * 0.35, 2, 4);
                wall.name = 'grove-green-wall';
                group.add(wall);
                
                // Vine lines
                for (let v = 0; v < 5; v++) {
                    const vinePoints = [];
                    const baseX = -corridorWidth * 0.35;
                    for (let p = 0; p < 8; p++) {
                        vinePoints.push(new THREE.Vector3(
                            baseX + Math.sin(p * 0.5 + v) * 0.2,
                            0.5 + p * 0.4,
                            4.01
                        ));
                    }
                    const vineGeo = new THREE.BufferGeometry().setFromPoints(vinePoints);
                    const vine = new THREE.Line(vineGeo, new THREE.LineBasicMaterial({
                        color: 0x7EB77F, transparent: true, opacity: 0.3
                    }));
                    vine.name = `grove-vine-${v}`;
                    group.add(vine);
                }
                return { group, type: 'grove' };
            }
            case 'crystal': {
                // Faceted glass wall with prismatic refraction
                const facetGeo = new THREE.IcosahedronGeometry(1.2, 1);
                const facetMat = new THREE.MeshPhysicalMaterial({
                    color: 0xCCEEFF, metalness: 0.0, roughness: 0.0,
                    transmission: 0.8, thickness: 0.5, ior: 2.0,
                    clearcoat: 1.0
                });
                const facet = new THREE.Mesh(facetGeo, facetMat);
                facet.position.set(corridorWidth * 0.3, 2.5, 5);
                facet.scale.set(1, 1.5, 0.3);
                facet.name = 'crystal-facet-wall';
                group.add(facet);
                return { group, type: 'crystal', facet };
            }
        }
        return null;
    }
    
    update(delta, cameraPosition) {
        this.time += delta;
        const t = this.time;
        
        // Spark: copper patina color shift
        const sparkWall = this.scene.getObjectByName('spark-copper-wall');
        if (sparkWall?.material) {
            const patina = Math.sin(t * 0.05) * 0.5 + 0.5;
            sparkWall.material.color.setHSL(0.07 + patina * 0.05, 0.6, 0.35 + patina * 0.1);
            sparkWall.material.emissiveIntensity = 0.03 + Math.sin(t * 0.3) * 0.02;
        }
        
        // Flow: ripple animation
        const ripple = this.scene.getObjectByName('flow-ripple');
        if (ripple) {
            const phase = (t * 0.3) % 1;
            ripple.scale.setScalar(0.5 + phase * 0.8);
            ripple.material.opacity = 0.15 * (1 - phase);
        }
        
        // Beacon: beam intensity animation
        const beam = this.scene.getObjectByName('beacon-beam');
        if (beam?.material) {
            beam.material.opacity = 0.04 + Math.sin(t * 0.5) * 0.02;
        }
        
        // Crystal: slow rotation
        const facet = this.scene.getObjectByName('crystal-facet-wall');
        if (facet) {
            facet.rotation.y = Math.sin(t * 0.1) * 0.1;
        }
        
        // Grove: vine growth animation
        for (let v = 0; v < 5; v++) {
            const vine = this.scene.getObjectByName(`grove-vine-${v}`);
            if (vine?.geometry) {
                const pos = vine.geometry.attributes.position;
                for (let i = 0; i < pos.count; i++) {
                    const baseX = pos.getX(i);
                    pos.setX(i, baseX + Math.sin(t * 0.5 + i * 0.3 + v) * 0.001);
                }
                pos.needsUpdate = true;
            }
        }
    }
    
    dispose() {
        this.enhancements.forEach(e => {
            e.group.traverse(obj => {
                if (obj.geometry) obj.geometry.dispose();
                if (obj.material) obj.material.dispose();
            });
            e.group.parent?.remove(e.group);
        });
        this.enhancements.clear();
    }
}

// Export for compatibility
export default WingEnhancementManager;
