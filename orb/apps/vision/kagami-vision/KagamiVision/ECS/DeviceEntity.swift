//
// DeviceEntity.swift - RealityKit Entity for Smart Home Devices
//
// Colony: Nexus (e4) - Integration
//
// Features:
//   - Base entity class for all smart home devices
//   - Automatic component registration
//   - State synchronization with home controller
//   - Spatial interaction support
//   - Visual feedback for device state
//
// Architecture:
//   DeviceEntity -> Components (Light, Shade, Interaction)
//   DeviceEntity -> API Service -> Smart Home Controller
//
// Created: December 31, 2025


import Foundation
import SwiftUI
import UIKit
import RealityKit
import Combine

/// Base entity for smart home device visualization in RealityKit
class DeviceEntity: Entity, HasModel, HasCollision {

    // MARK: - Device Types

    enum DeviceType: String, CaseIterable {
        case light = "light"
        case shade = "shade"
        case thermostat = "thermostat"
        case audioZone = "audio_zone"
        case lock = "lock"
        case fireplace = "fireplace"
        case tv = "tv"
        case camera = "camera"

        var defaultSize: SIMD3<Float> {
            switch self {
            case .light: return SIMD3<Float>(0.03, 0.03, 0.03)
            case .shade: return SIMD3<Float>(0.06, 0.04, 0.005)
            case .thermostat: return SIMD3<Float>(0.04, 0.05, 0.01)
            case .audioZone: return SIMD3<Float>(0.04, 0.03, 0.04)
            case .lock: return SIMD3<Float>(0.02, 0.04, 0.02)
            case .fireplace: return SIMD3<Float>(0.08, 0.06, 0.04)
            case .tv: return SIMD3<Float>(0.12, 0.07, 0.01)
            case .camera: return SIMD3<Float>(0.025, 0.025, 0.03)
            }
        }

        var primaryColor: UIColor {
            switch self {
            case .light: return UIColor(.beacon)
            case .shade: return UIColor(.grove)
            case .thermostat: return UIColor(.flow)
            case .audioZone: return UIColor(.nexus)
            case .lock: return UIColor(.spark)
            case .fireplace: return UIColor(.spark)
            case .tv: return UIColor(.crystal)
            case .camera: return UIColor(.crystal)
            }
        }

        var iconName: String {
            switch self {
            case .light: return "lightbulb.fill"
            case .shade: return "blinds.horizontal.closed"
            case .thermostat: return "thermometer"
            case .audioZone: return "speaker.wave.2.fill"
            case .lock: return "lock.fill"
            case .fireplace: return "flame.fill"
            case .tv: return "tv.fill"
            case .camera: return "video.fill"
            }
        }
    }

    // MARK: - Device State

    struct DeviceState: Equatable {
        var isOn: Bool
        var level: Int  // 0-100 for dimmable devices
        var additionalData: [String: String]

        init(isOn: Bool = false, level: Int = 0, additionalData: [String: String] = [:]) {
            self.isOn = isOn
            self.level = level
            self.additionalData = additionalData
        }

        static let off = DeviceState(isOn: false, level: 0)
        static let on = DeviceState(isOn: true, level: 100)
    }

    // MARK: - Properties

    let deviceId: String
    let deviceType: DeviceType
    let deviceName: String
    let roomId: String

    private(set) var deviceState: DeviceState = .off
    private var stateUpdateCancellable: AnyCancellable?

    // Visual components
    private var glowEntity: Entity?
    private var labelEntity: Entity?
    private var particleEntity: Entity?

    // Proxemic scaling support
    private var baseScale: SIMD3<Float> = SIMD3<Float>(repeating: 1.0)

    /// Proxemic zone distances for scaling
    enum ProxemicDistance: Float {
        case intimate = 0.45    // < 45cm
        case personal = 1.2     // 45cm - 1.2m
        case social = 3.6       // 1.2m - 3.6m
        case publicZone = 7.5   // > 3.6m

        /// Scale factor for this proxemic zone
        var scaleFactor: Float {
            switch self {
            case .intimate: return 0.8    // Smaller when very close
            case .personal: return 1.0    // Normal scale at arm's reach
            case .social: return 1.5      // Larger at social distance
            case .publicZone: return 2.0  // Largest at public distance
            }
        }
    }

    // MARK: - Initialization

    required init() {
        self.deviceId = UUID().uuidString
        self.deviceType = .light
        self.deviceName = "Unknown Device"
        self.roomId = ""
        super.init()
    }

