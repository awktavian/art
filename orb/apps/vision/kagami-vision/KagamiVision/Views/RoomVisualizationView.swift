//
// RoomVisualizationView.swift - Detailed Room Device Visualization
//
// Colony: Nexus (e4) - Integration
//
// Features:
//   - Show room with device placements
//   - Real-time status overlays
//   - Tap-to-control interactions
//   - Scene preview before activation
//   - Device grouping and organization
//   - Animated state transitions
//
// Design Philosophy:
//   A single room becomes an explorable space.
//   Each device is positioned in 3D relative to
//   its actual location in the physical room.
//   Control flows naturally from observation.
//
// Created: December 31, 2025


import SwiftUI
import RealityKit
import ARKit
import Combine

/// Detailed room visualization with interactive device controls
struct RoomVisualizationView: View {
    let room: RoomModel
    @EnvironmentObject var appModel: AppModel
    @StateObject private var viewModel = RoomVisualizationViewModel()
    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        ZStack {
            // 3D Room Content
            RealityView { content, attachments in
                await viewModel.setupRoomContent(
                    room: room,
                    in: content,
                    attachments: attachments
                )

            } update: { content, attachments in
                viewModel.updateContent(in: content)

            } attachments: {
                // Device control attachments
                ForEach(viewModel.deviceAttachments, id: \.deviceId) { attachment in
                    Attachment(id: attachment.deviceId) {
                        DeviceControlAttachment(
                            device: attachment,
                            onAction: { action in
                                Task {
                                    await viewModel.executeDeviceAction(
                                        deviceId: attachment.deviceId,
                                        action: action
                                    )
                                }
                            }
                        )
                    }
                }

                // Scene preview attachment
                Attachment(id: "scene-preview") {
                    ScenePreviewView(
                        previewState: viewModel.scenePreviewState,
                        onConfirm: {
                            Task { await viewModel.confirmSceneActivation() }
                        },
                        onCancel: { viewModel.cancelScenePreview() }
                    )
                    .opacity(viewModel.isPreviewingScene ? 1 : 0)
                }

                // Room info header
                Attachment(id: "room-header") {
                    RoomHeaderView(
                        room: room,
                        onClose: { dismiss() }
                    )
                }
            }
            .gesture(
                SpatialTapGesture()
                    .targetedToAnyEntity()
                    .onEnded { value in
                        viewModel.handleTap(on: value.entity)
                    }
            )
            .gesture(
                DragGesture()
                    .targetedToAnyEntity()
                    .onChanged { value in
                        viewModel.handleDrag(value)
                    }
                    .onEnded { value in
                        viewModel.endDrag(value)
                    }
            )

            // Loading overlay
            if viewModel.isLoading {
                ProgressView()
                    .scaleEffect(1.5)
                    .frame(maxWidth: .infinity, maxHeight: .infinity)
                    .background(Color.black.opacity(0.5))
            }
        }
        .task {
            await viewModel.initialize(room: room, apiService: appModel.apiService)
        }
        .onDisappear {
            viewModel.cleanup()
        }
    }
}

// MARK: - View Model

@MainActor
class RoomVisualizationViewModel: ObservableObject {

    // MARK: - Published State

    @Published var deviceAttachments: [DeviceAttachment] = []
    @Published var isLoading = true
    @Published var isPreviewingScene = false
    @Published var scenePreviewState: ScenePreviewState?
    @Published var selectedDeviceId: String?

    // MARK: - Types

    struct DeviceAttachment: Identifiable {
        let id: UUID = UUID()
        let deviceId: String
        let deviceType: DeviceType
        let deviceName: String
        var state: DeviceState
        var position: SIMD3<Float>
        var entity: Entity?

        enum DeviceType {
            case light
            case shade
            case audioZone
            case thermostat
        }

        struct DeviceState {
            var level: Int  // 0-100 for lights/shades
            var isOn: Bool
            var additionalInfo: String?
        }
    }

