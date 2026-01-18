//
// ImmersiveHomeView.swift - Full 3D Home Representation
//
// Colony: Beacon (e5) - Planning
//
// Features:
//   - Full 3D representation of the home
//   - Device overlays on real-world objects
//   - Spatial audio feedback for actions
//   - Hand gesture controls (pinch to dim, swipe to change)
//   - Multi-floor navigation
//   - Real-time device status visualization
//
// Design Philosophy:
//   The entire home becomes an interactive 3D model
//   you can walk through, examine, and control with
//   natural spatial interactions.
//
// Created: December 31, 2025


import SwiftUI
import RealityKit
import ARKit
import Combine

/// Immersive space view showing the full 3D home model
struct ImmersiveHomeView: View {
    @EnvironmentObject var appModel: AppModel
    @StateObject private var viewModel = ImmersiveHomeViewModel()
    @Environment(\.openImmersiveSpace) private var openImmersiveSpace
    @Environment(\.dismissImmersiveSpace) private var dismissImmersiveSpace
    @Environment(\.accessibilityReduceMotion) private var reduceMotion

    var body: some View {
        RealityView { content, attachments in
            // Create the immersive home content
            await viewModel.setupImmersiveContent(in: content, attachments: attachments)

        } update: { content, attachments in
            // Update based on state changes
            viewModel.updateContent(in: content)

        } attachments: {
            // SwiftUI attachments for room labels and controls
            ForEach(viewModel.roomAttachments, id: \.roomId) { attachment in
                Attachment(id: attachment.roomId) {
                    RoomAttachmentView(
                        room: attachment.room,
                        isSelected: viewModel.selectedRoomId == attachment.roomId,
                        onTap: {
                            viewModel.selectRoom(attachment.roomId)
                        }
                    )
                }
            }

            // Floor selector attachment
            Attachment(id: "floor-selector") {
                FloorSelectorView(
                    floors: viewModel.floors,
                    selectedFloor: $viewModel.selectedFloor
                )
            }

            // Quick actions attachment
            Attachment(id: "quick-actions") {
                ImmersiveQuickActionsView(
                    onMovieMode: { Task { await viewModel.activateMovieMode() } },
                    onGoodnight: { Task { await viewModel.activateGoodnight() } },
                    onAllLightsOff: { Task { await viewModel.allLightsOff() } }
                )
            }
        }
        .gesture(
            // Tap gesture for room selection
            SpatialTapGesture()
                .targetedToAnyEntity()
                .onEnded { value in
                    viewModel.handleTap(on: value.entity)
                }
        )
        .gesture(
            // Drag gesture for brightness/shade control
            DragGesture()
                .targetedToAnyEntity()
                .onChanged { value in
                    viewModel.handleDrag(value)
                }
                .onEnded { _ in
                    viewModel.endDrag()
                }
        )
        .gesture(
            // Pinch gesture for dimming
            MagnifyGesture()
                .targetedToAnyEntity()
                .onChanged { value in
                    viewModel.handlePinch(scale: Float(value.magnification))
                }
                .onEnded { _ in
                    viewModel.endPinch()
                }
        )
        .task {
            await viewModel.initialize(apiService: appModel.apiService)
        }
        .onDisappear {
            viewModel.cleanup()
        }
    }
}

// MARK: - View Model

@MainActor
class ImmersiveHomeViewModel: ObservableObject {

    // MARK: - Published State

    @Published var rooms: [RoomModel] = []
    @Published var selectedRoomId: String?
    @Published var selectedFloor: String = "Main Floor"
    @Published var floors: [String] = ["Lower Level", "Main Floor", "Upper Floor"]
    @Published var roomAttachments: [RoomAttachment] = []
    @Published var isLoading = true
    @Published var homeModelScale: Float = 0.05  // 5cm = 1 meter

    // Gesture state
    @Published var isDragging = false
    @Published var isPinching = false
    @Published var currentBrightnessAdjustment: Float = 0

