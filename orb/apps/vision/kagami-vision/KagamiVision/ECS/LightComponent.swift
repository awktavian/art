//
// LightComponent.swift - Light Control ECS Component
//
// Colony: Nexus (e4) - Integration
//
// Features:
//   - Brightness control (0-100)
//   - Color temperature support
//   - Dimming animations
//   - Group light coordination
//   - Visual feedback with emissive materials
//
// Architecture:
//   LightControlComponent -> DeviceEntity -> RealityKit Scene
//   LightControlComponent -> LightControlSystem -> State Updates
//
// Created: December 31, 2025


import Foundation
import SwiftUI
import UIKit
import RealityKit
import Combine

// MARK: - Light Control Component

/// ECS Component for light device control
struct LightControlComponent: Component {

    // MARK: - Properties

    /// Current brightness level (0-100)
    var brightness: Int {
        didSet {
            brightness = max(0, min(100, brightness))
            normalizedBrightness = Float(brightness) / 100.0
        }
    }

    /// Normalized brightness (0.0-1.0)
    private(set) var normalizedBrightness: Float

    /// Whether the light is on
    var isOn: Bool {
        didSet {
            if !isOn && brightness > 0 {
                previousBrightness = brightness
            }
        }
    }

    /// Color temperature in Kelvin (2700K warm - 6500K cool)
    var colorTemperature: Int

    /// Transition duration for dimming (seconds)
    var transitionDuration: Float

    /// Stored brightness for restore after off/on
    private(set) var previousBrightness: Int

    /// Whether this light is part of a group
    var groupId: String?

    /// Light type for visualization
    var lightType: LightType

    // MARK: - Types

    enum LightType: String {
        case ceiling = "ceiling"
        case lamp = "lamp"
        case accent = "accent"
        case strip = "strip"
        case outdoor = "outdoor"

        var glowRadius: Float {
            switch self {
            case .ceiling: return 0.1
            case .lamp: return 0.06
            case .accent: return 0.03
            case .strip: return 0.08
            case .outdoor: return 0.15
            }
        }

        var emissiveIntensityMultiplier: Float {
            switch self {
            case .ceiling: return 1.0
            case .lamp: return 0.7
            case .accent: return 0.5
            case .strip: return 0.8
            case .outdoor: return 1.2
            }
        }
    }

    // MARK: - Initialization

    init(
        brightness: Int = 0,
        isOn: Bool = false,
        colorTemperature: Int = 3000,
        transitionDuration: Float = 0.3,
        lightType: LightType = .ceiling,
        groupId: String? = nil
    ) {
        self.brightness = max(0, min(100, brightness))
        self.normalizedBrightness = Float(brightness) / 100.0
        self.isOn = isOn
        self.colorTemperature = colorTemperature
        self.transitionDuration = transitionDuration
        self.previousBrightness = brightness > 0 ? brightness : 100
        self.lightType = lightType
        self.groupId = groupId
    }

    // MARK: - Computed Properties

    /// Color based on temperature (warm to cool)
    var temperatureColor: UIColor {
        let normalizedTemp = Float(colorTemperature - 2700) / Float(6500 - 2700)

        // Warm (2700K) = orange-ish, Cool (6500K) = blue-white
        let warmColor = UIColor(red: 1.0, green: 0.85, blue: 0.65, alpha: 1.0)
        let coolColor = UIColor(red: 0.9, green: 0.95, blue: 1.0, alpha: 1.0)

        return interpolateColor(from: warmColor, to: coolColor, progress: CGFloat(normalizedTemp))
    }

    /// Emissive intensity based on brightness and type
    var emissiveIntensity: Float {
        normalizedBrightness * lightType.emissiveIntensityMultiplier
    }

    // MARK: - Methods

    /// Calculates the visual state for rendering
    func visualState() -> LightVisualState {
        LightVisualState(
            brightness: normalizedBrightness,
            color: temperatureColor,
            emissiveIntensity: emissiveIntensity,
            glowRadius: lightType.glowRadius * normalizedBrightness,
            isOn: isOn
        )
    }

    /// Toggles the light on/off
    mutating func toggle() {
        if isOn {
            previousBrightness = brightness
            brightness = 0
            isOn = false
        } else {
            brightness = previousBrightness
            isOn = true
        }
    }