    struct ScenePreviewState {
        let sceneName: String
        let changes: [SceneChange]

        struct SceneChange {
            let deviceName: String
            let currentState: String
            let newState: String
        }
    }

    // MARK: - Internal State

    private var room: RoomModel?
    private var apiService: KagamiAPIService?
    private var rootEntity: Entity?
    private var deviceEntities: [String: Entity] = [:]
    private var audioService = SpatialAudioService()
    private var pendingSceneAction: String?

    // Room dimensions (scaled)
    private let roomScale: Float = 0.1  // 10cm = 1m
    private let roomSize: SIMD3<Float> = SIMD3<Float>(0.4, 0.25, 0.3)

    // Device positions within room
    private var devicePositions: [String: SIMD3<Float>] = [:]

    // MARK: - Initialization

    func initialize(room: RoomModel, apiService: KagamiAPIService) async {
        self.room = room
        self.apiService = apiService

        calculateDevicePositions(for: room)
        createDeviceAttachments(for: room)

        isLoading = false
    }

    private func calculateDevicePositions(for room: RoomModel) {
        var positions: [String: SIMD3<Float>] = [:]

        // Position lights in a grid on the ceiling
        for (index, light) in room.lights.enumerated() {
            let col = index % 3
            let row = index / 3
            let x = Float(col - 1) * 0.1
            let z = Float(row) * 0.1 - 0.05
            positions["light-\(light.id)"] = SIMD3<Float>(x, roomSize.y * 0.4, z)
        }

        // Position shades along one wall
        for (index, shade) in room.shades.enumerated() {
            let x = Float(index - room.shades.count / 2) * 0.08
            positions["shade-\(shade.id)"] = SIMD3<Float>(x, roomSize.y * 0.2, -roomSize.z / 2 + 0.02)
        }

        // Audio zone in corner
        if let audio = room.audioZone {
            positions["audio-\(audio.id)"] = SIMD3<Float>(roomSize.x / 2 - 0.05, 0, -roomSize.z / 2 + 0.05)
        }

        // Thermostat on wall
        if room.hvac != nil {
            positions["hvac"] = SIMD3<Float>(-roomSize.x / 2 + 0.02, roomSize.y * 0.15, 0)
        }

        devicePositions = positions
    }

    private func createDeviceAttachments(for room: RoomModel) {
        var attachments: [DeviceAttachment] = []

        // Lights
        for light in room.lights {
            let position = devicePositions["light-\(light.id)"] ?? SIMD3<Float>(0, 0.1, 0)
            attachments.append(DeviceAttachment(
                deviceId: "light-\(light.id)",
                deviceType: .light,
                deviceName: light.name,
                state: DeviceAttachment.DeviceState(
                    level: light.level,
                    isOn: light.isOn
                ),
                position: position
            ))
        }

        // Shades
        for shade in room.shades {
            let position = devicePositions["shade-\(shade.id)"] ?? SIMD3<Float>(0, 0.08, -0.1)
            attachments.append(DeviceAttachment(
                deviceId: "shade-\(shade.id)",
                deviceType: .shade,
                deviceName: shade.name,
                state: DeviceAttachment.DeviceState(
                    level: shade.position,
                    isOn: shade.position > 0
                ),
                position: position
            ))
        }

        // Audio zone
        if let audio = room.audioZone {
            let position = devicePositions["audio-\(audio.id)"] ?? SIMD3<Float>(0.15, 0, -0.1)
            attachments.append(DeviceAttachment(
                deviceId: "audio-\(audio.id)",
                deviceType: .audioZone,
                deviceName: audio.name,
                state: DeviceAttachment.DeviceState(
                    level: audio.volume,
                    isOn: audio.isActive,
                    additionalInfo: audio.source
                ),
                position: position
            ))
        }

        // HVAC
        if let hvac = room.hvac {
            let position = devicePositions["hvac"] ?? SIMD3<Float>(-0.15, 0.06, 0)
            attachments.append(DeviceAttachment(
                deviceId: "hvac",
                deviceType: .thermostat,
                deviceName: "Thermostat",
                state: DeviceAttachment.DeviceState(
                    level: Int(hvac.targetTemp),
                    isOn: hvac.mode != "off",
                    additionalInfo: "\(Int(hvac.currentTemp))F / \(hvac.mode)"
                ),
                position: position
            ))
        }

        deviceAttachments = attachments
    }

