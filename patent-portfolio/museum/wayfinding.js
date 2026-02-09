/**
 * Wayfinding System
 * =================
 * 
 * Museum navigation aids including minimap, signage, and information kiosks.
 * Inspired by the Guggenheim's clear circulation and the Exploratorium's
 * discovery-oriented wayfinding.
 * 
 * h(x) ≥ 0 always
 */

import * as THREE from 'three';
import { getCanvasFont, SIZES } from '../lib/typography.js';
import { DIMENSIONS } from './architecture.js';
import { isInLineOfSight } from '../lib/culling-system.js';
import { shouldShowReturnToRotunda } from '../lib/guest-experience.js';

// Colony colors for consistent wayfinding
const COLONY_COLORS = {
    spark: { hex: 0xFF6B35, name: 'Spark', icon: '🔥' },
    forge: { hex: 0xFFD700, name: 'Forge', icon: '⚒️' },
    flow: { hex: 0x4ECDC4, name: 'Flow', icon: '🌊' },
    nexus: { hex: 0x9B7EBD, name: 'Nexus', icon: '🔗' },
    beacon: { hex: 0x45B7D1, name: 'Beacon', icon: '🗼' },
    grove: { hex: 0x7EB77F, name: 'Grove', icon: '🌿' },
    crystal: { hex: 0x67D4E4, name: 'Crystal', icon: '💎' }
};

const COLONY_ORDER = ['spark', 'forge', 'flow', 'nexus', 'beacon', 'grove', 'crystal'];

// ═══════════════════════════════════════════════════════════════════════════
// MINIMAP
// ═══════════════════════════════════════════════════════════════════════════

export class Minimap {
    constructor(options = {}) {
        this.options = {
            size: options.size || 150,
            position: options.position || { right: 20, bottom: 20 },
            scale: options.scale || 0.7,
            showPlayer: options.showPlayer !== false,
            showColonies: options.showColonies !== false,
            opacity: options.opacity || 0.92,
            ...options
        };
        
        this.element = null;
        this.canvas = null;
        this.ctx = null;
        this.playerPosition = new THREE.Vector3();
        this.playerRotation = 0;
        this.visible = true;
        
        // Journey tracking integration
        this.visitedWings = {
            spark: false, forge: false, flow: false, nexus: false,
            beacon: false, grove: false, crystal: false, rotunda: true
        };
        this.wingProgress = {};  // Percentage of patents viewed per wing
        
        // Artwork marker positions (populated externally)
        this.artworkPositions = [];  // [{x, z, patentId, colony, viewed}]
        
        // Click-to-teleport callback
        this.onTeleport = null;
        
        // Zoom level (0 = overview, 1 = detail)
        this.zoomLevel = 0;
        this.zoomScales = [0.7, 1.4];
        
        // Cached vector for direction calculation (avoid GC pressure)
        this._directionVector = new THREE.Vector3();
        this._pulsePhase = 0;
        
        this.init();
    }
    
    init() {
        // Use existing element if present, otherwise create
        this.element = document.getElementById('minimap');
        
        if (!this.element) {
            this.element = document.createElement('div');
            this.element.id = 'minimap';
            document.body.appendChild(this.element);
        }
        
        // Clear existing content and add canvas
        this.element.innerHTML = '';
        
        // Create canvas with high DPI
        this.canvas = document.createElement('canvas');
        this.canvas.width = this.options.size * 2;
        this.canvas.height = this.options.size * 2;
        this.canvas.style.cssText = `width: 100%; height: 100%;`;
        
        this.element.appendChild(this.canvas);
        this.ctx = this.canvas.getContext('2d');
        
        // Click-to-teleport handler
        this.canvas.style.cursor = 'pointer';
        this.canvas.addEventListener('click', (e) => this._handleClick(e));
        
        // Double-click to toggle zoom
        this.canvas.addEventListener('dblclick', () => this.toggleZoom());
        
        // Initial draw
        this.drawStaticElements();
    }
    
    /**
     * Toggle between overview and detail zoom levels
     */
    toggleZoom() {
        this.zoomLevel = (this.zoomLevel + 1) % this.zoomScales.length;
        this.options.scale = this.zoomScales[this.zoomLevel];
        this.drawStaticElements();
    }
    
    /**
     * Set artwork positions for display on minimap
     * @param {Array} positions - [{x, z, patentId, colony, viewed}]
     */
    setArtworkPositions(positions) {
        this.artworkPositions = positions;
        this.drawStaticElements();
    }
    
    /**
     * Handle click on minimap — teleport to clicked world position
     */
    _handleClick(e) {
        if (!this.onTeleport) return;
        const rect = this.canvas.getBoundingClientRect();
        const dpr = this.canvas.width / rect.width;
        const cx = (e.clientX - rect.left) * dpr;
        const cy = (e.clientY - rect.top) * dpr;
        
        const size = this.canvas.width;
        const center = size / 2;
        const scale = this.options.scale * 2;
        
        // Convert minimap coords back to world coords
        const worldX = ((cx - center) / (55 * scale)) * 100;
        const worldZ = ((cy - center) / (55 * scale)) * 100;
        
        // Check if click is near a wing endpoint for smarter teleport
        let targetColony = null;
        const wingLength = 42 * scale;
        COLONY_ORDER.forEach((colony, i) => {
            const angle = (i / 7) * Math.PI * 2 - Math.PI / 2;
            const endDist = 22 * scale + wingLength - 5;
            const endX = center + Math.cos(angle) * endDist;
            const endY = center + Math.sin(angle) * endDist;
            const dist = Math.sqrt((cx - endX) ** 2 + (cy - endY) ** 2);
            if (dist < 20 * scale) targetColony = colony;
        });
        
        // Also check center for rotunda
        const centerDist = Math.sqrt((cx - center) ** 2 + (cy - center) ** 2);
        if (centerDist < 25 * scale) targetColony = 'rotunda';
        
        this.onTeleport({ worldX, worldZ, colony: targetColony });
    }
    
    /**
     * Update visited wings from journey tracker
     */
    setVisitedWings(visited) {
        this.visitedWings = { ...this.visitedWings, ...visited };
        this.drawStaticElements();  // Redraw with new visited state
    }
    
