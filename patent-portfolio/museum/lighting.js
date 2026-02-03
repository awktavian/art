/**
 * Turrell-Inspired Mono-Frequency Lighting System
 * ===============================================
 * 
 * Inspired by James Turrell's Skyspaces and Olafur Eliasson's
 * mono-frequency rooms. Each wing bathes visitors in its colony's
 * characteristic light, creating perception shifts as they move.
 * 
 * "I'm shaping the experience of seeing rather than delivering an image."
 * — James Turrell
 * 
 * h(x) ≥ 0 always
 */

import * as THREE from 'three';
import { COLONY_DATA, COLONY_ORDER, DIMENSIONS } from './architecture.js';

// ═══════════════════════════════════════════════════════════════════════════
// LIGHTING PROFILES
// ═══════════════════════════════════════════════════════════════════════════

const LIGHTING_PROFILES = {
    // Warm, energetic start - increased fog for dramatic effect
    spark: {
        primary: 0xFF6B35,
        secondary: 0xFF8F5A,
        ambient: 0x3D1F10,
        intensity: 1.2,
        temperature: 'warm',
        mood: 'energetic',
        fogDensity: 0.025,
        fogHeightFalloff: 0.05
    },
    
    // Rich, golden craftsmanship
    forge: {
        primary: 0xD4AF37,
        secondary: 0xF4CF47,
        ambient: 0x2A2208,
        intensity: 1.1,
        temperature: 'warm',
        mood: 'focused',
        fogDensity: 0.022,
        fogHeightFalloff: 0.04
    },
    
    // Cool, flowing serenity - more fog for ethereal feel
    flow: {
        primary: 0x4ECDC4,
        secondary: 0x6EDDD4,
        ambient: 0x0D2927,
        intensity: 1.0,
        temperature: 'cool',
        mood: 'calm',
        fogDensity: 0.032,
        fogHeightFalloff: 0.03
    },
    
    // Mysterious, connecting purple - dense fog
    nexus: {
        primary: 0x9B7EBD,
        secondary: 0xBB9EDD,
        ambient: 0x1A1525,
        intensity: 0.9,
        temperature: 'neutral',
        mood: 'mysterious',
        fogDensity: 0.038,
        fogHeightFalloff: 0.02
    },
    
    // Bold, illuminating amber
    beacon: {
        primary: 0xF59E0B,
        secondary: 0xFFC043,
        ambient: 0x2D1D05,
        intensity: 1.3,
        temperature: 'warm',
        mood: 'inspiring',
        fogDensity: 0.02,
        fogHeightFalloff: 0.06
    },
    
    // Natural, organic green - soft fog
    grove: {
        primary: 0x7EB77F,
        secondary: 0x9ED79F,
        ambient: 0x152016,
        intensity: 0.95,
        temperature: 'neutral',
        mood: 'organic',
        fogDensity: 0.035,
        fogHeightFalloff: 0.025
    },
    
    // Pure, crystalline clarity - clearer, less fog
    crystal: {
        primary: 0x67D4E4,
        secondary: 0x87F4FF,
        ambient: 0x0D2A30,
        intensity: 1.05,
        temperature: 'cool',
        mood: 'clarity',
        fogDensity: 0.018,
        fogHeightFalloff: 0.08
    },
    
    // Neutral rotunda (all colors blend) - moderate fog
    rotunda: {
        primary: 0xF5F0E8,
        secondary: 0xFFFFFF,
        ambient: 0x12101A,
        intensity: 0.7,
        temperature: 'neutral',
        mood: 'wonder',
        fogDensity: 0.028,
        fogHeightFalloff: 0.04
    }
};

// ═══════════════════════════════════════════════════════════════════════════
// TURRELL LIGHTING CONTROLLER
// ═══════════════════════════════════════════════════════════════════════════

export class TurrellLighting {
    constructor(scene, camera) {
        this.scene = scene;
        this.camera = camera;
        
        // Current lighting state
        this.currentZone = 'rotunda';
        this.targetProfile = LIGHTING_PROFILES.rotunda;
        this.currentProfile = { ...LIGHTING_PROFILES.rotunda };
        
        // Transition state
        this.transitionProgress = 1.0;
        this.transitionDuration = 2.0; // seconds for full transition
        
        // Light objects
        this.ambientLight = null;
        this.hemisphereLights = [];
        this.zoneLights = {};
        this.fog = null;
        
        // Volumetric god rays (rotunda skylight)
        this.godRays = null;
        
        this.init();
    }
    