    // MARK: - Content Setup

    func setupRoomContent(
        room: RoomModel,
        in content: RealityViewContent,
        attachments: RealityViewAttachments
    ) async {
        // Create root entity
        let root = Entity()
        root.name = "room-\(room.id)"
        root.position = SIMD3<Float>(0, 1.2, -1.0)  // Personal zone
        rootEntity = root

        // Create room structure
        let roomStructure = createRoomStructure()
        root.addChild(roomStructure)

        // Create device entities
        for attachment in deviceAttachments {
            let entity = createDeviceEntity(for: attachment)
            deviceEntities[attachment.deviceId] = entity
            root.addChild(entity)

            // Add SwiftUI attachment
            if let attachmentEntity = attachments.entity(for: attachment.deviceId) {
                attachmentEntity.position = attachment.position + SIMD3<Float>(0, 0.05, 0)
                root.addChild(attachmentEntity)
            }
        }

        // Add room header
        if let headerAttachment = attachments.entity(for: "room-header") {
            headerAttachment.position = SIMD3<Float>(0, roomSize.y / 2 + 0.08, 0)
            root.addChild(headerAttachment)
        }

        // Add scene preview
        if let previewAttachment = attachments.entity(for: "scene-preview") {
            previewAttachment.position = SIMD3<Float>(0, 0, 0.2)
            root.addChild(previewAttachment)
        }

        // Add lighting
        let light = createRoomLighting()
        root.addChild(light)

        content.add(root)
    }

    func updateContent(in content: RealityViewContent) {
        // Update device entity appearances
        for attachment in deviceAttachments {
            guard let entity = deviceEntities[attachment.deviceId] else { continue }
            updateDeviceEntityAppearance(entity, state: attachment.state, type: attachment.deviceType)
        }
    }

    // MARK: - Entity Creation

    private func createRoomStructure() -> Entity {
        let structure = Entity()
        structure.name = "room-structure"

        // Floor
        let floorMesh = MeshResource.generatePlane(width: roomSize.x, depth: roomSize.z)
        var floorMaterial = PhysicallyBasedMaterial()
        floorMaterial.baseColor = .init(tint: UIColor(Color(white: 0.15).opacity(0.8)))
        floorMaterial.roughness = 0.8
        floorMaterial.metallic = 0.0

        let floor = Entity()
        floor.name = "floor"
        floor.components.set(ModelComponent(mesh: floorMesh, materials: [floorMaterial]))
        floor.position.y = -roomSize.y / 2
        structure.addChild(floor)

        // Walls (transparent glass effect)
        let wallMaterial = createGlassMaterial(opacity: 0.1)

        // Back wall
        let backWallMesh = MeshResource.generatePlane(width: roomSize.x, height: roomSize.y)
        let backWall = Entity()
        backWall.name = "back-wall"
        backWall.components.set(ModelComponent(mesh: backWallMesh, materials: [wallMaterial]))
        backWall.position = SIMD3<Float>(0, 0, -roomSize.z / 2)
        backWall.orientation = simd_quatf(angle: 0, axis: [0, 1, 0])
        structure.addChild(backWall)

        // Side walls
        let sideWallMesh = MeshResource.generatePlane(width: roomSize.z, height: roomSize.y)

        let leftWall = Entity()
        leftWall.name = "left-wall"
        leftWall.components.set(ModelComponent(mesh: sideWallMesh, materials: [wallMaterial]))
        leftWall.position = SIMD3<Float>(-roomSize.x / 2, 0, 0)
        leftWall.orientation = simd_quatf(angle: .pi / 2, axis: [0, 1, 0])
        structure.addChild(leftWall)

        let rightWall = Entity()
        rightWall.name = "right-wall"
        rightWall.components.set(ModelComponent(mesh: sideWallMesh, materials: [wallMaterial]))
        rightWall.position = SIMD3<Float>(roomSize.x / 2, 0, 0)
        rightWall.orientation = simd_quatf(angle: -.pi / 2, axis: [0, 1, 0])
        structure.addChild(rightWall)

        // Ceiling grid lines
        let ceilingGrid = createCeilingGrid()
        ceilingGrid.position.y = roomSize.y / 2
        structure.addChild(ceilingGrid)

        return structure
    }

