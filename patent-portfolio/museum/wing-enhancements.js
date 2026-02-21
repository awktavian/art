/**
 * Wing Visual Enhancements
 * ========================
 *
 * Each wing has a unique architectural identity:
 *
 * - CRYSTAL: Faceted ceiling, obsidian walls, UV-blue caustics
 * - FORGE: Exposed steel beams, copper conduits, amber glow from below
 * - SPARK: Curved walls, responsive emissive panels, light-reactive floor
 * - FLOW: Organic curves, water-worn textures, living wall, caustic shader
 * - NEXUS: Network channels in walls, grid floor, constellation ceiling
 * - BEACON: Tallest ceiling, lighthouse element, gilded insets, sweep light
 * - GROVE: Branching columns, canopy ceiling, bioluminescent vines
 *
 * h(x) ≥ 0 always
 */

import * as THREE from 'three';
import { COLONY_DATA, COLONY_ORDER, DIMENSIONS } from './architecture.js';

export class WingEnhancementManager {
    constructor(scene) {
        this.scene = scene;
        this.enhancements = new Map();
        this.time = 0;
    }

    init() {
        COLONY_ORDER.forEach(colony => {
            const data = COLONY_DATA[colony];
            const enhancement = this._createWingEnhancement(colony, data);
            if (enhancement) {
                this.enhancements.set(colony, enhancement);
                this.scene.add(enhancement.group);
            }
        });
    }

