//
// FullSpatialExperienceView.swift — Complete Immersive Home Control
//
// Colony: Crystal (e₇) — Verification & Polish
//
// Features:
//   - Combined spatial experience with all features
//   - Kagami orb presence at periphery
//   - 3D home model in social zone
//   - World-anchored control panel in personal zone
//   - Spatial audio feedback throughout
//   - Hand gesture integration
//   - Gaze-based navigation
//
// Spatial Zones:
//   - Intimate (0-45cm): Private notifications, emergency alerts
//   - Personal (45cm-1.2m): Control panel, active interactions
//   - Social (1.2m-3.6m): Home model, room visualization
//   - Ambient (3.6m+): Kagami orb, ambient awareness
//
// Created: December 31, 2025
// 鏡

import SwiftUI
import RealityKit

/// The complete spatial home control experience
struct FullSpatialExperienceView: View {
    @EnvironmentObject var appModel: AppModel
    @EnvironmentObject var health: HealthKitService
    @EnvironmentObject var spatialServices: SpatialServicesContainer

    @State private var rooms: [RoomModel] = []
    @State private var selectedRoom: RoomModel?
    @State private var isLoading = true
    @State private var showNotification = false
    @State private var notificationMessage = ""

    // Spatial positions
    private let orbPosition = SIMD3<Float>(0.4, 1.4, -2.0)  // Ambient zone
    private let homeModelPosition = SIMD3<Float>(0, 1.2, -2.0)  // Social zone
    private let controlPanelPosition = SIMD3<Float>(-0.3, 1.3, -0.8)  // Personal zone

    var body: some View {
        RealityView { content in
            // Create spatial scene container
            let scene = Entity()
            scene.name = "spatial-scene"

            // 1. Kagami Orb (Ambient Zone)
            let orb = createKagamiOrb()
            scene.addChild(orb)

            // 2. Home Model (Social Zone)
            let homeModel = createHomeModel()
            scene.addChild(homeModel)

            // 3. Control Panel Anchors (Personal Zone)
            let controlAnchors = createControlAnchors()
            scene.addChild(controlAnchors)

            // 4. Notification Area (Intimate Zone)
            let notificationArea = createNotificationArea()
            scene.addChild(notificationArea)

            // 5. Ambient Lighting
            let lighting = createSpatialLighting()
            scene.addChild(lighting)

            content.add(scene)

        } update: { content in
            guard let scene = content.entities.first(where: { $0.name == "spatial-scene" }) else { return }

            // Update orb color based on state
            updateOrbState(in: scene)

            // Update home model with room states
            updateHomeModel(in: scene)

            // Update notification visibility
            updateNotificationArea(in: scene)

            // Update based on gaze
            updateGazeFocus(in: scene)

            // Process hand gestures
            processGestures()
        }
        .gesture(
            SpatialTapGesture()
                .targetedToAnyEntity()
                .onEnded { value in
                    handleSpatialTap(value.entity)
                }
        )
        .task {
            await loadData()
            setupGestureCallbacks()
        }
    }

    // MARK: - Entity Creation

    private func createKagamiOrb() -> Entity {
        let container = Entity()
        container.name = "kagami-orb-container"
        container.position = orbPosition

        // Main orb
        let orb = Entity()
        orb.name = "kagami-orb"

        let mesh = MeshResource.generateSphere(radius: 0.08)
        var material = PhysicallyBasedMaterial()
        material.baseColor = .init(tint: .init(.crystal))
        material.emissiveColor = .init(color: .init(.crystal.opacity(0.6)))
        material.emissiveIntensity = 0.8
        material.roughness = 0.1
        material.clearcoat = .init(floatLiteral: 1.0)

        orb.components.set(ModelComponent(mesh: mesh, materials: [material]))
        orb.components.set(InputTargetComponent())
        orb.components.set(CollisionComponent(shapes: [.generateSphere(radius: 0.12)]))
        orb.components.set(HoverEffectComponent())

        // Accessibility
        var accessibility = AccessibilityComponent()
        accessibility.label = LocalizedStringResource(stringLiteral: "Kagami orb")
        accessibility.value = LocalizedStringResource(stringLiteral: appModel.isConnected ? "Connected, ready" : "Offline")
        accessibility.isAccessibilityElement = true
        accessibility.traits = [.button]
        orb.components.set(accessibility)

        container.addChild(orb)

        // Particle aura
        if !AccessibilitySettings.shared.reduceMotion {
            let particles = createOrbParticles()
            container.addChild(particles)
        }

        return container
    }

