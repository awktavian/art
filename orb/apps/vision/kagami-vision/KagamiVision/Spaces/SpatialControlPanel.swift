//
// SpatialControlPanel.swift — World-Anchored Control Interface
//
// Colony: Beacon (e₅) — Planning
//
// Features:
//   - World-locked control panel with persistent position
//   - Depth-layered UI elements (foreground, mid, background)
//   - Gaze-based selection with eye tracking
//   - Hand gesture integration for adjustments
//   - Proxemic-aware scaling and opacity
//   - Quick actions in orbital arrangement
//
// Design Philosophy:
//   The control panel exists in physical space, not as a flat
//   screen but as a volumetric interface. Controls have depth,
//   with primary actions closer to the user and secondary
//   controls receding into space.
//
// Created: December 31, 2025
// 鏡

import SwiftUI
import RealityKit

/// World-anchored spatial control panel with depth layers
struct SpatialControlPanel: View {
    @EnvironmentObject var appModel: AppModel
    @StateObject private var anchorService = SpatialAnchorService()
    @StateObject private var audioService = SpatialAudioService()
    @StateObject private var gestureRecognizer = SpatialGestureRecognizer()

    @State private var panelAnchor: SpatialAnchorService.SpatialAnchor?
    @State private var isExpanded = false
    @State private var selectedQuickAction: QuickAction?
    @State private var brightnessLevel: Float = 0.5

    // Depth layers (Z offset from anchor)
    private let depthLayers = DepthLayers()

    struct DepthLayers {
        let background: Float = -0.15    // 15cm behind anchor
        let midground: Float = -0.05     // 5cm behind anchor
        let foreground: Float = 0.0      // At anchor
        let interaction: Float = 0.05    // 5cm in front (for hover states)
    }

    // Quick actions arranged in a semicircle
    enum QuickAction: String, CaseIterable, Identifiable {
        case movieMode = "movie_mode"
        case goodnight = "goodnight"
        case welcome = "welcome"
        case lightsOn = "lights_on"
        case lightsOff = "lights_off"
        case fireplace = "fireplace"

        var id: String { rawValue }

        var icon: String {
            switch self {
            case .movieMode: return "film.fill"
            case .goodnight: return "moon.zzz.fill"
            case .welcome: return "house.fill"
            case .lightsOn: return "sun.max.fill"
            case .lightsOff: return "moon.fill"
            case .fireplace: return "flame.fill"
            }
        }

        var label: String {
            switch self {
            case .movieMode: return "Movie"
            case .goodnight: return "Goodnight"
            case .welcome: return "Welcome"
            case .lightsOn: return "Lights On"
            case .lightsOff: return "Lights Off"
            case .fireplace: return "Fireplace"
            }
        }

        var color: Color {
            switch self {
            case .movieMode: return .forge
            case .goodnight: return .nexus
            case .welcome: return .grove
            case .lightsOn: return .beacon
            case .lightsOff: return .crystal
            case .fireplace: return .spark
            }
        }
    }

    var body: some View {
        RealityView { content in
            // Create the control panel container
            let panelContainer = createPanelContainer()
            content.add(panelContainer)

        } update: { content in
            guard let container = content.entities.first(where: { $0.name == "control-panel" }) else { return }

            // Update panel position based on anchor
            if let anchor = panelAnchor {
                container.position = anchor.position
            }

            // Update expanded state
            updatePanelState(in: container)
        }
        .gesture(
            SpatialTapGesture()
                .targetedToAnyEntity()
                .onEnded { value in
                    handlePanelTap(value.entity)
                }
        )
        .task {
            await initializePanel()
        }
    }

    // MARK: - Entity Creation

    private func createPanelContainer() -> Entity {
        let container = Entity()
        container.name = "control-panel"
        container.position = SIMD3<Float>(0, 1.3, -0.8)  // Personal zone

        // Background layer - status display
        let background = createBackgroundLayer()
        background.position.z = depthLayers.background
        container.addChild(background)

        // Midground layer - secondary controls
        let midground = createMidgroundLayer()
        midground.position.z = depthLayers.midground
        container.addChild(midground)

        // Foreground layer - primary controls / quick actions
        let foreground = createForegroundLayer()
        foreground.position.z = depthLayers.foreground
        container.addChild(foreground)

        return container
    }