    init(
        id: String,
        type: DeviceType,
        name: String,
        roomId: String,
        initialState: DeviceState = .off
    ) {
        self.deviceId = id
        self.deviceType = type
        self.deviceName = name
        self.roomId = roomId
        self.deviceState = initialState

        super.init()

        self.name = "device-\(type.rawValue)-\(id)"

        setupEntity()
        setupComponents()
        updateVisualState()
    }

    // MARK: - Setup

    private func setupEntity() {
        // Create base mesh based on device type
        let mesh = createMesh(for: deviceType)
        let material = createMaterial(for: deviceType, state: deviceState)

        let modelComponent = ModelComponent(mesh: mesh, materials: [material])
        self.components.set(modelComponent)

        // Add collision for interaction
        let collisionShape = ShapeResource.generateBox(size: deviceType.defaultSize * 1.5)
        self.components.set(CollisionComponent(shapes: [collisionShape]))

        // Make interactive
        self.components.set(InputTargetComponent())
        self.components.set(HoverEffectComponent())

        // Add glow effect for active devices
        setupGlowEffect()

        // Setup accessibility
        setupAccessibility()
    }

    private func setupComponents() {
        // Add device-specific components
        switch deviceType {
        case .light:
            let lightComponent = LightControlComponent(brightness: deviceState.level)
            self.components.set(lightComponent)

        case .shade:
            let shadeComponent = ShadeControlComponent(position: deviceState.level)
            self.components.set(shadeComponent)

        default:
            break
        }

        // Add interaction component to all devices
        let interactionComponent = InteractionComponent(deviceType: deviceType)
        self.components.set(interactionComponent)
    }

    private func createMesh(for type: DeviceType) -> MeshResource {
        let size = type.defaultSize

        switch type {
        case .light:
            return MeshResource.generateSphere(radius: size.x)

        case .shade:
            return MeshResource.generateBox(size: size, cornerRadius: 0.002)

        case .thermostat:
            return MeshResource.generateBox(size: size, cornerRadius: 0.005)

        case .audioZone:
            return MeshResource.generateCylinder(height: size.y, radius: size.x / 2)

        case .lock:
            return MeshResource.generateBox(size: size, cornerRadius: 0.003)

        case .fireplace:
            return MeshResource.generateBox(size: size, cornerRadius: 0.01)

        case .tv:
            return MeshResource.generateBox(size: size, cornerRadius: 0.002)

        case .camera:
            return MeshResource.generateCylinder(height: size.z, radius: size.x / 2)
        }
    }

    private func createMaterial(for type: DeviceType, state: DeviceState) -> PhysicallyBasedMaterial {
        var material = PhysicallyBasedMaterial()

        let baseOpacity = state.isOn ? 0.9 : 0.5
        material.baseColor = .init(tint: type.primaryColor.withAlphaComponent(baseOpacity))

        if state.isOn {
            let emissiveIntensity = Float(state.level) / 100
            material.emissiveColor = .init(color: type.primaryColor)
            material.emissiveIntensity = emissiveIntensity
        }

        material.roughness = 0.3
        material.metallic = 0.1

        return material
    }

    private func setupGlowEffect() {
        guard deviceType == .light || deviceType == .fireplace else { return }

        let glow = Entity()
        glow.name = "glow"

        let glowSize = deviceType.defaultSize.x * 3
        let glowMesh = MeshResource.generateSphere(radius: glowSize)

        var glowMaterial = PhysicallyBasedMaterial()
        glowMaterial.baseColor = .init(tint: deviceType.primaryColor.withAlphaComponent(0.1))
        glowMaterial.blending = .transparent(opacity: .init(floatLiteral: 0.3))

        glow.components.set(ModelComponent(mesh: glowMesh, materials: [glowMaterial]))
        glow.isEnabled = deviceState.isOn

        self.addChild(glow)
        self.glowEntity = glow
    }

    private func setupAccessibility() {
        // Use SpatialEntityAccessibility pattern for consistent accessibility
        let spatialAccessibility = SpatialEntityAccessibility(
            label: "\(deviceName), \(deviceType.rawValue)",
            hint: "Look at and pinch to toggle. Current state: \(stateDescription)",
            traits: .button,
            customActions: ["Toggle", "Set to 50%", "Set to 100%"]
        )

        var accessibilityComponent = AccessibilityComponent()
        accessibilityComponent.label = LocalizedStringResource(stringLiteral: spatialAccessibility.label)
        accessibilityComponent.value = LocalizedStringResource(stringLiteral: stateDescription)
        accessibilityComponent.isAccessibilityElement = true
        accessibilityComponent.traits = [.button]

        self.components.set(accessibilityComponent)

        // Add visual pattern for color-blind accessibility (differentiateWithoutColor)
        addAccessibilityPattern()
    }