    private func createOrbParticles() -> Entity {
        let entity = Entity()
        entity.name = "orb-particles"

        var particles = ParticleEmitterComponent()
        particles.emitterShape = .sphere
        particles.emitterShapeSize = [0.2, 0.2, 0.2]
        particles.mainEmitter.birthRate = 10
        particles.mainEmitter.birthRateVariation = 3
        particles.mainEmitter.lifeSpan = 3
        particles.speed = 0.01
        particles.mainEmitter.color = .constant(.single(.init(.crystal.opacity(0.3))))
        particles.mainEmitter.size = 0.005

        entity.components.set(particles)

        return entity
    }

    private func createHomeModel() -> Entity {
        let container = Entity()
        container.name = "home-model-container"
        container.position = homeModelPosition

        // Base platform
        let platform = Entity()
        platform.name = "home-platform"
        let platformMesh = MeshResource.generateCylinder(height: 0.02, radius: 0.25)
        var platformMaterial = PhysicallyBasedMaterial()
        platformMaterial.baseColor = .init(tint: .init(.white.opacity(0.1)))
        platformMaterial.roughness = 1.0
        platform.components.set(ModelComponent(mesh: platformMesh, materials: [platformMaterial]))
        platform.position.y = -0.1
        container.addChild(platform)

        // Floor labels
        let floors = [
            ("Lower", -0.08),
            ("Main", 0.0),
            ("Upper", 0.08)
        ]

        for (name, yOffset) in floors {
            let floorEntity = createFloorEntity(name: name)
            floorEntity.position.y = Float(yOffset)
            container.addChild(floorEntity)
        }

        // Interaction
        container.components.set(InputTargetComponent())
        container.components.set(CollisionComponent(shapes: [.generateBox(size: SIMD3<Float>(0.5, 0.3, 0.4))]))

        return container
    }

    private func createFloorEntity(name: String) -> Entity {
        let floor = Entity()
        floor.name = "floor-\(name.lowercased())"

        // Semi-transparent floor plane
        let mesh = MeshResource.generatePlane(width: 0.35, depth: 0.25)
        var material = PhysicallyBasedMaterial()
        material.baseColor = .init(tint: .init(.white.opacity(0.05)))
        material.roughness = 1.0
        floor.components.set(ModelComponent(mesh: mesh, materials: [material]))

        return floor
    }

    private func createControlAnchors() -> Entity {
        let container = Entity()
        container.name = "control-anchors"
        container.position = controlPanelPosition

        // Quick action buttons in arc
        let actions = [
            ("Movie", Color.forge, "movie_mode"),
            ("Goodnight", Color.nexus, "goodnight"),
            ("Welcome", Color.grove, "welcome_home"),
            ("Lights", Color.beacon, "lights_on")
        ]

        let radius: Float = 0.15
        let angleStep = Float.pi / Float(actions.count + 1)

        for (index, (label, color, action)) in actions.enumerated() {
            let angle = Float.pi / 2 + Float(index + 1) * angleStep - Float.pi / 2
            let x = radius * cos(angle)
            let y = radius * sin(angle) * 0.5

            let button = createQuickActionButton(label: label, color: color, actionId: action)
            button.position = SIMD3<Float>(x, y, 0)
            container.addChild(button)
        }

        return container
    }

    private func createQuickActionButton(label: String, color: Color, actionId: String) -> Entity {
        let button = Entity()
        button.name = "action-\(actionId)"

        let mesh = MeshResource.generateSphere(radius: 0.03)
        var material = PhysicallyBasedMaterial()
        material.baseColor = .init(tint: .init(color.opacity(0.7)))
        material.emissiveColor = .init(color: .init(color))
        material.emissiveIntensity = 0.4
        material.roughness = 0.2
        material.clearcoat = .init(floatLiteral: 0.6)

        button.components.set(ModelComponent(mesh: mesh, materials: [material]))
        button.components.set(InputTargetComponent())
        button.components.set(CollisionComponent(shapes: [.generateSphere(radius: 0.04)]))
        button.components.set(HoverEffectComponent())

        var accessibility = AccessibilityComponent()
        accessibility.label = LocalizedStringResource(stringLiteral: label)
        accessibility.isAccessibilityElement = true
        accessibility.traits = [.button]
        button.components.set(accessibility)

        return button
    }

    private func createNotificationArea() -> Entity {
        let container = Entity()
        container.name = "notification-area"
        container.position = SIMD3<Float>(0, 1.5, -0.4)  // Intimate zone, above eye level

        // Notification panel (initially hidden)
        let panel = Entity()
        panel.name = "notification-panel"
        panel.scale = SIMD3<Float>(repeating: 0)  // Hidden by default

        let mesh = MeshResource.generatePlane(width: 0.2, height: 0.06, cornerRadius: 0.01)
        var material = PhysicallyBasedMaterial()
        material.baseColor = .init(tint: .init(.beacon.opacity(0.8)))
        material.emissiveColor = .init(color: .init(.beacon))
        material.emissiveIntensity = 0.3
        panel.components.set(ModelComponent(mesh: mesh, materials: [material]))

        container.addChild(panel)

        return container
    }