    private func createGlassMaterial(opacity: Double) -> PhysicallyBasedMaterial {
        var material = PhysicallyBasedMaterial()
        material.baseColor = .init(tint: UIColor(.crystal.opacity(opacity)))
        material.roughness = 0.1
        material.metallic = 0.0
        material.blending = .transparent(opacity: .init(floatLiteral: Float(opacity)))
        return material
    }

    private func createCeilingGrid() -> Entity {
        let grid = Entity()
        grid.name = "ceiling-grid"

        let gridSize: Int = 5
        let spacing = roomSize.x / Float(gridSize)

        let lineMaterial = createGlassMaterial(opacity: 0.15)

        for i in 0...gridSize {
            // Horizontal lines
            let hLine = Entity()
            let hMesh = MeshResource.generateBox(size: SIMD3<Float>(roomSize.x, 0.001, 0.002))
            hLine.components.set(ModelComponent(mesh: hMesh, materials: [lineMaterial]))
            hLine.position.z = Float(i) * spacing - roomSize.z / 2
            grid.addChild(hLine)

            // Vertical lines
            let vLine = Entity()
            let vMesh = MeshResource.generateBox(size: SIMD3<Float>(0.002, 0.001, roomSize.z))
            vLine.components.set(ModelComponent(mesh: vMesh, materials: [lineMaterial]))
            vLine.position.x = Float(i) * spacing - roomSize.x / 2
            grid.addChild(vLine)
        }

        return grid
    }

    private func createDeviceEntity(for attachment: DeviceAttachment) -> Entity {
        let entity = Entity()
        entity.name = attachment.deviceId
        entity.position = attachment.position

        let (mesh, material) = deviceMeshAndMaterial(for: attachment)
        entity.components.set(ModelComponent(mesh: mesh, materials: [material]))

        // Make interactive
        entity.components.set(InputTargetComponent())
        entity.components.set(CollisionComponent(shapes: [.generateSphere(radius: 0.025)]))
        entity.components.set(HoverEffectComponent())

        // Accessibility
        var accessibilityComponent = AccessibilityComponent()
        accessibilityComponent.label = LocalizedStringResource(stringLiteral: attachment.deviceName)
        accessibilityComponent.value = LocalizedStringResource(stringLiteral: deviceStateDescription(attachment))
        accessibilityComponent.isAccessibilityElement = true
        accessibilityComponent.traits = [.button]
        entity.components.set(accessibilityComponent)

        return entity
    }

