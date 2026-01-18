//
// SpatialUIService.swift - Spatial Window and Volume Management
//
// Colony: Nexus (e4) - Integration
//
// Features:
//   - Spatial window lifecycle management
//   - Device control panels that float near user
//   - Room-anchored controls (lights, shades, etc.)
//   - Gaze-based interaction highlighting
//   - Proxemic zone-aware UI placement
//   - Volume management for immersive content
//
// Architecture:
//   SpatialUIService -> SpatialAnchorService -> World Tracking
//   SpatialUIService -> RealityKit -> Visual Rendering
//
// Created: December 31, 2025


import SwiftUI
import RealityKit
import ARKit
import Combine

/// Manages spatial UI elements in visionOS
@MainActor
class SpatialUIService: ObservableObject {

    // MARK: - Published State

    @Published var activeWindows: [SpatialWindow] = []
    @Published var activeVolumes: [SpatialVolume] = []
    @Published var highlightedEntity: Entity?
    @Published var gazeTarget: GazeTarget?
    @Published var isTrackingGaze = false

    // MARK: - Types

    /// A spatial window that can float in space
    struct SpatialWindow: Identifiable {
        let id: UUID
        var position: SIMD3<Float>
        var rotation: simd_quatf
        var size: SIMD2<Float>
        var anchorType: SpatialAnchorService.AnchorType
        var windowType: WindowType
        var isVisible: Bool
        var opacity: Double
        var entity: Entity?
        let createdAt: Date

        enum WindowType: String {
            case controlPanel = "control_panel"
            case roomControls = "room_controls"
            case deviceDetail = "device_detail"
            case notification = "notification"
            case quickActions = "quick_actions"
            case settings = "settings"
        }

        init(
            id: UUID = UUID(),
            position: SIMD3<Float>,
            size: SIMD2<Float> = SIMD2<Float>(0.4, 0.3),
            anchorType: SpatialAnchorService.AnchorType = .headRelative,
            windowType: WindowType
        ) {
            self.id = id
            self.position = position
            self.rotation = simd_quatf(angle: 0, axis: [0, 1, 0])
            self.size = size
            self.anchorType = anchorType
            self.windowType = windowType
            self.isVisible = true
            self.opacity = 1.0
            self.entity = nil
            self.createdAt = Date()
        }
    }

    /// A volumetric content region
    struct SpatialVolume: Identifiable {
        let id: UUID
        var position: SIMD3<Float>
        var bounds: SIMD3<Float>
        var contentType: VolumeType
        var isActive: Bool
        var rootEntity: Entity?

        enum VolumeType: String {
            case homeModel = "home_model"
            case roomDetail = "room_detail"
            case deviceVisualization = "device_viz"
            case ambientPresence = "ambient"
        }

        init(
            id: UUID = UUID(),
            position: SIMD3<Float>,
            bounds: SIMD3<Float>,
            contentType: VolumeType
        ) {
            self.id = id
            self.position = position
            self.bounds = bounds
            self.contentType = contentType
            self.isActive = true
            self.rootEntity = nil
        }
    }

    /// Gaze target information
    struct GazeTarget {
        let entity: Entity
        let hitPosition: SIMD3<Float>
        let timestamp: Date
        var dwellTime: TimeInterval {
            Date().timeIntervalSince(timestamp)
        }
    }

    /// Highlight configuration for gaze interaction
    struct HighlightConfig {
        var color: UIColor
        var intensity: Float
        var pulseRate: Float
        var outlineWidth: Float

        static let `default` = HighlightConfig(
            color: UIColor(.crystal),
            intensity: 0.5,
            pulseRate: 2.0,
            outlineWidth: 0.002
        )

        static let active = HighlightConfig(
            color: UIColor(.crystal),
            intensity: 0.8,
            pulseRate: 1.0,
            outlineWidth: 0.003
        )
    }

    // MARK: - Dependencies

    private let anchorService: SpatialAnchorService
    private let audioService: SpatialAudioService

    // MARK: - Internal State