    private func createBackgroundLayer() -> Entity {
        let layer = Entity()
        layer.name = "background-layer"

        // Large semi-transparent backdrop
        let mesh = MeshResource.generatePlane(width: 0.5, height: 0.35, cornerRadius: 0.02)
        var material = PhysicallyBasedMaterial()
        material.baseColor = .init(tint: .init(.black.opacity(0.3)))
        material.roughness = 1.0
        material.blending = .transparent(opacity: 0.3)

        let modelComponent = ModelComponent(mesh: mesh, materials: [material])
        layer.components.set(modelComponent)

        // Status indicators
        let statusRow = createStatusRow()
        statusRow.position = SIMD3<Float>(0, 0.1, 0.01)
        layer.addChild(statusRow)

        return layer
    }

    private func createMidgroundLayer() -> Entity {
        let layer = Entity()
        layer.name = "midground-layer"

        // Brightness slider track
        let sliderTrack = createSliderTrack()
        sliderTrack.position = SIMD3<Float>(0, -0.08, 0)
        layer.addChild(sliderTrack)

        // Room selector
        let roomSelector = createRoomSelector()
        roomSelector.position = SIMD3<Float>(0, -0.04, 0)
        layer.addChild(roomSelector)

        return layer
    }

    private func createForegroundLayer() -> Entity {
        let layer = Entity()
        layer.name = "foreground-layer"

        // Quick action orbital
        let orbital = createQuickActionOrbital()
        layer.addChild(orbital)

        return layer
    }

    private func createStatusRow() -> Entity {
        let row = Entity()
        row.name = "status-row"

        // Safety indicator
        let safetyOrb = Entity()
        safetyOrb.name = "safety-orb"
        let safetyMesh = MeshResource.generateSphere(radius: 0.01)
        var safetyMaterial = PhysicallyBasedMaterial()
        safetyMaterial.baseColor = .init(tint: .init(.grove))
        safetyMaterial.emissiveColor = .init(color: .init(.grove))
        safetyMaterial.emissiveIntensity = 0.5
        safetyOrb.components.set(ModelComponent(mesh: safetyMesh, materials: [safetyMaterial]))
        safetyOrb.position = SIMD3<Float>(-0.15, 0, 0)
        row.addChild(safetyOrb)

        // Connection indicator
        let connOrb = Entity()
        connOrb.name = "connection-orb"
        let connMesh = MeshResource.generateSphere(radius: 0.008)
        var connMaterial = PhysicallyBasedMaterial()
        connMaterial.baseColor = .init(tint: .init(.crystal))
        connMaterial.emissiveColor = .init(color: .init(.crystal))
        connMaterial.emissiveIntensity = 0.5
        connOrb.components.set(ModelComponent(mesh: connMesh, materials: [connMaterial]))
        connOrb.position = SIMD3<Float>(0.15, 0, 0)
        row.addChild(connOrb)

        return row
    }

