/**
 * Culling System for Patent Museum
 * =================================
 * 
 * High-performance culling for:
 * - Frustum culling (camera view)
 * - Distance culling (LOD and visibility)
 * - Zone-based culling (museum wings)
 * - Light culling (active lights)
 * 
 * Inspired by AAA game engines and Google Maps optimization patterns.
 * 
 * h(x) ≥ 0 always
 */

import * as THREE from 'three';

// ═══════════════════════════════════════════════════════════════════════════
// CONSTANTS
// ═══════════════════════════════════════════════════════════════════════════

const DEFAULT_DRAW_DISTANCE = 80;
const LOD_DISTANCES = {
    high: 20,      // Full detail
    medium: 50,    // Reduced detail
    low: 80,       // Minimal detail
    cull: 120      // Not rendered
};

// ═══════════════════════════════════════════════════════════════════════════
// FRUSTUM CULLER
// ═══════════════════════════════════════════════════════════════════════════

export class FrustumCuller {
    constructor(camera) {
        this.camera = camera;
        this.frustum = new THREE.Frustum();
        this.projScreenMatrix = new THREE.Matrix4();
        this._tempBox = new THREE.Box3();
        this._tempSphere = new THREE.Sphere();
        
        // Cache for object bounds
        this.boundsCache = new Map();
    }
    
    /**
     * Update frustum from camera matrices
     * Call once per frame before culling checks
     */
    update() {
        this.camera.updateMatrixWorld();
        this.projScreenMatrix.multiplyMatrices(
            this.camera.projectionMatrix,
            this.camera.matrixWorldInverse
        );
        this.frustum.setFromProjectionMatrix(this.projScreenMatrix);
    }
    
    /**
     * Check if an object is visible in the frustum
     * @param {THREE.Object3D} object
     * @returns {boolean}
     */
    isVisible(object) {
        // Try cached bounds first
        let bounds = this.boundsCache.get(object.uuid);
        
        if (!bounds) {
            // Compute and cache bounds
            if (object.geometry) {
                if (!object.geometry.boundingSphere) {
                    object.geometry.computeBoundingSphere();
                }
                
                // Check for NaN in bounding sphere (can happen with empty geometries)
                if (object.geometry.boundingSphere && 
                    !isNaN(object.geometry.boundingSphere.radius) &&
                    object.geometry.boundingSphere.radius > 0) {
                    bounds = object.geometry.boundingSphere.clone();
                    this.boundsCache.set(object.uuid, bounds);
                } else {
                    // Invalid bounds - assume visible
                    return true;
                }
            } else {
                return true; // No geometry = assume visible
            }
        }
        
        // Transform sphere to world space
        this._tempSphere.copy(bounds);
        this._tempSphere.applyMatrix4(object.matrixWorld);
        
        // Check for NaN after transform (can happen with bad matrixWorld)
        if (isNaN(this._tempSphere.center.x) || isNaN(this._tempSphere.radius)) {
            return true; // Assume visible if transform failed
        }
        
        return this.frustum.intersectsSphere(this._tempSphere);
    }
    
    /**
     * Check if a bounding box is visible
     * @param {THREE.Box3} box
     * @returns {boolean}
     */
    isBoxVisible(box) {
        return this.frustum.intersectsBox(box);
    }
    
    /**
     * Clear cached bounds (call when geometry changes)
     */
    clearCache() {
        this.boundsCache.clear();
    }
}

// ═══════════════════════════════════════════════════════════════════════════
// DISTANCE CULLER
// ═══════════════════════════════════════════════════════════════════════════

export class DistanceCuller {
    constructor(camera, drawDistance = DEFAULT_DRAW_DISTANCE) {
        this.camera = camera;
        this.drawDistance = drawDistance;
        this.lodDistances = { ...LOD_DISTANCES };
        this._tempVec = new THREE.Vector3();
    }
    
    /**
     * Get distance from camera to object
     * @param {THREE.Object3D} object
     * @returns {number}
     */
    getDistance(object) {
        object.getWorldPosition(this._tempVec);
        return this._tempVec.distanceTo(this.camera.position);
    }
    
    /**
     * Check if object should be visible based on distance
     * @param {THREE.Object3D} object
     * @returns {boolean}
     */
    isVisible(object) {
        return this.getDistance(object) < this.drawDistance;
    }
    