    /// Sets brightness with validation
    mutating func setBrightness(_ level: Int) {
        brightness = max(0, min(100, level))
        isOn = brightness > 0
    }

    /// Increments brightness by step
    mutating func incrementBrightness(by step: Int = 10) {
        setBrightness(brightness + step)
    }

    /// Decrements brightness by step
    mutating func decrementBrightness(by step: Int = 10) {
        setBrightness(brightness - step)
    }

    /// Sets color temperature with validation
    mutating func setColorTemperature(_ kelvin: Int) {
        colorTemperature = max(2700, min(6500, kelvin))
    }

    // MARK: - Helpers

    private func interpolateColor(from: UIColor, to: UIColor, progress: CGFloat) -> UIColor {
        var fromR: CGFloat = 0, fromG: CGFloat = 0, fromB: CGFloat = 0, fromA: CGFloat = 0
        var toR: CGFloat = 0, toG: CGFloat = 0, toB: CGFloat = 0, toA: CGFloat = 0

        from.getRed(&fromR, green: &fromG, blue: &fromB, alpha: &fromA)
        to.getRed(&toR, green: &toG, blue: &toB, alpha: &toA)

        let r = fromR + (toR - fromR) * progress
        let g = fromG + (toG - fromG) * progress
        let b = fromB + (toB - fromB) * progress

        return UIColor(red: r, green: g, blue: b, alpha: 1.0)
    }
}

// MARK: - Light Visual State

/// Visual representation state for rendering
struct LightVisualState {
    let brightness: Float
    let color: UIColor
    let emissiveIntensity: Float
    let glowRadius: Float
    let isOn: Bool

    /// Creates a material from the visual state
    func createMaterial() -> PhysicallyBasedMaterial {
        var material = PhysicallyBasedMaterial()

        if isOn {
            material.baseColor = .init(tint: color.withAlphaComponent(CGFloat(brightness)))
            material.emissiveColor = .init(color: color)
            material.emissiveIntensity = emissiveIntensity
        } else {
            material.baseColor = .init(tint: UIColor.gray.withAlphaComponent(0.3))
            material.emissiveIntensity = 0
        }

        material.roughness = 0.2
        material.metallic = 0.0

        return material
    }

    /// Creates a glow entity from the visual state
    func createGlowEntity() -> Entity? {
        guard isOn && glowRadius > 0.01 else { return nil }

        let glow = Entity()
        glow.name = "light-glow"

        let mesh = MeshResource.generateSphere(radius: glowRadius)

        var material = PhysicallyBasedMaterial()
        material.baseColor = .init(tint: color.withAlphaComponent(0.1))
        material.blending = .transparent(opacity: .init(floatLiteral: Float(brightness * 0.5)))

        glow.components.set(ModelComponent(mesh: mesh, materials: [material]))

        return glow
    }
}

// MARK: - Frame Rate Configuration

/// visionOS frame rate configuration for optimal performance
private enum VisionOSFrameRate {
    /// visionOS runs at 90fps for smooth spatial rendering
    static let targetFPS: Float = 90.0

    /// Frame duration in seconds (1/90 = ~11.11ms)
    static let frameDuration: Float = 1.0 / targetFPS

    /// Frame duration in nanoseconds for Task.sleep
    static let frameDurationNanos: UInt64 = 11_111_111  // ~11.11ms

    /// Frame budget in milliseconds - must complete all updates within this time
    static let frameBudgetMs: Float = 11.11

    /// Warning threshold - log when frame time exceeds this percentage of budget
    static let warningThreshold: Float = 0.8  // 80% of frame budget
}

// MARK: - Frame Rate Monitor

/// Monitors frame timing to ensure 90fps budget compliance
@MainActor
class FrameRateMonitor: ObservableObject {
    @Published var averageFrameTime: Float = 0
    @Published var isOverBudget: Bool = false
    @Published var droppedFrames: Int = 0

    private var frameTimes: [Float] = []
    private let sampleSize = 90  // Track last 90 frames (1 second at 90fps)
    private var lastFrameStart: CFAbsoluteTime = 0

    /// Call at start of frame update
    func beginFrame() {
        lastFrameStart = CFAbsoluteTimeGetCurrent()
    }