    private func createSpatialLighting() -> Entity {
        let container = Entity()
        container.name = "spatial-lighting"

        // Note: PointLightComponent requires visionOS 2.0
        // Using empty entities for light positioning - actual lighting via IBL/environment
        let ambient = Entity()
        ambient.position = SIMD3<Float>(0, 2, -1)
        container.addChild(ambient)

        // Accent light placeholder for orb area
        let orbLight = Entity()
        orbLight.position = orbPosition + SIMD3<Float>(0, 0.3, 0)
        container.addChild(orbLight)

        return container
    }

    // MARK: - Updates

    private func updateOrbState(in scene: Entity) {
        guard let orb = scene.findEntity(named: "kagami-orb"),
              var model = orb.components[ModelComponent.self] else { return }

        // Update color based on state
        let color: Color
        if !appModel.isConnected {
            color = .spark
        } else if let active = appModel.activeColonies.first {
            switch active {
            case "spark": color = .spark
            case "forge": color = .forge
            case "flow": color = .flow
            case "nexus": color = .nexus
            case "beacon": color = .beacon
            case "grove": color = .grove
            default: color = .crystal
            }
        } else {
            color = .crystal
        }

        if var material = model.materials.first as? PhysicallyBasedMaterial {
            material.baseColor = .init(tint: .init(color))
            material.emissiveColor = .init(color: .init(color.opacity(0.6)))
            model.materials = [material]
            orb.components.set(model)
        }
    }

    private func updateHomeModel(in scene: Entity) {
        guard let homeContainer = scene.findEntity(named: "home-model-container") else { return }

        // Remove existing room entities
        let existingRooms = homeContainer.children.filter { $0.name.starts(with: "room-") }
        existingRooms.forEach { $0.removeFromParent() }

        // Add room cubes
        for room in rooms {
            let roomEntity = createRoomEntity(room: room)

            // Position based on floor and simple grid
            let floorY: Float
            switch room.floor {
            case "Lower Level": floorY = -0.08
            case "Main Floor": floorY = 0.0
            case "Upper Floor": floorY = 0.08
            default: floorY = 0.0
            }

            let roomIndex = rooms.filter { $0.floor == room.floor }.firstIndex(where: { $0.id == room.id }) ?? 0
            let col = roomIndex % 3
            let row = roomIndex / 3
            let x = Float(col - 1) * 0.08
            let z = Float(row) * 0.06 - 0.05

            roomEntity.position = SIMD3<Float>(x, floorY + 0.02, z)
            homeContainer.addChild(roomEntity)
        }
    }

    private func createRoomEntity(room: RoomModel) -> Entity {
        let entity = Entity()
        entity.name = "room-\(room.id)"

        let size: Float = 0.035
        let mesh = MeshResource.generateBox(size: size, cornerRadius: 0.002)

        // Color based on room state
        let color: Color
        if room.occupied {
            color = .grove
        } else if room.avgLightLevel > 50 {
            color = .beacon
        } else if room.avgLightLevel > 0 {
            color = .nexus
        } else {
            color = .crystal.opacity(0.3)
        }

        var material = PhysicallyBasedMaterial()
        material.baseColor = .init(tint: .init(color))
        material.emissiveColor = .init(color: .init(color))
        material.emissiveIntensity = Float(room.avgLightLevel) / 150
        material.roughness = 0.3

        entity.components.set(ModelComponent(mesh: mesh, materials: [material]))
        entity.components.set(InputTargetComponent())
        entity.components.set(CollisionComponent(shapes: [.generateBox(size: SIMD3<Float>(repeating: size * 1.3))]))
        entity.components.set(HoverEffectComponent())

        var accessibility = AccessibilityComponent()
        accessibility.label = LocalizedStringResource(stringLiteral: room.name)
        accessibility.value = LocalizedStringResource(stringLiteral: "\(room.floor), \(room.lightState)")
        accessibility.isAccessibilityElement = true
        accessibility.traits = [.button]
        entity.components.set(accessibility)

        return entity
    }

    private func updateNotificationArea(in scene: Entity) {
        guard let panel = scene.findEntity(named: "notification-panel") else { return }

        // Animate notification visibility
        let targetScale: SIMD3<Float> = showNotification ? SIMD3<Float>(repeating: 1) : SIMD3<Float>(repeating: 0)
        panel.scale = simd_mix(panel.scale, targetScale, SIMD3<Float>(repeating: 0.1))
    }

    private func updateGazeFocus(in scene: Entity) {
        guard let gazeDirection = spatialServices.gazeTracking.gazeDirection else { return }

        // Check what user is looking at
        // This would use ray casting in production
        // For now, we just track the focus area
        let focusArea = spatialServices.gazeTracking.focusedArea

        // Could highlight elements based on gaze focus
    }