    private func deviceMeshAndMaterial(for attachment: DeviceAttachment) -> (MeshResource, PhysicallyBasedMaterial) {
        var material = PhysicallyBasedMaterial()

        switch attachment.deviceType {
        case .light:
            let mesh = MeshResource.generateSphere(radius: 0.015)
            let intensity = Float(attachment.state.level) / 100
            material.baseColor = .init(tint: UIColor(.beacon.opacity(Double(max(0.3, intensity)))))
            material.emissiveColor = .init(color: UIColor(.beacon))
            material.emissiveIntensity = intensity
            return (mesh, material)

        case .shade:
            let height = 0.04 * (1 - Float(attachment.state.level) / 100)
            let mesh = MeshResource.generateBox(size: SIMD3<Float>(0.04, max(0.005, height), 0.003))
            material.baseColor = .init(tint: UIColor(.grove.opacity(0.8)))
            material.roughness = 0.6
            return (mesh, material)

        case .audioZone:
            let mesh = MeshResource.generateCylinder(height: 0.02, radius: 0.012)
            let intensity: Float = attachment.state.isOn ? 0.6 : 0.1
            material.baseColor = .init(tint: UIColor(.nexus.opacity(Double(intensity))))
            material.emissiveColor = .init(color: UIColor(.nexus))
            material.emissiveIntensity = intensity
            return (mesh, material)

        case .thermostat:
            let mesh = MeshResource.generateBox(size: SIMD3<Float>(0.025, 0.035, 0.005), cornerRadius: 0.003)
            material.baseColor = .init(tint: UIColor(.flow.opacity(0.8)))
            return (mesh, material)
        }
    }

    private func deviceStateDescription(_ attachment: DeviceAttachment) -> String {
        switch attachment.deviceType {
        case .light:
            return attachment.state.isOn ? "\(attachment.state.level)% brightness" : "Off"
        case .shade:
            return "\(attachment.state.level)% open"
        case .audioZone:
            return attachment.state.isOn ? "Playing: \(attachment.state.additionalInfo ?? "Unknown")" : "Off"
        case .thermostat:
            return attachment.state.additionalInfo ?? "\(attachment.state.level)F"
        }
    }

    private func updateDeviceEntityAppearance(
        _ entity: Entity,
        state: DeviceAttachment.DeviceState,
        type: DeviceAttachment.DeviceType
    ) {
        guard var model = entity.components[ModelComponent.self],
              var material = model.materials.first as? PhysicallyBasedMaterial else { return }

        switch type {
        case .light:
            let intensity = Float(state.level) / 100
            material.emissiveIntensity = intensity

        case .shade:
            // Update shade height
            let height = 0.04 * (1 - Float(state.level) / 100)
            let newMesh = MeshResource.generateBox(size: SIMD3<Float>(0.04, max(0.005, height), 0.003))
            model.mesh = newMesh

        case .audioZone:
            let intensity: Float = state.isOn ? 0.6 : 0.1
            material.emissiveIntensity = intensity

        case .thermostat:
            // Color based on heating/cooling
            if let info = state.additionalInfo {
                if info.contains("heat") {
                    material.baseColor = .init(tint: UIColor(.spark.opacity(0.8)))
                } else if info.contains("cool") {
                    material.baseColor = .init(tint: UIColor(.flow.opacity(0.8)))
                }
            }
        }

        model.materials = [material]
        entity.components.set(model)
    }

    private func createRoomLighting() -> Entity {
        let light = Entity()
        // PointLightComponent requires visionOS 2.0
        // Using environment-based lighting instead
        light.position = SIMD3<Float>(0, roomSize.y / 2 - 0.02, 0)

        return light
    }

    // MARK: - Gesture Handling

    func handleTap(on entity: Entity) {
        let deviceId = entity.name
        guard !deviceId.isEmpty else { return }

        if deviceId.starts(with: "light-") || deviceId.starts(with: "shade-") {
            selectedDeviceId = deviceId
            audioService.play(.tap, at: entity.position)
        }
    }

