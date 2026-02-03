/**
 * Artwork Plaque Component
 * ========================
 * 
 * 3D text plaque that displays next to each patent artwork.
 * Shows title, category, priority, and brief description.
 * 
 * h(x) ≥ 0 always
 */

import * as THREE from 'three';

// Colony color mapping
const COLONY_COLORS = {
    spark:   0xFF6B35,
    forge:   0xD4AF37,
    flow:    0x4ECDC4,
    nexus:   0x9B7EBD,
    beacon:  0xF59E0B,
    grove:   0x7EB77F,
    crystal: 0x67D4E4
};

const PRIORITY_COLORS = {
    P1: 0xFFD700,
    P2: 0x67D4E4,
    P3: 0x9E9994
};

// ═══════════════════════════════════════════════════════════════════════════
// PLAQUE CLASS
// ═══════════════════════════════════════════════════════════════════════════

export class Plaque extends THREE.Group {
    constructor(patent, options = {}) {
        super();
        
        this.patent = patent;
        this.options = {
            width: options.width || 2.0,
            height: options.height || 1.2,
            depth: options.depth || 0.05,
            showDescription: options.showDescription !== false,
            interactive: options.interactive !== false,
            ...options
        };
        
        this.name = `plaque-${patent.id}`;
        this.userData = { 
            patent, 
            interactive: this.options.interactive,
            type: 'plaque'
        };
        
        this.create();
    }
    
    create() {
        const { width, height, depth } = this.options;
        const patent = this.patent;
        const colonyColor = COLONY_COLORS[patent.colony] || 0x67D4E4;
        const priorityColor = PRIORITY_COLORS[patent.priority] || 0x9E9994;
        
        // Background panel
        const panelGeo = new THREE.BoxGeometry(width, height, depth);
        const panelMat = new THREE.MeshPhysicalMaterial({
            color: 0x0A0A10,
            metalness: 0.8,
            roughness: 0.3,
            clearcoat: 0.5,
            clearcoatRoughness: 0.2
        });
        this.panel = new THREE.Mesh(panelGeo, panelMat);
        this.add(this.panel);
        
        // Border frame
        const borderGeo = new THREE.BoxGeometry(width + 0.08, height + 0.08, depth * 0.5);
        const borderMat = new THREE.MeshBasicMaterial({
            color: colonyColor,
            transparent: true,
            opacity: 0.6
        });
        const border = new THREE.Mesh(borderGeo, borderMat);
        border.position.z = -depth * 0.5;
        this.add(border);
        
        // Priority indicator (corner badge)
        const badgeSize = 0.25;
        const badgeGeo = new THREE.PlaneGeometry(badgeSize, badgeSize);
        const badgeMat = new THREE.MeshBasicMaterial({
            color: priorityColor,
            transparent: true,
            opacity: 0.9
        });
        const badge = new THREE.Mesh(badgeGeo, badgeMat);
        badge.position.set(width/2 - badgeSize/2 - 0.05, height/2 - badgeSize/2 - 0.05, depth/2 + 0.01);
        this.add(badge);
        
        // Create text texture
        this.createTextTexture();
        
        // Glow effect (shown on hover)
        const glowGeo = new THREE.PlaneGeometry(width + 0.2, height + 0.2);
        const glowMat = new THREE.MeshBasicMaterial({
            color: colonyColor,
            transparent: true,
            opacity: 0,
            side: THREE.DoubleSide
        });
        this.glow = new THREE.Mesh(glowGeo, glowMat);
        this.glow.position.z = -depth;
        this.add(this.glow);
    }
    