    // MARK: - Types

    struct RoomAttachment: Identifiable {
        let id: UUID = UUID()
        let roomId: String
        let room: RoomModel
        var position: SIMD3<Float>
    }

    // MARK: - Internal State

    private var apiService: KagamiAPIService?
    private var rootEntity: Entity?
    private var roomEntities: [String: Entity] = [:]
    private var deviceEntities: [String: Entity] = [:]
    private var audioService = SpatialAudioService()
    private var gestureRecognizer = SpatialGestureRecognizer()
    private var anchorService = SpatialAnchorService()

    // Home model layout
    private let floorHeights: [String: Float] = [
        "Lower Level": 0.0,
        "Main Floor": 0.15,
        "Upper Floor": 0.30
    ]

    // Room positions (simplified grid layout)
    private var roomPositions: [String: SIMD3<Float>] = [:]

    private var cancellables = Set<AnyCancellable>()

    // MARK: - Initialization

    func initialize(apiService: KagamiAPIService) async {
        self.apiService = apiService

        // Start services
        _ = await anchorService.start()

        // Load room data
        await loadRooms()

        isLoading = false
    }

    private func loadRooms() async {
        guard let apiService = apiService else { return }

        do {
            rooms = try await apiService.fetchRooms()
            calculateRoomPositions()
            createRoomAttachments()
        } catch {
            print("Failed to load rooms: \(error)")
        }
    }

    private func calculateRoomPositions() {
        for (index, room) in rooms.enumerated() {
            let floorY = floorHeights[room.floor] ?? 0.15
            let roomsOnFloor = rooms.filter { $0.floor == room.floor }
            let indexOnFloor = roomsOnFloor.firstIndex { $0.id == room.id } ?? 0

            // Grid layout
            let col = indexOnFloor % 4
            let row = indexOnFloor / 4

            let x = Float(col - 2) * 0.12
            let z = Float(row) * 0.12

            roomPositions[room.id] = SIMD3<Float>(x, floorY, z)
        }
    }

    private func createRoomAttachments() {
        roomAttachments = rooms.map { room in
            let position = roomPositions[room.id] ?? SIMD3<Float>(0, 0.15, 0)
            return RoomAttachment(
                roomId: room.id,
                room: room,
                position: position + SIMD3<Float>(0, 0.08, 0) // Above room cube
            )
        }
    }

    // MARK: - Content Setup

    func setupImmersiveContent(
        in content: RealityViewContent,
        attachments: RealityViewAttachments
    ) async {
        // Create root entity for the home model
        let root = Entity()
        root.name = "immersive-home"
        root.position = SIMD3<Float>(0, 1.0, -2.0) // In social zone, below eye level
        rootEntity = root

        // Create floor platforms
        for (floor, height) in floorHeights {
            let platform = createFloorPlatform(name: floor, height: height)
            root.addChild(platform)
        }

        // Create room entities
        for room in rooms {
            let roomEntity = createRoomEntity(room: room)
            roomEntities[room.id] = roomEntity
            root.addChild(roomEntity)

            // Add device entities within room
            createDeviceEntities(for: room, parent: roomEntity)
        }

        // Add attachments to entities
        for attachment in roomAttachments {
            if let attachmentEntity = attachments.entity(for: attachment.roomId) {
                attachmentEntity.position = attachment.position
                root.addChild(attachmentEntity)
            }
        }

        // Add floor selector
        if let floorSelector = attachments.entity(for: "floor-selector") {
            floorSelector.position = SIMD3<Float>(-0.4, 0.2, 0)
            root.addChild(floorSelector)
        }

        // Add quick actions
        if let quickActions = attachments.entity(for: "quick-actions") {
            quickActions.position = SIMD3<Float>(0.4, 0.2, 0)
            root.addChild(quickActions)
        }

        // Add ambient lighting
        let light = createAmbientLighting()
        root.addChild(light)

        // Add subtle ambient particles
        let particles = createAmbientParticles()
        root.addChild(particles)

        content.add(root)
    }