    init() {
        // Base ambient (very dim, allows zone lights to dominate)
        this.ambientLight = new THREE.AmbientLight(0x404050, 0.15);
        this.scene.add(this.ambientLight);
        
        // Hemisphere light for natural feel
        const hemi = new THREE.HemisphereLight(0xF5F0E8, 0x12101A, 0.3);
        hemi.position.set(0, 50, 0);
        this.scene.add(hemi);
        this.hemisphereLights.push(hemi);
        
        // Initialize fog
        this.fog = new THREE.FogExp2(0x07060B, 0.015);
        this.scene.fog = this.fog;
        
        // Create zone-specific lighting
        this.createRotundaLighting();
        this.createWingLighting();
        
        // Create god rays for rotunda
        this.createGodRays();
    }
    
    createRotundaLighting() {
        const group = new THREE.Group();
        group.name = 'rotunda-lighting';
        
        // Central spotlight (Turrell skyspace effect)
        const skyspot = new THREE.SpotLight(0xF5F0E8, 1.5, 60, Math.PI / 3, 0.8, 1);
        skyspot.position.set(0, 40, 0);
        skyspot.target.position.set(0, 0, 0);
        group.add(skyspot);
        group.add(skyspot.target);
        
        // Ring of subtle colored lights (one for each colony, blending)
        COLONY_ORDER.forEach((colony, i) => {
            const angle = (i / 7) * Math.PI * 2;
            const radius = DIMENSIONS.rotunda.radius * 0.7;
            const color = COLONY_DATA[colony].hex;
            
            const light = new THREE.PointLight(color, 0.3, 25, 2);
            light.position.set(
                Math.cos(angle) * radius,
                12,
                Math.sin(angle) * radius
            );
            group.add(light);
        });
        
        this.zoneLights.rotunda = group;
        this.scene.add(group);
    }
    
    createWingLighting() {
        COLONY_ORDER.forEach(colony => {
            const data = COLONY_DATA[colony];
            const profile = LIGHTING_PROFILES[colony];
            const group = new THREE.Group();
            group.name = `${colony}-lighting`;
            
            const angle = data.wingAngle;
            const rotundaRadius = DIMENSIONS.rotunda.radius;
            const wingLength = DIMENSIONS.wing.length;
            const wingWidth = DIMENSIONS.wing.width;
            const wingHeight = DIMENSIONS.wing.height;
            
            // Calculate wing center position
            const wingCenterX = Math.cos(angle) * (rotundaRadius + wingLength / 2);
            const wingCenterZ = Math.sin(angle) * (rotundaRadius + wingLength / 2);
            
            // === MONO-FREQUENCY EFFECT ===
            // Main fill light (simulates Turrell's colored rooms)
            const fillLight = new THREE.RectAreaLight(
                profile.primary,
                profile.intensity * 3,
                wingWidth * 0.8,
                wingLength * 0.9
            );
            fillLight.position.set(wingCenterX, wingHeight - 0.5, wingCenterZ);
            fillLight.lookAt(wingCenterX, 0, wingCenterZ);
            group.add(fillLight);
            
            // Secondary fill (softer, from walls)
            const leftWallLight = new THREE.PointLight(profile.secondary, 0.4, 20, 2);
            leftWallLight.position.set(
                Math.cos(angle) * (rotundaRadius + 10) + Math.cos(angle + Math.PI/2) * (wingWidth/2 - 1),
                3,
                Math.sin(angle) * (rotundaRadius + 10) + Math.sin(angle + Math.PI/2) * (wingWidth/2 - 1)
            );
            group.add(leftWallLight);
            
            const rightWallLight = new THREE.PointLight(profile.secondary, 0.4, 20, 2);
            rightWallLight.position.set(
                Math.cos(angle) * (rotundaRadius + 10) - Math.cos(angle + Math.PI/2) * (wingWidth/2 - 1),
                3,
                Math.sin(angle) * (rotundaRadius + 10) - Math.sin(angle + Math.PI/2) * (wingWidth/2 - 1)
            );
            group.add(rightWallLight);
            
            // End of wing accent light (draws visitors deeper)
            const endLight = new THREE.SpotLight(profile.primary, 1.0, 25, Math.PI/4, 0.6, 1);
            endLight.position.set(
                Math.cos(angle) * (rotundaRadius + wingLength - 3),
                wingHeight - 1,
                Math.sin(angle) * (rotundaRadius + wingLength - 3)
            );
            endLight.target.position.set(
                Math.cos(angle) * (rotundaRadius + wingLength + 5),
                1.7,
                Math.sin(angle) * (rotundaRadius + wingLength + 5)
            );
            group.add(endLight);
            group.add(endLight.target);
            
            // Subtle floor wash (adds depth)
            const floorWash = new THREE.PointLight(profile.ambient, 0.6, 15, 2);
            floorWash.position.set(wingCenterX, 0.3, wingCenterZ);
            group.add(floorWash);
            
            this.zoneLights[colony] = group;
            this.scene.add(group);
        });
    }
    