    private var windowEntities: [UUID: Entity] = [:]
    private var volumeRoots: [UUID: Entity] = [:]
    private var gazeStartTime: Date?
    private var lastGazeEntity: Entity?
    private let dwellThreshold: TimeInterval = 0.4

    // Highlight materials
    private var highlightMaterial: PhysicallyBasedMaterial?
    private var originalMaterials: [Entity: [RealityKit.Material]] = [:]

    private var cancellables = Set<AnyCancellable>()

    // MARK: - Init

    init(anchorService: SpatialAnchorService? = nil,
         audioService: SpatialAudioService? = nil) {
        self.anchorService = anchorService ?? SpatialAnchorService()
        self.audioService = audioService ?? SpatialAudioService()
        setupHighlightMaterial()
        setupGazeTracking()
    }

    // MARK: - Setup

    private func setupHighlightMaterial() {
        var material = PhysicallyBasedMaterial()
        material.baseColor = .init(tint: UIColor(.crystal.opacity(0.3)))
        material.emissiveColor = .init(color: UIColor(.crystal))
        material.emissiveIntensity = 0.5
        material.roughness = 0.3
        material.metallic = 0.0
        material.blending = .transparent(opacity: .init(floatLiteral: 0.7))
        highlightMaterial = material
    }

    private func setupGazeTracking() {
        // Track head position updates from anchor service
        anchorService.$headPosition
            .receive(on: DispatchQueue.main)
            .sink { [weak self] _ in
                self?.updateGazeHighlighting()
            }
            .store(in: &cancellables)
    }

    // MARK: - Window Management

    /// Creates a control panel window at the optimal position
    func createControlPanel(for roomId: String? = nil) -> SpatialWindow {
        let position = anchorService.idealPosition(for: .personal)

        var window = SpatialWindow(
            position: position,
            size: SIMD2<Float>(0.4, 0.35),
            anchorType: .headRelative,
            windowType: roomId != nil ? .roomControls : .controlPanel
        )

        // Create the entity
        let entity = createWindowEntity(for: window)
        window.entity = entity
        windowEntities[window.id] = entity

        activeWindows.append(window)

        // Audio feedback
        audioService.play(.select, at: position)

        return window
    }

    /// Creates a device detail panel anchored to a position
    func createDevicePanel(
        deviceId: String,
        deviceType: String,
        position: SIMD3<Float>
    ) -> SpatialWindow {
        var window = SpatialWindow(
            position: position + SIMD3<Float>(0, 0.1, 0), // Slightly above device
            size: SIMD2<Float>(0.25, 0.2),
            anchorType: .worldLocked,
            windowType: .deviceDetail
        )

        let entity = createWindowEntity(for: window)
        window.entity = entity
        windowEntities[window.id] = entity

        activeWindows.append(window)

        return window
    }

    /// Creates a notification window in the intimate zone
    func createNotification(message: String, priority: NotificationPriority = .normal) -> SpatialWindow {
        let zone: SpatialAnchorService.ProxemicZone = priority == .urgent ? .intimate : .personal
        var position = anchorService.idealPosition(for: zone)

        // Offset slightly to the side
        position.x += 0.2

        var window = SpatialWindow(
            position: position,
            size: SIMD2<Float>(0.3, 0.1),
            anchorType: .headRelative,
            windowType: .notification
        )

        let entity = createWindowEntity(for: window)
        window.entity = entity
        windowEntities[window.id] = entity

        activeWindows.append(window)

        // Audio feedback based on priority
        let event: SpatialAudioService.AudioEvent = priority == .urgent ? .notification : .tap
        audioService.play(event, at: position)

        // Auto-dismiss after delay
        let dismissDelay: TimeInterval = priority == .urgent ? 10.0 : 5.0
        Task {
            try? await Task.sleep(nanoseconds: UInt64(dismissDelay * 1_000_000_000))
            await MainActor.run {
                dismissWindow(window.id)
            }
        }

        return window
    }

    enum NotificationPriority {
        case normal
        case urgent
    }