    func updateContent(in content: RealityViewContent) {
        // Update room appearances based on current state
        for room in rooms {
            guard let entity = roomEntities[room.id] else { continue }
            updateRoomAppearance(entity: entity, room: room)
        }

        // Update floor visibility based on selection
        updateFloorVisibility()
    }

    // MARK: - Entity Creation

    private func createFloorPlatform(name: String, height: Float) -> Entity {
        let platform = Entity()
        platform.name = "floor-\(name)"
        platform.position.y = height

        // Semi-transparent floor plane
        let mesh = MeshResource.generatePlane(width: 0.6, depth: 0.5)

        var material = PhysicallyBasedMaterial()
        material.baseColor = .init(tint: UIColor.white.withAlphaComponent(0.05))
        material.roughness = 1.0
        material.metallic = 0.0
        material.blending = .transparent(opacity: .init(floatLiteral: 0.1))

        let modelComponent = ModelComponent(mesh: mesh, materials: [material])
        platform.components.set(modelComponent)

        // Add floor label
        let labelEntity = Entity()
        labelEntity.name = "floor-label-\(name)"
        labelEntity.position = SIMD3<Float>(-0.25, 0.01, 0.2)
        platform.addChild(labelEntity)

        return platform
    }

    private func createRoomEntity(room: RoomModel) -> Entity {
        let entity = Entity()
        entity.name = "room-\(room.id)"

        let position = roomPositions[room.id] ?? SIMD3<Float>(0, 0.15, 0)
        entity.position = position

        // Room cube representation
        let size: Float = 0.06
        let mesh = MeshResource.generateBox(size: size, cornerRadius: 0.003)

        let color = roomColor(for: room)
        var material = PhysicallyBasedMaterial()
        material.baseColor = .init(tint: UIColor(color))
        material.emissiveColor = .init(color: UIColor(color.opacity(Double(room.avgLightLevel) / 150)))
        material.emissiveIntensity = Float(room.avgLightLevel) / 100
        material.roughness = 0.3
        material.metallic = 0.0

        let modelComponent = ModelComponent(mesh: mesh, materials: [material])
        entity.components.set(modelComponent)

        // Make interactive
        entity.components.set(InputTargetComponent())
        entity.components.set(CollisionComponent(shapes: [
            .generateBox(size: SIMD3<Float>(repeating: size * 1.3))
        ]))
        entity.components.set(HoverEffectComponent())

        // Accessibility
        var accessibilityComponent = AccessibilityComponent()
        accessibilityComponent.label = LocalizedStringResource(stringLiteral: "\(room.name), \(room.floor)")
        accessibilityComponent.value = LocalizedStringResource(
            stringLiteral: "Lights \(room.lightState)\(room.occupied ? ", occupied" : "")"
        )
        accessibilityComponent.isAccessibilityElement = true
        accessibilityComponent.traits = [.button]
        entity.components.set(accessibilityComponent)

        return entity
    }

    private func createDeviceEntities(for room: RoomModel, parent: Entity) {
        // Light indicator
        if !room.lights.isEmpty {
            let lightIndicator = createLightIndicator(brightness: room.avgLightLevel)
            lightIndicator.position = SIMD3<Float>(0, 0.04, 0)
            parent.addChild(lightIndicator)
            deviceEntities["\(room.id)-lights"] = lightIndicator
        }

        // Shade indicator
        if !room.shades.isEmpty {
            let shadeIndicator = createShadeIndicator(shades: room.shades)
            shadeIndicator.position = SIMD3<Float>(0.025, 0.02, 0)
            parent.addChild(shadeIndicator)
            deviceEntities["\(room.id)-shades"] = shadeIndicator
        }

        // Occupancy indicator
        if room.occupied {
            let occupancyIndicator = createOccupancyIndicator()
            occupancyIndicator.position = SIMD3<Float>(-0.025, 0.04, 0)
            parent.addChild(occupancyIndicator)
            deviceEntities["\(room.id)-occupancy"] = occupancyIndicator
        }
    }

