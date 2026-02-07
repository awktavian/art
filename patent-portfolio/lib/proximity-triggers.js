/**
 * Proximity Trigger System
 * ========================
 *
 * Automatic artwork engagement based on visitor distance:
 * - Enter zone (3m): spark effect + hint appears
 * - Dwell (5s): sustain reveal + info highlight
 * - Click: full info panel (unchanged)
 *
 * h(x) ≥ 0 always
 */

import * as THREE from 'three';

// ═══════════════════════════════════════════════════════════════════════════
// CONFIG
// ═══════════════════════════════════════════════════════════════════════════

const PROXIMITY_RADIUS = 3;       // meters - trigger spark when visitor enters
const SUSTAIN_DWELL_MS = 5000;    // 5 seconds in zone triggers sustain
const HINT_FADE_MS = 233;         // Fibonacci timing for hint appearance

// ═══════════════════════════════════════════════════════════════════════════
// PROXIMITY TRIGGER MANAGER
// ═══════════════════════════════════════════════════════════════════════════

export class ProximityTriggerManager {
    /**
     * @param {THREE.Scene} scene
     * @param {THREE.Camera} camera
     * @param {Map<string, THREE.Object3D>} artworkMap - patentId -> artwork Group
     */
    constructor(scene, camera, artworkMap) {
        this.scene = scene;
        this.camera = camera;
        this.artworkMap = artworkMap || new Map();

        /** @type {Map<THREE.Object3D, { inZone: boolean, enterTime: number, sustainFired: boolean }>} */
        this._state = new Map();
        this._worldPos = new THREE.Vector3();
        this._nearestArtwork = null;
        this._nearestDistance = Infinity;
        this._lastSparkPatentId = null;
        this._lastSustainPatentId = null;

        /** Callbacks for app integration */
        this.onSpark = null;   // (patentId, artwork) => void
        this.onSustain = null; // (patentId, artwork) => void
        this.onExit = null;    // (patentId) => void
    }

    /**
     * Register artworks from a Map or from scene traversal.
     * @param {Map<string, THREE.Object3D>} [map]
     */
    setArtworkMap(map) {
        this.artworkMap = map || new Map();
        this._state.clear();
    }

    /**
     * Collect interactable artwork groups from scene (groups with userData.patentId).
     */
    collectFromScene() {
        const map = new Map();
        this.scene.traverse((obj) => {
            const patentId = obj.userData?.patentId || obj.userData?.artwork?.id;
            if (patentId && (obj.userData?.interactive || obj.userData?.artwork)) {
                const root = this._getArtworkRoot(obj);
                if (root && !map.has(patentId)) {
                    map.set(patentId, root);
                }
            }
        });
        this.artworkMap = map;
        this._state.clear();
    }

    _getArtworkRoot(obj) {
        let current = obj;
        while (current.parent && current.parent !== this.scene) {
            if (current.userData?.patentId || current.userData?.artwork) {
                return current;
            }
            current = current.parent;
        }
        return current;
    }

    /**
     * @param {number} deltaTime
     * @param {THREE.Vector3} cameraPosition
     */
    update(deltaTime, cameraPosition) {
        if (!cameraPosition || !this.artworkMap.size) return;

        this._nearestArtwork = null;
        this._nearestDistance = Infinity;

        const now = performance.now();

        for (const [patentId, artwork] of this.artworkMap) {
            if (!artwork) continue;

            artwork.getWorldPosition(this._worldPos);
            const dx = cameraPosition.x - this._worldPos.x;
            const dy = cameraPosition.y - this._worldPos.y;
            const dz = cameraPosition.z - this._worldPos.z;
            const dist = Math.sqrt(dx * dx + dy * dy + dz * dz);

            if (dist < this._nearestDistance) {
                this._nearestDistance = dist;
                this._nearestArtwork = { patentId, artwork, dist };
            }

            let state = this._state.get(artwork);
            if (!state) {
                state = { inZone: false, enterTime: 0, sustainFired: false };
                this._state.set(artwork, state);
            }

            const inZone = dist <= PROXIMITY_RADIUS;

            if (inZone) {
                if (!state.inZone) {
                    state.inZone = true;
                    state.enterTime = now;
                    this._fireSpark(patentId, artwork);
                    if (typeof artwork.onProximity === 'function') {
                        artwork.onProximity('enter');
                    }
                }

                const dwellTime = now - state.enterTime;
                if (dwellTime >= SUSTAIN_DWELL_MS && !state.sustainFired) {
                    state.sustainFired = true;
                    this._fireSustain(patentId, artwork);
                    if (typeof artwork.onProximity === 'function') {
                        artwork.onProximity('sustain');
                    }
                }
            } else {
                if (state.inZone) {
                    state.inZone = false;
                    state.enterTime = 0;
                    state.sustainFired = false;
                    if (this._lastSparkPatentId === patentId) this._lastSparkPatentId = null;
                    if (this._lastSustainPatentId === patentId) this._lastSustainPatentId = null;
                    if (this.onExit) {
                        this.onExit(patentId);
                    }
                    if (typeof artwork.onProximity === 'function') {
                        artwork.onProximity('exit');
                    }
                }
            }
        }
    }

    _fireSpark(patentId, artwork) {
        if (this._lastSparkPatentId === patentId) return;
        this._lastSparkPatentId = patentId;

        if (this.onSpark) {
            this.onSpark(patentId, artwork);
        }

        window.dispatchEvent(new CustomEvent('proximity-spark', {
            detail: { patentId, artwork }
        }));
    }

    _fireSustain(patentId, artwork) {
        if (this._lastSustainPatentId === patentId) return;
        this._lastSustainPatentId = patentId;

        if (this.onSustain) {
            this.onSustain(patentId, artwork);
        }

        window.dispatchEvent(new CustomEvent('proximity-sustain', {
            detail: { patentId, artwork }
        }));
    }

    /**
     * Get currently nearest artwork and distance (for UI hint).
     */
    getNearest() {
        return this._nearestArtwork;
    }

    /**
     * Check if visitor is in proximity of any artwork.
     */
    isInProximity() {
        return this._nearestArtwork && this._nearestArtwork.dist <= PROXIMITY_RADIUS;
    }

    dispose() {
        this._state.clear();
        this.artworkMap.clear();
        this.onSpark = null;
        this.onSustain = null;
        this.onExit = null;
    }
}

export { PROXIMITY_RADIUS, SUSTAIN_DWELL_MS, HINT_FADE_MS };
export default ProximityTriggerManager;