    /**
     * Update wing progress percentages
     */
    setWingProgress(progress) {
        this.wingProgress = progress;
        this.drawStaticElements();
    }
    
    drawStaticElements() {
        const ctx = this.ctx;
        const size = this.canvas.width;
        const center = size / 2;
        const scale = this.options.scale * 2;
        
        ctx.clearRect(0, 0, size, size);
        
        // Background gradient (dark center, slightly lighter edges)
        const bgGrad = ctx.createRadialGradient(center, center, 0, center, center, size / 2);
        bgGrad.addColorStop(0, 'rgba(10, 10, 18, 0.95)');
        bgGrad.addColorStop(1, 'rgba(15, 15, 25, 0.85)');
        ctx.fillStyle = bgGrad;
        ctx.beginPath();
        ctx.arc(center, center, size / 2, 0, Math.PI * 2);
        ctx.fill();
        
        // Draw rotunda (center circle) with visited glow
        const rotundaVisited = this.visitedWings.rotunda;
        ctx.beginPath();
        ctx.arc(center, center, 22 * scale, 0, Math.PI * 2);
        ctx.fillStyle = rotundaVisited 
            ? 'rgba(103, 212, 228, 0.25)' 
            : 'rgba(103, 212, 228, 0.1)';
        ctx.fill();
        ctx.strokeStyle = rotundaVisited
            ? 'rgba(103, 212, 228, 0.8)'
            : 'rgba(103, 212, 228, 0.4)';
        ctx.lineWidth = rotundaVisited ? 2 : 1;
        ctx.stroke();
        
        // Draw wings (radiating from center)
        const wingLength = 42 * scale;
        const wingWidth = 10 * scale;
        
        COLONY_ORDER.forEach((colony, i) => {
            const angle = (i / 7) * Math.PI * 2 - Math.PI / 2;
            const color = COLONY_COLORS[colony].hex;
            const visited = this.visitedWings[colony];
            const progress = this.wingProgress[colony]?.percent || 0;
            
            const r = (color >> 16) & 255;
            const g = (color >> 8) & 255;
            const b = color & 255;
            
            // Wing path
            ctx.save();
            ctx.translate(center, center);
            ctx.rotate(angle);
            
            // Base wing (unvisited)
            ctx.beginPath();
            ctx.moveTo(22 * scale, -wingWidth / 2);
            ctx.lineTo(22 * scale + wingLength, -wingWidth / 2);
            ctx.lineTo(22 * scale + wingLength, wingWidth / 2);
            ctx.lineTo(22 * scale, wingWidth / 2);
            ctx.closePath();
            
            // Fill based on visited state
            const fillAlpha = visited ? 0.4 : 0.15;
            ctx.fillStyle = `rgba(${r}, ${g}, ${b}, ${fillAlpha})`;
            ctx.fill();
            
            // Progress fill (shows % of patents viewed)
            if (progress > 0 && visited) {
                ctx.beginPath();
                const progressLength = wingLength * (progress / 100);
                ctx.moveTo(22 * scale, -wingWidth / 2);
                ctx.lineTo(22 * scale + progressLength, -wingWidth / 2);
                ctx.lineTo(22 * scale + progressLength, wingWidth / 2);
                ctx.lineTo(22 * scale, wingWidth / 2);
                ctx.closePath();
                ctx.fillStyle = `rgba(${r}, ${g}, ${b}, 0.6)`;
                ctx.fill();
            }
            
            // Stroke
            const strokeAlpha = visited ? 0.9 : 0.4;
            ctx.strokeStyle = `rgba(${r}, ${g}, ${b}, ${strokeAlpha})`;
            ctx.lineWidth = visited ? 1.5 : 1;
            ctx.stroke();
            
            // Visited glow effect
            if (visited) {
                ctx.shadowColor = `rgb(${r}, ${g}, ${b})`;
                ctx.shadowBlur = 8 * scale;
                ctx.stroke();
                ctx.shadowBlur = 0;
            }
            
            ctx.restore();
            
            // Colony icon at end of wing
            const iconDist = 22 * scale + wingLength - 5;
            const iconX = center + Math.cos(angle) * iconDist;
            const iconY = center + Math.sin(angle) * iconDist;
            
            ctx.fillStyle = visited 
                ? `rgb(${r}, ${g}, ${b})` 
                : `rgba(${r}, ${g}, ${b}, 0.5)`;
            ctx.font = `${9 * scale}px sans-serif`;
            ctx.textAlign = 'center';
            ctx.textBaseline = 'middle';
            ctx.fillText(COLONY_COLORS[colony].icon, iconX, iconY);
        });
        
        // Central "You are here" indicator
        ctx.fillStyle = 'rgba(103, 212, 228, 0.6)';
        ctx.font = `${14 * scale}px sans-serif`;
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.fillText('鏡', center, center);
        
        // Store static background
        this.staticBackground = ctx.getImageData(0, 0, size, size);
    }
    
