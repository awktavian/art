/**
 * Gallery Loader
 * ==============
 * 
 * Dynamically loads and positions patent artworks
 * throughout the museum galleries.
 * 
 * h(x) ≥ 0 always
 */

import * as THREE from 'three';
import { DIMENSIONS, COLONY_DATA, COLONY_ORDER } from './architecture.js';

// Import P1 artworks
import { createEFECBFArtwork } from '../artworks/p1-efe-cbf.js';
import { createFanoConsensusArtwork } from '../artworks/p1-fano-consensus.js';
import { createE8LatticeArtwork } from '../artworks/p1-e8-lattice.js';
import { createS15HopfArtwork } from '../artworks/p1-s15-hopf.js';
import { createOrganismRSSMArtwork } from '../artworks/p1-organism-rssm.js';
import { createQuantumSafeArtwork } from '../artworks/p1-quantum-safe.js';

// Import components
import { InfoPanel, PATENTS } from '../components/info-panel.js';
import { createPlaque } from '../components/plaque.js';

// Import template system for P2/P3
import { createTemplateArtwork } from '../artworks/artwork-templates.js';

// Import custom P2 and P3 artworks
import { createP2Artwork } from '../artworks/p2-artworks.js';
import { createP3Artwork } from '../artworks/p3-artworks.js';
import { createInstancedPedestals, collectArtworkPositions, hideOriginalPedestals } from '../lib/instanced-elements.js';
import { getVisitorIdentity } from '../lib/visitor-identity.js';

// ═══════════════════════════════════════════════════════════════════════════
// ARTWORK PLACEMENT CONFIG
// ═══════════════════════════════════════════════════════════════════════════

const GALLERY_PLACEMENTS = {
    // Crystal Wing - Math (A) + Safety (B)
    crystal: {
        categories: ['A', 'B'],
        artworks: [
            { id: 'P1-001', factory: createEFECBFArtwork, position: { x: 0, y: 0, z: 20 }, scale: 1 },
            { id: 'P1-003', factory: createE8LatticeArtwork, position: { x: -8, y: 0, z: 25 }, scale: 1 },
            { id: 'P1-004', factory: createS15HopfArtwork, position: { x: 8, y: 0, z: 25 }, scale: 1 }
        ]
    },
    
    // Nexus Wing - Consensus (C) + Reasoning (J)
    nexus: {
        categories: ['C', 'J'],
        artworks: [
            { id: 'P1-002', factory: createFanoConsensusArtwork, position: { x: -15, y: 0, z: 15 }, scale: 1 }
        ]
    },
    
    // Grove Wing - World Models (D)
    grove: {
        categories: ['D'],
        artworks: [
            { id: 'P1-005', factory: createOrganismRSSMArtwork, position: { x: 15, y: 0, z: -15 }, scale: 1 }
        ]
    },
    
    // Forge Wing - Crypto (E) + Platform (I)
    forge: {
        categories: ['E', 'I'],
        artworks: [
            { id: 'P1-006', factory: createQuantumSafeArtwork, position: { x: -15, y: 0, z: -15 }, scale: 1 }
        ]
    },
    
    // Flow Wing - Smart Home (F)
    flow: {
        categories: ['F'],
        artworks: []
    },
    
    // Beacon Wing - Economic (H)
    beacon: {
        categories: ['H'],
        artworks: []
    },
    
    // Spark Wing - Voice (G) + Visual (K)
    spark: {
        categories: ['G', 'K'],
        artworks: []
    }
};

// Distance within which a wing's P2/P3 artworks are loaded
const WING_LOAD_DISTANCE = 38;

// ═══════════════════════════════════════════════════════════════════════════
// GALLERY LOADER CLASS
// ═══════════════════════════════════════════════════════════════════════════

export class GalleryLoader {
    constructor(scene) {
        this.scene = scene;
        this.loadedArtworks = new Map();
        this.infoPanel = new InfoPanel();
        /** @type {Array<{ patent: object, colony: string, position: THREE.Vector3, rotationY: number, placeholder: THREE.Group }>} */
        this.pendingArtworks = [];
        this.loadedColonies = new Set();
        
        // Listen for patent selection events
        window.addEventListener('patent-select', (e) => {
            const patentId = e.detail?.patentId;
            if (patentId) {
                getVisitorIdentity().recordVisit(patentId);
                this.infoPanel.show(patentId);
            }
        });
    }
    