    /// Creates quick action buttons floating near user
    func createQuickActions(actions: [QuickAction]) -> SpatialWindow {
        var position = anchorService.idealPosition(for: .personal)
        position.y -= 0.1 // Below eye level

        var window = SpatialWindow(
            position: position,
            size: SIMD2<Float>(0.5, 0.15),
            anchorType: .headRelative,
            windowType: .quickActions
        )

        let entity = createQuickActionsEntity(actions: actions)
        window.entity = entity
        windowEntities[window.id] = entity

        activeWindows.append(window)

        return window
    }

    struct QuickAction: Identifiable {
        let id: UUID = UUID()
        let icon: String
        let label: String
        let action: () async -> Void
        var color: Color = .crystal
    }

    /// Dismisses a window with animation
    func dismissWindow(_ id: UUID) {
        guard let index = activeWindows.firstIndex(where: { $0.id == id }) else { return }

        if let entity = windowEntities[id] {
            // Animate out
            animateEntityDismissal(entity)
        }

        activeWindows.remove(at: index)
        windowEntities.removeValue(forKey: id)

        audioService.play(.tap)
    }

    /// Dismisses all windows
    func dismissAllWindows() {
        for window in activeWindows {
            if let entity = windowEntities[window.id] {
                animateEntityDismissal(entity)
            }
        }
        activeWindows.removeAll()
        windowEntities.removeAll()
    }

    // MARK: - Volume Management

    /// Creates a volume for the home model visualization
    func createHomeModelVolume(at position: SIMD3<Float>? = nil) -> SpatialVolume {
        let pos = position ?? anchorService.idealPosition(for: .social)

        var volume = SpatialVolume(
            position: pos,
            bounds: SIMD3<Float>(0.5, 0.3, 0.4),
            contentType: .homeModel
        )

        let root = Entity()
        root.name = "home-model-volume"
        root.position = pos

        volume.rootEntity = root
        volumeRoots[volume.id] = root

        activeVolumes.append(volume)

        return volume
    }

    /// Creates a volume for detailed room visualization
    func createRoomVolume(roomId: String, at position: SIMD3<Float>) -> SpatialVolume {
        var volume = SpatialVolume(
            position: position,
            bounds: SIMD3<Float>(0.3, 0.2, 0.3),
            contentType: .roomDetail
        )

        let root = Entity()
        root.name = "room-volume-\(roomId)"
        root.position = position

        volume.rootEntity = root
        volumeRoots[volume.id] = root

        activeVolumes.append(volume)

        return volume
    }

    /// Deactivates a volume
    func deactivateVolume(_ id: UUID) {
        guard let index = activeVolumes.firstIndex(where: { $0.id == id }) else { return }

        activeVolumes[index].isActive = false

        if let entity = volumeRoots[id] {
            animateEntityDismissal(entity)
        }
    }

    // MARK: - Entity Creation

    private func createWindowEntity(for window: SpatialWindow) -> Entity {
        let entity = Entity()
        entity.name = "window-\(window.windowType.rawValue)-\(window.id.uuidString.prefix(8))"
        entity.position = window.position

        // Create glass panel background
        let panelMesh = MeshResource.generatePlane(
            width: window.size.x,
            height: window.size.y,
            cornerRadius: 0.02
        )

        var material = PhysicallyBasedMaterial()
        material.baseColor = .init(tint: UIColor(.voidSpatial))
        material.roughness = 0.1
        material.metallic = 0.0
        material.blending = .transparent(opacity: .init(floatLiteral: 0.85))

        let modelComponent = ModelComponent(mesh: panelMesh, materials: [material])
        entity.components.set(modelComponent)

        // Make interactive
        entity.components.set(InputTargetComponent())
        entity.components.set(CollisionComponent(shapes: [
            .generateBox(size: SIMD3<Float>(window.size.x, window.size.y, 0.02))
        ]))
        entity.components.set(HoverEffectComponent())

        // Add border glow
        let borderEntity = createBorderEntity(size: window.size)
        entity.addChild(borderEntity)

        return entity
    }

