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
            opacity: 0.9,
            side: THREE.DoubleSide
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
        
        // Create canvas (scale 3 for sharp text and small glyphs)
        const canvas = document.createElement('canvas');
        const scale = 3;
        canvas.width = 512 * scale;
        canvas.height = 300 * scale;
        const ctx = canvas.getContext('2d');
        
        // Scale for retina
        ctx.scale(scale, scale);
        
        // Clear — darker background for better contrast
        ctx.fillStyle = 'rgba(6, 6, 12, 0.98)';
        ctx.fillRect(0, 0, 512, 300);
        
        // Title — high contrast
        ctx.fillStyle = '#FFFFFF';
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
        
        // Category with icon (small diamond for category)
        y += 40;
        ctx.fillStyle = colonyHex;
        ctx.font = '500 14px "IBM Plex Mono", monospace';
        const catText = patent.categoryName?.toUpperCase() || patent.category || 'UNKNOWN';
        ctx.beginPath();
        ctx.moveTo(30, y - 10);
        ctx.lineTo(38, y - 4);
        ctx.lineTo(30, y + 2);
        ctx.lineTo(22, y - 4);
        ctx.closePath();
        ctx.fill();
        ctx.fillStyle = colonyHex;
        ctx.fillText(catText, 44, y);
        
        // Description (if enabled)
        if (showDescription && patent.description) {
            y += 30;
            ctx.fillStyle = '#B8B4AE';
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
        
        // Tap to learn more CTA (high contrast)
        y = 268;
        ctx.fillStyle = '#67D4E4';
        ctx.font = '600 13px "IBM Plex Sans", sans-serif';
        ctx.fillText('Tap to learn more', 30, y);
        
        // Patent ID and date (lighter for legibility)
        y = 280;
        ctx.fillStyle = '#B0ACA6';
        ctx.font = '400 13px "IBM Plex Mono", monospace';
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
        
        // Create texture (flipY = false so canvas top matches geometry top; avoids inverted text)
        const texture = new THREE.CanvasTexture(canvas);
        texture.flipY = false;
        texture.needsUpdate = true;
        
        // Apply to plane; FrontSide so correct face shows when plaque faces visitor
        const textGeo = new THREE.PlaneGeometry(width - 0.1, height - 0.1);
        const textMat = new THREE.MeshBasicMaterial({
            map: texture,
            transparent: true,
            side: THREE.FrontSide
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
        
        // Subtle glow pulse (Fibonacci 233ms feel)
        this.glow.material.opacity = 0.35;
        if (this._pulseInterval) clearInterval(this._pulseInterval);
        let phase = 0;
        this._pulseInterval = setInterval(() => {
            phase += 0.15;
            this.glow.material.opacity = 0.25 + 0.12 * Math.sin(phase);
            if (phase > Math.PI * 2) phase = 0;
        }, 80);
        
        this.scale.setScalar(1.02);
    }
    
    onHoverEnd() {
        if (!this.options.interactive) return;
        
        if (this._pulseInterval) {
            clearInterval(this._pulseInterval);
            this._pulseInterval = null;
        }
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