    update(camera, deltaTime = 0.016) {
        if (!this.visible) return;
        
        const ctx = this.ctx;
        const size = this.canvas.width;
        const center = size / 2;
        const scale = this.options.scale * 2;
        
        // Update pulse animation
        this._pulsePhase += deltaTime * 2;
        const pulse = 0.8 + 0.2 * Math.sin(this._pulsePhase);
        
        // Restore static background
        if (this.staticBackground) {
            ctx.putImageData(this.staticBackground, 0, 0);
        }
        
        // Draw artwork markers
        if (this.artworkPositions.length > 0) {
            this.artworkPositions.forEach(art => {
                const mapX = center + (art.x / 100) * 55 * scale;
                const mapY = center + (art.z / 100) * 55 * scale;
                const colonyData = COLONY_COLORS[art.colony];
                const r = colonyData ? (colonyData.hex >> 16) & 255 : 103;
                const g = colonyData ? (colonyData.hex >> 8) & 255 : 212;
                const b = colonyData ? colonyData.hex & 255 : 228;
                
                ctx.beginPath();
                ctx.arc(mapX, mapY, art.viewed ? 2.5 * scale : 1.5 * scale, 0, Math.PI * 2);
                ctx.fillStyle = art.viewed 
                    ? `rgba(${r}, ${g}, ${b}, 0.8)` 
                    : `rgba(${r}, ${g}, ${b}, 0.3)`;
                ctx.fill();
            });
        }
        
        // Update player position from camera
        this.playerPosition.copy(camera.position);
        
        // Get camera direction for rotation (reuse cached vector)
        camera.getWorldDirection(this._directionVector);
        this.playerRotation = Math.atan2(this._directionVector.x, this._directionVector.z);
        
        // Draw player position
        if (this.options.showPlayer) {
            // Convert world position to minimap position
            // Museum is roughly 100m x 100m centered at origin
            const mapX = center + (this.playerPosition.x / 100) * 55 * scale;
            const mapY = center + (this.playerPosition.z / 100) * 55 * scale;
            
            // View cone (field of view indicator)
            const coneLength = 18 * scale;
            const coneSpread = 0.4;
            ctx.save();
            ctx.translate(mapX, mapY);
            ctx.rotate(-this.playerRotation);
            
            ctx.beginPath();
            ctx.moveTo(0, 0);
            ctx.lineTo(-coneLength * Math.sin(coneSpread), -coneLength * Math.cos(coneSpread));
            ctx.lineTo(0, -coneLength * 0.9);
            ctx.lineTo(coneLength * Math.sin(coneSpread), -coneLength * Math.cos(coneSpread));
            ctx.closePath();
            
            const coneGrad = ctx.createRadialGradient(0, 0, 0, 0, -coneLength/2, coneLength);
            coneGrad.addColorStop(0, 'rgba(103, 212, 228, 0.25)');
            coneGrad.addColorStop(1, 'rgba(103, 212, 228, 0)');
            ctx.fillStyle = coneGrad;
            ctx.fill();
            
            ctx.restore();
            
            // Player dot with pulse glow
            ctx.save();
            ctx.translate(mapX, mapY);
            
            // Outer glow ring (pulsing)
            ctx.beginPath();
            ctx.arc(0, 0, 8 * scale * pulse, 0, Math.PI * 2);
            ctx.fillStyle = `rgba(103, 212, 228, ${0.15 * pulse})`;
            ctx.fill();
            
            // Inner dot
            ctx.beginPath();
            ctx.arc(0, 0, 4 * scale, 0, Math.PI * 2);
            ctx.fillStyle = '#67D4E4';
            ctx.fill();
            ctx.strokeStyle = 'rgba(255, 255, 255, 0.8)';
            ctx.lineWidth = 1;
            ctx.stroke();
            
            ctx.restore();
        }
    }
    
    show() {
        this.visible = true;
        this.element.style.opacity = '1';
    }
    
    hide() {
        this.visible = false;
        this.element.style.opacity = '0';
    }
    
    toggle() {
        if (this.visible) {
            this.hide();
        } else {
            this.show();
        }
    }
    
    dispose() {
        if (this.element && this.element.parentNode) {
            this.element.parentNode.removeChild(this.element);
        }
    }
}

// ═══════════════════════════════════════════════════════════════════════════
// SIGNAGE SYSTEM
// ═══════════════════════════════════════════════════════════════════════════

export class SignageSystem {
    constructor(scene) {
        this.scene = scene;
        this.signs = [];
        this.directionalSigns = [];
    }
    
