//
// ShadeComponent.swift - Shade Control ECS Component
//
// Colony: Grove (e6) - Research
//
// Features:
//   - Position control (0=closed, 100=open)
//   - Tilt angle support for blinds
//   - Animation for shade movement
//   - Group coordination for multi-shade windows
//   - Visual mesh deformation
//
// Architecture:
//   ShadeControlComponent -> DeviceEntity -> RealityKit Scene
//   ShadeControlComponent -> ShadeControlSystem -> State Updates
//
// Created: December 31, 2025


import Foundation
import SwiftUI
import UIKit
import RealityKit
import Combine

// MARK: - Shade Control Component

/// ECS Component for shade/blind device control
struct ShadeControlComponent: Component {

    // MARK: - Properties

    /// Current position (0=fully closed, 100=fully open)
    var position: Int {
        didSet {
            position = max(0, min(100, position))
            normalizedPosition = Float(position) / 100.0
        }
    }

    /// Normalized position (0.0-1.0)
    private(set) var normalizedPosition: Float

    /// Tilt angle for venetian blinds (-90 to 90 degrees)
    var tiltAngle: Int

    /// Shade type for visualization
    var shadeType: ShadeType

    /// Whether the shade is currently moving
    var isMoving: Bool

    /// Movement direction (1 = opening, -1 = closing, 0 = stopped)
    var movementDirection: Int

    /// Transition duration for movement (seconds)
    var transitionDuration: Float

    /// Target position during movement
    var targetPosition: Int?

    /// Group ID for coordinated control
    var groupId: String?

    /// Whether this shade has tilt capability
    var supportsTilt: Bool

    // MARK: - Types

    enum ShadeType: String {
        case roller = "roller"
        case venetian = "venetian"
        case cellular = "cellular"
        case roman = "roman"
        case curtain = "curtain"
        case exterior = "exterior"

        var meshHeight: Float {
            switch self {
            case .roller: return 0.04
            case .venetian: return 0.045
            case .cellular: return 0.04
            case .roman: return 0.05
            case .curtain: return 0.06
            case .exterior: return 0.05
            }
        }

        var meshWidth: Float {
            return 0.06
        }

        var thickness: Float {
            switch self {
            case .roller: return 0.003
            case .venetian: return 0.005
            case .cellular: return 0.008
            case .roman: return 0.006
            case .curtain: return 0.004
            case .exterior: return 0.01
            }
        }

        var supportsTilt: Bool {
            switch self {
            case .venetian, .exterior:
                return true
            default:
                return false
            }
        }

        var baseColor: UIColor {
            switch self {
            case .roller: return UIColor(.grove.opacity(0.9))
            case .venetian: return UIColor.white.withAlphaComponent(0.9)
            case .cellular: return UIColor(.crystal.opacity(0.8))
            case .roman: return UIColor(.nexus.opacity(0.8))
            case .curtain: return UIColor(.flow.opacity(0.8))
            case .exterior: return UIColor.gray.withAlphaComponent(0.9)
            }
        }
    }

    // MARK: - Initialization

    init(
        position: Int = 0,
        tiltAngle: Int = 0,
        shadeType: ShadeType = .roller,
        transitionDuration: Float = 1.0,
        groupId: String? = nil
    ) {
        self.position = max(0, min(100, position))
        self.normalizedPosition = Float(position) / 100.0
        self.tiltAngle = max(-90, min(90, tiltAngle))
        self.shadeType = shadeType
        self.isMoving = false
        self.movementDirection = 0
        self.transitionDuration = transitionDuration
        self.targetPosition = nil
        self.groupId = groupId
        self.supportsTilt = shadeType.supportsTilt
    }

    // MARK: - Computed Properties

    /// Visual height based on position (0 = full height, 100 = minimal height)
    var visualHeight: Float {
        let minHeight: Float = 0.005  // Never fully disappear
        let maxHeight = shadeType.meshHeight
        return minHeight + (maxHeight - minHeight) * (1 - normalizedPosition)
    }

    /// Visual y-offset for shade position
    var visualYOffset: Float {
        // Shade drops from top
        return (shadeType.meshHeight - visualHeight) / 2
    }

    /// Whether the shade is fully closed
    var isClosed: Bool {
        position == 0
    }

    /// Whether the shade is fully open
    var isOpen: Bool {
        position == 100
    }

    /// String description of current state
    var stateDescription: String {
        if isMoving {
            return movementDirection > 0 ? "Opening..." : "Closing..."
        }
        if isClosed { return "Closed" }
        if isOpen { return "Open" }
        return "\(position)% open"
    }