    /// Call at end of frame update
    func endFrame() {
        let frameTime = Float(CFAbsoluteTimeGetCurrent() - lastFrameStart) * 1000  // Convert to ms

        frameTimes.append(frameTime)
        if frameTimes.count > sampleSize {
            frameTimes.removeFirst()
        }

        averageFrameTime = frameTimes.reduce(0, +) / Float(frameTimes.count)

        // Check if over budget
        let budgetThreshold = VisionOSFrameRate.frameBudgetMs * VisionOSFrameRate.warningThreshold
        if frameTime > budgetThreshold {
            isOverBudget = true
            if frameTime > VisionOSFrameRate.frameBudgetMs {
                droppedFrames += 1
                print("Frame budget exceeded: \(frameTime)ms (budget: \(VisionOSFrameRate.frameBudgetMs)ms)")
            }
        } else {
            isOverBudget = false
        }
    }

    /// Returns frame budget utilization (0.0 - 1.0+)
    var budgetUtilization: Float {
        averageFrameTime / VisionOSFrameRate.frameBudgetMs
    }

    /// Resets monitoring statistics
    func reset() {
        frameTimes.removeAll()
        averageFrameTime = 0
        isOverBudget = false
        droppedFrames = 0
    }
}

// MARK: - Light Control System (RealityKit System)

/// Proper RealityKit ECS System for processing light component updates.
/// Conforms to RealityKit System protocol for automatic scene integration.
/// Optimized for visionOS 90fps rendering target.
@MainActor
class LightControlSystem: System {

    // MARK: - System Protocol Requirements

    static let query = EntityQuery(where: .has(LightControlComponent.self))

    /// Frame rate monitor for performance tracking
    static let frameMonitor = FrameRateMonitor()

    required init(scene: RealityKit.Scene) {}

    func update(context: SceneUpdateContext) {
        Self.frameMonitor.beginFrame()

        for entity in context.entities(matching: Self.query, updatingSystemWhen: .rendering) {
            guard let lightComponent = entity.components[LightControlComponent.self] else { continue }

            // Update visual representation
            Self.updateEntityVisuals(entity, with: lightComponent)
        }

        Self.frameMonitor.endFrame()
    }

    // MARK: - Visual Updates

    /// Updates entity visuals based on light component
    static func updateEntityVisuals(_ entity: Entity, with component: LightControlComponent) {
        let visualState = component.visualState()

        // Update main material using PhysicallyBasedMaterial (RealityKit standard)
        if var model = entity.components[ModelComponent.self] {
            model.materials = [visualState.createMaterial()]
            entity.components.set(model)
        }

        // Update or create glow
        updateGlow(for: entity, visualState: visualState)
    }

    private static func updateGlow(for entity: Entity, visualState: LightVisualState) {
        // Find existing glow
        let existingGlow = entity.children.first { $0.name == "light-glow" }

        if visualState.isOn {
            if let glow = existingGlow {
                // Update existing glow
                if var model = glow.components[ModelComponent.self],
                   var material = model.materials.first as? PhysicallyBasedMaterial {
                    material.baseColor = .init(tint: visualState.color.withAlphaComponent(0.1))
                    material.blending = .transparent(opacity: .init(floatLiteral: Float(visualState.brightness * 0.5)))
                    model.materials = [material]
                    glow.components.set(model)
                }
            } else if let newGlow = visualState.createGlowEntity() {
                entity.addChild(newGlow)
            }
        } else {
            existingGlow?.removeFromParent()
        }
    }

    /// Dims a light to a target over time, using correct 90fps timing for visionOS
    static func dimLight(
        entity: Entity,
        to targetBrightness: Int,
        duration: Float,
        completion: (() -> Void)? = nil
    ) {
        guard var component = entity.components[LightControlComponent.self] else { return }

        let startBrightness = component.brightness

        // Calculate steps for 90fps visionOS rendering (not 60fps!)
        let steps = Int(duration / VisionOSFrameRate.frameDuration)
        let brightnessStep = Float(targetBrightness - startBrightness) / Float(max(1, steps))

        // Animate dimming at 90fps
        Task { @MainActor in
            for step in 0...steps {
                frameMonitor.beginFrame()

                let newBrightness = startBrightness + Int(Float(step) * brightnessStep)
                component.setBrightness(newBrightness)
                entity.components.set(component)
                updateEntityVisuals(entity, with: component)

                frameMonitor.endFrame()

                // Sleep for 90fps frame duration (~11.11ms)
                try? await Task.sleep(nanoseconds: VisionOSFrameRate.frameDurationNanos)
            }

            completion?()
        }
    }