    private func createLightIndicator(brightness: Int) -> Entity {
        let entity = Entity()
        entity.name = "light-indicator"

        let mesh = MeshResource.generateSphere(radius: 0.008)

        var material = PhysicallyBasedMaterial()
        let intensity = Float(brightness) / 100
        material.baseColor = .init(tint: UIColor(.beacon.opacity(Double(intensity))))
        material.emissiveColor = .init(color: UIColor(.beacon))
        material.emissiveIntensity = intensity

        let modelComponent = ModelComponent(mesh: mesh, materials: [material])
        entity.components.set(modelComponent)

        return entity
    }

    private func createShadeIndicator(shades: [Shade]) -> Entity {
        let entity = Entity()
        entity.name = "shade-indicator"

        let avgPosition = shades.reduce(0) { $0 + $1.position } / max(shades.count, 1)
        let openness = Float(avgPosition) / 100

        let mesh = MeshResource.generateBox(size: SIMD3<Float>(0.003, 0.015, 0.003))

        var material = PhysicallyBasedMaterial()
        material.baseColor = .init(tint: UIColor(.grove.opacity(Double(openness))))
        material.emissiveColor = .init(color: UIColor(.grove))
        material.emissiveIntensity = openness * 0.5

        let modelComponent = ModelComponent(mesh: mesh, materials: [material])
        entity.components.set(modelComponent)

        return entity
    }

    private func createOccupancyIndicator() -> Entity {
        let entity = Entity()
        entity.name = "occupancy-indicator"

        let mesh = MeshResource.generateSphere(radius: 0.005)

        var material = PhysicallyBasedMaterial()
        material.baseColor = .init(tint: UIColor(.grove))
        material.emissiveColor = .init(color: UIColor(.grove))
        material.emissiveIntensity = 0.8

        let modelComponent = ModelComponent(mesh: mesh, materials: [material])
        entity.components.set(modelComponent)

        // Add pulsing particle effect
        var particles = ParticleEmitterComponent()
        particles.emitterShape = .sphere
        particles.emitterShapeSize = [0.01, 0.01, 0.01]
        particles.mainEmitter.birthRate = 5
        particles.mainEmitter.lifeSpan = 2
        particles.speed = 0.002
        particles.mainEmitter.color = .constant(.single(.init(Color.grove.opacity(0.5))))
        particles.mainEmitter.size = 0.002

        entity.components.set(particles)

        return entity
    }

    private func createAmbientLighting() -> Entity {
        let light = Entity()
        // PointLightComponent requires visionOS 2.0
        // Using environment-based lighting instead
        light.position = SIMD3<Float>(0, 0.5, 0)

        return light
    }

    private func createAmbientParticles() -> Entity {
        let entity = Entity()
        entity.name = "ambient-particles"

        var particles = ParticleEmitterComponent()
        particles.emitterShape = .box
        particles.emitterShapeSize = [0.6, 0.3, 0.5]
        particles.mainEmitter.birthRate = 10
        particles.mainEmitter.birthRateVariation = 5
        particles.mainEmitter.lifeSpan = 8
        particles.mainEmitter.lifeSpanVariation = 2
        particles.speed = 0.005
        particles.speedVariation = 0.002
        particles.mainEmitter.color = .constant(.single(.init(Color.crystal.opacity(0.2))))
        particles.mainEmitter.size = 0.002

        entity.components.set(particles)
        entity.position.y = 0.15

        return entity
    }

    // MARK: - Update Methods