    /// Adds visual patterns/icons to device for color-blind accessibility
    private func addAccessibilityPattern() {
        // Create icon indicator entity for differentiateWithoutColor mode
        // This provides shape-based state indication alongside color
        let iconEntity = Entity()
        iconEntity.name = "accessibility-icon"

        // Position icon slightly above device
        iconEntity.position = SIMD3<Float>(0, deviceType.defaultSize.y + 0.01, 0)

        // Icon will be visible to provide secondary visual cue
        // The actual icon rendering would use a texture with the device type icon
        // For now, we create a small sphere as a state indicator
        let indicatorSize: Float = 0.008
        let mesh = MeshResource.generateSphere(radius: indicatorSize)

        var material = PhysicallyBasedMaterial()
        // White indicator with pattern - always visible regardless of color perception
        material.baseColor = .init(tint: .white)
        material.emissiveColor = .init(color: .white)
        material.emissiveIntensity = 0.3

        iconEntity.components.set(ModelComponent(mesh: mesh, materials: [material]))
        self.addChild(iconEntity)
    }

    // MARK: - State Management

    var stateDescription: String {
        if !deviceState.isOn {
            return "Off"
        }

        switch deviceType {
        case .light:
            return "\(deviceState.level)% brightness"
        case .shade:
            return "\(deviceState.level)% open"
        case .thermostat:
            if let temp = deviceState.additionalData["currentTemp"] {
                return "\(temp) degrees"
            }
            return "Active"
        case .audioZone:
            if let source = deviceState.additionalData["source"] {
                return "Playing \(source)"
            }
            return "Active"
        case .lock:
            return deviceState.isOn ? "Locked" : "Unlocked"
        case .fireplace:
            return "On"
        case .tv:
            return "On"
        case .camera:
            return "Recording"
        }
    }

    func updateState(_ newState: DeviceState) {
        guard newState != deviceState else { return }

        let oldState = deviceState
        deviceState = newState

        // Update visual representation
        updateVisualState()

        // Update components
        updateComponents()

        // Notify observers
        NotificationCenter.default.post(
            name: .deviceStateChanged,
            object: self,
            userInfo: ["oldState": oldState, "newState": newState]
        )
    }

    private func updateVisualState() {
        // Update material
        let material = createMaterial(for: deviceType, state: deviceState)
        if var model = self.components[ModelComponent.self] {
            model.materials = [material]
            self.components.set(model)
        }

        // Update glow
        glowEntity?.isEnabled = deviceState.isOn

        // Update accessibility
        if var accessibility = self.components[AccessibilityComponent.self] {
            accessibility.value = LocalizedStringResource(stringLiteral: stateDescription)
            self.components.set(accessibility)
        }
    }

    private func updateComponents() {
        // Update light component
        if var lightComponent = self.components[LightControlComponent.self] {
            lightComponent.brightness = deviceState.level
            lightComponent.isOn = deviceState.isOn
            self.components.set(lightComponent)
        }

        // Update shade component
        if var shadeComponent = self.components[ShadeControlComponent.self] {
            shadeComponent.position = deviceState.level
            self.components.set(shadeComponent)
        }
    }

    // MARK: - Actions

    func toggle() {
        let newState = DeviceState(
            isOn: !deviceState.isOn,
            level: deviceState.isOn ? 0 : 100,
            additionalData: deviceState.additionalData
        )
        updateState(newState)
    }

    func setLevel(_ level: Int) {
        let clampedLevel = max(0, min(100, level))
        let newState = DeviceState(
            isOn: clampedLevel > 0,
            level: clampedLevel,
            additionalData: deviceState.additionalData
        )
        updateState(newState)
    }

    func turnOn() {
        updateState(DeviceState(isOn: true, level: 100, additionalData: deviceState.additionalData))
    }

    func turnOff() {
        updateState(DeviceState(isOn: false, level: 0, additionalData: deviceState.additionalData))
    }

    // MARK: - Visual Effects