    /**
     * Get LOD level for object based on distance
     * @param {THREE.Object3D} object
     * @returns {'high'|'medium'|'low'|'cull'}
     */
    getLODLevel(object) {
        const dist = this.getDistance(object);
        
        if (dist < this.lodDistances.high) return 'high';
        if (dist < this.lodDistances.medium) return 'medium';
        if (dist < this.lodDistances.low) return 'low';
        return 'cull';
    }
    
    /**
     * Set draw distance
     * @param {number} distance
     */
    setDrawDistance(distance) {
        this.drawDistance = distance;
    }
    
    /**
     * Set LOD distances
     * @param {Object} distances - { high, medium, low, cull }
     */
    setLODDistances(distances) {
        Object.assign(this.lodDistances, distances);
    }
}

// ═══════════════════════════════════════════════════════════════════════════
// ZONE CULLER (Museum Wing System)
// ═══════════════════════════════════════════════════════════════════════════

export class ZoneCuller {
    constructor() {
        this.zones = new Map();
        this.activeZones = new Set();
        this.adjacencyMap = new Map();
    }
    
    /**
     * Register a zone
     * @param {string} zoneId
     * @param {THREE.Box3} bounds - Zone bounding box
     * @param {THREE.Group} objects - Objects in this zone
     */
    registerZone(zoneId, bounds, objects) {
        this.zones.set(zoneId, {
            id: zoneId,
            bounds,
            objects,
            loaded: true,
            visible: true
        });
    }
    
    /**
     * Set zone adjacency (which zones should stay loaded when in a zone)
     * @param {string} zoneId
     * @param {string[]} adjacentZoneIds
     */
    setAdjacency(zoneId, adjacentZoneIds) {
        this.adjacencyMap.set(zoneId, adjacentZoneIds);
    }
    
    /**
     * Update active zones based on camera position
     * @param {THREE.Vector3} cameraPosition
     * @returns {Set<string>} - Active zone IDs
     */
    updateActiveZones(cameraPosition) {
        this.activeZones.clear();
        
        // Find which zone camera is in
        for (const [zoneId, zone] of this.zones) {
            if (zone.bounds.containsPoint(cameraPosition)) {
                this.activeZones.add(zoneId);
                
                // Add adjacent zones
                const adjacent = this.adjacencyMap.get(zoneId) || [];
                adjacent.forEach(id => this.activeZones.add(id));
            }
        }
        
        // Always include rotunda (center)
        if (this.zones.has('rotunda')) {
            this.activeZones.add('rotunda');
        }
        
        return this.activeZones;
    }
    
    /**
     * Apply zone culling to scene.
     * Wing and rotunda structure are always kept visible (no visible = false)
     * to avoid dead ends and disappearing walls; activeZones still updated for other use.
     */
    cull(cameraPosition) {
        this.updateActiveZones(cameraPosition);
        
        for (const [zoneId, zone] of this.zones) {
            if (!zone.objects) continue;
            // Never hide wing/rotunda structure — keeps walls and corridors always visible
            const shouldBeVisible = this.activeZones.has(zoneId);
            if (shouldBeVisible && !zone.visible) {
                zone.objects.visible = true;
                zone.visible = true;
            }
            // Do not set visible = false for any zone (avoids disappearing wings)
        }
    }
    
    /**
     * Check if a zone is currently active
     * @param {string} zoneId
     * @returns {boolean}
     */
    isZoneActive(zoneId) {
        return this.activeZones.has(zoneId);
    }
}

// ═══════════════════════════════════════════════════════════════════════════
// LIGHT CULLER
// ═══════════════════════════════════════════════════════════════════════════

export class LightCuller {
    constructor(camera, maxActiveLights = 8) {
        this.camera = camera;
        this.maxActiveLights = maxActiveLights;
        this.lights = [];
        this._tempVec = new THREE.Vector3();
    }
    
    /**
     * Register lights to be managed
     * @param {THREE.Light[]} lights
     */
    registerLights(lights) {
        this.lights = lights.map(light => ({
            light,
            originalIntensity: light.intensity,
            distance: 0
        }));
    }
    
    /**
     * Add a light to be managed
     * @param {THREE.Light} light
     */
    addLight(light) {
        this.lights.push({
            light,
            originalIntensity: light.intensity,
            distance: 0
        });
    }
    
    /**
     * Update light visibility based on distance
     * Only keep the N closest lights active
     */
    update() {
        // Calculate distances
        this.lights.forEach(entry => {
            entry.light.getWorldPosition(this._tempVec);
            entry.distance = this._tempVec.distanceTo(this.camera.position);
        });
        
        // Sort by distance
        this.lights.sort((a, b) => a.distance - b.distance);
        
        // Enable closest N lights, disable rest
        this.lights.forEach((entry, index) => {
            if (index < this.maxActiveLights) {
                entry.light.visible = true;
                
                // Fade intensity based on distance
                const maxDist = 50;
                const falloff = Math.max(0, 1 - (entry.distance / maxDist));
                entry.light.intensity = entry.originalIntensity * falloff;
            } else {
                entry.light.visible = false;
                entry.light.intensity = 0;
            }
        });
    }
    