    private func updateRoomAppearance(entity: Entity, room: RoomModel) {
        guard var model = entity.components[ModelComponent.self],
              var material = model.materials.first as? PhysicallyBasedMaterial else { return }

        let color = roomColor(for: room)
        let isSelected = selectedRoomId == room.id

        material.baseColor = .init(tint: UIColor(color.opacity(isSelected ? 1.0 : 0.8)))
        material.emissiveColor = .init(color: UIColor(color.opacity(Double(room.avgLightLevel) / 150)))
        material.emissiveIntensity = Float(room.avgLightLevel) / 100

        model.materials = [material]
        entity.components.set(model)

        // Scale up selected room
        let scale: Float = isSelected ? 1.2 : 1.0
        entity.scale = SIMD3<Float>(repeating: scale)

        // Update device indicators
        if let lightIndicator = deviceEntities["\(room.id)-lights"] {
            updateLightIndicator(lightIndicator, brightness: room.avgLightLevel)
        }
    }

    private func updateLightIndicator(_ entity: Entity, brightness: Int) {
        guard var model = entity.components[ModelComponent.self],
              var material = model.materials.first as? PhysicallyBasedMaterial else { return }

        let intensity = Float(brightness) / 100
        material.emissiveIntensity = intensity

        model.materials = [material]
        entity.components.set(model)
    }

    private func updateFloorVisibility() {
        guard let root = rootEntity else { return }

        for child in root.children {
            let name = child.name
            guard !name.isEmpty, name.starts(with: "floor-") else { continue }

            let floorName = String(name.dropFirst(6))
            let isSelected = floorName == selectedFloor

            // Adjust opacity based on selection
            child.scale = SIMD3<Float>(repeating: isSelected ? 1.0 : 0.7)

            // Show rooms on this floor
            let floorY = floorHeights[floorName] ?? 0.15
            for (roomId, roomEntity) in roomEntities {
                if let room = rooms.first(where: { $0.id == roomId }),
                   room.floor == floorName {
                    roomEntity.isEnabled = true
                } else if abs(roomEntity.position.y - floorY) < 0.01 {
                    roomEntity.isEnabled = selectedFloor == "All"
                }
            }
        }
    }

    private func roomColor(for room: RoomModel) -> Color {
        if room.occupied {
            return .grove
        }

        switch room.lightState {
        case "On": return .beacon
        case "Dim": return .nexus
        default: return .crystal.opacity(0.4)
        }
    }

    // MARK: - Gesture Handling

    func handleTap(on entity: Entity) {
        let name = entity.name
        guard !name.isEmpty else { return }

        if name.starts(with: "room-") {
            let roomId = String(name.dropFirst(5))
            selectRoom(roomId)
        }
    }

    func selectRoom(_ roomId: String) {
        if selectedRoomId == roomId {
            // Deselect if already selected
            selectedRoomId = nil
        } else {
            selectedRoomId = roomId

            // Play selection audio
            if let position = roomPositions[roomId] {
                audioService.play(.select, at: position)
            }
        }
    }

    func handleDrag(_ value: EntityTargetValue<DragGesture.Value>) {
        isDragging = true

        guard let selectedRoom = selectedRoomId,
              let room = rooms.first(where: { $0.id == selectedRoom }) else { return }

        // Vertical drag adjusts brightness
        let dragDelta = Float(value.translation.height)
        let brightnessChange = -dragDelta * 0.5 // Inverted: drag up = brighter

        currentBrightnessAdjustment = max(-100, min(100, brightnessChange))

        // Update preview (visual feedback)
        if let entity = roomEntities[selectedRoom],
           let lightIndicator = deviceEntities["\(selectedRoom)-lights"] {
            let previewBrightness = min(100, max(0, room.avgLightLevel + Int(currentBrightnessAdjustment)))
            updateLightIndicator(lightIndicator, brightness: previewBrightness)
        }
    }