    func handleDrag(_ value: EntityTargetValue<DragGesture.Value>) {
        let deviceId = value.entity.name
        guard !deviceId.isEmpty,
              let index = deviceAttachments.firstIndex(where: { $0.deviceId == deviceId }) else { return }

        let attachment = deviceAttachments[index]

        // Vertical drag adjusts level
        let dragDelta = Float(value.translation.height)
        let levelChange = -dragDelta * 2  // Inverted

        switch attachment.deviceType {
        case .light, .shade:
            let newLevel = max(0, min(100, attachment.state.level + Int(levelChange)))
            deviceAttachments[index].state.level = newLevel
            deviceAttachments[index].state.isOn = newLevel > 0

        default:
            break
        }
    }

    func endDrag(_ value: EntityTargetValue<DragGesture.Value>) {
        let deviceId = value.entity.name
        guard !deviceId.isEmpty,
              let attachment = deviceAttachments.first(where: { $0.deviceId == deviceId }),
              let room = room else { return }

        // Apply the change
        Task {
            switch attachment.deviceType {
            case .light:
                await apiService?.setLights(attachment.state.level, rooms: [room.id])
                audioService.play(attachment.state.isOn ? .lightOn : .lightOff, at: attachment.position)

            case .shade:
                let action = attachment.state.level > 50 ? "open" : "close"
                await apiService?.controlShades(action, rooms: [room.id])
                audioService.play(attachment.state.level > 50 ? .shadeOpen : .shadeClose, at: attachment.position)

            default:
                break
            }
        }
    }

    // MARK: - Device Actions

    func executeDeviceAction(deviceId: String, action: DeviceAction) async {
        guard let room = room,
              let index = deviceAttachments.firstIndex(where: { $0.deviceId == deviceId }) else { return }

        let attachment = deviceAttachments[index]

        switch action {
        case .setLevel(let level):
            deviceAttachments[index].state.level = level
            deviceAttachments[index].state.isOn = level > 0

            switch attachment.deviceType {
            case .light:
                await apiService?.setLights(level, rooms: [room.id])
            case .shade:
                let shadeAction = level > 50 ? "open" : "close"
                await apiService?.controlShades(shadeAction, rooms: [room.id])
            default:
                break
            }

        case .toggle:
            let newState = !attachment.state.isOn
            deviceAttachments[index].state.isOn = newState

            if attachment.deviceType == .light {
                await apiService?.setLights(newState ? 100 : 0, rooms: [room.id])
            }

        case .turnOn:
            deviceAttachments[index].state.isOn = true
            deviceAttachments[index].state.level = 100

        case .turnOff:
            deviceAttachments[index].state.isOn = false
            deviceAttachments[index].state.level = 0
        }

        audioService.play(.select, at: attachment.position)
    }

    enum DeviceAction {
        case setLevel(Int)
        case toggle
        case turnOn
        case turnOff
    }

    // MARK: - Scene Preview

    func previewScene(_ sceneName: String) {
        guard let room = room else { return }

        var changes: [ScenePreviewState.SceneChange] = []

        switch sceneName {
        case "movie_mode":
            for light in room.lights {
                changes.append(ScenePreviewState.SceneChange(
                    deviceName: light.name,
                    currentState: "\(light.level)%",
                    newState: "0%"
                ))
            }
            for shade in room.shades {
                changes.append(ScenePreviewState.SceneChange(
                    deviceName: shade.name,
                    currentState: "\(shade.position)% open",
                    newState: "0% open"
                ))
            }

        case "bright":
            for light in room.lights {
                changes.append(ScenePreviewState.SceneChange(
                    deviceName: light.name,
                    currentState: "\(light.level)%",
                    newState: "100%"
                ))
            }

        default:
            break
        }

        scenePreviewState = ScenePreviewState(sceneName: sceneName, changes: changes)
        pendingSceneAction = sceneName
        isPreviewingScene = true
    }

    func confirmSceneActivation() async {
        guard let sceneName = pendingSceneAction else { return }

        await apiService?.executeScene(sceneName)
        audioService.playSequence([.notification, .sceneChange])

        isPreviewingScene = false
        pendingSceneAction = nil
        scenePreviewState = nil
    }