    /**
     * Get count of currently active lights
     * @returns {number}
     */
    getActiveLightCount() {
        return this.lights.filter(e => e.light.visible).length;
    }
}

// ═══════════════════════════════════════════════════════════════════════════
// UNIFIED CULLING MANAGER
// ═══════════════════════════════════════════════════════════════════════════

export class CullingManager {
    constructor(camera, options = {}) {
        this.camera = camera;
        this.enabled = true;
        
        // Culling subsystems
        this.frustumCuller = new FrustumCuller(camera);
        this.distanceCuller = new DistanceCuller(camera, options.drawDistance || DEFAULT_DRAW_DISTANCE);
        this.zoneCuller = new ZoneCuller();
        this.lightCuller = new LightCuller(camera, options.maxLights || 8);
        
        // Managed objects
        this.cullableGroups = new Map();
        this.artworks = [];
        
        // Stats
        this.stats = {
            objectsCulled: 0,
            objectsVisible: 0,
            lightsCulled: 0,
            lightsActive: 0,
            lastUpdateTime: 0
        };
        
        // Update frequency (frames)
        this.updateFrequency = options.updateFrequency || 2;
        this._frameCount = 0;
    }
    
    /**
     * Register a group of objects for culling
     * @param {string} groupId
     * @param {THREE.Object3D} group
     */
    registerGroup(groupId, group) {
        this.cullableGroups.set(groupId, group);
    }
    
    /**
     * Register artworks for distance/LOD culling
     * @param {THREE.Object3D[]} artworks
     */
    registerArtworks(artworks) {
        this.artworks = artworks;
    }
    
    /**
     * Register a zone with bounds
     * @param {string} zoneId
     * @param {THREE.Vector3} center
     * @param {THREE.Vector3} size
     * @param {THREE.Group} objects
     */
    registerZone(zoneId, center, size, objects) {
        const bounds = new THREE.Box3(
            new THREE.Vector3(center.x - size.x/2, center.y - size.y/2, center.z - size.z/2),
            new THREE.Vector3(center.x + size.x/2, center.y + size.y/2, center.z + size.z/2)
        );
        this.zoneCuller.registerZone(zoneId, bounds, objects);
    }
    
    /**
     * Main update - call once per frame
     * @returns {Object} Stats
     */
    update() {
        if (!this.enabled) return this.stats;
        
        this._frameCount++;
        
        // Only update every N frames for performance
        if (this._frameCount % this.updateFrequency !== 0) {
            return this.stats;
        }
        
        const startTime = performance.now();
        
        // Reset stats
        this.stats.objectsCulled = 0;
        this.stats.objectsVisible = 0;
        
        // Update frustum
        this.frustumCuller.update();
        
        // Cull zones first (coarse culling)
        this.zoneCuller.cull(this.camera.position);
        
        // Cull artworks (fine culling)
        this.cullArtworks();
        
        // Cull lights
        this.lightCuller.update();
        this.stats.lightsActive = this.lightCuller.getActiveLightCount();
        this.stats.lightsCulled = this.lightCuller.lights.length - this.stats.lightsActive;
        
        this.stats.lastUpdateTime = performance.now() - startTime;
        
        return this.stats;
    }
    
    /**
     * Cull individual artworks based on frustum and distance
     */
    cullArtworks() {
        for (const artwork of this.artworks) {
            // Skip if parent zone is culled
            if (artwork.parent && !artwork.parent.visible) {
                continue;
            }
            
            // Distance check first (cheaper)
            const distance = this.distanceCuller.getDistance(artwork);
            
            if (distance > this.distanceCuller.drawDistance) {
                if (artwork.visible) {
                    artwork.visible = false;
                    this.stats.objectsCulled++;
                }
                continue;
            }
            
            // Frustum check
            const inFrustum = this.frustumCuller.isVisible(artwork);
            
            if (inFrustum) {
                if (!artwork.visible) {
                    artwork.visible = true;
                }
                this.stats.objectsVisible++;
                
                // Apply LOD
                this.applyLOD(artwork, distance);
            } else {
                if (artwork.visible) {
                    artwork.visible = false;
                    this.stats.objectsCulled++;
                }
            }
        }
    }
    