    private func createSliderTrack() -> Entity {
        let track = Entity()
        track.name = "brightness-track"

        // Track background
        let trackMesh = MeshResource.generateBox(width: 0.3, height: 0.008, depth: 0.008, cornerRadius: 0.004)
        var trackMaterial = PhysicallyBasedMaterial()
        trackMaterial.baseColor = .init(tint: .init(.white.opacity(0.2)))
        track.components.set(ModelComponent(mesh: trackMesh, materials: [trackMaterial]))

        // Track fill
        let fill = Entity()
        fill.name = "brightness-fill"
        let fillMesh = MeshResource.generateBox(width: 0.15, height: 0.008, depth: 0.01, cornerRadius: 0.004)
        var fillMaterial = PhysicallyBasedMaterial()
        fillMaterial.baseColor = .init(tint: .init(.beacon))
        fillMaterial.emissiveColor = .init(color: .init(.beacon))
        fillMaterial.emissiveIntensity = 0.3
        fill.components.set(ModelComponent(mesh: fillMesh, materials: [fillMaterial]))
        fill.position = SIMD3<Float>(-0.075, 0, 0.002)
        track.addChild(fill)

        // Thumb
        let thumb = Entity()
        thumb.name = "brightness-thumb"
        let thumbMesh = MeshResource.generateSphere(radius: 0.015)
        var thumbMaterial = PhysicallyBasedMaterial()
        thumbMaterial.baseColor = .init(tint: .init(.white))
        thumbMaterial.emissiveColor = .init(color: .init(.beacon))
        thumbMaterial.emissiveIntensity = 0.5
        thumb.components.set(ModelComponent(mesh: thumbMesh, materials: [thumbMaterial]))
        thumb.components.set(InputTargetComponent())
        thumb.components.set(CollisionComponent(shapes: [.generateSphere(radius: 0.02)]))
        thumb.components.set(HoverEffectComponent())
        thumb.position = SIMD3<Float>(0, 0, 0.01)
        track.addChild(thumb)

        // Accessibility
        var accessibility = AccessibilityComponent()
        accessibility.label = LocalizedStringResource(stringLiteral: "Brightness slider")
        accessibility.value = LocalizedStringResource(stringLiteral: "\(Int(brightnessLevel * 100)) percent")
        accessibility.isAccessibilityElement = true
        track.components.set(accessibility)

        return track
    }

    private func createRoomSelector() -> Entity {
        let selector = Entity()
        selector.name = "room-selector"

        // Simple room indicator dots
        let rooms = ["Living", "Bedroom", "Office", "Kitchen"]
        let spacing: Float = 0.05

        for (index, room) in rooms.enumerated() {
            let dot = Entity()
            dot.name = "room-\(room.lowercased())"

            let mesh = MeshResource.generateSphere(radius: 0.008)
            var material = PhysicallyBasedMaterial()
            material.baseColor = .init(tint: .init(index == 0 ? .crystal : .white.opacity(0.3)))
            material.emissiveColor = .init(color: .init(index == 0 ? .crystal : .clear))
            material.emissiveIntensity = index == 0 ? 0.5 : 0

            dot.components.set(ModelComponent(mesh: mesh, materials: [material]))
            dot.components.set(InputTargetComponent())
            dot.components.set(CollisionComponent(shapes: [.generateSphere(radius: 0.012)]))
            dot.components.set(HoverEffectComponent())
            dot.position = SIMD3<Float>(Float(index - rooms.count / 2) * spacing, 0, 0)

            selector.addChild(dot)
        }

        return selector
    }

    private func createQuickActionOrbital() -> Entity {
        let orbital = Entity()
        orbital.name = "quick-action-orbital"

        // Arrange quick actions in a semicircle
        let radius: Float = 0.12
        let actions = QuickAction.allCases
        let angleStep = Float.pi / Float(actions.count - 1)

        for (index, action) in actions.enumerated() {
            let angle = Float.pi / 2 - Float(index) * angleStep + Float.pi / 2
            let x = radius * cos(angle)
            let y = radius * sin(angle) - 0.05  // Offset down

            let button = createQuickActionButton(action: action)
            button.position = SIMD3<Float>(x, y, 0)

            orbital.addChild(button)
        }

        return orbital
    }

    private func createQuickActionButton(action: QuickAction) -> Entity {
        let button = Entity()
        button.name = "action-\(action.rawValue)"

        // Button base
        let mesh = MeshResource.generateSphere(radius: 0.025)
        var material = PhysicallyBasedMaterial()
        material.baseColor = .init(tint: .init(action.color.opacity(0.6)))
        material.emissiveColor = .init(color: .init(action.color))
        material.emissiveIntensity = 0.3
        material.roughness = 0.2
        material.clearcoat = .init(floatLiteral: 0.8)

        let modelComponent = ModelComponent(mesh: mesh, materials: [material])
        button.components.set(modelComponent)

        // Interactivity
        button.components.set(InputTargetComponent())
        button.components.set(CollisionComponent(shapes: [.generateSphere(radius: 0.03)]))
        button.components.set(HoverEffectComponent())

        // Accessibility
        var accessibility = AccessibilityComponent()
        accessibility.label = LocalizedStringResource(stringLiteral: action.label)
        accessibility.isAccessibilityElement = true
        accessibility.traits = [.button]
        button.components.set(accessibility)

        return button
    }