    // MARK: - Methods

    /// Calculates visual state for rendering
    func visualState() -> ShadeVisualState {
        ShadeVisualState(
            height: visualHeight,
            yOffset: visualYOffset,
            width: shadeType.meshWidth,
            thickness: shadeType.thickness,
            tiltAngle: supportsTilt ? Float(tiltAngle) : 0.0,
            color: shadeType.baseColor,
            isMoving: isMoving,
            position: normalizedPosition
        )
    }

    /// Opens the shade fully
    mutating func open() {
        startMovement(to: 100)
    }

    /// Closes the shade fully
    mutating func close() {
        startMovement(to: 0)
    }

    /// Sets position to specific value
    mutating func setPosition(_ newPosition: Int) {
        if newPosition != position {
            startMovement(to: newPosition)
        }
    }

    /// Starts movement to target position
    mutating func startMovement(to target: Int) {
        let clampedTarget = max(0, min(100, target))
        if clampedTarget == position {
            stopMovement()
            return
        }

        targetPosition = clampedTarget
        movementDirection = clampedTarget > position ? 1 : -1
        isMoving = true
    }

    /// Stops current movement
    mutating func stopMovement() {
        isMoving = false
        movementDirection = 0
        targetPosition = nil
    }

    /// Updates position during movement
    mutating func updateMovement(deltaTime: Float) {
        guard isMoving, let target = targetPosition else { return }

        let speed = 100.0 / transitionDuration * deltaTime
        let newPosition: Float

        if movementDirection > 0 {
            newPosition = min(Float(target), Float(position) + speed)
        } else {
            newPosition = max(Float(target), Float(position) - speed)
        }

        position = Int(newPosition)

        // Check if reached target
        if position == target {
            stopMovement()
        }
    }

    /// Sets tilt angle for venetian blinds
    mutating func setTilt(_ angle: Int) {
        guard supportsTilt else { return }
        tiltAngle = max(-90, min(90, angle))
    }

    /// Toggles between open and closed
    mutating func toggle() {
        if position > 50 {
            close()
        } else {
            open()
        }
    }
}

// MARK: - Shade Visual State

/// Visual representation state for rendering
struct ShadeVisualState {
    let height: Float
    let yOffset: Float
    let width: Float
    let thickness: Float
    let tiltAngle: Float
    let color: UIColor
    let isMoving: Bool
    let position: Float

    /// Creates a mesh for the shade
    func createMesh() -> MeshResource {
        MeshResource.generateBox(
            size: SIMD3<Float>(width, height, thickness),
            cornerRadius: 0.001
        )
    }

    /// Creates material for the shade
    func createMaterial() -> PhysicallyBasedMaterial {
        var material = PhysicallyBasedMaterial()

        // Adjust color based on position (more light through when open)
        let adjustedAlpha = 0.5 + (1 - position) * 0.4
        material.baseColor = .init(tint: color.withAlphaComponent(CGFloat(adjustedAlpha)))
        material.roughness = 0.7
        material.metallic = 0.0

        return material
    }

    /// Creates rotation for tilt
    func tiltRotation() -> simd_quatf {
        simd_quatf(angle: tiltAngle * .pi / 180, axis: SIMD3<Float>(1, 0, 0))
    }
}

// MARK: - Shade Control System (RealityKit System)

/// Proper RealityKit ECS System for processing shade component updates.
/// Conforms to RealityKit System protocol for automatic scene integration.
@MainActor
class ShadeControlSystem: System {

    // MARK: - System Protocol Requirements

    static let query = EntityQuery(where: .has(ShadeControlComponent.self))

    required init(scene: RealityKit.Scene) {}

    func update(context: SceneUpdateContext) {
        let deltaTime = Float(context.deltaTime)

        for entity in context.entities(matching: Self.query, updatingSystemWhen: .rendering) {
            guard var shadeComponent = entity.components[ShadeControlComponent.self] else { continue }

            // Update movement animation
            if shadeComponent.isMoving {
                shadeComponent.updateMovement(deltaTime: deltaTime)
                entity.components.set(shadeComponent)
            }

            // Update visual representation using PhysicallyBasedMaterial
            Self.updateEntityVisuals(entity, with: shadeComponent)
        }
    }

    // MARK: - Visual Updates