    /**
     * Apply LOD to artwork based on distance
     * @param {THREE.Object3D} artwork
     * @param {number} distance
     */
    applyLOD(artwork, distance) {
        const lodLevel = this.distanceCuller.getLODLevel({ 
            getWorldPosition: () => artwork.position 
        });
        
        // Apply material simplification based on LOD
        artwork.traverse(child => {
            if (child.isMesh && child.material) {
                const mat = child.material;
                
                switch (lodLevel) {
                    case 'high':
                        // Full quality
                        if (mat.userData.originalEnvMapIntensity !== undefined) {
                            mat.envMapIntensity = mat.userData.originalEnvMapIntensity;
                        }
                        break;
                    case 'medium':
                        // Reduced env map
                        if (mat.envMapIntensity !== undefined) {
                            mat.userData.originalEnvMapIntensity = mat.userData.originalEnvMapIntensity || mat.envMapIntensity;
                            mat.envMapIntensity = 0.3;
                        }
                        break;
                    case 'low':
                        // No env map
                        if (mat.envMapIntensity !== undefined) {
                            mat.userData.originalEnvMapIntensity = mat.userData.originalEnvMapIntensity || mat.envMapIntensity;
                            mat.envMapIntensity = 0;
                        }
                        break;
                }
            }
        });
    }
    
    /**
     * Set draw distance
     * @param {number} distance
     */
    setDrawDistance(distance) {
        this.distanceCuller.setDrawDistance(distance);
    }
    
    /**
     * Enable/disable culling
     * @param {boolean} enabled
     */
    setEnabled(enabled) {
        this.enabled = enabled;
        
        // If disabled, make everything visible
        if (!enabled) {
            for (const artwork of this.artworks) {
                artwork.visible = true;
            }
        }
    }
    
    /**
     * Get current stats
     * @returns {Object}
     */
    getStats() {
        return { ...this.stats };
    }
}

// ═══════════════════════════════════════════════════════════════════════════
// SPATIAL PARTITIONING (Octree for raycasts)
// ═══════════════════════════════════════════════════════════════════════════

export class SimpleOctree {
    constructor(bounds, maxDepth = 5, maxObjects = 8) {
        this.bounds = bounds;
        this.maxDepth = maxDepth;
        this.maxObjects = maxObjects;
        this.objects = [];
        this.children = null;
        this.depth = 0;
    }
    
    /**
     * Insert an object into the octree
     * @param {THREE.Object3D} object
     */
    insert(object) {
        if (!object.geometry) return;
        
        // Compute object bounds
        if (!object.geometry.boundingBox) {
            object.geometry.computeBoundingBox();
        }
        
        const objBounds = object.geometry.boundingBox.clone();
        objBounds.applyMatrix4(object.matrixWorld);
        
        // Check if object fits in this node
        if (!this.bounds.intersectsBox(objBounds)) {
            return false;
        }
        
        // If we have children, insert into appropriate child
        if (this.children) {
            for (const child of this.children) {
                child.insert(object);
            }
            return true;
        }
        
        // Add to this node
        this.objects.push({ object, bounds: objBounds });
        
        // Subdivide if needed
        if (this.objects.length > this.maxObjects && this.depth < this.maxDepth) {
            this.subdivide();
        }
        
        return true;
    }
    
    /**
     * Subdivide this node into 8 children
     */
    subdivide() {
        const center = new THREE.Vector3();
        this.bounds.getCenter(center);
        
        const min = this.bounds.min;
        const max = this.bounds.max;
        
        this.children = [];
        
        // Create 8 child nodes
        for (let x = 0; x < 2; x++) {
            for (let y = 0; y < 2; y++) {
                for (let z = 0; z < 2; z++) {
                    const childMin = new THREE.Vector3(
                        x === 0 ? min.x : center.x,
                        y === 0 ? min.y : center.y,
                        z === 0 ? min.z : center.z
                    );
                    const childMax = new THREE.Vector3(
                        x === 0 ? center.x : max.x,
                        y === 0 ? center.y : max.y,
                        z === 0 ? center.z : max.z
                    );
                    
                    const childBounds = new THREE.Box3(childMin, childMax);
                    const child = new SimpleOctree(childBounds, this.maxDepth, this.maxObjects);
                    child.depth = this.depth + 1;
                    this.children.push(child);
                }
            }
        }
        
        // Re-insert objects into children
        for (const entry of this.objects) {
            for (const child of this.children) {
                child.insert(entry.object);
            }
        }
        
        this.objects = [];
    }
    