    private func createBorderEntity(size: SIMD2<Float>) -> Entity {
        let border = Entity()
        border.name = "window-border"

        // Create a thin outline using a slightly larger plane
        let borderMesh = MeshResource.generatePlane(
            width: size.x + 0.004,
            height: size.y + 0.004,
            cornerRadius: 0.022
        )

        var material = PhysicallyBasedMaterial()
        material.baseColor = .init(tint: UIColor(.crystal.opacity(0.3)))
        material.emissiveColor = .init(color: UIColor(.crystal.opacity(0.5)))
        material.emissiveIntensity = 0.3
        material.blending = .transparent(opacity: .init(floatLiteral: 0.5))

        let modelComponent = ModelComponent(mesh: borderMesh, materials: [material])
        border.components.set(modelComponent)

        border.position.z = -0.001 // Slightly behind the main panel

        return border
    }

    private func createQuickActionsEntity(actions: [QuickAction]) -> Entity {
        let container = Entity()
        container.name = "quick-actions"

        let buttonSpacing: Float = 0.08
        let startX = -Float(actions.count - 1) / 2 * buttonSpacing

        for (index, action) in actions.enumerated() {
            let button = createQuickActionButton(action: action)
            button.position.x = startX + Float(index) * buttonSpacing
            container.addChild(button)
        }

        return container
    }

    private func createQuickActionButton(action: QuickAction) -> Entity {
        let button = Entity()
        button.name = "quick-action-\(action.id.uuidString.prefix(8))"

        // Circular button background
        let mesh = MeshResource.generateSphere(radius: 0.03)

        var material = PhysicallyBasedMaterial()
        material.baseColor = .init(tint: UIColor(action.color.opacity(0.3)))
        material.emissiveColor = .init(color: UIColor(action.color.opacity(0.5)))
        material.emissiveIntensity = 0.4
        material.roughness = 0.2

        let modelComponent = ModelComponent(mesh: mesh, materials: [material])
        button.components.set(modelComponent)

        // Make interactive
        button.components.set(InputTargetComponent())
        button.components.set(CollisionComponent(shapes: [.generateSphere(radius: 0.035)]))
        button.components.set(HoverEffectComponent())

        // Accessibility
        var accessibilityComponent = AccessibilityComponent()
        accessibilityComponent.label = LocalizedStringResource(stringLiteral: action.label)
        accessibilityComponent.isAccessibilityElement = true
        accessibilityComponent.traits = [.button]
        button.components.set(accessibilityComponent)

        return button
    }

    // MARK: - Gaze Interaction

    /// Updates gaze highlighting based on what user is looking at
    func updateGazeHighlighting() {
        guard isTrackingGaze else { return }

        // This would typically use gaze ray casting from ARKit
        // For now, we track based on proximity and head direction
        guard let headPos = anchorService.headPosition,
              let headForward = anchorService.headForward else { return }

        // Find the entity the user is looking at
        var closestEntity: Entity?
        var closestDistance: Float = Float.infinity

        for window in activeWindows {
            guard let entity = window.entity else { continue }

            // Check if looking at this entity
            if anchorService.isLookingAt(
                SpatialAnchorService.SpatialAnchor(
                    position: entity.position,
                    anchorType: .worldLocked,
                    label: ""
                ),
                threshold: 0.2
            ) {
                let distance = simd_length(entity.position - headPos)
                if distance < closestDistance {
                    closestDistance = distance
                    closestEntity = entity
                }
            }
        }

        // Update highlight state
        if let entity = closestEntity {
            if entity !== lastGazeEntity {
                // New entity - start dwell timer
                unhighlightEntity(lastGazeEntity)
                highlightEntity(entity, config: .default)
                gazeStartTime = Date()
                lastGazeEntity = entity

                gazeTarget = GazeTarget(
                    entity: entity,
                    hitPosition: entity.position,
                    timestamp: Date()
                )
            } else if let startTime = gazeStartTime {
                // Check dwell time
                let dwellTime = Date().timeIntervalSince(startTime)
                if dwellTime > dwellThreshold {
                    highlightEntity(entity, config: .active)
                }
            }
        } else {
            // No entity in gaze
            unhighlightEntity(lastGazeEntity)
            lastGazeEntity = nil
            gazeTarget = nil
            gazeStartTime = nil
        }
    }