    /// Dims a light using a smooth easing function for more natural animation
    static func dimLightSmooth(
        entity: Entity,
        to targetBrightness: Int,
        duration: Float,
        easing: AnimationEasing = .easeInOut,
        completion: (() -> Void)? = nil
    ) {
        guard var component = entity.components[LightControlComponent.self] else { return }

        let startBrightness = Float(component.brightness)
        let endBrightness = Float(targetBrightness)
        let totalFrames = Int(duration * VisionOSFrameRate.targetFPS)

        Task { @MainActor in
            for frame in 0...totalFrames {
                let progress = Float(frame) / Float(totalFrames)
                let easedProgress = easing.apply(progress)

                let currentBrightness = Int(startBrightness + (endBrightness - startBrightness) * easedProgress)
                component.setBrightness(currentBrightness)
                entity.components.set(component)
                updateEntityVisuals(entity, with: component)

                try? await Task.sleep(nanoseconds: VisionOSFrameRate.frameDurationNanos)
            }

            completion?()
        }
    }

    /// Animation easing functions
    enum AnimationEasing {
        case linear
        case easeIn
        case easeOut
        case easeInOut

        func apply(_ t: Float) -> Float {
            switch self {
            case .linear:
                return t
            case .easeIn:
                return t * t
            case .easeOut:
                return 1 - (1 - t) * (1 - t)
            case .easeInOut:
                return t < 0.5 ? 2 * t * t : 1 - pow(-2 * t + 2, 2) / 2
            }
        }
    }
}

// MARK: - Light Group Manager

/// Manages groups of lights for coordinated control
class LightGroupManager {

    private var groups: [String: [Entity]] = [:]

    /// Registers an entity to a light group
    func register(_ entity: Entity, to groupId: String) {
        var group = groups[groupId] ?? []
        if !group.contains(where: { $0 === entity }) {
            group.append(entity)
            groups[groupId] = group
        }

        // Update entity's component
        if var component = entity.components[LightControlComponent.self] {
            component.groupId = groupId
            entity.components.set(component)
        }
    }

    /// Removes an entity from its group
    func unregister(_ entity: Entity) {
        guard let component = entity.components[LightControlComponent.self],
              let groupId = component.groupId else { return }

        groups[groupId]?.removeAll { $0 === entity }
    }

    /// Sets brightness for all lights in a group
    func setGroupBrightness(_ groupId: String, to brightness: Int) {
        guard let entities = groups[groupId] else { return }

        for entity in entities {
            guard var component = entity.components[LightControlComponent.self] else { continue }
            component.setBrightness(brightness)
            entity.components.set(component)
        }
    }

    /// Toggles all lights in a group
    func toggleGroup(_ groupId: String) {
        guard let entities = groups[groupId] else { return }

        // Check if any are on
        let anyOn = entities.contains { entity in
            entity.components[LightControlComponent.self]?.isOn ?? false
        }

        // If any are on, turn all off. Otherwise turn all on.
        for entity in entities {
            guard var component = entity.components[LightControlComponent.self] else { continue }
            if anyOn {
                component.isOn = false
                component.setBrightness(0)
            } else {
                component.isOn = true
                component.setBrightness(component.previousBrightness)
            }
            entity.components.set(component)
        }
    }

    /// Gets average brightness of a group
    func groupBrightness(_ groupId: String) -> Int {
        guard let entities = groups[groupId], !entities.isEmpty else { return 0 }

        let total = entities.reduce(0) { sum, entity in
            sum + (entity.components[LightControlComponent.self]?.brightness ?? 0)
        }

        return total / entities.count
    }
}

/*
 *
 * h(x) >= 0. Always.
 *
 * Light is the first element of home.
 * Brightness creates mood.
 * Temperature creates warmth.
 * Control creates comfort.
 */