    func cancelScenePreview() {
        isPreviewingScene = false
        pendingSceneAction = nil
        scenePreviewState = nil
    }

    // MARK: - Cleanup

    func cleanup() {
        audioService.shutdown()
        deviceEntities.removeAll()
    }
}

// MARK: - Supporting Views

/// Device control attachment view
struct DeviceControlAttachment: View {
    let device: RoomVisualizationViewModel.DeviceAttachment
    let onAction: (RoomVisualizationViewModel.DeviceAction) -> Void

    @State private var sliderValue: Double = 0

    var body: some View {
        VStack(spacing: 8) {
            // Device name and status
            HStack {
                Text(device.deviceName)
                    .font(.system(size: 11, weight: .medium))
                    .foregroundColor(.white)

                Spacer()

                Circle()
                    .fill(device.state.isOn ? Color.grove : Color.secondary.opacity(0.3))
                    .frame(width: 6, height: 6)
            }

            // Device-specific controls
            switch device.deviceType {
            case .light, .shade:
                DeviceLevelSlider(
                    level: device.state.level,
                    color: device.deviceType == .light ? .beacon : .grove,
                    onChange: { newLevel in
                        onAction(.setLevel(newLevel))
                    }
                )

            case .audioZone:
                HStack(spacing: 12) {
                    Button(action: { onAction(.toggle) }) {
                        Image(systemName: device.state.isOn ? "speaker.wave.2.fill" : "speaker.slash.fill")
                            .font(.system(size: 14))
                            .foregroundColor(device.state.isOn ? .nexus : .secondary)
                    }
                    .buttonStyle(.plain)

                    if let source = device.state.additionalInfo {
                        Text(source)
                            .font(.system(size: 9))
                            .foregroundColor(.secondary)
                            .lineLimit(1)
                    }
                }

            case .thermostat:
                if let info = device.state.additionalInfo {
                    Text(info)
                        .font(.system(size: 10, design: .monospaced))
                        .foregroundColor(.flow)
                }
            }
        }
        .padding(10)
        .frame(width: 120)
        .background(
            RoundedRectangle(cornerRadius: 10)
                .fill(Color.black.opacity(0.8))
        )
        .overlay(
            RoundedRectangle(cornerRadius: 10)
                .stroke(Color.white.opacity(0.2), lineWidth: 0.5)
        )
    }
}

/// Slider for device level control
struct DeviceLevelSlider: View {
    let level: Int
    let color: Color
    let onChange: (Int) -> Void

    @State private var dragOffset: CGFloat = 0
    @State private var isDragging = false

    private let sliderWidth: CGFloat = 100
    private let sliderHeight: CGFloat = 8

    var body: some View {
        GeometryReader { geometry in
            ZStack(alignment: .leading) {
                // Background track
                RoundedRectangle(cornerRadius: sliderHeight / 2)
                    .fill(Color.white.opacity(0.1))
                    .frame(height: sliderHeight)

                // Fill
                RoundedRectangle(cornerRadius: sliderHeight / 2)
                    .fill(
                        LinearGradient(
                            colors: [color.opacity(0.5), color],
                            startPoint: .leading,
                            endPoint: .trailing
                        )
                    )
                    .frame(width: CGFloat(level) / 100 * geometry.size.width, height: sliderHeight)

                // Thumb
                Circle()
                    .fill(color)
                    .frame(width: 14, height: 14)
                    .shadow(color: color.opacity(0.5), radius: 4)
                    .offset(x: CGFloat(level) / 100 * (geometry.size.width - 14))
            }
            .gesture(
                DragGesture(minimumDistance: 0)
                    .onChanged { value in
                        let newLevel = Int(max(0, min(100, value.location.x / geometry.size.width * 100)))
                        onChange(newLevel)
                    }
            )
        }
        .frame(height: 16)
        .accessibilityElement()
        .accessibilityLabel("Level slider")
        .accessibilityValue("\(level) percent")
        .accessibilityAdjustableAction { direction in
            switch direction {
            case .increment:
                onChange(min(100, level + 10))
            case .decrement:
                onChange(max(0, level - 10))
            @unknown default:
                break
            }
        }
    }
}