    /**
     * Create a MUSEUM-QUALITY hanging sign for a wing entrance
     * Inspired by Disney's themed signage and museum wayfinding best practices
     * 
     * @param {string} colony - Colony name
     * @param {THREE.Vector3} position - Sign position
     * @param {number} rotation - Y rotation in radians
     * @param {string} arrowDirection - 'left' or 'right' - direction arrow points INTO the wing
     */
    createWingSign(colony, position, rotation = 0, arrowDirection = 'right') {
        const data = COLONY_COLORS[colony];
        const group = new THREE.Group();
        group.name = `sign-${colony}`;
        
        // Wing metadata for contextual info
        const WING_INFO = {
            spark:   { patents: 8, desc: 'Voice & Visual', categories: 'G, K' },
            forge:   { patents: 8, desc: 'Platform & Crypto', categories: 'E, I' },
            flow:    { patents: 7, desc: 'Smart Home', categories: 'F' },
            nexus:   { patents: 8, desc: 'Consensus & Reasoning', categories: 'C, J' },
            beacon:  { patents: 8, desc: 'Economic Agents', categories: 'H' },
            grove:   { patents: 8, desc: 'World Models', categories: 'D' },
            crystal: { patents: 7, desc: 'Math & Safety', categories: 'A, B' }
        };
        const wingInfo = WING_INFO[colony] || { patents: 8, desc: 'Innovation', categories: '—' };
        
        // === PREMIUM SIGN FRAME ===
        // Main panel with beveled edges
        const frameGeo = new THREE.BoxGeometry(3.8, 1.4, 0.12);
        const frameMat = new THREE.MeshPhysicalMaterial({
            color: 0x0A0A0F,
            metalness: 0.98,
            roughness: 0.05,
            clearcoat: 1.0,
            clearcoatRoughness: 0.02,
            reflectivity: 0.9
        });
        const frame = new THREE.Mesh(frameGeo, frameMat);
        group.add(frame);
        
        // Inner recessed panel
        const innerGeo = new THREE.BoxGeometry(3.5, 1.15, 0.08);
        const innerMat = new THREE.MeshPhysicalMaterial({
            color: 0x12121A,
            metalness: 0.7,
            roughness: 0.2,
            clearcoat: 0.6
        });
        const inner = new THREE.Mesh(innerGeo, innerMat);
        inner.position.z = 0.03;
        group.add(inner);
        
        // Colony accent trim (top edge)
        const trimGeo = new THREE.BoxGeometry(3.8, 0.06, 0.14);
        const trimMat = new THREE.MeshPhysicalMaterial({
            color: data.hex,
            emissive: data.hex,
            emissiveIntensity: 0.4,
            metalness: 0.8,
            roughness: 0.2
        });
        const topTrim = new THREE.Mesh(trimGeo, trimMat);
        topTrim.position.y = 0.7;
        topTrim.position.z = 0.01;
        group.add(topTrim);
        
        // === HIGH-RES CANVAS TEXTURE (2048x700 for crisp text) ===
        const canvas = document.createElement('canvas');
        canvas.width = 2048;
        canvas.height = 700;
        const ctx = canvas.getContext('2d');
        
        // Premium gradient background
        const grad = ctx.createLinearGradient(0, 0, 0, 700);
        grad.addColorStop(0, '#16161E');
        grad.addColorStop(0.5, '#101018');
        grad.addColorStop(1, '#0C0C14');
        ctx.fillStyle = grad;
        ctx.fillRect(0, 0, 2048, 700);
        
        // Subtle horizontal lines for texture
        ctx.strokeStyle = 'rgba(255, 255, 255, 0.02)';
        ctx.lineWidth = 1;
        for (let y = 50; y < 700; y += 25) {
            ctx.beginPath();
            ctx.moveTo(50, y);
            ctx.lineTo(1998, y);
            ctx.stroke();
        }
        
        const colorHex = `#${data.hex.toString(16).padStart(6, '0')}`;
        const r = (data.hex >> 16) & 255;
        const g = (data.hex >> 8) & 255;
        const b = data.hex & 255;
        
        // === LAYOUT ===
        const isRight = arrowDirection === 'right';
        const contentX = isRight ? 100 : 1948;
        const align = isRight ? 'left' : 'right';
        
        // Colony icon (large, with glow layers for depth)
        const iconX = isRight ? 150 : 1898;
        ctx.textAlign = isRight ? 'left' : 'right';
        ctx.textBaseline = 'middle';
        
        // Icon outer glow
        ctx.shadowColor = colorHex;
        ctx.shadowBlur = 40;
        ctx.fillStyle = `rgba(${r}, ${g}, ${b}, 0.3)`;
        ctx.font = '140px sans-serif';
        ctx.fillText(data.icon, iconX, 280);
        
        // Icon main
        ctx.shadowBlur = 20;
        ctx.fillStyle = colorHex;
        ctx.font = '120px sans-serif';
        ctx.fillText(data.icon, iconX, 280);
        ctx.shadowBlur = 0;
        
        // Colony name - Display typography (large, tracking)
        const nameX = isRight ? 320 : 1728;
        ctx.fillStyle = '#F5F0E8';
        ctx.font = getCanvasFont(110, 'displayBold');
        ctx.textAlign = align;
        ctx.letterSpacing = '0.05em';
        ctx.fillText(data.name.toUpperCase(), nameX, 200);
        
        // "WING" subtitle
        ctx.fillStyle = `rgba(${r}, ${g}, ${b}, 0.8)`;
        ctx.font = getCanvasFont(48, 'sansMedium');
        ctx.fillText('WING', nameX + (isRight ? 5 : -5), 310);
        
        // === CONTEXTUAL INFO ===
        // Separator line
        const lineY = 400;
        const lineStartX = isRight ? 320 : 500;
        const lineEndX = isRight ? 1500 : 1728;
        ctx.strokeStyle = `rgba(${r}, ${g}, ${b}, 0.3)`;
        ctx.lineWidth = 2;
        ctx.beginPath();
        ctx.moveTo(lineStartX, lineY);
        ctx.lineTo(lineEndX, lineY);
        ctx.stroke();
        
        // Patent count and categories
        const infoY = 500;
        ctx.fillStyle = '#9E9994';
        ctx.font = getCanvasFont(36, 'mono');
        ctx.textAlign = align;
        const infoText = `${wingInfo.patents} PATENTS  •  ${wingInfo.desc.toUpperCase()}`;
        ctx.fillText(infoText, nameX, infoY);
        
        // Category codes
        ctx.fillStyle = '#6B6660';
        ctx.font = getCanvasFont(28, 'mono');
        ctx.fillText(`Categories: ${wingInfo.categories}`, nameX, 580);
        
        // === DIRECTIONAL ARROW (animated chevron style) ===
        const arrowX = isRight ? 1750 : 298;
        ctx.fillStyle = colorHex;
        ctx.shadowColor = colorHex;
        ctx.shadowBlur = 25;
        
        // Modern chevron arrow with motion lines
        ctx.lineWidth = 8;
        ctx.lineCap = 'round';
        ctx.lineJoin = 'round';
        ctx.strokeStyle = colorHex;
        
        if (isRight) {
            // Chevron pointing right with motion trails
            ctx.globalAlpha = 0.3;
            ctx.beginPath();
            ctx.moveTo(1650, 250); ctx.lineTo(1700, 350); ctx.lineTo(1650, 450);
            ctx.stroke();
            
            ctx.globalAlpha = 0.5;
            ctx.beginPath();
            ctx.moveTo(1700, 250); ctx.lineTo(1750, 350); ctx.lineTo(1700, 450);
            ctx.stroke();
            
            ctx.globalAlpha = 1.0;
            ctx.beginPath();
            ctx.moveTo(1750, 220); ctx.lineTo(1850, 350); ctx.lineTo(1750, 480);
            ctx.stroke();
        } else {
            // Chevron pointing left with motion trails
            ctx.globalAlpha = 0.3;
            ctx.beginPath();
            ctx.moveTo(398, 250); ctx.lineTo(348, 350); ctx.lineTo(398, 450);
            ctx.stroke();
            
            ctx.globalAlpha = 0.5;
            ctx.beginPath();
            ctx.moveTo(348, 250); ctx.lineTo(298, 350); ctx.lineTo(348, 450);
            ctx.stroke();
            
            ctx.globalAlpha = 1.0;
            ctx.beginPath();
            ctx.moveTo(298, 220); ctx.lineTo(198, 350); ctx.lineTo(298, 480);
            ctx.stroke();
        }
        ctx.globalAlpha = 1.0;
        ctx.shadowBlur = 0;
        
        // Create texture (single readable face toward rotunda; no back face to avoid mirroring)
        const texture = new THREE.CanvasTexture(canvas);
        texture.anisotropy = 16;
        texture.minFilter = THREE.LinearMipmapLinearFilter;
        texture.magFilter = THREE.LinearFilter;

        const labelGeo = new THREE.PlaneGeometry(3.4, 1.1);
        const labelMat = new THREE.MeshBasicMaterial({
            map: texture,
            transparent: true,
            side: THREE.FrontSide
        });
        const label = new THREE.Mesh(labelGeo, labelMat);
        label.position.z = 0.07;
        group.add(label);

        // === HANGING HARDWARE ===
        // Premium mounting plate
        const mountGeo = new THREE.BoxGeometry(0.15, 0.08, 0.04);
        const mountMat = new THREE.MeshPhysicalMaterial({
            color: 0x2A2A30,
            metalness: 0.95,
            roughness: 0.1
        });
        
        const leftMount = new THREE.Mesh(mountGeo, mountMat);
        leftMount.position.set(-1.6, 0.74, 0);
        group.add(leftMount);
        
        const rightMount = new THREE.Mesh(mountGeo, mountMat);
        rightMount.position.set(1.6, 0.74, 0);
        group.add(rightMount);
        
        // Sleek cables
        const cableGeo = new THREE.CylinderGeometry(0.006, 0.006, 0.8, 8);
        const cableMat = new THREE.MeshPhysicalMaterial({
            color: 0x3A3A40,
            metalness: 0.9,
            roughness: 0.2
        });
        
        const leftCable = new THREE.Mesh(cableGeo, cableMat);
        leftCable.position.set(-1.6, 1.14, 0);
        group.add(leftCable);
        
        const rightCable = new THREE.Mesh(cableGeo, cableMat);
        rightCable.position.set(1.6, 1.14, 0);
        group.add(rightCable);
        
        // === LED ACCENT STRIP ===
        const ledGeo = new THREE.BoxGeometry(3.6, 0.025, 0.025);
        const ledMat = new THREE.MeshBasicMaterial({
            color: data.hex,
            transparent: true,
            opacity: 0.95
        });
        const led = new THREE.Mesh(ledGeo, ledMat);
        led.position.y = -0.72;
        group.add(led);
        
        // LED glow light
        const glow = new THREE.PointLight(data.hex, 0.4, 6, 2);
        glow.position.set(0, -0.5, 0.3);
        group.add(glow);
        
        // === APPROACH ANIMATION DATA ===
        group.userData = {
            colony: colony,
            baseScale: 1.0,
            baseEmissive: 0.4,
            isApproached: false
        };
        
        // Position and rotate
        group.position.copy(position);
        group.rotation.y = rotation;
        
        this.scene.add(group);
        this.signs.push(group);
        
        return group;
    }
    