    // MARK: - Gestures

    private func setupGestureCallbacks() {
        spatialServices.gestureRecognizer.onSemanticAction = { [weak appModel] action, value in
            Task { @MainActor in
                guard let appModel = appModel else { return }

                switch action {
                case .brightnessUp:
                    let newLevel = min(100, Int(Float(100) * (0.5 + value / 2)))
                    await appModel.apiService.setLights(newLevel)

                case .brightnessDown:
                    let newLevel = max(0, Int(Float(100) * (0.5 - value / 2)))
                    await appModel.apiService.setLights(newLevel)

                case .emergencyStop:
                    // Emergency: turn off everything
                    await appModel.apiService.setLights(0)
                    await appModel.apiService.executeScene("goodnight")

                default:
                    break
                }
            }
        }
    }

    private func processGestures() {
        // Update gesture recognizer with latest hand data
        spatialServices.gestureRecognizer.update(from: spatialServices.handTracking)

        // Update listener position for spatial audio
        if let headPos = spatialServices.anchorService.headPosition,
           let headForward = spatialServices.anchorService.headForward {
            spatialServices.audioService.updateListenerPosition(headPos, forward: headForward)
        }
    }

    // MARK: - Interaction

    private func handleSpatialTap(_ entity: Entity) {
        let name = entity.name
        guard !name.isEmpty else { return }

        // Play tap sound
        spatialServices.audioService.play(.tap, at: entity.position)

        // Kagami orb
        if name == "kagami-orb" {
            handleOrbTap()
            return
        }

        // Quick action buttons
        if name.starts(with: "action-") {
            let actionId = String(name.dropFirst(7))
            handleQuickAction(actionId)
            return
        }

        // Room selection
        if name.starts(with: "room-") {
            let roomId = String(name.dropFirst(5))
            handleRoomTap(roomId)
            return
        }
    }

    private func handleOrbTap() {
        spatialServices.audioService.play(.orbActivate, at: orbPosition)

        // Context-aware action
        let hour = Calendar.current.component(.hour, from: Date())

        Task {
            switch hour {
            case 6...9:
                await appModel.apiService.setLights(80)
                showTemporaryNotification("Good morning! Lights set to 80%")

            case 18...21:
                await appModel.apiService.executeScene("movie_mode")
                showTemporaryNotification("Movie mode activated")

            case 22...24, 0...5:
                await appModel.apiService.executeScene("goodnight")
                showTemporaryNotification("Goodnight! All systems off")

            default:
                await appModel.apiService.setLights(100)
                showTemporaryNotification("Lights on")
            }
        }
    }

    private func handleQuickAction(_ actionId: String) {
        Task {
            switch actionId {
            case "movie_mode":
                await appModel.apiService.executeScene("movie_mode")
                showTemporaryNotification("Movie mode")

            case "goodnight":
                await appModel.apiService.executeScene("goodnight")
                showTemporaryNotification("Goodnight")

            case "welcome_home":
                await appModel.apiService.executeScene("welcome_home")
                showTemporaryNotification("Welcome home")

            case "lights_on":
                await appModel.apiService.setLights(100)
                showTemporaryNotification("Lights on")

            default:
                break
            }

            spatialServices.audioService.play(.success)
        }
    }

    private func handleRoomTap(_ roomId: String) {
        guard let room = rooms.first(where: { $0.id == roomId }) else { return }

        selectedRoom = room
        showTemporaryNotification("\(room.name) selected")

        // Toggle lights in room
        Task {
            if room.avgLightLevel > 0 {
                await appModel.apiService.setLights(0, rooms: [roomId])
            } else {
                await appModel.apiService.setLights(100, rooms: [roomId])
            }
            await loadData()  // Refresh
        }
    }

    private func showTemporaryNotification(_ message: String) {
        notificationMessage = message
        showNotification = true

        // Auto-hide after 2 seconds
        Task {
            try? await Task.sleep(nanoseconds: 2_000_000_000)
            showNotification = false
        }
    }

    // MARK: - Data Loading

    private func loadData() async {
        isLoading = true

        do {
            rooms = try await appModel.apiService.fetchRooms()
        } catch {
            print("❌ Failed to load rooms: \(error)")
        }

        isLoading = false
    }
}

#Preview {
    FullSpatialExperienceView()
        .environmentObject(AppModel())
        .environmentObject(HealthKitService())
        .environmentObject(SpatialServicesContainer())
}

/*
 * 鏡
 * h(x) >= 0. Always.
 *
 * The full spatial experience:
 * - Orb at the periphery, watching
 * - Home model in reach, tangible
 * - Controls at hand, immediate
 * - Notifications intimate, personal
 *
 * Space becomes interface.
 * Distance becomes relationship.
 * Presence becomes action.
 */