    _createWingEnhancement(colony, data) {
        const angle = data.wingAngle;
        const wingLength = DIMENSIONS.wing.length;
        const corridorWidth = DIMENSIONS.wing.width;
        const rotR = DIMENSIONS.rotunda.radius;
        const cos = Math.cos(angle), sin = Math.sin(angle);
        const group = new THREE.Group();
        group.name = `wing-enhancement-${colony}`;

        const vestibuleDepth = DIMENSIONS.wing.vestibuleDepth ?? 6;
        const galleryDepth = DIMENSIONS.gallery.depth;
        const galleryCenterDist = rotR + wingLength + vestibuleDepth + galleryDepth / 2;
        const galleryCX = cos * galleryCenterDist;
        const galleryCZ = sin * galleryCenterDist;
        const galleryH = DIMENSIONS.gallery.height;
        const galleryW = DIMENSIONS.gallery.width;

        switch (colony) {
            case 'crystal': {
                // Faceted crystalline ceiling panels
                const facetMat = new THREE.MeshPhysicalMaterial({
                    color: 0xCCEEFF, metalness: 0, roughness: 0,
                    transmission: 0.6, thickness: 0.8, ior: 2.0,
                    clearcoat: 1.0, iridescence: 0.3, iridescenceIOR: 1.3
                });
                for (let i = 0; i < 12; i++) {
                    const size = 2 + Math.random() * 3;
                    const geo = new THREE.OctahedronGeometry(size, 0);
                    const facet = new THREE.Mesh(geo, facetMat.clone());
                    const ox = (Math.random() - 0.5) * galleryW * 0.7;
                    const oz = (Math.random() - 0.5) * galleryDepth * 0.6;
                    facet.position.set(
                        galleryCX - sin * ox + cos * oz,
                        galleryH - 1.5 - Math.random() * 2,
                        galleryCZ + cos * ox + sin * oz
                    );
                    facet.rotation.set(Math.random() * Math.PI, Math.random() * Math.PI, 0);
                    facet.scale.set(1, 0.3, 1);
                    facet.name = `crystal-ceiling-facet-${i}`;
                    group.add(facet);
                }

                // Obsidian wall accents (dark reflective panels on gallery walls)
                const obsidianMat = new THREE.MeshPhysicalMaterial({
                    color: 0x0A0A12, metalness: 0.4, roughness: 0.05,
                    clearcoat: 1.0, clearcoatRoughness: 0.02
                });
                for (let side = -1; side <= 1; side += 2) {
                    const panel = new THREE.Mesh(
                        new THREE.PlaneGeometry(galleryDepth * 0.6, galleryH * 0.7),
                        obsidianMat
                    );
                    panel.position.set(
                        galleryCX - sin * (galleryW / 2 - 0.3) * side,
                        galleryH * 0.45,
                        galleryCZ + cos * (galleryW / 2 - 0.3) * side
                    );
                    panel.rotation.y = angle + (side > 0 ? -Math.PI / 2 : Math.PI / 2);
                    group.add(panel);
                }

                // Dark reflective floor overlay
                const darkFloor = new THREE.Mesh(
                    new THREE.PlaneGeometry(galleryW * 0.8, galleryDepth * 0.8),
                    new THREE.MeshPhysicalMaterial({
                        color: 0x050510, metalness: 0.5, roughness: 0.02,
                        clearcoat: 1.0, clearcoatRoughness: 0.01,
                        envMapIntensity: 1.5, side: THREE.DoubleSide
                    })
                );
                darkFloor.rotation.x = -Math.PI / 2;
                darkFloor.rotation.z = angle;
                darkFloor.position.set(galleryCX, 0.015, galleryCZ);
                group.add(darkFloor);

                return { group, type: 'crystal' };
            }

            case 'forge': {
                // Exposed steel beams (I-beam cross section)
                const beamMat = new THREE.MeshStandardMaterial({
                    color: 0x4A4A4A, metalness: 0.9, roughness: 0.4
                });
                for (let i = 0; i < 5; i++) {
                    const beamGeo = new THREE.BoxGeometry(galleryW + 2, 0.3, 0.15);
                    const beam = new THREE.Mesh(beamGeo, beamMat);
                    const oz = (i - 2) * (galleryDepth / 5);
                    beam.position.set(
                        galleryCX + cos * oz,
                        galleryH - 0.5,
                        galleryCZ + sin * oz
                    );
                    beam.rotation.y = angle + Math.PI / 2;
                    group.add(beam);
                }

                // Copper conduit runs along walls
                const copperMat = new THREE.MeshPhysicalMaterial({
                    color: 0xB87333, metalness: 0.95, roughness: 0.2
                });
                for (let side = -1; side <= 1; side += 2) {
                    const conduit = new THREE.Mesh(
                        new THREE.CylinderGeometry(0.04, 0.04, galleryDepth * 0.8, 8),
                        copperMat
                    );
                    conduit.position.set(
                        galleryCX - sin * (galleryW / 2 - 0.5) * side,
                        galleryH * 0.7,
                        galleryCZ + cos * (galleryW / 2 - 0.5) * side
                    );
                    conduit.rotation.x = Math.PI / 2;
                    conduit.rotation.z = angle;
                    group.add(conduit);
                }

                // Brushed steel floor inlays
                const steelFloor = new THREE.Mesh(
                    new THREE.PlaneGeometry(galleryW * 0.3, galleryDepth * 0.8),
                    new THREE.MeshPhysicalMaterial({
                        color: 0x8A8A8A, metalness: 0.95, roughness: 0.25,
                        clearcoat: 0.3, side: THREE.DoubleSide
                    })
                );
                steelFloor.rotation.x = -Math.PI / 2;
                steelFloor.rotation.z = angle;
                steelFloor.position.set(galleryCX, 0.015, galleryCZ);
                group.add(steelFloor);

                // Forge glow from below (warm amber uplight)
                const forgeGlow = new THREE.PointLight(0xFF6600, 0.3, 15, 2);
                forgeGlow.position.set(galleryCX, 0.1, galleryCZ);
                forgeGlow.name = 'forge-underglow';
                group.add(forgeGlow);

                return { group, type: 'forge', forgeGlow };
            }

            case 'spark': {
                // Responsive emissive ceiling panels
                const panelCount = 8;
                const panels = [];
                for (let i = 0; i < panelCount; i++) {
                    const panelMat = new THREE.MeshStandardMaterial({
                        color: 0x111111, emissive: 0xFF6B35,
                        emissiveIntensity: 0.05, roughness: 0.3
                    });
                    const panelGeo = new THREE.PlaneGeometry(
                        galleryW / 3, galleryDepth / (panelCount / 2)
                    );
                    const panel = new THREE.Mesh(panelGeo, panelMat);
                    const col = i % 2;
                    const row = Math.floor(i / 2);
                    const ox = (col - 0.5) * galleryW * 0.35;
                    const oz = (row - (panelCount / 4 - 0.5)) * (galleryDepth / (panelCount / 2));
                    panel.position.set(
                        galleryCX - sin * ox + cos * oz,
                        galleryH - 0.1,
                        galleryCZ + cos * ox + sin * oz
                    );
                    panel.rotation.x = Math.PI / 2;
                    panel.rotation.z = angle;
                    panel.name = `spark-panel-${i}`;
                    group.add(panel);
                    panels.push(panel);
                }

                // Light-reactive floor area (emissive when visitor approaches)
                const reactiveFloor = new THREE.Mesh(
                    new THREE.CircleGeometry(6, 32),
                    new THREE.MeshStandardMaterial({
                        color: 0x0A0A0A, emissive: 0xFF6B35,
                        emissiveIntensity: 0.0, roughness: 0.3,
                        side: THREE.DoubleSide
                    })
                );
                reactiveFloor.rotation.x = -Math.PI / 2;
                reactiveFloor.position.set(galleryCX, 0.015, galleryCZ);
                reactiveFloor.name = 'spark-reactive-floor';
                group.add(reactiveFloor);

                return { group, type: 'spark', panels, reactiveFloor };
            }

            case 'flow': {
                // Water-worn stone texture (organic shape floor accent)
                const stoneMat = new THREE.MeshStandardMaterial({
                    color: 0x4A3828, roughness: 0.85, metalness: 0.0
                });
                for (let i = 0; i < 6; i++) {
                    const stone = new THREE.Mesh(
                        new THREE.SphereGeometry(1.5 + Math.random(), 8, 6),
                        stoneMat
                    );
                    const ox = (Math.random() - 0.5) * galleryW * 0.6;
                    const oz = (Math.random() - 0.5) * galleryDepth * 0.5;
                    stone.position.set(
                        galleryCX - sin * ox + cos * oz,
                        -0.8,
                        galleryCZ + cos * ox + sin * oz
                    );
                    stone.scale.set(1, 0.3, 1);
                    group.add(stone);
                }

                // Living wall section (green emissive plane)
                const livingWallMat = new THREE.MeshStandardMaterial({
                    color: 0x1A3A1E, emissive: 0x2A5A2E, emissiveIntensity: 0.08,
                    roughness: 0.95, metalness: 0.0
                });
                const livingWall = new THREE.Mesh(
                    new THREE.PlaneGeometry(galleryDepth * 0.5, galleryH * 0.6),
                    livingWallMat
                );
                livingWall.position.set(
                    galleryCX - sin * (galleryW / 2 - 0.2),
                    galleryH * 0.4,
                    galleryCZ + cos * (galleryW / 2 - 0.2)
                );
                livingWall.rotation.y = angle + Math.PI / 2;
                livingWall.name = 'flow-living-wall';
                group.add(livingWall);

                // Warm wood floor accent
                const woodFloor = new THREE.Mesh(
                    new THREE.PlaneGeometry(galleryW * 0.7, galleryDepth * 0.7),
                    new THREE.MeshStandardMaterial({
                        color: 0x8B5E3C, roughness: 0.7, metalness: 0.0,
                        side: THREE.DoubleSide
                    })
                );
                woodFloor.rotation.x = -Math.PI / 2;
                woodFloor.rotation.z = angle;
                woodFloor.position.set(galleryCX, 0.014, galleryCZ);
                group.add(woodFloor);

                // Water caustic projection light
                const causticLight = new THREE.SpotLight(0x4ECDC4, 0.2, 20, Math.PI / 4, 0.8, 2);
                causticLight.position.set(galleryCX, galleryH - 1, galleryCZ);
                causticLight.target.position.set(galleryCX, 0, galleryCZ);
                causticLight.name = 'flow-caustic-light';
                group.add(causticLight.target);
                group.add(causticLight);

                return { group, type: 'flow', livingWall, causticLight };
            }

            case 'nexus': {
                // Network channel lines in walls (illuminated grooves)
                const channelMat = new THREE.MeshBasicMaterial({
                    color: 0x9B7EBD, transparent: true, opacity: 0.3
                });
                for (let side = -1; side <= 1; side += 2) {
                    for (let i = 0; i < 8; i++) {
                        const channel = new THREE.Mesh(
                            new THREE.BoxGeometry(0.02, galleryH * 0.5, 0.02),
                            channelMat.clone()
                        );
                        const oz = (i - 3.5) * (galleryDepth / 8);
                        channel.position.set(
                            galleryCX - sin * (galleryW / 2 - 0.1) * side + cos * oz,
                            galleryH * 0.35,
                            galleryCZ + cos * (galleryW / 2 - 0.1) * side + sin * oz
                        );
                        channel.name = `nexus-channel-${side}-${i}`;
                        group.add(channel);
                    }
                }

                // Grid floor pattern
                const gridMat = new THREE.MeshBasicMaterial({
                    color: 0x9B7EBD, transparent: true, opacity: 0.08,
                    side: THREE.DoubleSide
                });
                const gridGeo = new THREE.PlaneGeometry(
                    galleryW * 0.8, galleryDepth * 0.8, 12, 16
                );
                const gridFloor = new THREE.Mesh(gridGeo, new THREE.MeshBasicMaterial({
                    color: 0x9B7EBD, wireframe: true, transparent: true, opacity: 0.12,
                    side: THREE.DoubleSide
                }));
                gridFloor.rotation.x = -Math.PI / 2;
                gridFloor.rotation.z = angle;
                gridFloor.position.set(galleryCX, 0.015, galleryCZ);
                gridFloor.name = 'nexus-grid-floor';
                group.add(gridFloor);

                // Constellation ceiling (small point lights as network nodes)
                for (let i = 0; i < 20; i++) {
                    const nodeLight = new THREE.PointLight(0x9B7EBD, 0.05, 4, 2);
                    const ox = (Math.random() - 0.5) * galleryW * 0.7;
                    const oz = (Math.random() - 0.5) * galleryDepth * 0.6;
                    nodeLight.position.set(
                        galleryCX - sin * ox + cos * oz,
                        galleryH - 0.3,
                        galleryCZ + cos * ox + sin * oz
                    );
                    nodeLight.name = `nexus-ceiling-node-${i}`;
                    group.add(nodeLight);
                }

                return { group, type: 'nexus' };
            }

            case 'beacon': {
                // Lighthouse vertical element at gallery end
                const farDist = rotR + wingLength + vestibuleDepth + galleryDepth - 3;
                const beaconX = cos * farDist;
                const beaconZ = sin * farDist;

                const towerGeo = new THREE.CylinderGeometry(0.4, 0.6, galleryH * 0.8, 8);
                const towerMat = new THREE.MeshStandardMaterial({
                    color: 0x8A7A5A, metalness: 0.3, roughness: 0.5
                });
                const tower = new THREE.Mesh(towerGeo, towerMat);
                tower.position.set(beaconX, galleryH * 0.4, beaconZ);
                tower.name = 'beacon-lighthouse';
                group.add(tower);

                // Beacon lamp at top
                const lampGeo = new THREE.SphereGeometry(0.3, 16, 16);
                const lampMat = new THREE.MeshBasicMaterial({
                    color: 0xF59E0B, transparent: true, opacity: 0.9
                });
                const lamp = new THREE.Mesh(lampGeo, lampMat);
                lamp.position.set(beaconX, galleryH * 0.82, beaconZ);
                lamp.name = 'beacon-lamp';
                group.add(lamp);

                // Rotating beacon sweep light
                const sweepLight = new THREE.SpotLight(0xF59E0B, 0.5, 30, Math.PI / 16, 0.3, 1);
                sweepLight.position.set(beaconX, galleryH * 0.8, beaconZ);
                sweepLight.target.position.set(beaconX + 10, 0, beaconZ);
                sweepLight.name = 'beacon-sweep';
                group.add(sweepLight.target);
                group.add(sweepLight);

                // Gilded wall insets
                const gildMat = new THREE.MeshPhysicalMaterial({
                    color: 0xD4AF37, metalness: 0.9, roughness: 0.15,
                    clearcoat: 0.5
                });
                for (let side = -1; side <= 1; side += 2) {
                    for (let i = 0; i < 3; i++) {
                        const inset = new THREE.Mesh(
                            new THREE.PlaneGeometry(2, 3),
                            gildMat
                        );
                        const oz = (i - 1) * (galleryDepth / 4);
                        inset.position.set(
                            galleryCX - sin * (galleryW / 2 - 0.2) * side + cos * oz,
                            galleryH * 0.4,
                            galleryCZ + cos * (galleryW / 2 - 0.2) * side + sin * oz
                        );
                        inset.rotation.y = angle + (side > 0 ? -Math.PI / 2 : Math.PI / 2);
                        group.add(inset);
                    }
                }

                // Amber stone floor accent
                const amberFloor = new THREE.Mesh(
                    new THREE.PlaneGeometry(galleryW * 0.6, galleryDepth * 0.8),
                    new THREE.MeshStandardMaterial({
                        color: 0x8B6914, roughness: 0.6, metalness: 0.1,
                        side: THREE.DoubleSide
                    })
                );
                amberFloor.rotation.x = -Math.PI / 2;
                amberFloor.rotation.z = angle;
                amberFloor.position.set(galleryCX, 0.014, galleryCZ);
                group.add(amberFloor);

                return { group, type: 'beacon', sweepLight, lamp };
            }

            case 'grove': {
                // Branching columns (tree-inspired)
                for (let i = 0; i < 4; i++) {
                    const trunkGeo = new THREE.CylinderGeometry(0.15, 0.25, galleryH * 0.6, 6);
                    const trunkMat = new THREE.MeshStandardMaterial({
                        color: 0x3A2A1A, roughness: 0.9, metalness: 0
                    });
                    const trunk = new THREE.Mesh(trunkGeo, trunkMat);
                    const ox = ((i % 2) - 0.5) * galleryW * 0.4;
                    const oz = (Math.floor(i / 2) - 0.5) * galleryDepth * 0.3;
                    trunk.position.set(
                        galleryCX - sin * ox + cos * oz,
                        galleryH * 0.3,
                        galleryCZ + cos * ox + sin * oz
                    );
                    group.add(trunk);

                    // Branches spreading at top
                    for (let b = 0; b < 3; b++) {
                        const branchAngle = (b / 3) * Math.PI * 2;
                        const branchGeo = new THREE.CylinderGeometry(0.03, 0.08, 3, 4);
                        const branch = new THREE.Mesh(branchGeo, trunkMat);
                        branch.position.set(
                            trunk.position.x + Math.cos(branchAngle) * 1,
                            galleryH * 0.65,
                            trunk.position.z + Math.sin(branchAngle) * 1
                        );
                        branch.rotation.z = Math.cos(branchAngle) * 0.6;
                        branch.rotation.x = Math.sin(branchAngle) * 0.6;
                        group.add(branch);
                    }
                }

                // Bioluminescent vine lines (static geometry, animated via group transform)
                const vineMat = new THREE.MeshBasicMaterial({
                    color: 0x7EB77F, transparent: true, opacity: 0.3
                });
                for (let v = 0; v < 8; v++) {
                    const vinePoints = [];
                    const startX = (Math.random() - 0.5) * galleryW * 0.6;
                    const startZ = (Math.random() - 0.5) * galleryDepth * 0.5;
                    for (let p = 0; p < 10; p++) {
                        vinePoints.push(new THREE.Vector3(
                            galleryCX - sin * startX + Math.sin(p * 0.7 + v) * 0.3,
                            0.5 + p * (galleryH / 12),
                            galleryCZ + cos * startZ + Math.cos(p * 0.5 + v) * 0.3
                        ));
                    }
                    const vineGeo = new THREE.BufferGeometry().setFromPoints(vinePoints);
                    const vine = new THREE.Line(vineGeo, vineMat.clone());
                    vine.name = `grove-vine-${v}`;
                    vine.userData._baseX = vine.position.x;
                    group.add(vine);
                }

                // Moss-joint stone floor
                const mossFloor = new THREE.Mesh(
                    new THREE.PlaneGeometry(galleryW * 0.7, galleryDepth * 0.7, 8, 8),
                    new THREE.MeshStandardMaterial({
                        color: 0x4A5A3A, roughness: 0.95, metalness: 0,
                        side: THREE.DoubleSide
                    })
                );
                mossFloor.rotation.x = -Math.PI / 2;
                mossFloor.rotation.z = angle;
                mossFloor.position.set(galleryCX, 0.014, galleryCZ);
                group.add(mossFloor);

                // Moss joint lines
                const mossLineMat = new THREE.MeshBasicMaterial({
                    color: 0x6A8A5A, transparent: true, opacity: 0.2, side: THREE.DoubleSide
                });
                for (let g = 0; g < 6; g++) {
                    const mossLine = new THREE.Mesh(
                        new THREE.PlaneGeometry(galleryW * 0.6, 0.04),
                        mossLineMat
                    );
                    const oz = (g - 2.5) * (galleryDepth / 6);
                    mossLine.rotation.x = -Math.PI / 2;
                    mossLine.rotation.z = angle;
                    mossLine.position.set(
                        galleryCX + cos * oz,
                        0.016,
                        galleryCZ + sin * oz
                    );
                    group.add(mossLine);
                }

                return { group, type: 'grove' };
            }
        }
        return null;
    }