    /**
     * Create directional floor marker
     */
    createFloorMarker(colony, position) {
        const data = COLONY_COLORS[colony];
        const group = new THREE.Group();
        group.name = `floor-marker-${colony}`;
        
        // Circular base
        const baseGeo = new THREE.CircleGeometry(0.8, 32);
        const baseMat = new THREE.MeshBasicMaterial({
            color: data.hex,
            transparent: true,
            opacity: 0.3,
            side: THREE.DoubleSide
        });
        const base = new THREE.Mesh(baseGeo, baseMat);
        base.rotation.x = -Math.PI / 2;
        base.position.y = 0.01;
        group.add(base);
        
        // Ring
        const ringGeo = new THREE.RingGeometry(0.7, 0.8, 32);
        const ringMat = new THREE.MeshBasicMaterial({
            color: data.hex,
            transparent: true,
            opacity: 0.7,
            side: THREE.DoubleSide
        });
        const ring = new THREE.Mesh(ringGeo, ringMat);
        ring.rotation.x = -Math.PI / 2;
        ring.position.y = 0.02;
        group.add(ring);
        
        // Icon (vertical floating)
        const iconCanvas = document.createElement('canvas');
        iconCanvas.width = 128;
        iconCanvas.height = 128;
        const ctx = iconCanvas.getContext('2d');
        
        ctx.font = '80px sans-serif';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.fillText(data.icon, 64, 64);
        
        const iconTexture = new THREE.CanvasTexture(iconCanvas);
        const iconGeo = new THREE.PlaneGeometry(0.5, 0.5);
        const iconMat = new THREE.MeshBasicMaterial({
            map: iconTexture,
            transparent: true,
            side: THREE.DoubleSide,
            depthWrite: false
        });
        const icon = new THREE.Mesh(iconGeo, iconMat);
        icon.position.y = 0.5;
        icon.userData.billboard = true; // Flag for billboard animation
        group.add(icon);
        
        // Store reference for animation
        group.userData.ring = ring;
        group.userData.icon = icon;
        group.userData.baseOpacity = 0.3;
        
        group.position.copy(position);
        this.scene.add(group);
        this.directionalSigns.push(group);
        
        return group;
    }
    
    /**
     * Create all wing entrance signs at rotunda/wing boundary (uses DIMENSIONS).
     * Sign readable face normal points toward rotunda center so guests see correct text.
     */
    createAllWingSigns() {
        const rotundaRadius = DIMENSIONS.rotunda.radius;
        const height = DIMENSIONS.wing.entranceHeight ?? 4;
        COLONY_ORDER.forEach((colony, i) => {
            const angle = (i / 7) * Math.PI * 2;
            const x = Math.cos(angle) * (rotundaRadius + 2);
            const z = Math.sin(angle) * (rotundaRadius + 2);
            const normalizedAngle = ((angle % (Math.PI * 2)) + Math.PI * 2) % (Math.PI * 2);
            const arrowDirection = normalizedAngle < Math.PI ? 'right' : 'left';
            this.createWingSign(
                colony,
                new THREE.Vector3(x, height, z),
                angle + Math.PI / 2,
                arrowDirection
            );
            this.createFloorMarker(
                colony,
                new THREE.Vector3(
                    Math.cos(angle) * (rotundaRadius + 5),
                    0,
                    Math.sin(angle) * (rotundaRadius + 5)
                )
            );
        });
        
        // Return-to-rotunda arrows at gallery far ends
        this.createReturnArrows();
    }
    
