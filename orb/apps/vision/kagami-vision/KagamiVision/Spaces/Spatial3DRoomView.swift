//
// Spatial3DRoomView.swift — 3D Room Visualization with Depth Layers
//
// Colony: Beacon (e₅) — Planning
//
// Features:
//   - 3D miniature home model floating in space
//   - Room entities with depth-based layering
//   - Gaze-based room selection
//   - Light visualization with volumetric glow
//   - Real-world anchored placement
//   - Occupancy indicators with particle effects
//
// Design Philosophy:
//   The home becomes a tangible object you can examine,
//   rotate, and interact with using natural gestures.
//   Each room is a distinct 3D entity at a unique depth,
//   creating a true spatial experience.
//
// Created: December 31, 2025
// 鏡

import SwiftUI
import RealityKit

/// Immersive 3D room visualization with depth layers
struct Spatial3DRoomView: View {
    @EnvironmentObject var appModel: AppModel
    @StateObject private var anchorService = SpatialAnchorService()
    @StateObject private var audioService = SpatialAudioService()

    // P1 FIX: Breadcrumb navigation state
    @StateObject private var breadcrumbState = BreadcrumbNavigationState()

    @State private var rooms: [RoomModel] = []
    @State private var selectedRoom: String?
    @State private var isLoading = true
    @State private var modelScale: Float = 0.1  // 10cm = 1 meter
    @State private var modelRotation: Float = 0

    // Floor positioning (depth layers)
    private let floorPositions: [String: Float] = [
        "Lower Level": -0.15,
        "Main Floor": 0.0,
        "Upper Floor": 0.15
    ]

    var body: some View {
        RealityView { content in
            // Create the house model container
            let houseContainer = Entity()
            houseContainer.name = "house-model"
            houseContainer.position = SIMD3<Float>(0, 1.2, -1.5)  // Personal zone distance

            // Add floor planes
            for (floor, yOffset) in floorPositions {
                let floorPlane = createFloorPlane(name: floor, yOffset: yOffset)
                houseContainer.addChild(floorPlane)
            }

            content.add(houseContainer)

            // Add ambient lighting
            let light = createAmbientLighting()
            content.add(light)

        } update: { content in
            guard let house = content.entities.first(where: { $0.name == "house-model" }) else { return }

            // Update rotation
            house.orientation = simd_quatf(angle: modelRotation, axis: SIMD3<Float>(0, 1, 0))

            // Update room entities
            updateRoomEntities(in: house)
        }
        .gesture(
            // Rotation gesture
            DragGesture()
                .onChanged { value in
                    modelRotation += Float(value.translation.width) * 0.01
                }
        )
        .gesture(
            // Selection gesture
            SpatialTapGesture()
                .targetedToAnyEntity()
                .onEnded { value in
                    handleRoomTap(value.entity)
                }
        )
        .task {
            await loadRooms()
            await anchorService.start()
            // P1 FIX: Initialize breadcrumb with root path
            breadcrumbState.setPath(["Rooms"])
        }
        // P1 FIX: Add spatial breadcrumb indicator
        .spatialBreadcrumb(path: breadcrumbState.currentPath, isVisible: true)
    }

    // MARK: - Entity Creation

    private func createFloorPlane(name: String, yOffset: Float) -> Entity {
        let floor = Entity()
        floor.name = "floor-\(name)"
        floor.position = SIMD3<Float>(0, yOffset, 0)

        // Semi-transparent floor plane
        let mesh = MeshResource.generatePlane(width: 0.4, depth: 0.3)
        var material = SimpleMaterial(color: .white.withAlphaComponent(0.1), isMetallic: false)
        material.roughness = .float(1.0)

        let modelComponent = ModelComponent(mesh: mesh, materials: [material])
        floor.components.set(modelComponent)

        // Add floor label
        let label = createTextEntity(text: name, size: 0.015)
        label.position = SIMD3<Float>(-0.15, 0.01, 0.12)
        floor.addChild(label)

        return floor
    }