    update(delta, cameraPosition) {
        this.time += delta;
        const t = this.time;

        this.enhancements.forEach((enhancement, colony) => {
            switch (enhancement.type) {
                case 'spark': {
                    // Responsive ceiling panels shift with time
                    if (enhancement.panels) {
                        enhancement.panels.forEach((panel, i) => {
                            if (panel.material) {
                                const phase = Math.sin(t * 0.8 + i * 0.5) * 0.5 + 0.5;
                                panel.material.emissiveIntensity = 0.02 + phase * 0.08;
                            }
                        });
                    }
                    // Reactive floor responds to camera proximity
                    if (enhancement.reactiveFloor && cameraPosition) {
                        const dist = cameraPosition.distanceTo(enhancement.reactiveFloor.position);
                        const factor = Math.max(0, 1 - dist / 15);
                        enhancement.reactiveFloor.material.emissiveIntensity = factor * 0.15;
                    }
                    break;
                }
                case 'forge': {
                    // Forge underglow flickers
                    if (enhancement.forgeGlow) {
                        enhancement.forgeGlow.intensity = 0.2 + Math.sin(t * 3) * 0.05 + Math.sin(t * 7.3) * 0.03;
                    }
                    break;
                }
                case 'flow': {
                    // Living wall subtle emissive pulse
                    if (enhancement.livingWall?.material) {
                        enhancement.livingWall.material.emissiveIntensity = 0.06 + Math.sin(t * 0.3) * 0.03;
                    }
                    // Caustic light slow rotation
                    if (enhancement.causticLight?.target) {
                        const base = enhancement.causticLight.position;
                        const offset = 5;
                        enhancement.causticLight.target.position.set(
                            base.x + Math.cos(t * 0.2) * offset,
                            0,
                            base.z + Math.sin(t * 0.2) * offset
                        );
                    }
                    break;
                }
                case 'nexus': {
                    // Network channel pulse
                    enhancement.group.traverse(child => {
                        if (child.name.startsWith('nexus-channel-') && child.material) {
                            const idx = parseInt(child.name.split('-').pop());
                            child.material.opacity = 0.2 + Math.sin(t * 2 + idx * 0.8) * 0.15;
                        }
                        if (child.name.startsWith('nexus-ceiling-node-')) {
                            const idx = parseInt(child.name.split('-').pop());
                            child.intensity = 0.03 + Math.sin(t * 1.5 + idx * 0.5) * 0.03;
                        }
                    });
                    // Grid floor pulse
                    const grid = enhancement.group.getObjectByName('nexus-grid-floor');
                    if (grid?.material) {
                        grid.material.opacity = 0.08 + Math.sin(t * 0.5) * 0.04;
                    }
                    break;
                }
                case 'beacon': {
                    // Rotating beacon sweep
                    if (enhancement.sweepLight?.target) {
                        const base = enhancement.sweepLight.position;
                        const sweepRadius = 15;
                        const sweepAngle = t * 0.3;
                        enhancement.sweepLight.target.position.set(
                            base.x + Math.cos(sweepAngle) * sweepRadius,
                            0,
                            base.z + Math.sin(sweepAngle) * sweepRadius
                        );
                    }
                    // Lamp glow pulse
                    if (enhancement.lamp?.material) {
                        enhancement.lamp.material.opacity = 0.7 + Math.sin(t * 1.2) * 0.2;
                    }
                    break;
                }
                case 'grove': {
                    // Vine sway via group transform
                    for (let v = 0; v < 8; v++) {
                        const vine = enhancement.group.getObjectByName(`grove-vine-${v}`);
                        if (vine) {
                            const baseX = vine.userData._baseX ?? 0;
                            vine.position.x = baseX + Math.sin(t * 0.5 + v * 1.2) * 0.08;
                        }
                    }
                    break;
                }
            }
        });
    }

    dispose() {
        this.enhancements.forEach(e => {
            e.group.traverse(obj => {
                if (obj.geometry) obj.geometry.dispose();
                if (obj.material) obj.material.dispose();
            });
            e.group.parent?.remove(e.group);
        });
        this.enhancements.clear();
    }
}

export default WingEnhancementManager;