/// Scene preview overlay
struct ScenePreviewView: View {
    let previewState: RoomVisualizationViewModel.ScenePreviewState?
    let onConfirm: () -> Void
    let onCancel: () -> Void

    var body: some View {
        if let state = previewState {
            VStack(spacing: 16) {
                Text("Preview: \(state.sceneName)")
                    .font(.system(size: 14, weight: .semibold))
                    .foregroundColor(.white)

                // Changes list
                VStack(alignment: .leading, spacing: 8) {
                    ForEach(state.changes, id: \.deviceName) { change in
                        HStack {
                            Text(change.deviceName)
                                .font(.system(size: 11))
                                .foregroundColor(.secondary)

                            Spacer()

                            Text("\(change.currentState) -> \(change.newState)")
                                .font(.system(size: 10, design: .monospaced))
                                .foregroundColor(.crystal)
                        }
                    }
                }
                .frame(maxWidth: 200)

                // Action buttons
                HStack(spacing: 12) {
                    Button("Cancel", action: onCancel)
                        .buttonStyle(.bordered)
                        .tint(.secondary)

                    Button("Activate", action: onConfirm)
                        .buttonStyle(.borderedProminent)
                        .tint(.crystal)
                }
            }
            .padding(16)
            .background(
                RoundedRectangle(cornerRadius: 16)
                    .fill(Color.black.opacity(0.9))
            )
            .overlay(
                RoundedRectangle(cornerRadius: 16)
                    .stroke(Color.crystal.opacity(0.3), lineWidth: 1)
            )
        }
    }
}

/// Room header with name and close button
struct RoomHeaderView: View {
    let room: RoomModel
    let onClose: () -> Void

    var body: some View {
        HStack {
            VStack(alignment: .leading, spacing: 2) {
                Text(room.name)
                    .font(.system(size: 16, weight: .semibold))
                    .foregroundColor(.white)

                Text(room.floor)
                    .font(.system(size: 11))
                    .foregroundColor(.secondary)
            }

            Spacer()

            // Status indicators
            HStack(spacing: 8) {
                if room.occupied {
                    Label("Occupied", systemImage: "person.fill")
                        .font(.system(size: 10))
                        .foregroundColor(.grove)
                }

                Text("\(room.avgLightLevel)%")
                    .font(.system(size: 12, design: .monospaced))
                    .foregroundColor(.beacon)
            }

            Button(action: onClose) {
                Image(systemName: "xmark.circle.fill")
                    .font(.system(size: 20))
                    .foregroundColor(.secondary)
            }
            .buttonStyle(.plain)
        }
        .padding(.horizontal, 16)
        .padding(.vertical, 10)
        .frame(width: 280)
        .background(
            Capsule()
                .fill(Color.black.opacity(0.8))
        )
    }
}

// MARK: - Preview

#Preview {
    RoomVisualizationView(room: RoomModel(
        id: "preview",
        name: "Living Room",
        floor: "Main Floor",
        lights: [
            Light(id: 1, name: "Main Light", level: 75),
            Light(id: 2, name: "Accent Light", level: 50)
        ],
        shades: [
            Shade(id: 1, name: "Window Shade", position: 80)
        ],
        audioZone: AudioZone(id: 1, name: "Living Room Speakers", isActive: true, source: "Spotify", volume: 60),
        hvac: HVACState(currentTemp: 72, targetTemp: 70, mode: "cool"),
        occupied: true
    ))
    .environmentObject(AppModel())
}

/*
 *
 * h(x) >= 0. Always.
 *
 * Each room is a world.
 * Each device is a conversation.
 * Control emerges from understanding.
 */
