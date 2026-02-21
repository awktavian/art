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
        const colonyColor = COLONY_COLORS[this.patent.colony] || 0x67D4E4;

        // Single panel mesh with baked text+border+badge via canvas texture
        this.createTextTexture();

        // Glow plane for hover interaction (second and final mesh)
        const glowMat = new THREE.MeshBasicMaterial({
            color: colonyColor, transparent: true, opacity: 0, side: THREE.DoubleSide
        });
        this.glow = new THREE.Mesh(new THREE.PlaneGeometry(width + 0.2, height + 0.2), glowMat);
        this.glow.position.z = -depth;
        this.add(this.glow);
    }
    
    createTextTexture() {
        const { width, height, depth, showDescription } = this.options;
        const patent = this.patent;
        const colonyColor = COLONY_COLORS[patent.colony] || 0x67D4E4;
        const colonyHex = '#' + colonyColor.toString(16).padStart(6, '0');
        const priorityColor = PRIORITY_COLORS[patent.priority] || 0x9E9994;
        const priorityHex = '#' + priorityColor.toString(16).padStart(6, '0');

        // 1x DPI canvas — 9x less VRAM than previous 3x scale
        const canvas = document.createElement('canvas');
        const cw = 512, ch = 300;
        canvas.width = cw;
        canvas.height = ch;
        const ctx = canvas.getContext('2d');

        // Background
        ctx.fillStyle = 'rgba(6, 6, 12, 0.98)';
        ctx.fillRect(0, 0, cw, ch);

        // Border (baked into canvas — replaces separate mesh)
        ctx.strokeStyle = colonyHex;
        ctx.lineWidth = 3;
        ctx.strokeRect(1.5, 1.5, cw - 3, ch - 3);

        // Accent bar (baked — replaces separate mesh)
        ctx.fillStyle = colonyHex;
        ctx.globalAlpha = 0.85;
        ctx.fillRect(0, 15, 6, ch - 30);
        ctx.globalAlpha = 1.0;

        // Priority badge (baked — replaces separate mesh)
        ctx.fillStyle = priorityHex;
        ctx.fillRect(cw - 40, 6, 34, 30);
        ctx.fillStyle = '#07060B';
        ctx.font = 'bold 18px "IBM Plex Mono", monospace';
        ctx.textAlign = 'center';
        ctx.fillText(patent.priority, cw - 23, 27);

        // Title
        ctx.fillStyle = '#FFFFFF';
        ctx.font = 'bold 22px "IBM Plex Sans", sans-serif';
        ctx.textAlign = 'left';
        const maxWidth = 430;
        const words = patent.name.split(' ');
        let line = '', y = 40;
        for (const word of words) {
            const test = line + word + ' ';
            if (ctx.measureText(test).width > maxWidth && line) {
                ctx.fillText(line.trim(), 20, y);
                line = word + ' ';
                y += 28;
            } else {
                line = test;
            }
        }
        ctx.fillText(line.trim(), 20, y);

        // Category
        y += 32;
        ctx.fillStyle = colonyHex;
        ctx.font = '500 13px "IBM Plex Mono", monospace';
        ctx.fillText((patent.categoryName?.toUpperCase() || patent.category || ''), 20, y);

        // Description
        if (showDescription && patent.description) {
            y += 22;
            ctx.fillStyle = '#B8B4AE';
            ctx.font = '400 13px "IBM Plex Sans", sans-serif';
            const dWords = patent.description.split(' ');
            line = '';
            let lc = 0;
            for (const word of dWords) {
                const test = line + word + ' ';
                if (ctx.measureText(test).width > maxWidth && line) {
                    ctx.fillText(line.trim(), 20, y);
                    line = word + ' ';
                    y += 18;
                    if (++lc >= 3) { ctx.fillText(line.trim() + '...', 20, y); break; }
                } else {
                    line = test;
                }
            }
            if (lc < 3 && line) ctx.fillText(line.trim(), 20, y);
        }

        // Novelty stars
        const novelty = patent.novelty || 0;
        ctx.fillStyle = '#FFD700';
        ctx.font = '11px sans-serif';
        ctx.fillText('\u2605'.repeat(novelty) + '\u2606'.repeat(5 - novelty), 20, 256);

        // CTA + ID
        ctx.fillStyle = '#67D4E4';
        ctx.font = '600 12px "IBM Plex Sans", sans-serif';
        ctx.fillText('Tap to learn more', 20, 274);
        ctx.fillStyle = '#B0ACA6';
        ctx.font = '400 12px "IBM Plex Mono", monospace';
        ctx.fillText(`${patent.id} \u00B7 ${patent.invented || 'N/A'}`, 20, 290);

        const texture = new THREE.CanvasTexture(canvas);
        texture.flipY = false;
        texture.needsUpdate = true;

        // Single mesh replaces 5 previous meshes (panel + border + badge + accent + textPlane)
        const geo = new THREE.PlaneGeometry(width, height);
        const mat = new THREE.MeshBasicMaterial({
            map: texture, transparent: true, side: THREE.FrontSide
        });
        this.panel = new THREE.Mesh(geo, mat);
        this.panel.position.z = depth / 2 + 0.005;
        this.add(this.panel);
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