    private func createRoomEntity(room: RoomModel) -> Entity {
        let roomEntity = Entity()
        roomEntity.name = "room-\(room.id)"

        // Room position based on a simplified layout
        let position = calculateRoomPosition(room: room)
        roomEntity.position = position

        // Room cube representation
        let size: Float = 0.04  // 4cm cube = 4m room
        let mesh = MeshResource.generateBox(size: size, cornerRadius: 0.002)

        // Color based on light state and occupancy
        let color = roomColor(for: room)
        var material = PhysicallyBasedMaterial()
        material.baseColor = .init(tint: .init(color))
        material.emissiveColor = .init(color: .init(color.opacity(Double(room.avgLightLevel) / 200)))
        material.emissiveIntensity = Float(room.avgLightLevel) / 100
        material.roughness = 0.3
        material.metallic = 0.0

        let modelComponent = ModelComponent(mesh: mesh, materials: [material])
        roomEntity.components.set(modelComponent)

        // Make interactive
        roomEntity.components.set(InputTargetComponent())
        roomEntity.components.set(CollisionComponent(shapes: [.generateBox(size: SIMD3<Float>(repeating: size * 1.2))]))
        roomEntity.components.set(HoverEffectComponent())

        // Add room label
        let label = createTextEntity(text: room.name, size: 0.008)
        label.position = SIMD3<Float>(0, size / 2 + 0.01, 0)
        roomEntity.addChild(label)

        // Add occupancy indicator
        if room.occupied {
            let indicator = createOccupancyIndicator()
            indicator.position = SIMD3<Float>(0, size / 2 + 0.02, 0)
            roomEntity.addChild(indicator)
        }

        // Add light glow if lights are on
        if room.avgLightLevel > 0 {
            let glow = createLightGlow(brightness: Float(room.avgLightLevel) / 100)
            roomEntity.addChild(glow)
        }

        // Accessibility using SpatialEntityAccessibility pattern
        let spatialAccessibility = SpatialEntityAccessibility(
            label: "\(room.name), \(room.floor)",
            hint: "Look at and pinch to control room devices. Lights: \(room.lightState)",
            traits: .button,
            customActions: ["Turn lights on", "Turn lights off", "Toggle shades"]
        )

        var accessibilityComponent = AccessibilityComponent()
        accessibilityComponent.label = LocalizedStringResource(stringLiteral: spatialAccessibility.label)
        accessibilityComponent.value = LocalizedStringResource(stringLiteral: room.occupied ? "occupied, lights \(room.lightState)" : "lights \(room.lightState)")
        accessibilityComponent.isAccessibilityElement = true
        accessibilityComponent.traits = [.button]
        roomEntity.components.set(accessibilityComponent)

        return roomEntity
    }

    private func createTextEntity(text: String, size: Float) -> Entity {
        let entity = Entity()

        // Note: In production, use MeshResource.generateText()
        // For now, we'll create a simple plane with the text concept
        let mesh = MeshResource.generatePlane(width: size * Float(text.count) * 0.6, height: size)
        var material = SimpleMaterial(color: .white.withAlphaComponent(0.8), isMetallic: false)
        material.roughness = .float(1.0)

        let modelComponent = ModelComponent(mesh: mesh, materials: [material])
        entity.components.set(modelComponent)

        return entity
    }

    private func createOccupancyIndicator() -> Entity {
        let entity = Entity()
        entity.name = "occupancy-indicator"

        // Small glowing sphere
        let mesh = MeshResource.generateSphere(radius: 0.005)
        var material = PhysicallyBasedMaterial()
        material.baseColor = .init(tint: .init(.grove))
        material.emissiveColor = .init(color: .init(.grove))
        material.emissiveIntensity = 1.0

        let modelComponent = ModelComponent(mesh: mesh, materials: [material])
        entity.components.set(modelComponent)

        // Accessibility for occupancy indicator
        let spatialAccessibility = SpatialEntityAccessibility(
            label: "Occupancy indicator",
            hint: "Room is currently occupied",
            traits: .staticText
        )
        var accessibilityComponent = AccessibilityComponent()
        accessibilityComponent.label = LocalizedStringResource(stringLiteral: spatialAccessibility.label)
        accessibilityComponent.isAccessibilityElement = true
        entity.components.set(accessibilityComponent)

        return entity
    }

    private func createLightGlow(brightness: Float) -> Entity {
        let entity = Entity()
        entity.name = "light-glow"

        // Volumetric glow using particles
        var particles = ParticleEmitterComponent()
        particles.emitterShape = .point
        particles.mainEmitter.birthRate = 5
        particles.mainEmitter.birthRateVariation = 2
        particles.mainEmitter.lifeSpan = 2
        particles.speed = 0.001
        particles.mainEmitter.color = .constant(.single(.init(.beacon.opacity(Double(brightness)))))
        particles.mainEmitter.size = 0.01 * brightness

        entity.components.set(particles)

        return entity
    }

    private func createAmbientLighting() -> Entity {
        let light = Entity()

        // Use directional light for visionOS 1.0 compatibility
        // PointLightComponent requires visionOS 2.0
        // Ambient lighting via environment settings instead
        light.position = SIMD3<Float>(0, 2, -1)

        return light
    }

    // MARK: - Position Calculation

    private func calculateRoomPosition(room: RoomModel) -> SIMD3<Float> {
        // Get floor Y position
        let floorY = floorPositions[room.floor] ?? 0

        // Simple grid layout for rooms
        let roomIndex = rooms.firstIndex(where: { $0.id == room.id }) ?? 0
        let roomsOnFloor = rooms.filter { $0.floor == room.floor }
        let indexOnFloor = roomsOnFloor.firstIndex(where: { $0.id == room.id }) ?? 0

        let col = indexOnFloor % 3
        let row = indexOnFloor / 3

        let x = Float(col - 1) * 0.08  // 8cm spacing
        let z = Float(row) * 0.08

        return SIMD3<Float>(x, floorY, z)
    }