    /**
     * Query objects that might intersect with a ray
     * @param {THREE.Ray} ray
     * @returns {THREE.Object3D[]}
     */
    queryRay(ray) {
        const results = [];
        
        // Check if ray intersects this node
        if (!ray.intersectsBox(this.bounds)) {
            return results;
        }
        
        // Check objects in this node
        for (const entry of this.objects) {
            if (ray.intersectsBox(entry.bounds)) {
                results.push(entry.object);
            }
        }
        
        // Recurse into children
        if (this.children) {
            for (const child of this.children) {
                results.push(...child.queryRay(ray));
            }
        }
        
        return results;
    }
    
    /**
     * Query objects within a sphere
     * @param {THREE.Sphere} sphere
     * @returns {THREE.Object3D[]}
     */
    querySphere(sphere) {
        const results = [];
        
        // Check if sphere intersects this node
        if (!this.bounds.intersectsSphere(sphere)) {
            return results;
        }
        
        // Check objects in this node
        for (const entry of this.objects) {
            if (entry.bounds.intersectsSphere(sphere)) {
                results.push(entry.object);
            }
        }
        
        // Recurse into children
        if (this.children) {
            for (const child of this.children) {
                results.push(...child.querySphere(sphere));
            }
        }
        
        return results;
    }
    
    /**
     * Clear the octree
     */
    clear() {
        this.objects = [];
        this.children = null;
    }
}

// ═══════════════════════════════════════════════════════════════════════════
// LINE-OF-SIGHT / VISIBILITY API
// ═══════════════════════════════════════════════════════════════════════════

const _rayOrigin = new THREE.Vector3();
const _rayDirection = new THREE.Vector3();
const _targetPosition = new THREE.Vector3();

/**
 * Collect all meshes in the scene that block line-of-sight (userData.occludes === true).
 * @param {THREE.Object3D} scene
 * @returns {THREE.Mesh[]}
 */
export function getOccludingObjects(scene) {
    const list = [];
    scene.traverseVisible((obj) => {
        if (obj.isMesh && obj.userData && obj.userData.occludes === true) {
            list.push(obj);
        }
    });
    return list;
}

/**
 * Check if a target point is in line of sight from the camera (no occluding geometry in between).
 * Uses meshes tagged with userData.occludes in the scene.
 * @param {THREE.Camera} camera
 * @param {THREE.Vector3|{x:number,y:number,z:number}} targetPosition - World position to test
 * @param {THREE.Object3D} scene
 * @param {{ epsilon?: number }} options - epsilon: tolerance for hit distance (default 0.1)
 * @returns {boolean} true if nothing occludes the line from camera to target
 */
export function isInLineOfSight(camera, targetPosition, scene, options = {}) {
    const epsilon = options.epsilon ?? 0.1;
    _rayOrigin.copy(camera.position);
    _targetPosition.set(targetPosition.x, targetPosition.y, targetPosition.z);
    _rayDirection.subVectors(_targetPosition, _rayOrigin);
    const distToTarget = _rayDirection.length();
    if (distToTarget < 1e-6) return true;
    _rayDirection.normalize();

    const raycaster = new THREE.Raycaster(_rayOrigin, _rayDirection, 0, distToTarget - epsilon);
    const occluding = getOccludingObjects(scene);
    const hits = raycaster.intersectObjects(occluding, true);
    return hits.length === 0 || hits[0].distance >= distToTarget - epsilon;
}

/**
 * Filter a list of target positions (or objects with position) to those visible from the camera.
 * @param {THREE.Camera} camera
 * @param {Array<THREE.Vector3|THREE.Object3D|{x:number,y:number,z:number}>} targets - Positions or objects with .position
 * @param {THREE.Object3D} scene
 * @returns {Array<THREE.Vector3|THREE.Object3D|{x:number,y:number,z:number}>} Targets that are in line of sight
 */
export function getVisibleTargets(camera, targets, scene) {
    return targets.filter((t) => {
        const pos = t && (t.position !== undefined) ? t.position : t;
        return pos && isInLineOfSight(camera, pos, scene);
    });
}

// ═══════════════════════════════════════════════════════════════════════════
// EXPORT SINGLETON FACTORY
// ═══════════════════════════════════════════════════════════════════════════

let cullingManagerInstance = null;

export function getCullingManager(camera, options = {}) {
    if (!cullingManagerInstance && camera) {
        cullingManagerInstance = new CullingManager(camera, options);
    }
    return cullingManagerInstance;
}
