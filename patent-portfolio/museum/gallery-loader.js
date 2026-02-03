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

// ═══════════════════════════════════════════════════════════════════════════
// GALLERY LOADER CLASS
// ═══════════════════════════════════════════════════════════════════════════

export class GalleryLoader {
    constructor(scene) {
        this.scene = scene;
        this.loadedArtworks = new Map();
        this.infoPanel = new InfoPanel();
        
        // Listen for patent selection events
        window.addEventListener('patent-select', (e) => {
            this.infoPanel.show(e.detail.patentId);
        });
    }
    
    /**
     * Load all galleries and artworks
     */
    loadAllGalleries() {
        const artworkGroup = new THREE.Group();
        artworkGroup.name = 'artworks';
        
        // Load P1 artworks with custom factories
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
        
        // Load P2 and P3 artworks using templates
        this.loadTemplateArtworks(artworkGroup);
        
        this.scene.add(artworkGroup);
        this.artworkGroup = artworkGroup;
        
        console.log(`📚 Loaded ${this.loadedArtworks.size} artworks`);
        return artworkGroup;
    }
    
    /**
     * Load P2 and P3 artworks using the template system
     */
    loadTemplateArtworks(group) {
        // Get all P2 and P3 patents
        const templatePatents = PATENTS.filter(p => 
            (p.priority === 'P2' || p.priority === 'P3') && 
            !this.loadedArtworks.has(p.id)
        );
        
        // Group by colony
        const patentsByColony = {};
        templatePatents.forEach(patent => {
            const colony = patent.colony || 'crystal';
            if (!patentsByColony[colony]) {
                patentsByColony[colony] = [];
            }
            patentsByColony[colony].push(patent);
        });
        
        // Position artworks in each wing
        Object.entries(patentsByColony).forEach(([colony, patents]) => {
            const colonyData = COLONY_DATA[colony];
            if (!colonyData) return;
            
            const wingAngle = colonyData.wingAngle;
            const wingRadius = DIMENSIONS.rotunda.radius;
            const wingLength = DIMENSIONS.wing.length;
            
            patents.forEach((patent, i) => {
                try {
                    // Create template artwork
                    const artwork = createTemplateArtwork(patent);
                    
                    // Calculate position along wing
                    const progress = (i + 1) / (patents.length + 1);
                    const distance = wingRadius + 5 + progress * (wingLength - 10);
                    
                    // Alternate left/right side
                    const side = i % 2 === 0 ? -1 : 1;
                    const lateralOffset = 3 * side;
                    
                    // Calculate world position
                    const baseX = Math.cos(wingAngle) * distance;
                    const baseZ = Math.sin(wingAngle) * distance;
                    
                    // Perpendicular offset
                    const perpAngle = wingAngle + Math.PI / 2;
                    const x = baseX + Math.cos(perpAngle) * lateralOffset;
                    const z = baseZ + Math.sin(perpAngle) * lateralOffset;
                    
                    artwork.position.set(x, 0, z);
                    
                    // Face toward center of wing
                    artwork.rotation.y = -wingAngle + (side > 0 ? 0 : Math.PI);
                    
                    group.add(artwork);
                    this.loadedArtworks.set(patent.id, artwork);
                } catch (error) {
                    console.warn(`Failed to create template artwork for ${patent.id}:`, error);
                }
            });
        });
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
        
        // Position
        artwork.position.set(
            config.position.x,
            config.position.y,
            config.position.z
        );
        
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
     * Update all loaded artworks
     */
    update(deltaTime) {
        this.loadedArtworks.forEach(artwork => {
            if (artwork.update) {
                artwork.update(deltaTime);
            }
        });
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