    createGodRays() {
        // Enhanced volumetric light effect with visible cones and particles
        const rayCount = 12; // More rays
        const group = new THREE.Group();
        group.name = 'god-rays';
        
        for (let i = 0; i < rayCount; i++) {
            const angle = (i / rayCount) * Math.PI * 2;
            const radius = 2 + Math.random() * 3;
            
            // Create a tall, thin cone for each ray - MUCH MORE VISIBLE
            const coneGeo = new THREE.ConeGeometry(2.0, 28, 12, 1, true);
            const coneMat = new THREE.MeshBasicMaterial({
                color: 0xF5F0E8,
                transparent: true,
                opacity: 0.12, // Increased from 0.03
                side: THREE.DoubleSide,
                blending: THREE.AdditiveBlending,
                depthWrite: false
            });
            
            const cone = new THREE.Mesh(coneGeo, coneMat);
            cone.position.set(Math.cos(angle) * radius, 28, Math.sin(angle) * radius);
            cone.rotation.x = Math.PI; // Point downward
            
            // Slight random tilt
            cone.rotation.z = (Math.random() - 0.5) * 0.2;
            cone.userData.baseAngle = angle;
            cone.userData.radius = radius;
            
            group.add(cone);
            
            // Inner brighter core
            const innerConeGeo = new THREE.ConeGeometry(0.5, 26, 8, 1, true);
            const innerConeMat = new THREE.MeshBasicMaterial({
                color: 0xFFFFFF,
                transparent: true,
                opacity: 0.08,
                side: THREE.DoubleSide,
                blending: THREE.AdditiveBlending,
                depthWrite: false
            });
            
            const innerCone = new THREE.Mesh(innerConeGeo, innerConeMat);
            innerCone.position.set(Math.cos(angle) * radius, 28, Math.sin(angle) * radius);
            innerCone.rotation.x = Math.PI;
            innerCone.rotation.z = cone.rotation.z;
            group.add(innerCone);
        }
        
        // Add dust particles within rays
        this.createRayParticles(group);
        
        this.godRays = group;
        this.scene.add(group);
    }
    