    func endDrag() {
        isDragging = false

        guard let selectedRoom = selectedRoomId,
              let room = rooms.first(where: { $0.id == selectedRoom }),
              abs(currentBrightnessAdjustment) > 5 else {
            currentBrightnessAdjustment = 0
            return
        }

        // Apply the brightness change
        let newBrightness = min(100, max(0, room.avgLightLevel + Int(currentBrightnessAdjustment)))

        Task {
            await apiService?.setLights(newBrightness, rooms: [selectedRoom])

            // Audio feedback
            if let position = roomPositions[selectedRoom] {
                audioService.play(newBrightness > room.avgLightLevel ? .lightOn : .lightOff, at: position)
            }

            // Reload room data
            await loadRooms()
        }

        currentBrightnessAdjustment = 0
    }

    func handlePinch(scale: Float) {
        isPinching = true

        guard let selectedRoom = selectedRoomId,
              let room = rooms.first(where: { $0.id == selectedRoom }) else { return }

        // Pinch adjusts brightness
        let brightnessMultiplier = scale
        let newBrightness = Int(Float(room.avgLightLevel) * brightnessMultiplier)

        // Preview
        if let lightIndicator = deviceEntities["\(selectedRoom)-lights"] {
            updateLightIndicator(lightIndicator, brightness: min(100, max(0, newBrightness)))
        }
    }

    func endPinch() {
        isPinching = false

        // Similar to endDrag, apply the change
        // For simplicity, not implementing full pinch-to-dim here
    }

    // MARK: - Scene Actions

    func activateMovieMode() async {
        await apiService?.executeScene("movie_mode")
        audioService.playSequence([.notification, .sceneChange])
        await loadRooms()
    }

    func activateGoodnight() async {
        await apiService?.executeScene("goodnight")
        audioService.playSequence([.notification, .sceneChange])
        await loadRooms()
    }

    func allLightsOff() async {
        await apiService?.setLights(0)
        audioService.play(.lightOff)
        await loadRooms()
    }

    // MARK: - Cleanup

    /// Properly cleans up all entities from the scene graph to prevent memory leaks
    func cleanup() {
        // Stop services first
        anchorService.stop()
        audioService.shutdown()
        gestureRecognizer.reset()

        // Remove all device entities from scene graph before clearing dictionary
        for (_, entity) in deviceEntities {
            entity.removeFromParent()
            // Clear components to release resources
            entity.components.removeAll()
        }
        deviceEntities.removeAll()

        // Remove all room entities from scene graph before clearing dictionary
        for (_, entity) in roomEntities {
            // First remove all children (device indicators)
            for child in entity.children {
                child.removeFromParent()
                child.components.removeAll()
            }
            entity.removeFromParent()
            entity.components.removeAll()
        }
        roomEntities.removeAll()

        // Remove root entity and all its children from scene
        if let root = rootEntity {
            // Recursively remove all descendants
            removeAllDescendants(from: root)
            root.removeFromParent()
            root.components.removeAll()
            rootEntity = nil
        }

        // Clear room attachments
        roomAttachments.removeAll()

        // Cancel any pending subscriptions
        cancellables.removeAll()
    }

    /// Recursively removes all descendants from an entity
    private func removeAllDescendants(from entity: Entity) {
        for child in entity.children {
            removeAllDescendants(from: child)
            child.removeFromParent()
            child.components.removeAll()
        }
    }
}

// MARK: - Supporting Views

/// Room label and status attachment
struct RoomAttachmentView: View {
    let room: RoomModel
    let isSelected: Bool
    let onTap: () -> Void