    /// Highlights an entity with gaze feedback
    func highlightEntity(_ entity: Entity?, config: HighlightConfig = .default) {
        guard let entity = entity else { return }

        // Store original materials if not already stored
        if originalMaterials[entity] == nil,
           let model = entity.components[ModelComponent.self] {
            originalMaterials[entity] = model.materials
        }

        // Apply highlight material
        var material = highlightMaterial ?? PhysicallyBasedMaterial()
        material.emissiveIntensity = config.intensity

        if var model = entity.components[ModelComponent.self] {
            // Blend highlight with original
            model.materials = [material]
            entity.components.set(model)
        }

        highlightedEntity = entity
    }

    /// Removes highlight from an entity
    func unhighlightEntity(_ entity: Entity?) {
        guard let entity = entity else { return }

        // Restore original materials
        if let original = originalMaterials[entity],
           var model = entity.components[ModelComponent.self] {
            model.materials = original
            entity.components.set(model)
            originalMaterials.removeValue(forKey: entity)
        }

        if highlightedEntity === entity {
            highlightedEntity = nil
        }
    }

    /// Starts gaze tracking for interaction
    func startGazeTracking() {
        isTrackingGaze = true
    }

    /// Stops gaze tracking
    func stopGazeTracking() {
        isTrackingGaze = false
        unhighlightEntity(highlightedEntity)
        gazeTarget = nil
    }

    // MARK: - Room-Anchored Controls

    /// Creates device controls anchored near physical device locations
    func createRoomAnchoredControls(
        for room: RoomModel,
        at anchorPosition: SIMD3<Float>
    ) -> [SpatialWindow] {
        var windows: [SpatialWindow] = []

        // Create light control if room has lights
        if !room.lights.isEmpty {
            var lightWindow = SpatialWindow(
                position: anchorPosition + SIMD3<Float>(-0.15, 0.1, 0),
                size: SIMD2<Float>(0.12, 0.15),
                anchorType: .worldLocked,
                windowType: .deviceDetail
            )

            let entity = createLightControlEntity(lights: room.lights)
            entity.position = lightWindow.position
            lightWindow.entity = entity
            windowEntities[lightWindow.id] = entity

            activeWindows.append(lightWindow)
            windows.append(lightWindow)
        }

        // Create shade control if room has shades
        if !room.shades.isEmpty {
            var shadeWindow = SpatialWindow(
                position: anchorPosition + SIMD3<Float>(0.15, 0.1, 0),
                size: SIMD2<Float>(0.12, 0.15),
                anchorType: .worldLocked,
                windowType: .deviceDetail
            )

            let entity = createShadeControlEntity(shades: room.shades)
            entity.position = shadeWindow.position
            shadeWindow.entity = entity
            windowEntities[shadeWindow.id] = entity

            activeWindows.append(shadeWindow)
            windows.append(shadeWindow)
        }

        return windows
    }

    private func createLightControlEntity(lights: [Light]) -> Entity {
        let container = Entity()
        container.name = "light-controls"

        // Light bulb icon
        let iconEntity = createIconEntity(systemName: "lightbulb.fill", color: .beacon)
        iconEntity.position.y = 0.04
        container.addChild(iconEntity)

        // Brightness indicator
        let avgLevel = lights.reduce(0) { $0 + $1.level } / max(lights.count, 1)
        let barEntity = createBrightnessBar(level: Float(avgLevel) / 100)
        barEntity.position.y = -0.02
        container.addChild(barEntity)

        // Make interactive
        container.components.set(InputTargetComponent())
        container.components.set(CollisionComponent(shapes: [
            .generateBox(size: SIMD3<Float>(0.1, 0.12, 0.02))
        ]))
        container.components.set(HoverEffectComponent())

        return container
    }