    /**
     * Place return-to-rotunda chevron arrows at the far end of each gallery.
     * Glowing arrow pointing back toward rotunda.
     */
    createReturnArrows() {
        const rotundaRadius = DIMENSIONS.rotunda.radius;
        const wingLength = DIMENSIONS.wing.length;
        const vestibuleDepth = DIMENSIONS.wing.vestibuleDepth ?? 6;
        const galleryDepth = DIMENSIONS.gallery.depth;
        
        COLONY_ORDER.forEach((colony, i) => {
            const data = COLONY_COLORS[colony];
            const angle = (i / 7) * Math.PI * 2;
            const cos = Math.cos(angle), sin = Math.sin(angle);
            
            // Position at gallery far end
            const farDist = rotundaRadius + wingLength + vestibuleDepth + galleryDepth - 2;
            const x = cos * farDist;
            const z = sin * farDist;
            
            const group = new THREE.Group();
            group.name = `return-arrow-${colony}`;
            
            // Chevron arrow shape (pointing back toward rotunda)
            const shape = new THREE.Shape();
            shape.moveTo(0, 0.5);
            shape.lineTo(-0.4, 0);
            shape.lineTo(-0.15, 0);
            shape.lineTo(-0.15, -0.5);
            shape.lineTo(0.15, -0.5);
            shape.lineTo(0.15, 0);
            shape.lineTo(0.4, 0);
            shape.closePath();
            
            const arrowGeo = new THREE.ShapeGeometry(shape);
            const arrowMat = new THREE.MeshBasicMaterial({
                color: data.hex,
                transparent: true,
                opacity: 0.7,
                side: THREE.DoubleSide
            });
            
            const arrow = new THREE.Mesh(arrowGeo, arrowMat);
            arrow.rotation.x = -Math.PI / 2;  // Lay flat on floor
            arrow.rotation.z = angle + Math.PI; // Point toward rotunda
            arrow.position.set(x, 0.03, z);
            group.add(arrow);
            
            // Glow light
            const light = new THREE.PointLight(data.hex, 0.3, 5, 2);
            light.position.set(x, 0.5, z);
            group.add(light);
            
            // "← Rotunda" text sprite
            const canvas = document.createElement('canvas');
            canvas.width = 512;
            canvas.height = 128;
            const ctx = canvas.getContext('2d');
            ctx.fillStyle = '#000000';
            ctx.fillRect(0, 0, 512, 128);
            ctx.font = '32px "IBM Plex Sans", sans-serif';
            ctx.fillStyle = `#${data.hex.toString(16).padStart(6, '0')}`;
            ctx.textAlign = 'center';
            ctx.textBaseline = 'middle';
            ctx.fillText('← Rotunda', 256, 64);
            
            const texture = new THREE.CanvasTexture(canvas);
            const spriteMat = new THREE.SpriteMaterial({
                map: texture,
                transparent: true,
                opacity: 0.8
            });
            const sprite = new THREE.Sprite(spriteMat);
            sprite.position.set(x, 2.5, z);
            sprite.scale.set(3, 0.75, 1);
            group.add(sprite);
            
            this.scene.add(group);
            this.directionalSigns.push(group);
        });
    }
    
    /**
     * Update signs with approach animations and billboard icons.
     * Signs occluded by walls/ceiling are hidden (line-of-sight).
     */
    update(camera, time) {
        const cameraPos = camera.position;
        const _worldPos = new THREE.Vector3();
        
        // Update wing signs with approach detection and line-of-sight visibility
        this.signs.forEach(sign => {
            if (!sign.userData || !sign.userData.colony) return;
            
            sign.getWorldPosition(_worldPos);
            const inSight = isInLineOfSight(camera, _worldPos, this.scene);
            sign.visible = inSight;
            if (!inSight) return;
            
            // Calculate distance to sign
            const dist = cameraPos.distanceTo(_worldPos);
            const approachThreshold = 15;  // Start animation at 15m
            const closeThreshold = 5;      // Full effect at 5m
            
            // Calculate approach factor (0 = far, 1 = close)
            let approachFactor = 0;
            if (dist < approachThreshold) {
                approachFactor = 1 - (dist - closeThreshold) / (approachThreshold - closeThreshold);
                approachFactor = Math.max(0, Math.min(1, approachFactor));
            }
            
            // Apply subtle scale animation on approach
            const baseScale = sign.userData.baseScale || 1.0;
            const targetScale = baseScale + approachFactor * 0.08;
            sign.scale.lerp(new THREE.Vector3(targetScale, targetScale, targetScale), 0.1);
            
            // Increase LED glow on approach
            sign.traverse(child => {
                if (child.isPointLight) {
                    const baseIntensity = 0.4;
                    child.intensity = baseIntensity + approachFactor * 0.6;
                }
                // Increase emissive on trim when approaching
                if (child.material && child.material.emissiveIntensity !== undefined) {
                    const baseEmissive = sign.userData.baseEmissive || 0.4;
                    child.material.emissiveIntensity = baseEmissive + approachFactor * 0.4;
                }
            });
        });
        
        // Update floor markers (billboard icons and pulse rings)
        this.directionalSigns.forEach(sign => {
            // Billboard icon
            if (sign.userData.icon) {
                sign.userData.icon.lookAt(camera.position);
            }
            
            // Pulse ring
            if (sign.userData.ring) {
                const pulse = Math.sin(time * 2) * 0.1 + 0.1;
                sign.userData.ring.material.opacity = 0.7 + pulse;
                sign.userData.ring.scale.setScalar(1 + pulse * 0.1);
            }
        });
    }
    
    dispose() {
        this.signs.forEach(sign => {
            sign.traverse(obj => {
                if (obj.geometry) obj.geometry.dispose();
                if (obj.material) {
                    if (obj.material.map) obj.material.map.dispose();
                    obj.material.dispose();
                }
            });
            this.scene.remove(sign);
        });
        this.signs = [];
        
        this.directionalSigns.forEach(sign => {
            sign.traverse(obj => {
                if (obj.geometry) obj.geometry.dispose();
                if (obj.material) {
                    if (obj.material.map) obj.material.map.dispose();
                    obj.material.dispose();
                }
            });
            this.scene.remove(sign);
        });
        this.directionalSigns = [];
    }
}