    /**
     * Load all galleries: P1 immediately, P2/P3 as placeholders to load when visitor approaches wing
     */
    loadAllGalleries() {
        const artworkGroup = new THREE.Group();
        artworkGroup.name = 'artworks';
        
        // Load P1 artworks immediately
        Object.entries(GALLERY_PLACEMENTS).forEach(([colony, config]) => {
            config.artworks.forEach(artworkConfig => {
                try {
                    const artwork = this.loadArtwork(artworkConfig);
                    if (artwork) {
                        artworkGroup.add(artwork);
                        this.loadedArtworks.set(artworkConfig.id, artwork);
                    }
                } catch (error) {
                    console.warn(`Failed to load artwork ${artworkConfig.id}:`, error);
                }
            });
        });
        
        // P2/P3: add placeholders and register pending loads by wing
        this.addTemplatePlaceholders(artworkGroup);
        
        this.scene.add(artworkGroup);
        this.artworkGroup = artworkGroup;

        // Instanced pedestals for all slots (P1 + placeholders)
        artworkGroup.updateMatrixWorld(true);
        const positions = collectArtworkPositions(this.loadedArtworks);
        const placeholderPositions = [];
        this.pendingArtworks.forEach((p) => {
            const v = new THREE.Vector3();
            p.placeholder.getWorldPosition(v);
            placeholderPositions.push(v);
        });
        const allPositions = [...positions, ...placeholderPositions];
        if (allPositions.length > 0) {
            const instancedPedestals = createInstancedPedestals(allPositions);
            artworkGroup.add(instancedPedestals);
            hideOriginalPedestals(artworkGroup);
        }
        
        console.log(`📚 Loaded ${this.loadedArtworks.size} P1 artworks, ${this.pendingArtworks.length} P2/P3 on approach`);
        return artworkGroup;
    }
    
    /**
     * Add placeholder nodes for P2/P3 and register pending loads by colony
     */
    addTemplatePlaceholders(group) {
        const templatePatents = PATENTS.filter(p => 
            (p.priority === 'P2' || p.priority === 'P3') && 
            !this.loadedArtworks.has(p.id)
        );
        const patentsByColony = {};
        templatePatents.forEach(patent => {
            const colony = patent.colony || 'crystal';
            if (!patentsByColony[colony]) patentsByColony[colony] = [];
            patentsByColony[colony].push(patent);
        });
        
        Object.entries(patentsByColony).forEach(([colony, patents]) => {
            const colonyData = COLONY_DATA[colony];
            if (!colonyData) return;
            const wingAngle = colonyData.wingAngle;
            const wingRadius = DIMENSIONS.rotunda.radius;
            const wingLength = DIMENSIONS.wing.length;
            
            patents.forEach((patent, i) => {
                const progress = (i + 1) / (patents.length + 1);
                const distance = wingRadius + 5 + progress * (wingLength - 10);
                const side = i % 2 === 0 ? -1 : 1;
                const lateralOffset = 3 * side;
                const safeWingAngle = typeof wingAngle === 'number' && !isNaN(wingAngle) ? wingAngle : 0;
                const baseX = Math.cos(safeWingAngle) * distance;
                const baseZ = Math.sin(safeWingAngle) * distance;
                const perpAngle = safeWingAngle + Math.PI / 2;
                const x = baseX + Math.cos(perpAngle) * lateralOffset;
                const z = baseZ + Math.sin(perpAngle) * lateralOffset;
                const rotationY = -wingAngle + (side > 0 ? 0 : Math.PI);
                
                const placeholder = this.createShimmerPlaceholder(patent.id);
                placeholder.position.set(x, 0, z);
                placeholder.rotation.y = rotationY;
                group.add(placeholder);
                
                this.pendingArtworks.push({
                    patent,
                    colony,
                    position: new THREE.Vector3(x, 0, z),
                    rotationY,
                    placeholder
                });
            });
        });
    }
    
    /**
     * Simple shimmer placeholder (small box) until artwork loads
     */
    createShimmerPlaceholder(patentId) {
        const group = new THREE.Group();
        group.name = `placeholder-${patentId}`;
        group.userData.patentId = patentId;
        group.userData.placeholder = true;
        const geo = new THREE.BoxGeometry(1.2, 0.5, 1.2);
        const mat = new THREE.MeshStandardMaterial({
            color: 0x1a1a2e,
            emissive: 0x2a2a4e,
            emissiveIntensity: 0.3,
            transparent: true,
            opacity: 0.8
        });
        const mesh = new THREE.Mesh(geo, mat);
        mesh.position.y = 0.25;
        group.add(mesh);
        group.userData._shimmerMesh = mesh;
        return group;
    }
    