    createRayParticles(group) {
        // Floating dust particles that catch the light
        const particleCount = 300;
        const positions = new Float32Array(particleCount * 3);
        const colors = new Float32Array(particleCount * 3);
        const sizes = new Float32Array(particleCount);
        
        const warmWhite = new THREE.Color(0xF5F0E8);
        
        for (let i = 0; i < particleCount; i++) {
            // Distribute within a cylinder in the rotunda
            const angle = Math.random() * Math.PI * 2;
            const radius = Math.random() * 8;
            const height = Math.random() * 25 + 2;
            
            positions[i * 3] = Math.cos(angle) * radius;
            positions[i * 3 + 1] = height;
            positions[i * 3 + 2] = Math.sin(angle) * radius;
            
            // Slight color variation
            colors[i * 3] = warmWhite.r + (Math.random() - 0.5) * 0.1;
            colors[i * 3 + 1] = warmWhite.g + (Math.random() - 0.5) * 0.1;
            colors[i * 3 + 2] = warmWhite.b + (Math.random() - 0.5) * 0.05;
            
            sizes[i] = 0.02 + Math.random() * 0.03;
        }
        
        const geometry = new THREE.BufferGeometry();
        geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));
        geometry.setAttribute('color', new THREE.BufferAttribute(colors, 3));
        geometry.setAttribute('size', new THREE.BufferAttribute(sizes, 1));
        
        const material = new THREE.PointsMaterial({
            size: 0.08,
            vertexColors: true,
            transparent: true,
            opacity: 0.6,
            blending: THREE.AdditiveBlending,
            depthWrite: false,
            sizeAttenuation: true
        });
        
        this.rayParticles = new THREE.Points(geometry, material);
        this.rayParticles.name = 'ray-particles';
        group.add(this.rayParticles);
    }
    
    // ═══════════════════════════════════════════════════════════════════════
    // ZONE DETECTION & TRANSITIONS
    // ═══════════════════════════════════════════════════════════════════════
    
    detectZone() {
        const pos = this.camera.position;
        const distFromCenter = Math.sqrt(pos.x ** 2 + pos.z ** 2);
        const rotundaRadius = DIMENSIONS.rotunda.radius;
        const wingLength = DIMENSIONS.wing.length;
        
        // In rotunda?
        if (distFromCenter < rotundaRadius - 2) {
            return 'rotunda';
        }
        
        // In vestibule?
        if (pos.z < -rotundaRadius - 2) {
            return 'rotunda'; // Treat as rotunda lighting
        }
        
        // Find which wing we're in
        let closestWing = 'rotunda';
        let closestDist = Infinity;
        
        COLONY_ORDER.forEach(colony => {
            const data = COLONY_DATA[colony];
            const angle = data.wingAngle;
            
            // Wing center line
            const wingMidpoint = rotundaRadius + wingLength / 2;
            const wingX = Math.cos(angle) * wingMidpoint;
            const wingZ = Math.sin(angle) * wingMidpoint;
            
            const dx = pos.x - wingX;
            const dz = pos.z - wingZ;
            const dist = Math.sqrt(dx * dx + dz * dz);
            
            if (dist < closestDist && dist < wingLength / 2 + 5) {
                closestDist = dist;
                closestWing = colony;
            }
        });
        
        return closestWing;
    }
    
    setZone(zone) {
        if (zone === this.currentZone) return;
        
        this.currentZone = zone;
        this.targetProfile = LIGHTING_PROFILES[zone] || LIGHTING_PROFILES.rotunda;
        this.transitionProgress = 0;
        
        console.log(`🔦 Entering ${zone} zone (${this.targetProfile.mood})`);
    }
    
    // ═══════════════════════════════════════════════════════════════════════
    // UPDATE LOOP
    // ═══════════════════════════════════════════════════════════════════════
    
    update(deltaTime, time) {
        // Auto-detect zone based on camera position
        const detectedZone = this.detectZone();
        this.setZone(detectedZone);
        
        // Smooth transition
        if (this.transitionProgress < 1.0) {
            this.transitionProgress = Math.min(1.0, this.transitionProgress + deltaTime / this.transitionDuration);
            this.interpolateLighting();
        }
        
        // Animate god rays
        this.animateGodRays(time);
        
        // Animate zone lights
        this.animateZoneLights(time);
    }
    
    interpolateLighting() {
        const t = this.easeInOutCubic(this.transitionProgress);
        
        // Interpolate ambient
        const currentAmbient = new THREE.Color(this.currentProfile.ambient);
        const targetAmbient = new THREE.Color(this.targetProfile.ambient);
        currentAmbient.lerp(targetAmbient, t);
        this.ambientLight.color.copy(currentAmbient);
        
        // Interpolate fog
        const currentFogColor = new THREE.Color(this.currentProfile.ambient);
        const targetFogColor = new THREE.Color(this.targetProfile.ambient);
        currentFogColor.lerp(targetFogColor, t);
        this.fog.color.copy(currentFogColor);
        
        const currentDensity = this.currentProfile.fogDensity;
        const targetDensity = this.targetProfile.fogDensity;
        this.fog.density = currentDensity + (targetDensity - currentDensity) * t;
        
        // Update stored current profile for next transition
        if (this.transitionProgress >= 1.0) {
            this.currentProfile = { ...this.targetProfile };
        }
    }
    
    animateGodRays(time) {
        if (!this.godRays) return;
        
        this.godRays.children.forEach((child, i) => {
            if (child.isMesh) {
                // Gentle swaying
                const angle = child.userData.baseAngle;
                const radius = child.userData.radius;
                if (angle !== undefined && radius !== undefined) {
                    const newAngle = angle + Math.sin(time * 0.3 + i * 0.8) * 0.08;
                    const newRadius = radius + Math.sin(time * 0.5 + i * 1.2) * 0.3;
                    child.position.x = Math.cos(newAngle) * newRadius;
                    child.position.z = Math.sin(newAngle) * newRadius;
                }
                
                // Opacity variation (breathing light) - using higher base opacity
                const baseOpacity = child.material.opacity > 0.1 ? 0.12 : 0.08;
                child.material.opacity = baseOpacity + Math.sin(time * 0.7 + i * 0.5) * 0.03;
            }
        });
        
        // Animate dust particles
        if (this.rayParticles) {
            const positions = this.rayParticles.geometry.attributes.position.array;
            for (let i = 0; i < positions.length; i += 3) {
                // Gentle upward drift
                positions[i + 1] += 0.005;
                if (positions[i + 1] > 27) {
                    positions[i + 1] = 2;
                }
                // Subtle horizontal drift
                positions[i] += Math.sin(time + i) * 0.002;
                positions[i + 2] += Math.cos(time + i * 0.7) * 0.002;
            }
            this.rayParticles.geometry.attributes.position.needsUpdate = true;
        }
    }
    
    animateZoneLights(time) {
        // Subtle intensity breathing in current zone
        const zoneGroup = this.zoneLights[this.currentZone];
        if (!zoneGroup) return;
        
        zoneGroup.traverse(child => {
            if (child.isLight) {
                const baseIntensity = child.userData.baseIntensity || child.intensity;
                if (!child.userData.baseIntensity) {
                    child.userData.baseIntensity = child.intensity;
                }
                // Subtle breathing (±5%)
                child.intensity = baseIntensity * (1 + Math.sin(time * 0.5) * 0.05);
            }
        });
    }
    
    // ═══════════════════════════════════════════════════════════════════════
    // UTILITIES
    // ═══════════════════════════════════════════════════════════════════════
    
    easeInOutCubic(t) {
        return t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2;
    }
    
    // Get current zone for external use
    getCurrentZone() {
        return this.currentZone;
    }
    
    // Get mood for audio integration
    getCurrentMood() {
        return this.targetProfile.mood;
    }
    
    // Manual override for special effects
    flashColor(color, duration = 0.5) {
        const originalAmbient = this.ambientLight.color.clone();
        this.ambientLight.color.set(color);
        this.ambientLight.intensity = 1.5;
        
        setTimeout(() => {
            this.ambientLight.color.copy(originalAmbient);
            this.ambientLight.intensity = 0.15;
        }, duration * 1000);
    }
}

// ═══════════════════════════════════════════════════════════════════════════
// ARTWORK SPOTLIGHT HELPER
// ═══════════════════════════════════════════════════════════════════════════

export function createArtworkSpotlight(position, color, intensity = 1.0) {
    const group = new THREE.Group();
    
    // Main spotlight on artwork
    const spot = new THREE.SpotLight(color, intensity, 15, Math.PI / 6, 0.7, 1);
    spot.position.set(position.x, position.y + 6, position.z);
    spot.target.position.copy(position);
    group.add(spot);
    group.add(spot.target);
    
    // Soft fill from below
    const fill = new THREE.PointLight(color, intensity * 0.2, 8, 2);
    fill.position.set(position.x, position.y + 0.5, position.z);
    group.add(fill);
    
    return group;
}

// ═══════════════════════════════════════════════════════════════════════════
// EXPORTS
// ═══════════════════════════════════════════════════════════════════════════

export { LIGHTING_PROFILES };