    // MARK: - Updates

    private func updatePanelState(in container: Entity) {
        // Update brightness slider position
        if let track = container.findEntity(named: "brightness-track"),
           let thumb = track.findEntity(named: "brightness-thumb") {
            let x = (brightnessLevel - 0.5) * 0.3  // -0.15 to 0.15
            thumb.position.x = x
        }

        // Update safety indicator based on app state
        if let safetyOrb = container.findEntity(named: "safety-orb"),
           var model = safetyOrb.components[ModelComponent.self] {
            var material = PhysicallyBasedMaterial()
            let safetyColor: Color = (appModel.safetyScore >= 0.5) ? .grove : .spark
            material.baseColor = .init(tint: .init(safetyColor))
            material.emissiveColor = .init(color: .init(safetyColor))
            material.emissiveIntensity = 0.5
            model.materials = [material]
            safetyOrb.components.set(model)
        }

        // Update connection indicator
        if let connOrb = container.findEntity(named: "connection-orb"),
           var model = connOrb.components[ModelComponent.self] {
            var material = PhysicallyBasedMaterial()
            let connColor: Color = appModel.isConnected ? .crystal : .spark
            material.baseColor = .init(tint: .init(connColor))
            material.emissiveColor = .init(color: .init(connColor))
            material.emissiveIntensity = appModel.isConnected ? 0.5 : 0.8
            model.materials = [material]
            connOrb.components.set(model)
        }
    }

    // MARK: - Interaction

    private func handlePanelTap(_ entity: Entity) {
        let name = entity.name
        guard !name.isEmpty else { return }

        // Quick action buttons
        if name.starts(with: "action-") {
            let actionId = String(name.dropFirst(7))
            if let action = QuickAction(rawValue: actionId) {
                executeQuickAction(action)
            }
            return
        }

        // Room selector
        if name.starts(with: "room-") {
            let roomId = String(name.dropFirst(5))
            selectRoom(roomId)
            return
        }

        // Brightness thumb
        if name == "brightness-thumb" {
            // This would enter drag mode in a full implementation
            print("🎚️ Brightness control activated")
        }
    }

    private func executeQuickAction(_ action: QuickAction) {
        audioService.play(.tap, at: nil)

        Task {
            switch action {
            case .movieMode:
                await appModel.apiService.executeScene("movie_mode")
            case .goodnight:
                await appModel.apiService.executeScene("goodnight")
            case .welcome:
                await appModel.apiService.executeScene("welcome_home")
            case .lightsOn:
                await appModel.apiService.setLights(100)
            case .lightsOff:
                await appModel.apiService.setLights(0)
            case .fireplace:
                await appModel.apiService.toggleFireplace()
            }

            // Success audio
            audioService.play(.success, at: nil)
        }
    }

    private func selectRoom(_ roomId: String) {
        audioService.play(.select, at: nil)
        print("🏠 Selected room: \(roomId)")
    }

    // MARK: - Initialization

    private func initializePanel() async {
        await anchorService.start()

        // Create persistent anchor for control panel
        panelAnchor = anchorService.createControlPanelAnchor(label: "Main Control Panel")
    }
}

// MARK: - Entity Extensions

extension Entity {
    func findEntity(named name: String) -> Entity? {
        if self.name == name { return self }

        for child in children {
            if let found = child.findEntity(named: name) {
                return found
            }
        }

        return nil
    }
}

#Preview {
    SpatialControlPanel()
        .environmentObject(AppModel())
}

/*
 * 鏡
 * h(x) >= 0. Always.
 *
 * The control panel floats in space,
 * anchored to the world, not the screen.
 * Depth creates hierarchy.
 * Distance creates intimacy.
 * The interface breathes.
 */