    private func createShadeControlEntity(shades: [Shade]) -> Entity {
        let container = Entity()
        container.name = "shade-controls"

        // Shade icon
        let iconEntity = createIconEntity(systemName: "blinds.horizontal.closed", color: .grove)
        iconEntity.position.y = 0.04
        container.addChild(iconEntity)

        // Position indicator
        let avgPos = shades.reduce(0) { $0 + $1.position } / max(shades.count, 1)
        let barEntity = createBrightnessBar(level: Float(avgPos) / 100)
        barEntity.position.y = -0.02
        container.addChild(barEntity)

        // Make interactive
        container.components.set(InputTargetComponent())
        container.components.set(CollisionComponent(shapes: [
            .generateBox(size: SIMD3<Float>(0.1, 0.12, 0.02))
        ]))
        container.components.set(HoverEffectComponent())

        return container
    }

    private func createIconEntity(systemName: String, color: Color) -> Entity {
        let entity = Entity()

        // Use a simple sphere as placeholder (in production, use SF Symbol mesh)
        let mesh = MeshResource.generateSphere(radius: 0.015)

        var material = PhysicallyBasedMaterial()
        material.baseColor = .init(tint: UIColor(color))
        material.emissiveColor = .init(color: UIColor(color.opacity(0.6)))
        material.emissiveIntensity = 0.5

        let modelComponent = ModelComponent(mesh: mesh, materials: [material])
        entity.components.set(modelComponent)

        return entity
    }

    private func createBrightnessBar(level: Float) -> Entity {
        let container = Entity()

        // Background bar
        let bgMesh = MeshResource.generateBox(size: SIMD3<Float>(0.06, 0.008, 0.002), cornerRadius: 0.002)
        var bgMaterial = SimpleMaterial(color: UIColor.white.withAlphaComponent(0.1), isMetallic: false)
        let bgModel = ModelComponent(mesh: bgMesh, materials: [bgMaterial])

        let background = Entity()
        background.components.set(bgModel)
        container.addChild(background)

        // Fill bar
        let fillWidth = 0.06 * level
        if fillWidth > 0.001 {
            let fillMesh = MeshResource.generateBox(
                size: SIMD3<Float>(fillWidth, 0.008, 0.003),
                cornerRadius: 0.002
            )

            var fillMaterial = PhysicallyBasedMaterial()
            fillMaterial.baseColor = .init(tint: UIColor(.beacon))
            fillMaterial.emissiveColor = .init(color: UIColor(.beacon.opacity(0.5)))
            fillMaterial.emissiveIntensity = level * 0.5

            let fill = Entity()
            fill.components.set(ModelComponent(mesh: fillMesh, materials: [fillMaterial]))
            fill.position.x = -(0.06 - fillWidth) / 2
            fill.position.z = 0.001
            container.addChild(fill)
        }

        return container
    }

    // MARK: - Animation Helpers

    private func animateEntityDismissal(_ entity: Entity) {
        // Scale down and fade out
        Task {
            for i in 0..<10 {
                let progress = Float(i) / 10.0
                let scale = 1.0 - progress * 0.5
                entity.scale = SIMD3<Float>(repeating: scale)

                if var model = entity.components[ModelComponent.self],
                   var material = model.materials.first as? PhysicallyBasedMaterial {
                    material.blending = .transparent(opacity: .init(floatLiteral: Float(1.0 - progress)))
                    model.materials = [material]
                    entity.components.set(model)
                }

                try? await Task.sleep(nanoseconds: 20_000_000) // 20ms
            }

            entity.removeFromParent()
        }
    }

    // MARK: - Window Queries

    /// Gets all windows of a specific type
    func windows(ofType type: SpatialWindow.WindowType) -> [SpatialWindow] {
        activeWindows.filter { $0.windowType == type }
    }

    /// Gets the window nearest to a position
    func nearestWindow(to position: SIMD3<Float>) -> SpatialWindow? {
        activeWindows.min { a, b in
            simd_length(a.position - position) < simd_length(b.position - position)
        }
    }

    /// Checks if any windows are currently visible
    var hasVisibleWindows: Bool {
        !activeWindows.filter { $0.isVisible }.isEmpty
    }
}

/*
 *
 * h(x) >= 0. Always.
 *
 * Spatial UI respects the human in the space.
 * Windows float where they're needed.
 * Gaze reveals intention.
 * Touch confirms action.
 */