    private func roomColor(for room: RoomModel) -> Color {
        if room.occupied {
            return .grove
        }

        switch room.lightState {
        case "On": return .beacon
        case "Dim": return .nexus
        default: return .crystal.opacity(0.3)
        }
    }

    // MARK: - Updates

    private func updateRoomEntities(in container: Entity) {
        // Remove old room entities
        let existingRooms = container.children.filter { $0.name.starts(with: "room-") }
        existingRooms.forEach { $0.removeFromParent() }

        // Create new room entities
        for room in rooms {
            let roomEntity = createRoomEntity(room: room)

            // Find the correct floor to add to
            if let floor = container.children.first(where: { $0.name == "floor-\(room.floor)" }) {
                floor.addChild(roomEntity)
            } else {
                // Add to container if no floor found
                container.addChild(roomEntity)
            }
        }
    }

    // MARK: - Interaction

    private func handleRoomTap(_ entity: Entity) {
        let name = entity.name
        guard !name.isEmpty, name.starts(with: "room-") else { return }

        let roomId = String(name.dropFirst(5))  // Remove "room-" prefix
        selectedRoom = roomId

        // Play audio feedback
        audioService.play(.select, at: entity.position)

        // Find room and show controls
        if let room = rooms.first(where: { $0.id == roomId }) {
            print("Selected room: \(room.name)")

            // P1 FIX: Update breadcrumb when room is selected
            breadcrumbState.setPath(["Rooms", room.name])

            // In a full implementation, this would show a room control panel
        }
    }

    // MARK: - Data Loading

    private func loadRooms() async {
        isLoading = true

        do {
            rooms = try await appModel.apiService.fetchRooms()
        } catch {
            print("❌ Failed to load rooms: \(error)")
        }

        isLoading = false
    }
}

// MARK: - Room Control Overlay

/// Overlay panel that appears when a room is selected
struct SpatialRoomControlOverlay: View {
    let room: RoomModel
    @EnvironmentObject var appModel: AppModel
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        VStack(spacing: 16) {
            // Header
            HStack {
                Text(room.name)
                    .font(.spatialHeadline)

                Spacer()

                Button(action: { dismiss() }) {
                    Image(systemName: "xmark.circle.fill")
                        .font(.title2)
                        .foregroundColor(.secondary)
                }
            }

            Divider()

            // Light controls
            VStack(spacing: 12) {
                Text("Lights")
                    .font(.spatialCaption)
                    .foregroundColor(.secondary)

                HStack(spacing: 16) {
                    SpatialControlButton(icon: "sun.max.fill", label: "On", color: .beacon) {
                        Task { await appModel.apiService.setLights(100, rooms: [room.id]) }
                    }

                    SpatialControlButton(icon: "moon.fill", label: "Dim", color: .nexus) {
                        Task { await appModel.apiService.setLights(30, rooms: [room.id]) }
                    }

                    SpatialControlButton(icon: "moon.zzz.fill", label: "Off", color: .crystal) {
                        Task { await appModel.apiService.setLights(0, rooms: [room.id]) }
                    }
                }
            }

            // Shade controls (if available)
            if !room.shades.isEmpty {
                VStack(spacing: 12) {
                    Text("Shades")
                        .font(.spatialCaption)
                        .foregroundColor(.secondary)

                    HStack(spacing: 16) {
                        SpatialControlButton(icon: "sun.max.fill", label: "Open", color: .grove) {
                            Task { await appModel.apiService.controlShades("open", rooms: [room.id]) }
                        }

                        SpatialControlButton(icon: "moon.fill", label: "Close", color: .flow) {
                            Task { await appModel.apiService.controlShades("close", rooms: [room.id]) }
                        }
                    }
                }
            }
        }
        .padding(24)
        .frame(width: 300)
        .glassBackgroundEffect()
    }
}

/// A spatial-optimized control button
struct SpatialControlButton: View {
    let icon: String
    let label: String
    let color: Color
    let action: () -> Void

    @State private var isHovered = false

    var body: some View {
        Button(action: action) {
            VStack(spacing: 8) {
                Image(systemName: icon)
                    .font(.title2)
                    .foregroundColor(color)

                Text(label)
                    .font(.spatialCaption)
                    .foregroundColor(.secondary)
            }
            .frame(width: 60, height: 60)
            .background(
                RoundedRectangle(cornerRadius: 12)
                    .fill(color.opacity(isHovered ? 0.3 : 0.15))
            )
            .overlay(
                RoundedRectangle(cornerRadius: 12)
                    .stroke(color.opacity(0.3), lineWidth: 1)
            )
        }
        .buttonStyle(.plain)
        .hoverEffect(.lift)
        .onHover { isHovered = $0 }
    }
}

#Preview {
    Spatial3DRoomView()
        .environmentObject(AppModel())
}

/*
 * 鏡
 * h(x) >= 0. Always.
 *
 * The home becomes an object in your hands.
 * Depth creates hierarchy.
 * Layers create understanding.
 * Space creates intimacy.
 */