    createTextTexture() {
        const { width, height, depth, showDescription } = this.options;
        const patent = this.patent;
        const colonyColor = COLONY_COLORS[patent.colony] || 0x67D4E4;
        const colonyHex = '#' + colonyColor.toString(16).padStart(6, '0');
        
        // Create canvas
        const canvas = document.createElement('canvas');
        const scale = 2; // Higher resolution
        canvas.width = 512 * scale;
        canvas.height = 300 * scale;
        const ctx = canvas.getContext('2d');
        
        // Scale for retina
        ctx.scale(scale, scale);
        
        // Clear
        ctx.fillStyle = 'rgba(10, 10, 16, 0.95)';
        ctx.fillRect(0, 0, 512, 300);
        
        // Title
        ctx.fillStyle = '#F5F0E8';
        ctx.font = 'bold 28px "IBM Plex Sans", sans-serif';
        ctx.textAlign = 'left';
        
        // Word wrap title
        const words = patent.name.split(' ');
        let line = '';
        let y = 45;
        const maxWidth = 440;
        
        for (let word of words) {
            const testLine = line + word + ' ';
            const metrics = ctx.measureText(testLine);
            if (metrics.width > maxWidth && line !== '') {
                ctx.fillText(line.trim(), 30, y);
                line = word + ' ';
                y += 34;
            } else {
                line = testLine;
            }
        }
        ctx.fillText(line.trim(), 30, y);
        
        // Category
        y += 40;
        ctx.fillStyle = colonyHex;
        ctx.font = '500 14px "IBM Plex Mono", monospace';
        ctx.fillText(patent.categoryName?.toUpperCase() || 'UNKNOWN', 30, y);
        
        // Description (if enabled)
        if (showDescription && patent.description) {
            y += 30;
            ctx.fillStyle = '#9E9994';
            ctx.font = '400 14px "IBM Plex Sans", sans-serif';
            
            // Word wrap description
            const descWords = patent.description.split(' ');
            line = '';
            let lineCount = 0;
            const maxLines = 3;
            
            for (let word of descWords) {
                const testLine = line + word + ' ';
                const metrics = ctx.measureText(testLine);
                if (metrics.width > maxWidth && line !== '') {
                    ctx.fillText(line.trim(), 30, y);
                    line = word + ' ';
                    y += 20;
                    lineCount++;
                    if (lineCount >= maxLines) {
                        ctx.fillText(line.trim() + '...', 30, y);
                        break;
                    }
                } else {
                    line = testLine;
                }
            }
            if (lineCount < maxLines && line) {
                ctx.fillText(line.trim(), 30, y);
            }
        }
        
        // Patent ID and date
        y = 280;
        ctx.fillStyle = '#5A5550';
        ctx.font = '400 12px "IBM Plex Mono", monospace';
        ctx.fillText(`${patent.id} · ${patent.invented || 'N/A'}`, 30, y);
        
        // Priority badge text
        ctx.fillStyle = '#07060B';
        ctx.font = 'bold 18px "IBM Plex Mono", monospace';
        ctx.textAlign = 'center';
        ctx.fillText(patent.priority, 470, 40);
        
        // Novelty stars
        const novelty = patent.novelty || 0;
        ctx.fillStyle = '#FFD700';
        ctx.font = '12px sans-serif';
        ctx.textAlign = 'left';
        ctx.fillText('★'.repeat(novelty) + '☆'.repeat(5 - novelty), 30, 260);
        
        // Create texture
        const texture = new THREE.CanvasTexture(canvas);
        texture.needsUpdate = true;
        
        // Apply to plane
        const textGeo = new THREE.PlaneGeometry(width - 0.1, height - 0.1);
        const textMat = new THREE.MeshBasicMaterial({
            map: texture,
            transparent: true
        });
        const textPlane = new THREE.Mesh(textGeo, textMat);
        textPlane.position.z = this.options.depth / 2 + 0.005;
        this.add(textPlane);
    }
    
    // ═══════════════════════════════════════════════════════════════════════
    // INTERACTION
    // ═══════════════════════════════════════════════════════════════════════
    
    onHover() {
        if (!this.options.interactive) return;
        
        // Animate glow
        this.glow.material.opacity = 0.3;
        
        // Slight scale
        this.scale.setScalar(1.02);
    }
    
    onHoverEnd() {
        if (!this.options.interactive) return;
        
        this.glow.material.opacity = 0;
        this.scale.setScalar(1.0);
    }
    
    onClick() {
        if (!this.options.interactive) return;
        
        // Dispatch event for info panel
        window.dispatchEvent(new CustomEvent('patent-select', {
            detail: { patentId: this.patent.id }
        }));
    }
    
    // ═══════════════════════════════════════════════════════════════════════
    // DISPOSAL
    // ═══════════════════════════════════════════════════════════════════════
    
    dispose() {
        this.traverse((obj) => {
            if (obj.geometry) obj.geometry.dispose();
            if (obj.material) {
                if (obj.material.map) obj.material.map.dispose();
                obj.material.dispose();
            }
        });
    }
}

// ═══════════════════════════════════════════════════════════════════════════
// FACTORY FUNCTION
// ═══════════════════════════════════════════════════════════════════════════

export function createPlaque(patent, options = {}) {
    return new Plaque(patent, options);
}

export default Plaque;