    /// Updates entity visuals based on shade component
    static func updateEntityVisuals(_ entity: Entity, with component: ShadeControlComponent) {
        let visualState = component.visualState()

        // Update mesh and material using PhysicallyBasedMaterial (RealityKit standard)
        if var model = entity.components[ModelComponent.self] {
            model.mesh = visualState.createMesh()
            model.materials = [visualState.createMaterial()]
            entity.components.set(model)
        }

        // Update position offset
        entity.position.y = visualState.yOffset

        // Update tilt rotation
        if component.supportsTilt {
            entity.orientation = visualState.tiltRotation()
        }

        // Update collision shape for interaction
        let collisionShape = ShapeResource.generateBox(
            size: SIMD3<Float>(visualState.width * 1.2, visualState.height * 1.2, visualState.thickness * 2)
        )
        entity.components.set(CollisionComponent(shapes: [collisionShape]))
    }

    /// Animates shade to target position
    static func animateShade(
        entity: Entity,
        to targetPosition: Int,
        duration: Float,
        completion: (() -> Void)? = nil
    ) {
        guard var component = entity.components[ShadeControlComponent.self] else { return }

        component.transitionDuration = duration
        component.startMovement(to: targetPosition)
        entity.components.set(component)

        // Monitor completion
        Task { @MainActor in
            while entity.components[ShadeControlComponent.self]?.isMoving == true {
                try? await Task.sleep(nanoseconds: 50_000_000)
            }
            completion?()
        }
    }
}

// MARK: - Shade Group Manager

/// Manages groups of shades for coordinated control
class ShadeGroupManager {

    private var groups: [String: [Entity]] = [:]

    /// Registers an entity to a shade group
    func register(_ entity: Entity, to groupId: String) {
        var group = groups[groupId] ?? []
        if !group.contains(where: { $0 === entity }) {
            group.append(entity)
            groups[groupId] = group
        }

        // Update entity's component
        if var component = entity.components[ShadeControlComponent.self] {
            component.groupId = groupId
            entity.components.set(component)
        }
    }

    /// Removes an entity from its group
    func unregister(_ entity: Entity) {
        guard let component = entity.components[ShadeControlComponent.self],
              let groupId = component.groupId else { return }

        groups[groupId]?.removeAll { $0 === entity }
    }

    /// Sets position for all shades in a group
    func setGroupPosition(_ groupId: String, to position: Int) {
        guard let entities = groups[groupId] else { return }

        for entity in entities {
            guard var component = entity.components[ShadeControlComponent.self] else { continue }
            component.setPosition(position)
            entity.components.set(component)
        }
    }

    /// Opens all shades in a group
    func openGroup(_ groupId: String) {
        setGroupPosition(groupId, to: 100)
    }

    /// Closes all shades in a group
    func closeGroup(_ groupId: String) {
        setGroupPosition(groupId, to: 0)
    }

    /// Sets tilt for all shades in a group (if supported)
    func setGroupTilt(_ groupId: String, to angle: Int) {
        guard let entities = groups[groupId] else { return }

        for entity in entities {
            guard var component = entity.components[ShadeControlComponent.self] else { continue }
            component.setTilt(angle)
            entity.components.set(component)
        }
    }

    /// Gets average position of a group
    func groupPosition(_ groupId: String) -> Int {
        guard let entities = groups[groupId], !entities.isEmpty else { return 0 }

        let total = entities.reduce(0) { sum, entity in
            sum + (entity.components[ShadeControlComponent.self]?.position ?? 0)
        }

        return total / entities.count
    }

    /// Checks if any shade in group is moving
    func isGroupMoving(_ groupId: String) -> Bool {
        guard let entities = groups[groupId] else { return false }

        return entities.contains { entity in
            entity.components[ShadeControlComponent.self]?.isMoving ?? false
        }
    }
}

// MARK: - Shade Presets

/// Common shade position presets
enum ShadePreset: String, CaseIterable {
    case closed = "closed"
    case quarterOpen = "quarter"
    case halfOpen = "half"
    case threeQuarterOpen = "three_quarter"
    case fullyOpen = "open"

    var position: Int {
        switch self {
        case .closed: return 0
        case .quarterOpen: return 25
        case .halfOpen: return 50
        case .threeQuarterOpen: return 75
        case .fullyOpen: return 100
        }
    }

    var displayName: String {
        switch self {
        case .closed: return "Closed"
        case .quarterOpen: return "25% Open"
        case .halfOpen: return "Half Open"
        case .threeQuarterOpen: return "75% Open"
        case .fullyOpen: return "Fully Open"
        }
    }
}

/*
 *
 * h(x) >= 0. Always.
 *
 * Shades control light from outside.
 * Position controls privacy.
 * Tilt controls glare.
 * Movement should be smooth, natural.
 */