    /**
     * Load P2/P3 artworks for a single colony (called when visitor approaches wing)
     */
    loadColonyArtworks(colony) {
        if (this.loadedColonies.has(colony)) return 0;
        const toLoad = this.pendingArtworks.filter(p => p.colony === colony);
        if (toLoad.length === 0) return 0;
        
        let added = 0;
        toLoad.forEach(({ patent, position, rotationY, placeholder }) => {
            let artwork = null;
            try {
                artwork = createP2Artwork(patent.id);
            } catch (_) {}
            if (!artwork && patent.priority === 'P3') {
                try {
                    artwork = createP3Artwork(patent);
                } catch (_) {}
            }
            if (!artwork) {
                try {
                    artwork = createTemplateArtwork(patent);
                } catch (_) {}
            }
            if (!artwork) return;
            
            artwork.position.copy(position);
            artwork.rotation.y = rotationY;
            artwork.userData.patentId = patent.id;
            artwork.userData.interactive = true;
            
            const idx = this.artworkGroup.children.indexOf(placeholder);
            this.artworkGroup.add(artwork);
            this.artworkGroup.remove(placeholder);
            if (placeholder.userData._shimmerMesh?.geometry) placeholder.userData._shimmerMesh.geometry.dispose();
            if (placeholder.userData._shimmerMesh?.material) placeholder.userData._shimmerMesh.material.dispose();
            
            this.loadedArtworks.set(patent.id, artwork);
            this.pendingArtworks = this.pendingArtworks.filter(p => p.placeholder !== placeholder);
            hideOriginalPedestals(artwork);
            added++;
        });
        this.loadedColonies.add(colony);
        return added;
    }
    
    /**
     * Wing center in world XZ (for distance check)
     */
    getWingCenter(colony) {
        const data = COLONY_DATA[colony];
        if (!data) return null;
        const midRadius = DIMENSIONS.rotunda.radius + DIMENSIONS.wing.length * 0.4;
        return new THREE.Vector3(
            Math.cos(data.wingAngle) * midRadius,
            0,
            Math.sin(data.wingAngle) * midRadius
        );
    }
    
    /**
     * Load a single artwork
     */
    loadArtwork(config) {
        if (!config.factory) {
            console.warn(`No factory for artwork ${config.id}`);
            return null;
        }
        
        const artwork = config.factory();
        
        if (!artwork) {
            console.warn(`Factory returned null for artwork ${config.id}`);
            return null;
        }
        
        // Position - with null check for missing position data
        if (config.position && typeof config.position.x === 'number') {
            artwork.position.set(
                config.position.x,
                config.position.y ?? 0,
                config.position.z ?? 0
            );
        } else {
            console.warn(`Missing position data for artwork ${config.id}, using default (0, 0, 0)`);
            artwork.position.set(0, 0, 0);
        }
        
        // Scale
        if (config.scale && config.scale !== 1) {
            artwork.scale.setScalar(config.scale);
        }
        
        // Rotation
        if (config.rotation) {
            artwork.rotation.y = config.rotation;
        }
        
        // Mark as interactive
        artwork.userData.patentId = config.id;
        artwork.userData.interactive = true;
        
        return artwork;
    }
    
    
    /**
     * Load a specific gallery
     */
    loadGallery(colonyName) {
        const config = GALLERY_PLACEMENTS[colonyName];
        if (!config) {
            console.warn(`Unknown gallery: ${colonyName}`);
            return null;
        }
        
        const galleryGroup = new THREE.Group();
        galleryGroup.name = `gallery-${colonyName}`;
        
        config.artworks.forEach(artworkConfig => {
            const artwork = this.loadArtwork(artworkConfig);
            if (artwork) {
                galleryGroup.add(artwork);
                this.loadedArtworks.set(artworkConfig.id, artwork);
            }
        });
        
        return galleryGroup;
    }
    
    /**
     * Get artwork by patent ID
     */
    getArtwork(patentId) {
        return this.loadedArtworks.get(patentId);
    }
    
    /**
     * Update all loaded artworks; lazy-load P2/P3 when camera approaches a wing.
     * @param {number} deltaTime - Time since last frame
     * @param {THREE.Camera} camera - Camera for billboard behavior
     * @returns {{ artworksAdded: boolean }} - True if new artworks were loaded (caller should rebuild interactables)
     */
    update(deltaTime, camera = null) {
        let artworksAdded = false;
        if (camera && this.pendingArtworks.length > 0) {
            const camPos = camera.position;
            COLONY_ORDER.forEach((colony) => {
                const center = this.getWingCenter(colony);
                if (center && camPos.distanceTo(center) < WING_LOAD_DISTANCE) {
                    const n = this.loadColonyArtworks(colony);
                    if (n > 0) artworksAdded = true;
                }
            });
        }
        this.loadedArtworks.forEach(artwork => {
            if (artwork.update) {
                artwork.update(deltaTime, camera);
            }
        });
        return { artworksAdded };
    }
    
    /**
     * Dispose all loaded artworks
     */
    dispose() {
        this.loadedArtworks.forEach(artwork => {
            if (artwork.dispose) {
                artwork.dispose();
            }
        });
        this.loadedArtworks.clear();
        
        if (this.artworkGroup) {
            this.scene.remove(this.artworkGroup);
        }
    }
}

// ═══════════════════════════════════════════════════════════════════════════
// FACTORY FUNCTION
// ═══════════════════════════════════════════════════════════════════════════

export function createGalleryLoader(scene) {
    return new GalleryLoader(scene);
}

export default GalleryLoader;