// ═══════════════════════════════════════════════════════════════════════════
// INFORMATION KIOSK (HTML Overlay)
// ═══════════════════════════════════════════════════════════════════════════

export class InformationKiosk {
    constructor() {
        this.element = null;
        this.visible = false;
        this.currentContent = null;
        
        // Bound handlers for cleanup
        this._escapeHandler = null;
        this._backdropHandler = null;
        
        this.init();
    }
    
    init() {
        this.element = document.createElement('div');
        this.element.id = 'info-kiosk';
        this.element.style.cssText = `
            position: fixed;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%) scale(0.9);
            width: 90%;
            max-width: 600px;
            max-height: 80vh;
            background: linear-gradient(135deg, rgba(26, 26, 26, 0.98), rgba(40, 40, 40, 0.98));
            border: 1px solid rgba(103, 212, 228, 0.3);
            border-radius: 16px;
            box-shadow: 0 20px 60px rgba(0, 0, 0, 0.6), 0 0 40px rgba(103, 212, 228, 0.1);
            z-index: 1000;
            opacity: 0;
            visibility: hidden;
            transition: opacity 0.3s ease, transform 0.3s ease, visibility 0.3s;
            overflow: hidden;
            font-family: 'IBM Plex Sans', sans-serif;
        `;
        
        this.element.innerHTML = `
            <div id="kiosk-header" style="
                padding: 20px 24px;
                border-bottom: 1px solid rgba(103, 212, 228, 0.2);
                display: flex;
                justify-content: space-between;
                align-items: center;
            ">
                <h2 id="kiosk-title" style="
                    margin: 0;
                    font-size: 24px;
                    font-weight: 600;
                    color: #67D4E4;
                ">Information</h2>
                <button id="kiosk-close" style="
                    background: transparent;
                    border: none;
                    color: #666;
                    font-size: 28px;
                    cursor: pointer;
                    padding: 0;
                    line-height: 1;
                    transition: color 0.2s;
                " aria-label="Close">&times;</button>
            </div>
            <div id="kiosk-content" style="
                padding: 24px;
                overflow-y: auto;
                max-height: calc(80vh - 80px);
                color: #E0E0E0;
                line-height: 1.6;
            ">
                <!-- Content injected here -->
            </div>
        `;
        
        document.body.appendChild(this.element);
        
        // Close button handler
        this.element.querySelector('#kiosk-close').addEventListener('click', () => this.hide());
        
        // Close on escape (store reference for cleanup)
        this._escapeHandler = (e) => {
            if (e.key === 'Escape' && this.visible) {
                this.hide();
            }
        };
        document.addEventListener('keydown', this._escapeHandler);
        
        // Close on backdrop click (store reference for cleanup)
        this._backdropHandler = (e) => {
            if (e.target === this.element) {
                this.hide();
            }
        };
        this.element.addEventListener('click', this._backdropHandler);
    }
    
    /**
     * Show kiosk with museum overview
     */
    showMuseumOverview() {
        const content = `
            <div style="text-align: center; margin-bottom: 24px;">
                <span style="font-size: 48px;">鏡</span>
                <h3 style="margin: 8px 0; color: #5BC4D4; font-size: 20px;">Patent Museum</h3>
                <p style="color: #9E9994; margin: 0;">A constellation of 54 innovations — each one a promise kept</p>
            </div>
            
            <div style="margin-bottom: 24px;">
                <h4 style="color: #67D4E4; margin: 0 0 12px 0; font-size: 16px;">Navigation</h4>
                <ul style="margin: 0; padding-left: 20px; color: #AAA;">
                    <li>WASD or Arrow keys to move</li>
                    <li>Mouse to look around</li>
                    <li>Click on artworks to interact</li>
                    <li>Press M to toggle minimap</li>
                    <li>Press I for information</li>
                </ul>
            </div>
            
            <div style="margin-bottom: 24px;">
                <h4 style="color: #67D4E4; margin: 0 0 12px 0; font-size: 16px;">The Seven Wings</h4>
                <div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 8px;">
                    ${COLONY_ORDER.map(colony => `
                        <div style="
                            padding: 8px 12px;
                            background: rgba(${(COLONY_COLORS[colony].hex >> 16) & 255}, ${(COLONY_COLORS[colony].hex >> 8) & 255}, ${COLONY_COLORS[colony].hex & 255}, 0.1);
                            border-radius: 8px;
                            border-left: 3px solid rgb(${(COLONY_COLORS[colony].hex >> 16) & 255}, ${(COLONY_COLORS[colony].hex >> 8) & 255}, ${COLONY_COLORS[colony].hex & 255});
                        ">
                            <span style="font-size: 16px;">${COLONY_COLORS[colony].icon}</span>
                            <span style="color: rgb(${(COLONY_COLORS[colony].hex >> 16) & 255}, ${(COLONY_COLORS[colony].hex >> 8) & 255}, ${COLONY_COLORS[colony].hex & 255}); margin-left: 8px; font-weight: 500;">${COLONY_COLORS[colony].name}</span>
                        </div>
                    `).join('')}
                </div>
            </div>
            
            <div style="
                background: rgba(103, 212, 228, 0.1);
                border: 1px solid rgba(103, 212, 228, 0.3);
                border-radius: 8px;
                padding: 16px;
                text-align: center;
            ">
                <code style="color: #6FA370; font-family: 'IBM Plex Mono', monospace;">h(x) ≥ 0 always</code>
                <p style="margin: 8px 0 0 0; color: #888; font-size: 14px;">
                    The safety guarantee at the heart of every innovation
                </p>
            </div>
        `;
        
        this.show('Welcome to the Museum', content);
    }
    
