/**
 * Instanced Elements
 * ==================
 *
 * Shared InstancedMesh for repeated museum elements (pedestals) to reduce draw calls.
 * h(x) ≥ 0 always
 */

import * as THREE from 'three';

const PEDESTAL_GEOMETRY = new THREE.CylinderGeometry(1, 1.2, 0.2, 32);
const PEDESTAL_MATERIAL = new THREE.MeshPhysicalMaterial({
    color: 0x0A0A15,
    metalness: 0.9,
    roughness: 0.1
});

const _position = new THREE.Vector3();
const _quaternion = new THREE.Quaternion();
const _scale = new THREE.Vector3(1, 1, 1);
const _matrix = new THREE.Matrix4();

/**
 * Create a single InstancedMesh for all pedestals at the given world positions.
 * Each position is the base of the pedestal (y=0); the cylinder is centered at height 0.1.
 *
 * @param {THREE.Vector3[]} worldPositions - Array of world positions (one per artwork)
 * @returns {THREE.InstancedMesh}
 */
export function createInstancedPedestals(worldPositions) {
    const count = worldPositions.length;
    const mesh = new THREE.InstancedMesh(PEDESTAL_GEOMETRY, PEDESTAL_MATERIAL, count);
    mesh.name = 'instanced-pedestals';
    mesh.count = count;

    for (let i = 0; i < count; i++) {
        _position.copy(worldPositions[i]);
        _position.y = 0.1; // pedestal center height
        _matrix.compose(_position, _quaternion, _scale);
        mesh.setMatrixAt(i, _matrix);
    }
    mesh.instanceMatrix.needsUpdate = true;

    return mesh;
}

/**
 * Traverse a container and hide all meshes marked as pedestals (userData.isPedestal === true).
 * Call after adding instanced pedestals so original per-artwork pedestals are not drawn.
 *
 * @param {THREE.Object3D} container
 */
export function hideOriginalPedestals(container) {
    container.traverse((obj) => {
        if (obj.userData?.isPedestal === true && obj.type === 'Mesh') {
            obj.visible = false;
        }
    });
}

/**
 * Collect world positions of all artwork roots (for instancing).
 *
 * @param {Map<string, THREE.Object3D>} artworkMap - patentId -> artwork Group
 * @param {THREE.Vector3} [out] - Optional array to push into
 * @returns {THREE.Vector3[]}
 */
export function collectArtworkPositions(artworkMap, out = []) {
    out.length = 0;
    const v = new THREE.Vector3();
    artworkMap.forEach((artwork) => {
        artwork.getWorldPosition(v);
        out.push(v.clone());
    });
    return out;
}

export { PEDESTAL_GEOMETRY, PEDESTAL_MATERIAL };