    func showSelectionHighlight(_ show: Bool) {
        let scale: Float = show ? 1.15 : 1.0

        // Animate scale change
        if show {
            self.scale = SIMD3<Float>(repeating: scale)

            // Add selection particle effect
            if particleEntity == nil {
                let particles = Entity()
                particles.name = "selection-particles"

                var particleComponent = ParticleEmitterComponent()
                particleComponent.emitterShape = .sphere
                particleComponent.emitterShapeSize = deviceType.defaultSize * 2
                // Configure particle emission via main emitter
                particleComponent.mainEmitter.birthRate = 20
                particleComponent.mainEmitter.lifeSpan = 1
                particleComponent.speed = 0.01
                // Crystal color with opacity for particles
                let crystalColor = SIMD4<Float>(0.4, 0.83, 0.89, 0.5) // #67d4e4 at 50% opacity
                particleComponent.mainEmitter.color = .constant(.single(.init(red: CGFloat(crystalColor.x), green: CGFloat(crystalColor.y), blue: CGFloat(crystalColor.z), alpha: CGFloat(crystalColor.w))))
                particleComponent.mainEmitter.size = 0.003

                particles.components.set(particleComponent)
                self.addChild(particles)
                particleEntity = particles
            }
        } else {
            self.scale = SIMD3<Float>(repeating: scale)
            particleEntity?.removeFromParent()
            particleEntity = nil
        }
    }

    func animateStateChange() {
        // Quick scale pulse animation using Fibonacci 144ms (micro)
        let originalScale = self.scale

        self.scale = originalScale * 1.2

        // Would use RealityKit animation in production
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.144) { [weak self] in
            self?.scale = originalScale
        }
    }

    // MARK: - Proxemic Scaling

    /// Updates the device scale based on distance to user's head position
    /// - Parameter userPosition: The user's head position in world coordinates
    func updateProxemicScale(userPosition: SIMD3<Float>) {
        let devicePosition = self.position(relativeTo: nil)
        let distance = simd_length(userPosition - devicePosition)

        let zone = proxemicZone(for: distance)
        let targetScale = baseScale * zone.scaleFactor

        // Smooth scale transition - Fibonacci 233ms
        self.scale = targetScale
    }

    /// Determines the proxemic zone based on distance
    private func proxemicZone(for distance: Float) -> ProxemicDistance {
        switch distance {
        case 0..<ProxemicDistance.intimate.rawValue:
            return .intimate
        case ProxemicDistance.intimate.rawValue..<ProxemicDistance.personal.rawValue:
            return .personal
        case ProxemicDistance.personal.rawValue..<ProxemicDistance.social.rawValue:
            return .social
        default:
            return .publicZone
        }
    }

    /// Sets the base scale for proxemic calculations
    func setBaseScale(_ scale: SIMD3<Float>) {
        baseScale = scale
        self.scale = scale
    }

    // MARK: - Factory Methods

    /// Creates a device entity from API data
    static func fromLight(_ light: Light, roomId: String) -> DeviceEntity {
        DeviceEntity(
            id: String(light.id),
            type: .light,
            name: light.name,
            roomId: roomId,
            initialState: DeviceState(isOn: light.isOn, level: light.level)
        )
    }

    static func fromShade(_ shade: Shade, roomId: String) -> DeviceEntity {
        DeviceEntity(
            id: String(shade.id),
            type: .shade,
            name: shade.name,
            roomId: roomId,
            initialState: DeviceState(isOn: shade.position > 0, level: shade.position)
        )
    }

    static func fromAudioZone(_ zone: AudioZone, roomId: String) -> DeviceEntity {
        var additionalData: [String: String] = [:]
        if let source = zone.source {
            additionalData["source"] = source
        }

        return DeviceEntity(
            id: String(zone.id),
            type: .audioZone,
            name: zone.name,
            roomId: roomId,
            initialState: DeviceState(
                isOn: zone.isActive,
                level: zone.volume,
                additionalData: additionalData
            )
        )
    }

    static func fromHVAC(_ hvac: HVACState, roomId: String) -> DeviceEntity {
        DeviceEntity(
            id: "hvac-\(roomId)",
            type: .thermostat,
            name: "Thermostat",
            roomId: roomId,
            initialState: DeviceState(
                isOn: hvac.mode != "off",
                level: Int(hvac.targetTemp),
                additionalData: [
                    "currentTemp": String(Int(hvac.currentTemp)),
                    "mode": hvac.mode
                ]
            )
        )
    }
}

// MARK: - Notification Names

extension Notification.Name {
    static let deviceStateChanged = Notification.Name("deviceStateChanged")
}

/*
 *
 * h(x) >= 0. Always.
 *
 * Every device is an entity.
 * Every entity has state.
 * State change flows through the system.
 * The interface reflects reality.
 */