    /**
     * Show wing-specific information
     */
    showWingInfo(colony) {
        const data = COLONY_COLORS[colony];
        const content = `
            <div style="text-align: center; margin-bottom: 24px;">
                <span style="font-size: 64px;">${data.icon}</span>
                <h3 style="margin: 8px 0; color: rgb(${(data.hex >> 16) & 255}, ${(data.hex >> 8) & 255}, ${data.hex & 255}); font-size: 24px;">${data.name} Wing</h3>
            </div>
            
            <p style="color: #AAA; margin-bottom: 24px;">
                Explore the innovations housed in this wing of the museum.
                Each artwork represents a unique patent or technological advancement.
            </p>
            
            <div style="
                background: rgba(${(data.hex >> 16) & 255}, ${(data.hex >> 8) & 255}, ${data.hex & 255}, 0.1);
                border-left: 3px solid rgb(${(data.hex >> 16) & 255}, ${(data.hex >> 8) & 255}, ${data.hex & 255});
                padding: 16px;
                border-radius: 0 8px 8px 0;
            ">
                <p style="margin: 0; color: #E0E0E0;">
                    Click on any artwork to learn more about the patent it represents.
                </p>
            </div>
        `;
        
        this.show(`${data.name} Wing`, content);
    }
    
    show(title, content) {
        this.element.querySelector('#kiosk-title').textContent = title;
        this.element.querySelector('#kiosk-content').innerHTML = content;
        
        this.visible = true;
        this.element.style.opacity = '1';
        this.element.style.visibility = 'visible';
        this.element.style.transform = 'translate(-50%, -50%) scale(1)';
        
        // Pause game/navigation if needed
        document.dispatchEvent(new CustomEvent('kiosk-opened'));
    }
    
    hide() {
        this.visible = false;
        this.element.style.opacity = '0';
        this.element.style.transform = 'translate(-50%, -50%) scale(0.9)';
        
        setTimeout(() => {
            if (!this.visible) {
                this.element.style.visibility = 'hidden';
            }
        }, 300);
        
        // Resume game/navigation
        document.dispatchEvent(new CustomEvent('kiosk-closed'));
    }
    
    toggle() {
        if (this.visible) {
            this.hide();
        } else {
            this.showMuseumOverview();
        }
    }
    
    dispose() {
        // Remove event listeners
        if (this._escapeHandler) {
            document.removeEventListener('keydown', this._escapeHandler);
            this._escapeHandler = null;
        }
        if (this._backdropHandler && this.element) {
            this.element.removeEventListener('click', this._backdropHandler);
            this._backdropHandler = null;
        }
        
        if (this.element && this.element.parentNode) {
            this.element.parentNode.removeChild(this.element);
        }
    }
}

// ═══════════════════════════════════════════════════════════════════════════
// WAYFINDING MANAGER
// ═══════════════════════════════════════════════════════════════════════════

export class WayfindingManager {
    constructor(scene) {
        this.scene = scene;
        this.minimap = null;
        this.signage = null;
        this.kiosk = null;
        this.architecturalCue = null;
        this.currentZone = 'rotunda';
        this.enabled = true;
        this._keyHandler = null;
        this.journeyTracker = null;
    }

    setJourneyTracker(tracker) {
        this.journeyTracker = tracker;
    }

    init() {
        this.minimap = new Minimap({
            size: 160,
            position: { right: 20, bottom: 20 }
        });
        this.minimap.hide();
        this.createArchitecturalCue();
        this.signage = new SignageSystem(this.scene);
        this.signage.createAllWingSigns();
        this.kiosk = new InformationKiosk();
        this._keyHandler = (e) => {
            if (!this.enabled) return;
            if (e.key.toLowerCase() === 'm') this.minimap.toggle();
            else if (e.key.toLowerCase() === 'i') this.kiosk.toggle();
        };
        document.addEventListener('keydown', this._keyHandler);
    }

    createArchitecturalCue() {
        this.architecturalCue = document.createElement('div');
        this.architecturalCue.id = 'architectural-cue';
        this.architecturalCue.setAttribute('aria-live', 'polite');
        this.architecturalCue.style.cssText = `
            position: fixed; bottom: 24px; left: 50%; transform: translateX(-50%);
            z-index: 100; pointer-events: none; text-align: center;
            font-family: 'IBM Plex Sans', sans-serif; font-size: 14px;
            color: rgba(245, 240, 232, 0.85); text-shadow: 0 1px 4px rgba(0,0,0,0.5);
        `;
        this.updateArchitecturalCue();
        document.body.appendChild(this.architecturalCue);
    }

    updateArchitecturalCue() {
        if (!this.architecturalCue) return;
        const zoneName = this.currentZone === 'rotunda' ? 'Rotunda' : this.currentZone.charAt(0).toUpperCase() + this.currentZone.slice(1);
        const showReturn = this.journeyTracker && shouldShowReturnToRotunda(this.journeyTracker);
        const hint = showReturn ? 'Return to Rotunda — Light and sound guide you to galleries' : `${zoneName} — Light and sound guide you to galleries`;
        this.architecturalCue.textContent = hint;
    }

    setZone(zone) {
        if (zone === this.currentZone) return;
        this.currentZone = zone || 'rotunda';
        this.updateArchitecturalCue();
    }

    update(camera, time) {
        if (!this.enabled) return;
        if (this.minimap) this.minimap.update(camera);
        if (this.signage) this.signage.update(camera, time);
    }

    showKiosk() {
        this.kiosk.showMuseumOverview();
    }

    hideKiosk() {
        this.kiosk.hide();
    }

    setEnabled(enabled) {
        this.enabled = enabled;
        if (this.minimap) this.minimap[enabled ? 'show' : 'hide']();
        if (!enabled) this.kiosk.hide();
        if (this.architecturalCue) this.architecturalCue.style.display = enabled ? '' : 'none';
    }

    dispose() {
        if (this._keyHandler) {
            document.removeEventListener('keydown', this._keyHandler);
            this._keyHandler = null;
        }
        if (this.architecturalCue && this.architecturalCue.parentNode) this.architecturalCue.remove();
        if (this.minimap) this.minimap.dispose();
        if (this.signage) this.signage.dispose();
        if (this.kiosk) this.kiosk.dispose();
    }
}

export default WayfindingManager;