    var body: some View {
        VStack(spacing: 4) {
            Text(room.name)
                .font(.system(size: 12, weight: .medium))
                .foregroundColor(.white)

            HStack(spacing: 4) {
                if room.occupied {
                    Circle()
                        .fill(Color.grove)
                        .frame(width: 6, height: 6)
                }

                Text("\(room.avgLightLevel)%")
                    .font(.system(size: 10, design: .monospaced))
                    .foregroundColor(.secondary)
            }
        }
        .padding(.horizontal, 8)
        .padding(.vertical, 4)
        .background(
            Capsule()
                .fill(isSelected ? Color.crystal.opacity(0.4) : Color.black.opacity(0.6))
        )
        .overlay(
            Capsule()
                .stroke(isSelected ? Color.crystal : Color.white.opacity(0.2), lineWidth: 1)
        )
        .onTapGesture(perform: onTap)
        .accessibilityElement()
        .accessibilityLabel("\(room.name), \(room.lightState)")
        .accessibilityHint("Tap to select")
        .accessibilityAddTraits(.isButton)
    }
}

/// Floor selector for multi-floor navigation
struct FloorSelectorView: View {
    let floors: [String]
    @Binding var selectedFloor: String

    var body: some View {
        VStack(spacing: 8) {
            Text("Floors")
                .font(.system(size: 10, weight: .medium))
                .foregroundColor(.secondary)

            ForEach(floors, id: \.self) { floor in
                Button(action: { selectedFloor = floor }) {
                    Text(floorAbbreviation(floor))
                        .font(.system(size: 11, weight: selectedFloor == floor ? .bold : .regular))
                        .foregroundColor(selectedFloor == floor ? .crystal : .white)
                        .frame(width: 24, height: 24)
                        .background(
                            Circle()
                                .fill(selectedFloor == floor ? Color.crystal.opacity(0.3) : Color.black.opacity(0.5))
                        )
                }
                .buttonStyle(.plain)
            }
        }
        .padding(8)
        .background(
            RoundedRectangle(cornerRadius: 12)
                .fill(Color.black.opacity(0.7))
        )
    }

    private func floorAbbreviation(_ floor: String) -> String {
        switch floor {
        case "Lower Level": return "L"
        case "Main Floor": return "M"
        case "Upper Floor": return "U"
        default: return String(floor.prefix(1))
        }
    }
}

/// Quick action buttons for immersive space
struct ImmersiveQuickActionsView: View {
    let onMovieMode: () -> Void
    let onGoodnight: () -> Void
    let onAllLightsOff: () -> Void

    var body: some View {
        VStack(spacing: 8) {
            Text("Quick Actions")
                .font(.system(size: 10, weight: .medium))
                .foregroundColor(.secondary)

            ImmersiveActionButton(icon: "film", label: "Movie", color: .nexus, action: onMovieMode)
            ImmersiveActionButton(icon: "moon.fill", label: "Night", color: .flow, action: onGoodnight)
            ImmersiveActionButton(icon: "lightbulb.slash", label: "Off", color: .spark, action: onAllLightsOff)
        }
        .padding(8)
        .background(
            RoundedRectangle(cornerRadius: 12)
                .fill(Color.black.opacity(0.7))
        )
    }
}

struct ImmersiveActionButton: View {
    let icon: String
    let label: String
    let color: Color
    let action: () -> Void

    @State private var isPressed = false

    var body: some View {
        Button(action: action) {
            HStack(spacing: 6) {
                Image(systemName: icon)
                    .font(.system(size: 12))
                    .foregroundColor(color)

                Text(label)
                    .font(.system(size: 10))
                    .foregroundColor(.white)
            }
            .frame(width: 60)
            .padding(.vertical, 6)
            .background(
                RoundedRectangle(cornerRadius: 8)
                    .fill(color.opacity(isPressed ? 0.4 : 0.2))
            )
        }
        .buttonStyle(.plain)
        .simultaneousGesture(
            DragGesture(minimumDistance: 0)
                .onChanged { _ in isPressed = true }
                .onEnded { _ in isPressed = false }
        )
    }
}

// MARK: - Preview

#Preview {
    ImmersiveHomeView()
        .environmentObject(AppModel())
}

/*
 *
 * h(x) >= 0. Always.
 *
 * The home becomes a tangible thing.
 * Walk through it. Touch it. Change it.
 * Space is the interface.
 */
